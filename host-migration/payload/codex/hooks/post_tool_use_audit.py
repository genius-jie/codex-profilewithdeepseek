#!/usr/bin/env python3
"""Record lightweight pending evidence after tool execution."""

from __future__ import annotations

import re
import json
from pathlib import Path

from hook_common import (
    additional_context,
    clear_pending,
    command_may_modify_files,
    command_failed,
    extract_governed_md_mentions,
    is_git_write_to_third_party,
    is_pip_install_with_requirements,
    load_state,
    mark_pending,
    now_iso,
    pending_owned_by_event,
    pending_owner_scope,
    pending_storage_key,
    read_event,
    record_hook_run,
    run_safely,
    response_text,
    save_state,
    state_lock,
    strip_command_literals,
    tool_command,
    tool_name,
    tool_text,
    within_openclaw,
)


def governance_hard_gate_passed(command: str, text: str) -> bool:
    cleaned = re.sub(r"\x1b\[[0-9;]*m", "", text)
    lowered = re.sub(r"\s+", " ", cleaned.lower())
    return (
        "verify-governance-hard-gate.ps1" in command.lower()
        and "governance hard gate passed" in lowered
        and re.search(r"\bfail:\s*0\b", lowered) is not None
    )


def governance_hard_gate_ran(command: str) -> bool:
    return "verify-governance-hard-gate.ps1" in command.lower()


def governance_hard_gate_profile(command: str) -> str | None:
    match = re.search(r"(?i)(?:^|\s)-gateprofile(?:\s+|=)([A-Za-z]+)", command or "")
    return match.group(1) if match else None


def git_subcommand_invoked(command: str, subcommand: str) -> bool:
    """Match an executed shell Git verb, not a quoted code or patch fragment."""
    surface = strip_command_literals(command or "")
    pattern = rf"(?im)(?:^|[;&|]\s*|&\s*)git(?:\.exe)?(?:\s+-C\s+[^\s;&|]+)*\s+{re.escape(subcommand)}\b"
    return re.search(pattern, surface) is not None


def failure_fingerprint(command: str) -> str:
    lowered = re.sub(r"\s+", " ", command.lower()).strip()
    for marker in (
        "verify_testing_governance.py",
        "verify-governance-hard-gate.ps1",
        "reconcile-birth-ceremony.py",
        "py_compile",
    ):
        if marker in lowered:
            return marker
    return lowered[:180]


def review_command_passed(command: str, text: str) -> bool:
    cleaned = re.sub(r"\x1b\[[0-9;]*m", "", text)
    lowered_command = command.lower()
    if governance_hard_gate_passed(command, text):
        return True
    if "verify_testing_governance.py" in lowered_command:
        return re.search(r'"status"\s*:\s*"pass"', cleaned, re.IGNORECASE) is not None
    return False


