#!/usr/bin/env python3
"""Archive explicit inactive Codex++ tasks through the official app-server API.

This helper deliberately rejects the ordinary Codex profile and never accesses
SQLite or moves rollout files.
"""

from __future__ import annotations

import argparse
import json
import os
import queue
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any


PROFILE_ALIASES = (
    Path(r"@@CODEXPP_HOME:win@@"),
)
RUNNING_STATUSES = {"active", "running"}
SOURCE_KINDS = [
    "cli",
    "vscode",
    "exec",
    "appServer",
    "subAgent",
    "subAgentReview",
    "subAgentCompact",
    "subAgentThreadSpawn",
    "subAgentOther",
    "unknown",
]


class ArchiveError(RuntimeError):
    """The profile-locked archive operation cannot be completed safely."""


def normalized(path: Path) -> str:
    return os.path.normcase(os.path.normpath(str(path.expanduser().resolve())))


def allowed_home(path: Path) -> bool:
    return normalized(path) in {normalized(alias) for alias in PROFILE_ALIASES}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Archive exact inactive Codex++ tasks through the official app-server."
    )
    parser.add_argument(
        "--codex-home",
        default=os.environ.get("CODEX_HOME"),
        help="Codex++ profile root; defaults to CODEX_HOME and rejects ordinary Codex.",
    )
    parser.add_argument(
        "--thread-id",
        action="append",
        required=True,
        help="Exact inactive Codex++ task ID; repeat for several pre-screened tasks.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate the profile and current task statuses without archiving.",
    )
    parser.add_argument("--timeout-seconds", type=float, default=15.0)
    return parser.parse_args()


def find_codex_command(codex_home: Path) -> str:
    configured = os.environ.get("CODEX_APP_SERVER_COMMAND")
    if configured and Path(configured).is_file():
        return configured
    store = Path(r"@@CODEXPP_INSTALL_ROOT:win@@\store-apps")
    candidates = []
    if store.is_dir():
        for app_root in store.glob("OpenAI.Codex_*/app/resources/codex.exe"):
            if app_root.is_file():
                candidates.append(app_root)
    if candidates:
        # The controlled store keeps the current package as the newest package
        # identity. Never fall back to PATH, which can resolve ordinary Codex.
        return str(sorted(candidates, key=lambda p: p.parent.parent.parent.name)[-1])
    raise ArchiveError("Current Codex++ fixed-store app-server command was not found; set CODEX_APP_SERVER_COMMAND explicitly")


def stream_reader(stream: Any, label: str, events: queue.Queue[tuple[str, str]]) -> None:
    for line in iter(stream.readline, ""):
        events.put((label, line.rstrip("\r\n")))


def request(
    process: subprocess.Popen[str],
    events: queue.Queue[tuple[str, str]],
    request_id: int,
    method: str,
    params: dict[str, Any],
    timeout_seconds: float,
) -> dict[str, Any]:
    assert process.stdin is not None
    process.stdin.write(
        json.dumps(
            {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params},
            separators=(",", ":"),
        )
        + "\n"
    )
    process.stdin.flush()
    deadline = time.monotonic() + timeout_seconds
    diagnostics: list[str] = []
    while time.monotonic() < deadline:
        if process.poll() is not None and events.empty():
            break
        try:
            label, line = events.get(timeout=0.15)
        except queue.Empty:
            continue
        if label != "stdout":
            diagnostics.append(line)
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            continue
        if message.get("id") != request_id:
            continue
        if "error" in message:
            raise ArchiveError(f"{method} returned {message['error']}")
        return message.get("result", {})
    detail = diagnostics[-1] if diagnostics else f"process_exit={process.poll()}"
    raise ArchiveError(f"{method} did not return before timeout; {detail}")


