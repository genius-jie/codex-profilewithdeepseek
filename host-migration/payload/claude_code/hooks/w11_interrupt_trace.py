#!/usr/bin/env python3
"""W11 G7 hardening PostToolUse hook (2026-06-30).

Auto-writes AskUserQuestion trace file when Agent calls AskUserQuestion.
The PreToolUse hook (pre_tool_use_guard.py W11 G7 section) checks this
trace file exists and is <5 min old, otherwise blocks governance_cli.py
manual-pipeline resume calls.

This implements the "interrupt MUST be user co-created" enforcement
without requiring Agent to remember to write the trace manually.
"""
from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(r"@@OPENCLAW_ROOT:win@@")


def read_event() -> dict:
    try:
        return json.loads(sys.stdin.read())
    except Exception:
        return {}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def current_runtime_paths():
    src_root = REPO_ROOT / "projects" / "automation-core" / "src"
    if str(src_root) not in sys.path:
        sys.path.insert(0, str(src_root))
    from pipeline_runtime_identity import resolve_owner_runtime_paths

    return resolve_owner_runtime_paths(REPO_ROOT)


def main() -> int:
    event = read_event()
    tool_name = event.get("tool_name", "")

    # 只在 AskUserQuestion 调用后写痕迹
    if tool_name != "AskUserQuestion":
        return 0

    # 提取 AskUserQuestion 的关键信息
    tool_input = event.get("tool_input", {})
    if not isinstance(tool_input, dict):
        tool_input = {}

    questions = tool_input.get("questions", [])
    if not isinstance(questions, list):
        questions = []

    # 简化:把 questions 摘要为"问了什么"
    question_summary = []
    for q in questions[:5]:  # 最多 5 个
        if isinstance(q, dict):
            q_text = q.get("question", "") or q.get("header", "")
            options = q.get("options", [])
            if isinstance(options, list):
                opt_labels = [o.get("label", "") if isinstance(o, dict) else str(o) for o in options[:4]]
            else:
                opt_labels = []
            question_summary.append({
                "question": str(q_text)[:200],
                "options": opt_labels,
            })

    runtime_paths = current_runtime_paths()
    launch_marker = runtime_paths.launch_marker_path
    if not launch_marker.is_file():
        # 没有 W11 active,不用写痕迹
        return 0

    # 写痕迹文件
    trace_path = runtime_paths.interrupt_trace_path
    trace_path.parent.mkdir(parents=True, exist_ok=True)

    # W11 launch 标记
    launch_data = {}
    if launch_marker.is_file():
        try:
            launch_data = json.loads(launch_marker.read_text(encoding="utf-8"))
        except Exception:
            pass

    trace = {
        "schema_version": "w11-interrupt-decision-trace.v1",
        "created_at": now_iso(),
        "tool_name": tool_name,
        "thread_id": launch_data.get("thread_id", "unknown"),
        "w11_task_id": launch_data.get("task_id", "unknown"),
        "w11_task_description": launch_data.get("task_description", ""),
        "blast_radius": launch_data.get("blast_radius", ""),
        "questions_asked": question_summary,
        "agent_invoked_ask_user_question": True,
        # L1 hook 校验:这一行 evidence_ref
        "evidence_ref": f"ask_user_question://{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}-{os.getpid()}",
        "note": "L1 hook 5分钟过期;L2 强制 _provenance.evidence_ref 引用此格式",
    }

    trace_path.write_text(
        json.dumps(trace, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    # 输出 hook feedback
    output = {
        "message": (
            f"[W11 G7] AskUserQuestion 痕迹已写入: {trace_path}\n"
            f"  thread_id: {trace['thread_id']}\n"
            f"  questions: {len(question_summary)} 个\n"
            f"  有效期: 5 分钟\n"
            f"  evidence_ref: {trace['evidence_ref']}\n"
            "  提示: 用此 evidence_ref 写 resume payload 的 _provenance.evidence_ref"
        )
    }
    print(json.dumps(output, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
