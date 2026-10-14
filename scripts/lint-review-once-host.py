#!/usr/bin/env python3
"""Live subprocess Host Bridge tests using real signed grants and fake workers.

No API tokens or actual Claude/Codex sessions required; verifies actual
orchestration, process exit, scope checks and false-success rejection.
"""
from __future__ import annotations

import importlib.util
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

REPO = Path(__file__).resolve().parent.parent
FEATURE = REPO / "plugins/feature-workflow/scripts"


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


fixture = load(REPO / "scripts/lint-review-once-runner.py", "review_once_runner_fixture")
bridge = load(FEATURE / "review-once-host.py", "crew_host_bridge")
packet = fixture.g.packet_tool


class HostBridgeScenarios(unittest.TestCase):
    setUp = fixture.RunnerScenarios.setUp
    sign = fixture.RunnerScenarios.sign
    state = fixture.RunnerScenarios.state
    issue = fixture.RunnerScenarios.issue
    write_plan = fixture.RunnerScenarios.write_plan
    set_skeleton = fixture.RunnerScenarios.set_skeleton

    def git(self, *argv):
        p = subprocess.run(["git", "-C", str(self.project), *argv],
                           capture_output=True, text=True, check=True)
        return p.stdout.strip()

    def prepare_repo(self):
        self.git("init", "-q")
        self.git("config", "user.email", "ci@example.invalid")
        self.git("config", "user.name", "CI")
        self.git("checkout", "-q", "-b", "feat/review-demo")
        (self.project / "src").mkdir()
        (self.project / "src" / "app.py").write_text("print('baseline')\n")
        (self.project / ".gitignore").write_text(".spec/\n")
        self.git("add", ".gitignore", "src/app.py")
        self.git("commit", "-q", "-m", "baseline")
        self.proposal["repository"]["base_commit"] = self.git("rev-parse", "HEAD")
        self.packet = packet.create_packet(self.proposal)
        self.packet_file.write_bytes(packet.canonical_bytes(self.packet))
        self.event["repository"] = self.proposal["repository"]
        self.event["packet_sha256"] = self.packet["packet_sha256"]
        self.sign()
        self.set_skeleton()
        res = self.issue()
        self.assertEqual(res.returncode, 0, res.stderr)

    def protected_worker(self, behavior: str = "success") -> Path:
        # Trust config and fake worker are held under the CI process home,
        # outside agent-writable repo, with parent permissions 0700.
        if not hasattr(self, "_host_dir"):
            self._host_dir = tempfile.TemporaryDirectory(dir=Path.home())
            self.addCleanup(self._host_dir.cleanup)
        host = Path(self._host_dir.name)
        worker = host / "mock-host-worker.py"
        worker.write_text(
            "import pathlib, subprocess, sys\n"
            "project, slug, instruction = sys.argv[1:]\n"
            "assert instruction.startswith('/plan-build --')\n"
            f"behavior = {behavior!r}\n"
            "if behavior == 'fail': sys.exit(9)\n"
            "if behavior == 'revoke':\n"
            "  p = subprocess.run([sys.executable, " + repr(str(FEATURE / "crew-state.py")) +
            ", 'grant', '--action', 'revoke', '--slug', slug, '--project', project], check=True)\n"
            "  sys.exit(0)\n"
            "if behavior == 'out-of-scope':\n"
            "  pathlib.Path(project, 'secret.txt').write_text('changed')\n"
            "if behavior == 'success':\n"
            "  pathlib.Path(project, 'src', 'app.py').write_text(\"print('done')\\n\")\n"
            "if behavior != 'no-evidence':\n"
            "  subprocess.run([sys.executable, " + repr(str(FEATURE / "crew-state.py")) +
            ", 'set', '--step', 'build', '--status', 'done', '--slug', slug, '--project', project], check=True)\n"
        )
        worker.chmod(0o600)
        cfg = host / "adapter.json"
        cfg.write_text(json.dumps({
            "schema_version": 1, "adapter": "trusted-host",
            "worker_argv": [sys.executable, str(worker),
                            "{project}", "{slug}", "{instruction}"],
            "host_guarantees": {
                "protected_human_approval": True,
                "enforced_write_scope": True,
                "worker_cancellation": True,
                "no_unattended_escalation": True,
            },
        }))
        cfg.chmod(0o600)
        return cfg

    def drive(self, behavior="success"):
        adapter = self.protected_worker(behavior)
        with patch.dict(os.environ, {
            "CREW_REVIEW_ONCE_TRUSTED_PUBLIC_KEY": str(self.pub)
        }):
            return bridge.drive(self.project, self.slug, "test-host",
                                bridge.protected_config(adapter, self.project),
                                "start", poll=0.1)

    def test_end_to_end_signed_host_build_stops_before_uat(self):
        self.prepare_repo()
        result = self.drive("success")
        self.assertEqual(result["status"], "completed_build")
        state = json.loads((self.spec_dir / "state.json").read_text())
        self.assertEqual(state["steps"]["spec"]["status"], "done")
        self.assertEqual(state["steps"]["db"]["status"], "skipped")
        self.assertEqual(state["steps"]["arch"]["status"], "done")
        self.assertEqual(state["steps"]["build"]["status"], "done")
        self.assertEqual(state["steps"]["verify"]["status"], "pending")
        self.assertEqual(state["gates"]["uat"]["status"], "pending")
        self.assertEqual(state["autonomy"]["status"], "consumed")
        self.assertEqual(self.git("diff", "--name-only"), "src/app.py")

    def test_no_false_success_when_worker_exits_without_evidence(self):
        self.prepare_repo()
        with self.assertRaisesRegex(bridge.BridgeError, "未以正式 state writer 完成 Build"):
            self.drive("no-evidence")
        state = json.loads((self.spec_dir / "state.json").read_text())
        self.assertEqual(state["autonomy"]["execution"]["status"], "paused")
        self.assertEqual(state["steps"]["build"]["status"], "pending")
        self.assertEqual(state["autonomy"]["execution"]["inflight"]["step"], "build")

    def test_nonzero_host_exit_pauses_at_exact_checkpoint(self):
        self.prepare_repo()
        with self.assertRaisesRegex(bridge.BridgeError, "exit=9"):
            self.drive("fail")
        state = json.loads((self.spec_dir / "state.json").read_text())
        self.assertEqual(state["autonomy"]["execution"]["status"], "paused")
        self.assertEqual(state["autonomy"]["execution"]["inflight"]["step"], "build")

    def test_unapproved_write_scope_blocks_successful_worker(self):
        self.prepare_repo()
        with self.assertRaisesRegex(bridge.BridgeError, "超出核准 Git 檔案範圍"):
            self.drive("out-of-scope")
        state = json.loads((self.spec_dir / "state.json").read_text())
        self.assertEqual(state["autonomy"]["execution"]["status"], "paused")
        self.assertNotEqual(state["autonomy"]["status"], "consumed")

    def test_revoke_during_host_worker_stops_pipeline(self):
        self.prepare_repo()
        with self.assertRaisesRegex(bridge.BridgeError, "授權"):
            self.drive("revoke")
        state = json.loads((self.spec_dir / "state.json").read_text())
        self.assertEqual(state["autonomy"]["status"], "revoked")
        self.assertNotEqual(state["autonomy"]["execution"]["status"], "completed_build")

    def test_explicit_resume_runs_the_original_inflight_build(self):
        self.prepare_repo()
        with self.assertRaises(bridge.BridgeError):
            self.drive("fail")
        config = self.protected_worker("success")
        with patch.dict(os.environ, {
            "CREW_REVIEW_ONCE_TRUSTED_PUBLIC_KEY": str(self.pub)
        }):
            result = bridge.drive(
                self.project, self.slug, "test-host",
                bridge.protected_config(config, self.project),
                "resume", poll=0.1, reconcile=True,
                reason="operator verified previous worker exited",
            )
        self.assertEqual(result["status"], "completed_build")
        state = json.loads((self.spec_dir / "state.json").read_text())
        self.assertEqual(state["autonomy"]["status"], "consumed")
        self.assertEqual(state["autonomy"]["execution"]["checkpoint"], "build")

    def test_reject_unprotected_or_workspace_controlled_adapter(self):
        self.prepare_repo()
        config = self.protected_worker()
        valid = bridge.protected_config(config, self.project)
        self.assertEqual(valid["adapter"], "trusted-host")
        evil = self.project / "host.json"
        evil.write_text(config.read_text())
        with self.assertRaisesRegex(bridge.BridgeError, "設定不能位於"):
            bridge.protected_config(evil, self.project)
        config.chmod(0o666)
        with self.assertRaisesRegex(bridge.BridgeError, "非 owner 修改"):
            bridge.protected_config(config, self.project)
        config.chmod(0o600)
        obj = json.loads(config.read_text())
        worker = self.project / "untrusted-worker.py"
        worker.write_text("print('do not run')\n")
        obj["worker_argv"][1] = str(worker)
        config.write_text(json.dumps(obj))
        with self.assertRaisesRegex(bridge.BridgeError, "Repo 中 Agent 可修改"):
            bridge.protected_config(config, self.project)
        obj["worker_argv"][1] = str(Path(self._host_dir.name) / "mock-host-worker.py")
        obj["host_guarantees"]["enforced_write_scope"] = False
        config.write_text(json.dumps(obj))
        with self.assertRaisesRegex(bridge.BridgeError, "Host 缺少"):
            bridge.protected_config(config, self.project)


if __name__ == "__main__":
    unittest.main(verbosity=2)
