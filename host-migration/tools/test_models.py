from __future__ import annotations

import copy
from contextlib import closing
import io
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from check_models import (ProbeError, anthropic_roundtrip, chat_roundtrip, check, current_claude_model,
                          headers_for, request_json, responses_roundtrip, validate_url)
from model_portability import transform_adapter


class FakeResponse(io.BytesIO):
    def __init__(self, data, content_type):
        super().__init__(data)
        self.headers = {"Content-Type": content_type}


class ModelTests(unittest.TestCase):
    def responses_transport(self, wrong_args=False, ignore_result=False):
        calls = []
        def send(url, headers, body=None):
            calls.append(copy.deepcopy(body))
            if body is None:
                return {"data": [{"id": "test-model"}]}
            self.assertEqual(body["tool_choice"], "auto")
            if len(body["input"]) == 1:
                return {"model": "test-model", "output": [{"type": "reasoning", "id": "rs_test", "encrypted_content": "unit-opaque-reasoning"}, {"type": "function_call", "id": "fc_test", "call_id": "opaque_call",
                         "name": "migration_read_fixture", "arguments": '{"path":"unrelated"}' if wrong_args else "{}"}]}
            output = body["input"][-1]
            self.assertEqual(output["call_id"], "opaque_call")
            self.assertEqual(body["input"][-2]["type"], "function_call")
            self.assertEqual(body["input"][1]["encrypted_content"], "unit-opaque-reasoning")
            self.assertTrue(output["output"].startswith("MIGRATION_"))
            return {"model": "test-model", "output": [{"type": "message", "content": [{"type": "output_text", "text": "wrong" if ignore_result else output["output"]}]}]}
        return send, calls

    def test_responses_real_fixture_read_and_result_return(self):
        send, calls = self.responses_transport()
        result = responses_roundtrip("http://127.0.0.1:1/v1", {}, "test-model", send)
        self.assertTrue(result["tool_result_consumed"])
        self.assertEqual(len(calls), 2)
        self.assertNotIn("MIGRATION_", json.dumps(calls[0]))

    def test_model_generated_path_is_rejected_before_execution(self):
        send, calls = self.responses_transport(wrong_args=True)
        with self.assertRaisesRegex(ProbeError, "unexpected_tool_arguments"):
            responses_roundtrip("http://127.0.0.1:1/v1", {}, "test-model", send)
        self.assertEqual(len(calls), 1)

    def test_unconsumed_result_cannot_pass(self):
        send, _ = self.responses_transport(ignore_result=True)
        with self.assertRaisesRegex(ProbeError, "tool_result_not_consumed"):
            responses_roundtrip("http://127.0.0.1:1/v1", {}, "test-model", send)

    def test_anthropic_fixture_result_is_preserved(self):
        calls = []
        def send(url, headers, body=None):
            calls.append(body)
            self.assertEqual(body["tool_choice"], {"type": "auto"})
            if len(calls) == 1:
                return {"content": [{"type": "tool_use", "id": "tool_opaque", "name": "migration_read_fixture", "input": {}}]}
            result = body["messages"][-1]["content"][0]
            self.assertEqual(result["tool_use_id"], "tool_opaque")
            return {"model": "test-model", "content": [{"type": "text", "text": result["content"]}]}
        result = anthropic_roundtrip("http://127.0.0.1:1", {}, "test-model", send)
        self.assertTrue(result["tool_result_consumed"])
        self.assertEqual(len(calls), 2)

    def test_discovery_is_not_runtime_success(self):
        send, calls = self.responses_transport()
        config = {"base_url": "http://127.0.0.1:1/v1", "token_env": "UNIT_AUTH"}
        result = check("codex_plus_plus", config, ["test-model"], environ={"UNIT_AUTH": "unit-placeholder"}, transport=send)
        self.assertFalse(result["all_passed"])
        self.assertEqual(result["checks"][0]["status"], "discovery_only")
        self.assertEqual(len(calls), 1)
        self.assertNotIn("unit-placeholder", json.dumps(result))

    def test_chat_supplier_preserves_assistant_and_tool_link(self):
        calls = []
        def send(url, headers, body=None):
            calls.append(body)
            self.assertEqual(body["tool_choice"], "auto")
            if len(calls) == 1:
                return {"choices": [{"message": {"role": "assistant", "content": None, "reasoning_content": "retained reasoning",
                    "tool_calls": [{"id": "opaque", "type": "function", "function": {"name": "migration_read_fixture", "arguments": "{}"}}]}}]}
            self.assertEqual(body["messages"][-2]["reasoning_content"], "retained reasoning")
            self.assertEqual(body["messages"][-1]["tool_call_id"], "opaque")
            return {"model": "test-model", "choices": [{"message": {"content": body["messages"][-1]["content"]}}]}
        self.assertTrue(chat_roundtrip("http://localhost/v1", {}, "test-model", send)["tool_result_consumed"])

    def test_missing_credentials_never_make_request(self):
        send, calls = self.responses_transport()
        with self.assertRaisesRegex(ProbeError, "missing_environment_credential"):
            check("codex_plus_plus", {"base_url": "http://127.0.0.1:1/v1", "token_env": "UNIT_AUTH"}, ["test-model"], environ={}, transport=send)
        self.assertEqual(calls, [])

    def test_protocol_headers_do_not_duplicate_gateway_key(self):
        result = headers_for({"token_env": "UNIT_AUTH", "header_env": {"x-openai-actor-authorization": "UNIT_ACTOR"}},
                             {"UNIT_AUTH": "unit-placeholder", "UNIT_ACTOR": "unit-actor"})
        self.assertEqual(result["Authorization"], "Bearer unit-placeholder")
        self.assertNotIn("x-api-key", result)
        self.assertEqual(result["x-openai-actor-authorization"], "unit-actor")

    def test_current_claude_provider_checked_without_switching(self):
        with tempfile.TemporaryDirectory(prefix="model-provider-test-") as tmp:
            db = Path(tmp) / "fixture.db"
            with closing(sqlite3.connect(db)) as conn:
                conn.execute("CREATE TABLE providers(app_type text,is_current integer,settings_config text)")
                conn.execute("INSERT INTO providers VALUES('claude',1,?)", (json.dumps({"env": {"ANTHROPIC_MODEL": "active-model[1M]"}}),))
                conn.commit()
            before = db.read_bytes()
            self.assertEqual(current_claude_model(db), "active-model")
            with self.assertRaisesRegex(ProbeError, "does_not_match"):
                check("claude_code", {"base_url": "http://127.0.0.1:1", "token_env": "UNIT_AUTH"}, ["different-model"], environ={}, cc_switch_db=db)
            self.assertEqual(db.read_bytes(), before)

    def test_claude_multi_provider_probe_rejected(self):
        with self.assertRaisesRegex(ProbeError, "one_current_claude_provider"):
            check("claude_code", {"base_url": "http://127.0.0.1:1", "token_env": "UNIT_AUTH"}, ["a", "b"], environ={})

    def test_missing_native_database_reports_safe_error_without_creating_file(self):
        with tempfile.TemporaryDirectory(prefix="model-provider-test-") as tmp:
            db = Path(tmp) / "not-installed.db"
            with self.assertRaisesRegex(ProbeError, "claude_provider_database_unreadable"):
                current_claude_model(db)
            self.assertFalse(db.exists())

    def test_secret_in_url_and_unapproved_remote_rejected(self):
        for value in ("http://user:credential@localhost", "http://localhost/v1?token=example", "https://example.com/v1"):
            with self.assertRaises(ProbeError):
                validate_url(value)

    def test_sse_requires_real_completed_event_and_keeps_errors(self):
        good = b'data: {"type":"response.completed","response":{"output":[]}}\n\n'
        with patch("urllib.request.urlopen", return_value=FakeResponse(good, "text/event-stream")):
            self.assertEqual(request_json("http://localhost", {}), {"output": []})
        error = b'data: {"type":"error","message":"private raw upstream text"}\n\n'
        with patch("urllib.request.urlopen", return_value=FakeResponse(error, "text/event-stream")):
            with self.assertRaises(ProbeError) as got:
                request_json("http://localhost", {})
            self.assertNotIn("private raw upstream text", str(got.exception))

    def test_service_templates_use_explicit_shell_and_no_old_provider_id(self):
        result, changes = transform_adapter("adapter/install-codex-id-sanitizer-nssm.ps1", "$powershell = Join-Path $PSHOME 'powershell.exe'", "C:/PowerShell/pwsh.exe")
        self.assertIn("C:/PowerShell/pwsh.exe", result)
        self.assertTrue(changes)
        raw_installer = "$nssm = 'C:\\Windows\\system32\\nssm.exe'\n& $nssm install $serviceName 'powershell.exe'"
        result, changes = transform_adapter("adapter/install-cc-switch-sanitizer-supervisor-service.ps1", raw_installer, "C:/PowerShell/pwsh.exe")
        self.assertIn("Get-Command nssm.exe", result)
        self.assertIn("C:/PowerShell/pwsh.exe", result)
        self.assertEqual(len(changes), 2)
        raw = "$deepseekProviderId = '00000000-0000-0000-0000-000000000000'\nfunction Ensure-ClaudeDeepSeekSettings {\n}"
        result, _ = transform_adapter("adapter/start-cc-switch-sanitizer-supervisor.ps1", raw, "C:/PowerShell/pwsh.exe")
        self.assertIn("if (-not $deepseekProviderId) { return }", result)
        self.assertNotIn("00000000-0000", result)
        self.assertIn("CC_SWITCH_QWEN_UPSTREAM", result)


if __name__ == "__main__":
    unittest.main(verbosity=2)
