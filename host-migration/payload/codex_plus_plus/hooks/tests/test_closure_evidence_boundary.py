"""DDT for evidence provenance and session isolation; never uses live Hook state."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

HOOK_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HOOK_DIR))
import post_tool_use_audit as audit
import stop_receipt_validator as stop
import stop_p0_gate as p0


class EvidenceBoundaryTests(unittest.TestCase):
    def test_real_runner_failure_rerun_stop_lifecycle(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "CodexPlusPlusProfile" / ".codex"
            home.mkdir(parents=True)
            env = os.environ.copy()
            env["CODEX_HOME"] = str(home)
            env["PYTHONPATH"] = str(HOOK_DIR)
            env.pop("CODEX_COMMANDER_EXPECTED_CWD", None)
            base = {"session_id": "closure-e2e", "turn_id": "closure-e2e-turn", "cwd": str(home)}

            def invoke(kind, script, data):
                result = subprocess.run(
                    [sys.executable, str(HOOK_DIR / "hook_runner.py"), "--event", kind, "--script", str(HOOK_DIR / script)],
                    input=json.dumps({**base, **data}), text=True, encoding="utf-8",
                    capture_output=True, env=env, cwd=home, timeout=20,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertNotIn("ERROR_DOWNGRADED", result.stdout)
                return json.loads(result.stdout) if result.stdout.strip() else {}

            command = "node closure-check.mjs"
            tool = {"tool_name": "Bash", "tool_input": {"command": command}}
            invoke("PostToolUse", "post_tool_use_audit.py", {**tool, "tool_response": {"exit_code": 1, "output": "closure fixture assertion failed"}})
            final = {"last_agent_message": 'STOP_COMPLETION_RECEIPT: {"status":"complete","verification":["fixture"],"open_items":[]}'}
            blocked = invoke("Stop", "stop_guard.py", final)
            self.assertEqual(blocked.get("decision"), "block", blocked)
            self.assertIn("pending_failure_review", blocked.get("reason", ""))
            invoke("PostToolUse", "post_tool_use_audit.py", {**tool, "tool_response": {"exit_code": 0, "output": "closure fixture passed"}})
            state = json.loads((home / "hook-state" / "openclaw-mono-pending.json").read_text(encoding="utf-8"))
            self.assertEqual(state.get("pending"), {})
            self.assertNotEqual(invoke("Stop", "stop_guard.py", final).get("decision"), "block")

    def test_structured_corrected_result_is_accepted(self):
        item = {"command_fingerprint": "read-target"}
        result = json.dumps({"command_fingerprint": "read-target", "evidenceType": "S12", "corrected_result": "PASS"})
        self.assertTrue(audit.failure_review_evidence_recorded(item, "read-receipt", result))

    def test_matching_fingerprint_without_proof_is_not_accepted_or_exception(self):
        item = {"command_fingerprint": "read-target"}
        self.assertFalse(audit.failure_review_evidence_recorded(item, "read-receipt", "read-target: still under investigation"))

    def test_main_does_not_treat_command_literal_as_returned_evidence(self):
        event = {"session_id": "test-session", "tool_name": "Bash", "tool_input": {"command": "inspect 'read-target' 'S12=PASS'"}, "tool_response": {"exit_code": 0, "output": "no verification"}}
        with patch.object(audit, "read_event", return_value=event), patch.object(audit, "record_hook_run"), patch.object(audit, "sanitize_transcript_tool_ids"), patch.object(audit, "within_openclaw", return_value=False), patch.object(audit, "failure_review_resolved", return_value=False) as resolved:
            audit.main()
        self.assertNotIn("S12=PASS", resolved.call_args.args[1])

    def test_log_fallback_stays_with_named_session(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"CODEX_HOME": tmp}):
            root = Path(tmp) / "sessions"
            root.mkdir()
            (root / "rollout-foreign-session.jsonl").write_text(json.dumps({"type": "event_msg", "payload": {"type": "agent_message", "message": "foreign debt"}}), encoding="utf-8")
            self.assertEqual(stop.assistant_output_text({"session_id": "current-session"}), "")

    def test_explicit_transcript_wins_over_recent_session_logs(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"CODEX_HOME": tmp}):
            root = Path(tmp) / "sessions"
            root.mkdir()
            own = root / "rollout-current-session.jsonl"
            foreign = root / "rollout-other-session.jsonl"
            for file, msg in [(own, "current final"), (foreign, "foreign final")]:
                file.write_text(json.dumps({"type": "event_msg", "payload": {"type": "agent_message", "message": msg, "phase": "final"}}), encoding="utf-8")
            os.utime(foreign, (2_000_000_000, 2_000_000_000))
            self.assertEqual(stop.assistant_output_text({"session_id": "current-session", "transcript_path": str(own)}), "current final")

    def test_default_profile_is_physical_hook_home(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(Path, "home", return_value=Path("C:/unrelated-profile")):
            self.assertEqual(stop._session_roots()[0], HOOK_DIR.parent / "sessions")
            self.assertTrue(p0._is_codex_plusplus_home())

    def test_receipt_needs_status_verification_and_explicit_closed_items(self):
        for receipt in [{"verification": ["test pass"], "open_items": []}, {"status": "complete", "verification": ["test pass"]}, {"status": "complete", "open_items": []}]:
            with self.subTest(receipt=receipt):
                self.assertTrue(stop.receipt_guard_reason("STOP_COMPLETION_RECEIPT: " + json.dumps(receipt)))

    def test_closed_items_must_be_a_list_not_a_falsey_placeholder(self):
        for value in [None, False, "", "none", {}]:
            with self.subTest(value=value):
                receipt = {"status": "complete", "verification": ["test pass"], "open_items": value}
                self.assertTrue(stop.receipt_guard_reason("STOP_COMPLETION_RECEIPT: " + json.dumps(receipt)))

    def test_complete_receipt_and_current_debt_stay_distinct(self):
        with patch.dict(os.environ, {"CODEX_HOME": str(HOOK_DIR.parent)}):
            good = {"status": "complete", "verification": ["targeted regression passed"], "open_items": []}
            text = "STOP_COMPLETION_RECEIPT: " + json.dumps(good)
            self.assertEqual(stop.completion_guard_reason({}, text, {}), "")
            good["open_items"] = ["production run not terminal"]
            self.assertTrue(stop.completion_guard_reason({}, "STOP_COMPLETION_RECEIPT: " + json.dumps(good), {}))

    def test_followup_is_not_current_debt(self):
        followup = {"codex_follow_up_candidate": True, "items": [{"prompt": "下一步建议验证新的项目范围"}]}
        self.assertEqual(stop.completion_guard_reason({}, "本次审计通过。\n```json\n" + json.dumps(followup, ensure_ascii=False) + "\n```", {}), "")


if __name__ == "__main__":
    unittest.main()
