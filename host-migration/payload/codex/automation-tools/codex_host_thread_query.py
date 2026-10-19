#!/usr/bin/env python3
"""Read Codex Desktop thread or Goal metadata through official app-server APIs.

This is a one-shot, read-only query helper for local automations.  It avoids
the Desktop renderer-dependent dynamic-tool path while deliberately avoiding
direct SQLite access.  The helper starts ``codex app-server --stdio``, sends
``initialize`` plus only the read-only thread/list pages, thread/read, or
thread/goal/get JSON-RPC requests needed for the selected operation, and exits.
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


ALL_SOURCE_KINDS = [
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
MAX_THREAD_LIST_PAGES = 1000


class HostQueryError(RuntimeError):
    """A local Codex app-server query did not complete."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Read Codex Desktop thread or Goal metadata through codex app-server stdio."
    )
    parser.add_argument("--codex-home", required=True, help="Exact Codex profile root.")
    parser.add_argument(
        "--match",
        default=None,
        help="Return only rows whose id, name, or preview contains this text.",
    )
    parser.add_argument(
        "--thread-id", default=None, help="Return only this exact thread ID."
    )
    parser.add_argument(
        "--read-thread-id",
        default=None,
        help="Read one exact thread and bypass renderer-dependent read_thread.",
    )
    parser.add_argument(
        "--goal-thread-id",
        default=None,
        help="Read one exact Codex task Goal through thread/goal/get.",
    )
    parser.add_argument(
        "--include-turns",
        action="store_true",
        help="When reading one thread, include its persisted turns and items.",
    )
    parser.add_argument(
        "--archived",
        choices=("active", "archived"),
        default="active",
        help="Select active or archived rows (default: active).",
    )
    parser.add_argument("--limit", type=int, default=200)
    parser.add_argument("--timeout-seconds", type=float, default=10.0)
    return parser.parse_args()


def find_codex_command(codex_home: Path) -> str:
    configured = os.environ.get("CODEX_APP_SERVER_COMMAND")
    if configured:
        return configured
    # The bundled plugin app-server is copied from the active Desktop build.
    # Prefer it over a globally installed CLI so rollout parsing stays on the
    # same protocol version as the local thread store.
    bundled = codex_home / "plugins" / ".plugin-appserver" / "codex.exe"
    if bundled.is_file():
        return str(bundled)
    for candidate in ("codex.cmd", "codex"):
        found = shutil.which(candidate)
        if found:
            return found
    raise HostQueryError("codex command was not found on PATH")


def emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))


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
) -> tuple[dict[str, Any], list[tuple[str, str]]]:
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
    seen: list[tuple[str, str]] = []
    while time.monotonic() < deadline:
        if process.poll() is not None and events.empty():
            break
        try:
            label, line = events.get(
                timeout=min(0.15, max(0.001, deadline - time.monotonic()))
            )
        except queue.Empty:
            continue
        seen.append((label, line))
        if label != "stdout":
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            continue
        if message.get("id") == request_id:
            if "error" in message:
                raise HostQueryError(f"{method} returned {message['error']}")
            return message, seen
    stderr = [line for label, line in seen if label == "stderr"]
    detail = stderr[-1] if stderr else f"process_exit={process.poll()}"
    raise HostQueryError(f"{method} did not return before timeout; {detail}")


def row_matches(row: dict[str, Any], text: str | None, thread_id: str | None) -> bool:
    if thread_id and row.get("id") != thread_id:
        return False
    if text:
        haystack = "\n".join(
            str(row.get(field) or "") for field in ("id", "name", "preview")
        )
        if text not in haystack:
            return False
    return True

REVIEW_MARKER_PREFIX = "OS-REVIEW-CARD-v1|"


def is_automation_runner_row(row: dict[str, Any]) -> bool:
    """Mechanical Host identity check, not an OS business decision."""
    preview = str(row.get("preview") or "")
    return preview.startswith("Automation:") and "\nAutomation ID:" in preview


