#!/usr/bin/env python3
"""crew-state.py —— CREW 流程狀態的單一寫者 CLI。

`.spec/{slug}/state.json` 是 CREW 任務流程狀態的唯一權威來源。
所有 skill 一律呼叫本 script 讀寫，**禁止 LLM 手寫 state.json**
（手寫 JSON 是欄位漂移與 parse 失敗的主因）。

設計要點：
  - 原子寫入：先寫 `.state.json.tmp` 再 `os.replace()`，永遠不會留下半截檔案
  - 併發保護：`fcntl.flock` 鎖 `.state.lock`，非阻塞、退避重試 3 次
  - 決策表內建：`next` 子命令用 Python 實作流程決策，LLM 不必讀表推理
  - 自我修復：`rebuild` 依「現存 state → git log → 檔案系統」重建，推測欄位標 `inferred: true`
  - 零 token 開場：`session-brief` 在無未結案任務時輸出空字串並 exit 0

退出碼：
  0 = 成功（`session-brief` 任何情況都是 0）
  1 = 使用者層級錯誤（找不到任務、參數不合法、validate 未通過）
  3 = 環境問題（取不到檔案鎖、無法寫入）

`results` 慣用鍵（`next` 決策會讀）：
  results.verify.status  = PASS | WARN | FAIL      results.verify.health_score = int
  results.review.critical = int（🔴 數量）          results.review.warnings = int
  results.security.critical = int
"""

import argparse
import contextlib
import fcntl
import json
import os
import re
import select
import signal
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

SCHEMA_VERSION = 1

# 流程步驟（順序即流程順序）
STEPS = ["start", "spec", "db", "arch", "build", "security", "verify", "review", "close"]
STATUSES = ["pending", "in_progress", "done", "skipped", "failed"]
DONE_LIKE = {"done", "skipped"}  # skipped 取代舊版「DB_REQUIRED=false 就沒檔案」的猜測

APPROVAL_GATES = ["requirement", "architecture", "uat"]
GATE_STATUSES = ["pending", "approved", "rejected", "waived"]
GATE_PASSED = {"approved", "waived"}
GATE_SOURCE_STEP = {
    "requirement": "spec",
    "architecture": "arch",
    "uat": "review",
}
TRANSITION_GATES = {
    "db": ["requirement"],
    "arch": ["requirement"],
    "build": ["requirement", "architecture"],
}

HISTORY_LIMIT = 50
LOCK_RETRIES = 3
LOCK_BACKOFF_SEC = 0.15
BRIEF_MAX_LINES = 3
# session-brief 掛在 SessionStart hook 上，慢一秒都是每次開 session 的成本。
# 兩道保險：讀 stdin 的短超時，以及整支子命令的總體超時。
BRIEF_STDIN_TIMEOUT = 0.2
BRIEF_TOTAL_TIMEOUT = 1.0

# 步驟 → 建議指令。v2 已把 plan-spec / plan-db / plan-arch 合併為 /plan 的三個 pass。
STEP_COMMAND = {
    "start": "/plan-start",
    "spec": "/plan spec",
    "db": "/plan db",
    "arch": "/plan arch",
    "build": "/plan-build",
    "security": "/plan-security",
    "verify": "/plan-verify",
    "review": "/plan-review",
    "close": "/plan-close",
}

# 舊版（v1）檔案 → 步驟，供 rebuild 從檔案系統推測
LEGACY_FILE_STEP = [
    ("README.md", "start"),
    ("plan.md", "start"),
    ("spec.md", "spec"),
    ("db.md", "db"),
    ("db.sql", "db"),
    ("deploy.sql", "db"),
    ("arch.md", "arch"),
    ("files.md", "build"),
    ("security.md", "security"),
    ("verify.md", "verify"),
    ("review.md", "review"),
]


class CrewError(Exception):
    """使用者層級錯誤，帶退出碼與修法說明。"""

    def __init__(self, message: str, fix: str = "", code: int = 1):
        super().__init__(message)
        self.message = message
        self.fix = fix
        self.code = code


# --------------------------------------------------------------------------
# 基礎工具
# --------------------------------------------------------------------------


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def parse_iso(value):
    if not value or not isinstance(value, str):
        return None
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.astimezone()
    return dt


def project_root(args) -> Path:
    raw = getattr(args, "project", None) or getattr(args, "cwd", None) or "."
    return Path(raw).expanduser().resolve()


def spec_root(project: Path) -> Path:
    return project / ".spec"


def spec_dir(project: Path, slug: str) -> Path:
    return spec_root(project) / slug


def state_path(project: Path, slug: str) -> Path:
    return spec_dir(project, slug) / "state.json"


@contextlib.contextmanager
def state_lock(directory: Path):
    """非阻塞檔案鎖，退避重試 3 次；仍拿不到就 exit 3。"""
    directory.mkdir(parents=True, exist_ok=True)
    lock_file = directory / ".state.lock"
    fd = os.open(str(lock_file), os.O_CREAT | os.O_RDWR, 0o644)
    acquired = False
    try:
        for attempt in range(LOCK_RETRIES):
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
                break
            except OSError:
                if attempt < LOCK_RETRIES - 1:
                    time.sleep(LOCK_BACKOFF_SEC * (2**attempt))
        if not acquired:
            raise CrewError(
                f"取不到狀態檔案鎖：{lock_file}（已重試 {LOCK_RETRIES} 次）",
                "修法：確認沒有其他 crew-state.py 正在寫同一個任務；"
                f"若確定無人使用，刪除 {lock_file} 後重跑",
                code=3,
            )
        yield
    finally:
        if acquired:
            try:
                fcntl.flock(fd, fcntl.LOCK_UN)
            except OSError:
                pass
        os.close(fd)


def read_state(project: Path, slug: str, required: bool = True):
    path = state_path(project, slug)
    if not path.exists():
        if not required:
            return None
        raise CrewError(
            f"找不到狀態檔：{path}",
            "修法：先跑 `crew-state.py init --slug <slug>` 建立，"
            "或用 `crew-state.py rebuild --slug <slug>` 從 git 與檔案系統重建",
        )
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        if not required:
            return None
        raise CrewError(
            f"狀態檔無法解析：{path}（{exc}）",
            "修法：跑 `crew-state.py rebuild --slug <slug>` 自我修復",
        )
    if not isinstance(data, dict):
        if not required:
            return None
        raise CrewError(
            f"狀態檔內容不是 JSON 物件：{path}",
            "修法：跑 `crew-state.py rebuild --slug <slug>` 自我修復",
        )
    return data


def write_state(project: Path, slug: str, state: dict) -> Path:
    """原子寫入：.state.json.tmp → os.replace()。"""
    directory = spec_dir(project, slug)
    directory.mkdir(parents=True, exist_ok=True)
    state["updated"] = now_iso()
    payload = json.dumps(state, ensure_ascii=False, indent=2) + "\n"
    tmp = directory / ".state.json.tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, directory / "state.json")
    except OSError as exc:
        raise CrewError(
            f"寫入狀態檔失敗：{directory / 'state.json'}（{exc}）",
            "修法：確認目錄存在且有寫入權限（ls -ld 該目錄）",
            code=3,
        )
    return directory / "state.json"


