#!/usr/bin/env python3
"""Regression tests for Claude Code Stop-hook text and state isolation."""

from __future__ import annotations

import importlib.util
import json
import os
import tempfile
from pathlib import Path


HOOK_DIR = Path(__file__).resolve().parents[1]
MODULE_PATH = HOOK_DIR / "stop_guard_template.py"


def load_module():
    spec = importlib.util.spec_from_file_location("claude_stop_guard", MODULE_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    guard = load_module()
    text_cases = [
        ("pending 数量：0。", ""),
        ("最终验证通过：`pending_failure_review=0`。", ""),
        ("pending: empty。", ""),
        ("pending 已清空。", ""),
        ("`pending_failure_review=0`，但 TODO 仍需处理。", "final answer contains unresolved current-task work"),
        ("已完成，但 `pending=1`。", "final answer contains unresolved current-task work"),
        ("pending=0，但 TODO 仍需处理。", "final answer contains unresolved current-task work"),
        ("pending 已清空，但 TODO 仍需处理。", "final answer contains unresolved current-task work"),
        ("Hook pending 有 TODO 待处理，其余已清空。", "final answer contains unresolved current-task work"),
        ("pending_a 仍需修复，pending_b 为空。", "final answer contains unresolved current-task work"),
    ]
    for text, expected in text_cases:
        actual = guard.text_guard_reason(text)
        if actual != expected:
            raise AssertionError(f"text_guard_reason({text!r}): expected {expected!r}, got {actual!r}")

    with tempfile.TemporaryDirectory(prefix="claude-stop-state-") as raw:
        state_path = Path(raw) / "state.json"
        state_path.write_text(
            json.dumps(
                {
                    "pending": {
                        "pending_failure_review@session:session-a": {
                            "reason": "tool reported error",
                            "owner_scope": "session:session-a",
                            "session_id": "session-a",
                        },
                        "pending_failure_review@session:session-b": {
                            "reason": "tool reported error",
                            "owner_scope": "session:session-b",
                            "session_id": "session-b",
                        },
                        "legacy_pending": {"reason": "unattributed old item"},
                    }
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        previous = os.environ.get("LOOP_ENGINEERING_STATE_FILE")
        os.environ["LOOP_ENGINEERING_STATE_FILE"] = str(state_path)
        try:
            pending_a = guard.pending_items({"session_id": "session-a", "turn_id": "turn-a"})
            if list(pending_a) != ["pending_failure_review@session:session-a"]:
                raise AssertionError(f"session-a saw unrelated pending: {pending_a}")
            pending_b = guard.pending_items({"session_id": "session-b", "turn_id": "turn-b"})
            if list(pending_b) != ["pending_failure_review@session:session-b"]:
                raise AssertionError(f"session-b saw unrelated pending: {pending_b}")
        finally:
            if previous is None:
                os.environ.pop("LOOP_ENGINEERING_STATE_FILE", None)
            else:
                os.environ["LOOP_ENGINEERING_STATE_FILE"] = previous

    print("test_stop_guard_template: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
