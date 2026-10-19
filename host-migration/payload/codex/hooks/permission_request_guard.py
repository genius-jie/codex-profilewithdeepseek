#!/usr/bin/env python3
"""Decide obvious OpenClaw permission requests."""

from __future__ import annotations

from hook_common import (
    deny,
    is_git_destructive,
    is_git_write_to_third_party,
    is_pip_install_without_requirements,
    is_python_base_modification,
    is_taskkill,
    read_event,
    record_hook_run,
    run_safely,
    tool_command,
    tool_text,
    uses_blocked_text_writer,
)


def main() -> int:
    event = read_event()
    record_hook_run("PermissionRequest", event)
    command = tool_command(event)
    text = command or tool_text(event)

    if is_git_write_to_third_party(text):
        return deny("PermissionRequest", "Denied: feishu-mcp-server is a third-party read-only repository.")
    if command and is_taskkill(command):
        return deny("PermissionRequest", "Denied: use S24_Session清理与重启 instead of裸 taskkill.")
    if command and is_pip_install_without_requirements(command):
        return deny("PermissionRequest", "Denied: dependency install must be aligned through requirements.txt and explicit human approval.")
    if command and is_git_destructive(command):
        return deny("PermissionRequest", "Denied: destructive git operation needs explicit human approval outside this hook.")
    if command and uses_blocked_text_writer(command):
        return deny("PermissionRequest", "Denied: Set-Content/Out-File are blocked; use WriteAllText with explicit UTF-8 encoding or apply_patch.")
    if command and is_python_base_modification(command):
        return deny("PermissionRequest", "Denied: system Python base library modifications are blocked.")

    return 0


if __name__ == "__main__":
    raise SystemExit(run_safely("PermissionRequest", main))