def find_target_ids(
    process: subprocess.Popen[str],
    events: queue.Queue[tuple[str, str]],
    request_id: int,
    target_ids: set[str],
    *,
    archived: bool,
    use_state_db_only: bool,
    timeout_seconds: float,
) -> tuple[set[str], int]:
    """Find exact target IDs through a fully paged official native list."""
    cursor: str | None = None
    found: set[str] = set()
    for _ in range(100):
        params: dict[str, Any] = {
            "archived": archived,
            "limit": 500,
            "sourceKinds": SOURCE_KINDS,
            "useStateDbOnly": use_state_db_only,
        }
        if cursor:
            params["cursor"] = cursor
        result = request(
            process,
            events,
            request_id,
            "thread/list",
            params,
            timeout_seconds,
        )
        request_id += 1
        found.update(
            str(item.get("id"))
            for item in result.get("data", [])
            if item.get("id") in target_ids
        )
        if target_ids.issubset(found):
            return found, request_id
        cursor = result.get("nextCursor")
        if not cursor:
            return found, request_id
    raise ArchiveError("native task-list verification exceeded 100 pages")


def is_archived_rollout_path(path: Any) -> bool:
    if not isinstance(path, str):
        return False
    normalized_path = path.replace("/", "\\").lower()
    return "\\archived_sessions\\" in normalized_path


def read_thread(
    process: subprocess.Popen[str],
    events: queue.Queue[tuple[str, str]],
    request_id: int,
    thread_id: str,
    timeout_seconds: float,
) -> tuple[dict[str, Any], int]:
    """Read one exact Codex++ task through the native protocol."""
    result = request(
        process,
        events,
        request_id,
        "thread/read",
        {"threadId": thread_id, "includeTurns": False},
        timeout_seconds,
    )
    return result.get("thread", result), request_id + 1


def task_status(thread: dict[str, Any]) -> str:
    return str((thread.get("status") or {}).get("type") or "unknown")


