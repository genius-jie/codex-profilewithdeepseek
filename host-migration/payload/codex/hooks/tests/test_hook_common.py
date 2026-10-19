#!/usr/bin/env python3
"""Regression tests for shared hook classification and Context scope resolution."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


HOOK_DIR = Path(__file__).resolve().parents[1]
SESSION_START = HOOK_DIR / "session_start_context.py"
sys.path.insert(0, str(HOOK_DIR))

from hook_common import (
    REPO_ROOT,
    command_failed,
    is_pip_install_without_requirements,
    resolve_effective_cwd,
    within_openclaw,
)  # noqa: E402


def assert_failed(name: str, event: dict, expected: bool) -> None:
    actual = command_failed(event)
    if actual != expected:
        raise AssertionError(f"{name}: expected {expected}, got {actual}")
    print(f"{name}: {'TRUE' if actual else 'FALSE'}")


def assert_scope(name: str, event: dict, *, source: str, valid: bool, inside_openclaw: bool) -> dict:
    scope = resolve_effective_cwd(event)
    actual = within_openclaw(event)
    if scope.get("source") != source or scope.get("valid") is not valid:
        raise AssertionError(f"{name}: unexpected scope {scope}")
    if actual != inside_openclaw:
        raise AssertionError(f"{name}: expected inside_openclaw={inside_openclaw}, got {actual}: {scope}")
    print(f"{name}: {scope}")
    return scope


def with_caller_env(value: str | None, callback) -> None:
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


def assert_junction_resolves_inside_openclaw() -> None:
    """Exercise realpath on a real temporary Windows junction, not a string prefix."""
    target = Path(REPO_ROOT)
    with tempfile.TemporaryDirectory(prefix="ctx02-junction-") as raw:
        link = Path(raw) / "openclaw-link"
        proc = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(link), str(target)],
            text=True,
            capture_output=True,
            timeout=20,
            check=False,
        )
        if proc.returncode != 0:
            raise AssertionError(f"junction setup failed: stdout={proc.stdout} stderr={proc.stderr}")
        try:
            assert_scope(
                "junction_inside_openclaw",
                {"cwd": str(link)},
                source="event_cwd",
                valid=True,
                inside_openclaw=True,
            )
        finally:
            if link.exists() or link.is_symlink():
                link.rmdir()


def assert_session_start_projects_configured_model_instructions() -> None:
    """Configured model instructions must appear as a mechanical Host L0 source."""
    with tempfile.TemporaryDirectory(prefix="ctx05-session-start-") as raw:
        home = Path(raw)
        host_agents = home / "AGENTS.md"
        model_instructions = home / "model-instructions.md"
        host_agents.write_text("host baseline\n", encoding="utf-8")
        model_instructions.write_text("model baseline\n", encoding="utf-8")
        (home / "config.toml").write_text(
            'model_instructions_file = "./model-instructions.md"\n',
            encoding="utf-8",
        )
        env = os.environ.copy()
        env["CODEX_HOME"] = str(home)
        env["PYTHONPATH"] = str(HOOK_DIR)
        env.pop("CODEX_HOOK_CALLER_CWD", None)
        proc = subprocess.run(
            [sys.executable, str(SESSION_START)],
            input=json.dumps({"cwd": r"C:\\ctx05-session-start"}),
            text=True,
            capture_output=True,
            cwd=str(HOOK_DIR),
            env=env,
            timeout=20,
            check=False,
        )
        if proc.returncode != 0:
            raise AssertionError(f"session_start L0 probe failed: stderr={proc.stderr}")
        payload = json.loads(proc.stdout)
        message = payload["hookSpecificOutput"]["additionalContext"]
        if not message.startswith("[HOST_SCOPE_FACT]\n"):
            raise AssertionError(f"session_start did not emit HOST_SCOPE_FACT: {message}")
        fact = json.loads(message.split("\n", 1)[1])
        expected_refs = {
            "host_agents": str(host_agents.resolve()),
            "model_instructions_file": str(model_instructions.resolve()),
        }
        if fact.get("l0_source_refs") != expected_refs:
            raise AssertionError(f"unexpected L0 source refs: {fact.get('l0_source_refs')}")
        if fact.get("l0_binding_fact", {}).get("model_instructions_file") != "config.toml#model_instructions_file":
            raise AssertionError(f"missing model instruction binding: {fact.get('l0_binding_fact')}")
        model_fact = fact.get("model_instructions_file") or {}
        if not model_fact.get("configured") or not model_fact.get("present"):
            raise AssertionError(f"configured model instructions were not projected: {model_fact}")
        if fact.get("load_order") != "not_observable" or fact.get("hook_selection_authority") is not False:
            raise AssertionError(f"SessionStart exceeded its mechanical boundary: {fact}")
        print("session_start_projects_configured_model_instructions: PASS")


def main() -> int:
    pip_cases = {
        "direct_pip": ("pip install requests", True),
        "python_module_pip": ("python -m pip install requests", True),
        "requirements_short": ("pip install -r requirements.txt", False),
        "requirements_long": ("pip install --requirement requirements.txt", False),
        "requirements_equals": ("pip install --requirement=requirements.txt", False),
        "quoted_fixture": ('Write-Output "pip install requests"', False),
        "python_fixture": ("python -c \"print('pip install requests')\"", False),
        "chained_command": ("echo ready; pip install requests", True),
    }
    for name, (command, expected) in pip_cases.items():
        actual = is_pip_install_without_requirements(command)
        if actual != expected:
            raise AssertionError(f"{name}: expected {expected}, got {actual}")
    print("pip_install_boundary_cases: PASS")

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

    root = str(REPO_ROOT)
    outside = r"C:\ctx02-other-drive"

    def caller_env_precedence() -> None:
        scope = assert_scope(
            "caller_env_precedence",
            {"cwd": outside},
            source="caller_env",
            valid=True,
            inside_openclaw=True,
        )
        if scope["cwd"] != os.path.normcase(os.path.realpath(root)):
            raise AssertionError(f"caller_env_precedence: unexpected canonical cwd {scope}")

    with_caller_env(root, caller_env_precedence)

    def event_fallback() -> None:
        assert_scope(
            "event_cwd_openclaw_subdir",
            {"cwd": root + r"\projects\ctx02"},
            source="event_cwd",
            valid=True,
            inside_openclaw=True,
        )
        assert_scope(
            "event_cwd_case_and_trailing_separator",
            {"cwd": root.upper().rstrip("\\/") + "\\"},
            source="event_cwd",
            valid=True,
            inside_openclaw=True,
        )
        assert_scope(
            "event_cwd_parent_escape",
            {"cwd": root + r"\..\ctx02-outside"},
            source="event_cwd",
            valid=True,
            inside_openclaw=False,
        )
        assert_scope(
            "event_cwd_prefix_collision",
            {"cwd": root + "-x"},
            source="event_cwd",
            valid=True,
            inside_openclaw=False,
        )
        assert_scope(
            "event_cwd_different_drive",
            {"cwd": outside},
            source="event_cwd",
            valid=True,
            inside_openclaw=False,
        )
        assert_scope(
            "event_cwd_unc",
            {"cwd": r"\\server\share\ctx02"},
            source="event_cwd",
            valid=True,
            inside_openclaw=False,
        )
        assert_scope(
            "event_cwd_nonexistent_inside_root",
            {"cwd": root + r"\__ctx02_nonexistent__"},
            source="event_cwd",
            valid=True,
            inside_openclaw=True,
        )

    with_caller_env(None, event_fallback)

    def unknown_scope() -> None:
        original_cwd = os.getcwd()
        try:
            os.chdir(HOOK_DIR)
            assert_scope("unknown_never_uses_child_cwd", {}, source="unknown", valid=False, inside_openclaw=False)
        finally:
            os.chdir(original_cwd)

    with_caller_env(None, unknown_scope)
    with_caller_env(None, assert_junction_resolves_inside_openclaw)
    assert_session_start_projects_configured_model_instructions()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
