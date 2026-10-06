#!/usr/bin/env python3
"""Deterministic promotion gate for CREW Playwright E2E candidates.

This script never runs the target application's tests and never writes state.json.
It evaluates source/review/stability evidence plus an explicit environment policy.

Usage:
  python3 crew-e2e-promote.py check --candidate tests/foo.spec.js --metadata .crew/e2e/foo.promotion.json
  python3 crew-e2e-promote.py template --candidate tests/foo.spec.js --adapter generic-playwright
  python3 crew-e2e-promote.py fingerprint --candidate tests/foo.spec.js
  python3 crew-e2e-promote.py --self-test
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import sys
import tempfile
from dataclasses import asdict
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1
MATURITY_VALUES = {"draft", "ci-ready"}
ENVIRONMENT_GATE_VALUES = {"not-required", "deferred", "policy"}
CLEANUP_VALUES = {"reliable", "best-effort", "none"}


class PromotionError(ValueError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise PromotionError(message)


def load_linter():
    path = Path(__file__).with_name("lint-playwright-e2e.py")
    spec = importlib.util.spec_from_file_location("crew_playwright_linter", path)
    if spec is None or spec.loader is None:
        raise PromotionError(f"無法載入 Playwright linter：{path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_environment(environment: Any) -> dict[str, Any]:
    require(isinstance(environment, dict), "environment_gate=policy 時 environment 必須是 object")

    bool_keys = (
        "shared_mutation",
        "environment_bound_fixture",
        "unique_test_data",
        "disposable_environment",
        "persistent_owned_fixture",
        "idempotent_seed",
        "exclusive_execution",
        "parallel_safe",
    )
    for key in bool_keys:
        require(isinstance(environment.get(key), bool), f"environment.{key} 必須是 boolean")

    workers = environment.get("workers")
    require(isinstance(workers, int) and not isinstance(workers, bool) and workers >= 1, "environment.workers 必須是 >= 1 的整數")

    cleanup = environment.get("cleanup")
    require(cleanup in CLEANUP_VALUES, f"environment.cleanup 必須是 {sorted(CLEANUP_VALUES)}")

    safety = environment.get("safety_invariants")
    require(isinstance(safety, list), "environment.safety_invariants 必須是 array")
    require(
        all(isinstance(item, str) and item.strip() for item in safety),
        "environment.safety_invariants 每項都必須是非空字串",
    )
    return environment


def load_metadata(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise PromotionError(f"promotion metadata 不存在：{path}") from exc
    except json.JSONDecodeError as exc:
        raise PromotionError(f"promotion metadata 不是合法 JSON：{exc}") from exc

    require(isinstance(data, dict), "promotion metadata root 必須是 object")
    require(data.get("schema_version") == SCHEMA_VERSION, "schema_version 必須為 1")
    require(isinstance(data.get("candidate"), str) and data["candidate"].strip(), "candidate 必須是非空字串")
    require(isinstance(data.get("adapter"), str) and data["adapter"].strip(), "adapter 必須是非空字串")
    require(data.get("maturity", "draft") in MATURITY_VALUES, "maturity 必須是 draft 或 ci-ready")

    environment_gate = data.get("environment_gate")
    require(
        environment_gate in ENVIRONMENT_GATE_VALUES,
        "environment_gate 必須是 not-required / deferred / policy",
    )
    if environment_gate == "policy":
        validate_environment(data.get("environment"))
    elif data.get("environment") not in (None, {}):
        raise PromotionError("environment 只能在 environment_gate=policy 時提供")

    waivers = data.get("review_waivers", [])
    require(isinstance(waivers, list), "review_waivers 必須是 array")
    for index, waiver in enumerate(waivers):
        require(isinstance(waiver, dict), f"review_waivers[{index}] 必須是 object")
        require(
            isinstance(waiver.get("code"), str) and waiver["code"].strip(),
            f"review_waivers[{index}].code 必填",
        )
        require(
            isinstance(waiver.get("reason"), str) and waiver["reason"].strip(),
            f"review_waivers[{index}].reason 必填",
        )

    stability = data.get("stability")
    require(isinstance(stability, dict), "stability 必須是 object")
    for key in ("discovery", "framework_load", "headless_pass"):
        require(isinstance(stability.get(key), bool), f"stability.{key} 必須是 boolean")
    for key in ("retries", "repeat_each", "passed", "failed"):
        value = stability.get(key)
        require(
            isinstance(value, int) and not isinstance(value, bool) and value >= 0,
            f"stability.{key} 必須是非負整數",
        )

    fingerprint = stability.get("candidate_sha256")
    require(
        isinstance(fingerprint, str) and re.fullmatch(r"[0-9a-f]{64}", fingerprint) is not None,
        "stability.candidate_sha256 必須是 64 字元小寫 SHA-256",
    )

    return data


def metadata_template(candidate: str, adapter: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "candidate": candidate,
        "adapter": adapter,
        "maturity": "draft",
        "environment_gate": "deferred",
        "review_waivers": [],
        "stability": {
            "discovery": False,
            "framework_load": False,
            "headless_pass": False,
            "retries": 0,
            "repeat_each": 0,
            "passed": 0,
            "failed": 0,
            "candidate_sha256": "0" * 64,
        },
    }


def waiver_map(metadata: dict[str, Any]) -> dict[str, str]:
    return {
        waiver["code"]: waiver["reason"]
        for waiver in metadata.get("review_waivers", [])
    }


def evaluate_environment(environment: dict[str, Any]) -> list[dict[str, str]]:
    blockers: list[dict[str, str]] = []

    shared_mutation = environment["shared_mutation"]
    environment_bound = environment["environment_bound_fixture"]
    unique = environment["unique_test_data"]
    disposable = environment["disposable_environment"]
    persistent_owned = environment["persistent_owned_fixture"]
    idempotent_seed = environment["idempotent_seed"]
    exclusive_execution = environment["exclusive_execution"]
    parallel_safe = environment["parallel_safe"]
    workers = environment["workers"]
    cleanup = environment["cleanup"]
    safety = environment["safety_invariants"]

    persistent_safe = (
        persistent_owned
        and idempotent_seed
        and exclusive_execution
        and workers == 1
        and not parallel_safe
    )

    if shared_mutation and not safety:
        blockers.append({
            "code": "MISSING_SAFETY_INVARIANT",
            "reason": "shared_mutation=true 時至少要宣告一條 safety invariant",
        })

    if persistent_owned and not idempotent_seed:
        blockers.append({
            "code": "PERSISTENT_FIXTURE_NOT_IDEMPOTENT",
            "reason": "persistent_owned_fixture=true 時必須 idempotent_seed=true",
        })

    if persistent_owned and not exclusive_execution:
        blockers.append({
            "code": "PERSISTENT_FIXTURE_NO_EXCLUSIVE_EXECUTION",
            "reason": "persistent-owned fixture 必須由 CI/runtime 保證 exclusive_execution=true",
        })

    if persistent_owned and (workers != 1 or parallel_safe):
        blockers.append({
            "code": "PERSISTENT_FIXTURE_PARALLEL_UNSAFE",
            "reason": "persistent-owned fixture 必須 workers=1 且 parallel_safe=false",
        })

    if (idempotent_seed or exclusive_execution) and not persistent_owned:
        blockers.append({
            "code": "PERSISTENT_FIXTURE_FLAGS_WITHOUT_OWNERSHIP",
            "reason": "idempotent_seed/exclusive_execution 只能搭配 persistent_owned_fixture=true",
        })

    if shared_mutation and cleanup != "reliable" and not disposable and not persistent_safe:
        blockers.append({
            "code": "UNRELIABLE_CLEANUP",
            "reason": (
                "shared mutation 必須 cleanup=reliable、disposable environment，"
                "或滿足 persistent-owned fixture contract"
            ),
        })

    if environment_bound and cleanup != "reliable" and not disposable and not persistent_safe:
        blockers.append({
            "code": "ENV_FIXTURE_NOT_RESTORABLE",
            "reason": (
                "environment-bound fixture 無 reliable restoration/disposable environment，"
                "也未滿足 persistent-owned fixture contract"
            ),
        })

    if parallel_safe and shared_mutation and not unique and not disposable:
        blockers.append({
            "code": "PARALLEL_FIXTURE_COLLISION",
            "reason": "parallel shared mutation 需要 unique_test_data=true 或 disposable environment",
        })

    if workers > 1 and not parallel_safe:
        blockers.append({
            "code": "WORKERS_EXCEED_PARALLEL_CONTRACT",
            "reason": f"workers={workers} 但 parallel_safe=false",
        })

    return blockers


def evaluate(candidate: Path, metadata: dict[str, Any]) -> dict[str, Any]:
    require(candidate.is_file(), f"candidate 不存在：{candidate}")

    linter = load_linter()
    text = candidate.read_text(encoding="utf-8")
    issues = linter.lint_text(candidate, text)

    hard_issues = [issue for issue in issues if issue.severity == "HARD"]
    review_issues = [issue for issue in issues if issue.severity == "REVIEW"]
    waivers = waiver_map(metadata)

    blockers: list[dict[str, str]] = []
    reviews: list[dict[str, Any]] = []

    metadata_candidate = Path(metadata["candidate"]).resolve()
    actual_candidate = candidate.resolve()
    if metadata_candidate != actual_candidate:
        blockers.append({
            "code": "CANDIDATE_METADATA_MISMATCH",
            "reason": (
                f"metadata candidate={metadata['candidate']!r}，"
                f"實際 candidate={str(candidate)!r}"
            ),
        })

    for issue in hard_issues:
        blockers.append({
            "code": f"STATIC_{issue.code}",
            "reason": f"{candidate}:{issue.line} {issue.message}",
        })

    for issue in review_issues:
        waiver_reason = waivers.get(issue.code)
        reviews.append({
            "code": issue.code,
            "line": issue.line,
            "message": issue.message,
            "waived": bool(waiver_reason),
            "waiver_reason": waiver_reason,
        })
        if not waiver_reason:
            blockers.append({
                "code": f"REVIEW_{issue.code}",
                "reason": f"{candidate}:{issue.line} 需要 review/waiver：{issue.message}",
            })

    environment_gate = metadata["environment_gate"]
    if environment_gate == "deferred":
        blockers.append({
            "code": "ENVIRONMENT_GATE_DEFERRED",
            "reason": "environment review 尚未完成",
        })
    elif environment_gate == "not-required":
        if any(issue.code == "FIXED_RECORD_ID" for issue in review_issues):
            blockers.append({
                "code": "ENVIRONMENT_POLICY_REQUIRED",
                "reason": "source 含固定 record ID；不得以 environment_gate=not-required 繞過 fixture policy",
            })
    elif environment_gate == "policy":
        blockers.extend(evaluate_environment(metadata["environment"]))

    stability = metadata["stability"]
    current_sha256 = sha256_file(candidate)
    if stability["candidate_sha256"] != current_sha256:
        blockers.append({
            "code": "STALE_STABILITY_EVIDENCE",
            "reason": "candidate SHA-256 已改變；必須重新跑 stability",
        })
    if not stability["discovery"]:
        blockers.append({"code": "DISCOVERY_NOT_PROVEN", "reason": "Playwright test discovery 尚未成功"})
    if not stability["framework_load"]:
        blockers.append({"code": "FRAMEWORK_LOAD_NOT_PROVEN", "reason": "framework/config load 尚未成功"})
    if not stability["headless_pass"]:
        blockers.append({"code": "HEADLESS_NOT_PROVEN", "reason": "headless 單跑尚未成功"})
    if stability["retries"] != 0:
        blockers.append({"code": "PROMOTION_RETRIES_NOT_ZERO", "reason": "promotion 必須 retries=0"})
    if stability["repeat_each"] < 3:
        blockers.append({"code": "INSUFFICIENT_REPEATS", "reason": "promotion 至少需要 repeat_each >= 3"})
    if stability["failed"] != 0:
        blockers.append({
            "code": "STABILITY_FAILURE",
            "reason": f"promotion stability run 有 {stability['failed']} 次失敗",
        })
    if stability["repeat_each"] >= 3 and stability["passed"] < stability["repeat_each"]:
        blockers.append({
            "code": "INCOMPLETE_STABILITY_PASS",
            "reason": (
                f"repeat_each={stability['repeat_each']}，"
                f"但 passed={stability['passed']}，沒有每次都成功"
            ),
        })

    maturity = "ci-ready" if not blockers else "draft"
    result = {
        "schema_version": SCHEMA_VERSION,
        "candidate": str(candidate),
        "adapter": metadata["adapter"],
        "maturity": maturity,
        "environment_gate": environment_gate,
        "stability": stability | {"current_candidate_sha256": current_sha256},
        "static": {
            "hard": [asdict(issue) | {"path": str(issue.path)} for issue in hard_issues],
            "review": reviews,
        },
        "blockers": blockers,
    }
    if environment_gate == "policy":
        result["environment"] = metadata["environment"]
    return result


def print_human(result: dict[str, Any]) -> None:
    if result["maturity"] == "ci-ready":
        print("✅ E2E promotion: ci-ready")
    else:
        print("🚧 E2E promotion: draft（尚未通過）")

    print(
        "stability: "
        f"retries={result['stability']['retries']} "
        f"repeat_each={result['stability']['repeat_each']} "
        f"passed={result['stability']['passed']} "
        f"failed={result['stability']['failed']}"
    )
    print(f"environment_gate: {result['environment_gate']}")

    for blocker in result["blockers"]:
        print(f"❌ [{blocker['code']}] {blocker['reason']}")

    for item in result["static"]["review"]:
        if item["waived"]:
            print(f"⚠️ [{item['code']}] 已 waiver：{item['waiver_reason']}")


def command_check(args: argparse.Namespace) -> int:
    try:
        metadata = load_metadata(Path(args.metadata))
        result = evaluate(Path(args.candidate), metadata)
    except (PromotionError, OSError, UnicodeError) as exc:
        print(f"❌ {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print_human(result)

    return 0 if result["maturity"] == "ci-ready" else 1


def command_template(args: argparse.Namespace) -> int:
    print(json.dumps(metadata_template(args.candidate, args.adapter), ensure_ascii=False, indent=2))
    return 0


def command_fingerprint(args: argparse.Namespace) -> int:
    candidate = Path(args.candidate)
    if not candidate.is_file():
        print(f"❌ candidate 不存在：{candidate}", file=sys.stderr)
        return 2
    print(sha256_file(candidate))
    return 0


def stable_evidence(candidate: Path) -> dict[str, Any]:
    return {
        "discovery": True,
        "framework_load": True,
        "headless_pass": True,
        "retries": 0,
        "repeat_each": 3,
        "passed": 3,
        "failed": 0,
        "candidate_sha256": sha256_file(candidate),
    }


def safe_environment(**overrides: Any) -> dict[str, Any]:
    environment = {
        "shared_mutation": False,
        "environment_bound_fixture": False,
        "unique_test_data": False,
        "disposable_environment": False,
        "persistent_owned_fixture": False,
        "idempotent_seed": False,
        "exclusive_execution": False,
        "parallel_safe": False,
        "workers": 1,
        "cleanup": "none",
        "safety_invariants": [],
    }
    environment.update(overrides)
    return environment


def self_test() -> int:
    clean_spec = """
