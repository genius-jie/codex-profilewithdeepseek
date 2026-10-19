#!/usr/bin/env python3
"""Thin stop hook that asks Codex to close pending governance work."""

from __future__ import annotations

import json
import hashlib
import os
import re
from pathlib import Path

from hook_common import (
    emit_json,
    hook_scope_id,
    hook_self_audit,
    load_state,
    pending_base_key,
    pending_owned_by_event,
    read_event,
    reconcile_superseded_permission_review,
    record_hook_evolution_candidates,
    record_hook_run,
    run_safely,
    save_state,
    state_lock,
)


MAX_AUTO_CONTINUE_PER_RESPONSE = 1
MAX_AUTO_CONTINUE_PER_SCOPE = 3
SESSION_LOG_FALLBACK_LIMIT = 3
STOP_RECEIPT_MARKER = "STOP_COMPLETION_RECEIPT"
P0_NEXT_STEP_MARKER = "P0_NEXT_STEP_RECOMMENDATION"
P0_STOP_EXPLANATION_FIELDS = ("best_candidate_considered", "rejected_reason", "evidence_basis")
MAX_INLINE_RECEIPT_CHARS = 1800
MAX_INLINE_RECEIPT_LINE_CHARS = 1800
MAX_RECEIPT_FILE_BYTES = 65536
PROPOSED_PLAN_RE = re.compile(r"<proposed_plan>\s*(?P<body>.*?)\s*</proposed_plan>", re.IGNORECASE | re.DOTALL)
MEMORY_CITATION_RE = re.compile(r"<oai-mem-citation>.*?</oai-mem-citation>", re.IGNORECASE | re.DOTALL)
COMPLETE_RECEIPT_STATUSES = {"complete", "completed", "done", "success", "pass", "passed", "已完成", "完成"}
HUMAN_BLOCKED_RECEIPT_STATUSES = {"blocked", "wait_human", "human_blocked", "blocked_by_human", "阻断", "等待人工"}
EMPTY_RECEIPT_VALUES = {"", "none", "null", "[]", "n/a", "na", "无", "没有", "无待办", "无剩余"}
P0_STOP_VALUES = {"", "none", "null", "[]", "n/a", "na", "无", "没有", "stop", "停止", "收口"}
P0_SAFE_DECISIONS = {"continue_once"}

_CURRENT_BLOCKING_FAILURE_CLASSES = {
    "CURRENT_TASK_TOOL_FAILURE",
    "CURRENT_TASK_BUSINESS_FAILURE",
    "FORMAL_CONTROL_BLOCKER",
}
_NON_BLOCKING_FAILURE_CLASSES = {
    "EXPECTED_HISTORICAL_FAILURE",
    "SUPERSEDED_OPERATIONAL_FAILURE",
    "CANDIDATE_DISPOSITION_PENDING",
}


INCOMPLETE_PATTERNS = [
    r"\bBLOCKER\b",
    r"\bBLOCKED\b",
    r"\bPARTIAL\b",
    r"\bTODO\b",
    r"\bpending\b",
    r"\bpending_[a-z0-9_]+\b",
    r"未完成",
    r"没有完成",
    r"尚未完成",
    r"只完成",
    r"完成一部分",
    r"部分完成",
    r"未成功",
    r"没有成功",
    r"没有落地",
    r"不能完成",
    r"无法完成",
    r"被阻断",
    r"阻断态",
    r"建议中断",
    r"建议暂停",
    r"建议停止",
    r"建议先到这里",
    r"建议到此为止",
    r"建议后续继续",
    r"后续.*继续执行",
    r"继续迁移",
]

COMPLETE_PATTERNS = [
    r"\bDONE\b",
    r"\bCOMPLETED\b",
    r"已完成",
    r"已经完成",
    r"处理完成",
    r"修复完成",
    r"验证通过",
    r"已验证",
    r"已解决",
]

