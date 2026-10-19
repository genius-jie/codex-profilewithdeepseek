#!/usr/bin/env python3
"""Regression tests for the Codex Stop hook contract."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path


HOOK_DIR = Path(__file__).resolve().parents[1]
STOP_GUARD = HOOK_DIR / "stop_guard.py"

P0_LOW = (
    '"next_step_score": 30, "auto_continue_allowed": false, '
    '"continuation_budget_remaining": 0, "next_step_decision": "stop", '
    '"P0_NEXT_STEP_RECOMMENDATION": "无", '
    '"first_principles_reason": "当前目标已闭环，继续推进收益不足", '
    '"best_candidate_considered": "观察下一次真实 Stop 事件", '
    '"rejected_reason": "本轮没有真实 Stop 事件样本，继续推进会变成猜测", '
    '"evidence_basis": "已有 py_compile 与 hook 单测通过"'
)

P0_LOW_INCOMPLETE = (
    '"next_step_score": 30, "auto_continue_allowed": false, '
    '"continuation_budget_remaining": 0, "next_step_decision": "stop", '
    '"P0_NEXT_STEP_RECOMMENDATION": "无", '
    '"first_principles_reason": "当前目标已闭环，继续推进收益不足"'
)

P0_HIGH_SUGGEST = (
    '"next_step_score": 90, "auto_continue_allowed": false, '
    '"continuation_budget_remaining": 0, "next_step_decision": "suggest_only", '
    '"P0_NEXT_STEP_RECOMMENDATION": "整理 Stop hook 运行样本", '
    '"first_principles_reason": "最短反馈路径是观察真实 Stop 事件"'
)

P0_HIGH_CONTINUE = (
    '"next_step_score": 88, "auto_continue_allowed": true, '
    '"continuation_budget_remaining": 1, "next_step_decision": "continue_once", '
    '"P0_NEXT_STEP_RECOMMENDATION": "运行一次 Stop hook 合约样例", '
    '"first_principles_reason": "新增协议的核心风险在 Stop 事件边界"'
)


def _codex_home(tmp: str, kind: str = "normal") -> Path:
    if kind == "plusplus":
        return Path(tmp) / "AppData" / "Roaming" / "CodexPlusPlusProfile" / ".codex"
    return Path(tmp)


def _invoke_stop_guard(home: Path, event: dict) -> dict:
    env = os.environ.copy()
    env["CODEX_HOME"] = str(home)
    env["PYTHONPATH"] = str(HOOK_DIR)
    proc = subprocess.run(
        ["python", str(STOP_GUARD)],
        input=json.dumps(event, ensure_ascii=False),
        text=True,
        capture_output=True,
        cwd=str(HOOK_DIR),
        env=env,
        timeout=20,
        check=False,
    )
    if proc.returncode != 0:
        raise AssertionError(f"returncode={proc.returncode} stderr={proc.stderr}")
    return json.loads(proc.stdout.strip() or "{}")


def run_stop_guard(
    name: str,
    event: dict,
    session_text: str | None = None,
    pending: dict | None = None,
    codex_home_kind: str = "normal",
) -> dict:
    with tempfile.TemporaryDirectory(prefix="stop-guard-test-") as tmp:
        home = _codex_home(tmp, codex_home_kind)
        if pending is not None:
            state_dir = home / "hook-state"
            state_dir.mkdir(parents=True)
            (state_dir / "openclaw-mono-pending.json").write_text(
                json.dumps({"pending": pending}, ensure_ascii=False),
                encoding="utf-8",
            )
        if session_text is not None:
            log_dir = home / "sessions" / "2026" / "05" / "18"
            log_dir.mkdir(parents=True)
            log_path = log_dir / f"rollout-test-{name}.jsonl"
            rows = [
                {"type": "event_msg", "payload": {"type": "agent_message", "message": session_text, "phase": "final"}},
                {"type": "event_msg", "payload": {"type": "task_complete", "last_agent_message": session_text}},
            ]
            log_path.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows), encoding="utf-8")

        try:
            return _invoke_stop_guard(home, event)
        except AssertionError as exc:
            raise AssertionError(f"{name}: {exc}") from exc


def run_stop_guard_twice(name: str, event: dict) -> tuple[dict, dict]:
    with tempfile.TemporaryDirectory(prefix="stop-guard-test-") as tmp:
        home = _codex_home(tmp)
        try:
            return _invoke_stop_guard(home, event), _invoke_stop_guard(home, event)
        except AssertionError as exc:
            raise AssertionError(f"{name}: {exc}") from exc


def is_block(payload: dict) -> bool:
    return payload.get("decision") == "block" and str(payload.get("reason") or "").startswith("[HOOK:STOP_GUARD]")


def assert_contract(name: str, payload: dict) -> None:
    if "hookSpecificOutput" in payload:
        raise AssertionError(f"{name}: Stop payload contains unsupported schema fields: {payload}")


def main() -> int:
    cases = [
        (
            "receipt_ok",
            {"turn_id": "receipt_ok", "last_agent_message": f'已完成。STOP_COMPLETION_RECEIPT: {{"status":"complete","changed_files":["a"],"verification":["py_compile"],"open_items":[],{P0_LOW}}}'},
            None,
            False,
        ),
        (
            "receipt_fenced_json_ok",
            {
                "turn_id": "receipt_fenced_json_ok",
                "last_agent_message": (
                    "已完成。\nSTOP_COMPLETION_RECEIPT:\n"
                    "```json\n"
                    f'{{"status":"complete","changed_files":["a"],"verification":["py_compile"],"open_items":[],{P0_LOW}}}\n'
                    "```"
                ),
            },
            None,
            False,
        ),
        (
            "receipt_inline_too_large",
            {
                "turn_id": "receipt_inline_too_large",
                "last_agent_message": (
                    '已完成。STOP_COMPLETION_RECEIPT: {"status":"complete",'
                    f'"changed_files":[{json.dumps("x" * 2200)}],'
                    f'"verification":["py_compile"],"open_items":[],{P0_LOW}}}'
                ),
            },
            None,
            True,
        ),
        (
            "receipt_low_stop_missing_explanation",
            {"turn_id": "receipt_low_stop_missing_explanation", "last_agent_message": f'已完成。STOP_COMPLETION_RECEIPT: {{"status":"complete","changed_files":["a"],"verification":["py_compile"],"open_items":[],{P0_LOW_INCOMPLETE}}}'},
            None,
            False,
        ),
        (
            "receipt_missing_p0",
            {"turn_id": "receipt_missing_p0", "last_agent_message": '已完成。STOP_COMPLETION_RECEIPT: {"status":"complete","changed_files":["a"],"verification":["py_compile"],"open_items":[]}'},
            None,
            False,
        ),
        (
            "receipt_open",
            {"turn_id": "receipt_open", "last_agent_message": '已完成。STOP_COMPLETION_RECEIPT: {"status":"complete","verification":["py_compile"],"open_items":["归档剩余项"]}'},
            None,
            True,
        ),
        (
            "receipt_no_verify",
            {"turn_id": "receipt_no_verify", "last_agent_message": '已完成。STOP_COMPLETION_RECEIPT: {"status":"complete","open_items":[]}'},
            None,
            True,
        ),
        (
            "receipt_blocker",
            {"turn_id": "receipt_blocker", "last_agent_message": 'WAIT_HUMAN_BLOCKER。STOP_COMPLETION_RECEIPT: {"status":"wait_human","blockers":["缺少登录权限"],"open_items":["等待用户授权"]}'},
            None,
            False,
        ),
        (
            "receipt_placeholder_example",
            {"turn_id": "receipt_placeholder_example", "last_agent_message": "说明：比如 `已完成。STOP_COMPLETION_RECEIPT: {...}` 这种文档示例不应被当成真实回执。"},
            None,
            False,
        ),
        (
            "p0_high_suggest_only",
            {"turn_id": "p0_high_suggest_only", "last_agent_message": f'已完成。STOP_COMPLETION_RECEIPT: {{"status":"complete","verification":["py_compile"],"open_items":[],{P0_HIGH_SUGGEST}}}'},
            None,
            False,
        ),
        (
            "p0_high_continue_once",
            {"turn_id": "p0_high_continue_once", "last_agent_message": f'已完成。STOP_COMPLETION_RECEIPT: {{"status":"complete","verification":["py_compile"],"open_items":[],{P0_HIGH_CONTINUE}}}'},
            None,
            False,
        ),
        ("mixed_direct", {"turn_id": "mixed_direct", "last_agent_message": "已完成，但仍需处理归档残留。"}, None, False),
        (
            "deferred_commitment_next_round",
            {
                "turn_id": "deferred_commitment_next_round",
                "last_agent_message": "下一轮我会按这个结构迁移，不把真实运行数据塞进 skill，只把可复用脚本和最小样例留在 skill。",
            },
            None,
            False,
        ),
        (
            "proposed_plan_ok",
            {
                "turn_id": "proposed_plan_ok",
                "last_agent_message": "<proposed_plan>\n**计划**\n- 下一步实现 hook 修复\n- 待办由执行阶段处理\n</proposed_plan>",
            },
            None,
            False,
        ),
        (
            "proposed_plan_missing_close",
            {
                "turn_id": "proposed_plan_missing_close",
                "last_agent_message": "<proposed_plan>\n**计划**\n- 下一步继续处理 pending_failure_review",
            },
            None,
            False,
        ),
        (
            "proposed_plan_live_debt_outside",
            {
                "turn_id": "proposed_plan_live_debt_outside",
                "last_agent_message": "<proposed_plan>\n**计划**\n- 修 hook\n</proposed_plan>\n计划外还有未完成工作，需要继续处理。",
            },
            None,
            False,
        ),
        ("empty_no_session", {"turn_id": "empty_no_session"}, None, False),
        (
            "session_fallback_agent_message",
            {"turn_id": "session_fallback_agent_message", "session_id": "missing-id"},
            "已完成，但建议后续继续处理剩余治理项。",
            False,
        ),
        (
            "empty_followup_payload_resolved_duplicate",
            {
                "turn_id": "empty_followup_payload_resolved_duplicate",
                "last_agent_message": (
                    "已修。自动提交前会反查当前会话里是否已经有同文案用户消息，"
                    "存在就登记并跳过，解决补丁上线前已经提交过的旧建议再次被吃的问题。\n"
                    '```json\n{"codex_follow_up_candidate": true, "task_complete": true, "items": []}\n```'
                ),
            },
            None,
            False,
        ),
        (
            "guard_result_example_with_blocking_text",
            {
                "turn_id": "guard_result_example_with_blocking_text",
                "last_agent_message": (
                    "已完成。真实未闭环文本仍保留阻断能力："
                    "但“建议后续继续处理”这种真实未闭环文本仍会阻断。"
                ),
            },
            None,
            False,
        ),
        (
            "guard_diagnostic_with_deferred_term_is_info_only",
            {
                "turn_id": "guard_diagnostic_with_deferred_term_is_info_only",
                "last_agent_message": (
                    "已恢复。STOP_GUARD 把包含“可继续处理事项”的收尾回复"
                    "判为尚未结束；遗留空白轮次已自动收口。"
                ),
            },
            None,
            False,
        ),
        (
            "completed_session_reuse_contract_is_info_only",
            {
                "turn_id": "completed_session_reuse_contract_is_info_only",
                "last_agent_message": (
                    "已修复。\n"
                    "- 后续同一会话的复杂消息都会复用该回执，不再重复加载 W1、M1 和通用文档。\n"
                    "- 快照被阻断、身份不一致或来源漂移时，不能被会话复用绕过。\n"
                    "验证：17 passed。"
                ),
            },
            None,
            False,
        ),
        (
            "zero_pending_summary_is_informational",
            {
                "turn_id": "zero_pending_summary_is_informational",
                "last_agent_message": "验收通过。Hook pending 数量：0。",
            },
            None,
            False,
        ),
        (
            "markdown_wrapped_zero_named_pending_is_informational",
            {
                "turn_id": "markdown_wrapped_zero_named_pending_is_informational",
                "last_agent_message": "最终验证通过：`pending_failure_review=0`。",
            },
            None,
            False,
        ),
        (
            "zero_pending_does_not_hide_real_todo",
            {
                "turn_id": "zero_pending_does_not_hide_real_todo",
                "last_agent_message": "Hook pending=0，但 TODO 仍需处理。",
            },
            None,
            False,
        ),
        (
            "cleared_pending_does_not_hide_real_todo",
            {
                "turn_id": "cleared_pending_does_not_hide_real_todo",
                "last_agent_message": "Hook pending 已清空，但 TODO 仍需处理。",
            },
            None,
            False,
        ),
        (
            "later_clear_does_not_hide_earlier_todo",
            {
                "turn_id": "later_clear_does_not_hide_earlier_todo",
                "last_agent_message": "Hook pending 有 TODO 待处理，其余已清空。",
            },
            None,
            False,
        ),
        (
            "one_named_pending_clear_does_not_hide_another",
            {
                "turn_id": "one_named_pending_clear_does_not_hide_another",
                "last_agent_message": "pending_a 仍需修复，pending_b 为空。",
            },
            None,
            False,
        ),
    ]

    for name, event, session_text, should_block in cases:
        payload = run_stop_guard(name, event, session_text)
        assert_contract(name, payload)
        actual = is_block(payload)
        if actual != should_block:
            raise AssertionError(f"{name}: expected block={should_block}, got {actual}: {payload}")
        print(f"{name}: {'BLOCK' if actual else 'ALLOW'}")
        reason = str(payload.get("reason") or "")
    plusplus_payload = run_stop_guard(
        "plusplus_skips_p0",
        {"turn_id": "plusplus_skips_p0", "last_agent_message": '已完成。STOP_COMPLETION_RECEIPT: {"status":"complete","changed_files":["a"],"verification":["py_compile"],"open_items":[]}'},
        codex_home_kind="plusplus",
    )
    assert_contract("plusplus_skips_p0", plusplus_payload)
    if is_block(plusplus_payload):
        raise AssertionError(f"plusplus_skips_p0: expected Codex++ skip, got {plusplus_payload}")
    print("plusplus_skips_p0: ALLOW")
    with tempfile.TemporaryDirectory(prefix="stop-guard-receipt-file-") as receipt_tmp:
        receipt_path = Path(receipt_tmp) / "receipt.json"
        receipt_path.write_text(
            "{"
            '"status":"complete",'
            '"changed_files":["a"],'
            '"verification":["py_compile"],'
            '"open_items":[],'
            f"{P0_LOW}"
            "}",
            encoding="utf-8",
        )
        receipt_path_json = json.dumps(str(receipt_path), ensure_ascii=False)
        receipt_file_payload = run_stop_guard(
            "receipt_path_ok",
            {
                "turn_id": "receipt_path_ok",
                "last_agent_message": f'已完成。STOP_COMPLETION_RECEIPT: {{"receipt_path":{receipt_path_json}}}',
            },
        )
    assert_contract("receipt_path_ok", receipt_file_payload)
    if is_block(receipt_file_payload):
        raise AssertionError(f"receipt_path_ok: expected allow, got {receipt_file_payload}")
    print("receipt_path_ok: ALLOW")
    first, second = run_stop_guard_twice(
        "p0_continue_loop_guard",
        {"turn_id": "p0_continue_loop_guard", "last_agent_message": f'已完成。STOP_COMPLETION_RECEIPT: {{"status":"complete","verification":["py_compile"],"open_items":[],{P0_HIGH_CONTINUE}}}'},
    )
    assert_contract("p0_continue_loop_guard:first", first)
    assert_contract("p0_continue_loop_guard:second", second)
    if is_block(first) or is_block(second):
        raise AssertionError(f"p0_continue_loop_guard: expected both allows, got {first} / {second}")
    print("p0_continue_loop_guard: ALLOW")
    payload = run_stop_guard(
        "proposed_plan_with_live_pending",
        {
            "turn_id": "proposed_plan_with_live_pending",
            "last_agent_message": "<proposed_plan>\n**计划**\n- 下一步处理 hook\n</proposed_plan>",
        },
        pending={
            "pending_failure_review@turn:proposed_plan_with_live_pending": {
                "reason": "tool reported error",
                "command_fingerprint": "example",
                "failure_count": 1,
                "owner_scope": "turn:proposed_plan_with_live_pending",
                "turn_id": "proposed_plan_with_live_pending",
            }
        },
    )
    assert_contract("proposed_plan_with_live_pending", payload)
    if not is_block(payload):
        raise AssertionError(f"proposed_plan_with_live_pending: expected block=True, got {payload}")
    print("proposed_plan_with_live_pending: BLOCK")
    payload = run_stop_guard(
        "foreign_failure_review_is_ignored",
        {
            "turn_id": "foreign_failure_review_is_ignored",
            "session_id": "session-current",
            "last_agent_message": "状态已读取。",
        },
        pending={
            "pending_failure_review:session-other": {
                "reason": "tool reported error",
                "session_id": "session-other",
                "command_fingerprint": "example",
                "failure_count": 1,
            }
        },
    )
    assert_contract("foreign_failure_review_is_ignored", payload)
    if is_block(payload):
        raise AssertionError(f"foreign_failure_review_is_ignored: expected allow, got {payload}")
    print("foreign_failure_review_is_ignored: ALLOW")
    payload = run_stop_guard(
        "foreign_s15_is_ignored",
        {
            "turn_id": "foreign_s15_is_ignored",
            "session_id": "session-current",
            "last_agent_message": "状态已读取。",
        },
        pending={
            "pending_s15:session-other": {
                "reason": "git commit observed",
                "session_id": "session-other",
            },
            "pending_s15": {"reason": "legacy global marker"},
        },
    )
    assert_contract("foreign_s15_is_ignored", payload)
    if is_block(payload):
        raise AssertionError(f"foreign_s15_is_ignored: expected allow, got {payload}")
    print("foreign_s15_is_ignored: ALLOW")
    payload = run_stop_guard(
        "foreign_w9_is_ignored",
        {
            "turn_id": "foreign_w9_is_ignored",
            "session_id": "session-current",
            "last_agent_message": "状态已读取。",
        },
        pending={
            "pending_w9:session-other": {
                "reason": "governed markdown changed",
                "session_id": "session-other",
            }
        },
    )
    assert_contract("foreign_w9_is_ignored", payload)
    if is_block(payload):
        raise AssertionError(f"foreign_w9_is_ignored: expected allow, got {payload}")
    print("foreign_w9_is_ignored: ALLOW")
    payload = run_stop_guard(
        "own_w9_still_blocks",
        {
            "turn_id": "own_w9_still_blocks",
            "session_id": "session-current",
            "last_agent_message": "状态已读取。",
        },
        pending={
            "pending_w9:session-current": {
                "reason": "governed markdown changed",
                "session_id": "session-current",
            }
        },
    )
    assert_contract("own_w9_still_blocks", payload)
    if not is_block(payload):
        raise AssertionError(f"own_w9_still_blocks: expected block, got {payload}")
    print("own_w9_still_blocks: BLOCK")
    payload = run_stop_guard(
        "foreign_turn_w9_is_ignored",
        {
            "turn_id": "turn-current",
            "last_agent_message": "状态已读取。",
        },
        pending={
            "pending_w9@turn:turn-other": {
                "reason": "governed markdown changed",
                "turn_id": "turn-other",
            }
        },
    )
    assert_contract("foreign_turn_w9_is_ignored", payload)
    if is_block(payload):
        raise AssertionError(f"foreign_turn_w9_is_ignored: expected allow, got {payload}")
    print("foreign_turn_w9_is_ignored: ALLOW")
    payload = run_stop_guard(
        "own_turn_w9_still_blocks",
        {
            "turn_id": "turn-current",
            "last_agent_message": "状态已读取。",
        },
        pending={
            "pending_w9@turn:turn-current": {
                "reason": "governed markdown changed",
                "turn_id": "turn-current",
            }
        },
    )
    assert_contract("own_turn_w9_still_blocks", payload)
    if not is_block(payload):
        raise AssertionError(f"own_turn_w9_still_blocks: expected block, got {payload}")
    print("own_turn_w9_still_blocks: BLOCK")
    return 0


def test_stop_guard_only_blocks_current_owned_failure_or_control_records() -> None:
    deferred = run_stop_guard(
        "deferred_text_is_not_task_authorization",
        {
            "turn_id": "deferred_text_is_not_task_authorization",
            "last_agent_message": "已完成；后续可考虑整理旧失败说明。",
        },
    )
    assert not is_block(deferred)

    historical = run_stop_guard(
        "historical_failure_is_evidence_not_current_work",
        {
            "turn_id": "historical_failure_is_evidence_not_current_work",
            "last_agent_message": "本轮已完成。",
        },
        pending={
            "pending_failure_review@turn:historical_failure_is_evidence_not_current_work": {
                "owner_scope": "turn:historical_failure_is_evidence_not_current_work",
                "failure_class": "EXPECTED_HISTORICAL_FAILURE",
                "reason": "preserved historical failure evidence",
            }
        },
    )
    assert not is_block(historical)

    current_tool_failure = run_stop_guard(
        "current_tool_failure_still_blocks",
        {"turn_id": "current_tool_failure_still_blocks", "last_agent_message": "本轮已完成。"},
        pending={
            "pending_failure_review@turn:current_tool_failure_still_blocks": {
                "owner_scope": "turn:current_tool_failure_still_blocks",
                "failure_class": "CURRENT_TASK_TOOL_FAILURE",
                "reason": "current command failed",
            }
        },
    )
    assert is_block(current_tool_failure)

    control_blocker = run_stop_guard(
        "formal_control_blocker_still_blocks",
        {"turn_id": "formal_control_blocker_still_blocks", "last_agent_message": "本轮已完成。"},
        pending={
            "pending_control@turn:formal_control_blocker_still_blocks": {
                "owner_scope": "turn:formal_control_blocker_still_blocks",
                "failure_class": "FORMAL_CONTROL_BLOCKER",
                "reason": "current target awaits formal control decision",
            }
        },
    )
    assert is_block(control_blocker)


def test_formal_control_blocker_allows_an_explicit_human_wait_response() -> None:
    payload = run_stop_guard(
        "formal_control_wait_is_not_auto_continuation",
        {
            "turn_id": "formal_control_wait_is_not_auto_continuation",
            "last_agent_message": "等待用户授权后再执行环境重建。",
        },
        pending={
            "pending_permission_review@turn:formal_control_wait_is_not_auto_continuation": {
                "owner_scope": "turn:formal_control_wait_is_not_auto_continuation",
                "failure_class": "FORMAL_CONTROL_BLOCKER",
                "reason": "environment installation requires user approval",
            }
        },
    )
    assert not is_block(payload)


def test_scoped_permission_review_is_nonblocking_after_a_formal_alternate_is_verified() -> None:
    turn_id = "permission_review_superseded_by_formal_alternate"
    payload = run_stop_guard(
        turn_id,
        {"turn_id": turn_id, "last_agent_message": "本轮已完成正式入口核验。"},
        pending={
            f"pending_permission_review@turn:{turn_id}": {
                "owner_scope": f"turn:{turn_id}",
                "reason": "denied environment dependency request",
            },
            f"pending_failure_review@turn:{turn_id}": {
                "owner_scope": f"turn:{turn_id}",
                "failure_class": "SUPERSEDED_OPERATIONAL_FAILURE",
                "superseded_by": "formal-runtime-r2:verified-launcher",
                "reason": "formal runtime verification succeeded",
            },
        },
    )

    assert not is_block(payload)


if __name__ == "__main__":
    raise SystemExit(main())
