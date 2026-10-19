"""Regression contract for the retired UserPromptSubmit Context hook.

The obsolete script is absent. These tests prove that no active configured
route invokes it or revives its continuation-state mechanism.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path


HOOK_DIR = Path(__file__).resolve().parents[1]
CODEX_CONFIG = HOOK_DIR.parent / "hooks.json"
RETIRED_SCRIPT = HOOK_DIR / "user_prompt_submit_w1_gate.py"
LEGACY_STATE_NAME = "openclaw-mono-pending.json"


def configured_commands() -> list[str]:
    config = json.loads(CODEX_CONFIG.read_text(encoding="utf-8"))
    commands: list[str] = []
    for entries in (config.get("hooks") or {}).values():
        for entry in entries or []:
            for hook in entry.get("hooks") or []:
                if hook.get("type") == "command":
                    commands.append(str(hook.get("command") or ""))
    return commands


def configured_script_paths() -> list[Path]:
    paths: list[Path] = []
    for command in configured_commands():
        match = re.search(r"--script\s+(\S+)", command)
        if match:
            paths.append(Path(match.group(1).strip('"')))
        elif "w11_interrupt_trace.py" in command:
            paths.append(HOOK_DIR / "w11_interrupt_trace.py")
    return paths


def session_start_command() -> str:
    config = json.loads(CODEX_CONFIG.read_text(encoding="utf-8"))
    for entry in config.get("hooks", {}).get("SessionStart", []):
        for hook in entry.get("hooks", []):
            if hook.get("type") == "command":
                return str(hook.get("command") or "")
    raise AssertionError("SessionStart command is not configured")


def state_digest(path: Path) -> tuple[int, int, str]:
    stat = path.stat()
    return stat.st_mtime_ns, stat.st_size, hashlib.sha256(path.read_bytes()).hexdigest()


def test_retired_user_prompt_hook_is_absent_and_unconfigured() -> None:
    config = json.loads(CODEX_CONFIG.read_text(encoding="utf-8"))
    assert "UserPromptSubmit" not in config.get("hooks", {})
    surface = json.dumps(config, ensure_ascii=False)
    assert "user_prompt_submit_w1_gate.py" not in surface
    assert not RETIRED_SCRIPT.exists(), "retired script must not remain on the Host catalog"


def test_active_hook_sources_do_not_read_or_write_legacy_continuation_state() -> None:
    forbidden = (
        "user_prompt_submit_w1_gate.py",
        "SESSION_CONTINUATION_STATE_KEY",
        "persist_session_continuation_receipt",
        "OPENCLAW_W1_PRETHINK_REQUIRED",
    )
    paths = configured_script_paths()
    assert paths, "expected active configured hook scripts"
    assert RETIRED_SCRIPT not in paths
    for path in paths:
        assert path.is_file(), f"configured script is missing: {path}"
        source = path.read_text(encoding="utf-8")
        for marker in forbidden:
            assert marker not in source, f"active script {path} still consumes legacy UserPrompt state: {marker}"


def test_repeated_complex_ordinary_session_start_keeps_historical_state_unchanged() -> None:
    """No UserPrompt route plus repeated complex input must leave history untouched."""
    command = session_start_command()
    complex_event = {
        "turn_id": "ctx02-retired-user-prompt",
        "session_id": "ctx02-retired-user-prompt-session",
        "cwd": r"C:\ctx02-ordinary-project",
        "source": "startup",
        "prompt": "继续推进复杂跨域架构治理并执行完整工作流",
    }
    with tempfile.TemporaryDirectory(prefix="ctx02-retired-home-") as home_raw:
        home = Path(home_raw)
        state_path = home / "hook-state" / LEGACY_STATE_NAME
        state_path.parent.mkdir(parents=True)
        state_path.write_text(
            json.dumps(
                {
                    "pending": {},
                    "session_continuations": {"historical": {"mode": "REUSE", "scope": 1}},
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        before = state_digest(state_path)
        env = os.environ.copy()
        env["CODEX_HOME"] = str(home)
        env["PYTHONPATH"] = str(HOOK_DIR)
        for _ in range(2):
            proc = subprocess.run(
                command,
                input=json.dumps(complex_event, ensure_ascii=False),
                text=True,
                capture_output=True,
                cwd=str(HOOK_DIR),
                env=env,
                shell=True,
                timeout=30,
                check=False,
            )
            assert proc.returncode == 0, proc.stderr
            assert "[HOOK:ERROR_DOWNGRADED]" not in proc.stdout
        assert state_digest(state_path) == before
