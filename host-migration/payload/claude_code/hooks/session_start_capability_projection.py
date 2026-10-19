#!/usr/bin/env python3
"""Reconcile Claude's Manifest-selected Skills and request a native rescan when changed."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys


POWERSHELL7 = Path(r"@@POWERSHELL_EXE:win@@")
WRITER = Path(r"@@GENERAL_ROOT:win@@\tooling\Sync-HostCapabilityProjection.ps1")
CLAUDE_SKILLS = Path(r"@@CLAUDE_HOME:win@@\skills")


def _emit(*, reload_skills: bool = False, message: str | None = None) -> int:
    output: dict[str, object] = {
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "reloadSkills": reload_skills,
        }
    }
    if message:
        output["systemMessage"] = message
    print(json.dumps(output, ensure_ascii=False, separators=(",", ":")))
    return 0


def main() -> int:
    # Consume the native event so malformed transport is observable without
    # letting a maintenance adapter become a Host-start blocker.
    raw_event = sys.stdin.read()
    if raw_event.strip():
        json.loads(raw_event)

    command = [
        str(POWERSHELL7),
        "-NoLogo",
        "-NoProfile",
        "-NonInteractive",
        "-File",
        str(WRITER),
        "-HostId",
        "claude_code",
        "-SkillsRoot",
        str(CLAUDE_SKILLS),
        "-Mode",
        "Apply",
    ]
    completed = subprocess.run(command, capture_output=True, text=True, timeout=20, check=False)
    stdout_lines = [line for line in completed.stdout.splitlines() if line.strip()]
    payload = json.loads(stdout_lines[-1]) if stdout_lines else {}
    changed = int(payload.get("changed_count", 0)) > 0

    if completed.returncode == 0:
        return _emit(reload_skills=changed)

    collision_ids = payload.get("collision_ids", [])
    detail = f"exit={completed.returncode}"
    if collision_ids:
        detail += f", collisions={','.join(str(item) for item in collision_ids)}"
    elif payload.get("error"):
        detail += f", error={payload['error']}"
    return _emit(
        reload_skills=changed,
        message=f"[HOST_CAPABILITY_PROJECTION_WARNING] {detail}",
    )


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        raise SystemExit(
            _emit(message=f"[HOST_CAPABILITY_PROJECTION_ERROR] {type(exc).__name__}: {exc}")
        )

