#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


STOP_RECEIPT_MARKER = "STOP_COMPLETION_RECEIPT"
COMPLETE_STATUSES = {"complete", "completed", "done", "success", "pass", "passed"}
HUMAN_BLOCKED_STATUSES = {"blocked", "wait_human", "human_blocked", "blocked_by_human"}

FOLLOWUP_PAYLOAD_RE = re.compile(
    r'"(?:codex_)?follow[_-]?up(?:_candidate)?"\s*:\s*true|'
    r'"(?:follow_up_payload|next_step_payload|continuation_payload)"',
    re.IGNORECASE,
)
FENCED_JSON_RE = re.compile(r"```(?:json)?\s*(?P<body>.*?)```", re.IGNORECASE | re.DOTALL)
FOLLOWUP_JSON_LINE_RE = re.compile(r"(?m)^\s*\{[^\r\n]*(?:follow[_-]?up|next_step|continuation)[^\r\n]*\}\s*$", re.IGNORECASE)

INCOMPLETE_RE = re.compile(
    r"("
    r"\bstill need\b|\bneed to\b|\bTODO\b|\bpending\b|\bunresolved\b|"
    r"还需|仍需|未完成|待处理|继续处理|需要继续"
    r")",
    re.IGNORECASE,
)

RESOLVED_PENDING_SPANS = (
    re.compile(
        r"\bpending(?:_[a-z0-9_]+)?\b"
        r"(?:\s*(?:数量|计数|count))?\s*[:=：]\s*"
        r"(?:0|零|none|null|false|empty|\{\}|\[\])"
        r"`*"
        r"(?=$|[\s,，。；;、])",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bpending(?:_[a-z0-9_]+)?\b\s*(?:[:=：]\s*)?"
        r"(?:(?:(?:仍然?|依然|还是)\s*)?(?:(?:为|是)\s*)?(?:空|空对象|empty)|"
        r"(?:已|已经)?\s*(?:清理|清掉|清空|清账|解除|关闭)(?:了)?)"
        r"(?=$|[\s,，。；;、])",
        re.IGNORECASE,
    ),
)

HUMAN_BLOCKER_RE = re.compile(
    r"(WAIT_HUMAN_BLOCKER|missing permission|missing login|missing credentials|等待用户|缺少授权|缺少登录|缺少凭证)",
    re.IGNORECASE,
)


def read_event() -> dict[str, Any]:
    raw = sys.stdin.read()
    if not raw.strip():
        return {}
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return {"raw_stdin": raw}
    return value if isinstance(value, dict) else {"payload": value}


def write_invocation_marker(event: dict[str, Any]) -> None:
    marker = os.environ.get("LOOP_ENGINEERING_INVOCATION_MARKER")
    if not marker:
        return
    path = Path(marker)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "event": str(event.get("hook_event_name") or "Stop"),
        "script": str(Path(__file__).resolve()),
        "run_id": str(event.get("run_id") or os.environ.get("LOOP_ENGINEERING_RUN_ID") or ""),
        "top_level_keys": sorted(event.keys()),
    }
    receipt = event.get("loop_engineering_receipt")
    decision = event.get("loop_engineering_decision")
    if isinstance(receipt, dict):
        payload["receipt"] = receipt
    if isinstance(decision, dict):
        payload["decision"] = decision
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=True) + "\n")


