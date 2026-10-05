#!/usr/bin/env python3
"""Deterministic promotion gate for CREW Playwright E2E candidates.

The static source linter catches code-level issues. This script additionally
checks fixture/safety metadata and recorded stability evidence before an asset
may be called ci-ready.

It never runs a target application's tests and never writes state.json.

Usage:
  python3 crew-e2e-promote.py check --candidate tests/foo.spec.js --metadata crew-promotion.json
  python3 crew-e2e-promote.py template --candidate tests/foo.spec.js --adapter generic-playwright
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
CLEANUP_VALUES = {"reliable", "best-effort", "none"}
MATURITY_VALUES = {"draft", "ci-ready"}


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

    for key in (
        "shared_mutation",
        "environment_bound_fixture",
        "unique_test_data",
        "disposable_environment",
        "parallel_safe",
    ):
        require(isinstance(data.get(key), bool), f"{key} 必須是 boolean")

    cleanup = data.get("cleanup")
    require(cleanup in CLEANUP_VALUES, f"cleanup 必須是 {sorted(CLEANUP_VALUES)}")

    for key in ("persistent_owned_fixture", "idempotent_seed", "exclusive_execution"):
        value = data.get(key, False)
        require(isinstance(value, bool), f"{key} 必須是 boolean")

    workers = data.get("workers", 1)
    require(isinstance(workers, int) and workers >= 1, "workers 必須是 >= 1 的整數")

    safety = data.get("safety_invariants", [])
    require(isinstance(safety, list), "safety_invariants 必須是 array")
    require(all(isinstance(item, str) and item.strip() for item in safety), "safety_invariants 每項都必須是非空字串")

    waivers = data.get("review_waivers", [])
    require(isinstance(waivers, list), "review_waivers 必須是 array")
    for index, waiver in enumerate(waivers):
        require(isinstance(waiver, dict), f"review_waivers[{index}] 必須是 object")
        require(isinstance(waiver.get("code"), str) and waiver["code"].strip(), f"review_waivers[{index}].code 必填")
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
        require(isinstance(value, int) and value >= 0, f"stability.{key} 必須是非負整數")

    candidate_sha256 = stability.get("candidate_sha256")
    require(
        isinstance(candidate_sha256, str) and re.fullmatch(r"[0-9a-f]{64}", candidate_sha256) is not None,
        "stability.candidate_sha256 必須是 64 字元小寫 SHA-256",
    )

    return data


def metadata_template(candidate: str, adapter: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "candidate": candidate,
        "adapter": adapter,
        "maturity": "draft",
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
    result: dict[str, str] = {}
    for waiver in metadata.get("review_waivers", []):
        result[waiver["code"]] = waiver["reason"]
    return result


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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

    if Path(metadata["candidate"]).name != candidate.name:
        blockers.append({
            "code": "CANDIDATE_METADATA_MISMATCH",
            "reason": (
                f"metadata candidate={metadata['candidate']!r}，"
                f"實際檔案={candidate.name!r}"
            ),
        })

    for issue in hard_issues:
        blockers.append({
            "code": f"STATIC_{issue.code}",
            "reason": f"{candidate}:{issue.line} {issue.message}",
        })

    for issue in review_issues:
        waived_reason = waivers.get(issue.code)
        reviews.append({
            "code": issue.code,
            "line": issue.line,
            "message": issue.message,
            "waived": bool(waived_reason),
            "waiver_reason": waived_reason,
        })
        if not waived_reason:
            blockers.append({
                "code": f"REVIEW_{issue.code}",
                "reason": f"{candidate}:{issue.line} 需要 review/waiver：{issue.message}",
            })

    shared_mutation = metadata["shared_mutation"]
    cleanup = metadata["cleanup"]
    disposable = metadata["disposable_environment"]
    unique = metadata["unique_test_data"]
    persistent_owned = metadata.get("persistent_owned_fixture", False)
    idempotent_seed = metadata.get("idempotent_seed", False)
    exclusive_execution = metadata.get("exclusive_execution", False)
    parallel_safe = metadata["parallel_safe"]
    workers = metadata.get("workers", 1)
    safety = metadata.get("safety_invariants", [])

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
            "reason": "persistent owned fixture 必須由 CI/runtime 保證 exclusive_execution=true",
        })

    if persistent_owned and (workers != 1 or parallel_safe):
        blockers.append({
            "code": "PERSISTENT_FIXTURE_PARALLEL_UNSAFE",
            "reason": "persistent owned fixture 必須 workers=1 且 parallel_safe=false",
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
                "共享資料 mutation 必須 cleanup=reliable、disposable environment，"
                "或滿足 persistent owned fixture 的 idempotent + exclusive contract"
            ),
        })

    if metadata["environment_bound_fixture"] and cleanup != "reliable" and not disposable and not persistent_safe:
        blockers.append({
            "code": "ENV_FIXTURE_NOT_RESTORABLE",
            "reason": (
                "environment-bound fixture 無 reliable cleanup/disposable environment，"
                "也未滿足 persistent owned fixture contract"
            ),
        })

    if parallel_safe and shared_mutation and not unique and not disposable:
        blockers.append({
            "code": "PARALLEL_FIXTURE_COLLISION",
            "reason": "parallel_safe=true 且會修改共享資料時，需要 unique_test_data=true 或 disposable environment",
        })

    if workers > 1 and not parallel_safe:
        blockers.append({
            "code": "WORKERS_EXCEED_PARALLEL_CONTRACT",
            "reason": f"workers={workers} 但 parallel_safe=false",
        })

    stability = metadata["stability"]
    current_sha256 = sha256_file(candidate)
    if stability["candidate_sha256"] != current_sha256:
        blockers.append({
            "code": "STALE_STABILITY_EVIDENCE",
            "reason": (
                "stability.candidate_sha256 與目前 candidate 不一致；"
                "修改測試後必須重新跑 promotion stability"
            ),
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

    result_maturity = "ci-ready" if not blockers else "draft"

    return {
        "schema_version": SCHEMA_VERSION,
        "candidate": str(candidate),
        "adapter": metadata["adapter"],
        "maturity": result_maturity,
        "fixture": {
            "shared_mutation": shared_mutation,
            "environment_bound_fixture": metadata["environment_bound_fixture"],
            "unique_test_data": unique,
            "disposable_environment": disposable,
            "persistent_owned_fixture": persistent_owned,
            "idempotent_seed": idempotent_seed,
            "exclusive_execution": exclusive_execution,
            "parallel_safe": parallel_safe,
            "workers": workers,
            "cleanup": cleanup,
        },
        "stability": stability | {"current_candidate_sha256": current_sha256},
        "static": {
            "hard": [asdict(issue) | {"path": str(issue.path)} for issue in hard_issues],
            "review": reviews,
        },
        "blockers": blockers,
    }


def print_human(result: dict[str, Any]) -> None:
    if result["maturity"] == "ci-ready":
        print("✅ E2E promotion: ci-ready")
    else:
        print("🚧 E2E promotion: draft（尚未通過）")

    print(
        "fixture: "
        f"cleanup={result['fixture']['cleanup']} "
        f"shared_mutation={str(result['fixture']['shared_mutation']).lower()} "
        f"persistent_owned={str(result['fixture']['persistent_owned_fixture']).lower()} "
        f"exclusive={str(result['fixture']['exclusive_execution']).lower()} "
        f"parallel_safe={str(result['fixture']['parallel_safe']).lower()} "
        f"workers={result['fixture']['workers']}"
    )
    print(
        "stability: "
        f"retries={result['stability']['retries']} "
        f"repeat_each={result['stability']['repeat_each']} "
        f"passed={result['stability']['passed']} "
        f"failed={result['stability']['failed']}"
    )

    for blocker in result["blockers"]:
        print(f"❌ [{blocker['code']}] {blocker['reason']}")

    waived = [item for item in result["static"]["review"] if item["waived"]]
    for item in waived:
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


def self_test() -> int:
    clean_spec = """
