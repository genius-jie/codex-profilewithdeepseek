#!/usr/bin/env python3
"""Record lightweight pending evidence after tool execution."""

from __future__ import annotations

import re
import json
from pathlib import Path

from hook_common import (
    additional_context,
    clear_pending,
    clear_pending_all,
    command_may_modify_files,
    command_targets_governed_markdown,
    command_failed,
    extract_governed_md_mentions,
    is_git_write_to_third_party,
    is_pip_install_with_requirements,
    load_state,
    mark_pending,
    now_iso,
    pending_item_for_event,
    pending_owner_scope,
    pending_storage_key,
    read_event,
    record_hook_run,
    run_safely,
    response_text,
    save_state,
    state_lock,
    tool_command,
    tool_name,
    tool_text,
    within_openclaw,
    sanitize_transcript_tool_ids,
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


FAILURE_FINGERPRINT_MARKERS = (
    "verify_testing_governance.py",
    "verify-governance-hard-gate.ps1",
    "reconcile-birth-ceremony.py",
    "py_compile",
)

KNOWN_CODEX_PLUSPLUS_NONGIT_SURFACES = (
    Path(r"@@LAUNCHER_ROOT:win@@"),
    Path(r"@@CODEX_HOME:win@@-plusplus"),
    Path(r"@@CODEXPP_HOME:win@@"),
)

EVIDENCE_RECEIPT_GLOBS = (
    ".codex-evidence/**/*.json",
    "projects/*/docs/specs/**/evidence/*.json",
)


def _fingerprint_surface(command: str) -> str:
    return re.sub(r"\s+", " ", command).strip()


def failure_fingerprint(command: str) -> str:
    surface = _fingerprint_surface(command)
    lowered = surface.lower()
    for marker in FAILURE_FINGERPRINT_MARKERS:
        if marker in lowered:
            return marker
    return surface[:180]


def failure_fingerprint_key(fingerprint: str) -> str:
    lowered = _fingerprint_surface(fingerprint).lower()

    def canonical_bool(match: re.Match[str]) -> str:
        return f"<bool:{match.group(0)}>"

    return re.sub(r"(?<![\w-])(?:true|false)(?![\w-])", canonical_bool, lowered)[:180]


def command_invokes_git_subcommand(command: str, subcommand: str) -> bool:
    surface = re.sub(r"'[^']*'|\"[^\"]*\"", " <arg> ", command)
    option = r"(?:\s+-[A-Za-z]\s+\S+|\s+--[^\s]+(?:\s+\S+)?)"
    pattern = rf"(?<![\w.-])git(?:\.exe)?(?:{option})*\s+{re.escape(subcommand)}\b"
    return re.search(pattern, surface, re.IGNORECASE) is not None


def command_text_contains_git_status(command: str) -> bool:
    return re.search(r"(?<![\w.-])git(?:\.exe)?\s+status\b", command, re.IGNORECASE) is not None


def path_has_git_root(path: Path) -> bool:
    return any((candidate / ".git").exists() for candidate in (path, *path.parents))


def cwd_is_known_codexplusplus_nongit_surface() -> bool:
    try:
        cwd = Path.cwd().resolve()
        if path_has_git_root(cwd):
            return False
        for surface in KNOWN_CODEX_PLUSPLUS_NONGIT_SURFACES:
            resolved = surface.resolve(strict=False)
            if cwd == resolved or cwd.is_relative_to(resolved):
                return True
    except Exception:
        return False
    return False


def benign_nongit_status_probe(command: str, text: str) -> bool:
    cleaned = re.sub(r"\x1b\[[0-9;]*m", "", text or "")
    return (
        command_text_contains_git_status(command)
        and "not a git repository" in cleaned.lower()
        and cwd_is_known_codexplusplus_nongit_surface()
    )


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
    command_surface = re.sub(r"\x1b\[[0-9;]*m", "", command or "")
    output_surface = re.sub(r"\x1b\[[0-9;]*m", "", text or "")
    command_lowered = re.sub(r"\s+", " ", command_surface.lower())
    output_lowered = re.sub(r"\s+", " ", output_surface.lower())
    # The command may contain a literal such as `S12=PASS` as part of the
    # command being tested.  That is an instruction, not evidence.  Evidence
    # must come from the tool's returned output (or a separately recorded
    # receipt), while the fingerprint may be present in either surface.
    fingerprint_surface = " ".join([command_lowered, output_lowered])
    evidence_surface = output_surface.replace(r"\"", '"').replace(r"\'", "'")
    surface_lowered = re.sub(r"\s+", " ", evidence_surface.lower())
    fingerprint_variants = {
        fingerprint,
        fingerprint.replace("\\\\", "\\"),
        fingerprint.replace("\\", "\\\\"),
    }
    if not any(variant and (variant in fingerprint_surface or variant in surface_lowered) for variant in fingerprint_variants):
        return False
    evidence_patterns = (
        r"['\"]?s12['\"]?\s*[:=]\s*['\"]?pass['\"]?",
        r"['\"]?w9['\"]?\s*[:=]\s*['\"]?pass['\"]?",
        r"['\"]?hook[_-]resolution['\"]?\s*[:=]\s*['\"]?failure-review['\"]?",
        r"['\"]?rerun[_-]exit[_-]code['\"]?\s*[:=]\s*0\b",
    )
    if any(re.search(pattern, evidence_surface, re.IGNORECASE) for pattern in evidence_patterns):
        return True
    has_evidence = any(marker in surface_lowered for marker in ("s12", "w9", "hook-resolution", "failure-review"))
    if not has_evidence:
        return False
    return (
        re.search(r'"corrected_result"\s*:\s*"pass"', evidence_surface, re.IGNORECASE) is not None
        or re.search(r'"corrected_command_exit_code"\s*:\s*0\b', evidence_surface, re.IGNORECASE) is not None
        or re.search(r'"rerun_exit_code"\s*:\s*0\b', evidence_surface, re.IGNORECASE) is not None
        or re.search(r'"s12"\s*:\s*"pass"', evidence_surface, re.IGNORECASE) is not None
        or re.search(r'"w9"\s*:\s*"pass"', evidence_surface, re.IGNORECASE) is not None
        or "corrected command returned" in surface_lowered
        or "corrected --id command passed" in surface_lowered
    )


def failure_review_evidence_file_recorded(item: dict) -> bool:
    fingerprint = str(item.get("command_fingerprint") or "").strip().lower()
    if not fingerprint:
        return False
    fingerprint_variants = {
        fingerprint,
        fingerprint.replace("\\\\", "\\"),
        fingerprint.replace("\\", "\\\\"),
    }
    for glob_pattern in EVIDENCE_RECEIPT_GLOBS:
        for path in Path.cwd().glob(glob_pattern):
            try:
                raw = path.read_text(encoding="utf-8", errors="ignore")
                receipt = json.loads(raw)
            except Exception:
                continue
            surface = raw.replace(r"\"", '"').replace(r"\'", "'")
            lowered = re.sub(r"\s+", " ", surface.lower())
            if not any(variant and variant in lowered for variant in fingerprint_variants):
                continue
            status = str(receipt.get("status") or receipt.get("corrected_result") or "").lower()
            evidence_type = str(receipt.get("evidenceType") or receipt.get("evidence_type") or "").lower()
            if status == "pass" and ("s12" in evidence_type or "w9" in evidence_type or "failure" in evidence_type):
                return True
            if receipt.get("rerun_exit_code") == 0 and ("s12" in lowered or "w9" in lowered):
                return True
    return False


def mark_failure_review(command: str, event: dict) -> None:
    fingerprint = failure_fingerprint(command)
    fingerprint_key = failure_fingerprint_key(fingerprint)
    with state_lock():
        state = load_state()
        pending = state.setdefault("pending", {})
        storage_key = pending_storage_key("pending_failure_review", event)
        item = pending.setdefault(storage_key, {})
        previous = item.get("command_fingerprint")
        previous_key = item.get("command_fingerprint_key") or failure_fingerprint_key(str(previous or ""))
        count = int(item.get("failure_count", 0)) + 1 if previous_key == fingerprint_key else 1
        if count >= 2:
            item["reason"] = "tool reported repeated errors; run S12 and consider M9"
        else:
            item["reason"] = "tool reported error; rerun the failed command or provide S12/W9 evidence"
        item["updated_at"] = now_iso()
        item["command_fingerprint"] = fingerprint
        item["command_fingerprint_key"] = fingerprint_key
        item["last_command"] = command[:500]
        item["failure_count"] = count
        owner_scope = pending_owner_scope(event)
        if owner_scope:
            item["owner_scope"] = owner_scope
        session_id = str(event.get("session_id") or "").strip()
        turn_id = str(event.get("turn_id") or "").strip()
        if session_id:
            item["session_id"] = session_id
        if turn_id:
            item["turn_id"] = turn_id
        save_state(state)


def failure_review_resolved(command: str, text: str, event: dict) -> bool:
    state = load_state()
    item = pending_item_for_event(state.get("pending") or {}, "pending_failure_review", event)
    if not item:
        return False
    fingerprint = failure_fingerprint(command)
    fingerprint_key = failure_fingerprint_key(fingerprint)
    pending_key = item.get("command_fingerprint_key") or failure_fingerprint_key(str(item.get("command_fingerprint") or ""))
    return (
        pending_key == fingerprint_key
        or review_command_passed(command, text)
        or failure_review_evidence_recorded(item, command, text)
        or failure_review_evidence_file_recorded(item)
    )


def main() -> int:
    event = read_event()
    record_hook_run("PostToolUse", event)
    sanitize_transcript_tool_ids(event.get("transcript_path"))
    name = tool_name(event)
    command = tool_command(event)
    is_shell_command = name.casefold() in {"bash", "shell_command", "functions.shell_command", "powershell"}
    input_text = command or tool_text(event)
    output_text = response_text(event)
    text = " ".join([input_text, output_text])
    notes: list[str] = []

    governed = extract_governed_md_mentions(input_text)
    if (
        within_openclaw(event)
        and governed
        and command_may_modify_files(name, command)
        and command_targets_governed_markdown(name, command, governed)
    ):
        mark_pending(
            "pending_w9",
            "governed markdown changed; W9 must choose GateProfile by the G0-G20 matrix (Constitution/SOP-only => Advisory)",
            governed,
            event=event,
        )
        notes.append("pending_w9 marked for governed Markdown.")

    if governance_hard_gate_ran(command):
        gate_profile = governance_hard_gate_profile(command)
        clear_pending_all("pending_w9")
        if governance_hard_gate_passed(command, text):
            notes.append("pending_w9 cleared after W9 hard gate pass.")
        else:
            notes.append("pending_w9 cleared after W9 hard gate ran; failure review carries the blocker.")
        if not gate_profile:
            notes.append("W9 hard gate ran without GateProfile; use the G0-G20 matrix, with Constitution/SOP-only changes on Advisory.")

    if is_shell_command and command_invokes_git_subcommand(command, "commit"):
        mark_pending("pending_s15", "git commit observed; verify push and dual-zero receipt", event=event)
        notes.append("pending_s15 marked after git commit.")
    if is_shell_command and command_invokes_git_subcommand(command, "push"):
        if command_failed(event) or "403" in text or "permission" in text.lower():
            mark_pending("pending_s15", "git push permission failure observed", event=event)
            notes.append("git push permission failure recorded.")
        else:
            clear_pending("pending_s15", event=event)
            notes.append("pending_s15 cleared after git push.")

    if is_git_write_to_third_party(command) and ("403" in text or "permission" in text.lower()):
        mark_pending("third_party_submodule_skipped", "feishu-mcp-server push blocked by third-party permissions")
        notes.append("third-party feishu skip recorded.")

    failed = command_failed(event)
    if not failed and is_pip_install_with_requirements(command):
        clear_pending("pending_permission_review", event=event)
        notes.append("pending_permission_review cleared after successful requirements install.")
    if failed:
        if benign_nongit_status_probe(input_text, output_text):
            notes.append("benign non-git Codex++ git status probe ignored.")
        else:
            mark_failure_review(input_text, event)
            notes.append("failure review marked.")
    elif failure_review_resolved(input_text, output_text, event):
        clear_pending("pending_failure_review", event=event)
        notes.append("pending_failure_review cleared after passing rerun/evidence.")

    if not notes:
        return 0
    return additional_context(
        "PostToolUse",
        "[HOOK:POST_TOOL_AUDIT]\n" + "\n".join(f"- {note}" for note in notes),
    )


if __name__ == "__main__":
    raise SystemExit(run_safely("PostToolUse", main))
