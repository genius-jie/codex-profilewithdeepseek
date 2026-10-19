#!/usr/bin/env python3
"""Emit temporary, mechanical Codex++ Host scope facts at session start."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from hook_common import (
    CODEX_HOME,
    GLOBAL_AGENT_ROOT,
    additional_context,
    read_event,
    resolve_effective_cwd,
    run_safely,
    sanitize_transcript_tool_ids,
)

HOST_PROFILE = "codex_plus_plus"
HOST_AGENTS = CODEX_HOME / "AGENTS.md"
GENERAL_OS_ENTRY = GLOBAL_AGENT_ROOT / "GLOBAL-ENTRY.md"
PROJECT_SENTINELS = (".git", "AGENTS.md", ".agents", ".agent")
MAX_PROJECT_ANCESTORS = 16

# Mechanically delivered every session: entry-receipt obligation reminder.
# Advisory only: no bodies, no OS selection, no blocking. The same block is
# mirrored in the .claude and .codex copies (engine isolation keeps
# independent scripts; text must stay identical to avoid rule drift).
ENTRY_OBLIGATION = (
    "[GOVERNANCE_ENTRY_OBLIGATION]\n"
    "Mechanical SessionStart reminder (advisory, non-blocking; injects no governance bodies):\n"
    "1. Before the first substantive deliverable, if not already in context, read the "
    "General Agent OS navigation entry GLOBAL-ENTRY.md (its path is given in the HOST_SCOPE_FACT above).\n"
    "2. Governance-scenario tasks must first emit M1 PRELOAD_RECEIPT (target_os/asset_home). "
    "Tasks whose project entry contract declares a domain entry receipt must emit that receipt "
    "before any analysis, command execution or edit.\n"
    "3. This hook selects no OS, schedules no execution and blocks nothing; "
    "blocking and completion authority stay with W9 and the Human Gate."
)


def file_fact(path: Path) -> dict[str, Any]:
    """Describe an L0 source mechanically; do not interpret its prompt body."""
    fact: dict[str, Any] = {"source_ref": str(path)}
    try:
        content = path.read_bytes()
        fact.update({"sha256": hashlib.sha256(content).hexdigest(), "bytes": len(content)})
        fact["present"] = True
    except (OSError, ValueError):
        fact.update({"present": False, "sha256": None, "bytes": None})
    return fact


def project_candidate(cwd: str | None) -> tuple[str | None, list[str], str | None]:
    """Find a bounded sentinel-only project candidate without selecting an OS."""
    if not cwd:
        return None, [], None
    try:
        node = Path(cwd)
        if node.is_file():
            node = node.parent
    except (OSError, ValueError):
        return None, [], None
    for _ in range(MAX_PROJECT_ANCESTORS):
        detected = [name for name in PROJECT_SENTINELS if (node / name).exists()]
        if detected:
            agents = node / "AGENTS.md"
            return str(node), detected, str(agents) if agents.is_file() else None
        if node.parent == node:
            break
        node = node.parent
    return None, [], None


def main() -> int:
    event = read_event()
    sanitize_transcript_tool_ids(event.get("transcript_path"))
    scope = resolve_effective_cwd(event)
    candidate_root, sentinels, project_agents = project_candidate(scope["cwd"])
    l0_agents = file_fact(HOST_AGENTS)
    fact = {
        "host_profile": HOST_PROFILE,
        "caller_cwd": scope["cwd"],
        "event_cwd": event.get("cwd") if isinstance(event.get("cwd"), str) else None,
        "cwd_source": scope["source"],
        "cwd_valid": scope["valid"],
        "candidate_project_root": candidate_root,
        "detected_sentinels": sentinels,
        "project_entry_ref": project_agents,
        "project_context_type": "native_project_agents" if project_agents else None,
        "general_os_entry_ref": str(GENERAL_OS_ENTRY),
        "l0_binding_fact": {"host_agents": "host_profile_l0"},
        "l0_source_refs": {"host_agents": l0_agents["source_ref"]},
        "l0_source_hashes": {"host_agents": l0_agents["sha256"]},
        "l0_source_bytes": {"host_agents": l0_agents["bytes"]},
        "load_order": "not_observable",
        "model_instructions_file": "absent",
        "hook_selection_authority": False,
        "governance_entry_obligation": ENTRY_OBLIGATION,
    }
    return additional_context(
        "SessionStart",
        "[HOST_SCOPE_FACT]\n" + json.dumps(fact, ensure_ascii=False, sort_keys=True),
    )


if __name__ == "__main__":
    raise SystemExit(run_safely("SessionStart", main))
