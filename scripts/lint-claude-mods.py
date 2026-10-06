#!/usr/bin/env python3
"""CREW Cockpit Mod guard（規格書 §18 / §23）：確保 Claude Code Mod 永遠唯讀、最小能力面。

既有 lint 只掃 md，不掃 .ts Mod，所以由本腳本守門。兩層：

  主層（需要 claude CLI）：
    跑 `claude plugin validate --json <plugin dir>`，解析 hooks / calls / state 清單，
    與 `mod-capabilities.baseline.txt` 比對。
      - validate 出現 baseline 沒有的項目 → FAIL（新能力）
      - baseline 有但 validate 沒有       → 只提示（能力縮小不算錯）
      - validate 回報 errors              → FAIL
    validate 依「實際呼叫」回報，所以抓得到 `const f = $.fs; f.write(...)` 這類別名。
    claude CLI 不存在時印「SKIP（無 claude CLI）」，只跑輔層，並明確標示主層未執行。

  輔層（純 Python、不需 claude CLI）— 規格 §23 五條：
    R1 hooks.json 的 modules 路徑存在
    R2 Mod source 不含禁止呼叫（fs.write / model.complete / tool.call / tool.check /
       prompt.submit / process.run / process.spawn）
    R3 Mod source 不含 $.fs / $.process / $.model / $.tool 的整體賦值或解構（別名繞過的前置動作）
    R4 既有 SessionStart hook 仍在 hooks.json
    R5 manifest 沒有重複宣告標準 hooks/hooks.json

  輔層是字串比對，抓不到「$ 先傳進別的函式、在裡面用別名」的寫法——那是主層的工作。
  注意：R2/R3 不剝註解，註解裡寫出禁止字串也會被擋（刻意保守；註解請改用中文描述）。

baseline 格式（純文字、一行一項、排序、`#` 開頭為註解）：
    <module> hook <spec>          例：./register.tsx hook command.run{command=tool-calls}
    <module> call <$.x.y>         例：./register.tsx call $.ui.open
    <module> state-write <key>    例：./register.tsx state-write tool-calls.calls
    <module> state-read <key>
  由 `--write-baseline` 產生；Mod 能力變動時重新產生並在 PR 說明理由。
  validate 的 `gating hook without .catch:` 行不進 baseline，只在輸出提示（AC-15 參考）。

用法：
  python3 scripts/lint-claude-mods.py                  # 主層（有 claude 才跑）＋輔層
  python3 scripts/lint-claude-mods.py --no-validate    # 只跑輔層（CI 用）
  python3 scripts/lint-claude-mods.py --require-validate  # 無 claude CLI 視為失敗（release 前用）
  python3 scripts/lint-claude-mods.py --write-baseline    # 依 validate 結果產生 baseline
  python3 scripts/lint-claude-mods.py --self-test

退出碼：0 = 通過；1 = 有違規；2 = 用法或環境錯誤
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DEFAULT_PLUGIN = Path("plugins/feature-workflow")
BASELINE_NAME = "mod-capabilities.baseline.txt"
FIXTURE_DIR = REPO / "scripts" / "fixtures" / "claude-mods"
STANDARD_HOOKS = "hooks/hooks.json"

# --- R2：禁止呼叫 ------------------------------------------------------------
# 接收者不限 `$`（`ctx.fs.write(` 之類改名也擋），但必須有接收者——
# 這樣 `on('tool.call', …)` 這種訂閱 hook 事件的字串不會被誤擋。容許空白、換行與 `?.`。
# key = 規格列出的禁止字串（報錯時顯示），value = 對應 regex。
FORBIDDEN_CALLS = {
    "$.fs.write(": r"[\w$)\]]\s*\??\.\s*fs\s*\??\.\s*write\b",
    "$.model.complete(": r"[\w$)\]]\s*\??\.\s*model\s*\??\.\s*complete\b",
    "$.tool.call(": r"[\w$)\]]\s*\??\.\s*tool\s*\??\.\s*call\b",
    "$.tool.check(": r"[\w$)\]]\s*\??\.\s*tool\s*\??\.\s*check\b",
    "$.prompt.submit(": r"[\w$)\]]\s*\??\.\s*prompt\s*\??\.\s*submit\b",
    "$.process.run(": r"[\w$)\]]\s*\??\.\s*process\s*\??\.\s*run\b",
    "$.process.spawn(": r"[\w$)\]]\s*\??\.\s*process\s*\??\.\s*spawn\b",
}
FORBIDDEN_RE = {name: re.compile(rx) for name, rx in FORBIDDEN_CALLS.items()}

# --- R3：整體賦值／解構／動態存取 --------------------------------------------
BANNED_NS = r"(?:fs|process|model|tool)"
ALIAS_RULES = {
    # `$.fs` 後面不是成員存取（`.read`、`?.read`、`['x']`；用運算子判斷，避免換行 ASI 漏判）→ 整體取用（= $.fs、f($.fs)、return $.fs …）
    "整體取用 $.fs/$.process/$.model/$.tool": re.compile(
        r"\$\s*\??\.\s*" + BANNED_NS + r"\b(?!\s*(?:\?\.|\.|\[))"
    ),
    # 解構：{ fs } = $、{ fs, ui } = $、{ ui, fs: f } = $
    "解構取出 fs/process/model/tool": re.compile(
        r"\{[^{}]*\b" + BANNED_NS + r"\b[^{}]*\}\s*=\s*\$(?![\w$])"
    ),
    # 函式第一個參數直接解構（({ fs }, e, next) =>）
    "參數解構取出 fs/process/model/tool": re.compile(
        r"\(\s*\{[^{}]*\b" + BANNED_NS + r"\b[^{}]*\}\s*(?::[^,)]*)?,\s*[A-Za-z_$]"
    ),
    # 把整個 $ 存成別的名字：const api = $;
    "別名整個 $": re.compile(r"(?:\b(?:const|let|var)\s+[A-Za-z_$][\w$]*|[A-Za-z_$][\w$]*)\s*=\s*\$\s*(?:[;,)\n]|$)"),
    # 動態存取：$['fs']、$.fs['write']、$[name]
    "動態存取 $[...]": re.compile(r"\$\s*\??\.?\s*\["),
    "動態存取 $.fs[...]": re.compile(r"\$\s*\??\.\s*" + BANNED_NS + r"\s*\??\.?\s*\["),
}
RULE_FORBIDDEN = "forbidden-call"
RULE_ALIAS = "alias"


def line_of(text: str, pos: int) -> int:
    return text.count("\n", 0, pos) + 1


def scan_source(name: str, text: str) -> list[tuple[str, str]]:
    """回傳 [(rule, 訊息)]。rule ∈ forbidden-call / alias。"""
    out: list[tuple[str, str]] = []
    for label, rx in FORBIDDEN_RE.items():
        for m in rx.finditer(text):
            out.append((RULE_FORBIDDEN, f"{name}:{line_of(text, m.start())} 含禁止呼叫 `{label}`"))
    for label, rx in ALIAS_RULES.items():
        for m in rx.finditer(text):
            out.append((RULE_ALIAS, f"{name}:{line_of(text, m.start())} {label}（規避字串比對的前置動作）"))
    return out


# --- R1 / R4 / R5：純函式，吃 dict 方便 self-test --------------------------


def normalize_rel(p: str) -> str:
    p = p.strip().replace("\\", "/")
    while p.startswith("./"):
        p = p[2:]
    return p


def check_modules(hooks_json: dict, exists) -> list[str]:
    """R1：modules 必須存在且每條路徑都解得到檔案。exists(rel_path)->bool，rel 相對 hooks.json 所在目錄。"""
    mods = hooks_json.get("modules")
    if not isinstance(mods, list) or not mods:
        return ["R1 hooks.json 缺 modules 宣告（Cockpit Mod 未掛載）"]
    errs = []
    for m in mods:
        if not isinstance(m, str) or not exists(m):
            errs.append(f"R1 modules 路徑不存在：{m!r}")
    return errs


def check_session_start(hooks_json: dict) -> list[str]:
    """R4：既有 SessionStart brief hook 仍在（含 crew-state.py session-brief 指令）。"""
    entries = (hooks_json.get("hooks") or {}).get("SessionStart")
    if not isinstance(entries, list) or not entries:
        return ["R4 hooks.json 的 hooks.SessionStart 不見了（既有 session brief 被移除）"]
    for entry in entries:
        for h in (entry or {}).get("hooks") or []:
            cmd = str((h or {}).get("command", ""))
            if "crew-state.py" in cmd and "session-brief" in cmd:
                return []
    return ["R4 hooks.SessionStart 存在，但找不到 `crew-state.py session-brief` 指令（brief hook 被改掉）"]


def check_manifest(label: str, manifest: dict) -> list[str]:
    """R5：manifest 的 hooks 不得宣告標準 hooks/hooks.json（否則 Duplicate hooks file detected）。"""
    hooks = manifest.get("hooks")
    entries = [hooks] if isinstance(hooks, str) else [e for e in hooks if isinstance(e, str)] if isinstance(hooks, list) else []
    return [
        f"R5 {label}: manifest 重複宣告標準 `{e}`（會造成 Duplicate hooks file detected）"
        for e in entries
        if normalize_rel(e) == STANDARD_HOOKS
    ]


# --- 主層：validate 解析 ------------------------------------------------------


def split_top_level(s: str) -> list[str]:
    """以逗號切分，但尊重 {} 內的逗號。"""
    parts, depth, cur = [], 0, []
    for ch in s:
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth = max(0, depth - 1)
        if ch == "," and depth == 0:
            parts.append("".join(cur).strip())
            cur = []
        else:
            cur.append(ch)
    tail = "".join(cur).strip()
    if tail:
        parts.append(tail)
    return [p for p in parts if p]


NOTE_RE = re.compile(r"^(\S+) (hooks|calls|state writes|state reads|gating hook without \.catch): ?(.*)$")
KIND = {"hooks": "hook", "calls": "call", "state writes": "state-write", "state reads": "state-read"}


VIA_RE = re.compile(r"\s+\(via [^()]*\)$")


def parse_validate(data: dict) -> tuple[set[str], list[str], list[str]]:
    """回傳 (能力項目集合, errors, 無 catch 的 gating hook 提示)。"""
    items: set[str] = set()
    errors: list[str] = []
    gating: list[str] = []
    containers = [data.get("manifest") or {}] + list(data.get("contents") or [])
    for c in containers:
        for e in c.get("errors") or []:
            errors.append(f"{e.get('path', '?')}: {e.get('message', e)}" if isinstance(e, dict) else str(e))
        if c.get("type") != "hooks":
            continue
        for note in c.get("notes") or []:
            m = NOTE_RE.match(note)
            if not m:
                continue
            module, what, rest = m.groups()
            if what in KIND:
                for spec in split_top_level(rest):
                    # validate 對經由 helper 的呼叫會加註「 (via 函式名)」；能力本身與 helper 名稱無關，
                    # 去掉後綴才不會因重新命名 helper 而誤報新能力
                    spec = VIA_RE.sub("", spec)
                    items.add(f"{module} {KIND[what]} {spec}")
            else:
                gating.append(f"{module} {rest}")
    return items, errors, gating


BASELINE_HEADER = (
    "# CREW Cockpit Mod capability baseline（由 scripts/lint-claude-mods.py --write-baseline 產生）\n"
    "# 格式：<module> hook|call|state-write|state-read <項目>；一行一項、已排序。\n"
    "# 新增能力 → lint fail，須重新產生本檔並在 PR 說明為何 MVP 不可避免（規格 §18）。\n"
)


def render_baseline(items: set[str]) -> str:
    return BASELINE_HEADER + "".join(f"{i}\n" for i in sorted(items))


def parse_baseline(text: str) -> set[str]:
    return {ln.strip() for ln in text.splitlines() if ln.strip() and not ln.strip().startswith("#")}


def compare_baseline(current: set[str], baseline: set[str]) -> tuple[list[str], list[str]]:
    """回傳 (新增能力＝fail, 消失能力＝提示)。"""
    return sorted(current - baseline), sorted(baseline - current)


def run_validate(plugin_dir: Path) -> dict:
    proc = subprocess.run(
        ["claude", "plugin", "validate", "--json", str(plugin_dir)],
        capture_output=True, text=True, timeout=180,
    )
    out = proc.stdout
    start = out.find("{")
    if start < 0:
        raise RuntimeError(f"validate 沒有輸出 JSON（exit={proc.returncode}）：{(proc.stderr or out)[:300]}")
    return json.loads(out[start:])


# --- 輔層：對真實 repo ---------------------------------------------------------


def mod_sources(plugin_dir: Path) -> list[Path]:
    hooks_dir = plugin_dir / "hooks"
    files = []
    for p in sorted(hooks_dir.rglob("*")):
        if p.suffix not in (".ts", ".tsx") or p.name.endswith(".d.ts"):
            continue
        if "tests" in p.relative_to(hooks_dir).parts:
            continue
        files.append(p)
    return files


def aux_layer(root: Path, plugin_rel: Path) -> list[str]:
    plugin_dir = root / plugin_rel
    hooks_path = plugin_dir / "hooks" / "hooks.json"
    errs: list[str] = []
    try:
        hooks_json = json.loads(hooks_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return [f"無法讀取 {hooks_path}：{exc}"]
    errs += check_modules(hooks_json, lambda m: (hooks_path.parent / m).is_file())
    errs += check_session_start(hooks_json)
    for mp in (plugin_dir / ".claude-plugin" / "plugin.json", plugin_dir / "plugin.json"):
        if mp.is_file():
            try:
                errs += check_manifest(str(mp.relative_to(root)), json.loads(mp.read_text(encoding="utf-8")))
            except ValueError as exc:
                errs.append(f"{mp} 不是合法 JSON：{exc}")
    for src in mod_sources(plugin_dir):
        rel = str(src.relative_to(root))
        for rule, msg in scan_source(rel, src.read_text(encoding="utf-8")):
            errs.append(("R2 " if rule == RULE_FORBIDDEN else "R3 ") + msg)
    return errs


def main_layer(plugin_dir: Path, baseline_path: Path, write: bool) -> tuple[int, list[str]]:
    """回傳 (exit code, 輸出行)。"""
    lines: list[str] = []
    try:
        data = run_validate(plugin_dir)
    except (RuntimeError, ValueError, subprocess.TimeoutExpired) as exc:
        return 1, [f"❌ 主層：claude plugin validate 失敗：{exc}"]
    items, errors, gating = parse_validate(data)
    for g in gating:
        lines.append(f"⚠️  gating hook 無 .catch（AC-15 參考，不阻擋）：{g}")
    if errors:
        lines += [f"❌ 主層：validate 回報 error：{e}" for e in errors]
        return 1, lines
    if write:
        baseline_path.write_text(render_baseline(items), encoding="utf-8")
        lines.append(f"✅ 已寫入 {baseline_path}（{len(items)} 項）")
        return 0, lines
    if not baseline_path.is_file():
        return 1, lines + [f"❌ 主層：baseline 不存在：{baseline_path}（先跑 --write-baseline）"]
    new, gone = compare_baseline(items, parse_baseline(baseline_path.read_text(encoding="utf-8")))
    for i in gone:
        lines.append(f"ℹ️  baseline 有但 validate 沒有（能力縮小，不算錯）：{i}")
    if new:
        lines += [f"❌ 主層：出現 baseline 沒有的新能力：{i}" for i in new]
        return 1, lines
    lines.append(f"✅ 主層：能力清單與 baseline 一致（{len(items)} 項）")
    return 0, lines


# --- self-test ----------------------------------------------------------------


def self_test() -> int:
    fails: list[str] = []

    def check(cond: bool, msg: str) -> None:
        if not cond:
            fails.append(msg)

    # 1) fixtures：bad-* 必 fail 且命中指定規則；good-* 必 pass
    check(FIXTURE_DIR.is_dir(), f"fixtures 目錄不存在：{FIXTURE_DIR}")
    bad_files = sorted(FIXTURE_DIR.glob("bad-*.ts"))
    good_files = sorted(FIXTURE_DIR.glob("good-*.ts"))
    check(len(good_files) >= 1, "缺 good-* 正對照 fixture")
    covered_labels: set[str] = set()
    for f in bad_files:
        text = f.read_text(encoding="utf-8")
        m = re.search(r"expect:\s*(forbidden-call|alias)(?:[ \t]+(\S+))?", text)
        check(m is not None, f"{f.name} 缺 `expect:` 標頭")
        if not m:
            continue
        hits = scan_source(f.name, text)
        rules = {r for r, _ in hits}
        check(m.group(1) in rules, f"{f.name} 應命中規則 {m.group(1)}，實際 {sorted(rules) or '無'}")
        want = (m.group(2) or "").strip()
        if want:  # 標頭寫 fs/write（避免標頭註解自己命中規則），還原成 $.fs.write(
            want = "$." + want.replace("/", ".") + "("
        if want:
            check(any(want in msg for _, msg in hits), f"{f.name} 應命中 `{want}`，實際訊息：{[x for _, x in hits]}")
            covered_labels.add(want)
    for label in FORBIDDEN_CALLS:
        check(label in covered_labels, f"七條禁止 pattern 缺反向 fixture：{label}")
    check(len(bad_files) >= 7 + 4, f"反向 fixture 太少（{len(bad_files)}）")
    for f in good_files:
        hits = scan_source(f.name, f.read_text(encoding="utf-8"))
        check(not hits, f"{f.name} 是正對照卻被擋：{hits}")

    # 2) 輔層純函式
    check(check_modules({"modules": ["./a.tsx"]}, lambda m: True) == [], "modules 存在應 pass")
    check(len(check_modules({"modules": ["./a.tsx"]}, lambda m: False)) == 1, "modules 不存在應 fail")
    check(len(check_modules({}, lambda m: True)) == 1, "缺 modules 應 fail")
    ss_ok = {"hooks": {"SessionStart": [{"hooks": [{"type": "command", "command": "python3 crew-state.py session-brief --cwd x"}]}]}}
    check(check_session_start(ss_ok) == [], "SessionStart 在應 pass")
    check(len(check_session_start({"hooks": {}})) == 1, "SessionStart 不見應 fail")
    check(len(check_session_start({"hooks": {"SessionStart": [{"hooks": [{"command": "echo hi"}]}]}})) == 1, "brief 指令被換掉應 fail")
    check(check_manifest("m", {"hooks": "./extra.json"}) == [], "額外 hook 檔應 pass")
    check(len(check_manifest("m", {"hooks": "./hooks/hooks.json"})) == 1, "重複宣告標準 hooks 應 fail")
    check(len(check_manifest("m", {"hooks": ["extra.json", "hooks/hooks.json"]})) == 1, "list 內重複宣告應 fail")
    check(check_manifest("m", {}) == [], "未宣告 hooks 應 pass")

    # 3) 主層：假 validate JSON
    def fake(hooks_spec: str, calls_spec: str, errors=None) -> dict:
        return {
            "manifest": {"errors": []},
            "contents": [{
                "type": "hooks", "errors": errors or [],
                "notes": [
                    f"./register.tsx hooks: {hooks_spec}",
                    f"./register.tsx calls: {calls_spec}",
                    "./register.tsx gating hook without .catch: tool.call",
                    "./register.tsx state writes: tool-calls.calls",
                ],
            }],
        }

    base_data = fake(
        "session.start, command.run{command=tool-calls}, tool.call, ui.render{component=Pane, requestId=tool-calls}",
        "$.command.register, $.state.get, $.ui.open",
    )
    items, errors, gating = parse_validate(base_data)
    check("./register.tsx hook ui.render{component=Pane, requestId=tool-calls}" in items, "大括號內逗號未被正確保留")
    check("./register.tsx hook command.run{command=tool-calls}" in items, "command.run 項解析錯誤")
    check("./register.tsx hook requestId=tool-calls}" not in items and not any(i.endswith(" hook requestId=tool-calls}") for i in items), "大括號內逗號被誤切")
    check(len([i for i in items if " hook " in i]) == 4, f"hook 項數應為 4：{sorted(items)}")
    check("./register.tsx state-write tool-calls.calls" in items, "state writes 未解析")
    check(gating == ["./register.tsx tool.call"], f"gating 提示解析錯誤：{gating}")
    check(errors == [], "無 error 時不應有 errors")
    baseline = parse_baseline(render_baseline(items))
    check(baseline == items, "baseline render/parse 不可逆")
    check(compare_baseline(items, baseline) == ([], []), "相同清單應一致")
    more, _, _ = parse_validate(fake(
        "session.start, command.run{command=tool-calls}, tool.call, ui.render{component=Pane, requestId=tool-calls}",
        "$.command.register, $.state.get, $.ui.open, $.fs.write",
    ))
    new, gone = compare_baseline(more, baseline)
    check(new == ["./register.tsx call $.fs.write"] and gone == [], f"多一項應 fail：{new}/{gone}")
    fewer, _, _ = parse_validate(fake(
        "session.start, command.run{command=tool-calls}, tool.call, ui.render{component=Pane, requestId=tool-calls}",
        "$.command.register, $.ui.open",
    ))
    new, gone = compare_baseline(fewer, baseline)
    check(new == [] and gone == ["./register.tsx call $.state.get"], f"少一項應 pass 且提示：{new}/{gone}")
    _, errs2, _ = parse_validate(fake("session.start", "$.ui.open", errors=[{"path": "p", "message": "boom"}]))
    check(errs2 == ["p: boom"], f"validate errors 應被收集：{errs2}")
    check(split_top_level("a{x=1, y=2}, b") == ["a{x=1, y=2}", "b"], "split_top_level 錯誤")
    via, _, _ = parse_validate(fake("session.start", "$.fs.read (via portsOf), $.ui.open"))
    check("./register.tsx call $.fs.read" in via and "./register.tsx call $.fs.read (via portsOf)" not in via,
          f"「(via helper)」後綴應被去除：{sorted(via)}")
    via2, _, _ = parse_validate(fake("session.start", "$.fs.write (via helper)"))
    check("./register.tsx call $.fs.write" in via2, f"經 helper 的禁止呼叫仍須以本名列入：{sorted(via2)}")

    if fails:
        for f in fails:
            print(f"❌ self-test：{f}")
        return 1
    print(f"✅ lint-claude-mods self-test passed（反向 fixture {len(bad_files)} 個、正對照 {len(good_files)} 個）")
    return 0


# --- CLI ----------------------------------------------------------------------


def main() -> int:
    ap = argparse.ArgumentParser(description="CREW Cockpit Mod guard（規格 §23）")
    ap.add_argument("--self-test", action="store_true", help="執行內建 regression tests")
    ap.add_argument("--no-validate", action="store_true", help="只跑輔層（CI 用）")
    ap.add_argument("--require-validate", action="store_true", help="無 claude CLI 時視為失敗")
    ap.add_argument("--write-baseline", action="store_true", help="依 validate 結果產生 baseline 檔")
    ap.add_argument("--root", type=Path, default=REPO, help="repo 根目錄（預設本腳本所在 repo）")
    ap.add_argument("--plugin-dir", type=Path, default=DEFAULT_PLUGIN, help="plugin 目錄，相對 --root")
    ap.add_argument("--baseline", type=Path, default=None, help="baseline 檔路徑（預設 <plugin-dir>/" + BASELINE_NAME + "）")
    args = ap.parse_args()

    if args.self_test:
        return self_test()

    plugin_dir = args.root / args.plugin_dir
    baseline_path = args.baseline or (plugin_dir / BASELINE_NAME)
    rc = 0

    if args.write_baseline:
        if args.no_validate or not shutil.which("claude"):
            print("❌ --write-baseline 需要 claude CLI")
            return 2
        code, lines = main_layer(plugin_dir, baseline_path, write=True)
        print("\n".join(lines))
        return code

    if args.no_validate:
        print("ℹ️  主層未執行（--no-validate）；僅輔層。主層列為 release 前本機必跑。")
    elif not shutil.which("claude"):
        print("⏭️  主層 SKIP（無 claude CLI）——主層【未執行】，下方只代表輔層結果")
        if args.require_validate:
            print("❌ --require-validate：無 claude CLI，視為失敗")
            rc = 1
    else:
        code, lines = main_layer(plugin_dir, baseline_path, write=False)
        print("\n".join(lines))
        rc = max(rc, code)

    errs = aux_layer(args.root, args.plugin_dir)
    if errs:
        print(f"❌ 輔層：{len(errs)} 項違規")
        for e in errs:
            print(f"  - {e}")
        rc = 1
    else:
        print("✅ 輔層（R1–R5）通過")
    return rc


if __name__ == "__main__":
    sys.exit(main())
