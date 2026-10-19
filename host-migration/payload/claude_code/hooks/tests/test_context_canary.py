#!/usr/bin/env python3
"""CI-CTX-03B contract tests for the Claude Code context adapter."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml


HOOK_DIR = Path(__file__).resolve().parents[1]
CLAUDE_HOME = Path(r"@@CLAUDE_HOME:win@@")
AGENT_ROOT = Path(r"@@GENERAL_ROOT:win@@")
RETIRED_CONTEXT_SCRIPTS = (
    HOOK_DIR / "scene_inject_advisory.py",
    HOOK_DIR / "agent_constitution_advisory.py",
)
if str(HOOK_DIR) not in sys.path:
    sys.path.insert(0, str(HOOK_DIR))


class ClaudeContextCanaryTests(unittest.TestCase):
    def test_effective_cwd_prefers_runner_verified_env(self) -> None:
        from claude_context_common import resolve_effective_cwd

        with patch.dict(
            os.environ,
            {"CODEX_HOOK_CALLER_CWD": r"@@TESTING_ROOT:win@@", "PATH": os.environ.get("PATH", "")},
            clear=False,
        ):
            result = resolve_effective_cwd({"cwd": r"@@OPENCLAW_ROOT:win@@"})
        self.assertEqual(result["cwd"], r"@@TESTING_ROOT:win@@")
        self.assertEqual(result["source"], "caller_env")
        self.assertTrue(result["valid"])

    def test_effective_cwd_falls_back_to_valid_event(self) -> None:
        from claude_context_common import CALLER_CWD_ENV, resolve_effective_cwd

        with patch.dict(os.environ, {CALLER_CWD_ENV: r"@@CLAUDE_HOME:win@@\hooks"}, clear=False):
            result = resolve_effective_cwd({"cwd": r"@@OPENCLAW_ROOT:win@@\projects\demo"})
        self.assertEqual(result["cwd"], r"@@OPENCLAW_ROOT:win@@\projects\demo")
        self.assertEqual(result["source"], "event_cwd")
        self.assertTrue(result["valid"])

    def test_unknown_never_falls_back_to_child_process_cwd(self) -> None:
        from claude_context_common import CALLER_CWD_ENV, resolve_effective_cwd

        with patch.dict(os.environ, {CALLER_CWD_ENV: r"@@CLAUDE_HOME:win@@\hooks"}, clear=False):
            result = resolve_effective_cwd({})
        self.assertIsNone(result["cwd"])
        self.assertEqual(result["source"], "unknown")
        self.assertFalse(result["valid"])

    def test_openclaw_containment_rejects_prefix_sibling(self) -> None:
        from claude_context_common import within_openclaw

        self.assertTrue(within_openclaw({"cwd": r"@@OPENCLAW_ROOT:win@@\child"}))
        self.assertTrue(within_openclaw({"cwd": r"@@OPENCLAW_ROOT:win@@\child"}))
        self.assertTrue(within_openclaw({"cwd": r"@@OPENCLAW_ROOT:win@@\child\..\nested"}))
        self.assertFalse(within_openclaw({"cwd": r"@@OPENCLAW_ROOT:win@@\..\other"}))
        self.assertFalse(within_openclaw({"cwd": r"@@OPENCLAW_ROOT:win@@-x"}))
        self.assertFalse(within_openclaw({"cwd": r"C:\other"}))
        self.assertFalse(within_openclaw({"cwd": r"\\server\share\openclaw-mono\child"}))
        # The user-level Claude profile is a junction to D:\.claude, not to
        # the OpenClaw project; canonicalization must not confuse it with the
        # project root.
        self.assertFalse(within_openclaw({"cwd": str(CLAUDE_HOME)}))
        self.assertFalse(within_openclaw({}))

    def test_runner_uses_outer_cwd_when_event_cwd_is_absent(self) -> None:
        with tempfile.NamedTemporaryFile(
            "w", suffix="_cwd_probe.py", dir=str(HOOK_DIR / "tests"), delete=False, encoding="utf-8"
        ) as handle:
            probe = Path(handle.name)
            handle.write(
                "import json, sys\n"
                "from claude_context_common import resolve_effective_cwd\n"
                "event = json.loads(sys.stdin.read())\n"
                "print(json.dumps(resolve_effective_cwd(event)))\n"
            )
        event = json.dumps({"hook_event_name": "SessionStart"})
        env = os.environ.copy()
        env["CODEX_HOOK_CALLER_CWD"] = r"C:\forged-inherited-value"
        try:
            proc = subprocess.run(
                [
                    sys.executable,
                    str(HOOK_DIR / "hook_runner.py"),
                    "--event",
                    "SessionStart",
                    "--script",
                    str(probe),
                ],
                input=event,
                text=True,
                capture_output=True,
                cwd=str(AGENT_ROOT),
                env=env,
                check=False,
                timeout=10,
            )
        finally:
            probe.unlink(missing_ok=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        payload = json.loads(proc.stdout)
        self.assertEqual(payload["cwd"], str(AGENT_ROOT))
        self.assertEqual(payload["source"], "caller_env")

    def test_runner_clears_forged_env_when_no_trusted_cwd_exists(self) -> None:
        with tempfile.NamedTemporaryFile(
            "w", suffix="_cwd_probe.py", dir=str(HOOK_DIR / "tests"), delete=False, encoding="utf-8"
        ) as handle:
            probe = Path(handle.name)
            handle.write(
                "import json, sys\n"
                "from claude_context_common import resolve_effective_cwd\n"
                "event = json.loads(sys.stdin.read())\n"
                "print(json.dumps(resolve_effective_cwd(event)))\n"
            )
        env = os.environ.copy()
        env["CODEX_HOOK_CALLER_CWD"] = r"C:\forged-inherited-value"
        try:
            proc = subprocess.run(
                [
                    sys.executable,
                    str(HOOK_DIR / "hook_runner.py"),
                    "--event",
                    "SessionStart",
                    "--script",
                    str(probe),
                ],
                input=json.dumps({"hook_event_name": "SessionStart"}),
                text=True,
                capture_output=True,
                cwd=str(HOOK_DIR),
                env=env,
                check=False,
                timeout=10,
            )
        finally:
            probe.unlink(missing_ok=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        payload = json.loads(proc.stdout)
        self.assertIsNone(payload["cwd"])
        self.assertEqual(payload["source"], "unknown")
        self.assertFalse(payload["valid"])

    def test_hook_directory_event_and_outer_cwd_yield_unknown(self) -> None:
        from claude_context_common import CALLER_CWD_ENV, resolve_effective_cwd

        with patch.dict(os.environ, {CALLER_CWD_ENV: str(HOOK_DIR)}, clear=False):
            result = resolve_effective_cwd({"cwd": str(HOOK_DIR)})
        self.assertIsNone(result["cwd"])
        self.assertEqual(result["source"], "unknown")
        self.assertFalse(result["valid"])

    def test_runner_overwrites_inherited_cwd_and_reports_source(self) -> None:
        with tempfile.NamedTemporaryFile(
            "w", suffix="_cwd_probe.py", dir=str(HOOK_DIR / "tests"), delete=False, encoding="utf-8"
        ) as handle:
            probe = Path(handle.name)
            handle.write(
                "import json, os\n"
                "from claude_context_common import resolve_effective_cwd\n"
                "event = json.loads(__import__('sys').stdin.read())\n"
                "print(json.dumps(resolve_effective_cwd(event)))\n"
            )
        event = json.dumps({"hook_event_name": "SessionStart", "cwd": r"@@OPENCLAW_ROOT:win@@"})
        env = os.environ.copy()
        env["CODEX_HOOK_CALLER_CWD"] = r"C:\forged-inherited-value"
        try:
            proc = subprocess.run(
                [
                    sys.executable,
                    str(HOOK_DIR / "hook_runner.py"),
                    "--event",
                    "SessionStart",
                    "--script",
                    str(probe),
                ],
                input=event,
                text=True,
                capture_output=True,
                cwd=str(HOOK_DIR),
                env=env,
                check=False,
                timeout=10,
            )
        finally:
            if probe.exists():
                probe.unlink()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        payload = json.loads(proc.stdout)
        self.assertEqual(payload["cwd"], r"@@OPENCLAW_ROOT:win@@")
        self.assertEqual(payload["source"], "caller_env")

    def test_session_start_is_mechanical_and_does_not_emit_packet_body(self) -> None:
        script = HOOK_DIR / "session_start_context.py"
        proc = subprocess.run(
            [sys.executable, str(script)],
            input=json.dumps({"hook_event_name": "SessionStart", "cwd": r"@@TESTING_ROOT:win@@"}),
            text=True,
            capture_output=True,
            cwd=str(HOOK_DIR),
            check=False,
            timeout=10,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        payload = json.loads(proc.stdout)
        context = payload["hookSpecificOutput"]["additionalContext"]
        self.assertIn("[HOST_SCOPE_FACT]", context)
        self.assertIn("hook_selection_authority", context)
        self.assertNotIn("packet-code-edit", context)
        self.assertNotIn("W1", context)
        fact = json.loads(context.split("\n", 1)[1])
        self.assertEqual(fact["host_profile"], "claude_code")
        self.assertEqual(fact["l0_sources"][0]["source_id"], "claude_code_global_claude_md")
        self.assertIsInstance(fact["l0_sources"][0]["sha256"], str)
        self.assertIsInstance(fact["l0_sources"][0]["bytes"], int)
        self.assertEqual(fact["l0_load_order"]["status"], "not_observable")
        self.assertFalse(fact["custom_hook_memory_injection"])
        self.assertFalse(fact["custom_hook_runtime_injection"])

    def test_settings_have_no_global_scene_injection(self) -> None:
        # Single-home contract (2026-09-20): user-scope SessionStart hooks are
        # registered ONLY in Claude Code managed settings. ~/.claude/settings.json
        # is owned by CC Switch (its proxy-apply path rewrites the whole file and
        # has silently dropped hooks twice: 06-20→09-11 window and 09-20 10:10:47),
        # so it must carry no hooks; ~/.claude/settings.local.json is not a
        # documented settings layer and must carry none either.
        managed_path = Path(r"@@CLAUDE_MANAGED:win@@\managed-settings.json")
        self.assertTrue(managed_path.is_file(), "managed settings file is missing")
        settings = json.loads((Path(r"@@CLAUDE_HOME:win@@") / "settings.json").read_text(encoding="utf-8"))
        self.assertNotIn("hooks", settings)
        managed = json.loads(managed_path.read_text(encoding="utf-8"))
        hooks = managed.get("hooks", {})
        registrations = [
            (event_name, str(hook.get("command", "")))
            for event_name, groups in hooks.items()
            for group in groups
            for hook in group.get("hooks", [])
        ]
        commands = [command for _, command in registrations]
        self.assertFalse(any("scene_inject_advisory.py" in command for command in commands))
        self.assertFalse(any("agent_constitution_advisory.py" in command for command in commands))
        self.assertTrue(any("session_start_context.py" in command for command in commands))
        self.assertNotIn("UserPromptSubmit", hooks)
        # Managed inventory after 2026-09-21 PreToolUse registration:
        # SessionStart (2 handlers) + PreToolUse (1 guard handler).
        self.assertEqual(set(hooks), {"SessionStart", "PreToolUse"})
        ss_cmds = [c for e, c in registrations if e == "SessionStart"]
        self.assertEqual(len(ss_cmds), 2)
        ptu_cmds = [c for e, c in registrations if e == "PreToolUse"]
        self.assertEqual(len(ptu_cmds), 1)
        self.assertTrue(any("pre_tool_use_guard.py" in c for c in ptu_cmds))
        session_groups = hooks.get("SessionStart", [])
        self.assertTrue(any("resume" in str(group.get("matcher", "")) for group in session_groups))
        self.assertTrue(any("fork" in str(group.get("matcher", "")) for group in session_groups))
        for groups in hooks.values():
            for group in groups:
                for hook in group.get("hooks", []):
                    self.assertLessEqual(int(hook.get("timeout", 0)), 30)
        local_settings = json.loads(
            (Path(r"@@CLAUDE_HOME:win@@") / "settings.local.json").read_text(encoding="utf-8")
        )
        self.assertNotIn("hooks", local_settings)

    def test_retired_context_scripts_are_absent(self) -> None:
        for script_path in RETIRED_CONTEXT_SCRIPTS:
            self.assertFalse(script_path.exists(), f"retired script remains: {script_path}")

    def test_session_start_reports_project_entries_as_unobserved_candidates(self) -> None:
        proc = subprocess.run(
            [sys.executable, str(HOOK_DIR / "session_start_context.py")],
            input=json.dumps({"hook_event_name": "SessionStart", "cwd": r"@@OPENCLAW_ROOT:win@@"}),
            text=True,
            capture_output=True,
            cwd=str(HOOK_DIR),
            check=False,
            timeout=10,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        payload = json.loads(proc.stdout)
        context = payload["hookSpecificOutput"]["additionalContext"]
        fact = json.loads(context.split("\n", 1)[1])
        candidates = {item["source_type"]: item for item in fact["project_context_candidates"]}
        self.assertIn("project_claude_md_candidate", candidates)
        self.assertIn("project_agents_candidate", candidates)
        self.assertFalse(candidates["project_claude_md_candidate"]["included_in_host_l0"])
        self.assertEqual(candidates["project_agents_candidate"]["binding_status"], "not_observed")

    def test_project_hook_keeps_w11_trace_without_global_context_registration(self) -> None:
        project_settings_path = Path(r"@@OPENCLAW_ROOT:win@@\.claude\settings.local.json")
        if not project_settings_path.is_file():
            self.skipTest("OpenClaw project settings are not present")
        settings = json.loads(project_settings_path.read_text(encoding="utf-8"))
        hooks = settings.get("hooks", {})
        commands = [
            str(hook.get("command", ""))
            for groups in hooks.values()
            for group in groups
            for hook in group.get("hooks", [])
        ]
        self.assertTrue(any("w11_interrupt_trace.py" in command for command in commands))
        self.assertFalse(any("scene_inject_advisory.py" in command for command in commands))
        self.assertFalse(any("session_start_context.py" in command for command in commands))

    def test_scope_sensitive_scripts_do_not_use_child_process_cwd(self) -> None:
        for filename in ("session_start_context.py", "codegraph_advisory.py", "pre_tool_use_guard.py"):
            text = (HOOK_DIR / filename).read_text(encoding="utf-8")
            self.assertNotIn("os.getcwd()", text, filename)

    def test_shared_contract_declares_claude_without_copying_selection_policy(self) -> None:
        contract_path = AGENT_ROOT / "context" / "context-consumption-contract.yaml"
        contract = yaml.safe_load(contract_path.read_text(encoding="utf-8"))
        boundary = yaml.safe_load((AGENT_ROOT / "context" / "context-boundary.yaml").read_text(encoding="utf-8"))
        self.assertEqual(contract["selection_policy_ref"], "context-boundary.yaml#selection_precedence")
        self.assertIn("selection_precedence", boundary)
        self.assertNotIn("selection_precedence", contract["host_profiles"])
        self.assertNotIn("selection_precedence", contract["consumers"])
        ordinary_sources = contract["host_profiles"]["ordinary_codex"]["effective_l0"]["sources"]
        self.assertEqual(contract["host_profiles"]["ordinary_codex"]["effective_l0"]["source_count"], 1)
        self.assertEqual(ordinary_sources[0]["source_type"], "host_global_agents")
        self.assertEqual(
            ordinary_sources[0]["source_ref"],
            r"@@CODEX_HOME:win@@\AGENTS.md",
        )
        self.assertIn("claude_code", contract["host_profiles"])
        claude_host = contract["host_profiles"]["claude_code"]
        self.assertEqual(claude_host["effective_l0"]["source_count"], 1)
        self.assertEqual(
            claude_host["effective_l0"]["sources"][0]["source_ref"],
            r"@@CLAUDE_HOME:win@@\CLAUDE.md",
        )
        consumer = contract["consumers"]["claude_code_interactive_agent_session"]
        # The canonical contract keeps consumer_status static and deliberately
        # does not store one-run bound_on/date snapshots. Fresh SessionStart
        # evidence is verified separately through runtime_evidence_ref.
        self.assertEqual(consumer["consumer_status"], "declared_bound")
        self.assertIn("promotion_condition", consumer)
        self.assertNotIn("bound_on", consumer)
        self.assertTrue(
            any("managed-settings.json" in str(ref) for ref in consumer["adapter_ref"]),
            "adapter_ref must point at the single-home managed registration",
        )
        self.assertNotIn("consumption_evidence", consumer)
        self.assertEqual(consumer["runtime_evidence_ref"], "acceptance_evidence_boundary")
        self.assertFalse(consumer["observation_projection"]["persistent_per_turn"])
        self.assertEqual(consumer["specialized_os"], None)
        historical_references = contract.get("historical_references") or {}
        self.assertNotIn("claude_code_user_prompt_context_hook", historical_references)
        self.assertNotIn("claude_code_constitution_advisory_hook", historical_references)
        self.assertNotIn("selection_precedence", contract["host_profiles"]["claude_code"])
        self.assertNotIn("selection_precedence", contract["consumers"]["claude_code_interactive_agent_session"])

    def test_active_hook_commands_are_enumerated_and_resolvable(self) -> None:
        managed_path = Path(r"@@CLAUDE_MANAGED:win@@\managed-settings.json")
        settings_paths = [
            managed_path,
            Path(r"@@OPENCLAW_ROOT:win@@\.claude\settings.local.json"),
            Path(r"@@TESTING_ROOT:win@@\.claude\settings.local.json"),
        ]
        registrations = []
        for settings_path in settings_paths:
            if not settings_path.is_file():
                continue
            settings = json.loads(settings_path.read_text(encoding="utf-8"))
            for event_name, groups in settings.get("hooks", {}).items():
                for group in groups:
                    for hook in group.get("hooks", []):
                        registrations.append((settings_path, event_name, hook))
        global_session_start = [
            hook
            for settings_path, event_name, hook in registrations
            if settings_path == managed_path and event_name == "SessionStart"
        ]
        self.assertEqual(len(global_session_start), 2)
        for settings_path, _event_name, hook in registrations:
            command = str(hook.get("command", ""))
            self.assertTrue(command.strip(), str(settings_path))
            for raw_path in re.findall(r"(?i)([A-Za-z]:[/\\][^\s\"']+\.(?:py|ps1))", command):
                script_path = Path(raw_path.replace("/", "\\"))
                self.assertTrue(script_path.is_file(), f"{settings_path}: {script_path}")
            self.assertNotIn("scene_inject_advisory.py", command)
            self.assertNotIn("agent_constitution_advisory.py", command)

    def test_superpowers_plugin_hook_remains_separate_and_present(self) -> None:
        registry_path = CLAUDE_HOME / "plugins" / "installed_plugins.json"
        if not registry_path.is_file():
            self.skipTest("plugin registry not present")
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
        entries = registry.get("plugins", {}).get("superpowers@claude-plugins-official", [])
        if not entries:
            self.skipTest("superpowers not installed")
        plugin_root = Path(entries[0]["installPath"])
        plugin_hook = plugin_root / "hooks" / "hooks.json"
        plugin_session_start = plugin_root / "hooks" / "session-start"
        if not plugin_hook.is_file() or not plugin_session_start.is_file():
            self.skipTest("superpowers plugin hook is not installed")
        payload = json.loads(plugin_hook.read_text(encoding="utf-8"))
        serialized = json.dumps(payload, ensure_ascii=False)
        self.assertIn("session-start", serialized)
        session_body = plugin_session_start.read_text(encoding="utf-8")
        self.assertIn("using-superpowers", session_body)
        self.assertIn("hookSpecificOutput", session_body)


if __name__ == "__main__":
    unittest.main(verbosity=2)
