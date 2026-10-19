#!/usr/bin/env python3
"""Bridge module for the Codex Stop hook.

Writes a structured JSON report to a shared file that the Codex Commander
(supervisor agent) can read. Imported by stop_guard.py — never executed
directly.

All file I/O uses explicit encoding='utf-8'.
All paths are absolute Windows paths.
Atomic writes use os.replace via a temp file.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from hook_common import CODEX_HOME, load_state, now_iso, save_state, state_lock

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

COMMANDER_STATE_DIR: Path = CODEX_HOME / "hook-state" / "commander"
BRIDGE_FILE: Path = COMMANDER_STATE_DIR / "stop_bridge.json"
BRIDGE_LOCK: Path = COMMANDER_STATE_DIR / "stop_bridge.lock"
BRIDGE_HISTORY: Path = COMMANDER_STATE_DIR / "bridge_history.jsonl"

_STALE_LOCK_SECONDS: float = 10.0
_OUTPUT_PREVIEW_LIMIT: int = 2000

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@contextmanager
def _bridge_lock(timeout_seconds: float = 2.0) -> Iterator[None]:
    """File-based lock identical in pattern to hook_common.state_lock."""
    COMMANDER_STATE_DIR.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + timeout_seconds
    handle: int | None = None
    while time.monotonic() < deadline:
        try:
            handle = os.open(
                str(BRIDGE_LOCK), os.O_CREAT | os.O_EXCL | os.O_RDWR
            )
            break
        except FileExistsError:
            try:
                if time.time() - BRIDGE_LOCK.stat().st_mtime > _STALE_LOCK_SECONDS:
                    BRIDGE_LOCK.unlink()
                    continue
            except FileNotFoundError:
                continue
            except Exception:
                pass
            time.sleep(0.05)
    try:
        yield
    finally:
        if handle is not None:
            os.close(handle)
            try:
                BRIDGE_LOCK.unlink()
            except FileNotFoundError:
                pass


def _sha256(text: str) -> str:
    """Return the hex SHA-256 digest of *text*."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _git_diff_summary() -> str:
    """Run ``git diff --stat HEAD`` and return the short summary."""
    try:
        result = subprocess.run(
            ["git", "diff", "--stat", "HEAD"],
            capture_output=True,
            text=True,
            timeout=10,
            encoding="utf-8",
        )
        return (result.stdout or "").strip()
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def write_bridge_report(
    event: dict[str, Any],
    output_text: str,
    guard_reason: str,
    pending: dict[str, Any],
) -> None:
    """Write a structured JSON report for the Codex Commander.

    Parameters
    ----------
    event:
        The raw Stop hook event dict (contains session_id etc.).
    output_text:
        The full assistant output text extracted by stop_guard.
    guard_reason:
        The reason string if stop_guard blocked; empty string if allowed.
    pending:
        The current pending-state dict from hook state.
    """
    try:
        COMMANDER_STATE_DIR.mkdir(parents=True, exist_ok=True)

        report: dict[str, Any] = {
            "timestamp": now_iso(),
            "session_id": event.get("session_id", ""),
            "codex_cwd": os.getcwd(),
            "output_text_preview": output_text[:_OUTPUT_PREVIEW_LIMIT],
            "output_text_hash": _sha256(output_text),
            "guard_reason": guard_reason,
            "guard_decision": "blocked" if guard_reason else "allowed",
            "pending_state": pending,
            "has_completion_receipt": "STOP_COMPLETION_RECEIPT" in output_text,
            "has_human_blocker": (
                "WAIT_HUMAN_BLOCKER" in output_text
                or "WAIT_HUMAN" in output_text
            ),
            "git_diff_summary": _git_diff_summary(),
        }

        with _bridge_lock():
            # Atomic write via temp file + os.replace
            tmp_fd, tmp_path = tempfile.mkstemp(
                dir=str(COMMANDER_STATE_DIR),
                prefix="stop_bridge_",
                suffix=".tmp",
            )
            try:
                with os.fdopen(tmp_fd, "w", encoding="utf-8") as fh:
                    json.dump(report, fh, ensure_ascii=False, indent=2)
                os.replace(tmp_path, str(BRIDGE_FILE))
            except Exception:
                # Clean up the temp file on failure
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
                raise

            # Append a one-line JSONL entry to the history log
            try:
                with open(
                    str(BRIDGE_HISTORY), "a", encoding="utf-8"
                ) as fh:
                    fh.write(
                        json.dumps(report, ensure_ascii=False) + "\n"
                    )
            except Exception:
                pass  # History append is best-effort

    except Exception:
        # This runs inside a hook — must never crash the caller.
        pass


def read_bridge_report() -> dict[str, Any] | None:
    """Read the latest bridge report if it exists.

    Returns
    -------
    dict or None
        Parsed JSON report, or ``None`` if the file is missing / invalid.
    """
    try:
        if not BRIDGE_FILE.exists():
            return None
        text = BRIDGE_FILE.read_text(encoding="utf-8")
        data = json.loads(text)
        if isinstance(data, dict):
            return data
        return None
    except Exception:
        return None


def clear_bridge_report() -> None:
    """Delete the bridge report file if it exists."""
    try:
        if BRIDGE_FILE.exists():
            BRIDGE_FILE.unlink()
    except Exception:
        pass
