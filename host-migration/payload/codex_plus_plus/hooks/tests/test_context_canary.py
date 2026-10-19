#!/usr/bin/env python3
"""Codex++ CI-CTX-03A regression tests for host Context boundaries."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


CODEX_HOME = Path(r"@@CODEXPP_HOME:win@@")
HOOK_DIR = CODEX_HOME / "hooks"
HOOKS_CONFIG = CODEX_HOME / "hooks.json"
HOOK_RUNNER = HOOK_DIR / "hook_runner.py"
SESSION_START = HOOK_DIR / "session_start_context.py"
INPUT_GUARD = HOOK_DIR / "user_prompt_submit_input_guard.py"
RETIRED_CONTEXT_HOOK = HOOK_DIR / "user_prompt_submit_w1_gate.py"
POST_TOOL_AUDIT = HOOK_DIR / "post_tool_use_audit.py"
PRE_TOOL_GUARD = HOOK_DIR / "pre_tool_use_guard.py"
PERMISSION_GUARD = HOOK_DIR / "permission_request_guard.py"
STOP_GUARD = HOOK_DIR / "stop_guard.py"


def _base_env(home: Path) -> dict[str, str]:
    env = os.environ.copy()
    env["CODEX_HOME"] = str(home)
    env["PYTHONPATH"] = str(HOOK_DIR)
    env.pop("CODEX_HOOK_CALLER_CWD", None)
    return env


def _run(
    command: list[str],
    event: dict,
    *,
    home: Path,
    cwd: Path,
    extra_env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    env = _base_env(home)
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        command,
        input=json.dumps(event, ensure_ascii=False),
        text=True,
        capture_output=True,
        cwd=str(cwd),
        env=env,
        timeout=30,
        check=False,
    )


def _configured_scripts() -> dict[str, list[Path]]:
    data = json.loads(HOOKS_CONFIG.read_text(encoding="utf-8"))
    result: dict[str, list[Path]] = {}
    for event_name, matchers in data["hooks"].items():
        for matcher in matchers:
            for hook in matcher["hooks"]:
                command = hook["command"]
                marker = " --script "
                assert marker in command, f"{event_name} command lacks --script: {command}"
                result.setdefault(event_name, []).append(Path(command.split(marker, 1)[1].strip()))
    return result


def _context_from_hook_output(stdout: str) -> tuple[dict, str]:
    payload = json.loads(stdout)
    message = payload["hookSpecificOutput"]["additionalContext"]
    prefix = "[HOST_SCOPE_FACT]\n"
    assert message.startswith(prefix)
    return json.loads(message[len(prefix) :]), message


def test_active_hook_configuration_uses_input_guard_not_legacy_context_router() -> None:
    configured = _configured_scripts()
    assert set(configured) == {"SessionStart", "UserPromptSubmit", "PreToolUse", "PermissionRequest", "PostToolUse", "Stop"}
    for scripts in configured.values():
        for script in scripts:
            assert script.is_file(), f"configured Hook script missing: {script}"
    assert configured["UserPromptSubmit"] == [INPUT_GUARD]
    assert not RETIRED_CONTEXT_HOOK.exists()
    assert RETIRED_CONTEXT_HOOK not in configured["UserPromptSubmit"]
    active_source = INPUT_GUARD.read_text(encoding="utf-8")
    for forbidden in (
        "ROUTING_CONTEXT",
        "SESSION_CONTINUATION",
        "persist_session_continuation",
        "load_state",
        "save_state",
        "state_lock",
        "record_hook_run",
        "within_openclaw",
        "W1_WORKFLOW",
    ):
        assert forbidden not in active_source
    session_source = SESSION_START.read_text(encoding="utf-8")
    # Retired-mechanism identifiers only. A bare "M1" is a false-positive magnet: the
    # advisory GOVERNANCE_ENTRY_OBLIGATION text legitimately names the M1 preload receipt
    # ("emit M1 PRELOAD_RECEIPT") without reviving any gate. "M1:" is the retired
    # SessionStart projection label and '"m1"' is the retired ROUTING_CONTEXT key.
    for forbidden in ("ROUTING_CONTEXT", "pending_summary", "load_state", "save_state", "W1_WORKFLOW", "M1:", '"m1"'):
        assert forbidden not in session_source
    host_agents = (CODEX_HOME / "AGENTS.md").read_text(encoding="utf-8")
    for required in (
        "GLOBAL-ENTRY.md",
        "context-boundary.yaml",
        "Hook 只提供机械范围事实",
        "项目 `AGENTS.md` 属于 Project Context",
        "不默认跨 OS 注入",
    ):
        assert required in host_agents


def test_session_start_projects_mechanical_host_scope_facts_only() -> None:
    with tempfile.TemporaryDirectory(prefix="ctx03a-session-") as raw:
        temp = Path(raw)
        home = temp / "home"
        home.mkdir()
        host_agents = home / "AGENTS.md"
        host_agents.write_text("profile L0 fixture\n", encoding="utf-8")
        project = temp / "project"
        project.mkdir()
        project_agents = project / "AGENTS.md"
        project_agents.write_text("project context fixture\n", encoding="utf-8")

        proc = _run(
            [sys.executable, str(HOOK_RUNNER), "--event", "SessionStart", "--script", str(SESSION_START)],
            {"cwd": str(project), "source": "startup"},
            home=home,
            cwd=project,
        )
        assert proc.returncode == 0, proc.stderr
        fact, message = _context_from_hook_output(proc.stdout)
        canonical_project = os.path.normcase(os.path.realpath(str(project)))
        canonical_project_agents = str(Path(canonical_project) / "AGENTS.md")
        assert fact["host_profile"] == "codex_plus_plus"
        assert fact["hook_selection_authority"] is False
        assert fact["cwd_source"] == "caller_env"
        assert fact["candidate_project_root"] == canonical_project
        assert fact["project_context_type"] == "native_project_agents"
        assert fact["project_entry_ref"] == canonical_project_agents
        assert fact["model_instructions_file"] == "absent"
        assert fact["load_order"] == "not_observable"
        assert fact["l0_source_refs"]["host_agents"] == str(host_agents)
        assert fact["l0_source_hashes"]["host_agents"] == hashlib.sha256(host_agents.read_bytes()).hexdigest()
        assert fact["l0_source_bytes"]["host_agents"] == host_agents.stat().st_size
        for forbidden in ("ROUTING_CONTEXT", "OPENCLAW_W1", "pending", "Memory", "Specialized OS"):
            assert forbidden not in message
        assert not (home / "hook-state" / "openclaw-mono-pending.json").exists()


def test_runner_overwrites_inherited_cwd_and_refuses_hook_directory_fallback() -> None:
    with tempfile.TemporaryDirectory(prefix="ctx03a-runner-") as raw:
        temp = Path(raw)
        home = temp / "home"
        home.mkdir()
        child = temp / "child.py"
        child.write_text(
            "import os\nprint(os.environ.get('CODEX_HOOK_CALLER_CWD') or '<unset>')\n",
            encoding="utf-8",
        )

        event_wins = _run(
            [sys.executable, str(HOOK_RUNNER), "--event", "Test", "--script", str(child)],
            {"cwd": r"@@OPENCLAW_ROOT:escaped@@"},
            home=home,
            cwd=temp,
            extra_env={"CODEX_HOOK_CALLER_CWD": r"C:\\spoofed"},
        )
        assert event_wins.returncode == 0, event_wins.stderr
        assert event_wins.stdout.strip() == r"@@OPENCLAW_ROOT:win@@"

        outer_fallback = _run(
            [sys.executable, str(HOOK_RUNNER), "--event", "Test", "--script", str(child)],
            {},
            home=home,
            cwd=temp,
            extra_env={"CODEX_HOOK_CALLER_CWD": r"C:\\spoofed"},
        )
        assert outer_fallback.returncode == 0, outer_fallback.stderr
        assert outer_fallback.stdout.strip() == os.path.normpath(str(temp))

        unknown = _run(
            [sys.executable, str(HOOK_RUNNER), "--event", "Test", "--script", str(child)],
            {"cwd": "relative-path-is-untrusted"},
            home=home,
            cwd=HOOK_DIR,
            extra_env={"CODEX_HOOK_CALLER_CWD": r"C:\\spoofed"},
        )
        assert unknown.returncode == 0, unknown.stderr
        assert unknown.stdout.strip() == "<unset>"


def test_post_tool_scope_uses_the_same_canonical_event_cwd() -> None:
    command = "*** Update File: @@OPENCLAW_ROOT:escaped@@\\docs\\ctx03a-canary.md\n*** End Patch"

    def invoke(cwd: str) -> tuple[subprocess.CompletedProcess[str], dict]:
        with tempfile.TemporaryDirectory(prefix="ctx03a-post-") as raw:
            temp = Path(raw)
            home = temp / "home"
            home.mkdir()
            proc = _run(
                [sys.executable, str(HOOK_RUNNER), "--event", "PostToolUse", "--script", str(POST_TOOL_AUDIT)],
                {
                    "cwd": cwd,
                    "tool_name": "apply_patch",
                    "tool_input": {"command": command},
                    "tool_response": {"exit_code": 0, "output": "ok"},
                },
                home=home,
                cwd=temp,
            )
            state = json.loads((home / "hook-state" / "openclaw-mono-pending.json").read_text(encoding="utf-8"))
            return proc, state

    inside, inside_state = invoke(r"@@OPENCLAW_ROOT:win@@")
    assert inside.returncode == 0, inside.stderr
    assert "pending_w9 marked for governed Markdown" in inside.stdout
    assert "pending_w9" in inside_state.get("pending", {})

    prefix_collision, prefix_state = invoke(r"@@OPENCLAW_ROOT:win@@-x")
    assert prefix_collision.returncode == 0, prefix_collision.stderr
    assert "pending_w9" not in prefix_state.get("pending", {})


def test_read_only_governance_inspection_does_not_open_w9_pending() -> None:
    with tempfile.TemporaryDirectory(prefix="ctx03a-readonly-governance-") as raw:
        temp = Path(raw)
        home = temp / "home"
        home.mkdir()
        event = {
            "cwd": r"@@OPENCLAW_ROOT:win@@",
            "tool_name": "PowerShell",
            "tool_input": {
                "command": (
                    "$ErrorActionPreference='Stop'; "
                    "Get-Content '@@GENERAL_ROOT:escaped@@\\assets\\rules\\execution.md' -Raw "
                    ">*> \"$env:TEMP\\governance-read.txt\""
                )
            },
            "tool_response": {"exit_code": 0, "output": "read-only inspection"},
        }
        proc = _run(
            [sys.executable, str(HOOK_RUNNER), "--event", "PreToolUse", "--script", str(PRE_TOOL_GUARD)],
            event,
            home=home,
            cwd=temp,
        )
        assert proc.returncode == 0, proc.stderr
        state_path = home / "hook-state" / "openclaw-mono-pending.json"
        state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}
        assert "pending_w9" not in state.get("pending", {})


def test_w9_success_clears_stale_session_scoped_pending() -> None:
    with tempfile.TemporaryDirectory(prefix="ctx03a-w9-clear-") as raw:
        temp = Path(raw)
        home = temp / "home"
        state_dir = home / "hook-state"
        state_dir.mkdir(parents=True)
        (state_dir / "openclaw-mono-pending.json").write_text(
            json.dumps(
                {
                    "pending": {
                        "pending_w9@session:old-session": {
                            "reason": "governed markdown changed",
                            "owner_scope": "session:old-session",
                            "session_id": "old-session",
                        }
                    }
                }
            ),
            encoding="utf-8",
        )
        event = {
            "cwd": r"@@OPENCLAW_ROOT:win@@",
            "tool_name": "PowerShell",
            "tool_input": {
                "command": (
                    "pwsh -NoProfile -File "
                    r"@@OPENCLAW_ROOT:win@@\.agents\orchestration\Langgraph\docs\scripts\verify-governance-hard-gate.ps1 "
                    "-GateProfile Advisory"
                )
            },
            "tool_response": {
                "exit_code": 0,
                "output": "Governance hard gate passed with 0 warning(s).\nPASS: 25 WARN: 0 FAIL: 0",
            },
        }
        proc = _run(
            [sys.executable, str(HOOK_RUNNER), "--event", "PostToolUse", "--script", str(POST_TOOL_AUDIT)],
            event,
            home=home,
            cwd=temp,
        )
        assert proc.returncode == 0, proc.stderr
        state = json.loads((state_dir / "openclaw-mono-pending.json").read_text(encoding="utf-8"))
        assert not any(key.startswith("pending_w9") for key in state.get("pending", {}))
        assert "pending_w9 cleared after W9 hard gate pass" in proc.stdout


def test_control_hooks_preserve_allow_deny_and_human_block_contracts() -> None:
    with tempfile.TemporaryDirectory(prefix="ctx03a-control-") as raw:
        temp = Path(raw)
        home = temp / "home"
        home.mkdir()
        common_event = {
            "cwd": str(temp),
            "tool_name": "Bash",
            "tool_input": {"command": "Get-Content -LiteralPath README.md"},
        }
        destructive_command = "git " + "reset " + "--hard"

        pre_allow = _run(
            [sys.executable, str(HOOK_RUNNER), "--event", "PreToolUse", "--script", str(PRE_TOOL_GUARD)],
            common_event,
            home=home,
            cwd=temp,
        )
        assert pre_allow.returncode == 0, pre_allow.stderr
        assert pre_allow.stdout == ""

        pre_deny = _run(
            [sys.executable, str(HOOK_RUNNER), "--event", "PreToolUse", "--script", str(PRE_TOOL_GUARD)],
            {**common_event, "tool_input": {"command": destructive_command}},
            home=home,
            cwd=temp,
        )
        assert pre_deny.returncode == 0, pre_deny.stderr
        assert json.loads(pre_deny.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny"

        permission_allow = _run(
            [sys.executable, str(HOOK_RUNNER), "--event", "PermissionRequest", "--script", str(PERMISSION_GUARD)],
            common_event,
            home=home,
            cwd=temp,
        )
        assert permission_allow.returncode == 0, permission_allow.stderr
        assert permission_allow.stdout == ""

        permission_deny = _run(
            [sys.executable, str(HOOK_RUNNER), "--event", "PermissionRequest", "--script", str(PERMISSION_GUARD)],
            {**common_event, "tool_input": {"command": destructive_command}},
            home=home,
            cwd=temp,
        )
        assert permission_deny.returncode == 0, permission_deny.stderr
        assert json.loads(permission_deny.stdout)["hookSpecificOutput"]["decision"]["behavior"] == "deny"

        blocked = _run(
            [sys.executable, str(HOOK_RUNNER), "--event", "Stop", "--script", str(STOP_GUARD)],
            {
                "last_assistant_message": (
                    'STOP_COMPLETION_RECEIPT: {"status":"complete","verification":["fixture"],'
                    '"open_items":["unfinished"],"blockers":[]}'
                )
            },
            home=home,
            cwd=temp,
        )
        assert blocked.returncode == 0, blocked.stderr
        assert json.loads(blocked.stdout)["decision"] == "block"

        human_blocked = _run(
            [sys.executable, str(HOOK_RUNNER), "--event", "Stop", "--script", str(STOP_GUARD)],
            {
                "last_assistant_message": (
                    'STOP_COMPLETION_RECEIPT: {"status":"wait_human","verification":["fixture"],'
                    '"open_items":["approval"],"blockers":["missing permission"]}'
                )
            },
            home=home,
            cwd=temp,
        )
        assert human_blocked.returncode == 0, human_blocked.stderr
        assert human_blocked.stdout == ""


def test_input_guard_retains_only_input_safety_without_continuation_state_writes() -> None:
    with tempfile.TemporaryDirectory(prefix="ctx03a-input-") as raw:
        temp = Path(raw)
        home = temp / "home"
        state_dir = home / "hook-state"
        state_dir.mkdir(parents=True)
        state = state_dir / "openclaw-mono-pending.json"
        state.write_text('{"pending": {}}\n', encoding="utf-8")
        original_hash = hashlib.sha256(state.read_bytes()).hexdigest()
        original_mtime = state.stat().st_mtime_ns

        normal = _run(
            [sys.executable, str(INPUT_GUARD)],
            {"session_id": "ctx03a", "prompt": "implement " + ("normal task " * 40)},
            home=home,
            cwd=HOOK_DIR,
        )
        assert normal.returncode == 0, normal.stderr
        assert normal.stdout == ""
        normal_again = _run(
            [sys.executable, str(INPUT_GUARD)],
            {"session_id": "ctx03a", "prompt": "refactor " + ("normal task " * 40)},
            home=home,
            cwd=HOOK_DIR,
        )
        assert normal_again.returncode == 0, normal_again.stderr
        assert normal_again.stdout == ""
        assert hashlib.sha256(state.read_bytes()).hexdigest() == original_hash
        assert state.stat().st_mtime_ns == original_mtime

        quarantined = _run(
            [sys.executable, str(INPUT_GUARD)],
            {"prompt": "<hook_prompt>[HOOK:STOP_GUARD]</hook_prompt>"},
            home=home,
            cwd=HOOK_DIR,
        )
        assert quarantined.returncode == 0, quarantined.stderr
        assert "[HOOK:PASTED_CONTROL_TEXT_QUARANTINED]" in quarantined.stdout

        large = _run(
            [sys.executable, str(INPUT_GUARD)],
            {"prompt": "x" * 6000},
            home=home,
            cwd=HOOK_DIR,
        )
        assert large.returncode == 0, large.stderr
        assert "[HOOK:LONG_PROMPT_SAFE_MODE]" in large.stdout