def text_of(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "\n".join(text_of(item) for item in value if item is not None)
    if isinstance(value, dict):
        for key in ("text", "content", "message", "last_agent_message", "last_assistant_message"):
            if key in value:
                return text_of(value[key])
    return ""


def assistant_output_text(event: dict[str, Any]) -> str:
    for key in (
        "last_agent_message",
        "last_assistant_message",
        "assistant_response",
        "output_text",
        "transcript",
    ):
        text = text_of(event.get(key))
        if text.strip():
            return text

    messages = event.get("messages")
    if isinstance(messages, list):
        for item in reversed(messages):
            if isinstance(item, dict) and str(item.get("role", "")).lower() == "assistant":
                text = text_of(item)
                if text.strip():
                    return text

    payload = event.get("payload")
    if isinstance(payload, dict):
        return assistant_output_text(payload)
    return ""


def strip_followup_payloads(text: str) -> str:
    def replace(match: re.Match[str]) -> str:
        body = match.group("body") or ""
        return "" if FOLLOWUP_PAYLOAD_RE.search(body) else match.group(0)

    without_fenced = FENCED_JSON_RE.sub(replace, text or "")
    return FOLLOWUP_JSON_LINE_RE.sub("", without_fenced)


def receipt_values(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return [item for item in value if str(item).strip()]
    if isinstance(value, tuple):
        return [item for item in value if str(item).strip()]
    if isinstance(value, str):
        return [value] if value.strip() else []
    return [value]


def completion_receipt(text: str) -> dict[str, Any]:
    matches = list(
        re.finditer(rf"(?m)(?:^|[\s。.!?；;]){re.escape(STOP_RECEIPT_MARKER)}\s*(?:$|[:：])", text or "")
    )
    if not matches:
        return {}
    surface = (text or "")[matches[-1].end() :].lstrip(" \t:：\r\n")
    if surface.startswith("```"):
        surface = re.sub(r"^```(?:json)?\s*", "", surface, count=1, flags=re.IGNORECASE)
    try:
        value, _index = json.JSONDecoder().raw_decode(surface)
    except Exception:
        return {"_parse_error": "STOP_COMPLETION_RECEIPT must be valid JSON."}
    return value if isinstance(value, dict) else {"_parse_error": "STOP_COMPLETION_RECEIPT must be a JSON object."}


def receipt_guard_reason(receipt: dict[str, Any]) -> str:
    if not receipt:
        return ""
    if receipt.get("_parse_error"):
        return str(receipt["_parse_error"])

    status = str(receipt.get("status") or receipt.get("task_status") or "").strip().lower()
    verification = receipt_values(receipt.get("verification") or receipt.get("verified") or receipt.get("tests"))
    open_items = receipt_values(
        receipt.get("open_items")
        or receipt.get("remaining_items")
        or receipt.get("unresolved_actions")
        or receipt.get("todo")
    )
    blockers = receipt_values(receipt.get("blockers") or receipt.get("external_blockers"))

    if not status:
        return "completion receipt status is missing"
    if status in HUMAN_BLOCKED_STATUSES and blockers:
        if not verification:
            return "human blocker receipt has no verification evidence"
        return ""
    if status and status not in COMPLETE_STATUSES:
        return "completion receipt status is not complete"
    if open_items and not blockers:
        return "completion receipt lists unresolved actions without a human blocker"
    if blockers and status in COMPLETE_STATUSES:
        return "completion receipt claims completion but still lists blockers"
    if status in COMPLETE_STATUSES and not verification:
        return "completion receipt claims completion but has no verification evidence"
    return ""


def text_guard_reason(text: str) -> str:
    scan_text = strip_followup_payloads(text)
    if HUMAN_BLOCKER_RE.search(scan_text):
        return ""
    for pattern in RESOLVED_PENDING_SPANS:
        scan_text = pattern.sub(" ", scan_text)
    if INCOMPLETE_RE.search(scan_text):
        return "final answer contains unresolved current-task work"
    return ""


def scope_id(event: dict[str, Any]) -> str:
    for key in ("turn_id", "conversation_id", "session_id"):
        value = str(event.get(key) or "").strip()
        if value:
            return f"{key}:{value}"
    return "scope:default"


def state_file() -> Path:
    configured = os.environ.get("LOOP_ENGINEERING_STATE_FILE")
    if configured:
        return Path(configured)
    base = Path(os.environ.get("LOOP_ENGINEERING_STATE_DIR") or tempfile.gettempdir())
    return base / "loop_engineering_stop_guard_state.json"


def load_state() -> dict[str, Any]:
    path = state_file()
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_state(state: dict[str, Any]) -> None:
    path = state_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def fingerprint(text: str) -> str:
    normalized = re.sub(r"\s+", " ", text).strip()
    return hashlib.sha256(normalized[:4000].encode("utf-8")).hexdigest()[:16]


def loop_suppressed(event: dict[str, Any], text: str, reason: str) -> bool:
    max_per_response = int(os.environ.get("LOOP_ENGINEERING_MAX_PER_RESPONSE", "1"))
    max_per_scope = int(os.environ.get("LOOP_ENGINEERING_MAX_PER_SCOPE", "3"))
    state = load_state()
    guard = state.setdefault("stop_auto_continue_guard", {})
    scope = guard.setdefault(scope_id(event), {"total": 0, "fingerprints": {}})
    fingerprints = scope.setdefault("fingerprints", {})
    item = fingerprints.setdefault(fingerprint(text), {"count": 0, "reason": reason[:240]})
    item["count"] = int(item.get("count") or 0) + 1
    scope["total"] = int(scope.get("total") or 0) + 1
    save_state(state)
    return item["count"] > max_per_response or scope["total"] > max_per_scope


def pending_base_key(key: str) -> str:
    for marker in ("@session:", "@turn:"):
        if marker in key:
            return key.split(marker, 1)[0]
    return key


def pending_owned_by_event(key: str, value: dict[str, Any], event: dict[str, Any]) -> bool:
    current_session = str(event.get("session_id") or event.get("conversation_id") or "").strip()
    current_turn = str(event.get("turn_id") or "").strip()
    owner_scope = str(value.get("owner_scope") or "").strip()
    if owner_scope:
        if owner_scope.startswith("session:"):
            return bool(current_session and owner_scope == f"session:{current_session}")
        if owner_scope.startswith("turn:"):
            return bool(current_turn and owner_scope == f"turn:{current_turn}")
    session_id = str(value.get("session_id") or "").strip()
    if session_id:
        return bool(current_session and session_id == current_session)
    turn_id = str(value.get("turn_id") or "").strip()
    if turn_id:
        return bool(current_turn and turn_id == current_turn)
    if "@session:" in key:
        return bool(current_session and key.split("@session:", 1)[1] == current_session)
    if "@turn:" in key:
        return bool(current_turn and key.split("@turn:", 1)[1] == current_turn)
    return not bool(current_session or current_turn)


def pending_items(event: dict[str, Any] | None = None) -> dict[str, Any]:
    pending = load_state().get("pending")
    if not isinstance(pending, dict):
        return {}
    if not event:
        return pending
    return {
        key: value
        for key, value in pending.items()
        if isinstance(value, dict) and pending_owned_by_event(key, value, event)
    }


def pending_guard_reason(pending: dict[str, Any], receipt: dict[str, Any]) -> str:
    if not pending:
        return ""
    blockers = receipt_values(receipt.get("blockers") if receipt else None)
    if blockers:
        return ""
    lines = ["pending hook state must be addressed before final completion"]
    for key, value in pending.items():
        reason = value.get("reason") if isinstance(value, dict) else ""
        lines.append(f"- {key}: {reason}")
    return "\n".join(lines)


def allow_decision(receipt: dict[str, Any], pending: dict[str, Any]) -> dict[str, Any]:
    status = str(receipt.get("status") or receipt.get("task_status") or "").strip().lower() if receipt else ""
    return {
        "behavior": "allow",
        "reason": "completion receipt accepted" if receipt else "no unresolved final-answer debt",
        "receipt_status": status,
        "pending_count": len(pending),
    }


def block_decision(reason: str, receipt: dict[str, Any], pending: dict[str, Any]) -> dict[str, Any]:
    status = str(receipt.get("status") or receipt.get("task_status") or "").strip().lower() if receipt else ""
    return {
        "behavior": "block",
        "reason": reason,
        "receipt_status": status,
        "pending_count": len(pending),
    }


def block(runtime: str, reason: str) -> int:
    message = "[HOOK:LOOP_ENGINEERING]\n" + reason
    if runtime == "claude":
        print(message, file=sys.stderr)
        return 2
    print(json.dumps({"decision": "block", "reason": message}, ensure_ascii=False))
    return 0


def main() -> int:
    runtime = os.environ.get("LOOP_ENGINEERING_RUNTIME", "codex").strip().lower()
    event = read_event()
    text = assistant_output_text(event)

    receipt = completion_receipt(text)
    pending = pending_items(event)
    pending_reason = pending_guard_reason(pending, receipt)
    reason = pending_reason or receipt_guard_reason(receipt) or ("" if receipt else text_guard_reason(text))
    event["loop_engineering_receipt"] = receipt
    event["loop_engineering_decision"] = block_decision(reason, receipt, pending) if reason else allow_decision(receipt, pending)
    write_invocation_marker(event)
    if not reason:
        return 0

    if not pending_reason and loop_suppressed(event, text, reason):
        return 0
    return block(runtime, reason)


if __name__ == "__main__":
    raise SystemExit(main())
