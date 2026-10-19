#!/usr/bin/env python3
"""Stop hook loop guard: prevents infinite auto-continue cycles by tracking
fingerprints and per-scope counters.

Also provides stop_block / stop_continue_payload output helpers.

Extracted from stop_guard.py to reduce the 935-line monolith.
"""

from __future__ import annotations

import hashlib
import re

from hook_common import (
    emit_json,
    hook_scope_id,
    load_state,
    save_state,
    state_lock,
)


# --- Constants ---

MAX_AUTO_CONTINUE_PER_RESPONSE = 1
MAX_AUTO_CONTINUE_PER_SCOPE = 3


# --- Fingerprinting ---

def _text_fingerprint(text: str) -> str:
    normalized = re.sub(r"\s+", " ", text).strip()
    return hashlib.sha256(normalized[:4000].encode("utf-8")).hexdigest()[:16]


# --- Loop guard ---

def auto_continue_loop_guard(event: dict, text: str, reason: str) -> str:
    """Returns non-empty string to suppress auto-continue (loop detected)."""
    scope = hook_scope_id(event)
    fingerprint = _text_fingerprint(text)
    with state_lock():
        state = load_state()
        guard = state.setdefault("stop_auto_continue_guard", {})
        scope_state = guard.setdefault(scope, {"total": 0, "fingerprints": {}})
        fingerprints = scope_state.setdefault("fingerprints", {})
        item = fingerprints.setdefault(fingerprint, {"count": 0, "reason": reason[:240]})
        item["count"] = int(item.get("count") or 0) + 1
        scope_state["total"] = int(scope_state.get("total") or 0) + 1
        save_state(state)
        if item["count"] > MAX_AUTO_CONTINUE_PER_RESPONSE:
            return (
                "Repeated identical assistant final response already triggered auto-continue once. "
                "Suppressing another Stop block to avoid a continuation loop."
            )
        if scope_state["total"] > MAX_AUTO_CONTINUE_PER_SCOPE:
            return (
                "Stop auto-continue triggered too many times in the same scope. "
                "Suppressing another Stop block to avoid a continuation loop."
            )
    return ""


# --- Output helpers ---

def stop_continue_payload(system_message: str = "") -> dict:
    payload = {"continue": True}
    if system_message:
        payload["systemMessage"] = system_message
    return payload


def stop_block_payload(reason: str) -> dict:
    system_message = reason.strip() or "Continue the current turn before stopping."
    return {
        "decision": "block",
        "reason": system_message,
    }


def stop_block(reason: str) -> int:
    """Block Stop so suggested follow-up work is auto-adopted and executed."""
    system_message = "[HOOK:STOP_GUARD]\n" + reason
    return emit_json(stop_block_payload(system_message))


def loop_guard_continue(reason: str) -> int:
    return 0
