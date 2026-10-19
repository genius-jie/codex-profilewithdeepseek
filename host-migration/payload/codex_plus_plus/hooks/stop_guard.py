#!/usr/bin/env python3
"""Thin stop hook entry point.

Delegates to four sub-modules:
  - stop_text_analysis:     pattern matching & text signal detection
  - stop_receipt_validator:  receipt parsing, assistant text extraction, completion_guard_reason
  - stop_p0_gate:           P0 next-step continuation gate
  - stop_loop_guard:        auto-continue loop prevention & output helpers

This file keeps only:
  - main() orchestration
  - Commander-scoped pending filter
  - Bridge report helper
"""

from __future__ import annotations

import os
import re
from pathlib import Path

from hook_common import (
    hook_self_audit,
    load_state,
    pending_base_key,
    pending_items_for_event,
    read_event,
    record_hook_evolution_candidates,
    record_hook_run,
    run_safely,
)

from stop_receipt_validator import (
    COMPLETE_RECEIPT_STATUSES,
    HUMAN_BLOCKED_RECEIPT_STATUSES,
    _completion_receipt,
    _has_complete_receipt,
    _receipt_values,
    assistant_output_text,
    completion_guard_reason,
)

from stop_loop_guard import (
    auto_continue_loop_guard,
    loop_guard_continue,
    stop_block,
)

try:
    from stop_hook_bridge import write_bridge_report
except Exception:
    def write_bridge_report(event: dict, output_text: str, guard_reason: str, pending: dict, **kwargs) -> None:
        return None


# --- Constants for commander filtering ---

FINGERPRINT_PATH_REWRITES = {
    r"@@TESTING_ROOT:win@@\.agent\config\perf_environment_registry.json": (
        r"@@TESTING_ROOT:win@@\接口测试\性能测试-小精灵全链路\config\perf_environment_registry.json"
    ),
}


# --- Commander-scoped pending filter ---

def _normalize_fingerprint_paths(text: str) -> str:
    normalized = text or ""
    for old, new in FINGERPRINT_PATH_REWRITES.items():
        normalized = normalized.replace(old, new)
        normalized = normalized.replace(old.replace("\\", "\\\\"), new)
    return normalized


def _norm_abs_path(value: str) -> str:
    return os.path.normcase(os.path.normpath(value.strip()))


def _is_relative_to_path(child: str, parent: str) -> bool:
    try:
        return os.path.commonpath([_norm_abs_path(child), _norm_abs_path(parent)]) == _norm_abs_path(parent)
    except Exception:
        return False


def _absolute_paths_from_text(text: str) -> list[str]:
    paths: list[str] = []
    for match in re.finditer(r"""['"]([A-Za-z]:\\[^'"]+)['"]""", text or ""):
        paths.append(match.group(1).strip())
    for match in re.finditer(r"""(?<![A-Za-z0-9])([A-Za-z]:\\[^\s`'"]+)""", text or ""):
        paths.append(match.group(1).strip())
    unique: list[str] = []
    seen: set[str] = set()
    for path_text in paths:
        key = _norm_abs_path(path_text)
        if key in seen:
            continue
        seen.add(key)
        unique.append(path_text)
    return unique


def _commander_unrelated_pending(key: str, value: dict, expected_cwd: str) -> bool:
    if pending_base_key(key) != "pending_failure_review" or not expected_cwd:
        return False
    fingerprint = _normalize_fingerprint_paths(
        str(value.get("command_fingerprint") or value.get("last_command") or "")
    )
    paths = _absolute_paths_from_text(fingerprint)
    if not paths:
        return False
    return all(not _is_relative_to_path(path_text, expected_cwd) for path_text in paths)


def filter_commander_unrelated_pending(actionable: dict, output_text: str) -> dict:
    expected_cwd = os.environ.get("CODEX_COMMANDER_EXPECTED_CWD", "").strip()
    if not expected_cwd or not _has_complete_receipt(output_text):
        return actionable
    return {
        key: value
        for key, value in actionable.items()
        if not _commander_unrelated_pending(key, value, expected_cwd)
    }


# --- Bridge report helper ---

def record_bridge_report(
    event: dict,
    output_text: str,
    guard_reason: str,
    pending: dict,
    guard_decision: str | None = None,
) -> None:
    try:
        write_bridge_report(event, output_text, guard_reason, pending, guard_decision=guard_decision)
    except Exception:
        pass


def has_concrete_human_blocker(output_text: str) -> bool:
    receipt = _completion_receipt(output_text)
    if not receipt:
        return False
    status = str(receipt.get("status") or receipt.get("task_status") or "").strip().lower()
    blockers = _receipt_values(receipt.get("blockers") or receipt.get("external_blockers"))
    return status in HUMAN_BLOCKED_RECEIPT_STATUSES and bool(blockers)


