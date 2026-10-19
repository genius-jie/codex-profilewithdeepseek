#!/usr/bin/env python3
"""Shared helpers for thin OpenClaw Codex hooks."""

from __future__ import annotations

import json
import os
import re
import sys
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


REPO_ROOT = Path(r"@@OPENCLAW_ROOT:win@@")
GLOBAL_AGENT_ROOT = Path(r"@@GENERAL_ROOT:win@@")
# Keep the Codex++ profile self-contained when the desktop host does not
# export CODEX_HOME (the TOML env table is not inherited by hook processes).
# An explicit environment override remains available for isolated test homes.
PROFILE_CODEX_HOME = Path(__file__).absolute().parents[1]
CODEX_HOME = Path(os.environ.get("CODEX_HOME") or PROFILE_CODEX_HOME)


def _first_existing_path(*candidates: Path) -> Path:
    """Resolve a moved governance asset without reviving the old layout."""

    for candidate in candidates:
        if candidate.is_file():
            return candidate
    # Keep a deterministic diagnostic path when an installation is incomplete.
    return candidates[0]


STATE_DIR = CODEX_HOME / "hook-state"
STATE_PATH = STATE_DIR / "openclaw-mono-pending.json"
STATE_LOCK_PATH = STATE_DIR / "openclaw-mono-pending.lock"
HOOK_RUN_EVENT_PATH = STATE_DIR / "hook-run-events.jsonl"
HOOK_AUDIT_MAX_SCOPES = 12
HOOK_AUDIT_POST_TOOL_THRESHOLD = 24
HOOK_EVOLUTION_MAX_CANDIDATES = 20
HOOK_EVOLUTION_READY_THRESHOLD = 3
HOOK_EVOLUTION_CLOSED_STATUSES = {"observed_closed", "recorded_closed", "reviewed_closed"}
STALE_LOCK_SECONDS = 10.0
DEFAULT_HOOK_RUN_EVENT_MAX_BYTES = 25 * 1024 * 1024
DEFAULT_HOOK_RUN_EVENT_MAX_BACKUPS = 3


def env_int(name: str, default: int, minimum: int = 1) -> int:
    raw = os.environ.get(name)
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value >= minimum else default


HOOK_RUN_EVENT_MAX_BYTES = env_int("CODEX_HOOK_RUN_EVENT_MAX_BYTES", DEFAULT_HOOK_RUN_EVENT_MAX_BYTES)
HOOK_RUN_EVENT_MAX_BACKUPS = env_int("CODEX_HOOK_RUN_EVENT_MAX_BACKUPS", DEFAULT_HOOK_RUN_EVENT_MAX_BACKUPS)

ROUTING_CONTEXT = {
    "repo": "openclaw-mono",
    "repo_root": str(REPO_ROOT),
    "repo_w1": str(
        _first_existing_path(
            REPO_ROOT / ".agents" / "workflows" / "W1_前置思考.md",
            REPO_ROOT / ".agents" / "control" / "orchestration" / "W1_前置思考.md",
        )
    ),
    "global_w1": str(
        _first_existing_path(
            GLOBAL_AGENT_ROOT / "control" / "orchestration" / "W1_前置思考.md",
            GLOBAL_AGENT_ROOT / "workflows" / "W1_前置思考.md",
        )
    ),
    "agent_constitution": str(
        _first_existing_path(
            GLOBAL_AGENT_ROOT / "assets" / "rules" / "agent-constitution.md",
            GLOBAL_AGENT_ROOT / "rules" / "agent-constitution.md",
        )
    ),
    "m1": str(
        _first_existing_path(
            GLOBAL_AGENT_ROOT / "assets" / "skills" / "M1_治理预加载门禁" / "SKILL.md",
            GLOBAL_AGENT_ROOT / "skills" / "M1_治理预加载门禁" / "SKILL.md",
        )
    ),
    "w9": str(
        _first_existing_path(
            REPO_ROOT / ".agents" / "workflows" / "W9_出口验收.md",
            REPO_ROOT / ".agents" / "assets" / "workflows" / "W9_出口验收.md",
        )
    ),
    "w7": str(
        _first_existing_path(
            REPO_ROOT / ".agents" / "workflows" / "W7_知识回流分析.md",
            REPO_ROOT / ".agents" / "assets" / "workflows" / "W7_知识回流分析.md",
        )
    ),
    "s15": str(
        _first_existing_path(
            REPO_ROOT / ".agents" / "skills" / "S15_Git提交全链路" / "SKILL.md",
            REPO_ROOT / ".agents" / "assets" / "skills" / "S15_Git提交全链路" / "SKILL.md",
        )
    ),
    "hard_gate": str(
        REPO_ROOT
        / ".agents"
        / "orchestration"
        / "Langgraph"
        / "docs"
        / "scripts"
        / "verify-governance-hard-gate.ps1"
    ),
}

GOVERNED_MD_PATTERNS = [
    r"(^|[\\/])AGENTS\.md$",
    r"(^|[\\/])\.codex[\\/].+\.md$",
    r"(^|[\\/])\.agent[\\/].+\.md$",
    r"(^|[\\/])\.agents[\\/].+\.md$",
    r"(^|[\\/])docs[\\/].+\.md$",
    r"(^|[\\/])skills[\\/].+\.md$",
    r"(^|[\\/])workflows[\\/].+\.md$",
    r"(^|[\\/])rules[\\/].+\.md$",
    r"(^|[\\/])index[\\/].+\.md$",
    r"(^|[\\/])references[\\/].+\.md$",
]


