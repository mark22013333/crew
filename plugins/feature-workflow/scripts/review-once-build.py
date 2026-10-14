#!/usr/bin/env python3
"""Fail-closed Review Once Build pre/post guard, scoped to approved Git paths."""
from __future__ import annotations

import argparse
import fnmatch
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
s = importlib.util.spec_from_file_location("crew_review_once_build_grant", ROOT / "review-once-grant.py")
assert s is not None and s.loader is not None
contract = importlib.util.module_from_spec(s)
s.loader.exec_module(contract)


class GuardError(ValueError):
    pass


def git(project: Path, *argv: str) -> str:
    proc = subprocess.run(["git", "-C", str(project), *argv],
                          capture_output=True, timeout=10, check=False)
    if proc.returncode:
        raise GuardError(f"Git check failed: {argv}: {proc.stderr.decode(errors='replace')}")
    return proc.stdout.decode("utf-8", errors="strict").strip()


def validate(project: Path, slug: str) -> dict:
    p = project / ".spec" / slug / "state.json"
    try:
        state = contract.packet_contract.parse_object(p)
        proposal, _ = contract.validate_active(project, slug, state, "all")
    except (contract.GrantError, contract.packet_contract.PacketError, OSError, KeyError, ValueError) as exc:
        raise GuardError(f"簽署 Grant 或 Spec/Arch 不合法：{exc}") from exc
    if (state.get("autonomy") or {}).get("target_step") == "arch":
        # --until arch 的授權只涵蓋 Spec／DB／Arch，不得用來執行任何 Build
        raise GuardError("grant 只核准到 arch，不得執行 Build；請改走互動 /plan-build 或重新核准到 build 的 packet")
    run = (state.get("autonomy") or {}).get("execution") or {}
    inflight = run.get("inflight") or {}
    if run.get("status") != "running" or inflight.get("step") != "build":
        raise GuardError("沒有有效的 Build 派工 checkpoint")
    if any((state.get("gates") or {}).get(n, {}).get("status") not in ("approved",)
           for n in ("requirement", "architecture")):
        raise GuardError("Requirement / Architecture Approval Gate 尚未 approved")
    repo = proposal["repository"]
    branch = git(project, "symbolic-ref", "--quiet", "--short", "HEAD")
    if branch != repo["branch"]:
        raise GuardError("實際 Git branch 與已核准提案不一致")
    git(project, "cat-file", "-e", f"{repo['base_commit']}^{{commit}}")
    return proposal


def changed_paths(project: Path, base_sha: str) -> list[str]:
    paths = set()
    for argv in (("diff", "--name-only", "-z", base_sha, "--"),
                 ("ls-files", "--others", "--exclude-standard", "-z")):
        proc = subprocess.run(["git", "-C", str(project), *argv],
                              capture_output=True, timeout=15, check=False)
        if proc.returncode:
            raise GuardError("不能列出完整 Git 變更，拒絕 Build scope 檢查")
        for raw in proc.stdout.split(b"\0"):
            if not raw:
                continue
            try:
                path = raw.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise GuardError("非 UTF-8 檔名，無法驗證 scope") from exc
            # CREW local spec/cache is a workflow asset; only application paths
            # must satisfy the approved product scope. Never permit .git internals.
            if path.startswith(".git/"):
                raise GuardError("拒絕檢查範圍中包含 .git/")
            if not path.startswith(".spec/"):
                paths.add(path)
    return sorted(paths)


def check(project: Path, slug: str) -> dict:
    proposal = validate(project, slug)
    allow = proposal["scope"]["allowed_paths"]
    changes = changed_paths(project, proposal["repository"]["base_commit"])
    outside = [path for path in changes if not any(
        fnmatch.fnmatchcase(path, rule) for rule in allow)]
    if outside:
        raise GuardError(f"超出核准 Git 檔案範圍：{', '.join(outside[:20])}")
    return {"status": "authorized_build_scope", "changed_files": changes,
            "allowed_paths": allow, "test_policy": proposal["test_policy"]}


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--project", type=Path, default=Path("."))
    p.add_argument("--slug", required=True)
    args = p.parse_args()
    try:
        print(json.dumps(check(args.project.resolve(), args.slug), ensure_ascii=False))
    except (GuardError, OSError, subprocess.TimeoutExpired) as exc:
        print(f"BLOCKED: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