def failure_review_evidence_recorded(item: dict, command: str, text: str) -> bool:
    fingerprint = str(item.get("command_fingerprint") or "").strip().lower()
    if not fingerprint:
        return False
    cleaned = re.sub(r"\x1b\[[0-9;]*m", "", " ".join([command, text]))
    lowered = re.sub(r"\s+", " ", cleaned.lower())
    evidence_surface = (
        cleaned.replace(r"\"", '"')
        .replace(r"\'", "'")
        .replace(r"\n", "\n")
        .replace(r"\r", "\r")
        .replace(r"\t", "\t")
    )
    surface_lowered = re.sub(r"\s+", " ", evidence_surface.lower())
    explicit_s12_w9_marker = re.search(
        r"\bs12\s*/\s*w9(?:[_ -]?(?:evidence|verification))?\s*[:=]\s*pass\b",
        surface_lowered,
    ) is not None
    explicit_rerun_pass = re.search(
        r"\b(?:replay|rerun)_exit(?:_code)?\s*[:=]\s*0\b",
        surface_lowered,
    ) is not None
    # A successful PostToolUse command may be an equivalent verification
    # command rather than a byte-for-byte replay of the failed command.  An
    # explicit S12/W9 pass marker plus an exit-0 marker is a bounded resolution
    # contract; do not require the old raw fingerprint in that case.
    if explicit_s12_w9_marker and explicit_rerun_pass:
        return True
    fingerprint_variants = {
        fingerprint,
        fingerprint.replace("\\\\", "\\"),
        fingerprint.replace("\\", "\\\\"),
    }
    fingerprint_present = any(
        variant and (variant in lowered or variant in surface_lowered)
        for variant in fingerprint_variants
    )
    if not fingerprint_present and not re.search(r"(?i)[a-z]:\\[^\"\r\n<>|*?]+?\.json", evidence_surface):
        return False
    evidence_patterns = (
        r"['\"]?s12['\"]?\s*[:=]\s*['\"]?pass['\"]?",
        r"['\"]?w9['\"]?\s*[:=]\s*['\"]?pass['\"]?",
        r"['\"]?hook[_-]resolution['\"]?\s*[:=]\s*['\"]?failure-review['\"]?",
        r"['\"]?rerun[_-]exit[_-]code['\"]?\s*[:=]\s*0\b",
    )
    if any(re.search(pattern, evidence_surface, re.IGNORECASE) for pattern in evidence_patterns):
        return True
    has_evidence = any(marker in lowered for marker in ("s12", "w9", "hook-resolution", "failure-review"))
    if not has_evidence:
        return False
    if (
        re.search(r'"corrected_result"\s*:\s*"pass"', cleaned, re.IGNORECASE) is not None
        or re.search(r'"corrected_command_exit_code"\s*:\s*0\b', cleaned, re.IGNORECASE) is not None
        or re.search(r'"rerun_exit_code"\s*:\s*0\b', cleaned, re.IGNORECASE) is not None
        or re.search(r'"s12"\s*:\s*"pass"', cleaned, re.IGNORECASE) is not None
        or re.search(r'"w9"\s*:\s*"pass"', cleaned, re.IGNORECASE) is not None
        or "corrected command returned" in lowered
        or "corrected --id command passed" in lowered
    ):
        return True

    # A receipt written by an earlier tool call is valid evidence only when
    # the current command explicitly names that JSON file.  This keeps the
    # existing session-scoped pending key while making file-backed S12/W9
    # receipts consumable by the hook instead of leaving a sticky blocker.
    path_candidates = re.findall(r"(?i)([a-z]:\\[^\"\r\n<>|*?]+?\.json)", evidence_surface)
    for raw_path in path_candidates:
        path = Path(raw_path.rstrip("'`"))
        try:
            if not path.is_file() or path.stat().st_size > 2 * 1024 * 1024:
                continue
            receipt = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, UnicodeError):
            continue
        if not isinstance(receipt, dict):
            continue
        serialized = json.dumps(receipt, ensure_ascii=False).lower()
        serialized_fingerprint_variants = {
            fingerprint,
            fingerprint.replace("\\", "\\\\"),
            fingerprint.replace("\\\\", "\\"),
            json.dumps(fingerprint, ensure_ascii=False)[1:-1],
        }
        if not any(variant and variant in serialized for variant in serialized_fingerprint_variants):
            continue
        has_receipt_identity = bool(receipt.get("schema_version") or receipt.get("evidence_id"))
        has_resolution = any(
            marker in serialized
            for marker in ("s12", "w9", "hook_resolution", "failure-review", "corrected_command_exit_code")
        )
        has_positive_result = bool(
            re.search(r'"(?:status|result|verdict|exit_code|rerun_exit_code)"\s*:\s*(?:"pass"|"approved"|0\b)', serialized)
            or "exit=0" in serialized
            or "completed successfully" in serialized
            or "cleared" in serialized
            or "successfully" in serialized
        )
        if has_receipt_identity and has_resolution and has_positive_result:
            return True
    return False


def failure_review_key(event: dict) -> str:
    return pending_storage_key("pending_failure_review", event)


def s15_pending_key(event: dict) -> str:
    """Keep a Git closeout obligation bound to the originating Codex session."""
    session_id = str(event.get("session_id") or "").strip()
    return f"pending_s15:{session_id}" if session_id else ""


def mark_s15_pending(event: dict) -> bool:
    """Record S15 only when the host supplied an exact session identity."""
    key = s15_pending_key(event)
    if not key:
        return False
    session_id = str(event.get("session_id") or "").strip()
    with state_lock():
        state = load_state()
        pending = state.setdefault("pending", {})
        pending[key] = {
            "reason": "git commit observed; verify push and dual-zero receipt",
            "updated_at": now_iso(),
            "session_id": session_id,
        }
        save_state(state)
    return True


def clear_legacy_unscoped_s15() -> bool:
    """Drop the retired global S15 key; active markers always carry a session suffix."""
    with state_lock():
        state = load_state()
        pending = state.setdefault("pending", {})
        if "pending_s15" not in pending:
            return False
        pending.pop("pending_s15", None)
        save_state(state)
        return True


def s15_external_blocker_evidence(event: dict, text: str) -> bool:
    """Recognize a bounded no-remote receipt as a terminal S15 blocker for one session."""
    key = s15_pending_key(event)
    if not key:
        return False
    state = load_state()
    item = (state.get("pending") or {}).get(key)
    if not item:
        return False
    surface = (text or "").replace(r'\"', '"').replace(r"\'", "'")
    cleaned = re.sub(r"\s+", " ", surface).lower()
    has_resolution = "hook_resolution" in cleaned and "s15" in cleaned
    has_blocker = (
        "s15_external_blocker" in cleaned
        or re.search(r'"s15"\s*:\s*"blocked"', cleaned) is not None
    )
    has_no_remote = (
        re.search(r'"remote_count"\s*:\s*0\b', cleaned) is not None
        or "no configured remote" in cleaned
    )
    return bool(has_resolution and has_blocker and has_no_remote)


def failure_review_matches_event(item: dict, event: dict) -> bool:
    return pending_owned_by_event(failure_review_key(event), item, event)