def read_event() -> dict[str, Any]:
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            return {}
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return parsed
        return {
            "_raw_event": parsed,
            "_raw_event_type": type(parsed).__name__,
        }
    except json.JSONDecodeError:
        return {}


def emit_json(payload: dict[str, Any]) -> int:
    print(json.dumps(payload, ensure_ascii=False))
    return 0


def additional_context(event_name: str, message: str, **extra: Any) -> int:
    output: dict[str, Any] = {
        "hookSpecificOutput": {
            "hookEventName": event_name,
            "additionalContext": message,
        }
    }
    output.update(extra)
    return emit_json(output)


def rotated_path(path: Path, index: int) -> Path:
    return path.with_name(f"{path.name}.{index}")


def rotate_log_if_needed(path: Path, max_bytes: int, max_backups: int) -> None:
    try:
        if not path.exists() or path.stat().st_size < max_bytes:
            return
        for index in range(max_backups, 1, -1):
            newer = rotated_path(path, index)
            older = rotated_path(path, index - 1)
            if newer.exists():
                newer.unlink()
            if older.exists():
                older.replace(newer)
        first = rotated_path(path, 1)
        if first.exists():
            first.unlink()
        path.replace(first)
    except Exception:
        return


def _write_hook_run_event(payload: dict[str, Any]) -> None:
    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        base = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "pid": os.getpid(),
            "cwd": os.getcwd(),
            "codex_home": str(CODEX_HOME),
        }
        rotate_log_if_needed(HOOK_RUN_EVENT_PATH, HOOK_RUN_EVENT_MAX_BYTES, HOOK_RUN_EVENT_MAX_BACKUPS)
        with HOOK_RUN_EVENT_PATH.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({**base, **payload}, ensure_ascii=False) + "\n")
    except Exception:
        pass


def run_safely(event_name: str, fn: Callable[[], int]) -> int:
    try:
        rc = int(fn() or 0)
        _write_hook_run_event({"event_name": event_name, "returncode": rc, "status": "completed"})
        return rc
    except Exception as exc:
        message = f"[HOOK:ERROR_DOWNGRADED]\n{event_name} hook caught {type(exc).__name__}: {exc}"
        _write_hook_run_event(
            {
                "event_name": event_name,
                "returncode": 0,
                "status": "exception_downgraded",
                "exception_type": type(exc).__name__,
                "exception": str(exc),
            }
        )
        if event_name == "Stop":
            return emit_json({"decision": "block", "reason": message})
        return additional_context(event_name, message)


def deny(event_name: str, reason: str) -> int:
    if event_name == "PermissionRequest":
        return emit_json(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PermissionRequest",
                    "decision": {"behavior": "deny", "message": reason},
                }
            }
        )
    return emit_json(
        {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": reason,
            }
        }
    )


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


PENDING_SESSION_SEPARATOR = "@session:"
PENDING_TURN_SEPARATOR = "@turn:"

# These entries describe a transient failure in one execution turn.  They
# must not follow an entire conversation: a later user turn is a new unit of
# work, even when it uses the same session id.  Keep governance artefacts
# such as pending_w9 session-scoped until their own verifier clears them.
TRANSIENT_TURN_PENDING_KEYS = {
    "pending_failure_review",
    "pending_permission_review",
    "pending_s15",
}


def pending_base_key(key: str) -> str:
    for separator in (PENDING_SESSION_SEPARATOR, PENDING_TURN_SEPARATOR):
        if separator in key:
            return key.split(separator, 1)[0]
    return key


def pending_owner_scope(event: dict[str, Any] | None) -> str | None:
    if not event:
        return None
    session_id = str(event.get("session_id") or "").strip()
    if session_id:
        return f"session:{session_id}"
    turn_id = str(event.get("turn_id") or "").strip()
    if turn_id:
        return f"turn:{turn_id}"
    return None


def pending_storage_key(key: str, event: dict[str, Any] | None) -> str:
    base_key = pending_base_key(key)
    owner_scope = pending_owner_scope(event)
    return f"{base_key}@{owner_scope}" if owner_scope else base_key


def pending_owned_by_event(key: str, item: dict[str, Any], event: dict[str, Any]) -> bool:
    base_key = pending_base_key(key)
    current_turn = str(event.get("turn_id") or "").strip()
    item_turn = str(item.get("turn_id") or "").strip()

    # A transient failure belongs to the turn that produced it.  This also
    # handles legacy session-scoped records: if they have no turn id, they
    # are historical evidence rather than a blocker for a newer turn.
    if base_key in TRANSIENT_TURN_PENDING_KEYS and current_turn:
        if item_turn:
            return item_turn == current_turn
        return False

    owner_scope = str(item.get("owner_scope") or "").strip()
    current_scope = pending_owner_scope(event)
    if owner_scope:
        return bool(current_scope and owner_scope == current_scope)

    item_session = str(item.get("session_id") or "").strip()
    current_session = str(event.get("session_id") or "").strip()
    if item_session:
        return bool(current_session and item_session == current_session)
    if PENDING_SESSION_SEPARATOR in key:
        key_session = key.split(PENDING_SESSION_SEPARATOR, 1)[1]
        return bool(current_session and key_session == current_session)

    if item_turn:
        return bool(current_turn and item_turn == current_turn)
    if PENDING_TURN_SEPARATOR in key:
        key_turn = key.split(PENDING_TURN_SEPARATOR, 1)[1]
        return bool(current_turn and key_turn == current_turn)

    # A session-scoped event cannot safely claim an older unattributed item.
    # Keep the legacy fallback only for hosts that do not expose a session id.
    return not bool(str(event.get("session_id") or "").strip())