const { test, expect } = require('@playwright/test');
test('feature-x#AC-1 renders', async ({ page }) => {
  await test.step('feature-x#AC-1: render', async () => {
    await expect(page.getByRole('main')).toBeVisible();
  });
});
""".strip()

    review_spec = """
const { test, expect } = require('@playwright/test');
test('feature-y#AC-2 legacy wait', async ({ page }) => {
  await test.step('feature-y#AC-2: wait', async () => {
    await page.waitForTimeout(100);
    await expect.soft(page.getByText('ok')).toBeVisible();
  });
});
""".strip()

    stable = {
        "discovery": True,
        "framework_load": True,
        "headless_pass": True,
        "retries": 0,
        "repeat_each": 3,
        "passed": 3,
        "failed": 0,
        "candidate_sha256": "",
    }

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        clean_path = root / "clean.spec.js"
        review_path = root / "review.spec.js"
        clean_path.write_text(clean_spec, encoding="utf-8")
        review_path.write_text(review_spec, encoding="utf-8")

        base = metadata_template(str(clean_path), "generic-playwright")
        base["stability"] = dict(stable)
        base["stability"]["candidate_sha256"] = sha256_file(clean_path)

        ready = evaluate(clean_path, base)
        assert ready["maturity"] == "ci-ready", ready

        mutating = dict(base)
        mutating["shared_mutation"] = True
        mutating["environment_bound_fixture"] = True
        mutating["cleanup"] = "best-effort"
        mutating["safety_invariants"] = ["forbid_request POST /dangerous"]
        blocked = evaluate(clean_path, mutating)
        codes = {item["code"] for item in blocked["blockers"]}
        assert "UNRELIABLE_CLEANUP" in codes, blocked
        assert "ENV_FIXTURE_NOT_RESTORABLE" in codes, blocked
        assert blocked["maturity"] == "draft", blocked

        persistent = dict(base)
        persistent["shared_mutation"] = True
        persistent["environment_bound_fixture"] = True
        persistent["cleanup"] = "none"
        persistent["persistent_owned_fixture"] = True
        persistent["idempotent_seed"] = True
        persistent["exclusive_execution"] = True
        persistent["parallel_safe"] = False
        persistent["workers"] = 1
        persistent["safety_invariants"] = [
            "mutate only dedicated E2E fixture records",
            "forbid destructive production-like actions",
        ]
        persistent_ready = evaluate(clean_path, persistent)
        assert persistent_ready["maturity"] == "ci-ready", persistent_ready

        persistent_unlocked = dict(persistent)
        persistent_unlocked["exclusive_execution"] = False
        unlocked = evaluate(clean_path, persistent_unlocked)
        unlocked_codes = {item["code"] for item in unlocked["blockers"]}
        assert "PERSISTENT_FIXTURE_NO_EXCLUSIVE_EXECUTION" in unlocked_codes, unlocked
        assert "UNRELIABLE_CLEANUP" in unlocked_codes, unlocked

        unwaived = dict(base)
        unwaived["candidate"] = str(review_path)
        unwaived["stability"] = dict(stable)
        unwaived["stability"]["candidate_sha256"] = sha256_file(review_path)
        review_blocked = evaluate(review_path, unwaived)
        assert any(item["code"] == "REVIEW_FIXED_SLEEP" for item in review_blocked["blockers"]), review_blocked

        waived = dict(base)
        waived["candidate"] = str(review_path)
        waived["stability"] = dict(stable)
        waived["stability"]["candidate_sha256"] = sha256_file(review_path)
        waived["review_waivers"] = [{
            "code": "FIXED_SLEEP",
            "reason": "legacy component has no observable completion event yet; tracked for removal",
        }]
        review_ready = evaluate(review_path, waived)
        assert review_ready["maturity"] == "ci-ready", review_ready

        stale_evidence = dict(base)
        stale_evidence["stability"] = dict(base["stability"])
        stale_evidence["stability"]["candidate_sha256"] = "f" * 64
        stale_result = evaluate(clean_path, stale_evidence)
        assert any(item["code"] == "STALE_STABILITY_EVIDENCE" for item in stale_result["blockers"]), stale_result

        bad_stability = dict(base)
        bad_stability["stability"] = dict(stable)
        bad_stability["stability"]["retries"] = 1
        unstable = evaluate(clean_path, bad_stability)
        assert any(item["code"] == "PROMOTION_RETRIES_NOT_ZERO" for item in unstable["blockers"]), unstable

    print("✅ crew-e2e-promote self-test passed")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate CREW E2E candidate promotion readiness")
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
