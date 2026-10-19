#!/usr/bin/env python3
"""Regression tests for PostToolUse pending-failure fingerprints."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


HOOK_DIR = Path(__file__).resolve().parents[1]
POST_TOOL_USE = HOOK_DIR / "post_tool_use_audit.py"
sys.path.insert(0, str(HOOK_DIR))

from post_tool_use_audit import failure_fingerprint, failure_fingerprint_key  # noqa: E402


def assert_equal(name: str, actual: object, expected: object) -> None:
    if actual != expected:
        raise AssertionError(f"{name}: expected {expected!r}, got {actual!r}")
    print(f"{name}: OK")


def assert_contains(name: str, text: str, needle: str) -> None:
    if needle not in text:
        raise AssertionError(f"{name}: missing {needle!r} in {text!r}")
    print(f"{name}: OK")


def run_post_tool_use(
    name: str,
    event: dict,
    pending: dict,
    cwd: str = r"@@OPENCLAW_ROOT:win@@",
    evidence_receipts: dict[str, dict] | None = None,
) -> tuple[str, dict]:
    with tempfile.TemporaryDirectory(prefix="post-tool-audit-test-") as tmp:
        home = Path(tmp)
        state_dir = home / "hook-state"
        state_dir.mkdir(parents=True)
        state_path = state_dir / "openclaw-mono-pending.json"
        state_path.write_text(json.dumps({"pending": pending}, ensure_ascii=False), encoding="utf-8")
        if evidence_receipts:
            workspace = home / "workspace"
            evidence_dir = workspace / ".codex-evidence"
            evidence_dir.mkdir(parents=True)
            cwd = str(workspace)
            for filename, receipt in evidence_receipts.items():
                (evidence_dir / filename).write_text(json.dumps(receipt, ensure_ascii=False), encoding="utf-8")

        env = os.environ.copy()
        env["CODEX_HOME"] = str(home)
        env["PYTHONPATH"] = str(HOOK_DIR)
        proc = subprocess.run(
            ["python", str(POST_TOOL_USE)],
            input=json.dumps(event, ensure_ascii=False),
            text=True,
            capture_output=True,
            cwd=cwd,
            env=env,
            timeout=20,
            check=False,
        )
        if proc.returncode != 0:
            raise AssertionError(f"{name}: returncode={proc.returncode} stderr={proc.stderr}")
        state = json.loads(state_path.read_text(encoding="utf-8"))
        return proc.stdout, state


def invoke_post_tool_use(home: Path, event: dict, cwd: str) -> tuple[str, dict]:
    state_dir = home / "hook-state"
    state_dir.mkdir(parents=True, exist_ok=True)
    state_path = state_dir / "openclaw-mono-pending.json"
    if not state_path.exists():
        state_path.write_text('{"pending": {}}', encoding="utf-8")
    env = os.environ.copy()
    env["CODEX_HOME"] = str(home)
    env["PYTHONPATH"] = str(HOOK_DIR)
    proc = subprocess.run(
        ["python", str(POST_TOOL_USE)],
        input=json.dumps(event, ensure_ascii=False),
        text=True,
        capture_output=True,
        cwd=cwd,
        env=env,
        timeout=20,
        check=False,
    )
    if proc.returncode != 0:
        raise AssertionError(f"returncode={proc.returncode} stderr={proc.stderr}")
    return proc.stdout, json.loads(state_path.read_text(encoding="utf-8"))


def main() -> int:
    python_false = (
        'openclaw tasks list --runtime cron --json | python -c '
        '"import json,sys; data=json.load(sys.stdin); '
        'print(json.dumps(data, ensure_ascii=False, indent=2)[:12000])"'
    )
    json_false = python_false.replace("ensure_ascii=False", "ensure_ascii=false")

    display = failure_fingerprint(python_false)
    assert_contains("preserve_python_false_display", display, "ensure_ascii=False")
    assert_equal(
        "semantic_false_key",
        failure_fingerprint_key(failure_fingerprint(python_false)),
        failure_fingerprint_key(failure_fingerprint(json_false)),
    )

    failed_command = "Get-Content -LiteralPath 'C:/tmp/example.py'"
    fingerprint = failure_fingerprint(failed_command)
    stdout, state = run_post_tool_use(
        "failure_review_s12_evidence_clears",
        {
            "tool_name": "Bash",
            "tool_input": {"command": "echo hook evidence"},
            "tool_response": {
                "exit_code": 0,
                "output": json.dumps(
                    {
                        "command_fingerprint": fingerprint,
                        "hook_resolution": "failure-review",
                        "s12": "pass",
                        "rerun_exit_code": 0,
                    },
                    ensure_ascii=False,
                ),
            },
        },
        {
            "pending_failure_review": {
                "command_fingerprint": fingerprint,
                "last_command": failed_command,
                "failure_count": 2,
            }
        },
    )
    if (state.get("pending") or {}).get("pending_failure_review"):
        raise AssertionError(f"failure_review_s12_evidence_clears: pending still present: {state}")
    assert_contains("failure_review_s12_evidence_clears_stdout", stdout, "pending_failure_review cleared")

    equals_command = (
        "python -B -c \"import json,pathlib; "
        "p=pathlib.Path(r'@@TESTING_ROOT:escaped@@\\.agent\\config\\perf_environment_registry.json'); "
        "d=json.loads(p.read_text(encoding='utf-8-sig')); "
        "print(json.dumps({'ex"
    )
    equals_fingerprint = failure_fingerprint(equals_command)
    stdout, state = run_post_tool_use(
        "failure_review_equals_evidence_clears",
        {
            "tool_name": "Bash",
            "tool_input": {"command": "Write-Output hook evidence"},
            "tool_response": {
                "exit_code": 0,
                "output": "\n".join(
                    [
                        "hook_resolution=failure-review",
                        "s12=pass",
                        "w9=pass",
                        "rerun_exit_code=0",
                        f"command_fingerprint={equals_fingerprint}",
                    ]
                ),
            },
        },
        {
            "pending_failure_review": {
                "command_fingerprint": equals_fingerprint,
                "last_command": equals_command,
                "failure_count": 1,
            }
        },
    )
    if (state.get("pending") or {}).get("pending_failure_review"):
        raise AssertionError(f"failure_review_equals_evidence_clears: pending still present: {state}")
    assert_contains("failure_review_equals_evidence_clears_stdout", stdout, "pending_failure_review cleared")

    file_fingerprint = failure_fingerprint(
        "$ErrorActionPreference='Stop'; $pat='(?i)(api[_-]?key|access[_-]?token|secret|password|cookie_string|cookie_header|Set-Cookie)'; $hits = git -c grep.patternType=perl diff -G $pat -"
    )
    stdout, state = run_post_tool_use(
        "failure_review_file_receipt_clears",
        {
            "tool_name": "Bash",
            "tool_input": {"command": "Write-Output evidence recorded"},
            "tool_response": {"exit_code": 0, "output": "evidence file exists"},
        },
        {
            "pending_failure_review": {
                "command_fingerprint": file_fingerprint,
                "last_command": file_fingerprint,
                "failure_count": 1,
            }
        },
        evidence_receipts={
            "s12-w9-stop-guard-sticky-sensitive-scan.json": {
                "evidenceType": "S12_W9_STOP_GUARD_STICKY_RESOLUTION",
                "status": "PASS",
                "failingFingerprint": file_fingerprint,
                "hitCount": 0,
            }
        },
    )
    if (state.get("pending") or {}).get("pending_failure_review"):
        raise AssertionError(f"failure_review_file_receipt_clears: pending still present: {state}")
    assert_contains("failure_review_file_receipt_clears_stdout", stdout, "pending_failure_review cleared")

    s15_read_command = 'Get-Content -Raw ".agents\\skills\\S15_Git提交全链路\\SKILL.md" | Select-Object -First 1'
    s15_fingerprint = failure_fingerprint(s15_read_command)
    stdout, state = run_post_tool_use(
        "successful_get_content_body_error_terms_clear_pending",
        {
            "tool_name": "Bash",
            "tool_input": {"command": s15_read_command},
            "tool_response": (
                "---\n"
                "name: S15_Git提交全链路\n"
                "Error: examples in this documentation are not command failures\n"
                "failed command examples should not poison successful Get-Content reads\n"
            ),
        },
        {
            "pending_failure_review": {
                "command_fingerprint": s15_fingerprint,
                "last_command": s15_read_command,
                "failure_count": 3,
            }
        },
    )
    if (state.get("pending") or {}).get("pending_failure_review"):
        raise AssertionError(f"successful_get_content_body_error_terms_clear_pending: pending still present: {state}")
    assert_contains("successful_get_content_body_error_terms_clear_pending_stdout", stdout, "pending_failure_review cleared")

    guarded_s15_read_command = (
        'if (Test-Path ".agents\\skills\\S15_Git提交全链路\\SKILL.md") '
        '{ Get-Content -Raw ".agents\\skills\\S15_Git提交全链路\\SKILL.md" | Select-Object -First 1 } '
        "else { 'SKILL_NOT_FOUND' }"
    )
    guarded_s15_fingerprint = failure_fingerprint(guarded_s15_read_command)
    stdout, state = run_post_tool_use(
        "guarded_get_content_body_exception_terms_clear_pending",
        {
            "tool_name": "functions.shell_command",
            "tool_input": {"command": guarded_s15_read_command},
            "tool_response": (
                "---\n"
                "name: S15_Git提交全链路\n"
                "Exception: documentation examples are not command failures\n"
                "successful guarded Get-Content probes should clear pending failure review\n"
            ),
        },
        {
            "pending_failure_review": {
                "command_fingerprint": guarded_s15_fingerprint,
                "last_command": guarded_s15_read_command,
                "failure_count": 2,
            }
        },
    )
    if (state.get("pending") or {}).get("pending_failure_review"):
        raise AssertionError(f"guarded_get_content_body_exception_terms_clear_pending: pending still present: {state}")
    assert_contains("guarded_get_content_body_exception_terms_clear_pending_stdout", stdout, "pending_failure_review cleared")

    stdout, state = run_post_tool_use(
        "codexplusplus_nongit_status_probe_ignored",
        {
            "tool_name": "Bash",
            "tool_input": {"command": 'powershell -NoProfile -Command "git status --short"'},
            "tool_response": {
                "exit_code": 1,
                "output": "fatal: not a git repository (or any of the parent directories): .git",
            },
        },
        {},
        cwd=r"@@LAUNCHER_ROOT:win@@",
    )
    if (state.get("pending") or {}).get("pending_failure_review"):
        raise AssertionError(f"codexplusplus_nongit_status_probe_ignored: pending marked: {state}")
    assert_contains("codexplusplus_nongit_status_probe_ignored_stdout", stdout, "benign non-git Codex++ git status probe ignored")

    stdout, state = run_post_tool_use(
        "requirements_install_clears_permission_review",
        {
            "tool_name": "functions.shell_command",
            "tool_input": {"command": "python -m pip install -r requirements-dev.txt"},
            "tool_response": {"exit_code": 0, "output": "Successfully installed harness-0.1.0"},
        },
        {"pending_permission_review": {"reason": "dependency install requires review"}},
    )
    if (state.get("pending") or {}).get("pending_permission_review"):
        raise AssertionError(f"requirements_install_clears_permission_review: pending still present: {state}")
    assert_contains("requirements_install_clears_permission_review_stdout", stdout, "pending_permission_review cleared")

    stdout, state = run_post_tool_use(
        "non_shell_patch_text_does_not_mark_s15",
        {
            "tool_name": "apply_patch",
            "tool_input": {"command": "git commit -m documentation-example"},
            "tool_response": {"exit_code": 0, "output": "Done"},
        },
        {},
    )
    if (state.get("pending") or {}).get("pending_s15"):
        raise AssertionError(f"non_shell_patch_text_does_not_mark_s15: pending marked: {state}")

    with tempfile.TemporaryDirectory(prefix="post-tool-session-scope-") as tmp:
        home = Path(tmp)
        cwd = str(home)
        command_a = "python -c \"raise RuntimeError('a')\""
        command_b = "python -c \"raise RuntimeError('b')\""
        base_a = {
            "session_id": "session-a",
            "turn_id": "turn-a",
            "tool_name": "Bash",
            "tool_input": {"command": command_a},
        }
        base_b = {
            "session_id": "session-b",
            "turn_id": "turn-b",
            "tool_name": "Bash",
            "tool_input": {"command": command_b},
        }
        invoke_post_tool_use(
            home,
            {**base_a, "tool_response": {"exit_code": 1, "output": "probe a stopped"}},
            cwd,
        )
        _, state = invoke_post_tool_use(
            home,
            {**base_b, "tool_response": {"exit_code": 1, "output": "probe b stopped"}},
            cwd,
        )
        failure_items = [
            item
            for key, item in (state.get("pending") or {}).items()
            if key == "pending_failure_review" or key.startswith("pending_failure_review@session:")
        ]
        assert_equal(
            "two_sessions_keep_independent_failure_reviews",
            sorted(item.get("session_id") for item in failure_items),
            ["session-a", "session-b"],
        )
        _, state = invoke_post_tool_use(
            home,
            {**base_b, "tool_response": {"exit_code": 0, "output": "probe b completed"}},
            cwd,
        )
        failure_items = [
            item
            for key, item in (state.get("pending") or {}).items()
            if key == "pending_failure_review" or key.startswith("pending_failure_review@session:")
        ]
        assert_equal(
            "session_b_rerun_clears_only_session_b",
            [item.get("session_id") for item in failure_items],
            ["session-a"],
        )
        _, state = invoke_post_tool_use(
            home,
            {**base_a, "tool_response": {"exit_code": 0, "output": "probe a completed"}},
            cwd,
        )
        failure_items = [
            key
            for key in (state.get("pending") or {})
            if key == "pending_failure_review" or key.startswith("pending_failure_review@session:")
        ]
        assert_equal("session_a_rerun_clears_session_a", failure_items, [])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