def pending_items_for_event(pending: dict[str, Any], event: dict[str, Any]) -> dict[str, Any]:
    return {
        key: item
        for key, item in pending.items()
        if isinstance(item, dict) and pending_owned_by_event(key, item, event)
    }


def pending_item_for_event(
    pending: dict[str, Any], key: str, event: dict[str, Any]
) -> dict[str, Any] | None:
    base_key = pending_base_key(key)
    preferred_key = pending_storage_key(base_key, event)
    preferred = pending.get(preferred_key)
    if isinstance(preferred, dict) and pending_owned_by_event(preferred_key, preferred, event):
        return preferred
    for stored_key, item in pending.items():
        if (
            pending_base_key(stored_key) == base_key
            and isinstance(item, dict)
            and pending_owned_by_event(stored_key, item, event)
        ):
            return item
    return None


def load_state() -> dict[str, Any]:
    if not STATE_PATH.exists():
        return {"pending": {}}
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"pending": {}}


def save_state(state: dict[str, Any]) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    tmp_path = STATE_PATH.with_name(f"{STATE_PATH.name}.{os.getpid()}.tmp")
    tmp_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp_path, STATE_PATH)


@contextmanager
def state_lock(timeout_seconds: float = 2.0):
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + timeout_seconds
    handle: int | None = None
    while time.monotonic() < deadline:
        try:
            handle = os.open(str(STATE_LOCK_PATH), os.O_CREAT | os.O_EXCL | os.O_RDWR)
            break
        except FileExistsError:
            try:
                if time.time() - STATE_LOCK_PATH.stat().st_mtime > STALE_LOCK_SECONDS:
                    STATE_LOCK_PATH.unlink()
                    continue
            except FileNotFoundError:
                continue
            except Exception:
                pass
            time.sleep(0.05)
    if handle is None:
        raise TimeoutError(f"timed out waiting for hook state lock: {STATE_LOCK_PATH}")
    try:
        yield
    finally:
        if handle is not None:
            os.close(handle)
            try:
                STATE_LOCK_PATH.unlink()
            except FileNotFoundError:
                pass


def mark_pending(
    key: str,
    reason: str,
    files: list[str] | None = None,
    event: dict[str, Any] | None = None,
) -> None:
    with state_lock():
        state = load_state()
        pending = state.setdefault("pending", {})
        storage_key = pending_storage_key(key, event)
        item = pending.setdefault(storage_key, {})
        item["reason"] = reason
        item["updated_at"] = now_iso()
        owner_scope = pending_owner_scope(event)
        if owner_scope:
            item["owner_scope"] = owner_scope
        if event:
            session_id = str(event.get("session_id") or "").strip()
            turn_id = str(event.get("turn_id") or "").strip()
            if session_id:
                item["session_id"] = session_id
            if turn_id:
                item["turn_id"] = turn_id
        if files:
            known = list(dict.fromkeys([*item.get("files", []), *files]))
            item["files"] = known[:80]
        save_state(state)


def clear_pending(key: str, event: dict[str, Any] | None = None) -> None:
    with state_lock():
        state = load_state()
        pending = state.setdefault("pending", {})
        base_key = pending_base_key(key)
        storage_key = pending_storage_key(base_key, event)
        pending.pop(storage_key, None)
        if storage_key != base_key:
            legacy = pending.get(base_key)
            if isinstance(legacy, dict) and pending_owned_by_event(base_key, legacy, event or {}):
                pending.pop(base_key, None)
        save_state(state)


def clear_pending_all(key: str) -> None:
    """Clear a repository-wide pending gate after its global verifier passes."""

    with state_lock():
        state = load_state()
        pending = state.setdefault("pending", {})
        base_key = pending_base_key(key)
        for stored_key in list(pending):
            if pending_base_key(stored_key) == base_key:
                pending.pop(stored_key, None)
        save_state(state)


def pending_summary() -> str:
    pending = load_state().get("pending", {})
    if not pending:
        return ""
    lines = ["Pending hook state from an earlier turn:"]
    for key, value in pending.items():
        reason = value.get("reason", "")
        updated_at = value.get("updated_at", "")
        files = value.get("files") or []
        suffix = f" files={len(files)}" if files else ""
        lines.append(f"- {pending_base_key(key)}: {reason} ({updated_at}){suffix}")
    return "\n".join(lines)


def hook_scope_id(event: dict[str, Any]) -> str:
    turn_id = event.get("turn_id")
    if turn_id:
        return f"turn:{turn_id}"
    session_id = event.get("session_id")
    if session_id:
        source = event.get("source") or event.get("hook_event_name") or "session"
        return f"session:{session_id}:{source}"
    return "unknown"


