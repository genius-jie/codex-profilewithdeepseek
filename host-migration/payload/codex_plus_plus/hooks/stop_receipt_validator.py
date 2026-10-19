#!/usr/bin/env python3
"""Stop hook receipt validation: parsing STOP_COMPLETION_RECEIPT, extracting
assistant output text from events and session logs, and completion_guard_reason.

Extracted from stop_guard.py to reduce the 935-line monolith.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

from stop_text_analysis import (
    COMPLETE_PATTERNS,
    HUMAN_BLOCKER_PATTERNS,
    has_action_deferred_signal,
    has_semantic_action_debt,
    has_unresolved_work_signal,
    matches_any,
)

try:
    from stop_p0_gate import p0_next_step_guard_reason
except ImportError:
    def p0_next_step_guard_reason(receipt: dict) -> str:
        return ""


# --- Constants ---

STOP_RECEIPT_MARKER = "STOP_COMPLETION_RECEIPT"
MAX_RECEIPT_FILE_BYTES = 65536
PROFILE_CODEX_HOME = Path(__file__).absolute().parent.parent

COMPLETE_RECEIPT_STATUSES = {"complete", "completed", "done", "success", "pass", "passed", "已完成", "完成"}
HUMAN_BLOCKED_RECEIPT_STATUSES = {"blocked", "wait_human", "human_blocked", "blocked_by_human", "阻断", "等待人工"}
EMPTY_RECEIPT_VALUES = {"", "none", "null", "[]", "n/a", "na", "无", "没有", "无待办", "无剩余"}

PROPOSED_PLAN_RE = re.compile(r"<proposed_plan>\s*(?P<body>.*?)\s*</proposed_plan>", re.IGNORECASE | re.DOTALL)
MEMORY_CITATION_RE = re.compile(r"<oai-mem-citation>.*?</oai-mem-citation>", re.IGNORECASE | re.DOTALL)
FENCED_JSON_RE = re.compile(r"```(?:json)?\s*(?P<body>.*?)\s*```", re.IGNORECASE | re.DOTALL)
FOLLOWUP_PAYLOAD_MARKER_RE = re.compile(r'"codex_follow_up(?:_candidate)?"\s*:\s*true', re.IGNORECASE)


# --- Helper functions ---

def _stringify(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False)
    except Exception:
        return str(value)


def _content_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        parts = [_content_text(item) for item in value]
        return "\n".join(part for part in parts if part)
    if isinstance(value, dict):
        for key in ("text", "message", "content", "output_text", "input_text"):
            text = _content_text(value.get(key)).strip()
            if text:
                return text
    return _stringify(value)


def _last_assistant_message(value: object) -> str:
    if not isinstance(value, list):
        return ""
    for item in reversed(value):
        if isinstance(item, dict) and str(item.get("role", "")).lower() == "assistant":
            return _content_text(item.get("content") or item.get("message") or item)
    return ""


def _session_roots() -> list[Path]:
    codex_home = Path(os.environ.get("CODEX_HOME") or PROFILE_CODEX_HOME)
    return [codex_home / "sessions", codex_home / "archived_sessions"]


def _event_path_candidates(value: object) -> list[Path]:
    paths: list[Path] = []
    if isinstance(value, str):
        if value.lower().endswith(".jsonl") or "rollout-" in value.lower():
            path = Path(value)
            if path.exists():
                paths.append(path)
        return paths
    if isinstance(value, list):
        for item in value:
            paths.extend(_event_path_candidates(item))
        return paths
    if isinstance(value, dict):
        for item in value.values():
            paths.extend(_event_path_candidates(item))
    return paths


def _session_files(event: dict) -> list[Path]:
    # The host's explicit transcript is authoritative. Never substitute a
    # newer neighbour session when current-session evidence is absent.
    for key in ("transcript_path", "session_path", "rollout_path"):
        explicit = _event_path_candidates(event.get(key))
        if explicit:
            return list(dict.fromkeys(explicit))
    ids = [
        str(value)
        for value in (
            event.get("session_id"),
            event.get("conversation_id"),
            event.get("conversationId"),
            event.get("thread_id"),
            event.get("threadId"),
        )
        if value
    ]
    candidates: list[Path] = []
    if not ids:
        return []
    for root in _session_roots():
        if not root.exists():
            continue
        files = list(root.rglob("rollout-*.jsonl"))
        matches = [path for path in files if any(value in path.name for value in ids)]
        candidates.extend(matches)
    unique = list(dict.fromkeys(candidates))
    return sorted(unique, key=lambda path: path.stat().st_mtime, reverse=True)


def _assistant_text_from_log_item(item: dict, payload: object) -> str:
    if not isinstance(payload, dict):
        return ""
    if item.get("type") == "response_item":
        if payload.get("type") == "message" and str(payload.get("role", "")).lower() == "assistant":
            return _content_text(payload.get("content") or payload.get("message") or payload)
    if item.get("type") == "event_msg":
        if payload.get("type") == "agent_message":
            return _content_text(payload.get("message"))
        if payload.get("type") == "task_complete":
            return _content_text(payload.get("last_agent_message"))
    return ""


def _assistant_text_from_session_log(event: dict) -> str:
    for path in _session_files(event):
        last_text = ""
        try:
            with path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    try:
                        item = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    payload = item.get("payload") or {}
                    text = _assistant_text_from_log_item(item, payload).strip()
                    if text:
                        last_text = text
        except Exception:
            continue
        if last_text:
            return last_text
    return ""


def assistant_output_text(event: dict) -> str:
    """Best-effort extraction of the final assistant text from Stop hook input."""
    for key in ("last_assistant_message", "last_agent_message", "assistant_response", "final_response", "response", "last_response", "message", "content", "output"):
        text = _content_text(event.get(key)).strip()
        if text:
            return text
    for key in ("messages", "conversation", "transcript"):
        text = _last_assistant_message(event.get(key)).strip()
        if text:
            return text
    return _assistant_text_from_session_log(event)


# --- Receipt parsing ---

def _receipt_values(value: object) -> list[object]:
    if value is None:
        return []
    if isinstance(value, list):
        return [item for item in value if _receipt_values(item)]
    if isinstance(value, dict):
        return [value] if value else []
    normalized = str(value).strip().lower()
    if normalized in EMPTY_RECEIPT_VALUES:
        return []
    return [value]


def _load_receipt_path(value: object) -> dict:
    raw_path = str(value or "").strip().strip("`").strip()
    if not raw_path:
        return {"_parse_error": "STOP_COMPLETION_RECEIPT receipt_path is empty."}
    path = Path(raw_path).expanduser()
    if not path.is_absolute():
        return {"_parse_error": "STOP_COMPLETION_RECEIPT receipt_path must be an absolute path."}
    if not path.exists() or not path.is_file():
        return {"_parse_error": "STOP_COMPLETION_RECEIPT receipt_path not found."}
    if path.stat().st_size > MAX_RECEIPT_FILE_BYTES:
        return {"_parse_error": "STOP_COMPLETION_RECEIPT receipt_path is too large."}
    try:
        loaded = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return {"_parse_error": "STOP_COMPLETION_RECEIPT receipt_path must contain valid JSON."}
    if not isinstance(loaded, dict):
        return {"_parse_error": "STOP_COMPLETION_RECEIPT receipt_path must contain a JSON object."}
    loaded.setdefault("receipt_path", str(path))
    return loaded


def _completion_receipt(text: str) -> dict:
    marker_matches = list(
        re.finditer(rf"(?m)(?:^|[\s。.!?；;]){re.escape(STOP_RECEIPT_MARKER)}\s*(?:$|[:：])", text)
    )
    if not marker_matches:
        return {}
    marker_end = marker_matches[-1].end()
    surface = text[marker_end:].lstrip(" \t:：\r\n")
    if not surface:
        return {}
    if surface.startswith("```"):
        surface = re.sub(r"^```(?:json)?\s*", "", surface, count=1, flags=re.IGNORECASE)
    if re.match(r"^\{\s*(?:\.{3}|…)\s*\}", surface):
        return {}
    try:
        value, _index = json.JSONDecoder().raw_decode(surface)
    except Exception:
        return {"_parse_error": "STOP_COMPLETION_RECEIPT must be valid JSON."}
    if not isinstance(value, dict):
        return {"_parse_error": "STOP_COMPLETION_RECEIPT must be a JSON object."}
    if value.get("receipt_path"):
        return _load_receipt_path(value.get("receipt_path"))
    return value


def _has_complete_receipt(text: str) -> bool:
    receipt = _completion_receipt(text)
    if not receipt or receipt.get("_parse_error"):
        return False
    status = str(receipt.get("status") or receipt.get("task_status") or "").strip().lower()
    verification = _receipt_values(receipt.get("verification") or receipt.get("verified") or receipt.get("tests"))
    open_items = _receipt_values(
        receipt.get("open_items")
        or receipt.get("remaining_items")
        or receipt.get("unresolved_actions")
        or receipt.get("todo")
    )
    blockers = _receipt_values(receipt.get("blockers") or receipt.get("external_blockers"))
    return status in COMPLETE_RECEIPT_STATUSES and bool(verification) and not open_items and not blockers


# --- Follow-up payload handling ---

def _is_followup_payload_block(body: str) -> bool:
    if not FOLLOWUP_PAYLOAD_MARKER_RE.search(body or ""):
        return False
    start = body.find("{")
    if start >= 0:
        try:
            value, _index = json.JSONDecoder().raw_decode(body[start:].strip())
            if isinstance(value, dict):
                return value.get("codex_follow_up_candidate") is True or value.get("codex_follow_up") is True
        except Exception:
            pass
    return True


def strip_followup_payloads(text: str) -> str:
    def replace(match: re.Match[str]) -> str:
        return "" if _is_followup_payload_block(match.group("body") or "") else match.group(0)

    return FENCED_JSON_RE.sub(replace, text or "")


# --- Plan mode ---

def is_plan_mode_completion(
    text: str,
    event: dict | None = None,
    pending: dict | None = None,
) -> bool:
    """Allow official Plan Mode outputs to stop without auto-continuing."""
    from hook_common import load_state, pending_base_key, pending_items_for_event

    matches = list(PROPOSED_PLAN_RE.finditer(text or ""))
    if not matches or not any((match.group("body") or "").strip() for match in matches):
        return False
    if "WAIT_HUMAN_BLOCKER" in text:
        return False
    if pending is None:
        raw_pending = load_state().get("pending") or {}
        pending = pending_items_for_event(raw_pending, event or {})
    actionable = {
        key: value
        for key, value in pending.items()
        if pending_base_key(key) != "third_party_submodule_skipped"
    }
    if actionable:
        return False
    outside = PROPOSED_PLAN_RE.sub(" ", text)
    outside = MEMORY_CITATION_RE.sub(" ", outside)
    outside = re.sub(rf"{re.escape(STOP_RECEIPT_MARKER)}\s*[:：]\s*\{{.*?\}}\s*", " ", outside, flags=re.IGNORECASE | re.DOTALL)
    if re.search(r"(还需|还需要|仍需|仍需要|需要继续|未完成).{0,24}(处理|清理|修复|移除|删除|归档|治理|补齐|更新|校验|验证|继续|解决|收口|pending|阻断|待办)", outside, re.IGNORECASE):
        return False
    return not (
        has_unresolved_work_signal(outside)
        or has_action_deferred_signal(outside)
        or has_semantic_action_debt(outside)
        or matches_any(outside, HUMAN_BLOCKER_PATTERNS)
    )


# --- Receipt guard ---

def receipt_guard_reason(text: str) -> str:
    receipt = _completion_receipt(text)
    if not receipt:
        return ""
    if receipt.get("_parse_error"):
        return str(receipt["_parse_error"])
    status = str(receipt.get("status") or receipt.get("task_status") or "").strip().lower()
    open_items = _receipt_values(
        receipt.get("open_items")
        or receipt.get("remaining_items")
        or receipt.get("unresolved_actions")
        or receipt.get("todo")
    )
    blockers = _receipt_values(receipt.get("blockers") or receipt.get("external_blockers"))
    verification = _receipt_values(receipt.get("verification") or receipt.get("verified") or receipt.get("tests"))
    if status in HUMAN_BLOCKED_RECEIPT_STATUSES and blockers:
        return ""
    if not status:
        return "STOP_COMPLETION_RECEIPT requires an explicit status."
    if status not in COMPLETE_RECEIPT_STATUSES:
        return "STOP_COMPLETION_RECEIPT status is not complete; continue working or report a concrete human blocker."
    if not any(key in receipt for key in ("open_items", "remaining_items", "unresolved_actions", "todo")):
        return "STOP_COMPLETION_RECEIPT requires an explicit open_items list; use [] only after current-task work is verified closed."
    if any(key in receipt and not isinstance(receipt[key], list)
           for key in ("open_items", "remaining_items", "unresolved_actions", "todo")):
        return "STOP_COMPLETION_RECEIPT open_items must be a list, not a null, scalar, or object placeholder."
    if open_items and not blockers:
        return "STOP_COMPLETION_RECEIPT lists unresolved actions without a human blocker; continue working before stopping."
    if blockers and status in COMPLETE_RECEIPT_STATUSES:
        return "STOP_COMPLETION_RECEIPT claims completion but still lists blockers; resolve the mismatch before stopping."
    if status in COMPLETE_RECEIPT_STATUSES and not verification:
        return "STOP_COMPLETION_RECEIPT claims completion but has no verification evidence."
    return ""


# --- Completion guard (main analysis entry point) ---

def completion_guard_reason(
    event: dict,
    text: str | None = None,
    pending: dict | None = None,
) -> str:
    text = text if text is not None else assistant_output_text(event)
    if not text:
        return ""
    receipt_reason = receipt_guard_reason(text)
    if receipt_reason:
        return receipt_reason
    receipt = _completion_receipt(text)
    if receipt:
        p0_reason = p0_next_step_guard_reason(receipt)
        if p0_reason:
            return p0_reason
        return ""
    scan_text = MEMORY_CITATION_RE.sub(" ", strip_followup_payloads(text))
    if PROPOSED_PLAN_RE.search(text):
        if is_plan_mode_completion(text, event, pending):
            return ""
        return (
            "STOP_GUARD_REJECT_REASON: <proposed_plan> is present but cannot stop while "
            "pending state or plan-external action debt remains."
        )
    has_followup = has_action_deferred_signal(scan_text)
    has_action_debt = has_semantic_action_debt(scan_text)
    has_incomplete = has_unresolved_work_signal(scan_text)
    has_complete = matches_any(scan_text, COMPLETE_PATTERNS)
    if (
        (has_action_debt or has_followup)
        and not matches_any(scan_text, HUMAN_BLOCKER_PATTERNS)
    ):
        return (
            "STOP_GUARD_REJECT_REASON: final response contains unresolved action wording. "
            "Finish the named action before stopping. If an external blocker is real, return WAIT_HUMAN_BLOCKER with concrete evidence. "
            "A completed turn must include STOP_COMPLETION_RECEIPT with status=complete, non-empty verification, and open_items=[]."
        )
    if has_incomplete and not matches_any(scan_text, HUMAN_BLOCKER_PATTERNS):
        return (
            "STOP_GUARD_REJECT_REASON: completion wording conflicts with unresolved-work wording. "
            "A completion claim requires STOP_COMPLETION_RECEIPT with status=complete, non-empty verification, and open_items=[]. "
            "Otherwise finish the named action, or return WAIT_HUMAN_BLOCKER with concrete external-blocker evidence."
        )
    if has_complete:
        return ""
    if not has_incomplete:
        return ""
    if matches_any(scan_text, HUMAN_BLOCKER_PATTERNS):
        return ""
    return (
        "STOP_GUARD_REJECT_REASON: final response has no completion receipt and still reads as unfinished. "
        "Finish the named action before stopping, or return WAIT_HUMAN_BLOCKER with concrete external-blocker evidence."
    )
