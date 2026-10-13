#!/usr/bin/env python3
"""Review Once proposal self-tests, with zero third-party dependencies."""
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "plugins/feature-workflow/scripts/review-once-packet.py"
spec = importlib.util.spec_from_file_location("review_once_packet", CLI)
assert spec and spec.loader
pkt = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pkt)


def fixture():
    return {
        "schema_version": 1, "mode": "review_once", "task_type": "feature",
        "slug": "booking-feature",
        "repository": {
            "full_name": "example/booking", "branch": "feat/booking",
            "base_commit": "a" * 40
        },
        "spec": {
            "goal": ["- Allow booking", "- Exclude production deploy"],
            "ac": ["- [ ] AC-1 不能重複預約｜例：S01 正常；S02 衝突"],
            "decisions": ["- D-1 [spec] 範圍判斷：TASK_TYPE=feature"],
            "risks": [],
        },
        "db": {"required": False, "deploy_sql": "", "decisions": []},
        "architecture": {"decisions": ["- D-2 [arch] 採 Service 層｜理由：..."], "risks": []},
        "scope": {"allowed_paths": ["src/**", "tests/**"],
                  "allowed_actions": ["write_source", "write_tests"]},
        "test_policy": "with_test", "max_duration_seconds": 14400,
    }


class ReviewPacketScenarios(unittest.TestCase):
    def test_snapshot_is_deterministic(self):
        a = fixture()
        p = pkt.create_packet(a)
        self.assertEqual(pkt.verify_packet(p), a)
        reordered = {k: a[k] for k in reversed(a)}
        self.assertEqual(p["packet_sha256"], pkt.create_packet(reordered)["packet_sha256"])

    def test_revise_requires_new_packet_hash(self):
        a = fixture()
        signed = pkt.create_packet(a)
        a["spec"]["ac"][0] += "；S03 邊界"
        self.assertNotEqual(signed["packet_sha256"], pkt.create_packet(a)["packet_sha256"])
        with self.assertRaisesRegex(pkt.PacketError, "mismatch"):
            pkt.verify_packet(signed)

    def test_fail_closed_on_malformed_or_unapproved_inputs(self):
        for path, value in [
            ("max_duration_seconds", 14401), ("mode", "autonomous"),
            ("task_type", "bug"), ("test_policy", "no_test"),
        ]:
            a = fixture()
            a[path] = value
            with self.subTest(path=path), self.assertRaises(pkt.PacketError):
                pkt.create_packet(a)
        a = fixture()
        a["scope"]["allowed_paths"] = ["../secrets"]
        with self.assertRaises(pkt.PacketError):
            pkt.create_packet(a)
        a = fixture()
        a["scope"]["allowed_actions"] = ["git_push"]
        with self.assertRaises(pkt.PacketError):
            pkt.create_packet(a)
        a = fixture()
        a["db"]["required"] = True
        with self.assertRaises(pkt.PacketError):
            pkt.create_packet(a)

    def test_reject_malformed_ac_and_arch(self):
        for ac in ("- AC-1 no checkbox", "- [ ] AC-0 invalid"):
            a = fixture()
            a["spec"]["ac"] = [ac]
            with self.assertRaises(pkt.PacketError):
                pkt.create_packet(a)
        a = fixture()
        a["architecture"]["decisions"] = ["- D-2 [spec] wrong owner"]
        with self.assertRaises(pkt.PacketError):
            pkt.create_packet(a)

    def test_cli_prepare_verify_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            draft = root / "draft.json"
            output = root / "packet.json"
            draft.write_text(json.dumps(fixture(), ensure_ascii=False), encoding="utf-8")
            ok = subprocess.run([sys.executable, str(CLI), "prepare", "--draft",
                                 str(draft), "--output", str(output)],
                                capture_output=True, text=True)
            self.assertEqual(ok.returncode, 0, ok.stderr)
            self.assertEqual(json.loads(ok.stdout)["status"], "awaiting_review")
            verify = subprocess.run([sys.executable, str(CLI), "verify", "--packet", str(output)],
                                    capture_output=True, text=True)
            self.assertEqual(verify.returncode, 0, verify.stderr)
            self.assertEqual(json.loads(verify.stdout)["status"], "valid_unapproved_packet")
            again = subprocess.run([sys.executable, str(CLI), "prepare", "--draft",
                                    str(draft), "--output", str(output)],
                                   capture_output=True, text=True)
            self.assertEqual(again.returncode, 1)
            self.assertIn("已存在", again.stderr)
            forbidden = subprocess.run([sys.executable, str(CLI), "prepare", "--draft",
                                        str(draft), "--output", str(root / "state.json")],
                                       capture_output=True, text=True)
            self.assertEqual(forbidden.returncode, 1)
            corrupt = json.loads(output.read_text(encoding="utf-8"))
            corrupt["proposal"]["spec"]["ac"][0] += " modified"
            output.write_text(json.dumps(corrupt, ensure_ascii=False), encoding="utf-8")
            bad = subprocess.run([sys.executable, str(CLI), "verify", "--packet", str(output)],
                                 capture_output=True, text=True)
            self.assertEqual(bad.returncode, 1)
            self.assertIn("mismatch", bad.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
