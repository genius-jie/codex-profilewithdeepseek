#!/usr/bin/env python3
"""Stop hook text signal analysis: pattern matching for completion, incompletion,
deferred actions, human blockers, and semantic action debt.

Extracted from stop_guard.py to reduce the 935-line monolith.
"""

from __future__ import annotations

import re


# --- Pattern definitions ---

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
    r"发现", r"看到", r"检出", r"扫描到", r"识别到",
    r"残留", r"坏链接", r"断链", r"异常", r"问题", r"风险", r"报错", r"失败",
]

DEFERRED_TERMS = [
    r"未", r"没有", r"没", r"待", r"需要", r"需", r"仍需", r"还需",
    r"建议", r"后续", r"下一步", r"接下来", r"暂未", r"这次不",
]

ACTION_TERMS = [
    r"处理", r"清理", r"修复", r"移除", r"删除", r"归档",
    r"治理", r"补齐", r"更新", r"校验", r"验证", r"继续", r"解决", r"收口", r"动",
]

FOLLOWUP_SCORE_PATTERNS = [
    r"后续建议评分\s*[:：]\s*\d+",
    r"next_step_score\s*[:=]\s*\d+",
]

RESOLVED_OR_INFO_ONLY_PATTERNS = [
    r"\bpending_[a-z0-9_]+\b.{0,24}(会被识别|已被识别|用于识别|避免.{0,8}漏判)",
    r"已处理", r"已经处理", r"已清理", r"已经清理",
    r"已修复", r"已经修复", r"已移除", r"已经移除",
    r"已删除", r"已经删除", r"已归档", r"已经归档",
    r"已解决", r"已经解决", r"已根治", r"已经根治",
    r"无需处理", r"不用处理", r"不需要处理",
    r"(根因|原因).{0,24}(是|在于|来自|不是).{0,80}(不够完整|不完整|不会主动|无法识别|不能识别|误判|漏判)",
    r"仅供参考", r"信息性",
]

RESOLVED_RESULT_PATTERNS = [
    r"(已|已经)?(解决|修复|修掉|避免|规避).{0,48}(问题|缺陷|误判|重复|重复提交|重复触发)",
    r"(问题|缺陷|误判|重复|重复提交|重复触发).{0,48}(已|已经)?(解决|修复|修掉|避免|规避)",
]

NO_UNRESOLVED_WORK_PATTERNS = [
    r"\bNO[_ -]?PENDING[_ -]?WORK\b",
    r"\bNO[_ -]?UNRESOLVED[_ -]?(WORK|ACTIONS|ITEMS)\b",
    r"(不再|不会再|不会|不应|避免).{0,24}(写入|标记|制造|产生|创建|挂起).{0,24}\bpending_[a-z0-9_]+\b",
    r"\bpending_[a-z0-9_]+\b.{0,32}(不再|不会再|不会|不应).{0,16}(写入|标记|制造|产生|创建|挂起)",
    r"无(待办|剩余|未完成|未决|阻断|开放项)",
    r"没有(实际)?(需要继续执行的)?(未完成|待办|未决|剩余)(任务|事项|工作|动作)?",
    r"(当前|本轮|这轮).{0,12}(没有|无).{0,12}(未完成|待办|未决|剩余|需要继续执行)",
    r"(不代表|不是|并非).{0,24}(未完成|待办|未决|剩余|需要继续执行)",
    r"(只是|仅是|只会).{0,24}(交给|给到|发送到).{0,24}Follow-up.{0,24}(面板|自动化|Gate)",
    r"(没有|未|不)(做|进行)?\s*(Git|git)\s*(提交|commit|push|推送)",
    r"(不用|无需|不需要|本轮不|本次不).{0,12}(Git|git).{0,12}(提交|commit|push|推送)",
    r"不应报\s*WAIT_HUMAN_BLOCKER",
    r"无需(继续执行|处理|人工介入|等待人工)",
    r"(没有|无)(任何)?(遗留|残留)(文件|目录|产物|事项|问题|风险|动作)?",
    # A zero-valued health counter is evidence about the observed run, not an
    # instruction to process the named failure class. Keep this narrow so a
    # real phrase such as "未处理异常仍有 1" remains actionable.
    r"(?:未处理|未捕获)异常(?:[_ -]?(?:数量|计数|count))?\s*[:=：]?\s*(?:0|零|none|false)\b",
    r"unhandled[_ -]?(?:exception|error)s?(?:[_ -]?(?:count|数量|计数))?\s*[:=：]?\s*(?:0|零|none|false)\b",
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
        r"`*\bpending(?:_[a-z0-9_]+)?\b`*\s*(?:已经|已)\s*"
        r"(?:(?!(?:但|不过|仍需|还需|需要|待处理|\bTODO\b|`*\bpending(?:_[a-z0-9_]+)?\b`*)).){0,96}?"
        r"(?:清理|清掉|清空|清账|解除|关闭|清除)(?:了)?"
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

PRIORITY_TAXONOMY_PATTERNS = [
    r"(单\s*P0|P0\s*/\s*P1\s*/\s*P2\s*/\s*P3|P1\s*/\s*P2\s*/\s*P3|\bP[0-3]\b).{0,48}(定义|表示|含义|语义|分类|标签|优先级|理由|设计|不是|只是|不代表|唯一焦点|阻断点|非阻断)",
    r"(定义|表示|含义|语义|分类|标签|优先级|理由|设计|不是|只是|不代表|唯一焦点|阻断点|非阻断).{0,48}(单\s*P0|P0\s*/\s*P1\s*/\s*P2\s*/\s*P3|P1\s*/\s*P2\s*/\s*P3|\bP[0-3]\b)",
]


# --- Analysis functions ---

def matches_any(text: str, patterns: list[str]) -> bool:
    return any(re.search(pattern, text, re.IGNORECASE | re.DOTALL) for pattern in patterns)


def clauses(text: str) -> list[str]:
    return [part.strip() for part in re.split(r"[。！？!?；;\n]+", text) if part.strip()]


def is_info_only_clause(clause: str) -> bool:
    return (
        matches_any(clause, GUARD_RESULT_EXAMPLE_PATTERNS)
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
