#!/usr/bin/env python3
"""Signed Review Once grant → existing CREW Approval Gates regression scenarios."""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "plugins/feature-workflow/scripts"
STATE = SCRIPTS / "crew-state.py"
packet_spec = importlib.util.spec_from_file_location("review_once_packet", SCRIPTS / "review-once-packet.py")
assert packet_spec and packet_spec.loader
packet_tool = importlib.util.module_from_spec(packet_spec)
packet_spec.loader.exec_module(packet_tool)
grant_spec = importlib.util.spec_from_file_location("review_once_grant", SCRIPTS / "review-once-grant.py")
assert grant_spec and grant_spec.loader
grant_tool = importlib.util.module_from_spec(grant_spec)
grant_spec.loader.exec_module(grant_tool)


def proposal() -> dict:
    return {
        "schema_version": 1, "mode": "review_once", "task_type": "feature",
        "slug": "review-once-demo",
        "repository": {"full_name": "example/crew-demo", "branch": "feat/review-demo",
                       "base_commit": "a" * 40},
        "spec": {"goal": ["- 新增預約限制"],
                 "ac": ["- [ ] AC-1 重疊時拒絕｜例：S01 無衝突；S02 有衝突"],
                 "decisions": ["- D-1 [spec] 範圍判斷：TASK_TYPE=feature"],
                 "risks": []},
        "db": {"required": False, "deploy_sql": "", "decisions": []},
        "architecture": {"decisions": ["- D-2 [arch] 驗證放在 Service｜理由：單一責任"],
                         "risks": []},
        "scope": {"allowed_paths": ["src/**", "tests/**"],
                  "allowed_actions": ["write_source", "write_tests"]},
        "test_policy": "with_test", "max_duration_seconds": 14400,
    }


