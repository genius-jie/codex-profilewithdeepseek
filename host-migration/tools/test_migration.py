"""Real filesystem/Hook drills; never start a desktop app or upstream API call."""
from __future__ import annotations

import ast
import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import tomllib
import unittest

from common import HOSTS, is_reparse, json_bytes, scan_secrets, sha256, strip_secrets
from restore import (PACKAGE, apply, bindings_from_layout, plan, rollback, seal,
                     verify, package_files)
from readiness import readiness


def test_layout(base):
    general = os.environ.get("HOST_MIGRATION_GENERAL_ROOT")
    ps = os.environ.get("HOST_MIGRATION_POWERSHELL") or shutil.which("pwsh")
    if not general or not ps:
        raise RuntimeError("Set HOST_MIGRATION_GENERAL_ROOT to the pinned General clone and install PowerShell 7")
    return {"user_profile": str(base / "新用户 User"), "codexpp_profile": str(base / "CodexPP 独立"),
            "general_root": general, "python_exe": sys.executable, "powershell_exe": ps,
            "node_exe": str(base / "Program Files/nodejs/node.exe"),
            "program_files": str(base / "Program Files"), "system_root": str(base / "Windows"),
            "codexpp_source": str(base / "Tools/codex-plusplus/source"),
            "suite_root": str(base / "Projects/personal-ai-suite"),
            "core_root": str(base / "Projects/personal-ai-suite/automation-core"),
            "testing_root": str(base / "Projects/测试"), "openclaw_root": str(base / "Projects/openclaw")}


class MigrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = verify()

    def setUp(self):
        # A new-user drill must be physically outside the source clone.
        self.scratch = Path(tempfile.gettempdir()) / "codex-host-migration-tests"
        self.scratch.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix="migration-test-", dir=self.scratch)
        self.base = Path(self.temp.name)
        self.layout = test_layout(self.base)
        self.bindings = bindings_from_layout(self.layout)

    def tearDown(self):
        # Tests explicitly roll back Junctions before tempfile cleans its own files.
        self.base.resolve().relative_to(self.scratch.resolve())
        self.temp.cleanup()

    def test_complete_host_surfaces_and_private_exclusions(self):
        for host in HOSTS:
            active = {e["target_path"] for e in self.manifest["entries"] if e["component"] == host and e["installable"]}
            self.assertIn("CLAUDE.md" if host == "claude_code" else "AGENTS.md", active)
            self.assertIn("hooks/session_start_context.py", active)
            self.assertIn("settings.json" if host == "claude_code" else "config.toml", active)
            for name in active:
                self.assertFalse(name.endswith((".sqlite", ".jsonl", ".env")))
                self.assertNotIn("auth.json", name)
                self.assertNotIn("hooks/evidence/", name)
        self.assertTrue(any(e["component"] == "claude_managed" for e in self.manifest["entries"]))
        self.assertFalse(any("feishu_bot_webhooks" in e["path"] for e in self.manifest["entries"]))
        self.assertTrue(any(e["path"].startswith("review-only/codex_plus_plus/model-instructions/") for e in self.manifest["entries"]))
        for host in ("codex", "codex_plus_plus"):
            obj = tomllib.loads((PACKAGE / "payload" / host / "config.toml").read_text(encoding="utf-8"))
            self.assertNotIn("hooks", obj)
            self.assertNotIn("projects", obj)
            self.assertNotIn("model_instructions_file", obj)
            self.assertNotIn("node_repl", obj.get("mcp_servers", {}))
            self.assertIsInstance(obj.get("model_auto_compact_token_limit", 1), int)
            if host == "codex_plus_plus":
                self.assertEqual(obj["model_providers"]["cm"]["env_http_headers"]["x-openai-actor-authorization"], "CODEXPP_ACTOR_AUTHORIZATION")

    def test_credentials_are_removed_but_token_counts_survive(self):
        removed = []
        value = {"model_auto_compact_token_limit": 160000, "token": "sensitive-example",
                 "env_http_headers": {"Authorization": "PROVIDER_HEADER_ENV"},
                 "env": {"ANTHROPIC_AUTH_TOKEN": "sensitive-example", "API_TIMEOUT_MS": "3000"}}
        clean = strip_secrets(value, removed)
        self.assertEqual(clean["model_auto_compact_token_limit"], 160000)
        self.assertNotIn("token", clean)
        self.assertEqual(clean["env"], {"API_TIMEOUT_MS": "3000"})
        self.assertEqual(clean["env_http_headers"], {"Authorization": "PROVIDER_HEADER_ENV"})
        self.assertTrue(scan_secrets("key=" + "sk-" + "a" * 40))
        self.assertTrue(scan_secrets("https://open.feishu.cn/open-apis/bot/v2/hook/" + "0" * 8 + "-" + "0" * 28))

    def test_plan_is_read_only(self):
        ops = plan(self.manifest, self.bindings)
        self.assertGreater(len(ops), 100)
        self.assertEqual(list(self.base.iterdir()), [])

    def test_git_tracks_every_sealed_package_file(self):
        proc = subprocess.run(["git", "-C", str(PACKAGE.parent), "ls-files", "-z", "--", "host-migration"], capture_output=True)
        if proc.returncode:
            self.skipTest("Git tracking check applies to Git clones, not extracted archives")
        tracked = {x for x in proc.stdout.decode("utf-8").split("\0") if x}
        missing = [name for name in package_files(PACKAGE) if "host-migration/" + name not in tracked]
        self.assertEqual(missing, [])

    def test_all_hosts_support_managed_idempotency_and_rollback(self):
        support = ("launcher", "adapter", "ccs_mcp", "codexpp_source", "codexpp_tweaks")
        ops = plan(self.manifest, self.bindings, support=support, managed=True)
        receipt = self.base / "restore.json"
        result = apply(self.manifest, self.bindings, ops, receipt)
        try:
            self.assertEqual(result["status"], "applied")
            after = plan(self.manifest, self.bindings, support=support, managed=True)
            self.assertTrue(all(x["status"] == "identical" for x in after), [(x["target"],x["status"]) for x in after if x["status"] != "identical"][:3])
            for host, key in (("codex", "CODEX_HOME"), ("codex_plus_plus", "CODEXPP_HOME"), ("claude_code", "CLAUDE_HOME")):
                root = Path(self.bindings[key])
                self.assertFalse(is_reparse(root))
                for entry in self.manifest["entries"]:
                    if entry["component"] == host and entry["installable"] and entry["target_path"].endswith(".py"):
                        path = root / entry["target_path"]
                        ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
                for name in self.manifest["general"]["selected_skills"]:
                    junction = root / "skills" / name
                    self.assertTrue(is_reparse(junction))
                    self.assertEqual(junction.resolve(), (Path(self.bindings["GENERAL_ROOT"]) / "assets/skills" / name).resolve())
            self.assertEqual(tomllib.loads((Path(self.bindings["CODEX_HOME"]) / "config.toml").read_text(encoding="utf-8"))["model"], "gpt-6.1-sol")
        finally:
            rollback(receipt)
        self.assertFalse((Path(self.bindings["CODEX_HOME"]) / "config.toml").exists())
        self.assertFalse((Path(self.bindings["CODEXPP_HOME"]) / "config.toml").exists())
        self.assertFalse((Path(self.bindings["CLAUDE_HOME"]) / "settings.json").exists())
        self.assertFalse((Path(self.bindings["CLAUDE_MANAGED"]) / "managed-settings.json").exists())

    def test_real_registered_session_start_hooks_use_new_roots(self):
        ops = plan(self.manifest, self.bindings, managed=True)
        receipt = self.base / "restore.json"
        apply(self.manifest, self.bindings, ops, receipt)
        project = self.base / "新项目 with spaces"
        project.mkdir()
        (project / "AGENTS.md").write_text("Migration hook smoke fixture.\n", encoding="utf-8")
        try:
            for host, root_key in (("codex", "CODEX_HOME"), ("codex_plus_plus", "CODEXPP_HOME"), ("claude_code", "CLAUDE_HOME")):
                root = Path(self.bindings[root_key])
                registration = json.loads((Path(self.bindings["CLAUDE_MANAGED"]) / "managed-settings.json").read_text(encoding="utf-8")) if host == "claude_code" else json.loads((root / "hooks.json").read_text(encoding="utf-8"))
                env = dict(os.environ, CODEX_HOME=str(root), USERPROFILE=self.bindings["USERPROFILE"], HOME=self.bindings["USERPROFILE"], CLAUDE_CONFIG_DIR=self.bindings["CLAUDE_HOME"], CODEX_HOOK_CALLER_CWD=str(project))
                outputs = []
                for group in registration["hooks"]["SessionStart"]:
                    for hook in group["hooks"]:
                        process = subprocess.run(hook["command"], input=json.dumps({"cwd": str(project), "session_id": "migration-smoke", "hook_event_name": "SessionStart"}), text=True, encoding="utf-8", capture_output=True, env=env, cwd=project, timeout=40)
                        self.assertEqual(process.returncode, 0, host + ": " + process.stderr[:200])
                        outputs.append(process.stdout)
                facts = []
                for output in outputs:
                    for line in output.splitlines():
                        if not line.startswith("{"):
                            continue
                        outer = json.loads(line)
                        context = outer.get("hookSpecificOutput", {}).get("additionalContext", "")
                        if context.startswith("[HOST_SCOPE_FACT]\n"):
                            facts.append(json.loads(context.split("\n", 1)[1]))
                self.assertTrue(facts, host)
                entry_ref = facts[-1].get("general_os_entry_ref") or facts[-1].get("general_os_entry_refs", {}).get("global_entry")
                self.assertEqual(Path(entry_ref).resolve(), (Path(self.bindings["GENERAL_ROOT"]) / "GLOBAL-ENTRY.md").resolve())
                refs = facts[-1].get("l0_source_refs", {})
                self.assertTrue(any(str(root).casefold() in str(value).casefold() for value in refs.values()), host)
            ready = readiness(self.bindings, HOSTS, smoke=True)
            self.assertTrue(ready["configuration_ready"], ready)
            self.assertTrue(all(h["session_start_smoke"] == "passed" for h in ready["hosts"]))
        finally:
            rollback(receipt)

    def test_collision_stops_before_any_other_write(self):
        target = Path(self.bindings["CODEX_HOME"]) / "AGENTS.md"
        target.parent.mkdir(parents=True)
        target.write_text("User changes must survive", encoding="utf-8")
        ops = plan(self.manifest, self.bindings)
        with self.assertRaisesRegex(ValueError, "Collision"):
            apply(self.manifest, self.bindings, ops, self.base / "restore.json")
        self.assertEqual(target.read_text(encoding="utf-8"), "User changes must survive")
        self.assertFalse(Path(self.bindings["CLAUDE_HOME"]).exists())
        self.assertFalse((self.base / "restore.json").exists())

    def test_single_host_plan_never_includes_other_hosts(self):
        for host in HOSTS:
            ops = plan(self.manifest, self.bindings, hosts=(host,))
            self.assertTrue(all(x["host"] == host and x["component"] == host for x in ops))

    def test_overlapping_host_and_source_roots_are_rejected(self):
        bad = dict(self.layout, codexpp_profile=str(Path(self.layout["user_profile"]) / ".codex/pp"))
        with self.assertRaises(ValueError):
            bindings_from_layout(bad)
        bad = dict(self.layout, codexpp_source=str(Path(self.layout["user_profile"]) / ".claude/source"))
        with self.assertRaises(ValueError):
            bindings_from_layout(bad)

    def test_manifest_traversal_is_rejected(self):
        bad = copy.deepcopy(self.manifest)
        next(e for e in bad["entries"] if e["installable"] and e["component"] == "codex")["target_path"] = "../escape"
        with self.assertRaises(ValueError):
            plan(bad, self.bindings)

    def test_reparse_host_target_is_rejected(self):
        outside = self.base / "unrelated"
        outside.mkdir()
        target = Path(self.bindings["CODEX_HOME"])
        target.parent.mkdir()
        script = self.base / "junction.ps1"
        script.write_text("param($Link,$Source)\nNew-Item -ItemType Junction -Path $Link -Target $Source | Out-Null\n", encoding="utf-8")
        subprocess.run([self.bindings["POWERSHELL_EXE"], "-NoProfile", "-File", str(script), str(target), str(outside)], check=True, capture_output=True)
        try:
            with self.assertRaises(ValueError):
                plan(self.manifest, self.bindings)
        finally:
            target.rmdir()

    def test_new_computer_entry_preview_does_not_write(self):
        output = subprocess.run([self.bindings["POWERSHELL_EXE"], "-NoProfile", "-File", str(PACKAGE / "new-computer.ps1"),
                                 "-GeneralRoot", self.layout["general_root"], "-CodexPlusPlusProfile", self.layout["codexpp_profile"],
                                 "-UserProfile", self.layout["user_profile"], "-PythonExe", sys.executable], capture_output=True, text=True, encoding="utf-8", timeout=40)
        self.assertEqual(output.returncode, 0, output.stderr)
        summary = json.loads(output.stdout)
        self.assertGreater(summary["create"], 100)
        self.assertEqual(summary["collisions"], [])
        self.assertEqual(list(self.base.iterdir()), [])

    def test_rollback_retains_user_modified_file(self):
        ops = plan(self.manifest, self.bindings, hosts=("codex",))
        receipt = self.base / "restore.json"
        apply(self.manifest, self.bindings, ops, receipt, hosts=("codex",))
        target = Path(self.bindings["CODEX_HOME"]) / "AGENTS.md"
        original = target.read_bytes()
        target.write_text("new user work", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Changed file"):
            rollback(receipt)
        self.assertEqual(target.read_text(encoding="utf-8"), "new user work")
        target.write_bytes(original)
        rollback(receipt)


if __name__ == "__main__":
    unittest.main(verbosity=2)
