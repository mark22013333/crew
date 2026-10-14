#!/usr/bin/env python3
"""CREW Review Once synchronous Host bridge.

An operator-controlled Host can supply a *protected* worker adapter that
executes an existing plan-build skill with OS/Host-enforced write scope.
This bridge performs no signing and cannot make a CLI sandbox secure itself.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import signal
import stat
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STATE = ROOT / "crew-state.py"
APPLY = ROOT / "review-once-apply.py"
BUILD = ROOT / "review-once-build.py"
OWNER_RE = re.compile(r"^[A-Za-z0-9._-]{1,80}$")
EXPECTED = {"spec", "db", "arch", "build"}
TEMPLATES = {"{project}", "{slug}", "{instruction}"}


class BridgeError(RuntimeError):
    pass


def assert_ok(value, message):
    if not value:
        raise BridgeError(message)


def project_path(raw: Path) -> Path:
    project = raw.expanduser().resolve(strict=True)
    assert_ok(project.is_dir(), "Project 必須是存在的目錄")
    return project


def protected_config(raw: Path, project: Path) -> dict:
    """Only a Host-owned, out-of-repository config may define the worker."""
    assert_ok(raw.is_absolute() and not raw.is_symlink(),
              "Host adapter 設定必須是非 symlink 的絕對路徑")
    path = raw.resolve(strict=True)
    assert_ok(path.is_file() and not path.is_relative_to(project),
              "Host adapter 設定不能位於 Agent 可修改的 Repo")
    # Fail closed on writable host config/parent directories. This is a
    # cooperative check; real security also requires a separate Host identity.
    parents = [path.parent]
    while parents[-1] != parents[-1].parent:
        parents.append(parents[-1].parent)
    for entry in [path, *parents]:
        mode = entry.stat().st_mode
        # /tmp may be sticky and world-writable; trust rules reject it.
        assert_ok(not mode & (stat.S_IWGRP | stat.S_IWOTH),
                  f"Host 設定路徑可由非 owner 修改：{entry}")
    try:
        config = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise BridgeError(f"Host adapter 設定不可讀：{exc}") from exc
    assert_ok(isinstance(config, dict) and set(config) == {
        "schema_version", "adapter", "worker_argv", "host_guarantees"},
        "Host 設定 schema 不合法")
    assert_ok(type(config["schema_version"]) is int and config["schema_version"] == 1,
              "Host adapter schema_version 必須為 1")
    assert_ok(config["adapter"] in ("claude-code", "codex", "trusted-host"),
              "未知 Host adapter 類型")
    guarantees = config["host_guarantees"]
    assert_ok(isinstance(guarantees, dict) and set(guarantees) == {
        "protected_human_approval", "enforced_write_scope",
        "worker_cancellation", "no_unattended_escalation"},
        "Host 必須聲明所有必要的安全能力")
    assert_ok(all(guarantees.values()) and
              all(type(v) is bool for v in guarantees.values()),
              "Host 缺少保護授權、寫入隔離、取消或禁止提權能力；拒絕啟動")
    argv = config["worker_argv"]
    assert_ok(isinstance(argv, list) and 1 <= len(argv) <= 32 and
              all(isinstance(x, str) and x and len(x) <= 2048 for x in argv),
              "worker_argv 必須是有效的非 Shell 參數陣列")
    assert_ok(argv[0].startswith("/") and Path(argv[0]).is_file() and
              os.access(argv[0], os.X_OK),
              "worker_argv[0] 必須是存在的絕對可執行檔")
    assert_ok(not Path(argv[0]).resolve().is_relative_to(project),
              "Host worker 執行檔不能位於專案工作區")
    assert_ok(all(not (("{" in v or "}" in v) and v not in TEMPLATES)
                  for v in argv),
              "只允許獨立參數使用 {project}/{slug}/{instruction} 模板")
    assert_ok("{instruction}" in argv and "{slug}" in argv and "{project}" in argv,
              "Worker 必須收到 Task/Project/已核准 Skill 指令")
    for arg in argv:
        assert_ok(arg not in ("--dangerously-skip-permissions",
                              "--yolo", "--danger-full-access",
                              "bypassPermissions"),
                  "不允許繞過 Host 權限的 CLI 參數")
        if arg.startswith("/") and arg not in TEMPLATES:
            assert_ok(not Path(arg).resolve().is_relative_to(project),
                      "不可透過受保護 Adapter 執行 Repo 中 Agent 可修改的 Script")
    return config


def cmd(project: Path, slug: str, *args: str, timeout: float = 25) -> dict:
    proc = subprocess.run(
        [sys.executable, str(STATE), *args, "--slug", slug, "--project", str(project)],
        capture_output=True, text=True, timeout=timeout, check=False,
    )
    if proc.returncode:
        raise BridgeError((proc.stderr or proc.stdout).strip()[:700])
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        return {"message": proc.stdout.strip()}


def stage_apply(project: Path, slug: str, step: str) -> None:
    assert_ok(step in ("spec", "db", "arch"), "只有正式核准的規劃階段可以自動套用")
    proc = subprocess.run(
        [sys.executable, str(APPLY), "--project", str(project),
         "--slug", slug, "--step", step],
        capture_output=True, text=True, timeout=120, check=False,
    )
    if proc.returncode:
        raise BridgeError((proc.stderr or proc.stdout).strip()[:700])


def build_guard(project: Path, slug: str) -> dict:
    proc = subprocess.run([sys.executable, str(BUILD), "--project", str(project),
                           "--slug", slug], capture_output=True, text=True,
                          timeout=40, check=False)
    if proc.returncode:
        raise BridgeError("Build scope/approval 驗證失敗：" +
                          (proc.stderr or proc.stdout).strip()[:650])
    return json.loads(proc.stdout)


def check_runtime(project: Path, slug: str, owner: str) -> dict:
    status = cmd(project, slug, "run", "--action", "status")
    assert_ok(status["status"] == "running" and status["owner"] == owner,
              "Runner 已暫停、撤銷或被其他 Host 接管，停止 worker")
    # trusted-host Bridge 只接受外部簽章授權；同 session 對話核准（dialogue）不得交給無人值守 worker
    assert_ok(status.get("grant_proof") == "signed",
              "trusted-host Bridge 只接受簽章授權（proof=signed）；"
              f"目前為 {status.get('grant_proof')}，請改用同 session 模式")
    dt = datetime.fromisoformat(status["expires_at"].replace("Z", "+00:00"))
    assert_ok(dt.tzinfo is not None and datetime.now(timezone.utc) < dt.astimezone(timezone.utc),
              "Review Once 四小時 Grant 已到期")
    cmd(project, slug, "grant", "--action", "check")
    return status


def terminate(child: subprocess.Popen) -> None:
    if child.poll() is not None:
        return
    try:
        if os.name == "posix":
            os.killpg(child.pid, signal.SIGTERM)
        else:
            child.terminate()
        child.wait(timeout=4)
    except (ProcessLookupError, subprocess.TimeoutExpired):
        if child.poll() is None:
            if os.name == "posix":
                os.killpg(child.pid, signal.SIGKILL)
            else:
                child.kill()
            child.wait(timeout=4)


def worker_log_path(project: Path, slug: str, run_id: object,
                    override: Path | None = None) -> Path:
    """worker 輸出檔；預設落在 .spec/{slug}/.cache/（review-once-build.py 的 scope 檢查已排除）。"""
    if override is not None:
        return override.expanduser().resolve()
    assert_ok(isinstance(run_id, str) and bool(OWNER_RE.fullmatch(run_id)),
              "Runner run_id 不合法，無法決定 worker log 路徑")
    return project / ".spec" / slug / ".cache" / f"review-once-worker-{run_id}.log"


def run_worker(project: Path, slug: str, owner: str,
               config: dict, instruction: str, poll: float = 2.0,
               worker_log: Path | None = None) -> None:
    values = {"{project}": str(project), "{slug}": slug,
              "{instruction}": instruction}
    argv = [values.get(v, v) for v in config["worker_argv"]]
    status = cmd(project, slug, "run", "--action", "status")
    log_path = worker_log_path(project, slug, status.get("run_id"), worker_log)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    # OS/Host-level containment is supplied by the protected adapter. A
    # generic 'claude -p' / 'codex exec' without that containment is unsafe.
    # worker 的 stdout／stderr 一律保存（附加寫入），失敗時才有證據可查。
    log_handle = open(log_path, "ab")
    try:
        child = subprocess.Popen(
            argv, cwd=str(project), stdin=subprocess.DEVNULL,
            stdout=log_handle, stderr=subprocess.STDOUT,
            start_new_session=(os.name == "posix"),
        )
    except BaseException:
        log_handle.close()
        raise
    last_heartbeat = time.monotonic()
    try:
        while child.poll() is None:
            check_runtime(project, slug, owner)
            if time.monotonic() - last_heartbeat >= 30:
                cmd(project, slug, "run", "--action", "heartbeat", "--owner", owner)
                last_heartbeat = time.monotonic()
            time.sleep(poll)
        check_runtime(project, slug, owner)
        assert_ok(child.returncode == 0,
                  f"Host Build worker 失敗，exit={child.returncode}（輸出見 {log_path}）")
    finally:
        terminate(child)
        log_handle.close()


def safe_pause(project: Path, slug: str, owner: str, reason: str) -> None:
    try:
        cmd(project, slug, "run", "--action", "pause", "--owner", owner,
            "--reason", reason)
    except (BridgeError, subprocess.TimeoutExpired, OSError):
        # An expired/revoked grant may already have caused run to pause.
        pass


def execute_dispatch(project: Path, slug: str, owner: str,
                     config: dict, item: dict, poll: float,
                     worker_log: Path | None = None) -> None:
    step = item["step"]
    assert_ok(step in EXPECTED, "Runner 下達未知階段")
    check_runtime(project, slug, owner)
    if step in ("spec", "db", "arch"):
        stage_apply(project, slug, step)
    else:
        scope = build_guard(project, slug)
        assert_ok(scope["test_policy"] in ("with_test", "bdd"),
                  "Review Once 不允許無測試 Build")
        instruction = item["command"]
        assert_ok(instruction.startswith("/plan-build ") and
                  instruction.endswith(" --review-once"),
                  "只允許已核准的 Build Skill 指令")
        run_worker(project, slug, owner, config, instruction, poll, worker_log)
        build_guard(project, slug)
        current = cmd(project, slug, "run", "--action", "status")
        assert_ok(current["step_build"] == "done",
                  "Host Worker 未以正式 state writer 完成 Build")
    check_runtime(project, slug, owner)


def drive(project: Path, slug: str, owner: str, config: dict,
          mode: str, *, max_stages: int = 6, poll: float = 2.0,
          reconcile: bool = False, reason: str = "",
          worker_log: Path | None = None) -> dict:
    assert_ok(bool(OWNER_RE.fullmatch(owner)), "Host Runner owner 不合法")
    assert_ok(mode in ("start", "continue", "resume"), "未知啟動模式")
    # 任何 run start／resume 之前先確認授權種類：dialogue 授權直接 BLOCK，不建立或接管 Runner
    preflight = cmd(project, slug, "run", "--action", "status")
    assert_ok(preflight.get("grant_proof") == "signed",
              "trusted-host Bridge 只接受簽章授權（proof=signed）；"
              f"目前為 {preflight.get('grant_proof')}，請改用同 session 模式")
    try:
        if mode == "start":
            cmd(project, slug, "run", "--action", "start", "--owner", owner)
        elif mode == "resume":
            argv = ["run", "--action", "resume", "--owner", owner]
            if reconcile:
                assert_ok(bool(reason), "對帳續跑必須提供明確理由")
                argv += ["--reconcile", "--reason", reason]
            cmd(project, slug, *argv)
        check_runtime(project, slug, owner)
        if mode == "resume" and reconcile:
            # crew-state.py intentionally retains unresolved in-flight evidence
            # after explicit reconciliation; only this Host can now replay
            # that precise task after the operator confirmed old worker stopped.
            previous = cmd(project, slug, "run", "--action", "status").get("inflight")
            if previous:
                assert_ok(reason.strip(), "中斷派工續跑需要明確的對帳理由")
                if previous["step"] == "build":
                    # Delegate already-started Build through its native work_unit
                    # resume contract, never quietly restart a clean Build.
                    prior = previous.copy()
                    command = prior["command"]
                    if "--resume" not in command.split():
                        command = command.replace(" --review-once", " --resume --review-once")
                    previous = {**prior, "command": command}
                execute_dispatch(project, slug, owner, config, previous, poll, worker_log)
        for _ in range(max_stages):
            result = cmd(project, slug, "run", "--action", "next", "--owner", owner)
            if result["status"] in ("completed_build", "completed_plan"):
                # completed_plan＝--until arch 已套用 Spec／DB／Arch，不進 build
                return {"status": result["status"], "slug": slug,
                        "run_id": result["run_id"]}
            assert_ok(result["action"] == "next" and
                      result.get("inflight") is not None,
                      "未完成派工尚未對帳，不得重複呼叫 Worker")
            item = result["inflight"]
            execute_dispatch(project, slug, owner, config, item, poll, worker_log)
        raise BridgeError("超過階段派工上限；停止以避免失控迴圈")
    except (BridgeError, OSError, ValueError, subprocess.TimeoutExpired,
            KeyboardInterrupt) as exc:
        safe_pause(project, slug, owner, "HOST_BRIDGE_STOPPED")
        raise BridgeError(f"Host Bridge 停止；保留 checkpoint：{exc}") from exc


def main() -> int:
    parser = argparse.ArgumentParser(description="CREW Review Once secure Host bridge")
    parser.add_argument("--project", required=True, type=Path)
    parser.add_argument("--slug", required=True)
    parser.add_argument("--owner", default="host-review-once")
    parser.add_argument("--adapter", type=Path,
                        help="Host 管理的工作區外 JSON 設定（缺少即不能啟動）")
    parser.add_argument("--action", choices=["probe", "start", "continue",
                                             "resume", "status", "pause", "revoke"],
                        required=True)
    parser.add_argument("--reconcile", action="store_true")
    parser.add_argument("--reason", default="")
    parser.add_argument("--poll-seconds", type=float, default=2.0)
    parser.add_argument("--worker-log", type=Path, default=None,
                        help="worker stdout／stderr 輸出檔（預設 .spec/{slug}/.cache/review-once-worker-{run_id}.log）")
    args = parser.parse_args()
    try:
        project = project_path(args.project)
        if args.action in ("status", "pause", "revoke"):
            cmd_args = (("run", "--action", "status") if args.action == "status"
                        else ("run", "--action", "pause", "--owner", args.owner,
                              "--reason", args.reason or "USER_PAUSED")
                        if args.action == "pause" else
                        ("grant", "--action", "revoke"))
            result = cmd(project, args.slug, *cmd_args)
        else:
            assert_ok(args.adapter is not None, "需要受保護 Host adapter 設定")
            config = protected_config(args.adapter, project)
            if args.action == "probe":
                result = {"status": "adapter_contract_ready",
                          "adapter": config["adapter"],
                          "warning": "Host 實際授權、沙箱與 CLI 安裝需由部署者驗證"}
            else:
                assert_ok(0.1 <= args.poll_seconds <= 30.0,
                          "poll-seconds 應介於 0.1～30 秒")
                result = drive(project, args.slug, args.owner, config,
                               args.action, poll=args.poll_seconds,
                               reconcile=args.reconcile, reason=args.reason,
                               worker_log=args.worker_log)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (BridgeError, OSError, subprocess.TimeoutExpired) as exc:
        print(f"BLOCKED: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
