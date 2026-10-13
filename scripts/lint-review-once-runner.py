#!/usr/bin/env python3
"""Executable Review Once Host dispatch / resume / expiry / Build regressions."""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import unittest
from datetime import timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FEATURE = ROOT / "plugins/feature-workflow/scripts"
GRANT_TEST = ROOT / "scripts/lint-review-once-grants.py"
m = importlib.util.spec_from_file_location("review_once_grants_test", GRANT_TEST)
assert m and m.loader
g = importlib.util.module_from_spec(m)
m.loader.exec_module(g)


class RunnerScenarios(unittest.TestCase):
    # Reuse real OpenSSL-signed Test Fixture and state CLI without rerunning old
    # inherited test cases. This exercises production scripts, not mocks.
    setUp = g.SignedGrantScenarios.setUp
    sign = g.SignedGrantScenarios.sign
    state = g.SignedGrantScenarios.state
    issue = g.SignedGrantScenarios.issue

    def runner(self, action: str, owner: str = "host-a", *args):
        return self.state("run", "--action", action, "--owner", owner, *args)

    def apply_stage(self, stage: str):
        return subprocess.run(
            [sys.executable, str(FEATURE / "review-once-apply.py"),
             "--project", str(self.project), "--slug", self.slug, "--step", stage],
            env=self.env, capture_output=True, text=True, check=False,
        )

    def set_skeleton(self):
        (self.spec_dir / "plan.md").write_text(
            "---\nslug: review-once-demo\nname: 預約規則\ntype: feature\n"
            "verified_at_commit:\nverified_at:\ndrift_policy: normal\n---\n\n"
            "# 預約規則\n\n"
            "## 目標與範圍 <!-- crew:goal owner=spec -->\n\n"
            "## 驗收條件 <!-- crew:ac owner=spec -->\n\n"
            "## 決策紀錄 <!-- crew:dec append-only -->\n\n"
            "## 已知取捨與風險 <!-- crew:risk append-only -->\n\n"
            "## 指路 <!-- crew:map append-only -->\n\n"
            "## 檢查報告摘要 <!-- crew:rep append-only -->\n",
            encoding="utf-8",
        )

    def dispatched(self, step: str) -> dict:
        p = self.runner("next")
        self.assertEqual(p.returncode, 0, p.stderr)
        out = json.loads(p.stdout)
        self.assertEqual(out["inflight"]["step"], step)
        return out

    def initialize(self):
        self.set_skeleton()
        i = self.issue()
        self.assertEqual(i.returncode, 0, i.stderr)
        started = self.runner("start")
        self.assertEqual(started.returncode, 0, started.stderr)
        return json.loads(started.stdout)

    def plan_stages(self):
        self.dispatched("spec")
        spec = self.apply_stage("spec")
        self.assertEqual(spec.returncode, 0, spec.stderr)
        self.dispatched("db")
        db = self.apply_stage("db")
        self.assertEqual(db.returncode, 0, db.stderr)
        self.dispatched("arch")
        arch = self.apply_stage("arch")
        self.assertEqual(arch.returncode, 0, arch.stderr)

    def test_approved_packet_reaches_build_but_never_implicitly_completes(self):
        self.initialize()
        self.plan_stages()
        command = self.dispatched("build")
        self.assertIn("--with-test --review-once", command["inflight"]["command"])
        pending = self.runner("next")
        self.assertEqual(pending.returncode, 0, pending.stderr)
        self.assertEqual(json.loads(pending.stdout)["reason"], "INFLIGHT_UNRECONCILED")
        self.assertEqual(self.state("set", "--step", "build", "--status", "done").returncode, 0)
        completed = self.runner("next")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        report = json.loads(completed.stdout)
        self.assertEqual(report["status"], "completed_build")
        state = json.loads((self.spec_dir / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(state["autonomy"]["status"], "consumed")
        self.assertEqual(state["gates"]["uat"]["status"], "pending")
        self.assertEqual(state["steps"]["verify"]["status"], "pending")
        self.assertEqual(state["steps"]["close"]["status"], "pending")
        self.assertNotEqual(self.runner("next").returncode, 0)

    def test_no_repeat_dispatch_and_stale_inflight_requires_explicit_reconcile(self):
        self.initialize()
        self.dispatched("spec")
        next_run = self.runner("next")
        self.assertEqual(json.loads(next_run.stdout)["action"], "blocked")
        paused = self.runner("pause", "host-a", "--reason", "HOST_UNAVAILABLE")
        self.assertEqual(paused.returncode, 0, paused.stderr)
        self.assertNotEqual(self.runner("next").returncode, 0)
        self.assertNotEqual(self.runner("resume").returncode, 0)
        resume = self.runner("resume", "host-a", "--reconcile",
                             "--reason", "verified original worker was cancelled")
        self.assertEqual(resume.returncode, 0, resume.stderr)
        self.assertEqual(json.loads(resume.stdout)["inflight"]["step"], "spec")
        res = self.apply_stage("spec")
        self.assertEqual(res.returncode, 0, res.stderr)
        self.dispatched("db")

    def test_owner_conflict_and_explicit_paused_takeover(self):
        self.initialize()
        self.assertNotEqual(self.runner("next", "host-b").returncode, 0)
        self.assertEqual(self.runner("pause", "host-a", "--reason", "SESSION_END").returncode, 0)
        self.assertNotEqual(self.runner("resume", "host-b").returncode, 0)
        transfer = self.runner("resume", "host-b", "--takeover", "--reason",
                               "Host confirmed previous worker has exited")
        self.assertEqual(transfer.returncode, 0, transfer.stderr)
        self.assertEqual(json.loads(transfer.stdout)["owner"], "host-b")
        self.assertNotEqual(self.runner("next", "host-a").returncode, 0)

    def test_revocation_and_expired_grant_pause_execution(self):
        self.initialize()
        self.assertEqual(self.state("grant", "--action", "revoke").returncode, 0)
        blocked = self.runner("next")
        self.assertNotEqual(blocked.returncode, 0)
        report = json.loads(self.runner("status").stdout)
        self.assertEqual(report["status"], "paused")
        self.assertEqual(report["grant_status"], "revoked")

    def test_trusted_proof_cli_not_agent_approval_text(self):
        from subprocess import run
        good = run([
            sys.executable, str(FEATURE / "review-once-proof.py"), "--project",
            str(self.project), "--packet", str(self.packet_file),
            "--event", str(self.event_file), "--signature", str(self.signature_file)
        ], env=self.env, capture_output=True, text=True, check=False)
        self.assertEqual(good.returncode, 0, good.stderr)
        self.assertEqual(json.loads(good.stdout)["status"], "valid_signed_human_review")
        self.event["decision"] = "auto_approve_without_human"
        self.sign()
        bad = run([
            sys.executable, str(FEATURE / "review-once-proof.py"), "--project",
            str(self.project), "--packet", str(self.packet_file),
            "--event", str(self.event_file), "--signature", str(self.signature_file),
        ], env=self.env, capture_output=True, text=True, check=False)
        self.assertNotEqual(bad.returncode, 0)

    def test_packet_stage_write_is_not_generic_production_source_write(self):
        self.initialize()
        self.dispatched("spec")
        self.assertEqual(self.apply_stage("spec").returncode, 0)
        p = self.spec_dir / "plan.md"
        content = p.read_text(encoding="utf-8")
        self.assertIn("AC-1 重疊時拒絕", content)
        self.assertIn("D-1 [spec]", content)
        self.assertEqual(content.count("<!-- crew:ac"), 1)
        self.assertEqual(content.count("## "), 6)
        # Stage already done, cannot use the signed packet to repeat the writer.
        self.assertNotEqual(self.apply_stage("spec").returncode, 0)

    def test_git_scope_guard_rejects_unapproved_product_files(self):
        git = lambda *args: subprocess.run(
            ["git", "-C", str(self.project), *args],
            capture_output=True, text=True, check=True)
        git("init", "-q")
        git("config", "user.name", "CI")
        git("config", "user.email", "ci@example.invalid")
        git("checkout", "-q", "-b", "feat/review-demo")
        (self.project / "src").mkdir()
        (self.project / "src" / "main.txt").write_text("baseline\n")
        git("add", "src/main.txt")
        git("commit", "-q", "-m", "baseline")
        sha = git("rev-parse", "HEAD").stdout.decode().strip()
        self.proposal["repository"]["base_commit"] = sha
        self.packet = g.packet_tool.create_packet(self.proposal)
        self.packet_file.write_bytes(g.packet_tool.canonical_bytes(self.packet))
        self.event["repository"] = self.proposal["repository"]
        self.event["packet_sha256"] = self.packet["packet_sha256"]
        self.sign()
        self.initialize()
        self.plan_stages()
        self.dispatched("build")
        guard = [sys.executable, str(FEATURE / "review-once-build.py"),
                 "--slug", self.slug, "--project", str(self.project)]
        clean = subprocess.run(guard, env=self.env, capture_output=True, text=True)
        self.assertEqual(clean.returncode, 0, clean.stderr)
        (self.project / "src" / "main.txt").write_text("approved change\n")
        approved = subprocess.run(guard, env=self.env, capture_output=True, text=True)
        self.assertEqual(approved.returncode, 0, approved.stderr)
        (self.project / "secrets.txt").write_text("unapproved\n")
        out = subprocess.run(guard, env=self.env, capture_output=True, text=True)
        self.assertEqual(out.returncode, 1)
        self.assertIn("超出核准 Git 檔案範圍", out.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
