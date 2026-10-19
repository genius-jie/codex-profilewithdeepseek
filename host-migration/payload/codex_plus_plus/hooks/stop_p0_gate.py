#!/usr/bin/env python3
"""Stop hook P0 next-step gate: enforces first-principles continuation decisions
after completed receipts.

Extracted from stop_guard.py to reduce the 935-line monolith.
"""

from __future__ import annotations

import os
import re
from pathlib import Path


# --- Constants ---

P0_NEXT_STEP_MARKER = "P0_NEXT_STEP_RECOMMENDATION"
P0_STOP_EXPLANATION_FIELDS = ("best_candidate_considered", "rejected_reason", "evidence_basis")
P0_STOP_VALUES = {"", "none", "null", "[]", "n/a", "na", "无", "没有", "stop", "停止", "收口"}
P0_SAFE_DECISIONS = {"continue_once"}

COMPLETE_RECEIPT_STATUSES = {"complete", "completed", "done", "success", "pass", "passed", "已完成", "完成"}
HUMAN_BLOCKED_RECEIPT_STATUSES = {"blocked", "wait_human", "human_blocked", "blocked_by_human", "阻断", "等待人工"}
EMPTY_RECEIPT_VALUES = {"", "none", "null", "[]", "n/a", "na", "无", "没有", "无待办", "无剩余"}


# --- Helper functions ---

def _is_codex_plusplus_home() -> bool:
    codex_home = Path(os.environ.get("CODEX_HOME") or Path(__file__).absolute().parent.parent)
    normalized = str(codex_home).replace("/", "\\").lower()
    return "\\codexplusplusprofile\\.codex" in normalized or "codexplusplusprofile" in normalized


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


def _receipt_lookup(receipt: dict, *keys: str) -> object:
    lowered = {str(key).lower(): value for key, value in receipt.items()}
    for key in keys:
        if key in receipt:
            return receipt[key]
        value = lowered.get(key.lower())
        if value is not None:
            return value
    return None


def _parse_int(value: object) -> int | None:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return int(value)
    text = str(value or "").strip()
    match = re.search(r"-?\d+", text)
    return int(match.group(0)) if match else None


def _parse_bool(value: object) -> bool | None:
    if isinstance(value, bool):
        return value
    text = str(value or "").strip().lower()
    if text in {"true", "1", "yes", "y", "是", "允许"}:
        return True
    if text in {"false", "0", "no", "n", "否", "不允许"}:
        return False
    return None


# --- Main gate ---

def p0_next_step_guard_reason(receipt: dict) -> str:
    """Require a Codex-only first-principles P0 next-step decision after completion."""
    if _is_codex_plusplus_home():
        return ""
    status = str(receipt.get("status") or receipt.get("task_status") or "").strip().lower()
    blockers = _receipt_values(receipt.get("blockers") or receipt.get("external_blockers"))
    verification = _receipt_values(receipt.get("verification") or receipt.get("verified") or receipt.get("tests"))
    open_items = _receipt_values(
        receipt.get("open_items")
        or receipt.get("remaining_items")
        or receipt.get("unresolved_actions")
        or receipt.get("todo")
    )
    if status in HUMAN_BLOCKED_RECEIPT_STATUSES or blockers or open_items or not verification:
        return ""

    score = _parse_int(_receipt_lookup(receipt, "next_step_score", "后续建议评分", "next_step_score_value"))
    auto_continue = _parse_bool(_receipt_lookup(receipt, "auto_continue_allowed"))
    budget = _parse_int(_receipt_lookup(receipt, "continuation_budget_remaining"))
    decision = str(_receipt_lookup(receipt, "next_step_decision") or "").strip().lower()
    recommendation = str(_receipt_lookup(receipt, P0_NEXT_STEP_MARKER, "p0_next_step_recommendation") or "").strip()
    reason = str(_receipt_lookup(receipt, "first_principles_reason") or "").strip()

    missing = []
    if score is None:
        missing.append("后续建议评分/next_step_score")
    if auto_continue is None:
        missing.append("auto_continue_allowed")
    if budget is None:
        missing.append("continuation_budget_remaining")
    if not decision:
        missing.append("next_step_decision")
    if not recommendation:
        missing.append(P0_NEXT_STEP_MARKER)
    if not reason:
        missing.append("first_principles_reason")
    if missing:
        return (
            "P0_NEXT_STEP_GATE_MISSING: completed Codex receipts must include first-principles P0 next-step fields: "
            + ", ".join(missing)
            + ". Fill the fields; do not execute a new task merely to satisfy this gate."
        )

    stopish = decision == "stop" or recommendation.lower() in P0_STOP_VALUES
    if stopish:
        stop_missing = [field for field in P0_STOP_EXPLANATION_FIELDS if not str(_receipt_lookup(receipt, field) or "").strip()]
        if stop_missing:
            return (
                "P0_NEXT_STEP_STOP_EXPLANATION_MISSING: stop/no-next-step receipts must include "
                "best_candidate_considered, rejected_reason, and evidence_basis. Missing: "
                + ", ".join(stop_missing)
                + ". Explain the best P0 candidate considered and why it is not allowed or not worth continuing now."
            )

    if score < 60:
        return ""
    if recommendation.lower() in P0_STOP_VALUES:
        return "P0_NEXT_STEP_GATE_MISMATCH: score >=60 requires a concrete P0_NEXT_STEP_RECOMMENDATION."
    if score >= 80 and auto_continue and budget > 0 and decision in P0_SAFE_DECISIONS:
        return (
            "P0_NEXT_STEP_CONTINUE_ONCE: continue exactly one bounded step now: "
            f"{recommendation}. First-principles reason: {reason}. "
            "Before acting, confirm it stays inside the current user-approved scope, has no new blast radius, "
            "needs no human approval, has no W9/hard-gate FAIL, and will not trigger a new P_PIPELINE. "
            "After that one step, decrement continuation_budget_remaining or set auto_continue_allowed=false."
        )
    return ""
