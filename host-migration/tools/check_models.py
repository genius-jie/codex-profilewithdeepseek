"""Read-only route checks and bounded, explicit real model/tool round trips.

Uses the existing gateway/CC Switch. Never changes provider selection, registers
services, runs model-generated code, or prints credentials/raw upstream errors.
"""
from __future__ import annotations

import argparse
import http.client
import json
import os
from pathlib import Path
import secrets
import sqlite3
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request

from common import fs_path, json_bytes, load_json

PACKAGE = Path(__file__).resolve().parents[1]
TOOL = "migration_read_fixture"


class ProbeError(Exception):
    def __init__(self, code, status=None):
        super().__init__(code)
        self.code, self.status = code, status


def validate_url(url, allow_remote=False):
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ProbeError("invalid_endpoint")
    if not allow_remote and parsed.hostname not in ("127.0.0.1", "localhost", "::1"):
        raise ProbeError("remote_endpoint_requires_explicit_flag")
    return url.rstrip("/")


def headers_for(config, environ):
    name = config["token_env"]
    token = environ.get(name, "")
    if not token or token.startswith(("<", "YOUR_", "FILL_")):
        raise ProbeError("missing_environment_credential:" + name)
    headers = {"Content-Type": "application/json"}
    auth_header = config.get("auth_header", "Authorization")
    headers[auth_header] = "Bearer " + token if auth_header.lower() == "authorization" else token
    for header, variable in config.get("header_env", {}).items():
        if environ.get(variable):
            headers[header] = environ[variable]
    return headers


def request_json(url, headers, body=None, timeout=45):
    request = urllib.request.Request(url, data=None if body is None else json_bytes(body), headers=headers,
                                     method="GET" if body is None else "POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            # A diagnostic probe must stay bounded even if a service streams forever.
            content_type = response.headers.get("Content-Type", "")
            if "text/event-stream" in content_type:
                chunks, total = [], 0
                deadline = time.monotonic() + timeout
                while time.monotonic() < deadline:
                    line = response.readline(65537)
                    if not line:
                        break
                    total += len(line)
                    if total > 512 * 1024 or len(line) > 65536:
                        raise ProbeError("response_limit_exceeded")
                    chunks.append(line)
                    if line.startswith(b"data:"):
                        try:
                            event = json.loads(line[5:].strip())
                        except json.JSONDecodeError:
                            continue
                        if event.get("type") in ("response.completed", "response.failed", "error"):
                            chunks.append(b"\n")
                            break
                else:
                    raise ProbeError("stream_deadline_exceeded")
                data = b"".join(chunks)
            else:
                data = response.read(512 * 1024 + 1)
    except urllib.error.HTTPError as exc:
        raise ProbeError("http_error", exc.code) from None
    except (urllib.error.URLError, TimeoutError, OSError, http.client.HTTPException):
        raise ProbeError("connection_or_timeout") from None
    if len(data) > 512 * 1024:
        raise ProbeError("response_limit_exceeded")
    try:
        if "text/event-stream" in content_type:
            events = []
            for frame in data.decode("utf-8").replace("\r\n", "\n").split("\n\n"):
                value = "\n".join(line[5:].lstrip() for line in frame.splitlines() if line.startswith("data:"))
                if not value or value == "[DONE]":
                    continue
                item = json.loads(value)
                if item.get("type") in ("error", "response.failed"):
                    raise ProbeError("upstream_stream_error")
                events.append(item)
            for item in reversed(events):
                if item.get("type") == "response.completed":
                    return item["response"]
            raise ProbeError("response_completed_missing")
        obj = json.loads(data)
    except (UnicodeDecodeError, json.JSONDecodeError, KeyError):
        raise ProbeError("invalid_response_shape") from None
    if not isinstance(obj, dict):
        raise ProbeError("invalid_response_shape")
    if obj.get("error") or obj.get("type") == "error":
        raise ProbeError("upstream_error")
    return obj


def current_claude_model(db):
    """Observe native CC Switch ownership; never copy or mutate its database."""
    path = Path(db).resolve()
    conn = None
    try:
        conn = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)
        conn.execute("PRAGMA query_only=ON")
        rows = conn.execute("SELECT settings_config FROM providers WHERE app_type='claude' AND is_current=1").fetchall()
        if len(rows) != 1:
            raise ProbeError("claude_provider_selection_ambiguous")
        env = json.loads(rows[0][0]).get("env", {})
        model = env.get("ANTHROPIC_MODEL") or env.get("ANTHROPIC_DEFAULT_SONNET_MODEL")
        if not model:
            raise ProbeError("claude_provider_model_missing")
        return str(model).removesuffix("[1M]")
    except (sqlite3.Error, json.JSONDecodeError):
        raise ProbeError("claude_provider_database_unreadable") from None
    finally:
        if conn is not None:
            conn.close()


def response_text(obj):
    result = []
    for item in obj.get("output", []):
        if item.get("type") == "message":
            result.extend(part.get("text", "") for part in item.get("content", []) if part.get("type") == "output_text")
    return "".join(result)