def record_hook_run(event_name: str, event: dict[str, Any], note: str | None = None) -> None:
    try:
        with state_lock():
            state = load_state()
            audit = state.setdefault("hook_audit", {})
            scopes = audit.setdefault("scopes", {})
            order = audit.setdefault("order", [])
            scope = hook_scope_id(event)
            timestamp = now_iso()
            entry = scopes.setdefault(
                scope,
                {
                    "first_seen": timestamp,
                    "last_seen": timestamp,
                    "turn_id": event.get("turn_id"),
                    "session_id": event.get("session_id"),
                    "counts": {},
                    "notes": [],
                },
            )
            entry["last_seen"] = timestamp
            counts = entry.setdefault("counts", {})
            counts[event_name] = int(counts.get(event_name, 0)) + 1
            if note:
                notes = entry.setdefault("notes", [])
                notes.append(f"{timestamp} {note}")
                entry["notes"] = notes[-8:]
            if scope in order:
                order.remove(scope)
            order.append(scope)
            while len(order) > HOOK_AUDIT_MAX_SCOPES:
                stale = order.pop(0)
                scopes.pop(stale, None)
            save_state(state)
    except Exception:
        return


def hook_self_audit(event: dict[str, Any]) -> tuple[str, list[str]]:
    try:
        scope = hook_scope_id(event)
        state = load_state()
        entry = (state.get("hook_audit") or {}).get("scopes", {}).get(scope)
        if not entry:
            return "", []
        counts = entry.get("counts") or {}
        ordered_names = ["SessionStart", "UserPromptSubmit", "PreToolUse", "PermissionRequest", "PostToolUse", "Stop"]
        summary = ", ".join(f"{name}={counts.get(name, 0)}" for name in ordered_names if counts.get(name, 0))
        anomalies: list[str] = []
        post_count = int(counts.get("PostToolUse", 0))
        pre_count = int(counts.get("PreToolUse", 0))
        permission_count = int(counts.get("PermissionRequest", 0))
        stop_count = int(counts.get("Stop", 0))
        if post_count > HOOK_AUDIT_POST_TOOL_THRESHOLD:
            anomalies.append(f"PostToolUse ran {post_count} times in this turn; review tool batching if the UI feels noisy.")
        if post_count and not pre_count:
            anomalies.append("PostToolUse ran but PreToolUse was not observed for this turn; matcher coverage may need review.")
        if permission_count > 3:
            anomalies.append(f"PermissionRequest ran {permission_count} times; permission policy may be too chatty.")
        if stop_count > 2:
            anomalies.append(f"Stop ran {stop_count} times; check for a continuation loop or sticky pending state.")
        return summary, anomalies
    except Exception:
        return "", []


def evolution_candidate_key(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:96] or "hook-evolution-candidate"


def record_hook_evolution_candidates(event: dict[str, Any], summary: str, anomalies: list[str]) -> list[str]:
    if not anomalies:
        return []
    promoted: list[str] = []
    try:
        with state_lock():
            state = load_state()
            evolution = state.setdefault("hook_evolution", {})
            candidates = evolution.setdefault("candidates", {})
            order = evolution.setdefault("order", [])
            scope = hook_scope_id(event)
            timestamp = now_iso()
            for anomaly in anomalies:
                key = evolution_candidate_key(anomaly)
                item = candidates.setdefault(
                    key,
                    {
                        "kind": "hook_self_evolution",
                        "status": "observing",
                        "first_seen": timestamp,
                        "last_seen": timestamp,
                        "count": 0,
                        "scopes": [],
                        "evidence": [],
                        "next_action": "none",
                    },
                )
                was_closed = item.get("status") in HOOK_EVOLUTION_CLOSED_STATUSES
                scopes = item.setdefault("scopes", [])
                if scope not in scopes:
                    scopes.append(scope)
                    item["count"] = int(item.get("count", 0)) + 1
                item["last_seen"] = timestamp
                item["latest_summary"] = summary
                evidence = item.setdefault("evidence", [])
                evidence.append({"at": timestamp, "scope": scope, "summary": summary, "anomaly": anomaly})
                item["evidence"] = evidence[-5:]
                item.setdefault("next_action", "none")
                if (not was_closed) and int(item.get("count", 0)) >= HOOK_EVOLUTION_READY_THRESHOLD:
                    item["status"] = "ready_for_m8_review"
                    promoted.append(anomaly)
                if key in order:
                    order.remove(key)
                order.append(key)
            while len(order) > HOOK_EVOLUTION_MAX_CANDIDATES:
                stale = order.pop(0)
                candidates.pop(stale, None)
            save_state(state)
    except Exception:
        return []
    return promoted


def hook_evolution_summary() -> str:
    try:
        state = load_state()
        candidates = (state.get("hook_evolution") or {}).get("candidates") or {}
        ready = [
            (key, value)
            for key, value in candidates.items()
            if value.get("status") == "ready_for_m8_review"
        ]
        if not ready:
            return ""
        lines = ["Hook evolution candidates ready for M8/W7 review:"]
        for _key, value in sorted(ready, key=lambda item: str(item[1].get("last_seen", "")), reverse=True)[:5]:
            evidence = value.get("evidence") or []
            latest = evidence[-1].get("anomaly", "") if evidence else ""
            lines.append(f"- count={value.get('count', 0)} latest={latest}")
        return "\n".join(lines)
    except Exception:
        return ""


def tool_command(event: dict[str, Any]) -> str:
    tool_input = event.get("tool_input") or {}
    if isinstance(tool_input, dict):
        for key in ("command", "script"):
            value = tool_input.get(key)
            if isinstance(value, str):
                return value
    return ""


def tool_name(event: dict[str, Any]) -> str:
    return str(event.get("tool_name") or event.get("tool") or event.get("name") or "")


def contains_unquoted_output_redirect(command: str) -> bool:
    quote: str | None = None
    for index, char in enumerate(command):
        if quote:
            if char == quote:
                quote = None
            continue
        if char in {"'", '"'}:
            quote = char
            continue
        if char == ">" and command[index + 1 : index + 2] != "&":
            return True
    return False