def main() -> int:
    args = parse_args()
    if not args.codex_home:
        raise ArchiveError("CODEX_HOME is missing; refusing to guess a profile")
    codex_home = Path(args.codex_home)
    if not codex_home.is_dir() or not allowed_home(codex_home):
        raise ArchiveError(
            "refusing non-Codex++ profile; allowed only @@CODEXPP_HOME:escaped@@"
        )
    if args.timeout_seconds <= 0:
        raise ArchiveError("--timeout-seconds must be positive")

    command = find_codex_command(codex_home)
    environment = os.environ.copy()
    environment["CODEX_HOME"] = str(codex_home)
    process = subprocess.Popen(
        [command, "app-server", "--stdio"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
        env=environment,
        shell=os.name == "nt" and command.lower().endswith(".cmd"),
    )
    events: queue.Queue[tuple[str, str]] = queue.Queue()
    assert process.stdout is not None and process.stderr is not None
    threading.Thread(target=stream_reader, args=(process.stdout, "stdout", events), daemon=True).start()
    threading.Thread(target=stream_reader, args=(process.stderr, "stderr", events), daemon=True).start()

    try:
        initialized = request(
            process,
            events,
            1,
            "initialize",
            {"clientInfo": {"name": "codex-plusplus-thread-archive", "version": "1.0"}},
            args.timeout_seconds,
        )
        initialized_home = Path(str(initialized.get("codexHome", "")))
        if not initialized_home.is_dir() or not allowed_home(initialized_home):
            raise ArchiveError("app-server did not open the Codex++ profile")

        preflight: list[dict[str, Any]] = []
        next_id = 2
        for thread_id in args.thread_id:
            thread, next_id = read_thread(
                process, events, next_id, thread_id, args.timeout_seconds
            )
            preflight.append(
                {
                    "thread_id": thread_id,
                    "status": task_status(thread),
                    "rollout_path": thread.get("path"),
                    "archived_rollout_path": is_archived_rollout_path(thread.get("path")),
                }
            )

        running = [item for item in preflight if item["status"] in RUNNING_STATUSES]
        if running:
            raise ArchiveError(f"refusing to archive running Codex++ task(s): {running}")

        target_ids = {item["thread_id"] for item in preflight}
        active_index_ids, next_id = find_target_ids(
            process,
            events,
            next_id,
            target_ids,
            archived=False,
            use_state_db_only=True,
            timeout_seconds=args.timeout_seconds,
        )
        archived_index_ids, next_id = find_target_ids(
            process,
            events,
            next_id,
            target_ids,
            archived=True,
            use_state_db_only=True,
            timeout_seconds=args.timeout_seconds,
        )
        for item in preflight:
            item["active_index_membership"] = item["thread_id"] in active_index_ids
            item["archived_index_membership"] = item["thread_id"] in archived_index_ids
            item["stale_active_index"] = (
                item["archived_rollout_path"]
                and item["active_index_membership"]
                and not item["archived_index_membership"]
            )

        if args.dry_run:
            print(json.dumps({"schema": "codex_plusplus_thread_archive.v1", "status": "dry_run", "profile": "codex-plusplus", "targets": preflight}, ensure_ascii=False))
            return 0

        for item in preflight:
            if item["archived_rollout_path"]:
                item["archive_disposition"] = "already_archived"
                item["catalog_status"] = (
                    "stale" if item["stale_active_index"] else "consistent"
                )
                continue
            request(
                process,
                events,
                next_id,
                "thread/archive",
                {"threadId": item["thread_id"]},
                args.timeout_seconds,
            )
            item["archive_disposition"] = "newly_archived"
            next_id += 1

        final_active_index_ids: set[str] = set()
        final_archived_index_ids: set[str] = set()
        physical_archived_ids: set[str] = set()
        for attempt in range(5):
            physical_archived_ids.clear()
            for item in preflight:
                thread, next_id = read_thread(
                    process, events, next_id, item["thread_id"], args.timeout_seconds
                )
                item["status"] = task_status(thread)
                item["rollout_path"] = thread.get("path")
                item["archived_rollout_path"] = is_archived_rollout_path(item["rollout_path"])
                if item["status"] in RUNNING_STATUSES:
                    raise ArchiveError(
                        f"verification stopped because {item['thread_id']} is running"
                    )
                if item["archived_rollout_path"]:
                    physical_archived_ids.add(item["thread_id"])
            final_active_index_ids, next_id = find_target_ids(
                process,
                events,
                next_id,
                target_ids,
                archived=False,
                use_state_db_only=True,
                timeout_seconds=args.timeout_seconds,
            )
            final_archived_index_ids, next_id = find_target_ids(
                process,
                events,
                next_id,
                target_ids,
                archived=True,
                use_state_db_only=True,
                timeout_seconds=args.timeout_seconds,
            )
            if target_ids.issubset(physical_archived_ids):
                break
            if attempt < 4:
                time.sleep(0.5)

        missing_physical = sorted(target_ids - physical_archived_ids)
        if missing_physical:
            raise ArchiveError(
                "native archive verification failed: "
                f"missing_physical={missing_physical}"
            )
        catalog_lag_ids = sorted(
            (target_ids - final_archived_index_ids) | final_active_index_ids
        )
        for item in preflight:
            item["active_index_membership"] = item["thread_id"] in final_active_index_ids
            item["archived_index_membership"] = (
                item["thread_id"] in final_archived_index_ids
            )
            item["catalog_status"] = (
                "stale" if item["thread_id"] in catalog_lag_ids else "consistent"
            )
        print(json.dumps({"schema": "codex_plusplus_thread_archive.v1", "status": "archived_with_catalog_lag" if catalog_lag_ids else "archived", "profile": "codex-plusplus", "targets": preflight, "verified_archived": True, "verified_by_archived_rollout_path": sorted(physical_archived_ids), "verified_by_archived_state_index": sorted(final_archived_index_ids), "catalog_lag_thread_ids": catalog_lag_ids}, ensure_ascii=False))
        return 0
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ArchiveError as error:
        print(json.dumps({"schema": "codex_plusplus_thread_archive.v1", "status": "error", "error": str(error)}, ensure_ascii=False), file=sys.stderr)
        raise SystemExit(2)