def responses_roundtrip(base, headers, model, transport=request_json):
    """A genuine model call, an actual local fixture read, then tool-result use."""
    challenge = "MIGRATION_" + secrets.token_hex(12)
    schema = {"type": "object", "properties": {}, "required": [], "additionalProperties": False}
    user = {"role": "user", "content": [{"type": "input_text", "text": "Call " + TOOL + " once to read the prepared test fixture. After the result, return its content exactly. Do not guess its content."}]}
    first = {"model": model, "input": [user], "stream": True, "store": False,
             "max_output_tokens": 2048, "reasoning": {"effort": "low"},
             "tools": [{"type": "function", "name": TOOL, "description": "Read the prepared migration fixture; no arguments.", "parameters": schema, "strict": True}],
             "tool_choice": "auto"}
    answer = transport(base + "/responses", headers, first)
    calls = [x for x in answer.get("output", []) if x.get("type") == "function_call"]
    if len(calls) != 1 or calls[0].get("name") != TOOL:
        raise ProbeError("expected_single_fixture_tool_call")
    call = calls[0]
    try:
        arguments = json.loads(call.get("arguments", ""))
    except json.JSONDecodeError:
        raise ProbeError("invalid_tool_arguments") from None
    if arguments != {} or not call.get("call_id"):
        raise ProbeError("unexpected_tool_arguments_or_call_id")
    # Model-generated arguments never determine a file path or executable.
    with tempfile.TemporaryDirectory(prefix="model-migration-probe-") as scratch:
        fixture = Path(scratch) / "fixture.txt"
        fs_path(fixture).write_bytes(challenge.encode("utf-8"))
        actual = fs_path(fixture).read_text(encoding="utf-8")
    # Native Responses callers replay all output items, including reasoning
    # and assistant messages. Do not reduce a response to its tool call alone.
    second = {**first, "tool_choice": "auto", "input": [user, *answer.get("output", []),
              {"type": "function_call_output", "call_id": call["call_id"], "output": actual}]}
    final = transport(base + "/responses", headers, second)
    if challenge not in response_text(final):
        raise ProbeError("tool_result_not_consumed")
    return {"http_model_roundtrip": "passed", "local_fixture_tool": "passed", "tool_result_consumed": True,
            "reported_model_matches_request": final.get("model") == model, "native_desktop_ui": "requires_target_host_acceptance"}


def anthropic_roundtrip(base, headers, model, transport=request_json):
    challenge = "MIGRATION_" + secrets.token_hex(12)
    tool = {"name": TOOL, "description": "Read the prepared migration fixture; no arguments.",
            "input_schema": {"type": "object", "properties": {}, "additionalProperties": False}}
    messages = [{"role": "user", "content": "Use " + TOOL + " once. Then repeat exactly the text returned by the tool."}]
    first = {"model": model, "messages": messages, "tools": [tool], "tool_choice": {"type": "auto"}, "max_tokens": 2048}
    answer = transport(base + "/v1/messages", headers, first)
    blocks = answer.get("content", [])
    calls = [x for x in blocks if x.get("type") == "tool_use"]
    if len(calls) != 1 or calls[0].get("name") != TOOL or calls[0].get("input") != {} or not calls[0].get("id"):
        raise ProbeError("expected_single_fixture_tool_call")
    with tempfile.TemporaryDirectory(prefix="model-migration-probe-") as scratch:
        fixture = Path(scratch) / "fixture.txt"
        fs_path(fixture).write_bytes(challenge.encode("utf-8"))
        actual = fs_path(fixture).read_text(encoding="utf-8")
    final = transport(base + "/v1/messages", headers, {**first, "tool_choice": {"type": "auto"}, "messages": messages + [
        {"role": "assistant", "content": blocks}, {"role": "user", "content": [{"type": "tool_result", "tool_use_id": calls[0]["id"], "content": actual}]}]})
    text = "".join(x.get("text", "") for x in final.get("content", []) if x.get("type") == "text")
    if challenge not in text:
        raise ProbeError("tool_result_not_consumed")
    return {"http_model_roundtrip": "passed", "local_fixture_tool": "passed", "tool_result_consumed": True,
            "reported_model_matches_request": final.get("model") == model, "native_desktop_ui": "requires_target_host_acceptance"}


