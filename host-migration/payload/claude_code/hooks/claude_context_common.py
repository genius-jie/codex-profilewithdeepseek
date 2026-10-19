#!/usr/bin/env python3
"""Small, mechanical context helpers for the Claude Code host adapter.

This module deliberately does not select an OS, read prompt packets, or load
memory.  It only normalizes trusted scope inputs and describes local entry
points for the SessionStart projection.
"""

from __future__ import annotations

import json
import ntpath
import os
from pathlib import Path
from typing import Any


HOOK_DIR = Path(__file__).resolve().parent
CALLER_CWD_ENV = "CODEX_HOOK_CALLER_CWD"
OPENCLAW_ROOT = r"@@OPENCLAW_ROOT:win@@"
GLOBAL_AGENT_ROOT = Path(r"@@GENERAL_ROOT:win@@")
GLOBAL_ENTRY = GLOBAL_AGENT_ROOT / "GLOBAL-ENTRY.md"
GENERAL_CONSTITUTION = GLOBAL_AGENT_ROOT / "CONSTITUTION.md"
PROJECT_SENTINELS = ("CLAUDE.md", "AGENTS.md", ".git", ".claude", ".agents", ".agent")
MAX_PROJECT_ANCESTORS = 16


def normalize_absolute_path(value: Any) -> str | None:
    """Return a normalized absolute Windows path, or ``None`` if untrusted."""

    if not isinstance(value, str):
        return None
    candidate = value.strip()
    if not candidate or "\x00" in candidate or not ntpath.isabs(candidate):
        return None
    drive, tail = ntpath.splitdrive(candidate)
    # Reject drive-relative values such as ``D:folder``.  UNC paths have a
    # non-empty drive/share and an absolute tail, so they remain supported.
    if not drive or not tail.startswith(("\\", "/")):
        return None
    try:
        resolved = os.path.realpath(candidate)
        normalized = os.path.normpath(resolved)
    except (OSError, ValueError):
        return None
    if not ntpath.isabs(normalized):
        # This fallback only helps test/portable runtimes; it never makes a
        # relative value valid.
        normalized = ntpath.normpath(candidate)
    return normalized if ntpath.isabs(normalized) else None


def canonical_path(value: Any) -> str | None:
    """Canonicalize a path for containment checks (realpath + normcase)."""

    normalized = normalize_absolute_path(value)
    if normalized is None:
        return None
    try:
        return ntpath.normcase(ntpath.normpath(os.path.realpath(normalized)))
    except (OSError, ValueError):
        return None


def is_within(candidate: Any, root: Any) -> bool:
    """Return true only when canonical ``candidate`` is inside ``root``."""

    candidate_canonical = canonical_path(candidate)
    root_canonical = canonical_path(root)
    if candidate_canonical is None or root_canonical is None:
        return False
    try:
        return ntpath.commonpath([candidate_canonical, root_canonical]) == root_canonical
    except (OSError, ValueError):
        # ValueError covers different drive letters and malformed UNC paths.
        return False


def is_within_hook_dir(path: Any) -> bool:
    return is_within(path, str(HOOK_DIR))


def parse_event(raw_event: str) -> dict[str, Any]:
    try:
        parsed = json.loads(raw_event)
    except (TypeError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def read_event() -> dict[str, Any]:
    """Read one hook event without treating malformed input as scope."""

    import sys

    return parse_event(sys.stdin.read())


def trusted_runner_cwd(raw_event: str, runner_cwd: str) -> tuple[str | None, str]:
    """Choose a caller cwd before the child is moved into ``HOOK_DIR``.

    Inherited ``CODEX_HOOK_CALLER_CWD`` is intentionally ignored here.  The
    runner is the only writer of that variable for its child process.
    """

    event = parse_event(raw_event)
    event_cwd = normalize_absolute_path(event.get("cwd"))
    if event_cwd and not is_within_hook_dir(event_cwd):
        return event_cwd, "event_cwd"

    outer_cwd = normalize_absolute_path(runner_cwd)
    if outer_cwd and not is_within_hook_dir(outer_cwd):
        return outer_cwd, "runner_cwd"
    return None, "unknown"


def resolve_effective_cwd(event: dict[str, Any] | None) -> dict[str, Any]:
    """Resolve scope from runner-written env, then a valid event cwd.

    The child process's own ``os.getcwd()`` is never a fallback because the
    runner deliberately starts children in the hooks directory.
    """

    event = event if isinstance(event, dict) else {}
    env_cwd = normalize_absolute_path(os.environ.get(CALLER_CWD_ENV))
    if env_cwd and not is_within_hook_dir(env_cwd):
        return {"cwd": env_cwd, "source": "caller_env", "valid": True}

    event_cwd = normalize_absolute_path(event.get("cwd"))
    if event_cwd and not is_within_hook_dir(event_cwd):
        return {"cwd": event_cwd, "source": "event_cwd", "valid": True}

    return {"cwd": None, "source": "unknown", "valid": False}


def within_openclaw(event_or_path: dict[str, Any] | str | None) -> bool:
    if isinstance(event_or_path, dict):
        scope = resolve_effective_cwd(event_or_path)
        path = scope.get("cwd")
    else:
        path = event_or_path
    return bool(path and is_within(path, OPENCLAW_ROOT))


def project_candidate(cwd: str | None) -> dict[str, Any]:
    """Find a bounded project candidate using sentinel files only."""

    if not cwd:
        return {"root": None, "sentinels": [], "entry_refs": []}
    try:
        node = Path(cwd)
        if node.is_file():
            node = node.parent
    except (OSError, ValueError):
        return {"root": None, "sentinels": [], "entry_refs": []}

    for _ in range(MAX_PROJECT_ANCESTORS):
        detected = [name for name in PROJECT_SENTINELS if (node / name).exists()]
        if detected:
            entry_refs = [
                str(node / name)
                for name in ("CLAUDE.md", "AGENTS.md")
                if (node / name).is_file()
            ]
            return {"root": str(node), "sentinels": detected, "entry_refs": entry_refs}
        if node.parent == node:
            break
        node = node.parent
    return {"root": None, "sentinels": [], "entry_refs": []}


def file_fact(path: Path) -> dict[str, Any]:
    """Describe a source without interpreting or returning its body."""

    import hashlib

    fact: dict[str, Any] = {"source_ref": str(path)}
    try:
        content = path.read_bytes()
        fact.update(
            {
                "present": True,
                "sha256": hashlib.sha256(content).hexdigest(),
                "bytes": len(content),
            }
        )
    except (OSError, ValueError):
        fact.update({"present": False, "sha256": None, "bytes": None})
    return fact


def emit_additional_context(event_name: str, context: str) -> int:
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": event_name,
                    "additionalContext": context,
                }
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )
    )
    return 0