def strip_command_literals(command: str) -> str:
    without_heredocs = re.sub(r"@(['\"])[\s\S]*?\1@", " ", command, flags=re.DOTALL)
    return re.sub(r"'[^']*'|\"(?:\\.|[^\"])*\"", " ", without_heredocs)


def uses_blocked_text_writer(command: str) -> bool:
    command_surface = strip_command_literals(command)
    return bool(re.search(r"\b(set-content|out-file)\b", command_surface, re.IGNORECASE))


def command_may_modify_files(name: str, command: str) -> bool:
    lowered_name = name.lower()
    command_surface = strip_command_literals(command)
    lowered_command = command_surface.lower()
    if lowered_name in {"edit", "write", "apply_patch"}:
        return True
    return bool(
        re.search(
            r"\b(set-content|out-file|add-content|remove-item|move-item|copy-item|new-item|tee-object|git\s+add|git\s+commit|git\s+mv)\b|writealltext",
            lowered_command,
        )
        or contains_unquoted_output_redirect(command_surface)
    )


def command_targets_governed_markdown(name: str, command: str, governed: list[str]) -> bool:
    """Distinguish a governed-document write from a read-only inspection."""

    if not governed:
        return False
    lowered_name = (name or "").lower()
    if lowered_name in {"edit", "write", "apply_patch"}:
        return True
    write_targets = command_write_target_surface(command)
    if not write_targets:
        return False
    normalized_targets = normalize_slashes(write_targets).lower()
    return any(normalize_slashes(path).lower() in normalized_targets for path in governed)


def command_write_target_surface(command: str) -> str:
    """Return only paths/arguments that a command writes to.

    A shell command often reads a governed Markdown file and writes an
    unrelated JSON/text receipt in the same invocation.  Matching the entire
    command made that read look like a governed-document write and left a
    sticky W9 pending item.  Keep the write-intent detector broad, but narrow
    the W9 target matcher to writer arguments and redirect destinations.
    """

    targets: list[str] = []
    assignment_values: dict[str, str] = {}
    for match in re.finditer(r"\$(\w+)\s*=\s*(['\"])(.*?)\2", command, re.DOTALL):
        assignment_values[match.group(1).lower()] = match.group(3)

    def add_segment(segment: str) -> None:
        if not segment:
            return
        resolved = segment
        for variable, value in assignment_values.items():
            resolved = re.sub(
                rf"\${re.escape(variable)}\b",
                lambda _match, replacement=value: replacement,
                resolved,
                flags=re.IGNORECASE,
            )
        targets.append(resolved)

    # PowerShell/CMD redirects: include the destination, not the input side
    # of the pipeline or an earlier Get-Content argument.
    for match in re.finditer(
        r"(?<![\w])(?:\d*)>{1,2}\s*(?:['\"]([^'\"]+)['\"]|([^\s;|]+))",
        command,
        re.IGNORECASE,
    ):
        add_segment(match.group(1) or match.group(2) or "")

    # File writers whose target commonly follows -Path/-LiteralPath or is a
    # positional argument.  Split at command boundaries so a preceding read
    # of a governed file does not become a false write target.
    writer_pattern = re.compile(
        r"\b(?:set-content|out-file|add-content|remove-item|move-item|copy-item|new-item|tee-object)\b"
        r"(?P<tail>[^;|\r\n]*)",
        re.IGNORECASE,
    )
    for match in writer_pattern.finditer(command):
        tail = match.group("tail")
        path_arg = re.search(
            r"(?:-literalpath|-path|--path)\s+(?:['\"]([^'\"]+)['\"]|([^\s]+))",
            tail,
            re.IGNORECASE,
        )
        add_segment(path_arg.group(1) or path_arg.group(2) if path_arg else tail)

    # git add/mv carry explicit path arguments; git commit itself does not
    # write a Markdown document and therefore is intentionally excluded.
    for match in re.finditer(r"\bgit\s+(?:add|mv)\b(?P<tail>[^;|\r\n]*)", command, re.IGNORECASE):
        add_segment(match.group("tail"))

    # Node/Python-style writers.  Resolve simple variables assigned earlier in
    # the same command, which covers the common receipt-writing pattern.
    for match in re.finditer(
        r"\b(?:writealltext|write_text|write_bytes)\b(?P<tail>[^;\r\n]*)",
        command,
        re.IGNORECASE,
    ):
        add_segment(match.group("tail"))

    return "\n".join(targets)


def tool_text(event: dict[str, Any]) -> str:
    try:
        return json.dumps(event.get("tool_input") or {}, ensure_ascii=False)
    except Exception:
        return str(event.get("tool_input") or "")


def normalize_slashes(text: str) -> str:
    return text.replace("\\", "/")


def references_third_party_feishu(text: str) -> bool:
    lowered = normalize_slashes(text).lower()
    return "feishu-mcp-server" in lowered or "openclaw-config/feishu-mcp-server" in lowered


def strip_feishu_exclude_pathspecs(text: str) -> str:
    lowered = normalize_slashes(text).lower()
    return re.sub(
        r"(?:\"[^\"]*:\(exclude\)[^\"]*feishu-mcp-server[^\"]*\"|'[^']*:\(exclude\)[^']*feishu-mcp-server[^']*'|:\(exclude\)\S*feishu-mcp-server\S*)",
        "",
        lowered,
    )


