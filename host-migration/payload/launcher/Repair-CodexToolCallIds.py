#!/usr/bin/env python3
"""Sanitize custom_tool_call and function_call IDs in Codex session transcripts.

Converts invalid 'msg_' prefixes to required 'ctc_' (custom_tool_call) or 'fc_' (function_call)
to prevent OpenAI schema rejections ('Expected an ID that begins with ctc') when switching
from third-party models (e.g. Qwen) to OpenAI official models (e.g. GPT-5.6 / GPT-6).
"""

from __future__ import annotations

import glob
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path


def sanitize_transcript_tool_ids(transcript_path: str | Path | None) -> tuple[int, int]:
    """Sanitize a single transcript file in-place."""
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
                    # tool_call_id references in *output* items must track the
                    # call id rewrite, otherwise OpenAI rejects the pairing.
                    tcid = payload.get("tool_call_id")
                    if isinstance(tcid, str) and tcid.startswith("msg_"):
                        if ptype == "custom_tool_call_output":
                            payload["tool_call_id"] = "ctc_" + tcid[4:]
                            ctc_fixed += 1
                            modified = True
                            line = json.dumps(data, ensure_ascii=False) + "\n"
                        elif ptype == "function_call_output":
                            payload["tool_call_id"] = "fc_" + tcid[4:]
                            fc_fixed += 1
                            modified = True
                            line = json.dumps(data, ensure_ascii=False) + "\n"
            else:
                # Top-level item shapes (some rollouts store the tool call
                # object directly without a response_item wrapper).
                ttype = data.get("type")
                if ttype in ("custom_tool_call", "function_call"):
                    tid = data.get("id")
                    want = "ctc_" if ttype == "custom_tool_call" else "fc_"
                    if isinstance(tid, str) and tid.startswith("msg_"):
                        data["id"] = want + tid[4:]
                        if ttype == "custom_tool_call":
                            ctc_fixed += 1
                        else:
                            fc_fixed += 1
                        modified = True
                        line = json.dumps(data, ensure_ascii=False) + "\n"
                elif ttype in ("custom_tool_call_output", "function_call_output"):
                    tcid2 = data.get("tool_call_id")
                    want2 = "ctc_" if ttype == "custom_tool_call_output" else "fc_"
                    if isinstance(tcid2, str) and tcid2.startswith("msg_"):
                        data["tool_call_id"] = want2 + tcid2[4:]
                        if ttype == "custom_tool_call_output":
                            ctc_fixed += 1
                        else:
                            fc_fixed += 1
                        modified = True
                        line = json.dumps(data, ensure_ascii=False) + "\n"
            new_lines.append(line)

        if modified:
            # Back up the original before rewriting (idempotent: the backup is
            # only created when an actual rewrite happens).
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup = path.with_name(path.name + f".bak_idfix_{ts}")
            try:
                with open(backup, "wb") as bf:
                    bf.write(content.encode("utf-8"))
            except Exception:
                pass  # best-effort backup; do not block the repair
            with open(path, "r+", encoding="utf-8") as f:
                f.seek(0)
                f.writelines(new_lines)
                f.truncate()

        return ctc_fixed, fc_fixed
    except Exception:
        return 0, 0


def scan_and_repair_sessions(
    root_dirs: list[str | Path] | None = None,
    max_days: int = 0,
) -> dict[str, int]:
    """Scan and repair all sessions in candidate root directories.

    By default scans ALL sessions regardless of age (max_days=0), because any
    historical session may be resumed/replayed when the user switches models.
    Pass max_days>0 to limit to recent files only.
    """
    if not root_dirs:
        root_dirs = [
            Path(r"@@CODEXPP_HOME:win@@\sessions"),
            Path(r"@@USERPROFILE:win@@\AppData\Roaming\CodexPlusPlusProfile\AppData\Roaming\Codex\.codex\sessions"),
        ]

    seen_real_paths = set()
    total_files = 0
    repaired_files = 0
    total_ctc = 0
    total_fc = 0

    cutoff = datetime.now() - timedelta(days=max_days) if max_days > 0 else None

    for rdir in root_dirs:
        rpath = Path(rdir)
        if not rpath.is_dir():
            continue
        for fpath in rpath.rglob("*.jsonl"):
            try:
                real_p = str(fpath.resolve())
                if real_p in seen_real_paths:
                    continue
                seen_real_paths.add(real_p)

                if cutoff is not None:
                    mtime = datetime.fromtimestamp(fpath.stat().st_mtime)
                    if mtime < cutoff:
                        continue

                total_files += 1
                ctc, fc = sanitize_transcript_tool_ids(fpath)
                if ctc > 0 or fc > 0:
                    repaired_files += 1
                    total_ctc += ctc
                    total_fc += fc
                    print(f"[REPAIRED] {fpath.name}: fixed {ctc} ctc, {fc} fc IDs")
            except Exception:
                continue

    return {
        "scanned_files": total_files,
        "repaired_files": repaired_files,
        "repaired_ctc": total_ctc,
        "repaired_fc": total_fc,
    }


def main() -> int:
    if len(sys.argv) > 1:
        target = sys.argv[1]
        p = Path(target)
        if p.is_file():
            ctc, fc = sanitize_transcript_tool_ids(p)
            print(f"Repaired {p}: {ctc} ctc, {fc} fc IDs.")
            return 0
        elif p.is_dir():
            stats = scan_and_repair_sessions(root_dirs=[p], max_days=365)
            print(f"Batch repair summary: {stats}")
            return 0
        else:
            print(f"Target not found: {target}")
            return 1

    stats = scan_and_repair_sessions()
    print(f"Auto-scan summary: {stats}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
