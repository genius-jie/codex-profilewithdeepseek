#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Extract the first JSON object from a research sub-agent's text reply and persist it.

Deterministic bridge for the deep phase: a read-only research sub-agent can only
RETURN JSON as prose (often wrapped in ``` fences); this tool strips the fences,
locates the first balanced top-level JSON object, parses it, writes it to the
output path, and (with --validate) runs validate_json.py on it.

Exits non-zero when no parseable JSON is found, so the caller can re-research.
This closes the "agent text -> result file" leg that previously existed only as
prose in the SKILL prompt.

Usage:
    python persist_agent_json.py -i agent_reply.txt -o results/Item.json \
        --validate --fields fields.yaml \
        --validator ~/.claude/skills/research/validate_json.py
"""

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path


def _first_json_object(s):
    start = s.find("{")
    while start != -1:
        depth = 0
        in_str = False
        esc = False
        for i in range(start, len(s)):
            c = s[i]
            if in_str:
                if esc:
                    esc = False
                elif c == "\\":
                    esc = True
                elif c == '"':
                    in_str = False
            else:
                if c == '"':
                    in_str = True
                elif c == "{":
                    depth += 1
                elif c == "}":
                    depth -= 1
                    if depth == 0:
                        try:
                            return json.loads(s[start:i + 1])
                        except json.JSONDecodeError:
                            break
        start = s.find("{", start + 1)
    return None


def extract_json(text):
    # Prefer fenced ```json / ``` blocks; fall back to any balanced object.
    for m in re.finditer(r"```(?:json|JSON)?\s*(.*?)```", text, re.DOTALL):
        obj = _first_json_object(m.group(1))
        if obj is not None:
            return obj
    return _first_json_object(text)


def _parse_receipt(stdout):
    """Read the validator's machine-readable result line; None if absent/malformed."""
    marker = "__VALIDATION_RESULT__ "
    for line in reversed(stdout.splitlines()):
        if line.startswith(marker):
            try:
                return json.loads(line[len(marker):].strip())
            except json.JSONDecodeError:
                return None
    return None


def _save_raw(a, out, text):
    if a.keep_raw:
        out.with_name(out.name + ".agent_raw.txt").write_text(text, encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description="Persist a research agent's JSON reply to disk")
    ap.add_argument("-i", "--input", help="File containing the agent reply (default: read stdin)")
    ap.add_argument("-o", "--out", required=True, help="Output JSON path")
    ap.add_argument("--validate", action="store_true", help="Run validate_json.py after writing")
    ap.add_argument("--fields", help="fields.yaml path for validation")
    ap.add_argument("--validator", default="validate_json.py", help="Path to validate_json.py")
    ap.add_argument("--mode", default="all", choices=["all", "required", "coverage"], help="Validation mode")
    ap.add_argument("--keep-raw", action="store_true", help="Also save the raw agent reply next to the output for audit")
    ap.add_argument("--unvalidated", action="store_true", help="Explicitly allow writing the file WITHOUT validation")
    a = ap.parse_args()

    if a.input:
        try:
            text = Path(a.input).expanduser().read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as e:
            print(f"[ERROR] Cannot read --input: {e}")
            sys.exit(2)
    else:
        try:
            sys.stdin.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
        text = sys.stdin.read()

    data = extract_json(text)
    if data is None:
        print("[ERROR] No parseable JSON object found in agent output")
        sys.exit(1)

    out = Path(a.out).expanduser()
    if out.parent and not out.parent.exists():
        out.parent.mkdir(parents=True, exist_ok=True)
    # Write to a temp file first; publish to the final path only if it validates.
    tmp = out.with_name(out.name + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if a.validate:
        if not a.fields:
            tmp.unlink(missing_ok=True)
            print("[ERROR] --validate requires --fields")
            sys.exit(2)
        cmd = [sys.executable, a.validator, "-f", a.fields, "-j", str(tmp), "--mode", a.mode, "--quiet"]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True)
        except OSError as e:
            tmp.unlink(missing_ok=True)
            print(f"[ERROR] Could not run validator: {e}; previous result kept")
            sys.exit(1)
        receipt = _parse_receipt(proc.stdout)
        overall = receipt.get("overall") if receipt else None
        # Publish ONLY on a valid receipt. complete/needs_review are honest outcomes that
        # may be stored; rc==2 (argparse/tool error) or a missing receipt are NOT
        # "needs_review" and must never publish an unvalidated file.
        if proc.returncode == 0 and overall in ("complete", "needs_review"):
            os.replace(tmp, out)
            _save_raw(a, out, text)
            print(f"Wrote {out} (validated: {overall})")
            sys.exit(0)
        tmp.unlink(missing_ok=True)
        print(f"[ERROR] Not published (validator rc={proc.returncode}, receipt={overall or 'NONE'}); previous result kept")
        sys.exit(1)

    if not a.unvalidated:
        tmp.unlink(missing_ok=True)
        print("[ERROR] refusing to publish without validation; pass --validate, or --unvalidated to write an unchecked candidate")
        sys.exit(2)
    os.replace(tmp, out)
    _save_raw(a, out, text)
    print(f"[UNVALIDATED] Wrote {out} (explicitly unvalidated; resume/report must re-check status against current fields.yaml)")


if __name__ == "__main__":
    main()