def has_direct_third_party_feishu_reference(text: str) -> bool:
    return references_third_party_feishu(strip_feishu_exclude_pathspecs(text))


def is_git_write_to_third_party(text: str) -> bool:
    lowered = text.lower()
    if not has_direct_third_party_feishu_reference(text):
        return False
    return bool(re.search(r"\bgit\b.*\b(add|commit|push|checkout|reset|restore)\b", lowered))


def is_governed_md_path(path_text: str) -> bool:
    normalized = normalize_slashes(path_text)
    if is_memory_ad_hoc_note_path(normalized):
        return False
    return any(re.search(pattern, normalized, re.IGNORECASE) for pattern in GOVERNED_MD_PATTERNS)


def is_memory_ad_hoc_note_path(path_text: str) -> bool:
    normalized = normalize_slashes(path_text).lower()
    return "/.codex/memories/extensions/ad_hoc/notes/" in normalized and normalized.endswith(".md")


def extract_patch_file_targets(text: str) -> list[str]:
    targets = re.findall(r"^\*\*\* (?:Add|Update|Delete) File:\s+(.+)$", text, flags=re.MULTILINE)
    return [target.strip() for target in targets if target.strip()]


def extract_path_mentions(text: str) -> list[str]:
    candidates = re.findall(
        r"(?:[A-Za-z]:[\\/][^'\"`\s<>|;]+|projects[\\/][^'\"`\s<>|;]+)",
        text,
        flags=re.IGNORECASE,
    )
    return list(dict.fromkeys(candidate.strip(",:;()[]{}\"'") for candidate in candidates if candidate.strip()))


def extract_governed_md_mentions(text: str) -> list[str]:
    patch_targets = extract_patch_file_targets(text)
    if patch_targets:
        return list(dict.fromkeys(target for target in patch_targets if is_governed_md_path(target)))
    candidates = re.findall(r"[^'\"`<>\s]+\.md", text, flags=re.IGNORECASE)
    flat: list[str] = []
    for value in candidates:
        cleaned = value.strip(",:;()[]{}")
        if cleaned and is_governed_md_path(cleaned):
            flat.append(cleaned)
    return list(dict.fromkeys(flat))


# -- W11 delivery manifest: write-time business code guard (Rung 2) ----------
# Keep this in sync with .git/hooks/pre-commit and
# projects/automation-core/scripts/w11_delivery_manifest.py.
_W11_BUSINESS_CODE_SUFFIXES = {
    ".ts", ".tsx", ".js", ".jsx", ".py", ".css", ".sql", ".mjs", ".cjs",
}


def tool_file_targets(event: dict[str, Any]) -> list[str]:
    """Extract file targets from Edit/Write/apply_patch-style tool events."""
    tool_input = event.get("tool_input") or {}
    targets: list[str] = []
    if isinstance(tool_input, dict):
        for key in ("file_path", "path", "notebook_path"):
            value = tool_input.get(key)
            if isinstance(value, str) and value.strip():
                targets.append(value.strip())
    patch_text = tool_command(event) or tool_text(event)
    targets.extend(extract_patch_file_targets(patch_text))
    return list(dict.fromkeys(targets))


def is_w11_business_code_path(path_text: str) -> bool:
    """Return whether a path is governed business code for W11 delivery binding."""
    normalized = normalize_slashes(str(path_text or "")).strip().strip('"')
    if not normalized:
        return False
    lowered = normalized.lower()
    root_prefix = normalize_slashes(str(REPO_ROOT)).lower().rstrip("/") + "/"
    if lowered.startswith(root_prefix):
        normalized = normalized[len(root_prefix):]
    normalized = normalized.lstrip("/")
    if not normalized.startswith("projects/"):
        return False
    if normalized.startswith("projects/automation-core/"):
        return False
    return Path(normalized).suffix.lower() in _W11_BUSINESS_CODE_SUFFIXES


def is_business_code_write(event: dict[str, Any]) -> list[str]:
    """Return W11-governed business code targets in this write event."""
    name = tool_name(event)
    if name.lower() not in {"edit", "write", "apply_patch", "notebookedit"}:
        command = tool_command(event)
        if name.lower() not in {"bash", "shell_command"} or not command:
            return []
        has_write_intent = (
            command_may_modify_files(name, command)
            or bool(re.search(r"\b(writealltext|write_text|write_bytes)\b", command, re.IGNORECASE))
            or bool(re.search(r"\bopen\s*\([^)]*,\s*['\"][wa+x]", command, re.IGNORECASE))
        )
        if not has_write_intent:
            return []
        return [target for target in extract_path_mentions(command) if is_w11_business_code_path(target)]
    return [target for target in tool_file_targets(event) if is_w11_business_code_path(target)]


def w11_verify_business_writes(paths: list[str]) -> tuple[bool, str]:
    """Use the repository delivery-manifest verifier, matching the commit gate."""
    verifier = REPO_ROOT / "projects" / "automation-core" / "scripts" / "w11_delivery_manifest.py"
    if not verifier.exists():
        return True, ""
    try:
        import subprocess
        proc = subprocess.run(
            [sys.executable, str(verifier), "verify", "--staged-from-stdin"],
            input="\n".join(paths),
            capture_output=True,
            text=True,
            timeout=15,
        )
        if proc.returncode == 0:
            return True, ""
        return False, (proc.stderr or proc.stdout or "").strip()
    except Exception:
        return True, ""