def new_state(slug: str, name: str = "", task_type: str = "feature") -> dict:
    stamp = now_iso()
    return {
        "schema_version": SCHEMA_VERSION,
        "slug": slug,
        "name": name or slug,
        "type": task_type,
        "inferred": False,
        "phase": "start",
        "next": {"command": None, "reason": ""},
        "steps": {
            step: {"status": "pending", "at": None, "commit": None, "reason": None}
            for step in STEPS
        },
        "work_unit": {
            "skill": None,
            "done": 0,
            "total": 0,
            "label": "",
            "remaining": [],
            "evidence": [],
            "ambiguities": [],
        },
        "gates": {
            gate: {
                "status": "pending",
                "at": None,
                "by": None,
                "reason": None,
            }
            for gate in APPROVAL_GATES
        },
        "resume_hint": {"branch": None, "services": [], "read_first": []},
        "results": {"verify": {}, "review": {}, "security": {}},
        "git": {"branch": None, "base": None, "last_commit": None},
        "notion": {"page_id": None, "mirrored_status": None, "last_synced_at": None},
        "deploy": {"steps_total": 0, "steps_confirmed": 0},
        "parked": None,
        "history": [],
        "created": stamp,
        "updated": stamp,
    }


def normalize(state: dict, slug: str = "") -> dict:
    """補齊缺漏欄位，讓舊檔／半殘檔也能安全操作。不改變已有值。

    Approval Gate 是向後相容擴充：舊 state 沒有 gates 時，
    已完成的 spec/arch 視為舊流程已通過對應人工確認，避免升級後卡住既有任務。
    """
    had_gates = isinstance(state.get("gates"), dict)
    base = new_state(slug or state.get("slug") or "unknown")
    for key, default in base.items():
        if key not in state:
            state[key] = default
        elif state[key] is None and key != "parked":
            # parked 的 None 是有意義的值（＝未擱置），不可被預設值覆蓋
            state[key] = default
    state["schema_version"] = SCHEMA_VERSION
    if slug:
        state["slug"] = slug

    steps = state.get("steps")
    if not isinstance(steps, dict):
        steps = {}
    for step in STEPS:
        entry = steps.get(step)
        if not isinstance(entry, dict):
            entry = {}
        entry.setdefault("status", "pending")
        if entry["status"] not in STATUSES:
            entry["status"] = "pending"
        for field in ("at", "commit", "reason"):
            entry.setdefault(field, None)
        steps[step] = entry
    state["steps"] = {step: steps[step] for step in STEPS}

    work_unit = state.get("work_unit")
    if not isinstance(work_unit, dict):
        work_unit = {}
    for field, default in base["work_unit"].items():
        work_unit.setdefault(field, default)
    state["work_unit"] = work_unit

    gates = state.get("gates")
    if not isinstance(gates, dict):
        gates = {}
    normalized_gates = {}
    for gate in APPROVAL_GATES:
        entry = gates.get(gate)
        if not isinstance(entry, dict):
            entry = {}
        status = entry.get("status", "pending")
        if status not in GATE_STATUSES:
            status = "pending"
        normalized_gates[gate] = {
            "status": status,
            "at": entry.get("at"),
            "by": entry.get("by"),
            "reason": entry.get("reason"),
        }
    state["gates"] = normalized_gates

    # 舊任務相容：舊流程 spec 完成代表需求已確認；arch 完成代表架構已通過舊流程。
    if not had_gates:
        for gate, source_step in (("requirement", "spec"), ("architecture", "arch")):
            if step_status(state, source_step) in DONE_LIKE:
                source = state["steps"][source_step]
                state["gates"][gate] = {
                    "status": "approved",
                    "at": source.get("at"),
                    "by": "migration",
                    "reason": f"legacy state：{source_step} 已完成於 approval gate 導入前",
                }
        if step_status(state, "close") in DONE_LIKE:
            state["gates"]["uat"] = {
                "status": "waived",
                "at": state["steps"]["close"].get("at"),
                "by": "migration",
                "reason": "legacy state：任務已於 approval gate 導入前結案",
            }

    for section in ("resume_hint", "git", "notion", "deploy", "results"):
        value = state.get(section)
        if not isinstance(value, dict):
            value = {}
        for field, default in base[section].items():
            value.setdefault(field, default)
        state[section] = value

    for kind in ("verify", "review", "security"):
        if not isinstance(state["results"].get(kind), dict):
            state["results"][kind] = {}

    if state.get("phase") not in STEPS:
        state["phase"] = "start"
    if not isinstance(state.get("history"), list):
        state["history"] = []
    if not isinstance(state.get("inferred"), bool):
        state["inferred"] = bool(state.get("inferred"))
    return state


def push_history(state: dict, event: str, detail: str = "") -> None:
    state.setdefault("history", []).append(
        {"at": now_iso(), "event": event, "detail": detail}
    )
    if len(state["history"]) > HISTORY_LIMIT:
        state["history"] = state["history"][-HISTORY_LIMIT:]


def step_status(state: dict, step: str) -> str:
    return (state.get("steps") or {}).get(step, {}).get("status", "pending")


def gate_status(state: dict, gate: str) -> str:
    return (state.get("gates") or {}).get(gate, {}).get("status", "pending")


def gate_passed(state: dict, gate: str) -> bool:
    return gate_status(state, gate) in GATE_PASSED


def transition_gate_failures(state: dict, step: str) -> list[str]:
    return [
        gate
        for gate in TRANSITION_GATES.get(step, [])
        if not gate_passed(state, gate)
    ]


def assert_transition_allowed(state: dict, step: str, target_status: str) -> None:
    """Runtime hard gate：進入／完成需要核准的 step 前先檢查 Approval Gate。"""
    if target_status not in {"in_progress", "done", "skipped"}:
        return
    blocked = transition_gate_failures(state, step)
    if not blocked:
        return
    detail = "、".join(f"{gate}={gate_status(state, gate)}" for gate in blocked)
    first = blocked[0]
    raise CrewError(
        f"{step} transition 被 Approval Gate 阻擋：{detail}",
        "修法：先取得人類明確核准，再執行 "
        f"`crew-state.py gate --slug {state.get('slug')} --name {first} "
        "--status approved --by human`；不得由執行 Agent 自行核准",
    )


def result_of(state: dict, kind: str) -> dict:
    value = (state.get("results") or {}).get(kind)
    return value if isinstance(value, dict) else {}


