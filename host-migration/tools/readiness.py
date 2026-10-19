"""Target-local readiness; distinguish saved configuration from actual Hook smoke."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import tomllib

from common import HOSTS, fs_path, is_reparse, load_json, render
from restore import PACKAGE, HOST_ROOTS, bindings_from_layout, verify


def readiness(bindings, hosts, smoke=False):
    results = []
    python = Path(bindings["PYTHON_EXE"])
    powershell = Path(bindings["POWERSHELL_EXE"])
    for host in hosts:
        root = Path(bindings[HOST_ROOTS[host]])
        config = root / ("settings.json" if host == "claude_code" else "config.toml")
        prompt = root / ("CLAUDE.md" if host == "claude_code" else "AGENTS.md")
        registration = (Path(bindings["CLAUDE_MANAGED"]) / "managed-settings.json") if host == "claude_code" else root / "hooks.json"
        missing = []
        for label, path in (("configuration", config), ("global_prompt", prompt), ("hook_registration", registration), ("python", python), ("powershell7", powershell)):
            if not fs_path(path).is_file():
                missing.append(label)
        if is_reparse(root):
            missing.append("physical_host_root")
        if fs_path(config).is_file():
            if host == "claude_code":
                load_json(config)
            else:
                tomllib.loads(config.read_text(encoding="utf-8-sig"))
        hook_status = "not_run"
        if smoke and not missing:
            obj = load_json(registration)
            hooks = [item for group in obj.get("hooks", {}).get("SessionStart", []) for item in group.get("hooks", [])]
            if not hooks:
                missing.append("registered_session_start")
            else:
                # Only run this package's restored Hook command chain. Never execute
                # an unrelated machine/enterprise hook found in an existing config.
                relative = "payload/claude_managed/managed-settings.json" if host == "claude_code" else "payload/" + host + "/hooks.json"
                expected = json.loads(render((PACKAGE / relative).read_text(encoding="utf-8"), bindings))
                expected_hooks = [item for group in expected["hooks"]["SessionStart"] for item in group["hooks"]]
                if [h.get("command") for h in hooks] != [h.get("command") for h in expected_hooks]:
                    missing.append("hook_owner_mismatch")
                else:
                    with tempfile.TemporaryDirectory(prefix="host-migration-hook-smoke-") as scratch:
                        cwd = Path(scratch)
                        (cwd / "AGENTS.md").write_text("Migration smoke fixture.\n", encoding="utf-8")
                        env = dict(os.environ, CODEX_HOME=str(root), USERPROFILE=bindings["USERPROFILE"], HOME=bindings["USERPROFILE"], CLAUDE_CONFIG_DIR=bindings["CLAUDE_HOME"], CODEX_HOOK_CALLER_CWD=str(cwd))
                        contexts = []
                        for hook in hooks:
                            proc = subprocess.run(hook["command"], input=json.dumps({"cwd": str(cwd), "session_id": "host-migration-smoke", "hook_event_name": "SessionStart"}), cwd=cwd, env=env, capture_output=True, text=True, encoding="utf-8", timeout=40)
                            if proc.returncode:
                                missing.append("session_start_exit_nonzero")
                            for line in proc.stdout.splitlines():
                                if line.startswith("{"):
                                    context = json.loads(line).get("hookSpecificOutput", {}).get("additionalContext", "")
                                    if context.startswith("[HOST_SCOPE_FACT]\n"):
                                        contexts.append(json.loads(context.split("\n", 1)[1]))
                        if not contexts:
                            missing.append("session_start_scope_fact")
                        else:
                            refs = contexts[-1].get("l0_source_refs", {})
                            if not any(str(root).casefold() in str(v).casefold() for v in refs.values()):
                                missing.append("session_start_host_binding")
                    hook_status = "passed" if not missing else "failed"
        results.append({"host": host, "configuration_complete": not missing, "missing": missing,
                        "session_start_smoke": hook_status, "account_login_and_model_call": "requires_target_host_verification"})
    return {"hosts": results, "configuration_ready": all(not x["missing"] for x in results),
            "native_desktop_acceptance": "not_established_by_this_command"}


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--layout", type=Path, required=True)
    p.add_argument("--hosts", default=",".join(HOSTS))
    p.add_argument("--smoke-hooks", action="store_true")
    args = p.parse_args()
    verify()
    hosts = tuple(x for x in args.hosts.split(",") if x)
    if not hosts or set(hosts) - set(HOSTS):
        p.error("unknown host")
    layout = json.load(sys.stdin) if str(args.layout) == "-" else load_json(args.layout)
    result = readiness(bindings_from_layout(layout), hosts, args.smoke_hooks)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0 if result["configuration_ready"] else 2)
