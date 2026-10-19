#!/usr/bin/env python3
"""Regression tests for the Codex Commander Stop bridge."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


HOOK_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HOOK_DIR))

import stop_hook_bridge as bridge  # noqa: E402


def _run(command: list[str], cwd: Path) -> None:
    result = subprocess.run(
        command,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    if result.returncode != 0:
        raise AssertionError(f"{command} failed: {result.stderr}")


def _init_repo(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    _run(["git", "init"], path)
    return path


def _patch_bridge_paths(state_dir: Path) -> None:
    bridge.COMMANDER_STATE_DIR = state_dir
    bridge.BRIDGE_FILE = state_dir / "stop_bridge.json"
    bridge.BRIDGE_LOCK = state_dir / "stop_bridge.lock"
    bridge.BRIDGE_HISTORY = state_dir / "bridge_history.jsonl"


def _read_report() -> dict:
    return json.loads(bridge.BRIDGE_FILE.read_text(encoding="utf-8"))


def _clean_env() -> None:
    for key in (
        "CODEX_COMMANDER_EXPECTED_CWD",
        "OPENCLAW_COMMANDER_EXPECTED_CWD",
        "COMMANDER_EXPECTED_CWD",
        "CODEX_COMMANDER_BASELINE_STATUS_HASH",
        "OPENCLAW_COMMANDER_BASELINE_STATUS_HASH",
        "COMMANDER_BASELINE_STATUS_HASH",
        "CODEX_COMMANDER_TASK_TOKEN",
        "OPENCLAW_COMMANDER_TASK_TOKEN",
        "COMMANDER_TASK_TOKEN",
    ):
        os.environ.pop(key, None)


def test_parsed_completion_receipt() -> None:
    receipt = bridge._receipt_summary(
        'done STOP_COMPLETION_RECEIPT: {"status":"complete","verification":["py_compile"],"open_items":[],"contract_ids":["C1"],"skill_route":["P3_单体极速流水线"]}'
    )
    assert receipt["present"] is True
    assert receipt["valid"] is True
    assert receipt["is_complete"] is True
    assert receipt["verification_count"] == 1
    assert receipt["contract_ids"] == ["C1"]
    assert receipt["contracts_met"] == ["C1"]
    assert receipt["skill_route"] == ["P3_单体极速流水线"]


def test_invalid_receipt_is_not_completion() -> None:
    receipt = bridge._receipt_summary("STOP_COMPLETION_RECEIPT: {...}")
    assert receipt["present"] is True
    assert receipt["valid"] is False
    assert receipt["is_complete"] is False
    assert receipt["parse_error"]


def test_bridge_writes_expected_cwd_and_baseline() -> None:
    with tempfile.TemporaryDirectory(prefix="bridge-test-") as tmp:
        root = Path(tmp)
        repo = _init_repo(root / "repo")
        (repo / "new.txt").write_text("new\n", encoding="utf-8")
        _patch_bridge_paths(root / "state")
        _clean_env()
        os.environ["CODEX_COMMANDER_EXPECTED_CWD"] = str(repo)
        os.environ["CODEX_COMMANDER_BASELINE_STATUS_HASH"] = hashlib.sha256(b"").hexdigest()
        try:
            bridge.write_bridge_report(
                {"session_id": "s1", "cwd": str(repo)},
                'ok STOP_COMPLETION_RECEIPT: {"status":"complete","verification":["smoke"],"open_items":[],"contract_ids":["C1"],"skill_route":["P3_单体极速流水线"]}',
                "",
                {},
            )
            report = _read_report()
            assert report["guard_decision"] == "allowed"
            assert report["expected_cwd_match"] is True
            assert report["target_cwd_trusted"] is True
            assert report["has_completion_receipt"] is True
            assert report["receipt"]["is_complete"] is True
            assert report["git_status_hash"]
            assert report["changed_since_baseline"] is True
            assert "new.txt" in report["git_status_summary"]
            assert "new.txt" in report["git_diff_summary"]
            assert report["contract_ids"] == ["C1"]
            assert report["contracts_met"] == ["C1"]
            assert report["skill_route"] == ["P3_单体极速流水线"]
        finally:
            _clean_env()


def test_bridge_records_commander_task_token() -> None:
    with tempfile.TemporaryDirectory(prefix="bridge-test-") as tmp:
        root = Path(tmp)
        repo = _init_repo(root / "repo")
        _patch_bridge_paths(root / "state")
        _clean_env()
        os.environ["CODEX_COMMANDER_EXPECTED_CWD"] = str(repo)
        os.environ["CODEX_COMMANDER_TASK_TOKEN"] = "COMMANDER_SMOKE_TASK=probe-cwd-token"
        try:
            bridge.write_bridge_report(
                {"session_id": "s-token", "cwd": str(repo)},
                "Smoke check passed.",
                "",
                {},
            )
            report = _read_report()
            assert report["commander_task_token"] == "COMMANDER_SMOKE_TASK=probe-cwd-token"
        finally:
            _clean_env()


def test_git_status_hash_preserves_porcelain_leading_space() -> None:
    with tempfile.TemporaryDirectory(prefix="bridge-test-") as tmp:
        root = Path(tmp)
        repo = _init_repo(root / "repo")
        _run(["git", "config", "user.email", "bridge@example.test"], repo)
        _run(["git", "config", "user.name", "Bridge Test"], repo)
        (repo / "tracked.txt").write_text("before\n", encoding="utf-8")
        _run(["git", "add", "tracked.txt"], repo)
        _run(["git", "commit", "-m", "init"], repo)
        (repo / "tracked.txt").write_text("after\n", encoding="utf-8")
        _patch_bridge_paths(root / "state")
        _clean_env()
        os.environ["CODEX_COMMANDER_EXPECTED_CWD"] = str(repo)
        os.environ["CODEX_COMMANDER_BASELINE_STATUS_HASH"] = hashlib.sha256(b" M tracked.txt").hexdigest()
        try:
            bridge.write_bridge_report(
                {"session_id": "s-leading-space", "cwd": str(repo)},
                "Smoke check passed.",
                "",
                {},
            )
            report = _read_report()
            assert report["git_status_summary"] == " M tracked.txt"
            assert report["changed_since_baseline"] is False
        finally:
            _clean_env()


def test_output_cwd_mismatch_is_untrusted() -> None:
    with tempfile.TemporaryDirectory(prefix="bridge-test-") as tmp:
        root = Path(tmp)
        expected = _init_repo(root / "expected")
        actual = _init_repo(root / "actual")
        _patch_bridge_paths(root / "state")
        _clean_env()
        os.environ["CODEX_COMMANDER_EXPECTED_CWD"] = str(expected)
        try:
            bridge.write_bridge_report(
                {"session_id": "s2"},
                f"current working directory: {actual}\nSTOP_COMPLETION_RECEIPT: {{\"status\":\"complete\",\"verification\":[\"smoke\"],\"open_items\":[]}}",
                "",
                {},
            )
            report = _read_report()
            assert report["codex_cwd_source"] == "output"
            assert report["expected_cwd_match"] is False
            assert report["target_cwd_trusted"] is False
        finally:
            _clean_env()


def main() -> int:
    test_parsed_completion_receipt()
    test_invalid_receipt_is_not_completion()
    test_bridge_writes_expected_cwd_and_baseline()
    test_bridge_records_commander_task_token()
    test_git_status_hash_preserves_porcelain_leading_space()
    test_output_cwd_mismatch_is_untrusted()
    print("test_stop_hook_bridge: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