def as_int(value, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def split_list(raw):
    """把 `a,b,c` 或多次傳入的參數整理成字串清單。"""
    items = []
    for chunk in raw or []:
        for piece in str(chunk).split(","):
            piece = piece.strip()
            if piece:
                items.append(piece)
    return items


# --------------------------------------------------------------------------
# 決策表（原 plan-next/SKILL.md 的 18 列表格，改以 state.json 為判斷依據）
# --------------------------------------------------------------------------


def compute_next(state: dict) -> dict:
    """回傳 {"command": str|None, "reason": str}。第一個匹配的規則勝出。"""
    slug = state.get("slug") or "<slug>"
    result = _compute_next_rule(state, slug)
    if state.get("inferred"):
        result = dict(result)
        result["reason"] = "（狀態為推測，請確認）" + result["reason"]
    return result


def _compute_next_rule(state: dict, slug: str) -> dict:
    parked = state.get("parked")
    if parked:
        reason = ""
        if isinstance(parked, dict):
            reason = parked.get("reason") or ""
        return {
            "command": None,
            "reason": f"任務已擱置（{reason or '未註明原因'}）；要復工請跑 crew-state.py unpark --slug {slug}",
        }

    if step_status(state, "close") in DONE_LIKE:
        return {"command": None, "reason": "任務已結案（close 完成），可用 /plan-start 開新任務"}

    if step_status(state, "start") not in DONE_LIKE:
        return {"command": f"/plan-start {slug}", "reason": "任務尚未建立（start 未完成）"}

    # 斷點續跑優先（取代舊版 handoff.md 的「優先讀取」）
    work_unit = state.get("work_unit") or {}
    skill = work_unit.get("skill")
    total = as_int(work_unit.get("total"))
    done = as_int(work_unit.get("done"))
    if skill and total > 0 and done < total:
        command = skill if str(skill).startswith("/") else f"/{skill}"
        label = work_unit.get("label") or ""
        return {
            "command": f"{command} --resume",
            "reason": f"{skill} 中斷於 {done}/{total}{label}，先續跑未完成的工作單元",
        }

    if step_status(state, "spec") not in DONE_LIKE:
        return {"command": STEP_COMMAND["spec"], "reason": "規格（目標與驗收條件）尚未產出"}

    if not gate_passed(state, "requirement"):
        return {
            "command": None,
            "reason": "等待人類核准需求（requirement gate="
            f"{gate_status(state, 'requirement')}）；核准後才可進 DB／架構／實作",
        }

    if step_status(state, "db") not in DONE_LIKE:
        return {"command": STEP_COMMAND["db"], "reason": "DB 設計缺；不需要 DB 時把 db 標成 skipped"}

    if step_status(state, "arch") not in DONE_LIKE:
        return {"command": STEP_COMMAND["arch"], "reason": "架構決策尚未記錄"}

    if not gate_passed(state, "architecture"):
        return {
            "command": None,
            "reason": "等待人類核准架構（architecture gate="
            f"{gate_status(state, 'architecture')}）；核准後才可進實作",
        }

    if step_status(state, "build") not in DONE_LIKE:
        return {"command": STEP_COMMAND["build"], "reason": "設計已齊備，可進入程式碼產生階段"}

    verify = result_of(state, "verify")
    verify_status = str(verify.get("status") or "").upper()
    verify_done = step_status(state, "verify") in DONE_LIKE

    # verify FAIL 優先於下方任何缺檔判斷
    if verify_status == "FAIL":
        return {
            "command": STEP_COMMAND["build"],
            "reason": "驗收有 FAIL 項目要優先處理；修完再跑 /plan-verify --recheck",
        }
    if verify_status == "WARN":
        return {
            "command": "/plan-verify --recheck",
            "reason": "驗收有 WARN；可重驗，或確認可接受後改跑 /plan-review",
        }
    if verify_done and step_status(state, "review") not in DONE_LIKE:
        return {"command": STEP_COMMAND["review"], "reason": "驗收通過，程式碼審查尚未進行"}

    if step_status(state, "security") not in DONE_LIKE:
        return {"command": STEP_COMMAND["security"], "reason": "安全掃描缺"}

    if not verify_done:
        return {"command": STEP_COMMAND["verify"], "reason": "驗收條件尚未驗證"}

    review = result_of(state, "review")
    if as_int(review.get("critical")) > 0:
        return {
            "command": STEP_COMMAND["build"],
            "reason": f"審查有 {as_int(review.get('critical'))} 個 🔴 嚴重發現要先修",
        }
    if step_status(state, "review") in DONE_LIKE:
        if not gate_passed(state, "uat"):
            return {
                "command": None,
                "reason": "機器驗證與程式碼審查已完成，但仍等待人類 UAT 決策"
                f"（uat gate={gate_status(state, 'uat')}）；verify=PASS 不等於 UAT 通過",
            }
        return {"command": STEP_COMMAND["close"], "reason": "UAT 已通過，所有階段完成，可以結案"}

    return {"command": "/plan-status", "reason": "狀態無法對應到既定流程，先看任務清單確認"}


def refresh_next(state: dict) -> dict:
    state["next"] = compute_next(state)
    return state


def current_phase(state: dict) -> str:
    """最後一個已完成（或進行中）的步驟。"""
    phase = state.get("phase")
    return phase if phase in STEPS else "start"


# --------------------------------------------------------------------------
# 子命令：init / set / unit / result
# --------------------------------------------------------------------------


def cmd_init(args) -> int:
    project = project_root(args)
    slug = args.slug
    directory = spec_dir(project, slug)
    with state_lock(directory):
        existing = read_state(project, slug, required=False)
        if existing and not args.force:
            raise CrewError(
                f"狀態檔已存在：{state_path(project, slug)}",
                "修法：要覆蓋請加 --force；只想改欄位請用 `crew-state.py set`",
            )
        state = new_state(slug, args.name or slug, args.type)
        state["steps"]["start"] = {
            "status": "done",
            "at": now_iso(),
            "commit": args.commit or None,
            "reason": None,
        }
        state["phase"] = "start"
        if args.branch:
            state["git"]["branch"] = args.branch
            state["resume_hint"]["branch"] = args.branch
        if args.notion_page_id:
            state["notion"]["page_id"] = args.notion_page_id
        push_history(state, "init", f"type={args.type}")
        refresh_next(state)
        path = write_state(project, slug, state)
    print(f"✅ 已建立狀態檔：{path}")
    print(f"   下一步：{state['next']['command']}（{state['next']['reason']}）")
    return 0


def _apply_set(state: dict, args) -> list:
    changes = []

    if args.name:
        state["name"] = args.name
        changes.append(f"name={args.name}")
    if args.type:
        state["type"] = args.type
        changes.append(f"type={args.type}")

    if args.step:
        if not args.status:
            raise CrewError(
                "--step 必須搭配 --status",
                f"修法：加上 --status，可用值：{'/'.join(STATUSES)}",
            )
        assert_transition_allowed(state, args.step, args.status)
        entry = state["steps"][args.step]
        entry["status"] = args.status
        entry["at"] = args.at or now_iso()
        if args.commit:
            entry["commit"] = args.commit
        if args.reason is not None:
            entry["reason"] = args.reason
        changes.append(f"steps.{args.step}={args.status}")
        # skipped 不推進 phase（跳過的階段不是「現在在做的事」）
        if not args.phase and args.status != "skipped":
            state["phase"] = args.step

    if args.phase:
        assert_transition_allowed(state, args.phase, "in_progress")
        state["phase"] = args.phase
        changes.append(f"phase={args.phase}")

    if args.branch:
        state["git"]["branch"] = args.branch
        state["resume_hint"]["branch"] = args.branch
        changes.append(f"git.branch={args.branch}")
    if args.base:
        state["git"]["base"] = args.base
        changes.append(f"git.base={args.base}")
    if args.last_commit:
        state["git"]["last_commit"] = args.last_commit
        changes.append("git.last_commit")

    if args.notion_page_id:
        state["notion"]["page_id"] = args.notion_page_id
        changes.append("notion.page_id")
    if args.mirrored_status:
        state["notion"]["mirrored_status"] = args.mirrored_status
        changes.append(f"notion.mirrored_status={args.mirrored_status}")
    if args.synced_now:
        state["notion"]["last_synced_at"] = now_iso()
        changes.append("notion.last_synced_at")

    if args.deploy_total is not None:
        state["deploy"]["steps_total"] = args.deploy_total
        changes.append(f"deploy.steps_total={args.deploy_total}")
    if args.deploy_confirmed is not None:
        state["deploy"]["steps_confirmed"] = args.deploy_confirmed
        changes.append(f"deploy.steps_confirmed={args.deploy_confirmed}")

    if args.read_first:
        state["resume_hint"]["read_first"] = split_list(args.read_first)
        changes.append("resume_hint.read_first")
    if args.services:
        state["resume_hint"]["services"] = split_list(args.services)
        changes.append("resume_hint.services")

    if args.inferred is not None:
        state["inferred"] = args.inferred == "true"
        changes.append(f"inferred={state['inferred']}")

    if not changes:
        raise CrewError(
            "沒有指定任何要修改的欄位",
            "修法：至少給一個欄位參數，例如 --step build --status done；"
            "完整清單見 `crew-state.py set --help`",
        )
    return changes


def cmd_set(args) -> int:
    project = project_root(args)
    slug = args.slug
    with state_lock(spec_dir(project, slug)):
        state = normalize(read_state(project, slug), slug)
        changes = _apply_set(state, args)
        push_history(state, "set", "；".join(changes))
        refresh_next(state)
        write_state(project, slug, state)
    print(f"✅ {slug} 已更新：{'；'.join(changes)}")
    print(f"   phase={state['phase']}｜下一步：{state['next']['command']}")
    return 0


def cmd_gate(args) -> int:
    project = project_root(args)
    slug = args.slug
    with state_lock(spec_dir(project, slug)):
        state = normalize(read_state(project, slug), slug)
        gate = state["gates"][args.name]

        source_step = GATE_SOURCE_STEP.get(args.name)
        if args.status != "pending" and source_step and step_status(state, source_step) not in DONE_LIKE:
            raise CrewError(
                f"{args.name} gate 尚不能設定為 {args.status}：{source_step} 尚未完成",
                f"修法：先完成 {STEP_COMMAND[source_step]}，再由人類做核准決策",
            )
        if args.status == "waived" and not args.reason:
            raise CrewError(
                "waived 必須提供 --reason",
                "修法：說明為何可以略過此人工核准，留下可稽核紀錄",
            )

        gate["status"] = args.status
        gate["at"] = now_iso()
        gate["by"] = args.by
        gate["reason"] = args.reason or None
        detail = f"{args.name}={args.status} by={args.by}"
        if args.reason:
            detail += f" reason={args.reason}"
        push_history(state, "gate", detail[:400])
        refresh_next(state)
        write_state(project, slug, state)

    print(f"✅ {slug} gate.{args.name}={args.status}（by={args.by}）")
    print(f"   下一步：{state['next']['command']}｜{state['next']['reason']}")
    return 0


def cmd_unit(args) -> int:
    project = project_root(args)
    slug = args.slug
    with state_lock(spec_dir(project, slug)):
        state = normalize(read_state(project, slug), slug)
        work_unit = state["work_unit"]
        if args.clear:
            state["work_unit"] = new_state(slug)["work_unit"]
            push_history(state, "unit", "清空工作單元")
            detail = "已清空工作單元"
        else:
            if args.skill:
                work_unit["skill"] = args.skill
            if not work_unit.get("skill"):
                raise CrewError(
                    "work_unit 缺 skill",
                    "修法：加上 --skill plan-build（或當前執行中的 skill 名）",
                )
            if args.done is not None:
                work_unit["done"] = args.done
            if args.total is not None:
                work_unit["total"] = args.total
            if args.label is not None:
                work_unit["label"] = args.label
            if args.remaining:
                work_unit["remaining"] = split_list(args.remaining)
            if args.evidence:
                work_unit["evidence"] = split_list(args.evidence)
            if args.ambiguity:
                work_unit["ambiguities"] = list(args.ambiguity)
            detail = (
                f"{work_unit['skill']} {as_int(work_unit.get('done'))}/"
                f"{as_int(work_unit.get('total'))}"
            )
            push_history(state, "unit", detail)
        refresh_next(state)
        write_state(project, slug, state)
    print(f"✅ {slug} 工作單元：{detail}")
    print(f"   下一步：{state['next']['command']}")
    return 0


def _parse_kv(pairs) -> dict:
    """`k=v` 清單 → dict；值先試 JSON（數字/布林/null），失敗當字串。"""
    out = {}
    for pair in pairs or []:
        if "=" not in pair:
            raise CrewError(
                f"--set 參數格式錯誤：{pair}",
                "修法：用 key=value 格式，例如 --set health_score=92",
            )
        key, _, raw = pair.partition("=")
        key = key.strip()
        raw = raw.strip()
        try:
            out[key] = json.loads(raw)
        except json.JSONDecodeError:
            out[key] = raw
    return out


def cmd_result(args) -> int:
    project = project_root(args)
    slug = args.slug
    payload = {}
    if args.json:
        try:
            parsed = json.loads(args.json)
        except json.JSONDecodeError as exc:
            raise CrewError(
                f"--json 不是合法 JSON：{exc}",
                "修法：用單引號包住整段 JSON，例如 --json '{\"status\":\"PASS\"}'",
            )
        if not isinstance(parsed, dict):
            raise CrewError("--json 必須是 JSON 物件", "修法：改成 {\"key\": value} 形式")
        payload.update(parsed)
    payload.update(_parse_kv(args.set))
    if args.status:
        payload["status"] = args.status.upper()
    if not payload:
        raise CrewError(
            "沒有給任何結果欄位",
            "修法：用 --status PASS、--set health_score=92 或 --json '{...}'",
        )

    with state_lock(spec_dir(project, slug)):
        state = normalize(read_state(project, slug), slug)
        bucket = state["results"].setdefault(args.kind, {})
        bucket.update(payload)
        push_history(state, "result", f"{args.kind}: {json.dumps(payload, ensure_ascii=False)}")
        refresh_next(state)
        write_state(project, slug, state)
    print(f"✅ {slug} results.{args.kind} 已更新：{json.dumps(payload, ensure_ascii=False)}")
    print(f"   下一步：{state['next']['command']}")
    return 0


# --------------------------------------------------------------------------
# 子命令：next / list / park / unpark
# --------------------------------------------------------------------------


def cmd_next(args) -> int:
    project = project_root(args)
    state = normalize(read_state(project, args.slug), args.slug)
    result = compute_next(state)
    if args.format == "json":
        print(json.dumps(result, ensure_ascii=False))
    else:
        command = result["command"] or "（無建議）"
        print(f"📋 任務：{state.get('name') or state['slug']}（{state['slug']}）")
        print(f"📂 階段：{state['phase']}")
        print(f"💡 下一步：{command}")
        print(f"   理由：{result['reason']}")
    return 0


def iter_states(project: Path):
    """只掃 .spec/*/state.json 這一層，不遞迴。壞檔靜默略過。"""
    root = spec_root(project)
    if not root.is_dir():
        return
    try:
        entries = sorted(root.iterdir())
    except OSError:
        return
    for entry in entries:
        if not entry.is_dir():
            continue
        path = entry / "state.json"
        if not path.is_file():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, UnicodeDecodeError):
            continue
        if isinstance(data, dict):
            data.setdefault("slug", entry.name)
            yield entry.name, data


