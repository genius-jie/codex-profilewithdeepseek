#!/usr/bin/env python3
"""Collect same-day user input streams for S19 daily reports."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ASIA_SHANGHAI = timezone(timedelta(hours=8))

SOURCE_DEFS = [
    {
        "source_id": "antigravity",
        "display_name": "Antigravity",
        "roots": [Path(r"@@USERPROFILE:win@@\.gemini\antigravity-ide\brain")],
        "glob": r"*\ .system_generated\logs\transcript.jsonl".replace(" ", ""),
    },
    {
        "source_id": "codexplusplus",
        "display_name": "Codex++",
        "roots": [
            Path(r"@@USERPROFILE:win@@\AppData\Roaming\CodexPlusPlusProfile\.codex\sessions"),
            Path(r"@@PROFILE_REPO:win@@\sessions"),
        ],
        "glob": None,
    },
    {
        "source_id": "codex",
        "display_name": "Independent Codex",
        "roots": [
            Path(r"@@CODEX_HOME:win@@\sessions"),
            Path(r"@@CODEX_HOME:win@@\archived_sessions"),
            Path(r"@@CODEX_HOME:win@@\quarantined_sessions"),
        ],
        "glob": None,
    },
    {
        "source_id": "vscode_claude_code",
        "display_name": "VSCode Claude Code",
        "roots": [Path(r"@@CLAUDE_HOME:win@@\projects")],
        "glob": "**/*.jsonl",
    },
]

NOISE_EXACT_LINES = {
    "<INSTRUCTIONS>",
    "</INSTRUCTIONS>",
    "--- project-doc ---",
}

NOISE_PREFIXES = (
    "# AGENTS.md instructions",
    "<task-notification",
    "[Request interrupted by user]",
    "The following is the Codex agent history added since your last approval assessment.",
)

NOISE_STRUCTURAL_MARKERS = (
    "doc_status: active-profile-overlay",
    "birth_ceremony_id:",
    "<environment_context>",
    ">>> TRANSCRIPT DELTA START",
)

STRIPPABLE_METADATA_BLOCKS = (
    ("<ADDITIONAL_METADATA>", "</ADDITIONAL_METADATA>"),
    ("<USER_SETTINGS_CHANGE>", "</USER_SETTINGS_CHANGE>"),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect user input streams for S19.")
    parser.add_argument("--date", required=True, help="Asia/Shanghai date, YYYY-MM-DD.")
    parser.add_argument("--output", required=True, help="Output JSON path.")
    return parser.parse_args()


def parse_time(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(value, tz=timezone.utc).astimezone(ASIA_SHANGHAI)
        except (OverflowError, OSError, ValueError):
            return None
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=ASIA_SHANGHAI)
    return parsed.astimezone(ASIA_SHANGHAI)


def normalize_parts(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        for key in ("text", "content", "input_text"):
            if key in value:
                return normalize_parts(value.get(key))
        return ""
    if isinstance(value, list):
        parts: list[str] = []
        for item in value:
            text = normalize_parts(item)
            if text:
                parts.append(text)
        return "\n".join(parts)
    return str(value)


def clean_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    for start_marker, end_marker in STRIPPABLE_METADATA_BLOCKS:
        while start_marker in text and end_marker in text:
            start = text.find(start_marker)
            end = text.find(end_marker, start)
            if end < 0:
                break
            text = text[:start] + text[end + len(end_marker) :]
    text = text.replace("<USER_REQUEST>", "").replace("</USER_REQUEST>", "")
    lines = [line.rstrip() for line in text.split("\n")]
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    return "\n".join(lines).strip()


def is_noise(text: str) -> bool:
    compact = text.strip()
    if not compact:
        return True
    first_line = compact.splitlines()[0].strip()
    if first_line in NOISE_EXACT_LINES:
        return True
    if any(first_line.startswith(prefix) for prefix in NOISE_PREFIXES):
        return True
    return any(marker in compact for marker in NOISE_STRUCTURAL_MARKERS)


def read_jsonl(path: Path) -> tuple[list[dict[str, Any]], int]:
    rows: list[dict[str, Any]] = []
    errors = 0
    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    errors += 1
                    continue
                if isinstance(obj, dict):
                    rows.append(obj)
    except OSError:
        errors += 1
    return rows, errors


def append_record(
    records: list[dict[str, Any]],
    source_id: str,
    source_name: str,
    path: Path,
    when: datetime,
    text: str,
    raw_kind: str,
) -> None:
    records.append(
        {
            "source_id": source_id,
            "source_name": source_name,
            "time": when.isoformat(timespec="seconds"),
            "text": text,
            "file": str(path),
            "raw_kind": raw_kind,
        }
    )


def dedupe_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for record in records:
        key = (
            str(record.get("source_id", "")),
            str(record.get("time", "")),
            " ".join(str(record.get("text", "")).split()),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(record)
    return deduped


def antigravity_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return sorted(root.glob(r"*\ .system_generated\logs\transcript.jsonl".replace(" ", "")))


def codex_files(root: Path, date_text: str) -> list[Path]:
    if not root.exists():
        return []
    target_date = datetime.strptime(date_text, "%Y-%m-%d").date()
    files: list[Path] = []
    seen: set[Path] = set()

    def add_path(path: Path) -> None:
        try:
            resolved = path.resolve()
        except OSError:
            return
        if resolved in seen:
            return
        seen.add(resolved)
        files.append(path)

    for offset in range(-14, 2):
        candidate = target_date + timedelta(days=offset)
        day_dir = root / f"{candidate.year:04d}" / f"{candidate.month:02d}" / f"{candidate.day:02d}"
        if not day_dir.exists():
            continue
        for path in day_dir.glob("*.jsonl"):
            add_path(path)

    mtime_start = target_date - timedelta(days=1)
    mtime_end = target_date + timedelta(days=1)
    for path in root.glob("**/*.jsonl"):
        try:
            modified_date = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).astimezone(ASIA_SHANGHAI).date()
        except OSError:
            continue
        if mtime_start <= modified_date <= mtime_end:
            add_path(path)
    return sorted(files)


def collect_antigravity(date_text: str, root: Path, source: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    records: list[dict[str, Any]] = []
    files = antigravity_files(root)
    ignored = 0
    errors = 0
    for path in files:
        rows, row_errors = read_jsonl(path)
        errors += row_errors
        for row in rows:
            if row.get("type") != "USER_INPUT" or row.get("source") != "USER_EXPLICIT":
                continue
            when = parse_time(row.get("created_at"))
            if not when or when.date().isoformat() != date_text:
                continue
            text = clean_text(normalize_parts(row.get("content")))
            if is_noise(text):
                ignored += 1
                continue
            append_record(records, source["source_id"], source["display_name"], path, when, text, "USER_INPUT")
    meta = {
        "files_scanned": len(files),
        "ignored_count": ignored,
        "parse_error_count": errors,
    }
    return records, meta


def collect_codexplusplus(date_text: str, root: Path, source: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    records: list[dict[str, Any]] = []
    files = codex_files(root, date_text)
    ignored = 0
    errors = 0
    for path in files:
        rows, row_errors = read_jsonl(path)
        errors += row_errors
        for row in rows:
            if row.get("type") != "response_item":
                continue
            payload = row.get("payload")
            if not isinstance(payload, dict) or payload.get("role") != "user":
                continue
            when = parse_time(row.get("timestamp"))
            if not when or when.date().isoformat() != date_text:
                continue
            text = clean_text(normalize_parts(payload.get("content")))
            if is_noise(text):
                ignored += 1
                continue
            append_record(records, source["source_id"], source["display_name"], path, when, text, "response_item:user")
    meta = {
        "files_scanned": len(files),
        "ignored_count": ignored,
        "parse_error_count": errors,
    }
    return records, meta


def collect_claude(date_text: str, root: Path, source: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    records: list[dict[str, Any]] = []
    files = []
    if root.exists():
        files = sorted(path for path in root.glob("**/*.jsonl") if "subagents" not in str(path).lower())
    ignored = 0
    errors = 0
    for path in files:
        rows, row_errors = read_jsonl(path)
        errors += row_errors
        for row in rows:
            if row.get("type") != "user":
                continue
            message = row.get("message")
            if not isinstance(message, dict) or message.get("role") != "user":
                continue
            content = message.get("content")
            if isinstance(content, list) and content and all(isinstance(item, dict) and item.get("type") == "tool_result" for item in content):
                continue
            when = parse_time(row.get("timestamp"))
            if not when or when.date().isoformat() != date_text:
                continue
            text = clean_text(normalize_parts(content))
            if is_noise(text):
                ignored += 1
                continue
            append_record(records, source["source_id"], source["display_name"], path, when, text, "message:user")
    meta = {
        "files_scanned": len(files),
        "ignored_count": ignored,
        "parse_error_count": errors,
    }
    return records, meta


def collect_source(date_text: str, source: dict[str, Any]) -> dict[str, Any]:
    root_records: list[dict[str, Any]] = []
    root_paths = [str(root) for root in source["roots"]]
    files_scanned = 0
    ignored_count = 0
    parse_error_count = 0
    warnings: list[str] = []
    roots_found = 0

    for root in source["roots"]:
        if not root.exists():
            warnings.append(f"root_missing: {root}")
            continue
        roots_found += 1
        if source["source_id"] == "antigravity":
            records, meta = collect_antigravity(date_text, root, source)
        elif source["source_id"] in ("codexplusplus", "codex"):
            records, meta = collect_codexplusplus(date_text, root, source)
        elif source["source_id"] == "vscode_claude_code":
            records, meta = collect_claude(date_text, root, source)
        else:
            records, meta = [], {"files_scanned": 0, "ignored_count": 0, "parse_error_count": 1}
        root_records.extend(records)
        files_scanned += int(meta["files_scanned"])
        ignored_count += int(meta["ignored_count"])
        parse_error_count += int(meta["parse_error_count"])

    status = "ok"
    if roots_found == 0:
        status = "missing"
    elif parse_error_count > 0:
        status = "warn"

    root_records = dedupe_records(root_records)

    return {
        "source_id": source["source_id"],
        "display_name": source["display_name"],
        "status": status,
        "root_paths": root_paths,
        "files_scanned": files_scanned,
        "user_input_count": len(root_records),
        "ignored_count": ignored_count,
        "parse_error_count": parse_error_count,
        "warnings": warnings,
        "records": sorted(root_records, key=lambda item: item["time"]),
    }


def topic_hits(records: list[dict[str, Any]]) -> dict[str, int]:
    # Topic grouping is a semantic writing decision. Keep this field for
    # backward compatibility, but leave it empty for the Agent to classify.
    return {}


def build_source_index(sources: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for source in sources:
        index[source["source_id"]] = {
            "display_name": source["display_name"],
            "status": source["status"],
            "files_scanned": source["files_scanned"],
            "user_input_count": source["user_input_count"],
            "count": source["user_input_count"],
            "ignored_count": source["ignored_count"],
            "parse_error_count": source["parse_error_count"],
            "root_paths": source["root_paths"],
            "warnings": source["warnings"],
        }
    return index


def main() -> int:
    args = parse_args()
    try:
        datetime.strptime(args.date, "%Y-%m-%d")
    except ValueError:
        raise SystemExit("--date must be YYYY-MM-DD")

    sources = [collect_source(args.date, source) for source in SOURCE_DEFS]
    records: list[dict[str, Any]] = []
    for source in sources:
        records.extend(source["records"])
    records = dedupe_records(records)
    records.sort(key=lambda item: item["time"])

    output = {
        "schema_version": "daily_user_input_streams.v1",
        "date": args.date,
        "generated_at": datetime.now(ASIA_SHANGHAI).isoformat(timespec="seconds"),
        "primary_source": "four_user_input_streams",
        "required_source_ids": ["antigravity", "codexplusplus", "codex", "vscode_claude_code"],
        "summary": {
            "total_user_inputs": len(records),
            "sources_found": sum(1 for source in sources if source["status"] != "missing"),
            "sources_ok": [source["source_id"] for source in sources if source["status"] == "ok"],
            "sources_missing": [source["source_id"] for source in sources if source["status"] == "missing"],
            "sources_warn": [source["source_id"] for source in sources if source["status"] == "warn"],
            "topic_hits": topic_hits(records),
            "topic_classification_owner": "agent",
        },
        "source_index": build_source_index(sources),
        # Per-source records duplicate the canonical top-level records list and
        # previously doubled every collector artifact. Keep only diagnostics
        # here; records remain available through output["records"].
        "sources": [
            {key: value for key, value in source.items() if key != "records"}
            for source in sources
        ],
        "records": records,
    }

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        f"Collected {len(records)} user inputs from {output['summary']['sources_found']} sources; "
        f"output={out_path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
