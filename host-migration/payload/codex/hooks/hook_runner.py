#!/usr/bin/env python3
"""Codex hook runner with local command-level telemetry."""

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


HOOK_DIR = Path(__file__).resolve().parent
CODEX_HOME = Path(os.environ.get("CODEX_HOME") or (Path.home() / ".codex"))
RUN_LOG = CODEX_HOME / "hook-state" / "hook-runner-events.jsonl"
MAX_TEXT = 1200
CALLER_CWD_ENV = "CODEX_HOOK_CALLER_CWD"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def preview(text: str) -> str:
    text = text.replace("\r", "\\r").replace("\n", "\\n")
    return text[:MAX_TEXT]


def write_record(record: dict[str, Any]) -> None:
    try:
        RUN_LOG.parent.mkdir(parents=True, exist_ok=True)
        with RUN_LOG.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    except Exception:
        return


def normalize_absolute_path(value: Any) -> str | None:
    """Return a normalized absolute path, or None for an untrusted value."""
    if not isinstance(value, str):
        return None
    candidate = value.strip()
    drive, tail = os.path.splitdrive(candidate)
    if (
        not candidate
        or "\x00" in candidate
        or not os.path.isabs(candidate)
        or not drive
        or not tail.startswith(("\\", "/"))
    ):
        return None
    try:
        return os.path.normpath(os.path.abspath(candidate))
    except (OSError, ValueError):
        return None


def parse_event(raw_event: str) -> dict[str, Any]:
    try:
        parsed = json.loads(raw_event)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def is_within_hook_dir(path: str) -> bool:
    """Do not mistake the runner's fixed child directory for a caller cwd."""
    try:
        candidate = os.path.normcase(os.path.realpath(path))
        hook_dir = os.path.normcase(os.path.realpath(str(HOOK_DIR)))
        return os.path.commonpath([candidate, hook_dir]) == hook_dir
    except (OSError, ValueError):
        return False


def trusted_caller_cwd(raw_event: str, runner_cwd: str) -> tuple[str | None, str]:
    """Choose only host-event or runner-observed cwd; inherited env is ignored."""
    event_cwd = normalize_absolute_path(parse_event(raw_event).get("cwd"))
    if event_cwd:
        return event_cwd, "event_cwd"
    outer_cwd = normalize_absolute_path(runner_cwd)
    if outer_cwd and not is_within_hook_dir(outer_cwd):
        return outer_cwd, "runner_cwd"
    return None, "unknown"


def run_child(event_name: str, script: Path, raw_event: str) -> int:
    started = time.monotonic()
    env = os.environ.copy()
    # Only this runner may supply the child with a caller cwd. Discard values
    # inherited from an arbitrary parent before selecting a verified source.
    env.pop(CALLER_CWD_ENV, None)
    runner_cwd = os.getcwd()
    caller_cwd, caller_cwd_source = trusted_caller_cwd(raw_event, runner_cwd)
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
        print(f"hook_runner failed before child completion: {type(exc).__name__}: {exc}", file=sys.stderr)
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
