#!/usr/bin/env python3
"""Validate a Product PRD Handoff capability package."""

from __future__ import annotations

import argparse
from html.parser import HTMLParser
from pathlib import Path
import sys


REQUIRED_SECTIONS = [
    "00 Product Map",
    "01 Core Loop",
    "02 Branch Flows",
    "03 Object Flow",
    "04 Decision Gates",
    "05 Entrance Rules",
    "06 AI Suggestion",
    "07 Field Policy",
    "08 Object Matrix",
    "09 Design / Dev Traceability",
    "10 Stage Scope",
    "11 Screen Inventory",
    "12 Screen State & Navigation Matrix",
    "13 Global State Priority",
    "14 Action & Decision Rules",
    "15 Empty / Error / Permission Matrix",
    "16 Object Field By Screen",
    "17 UI Handoff Checklist",
]

FORBIDDEN_PATTERNS = [
    "状态：Draft",
    "SoundPage Product Flow Spec",
    "Product Flow Spec",
    "下一阶段确认产品需求后",
    "final local validation pending",
]

DISCOVERY_FILE_HINTS = {
    "decision log": ("decision-log", "decision_log", "决策"),
    "open questions": ("open-questions", "open_questions", "待确认", "未决"),
}


class _Parser(HTMLParser):
    pass


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _iter_doc_files(root: Path):
    for suffix in ("*.md", "*.html"):
        yield from root.rglob(suffix)


def validate(args: argparse.Namespace) -> list[str]:
    failures: list[str] = []
    flow_path = Path(args.flow)

    if not flow_path.exists():
        return [f"missing flow file: {flow_path}"]

    flow_text = _read(flow_path)
    try:
        _Parser().feed(flow_text)
    except Exception as exc:  # pragma: no cover - parser errors are environment-specific
        failures.append(f"html parse failed: {exc}")

    for marker in REQUIRED_SECTIONS:
        if marker not in flow_text:
            failures.append(f"missing Visual PRD section: {marker}")

    if "Ready for UI Design v1" not in flow_text:
        failures.append("flow file does not say Ready for UI Design v1")

    scan_paths: list[Path] = [flow_path]

    docs_root: Path | None = None
    docs_files: list[Path] = []

    if args.docs:
        docs_root = Path(args.docs)
        if not docs_root.exists():
            failures.append(f"missing docs root: {docs_root}")
        else:
            docs_files = list(_iter_doc_files(docs_root))
            scan_paths.extend(docs_files)

    if args.require_discovery:
        if docs_root is None:
            failures.append("--require-discovery needs --docs")
        elif docs_root.exists():
            markdown_names = [path.name.lower() for path in docs_root.rglob("*.md")]
            for label, hints in DISCOVERY_FILE_HINTS.items():
                if not any(any(hint in name for hint in hints) for name in markdown_names):
                    failures.append(f"missing discovery artifact: {label}")

            discovery_files = [
                path
                for path in docs_root.rglob("*.md")
                if any(
                    hint in path.name.lower()
                    for hints in DISCOVERY_FILE_HINTS.values()
                    for hint in hints
                )
            ]
            for path in discovery_files:
                if not _read(path).strip():
                    failures.append(f"empty discovery artifact: {path}")

    if args.status:
        status_path = Path(args.status)
        if not status_path.exists():
            failures.append(f"missing status file: {status_path}")
        else:
            scan_paths.append(status_path)

    unique_paths = []
    seen = set()
    for path in scan_paths:
        key = str(path.resolve())
        if key not in seen and path.exists():
            unique_paths.append(path)
            seen.add(key)

    for path in unique_paths:
        text = _read(path)
        for pattern in FORBIDDEN_PATTERNS:
            if pattern in text:
                failures.append(f"forbidden leftover `{pattern}` in {path}")

    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--flow", required=True, help="Path to the Visual PRD HTML file.")
    parser.add_argument("--docs", help="Product docs root to scan for stale wording.")
    parser.add_argument("--status", help="Project status file to scan for stale wording.")
    parser.add_argument(
        "--require-discovery",
        action="store_true",
        help="Require decision-log and open-questions artifacts for new product PRDs.",
    )
    args = parser.parse_args()

    failures = validate(args)
    if failures:
        print("prd_handoff_validation=fail")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("prd_handoff_validation=pass")
    print(f"flow={args.flow}")
    print(f"sections={len(REQUIRED_SECTIONS)}")
    if args.require_discovery:
        print("discovery_artifacts=required")
    return 0


if __name__ == "__main__":
    sys.exit(main())