def filter_thread_matches(
    rows: list[dict[str, Any]], text: str | None, thread_id: str | None
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    raw_matches = [row for row in rows if row_matches(row, text, thread_id)]
    if thread_id is not None or not (
        isinstance(text, str) and text.startswith(REVIEW_MARKER_PREFIX)
    ):
        return raw_matches, []
    excluded = [row for row in raw_matches if is_automation_runner_row(row)]
    excluded_ids = {str(row.get("id")) for row in excluded}
    return [row for row in raw_matches if str(row.get("id")) not in excluded_ids], excluded


def match_cardinality(count: int) -> str:
    if count == 0:
        return "none"
    if count == 1:
        return "single"
    return "multiple"


def remaining_timeout(overall_deadline: float) -> float:
    remaining = overall_deadline - time.monotonic()
    if remaining <= 0:
        raise HostQueryError("codex host query exceeded total deadline")
    return remaining


def validate_exact_thread_read(
    read_result: Any, *, thread_id: str, include_turns: bool
) -> dict[str, Any]:
    if not isinstance(read_result, dict):
        raise HostQueryError("thread/read returned an invalid result object")
    thread = read_result.get("thread", read_result)
    if not isinstance(thread, dict):
        raise HostQueryError("thread/read returned an invalid thread object")
    if thread.get("id") != thread_id:
        raise HostQueryError("thread/read returned a different exact thread id")
    if include_turns and not isinstance(thread.get("turns"), list):
        raise HostQueryError("thread/read did not return readable turns")
    return thread


def collect_thread_pages(
    *,
    process: subprocess.Popen[str] | object,
    events: queue.Queue[tuple[str, str]] | object,
    archived: bool,
    page_limit: int,
    timeout_seconds: float,
    start_request_id: int,
    overall_deadline: float | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Read every app-server thread/list page or fail without partial success."""

    if overall_deadline is None:
        overall_deadline = time.monotonic() + timeout_seconds
    rows: list[dict[str, Any]] = []
    seen_thread_ids: set[str] = set()
    seen_cursors: set[str] = set()
    cursor: str | None = None
    request_id = start_request_id
    page_count = 0
    while True:
        remaining_timeout(overall_deadline)
        params: dict[str, Any] = {
            "archived": archived,
            "limit": page_limit,
            "sourceKinds": ALL_SOURCE_KINDS,
            "useStateDbOnly": True,
        }
        if cursor is not None:
            params["cursor"] = cursor
        response, _ = request(
            process,  # type: ignore[arg-type]
            events,  # type: ignore[arg-type]
            request_id,
            "thread/list",
            params,
            min(timeout_seconds, remaining_timeout(overall_deadline)),
        )
        request_id += 1
        page_count += 1
        result = response.get("result")
        if not isinstance(result, dict):
            raise HostQueryError("thread/list returned an invalid result object")
        page = result.get("data")
        if not isinstance(page, list) or not all(isinstance(row, dict) for row in page):
            raise HostQueryError("thread/list returned invalid page data")
        for row in page:
            thread_id = row.get("id")
            if not isinstance(thread_id, str) or not thread_id:
                raise HostQueryError("thread/list returned a row without an exact thread id")
            if thread_id in seen_thread_ids:
                raise HostQueryError("thread/list repeated a thread id across pages")
            seen_thread_ids.add(thread_id)
            rows.append(row)
        next_cursor = result.get("nextCursor")
        if next_cursor is None:
            return rows, {
                "complete": True,
                "page_count": page_count,
                "next_request_id": request_id,
            }
        if not isinstance(next_cursor, str) or not next_cursor:
            raise HostQueryError("thread/list returned an invalid pagination cursor")
        if next_cursor in seen_cursors:
            raise HostQueryError("thread/list returned a repeated pagination cursor")
        if page_count >= MAX_THREAD_LIST_PAGES:
            raise HostQueryError("thread/list exceeded the pagination safety bound")
        seen_cursors.add(next_cursor)
        cursor = next_cursor


def main() -> int:
    args = parse_args()
    codex_home = Path(args.codex_home).expanduser().resolve()
    if not codex_home.is_dir():
        raise HostQueryError(f"codex home does not exist: {codex_home}")
    if args.limit < 1 or args.limit > 500:
        raise HostQueryError("limit must be between 1 and 500")
    if args.timeout_seconds < 1.0:
        raise HostQueryError(
            "timeout-seconds must be at least 1.0 for a total host deadline"
        )
    selected_exact_operations = sum(
        value is not None
        for value in (args.read_thread_id, args.goal_thread_id)
    )
    if selected_exact_operations > 1:
        raise HostQueryError(
            "--read-thread-id and --goal-thread-id cannot be combined"
        )

    env = os.environ.copy()
    env["CODEX_HOME"] = str(codex_home)
    command = find_codex_command(codex_home)
    overall_deadline = time.monotonic() + args.timeout_seconds
    process = subprocess.Popen(
        [command, "app-server", "--stdio"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
        env=env,
        shell=os.name == "nt" and command.lower().endswith(".cmd"),
    )
    events: queue.Queue[tuple[str, str]] = queue.Queue()
    assert process.stdout is not None and process.stderr is not None
    threading.Thread(
        target=stream_reader, args=(process.stdout, "stdout", events), daemon=True
    ).start()
    threading.Thread(
        target=stream_reader, args=(process.stderr, "stderr", events), daemon=True
    ).start()

    try:
        initialize, _ = request(
            process,
            events,
            1,
            "initialize",
            {
                "clientInfo": {
                    "name": "codex-host-thread-query",
                    "version": "1.0",
                },
                "capabilities": (
                    {"experimentalApi": True}
                    if args.goal_thread_id
                    else {}
                ),
            },
            remaining_timeout(overall_deadline),
        )
        initialized_home = initialize["result"].get("codexHome")
        if Path(initialized_home).resolve() != codex_home:
            raise HostQueryError(
                f"app-server opened unexpected codex home: {initialized_home}"
            )
        if args.read_thread_id:
            response, _ = request(
                process,
                events,
                2,
                "thread/read",
                {
                    "threadId": args.read_thread_id,
                    "includeTurns": args.include_turns,
                },
                remaining_timeout(overall_deadline),
            )
            thread = validate_exact_thread_read(
                response.get("result"),
                thread_id=args.read_thread_id,
                include_turns=args.include_turns,
            )
            emit(
                {
                    "schema": "codex_host_thread_query.v1",
                    "status": "ok",
                    "backend": "codex_app_server_stdio",
                    "app_server_command": command,
                    "operation": "thread_read",
                    "codex_home": str(codex_home),
                    "thread_id": args.read_thread_id,
                    "complete": True,
                    "turns_readable": bool(args.include_turns),
                    "thread": thread,
                }
            )
            return 0

        if args.goal_thread_id:
            response, _ = request(
                process,
                events,
                2,
                "thread/goal/get",
                {"threadId": args.goal_thread_id},
                remaining_timeout(overall_deadline),
            )
            emit(
                {
                    "schema": "codex_host_thread_query.v1",
                    "status": "ok",
                    "backend": "codex_app_server_stdio",
                    "app_server_command": command,
                    "operation": "thread_goal_get",
                    "codex_home": str(codex_home),
                    "goal_thread_id": args.goal_thread_id,
                    "complete": True,
                    "goal": response.get("goal"),
                }
            )
            return 0

        rows, pagination = collect_thread_pages(
            process=process,
            events=events,
            archived=args.archived == "archived",
            page_limit=args.limit,
            timeout_seconds=args.timeout_seconds,
            start_request_id=2,
            overall_deadline=overall_deadline,
        )
        matched, excluded_automation_runners = filter_thread_matches(
            rows, args.match, args.thread_id
        )
        raw_matched_count = len(matched) + len(excluded_automation_runners)
        cardinality = match_cardinality(len(matched))
        emit(
            {
                "schema": "codex_host_thread_query.v1",
                "status": "ok",
                "backend": "codex_app_server_stdio",
                "app_server_command": command,
                "operation": "thread_list",
                "codex_home": str(codex_home),
                "archived": args.archived,
                "match": args.match,
                "thread_id": args.thread_id,
                "complete": pagination["complete"],
                "page_count": pagination["page_count"],
                "returned_count": len(rows),
                "raw_matched_count": raw_matched_count,
                "excluded_automation_runner_count": len(excluded_automation_runners),
                "excluded_automation_runner_ids": [
                    str(row.get("id")) for row in excluded_automation_runners
                ],
                "matched_count": len(matched),
                "match_cardinality": cardinality,
                "multiple_matches": cardinality == "multiple",
                "safe_single_match": pagination["complete"] and cardinality == "single",
                "threads": matched,
            }
        )
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
    except HostQueryError as error:
        emit(
            {
                "schema": "codex_host_thread_query.v1",
                "status": "host_error",
                "complete": False,
                "multiple_matches": None,
                "error": str(error),
            }
        )
        raise SystemExit(2)