ADVISORY_PENDING_BASE_KEYS = {"pending_s15"}


def split_pending_for_stop(pending: dict) -> tuple[dict, dict]:
    """Separate current-turn blockers from cross-task advisory notices.

    A commit/push receipt is repository bookkeeping, not proof that the
    product task itself is unfinished.  S15 remains visible in the bridge
    report, but it must not trap an unrelated product task in a Stop loop.
    """
    actionable: dict = {}
    advisory: dict = {}
    for key, value in pending.items():
        if pending_base_key(key) in ADVISORY_PENDING_BASE_KEYS:
            advisory[key] = value
        else:
            actionable[key] = value
    return actionable, advisory


# --- Main orchestration ---

def main() -> int:
    event = read_event()
    record_hook_run("Stop", event)
    state = load_state()
    pending = state.get("pending") or {}
    audit_summary, audit_anomalies = hook_self_audit(event)
    output_text = assistant_output_text(event)
    owned_pending = pending_items_for_event(pending, event)
    owned_pending = {
        key: value
        for key, value in owned_pending.items()
        if pending_base_key(key) != "third_party_submodule_skipped"
    }
    actionable, _advisory_pending = split_pending_for_stop(owned_pending)
    actionable = filter_commander_unrelated_pending(actionable, output_text)
    if actionable and has_concrete_human_blocker(output_text):
        record_bridge_report(event, output_text, "", owned_pending, guard_decision="human_blocked")
        return 0
    if not output_text:
        audit_anomalies.append("Stop hook could not extract assistant output text; review Codex Stop event schema.")
    evolution_ready = record_hook_evolution_candidates(event, audit_summary, audit_anomalies)
    if not actionable:
        completion_reason = completion_guard_reason(event, output_text, actionable)
        if completion_reason:
            loop_guard_reason = auto_continue_loop_guard(event, output_text, completion_reason)
            if loop_guard_reason:
                record_bridge_report(event, output_text, loop_guard_reason, owned_pending, guard_decision="loop_suppressed")
                return loop_guard_continue(loop_guard_reason)
            record_bridge_report(event, output_text, completion_reason, owned_pending)
            return stop_block(completion_reason)
        if audit_anomalies:
            evolution_lines = []
            if evolution_ready:
                evolution_lines.append("Ready for M8/W7 review:")
                evolution_lines.extend(f"- {item}" for item in evolution_ready)
            else:
                evolution_lines.append("Recorded as hook evolution candidate; promote only after repeated evidence.")
            record_bridge_report(event, output_text, "", owned_pending)
            return 0
        record_bridge_report(event, output_text, "", owned_pending)
        return 0

    lines = ["Pending hook state must be addressed before final completion:"]
    for key, value in actionable.items():
        base_key = pending_base_key(key)
        lines.append(f"- {base_key}: {value.get('reason', '')}")
        if base_key == "pending_failure_review":
            fingerprint = _normalize_fingerprint_paths(str(value.get("command_fingerprint") or ""))
            failure_count = int(value.get("failure_count") or 0)
            if fingerprint:
                lines.append(f"  resolution: rerun a passing command for fingerprint `{fingerprint}`, or record S12/W9 evidence.")
            if failure_count >= 2:
                lines.append("  escalation: repeated same-fingerprint failures; include M9 review if S12 does not close it.")
            elif failure_count == 1:
                lines.append("  escalation: single failure; S12 evidence is enough unless it repeats.")
    if audit_summary:
        lines.append(f"Hook self-audit observed: {audit_summary}")
    if evolution_ready:
        lines.append("Hook evolution candidates reached M8/W7 review threshold:")
        lines.extend(f"- {item}" for item in evolution_ready)
    lines.append("Run the named resolution step above or explicitly report the blocker with evidence.")
    reason = "\n".join(lines)
    loop_guard_reason = auto_continue_loop_guard(event, output_text, reason)
    if loop_guard_reason:
        record_bridge_report(event, output_text, loop_guard_reason, owned_pending, guard_decision="loop_suppressed")
        return loop_guard_continue(loop_guard_reason)
    record_bridge_report(event, output_text, reason, owned_pending)
    return stop_block(reason)


def _is_followup_payload_block(last_assistant_message: str) -> dict:
    # [HOOK:STOP_GUARD]
    # 不再|不会再|不会|不应|避免
    # 为空|空对象|empty
    # payload = {"continue": True}
    # "decision": "block"
    pass


if __name__ == "__main__":
    raise SystemExit(run_safely("Stop", main))
