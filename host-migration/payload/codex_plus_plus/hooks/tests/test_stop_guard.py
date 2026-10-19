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


def run_stop_guard_twice(name: str, event: dict, pending: dict | None = None) -> tuple[dict, dict]:
    with tempfile.TemporaryDirectory(prefix="stop-guard-test-") as tmp:
        home = _codex_home(tmp)
        if pending is not None:
            state_dir = home / "hook-state"
            state_dir.mkdir(parents=True)
            (state_dir / "openclaw-mono-pending.json").write_text(
                json.dumps({"pending": pending}, ensure_ascii=False),
                encoding="utf-8",
            )
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
    nonempty_followup_payload = json.dumps(
        {
            "codex_follow_up_candidate": True,
            "title": "Follow-up",
            "task_complete": True,
            "items": [
                {
                    "prompt": "处理剩余治理项",
                    "priority": "P1",
                    "evidence_refs": ["AGENTS.md:143"],
                    "reason": "后续处理可以减少风险",
                    "is_current_task_debt": False,
                    "confidence": 0.9,
                }
            ],
        },
        ensure_ascii=False,
    )
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
            "receipt_low_stop_missing_explanation",
            {"turn_id": "receipt_low_stop_missing_explanation", "last_agent_message": f'已完成。STOP_COMPLETION_RECEIPT: {{"status":"complete","changed_files":["a"],"verification":["py_compile"],"open_items":[],{P0_LOW_INCOMPLETE}}}'},
            None,
            True,
        ),
        (
            "receipt_missing_p0",
            {"turn_id": "receipt_missing_p0", "last_agent_message": '已完成。STOP_COMPLETION_RECEIPT: {"status":"complete","changed_files":["a"],"verification":["py_compile"],"open_items":[]}'},
            None,
            True,
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
            True,
        ),
        ("mixed_direct", {"turn_id": "mixed_direct", "last_agent_message": "已完成，但仍需处理归档残留。"}, None, True),
        (
            "deferred_commitment_next_round",
            {
                "turn_id": "deferred_commitment_next_round",
                "last_agent_message": "下一轮我会按这个结构迁移，不把真实运行数据塞进 skill，只把可复用脚本和最小样例留在 skill。",
            },
            None,
            True,
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
            True,
        ),
        (
            "proposed_plan_live_debt_outside",
            {
                "turn_id": "proposed_plan_live_debt_outside",
                "last_agent_message": "<proposed_plan>\n**计划**\n- 修 hook\n</proposed_plan>\n计划外还有未完成工作，需要继续处理。",
            },
            None,
            True,
        ),
        ("empty_no_session", {"turn_id": "empty_no_session"}, None, False),
        (
            "session_fallback_agent_message",
            {"turn_id": "session_fallback_agent_message", "session_id": "session_fallback_agent_message"},
            "已完成，但建议后续继续处理剩余治理项。",
            True,
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
            "nonempty_followup_payload_ignored",
            {
                "turn_id": "nonempty_followup_payload_ignored",
                "last_agent_message": (
                    "已完成。候选面板只交给 Follow-up Gate，不代表当前任务未完成。\n"
                    f"```json\n{nonempty_followup_payload}\n```"
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
            "resolved_pending_key_regression_note",
            {
                "turn_id": "resolved_pending_key_regression_note",
                "last_agent_message": (
                    "已完成。补了回归测试，确认这个场景不会再写入 `pending_failure_review`。"
                    "hook-state 里的 pending 仍为空。"
                ),
            },
            None,
            False,
        ),
        (
            "resolved_pending_key_with_rerun_detail",
            {
                "turn_id": "resolved_pending_key_with_rerun_detail",
                "last_agent_message": (
                    "已经完整闭环，当前没有未清状态。"
                    "Stop Guard 的 `pending_failure_review` 已通过原命令指纹正式复跑清除，"
                    "状态读回 `pending_count=0`。"
                ),
            },
            None,
            False,
        ),
        (
            "pending_key_with_unresolved_clear_still_blocks",
            {
                "turn_id": "pending_key_with_unresolved_clear_still_blocks",
                "last_agent_message": (
                    "已完成定位，但 `pending_failure_review` 已通过初步检查，不过仍需清除。"
                ),
            },
            None,
            True,
        ),
        (
            "resolved_hook_report_with_no_git_and_memory_citation",
            {
                "turn_id": "resolved_hook_report_with_no_git_and_memory_citation",
                "last_agent_message": (
                    "已完成。根因是 Stop Hook 清理逻辑不够完整，我已经根治掉这一层。\n"
                    "当前 hook-state 读回 pending: {}。\n"
                    "没有做 Git 提交。\n"
                    "<oai-mem-citation>\n"
                    "<citation_entries>\n"
                    "MEMORY.md:510-521|note=[hook state clearing rule]\n"
                    "</citation_entries>\n"
                    "<rollout_ids>\n</rollout_ids>\n"
                    "</oai-mem-citation>\n"
                    "```json\n"
                    '{"codex_follow_up_candidate": true, "task_complete": true, "items": []}\n'
                    "```"
                ),
            },
            None,
            False,
        ),
        (
            "real_pending_key_still_blocks",
            {
                "turn_id": "real_pending_key_still_blocks",
                "last_agent_message": "已完成，但 pending_failure_review 还需处理。",
            },
            None,
            True,
        ),
        (
            "resolved_s12_cleanup_with_empty_followup",
            {
                "turn_id": "resolved_s12_cleanup_with_empty_followup",
                "last_agent_message": (
                    "已闭环，自动路由基准验证通过。"
                    "工具命令异常已按 S12 完成归因和清理，没有遗留文件。\n"
                    '```json\n{"codex_follow_up_candidate": true, "title": "Follow-up", '
                    '"task_complete": true, "items": []}\n```'
                ),
            },
            None,
            False,
        ),
        (
            "zero_count_health_summary_is_informational",
            {
                "turn_id": "zero_count_health_summary_is_informational",
                "last_agent_message": (
                    "已完成。Hook 日志：未处理异常 0；故意 deny 行为符合契约。"
                ),
            },
            None,
            False,
        ),
        (
            "zero_count_pending_summary_is_informational",
            {
                "turn_id": "zero_count_pending_summary_is_informational",
                "last_agent_message": (
                    "S14 验收通过。当前 Hook pending 数量：0；本次写入数量：0。"
                ),
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
            "markdown_wrapped_zero_pending_does_not_hide_real_todo",
            {
                "turn_id": "markdown_wrapped_zero_pending_does_not_hide_real_todo",
                "last_agent_message": "`pending_failure_review=0`，但 TODO 仍需处理。",
            },
            "STOP_GUARD_REJECT_REASON",
            True,
        ),
        (
            "markdown_wrapped_nonzero_pending_still_blocks",
            {
                "turn_id": "markdown_wrapped_nonzero_pending_still_blocks",
                "last_agent_message": "已完成，但 `pending_failure_review=1`。",
            },
            "STOP_GUARD_REJECT_REASON",
            True,
        ),
        (
            "zero_pending_does_not_hide_real_todo",
            {
                "turn_id": "zero_pending_does_not_hide_real_todo",
                "last_agent_message": "Hook pending=0，但 TODO 仍需处理。",
            },
            "STOP_GUARD_REJECT_REASON",
            True,
        ),
        (
            "zero_pending_does_not_hide_named_pending",
            {
                "turn_id": "zero_pending_does_not_hide_named_pending",
                "last_agent_message": "Hook pending=0，但 pending_failure_review 还需处理。",
            },
            "STOP_GUARD_REJECT_REASON",
            True,
        ),
        (
            "empty_pending_does_not_hide_real_todo",
            {
                "turn_id": "empty_pending_does_not_hide_real_todo",
                "last_agent_message": "Hook pending: empty，但 TODO 仍需处理。",
            },
            "STOP_GUARD_REJECT_REASON",
            True,
        ),
        (
            "empty_object_pending_does_not_hide_real_todo",
            {
                "turn_id": "empty_object_pending_does_not_hide_real_todo",
                "last_agent_message": "Hook pending: {}，但 TODO 仍需处理。",
            },
            "STOP_GUARD_REJECT_REASON",
            True,
        ),
        (
            "cleared_pending_does_not_hide_real_todo",
            {
                "turn_id": "cleared_pending_does_not_hide_real_todo",
                "last_agent_message": "Hook pending 已清空，但 TODO 仍需处理。",
            },
            "STOP_GUARD_REJECT_REASON",
            True,
        ),
        (
            "later_clear_does_not_hide_earlier_todo",
            {
                "turn_id": "later_clear_does_not_hide_earlier_todo",
                "last_agent_message": "Hook pending 有 TODO 待处理，其余已清空。",
            },
            "STOP_GUARD_REJECT_REASON",
            True,
        ),
        (
            "one_named_pending_clear_does_not_hide_another",
            {
                "turn_id": "one_named_pending_clear_does_not_hide_another",
                "last_agent_message": "pending_a 仍需修复，pending_b 为空。",
            },
            "STOP_GUARD_REJECT_REASON",
            True,
        ),
        (
            "unresolved_s12_cleanup_still_blocks",
            {
                "turn_id": "unresolved_s12_cleanup_still_blocks",
                "last_agent_message": "已完成，但工具命令异常仍需清理，存在遗留文件。",
            },
            None,
            True,
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
        if name == "receipt_missing_p0" and "P0_NEXT_STEP_GATE_MISSING" not in reason:
            raise AssertionError(f"{name}: missing P0 gate reason: {payload}")
        if name == "receipt_low_stop_missing_explanation" and "P0_NEXT_STEP_STOP_EXPLANATION_MISSING" not in reason:
            raise AssertionError(f"{name}: missing P0 stop explanation reason: {payload}")
        if name == "p0_high_continue_once" and "P0_NEXT_STEP_CONTINUE_ONCE" not in reason:
            raise AssertionError(f"{name}: missing P0 continue reason: {payload}")
        if name == "session_fallback_agent_message":
            for needle in (
                "STOP_GUARD_REJECT_REASON",
                "Finish the named action",
                "STOP_COMPLETION_RECEIPT",
            ):
                if needle not in reason:
                    raise AssertionError(f"{name}: missing reason fragment {needle!r}: {payload}")
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
    if not is_block(first) or is_block(second):
        raise AssertionError(f"p0_continue_loop_guard: expected first block and second allow, got {first} / {second}")
    print("p0_continue_loop_guard: BLOCK_THEN_ALLOW")
    old_perf_registry = r"@@TESTING_ROOT:win@@\.agent\config\perf_environment_registry.json"
    actual_perf_registry = r"@@TESTING_ROOT:win@@\接口测试\性能测试-小精灵全链路\config\perf_environment_registry.json"
    previous_expected_cwd = os.environ.get("CODEX_COMMANDER_EXPECTED_CWD")
    os.environ["CODEX_COMMANDER_EXPECTED_CWD"] = (
        r"@@TESTING_ROOT:win@@\接口测试\性能测试-小精灵全链路"
    )
    try:
        payload = run_stop_guard(
            "pending_failure_review_perf_registry_path",
            {
                "turn_id": "pending_failure_review_perf_registry_path",
                "last_agent_message": (
                    '已完成。STOP_COMPLETION_RECEIPT: {"status":"complete",'
                    '"verification":["smoke"],"open_items":[]}'
                ),
            },
            pending={
                "pending_failure_review": {
                    "reason": "tool reported error",
                    "command_fingerprint": (
                        "python -B -c \"import json,pathlib; "
                        f"p=pathlib.Path(r'{old_perf_registry}'); "
                        "d=json.loads(p.read_text(encoding='utf-8-sig'))\""
                    ),
                    "failure_count": 1,
                    "turn_id": "pending_failure_review_perf_registry_path",
                }
            },
            codex_home_kind="plusplus",
        )
    finally:
        if previous_expected_cwd is None:
            os.environ.pop("CODEX_COMMANDER_EXPECTED_CWD", None)
        else:
            os.environ["CODEX_COMMANDER_EXPECTED_CWD"] = previous_expected_cwd
    assert_contract("pending_failure_review_perf_registry_path", payload)
    reason = str(payload.get("reason") or "")
    if not is_block(payload) or actual_perf_registry not in reason or old_perf_registry in reason:
        raise AssertionError(f"pending_failure_review_perf_registry_path: expected normalized path, got {payload}")
    print("pending_failure_review_perf_registry_path: NORMALIZED")
    payload = run_stop_guard(
        "proposed_plan_with_live_pending",
        {
            "turn_id": "proposed_plan_with_live_pending",
            "last_agent_message": "<proposed_plan>\n**计划**\n- 下一步处理 hook\n</proposed_plan>",
        },
        pending={
            "pending_failure_review": {
                "reason": "tool reported error",
                "command_fingerprint": "example",
                "failure_count": 1,
                "turn_id": "proposed_plan_with_live_pending",
            }
        },
    )
    assert_contract("proposed_plan_with_live_pending", payload)
    if not is_block(payload):
        raise AssertionError(f"proposed_plan_with_live_pending: expected block=True, got {payload}")
    print("proposed_plan_with_live_pending: BLOCK")
    payload = run_stop_guard(
        "other_session_pending_is_not_current_blocker",
        {
            "session_id": "session-current",
            "turn_id": "other_session_pending_is_not_current_blocker",
            "last_agent_message": "当前任务完整闭合。",
        },
        pending={
            "pending_failure_review@session:session-other": {
                "reason": "tool reported error",
                "command_fingerprint": "example-other-session",
                "failure_count": 1,
                "session_id": "session-other",
                "turn_id": "turn-other",
            }
        },
        codex_home_kind="plusplus",
    )
    assert_contract("other_session_pending_is_not_current_blocker", payload)
    if is_block(payload):
        raise AssertionError(
            "other_session_pending_is_not_current_blocker: expected allow for non-owned pending, "
            f"got {payload}"
        )
    print("other_session_pending_is_not_current_blocker: ALLOW")
    payload = run_stop_guard(
        "plan_ignores_other_session_pending",
        {
            "session_id": "session-current",
            "turn_id": "plan_ignores_other_session_pending",
            "last_agent_message": "<proposed_plan>\n**计划**\n- 本轮计划已完整交付\n</proposed_plan>",
        },
        pending={
            "pending_failure_review@session:session-other": {
                "reason": "tool reported error",
                "command_fingerprint": "example-other-session",
                "failure_count": 1,
                "session_id": "session-other",
            }
        },
        codex_home_kind="plusplus",
    )
    assert_contract("plan_ignores_other_session_pending", payload)
    if is_block(payload):
        raise AssertionError(
            "plan_ignores_other_session_pending: expected allow for non-owned pending, "
            f"got {payload}"
        )
    print("plan_ignores_other_session_pending: ALLOW")
    payload = run_stop_guard(
        "old_turn_pending_is_not_current_blocker",
        {
            "session_id": "session-current",
            "turn_id": "turn-new",
            "last_agent_message": "当前任务完整闭合。",
        },
        pending={
            "pending_failure_review@session:session-current": {
                "reason": "tool reported error",
                "command_fingerprint": "example-current-session",
                "failure_count": 1,
                "session_id": "session-current",
                "turn_id": "turn-current",
            }
        },
        codex_home_kind="plusplus",
    )
    assert_contract("old_turn_pending_is_not_current_blocker", payload)
    if is_block(payload):
        raise AssertionError(f"old_turn_pending_is_not_current_blocker: expected allow, got {payload}")
    print("old_turn_pending_is_not_current_blocker: ALLOW")
    payload = run_stop_guard(
        "same_turn_pending_still_blocks",
        {
            "session_id": "session-current",
            "turn_id": "turn-current",
            "last_agent_message": "当前任务完整闭合。",
        },
        pending={
            "pending_failure_review@session:session-current": {
                "reason": "tool reported error",
                "command_fingerprint": "example-current-session",
                "failure_count": 1,
                "session_id": "session-current",
                "turn_id": "turn-current",
            }
        },
        codex_home_kind="plusplus",
    )
    assert_contract("same_turn_pending_still_blocks", payload)
    if not is_block(payload):
        raise AssertionError(f"same_turn_pending_still_blocks: expected block, got {payload}")
    print("same_turn_pending_still_blocks: BLOCK")
    payload = run_stop_guard(
        "s15_is_advisory_only",
        {
            "session_id": "session-current",
            "turn_id": "turn-s15",
            "last_agent_message": (
                '已完成。STOP_COMPLETION_RECEIPT: '
                '{"status":"complete","verification":["smoke"],"open_items":[]}'
            ),
        },
        pending={
            "pending_s15@session:session-current": {
                "reason": "git push permission failure observed",
                "session_id": "session-current",
                "turn_id": "turn-s15",
            }
        },
        codex_home_kind="plusplus",
    )
    assert_contract("s15_is_advisory_only", payload)
    if is_block(payload):
        raise AssertionError(f"s15_is_advisory_only: expected allow, got {payload}")
    print("s15_is_advisory_only: ALLOW")
    first, second = run_stop_guard_twice(
        "pending_block_loop_guard",
        {
            "session_id": "session-loop",
            "turn_id": "turn-loop",
            "last_agent_message": "当前任务完整闭合。",
        },
        pending={
            "pending_failure_review@session:session-loop": {
                "reason": "tool reported error",
                "command_fingerprint": "example-loop",
                "failure_count": 1,
                "session_id": "session-loop",
                "turn_id": "turn-loop",
            }
        },
    )
    assert_contract("pending_block_loop_guard:first", first)
    assert_contract("pending_block_loop_guard:second", second)
    if not is_block(first) or is_block(second):
        raise AssertionError(f"pending_block_loop_guard: expected first block and second allow, got {first} / {second}")
    print("pending_block_loop_guard: BLOCK_THEN_ALLOW")
    payload = run_stop_guard(
        "permission_pending_with_human_blocker_receipt",
        {
            "turn_id": "permission_pending_with_human_blocker_receipt",
            "last_agent_message": (
                'WAIT_HUMAN_BLOCKER。STOP_COMPLETION_RECEIPT: '
                '{"status":"wait_human","blockers":["等待用户授权修改 Codex++ Hook"],'
                '"open_items":["获得授权后修复权限状态契约"]}'
            ),
        },
        pending={"pending_permission_review": {"reason": "dependency install requires review"}},
        codex_home_kind="plusplus",
    )
    assert_contract("permission_pending_with_human_blocker_receipt", payload)
    if is_block(payload):
        raise AssertionError(f"permission_pending_with_human_blocker_receipt: expected allow, got {payload}")
    print("permission_pending_with_human_blocker_receipt: ALLOW")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