ACTION_DEFERRED_PATTERNS = [
    r"建议下一步",
    r"下一步建议",
    r"下一步可以",
    r"下一步.{0,16}(值得|最值得|做|执行)",
    r"后续建议",
    r"建议后续",
    r"接下来建议",
    r"下一轮.{0,24}(我会|我来|将|继续|迁移|落地|整理|统一管理|补齐|更新|处理|执行)",
    r"下次.{0,24}(我会|我来|将|继续|迁移|落地|整理|统一管理|补齐|更新|处理|执行)",
    r"(之后|后面).{0,24}(我会|我来|将|继续|迁移|落地|整理|统一管理|补齐|更新|处理|执行)",
    r"另外说明",
    r"补充说明",
    r"额外提示",
    r"顺手发现",
    r"还有一点",
    r"可以继续",
    r"可继续",
]

HUMAN_BLOCKER_PATTERNS = [
    r"WAIT_HUMAN",
    r"需要人工",
    r"需要人类",
    r"需要用户",
    r"等待.*确认",
    r"等待.*授权",
    r"验证码",
    r"登录",
    r"权限",
    r"Access to the path .* is denied",
    r"Permission denied",
    r"被占用",
    r"关闭.*窗口",
    r"外部.*阻断",
]

DISCOVERY_TERMS = [
    r"发现",
    r"看到",
    r"检出",
    r"扫描到",
    r"识别到",
    r"残留",
    r"坏链接",
    r"断链",
    r"异常",
    r"问题",
    r"风险",
    r"报错",
    r"失败",
]

DEFERRED_TERMS = [
    r"未",
    r"没有",
    r"没",
    r"待",
    r"需要",
    r"需",
    r"仍需",
    r"还需",
    r"建议",
    r"后续",
    r"下一步",
    r"接下来",
    r"暂未",
    r"这次不",
]

FOLLOWUP_SCORE_PATTERNS = [
    r"后续建议评分\s*[:：]\s*\d+",
    r"next_step_score\s*[:=]\s*\d+",
]

ACTION_TERMS = [
    r"处理",
    r"清理",
    r"修复",
    r"移除",
    r"删除",
    r"归档",
    r"治理",
    r"补齐",
    r"更新",
    r"校验",
    r"验证",
    r"继续",
    r"解决",
    r"收口",
    r"动",
]

RESOLVED_OR_INFO_ONLY_PATTERNS = [
    r"\bpending_[a-z0-9_]+\b.{0,24}(会被识别|已被识别|用于识别|避免.{0,8}漏判)",
    r"已处理",
    r"已经处理",
    r"已清理",
    r"已经清理",
    r"已修复",
    r"已经修复",
    r"已移除",
    r"已经移除",
    r"已删除",
    r"已经删除",
    r"已归档",
    r"已经归档",
    r"已解决",
    r"已经解决",
    r"无需处理",
    r"不用处理",
    r"不需要处理",
    r"仅供参考",
    r"信息性",
]

RESOLVED_RESULT_PATTERNS = [
    r"(已|已经)?(解决|修复|修掉|避免|规避).{0,48}(问题|缺陷|误判|重复|重复提交|重复触发)",
    r"(问题|缺陷|误判|重复|重复提交|重复触发).{0,48}(已|已经)?(解决|修复|修掉|避免|规避)",
]

NO_UNRESOLVED_WORK_PATTERNS = [
    r"\bNO[_ -]?PENDING[_ -]?WORK\b",
    r"\bNO[_ -]?UNRESOLVED[_ -]?(WORK|ACTIONS|ITEMS)\b",
    r"无(待办|剩余|未完成|未决|阻断|开放项)",
    r"没有(实际)?(需要继续执行的)?(未完成|待办|未决|剩余)(任务|事项|工作|动作)?",
    r"(当前|本轮|这轮).{0,12}(没有|无).{0,12}(未完成|待办|未决|剩余|需要继续执行)",
    r"不应报\s*WAIT_HUMAN_BLOCKER",
    r"无需(继续执行|处理|人工介入|等待人工)",
]

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
    re.compile(
        r"(?:已|已经)?\s*(?:清理|清掉|清空|清账|解除|关闭)(?:了)?"
        r"\s*(?:的\s*)?\bpending(?:_[a-z0-9_]+)?\b",
        re.IGNORECASE,
    ),
)


def mask_resolved_pending_spans(text: str) -> str:
    remaining = text
    for pattern in RESOLVED_PENDING_SPANS:
        remaining = pattern.sub(" ", remaining)
    return remaining

