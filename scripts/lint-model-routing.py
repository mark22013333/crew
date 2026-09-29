#!/usr/bin/env python3
"""Smoke-test CREW model routing policy with deterministic expectations."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ROUTER = REPO / "plugins" / "bug-workflow" / "scripts" / "crew-model-route.py"


def run(*args: str) -> dict:
    proc = subprocess.run(
        [sys.executable, str(ROUTER), "route", *args, "--format", "json"],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise AssertionError(proc.stderr or proc.stdout)
    return json.loads(proc.stdout)


def expect(label: str, result: dict, profile: str, **mapping) -> None:
    if result["profile"] != profile:
        raise AssertionError(f"{label}: profile={result['profile']} expected={profile}")
    for key, value in mapping.items():
        actual = result["host_mapping"].get(key)
        if actual != value:
            raise AssertionError(f"{label}: {key}={actual!r} expected={value!r}")
    print(f"✅ {label}: {profile} {result['host_mapping']}")


def main() -> int:
    validate = subprocess.run(
        [sys.executable, str(ROUTER), "validate"],
        capture_output=True,
        text=True,
    )
    if validate.returncode != 0:
        print(validate.stderr or validate.stdout)
        return 1
    print(validate.stdout.strip())

    cases = [
        ("deterministic", run("--task", "git_diff", "--host", "claude"), "NONE", {"model": None}),
        ("fast-search", run("--task", "repository_search", "--host", "claude"), "FAST", {"model": "haiku", "effort": "low"}),
        ("standard-analysis", run("--task", "requirement_analysis", "--host", "claude"), "STANDARD", {"model": "sonnet", "effort": "medium"}),
        ("deep-architecture", run("--task", "architecture", "--host", "claude"), "DEEP", {"model": "opus", "effort": "high"}),
        ("risk-escalation", run("--task", "repository_search", "--risk", "high", "--host", "claude"), "DEEP", {"model": "opus"}),
        ("sensitive-escalation", run("--task", "routine_implementation", "--sensitive", "transaction", "--host", "claude"), "DEEP", {"model": "opus"}),
        ("failure-escalation", run("--task", "debugging", "--failures", "2", "--host", "claude"), "DEEP", {"model": "opus"}),
        ("codex-fast", run("--task", "evidence_collection", "--host", "codex"), "FAST", {"model": "inherit", "reasoning_effort": "low"}),
    ]

    try:
        for label, result, profile, mapping in cases:
            expect(label, result, profile, **mapping)
    except AssertionError as exc:
        print(f"❌ {exc}")
        return 1

    print(f"✅ model routing smoke tests: {len(cases)} cases")
    return 0


if __name__ == "__main__":
    sys.exit(main())
