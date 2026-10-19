#!/usr/bin/env python3
"""Claude Code user-level hook runner for the local guard layer.

Reads JSON event from stdin, delegates to the specified guard script,
and writes structured JSON output to stdout.

Usage (from hooks config):
  python hook_runner.py --event PreToolUse --script pre_tool_use_guard.py
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from claude_context_common import CALLER_CWD_ENV, trusted_runner_cwd


HOOK_DIR = Path(__file__).resolve().parent
LOG_DIR = HOOK_DIR / "logs"
RUN_LOG = LOG_DIR / "hook-events.jsonl"
MAX_TEXT = 1200


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def preview(text: str) -> str:
    text = text.replace("\r", "\\r").replace("\n", "\\n")
    return text[:MAX_TEXT]


def write_record(record: dict[str, Any]) -> None:
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        with RUN_LOG.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    except Exception:
        return


def run_child(event_name: str, script: Path, raw_event: str) -> int:
    started = time.monotonic()
    env = os.environ.copy()
    runner_cwd = os.getcwd()
    # The parent may carry a stale or forged value.  Only this runner writes
    # the child override after validating the event/outer cwd.
    env.pop(CALLER_CWD_ENV, None)
    caller_cwd, caller_cwd_source = trusted_runner_cwd(raw_event, runner_cwd)
    if caller_cwd:
        env[CALLER_CWD_ENV] = caller_cwd
    env["PYTHONPATH"] = str(HOOK_DIR) + os.pathsep + env.get("PYTHONPATH", "")
    record_base = {
        "event": event_name,
        "script": str(script),
        "cwd": runner_cwd,
        "caller_cwd": caller_cwd,
        "caller_cwd_source": caller_cwd_source,
        "pid": os.getpid(),
        "raw_event_len": len(raw_event),
        "raw_event_preview": preview(raw_event),
    }
    write_record({"phase": "started", "ts": now_iso(), **record_base})
    try:
        proc = subprocess.run(
            [sys.executable, str(script)],
            input=raw_event,
            text=True,
            capture_output=True,
            cwd=str(HOOK_DIR),
            env=env,
            timeout=25,
            check=False,
        )
        duration_ms = int((time.monotonic() - started) * 1000)
        write_record(
            {
                "phase": "completed",
                "ts": now_iso(),
                "returncode": proc.returncode,
                "duration_ms": duration_ms,
                "stdout_preview": preview(proc.stdout),
                "stderr_preview": preview(proc.stderr),
                **record_base,
            }
        )
        if proc.stdout:
            sys.stdout.write(proc.stdout)
        if proc.stderr:
            sys.stderr.write(proc.stderr)
        return proc.returncode
    except Exception as exc:
        duration_ms = int((time.monotonic() - started) * 1000)
        write_record(
            {
                "phase": "runner_exception",
                "ts": now_iso(),
                "duration_ms": duration_ms,
                "exception_type": type(exc).__name__,
                "exception": str(exc),
                **record_base,
            }
        )
        print(f"hook_runner failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--event", required=True)
    parser.add_argument("--script", required=True)
    args = parser.parse_args()
    raw_event = sys.stdin.read()
    return run_child(args.event, Path(args.script), raw_event)


if __name__ == "__main__":
    raise SystemExit(main())
