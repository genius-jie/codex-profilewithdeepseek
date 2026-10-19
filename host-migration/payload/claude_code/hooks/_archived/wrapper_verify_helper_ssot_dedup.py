#!/usr/bin/env python3
"""
wrapper_verify_helper_ssot_dedup.py — User-level SSOT dedup gate runner

Thin shim that locates the project-local verify-helper-ssot-dedup.py
and runs it from the user's hook directory. Centralizes the SSOT gate
so future Claude Code sessions can `bash run_ssot_gate.sh` or invoke
directly from CLAUDE.md instructions.

Source-of-truth location:
  $OPENCLAW_MONO/projects/automation-core/scripts/verify-helper-ssot-dedup.py

Behavior:
  - If project script not found: exit 0 (passive — no project = no check)
  - Strict mode flag passed through via --strict
  - Logs result to $HOOK_DIR/logs/ssot-dedup-gate.jsonl

Usage:
  python ~/.claude/hooks/wrapper_verify_helper_ssot_dedup.py
  python ~/.claude/hooks/wrapper_verify_helper_ssot_dedup.py --strict
  python ~/.claude/hooks/wrapper_verify_helper_ssot_dedup.py --fix-report

Exit codes:
  0 — gate green OR project not found (passive)
  1 — gate red (violations found)
  2 — script error

Anchor:
  - src-dedup-refactor-8-commit-pushed-2026-07-03.md (commit 19 + 20)
  - projects/automation-core/scripts/verify-helper-ssot-dedup.py (303 行 SSOT 漂移门禁)
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HOOK_DIR = Path(__file__).resolve().parent
LOG_DIR = HOOK_DIR / "logs"
LOG_FILE = LOG_DIR / "ssot-dedup-gate.jsonl"

# Project-local gate script location (resolved at runtime)
PROJECT_GATE = Path(
    os.environ.get(
        "OPENCLAW_MONO",
        Path.home() / "openclaw-mono" / "projects" / "automation-core" / "scripts" / "verify-helper-ssot-dedup.py",
    )
)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_log(record: dict) -> None:
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        with LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    except Exception:
        pass


def main() -> int:
    args = sys.argv[1:]
    record = {
        "ts": now_iso(),
        "gate_script": str(PROJECT_GATE),
        "exists": PROJECT_GATE.exists(),
        "args": args,
    }

    if not PROJECT_GATE.exists():
        # Passive — openclaw-mono not present, skip silently
        record["outcome"] = "skipped_not_found"
        write_log(record)
        return 0

    try:
        result = subprocess.run(
            [sys.executable, str(PROJECT_GATE), *args],
            capture_output=True,
            text=True,
            timeout=300,
        )
        record["exit_code"] = result.returncode
        record["stdout_preview"] = result.stdout[:1500]
        record["stderr_preview"] = result.stderr[:500]
        record["outcome"] = "green" if result.returncode == 0 else "red"
    except subprocess.TimeoutExpired:
        record["outcome"] = "timeout"
        record["exit_code"] = -1
    except Exception as exc:
        record["outcome"] = "error"
        record["error"] = str(exc)[:500]
        record["exit_code"] = -2

    write_log(record)

    # 重要: 不在用户级 hooks 主动阻断 — 返回 exit code 让调用方决定
    return 0  # Passive — log only, caller decides action


if __name__ == "__main__":
    sys.exit(main())
