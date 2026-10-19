#!/usr/bin/env python3
"""Universal PostToolUse audit for Claude Code / Codex++.

Records lightweight evidence after tool execution:
1. Governed Markdown change tracking
2. Command failure fingerprinting
3. git commit/push state tracking

Runs AFTER tool execution completes. Cannot block, only observes and logs.
"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path


HOOK_DIR = Path(__file__).resolve().parent
LOG_DIR = HOOK_DIR / "logs"
AUDIT_LOG = LOG_DIR / "post-tool-audit.jsonl"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_event() -> dict:
    try:
        return json.loads(sys.stdin.read())
    except Exception:
        return {}


def tool_input(event: dict) -> str:
    tool_input_val = event.get("tool_input", {})
    if isinstance(tool_input_val, dict):
        return tool_input_val.get("command", "") or tool_input_val.get("content", "") or json.dumps(tool_input_val)
    return str(tool_input_val)


def tool_output(event: dict) -> str:
    """Extract tool output/result text, tolerant of field-name variants.

    Claude Code PostToolUse payload uses different keys across versions/runtimes
    (tool_response / tool_output / output), and Bash results may be nested under
    stdout/stderr or content[]. Accept all known shapes so failure detection
    doesn't silently miss.
    """
    for key in ("tool_response", "tool_output", "output", "result"):
        value = event.get(key)
        if value is None:
            continue
        if isinstance(value, str):
            return value
        if isinstance(value, dict):
            # Bash result object: {stdout, stderr, content, exit_code, ...}
            for sub in ("stdout", "stderr", "content", "output", "message"):
                if sub in value:
                    sub_val = value[sub]
                    if isinstance(sub_val, list):
                        joined = "\n".join(str(x) for x in sub_val if x is not None)
                        if joined.strip():
                            return joined
                    elif isinstance(sub_val, str) and sub_val.strip():
                        return sub_val
            return json.dumps(value, ensure_ascii=False)
        if isinstance(value, list):
            return "\n".join(str(x) for x in value if x is not None)
    return ""


def write_audit(record: dict) -> None:
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        with AUDIT_LOG.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    except Exception:
        return


GOVERNED_MD_PATTERNS = [
    r"skills[/\\].*\.md",
    r"rules[/\\].*\.md",
    r"workflows[/\\].*\.md",
    r"index[/\\].*\.md",
    r"references[/\\].*\.md",
    r"AGENTS\.md",
]


def detect_governed_md(text: str) -> list[str]:
    return [p for p in GOVERNED_MD_PATTERNS if re.search(p, text)]


def command_failed(event: dict) -> bool:
    """Check if tool execution reported failure. Prioritize exit_code over keywords."""
    exit_code = event.get("exit_code")
    if exit_code is None:
        # Bash results often nest exit_code under tool_response / tool_output object
        for container_key in ("tool_response", "tool_output", "result"):
            container = event.get(container_key)
            if isinstance(container, dict) and "exit_code" in container:
                exit_code = container.get("exit_code")
                break
    if exit_code is not None:
        return exit_code != 0
    # Fallback: keyword heuristic only when exit_code is absent
    output = tool_output(event)
    error_signals = ["Traceback (most recent", "FAILED", "CommandNotFoundException", "SyntaxError:", "not recognized as", "Access is denied"]
    return any(signal in output for signal in error_signals)


def main() -> int:
    event = read_event()
    tool_name = event.get("tool_name", "")
    input_text = tool_input(event)
    output_text = tool_output(event)
    notes: list[str] = []

    # 1. Track governed Markdown changes
    governed = detect_governed_md(input_text)
    if governed and tool_name in ("Edit", "Write", "MultiEdit", "apply_patch", "Bash"):
        notes.append(f"governed_md_changed: {', '.join(governed[:5])}")
        write_audit({
            "ts": now_iso(),
            "event": "governed_md_changed",
            "tool": tool_name,
            "files": governed[:10],
        })

    # 2. Track git operations
    if re.search(r"git\s+commit\b", input_text, re.IGNORECASE):
        notes.append("git_commit_observed")
        write_audit({"ts": now_iso(), "event": "git_commit", "tool": tool_name})

    if re.search(r"git\s+push\b", input_text, re.IGNORECASE):
        if "403" in output_text or "permission" in output_text.lower():
            notes.append("git_push_permission_failure")
        else:
            notes.append("git_push_success")
        write_audit({"ts": now_iso(), "event": "git_push", "tool": tool_name, "success": "403" not in output_text})

    # 3. Record command failures
    if command_failed(event):
        fingerprint = re.sub(r"\s+", " ", input_text).strip()[:200]
        notes.append(f"command_failed: {fingerprint[:80]}")
        write_audit({
            "ts": now_iso(),
            "event": "command_failed",
            "tool": tool_name,
            "fingerprint": fingerprint,
        })

    # Output summary for Claude's context (non-blocking)
    if notes:
        output = {
            "message": "[HOOK:POST_TOOL_AUDIT] " + "; ".join(notes)
        }
        print(json.dumps(output, ensure_ascii=False))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