GUARD_RESULT_EXAMPLE_PATTERNS = [
    r"(验证结果|验证样本|测试样本|负例样本|回归样本)",
    r"(仍会|应该|应当|预期).{0,12}触发\s*Stop\s*阻断",
    r"(这种|这类|该|上述).{0,32}(文本|样本|负例|回归).{0,16}(仍会|仍然会|应该|应当|预期).{0,16}(阻断|放行|ALLOW|BLOCK)",
    r"(：|:)\s*(放行|继续阻断|阻断|PASS|BLOCK)\s*$",
    r"\b(normal|plusplus):[a-z0-9_ -]+:\s*(PASS|BLOCK)\b",
    r"\b(no_pending_marker|chinese_no_open_work|real_todo|real_pending|plain_done)\b",
]

GUARD_DIAGNOSTIC_PATTERNS = [
    r"(?:STOP_GUARD|收口检查|Stop\s*hook).{0,80}(?:把|将).{0,80}"
    r"(?:判为|判定为|识别为|当作).{0,80}(?:未结束|后续工作|待办|执行)",
]

BEHAVIOR_CONTRACT_PATTERNS = [
    r"后续.{0,80}(?:同一会话|same session).{0,80}(?:会|将).{0,40}(?:复用|重用).{0,80}(?:回执|上下文)",
    r"(?:快照|身份|来源).{0,80}(?:不能|不可).{0,48}(?:绕过|复用)",
]

PRIORITY_TAXONOMY_PATTERNS = [
    r"(单\s*P0|P0\s*/\s*P1\s*/\s*P2\s*/\s*P3|P1\s*/\s*P2\s*/\s*P3|\bP[0-3]\b).{0,48}(定义|表示|含义|语义|分类|标签|优先级|理由|设计|不是|只是|不代表|唯一焦点|阻断点|非阻断)",
    r"(定义|表示|含义|语义|分类|标签|优先级|理由|设计|不是|只是|不代表|唯一焦点|阻断点|非阻断).{0,48}(单\s*P0|P0\s*/\s*P1\s*/\s*P2\s*/\s*P3|P1\s*/\s*P2\s*/\s*P3|\bP[0-3]\b)",
]


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
    codex_home = Path(os.environ.get("CODEX_HOME") or (Path.home() / ".codex"))
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
    ids = [
        str(value)
        for value in (
            event.get("session_id"),
            event.get("conversation_id"),
            event.get("conversationId"),
            event.get("thread_id"),
            event.get("threadId"),
            event.get("turn_id"),
            event.get("turnId"),
        )
        if value
    ]
    candidates: list[Path] = []
    candidates.extend(_event_path_candidates(event))
    for root in _session_roots():
        if not root.exists():
            continue
        files = list(root.rglob("rollout-*.jsonl"))
        matches = [path for path in files if any(value in path.name or value in str(path) for value in ids)]
        candidates.extend(matches)
        if not matches:
            candidates.extend(sorted(files, key=lambda path: path.stat().st_mtime, reverse=True)[:SESSION_LOG_FALLBACK_LIMIT])
    unique = list(dict.fromkeys(candidates))
    return sorted(unique, key=lambda path: path.stat().st_mtime, reverse=True)


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


def matches_any(text: str, patterns: list[str]) -> bool:
    return any(re.search(pattern, text, re.IGNORECASE | re.DOTALL) for pattern in patterns)


def clauses(text: str) -> list[str]:
    return [part.strip() for part in re.split(r"[。！？!?；;\n]+", text) if part.strip()]


def is_info_only_clause(clause: str) -> bool:
    return (
        matches_any(clause, GUARD_RESULT_EXAMPLE_PATTERNS)
        or matches_any(clause, GUARD_DIAGNOSTIC_PATTERNS)
        or matches_any(clause, BEHAVIOR_CONTRACT_PATTERNS)
        or matches_any(clause, NO_UNRESOLVED_WORK_PATTERNS)
        or matches_any(clause, RESOLVED_OR_INFO_ONLY_PATTERNS)
        or is_resolved_result_clause(clause)
        or matches_any(clause, PRIORITY_TAXONOMY_PATTERNS)
    )


def is_resolved_result_clause(clause: str) -> bool:
    if re.search(r"(还需|仍需|需要|需|待|未|没有|没|建议|后续|下一步|接下来).{0,16}(解决|修复|处理|清理|规避|避免)", clause, re.IGNORECASE | re.DOTALL):
        return False
    return matches_any(clause, RESOLVED_RESULT_PATTERNS)


