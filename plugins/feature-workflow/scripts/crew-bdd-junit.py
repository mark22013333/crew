#!/usr/bin/env python3
"""Translate JUnit/Surefire XML test cases into CREW's scenario result schema v1.

Use a stable id like "booking#AC-1#S01" in JUnit @DisplayName or method name.
Only assertion <failure> is treated as RED; infrastructure <error> is BLOCKED.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

SCENARIO_ID = re.compile(
    r"(?<![A-Za-z0-9._-])(?P<id>[A-Za-z0-9][A-Za-z0-9._-]*#AC-[1-9]\d*#S(?:0[1-9]|[1-9]\d+))(?!\d)"
)


def convert(paths: list[Path], environment: str, run_id: str | None) -> dict:
    if not paths:
        raise ValueError("至少需要一個 JUnit XML 報告")
    results = []
    for file in paths:
        try:
            root = ET.parse(file).getroot()
        except (OSError, ET.ParseError) as exc:
            raise ValueError(f"無法讀取 JUnit XML {file}: {exc}") from exc
        if root.tag not in ("testsuite", "testsuites"):
            raise ValueError(f"{file} 不是 JUnit testsuite/testsuites XML")
        for case in root.iter("testcase"):
            title = str(case.get("name") or "")
            ids = [match.group("id") for match in SCENARIO_ID.finditer(title)]
            if not ids:
                continue  # Other, non-CREW JUnit tests are not behavior scenarios.
            if len(ids) != 1:
                raise ValueError(f"{file} 的 testcase 對應多個 scenario_id: {title}")
            sid = ids[0]
            ac = sid.rsplit("#", 1)[0]
            failed = case.find("failure")
            blocked = case.find("error")
            skipped = case.find("skipped")
            if failed is not None:
                status, node = "failed", failed
            elif blocked is not None:
                status, node = "blocked", blocked
            elif skipped is not None:
                status, node = "skipped", skipped
            else:
                status, node = "passed", None
            reason = None
            if node is not None:
                reason = (node.get("message") or (node.text or "").strip().split("\n")[0]).strip()
                if not reason:
                    reason = f"JUnit {node.tag} without diagnostic message"
            try:
                duration_ms = max(0, int(float(case.get("time") or "0") * 1000))
            except ValueError as exc:
                raise ValueError(f"{file} 的 testcase.time 不是數字: {title}") from exc
            results.append({
                "ac": ac,
                "scenario": title,
                "scenario_id": sid,
                "status": status,
                "coverage": "full",
                "attempts": 1,
                "duration_ms": duration_ms,
                "reason": reason,
                "evidence": {"junit_xml": str(file)},
            })
    if not results:
        raise ValueError("JUnit XML 中沒有帶 {slug}#AC-n#Sxx 的 testcase")
    return {
        "schema_version": 1,
        "runner": "junit",
        "environment": environment,
        "run_id": run_id,
        "results": results,
    }


def main() -> int:
    p = argparse.ArgumentParser(description="JUnit XML to CREW BDD scenario result v1")
    p.add_argument("--junit-xml", type=Path, action="append", required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--environment", required=True)
    p.add_argument("--run-id", help="Different identifier for RED and GREEN test executions")
    args = p.parse_args()
    try:
        report = convert(args.junit_xml, args.environment, args.run_id)
        # This is an artifact writer, never a state.json writer.
        if args.output.name in ("state.json", "plan.md"):
            raise ValueError("輸出不得覆寫 CREW state.json 或 plan.md")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except (OSError, ValueError) as exc:
        print(f"BLOCKED: {exc}", file=sys.stderr)
        return 1
    print(f"converted {len(report['results'])} JUnit scenario test record(s) -> {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