class SignedGrantScenarios(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.project = root / "workspace"
        self.project.mkdir()
        self.slug = "review-once-demo"
        self.spec_dir = self.project / ".spec" / self.slug
        self.spec_dir.mkdir(parents=True)
        self.draft_dir = self.project / ".spec" / ".drafts" / "demo"
        self.draft_dir.mkdir(parents=True)
        self.key = root / "signer.pem"
        self.pub = root / "public.pem"
        self.env = {**os.environ, "CREW_REVIEW_ONCE_TRUSTED_PUBLIC_KEY": str(self.pub)}
        create = subprocess.run([
            "openssl", "genpkey", "-algorithm", "RSA", "-out", str(self.key),
            "-pkeyopt", "rsa_keygen_bits:2048",
        ], capture_output=True, text=True, check=False)
        self.assertEqual(create.returncode, 0, create.stderr)
        publish = subprocess.run([
            "openssl", "pkey", "-in", str(self.key), "-pubout", "-out", str(self.pub),
        ], capture_output=True, text=True, check=False)
        self.assertEqual(publish.returncode, 0, publish.stderr)
        self.proposal = proposal()
        self.packet_file = self.draft_dir / "packet.json"
        self.packet = packet_tool.create_packet(self.proposal)
        self.packet_file.write_bytes(packet_tool.canonical_bytes(self.packet))
        self.event_file = self.draft_dir / "event.json"
        self.signature_file = self.draft_dir / "approval.sig"
        self.issued = datetime.now(timezone.utc).replace(microsecond=0)
        self.event = {
            "schema_version": 1, "decision": "approve_review_once", "actor": "human",
            "grant_id": "c2bb6f98-c20d-4e3e-9c38-c75a0d360901",
            "packet_sha256": self.packet["packet_sha256"], "slug": self.slug,
            "repository": self.proposal["repository"],
            "issued_at": self.issued.isoformat(),
            "expires_at": (self.issued + timedelta(hours=4)).isoformat(),
        }
        self.sign()
        init = self.state("init", "--slug", self.slug,
                          "--branch", self.proposal["repository"]["branch"])
        self.assertEqual(init.returncode, 0, init.stderr)
        self.write_plan()

    def state(self, command: str, *args: str, env: dict | None = None):
        return subprocess.run(
            [sys.executable, str(STATE), command, "--slug", self.slug, *args,
             "--project", str(self.project)],
            env=self.env if env is None else env,
            capture_output=True, text=True, check=False,
        )

    def sign(self):
        self.event_file.write_bytes(packet_tool.canonical_bytes(self.event))
        plain = self.draft_dir / "canonical-event.json"
        plain.write_bytes(packet_tool.canonical_bytes(self.event))
        signed = subprocess.run([
            "openssl", "dgst", "-sha256", "-sign", str(self.key),
            "-out", str(self.signature_file), str(plain),
        ], capture_output=True, text=True, check=False)
        self.assertEqual(signed.returncode, 0, signed.stderr)

    def write_plan(self):
        spec = self.proposal["spec"]
        arch = self.proposal["architecture"]
        text = (
            "---\nslug: review-once-demo\ntype: feature\n---\n"
            "# 新增預約限制\n"
            "## 目標與範圍 <!-- crew:goal owner=spec -->\n" +
            "\n".join(spec["goal"]) + "\n"
            "## 驗收條件 <!-- crew:ac owner=spec -->\n" +
            "\n".join(spec["ac"]) + "\n"
            "## 決策紀錄 <!-- crew:dec append-only -->\n" +
            "\n".join(spec["decisions"] + arch["decisions"]) + "\n"
            "## 已知取捨與風險 <!-- crew:risk append-only -->\n"
            "## 指路 <!-- crew:map append-only -->\n"
            "## 檢查報告摘要 <!-- crew:rep append-only -->\n"
        )
        (self.spec_dir / "plan.md").write_text(text, encoding="utf-8")

    def issue(self):
        return self.state("grant", "--action", "issue", "--packet", str(self.packet_file),
                          "--approval-event", str(self.event_file),
                          "--signature", str(self.signature_file))

    def test_approved_snapshot_unlocks_only_bounded_gates(self):
        issued = self.issue()
        self.assertEqual(issued.returncode, 0, issued.stderr)
        with_missing_step = self.state("grant", "--action", "approve-requirement")
        self.assertNotEqual(with_missing_step.returncode, 0)
        spoof = self.state("gate", "--name", "requirement",
                           "--status", "approved", "--by", "human")
        self.assertNotEqual(spoof.returncode, 0)
        self.assertIn("不可直接偽裝", spoof.stderr)

        spec_done = self.state("set", "--step", "spec", "--status", "done")
        self.assertEqual(spec_done.returncode, 0, spec_done.stderr)
        spec_approved = self.state("grant", "--action", "approve-requirement")
        self.assertEqual(spec_approved.returncode, 0, spec_approved.stderr)
        db_skipped = self.state("set", "--step", "db", "--status", "skipped",
                                "--reason", "DB_REQUIRED=false")
        self.assertEqual(db_skipped.returncode, 0, db_skipped.stderr)
        arch_done = self.state("set", "--step", "arch", "--status", "done")
        self.assertEqual(arch_done.returncode, 0, arch_done.stderr)
        arch_approved = self.state("grant", "--action", "approve-architecture")
        self.assertEqual(arch_approved.returncode, 0, arch_approved.stderr)
        validated = self.state("validate", "--require-gate", "requirement",
                               "--require-gate", "architecture")
        self.assertEqual(validated.returncode, 0, validated.stdout + validated.stderr)
        build = self.state("set", "--step", "build", "--status", "in_progress")
        self.assertEqual(build.returncode, 0, build.stderr)
        self.assertEqual(self.state("grant", "--action", "check").returncode, 0)
        final = json.loads((self.spec_dir / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(final["gates"]["requirement"]["by"], "delegated-review-once")
        self.assertEqual(final["gates"]["architecture"]["by"], "delegated-review-once")
        self.assertEqual(final["gates"]["uat"]["status"], "pending")

    def test_unsigned_or_untrusted_events_are_rejected(self):
        bad_env = {k: v for k, v in self.env.items() if k != "CREW_REVIEW_ONCE_TRUSTED_PUBLIC_KEY"}
        missing_trust = self.state("grant", "--action", "issue",
                                   "--packet", str(self.packet_file),
                                   "--approval-event", str(self.event_file),
                                   "--signature", str(self.signature_file), env=bad_env)
        self.assertNotEqual(missing_trust.returncode, 0)
        self.assertIn("未配置", missing_trust.stderr)
        self.event["packet_sha256"] = "f" * 64
        self.sign()
        mismatch = self.issue()
        self.assertNotEqual(mismatch.returncode, 0)
        self.assertIn("Hash 不一致", mismatch.stderr)

    def test_expired_or_long_events_are_rejected(self):
        self.event["expires_at"] = (self.issued + timedelta(hours=4, seconds=1)).isoformat()
        self.sign()
        self.assertNotEqual(self.issue().returncode, 0)
        self.event["expires_at"] = (self.issued - timedelta(seconds=1)).isoformat()
        self.sign()
        self.assertNotEqual(self.issue().returncode, 0)

    def test_mutated_plan_pauses_gate_approval(self):
        self.assertEqual(self.issue().returncode, 0)
        self.assertEqual(self.state("set", "--step", "spec", "--status", "done").returncode, 0)
        self.write_plan()
        path = self.spec_dir / "plan.md"
        path.write_text(path.read_text(encoding="utf-8").replace("重疊時拒絕", "允許重疊"),
                        encoding="utf-8")
        rejected = self.state("grant", "--action", "approve-requirement")
        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn("AC 已偏離", rejected.stderr)

    def test_revoke_blocks_later_grant_actions(self):
        self.assertEqual(self.issue().returncode, 0)
        revoke = self.state("grant", "--action", "revoke")
        self.assertEqual(revoke.returncode, 0, revoke.stderr)
        self.assertNotEqual(self.state("grant", "--action", "check").returncode, 0)
        self.assertNotEqual(self.state("grant", "--action", "approve-requirement").returncode, 0)
        replay = self.issue()
        self.assertNotEqual(replay.returncode, 0, replay.stderr)
        self.assertIn("不可用同一個簽章重放", replay.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
