#!/usr/bin/env python3
"""Universal PreToolUse guard for Claude Code.

Blocks dangerous operations BEFORE tool execution (cross-project invariants
only, matching AGENTS.md Git Safety Protocol):
1. Destructive git (reset --hard, checkout <file>, --no-verify, --force push)
2. Dependency installs without a requirements-file option (-r/--requirement) -> advisory only
3. Naked process termination (taskkill/Stop-Process) -> blocking
4. Governed Markdown edit reminder (non-blocking)

Exit code 2 = block the tool call (Claude Code convention).
Exit code 0 = allow.

Scope decision (2026-09-20 audit, Hook Control change):
  The former W11 delivery-manifest write gate (5b) and W11 G7 resume guard (6)
  are REMOVED from this Claude-side copy. Their physical verifier
  (projects/automation-core/scripts/w11_delivery_manifest.py) no longer exists
  on any drive, and their fail-closed mono_root anchor would have denied every
  Edit/Write in every project. Project-scoped completion/authorization control
  belongs to project settings, never to the host-global managed layer.
  Engine isolation unchanged: the Codex-side sibling keeps its own policy via
  hook_common.is_business_code_write; do not sync this removal across hosts
  without its own audit.

Authorization profile (Owner decision 2026-09-21, revised 2026-09-22 audit close-out):
  Rules 1 and 3 are blocking — aligned with the Codex-side guard whose
  git/taskkill blocks have run since June 2026 with zero incident.
  Rule 2 (dependency declarative flow) is advisory only: the guard cannot
  reliably tell a global interpreter from an active project venv, so a hard
  block would false-block legitimate named installs and false-pass global
  `-r` installs. It is not promoted to a global enforced block.
  Rule 4 stays a non-blocking governance reminder. This profile is the source
  behavior that the managed PreToolUse registration package publishes.
"""

from __future__ import annotations

import json
import re
import sys

from claude_context_common import resolve_effective_cwd


def read_event() -> dict:
    try:
        return json.loads(sys.stdin.read())
    except Exception:
        return {}


def deny(reason: str, event_name: str = "PreToolUse") -> int:
    """Block the tool call (event-adaptive).

    PreToolUse: exit 2 + reason on STDERR. Claude blocks on exit 2 and uses
    stderr as the blocking reason when no valid decision JSON is emitted.
    PermissionRequest: exit 0 + permissionDecision deny (Claude Code convention).
    """
    if event_name == "PermissionRequest":
        output = {
            "hookSpecificOutput": {
                "hookEventName": "PermissionRequest",
                "permissionDecision": "deny",
                "permissionDecisionReason": reason,
            }
        }
        print(json.dumps(output, ensure_ascii=False))
        return 0
    sys.stderr.write(reason + "\n")
    return 2


def tool_input(event: dict) -> str:
    """Extract the tool input text from Claude Code's event payload."""
    tool_input_val = event.get("tool_input", {})
    if isinstance(tool_input_val, dict):
        return tool_input_val.get("command", "") or tool_input_val.get("content", "") or json.dumps(tool_input_val)
    return str(tool_input_val)


# --- Guard rules ---

GIT_DESTRUCTIVE_PATTERNS = [
    r"git\s+reset\s+--hard",
    r"git\s+checkout\s+--\s+\.",
    r"git\s+checkout\s+(?!-b\b)[^\s]+\s+--",
    r"git\s+restore\s+",
    r"git\s+clean\s+-[fdx]",
    r"git\s+commit\s+.*--no-verify",
    r"git\s+commit\s+.*\s-n\b",
    r"git\s+push\s+.*--force",
]

# (2026-09-20 audit closure) GIT_BYPASS_ENV_PATTERNS / is_git_bypass_env removed:
# their only control target was the retired D-drive pre-commit W11_SKIP escape
# hatch; the E-drive core OS has no such mechanism. The durable invariant
# "never skip commit hooks" stays covered by GIT_DESTRUCTIVE_PATTERNS
# (--no-verify / -n). Re-add only with a current, owner-approved control target.

PIP_INSTALL_PATTERNS = [
    r"\bpip(?:3)?\s+install\b",
    r"\bpython(?:3)?\s+-m\s+pip\s+install\b",
    r"\bpy\s+-m\s+pip\s+install\b",
]

# This rule intentionally checks only the declared dependency-flow option.
# It does not claim to detect the active interpreter or whether installation
# would land in a global environment.
PIP_REQUIREMENTS_OPTION_PATTERNS = [
    r"(?<!\S)-r(?:\s|=)",
    r"(?<!\S)--requirement(?:\s|=)",
]

TASKKILL_PATTERNS = [
    r"\btaskkill\b",
    r"\bStop-Process\b",
    r"\bkill\s+-\d+",
]

GOVERNED_MD_GLOBS = [
    r"skills[/\\].*\.md",
    r"rules[/\\].*\.md",
    r"workflows[/\\].*\.md",
    r"index[/\\].*\.md",
    r"references[/\\].*\.md",
    r"AGENTS\.md",
]