def command_has_unbounded_git_add(command: str) -> bool:
    lowered = normalize_slashes(command).lower()
    if not re.search(r"\bgit(\.exe)?\b.*\badd\b", lowered):
        return False
    if ":(exclude)openclaw-config/feishu-mcp-server" in lowered:
        return False
    return bool(re.search(r"\bgit(\.exe)?\b.*\badd\b.*(?:-a\b|--all\b|\s\.\s*$)", lowered))


def _pip_install_surface(command: str) -> str:
    return re.sub(r"'[^']*'|\"[^\"]*\"", " <arg> ", command or "").lower()


def is_pip_install_without_requirements(command: str) -> bool:
    lowered = _pip_install_surface(command)
    if not re.search(r"\b(python\s+-m\s+pip|pip(?:3)?)\s+install\b", lowered):
        return False
    return "-r " not in lowered and "--requirement" not in lowered


def is_pip_install_with_requirements(command: str) -> bool:
    lowered = _pip_install_surface(command)
    return bool(
        re.search(r"\b(python\s+-m\s+pip|pip(?:3)?)\s+install\b", lowered)
        and ("-r " in lowered or "--requirement" in lowered)
    )


def is_taskkill(command: str) -> bool:
    return bool(re.search(r"\btaskkill(?:\.exe)?\b", command, re.IGNORECASE))


def is_git_destructive(command: str) -> bool:
    lowered = command.lower()
    return bool(re.search(r"\bgit\b.*\b(reset\s+--hard|checkout\s+--|clean\s+-[fdx]|push\s+--force)\b", lowered))


def is_python_base_modification(command: str) -> bool:
    lowered = normalize_slashes(command).lower()
    python_path = r"(?:^|\s|['\"])(?:[a-z]:/[^'\"\s]*(?:python|python\d+|python\d+\.\d+|python\.exe)[^'\"\s]*|python(?:\d+(?:\.\d+)?)?(?:\.exe)?)"
    base_path = r"(?:/python\d*(?:\.\d+)?/|/programs/python/|/python\d*/|/lib/|/libs/|/site-packages/|/dlls/)"
    destructive = r"\b(del|erase|remove-item|set-content|out-file|add-content|writealltext|move-item|copy-item)\b"
    return bool(
        re.search(python_path, lowered)
        and re.search(base_path, lowered)
        and re.search(destructive, lowered)
    )


def response_text(event: dict[str, Any]) -> str:
    value = event.get("tool_response")
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value or {}, ensure_ascii=False)
    except Exception:
        return str(value or "")


def _has_textual_nonzero_exit(text: str) -> bool:
    return _has_textual_exit_status(text, r"[1-9]\d*")


def _has_textual_zero_exit(text: str) -> bool:
    return _has_textual_exit_status(text, r"0")


def _has_textual_exit_status(text: str, code_pattern: str) -> bool:
    for line in (text or "").splitlines():
        stripped = line.strip()
        if re.search(rf"^(?:process|command|tool)\s+exited with code\s+{code_pattern}\b", stripped, re.IGNORECASE):
            return True
        if re.search(rf"^(?:process|command|tool)\s+exit code\s*[:=]\s*{code_pattern}\b", stripped, re.IGNORECASE):
            return True
        if re.search(rf"^(?:process|command|tool)\s+return_?code\s*[:=]\s*{code_pattern}\b", stripped, re.IGNORECASE):
            return True
    return False


