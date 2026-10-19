#!/usr/bin/env python3
"""Regression tests for PostToolUse failure-review cleanup."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


HOOK_DIR = Path(__file__).resolve().parents[1]
POST_TOOL_USE = HOOK_DIR / "post_tool_use_audit.py"
HOOK_RUNNER = HOOK_DIR / "hook_runner.py"


def failure_fingerprint_for_test(command: str) -> str:
    lowered = " ".join(command.lower().split()).strip()
    for marker in (
        "verify_testing_governance.py",
        "verify-governance-hard-gate.ps1",
        "reconcile-birth-ceremony.py",
        "py_compile",
    ):
        if marker in lowered:
            return marker
    return lowered[:180]


def run_post_tool_use(name: str, event: dict, pending: dict) -> tuple[dict, str]:
    with tempfile.TemporaryDirectory(prefix="post-tool-use-test-") as tmp:
        home = Path(tmp)
        state_dir = home / "hook-state"
        state_dir.mkdir(parents=True)
        state_path = state_dir / "openclaw-mono-pending.json"
        state_path.write_text(json.dumps({"pending": pending}, ensure_ascii=False), encoding="utf-8")

        env = os.environ.copy()
        env["CODEX_HOME"] = str(home)
        env["PYTHONPATH"] = str(HOOK_DIR)
        # The runner must remove this untrusted inherited value before child launch.
        env["CODEX_HOOK_CALLER_CWD"] = r"C:\ctx02-inherited-poison"
        proc = subprocess.run(
            [
                sys.executable,
                str(HOOK_RUNNER),
                "--event",
                "PostToolUse",
                "--script",
                str(POST_TOOL_USE),
            ],
            input=json.dumps(event, ensure_ascii=False),
            text=True,
            capture_output=True,
            # The child always runs in HOOK_DIR; scope must therefore come from
            # the runner's verified event cwd, never child os.getcwd().
            cwd=str(HOOK_DIR),
            env=env,
            timeout=20,
            check=False,
        )
        if proc.returncode != 0:
            raise AssertionError(f"{name}: returncode={proc.returncode} stderr={proc.stderr}")
        state = json.loads(state_path.read_text(encoding="utf-8"))
        return state, proc.stdout


def main() -> int:
    fingerprint = "get-content -literalpath 'c:/tmp/example.py'"
    pending = {
        "pending_failure_review@turn:post_tool_s12_evidence": {
            "reason": "tool reported repeated errors; run S12 and consider M9",
            "command_fingerprint": fingerprint,
            "last_command": fingerprint,
            "failure_count": 2,
            "owner_scope": "turn:post_tool_s12_evidence",
            "turn_id": "post_tool_s12_evidence",
        }
    }
    event = {
        "turn_id": "post_tool_s12_evidence",
        "tool_name": "Bash",
        "tool_input": {"command": "echo hook evidence"},
        "tool_response": {
            "exit_code": 0,
            "output": (
                "{"
                '"hook_resolution":"failure-review",'
                '"s12":"pass",'
                '"rerun_exit_code":0,'
                f'"command_fingerprint":"{fingerprint}"'
                "}"
            ),
        },
    }
    state, stdout = run_post_tool_use("s12_evidence_clears_pending", event, pending)
    if state.get("pending", {}).get("pending_failure_review@turn:post_tool_s12_evidence"):
        raise AssertionError(f"s12_evidence_clears_pending: pending was not cleared: {state}")
    if "pending_failure_review cleared" not in stdout:
        raise AssertionError(f"s12_evidence_clears_pending: missing clear note: {stdout}")
    print("s12_evidence_clears_pending: CLEARED")

    equals_fingerprint = (
        "python -B -c \"import json,pathlib; p=pathlib.Path(r'@@TESTING_ROOT:escaped@@\\.agent\\config\\perf_environment_registry.json'); "
        "d=json.loads(p.read_text(encoding='utf-8-sig')); print(json.dumps({'ex"
    )
    equals_pending = {
        "pending_failure_review@turn:post_tool_s12_equals_evidence": {
            "reason": "tool reported error; rerun the failed command or provide S12/W9 evidence",
            "command_fingerprint": equals_fingerprint,
            "last_command": equals_fingerprint,
            "failure_count": 1,
            "owner_scope": "turn:post_tool_s12_equals_evidence",
            "turn_id": "post_tool_s12_equals_evidence",
        }
    }
    equals_event = {
        "turn_id": "post_tool_s12_equals_evidence",
        "tool_name": "Bash",
        "tool_input": {"command": "echo hook evidence"},
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
    }
    state, stdout = run_post_tool_use("s12_equals_evidence_clears_pending", equals_event, equals_pending)
    if state.get("pending", {}).get("pending_failure_review@turn:post_tool_s12_equals_evidence"):
        raise AssertionError(f"s12_equals_evidence_clears_pending: pending was not cleared: {state}")
    if "pending_failure_review cleared" not in stdout:
        raise AssertionError(f"s12_equals_evidence_clears_pending: missing clear note: {stdout}")
    print("s12_equals_evidence_clears_pending: CLEARED")

    marker_pending = {
        "pending_failure_review@turn:post_tool_s12_w9_marker": {
            "reason": "tool reported error; rerun the failed command or provide S12/W9 evidence",
            "command_fingerprint": "original-failing-command",
            "last_command": "original-failing-command",
            "failure_count": 1,
            "owner_scope": "turn:post_tool_s12_w9_marker",
            "turn_id": "post_tool_s12_w9_marker",
        }
    }
    marker_event = {
        "turn_id": "post_tool_s12_w9_marker",
        "tool_name": "Bash",
        "tool_input": {"command": "python equivalent_success.py"},
        "tool_response": {
            "exit_code": 0,
            "output": "S12/W9_EVIDENCE=PASS\nreplay_exit=0",
        },
    }
    state, stdout = run_post_tool_use(
        "standalone_s12_w9_marker_clears_equivalent_success",
        marker_event,
        marker_pending,
    )
    if state.get("pending", {}).get("pending_failure_review@turn:post_tool_s12_w9_marker"):
        raise AssertionError(
            "standalone_s12_w9_marker_clears_equivalent_success: pending was not cleared: "
            f"{state}"
        )
    if "pending_failure_review cleared" not in stdout:
        raise AssertionError(
            "standalone_s12_w9_marker_clears_equivalent_success: missing clear note: "
            f"{stdout}"
        )
    print("standalone_s12_w9_marker_clears_equivalent_success: CLEARED")

    guarded_read_command = (
        'if (Test-Path ".agents\\skills\\S15_Git提交全链路\\SKILL.md") '
        '{ Get-Content -Raw ".agents\\skills\\S15_Git提交全链路\\SKILL.md" | Select-Object -First 1 } '
        "else { 'SKILL_NOT_FOUND' }"
    )
    guarded_fingerprint = failure_fingerprint_for_test(guarded_read_command)
    guarded_pending = {
        "pending_failure_review@turn:post_tool_guarded_get_content_string_surface": {
            "reason": "tool reported repeated errors; run S12 and consider M9",
            "command_fingerprint": guarded_fingerprint,
            "last_command": guarded_read_command,
            "failure_count": 2,
            "owner_scope": "turn:post_tool_guarded_get_content_string_surface",
            "turn_id": "post_tool_guarded_get_content_string_surface",
        }
    }
    guarded_event = {
        "turn_id": "post_tool_guarded_get_content_string_surface",
        "tool_name": "functions.shell_command",
        "tool_input": {"command": guarded_read_command},
        "tool_response": (
            "---\n"
            "name: S15_Git提交全链路\n"
            "Exception: documentation examples are not command failures\n"
            "successful guarded Get-Content probes should clear pending failure review\n"
        ),
    }
    state, stdout = run_post_tool_use("guarded_get_content_string_surface_clears_pending", guarded_event, guarded_pending)
    if state.get("pending", {}).get("pending_failure_review@turn:post_tool_guarded_get_content_string_surface"):
        raise AssertionError(f"guarded_get_content_string_surface_clears_pending: pending was not cleared: {state}")
    if "pending_failure_review cleared" not in stdout:
        raise AssertionError(f"guarded_get_content_string_surface_clears_pending: missing clear note: {stdout}")
    print("guarded_get_content_string_surface_clears_pending: CLEARED")

    host_exit_pending = {
        "pending_failure_review@turn:post_tool_host_exit_zero_with_archived_traceback": {
            "reason": "tool reported repeated errors; run S12 and consider M9",
            "command_fingerprint": "rg -n 'traceback' historical-result.json",
            "last_command": "rg -n 'traceback' historical-result.json",
            "failure_count": 2,
            "owner_scope": "turn:post_tool_host_exit_zero_with_archived_traceback",
            "turn_id": "post_tool_host_exit_zero_with_archived_traceback",
        }
    }
    host_exit_event = {
        "turn_id": "post_tool_host_exit_zero_with_archived_traceback",
        "tool_name": "functions.shell_command",
        "tool_input": {"command": "rg -n 'traceback' historical-result.json"},
        "tool_response": (
            "Script completed\n"
            "Exit code: 0\n"
            "pipeline_crash_traceback: Traceback (most recent call last)\n"
            "archived failure payload\n"
        ),
    }
    state, stdout = run_post_tool_use(
        "host_exit_zero_with_archived_traceback_clears_pending",
        host_exit_event,
        host_exit_pending,
    )
    if state.get("pending", {}).get("pending_failure_review@turn:post_tool_host_exit_zero_with_archived_traceback"):
        raise AssertionError(
            "host_exit_zero_with_archived_traceback_clears_pending: "
            f"pending was not cleared: {state}"
        )
    if "pending_failure_review cleared" not in stdout:
        raise AssertionError(
            "host_exit_zero_with_archived_traceback_clears_pending: "
            f"missing clear note: {stdout}"
        )
    print("host_exit_zero_with_archived_traceback_clears_pending: CLEARED")

    scoped_failure_event = {
        "turn_id": "post_tool_scoped_failure",
        "session_id": "session-current",
        "tool_name": "Bash",
        "tool_input": {"command": "python broken_command.py"},
        "tool_response": {"exit_code": 1, "output": "Exit code: 1"},
    }
    state, _stdout = run_post_tool_use("failure_review_is_scoped_to_session", scoped_failure_event, {})
    scoped_item = state.get("pending", {}).get("pending_failure_review:session-current")
    if not scoped_item or scoped_item.get("session_id") != "session-current":
        raise AssertionError(f"failure_review_is_scoped_to_session: missing scoped item: {state}")
    if state.get("pending", {}).get("pending_failure_review"):
        raise AssertionError(f"failure_review_is_scoped_to_session: legacy key unexpectedly written: {state}")
    print("failure_review_is_scoped_to_session: SCOPED")

    superseded_pending = {
        "pending_failure_review:session-new-failure": {
            "reason": "historical formal alternate succeeded",
            "failure_class": "SUPERSEDED_OPERATIONAL_FAILURE",
            "superseded_by": "formal-runtime-r2:verified-launcher",
            "resolution": "retained as historical evidence",
            "owner_scope": "session:session-new-failure",
            "session_id": "session-new-failure",
        }
    }
    new_failure_event = {
        "turn_id": "post_tool_new_failure_after_superseded",
        "session_id": "session-new-failure",
        "tool_name": "Bash",
        "tool_input": {"command": "python current_failure.py"},
        "tool_response": {"exit_code": 1, "output": "Exit code: 1"},
    }
    state, _stdout = run_post_tool_use(
        "new_failure_replaces_superseded_class",
        new_failure_event,
        superseded_pending,
    )
    new_item = state.get("pending", {}).get("pending_failure_review:session-new-failure")
    if not new_item or new_item.get("failure_class") != "CURRENT_TASK_TOOL_FAILURE":
        raise AssertionError(f"new_failure_replaces_superseded_class: {state}")
    if new_item.get("superseded_by") or new_item.get("resolution"):
        raise AssertionError(f"new_failure_replaces_superseded_class retained stale disposition: {new_item}")
    print("new_failure_replaces_superseded_class: CURRENT")

    commit_event = {
        "turn_id": "post_tool_s15_commit",
        "session_id": "session-commit",
        "tool_name": "Bash",
        "tool_input": {"command": "git commit -m 'test'"},
        "tool_response": {"exit_code": 0, "output": "Exit code: 0"},
    }
    state, stdout = run_post_tool_use("s15_commit_is_scoped", commit_event, {})
    scoped_s15 = state.get("pending", {}).get("pending_s15:session-commit")
    if not scoped_s15 or scoped_s15.get("session_id") != "session-commit":
        raise AssertionError(f"s15_commit_is_scoped: missing scoped S15 item: {state}")
    if state.get("pending", {}).get("pending_s15"):
        raise AssertionError(f"s15_commit_is_scoped: legacy S15 key unexpectedly written: {state}")
    if "session-scoped pending_s15 marked" not in stdout:
        raise AssertionError(f"s15_commit_is_scoped: missing scope note: {stdout}")
    print("s15_commit_is_scoped: SCOPED")

    no_remote_event = {
        "turn_id": "post_tool_s15_no_remote",
        "session_id": "session-commit",
        "tool_name": "Bash",
        "tool_input": {"command": "git remote -v"},
        "tool_response": {
            "exit_code": 0,
            "output": (
                "Exit code: 0\n"
                '{"hook_resolution":"s15_external_blocker","s15":"blocked",'
                '"remote_count":0}'
            ),
        },
    }
    state, stdout = run_post_tool_use(
        "s15_no_remote_receipt_clears_scoped_pending",
        no_remote_event,
        {"pending_s15:session-commit": scoped_s15},
    )
    if state.get("pending", {}).get("pending_s15:session-commit"):
        raise AssertionError(f"s15_no_remote_receipt_clears_scoped_pending: pending was not cleared: {state}")
    if "scoped no-remote blocker evidence" not in stdout:
        raise AssertionError(f"s15_no_remote_receipt_clears_scoped_pending: missing clear note: {stdout}")
    print("s15_no_remote_receipt_clears_scoped_pending: CLEARED")

    legacy_state = {"pending_s15": {"reason": "legacy global marker"}}
    state, stdout = run_post_tool_use("legacy_unscoped_s15_is_cleared", no_remote_event, legacy_state)
    if state.get("pending", {}).get("pending_s15"):
        raise AssertionError(f"legacy_unscoped_s15_is_cleared: legacy marker remains: {state}")
    if "legacy unscoped pending_s15 cleared" not in stdout:
        raise AssertionError(f"legacy_unscoped_s15_is_cleared: missing migration note: {stdout}")
    print("legacy_unscoped_s15_is_cleared: CLEARED")

    quoted_patch_event = {
        "turn_id": "post_tool_s15_quoted_patch",
        "session_id": "session-patch",
        "tool_name": "Bash",
        "tool_input": {
            "command": (
                'const patch = "*** Update File: hook.py\\n'
                '+ text = \\"git commit then git push permission\\"\\n"; '
                "await tools.apply_patch(patch);"
            )
        },
        "tool_response": {"exit_code": 0, "output": "Exit code: 0"},
    }
    state, stdout = run_post_tool_use("quoted_patch_does_not_mark_s15", quoted_patch_event, {})
    if any(key.startswith("pending_s15") for key in state.get("pending", {})):
        raise AssertionError(f"quoted_patch_does_not_mark_s15: false S15 pending: {state}")
    if "pending_s15 marked" in stdout or "git push permission failure" in stdout:
        raise AssertionError(f"quoted_patch_does_not_mark_s15: false audit note: {stdout}")
    print("quoted_patch_does_not_mark_s15: PASS")

    governed_write = {
        "turn_id": "post_tool_runner_scope_openclaw",
        "session_id": "post-tool-scope-session",
        "cwd": r"@@OPENCLAW_ROOT:win@@\projects\ctx02",
        "tool_name": "Write",
        "tool_input": {"file_path": r"@@OPENCLAW_ROOT:win@@\docs\ctx02-scope.md"},
        "tool_response": {"exit_code": 0, "output": "Exit code: 0"},
    }
    state, stdout = run_post_tool_use("runner_event_cwd_marks_openclaw_w9", governed_write, {})
    if not state.get("pending", {}).get("pending_w9:post-tool-scope-session"):
        raise AssertionError(f"runner_event_cwd_marks_openclaw_w9: scoped pending_w9 missing: {state}")
    if state.get("pending", {}).get("pending_w9"):
        raise AssertionError(f"runner_event_cwd_marks_openclaw_w9: global pending_w9 written: {state}")
    if "pending_w9 marked" not in stdout:
        raise AssertionError(f"runner_event_cwd_marks_openclaw_w9: missing scope note: {stdout}")
    print("runner_event_cwd_marks_openclaw_w9: PASS")

    foreign_w9 = {
        "pending_w9:session-a": {
            "reason": "session-a still owns this W9 review",
            "session_id": "session-a",
        }
    }
    foreign_gate_event = {
        "turn_id": "post_tool_foreign_w9_gate",
        "session_id": "session-b",
        "cwd": r"@@OPENCLAW_ROOT:win@@\projects\ctx02",
        "tool_name": "Bash",
        "tool_input": {
            "command": "powershell -File verify-governance-hard-gate.ps1 -GateProfile Advisory"
        },
        "tool_response": {
            "exit_code": 0,
            "output": "Exit code: 0\nGovernance Hard Gate Passed\nFail: 0",
        },
    }
    state, _stdout = run_post_tool_use(
        "foreign_session_cannot_clear_w9",
        foreign_gate_event,
        foreign_w9,
    )
    if not state.get("pending", {}).get("pending_w9:session-a"):
        raise AssertionError(f"foreign_session_cannot_clear_w9: session-a state was cleared: {state}")
    print("foreign_session_cannot_clear_w9: PRESERVED")

    turn_only_write = dict(governed_write)
    turn_only_write.pop("session_id")
    turn_only_write["turn_id"] = "turn-only-a"
    state, _stdout = run_post_tool_use("turn_only_w9_is_scoped", turn_only_write, {})
    if not state.get("pending", {}).get("pending_w9@turn:turn-only-a"):
        raise AssertionError(f"turn_only_w9_is_scoped: turn-owned state missing: {state}")
    print("turn_only_w9_is_scoped: SCOPED")

    turn_failure_event = {
        "turn_id": "turn-failure-a",
        "tool_name": "Bash",
        "tool_input": {"command": "python broken_turn_command.py"},
        "tool_response": {"exit_code": 1, "output": "Exit code: 1"},
    }
    state, _stdout = run_post_tool_use("turn_only_failure_review_is_scoped", turn_failure_event, {})
    scoped_failure = state.get("pending", {}).get("pending_failure_review@turn:turn-failure-a")
    if not scoped_failure or scoped_failure.get("turn_id") != "turn-failure-a":
        raise AssertionError(f"turn_only_failure_review_is_scoped: turn-owned state missing: {state}")
    print("turn_only_failure_review_is_scoped: SCOPED")

    foreign_turn_gate = dict(foreign_gate_event)
    foreign_turn_gate.pop("session_id")
    foreign_turn_gate["turn_id"] = "turn-only-b"
    state, _stdout = run_post_tool_use(
        "foreign_turn_cannot_clear_w9",
        foreign_turn_gate,
        {
            "pending_w9@turn:turn-only-a": {
                "reason": "turn-only-a still owns this W9 review",
                "turn_id": "turn-only-a",
            }
        },
    )
    if not state.get("pending", {}).get("pending_w9@turn:turn-only-a"):
        raise AssertionError(f"foreign_turn_cannot_clear_w9: turn-only-a state was cleared: {state}")
    print("foreign_turn_cannot_clear_w9: PRESERVED")

    nonmatching_write = dict(governed_write)
    nonmatching_write["turn_id"] = "post_tool_runner_scope_prefix_collision"
    nonmatching_write["cwd"] = r"@@OPENCLAW_ROOT:win@@-x"
    nonmatching_write["tool_input"] = {"file_path": r"@@OPENCLAW_ROOT:win@@-x\docs\ctx02-scope.md"}
    state, stdout = run_post_tool_use("runner_prefix_collision_skips_openclaw_w9", nonmatching_write, {})
    if state.get("pending", {}).get("pending_w9"):
        raise AssertionError(f"runner_prefix_collision_skips_openclaw_w9: false pending_w9: {state}")
    if "pending_w9 marked" in stdout:
        raise AssertionError(f"runner_prefix_collision_skips_openclaw_w9: false scope note: {stdout}")
    print("runner_prefix_collision_skips_openclaw_w9: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
