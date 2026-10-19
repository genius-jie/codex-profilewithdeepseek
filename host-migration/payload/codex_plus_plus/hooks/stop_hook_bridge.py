#!/usr/bin/env python3
"""Bridge module for the Codex++ Stop hook.

Writes a structured JSON report to the Codex++ hook-state directory so an
OpenClaw Commander skill can inspect the last Stop decision. This module is
imported by stop_guard.py and must never crash the hook caller.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from hook_common import CODEX_HOME, now_iso


COMMANDER_STATE_DIR: Path = CODEX_HOME / "hook-state" / "commander"
BRIDGE_FILE: Path = COMMANDER_STATE_DIR / "stop_bridge.json"
BRIDGE_LOCK: Path = COMMANDER_STATE_DIR / "stop_bridge.lock"
BRIDGE_HISTORY: Path = COMMANDER_STATE_DIR / "bridge_history.jsonl"

_STALE_LOCK_SECONDS: float = 10.0
_OUTPUT_PREVIEW_LIMIT: int = 2000
_GIT_SUMMARY_LIMIT: int = 6000
STOP_RECEIPT_MARKER = "STOP_COMPLETION_RECEIPT"
MAX_RECEIPT_FILE_BYTES = 65536
COMPLETE_RECEIPT_STATUSES = {"complete", "completed", "done", "success", "pass", "passed", "已完成", "完成"}
HUMAN_BLOCKED_RECEIPT_STATUSES = {"blocked", "wait_human", "human_blocked", "blocked_by_human", "阻断", "等待人工"}
EMPTY_RECEIPT_VALUES = {"", "none", "null", "[]", "n/a", "na", "无", "没有", "无待办", "无剩余"}
_WINDOWS_PATH_RE = re.compile(r"(?:\\\\\?\\)?[A-Za-z]:\\[^`\"'\r\n<>|]+")
_TRAILING_PATH_CHARS = " \t\r\n`'\".,;:，。；：、)]}）】>"
_EVENT_CWD_KEYS = {
    "cwd",
    "codex_cwd",
    "current_working_directory",
    "working_directory",
    "workdir",
    "workspace",
    "workspace_dir",
    "workspace_path",
    "target_cwd",
    "target_workspace",
    "repo_root",
    "project_dir",
}
_OUTPUT_CWD_HINTS = (
    "current working directory",
    "target workspace",
    "workspace",
    "working directory",
    "workdir",
    "cwd",
    "当前工作目录",
    "目标工作区",
    "工作区",
)
_EXPECTED_CWD_ENV_KEYS = (
    "CODEX_COMMANDER_EXPECTED_CWD",
    "OPENCLAW_COMMANDER_EXPECTED_CWD",
    "COMMANDER_EXPECTED_CWD",
)
_BASELINE_STATUS_HASH_ENV_KEYS = (
    "CODEX_COMMANDER_BASELINE_STATUS_HASH",
    "OPENCLAW_COMMANDER_BASELINE_STATUS_HASH",
    "COMMANDER_BASELINE_STATUS_HASH",
)
_TASK_TOKEN_ENV_KEYS = (
    "CODEX_COMMANDER_TASK_TOKEN",
    "OPENCLAW_COMMANDER_TASK_TOKEN",
    "COMMANDER_TASK_TOKEN",
)
_EXPECTED_CWD_EVENT_KEYS = {
    "expected_cwd",
    "commander_expected_cwd",
    "openclaw_expected_cwd",
    "dispatch_cwd",
    "task_workdir",
    "task_working_directory",
}


@contextmanager
def _bridge_lock(timeout_seconds: float = 2.0) -> Iterator[None]:
    """Best-effort file lock for the bridge report."""
    COMMANDER_STATE_DIR.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + timeout_seconds
    handle: int | None = None
    while time.monotonic() < deadline:
        try:
            handle = os.open(str(BRIDGE_LOCK), os.O_CREAT | os.O_EXCL | os.O_RDWR)
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
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _clean_path_text(value: object) -> str:
    text = str(value or "").strip().strip("`'\"")
    text = text.rstrip(_TRAILING_PATH_CHARS)
    if text.startswith("\\\\?\\"):
        text = text[4:]
    return text


def _safe_resolve(path: Path) -> Path:
    try:
        return path.resolve()
    except Exception:
        return path.resolve(strict=False)


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _is_internal_codex_path(path: Path) -> bool:
    resolved = _safe_resolve(path)
    for internal in (CODEX_HOME / "hooks", CODEX_HOME / "hook-state"):
        internal_resolved = _safe_resolve(internal)
        if resolved == internal_resolved or _is_relative_to(resolved, internal_resolved):
            return True
    return False


def _git_root_for(path: Path) -> Path | None:
    try:
        candidate = _safe_resolve(path)
        if candidate.is_file():
            candidate = candidate.parent
        if not candidate.exists():
            return None
        result = subprocess.run(
            ["git", "-C", str(candidate), "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=5,
            encoding="utf-8",
            errors="replace",
        )
        if result.returncode != 0:
            return None
        root_text = (result.stdout or "").strip()
        return _safe_resolve(Path(root_text)) if root_text else None
    except Exception:
        return None


def _path_candidate(path_text: object, score: int, require_git: bool = True) -> tuple[int, Path] | None:
    cleaned = _clean_path_text(path_text)
    if not cleaned:
        return None
    try:
        path = Path(cleaned)
    except Exception:
        return None
    if not path.is_absolute() or _is_internal_codex_path(path):
        return None
    root = _git_root_for(path)
    if root is None:
        if require_git:
            return None
        resolved = _safe_resolve(path)
        if resolved.exists() and resolved.is_file():
            return score, resolved.parent
        if resolved.exists() and resolved.is_dir():
            return score, resolved
        return None
    resolved = _safe_resolve(path)
    target = resolved if resolved.exists() and resolved.is_dir() else root
    return score, target


def _event_path_candidates(value: object, key_hint: str = "") -> list[tuple[int, Path, str]]:
    candidates: list[tuple[int, Path, str]] = []
    if isinstance(value, dict):
        for key, item in value.items():
            lower = str(key).lower()
            explicit = lower in _EVENT_CWD_KEYS or any(part in lower for part in ("cwd", "workdir", "workspace"))
            if explicit and isinstance(item, str):
                candidate = _path_candidate(item, 100, require_git=False)
                if candidate:
                    score, path = candidate
                    candidates.append((score, path, "event"))
            if isinstance(item, (dict, list)):
                candidates.extend(_event_path_candidates(item, lower))
        return candidates
    if isinstance(value, list):
        for item in value:
            candidates.extend(_event_path_candidates(item, key_hint))
    return candidates


def _output_path_candidates(output_text: str) -> list[tuple[int, Path, str]]:
    candidates: list[tuple[int, Path, str]] = []
    for match in _WINDOWS_PATH_RE.finditer(output_text or ""):
        context = output_text[max(0, match.start() - 120) : match.start()].lower()
        score = 50 if any(hint in context for hint in _OUTPUT_CWD_HINTS) else 10
        candidate = _path_candidate(match.group(0), score)
        if candidate:
            candidate_score, path = candidate
            candidates.append((candidate_score, path, "output"))
    return candidates


def _resolve_target_cwd(event: dict[str, Any], output_text: str) -> tuple[Path | None, str]:
    candidates = [*_event_path_candidates(event), *_output_path_candidates(output_text)]
    if not candidates:
        return None, "hook_fallback"
    candidates.sort(key=lambda item: (item[0], len(str(item[1]))), reverse=True)
    return candidates[0][1], candidates[0][2]


def _event_value_for_keys(value: object, keys: set[str]) -> object | None:
    if isinstance(value, dict):
        for key, item in value.items():
            if str(key).lower() in keys:
                return item
        for item in value.values():
            found = _event_value_for_keys(item, keys)
            if found is not None:
                return found
    elif isinstance(value, list):
        for item in value:
            found = _event_value_for_keys(item, keys)
            if found is not None:
                return found
    return None


def _first_env_value(keys: tuple[str, ...]) -> str:
    for key in keys:
        value = os.environ.get(key)
        if value:
            return value.strip()
    return ""


def _expected_cwd(event: dict[str, Any]) -> Path | None:
    for raw in (_first_env_value(_EXPECTED_CWD_ENV_KEYS), _event_value_for_keys(event, _EXPECTED_CWD_EVENT_KEYS)):
        candidate = _path_candidate(raw, 100, require_git=False)
        if candidate:
            return candidate[1]
    return None


def _cwd_matches(target: Path | None, expected: Path | None) -> bool | None:
    if expected is None:
        return None
    if target is None:
        return False
    target_resolved = _safe_resolve(target)
    expected_resolved = _safe_resolve(expected)
    if target_resolved == expected_resolved:
        return True
    target_root = _git_root_for(target_resolved)
    expected_root = _git_root_for(expected_resolved)
    return bool(target_root and expected_root and target_root == expected_root)


def _receipt_values(value: object) -> list[object]:
    if value is None:
        return []
    if isinstance(value, bool):
        return [value] if value else []
    if isinstance(value, (list, tuple, set)):
        items: list[object] = []
        for item in value:
            items.extend(_receipt_values(item))
        return items
    if isinstance(value, dict):
        return [value] if value else []
    text = str(value).strip()
    if text.lower() in EMPTY_RECEIPT_VALUES:
        return []
    return [text] if text else []


def _load_receipt_path(value: object) -> dict[str, Any]:
    raw_path = str(value or "").strip().strip("`").strip()
    if not raw_path:
        return {"_parse_error": "STOP_COMPLETION_RECEIPT receipt_path is empty."}
    path = Path(raw_path).expanduser()
    if not path.is_absolute():
        return {"_parse_error": "STOP_COMPLETION_RECEIPT receipt_path must be an absolute path."}
    if not path.exists() or not path.is_file():
        return {"_parse_error": "STOP_COMPLETION_RECEIPT receipt_path not found."}
    if path.stat().st_size > MAX_RECEIPT_FILE_BYTES:
        return {"_parse_error": "STOP_COMPLETION_RECEIPT receipt_path is too large."}
    try:
        loaded = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return {"_parse_error": "STOP_COMPLETION_RECEIPT receipt_path must contain valid JSON."}
    if not isinstance(loaded, dict):
        return {"_parse_error": "STOP_COMPLETION_RECEIPT receipt_path must contain a JSON object."}
    loaded.setdefault("receipt_path", str(path))
    return loaded


def _completion_receipt(output_text: str) -> dict[str, Any]:
    marker_matches = list(
        re.finditer(rf"(?m)(?:^|[\s。.!?；;]){re.escape(STOP_RECEIPT_MARKER)}\s*(?:$|[:：])", output_text or "")
    )
    if not marker_matches:
        return {}
    surface = (output_text or "")[marker_matches[-1].end() :].lstrip(" \t:：\r\n")
    if not surface:
        return {"_parse_error": "STOP_COMPLETION_RECEIPT must be valid JSON."}
    if surface.startswith("```"):
        surface = re.sub(r"^```(?:json)?\s*", "", surface, count=1, flags=re.IGNORECASE)
    if re.match(r"^\{\s*(?:\.{3}|…)\s*\}", surface):
        return {"_parse_error": "STOP_COMPLETION_RECEIPT must be valid JSON."}
    try:
        value, _index = json.JSONDecoder().raw_decode(surface)
    except Exception:
        return {"_parse_error": "STOP_COMPLETION_RECEIPT must be valid JSON."}
    if not isinstance(value, dict):
        return {"_parse_error": "STOP_COMPLETION_RECEIPT must be a JSON object."}
    if value.get("receipt_path"):
        return _load_receipt_path(value.get("receipt_path"))
    return value


def _receipt_summary(output_text: str) -> dict[str, Any]:
    receipt = _completion_receipt(output_text)
    if not receipt:
        return {
            "present": False,
            "valid": False,
            "is_complete": False,
            "is_human_blocked": False,
            "status": "",
            "verification_count": 0,
            "open_item_count": 0,
            "blocker_count": 0,
            "parse_error": "",
            "contract_coverage": None,
            "contract_ids": [],
            "contracts_met": [],
            "skill_route": [],
        }
    parse_error = str(receipt.get("_parse_error") or "")
    status = str(receipt.get("status") or receipt.get("task_status") or "").strip().lower()
    open_items = _receipt_values(
        receipt.get("open_items")
        or receipt.get("remaining_items")
        or receipt.get("unresolved_actions")
        or receipt.get("todo")
    )
    blockers = _receipt_values(receipt.get("blockers") or receipt.get("external_blockers"))
    verification = _receipt_values(receipt.get("verification") or receipt.get("verified") or receipt.get("tests"))
    is_human_blocked = status in HUMAN_BLOCKED_RECEIPT_STATUSES and bool(blockers)
    is_complete = (
        not parse_error
        and status in COMPLETE_RECEIPT_STATUSES
        and bool(verification)
        and not open_items
        and not blockers
    )
    raw_coverage = receipt.get("contract_coverage")
    contract_coverage = float(raw_coverage) if raw_coverage is not None else None
    contract_ids = _receipt_values(receipt.get("contract_ids") or receipt.get("contracts_met"))
    contracts_met = _receipt_values(receipt.get("contracts_met") or receipt.get("contract_ids"))
    skill_route = _receipt_values(receipt.get("skill_route") or receipt.get("routes"))
    return {
        "present": True,
        "valid": not bool(parse_error),
        "is_complete": is_complete,
        "is_human_blocked": is_human_blocked,
        "status": status,
        "verification_count": len(verification),
        "open_item_count": len(open_items),
        "blocker_count": len(blockers),
        "parse_error": parse_error,
        "receipt_path": str(receipt.get("receipt_path") or ""),
        "contract_coverage": contract_coverage,
        "contract_ids": contract_ids,
        "contracts_met": contracts_met,
        "skill_route": skill_route,
    }


def _git_diff_summary(cwd: Path | None) -> str:
    root = _git_root_for(cwd) if cwd else None
    if root is None:
        return ""
    try:
        for command in (
            ["git", "-C", str(root), "diff", "--stat", "HEAD"],
            ["git", "-C", str(root), "diff", "--stat"],
        ):
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=10,
                encoding="utf-8",
                errors="replace",
            )
            if result.returncode == 0:
                return (result.stdout or "").strip()
    except Exception:
        pass
    return ""


def _git_status_snapshot(cwd: Path | None) -> dict[str, str]:
    root = _git_root_for(cwd) if cwd else None
    if root is None:
        return {"git_root": "", "git_status_summary": "", "git_status_hash": ""}
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "status", "--porcelain=v1", "--untracked-files=all"],
            capture_output=True,
            text=True,
            timeout=10,
            encoding="utf-8",
            errors="replace",
        )
        if result.returncode != 0:
            return {"git_root": str(root), "git_status_summary": "", "git_status_hash": ""}
        summary = (result.stdout or "").rstrip("\r\n")
        return {
            "git_root": str(root),
            "git_status_summary": summary[:_GIT_SUMMARY_LIMIT],
            "git_status_hash": _sha256(summary),
        }
    except Exception:
        return {"git_root": str(root), "git_status_summary": "", "git_status_hash": ""}


def _combined_git_diff_summary(cwd: Path | None, status_summary: str) -> str:
    diff_summary = _git_diff_summary(cwd)
    if diff_summary and status_summary:
        return (diff_summary + "\n-- status --\n" + status_summary)[:_GIT_SUMMARY_LIMIT]
    return (diff_summary or status_summary)[:_GIT_SUMMARY_LIMIT]


def write_bridge_report(
    event: dict[str, Any],
    output_text: str,
    guard_reason: str,
    pending: dict[str, Any],
    guard_decision: str | None = None,
) -> None:
    """Write the latest Stop decision for Codex Commander consumers."""
    try:
        COMMANDER_STATE_DIR.mkdir(parents=True, exist_ok=True)
        target_cwd, target_cwd_source = _resolve_target_cwd(event, output_text)
        expected_cwd = _expected_cwd(event)
        expected_cwd_match = _cwd_matches(target_cwd, expected_cwd)
        target_cwd_trusted = bool(
            target_cwd
            and (
                expected_cwd_match is True
                or (expected_cwd is None and target_cwd_source == "event")
            )
        )
        receipt = _receipt_summary(output_text)
        status_snapshot = _git_status_snapshot(target_cwd)
        baseline_status_hash = _first_env_value(_BASELINE_STATUS_HASH_ENV_KEYS)
        commander_task_token = _first_env_value(_TASK_TOKEN_ENV_KEYS)
        git_status_hash = status_snapshot.get("git_status_hash", "")
        changed_since_baseline = None
        if baseline_status_hash and git_status_hash:
            changed_since_baseline = baseline_status_hash != git_status_hash
        report: dict[str, Any] = {
            "timestamp": now_iso(),
            "session_id": event.get("session_id", ""),
            "codex_cwd": str(target_cwd) if target_cwd else os.getcwd(),
            "codex_cwd_source": target_cwd_source,
            "expected_cwd": str(expected_cwd) if expected_cwd else "",
            "expected_cwd_match": expected_cwd_match,
            "target_cwd_trusted": target_cwd_trusted,
            "hook_cwd": os.getcwd(),
            "output_text_preview": output_text[:_OUTPUT_PREVIEW_LIMIT],
            "output_text_hash": _sha256(output_text),
            "guard_reason": guard_reason,
            "guard_decision": guard_decision or ("blocked" if guard_reason else "allowed"),
            "pending_state": pending,
            "receipt": receipt,
            "has_completion_receipt": bool(receipt.get("is_complete")),
            "has_human_blocker": (
                bool(receipt.get("is_human_blocked"))
                or "WAIT_HUMAN_BLOCKER" in output_text
                or "WAIT_HUMAN" in output_text
            ),
            **status_snapshot,
            "baseline_status_hash": baseline_status_hash,
            "commander_task_token": commander_task_token,
            "changed_since_baseline": changed_since_baseline,
            "git_diff_summary": _combined_git_diff_summary(target_cwd, status_snapshot.get("git_status_summary", "")),
            "contract_coverage": receipt.get("contract_coverage"),
            "contract_ids": receipt.get("contract_ids", []),
            "contracts_met": receipt.get("contracts_met", []),
            "skill_route": receipt.get("skill_route", []),
        }

        with _bridge_lock():
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
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
                raise

            try:
                with BRIDGE_HISTORY.open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps(report, ensure_ascii=False) + "\n")
            except Exception:
                pass
    except Exception:
        pass


def read_bridge_report() -> dict[str, Any] | None:
    try:
        if not BRIDGE_FILE.exists():
            return None
        data = json.loads(BRIDGE_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def clear_bridge_report() -> None:
    try:
        if BRIDGE_FILE.exists():
            BRIDGE_FILE.unlink()
    except Exception:
        pass