def cmd_list(args) -> int:
    project = project_root(args)
    rows = []
    for slug, raw in iter_states(project):
        state = normalize(raw, slug)
        closed = step_status(state, "close") in DONE_LIKE
        if closed and not args.all:
            continue
        rows.append(
            {
                "slug": slug,
                "name": state.get("name") or slug,
                "type": state.get("type"),
                "phase": state.get("phase"),
                "closed": closed,
                "parked": state.get("parked"),
                "inferred": bool(state.get("inferred")),
                "updated": state.get("updated"),
                "stale_days": stale_days(state),
                "next": compute_next(state),
            }
        )
    rows.sort(key=lambda r: (-(r["stale_days"] or 0), r["slug"]))

    if args.format == "json":
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return 0
    if not rows:
        print("（沒有符合條件的任務）")
        return 0
    for row in rows:
        marks = []
        if row["closed"]:
            marks.append("已結案")
        if row["parked"]:
            marks.append("已擱置")
        if row["inferred"]:
            marks.append("推測")
        suffix = f"［{'／'.join(marks)}］" if marks else ""
        print(
            f"• {row['slug']}（{row['type']}｜{row['phase']}｜停滯 {row['stale_days']} 天）{suffix}"
        )
        print(f"    → {row['next']['command'] or '（無建議）'}：{row['next']['reason']}")
    return 0