def mark_failure_review(command: str, event: dict) -> None:
    fingerprint = failure_fingerprint(command)
    key = failure_review_key(event)
    with state_lock():
        state = load_state()
        pending = state.setdefault("pending", {})
        item = pending.setdefault(key, {})
        previous = item.get("command_fingerprint")
        count = int(item.get("failure_count", 0)) + 1 if previous == fingerprint else 1
        if count >= 2:
            item["reason"] = "tool reported repeated errors; run S12 and consider M9"
        else:
            item["reason"] = "tool reported error; rerun the failed command or provide S12/W9 evidence"
        item["updated_at"] = now_iso()
        item["command_fingerprint"] = fingerprint
        item["last_command"] = command[:500]
        item["failure_count"] = count
        # A newly observed failing command is current work.  Do not let an
        # earlier, already-superseded failure class silently downgrade this
        # new failure in the same session.
        item["failure_class"] = "CURRENT_TASK_TOOL_FAILURE"
        item.pop("failure_disposition", None)
        item.pop("disposition", None)
        item.pop("superseded_by", None)
        item.pop("resolution", None)
        owner_scope = pending_owner_scope(event)
        if owner_scope:
            item["owner_scope"] = owner_scope
        session_id = str(event.get("session_id") or "").strip()
        if session_id:
            item["session_id"] = session_id
        turn_id = str(event.get("turn_id") or "").strip()
        if turn_id:
            item["turn_id"] = turn_id
        save_state(state)


def failure_review_resolved(event: dict, command: str, text: str) -> bool:
    state = load_state()
    item = (state.get("pending") or {}).get(failure_review_key(event))
    if not item or not failure_review_matches_event(item, event):
        return False
    fingerprint = failure_fingerprint(command)
    return (
        item.get("command_fingerprint") == fingerprint
        or review_command_passed(command, text)
        or failure_review_evidence_recorded(item, command, text)
    )


def main() -> int:
    event = read_event()
    record_hook_run("PostToolUse", event)
    in_openclaw = within_openclaw(event)
    name = tool_name(event)
    command = tool_command(event)
    input_text = command or tool_text(event)
    output_text = response_text(event)
    text = " ".join([input_text, output_text])
    notes: list[str] = []

    if clear_legacy_unscoped_s15():
        notes.append("legacy unscoped pending_s15 cleared; it had no owning session or repository.")

    governed = extract_governed_md_mentions(input_text)
    if in_openclaw and governed and command_may_modify_files(name, command):
        mark_pending(
            "pending_w9",
            "governed markdown changed; W9 must choose GateProfile by the G0-G20 matrix (Constitution/SOP-only => Advisory)",
            governed,
            event=event,
        )
        notes.append("pending_w9 marked for governed Markdown.")

    if governance_hard_gate_ran(command):
        gate_profile = governance_hard_gate_profile(command)
        clear_pending("pending_w9", event=event)
        if governance_hard_gate_passed(command, text):
            notes.append("pending_w9 cleared after W9 hard gate pass.")
        else:
            notes.append("pending_w9 cleared after W9 hard gate ran; failure review carries the blocker.")
        if not gate_profile:
            notes.append("W9 hard gate ran without GateProfile; use the G0-G20 matrix, with Constitution/SOP-only changes on Advisory.")

    if git_subcommand_invoked(command, "commit"):
        if mark_s15_pending(event):
            notes.append("session-scoped pending_s15 marked after git commit.")
        else:
            notes.append("git commit was observed without a session id; no global pending_s15 was created.")
    if git_subcommand_invoked(command, "push"):
        if command_failed(event) or "403" in output_text or "permission" in output_text.lower():
            key = s15_pending_key(event)
            if key:
                mark_pending(key, "git push permission failure observed")
            notes.append("git push permission failure recorded.")
        else:
            key = s15_pending_key(event)
            if key:
                clear_pending(key)
            notes.append("pending_s15 cleared after git push.")
    elif s15_external_blocker_evidence(event, output_text):
        clear_pending(s15_pending_key(event))
        notes.append("pending_s15 cleared after scoped no-remote blocker evidence.")

    if is_git_write_to_third_party(command) and ("403" in output_text or "permission" in output_text.lower()):
        mark_pending("third_party_submodule_skipped", "feishu-mcp-server push blocked by third-party permissions")
        notes.append("third-party feishu skip recorded.")

    if not command_failed(event) and is_pip_install_with_requirements(command):
        clear_pending("pending_permission_review", event=event)
        notes.append("pending_permission_review cleared after successful requirements install.")

    failed = command_failed(event)
    if failed:
        mark_failure_review(input_text, event)
        notes.append("failure review marked.")
    elif failure_review_resolved(event, input_text, text):
        clear_pending(failure_review_key(event))
        notes.append("pending_failure_review cleared after passing rerun/evidence.")

    if not notes:
        return 0
    return additional_context(
        "PostToolUse",
        "[HOOK:POST_TOOL_AUDIT]\n" + "\n".join(f"- {note}" for note in notes),
    )


if __name__ == "__main__":
    raise SystemExit(run_safely("PostToolUse", main))
