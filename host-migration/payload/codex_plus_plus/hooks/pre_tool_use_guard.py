#!/usr/bin/env python3
"""Block obvious unsafe actions before tool execution."""

from __future__ import annotations

from hook_common import (
    additional_context,
    command_may_modify_files,
    command_targets_governed_markdown,
    command_has_unbounded_git_add,
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
    if (
        within_openclaw(event)
        and governed
        and command_may_modify_files(name, command)
        and command_targets_governed_markdown(name, command, governed)
    ):
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

    # W11 write-time guard (Rung 2): business code writes must be bound to the
    # delivery manifest emitted at the P3 authorization point.
    if within_openclaw(event):
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
                    "黄金路径：先 W11 发车 -> P1 PRD -> P2 方案 -> P2.5 拆解 -> 推进到 P3 "
                    "（管线自动产出 .w11-delivery-manifest.json），之后只改授权范围内的文件。\n"
                    "小改动可先跑 validate_task.py 取得带范围的 FAST_TRACK 回执。",
                )

    return 0


if __name__ == "__main__":
    raise SystemExit(run_safely("PreToolUse", main))
