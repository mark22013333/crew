#!/usr/bin/env python3
"""Validate and summarize CREW E2E result artifacts.

This script is the deterministic bridge for /plan-verify --from-e2e.
It never writes state.json. The caller must use crew-state.py for state changes.

Usage:
  python3 crew-e2e-results.py summarize --file test-results/crew-results.json --slug feature-x
  python3 crew-e2e-results.py summarize --file ... --slug feature-x --expected-git-sha abc123
  python3 crew-e2e-results.py --self-test
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
from collections import defaultdict
from pathlib import Path
from typing import Any


AC_RE = re.compile(r"^(?P<slug>[A-Za-z0-9][A-Za-z0-9._-]*)#AC-(?P<number>[1-9]\d*)$")
ALLOWED_STATUSES = {"passed", "failed", "flaky", "blocked", "skipped", "manual"}
ALLOWED_COVERAGE = {"full", "partial"}

# For multiple test records covering the same AC, the least healthy outcome wins.
STATUS_PRIORITY = {
    "passed": 0,
    "skipped": 1,
    "manual": 2,
    "flaky": 3,
    "blocked": 4,
    "failed": 5,
}

VERIFY_STATUS = {
    "passed": "PASS",
    "failed": "FAIL",
    "flaky": "WARN",
    "blocked": "BLOCKED",
    "skipped": "SKIP",
    "manual": "MANUAL",
}


class ValidationError(ValueError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationError(message)


def load_payload(file_path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(file_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValidationError(f"result file 不存在：{file_path}") from exc
    except json.JSONDecodeError as exc:
        raise ValidationError(f"result file 不是合法 JSON：{exc}") from exc

    require(isinstance(payload, dict), "root 必須是 JSON object")
    require(payload.get("schema_version") == 1, "schema_version 必須為 1")
    require(isinstance(payload.get("runner"), str) and payload["runner"].strip(), "runner 必須是非空字串")
    require(isinstance(payload.get("environment"), str) and payload["environment"].strip(), "environment 必須是非空字串")
    require(isinstance(payload.get("results"), list), "results 必須是 array")
    return payload


def validate_result(item: Any, index: int) -> dict[str, Any]:
    require(isinstance(item, dict), f"results[{index}] 必須是 object")

    ac = item.get("ac")
    require(isinstance(ac, str) and AC_RE.match(ac) is not None, f"results[{index}].ac 必須符合 {{slug}}#AC-n")

    status = item.get("status")
    require(status in ALLOWED_STATUSES, f"results[{index}].status 不支援：{status!r}")

    attempts = item.get("attempts", 1)
    require(isinstance(attempts, int) and attempts >= 1, f"results[{index}].attempts 必須 >= 1")

    duration = item.get("duration_ms", 0)
    require(isinstance(duration, (int, float)) and duration >= 0, f"results[{index}].duration_ms 必須 >= 0")

    coverage = item.get("coverage", "full")
    require(coverage in ALLOWED_COVERAGE, f"results[{index}].coverage 不支援：{coverage!r}")

    if status == "blocked":
        reason = item.get("reason")
        require(isinstance(reason, str) and reason.strip(), f"results[{index}] blocked 必須有 reason")

    scenario = item.get("scenario")
    if scenario is not None:
        require(isinstance(scenario, str), f"results[{index}].scenario 必須是字串")

    return item


def aggregate_ac(items: list[dict[str, Any]]) -> dict[str, Any]:
    require(items, "aggregate_ac 不可接收空清單")

    worst = max(items, key=lambda item: STATUS_PRIORITY[item["status"]])
    status = worst["status"]
    coverage = "full" if any(item.get("coverage", "full") == "full" for item in items) else "partial"
    reasons = []
    for item in items:
        reason = item.get("reason")
        if reason and reason not in reasons:
            reasons.append(reason)

    evidence: list[dict[str, Any]] = []
    for item in items:
        ev = item.get("evidence")
        if isinstance(ev, dict) and ev and ev not in evidence:
            evidence.append(ev)

    scenarios = []
    for item in items:
        scenario = item.get("scenario")
        if scenario and scenario not in scenarios:
            scenarios.append(scenario)

    return {
        "ac": items[0]["ac"],
        "status": status,
        "coverage": coverage,
        "verify_status": "WARN" if status == "passed" and coverage == "partial" else VERIFY_STATUS[status],
        "records": len(items),
        "attempts": sum(int(item.get("attempts", 1)) for item in items),
        "duration_ms": int(sum(float(item.get("duration_ms", 0)) for item in items)),
        "reason": " | ".join(reasons) if reasons else None,
        "scenarios": scenarios,
        "evidence": evidence,
    }


def summarize(payload: dict[str, Any], slug: str, expected_git_sha: str | None = None) -> dict[str, Any]:
    validated = [validate_result(item, i) for i, item in enumerate(payload["results"])]

    scoped: list[dict[str, Any]] = []
    ignored = 0
    for item in validated:
        match = AC_RE.match(item["ac"])
        assert match is not None
        if match.group("slug") == slug:
            scoped.append(item)
        else:
            ignored += 1

    require(scoped, f"result artifact 沒有目前 slug {slug!r} 的 AC")

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in scoped:
        grouped[item["ac"]].append(item)

    ac_results = [
        aggregate_ac(grouped[key])
        for key in sorted(
            grouped,
            key=lambda ac: int(AC_RE.match(ac).group("number")),  # type: ignore[union-attr]
        )
    ]

    counts = {status: 0 for status in sorted(ALLOWED_STATUSES)}
    partial_coverage = 0
    for item in ac_results:
        counts[item["status"]] += 1
        if item["coverage"] == "partial":
            partial_coverage += 1

    stale = False
    artifact_sha = payload.get("git_sha")
    if expected_git_sha and artifact_sha:
        stale = not (
            str(expected_git_sha).startswith(str(artifact_sha))
            or str(artifact_sha).startswith(str(expected_git_sha))
        )

    if counts["failed"] > 0:
        overall = "FAIL"
    elif counts["blocked"] > 0 or counts["flaky"] > 0 or partial_coverage > 0 or stale:
        overall = "WARN"
    else:
        overall = "PASS"

    return {
        "schema_version": 1,
        "slug": slug,
        "runner": payload["runner"],
        "environment": payload["environment"],
        "git_sha": artifact_sha,
        "expected_git_sha": expected_git_sha,
        "stale": stale,
        "status": overall,
        "counts": {
            "passed": counts["passed"],
            "failed": counts["failed"],
            "flaky": counts["flaky"],
            "blocked": counts["blocked"],
            "skipped": counts["skipped"],
            "manual": counts["manual"],
        },
        "partial_coverage": partial_coverage,
        "ignored_results": ignored,
        "ac_results": ac_results,
    }


def command_summarize(args: argparse.Namespace) -> int:
    try:
        payload = load_payload(Path(args.file))
        result = summarize(payload, args.slug, args.expected_git_sha)
    except ValidationError as exc:
        print(f"❌ {exc}", file=sys.stderr)
        return 1

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def self_test() -> int:
    payload = {
        "schema_version": 1,
        "runner": "playwright",
        "environment": "self-test",
        "git_sha": "abc123",
        "results": [
            {"ac": "feature-x#AC-1", "status": "passed", "attempts": 1, "duration_ms": 10},
            {"ac": "feature-x#AC-2", "status": "passed", "attempts": 1, "duration_ms": 10},
            {
                "ac": "feature-x#AC-2",
                "status": "flaky",
                "attempts": 2,
                "duration_ms": 20,
                "reason": "first attempt failed",
            },
            {
                "ac": "feature-x#AC-3",
                "status": "blocked",
                "attempts": 1,
                "duration_ms": 1,
                "reason": "fixture unavailable",
            },
            {
                "ac": "feature-x#AC-4",
                "status": "passed",
                "coverage": "partial",
                "attempts": 1,
                "duration_ms": 8,
                "reason": "browser half only",
            },
            {"ac": "other#AC-1", "status": "failed", "attempts": 1, "duration_ms": 1},
        ],
    }

    result = summarize(payload, "feature-x", "abc1234")
    assert result["status"] == "WARN", result
    assert result["counts"]["passed"] == 1, result
    assert result["counts"]["flaky"] == 1, result
    assert result["counts"]["blocked"] == 1, result
    assert result["partial_coverage"] == 1, result
    assert result["ignored_results"] == 1, result
    assert result["ac_results"][1]["status"] == "flaky", result
    assert result["ac_results"][3]["coverage"] == "partial", result
    assert result["ac_results"][3]["verify_status"] == "WARN", result
    assert result["stale"] is False, result

    stale = summarize(payload, "feature-x", "zzz999")
    assert stale["stale"] is True, stale
    assert stale["status"] == "WARN", stale

    bad = dict(payload)
    bad["results"] = [{"ac": "feature-x#AC-1", "status": "blocked"}]
    try:
        summarize(bad, "feature-x")
    except ValidationError as exc:
        assert "reason" in str(exc)
    else:
        raise AssertionError("blocked without reason should fail validation")

    bad_coverage = dict(payload)
    bad_coverage["results"] = [{"ac": "feature-x#AC-1", "status": "passed", "coverage": "half"}]
    try:
        summarize(bad_coverage, "feature-x")
    except ValidationError as exc:
        assert "coverage" in str(exc)
    else:
        raise AssertionError("unknown coverage should fail validation")

    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "crew-results.json"
        p.write_text(json.dumps(payload), encoding="utf-8")
        loaded = load_payload(p)
        assert loaded["schema_version"] == 1

    print("✅ crew-e2e-results self-test passed")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate and summarize CREW E2E results")
    parser.add_argument("--self-test", action="store_true")
    sub = parser.add_subparsers(dest="command")

    summarize_parser = sub.add_parser("summarize")
    summarize_parser.add_argument("--file", required=True)
    summarize_parser.add_argument("--slug", required=True)
    summarize_parser.add_argument("--expected-git-sha")

    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.self_test:
        return self_test()
    if args.command == "summarize":
        return command_summarize(args)
    print("❌ 請使用 summarize 或 --self-test", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
