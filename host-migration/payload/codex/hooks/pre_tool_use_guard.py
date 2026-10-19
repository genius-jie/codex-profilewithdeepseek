#!/usr/bin/env python3
"""Block obvious unsafe actions before tool execution.

SSOT 互指（引擎隔离，各维护独立副本，不抽共享模块）：
  兄弟副本：@@CLAUDE_HOME:escaped@@\\hooks\\pre_tool_use_guard.py
    （Claude 侧自包含 enforce_delivery_manifest 直接 import 校验器）。
  W11 写时关物理 SSOT（两边最终收敛的唯一真相源）：
    projects/automation-core/scripts/w11_delivery_manifest.py::verify_paths
    —— 本文件经 hook_common.is_business_code_write 调同一函数，
       与 pre-commit / Claude 侧共用同一判定，口径不得各自漂移。
  改此文件的判定逻辑前，先确认兄弟副本与物理校验器是否需要同步。
"""

from __future__ import annotations

from hook_common import (
    additional_context,
    command_may_modify_files,
    command_has_unbounded_git_add,
    current_pipeline_runtime_paths,
    deny,
    extract_governed_md_mentions,
    is_business_code_write,
    is_git_destructive,
    is_git_write_to_third_party,
    is_pip_install_without_requirements,
    is_taskkill,
    mark_pending,
    read_event,
    record_hook_run,
    run_safely,
    tool_command,
    tool_name,
    tool_text,
    uses_blocked_text_writer,
    within_openclaw,
    w11_verify_business_writes,
)


def main() -> int:
    event = read_event()
    record_hook_run("PreToolUse", event)
    in_openclaw = within_openclaw(event)
    name = tool_name(event)
    command = tool_command(event)
    text = command or tool_text(event)

    if is_git_write_to_third_party(text):
        return deny(
            "PreToolUse",
            "Blocked: feishu-mcp-server is a third-party read-only repository. Do not add, commit, push, reset, or update its parent pointer.",
        )

    if command and command_has_unbounded_git_add(command):
        mark_pending("pending_s15", "git add needs S15 triage before broad staging", event=event)
        return deny(
            "PreToolUse",
            "Blocked: broad git add requires S15 full-scan triage first. Exclude openclaw-config/feishu-mcp-server and show grouped status before staging.",
        )

    if command and is_taskkill(command):
        return deny(
            "PreToolUse",
            "Blocked:裸 taskkill is not allowed in OpenClaw. Route Gateway/session cleanup through S24_Session清理与重启.",
        )

    if command and is_pip_install_without_requirements(command):
        mark_pending(
            "pending_permission_review",
            "pip install requested outside requirements flow",
            event=event,
        )
        return deny(
            "PreToolUse",
            "Blocked: pip install without requirements.txt review. Check requirements alignment and request explicit approval.",
        )

    if command and is_git_destructive(command):
        return deny(
            "PreToolUse",
            "Blocked: destructive git operation requires explicit human approval and affected-file summary.",
        )

    if command and uses_blocked_text_writer(command):
        return deny(
            "PreToolUse",
            "Blocked: Set-Content/Out-File are not allowed for repository edits. Use .NET WriteAllText with explicit UTF-8 encoding, or apply_patch for manual code edits.",
        )

    governed = extract_governed_md_mentions(text)
    if in_openclaw and governed and command_may_modify_files(name, command):
        mark_pending(
            "pending_w9",
            "governed markdown touched; W9 must choose GateProfile by the G0-G20 matrix (Constitution/SOP-only => Advisory)",
            governed,
            event=event,
        )
        return additional_context(
            "PreToolUse",
            "[HOOK:GOVERNED_MARKDOWN_HINT]\n"
            "Governed Markdown path detected. Treat this as a reminder only: W9 remains the authority and must choose GateProfile by the G0-G20 matrix; Constitution/SOP-only changes use Advisory.\n"
            f"Files: {', '.join(governed[:10])}",
        )

    # W11 G7 hardening (2026-06-30, 镜像自 Claude Code pre_tool_use_guard.py):
    # 当 W11 active 状态 + Agent 试图调 governance_cli.py manual-pipeline resume 时,
    # 必须有最近的 AskUserQuestion 痕迹文件,否则 DENY(L1 UI 层提示)。
    # 注:governance_cli.py 内部还有 L2.5 executor-agnostic 硬拦截,两层独立防御。
    if tool_name == "Bash":
        import re as _re
        import time as _time
        _cmd_text = event.get("tool_input", {})
        _cmd_text = _cmd_text.get("command", "") if isinstance(_cmd_text, dict) else str(_cmd_text)
        if (_re.search(r"governance_cli\.py\s+manual-pipeline", _cmd_text, _re.IGNORECASE) and
                _re.search(r"--task-id\s+resume", _cmd_text, _re.IGNORECASE)):
            _runtime_paths = current_pipeline_runtime_paths()
            if _runtime_paths.launch_marker_path.is_file():
                _trace_path = _runtime_paths.interrupt_trace_path
                if not _trace_path.is_file():
                    return deny(
                        "PreToolUse",
                        "[W11 G7 Codex] DENY: W11 流水线 active,但缺少最近一次 AskUserQuestion 痕迹文件。\n"
                        f"  期望路径: {_trace_path}\n"
                        "  修复方法: 1) 先用 AskUserQuestion 工具向用户问本次 interrupt 的决定;\n"
                        "           2) 痕迹写入后 5 分钟内再 resume。"
                    )
                _age_sec = _time.time() - _trace_path.stat().st_mtime
                if _age_sec > 300:
                    return deny(
                        "PreToolUse",
                        f"[W11 G7 Codex] DENY: AskUserQuestion 痕迹已过期({int(_age_sec)}s > 300s)。\n"
                        "  请重新调 AskUserQuestion 询问用户,然后再 resume W11。"
                    )

    # W11 写时守卫 (Rung 2)：业务代码写操作必须落在管线 P3 授权的交付范围内。
    # 在代码落盘那一刻拦截，而不是 3 个 commit 之后的 git commit。
    # 仅作用于 projects/ 下非 automation-core 的业务代码——基建/治理/文档写入不受影响。
    if in_openclaw:
        biz_writes = is_business_code_write(event)
        if biz_writes:
            ok, reason = w11_verify_business_writes(biz_writes)
            if not ok:
                mark_pending(
                    "pending_w11_delivery",
                    "business code write outside W11 P3 delivery authorization",
                    biz_writes,
                    event=event,
                )
                return deny(
                    "PreToolUse",
                    "Blocked (W11 交付清单)：你正要写入未被管线 P3 授权的业务代码。\n"
                    f"{reason}\n"
                    "黄金路径：先 W11 发车 → P1 PRD → P2 方案 → P2.5 拆解 → 推进到 P3"
                    "（管线自动产出 .w11-delivery-manifest.json），之后只改授权范围内的文件。\n"
                    "小改动可先跑 validate_task.py 取得带范围的 FAST_TRACK 回执。",
                )

    return 0


if __name__ == "__main__":
    raise SystemExit(run_safely("PreToolUse", main))