const { test, expect } = require('@playwright/test');
test('feature-x#AC-1 renders', async ({ page }) => {
  await test.step('feature-x#AC-1: render', async () => {
    await expect(page.getByRole('main')).toBeVisible();
  });
});
""".strip()

    fixed_record_spec = """
const { test, expect } = require('@playwright/test');
test('feature-z#AC-3 fixed fixture', async ({ page }) => {
  await page.goto('/example?id=5');
  await expect(page.getByRole('main')).toBeVisible();
});
""".strip()

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        clean_path = root / "clean.spec.js"
        fixed_path = root / "fixed.spec.js"
        clean_path.write_text(clean_spec, encoding="utf-8")
        fixed_path.write_text(fixed_record_spec, encoding="utf-8")

        base = metadata_template(str(clean_path), "generic-playwright")
        base["environment_gate"] = "not-required"
        base["stability"] = stable_evidence(clean_path)
        ready = evaluate(clean_path, base)
        assert ready["maturity"] == "ci-ready", ready

        deferred = dict(base)
        deferred["environment_gate"] = "deferred"
        deferred_result = evaluate(clean_path, deferred)
        assert any(item["code"] == "ENVIRONMENT_GATE_DEFERRED" for item in deferred_result["blockers"]), deferred_result

        fixed = metadata_template(str(fixed_path), "generic-playwright")
        fixed["environment_gate"] = "not-required"
        fixed["review_waivers"] = [{"code": "FIXED_RECORD_ID", "reason": "fixture is intentionally fixed"}]
        fixed["stability"] = stable_evidence(fixed_path)
        fixed_result = evaluate(fixed_path, fixed)
        assert any(item["code"] == "ENVIRONMENT_POLICY_REQUIRED" for item in fixed_result["blockers"]), fixed_result

        reliable = dict(fixed)
        reliable["environment_gate"] = "policy"
        reliable["environment"] = safe_environment(
            shared_mutation=True,
            environment_bound_fixture=True,
            cleanup="reliable",
            safety_invariants=["restore fixture after mutation"],
        )
        reliable_result = evaluate(fixed_path, reliable)
        assert reliable_result["maturity"] == "ci-ready", reliable_result

        unsafe = dict(reliable)
        unsafe["environment"] = safe_environment(
            shared_mutation=True,
            environment_bound_fixture=True,
            cleanup="best-effort",
            safety_invariants=["mutate only test fixture"],
        )
        unsafe_result = evaluate(fixed_path, unsafe)
        unsafe_codes = {item["code"] for item in unsafe_result["blockers"]}
        assert "UNRELIABLE_CLEANUP" in unsafe_codes, unsafe_result
        assert "ENV_FIXTURE_NOT_RESTORABLE" in unsafe_codes, unsafe_result

        disposable = dict(reliable)
        disposable["environment"] = safe_environment(
            shared_mutation=True,
            environment_bound_fixture=True,
            disposable_environment=True,
            cleanup="none",
            safety_invariants=["mutate only isolated namespace"],
        )
        disposable_result = evaluate(fixed_path, disposable)
        assert disposable_result["maturity"] == "ci-ready", disposable_result

        persistent = dict(reliable)
        persistent["environment"] = safe_environment(
            shared_mutation=True,
            environment_bound_fixture=True,
            persistent_owned_fixture=True,
            idempotent_seed=True,
            exclusive_execution=True,
            parallel_safe=False,
            workers=1,
            cleanup="none",
            safety_invariants=["mutate only CREW_E2E-owned records"],
        )
        persistent_result = evaluate(fixed_path, persistent)
        assert persistent_result["maturity"] == "ci-ready", persistent_result

        unlocked = dict(persistent)
        unlocked["environment"] = dict(persistent["environment"])
        unlocked["environment"]["exclusive_execution"] = False
        unlocked_result = evaluate(fixed_path, unlocked)
        assert any(
            item["code"] == "PERSISTENT_FIXTURE_NO_EXCLUSIVE_EXECUTION"
            for item in unlocked_result["blockers"]
        ), unlocked_result

        parallel = dict(reliable)
        parallel["environment"] = safe_environment(
            shared_mutation=True,
            unique_test_data=False,
            parallel_safe=True,
            workers=2,
            cleanup="reliable",
            safety_invariants=["mutate only test records"],
        )
        parallel_result = evaluate(fixed_path, parallel)
        assert any(
            item["code"] == "PARALLEL_FIXTURE_COLLISION"
            for item in parallel_result["blockers"]
        ), parallel_result

        stale = dict(base)
        stale["stability"] = dict(base["stability"])
        stale["stability"]["candidate_sha256"] = "f" * 64
        stale_result = evaluate(clean_path, stale)
        assert any(item["code"] == "STALE_STABILITY_EVIDENCE" for item in stale_result["blockers"]), stale_result

    print("✅ crew-e2e-promote self-test passed")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate CREW E2E promotion readiness")
    parser.add_argument("--self-test", action="store_true")
    sub = parser.add_subparsers(dest="command")

    check = sub.add_parser("check")
    check.add_argument("--candidate", required=True)
    check.add_argument("--metadata", required=True)
    check.add_argument("--json", action="store_true")

    template = sub.add_parser("template")
    template.add_argument("--candidate", required=True)
    template.add_argument("--adapter", required=True)

    fingerprint = sub.add_parser("fingerprint")
    fingerprint.add_argument("--candidate", required=True)

    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.self_test:
        return self_test()
    if args.command == "check":
        return command_check(args)
    if args.command == "template":
        return command_template(args)
    if args.command == "fingerprint":
        return command_fingerprint(args)
    print("❌ 請使用 check / template / fingerprint 或 --self-test", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
