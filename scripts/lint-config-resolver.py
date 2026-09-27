#!/usr/bin/env python3
"""Deterministic smoke tests for the CREW portable config resolver."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
RESOLVER = REPO / "plugins" / "bug-workflow" / "scripts" / "crew-config.py"


def run(env: dict[str, str], *args: str, expect: int = 0) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(
        [sys.executable, str(RESOLVER), "resolve", *args],
        text=True,
        capture_output=True,
        env=env,
    )
    if proc.returncode != expect:
        raise AssertionError(
            f"{' '.join(args)} => {proc.returncode}, expected {expect}\n"
            f"stdout={proc.stdout}\nstderr={proc.stderr}"
        )
    return proc


def data(env: dict[str, str], *args: str) -> dict:
    return json.loads(run(env, *args, "--format", "json").stdout)


def touch(path: Path, text: str = "x") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def main() -> int:
    try:
        with tempfile.TemporaryDirectory() as raw:
            base = Path(raw)
            home = base / "home"
            xdg = base / "xdg"
            home.mkdir()
            env = os.environ.copy()
            env["HOME"] = str(home)
            env["XDG_CONFIG_HOME"] = str(xdg)
            env.pop("CREW_CONFIG_HOME", None)

            missing = data(env, "--key", "feature/config", "--mode", "read")
            expected_feature = xdg / "crew" / "feature" / "config.md"
            assert missing["source"] == "missing"
            assert Path(missing["path"]) == expected_feature
            assert not expected_feature.exists()
            print("✅ missing read returns canonical path without creating files")

            write = data(env, "--key", "feature/config", "--mode", "write")
            assert Path(write["path"]) == expected_feature
            assert write["source"] == "portable"
            assert not expected_feature.exists()
            print("✅ write resolution is side-effect free and always canonical")

            legacy_feature = home / ".claude" / "feature-workflow" / "config.md"
            touch(legacy_feature)
            resolved = data(env, "--key", "feature/config", "--mode", "read")
            assert Path(resolved["path"]) == legacy_feature
            assert resolved["source"] == "legacy"
            assert resolved["representation"] == "hierarchical"

            touch(expected_feature)
            preferred = data(env, "--key", "feature/config", "--mode", "read")
            assert Path(preferred["path"]) == expected_feature
            assert preferred["source"] == "portable"
            print("✅ portable config wins over legacy fallback")

            project = data(
                env,
                "--key", "feature/project",
                "--repo-id", "github.com/org/repo.git",
                "--mode", "write",
            )
            assert Path(project["path"]).name == "github.com--org--repo.md"
            assert Path(project["path"]).parent == xdg / "crew" / "feature" / "projects"

            monolith = home / ".claude-company" / "feature-workflow-config.md"
            touch(monolith)
            project_read = data(
                env,
                "--key", "feature/project",
                "--repo-id", "ORG01P2401/PushAPIService",
                "--mode", "read",
            )
            assert Path(project_read["path"]) == monolith
            assert project_read["representation"] == "legacy_monolith"
            print("✅ feature project supports hierarchical and monolith legacy representations")

            bug_legacy = home / ".claude-company" / "bug-workflow-config.md"
            touch(bug_legacy)
            bug_config = data(env, "--key", "bug/config", "--mode", "read")
            assert Path(bug_config["path"]) == bug_legacy
            assert bug_config["legacy"] is True

            learning = data(
                env,
                "--key", "bug/learning",
                "--project-slug", "github.com-org-repo",
                "--mode", "write",
            )
            assert Path(learning["path"]) == xdg / "crew" / "bug" / "learnings" / "github.com-org-repo.jsonl"
            print("✅ bug config/learnings resolve through portable contract")

            override = base / "custom-crew"
            env["CREW_CONFIG_HOME"] = str(override)
            explicit = data(env, "--key", "feature/stack", "--stack-id", "spring-boot-jpa", "--mode", "write")
            assert Path(explicit["root"]) == override
            assert Path(explicit["path"]) == override / "feature" / "stacks" / "spring-boot-jpa.md"
            print("✅ CREW_CONFIG_HOME overrides XDG/default root")

            bad = run(
                env,
                "--key", "bug/learning",
                "--project-slug", "../escape",
                "--mode", "write",
                expect=2,
            )
            assert "不得包含路徑分隔符" in bad.stderr
            print("✅ unsafe path traversal input is rejected")

        print("✅ portable config resolver smoke tests passed")
        return 0
    except (AssertionError, KeyError, json.JSONDecodeError) as exc:
        print(f"❌ {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
