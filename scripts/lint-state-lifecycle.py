#!/usr/bin/env python3
"""Smoke-test type-aware feature/bug state lifecycle semantics."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CLI = REPO / "plugins" / "bug-workflow" / "scripts" / "crew-state.py"
BUG_START_SKILL = REPO / "plugins" / "bug-workflow" / "skills" / "bug-start" / "SKILL.md"
BUG_INVESTIGATE_SKILL = REPO / "plugins" / "bug-workflow" / "skills" / "bug-investigate" / "SKILL.md"
FEATURE_STEPS = {"start", "spec", "db", "arch", "build", "security", "verify", "review", "close"}
BUG_STEPS = {"start", "investigate", "fix", "close"}


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


def load(project: Path, slug: str) -> dict:
    return json.loads((project / ".spec" / slug / "state.json").read_text(encoding="utf-8"))


def next_json(project: Path, slug: str) -> dict:
    return json.loads(run(project, "next", "--slug", slug, "--format", "json").stdout)


def main() -> int:
    try:
        with tempfile.TemporaryDirectory() as raw:
            project = Path(raw)

            feature = "feature-demo"
            run(project, "init", "--slug", feature, "--type", "feature")
            feature_state = load(project, feature)
            assert feature_state["schema_version"] == 2
            assert set(feature_state["steps"]) == FEATURE_STEPS
            assert next_json(project, feature)["command"] == "/plan spec"
            bad_feature = run(
                project, "set", "--slug", feature, "--step", "investigate", "--status", "done", expect=1
            )
            assert "feature 任務不支援 step=investigate" in bad_feature.stderr
            print("✅ feature lifecycle remains isolated from bug steps")

            bug = "bug-demo"
            run(project, "init", "--slug", bug, "--type", "bug")
            bug_state = load(project, bug)
            assert bug_state["schema_version"] == 2
            assert set(bug_state["steps"]) == BUG_STEPS
            assert bug_state["phase"] == "start"
            assert next_json(project, bug)["command"] == "/bug-investigate"
            bad_bug = run(
                project, "set", "--slug", bug, "--step", "spec", "--status", "done", expect=1
            )
            assert "bug 任務不支援 step=spec" in bad_bug.stderr
            print("✅ bug init exposes only start/investigate/fix/close")

            run(project, "set", "--slug", bug, "--step", "investigate", "--status", "in_progress")
            run(
                project, "unit", "--slug", bug, "--skill", "bug-investigate",
                "--done", "0", "--total", "1", "--label", "假說",
                "--remaining", "建立並驗證第一個可驗證根因假說"
            )
            assert load(project, bug)["phase"] == "investigate"
            assert next_json(project, bug)["command"] == "/bug-investigate --resume"

            run(
                project, "unit", "--slug", bug, "--skill", "bug-investigate",
                "--done", "1", "--total", "2", "--label", "假說",
                "--evidence", "假說 #1 已否定", "--remaining", "假說 #2"
            )
            assert next_json(project, bug)["command"] == "/bug-investigate --resume"
            assert load(project, bug)["work_unit"]["done"] == 1
            assert load(project, bug)["work_unit"]["total"] == 2

            run(
                project, "unit", "--slug", bug, "--skill", "bug-investigate",
                "--done", "2", "--total", "2", "--label", "假說",
                "--evidence", "假說 #2 已確認根因"
            )
            run(project, "unit", "--slug", bug, "--clear")
            run(project, "set", "--slug", bug, "--step", "investigate", "--status", "done")
            assert next_json(project, bug)["command"] == "/bug-fix"
            run(project, "validate", "--slug", bug, "--expect-phase", "investigate")
            assert load(project, bug)["work_unit"]["skill"] is None
            print("✅ bug-investigate persists resumable hypothesis units and closes only after root cause confirmation")

            run(project, "set", "--slug", bug, "--step", "fix", "--status", "done")
            pending_uat = next_json(project, bug)
            assert pending_uat["command"] == "/bug-close"
            assert "Human UAT" in pending_uat["reason"]
            blocked = run(
                project, "set", "--slug", bug, "--step", "close", "--status", "done", expect=1
            )
            assert "uat=pending" in blocked.stderr

            run(
                project, "gate", "--slug", bug, "--name", "uat",
                "--status", "rejected", "--by", "human", "--reason", "needs another fix"
            )
            assert next_json(project, bug)["command"] == "/bug-fix"
            run(project, "gate", "--slug", bug, "--name", "uat", "--status", "pending", "--by", "crew")
            run(
                project, "gate", "--slug", bug, "--name", "uat",
                "--status", "approved", "--by", "human", "--reason", "accepted"
            )
            run(project, "set", "--slug", bug, "--step", "close", "--status", "done")
            assert next_json(project, bug)["command"] is None
            assert "/bug-start" in next_json(project, bug)["reason"]
            print("✅ bug UAT reject returns to fix; approval unlocks close")

            legacy = "legacy-bug"
            legacy_dir = project / ".spec" / legacy
            legacy_dir.mkdir(parents=True)
            legacy_state = {
                "schema_version": 1,
                "slug": legacy,
                "name": legacy,
                "type": "bug",
                "phase": "build",
                "steps": {
                    step: {"status": "pending", "at": None, "commit": None, "reason": None}
                    for step in FEATURE_STEPS
                },
                "work_unit": {
                    "skill": "bug-fix", "done": 0, "total": 0, "label": "",
                    "remaining": [], "evidence": [], "ambiguities": []
                },
            }
            legacy_state["steps"]["start"]["status"] = "done"
            (legacy_dir / "state.json").write_text(
                json.dumps(legacy_state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
            run(project, "set", "--slug", legacy, "--last-commit", "abc123")
            migrated = load(project, legacy)
            assert migrated["schema_version"] == 2
            assert set(migrated["steps"]) == BUG_STEPS
            assert migrated["phase"] == "fix"
            assert next_json(project, legacy)["command"] == "/bug-investigate"
            print("✅ schema v1 bug state normalizes to v2 without fake feature progress")

        bug_start_text = BUG_START_SKILL.read_text(encoding="utf-8")
        bug_investigate_text = BUG_INVESTIGATE_SKILL.read_text(encoding="utf-8")
        assert 'crew-state.py" init' in bug_start_text
        assert "--type bug" in bug_start_text
        assert "--expect-phase start" in bug_start_text
        assert 'next.command == "/bug-investigate"' in bug_start_text
        assert "不建立 `plan.md`" in bug_start_text
        assert "不得使用 `--force`" in bug_start_text
        assert "Notion API 失敗不阻擋本地 state 建立" in bug_start_text
        print("✅ bug-start wires Notion intake to minimal bug runtime state")

        assert "--step investigate --status in_progress" in bug_investigate_text
        assert "--skill bug-investigate --done 0 --total 1" in bug_investigate_text
        assert "/bug-investigate --resume" in bug_investigate_text
        assert "--step investigate --status done" in bug_investigate_text
        assert "--expect-phase investigate" in bug_investigate_text
        assert 'next.command == "/bug-fix"' in bug_investigate_text
        assert "不得自行 `init --force`" in bug_investigate_text
        assert "state.notion.page_id" in bug_investigate_text
        print("✅ bug-investigate wires resumable runtime progress and done transition")

        print("✅ type-aware state lifecycle smoke tests passed")
        return 0
    except (AssertionError, KeyError, json.JSONDecodeError) as exc:
        print(f"❌ {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