def _coerce_exit_code(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and re.fullmatch(r"\d+", value.strip()):
        return int(value.strip())
    return None


def _rg_no_match_exit(event: dict[str, Any], code: int, text: str) -> bool:
    if code != 1:
        return False
    command = normalize_slashes(tool_command(event)).strip().lower()
    if not re.search(r"(^|[\s;&|()])rg(?:\.exe)?(?:\s|$)", command):
        return False
    cleaned = re.sub(r"\x1b\[[0-9;]*m", "", text or "")
    return not re.search(
        r"(?i)\b(parsererror|fatal|exception|traceback|denied|invalid|missing|not found|no such|cannot|can't|unauthorized|forbidden|timeout|timed out|permission|refused|unexpected|unrecognized)\b",
        cleaned,
    )


def _structured_failure_status(event: dict[str, Any]) -> bool | None:
    sources: list[dict[str, Any]] = [event]
    response = event.get("tool_response")
    if isinstance(response, dict):
        sources.append(response)
    for source in sources:
        for key in ("returncode", "return_code", "exit_code", "exitCode"):
            code = _coerce_exit_code(source.get(key))
            if code is not None:
                if _rg_no_match_exit(event, code, response_text(event)):
                    return False
                return code != 0
    return None


def _failure_line(line: str) -> bool:
    if not line or line[:1].isspace():
        return False
    stripped = line.strip()
    if re.search(r"(?i)^(?:parsererror|fatal|exception):\s+\S+", stripped):
        return True
    match = re.search(r"(?i)^error:\s+(.+)$", stripped)
    if not match:
        return False
    message = match.group(1).strip()
    if re.search(r"(?i)^(?:str|int|float|bool|list|dict|set|tuple|path|datetime)\b", message):
        return False
    return re.search(
        r"(?i)\b(fail(?:ed|ure)?|fatal|exception|traceback|denied|invalid|missing|not found|no such|does not exist|module not found|cannot|can't|unauthorized|forbidden|timeout|timed out|permission|refused|unexpected|unrecognized)\b",
        message,
    ) is not None


def command_is_plain_content_read(command: str) -> bool:
    surface = strip_command_literals(command or "").strip()
    if not surface:
        return False
    if re.search(r"[;&]|\|\|", surface) or contains_unquoted_output_redirect(surface):
        return False
    segments = [segment.strip().lower() for segment in surface.split("|") if segment.strip()]
    if not segments:
        return False
    read_commands = {"get-content", "gc", "type"}
    passthrough_commands = {"select-object", "select"}
    for index, segment in enumerate(segments):
        match = re.match(r"^([a-z][a-z0-9.-]*)\b", segment)
        if not match:
            return False
        command_name = match.group(1)
        if index == 0 and command_name not in read_commands:
            return False
        if index > 0 and command_name not in passthrough_commands:
            return False
    return True


def command_is_guarded_content_read(command: str) -> bool:
    surface = strip_command_literals(command or "").strip()
    if not surface:
        return False
    if re.search(r"[;&]|\|\|", surface) or contains_unquoted_output_redirect(surface):
        return False
    normalized = re.sub(r"\s+", " ", surface.lower())
    return bool(
        re.fullmatch(
            r"if\s*\(\s*test-path\b.+?\)\s*\{\s*(?:get-content|gc|type)\b.+?\}\s*else\s*\{\s*[^{}]*\s*\}",
            normalized,
            re.IGNORECASE,
        )
    )


def command_is_safe_content_read(command: str) -> bool:
    return command_is_plain_content_read(command) or command_is_guarded_content_read(command)


def plain_content_read_failure(event: dict[str, Any], text: str) -> bool | None:
    if not command_is_safe_content_read(tool_command(event)):
        return None
    return bool(
        re.search(
            r"(?im)^\s*(?:get-content|gc|type)\s*:\s+"
            r"(?:cannot|could not|access|permission|a parameter|cannot find)",
            text or "",
        )
    )


def command_failed(event: dict[str, Any]) -> bool:
    structured = _structured_failure_status(event)
    if structured is not None:
        return structured
    text = response_text(event)
    if _has_textual_nonzero_exit(text):
        return True
    if _has_textual_zero_exit(text):
        return False
    plain_read_failed = plain_content_read_failure(event, text)
    if plain_read_failed is not None:
        return plain_read_failed
    return bool(
        re.search(r"traceback \(most recent call last\)", text, re.IGNORECASE)
        or any(_failure_line(line) for line in text.splitlines())
    )


def _canonical_absolute_path(value: Any) -> str | None:
    """Canonicalize only absolute Windows paths; unknown inputs never match."""
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
        return os.path.normcase(os.path.realpath(os.path.normpath(candidate)))
    except (OSError, ValueError):
        return None


def resolve_effective_cwd(event: dict[str, Any]) -> dict[str, Any]:
    """Resolve scope without ever falling back to the child Hook cwd."""
    caller_cwd = _canonical_absolute_path(os.environ.get("CODEX_HOOK_CALLER_CWD"))
    if caller_cwd:
        return {"cwd": caller_cwd, "source": "caller_env", "valid": True}
    event_cwd = _canonical_absolute_path(event.get("cwd") if isinstance(event, dict) else None)
    if event_cwd:
        return {"cwd": event_cwd, "source": "event_cwd", "valid": True}
    return {"cwd": None, "source": "unknown", "valid": False}


def within_openclaw(event: dict[str, Any]) -> bool:
    """True only when the verified event scope is in the OpenClaw root."""
    scope = resolve_effective_cwd(event)
    candidate = scope["cwd"]
    root = _canonical_absolute_path(str(REPO_ROOT))
    if not candidate or not root:
        return False
    try:
        return os.path.commonpath([candidate, root]) == root
    except (OSError, ValueError):
        return False


def sanitize_transcript_tool_ids(transcript_path: str | Path | None) -> tuple[int, int]:
    """Sanitize custom_tool_call and function_call IDs in a transcript file."""
    if not transcript_path:
        return 0, 0
    raw_path = str(transcript_path)
    if raw_path.startswith("\\\\?\\"):
        raw_path = raw_path[4:]
    path = Path(raw_path)
    if not path.is_file():
        return 0, 0

    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()

        if "msg_" not in content:
            return 0, 0
        if "custom_tool_call" not in content and "function_call" not in content:
            return 0, 0

        lines = content.splitlines(keepends=True)
        ctc_fixed = 0
        fc_fixed = 0
        modified = False
        new_lines = []

        for line in lines:
            line_str = line.strip()
            if not line_str or ("custom_tool_call" not in line_str and "function_call" not in line_str):
                new_lines.append(line)
                continue
            try:
                data = json.loads(line_str)
            except Exception:
                new_lines.append(line)
                continue

            if data.get("type") == "response_item":
                payload = data.get("payload")
                if isinstance(payload, dict):
                    ptype = payload.get("type")
                    pid = payload.get("id")
                    if isinstance(pid, str) and pid.startswith("msg_"):
                        if ptype == "custom_tool_call":
                            payload["id"] = "ctc_" + pid[4:]
                            ctc_fixed += 1
                            modified = True
                            line = json.dumps(data, ensure_ascii=False) + "\n"
                        elif ptype == "function_call":
                            payload["id"] = "fc_" + pid[4:]
                            fc_fixed += 1
                            modified = True
                            line = json.dumps(data, ensure_ascii=False) + "\n"
            new_lines.append(line)

        if modified:
            with open(path, "r+", encoding="utf-8") as f:
                f.seek(0)
                f.writelines(new_lines)
                f.truncate()

        return ctc_fixed, fc_fixed
    except Exception:
        return 0, 0
