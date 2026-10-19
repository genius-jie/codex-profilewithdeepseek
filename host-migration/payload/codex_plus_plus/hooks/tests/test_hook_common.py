#!/usr/bin/env python3
"""Regression tests for shared hook failure classification."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


HOOK_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HOOK_DIR))

import hook_common  # noqa: E402
from hook_common import (  # noqa: E402
    REPO_ROOT,
    command_failed,
    command_may_modify_files,
    command_targets_governed_markdown,
    resolve_effective_cwd,
    within_openclaw,
)
from post_tool_use_audit import failure_review_evidence_recorded  # noqa: E402


def _assert_scope(
    event: dict,
    *,
    source: str,
    valid: bool,
    inside_openclaw: bool,
) -> dict:
    scope = resolve_effective_cwd(event)
    assert scope["source"] == source
    assert scope["valid"] is valid
    assert within_openclaw(event) is inside_openclaw
    return scope


def _with_caller_cwd(value: str | None, callback) -> None:
    key = "CODEX_HOOK_CALLER_CWD"
    previous = os.environ.get(key)
    try:
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value
        callback()
    finally:
        if previous is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = previous


def test_effective_cwd_uses_only_trusted_sources_and_canonical_containment() -> None:
    root = str(REPO_ROOT)
    outside = r"C:\\ctx03a-outside"

    def caller_env_precedence() -> None:
        scope = _assert_scope(
            {"cwd": outside},
            source="caller_env",
            valid=True,
            inside_openclaw=True,
        )
        assert scope["cwd"] == os.path.normcase(os.path.realpath(root))

    _with_caller_cwd(root, caller_env_precedence)

    def event_fallback() -> None:
        _assert_scope({"cwd": root + r"\projects\ctx03a"}, source="event_cwd", valid=True, inside_openclaw=True)
        _assert_scope(
            {"cwd": root.upper().rstrip("\\/") + "\\"},
            source="event_cwd",
            valid=True,
            inside_openclaw=True,
        )
        _assert_scope({"cwd": root + r"\..\ctx03a-outside"}, source="event_cwd", valid=True, inside_openclaw=False)
        _assert_scope({"cwd": root + "-x"}, source="event_cwd", valid=True, inside_openclaw=False)
        _assert_scope({"cwd": outside}, source="event_cwd", valid=True, inside_openclaw=False)
        _assert_scope({"cwd": r"\\server\share\ctx03a"}, source="event_cwd", valid=True, inside_openclaw=False)
        _assert_scope(
            {"cwd": root + r"\__ctx03a_nonexistent__"},
            source="event_cwd",
            valid=True,
            inside_openclaw=True,
        )

    _with_caller_cwd(None, event_fallback)

    def unknown_scope() -> None:
        original_cwd = os.getcwd()
        try:
            os.chdir(HOOK_DIR)
            _assert_scope({}, source="unknown", valid=False, inside_openclaw=False)
        finally:
            os.chdir(original_cwd)

    _with_caller_cwd(None, unknown_scope)


def test_effective_cwd_resolves_a_real_junction_before_containment() -> None:
    with tempfile.TemporaryDirectory(prefix="ctx03a-junction-") as raw:
        link = Path(raw) / "openclaw-link"
        proc = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(link), str(REPO_ROOT)],
            text=True,
            capture_output=True,
            timeout=20,
            check=False,
        )
        assert proc.returncode == 0, f"junction setup failed: stdout={proc.stdout} stderr={proc.stderr}"
        try:
            _with_caller_cwd(
                None,
                lambda: _assert_scope(
                    {"cwd": str(link)},
                    source="event_cwd",
                    valid=True,
                    inside_openclaw=True,
                ),
            )
        finally:
            if link.exists() or link.is_symlink():
                link.rmdir()


def test_routing_context_resolves_existing_active_assets() -> None:
    required = (
        "repo_w1",
        "global_w1",
        "agent_constitution",
        "m1",
        "w9",
        "w7",
        "s15",
        "hard_gate",
    )
    for key in required:
        path = Path(hook_common.ROUTING_CONTEXT[key])
        assert path.is_file(), f"{key} points to missing asset: {path}"


def assert_failed(name: str, event: dict, expected: bool) -> None:
    actual = command_failed(event)
    if actual != expected:
        raise AssertionError(f"{name}: expected {expected}, got {actual}")
    print(f"{name}: {'TRUE' if actual else 'FALSE'}")


def test_hook_evolution_observation_state_is_not_current_task_debt() -> None:
    old_state_dir = hook_common.STATE_DIR
    old_state_path = hook_common.STATE_PATH
    old_lock_path = hook_common.STATE_LOCK_PATH
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            hook_common.STATE_DIR = Path(temp_dir)
            hook_common.STATE_PATH = hook_common.STATE_DIR / "pending.json"
            hook_common.STATE_LOCK_PATH = hook_common.STATE_DIR / "pending.lock"

            anomaly = "PostToolUse ran 99 times in this turn; review tool batching if the UI feels noisy."
            promoted = hook_common.record_hook_evolution_candidates({"turn_id": "turn-1"}, "summary-1", [anomaly])
            state = json.loads(hook_common.STATE_PATH.read_text(encoding="utf-8"))
            item = next(iter(state["hook_evolution"]["candidates"].values()))
            assert promoted == []
            assert item["status"] == "observing"
            assert item["next_action"] == "none"

            hook_common.record_hook_evolution_candidates({"turn_id": "turn-2"}, "summary-2", [anomaly])
            promoted = hook_common.record_hook_evolution_candidates({"turn_id": "turn-3"}, "summary-3", [anomaly])
            state = json.loads(hook_common.STATE_PATH.read_text(encoding="utf-8"))
            item = next(iter(state["hook_evolution"]["candidates"].values()))
            assert promoted == [anomaly]
            assert item["status"] == "ready_for_m8_review"

            item["status"] = "recorded_closed"
            item["next_action"] = "none"
            hook_common.save_state(state)
            promoted = hook_common.record_hook_evolution_candidates({"turn_id": "turn-4"}, "summary-4", [anomaly])
            state = json.loads(hook_common.STATE_PATH.read_text(encoding="utf-8"))
            item = next(iter(state["hook_evolution"]["candidates"].values()))
            assert promoted == []
            assert item["status"] == "recorded_closed"
            assert item["next_action"] == "none"
    finally:
        hook_common.STATE_DIR = old_state_dir
        hook_common.STATE_PATH = old_state_path
        hook_common.STATE_LOCK_PATH = old_lock_path


def test_pending_view_is_scoped_to_the_current_session() -> None:
    pending = {
        "pending_failure_review@session:session-a": {
            "owner_scope": "session:session-a",
            "session_id": "session-a",
            "turn_id": "turn-a",
        },
        "pending_failure_review@session:session-b": {
            "owner_scope": "session:session-b",
            "session_id": "session-b",
            "turn_id": "turn-b",
        },
        "pending_s15": {"reason": "legacy unattributed item"},
    }
    session_a = hook_common.pending_items_for_event(
        pending,
        {"session_id": "session-a", "turn_id": "turn-a"},
    )
    assert list(session_a) == ["pending_failure_review@session:session-a"]
    assert hook_common.pending_item_for_event(
        pending,
        "pending_failure_review",
        {"session_id": "session-a", "turn_id": "turn-a"},
    ) is pending["pending_failure_review@session:session-a"]


def test_governed_markdown_read_with_unrelated_receipt_write_does_not_open_w9() -> None:
    governed_path = r"@@GENERAL_ROOT:win@@\assets\rules\execution.md"
    command = (
        "$p='@@OPENCLAW_ROOT:escaped@@\\projects\\tophub-daily-trend-radar\\ops\\evidence\\health.json'; "
        f"Get-Content -LiteralPath '{governed_path}' -Raw | Out-Null; "
        "[IO.File]::WriteAllText($p, '{}')"
    )
    governed = hook_common.extract_governed_md_mentions(command)
    assert command_may_modify_files("Bash", command) is True
    assert command_targets_governed_markdown("Bash", command, governed) is False


def test_direct_governed_markdown_writer_opens_w9() -> None:
    governed_path = r"@@GENERAL_ROOT:win@@\assets\rules\execution.md"
    command = f"Set-Content -LiteralPath '{governed_path}' -Value 'updated'"
    governed = hook_common.extract_governed_md_mentions(command)
    assert command_targets_governed_markdown("Bash", command, governed) is True


def test_unrelated_redirect_does_not_open_w9_but_governed_redirect_does() -> None:
    governed_path = r"@@GENERAL_ROOT:win@@\assets\rules\execution.md"
    unrelated = f"Get-Content '{governed_path}' -Raw *> '$env:TEMP\\receipt.txt'"
    direct = f"Get-Content 'input.txt' -Raw *> '{governed_path}'"
    assert command_targets_governed_markdown(
        "Bash", unrelated, hook_common.extract_governed_md_mentions(unrelated)
    ) is False
    assert command_targets_governed_markdown(
        "Bash", direct, hook_common.extract_governed_md_mentions(direct)
    ) is True


def main() -> int:
    read_only_search = "Select-String -Pattern 'pip install' -Path README.md"
    assert hook_common.is_pip_install_without_requirements(read_only_search) is False
    assert hook_common.is_pip_install_without_requirements("python -m pip install demo") is True
    assert hook_common.is_pip_install_with_requirements("python -m pip install -r requirements-dev.txt") is True

    assert_failed(
        "source_text_success",
        {
            "tool_input": {"command": "Get-Content -LiteralPath example.py"},
            "tool_response": "Process exited with code 0\nParserError: sample text in source\nfailure_reason = 'fixture'",
        },
        False,
    )
    assert_failed(
        "textual_nonzero",
        {
            "tool_input": {"command": "pwsh -Command bad"},
            "tool_response": "Process exited with code 1\nParserError: real parse failure",
        },
        True,
    )
    assert_failed(
        "source_text_embedded_nonzero",
        {
            "tool_input": {"command": "Get-Content -LiteralPath test_hook_common.py"},
            "tool_response": r'C:\hooks\tests\test_hook_common.py:36: "tool_response": "Process exited with code 1\nParserError: real parse failure"',
        },
        False,
    )
    assert_failed(
        "rg_no_match",
        {
            "tool_input": {"command": "rg -n missing C:\\tmp\\file.txt"},
            "tool_response": {"exit_code": 1, "stdout": "", "stderr": ""},
        },
        False,
    )
    assert_failed(
        "rg_real_error",
        {
            "tool_input": {"command": "rg -n missing C:\\tmp\\missing-dir"},
            "tool_response": {"exit_code": 1, "stdout": "", "stderr": "No such file or directory"},
        },
        True,
    )
    assert_failed(
        "sql_missing_column",
        {
            "tool_input": {"command": "node D:\\Temp\\query.cjs"},
            "tool_response": "error: column r.reason_code does not exist",
        },
        True,
    )
    item = {
        "command_fingerprint": "broken-query-command",
        "command_fingerprint_key": "broken-query-command",
    }
    assert failure_review_evidence_recorded(
        item,
        "broken-query-command; Write-Output 'S12=PASS'",
        "error: column r.reason_code does not exist",
    ) is False
    assert failure_review_evidence_recorded(
        item,
        "broken-query-command",
        "S12=PASS; corrected_command_exit_code=0; fingerprint=broken-query-command",
    ) is True
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
