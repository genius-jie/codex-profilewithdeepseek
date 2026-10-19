#!/usr/bin/env python3
"""Emit a temporary, mechanical Claude Code Host scope fact."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from claude_context_common import (
    GLOBAL_ENTRY,
    GENERAL_CONSTITUTION,
    emit_additional_context,
    file_fact,
    normalize_absolute_path,
    project_candidate,
    read_event,
    resolve_effective_cwd,
)


HOST_PROFILE = "claude_code"
HOST_CLAUDE = Path(r"@@CLAUDE_HOME:win@@\CLAUDE.md")
HOST_AGENTS_CANDIDATE = Path(r"@@CLAUDE_HOME:win@@\AGENTS.md")

# Mechanically delivered every session: entry-receipt obligation reminder.
# Advisory only: no bodies, no OS selection, no blocking. The same block is
# mirrored in the .codex and Codex++ profile copies (engine isolation keeps
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


def main() -> int:
    event = read_event()
    scope = resolve_effective_cwd(event)
    event_cwd = normalize_absolute_path(event.get("cwd"))
    project = project_candidate(scope.get("cwd"))
    l0 = file_fact(HOST_CLAUDE)
    project_entry_refs = project["entry_refs"]
    project_context_candidates = []
    for entry_ref in project_entry_refs:
        entry_name = Path(entry_ref).name.lower()
        if entry_name == "claude.md":
            source_type = "project_claude_md_candidate"
        elif entry_name == "agents.md":
            source_type = "project_agents_candidate"
        else:
            continue
        project_context_candidates.append(
            {
                "source_type": source_type,
                "classification": "project_context",
                "source_ref": entry_ref,
                "included_in_host_l0": False,
                "binding_status": "not_observed",
                "host_native_consumption": "observe_separately",
            }
        )
    fact: dict[str, Any] = {
        "host_profile": HOST_PROFILE,
        "caller_cwd": scope.get("cwd"),
        "event_cwd": event_cwd,
        "event_cwd_valid": bool(event_cwd),
        "cwd_source": scope.get("source"),
        "cwd_valid": scope.get("valid"),
        "candidate_project_root": project["root"],
        "detected_sentinels": project["sentinels"],
        "project_entry_refs": project_entry_refs,
        "project_context_candidates": project_context_candidates,
        "project_context_type": "project_context_candidates" if project_context_candidates else None,
        "general_os_entry_refs": {
            "global_entry": str(GLOBAL_ENTRY),
            "constitution": str(GENERAL_CONSTITUTION),
        },
        "l0_binding_fact": {"claude_code_global_claude_md": "native_claude_user_claude_md"},
        "l0_sources": [
            {
                "source_id": "claude_code_global_claude_md",
                "source_type": "host_global_claude_md",
                **l0,
                "observed_order": None,
            }
        ],
        # Keep the common Host projection shape aligned with Codex and
        # Codex++; l0_sources remains as a compatibility view for Claude's
        # existing consumers.
        "l0_source_refs": {"host_agents": l0["source_ref"]},
        "l0_source_hashes": {"host_agents": l0.get("sha256")},
        "l0_source_bytes": {"host_agents": l0.get("bytes")},
        "l0_load_order": {
            "status": "not_observable",
            "invariant": "active L0 sources must not rely on mutual override semantics",
        },
        "unbound_host_candidates": [
            {
                "source_ref": str(HOST_AGENTS_CANDIDATE),
                "source_type": "unverified_profile_agents",
                "binding_status": "not_observed",
            }
        ],
        "model_instructions_file": {"status": "not_applicable", "binding_key": None},
        "custom_hook_memory_injection": False,
        "custom_hook_runtime_injection": False,
        "hook_selection_authority": False,
        "governance_entry_obligation": ENTRY_OBLIGATION,
    }
    context = "[HOST_SCOPE_FACT]\n" + json.dumps(fact, ensure_ascii=False, sort_keys=True)
    return emit_additional_context("SessionStart", context)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        # SessionStart is advisory; malformed local state must not block launch.
        print(json.dumps({"systemMessage": f"[HOST_SCOPE_FACT_ERROR] {type(exc).__name__}: {exc}"}, ensure_ascii=False))
        raise SystemExit(0)
