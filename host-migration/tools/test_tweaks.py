"""Restore existing tweaks into a new profile and run their own checks offline."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from common import fs_path, json_bytes
from restore import PACKAGE, apply, bindings_from_layout, plan, rollback, verify
from test_migration import test_layout


class TweakTests(unittest.TestCase):
    def test_native_renderer_preference_transport(self):
        node = shutil.which("node")
        self.assertIsNotNone(node, "Install the documented Node runtime before the tweak check")
        proc = subprocess.run([node, str(PACKAGE / "tools/test-tweak-preferences.cjs")], capture_output=True, text=True, timeout=20)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def test_restored_follow_up_contract_and_native_regressions(self):
        node = shutil.which("node")
        self.assertIsNotNone(node)
        manifest = verify()
        with tempfile.TemporaryDirectory(prefix="host-tweak-migration-") as tmp:
            base = Path(tmp)
            bindings = bindings_from_layout(test_layout(base))
            hosts = ("codex_plus_plus",)
            support = ("codexpp_source", "codexpp_tweaks")
            operations = plan(manifest, bindings, hosts=hosts, support=support)
            receipt = base / "restore.json"
            apply(manifest, bindings, operations, receipt, hosts=hosts)
            source = Path(bindings["CODEXPP_SOURCE"]) / "tweaks/auto-follow-up"
            runtime = Path(bindings["CODEXPP_RUNTIME"])
            installed = runtime / "tweaks/com.lobster.auto-follow-up"
            config = runtime / "config.json"
            env = dict(os.environ, CODEX_HOME=bindings["CODEXPP_HOME"], USERPROFILE=bindings["USERPROFILE"])

            def run_guard(folder=source, extra=()):
                return subprocess.run([node, str(folder / "scripts/verify-auto-follow-up-contract.js"), *extra],
                                      cwd=folder, env=env, capture_output=True, text=True, timeout=40)
            try:
                contract = json.loads((source / "auto-follow-up.contract.json").read_text("utf-8"))
                self.assertEqual(Path(contract["source_path"]), source)
                self.assertEqual(Path(contract["installed_path"]), installed)
                self.assertEqual(Path(contract["codex_plusplus_config_path"]), config)
                self.assertFalse((runtime / "state.json").exists())
                self.assertFalse((runtime / "self-update-state.json").exists())
                for folder in (source, installed):
                    proc = run_guard(folder)
                    self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
                companion = runtime / "tweaks/co.Arconte112.followup"
                proc = subprocess.run([node, str(companion / "tests/real-final-sidecar.test.js")], cwd=companion,
                                      env=env, capture_output=True, text=True, timeout=40)
                self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

                original_config = config.read_bytes()
                for plugin in ("com.lobster.auto-follow-up", "co.Arconte112.followup"):
                    changed = json.loads(original_config)
                    changed["tweaks"][plugin]["enabled"] = False
                    config.write_bytes(json_bytes(changed))
                    self.assertNotEqual(run_guard().returncode, 0)
                    self.assertEqual(config.read_bytes(), json_bytes(changed))
                config.write_bytes(original_config)
                automation = installed / "automation.js"
                original_automation = automation.read_bytes()
                automation.write_bytes(original_automation + b"\n// temporary drift fixture\n")
                self.assertNotEqual(run_guard().returncode, 0)
                automation.write_bytes(original_automation)
                proc = run_guard(extra=("--repair",))
                self.assertNotEqual(proc.returncode, 0)
                self.assertIn("read-only verification", proc.stderr)
                self.assertEqual(config.read_bytes(), original_config)
                self.assertEqual(automation.read_bytes(), original_automation)
                proc = run_guard()
                self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
                self.assertFalse((Path(bindings["USERPROFILE"]) / "AppData/Roaming/codex-plusplus").exists())
            finally:
                rollback(receipt)


if __name__ == "__main__":
    unittest.main(verbosity=2)
