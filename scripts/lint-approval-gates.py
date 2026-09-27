#!/usr/bin/env python3
"""Smoke-test crew-state.py Approval Gate schema and transition contract."""

from __future__ import annotations

import json
import re
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

        assert "--name architecture --status approved --by human" in plan_text
        assert "--name architecture --status pending --by crew" in plan_text
        assert "--require-gate architecture" in plan_text

        assert "--require-gate requirement --require-gate architecture" in build_text
        assert "--name architecture --status approved" not in build_text

        # 只有 /plan 可以真的執行 Approval Gate approve。
        # 禁止說明裡可以提到 "--status approved"，所以只掃 bash code block 中的實際命令。
        def approved_gate_commands(text_value: str) -> list[str]:
            commands = []
            for block in re.findall(r"```bash\n(.*?)```", text_value, re.DOTALL):
                normalized = " ".join(
                    line.strip().rstrip("\\").strip()
                    for line in block.splitlines()
                    if line.strip() and not line.lstrip().startswith("#")
                )
                if (
                    "crew-state.py" in normalized
                    and " gate " in f" {normalized} "
                    and "--status approved" in normalized
                ):
                    commands.append(normalized)
            return commands

        plan_approvals = approved_gate_commands(plan_text)
        assert len(plan_approvals) == 2, plan_approvals

        offenders = []
        for skill in sorted((REPO / "plugins").glob("*/skills/*/SKILL.md")):
            if skill == PLAN_SKILL:
                continue
            text_value = skill.read_text(encoding="utf-8")
            if approved_gate_commands(text_value):
                offenders.append(str(skill.relative_to(REPO)))
        assert not offenders, f"non-plan skills may not approve gates: {offenders}"

        assert "只有使用者本輪明確核准" in plan_text
        assert "Agent 不得自行 approve" in plan_text
        print("✅ feature skills wire requirement + architecture approvals to explicit human confirmation")

        print("✅ approval gate smoke tests passed")
        return 0
    except (AssertionError, KeyError, json.JSONDecodeError) as exc:
        print(f"❌ {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
