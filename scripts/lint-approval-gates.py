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
PLAN_VERIFY_SKILL = REPO / "plugins" / "feature-workflow" / "skills" / "plan-verify" / "SKILL.md"
PLAN_CLOSE_SKILL = REPO / "plugins" / "feature-workflow" / "skills" / "plan-close" / "SKILL.md"
BUG_CLOSE_SKILL = REPO / "plugins" / "bug-workflow" / "skills" / "bug-close" / "SKILL.md"
UAT_CONTRACT = REPO / "plugins" / "feature-workflow" / "references" / "uat-gate.md"


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

            early_uat = run(
                project, "gate", "--slug", slug, "--name", "uat",
                "--status", "approved", "--by", "human", expect=1
            )
            assert "review 尚未完成" in early_uat.stderr
            print("✅ UAT cannot be approved before review")

            run(project, "set", "--slug", slug, "--step", "build", "--status", "done")
            run(project, "set", "--slug", slug, "--step", "security", "--status", "done")
            run(project, "result", "--slug", slug, "--kind", "verify", "--status", "PASS")
            run(project, "set", "--slug", slug, "--step", "verify", "--status", "done")
            run(project, "set", "--slug", slug, "--step", "review", "--status", "done")

            pending_uat = json.loads(
                run(project, "next", "--slug", slug, "--format", "json").stdout
            )
            assert pending_uat["command"] is None
            assert "等待人類 UAT" in pending_uat["reason"]
            print("✅ verify PASS + review done do not imply UAT approval")

            blocked_close = run(
                project, "set", "--slug", slug, "--step", "close", "--status", "done", expect=1
            )
            assert "uat=pending" in blocked_close.stderr
            print("✅ feature close is hard-blocked until Human UAT passes")

            run(
                project, "gate", "--slug", slug, "--name", "uat",
                "--status", "approved", "--by", "human",
                "--reason", "user explicitly accepted current delivery"
            )
            after_uat = json.loads(
                run(project, "next", "--slug", slug, "--format", "json").stdout
            )
            assert after_uat["command"] == "/plan-close", after_uat
            print("✅ human UAT approval unlocks plan-close recommendation")
            run(project, "set", "--slug", slug, "--step", "close", "--status", "done")
            assert load(project, slug)["steps"]["close"]["status"] == "done"
            print("✅ feature close succeeds after Human UAT approval")

            # Bug 沒有 feature review lifecycle；UAT prerequisite 依 type 調整，但 close hard gate 相同。
            bug_slug = "bug-gate-demo"
            run(project, "init", "--slug", bug_slug, "--type", "bug")
            bug_blocked_close = run(
                project, "set", "--slug", bug_slug, "--step", "close", "--status", "done", expect=1
            )
            assert "uat=pending" in bug_blocked_close.stderr
            run(
                project, "gate", "--slug", bug_slug, "--name", "uat",
                "--status", "approved", "--by", "human",
                "--reason", "user explicitly accepted current bug fix"
            )
            bug_state = load(project, bug_slug)
            assert bug_state["gates"]["uat"]["status"] == "approved"
            assert bug_state["steps"]["review"]["status"] == "pending"
            run(project, "set", "--slug", bug_slug, "--step", "close", "--status", "done")
            assert load(project, bug_slug)["steps"]["close"]["status"] == "done"
            print("✅ bug close is hard-blocked before UAT and succeeds after explicit acceptance")

            waived_slug = "waived-bug-demo"
            run(project, "init", "--slug", waived_slug, "--type", "bug")
            run(
                project, "gate", "--slug", waived_slug, "--name", "uat",
                "--status", "waived", "--by", "human", "--reason", "emergency operational waiver"
            )
            run(project, "set", "--slug", waived_slug, "--step", "close", "--status", "done")
            print("✅ explicit UAT waiver with reason also satisfies close hard gate")

            legacy = load(project, slug)
            legacy.pop("gates", None)
            legacy["steps"]["build"]["status"] = "pending"
            legacy["steps"]["close"]["status"] = "pending"
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
        verify_text = PLAN_VERIFY_SKILL.read_text(encoding="utf-8")
        close_text = PLAN_CLOSE_SKILL.read_text(encoding="utf-8")
        bug_close_text = BUG_CLOSE_SKILL.read_text(encoding="utf-8")
        uat_contract = UAT_CONTRACT.read_text(encoding="utf-8")

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

        plan_close_approvals = approved_gate_commands(close_text)
        assert len(plan_close_approvals) == 1, plan_close_approvals
        assert "--name uat --status approved --by human" in plan_close_approvals[0]

        bug_close_approvals = approved_gate_commands(bug_close_text)
        assert len(bug_close_approvals) == 1, bug_close_approvals
        assert "--name uat --status approved --by human" in bug_close_approvals[0]

        allowed_approvers = {PLAN_SKILL, PLAN_CLOSE_SKILL, BUG_CLOSE_SKILL}
        offenders = []
        for skill in sorted((REPO / "plugins").glob("*/skills/*/SKILL.md")):
            if skill in allowed_approvers:
                continue
            text_value = skill.read_text(encoding="utf-8")
            if approved_gate_commands(text_value):
                offenders.append(str(skill.relative_to(REPO)))
        assert not offenders, f"unauthorized skills may not approve gates: {offenders}"

        assert "只有使用者本輪明確核准" in plan_text
        assert "Agent 不得自行 approve" in plan_text
        print("✅ feature skills wire requirement + architecture approvals to explicit human confirmation")

        assert "不是人類 UAT 決策" in verify_text
        assert "本 skill 不得寫 `gates.uat`" in verify_text
        assert "Human UAT Gate（Runtime hard block）" in close_text
        assert "--name uat --status pending --by crew" in close_text
        assert "--name uat --status rejected --by human" in close_text
        assert "--require-gate uat" in close_text
        assert "verify=PASS" in uat_contract and "uat=approved" in uat_contract
        assert 'TRANSITION_GATES["close"] = ["uat"]' in uat_contract
        assert "type-aware" in uat_contract
        assert "本輪" in bug_close_text
        assert "--name uat --status pending --by crew" in bug_close_text
        assert "C1-C4 全綠 **不等於** UAT approved" in bug_close_text
        assert "--name uat --status rejected --by human" in bug_close_text
        assert "--require-gate uat" in bug_close_text
        print("✅ close hard gate is enforced for feature + bug with explicit Human UAT paths")

        print("✅ approval gate smoke tests passed")
        return 0
    except (AssertionError, KeyError, json.JSONDecodeError) as exc:
        print(f"❌ {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
