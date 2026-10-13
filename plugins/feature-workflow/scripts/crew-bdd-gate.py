#!/usr/bin/env python3
"""Portable, opt-in Test-First gate for CREW behavior examples.

Validates existing crew-results.json evidence against approved Sxx examples.
No state.json writes, product changes, Host SDKs, or external dependencies.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

E2E = Path(__file__).with_name("crew-e2e-results.py")
_spec = importlib.util.spec_from_file_location("crew_e2e_results", E2E)
if _spec is None or _spec.loader is None:
    raise RuntimeError(f"cannot load CREW E2E contract: {E2E}")
_e2e = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_e2e)


class BddGateError(ValueError):
    """An approved behavior contract or test evidence is not satisfied."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise BddGateError(message)


def expected_cases(plan: Path, slug: str) -> dict[str, list[str]]:
    expected = _e2e.load_expected_scenarios(plan, slug)
    require(bool(expected), "未宣告 Sxx 行為情境；請先經 /plan spec 與 Human requirement approval")
    return expected


def inspect(
    payload: dict[str, Any], slug: str, expected: dict[str, list[str]],
    phase: str,
) -> dict[str, Any]:
    """Strict opt-in gate; generic E2E aggregation remains backward-compatible."""
    require(phase in ("red", "green"), "phase 必須為 red 或 green")
    # The shared result schema already validates statuses, AC keys, blocked reasons,
    # coverage values and scenario_id-to-AC correspondence.
    all_records = [_e2e.validate_result(item, i) for i, item in enumerate(payload["results"])]
    records = [r for r in all_records if r["ac"].startswith(f"{slug}#")]
    expected_ids = {sid for group in expected.values() for sid in group}
    seen_ids: set[str] = set()
    relevant: list[dict[str, Any]] = []
    for row in records:
        if row["ac"] not in expected:
            continue  # legacy AC without Sxx remains verified by normal /plan-verify
        sid = row.get("scenario_id")
        require(isinstance(sid, str), f"{row['ac']} 的 BDD 測試缺 scenario_id")
        require(sid in expected_ids, f"未核准的 Scenario：{sid}")
        seen_ids.add(sid)
        relevant.append(row)
    missing = sorted(expected_ids - seen_ids)
    require(not missing, f"測試未涵蓋已核准的情境：{', '.join(missing)}")
    require(bool(relevant), "無 BDD 情境結果")

    failed = []
    for row in relevant:
        sid = row["scenario_id"]
        require(row.get("coverage", "full") == "full", f"{sid} 僅有部分覆蓋")
        status = row["status"]
        if phase == "red":
            require(status in ("passed", "failed"), f"{sid} RED 不接受 {status}；需修正測試環境")
            if status == "failed":
                require(isinstance(row.get("reason"), str) and row["reason"].strip(),
                        f"{sid} RED failure 須附 assertion 失敗原因")
                failed.append(sid)
        else:
            require(status == "passed", f"{sid} GREEN 仍為 {status}，不可結束 build")
    if phase == "red":
        require(bool(failed), "RED 沒有任何失敗的行為 assertion；不得宣稱先測試後實作")
    return {
        "phase": phase,
        "status": "RED_VALID" if phase == "red" else "GREEN_VALID",
        "scenario_ids": sorted(expected_ids),
        "failed_scenario_ids": sorted(set(failed)),
        "checked_records": len(relevant),
        "runner": payload["runner"],
        "run_id": payload.get("run_id"),
    }


def check(
    plan: Path, slug: str, results: Path, phase: str,
    red_results: Path | None = None,
) -> dict[str, Any]:
    expected = expected_cases(plan, slug)
    current = _e2e.load_payload(results)
    output = inspect(current, slug, expected, phase)
    if phase == "green":
        require(red_results is not None, "GREEN 必須提供先前保存的 --red-results")
        require(red_results.resolve() != results.resolve(), "RED 與 GREEN 不可使用同一份檔案")
        red_payload = _e2e.load_payload(red_results)
        previous = inspect(red_payload, slug, expected, "red")
        rid = red_payload.get("run_id")
        gid = current.get("run_id")
        if rid is not None and gid is not None:
            require(str(rid) != str(gid), "RED / GREEN 不可使用相同 run_id")
        require(red_payload != current, "RED 與 GREEN 的結果相同，無法證明測試重新執行")
        output["red_failed_scenario_ids"] = previous["failed_scenario_ids"]
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description="CREW opt-in BDD Test-First evidence gate")
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--slug", required=True)
    parser.add_argument("--results", required=True, type=Path)
    parser.add_argument("--phase", required=True, choices=("red", "green"))
    parser.add_argument("--red-results", type=Path)
    args = parser.parse_args()
    try:
        result = check(args.plan, args.slug, args.results, args.phase, args.red_results)
    except (BddGateError, _e2e.ValidationError) as exc:
        print(f"BLOCKED: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