def cmd_park(args) -> int:
    project = project_root(args)
    slug = args.slug
    with state_lock(spec_dir(project, slug)):
        state = normalize(read_state(project, slug), slug)
        state["parked"] = {"at": now_iso(), "reason": args.reason or ""}
        push_history(state, "park", args.reason or "")
        refresh_next(state)
        write_state(project, slug, state)
    print(f"✅ {slug} 已擱置（不再出現在 session 開場提醒）")
    return 0


def cmd_unpark(args) -> int:
    project = project_root(args)
    slug = args.slug
    with state_lock(spec_dir(project, slug)):
        state = normalize(read_state(project, slug), slug)
        state["parked"] = None
        push_history(state, "unpark", "")
        refresh_next(state)
        write_state(project, slug, state)
    print(f"✅ {slug} 已復工｜下一步：{state['next']['command']}")
    return 0


# --------------------------------------------------------------------------
# 子命令：rebuild（自我修復）
# --------------------------------------------------------------------------


def git_out(project: Path, argv: list, timeout: int = 10):
    try:
        proc = subprocess.run(
            ["git", "-C", str(project)] + argv,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout.strip()


def rebuild_from_git(project: Path, slug: str, state: dict) -> list:
    notes = []
    if git_out(project, ["rev-parse", "--is-inside-work-tree"]) != "true":
        notes.append("非 git 工作目錄，略過 git 證據")
        return notes

    branch = git_out(project, ["rev-parse", "--abbrev-ref", "HEAD"])
    branches = git_out(project, ["branch", "--list", "--format=%(refname:short)"]) or ""
    match = next((b for b in branches.splitlines() if slug in b), None)
    chosen = match or (branch if branch and branch != "HEAD" else None)
    if chosen and not state["git"].get("branch"):
        state["git"]["branch"] = chosen
        state["resume_hint"]["branch"] = chosen
        notes.append(f"git 分支推測為 {chosen}")

    head = git_out(project, ["rev-parse", "HEAD"])
    if head and not state["git"].get("last_commit"):
        state["git"]["last_commit"] = head
        notes.append(f"last_commit={head[:8]}")

    rel = f".spec/{slug}"
    first = git_out(project, ["log", "--reverse", "--format=%H %ct", "--", rel])
    if first:
        line = first.splitlines()[0].split()
        if len(line) == 2:
            state["steps"]["start"]["status"] = "done"
            state["steps"]["start"]["commit"] = line[0]
            state["steps"]["start"]["at"] = datetime.fromtimestamp(
                int(line[1])
            ).astimezone().isoformat(timespec="seconds")
            notes.append("git log 顯示 .spec 目錄已建立 → start=done")
    return notes


def _section_bodies(text: str) -> dict:
    """依 `<!-- crew:xxx ... -->` 錨點切出各節內容。"""
    bodies = {}
    pattern = re.compile(r"<!--\s*crew:([a-z]+)[^>]*-->")
    matches = list(pattern.finditer(text))
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        body = text[match.end() : end]
        # 去掉下一節的標題行
        body = re.sub(r"\n#{1,6} .*$", "", body).strip()
        bodies[match.group(1)] = body
    return bodies


def rebuild_from_files(project: Path, slug: str, state: dict) -> list:
    notes = []
    directory = spec_dir(project, slug)

    def mark(step: str, why: str):
        if state["steps"][step]["status"] in DONE_LIKE:
            return
        state["steps"][step]["status"] = "done"
        state["steps"][step]["reason"] = f"rebuild 推測：{why}"
        notes.append(f"{step}=done（{why}）")

    plan = directory / "plan.md"
    if plan.is_file():
        mark("start", "plan.md 存在")
        try:
            text = plan.read_text(encoding="utf-8", errors="replace")
        except OSError:
            text = ""
        bodies = _section_bodies(text)
        if bodies.get("goal") or bodies.get("ac"):
            mark("spec", "plan.md 目標／驗收條件有內容")
        dec = bodies.get("dec", "")
        if "[arch]" in dec:
            mark("arch", "決策紀錄含 [arch] 條目")
        if "[db]" in dec:
            mark("db", "決策紀錄含 [db] 條目")
        if "@code:" in bodies.get("map", ""):
            mark("build", "指路段已有 @code: 錨點")
        rep = bodies.get("rep", "")
        for keyword, step in (("security", "security"), ("verify", "verify"), ("review", "review")):
            if keyword in rep.lower():
                mark(step, f"檢查報告摘要提到 {keyword}")
        match = re.search(r"^type:\s*(\w+)", text, re.MULTILINE)
        if match:
            state["type"] = match.group(1)
        match = re.search(r"^name:\s*(.+)$", text, re.MULTILINE)
        if match:
            state["name"] = match.group(1).strip()

    for filename, step in LEGACY_FILE_STEP:
        path = directory / filename
        try:
            if path.is_file() and path.stat().st_size > 0:
                mark(step, f"{filename} 存在")
        except OSError:
            continue

    deploy = directory / "deploy.sql"
    if deploy.is_file():
        try:
            body = deploy.read_text(encoding="utf-8", errors="replace")
            # 先去掉 -- 行註解，再依分號切；避免註解黏在語句前導致漏算
            stripped = "\n".join(
                line for line in body.splitlines() if not line.strip().startswith("--")
            )
            total = len([s for s in stripped.split(";") if s.strip()])
            state["deploy"]["steps_total"] = total
            notes.append(f"deploy.sql 推測 {total} 個執行步驟")
        except OSError:
            pass

    return notes


def cmd_rebuild(args) -> int:
    project = project_root(args)
    slug = args.slug
    directory = spec_dir(project, slug)
    if not directory.is_dir():
        raise CrewError(
            f"找不到任務目錄：{directory}",
            "修法：確認 slug 拼字，或用 `crew-state.py list` 看有哪些任務",
        )

    with state_lock(directory):
        existing = read_state(project, slug, required=False)
        intact = bool(existing) and existing.get("schema_version") == SCHEMA_VERSION and bool(
            existing.get("steps")
        )
        if existing:
            state = normalize(dict(existing), slug)
            notes = ["沿用現存 state.json 作為基底"]
        else:
            state = new_state(slug)
            notes = ["現存 state.json 缺失或損毀，改由 git 與檔案系統重建"]

        if not intact:
            notes += rebuild_from_git(project, slug, state)
            notes += rebuild_from_files(project, slug, state)
            state["inferred"] = True

        # phase = 最後一個已完成的步驟
        last_done = "start"
        for step in STEPS:
            if step_status(state, step) in DONE_LIKE:
                last_done = step
        state["phase"] = last_done
        push_history(state, "rebuild", "；".join(notes)[:400])
        refresh_next(state)
        path = write_state(project, slug, state)

    print(f"{'✅' if intact else '⚠️'} 已重建狀態檔：{path}")
    for note in notes:
        print(f"   • {note}")
    print(f"   inferred={json.dumps(state['inferred'])}｜phase={state['phase']}")
    print(f"   下一步：{state['next']['command']}（{state['next']['reason']}）")
    if state["inferred"]:
        print("   修法：內容為推測，請人工核對 steps 與 results 後跑 `crew-state.py set --inferred false`")
    return 0


# --------------------------------------------------------------------------
# 子命令：validate（供 skill exit-gate 呼叫）
# --------------------------------------------------------------------------


def cmd_validate(args) -> int:
    project = project_root(args)
    slug = args.slug
    problems = []

    path = state_path(project, slug)
    if not path.exists():
        print(f"❌ {slug}：狀態檔不存在（{path}）")
        print(f"   修法：跑 `crew-state.py init --slug {slug}` 或 `crew-state.py rebuild --slug {slug}`")
        return 1
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        print(f"❌ {slug}：狀態檔無法解析（{exc}）")
        print(f"   修法：跑 `crew-state.py rebuild --slug {slug}` 自我修復")
        return 1
    if not isinstance(state, dict):
        print(f"❌ {slug}：狀態檔內容不是 JSON 物件")
        print(f"   修法：跑 `crew-state.py rebuild --slug {slug}` 自我修復")
        return 1

    # normalize 提供舊 state 的 approval-gate 相容遷移；validate 本身不直接寫檔。
    state = normalize(state, slug)

    if state.get("schema_version") != SCHEMA_VERSION:
        problems.append(
            (
                f"schema_version 應為 {SCHEMA_VERSION}，實際為 {state.get('schema_version')!r}",
                f"跑 `crew-state.py rebuild --slug {slug}` 升級 schema",
            )
        )
    if state.get("slug") != slug:
        problems.append(
            (f"slug 欄位為 {state.get('slug')!r}，與目錄名 {slug!r} 不符", "跑 rebuild 或手動更正目錄名"),
        )
    if state.get("type") not in ("feature", "bug"):
        problems.append(
            (f"type 應為 feature 或 bug，實際為 {state.get('type')!r}", f"跑 `crew-state.py set --slug {slug} --type feature`"),
        )

    for key in ("phase", "steps", "work_unit", "results", "next", "gates"):
        if key not in state:
            problems.append((f"缺少必要欄位 {key}", f"跑 `crew-state.py rebuild --slug {slug}` 補齊"))

    steps = state.get("steps")
    if not isinstance(steps, dict):
        problems.append(("steps 不是物件", f"跑 `crew-state.py rebuild --slug {slug}`"))
    else:
        for step in STEPS:
            entry = steps.get(step)
            if not isinstance(entry, dict) or "status" not in entry:
                problems.append((f"steps.{step} 缺失或缺 status", f"跑 `crew-state.py rebuild --slug {slug}` 補齊"))
            elif entry["status"] not in STATUSES:
                problems.append(
                    (
                        f"steps.{step}.status 值不合法：{entry['status']!r}",
                        f"改用 {'/'.join(STATUSES)} 之一：`crew-state.py set --slug {slug} --step {step} --status done`",
                    )
                )

    gates = state.get("gates")
    if not isinstance(gates, dict):
        problems.append(("gates 不是物件", f"跑 `crew-state.py rebuild --slug {slug}`"))
    else:
        for gate in APPROVAL_GATES:
            entry = gates.get(gate)
            if not isinstance(entry, dict):
                problems.append((f"gates.{gate} 缺失或不是物件", f"跑 `crew-state.py rebuild --slug {slug}` 補齊"))
                continue
            status = entry.get("status")
            if status not in GATE_STATUSES:
                problems.append(
                    (
                        f"gates.{gate}.status 值不合法：{status!r}",
                        f"改用 {'/'.join(GATE_STATUSES)} 之一",
                    )
                )

    if state.get("phase") not in STEPS:
        problems.append(
            (f"phase 值不合法：{state.get('phase')!r}", f"合法值：{'/'.join(STEPS)}"),
        )

    for gate in args.require_gate or []:
        if not gate_passed(state, gate):
            problems.append(
                (
                    f"Approval Gate {gate} 未通過：{gate_status(state, gate)}",
                    f"取得人類核准後執行 `crew-state.py gate --slug {slug} --name {gate} --status approved --by human`",
                )
            )

    if args.expect_phase:
        if args.expect_phase not in STEPS:
            problems.append((f"--expect-phase 給了不存在的階段：{args.expect_phase}", f"合法值：{'/'.join(STEPS)}"))
        elif state.get("phase") != args.expect_phase:
            problems.append(
                (
                    f"phase 應為 {args.expect_phase}，實際為 {state.get('phase')!r}",
                    f"本階段收尾時跑 `crew-state.py set --slug {slug} --step {args.expect_phase} --status done`",
                )
            )

    if problems:
        print(f"❌ {slug} state.json 驗證未通過（{len(problems)} 項）：")
        for message, fix in problems:
            print(f"   • {message}")
            print(f"     修法：{fix}")
        return 1

    suffix = f"、phase={args.expect_phase}" if args.expect_phase else ""
    inferred = "（注意：inferred=true，內容為推測）" if state.get("inferred") else ""
    print(f"✅ {slug} state.json 驗證通過（schema_version={SCHEMA_VERSION}{suffix}）{inferred}")
    return 0


# --------------------------------------------------------------------------
# 子命令：session-brief（SessionStart hook 專用，任何情況都 exit 0）
# --------------------------------------------------------------------------


def stale_days(state: dict) -> int:
    updated = parse_iso(state.get("updated")) or parse_iso(state.get("created"))
    if not updated:
        return 0
    delta = datetime.now().astimezone() - updated
    return max(0, delta.days)


def read_stdin_nonblocking(deadline_sec: float = BRIEF_STDIN_TIMEOUT) -> str:
    """在短超時內盡量讀 stdin，讀不到就回空字串 —— 絕不阻塞。

    hook 呼叫時 stdin 可能是「已開啟但永遠不會關」的管線，
    用 `sys.stdin.read()` 會等 EOF 等到天荒地老，卡住使用者每一次開 session。
    因此改成 non-blocking fd + `select` 短超時輪詢，超時就當作沒有 payload。
    """
    try:
        stream = sys.stdin
        if stream is None or stream.closed or stream.isatty():
            return ""  # 互動式終端不會有 hook payload
        fd = stream.fileno()
    except (AttributeError, ValueError, OSError):
        return ""

    try:
        os.set_blocking(fd, False)
    except (OSError, ValueError):
        return ""  # 設不成非阻塞就寧可放棄去重，也不冒卡死的險

    chunks = []
    total = 0
    end = time.monotonic() + deadline_sec
    try:
        while True:
            remaining = end - time.monotonic()
            if remaining <= 0:
                break
            try:
                ready, _, _ = select.select([fd], [], [], remaining)
            except (OSError, ValueError):
                break
            if not ready:
                break
            try:
                data = os.read(fd, 65536)
            except BlockingIOError:
                continue
            except OSError:
                break
            if not data:
                break  # EOF
            chunks.append(data)
            total += len(data)
            if total > 1_048_576:  # 1 MB 上限，防惡意／異常巨量輸入
                break
    finally:
        try:
            os.set_blocking(fd, True)
        except (OSError, ValueError):
            pass
    return b"".join(chunks).decode("utf-8", errors="replace")


def brief_dedupe_ok() -> bool:
    """同一 session 只輸出一次（bug-workflow 與 feature-workflow 可能同時安裝）。

    取不到 session_id 就不去重，直接輸出（容忍重複優於漏報，更優於卡死）。
    """
    raw = read_stdin_nonblocking()
    session_id = ""
    if raw.strip():
        try:
            payload = json.loads(raw)
            if isinstance(payload, dict):
                session_id = str(payload.get("session_id") or "")
        except Exception:
            session_id = ""
        if not session_id:
            # JSON 可能因為超時而被截斷，退而求其次直接抓欄位
            match = re.search(r'"session_id"\s*:\s*"([^"]+)"', raw)
            if match:
                session_id = match.group(1)
    if not session_id:
        return True

    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", session_id)[:80]
    marker = Path(tempfile.gettempdir()) / f"crew-session-brief-{safe}.marker"
    try:
        fd = os.open(str(marker), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        return False
    except OSError:
        return True
    try:
        os.write(fd, now_iso().encode("utf-8"))
    except OSError:
        pass
    finally:
        os.close(fd)
    return True


def brief_lines(project: Path) -> list:
    pending = []
    for slug, raw in iter_states(project):
        try:
            state = normalize(raw, slug)
            if step_status(state, "close") in DONE_LIKE:
                continue
            if state.get("parked"):
                continue
            pending.append(state)
        except Exception:
            continue
    if not pending:
        return []

    pending.sort(key=lambda s: (-stale_days(s), s.get("slug") or ""))

    lines = [f"[CREW] {len(pending)} 個未結案任務"]
    for state in pending[:BRIEF_MAX_LINES]:
        slug = state.get("slug")
        task_type = state.get("type") or "feature"
        phase = state.get("phase") or "start"
        work_unit = state.get("work_unit") or {}
        total = as_int(work_unit.get("total"))
        progress = phase
        if total > 0:
            label = work_unit.get("label") or ""
            progress = f"{phase} {as_int(work_unit.get('done'))}/{total}"
            if label:
                progress = f"{progress} {label}"
        lines.append(
            f"• {slug}（{task_type}｜{progress}｜停滯 {stale_days(state)} 天）→ /plan-next {slug}"
        )
    if len(pending) > BRIEF_MAX_LINES:
        lines.append(f"另有 {len(pending) - BRIEF_MAX_LINES} 個，`/plan-status`")
    return lines


def _brief_timeout(signum, frame):
    raise TimeoutError("session-brief 超過總體時限")


def cmd_session_brief(args) -> int:
    """絕不 exit 2、絕不拋例外、絕不阻塞超過 BRIEF_TOTAL_TIMEOUT 秒。

    hook 失敗或變慢都不該阻擋使用者的 session，所以失敗一律靜默 exit 0。
    """
    timer_on = False
    try:
        signal.signal(signal.SIGALRM, _brief_timeout)
        signal.setitimer(signal.ITIMER_REAL, BRIEF_TOTAL_TIMEOUT)
        timer_on = True
    except (AttributeError, ValueError, OSError):
        timer_on = False  # 非主執行緒或平台不支援時，仍有 stdin 短超時擋著

    try:
        project = project_root(args)
        if not spec_root(project).is_dir():
            return 0
        lines = brief_lines(project)
        if not lines:
            return 0
        if not brief_dedupe_ok():
            return 0
        print("\n".join(lines))
    except Exception:
        return 0
    finally:
        if timer_on:
            try:
                signal.setitimer(signal.ITIMER_REAL, 0)
            except (ValueError, OSError):
                pass
    return 0


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def add_target(parser, slug_required: bool = True) -> None:
    parser.add_argument("--slug", required=slug_required, help="任務 slug（.spec/ 下的目錄名）")
    parser.add_argument(
        "--project",
        "--cwd",
        dest="project",
        default=".",
        help="專案根目錄（預設當前目錄），內含 .spec/",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="crew-state.py",
        description="CREW 流程狀態的單一寫者 —— 讀寫 .spec/{slug}/state.json",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "退出碼：0 成功｜1 使用者錯誤或 validate 未通過｜3 環境問題（鎖／寫入失敗）\n"
            "session-brief 任何情況都回 0。"
        ),
    )
    sub = parser.add_subparsers(dest="command", metavar="子命令", required=True)

    p = sub.add_parser("init", help="建立任務狀態檔（start 標為 done）")
    add_target(p)
    p.add_argument("--name", default="", help="任務名稱（預設同 slug）")
    p.add_argument("--type", choices=["feature", "bug"], default="feature", help="任務型別")
    p.add_argument("--branch", default="", help="開發分支")
    p.add_argument("--commit", default="", help="建立當下的 commit sha")
    p.add_argument("--notion-page-id", default="", help="Notion 頁面 ID")
    p.add_argument("--force", action="store_true", help="覆蓋已存在的狀態檔")
    p.set_defaults(func=cmd_init)

    p = sub.add_parser("set", help="更新步驟狀態與各項欄位")
    add_target(p)
    p.add_argument("--step", choices=STEPS, help="要更新的步驟（需搭配 --status）")
    p.add_argument("--status", choices=STATUSES, help="步驟狀態")
    p.add_argument("--at", default="", help="時間戳（ISO 8601，預設現在）")
    p.add_argument("--commit", default="", help="該步驟對應的 commit sha")
    p.add_argument("--reason", default=None, help="狀態理由（例：DB_REQUIRED=false）")
    p.add_argument("--phase", choices=STEPS, help="直接指定當前階段")
    p.add_argument("--name", default="", help="任務名稱")
    p.add_argument("--type", choices=["feature", "bug"], help="任務型別")
    p.add_argument("--branch", default="", help="git 分支")
    p.add_argument("--base", default="", help="git 基準分支")
    p.add_argument("--last-commit", default="", help="最後一個 commit sha")
    p.add_argument("--notion-page-id", default="", help="Notion 頁面 ID")
    p.add_argument("--mirrored-status", default="", help="Notion 上呈現的狀態字串")
    p.add_argument("--synced-now", action="store_true", help="把 notion.last_synced_at 設為現在")
    p.add_argument("--deploy-total", type=int, help="deploy.sql 的執行步驟總數")
    p.add_argument("--deploy-confirmed", type=int, help="已確認執行的步驟數")
    p.add_argument("--read-first", action="append", help="復工時要先讀的檔案（可重複或逗號分隔）")
    p.add_argument("--services", action="append", help="復工時要啟動的服務（可重複或逗號分隔）")
    p.add_argument("--inferred", choices=["true", "false"], help="標記／解除「狀態為推測」")
    p.set_defaults(func=cmd_set)

    p = sub.add_parser("gate", help="更新人類 Approval Gate 決策")
    add_target(p)
    p.add_argument("--name", choices=APPROVAL_GATES, required=True, help="gate 名稱")
    p.add_argument("--status", choices=GATE_STATUSES, required=True, help="核准狀態")
    p.add_argument("--by", required=True, help="決策者識別（例：human / 使用者名稱）")
    p.add_argument("--reason", default="", help="核准／拒絕／waive 原因；waived 必填")
    p.set_defaults(func=cmd_gate)

    p = sub.add_parser("unit", help="更新工作單元進度（斷點續跑用）")
    add_target(p)
    p.add_argument("--skill", default="", help="執行中的 skill 名（例：plan-build）")
    p.add_argument("--done", type=int, help="已完成單元數")
    p.add_argument("--total", type=int, help="單元總數")
    p.add_argument("--label", default=None, help="單元量詞（例：檔），顯示成 3/7檔")
    p.add_argument("--remaining", action="append", help="未完成單元（可重複或逗號分隔）")
    p.add_argument("--evidence", action="append", help="已完成的證據（可重複或逗號分隔）")
    p.add_argument("--ambiguity", action="append", help="歧義點（可重複，整句不切分）")
    p.add_argument("--clear", action="store_true", help="清空工作單元（skill 正常收工時用）")
    p.set_defaults(func=cmd_unit)

    p = sub.add_parser("result", help="寫入 verify / review / security 的結果")
    add_target(p)
    p.add_argument("--kind", choices=["verify", "review", "security"], required=True)
    p.add_argument("--status", help="PASS / WARN / FAIL")
    p.add_argument("--set", action="append", help="key=value（值可為 JSON 純量），可重複")
    p.add_argument("--json", help="整包 JSON 物件")
    p.set_defaults(func=cmd_result)

    p = sub.add_parser("next", help="依決策表算出下一步指令")
    add_target(p)
    p.add_argument("--format", choices=["json", "text"], default="json")
    p.set_defaults(func=cmd_next)

    p = sub.add_parser("list", help="列出 .spec/ 下所有任務與各自下一步")
    add_target(p, slug_required=False)
    p.add_argument("--all", action="store_true", help="包含已結案任務")
    p.add_argument("--format", choices=["json", "text"], default="text")
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("park", help="擱置任務（不再出現在 session 開場提醒）")
    add_target(p)
    p.add_argument("--reason", default="", help="擱置原因")
    p.set_defaults(func=cmd_park)

    p = sub.add_parser("unpark", help="解除擱置")
    add_target(p)
    p.set_defaults(func=cmd_unpark)

    p = sub.add_parser("rebuild", help="自我修復：從 git 與檔案系統重建狀態檔")
    add_target(p)
    p.set_defaults(func=cmd_rebuild)

    p = sub.add_parser("validate", help="驗證 schema、階段與 Approval Gate（skill exit-gate 用）")
    add_target(p)
    p.add_argument("--expect-phase", choices=STEPS, help="期望的當前階段")
    p.add_argument(
        "--require-gate",
        action="append",
        choices=APPROVAL_GATES,
        help="要求指定 gate 已 approved/waived；可重複",
    )
    p.set_defaults(func=cmd_validate)

    p = sub.add_parser("session-brief", help="SessionStart hook：列出未結案任務（無則零輸出）")
    p.add_argument(
        "--cwd",
        "--project",
        dest="project",
        default=".",
        help="專案根目錄（預設當前目錄）",
    )
    p.set_defaults(func=cmd_session_brief)

    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except CrewError as exc:
        print(f"❌ {exc.message}", file=sys.stderr)
        if exc.fix:
            print(f"   {exc.fix}", file=sys.stderr)
        return exc.code
    except KeyboardInterrupt:
        print("❌ 已中斷", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
