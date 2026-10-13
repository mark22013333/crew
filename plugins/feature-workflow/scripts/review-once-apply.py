#!/usr/bin/env python3
"""Apply an approved Review Once packet to the existing CREW plan skeleton.

Only signed content is inserted, using the plan-common section anchors.
This script never mutates state.json directly: crew-state.py is its sole writer.
It NEVER executes deploy.sql or modifies production source files.
"""
from __future__ import annotations

import argparse
import importlib.util
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path


def module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load contract {path}")
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


SCRIPTS = Path(__file__).resolve().parent
grant_contract = module(SCRIPTS / "review-once-grant.py", "crew_review_once_grant_apply")
packet_contract = grant_contract.packet_contract
STATE = SCRIPTS / "crew-state.py"

STAGE_TAGS = {"spec": "spec", "db": "db", "arch": "arch"}


class ApplyError(ValueError):
    pass


def state_command(project: Path, slug: str, *parts: str) -> None:
    command = [sys.executable, str(STATE), *parts, "--slug", slug, "--project", str(project)]
    result = subprocess.run(command, capture_output=True, text=True, timeout=30, check=False)
    if result.returncode:
        raise ApplyError(f"crew-state.py 拒絕狀態轉換：{result.stderr.strip() or result.stdout.strip()}")


def section_values(text: str, tag: str) -> list[str]:
    return grant_contract.sections(text).get(tag, [])


def insert_entries(text: str, tag: str, entries: list[str], stage: str,
                   append_only: bool = False) -> str:
    if not entries:
        return text
    if any("\r" in s or "\n" in s for s in entries):
        raise ApplyError(f"{tag} 不允許多行條目")
    current = section_values(text, tag)
    if append_only:
        existing = [x for x in current if f" [{stage}] " in x] if tag == "dec" else current
        if existing == entries:
            return text
        if tag == "risk":
            additions = [e for e in entries if e not in current]
        else:
            if existing:
                raise ApplyError(f"{tag} 已有部分 {stage} 決策；需要人工對帳")
            additions = entries
    else:
        if current == entries:
            return text
        if current:
            raise ApplyError(f"{tag} 已存在非核准內容，不能覆寫")
        additions = entries
    if not additions:
        return text
    pattern = re.compile(r"^(## [^\n]*<!--\s*crew:" + re.escape(tag) + r"\b[^>]*-->)$", re.M)
    found = list(pattern.finditer(text))
    if len(found) != 1:
        raise ApplyError(f"plan.md 缺少唯一的 {tag} section anchor")
    line = found[0].group(1)
    return text[:found[0].start()] + line + "\n" + "\n".join(additions) + text[found[0].end():]


def atomic_update(path: Path, new_text: str, old_text: str) -> None:
    if new_text == old_text:
        return
    # Avoid deleting an existing human file if a concurrent writer changes it.
    if path.read_text(encoding="utf-8") != old_text:
        raise ApplyError("plan.md 被其他 Writer 修改，停止本次套用")
    descriptor, name = tempfile.mkstemp(dir=path.parent, prefix=".plan-review-once-")
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as writer:
            writer.write(new_text)
            writer.flush()
            os.fsync(writer.fileno())
        os.chmod(name, path.stat().st_mode & 0o777)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def apply(project: Path, slug: str, stage: str) -> dict:
    # This is a Host-invoked, cooperative stage applier. A production Host must
    # not execute it with an agent-controlled trust-root environment.
    path = project / ".spec" / slug / "state.json"
    state = packet_contract.parse_object(path)
    running = (state.get("autonomy") or {}).get("execution") or {}
    expected = {"spec": "spec", "db": "db", "arch": "arch"}[stage]
    inflight = running.get("inflight") or {}
    if running.get("status") != "running" or inflight.get("step") != expected:
        raise ApplyError("沒有 Runner dispatch 或 dispatch 階段不一致")
    grant = state.get("autonomy") or {}
    if not grant or grant.get("status") != "active":
        raise ApplyError("沒有有效的 Review Once 授權")

    verify_stage = ("none" if stage == "spec" else "spec" if stage == "db" else "spec")
    try:
        proposal, _ = grant_contract.validate_active(project, slug, state, verify_stage)
    except (grant_contract.GrantError, KeyError, OSError, ValueError) as exc:
        raise ApplyError(f"Review Once Grant 校驗失敗：{exc}") from exc
    if proposal["slug"] != slug:
        raise ApplyError("approved proposal slug mismatch")
    step_state = (state.get("steps") or {}).get(stage, {}).get("status")
    if step_state not in ("pending", "in_progress"):
        raise ApplyError(f"{stage} 已是 {step_state}，不得重複套用")
    steps = state.get("steps") or {}
    if stage == "db" and steps.get("spec", {}).get("status") != "done":
        raise ApplyError("Spec 未正式完成")
    if stage == "arch" and steps.get("db", {}).get("status") not in ("done", "skipped"):
        raise ApplyError("DB 設計尚未完成")
    plan = project / ".spec" / slug / "plan.md"
    original = plan.read_text(encoding="utf-8")
    content = original

    if stage == "spec":
        spec = proposal["spec"]
        content = insert_entries(content, "goal", spec["goal"], stage)
        content = insert_entries(content, "ac", spec["ac"], stage)
        content = insert_entries(content, "dec", spec["decisions"], stage, append_only=True)
        content = insert_entries(content, "risk", spec["risks"], stage, append_only=True)
    elif stage == "db":
        db = proposal["db"]
        if db["required"]:
            sql = project / ".spec" / slug / "deploy.sql"
            if sql.exists():
                if sql.read_text(encoding="utf-8") != db["deploy_sql"]:
                    raise ApplyError("deploy.sql 已存在且與核准內容不同")
            else:
                with sql.open("x", encoding="utf-8") as f:
                    f.write(db["deploy_sql"])
        content = insert_entries(content, "dec", db["decisions"], stage, append_only=True)
    elif stage == "arch":
        arch = proposal["architecture"]
        content = insert_entries(content, "dec", arch["decisions"], stage, append_only=True)
        content = insert_entries(content, "risk", arch["risks"], stage, append_only=True)

    if len(content.splitlines()) > 100:
        raise ApplyError("plan.md 超過 100 行限制")
    atomic_update(plan, content, original)
    try:
        grant_contract.check_stage(project, slug, proposal, "spec" if stage != "arch" else "all")
    except grant_contract.GrantError as exc:
        raise ApplyError(f"核准提案內容未完整套用：{exc}") from exc

    if stage == "spec":
        state_command(project, slug, "set", "--step", "spec", "--status", "done")
        state_command(project, slug, "grant", "--action", "approve-requirement")
    elif stage == "db":
        status = "done" if proposal["db"]["required"] else "skipped"
        options = ["--step", "db", "--status", status]
        if status == "skipped":
            options.extend(["--reason", "DB_REQUIRED=false"])
        state_command(project, slug, "set", *options)
    elif stage == "arch":
        state_command(project, slug, "set", "--step", "arch", "--status", "done")
        state_command(project, slug, "grant", "--action", "approve-architecture")
    return {"stage": stage, "status": "applied_approved_packet"}


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply a Host-signed Review Once stage")
    parser.add_argument("--project", type=Path, default=Path("."))
    parser.add_argument("--slug", required=True)
    parser.add_argument("--step", required=True, choices=tuple(STAGE_TAGS))
    args = parser.parse_args()
    try:
        result = apply(args.project.resolve(), args.slug, args.step)
    except (ApplyError, OSError, ValueError) as exc:
        print(f"BLOCKED: {exc}", file=sys.stderr)
        return 1
    import json
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
