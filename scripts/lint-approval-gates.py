#!/usr/bin/env python3
"""Smoke-test crew-state.py Approval Gate schema and transition contract."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CLI = REPO / "plugins" / "bug-workflow" / "scripts" / "crew-state.py"
PLAN_SKILL = REPO / "plugins" / "feature-workflow" / "skills" / "plan" / "SKILL.md"
PLAN_BUILD_SKILL = REPO / "plugins" / "feature-workflow" / "skills" / "plan-build" / "SKILL.md"


def run(project: Path, *args: str, expect: int = 0) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(
        [sys.executable, str(CLI), *args, "--project", str(project)],
        capture_output=True,
        text=True,
    )
    if proc.returncode != expect:
        raise AssertionError(
            f"{' '.join(args)} => {proc.returncode}, expected {expect}\n"
            f"stdout={proc.stdout}\nstderr={proc.stderr}"
        )
    return proc


def load(project: Path, slug: str = "gate-demo") -> dict:
    return json.loads((project / ".spec" / slug / "state.json").read_text(encoding="utf-8"))


def main() -> int:
    try:
        with tempfile.TemporaryDirectory() as raw:
            project = Path(raw)
            slug = "gate-demo"

            run(project, "init", "--slug", slug)
            state = load(project, slug)
            assert state["gates"]["requirement"]["status"] == "pending"
            assert state["gates"]["architecture"]["status"] == "pending"
            assert state["gates"]["uat"]["status"] == "pending"
            print("✅ new state: approval gates pending")

            run(project, "set", "--slug", slug, "--step", "spec", "--status", "done")
            blocked = run(
                project, "set", "--slug", slug, "--step", "arch", "--status", "in_progress", expect=1
            )
            assert "Approval Gate" in blocked.stderr
            print("✅ requirement gate blocks arch transition")

            run(
                project, "gate", "--slug", slug, "--name", "requirement",
                "--status", "approved", "--by", "human"
            )
            run(project, "set", "--slug", slug, "--step", "db", "--status", "skipped")
            run(project, "set", "--slug", slug, "--step", "arch", "--status", "done")

            next_before = json.loads(
                run(project, "next", "--slug", slug, "--format", "json").stdout
            )
            assert next_before["command"] is None
            assert "architecture gate=pending" in next_before["reason"]
            print("✅ architecture gate blocks next/build")

            blocked_build = run(
                project, "set", "--slug", slug, "--step", "build", "--status", "in_progress", expect=1
            )
            assert "architecture=pending" in blocked_build.stderr

            run(
                project, "gate", "--slug", slug, "--name", "architecture",
                "--status", "approved", "--by", "human"
            )
            run(project, "set", "--slug", slug, "--step", "build", "--status", "in_progress")
            run(
                project, "validate", "--slug", slug,
                "--require-gate", "requirement", "--require-gate", "architecture"
            )
            print("✅ approved gates allow build + validate")

            legacy = load(project, slug)
            legacy.pop("gates", None)
            legacy["steps"]["build"]["status"] = "pending"
            legacy["phase"] = "arch"
            (project / ".spec" / slug / "state.json").write_text(
                json.dumps(legacy, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
            legacy_next = json.loads(
                run(project, "next", "--slug", slug, "--format", "json").stdout
            )
            assert legacy_next["command"] == "/plan-build", legacy_next
            run(
                project, "validate", "--slug", slug,
                "--require-gate", "requirement", "--require-gate", "architecture"
            )
            print("✅ legacy state migrates completed spec/arch to approved gates")

        plan_text = PLAN_SKILL.read_text(encoding="utf-8")
        build_text = PLAN_BUILD_SKILL.read_text(encoding="utf-8")

        assert "--name requirement --status approved --by human" in plan_text
        assert "--name requirement --status pending --by crew" in plan_text
        assert "--require-gate requirement" in plan_text

        assert "--require-gate requirement --require-gate architecture" in build_text
        assert "--name architecture --status approved" not in build_text
        print("✅ feature skills wire requirement approval and build gate checks safely")

        print("✅ approval gate smoke tests passed")
        return 0
    except (AssertionError, KeyError, json.JSONDecodeError) as exc:
        print(f"❌ {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
