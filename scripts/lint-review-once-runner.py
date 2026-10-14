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
    write_plan = g.SignedGrantScenarios.write_plan

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

    def test_original_grant_expiry_cannot_be_renewed_by_event_replacement(self):
        self.initialize()
        from datetime import datetime
        end = g.grant_tool.parse_time(self.event["expires_at"], "expires_at")
        with self.assertRaisesRegex(g.grant_tool.GrantError, "授權已到期"):
            g.grant_tool.verify_event(
                self.project, self.packet_file, self.event_file, self.signature_file,
                when=end + timedelta(seconds=1),
            )
        # Even a newly signed shorter event cannot change the original
        # grant deadline without issuing a new, explicitly approved Grant.
        self.event["expires_at"] = (self.issued + timedelta(hours=3)).isoformat()
        self.sign()
        invalid = self.runner("next")
        self.assertNotEqual(invalid.returncode, 0)
        self.assertIn("原始四小時期限", invalid.stderr)
        status = json.loads(self.runner("status").stdout)
        self.assertEqual(status["status"], "paused")

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

    def issue_dialogue(self, until: str = "build", seconds: int = 14400):
        proc = self.state("grant", "--action", "issue", "--proof", "dialogue",
                          "--packet", str(self.packet_file),
                          "--approved-sha", self.packet["packet_sha256"],
                          "--max-duration", str(seconds), "--until", until)
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def start_dialogue(self, until: str = "build", seconds: int = 14400, owner: str = "dialogue-1"):
        self.set_skeleton()
        self.issue_dialogue(until, seconds)
        started = self.runner("start", owner)
        self.assertEqual(started.returncode, 0, started.stderr)
        return json.loads(started.stdout)

    def read_state(self) -> dict:
        return json.loads((self.spec_dir / "state.json").read_text(encoding="utf-8"))

    def test_dialogue_full_path_commands(self):
        started = self.start_dialogue()
        self.assertEqual((started["grant_proof"], started["target_step"]), ("dialogue", "build"))
        for stage in ("spec", "db", "arch"):
            p = self.runner("next", "dialogue-1")
            self.assertEqual(p.returncode, 0, p.stderr)
            inflight = json.loads(p.stdout)["inflight"]
            self.assertEqual(inflight["command"], f"review-once-apply.py --step {stage}")
            applied = self.apply_stage(stage)
            self.assertEqual(applied.returncode, 0, applied.stderr)
            if stage == "spec":
                # packet 的測試策略鏡像進 state.json.testing
                testing = self.read_state()["testing"]
                self.assertEqual((testing["policy"], testing["by"]), ("with_test", "packet"))
        build = self.runner("next", "dialogue-1")
        self.assertEqual(json.loads(build.stdout)["inflight"]["command"],
                         "/plan-build --with-test --review-once")
        self.assertEqual(self.runner("heartbeat", "dialogue-1").returncode, 0)
        self.assertEqual(self.state("set", "--step", "build", "--status", "done").returncode, 0)
        done = self.runner("next", "dialogue-1")
        self.assertEqual(json.loads(done.stdout)["status"], "completed_build")
        state = self.read_state()
        self.assertEqual(state["autonomy"]["status"], "consumed")
        self.assertEqual(state["gates"]["uat"]["status"], "pending")

    def test_until_arch_completed_plan(self):
        self.start_dialogue(until="arch", owner="host-a")  # plan_stages 以預設 owner 派工
        self.plan_stages()
        p = self.runner("next", "host-a")
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(json.loads(p.stdout)["status"], "completed_plan")
        state = self.read_state()
        self.assertEqual(state["autonomy"]["status"], "consumed")
        self.assertEqual(state["autonomy"]["execution"]["stop_reason"], "PLAN_DONE")
        self.assertEqual(state["steps"]["build"]["status"], "pending")
        self.assertEqual(state["gates"]["architecture"]["status"], "approved")
        # 授權已用盡，不得順勢派 build
        self.assertNotEqual(self.runner("next", "host-a").returncode, 0)

    def test_reclaim_running_from_new_session(self):
        self.start_dialogue(owner="dialogue-old")
        self.dispatched_by("spec", "dialogue-old")
        self.assertNotEqual(self.runner("reclaim", "dialogue-new").returncode, 0)  # 缺 --reason
        self.assertNotEqual(self.runner("reclaim", "dialogue-old", "--reason", "x").returncode, 0)
        reclaimed = self.runner("reclaim", "dialogue-new", "--reason", "原 session 已關閉")
        self.assertEqual(reclaimed.returncode, 0, reclaimed.stderr)
        run = self.read_state()["autonomy"]["execution"]
        self.assertEqual((run["status"], run["stop_reason"], run["previous_owner"], run["owner"]),
                         ("paused", "SESSION_LOST", "dialogue-old", "dialogue-new"))
        self.assertEqual(run["inflight"]["step"], "spec")
        self.assertNotEqual(self.runner("reclaim", "dialogue-other", "--reason", "x").returncode, 0)
        # 之後照既有 resume 規則：有 inflight 必須明示對帳
        self.assertNotEqual(self.runner("resume", "dialogue-new").returncode, 0)
        resumed = self.runner("resume", "dialogue-new", "--reconcile",
                              "--reason", "確認原 session 已結束")
        self.assertEqual(resumed.returncode, 0, resumed.stderr)
        self.assertEqual(self.apply_stage("spec").returncode, 0)
        self.dispatched_by("db", "dialogue-new")

    def dispatched_by(self, step: str, owner: str) -> dict:
        p = self.runner("next", owner)
        self.assertEqual(p.returncode, 0, p.stderr)
        out = json.loads(p.stdout)
        self.assertEqual(out["inflight"]["step"], step)
        return out

    def test_dialogue_expiry_pauses(self):
        self.start_dialogue(seconds=600)
        grant = self.read_state()["autonomy"]
        end = g.grant_tool.parse_time(grant["expires_at"], "expires_at")
        with self.assertRaisesRegex(g.grant_tool.GrantError, "授權已到期"):
            g.grant_tool.verify_dialogue(self.project, grant, when=end + timedelta(seconds=1))
        # 模擬時間經過：把同樣 600 秒的窗口整段移到過去
        from datetime import datetime, timezone
        path = self.spec_dir / "state.json"
        raw = self.read_state()
        past = datetime.now(timezone.utc).replace(microsecond=0) - timedelta(hours=1)
        raw["autonomy"]["issued_at"] = past.isoformat()
        raw["autonomy"]["expires_at"] = (past + timedelta(seconds=600)).isoformat()
        path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
        expired = self.runner("next", "dialogue-1")
        self.assertNotEqual(expired.returncode, 0)
        self.assertIn("授權已到期", expired.stderr)
        status = json.loads(self.runner("status").stdout)
        self.assertEqual(status["status"], "paused")

    def test_plan_run_skill_contract(self):
        skill_dir = ROOT / "plugins/feature-workflow/skills/plan-run"
        texts = [(skill_dir / "SKILL.md").read_text(encoding="utf-8")]
        texts += [p.read_text(encoding="utf-8") for p in sorted((skill_dir / "phases").glob("*.md"))]
        combined = "\n".join(texts)
        for needle in ("ask_user(", "CREW_PLUGIN_ROOT=", "不是無人值守"):
            self.assertIn(needle, combined)
        self.assertNotIn("AskUserQuestion", combined)
        # resume 分流：owner 不同時必須明示接管（同一行同時帶 --takeover 與 --reason）
        resume_lines = [line for line in combined.splitlines()
                        if "--action resume" in line and "--takeover" in line and "--reason" in line]
        self.assertTrue(resume_lines, "plan-run 的 resume 指令缺 --takeover／--reason")

    def test_resume_by_other_owner_requires_takeover_and_reason(self):
        self.start_dialogue(owner="dialogue-a")
        self.assertEqual(self.runner("pause", "dialogue-a", "--reason", "SESSION_END").returncode, 0)
        direct = self.runner("resume", "dialogue-b")
        self.assertNotEqual(direct.returncode, 0)
        no_reason = self.runner("resume", "dialogue-b", "--takeover")
        self.assertNotEqual(no_reason.returncode, 0)
        taken = self.runner("resume", "dialogue-b", "--takeover",
                            "--reason", "確認 dialogue-a 的 session 已結束")
        self.assertEqual(taken.returncode, 0, taken.stderr)
        self.assertEqual(json.loads(taken.stdout)["owner"], "dialogue-b")

    def test_arch_only_grant_blocks_build_guard(self):
        self.start_dialogue(until="arch", owner="host-a")
        self.plan_stages()
        guard = subprocess.run(
            [sys.executable, str(FEATURE / "review-once-build.py"),
             "--slug", self.slug, "--project", str(self.project)],
            env=self.env, capture_output=True, text=True, check=False)
        self.assertEqual(guard.returncode, 1, guard.stdout)
        self.assertIn("grant 只核准到 arch", guard.stderr)

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
        sha = git("rev-parse", "HEAD").stdout.strip()
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
