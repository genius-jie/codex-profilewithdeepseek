#!/usr/bin/env python3
"""Healthy-path process checks for every currently registered Codex command hook.

This is deliberately a process-health check, not an allow-all policy test. Control
hooks have their allow/deny/block semantics covered by focused contract tests.
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path


HOOK_DIR = Path(__file__).resolve().parents[1]
CODEX_CONFIG = HOOK_DIR.parent / "hooks.json"


@dataclass(frozen=True)
class RegisteredCommand:
    event_name: str
    matcher: str
    command: str


def registered_commands() -> list[RegisteredCommand]:
    config = json.loads(CODEX_CONFIG.read_text(encoding="utf-8"))
    commands: list[RegisteredCommand] = []
    for event_name, entries in (config.get("hooks") or {}).items():
        for entry in entries or []:
            matcher = str(entry.get("matcher") or "")
            for hook in entry.get("hooks") or []:
                if hook.get("type") != "command":
                    continue
                command = str(hook.get("command") or "").strip()
                if not command:
                    raise AssertionError(f"{event_name} has an empty command hook")
                commands.append(RegisteredCommand(event_name, matcher, command))
    return commands


def healthy_event(command: RegisteredCommand, caller_cwd: str) -> dict:
    event: dict = {
        "turn_id": f"hook-health-{command.event_name}",
        "session_id": "hook-health-session",
        "cwd": caller_cwd,
        "source": "startup",
        "prompt": "ordinary healthy-path probe",
    }
    if command.event_name == "SessionStart":
        return event
    if command.event_name == "Stop":
        event["last_agent_message"] = (
            "WAIT_HUMAN_BLOCKER。"
            "STOP_COMPLETION_RECEIPT: "
            '{"status":"wait_human","blockers":["health probe"],"open_items":["wait"]}'
        )
        return event

    # The W11 trace command is intentionally invoked with a non-AskUserQuestion
    # event in this generic health suite: it must not create a real W11 trace.
    event.update(
        {
            "tool_name": "Bash",
            "tool_input": {"command": "Get-Location"},
            "tool_response": {"exit_code": 0, "output": "Exit code: 0"},
        }
    )
    return event


def run_registered_command(command: RegisteredCommand, event: dict, home: Path, cwd: Path) -> None:
    env = os.environ.copy()
    env["CODEX_HOME"] = str(home)
    env["PYTHONPATH"] = str(HOOK_DIR)
    # Runner must discard this inherited value and use the event's verified cwd.
    env["CODEX_HOOK_CALLER_CWD"] = r"C:\inherited-poison"
    proc = subprocess.run(
        command.command,
        input=json.dumps(event, ensure_ascii=False),
        text=True,
        capture_output=True,
        cwd=str(cwd),
        env=env,
        shell=True,
        timeout=30,
        check=False,
    )
    if proc.returncode != 0:
        raise AssertionError(
            f"{command.event_name}[{command.matcher or '<none>'}]: "
            f"returncode={proc.returncode}\nstdout={proc.stdout}\nstderr={proc.stderr}"
        )
    if "[HOOK:ERROR_DOWNGRADED]" in proc.stdout or "[HOOK:ERROR_DOWNGRADED]" in proc.stderr:
        raise AssertionError(
            f"{command.event_name}[{command.matcher or '<none>'}]: healthy path downgraded\n"
            f"stdout={proc.stdout}\nstderr={proc.stderr}"
        )
    output = proc.stdout.strip()
    if output:
        try:
            json.loads(output)
        except json.JSONDecodeError as exc:
            raise AssertionError(
                f"{command.event_name}[{command.matcher or '<none>'}]: stdout is not JSON: {output}"
            ) from exc


def main() -> int:
    commands = registered_commands()
    if not commands:
        raise AssertionError("hooks.json has no registered command hooks")

    events = {command.event_name for command in commands}
    required_events = {"SessionStart", "PreToolUse", "PermissionRequest", "PostToolUse", "Stop"}
    missing = sorted(required_events - events)
    if missing:
        raise AssertionError(f"hooks.json missing expected command events: {', '.join(missing)}")
    if "UserPromptSubmit" in events:
        raise AssertionError("retired UserPromptSubmit Context hook is still registered")

    post_tool_commands = [command for command in commands if command.event_name == "PostToolUse"]
    if len(post_tool_commands) < 2 or not any(
        command.matcher == "AskUserQuestion" for command in post_tool_commands
    ):
        raise AssertionError("PostToolUse must enumerate the secondary AskUserQuestion/W11 command")

    with tempfile.TemporaryDirectory(prefix="hook-healthy-home-") as home_raw:
        with tempfile.TemporaryDirectory(prefix="hook-healthy-cwd-") as cwd_raw:
            home = Path(home_raw)
            caller_cwd = Path(cwd_raw)
            for command in commands:
                run_registered_command(command, healthy_event(command, str(caller_cwd)), home, caller_cwd)
                print(f"{command.event_name}[{command.matcher or '<none>'}]: HEALTHY")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
