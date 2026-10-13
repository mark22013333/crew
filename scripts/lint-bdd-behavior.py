#!/usr/bin/env python3
"""Executable Given/When/Then scenarios for CREW BDD Test-First.

No Cucumber/Gherkin runtime dependency: all scenarios drive the real
crew-bdd-gate.py and crew-state.py commands/contracts.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "plugins" / "feature-workflow" / "scripts"
GATE = SCRIPTS / "crew-bdd-gate.py"
STATE = SCRIPTS / "crew-state.py"
SPEC = importlib.util.spec_from_file_location("crew_bdd_gate", GATE)
assert SPEC and SPEC.loader
bdd = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bdd)


class BddBehaviorScenarios(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.slug = "reservation"
        self.plan = self.root / ".spec" / self.slug / "plan.md"
        self.plan.parent.mkdir(parents=True)
        self.plan.write_text(
            "# 預約\n"
            "## 驗收條件 <!-- crew:ac owner=spec -->\n"
            "- [ ] AC-1 預約不可重疊｜例：S01 正常：成功；S02 衝突：拒絕\n"
            "- [ ] AC-2 列表分頁\n"
            "## 決策紀錄 <!-- crew:dec append-only -->\n"
            "- D-1 [spec] 限制\n",
            encoding="utf-8",
        )

    def payload(self, first: str = "passed", second: str = "passed",
                first_coverage: str = "full", second_coverage: str = "full",
                run_id: str = "green-1") -> dict:
        return {
            "schema_version": 1,
            "runner": "junit",
            "environment": "integration-test",
            "run_id": run_id,
            "results": [
                {"ac": "reservation#AC-1", "scenario_id": "reservation#AC-1#S01",
                 "status": first, "coverage": first_coverage,
                 "reason": "expected success but was rejected" if first == "failed" else None},
                {"ac": "reservation#AC-1", "scenario_id": "reservation#AC-1#S02",
                 "status": second, "coverage": second_coverage,
                 "reason": "expected conflict rejection but was accepted"
                 if second == "failed" else "fixture missing" if second == "blocked" else None},
                # Existing AC without Sxx remains outside the opt-in scenario gate.
                {"ac": "reservation#AC-2", "status": "passed"},
            ],
        }

    def save(self, filename: str, payload: dict) -> Path:
        dest = self.root / filename
        dest.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        return dest

    def test_given_approved_examples_when_red_then_green_requires_real_rerun(self) -> None:
        """Given S01/S02; When assertions fail before code, then later pass on a distinct run."""
        red = self.save("red.json", self.payload(second="failed", run_id="red-1"))
        green = self.save("green.json", self.payload(run_id="green-1"))
        self.assertEqual(bdd.check(self.plan, self.slug, red, "red")["status"], "RED_VALID")
        summary = bdd.check(self.plan, self.slug, green, "green", red)
        self.assertEqual(summary["status"], "GREEN_VALID")
        self.assertEqual(summary["red_failed_scenario_ids"], ["reservation#AC-1#S02"])
        self.assertEqual(len(summary["scenario_ids"]), 2)

    def test_given_no_behavior_failure_when_red_then_block(self) -> None:
        """Given all-green baseline; When requesting RED, Then it is not test-first evidence."""
        result = self.save("not-red.json", self.payload())
        with self.assertRaisesRegex(bdd.BddGateError, "RED 沒有任何失敗"):
            bdd.check(self.plan, self.slug, result, "red")

    def test_given_missing_or_partial_sxx_when_green_then_block(self) -> None:
        """Given two approved examples; When one is missing or partial, Then no false GREEN."""
        red = self.save("red.json", self.payload(second="failed", run_id="red-1"))
        missing = self.payload()
        missing["results"].pop(1)
        missing_path = self.save("missing.json", missing)
        with self.assertRaisesRegex(bdd.BddGateError, "未涵蓋"):
            bdd.check(self.plan, self.slug, missing_path, "green", red)
        partial = self.save("partial.json", self.payload(second_coverage="partial"))
        with self.assertRaisesRegex(bdd.BddGateError, "部分覆蓋"):
            bdd.check(self.plan, self.slug, partial, "green", red)

    def test_given_environment_block_when_red_then_block(self) -> None:
        """Given absent fixture; When runner returns blocked, Then it is not a behavioral RED."""
        result = self.save("blocked.json", self.payload(second="blocked", run_id="red-1"))
        with self.assertRaisesRegex(bdd.BddGateError, "RED 不接受 blocked"):
            bdd.check(self.plan, self.slug, result, "red")

    def test_given_scenario_without_id_when_green_then_block(self) -> None:
        """Given legacy AC-only evidence; When scenario is approved, Then it cannot claim GREEN."""
        payload = self.payload()
        del payload["results"][1]["scenario_id"]
        result = self.save("legacy.json", payload)
        with self.assertRaisesRegex(bdd.BddGateError, "缺 scenario_id"):
            bdd.check(self.plan, self.slug, result, "green", self.save(
                "red.json", self.payload(second="failed", run_id="red-1")))

    def test_given_unapproved_sxx_when_green_then_block(self) -> None:
        """Given S01/S02; When report invents S03, Then never accept unexpected test evidence."""
        payload = self.payload()
        payload["results"][1]["scenario_id"] = "reservation#AC-1#S03"
        result = self.save("unknown.json", payload)
        with self.assertRaisesRegex(bdd.BddGateError, "未核准"):
            bdd.check(self.plan, self.slug, result, "green", self.save(
                "red.json", self.payload(second="failed", run_id="red-1")))

    def test_given_identical_run_ids_when_green_then_block(self) -> None:
        """Given RED and GREEN claims from one run id; Then rerun evidence must be rejected."""
        red = self.save("red.json", self.payload(second="failed", run_id="same-run"))
        green = self.save("green.json", self.payload(run_id="same-run"))
        with self.assertRaisesRegex(bdd.BddGateError, "相同 run_id"):
            bdd.check(self.plan, self.slug, green, "green", red)

    def test_given_no_sxx_when_bdd_selected_then_block(self) -> None:
        """Given old plain ACs; When opting into BDD, Then explicit scenarios are required."""
        self.plan.write_text(
            "## 驗收條件\n- [ ] AC-1 既有規格\n## 決策紀錄\n", encoding="utf-8"
        )
        result = self.save("legacy.json", self.payload())
        with self.assertRaisesRegex(bdd.BddGateError, "未宣告 Sxx"):
            bdd.check(self.plan, self.slug, result, "red")

    def test_given_genuine_bdd_artifacts_when_cli_runs_then_machine_exit_codes_match(self) -> None:
        """Given real JSON; When gate CLI runs, Then consumers receive deterministic exit codes."""
        red = self.save("red.json", self.payload(second="failed", run_id="red-1"))
        green = self.save("green.json", self.payload(run_id="green-1"))
        base = [sys.executable, str(GATE), "--plan", str(self.plan), "--slug", self.slug]
        red_run = subprocess.run(
            base + ["--phase", "red", "--results", str(red)],
            capture_output=True, text=True, check=False,
        )
        self.assertEqual(red_run.returncode, 0, red_run.stderr)
        self.assertEqual(json.loads(red_run.stdout)["status"], "RED_VALID")
        green_run = subprocess.run(
            base + ["--phase", "green", "--results", str(green),
                    "--red-results", str(red)],
            capture_output=True, text=True, check=False,
        )
        self.assertEqual(green_run.returncode, 0, green_run.stderr)
        failed = subprocess.run(
            base + ["--phase", "red", "--results", str(green)],
            capture_output=True, text=True, check=False,
        )
        self.assertEqual(failed.returncode, 1)

    def test_given_junit_xml_when_converted_then_gate_validates_red_green(self) -> None:
        """Given JUnit/Surefire evidence; When converted; Then RED/GREEN remain traceable."""
        adapter = SCRIPTS / "crew-bdd-junit.py"
        reports = []
        for mode, failure in (("red", True), ("green", False)):
            source = self.root / f"{mode}.xml"
            detail = '<failure message="expected rejection"/>' if failure else ""
            source.write_text(
                '<testsuite><testcase name="reservation#AC-1#S01" time="0.01"/>'
                f'<testcase name="reservation#AC-1#S02" time="0.02">{detail}</testcase>'
                '</testsuite>', encoding="utf-8"
            )
            report = self.root / f"{mode}-junit.json"
            proc = subprocess.run([
                sys.executable, str(adapter), "--junit-xml", str(source),
                "--output", str(report), "--environment", "test", "--run-id", mode,
            ], capture_output=True, text=True, check=False)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            reports.append(report)
        self.assertEqual(bdd.check(self.plan, self.slug, reports[0], "red")["status"], "RED_VALID")
        self.assertEqual(bdd.check(self.plan, self.slug, reports[1], "green", reports[0])["status"], "GREEN_VALID")

        source = self.root / "broken.xml"
        source.write_text(
            '<testsuite><testcase name="reservation#AC-1#S01"><error message="boot failure"/>'
            '</testcase><testcase name="reservation#AC-1#S02">'
            '<failure message="expected rejection"/></testcase></testsuite>', encoding="utf-8"
        )
        blocked = self.root / "blocked-junit.json"
        proc = subprocess.run([
            sys.executable, str(adapter), "--junit-xml", str(source),
            "--output", str(blocked), "--environment", "test",
        ], capture_output=True, text=True, check=False)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        with self.assertRaisesRegex(bdd.BddGateError, "RED 不接受 blocked"):
            bdd.check(self.plan, self.slug, blocked, "red")

    def test_given_junit_without_sxx_when_converting_then_block(self) -> None:
        """Given generic tests without scenario ids; Then converter cannot fabricate evidence."""
        source = self.root / "generic.xml"
        source.write_text('<testsuite><testcase name="ordinaryTest"/></testsuite>', encoding="utf-8")
        proc = subprocess.run([
            sys.executable, str(SCRIPTS / "crew-bdd-junit.py"), "--junit-xml", str(source),
            "--output", str(self.root / "out.json"), "--environment", "test",
        ], capture_output=True, text=True, check=False)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("沒有帶", proc.stderr)

    def test_given_pending_human_approval_when_build_attempted_then_runtime_blocks(self) -> None:
        """Given unapproved state; When build starts, Then BDD cannot bypass Human approval."""
        def state(*args: str) -> subprocess.CompletedProcess[str]:
            return subprocess.run(
                [sys.executable, str(STATE), *args, "--project", str(self.root)],
                capture_output=True, text=True, check=False,
            )

        initialized = state("init", "--slug", self.slug)
        self.assertEqual(initialized.returncode, 0, initialized.stderr)
        rejected = state("set", "--slug", self.slug,
                         "--step", "build", "--status", "in_progress")
        self.assertNotEqual(rejected.returncode, 0)
        self.assertTrue(
            "Approval" in rejected.stderr or "gate" in rejected.stderr
            or "尚未" in rejected.stderr or "arch" in rejected.stderr, rejected.stderr
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
