#!/usr/bin/env python3
"""Targeted PreToolUse candidate and runner protocol checks."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


HOOK_DIR = Path(__file__).resolve().parents[1]
RUNNER = HOOK_DIR / "hook_runner.py"
GUARD = HOOK_DIR / "pre_tool_use_guard.py"

if str(HOOK_DIR) not in sys.path:
    sys.path.insert(0, str(HOOK_DIR))


class PreToolUseChainTests(unittest.TestCase):
    def invoke_guard(self, event: dict) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                str(RUNNER),
                "--event",
                "PreToolUse",
                "--script",
                str(GUARD),
            ],
            input=json.dumps(event),
            text=True,
            capture_output=True,
            cwd=str(HOOK_DIR),
            check=False,
            timeout=10,
        )

    def test_dependency_flow_option_is_not_mistaken_for_missing_requirements_file(self) -> None:
        from pre_tool_use_guard import is_dependency_flow_hint

        self.assertTrue(is_dependency_flow_hint("pip install requests"))
        self.assertTrue(is_dependency_flow_hint("python -m pip install requests"))
        self.assertFalse(is_dependency_flow_hint("pip install -r requirements.txt"))
        self.assertFalse(is_dependency_flow_hint("pip install --requirement requirements.txt"))
        self.assertFalse(is_dependency_flow_hint("pip install --requirement=requirements.txt"))
        self.assertFalse(is_dependency_flow_hint("py -m pip install -r requirements.txt"))

    def test_advisory_round_trip_through_runner(self) -> None:
        result = self.invoke_guard(
            {
                "tool_name": "PowerShell",
                "tool_input": {"command": "pip install requests"},
            }
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertIn("DEPENDENCY_FLOW_HINT", payload["message"])
        self.assertEqual(result.stderr, "")

    def test_requirements_file_round_trip_is_silent(self) -> None:
        result = self.invoke_guard(
            {
                "tool_name": "PowerShell",
                "tool_input": {"command": "pip install --requirement requirements.txt"},
            }
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "")
        self.assertEqual(result.stderr, "")

    def test_blocking_round_trip_keeps_exit_code_and_reason(self) -> None:
        result = self.invoke_guard(
            {
                "tool_name": "Bash",
                "tool_input": {"command": "git commit --no-verify"},
            }
        )
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")
        self.assertIn("destructive git operation", result.stderr)

    def test_pretooluse_registration_is_bound_and_scoped(self) -> None:
        managed = Path(r"@@CLAUDE_MANAGED:win@@\managed-settings.json")
        settings = json.loads(managed.read_text(encoding="utf-8"))
        hooks = settings.get("hooks", {})
        self.assertIn("PreToolUse", hooks)
        entry = hooks["PreToolUse"][0]
        self.assertEqual(entry["matcher"], "Bash|PowerShell|Edit|Write")
        command = entry["hooks"][0]["command"]
        self.assertIn("hook_runner.py", command)
        self.assertIn("--event PreToolUse", command)
        self.assertIn("pre_tool_use_guard.py", command)

    def test_runner_preserves_child_exit_code_and_streams(self) -> None:
        with tempfile.NamedTemporaryFile(
            "w",
            suffix="_runner_probe.py",
            dir=str(HOOK_DIR / "tests"),
            delete=False,
            encoding="utf-8",
        ) as handle:
            probe = Path(handle.name)
            handle.write(
                "import sys\n"
                "sys.stdout.write('child-stdout\\n')\n"
                "sys.stderr.write('child-stderr\\n')\n"
                "raise SystemExit(2)\n"
            )
        try:
            result = subprocess.run(
                [
                    sys.executable,
                    str(RUNNER),
                    "--event",
                    "PreToolUse",
                    "--script",
                    str(probe),
                ],
                input=json.dumps({"tool_name": "Write", "tool_input": {}}),
                text=True,
                capture_output=True,
                cwd=str(HOOK_DIR),
                check=False,
                timeout=10,
            )
        finally:
            probe.unlink(missing_ok=True)

        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "child-stdout\n")
        self.assertEqual(result.stderr, "child-stderr\n")


if __name__ == "__main__":
    unittest.main(verbosity=2)