def has_action_deferred_signal(text: str) -> bool:
    for clause in clauses(text):
        if is_info_only_clause(clause):
            continue
        if matches_any(clause, FOLLOWUP_SCORE_PATTERNS) or matches_any(clause, ACTION_DEFERRED_PATTERNS):
            return True
    return False


def has_unresolved_work_signal(text: str) -> bool:
    for clause in clauses(text):
        if is_info_only_clause(clause):
            continue
        remaining = mask_resolved_pending_spans(clause)
        if matches_any(remaining, INCOMPLETE_PATTERNS):
            return True
    return False


def has_semantic_action_debt(text: str) -> bool:
    """Detect unresolved actionable discoveries by intent, not only fixed wording."""
    for clause in clauses(text):
        if is_info_only_clause(clause):
            continue
        has_discovery = matches_any(clause, DISCOVERY_TERMS)
        has_deferred = matches_any(clause, DEFERRED_TERMS)
        has_action = matches_any(clause, ACTION_TERMS)
        if has_discovery and has_deferred and has_action:
            return True
        if has_discovery and re.search(r"(未|没有|没|待|需).{0,8}(处理|清理|修复|移除|删除|归档|治理|收口|动)", clause):
            return True
        if re.search(r"(建议|后续|下一步|接下来|下一轮|下次|之后|后面).{0,24}(处理|清理|修复|移除|删除|归档|治理|补齐|更新|校验|验证|继续|解决|收口|迁移|落地|统一管理)", clause):
            return True
    return False


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
        value, index = json.JSONDecoder().raw_decode(surface)
    except Exception:
        return {"_parse_error": "STOP_COMPLETION_RECEIPT must be valid JSON."}
    if not isinstance(value, dict):
        return {"_parse_error": "STOP_COMPLETION_RECEIPT must be a JSON object."}
    inline_json = surface[:index].strip()
    if not value.get("receipt_path") and (
        len(inline_json) > MAX_INLINE_RECEIPT_CHARS
        or any(len(line) > MAX_INLINE_RECEIPT_LINE_CHARS for line in inline_json.splitlines())
    ):
        return {
            "_parse_error": (
                "STOP_COMPLETION_RECEIPT inline JSON is too large for the final Markdown renderer; "
                "write the full receipt to a JSON file and output only {\"receipt_path\":\"<absolute path>\"}."
            )
        }
    if value.get("receipt_path"):
        return _load_receipt_path(value.get("receipt_path"))
    return value


def _is_codex_plusplus_home() -> bool:
    codex_home = Path(os.environ.get("CODEX_HOME") or (Path.home() / ".codex"))
    normalized = str(codex_home).replace("/", "\\").lower()
    return "\\codexplusplusprofile\\.codex" in normalized or "codexplusplusprofile" in normalized


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


def p0_next_step_guard_reason(receipt: dict) -> str:
    """Deprecated compatibility hook: Stop no longer generates continuation work."""

    return ""


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
    if status and status not in COMPLETE_RECEIPT_STATUSES:
        return (
            "STOP_COMPLETION_RECEIPT status is not complete; correct the current completion "
            "claim or record a formal current blocker."
        )
    if open_items and not blockers:
        return (
            "STOP_COMPLETION_RECEIPT lists unresolved current actions without a formal "
            "blocker; correct the completion claim or bind the current work explicitly."
        )
    if blockers and status in COMPLETE_RECEIPT_STATUSES:
        return "STOP_COMPLETION_RECEIPT claims completion but still lists blockers; resolve the mismatch before stopping."
    if status in COMPLETE_RECEIPT_STATUSES and not verification:
        return "STOP_COMPLETION_RECEIPT claims completion but has no verification evidence."
    return ""


def _pending_is_actionable_for_event(key: str, value: dict, event: dict) -> bool:
    if pending_base_key(key) == "third_party_submodule_skipped":
        return False
    if not pending_owned_by_event(key, value, event):
        return False
    failure_class = str(
        value.get("failure_class")
        or value.get("failure_disposition")
        or value.get("disposition")
        or ""
    ).strip().upper()
    if failure_class in _NON_BLOCKING_FAILURE_CLASSES:
        return False
    if failure_class in _CURRENT_BLOCKING_FAILURE_CLASSES:
        return True
    # Backward-compatible pending records predate failure classification. They
    # remain scoped to their owning event, but cannot be promoted across scopes.
    return True