# Command channels: Claude Code exposes Bash and PowerShell as distinct tools
# (2.1.x). Execution-intent rules below must see both; Windows sessions may
# route through either. (2026-09-20 audit correction)
COMMAND_TOOLS = ("Bash", "PowerShell")


def is_git_destructive(text: str) -> bool:
    return any(re.search(p, text, re.IGNORECASE) for p in GIT_DESTRUCTIVE_PATTERNS)


# (2026-09-20) W11 delivery-manifest write gate removed from this Claude-side
# copy: its physical verifier exists neither in the retired D-drive monorepo
# layout nor in the current E-drive core OS, and its fail-closed mono_root
# anchor would deny every Edit/Write in every project. See module docstring
# Scope decision. The W11 business rule itself is NOT declared retired by this
# change; project-flow control belongs to the current core OS control entry.


def is_dependency_flow_hint(text: str) -> bool:
    """Return true when a pip install lacks a requirements-file option."""
    has_install = any(re.search(p, text, re.IGNORECASE) for p in PIP_INSTALL_PATTERNS)
    has_requirements_file = any(
        re.search(p, text, re.IGNORECASE) for p in PIP_REQUIREMENTS_OPTION_PATTERNS
    )
    return has_install and not has_requirements_file


def is_taskkill(text: str) -> bool:
    return any(re.search(p, text, re.IGNORECASE) for p in TASKKILL_PATTERNS)


def touches_governed_md(text: str) -> list[str]:
    return [p for p in GOVERNED_MD_GLOBS if re.search(p, text)]


def main() -> int:
    event = read_event()
    tool_name = event.get("tool_name", "")
    event_name = str(event.get("hook_event_name") or "PreToolUse")
    text = tool_input(event)

    # Only guard command channels and file-write tools that exist in the
    # current Claude Code tool list (2.1.x: Bash, PowerShell, Edit, Write;
    # MultiEdit/apply_patch are not real Claude tool names — audit closure
    # 2026-09-20, do not carry cross-host names without a consumer)
    if tool_name not in COMMAND_TOOLS + ("Edit", "Write"):
        return 0

    # 1. Destructive git (only check command channels, not Write/Edit file content)
    if tool_name in COMMAND_TOOLS and is_git_destructive(text):
        return deny(
            "Blocked: destructive git operation (reset --hard / checkout file / --no-verify / --force push). "
            "This violates the governance hook bypass ban. Use safe alternatives.",
            event_name=event_name,
        )

    # 1b. (removed 2026-09-20 audit closure — see GIT_BYPASS_ENV_PATTERNS note;
    # the --no-verify / -n invariant remains covered by rule 1 above)

    # 2. 依赖流程 — advisory（非阻断），仅命令通道生效。
    #    语义：依赖应通过 requirements 文件声明（-r/--requirement）。
    #    2026-09-22 审计收口：无法可靠判断目标解释器是全局还是已激活 venv，
    #    故不升级为全局强制阻断；仅在直接命名安装时提醒声明式依赖流程。
    if tool_name in COMMAND_TOOLS and is_dependency_flow_hint(text):
        output = {
            "message": (
                "[HOOK:DEPENDENCY_FLOW_HINT] Prefer declaring dependencies via a "
                "requirements file (pip install -r requirements.txt). Declared-"
                "dependency flow only; this does not detect whether the install "
                "lands in a global environment. Ask the human for an explicit "
                "exception when a direct package-name install is intentional."
            )
        }
        print(json.dumps(output, ensure_ascii=False))
        return 0

    # 3. Naked taskkill/process termination — 执行意图类，仅对命令通道生效。
    #    2026-09-21 Owner 授权升为硬阻断（对齐 Codex 侧三个月零事故实证）。
    if tool_name in COMMAND_TOOLS and is_taskkill(text):
        return deny(
            "Blocked: naked taskkill/Stop-Process is not allowed. "
            "Route process cleanup through proper service management (S44/NSSM).",
            event_name=event_name,
        )

    # 4. Governed Markdown reminder (non-blocking)
    governed = touches_governed_md(text)
    if governed:
        output = {
            "message": (
                "[HOOK:GOVERNED_MARKDOWN_HINT] "
                "You are editing governed Markdown. Remember the birth ceremony "
                "(asset-birth-ceremony.py: passport + registration + weave + hard gate) "
                "and ensure frontmatter passport fields are present. "
                f"Matched: {', '.join(governed[:5])}"
            )
        }
        print(json.dumps(output, ensure_ascii=False))
        return 0

    # (2026-09-20) former 5b W11 delivery-manifest gate and 6 W11 G7 resume
    # guard removed — see module docstring Scope decision.

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as _e:
        # fail-safe：guard 自身异常不应阻断用户操作，降级放行并记 stderr
        # （宁可漏拦一次，不能让 hook 崩溃锁死所有写操作）
        import traceback as _tb
        sys.stderr.write(f"[pre_tool_use_guard INTERNAL ERROR] {_e}\n{_tb.format_exc()}\n")
        raise SystemExit(0)