def chat_roundtrip(base, headers, model, transport=request_json):
    """Check a supplier/adapter without switching CC Switch's active provider."""
    challenge = "MIGRATION_" + secrets.token_hex(12)
    messages = [{"role": "user", "content": "Call " + TOOL + " once to read the prepared fixture. Then return exactly its content."}]
    tools = [{"type": "function", "function": {"name": TOOL, "description": "Read the prepared migration fixture; no arguments.",
              "parameters": {"type": "object", "properties": {}, "additionalProperties": False}}}]
    first = {"model": model, "messages": messages, "tools": tools, "tool_choice": "auto", "max_tokens": 2048, "stream": False}
    answer = transport(base + "/chat/completions", headers, first)
    choices = answer.get("choices", [])
    if not choices or not isinstance(choices[0].get("message"), dict):
        raise ProbeError("invalid_chat_response")
    message = choices[0]["message"]
    calls = message.get("tool_calls", [])
    if len(calls) != 1 or calls[0].get("function", {}).get("name") != TOOL or not calls[0].get("id"):
        raise ProbeError("expected_single_fixture_tool_call")
    try:
        arguments = json.loads(calls[0]["function"].get("arguments", ""))
    except (json.JSONDecodeError, TypeError):
        raise ProbeError("invalid_tool_arguments") from None
    if arguments != {}:
        raise ProbeError("unexpected_tool_arguments")
    with tempfile.TemporaryDirectory(prefix="model-migration-probe-") as scratch:
        fixture = Path(scratch) / "fixture.txt"
        fs_path(fixture).write_bytes(challenge.encode("utf-8"))
        actual = fs_path(fixture).read_text(encoding="utf-8")
    # Keep the complete assistant message, including provider reasoning fields.
    final = transport(base + "/chat/completions", headers, {**first, "tool_choice": "auto", "messages": messages + [message,
        {"role": "tool", "tool_call_id": calls[0]["id"], "content": actual}]})
    final_choices = final.get("choices", [])
    text = final_choices[0].get("message", {}).get("content", "") if final_choices else ""
    if challenge not in (text or ""):
        raise ProbeError("tool_result_not_consumed")
    return {"http_model_roundtrip": "passed", "local_fixture_tool": "passed", "tool_result_consumed": True,
            "reported_model_matches_request": final.get("model") == model, "native_claude_provider_switch": "not_performed"}


def check(target, config, models, smoke=False, environ=None, cc_switch_db=None, catalog=None, allow_remote=False, transport=request_json):
    environ = os.environ if environ is None else environ
    base = validate_url(config["base_url"], allow_remote)
    if target == "claude_code":
        if len(models) != 1:
            raise ProbeError("select_one_current_claude_provider_at_a_time")
        if cc_switch_db and current_claude_model(cc_switch_db) != models[0]:
            raise ProbeError("selected_cc_switch_provider_does_not_match_requested_model")
    headers = headers_for(config, environ)
    if target == "claude_code":
        headers["anthropic-version"] = "2023-06-01"
    catalog_ids = None
    if catalog:
        catalog_ids = {x.get("slug") for x in load_json(Path(catalog)).get("models", [])}
    discovered = None
    if target != "claude_code":
        listing = transport(base + "/models", headers)
        discovered = {x.get("id") for x in listing.get("data", [])}
    results = []
    for model in models:
        started = time.monotonic()
        result = {"requested_model": model, "catalog_visible": model in catalog_ids if catalog_ids is not None else None,
                  "gateway_discovered": model in discovered if discovered is not None else None}
        try:
            if catalog_ids is not None and model not in catalog_ids:
                raise ProbeError("model_missing_from_host_catalog")
            if discovered is not None and model not in discovered:
                raise ProbeError("model_missing_from_authenticated_gateway_list")
            if smoke:
                runner = anthropic_roundtrip if target == "claude_code" else (chat_roundtrip if target == "openai_chat_provider" else responses_roundtrip)
                result.update(runner(base, headers, model, transport))
            else:
                result["http_model_roundtrip"] = "not_run"
            result["status"] = "passed" if smoke else "discovery_only"
        except ProbeError as exc:
            result.update(status="failed", error=exc.code, http_status=exc.status)
        result["elapsed_seconds"] = round(time.monotonic() - started, 3)
        results.append(result)
    return {"target": target, "checks": results, "all_passed": all(x["status"] == "passed" for x in results),
            "changed_provider_or_host_settings": False, "credential_values_logged": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=PACKAGE / "model-setup/model-check.example.json")
    parser.add_argument("--target", choices=("codex_plus_plus", "claude_code", "openai_chat_provider"), required=True)
    parser.add_argument("--models", help="Exact comma-separated IDs; Claude accepts one selected provider at a time")
    parser.add_argument("--catalog", type=Path)
    parser.add_argument("--cc-switch-db", type=Path)
    parser.add_argument("--smoke", action="store_true", help="Make paid upstream requests and execute a bounded local fixture read")
    parser.add_argument("--allow-remote", action="store_true")
    args = parser.parse_args()
    config = load_json(args.config)[args.target]
    models = [x for x in (args.models.split(",") if args.models else config["models"]) if x]
    if not models:
        parser.error("at least one exact model ID is required")
    try:
        result = check(args.target, config, models, args.smoke, cc_switch_db=args.cc_switch_db,
                       catalog=args.catalog, allow_remote=args.allow_remote)
    except ProbeError as exc:
        result = {"target": args.target, "all_passed": False, "error": exc.code, "http_status": exc.status}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0 if result["all_passed"] else 2)


if __name__ == "__main__":
    main()