def _is_formal_control_blocker(value: object) -> bool:
    if not isinstance(value, dict):
        return False
    return str(
        value.get("failure_class")
        or value.get("failure_disposition")
        or value.get("disposition")
        or ""
    ).strip().upper() == "FORMAL_CONTROL_BLOCKER"


def _actionable_pending_for_event(event: dict) -> dict:
    pending = load_state().get("pending") or {}
    return {
        key: value
        for key, value in pending.items()
        if _pending_is_actionable_for_event(key, value, event)
    }


def is_plan_mode_completion(text: str, event: dict | None = None) -> bool:
    """Allow official Plan Mode outputs to stop without auto-continuing."""
    matches = list(PROPOSED_PLAN_RE.finditer(text or ""))
    if not matches or not any((match.group("body") or "").strip() for match in matches):
        return False
    if "WAIT_HUMAN_BLOCKER" in text:
        return False
    actionable = _actionable_pending_for_event(event or {})
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


def completion_guard_reason(event: dict, text: str | None = None) -> str:
    text = text if text is not None else assistant_output_text(event)
    if not text:
        return ""
    receipt_reason = receipt_guard_reason(text)
    if receipt_reason:
        return receipt_reason
    receipt = _completion_receipt(text)
    if receipt:
        return ""
    # Narrative observations, historical failures, and possible next steps are
    # Evidence. They do not establish a current task, authorization, or Control
    # record, so a Stop hook must not auto-adopt them as new work.
    return ""


def _text_fingerprint(text: str) -> str:
    normalized = re.sub(r"\s+", " ", text).strip()
    return hashlib.sha256(normalized[:4000].encode("utf-8")).hexdigest()[:16]


def _auto_continue_loop_guard(event: dict, text: str, reason: str) -> str:
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
    """Block only a scoped current pending record or inconsistent completion claim."""
    system_message = "[HOOK:STOP_GUARD]\n" + reason
    return emit_json(stop_block_payload(system_message))


def loop_guard_continue(reason: str) -> int:
    return 0


def main() -> int:
    event = read_event()
    record_hook_run("Stop", event)
    reconcile_superseded_permission_review(event)
    state = load_state()
    actionable = _actionable_pending_for_event(event)
    audit_summary, audit_anomalies = hook_self_audit(event)
    output_text = assistant_output_text(event)
    if not output_text:
        audit_anomalies.append("Stop hook could not extract assistant output text; review Codex Stop event schema.")
    evolution_ready = record_hook_evolution_candidates(event, audit_summary, audit_anomalies)
    formal_control = {
        key: value
        for key, value in actionable.items()
        if _is_formal_control_blocker(value)
    }
    blocking_pending = {
        key: value for key, value in actionable.items() if key not in formal_control
    }
    if formal_control and not blocking_pending:
        if matches_any(output_text, HUMAN_BLOCKER_PATTERNS):
            return 0
        return stop_block(
            "Current formal Control blocker requires an explicit Human wait response; "
            "do not claim completion or auto-continue."
        )
    if not blocking_pending:
        completion_reason = completion_guard_reason(event, output_text)
        if completion_reason:
            loop_guard_reason = _auto_continue_loop_guard(event, output_text, completion_reason)
            if loop_guard_reason:
                return loop_guard_continue(loop_guard_reason)
            return stop_block(completion_reason)
        if audit_anomalies:
            evolution_lines = []
            if evolution_ready:
                evolution_lines.append("Ready for M8/W7 review:")
                evolution_lines.extend(f"- {item}" for item in evolution_ready)
            else:
                evolution_lines.append("Recorded as hook evolution candidate; promote only after repeated evidence.")
            return 0
        return 0

    lines = ["Pending hook state must be addressed before final completion:"]
    for key, value in blocking_pending.items():
        base_key = pending_base_key(key)
        lines.append(f"- {base_key}: {value.get('reason', '')}")
        if base_key == "pending_failure_review":
            fingerprint = value.get("command_fingerprint")
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
    return stop_block(reason)


if __name__ == "__main__":
    raise SystemExit(run_safely("Stop", main))
