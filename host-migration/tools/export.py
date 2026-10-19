"""Export explicitly selected local host sources; never edit a live host.

The private source-layout file is supplied by the operator, never committed.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
import os
from pathlib import Path
import re
import subprocess
import tomllib
from model_portability import transform_adapter

from common import (HOSTS, PRIVATE_NAME, SKIP_DIRS, TEXT_SUFFIXES, is_reparse, safe_relative,
                    json_bytes, load_json, scan_secrets, secret_values, sha256,
                    strip_secrets, tokenize, toml_bytes, general_asset_sha256)

ROOT_FILES = ("AGENTS.md", "AGENTS.override.md", "CLAUDE.md", "birth-ceremony-protocol.md",
              "model_catalog.json", "keybindings.json", "policy-limits.json", "config.json")
HOST_DIRS = ("hooks", "rules", "contracts", "automation-tools", "commands", "agents", "prompts")


def git_head(root):
    return subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()


def export(sources: dict, package: Path):
    roots = {key: Path(value) for key, value in sources.items() if key not in ("bindings",)}
    general = roots["general"]
    publication = general / "control/host-capability-publication-manifest.yaml"
    selected = re.findall(r"^  - skill_id: (.+)$", publication.read_text(encoding="utf-8"), re.M)
    bindings = dict(sources.get("bindings", {}))
    bindings.update({"GENERAL_ROOT": str(general), "CODEX_HOME": str(roots["codex"]),
                     "CODEXPP_HOME": str(roots["codex_plus_plus"]), "CLAUDE_HOME": str(roots["claude_code"]),
                     "LAUNCHER_ROOT": str(roots["launcher"]), "SANITIZER_ROOT": str(roots["adapter"]),
                     "CODEXPP_SOURCE": str(roots["codexpp_source"]), "CODEXPP_RUNTIME": str(roots["codexpp_runtime"])})
    bindings["CODEXPP_SOURCE_PARENT"] = str(roots["codexpp_source"].parent)
    parsed = {}
    known = set()
    for host in HOSTS:
        for name in ("config.toml", "settings.json", "settings.local.json"):
            p = roots[host] / name
            if p.exists():
                obj = tomllib.loads(p.read_text(encoding="utf-8-sig")) if p.suffix == ".toml" else load_json(p)
                parsed[(host, name)] = obj
                known.update(secret_values(obj))
    runtime_config = roots["codexpp_runtime"] / "config.json"
    if runtime_config.exists():
        known.update(secret_values(load_json(runtime_config)))
    old_manifest = load_json(package / "manifest.json") if (package / "manifest.json").exists() else {"entries": []}
    entries, inventory, skills, redactions = [], [], [], []
    exclusions = Counter()
    refs = {}
    def reference(path):
        rel = path.relative_to(general).as_posix()
        refs[rel] = general_asset_sha256(path)
        return rel
    reference(publication)
    reference(general / "tooling/Sync-HostCapabilityProjection.ps1")
    tracked_general = subprocess.check_output(["git", "-C", str(general), "ls-files", "-z", "--", *["assets/skills/" + name for name in selected]], text=True).split("\0")
    for relative in tracked_general:
        if relative:
            reference(general / relative)

    def skip(label, reason):
        parts = label.split("/")
        scope = "/".join(parts[:3]) if len(parts) > 2 and parts[1] == "skills" else parts[0]
        exclusions[(scope, reason)] += 1

    def add(path, label, component, target, relative, host=None, review=False, data=None, changes=None):
        original = path.read_bytes()
        blob = original if data is None else data
        text = None
        if path.suffix.lower() in TEXT_SUFFIXES or data is not None or path.name in ("LICENSE", ".gitignore"):
            try:
                text = blob.decode("utf-8-sig")
            except UnicodeDecodeError:
                raise ValueError(f"Non UTF-8 text source requires review: {label}")
            if scan_secrets(text, known):
                if review:
                    skip(label, "private_value_detected_in_review_only_source")
                    return
                raise ValueError(f"Potential credential in selected source (value withheld): {label}")
            changes = list(changes or [])
            text, adapter_changes = transform_adapter(label, text, bindings["POWERSHELL_EXE"])
            changes.extend(adapter_changes)
            if label == "codex/AGENTS.md":
                retired = str(Path(bindings["USERPROFILE"]) / "AppData/Roaming/CodexPlusPlusProfile/.codex")
                if retired in text:
                    text = text.replace(retired, str(roots["codex_plus_plus"]))
                    changes.append("point ordinary L0 at the actual isolated Codex++ home")
            if label.endswith("/archive_codexplusplus_threads.py"):
                before = 'store.glob("OpenAI.Codex_*\\app\\resources\\codex.exe")'
                if before in text:
                    text = text.replace(before, 'store.glob("OpenAI.Codex_*/app/resources/codex.exe")')
                    changes.append("use forward slash glob separators; avoid Python string escape corruption")
            text = tokenize(text.replace("\r\n", "\n"), bindings)
            blob = text.encode("utf-8")
        bucket = "review-only" if review else "payload"
        out = package / bucket / component / relative
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(blob)
        entry = {"source": label, "source_sha256": sha256(original), "path": out.relative_to(package).as_posix(),
                 "sha256": sha256(blob), "bytes": len(blob), "component": component,
                 "host": host, "installable": not review, "target_root": target,
                 "target_path": relative, "template": text is not None,
                 "changes": changes or []}
        entries.append(entry)
        inventory.append({"source": label, "disposition": "review_only" if review else "packaged", "package_path": entry["path"]})

    def tree(root, label, component, target, prefix="", host=None, review=False, compare=None):
        if not root.exists():
            return
        for base, dirs, files in os.walk(root, followlinks=False):
            base = Path(base)
            keep = []
            for name in sorted(dirs):
                p = base / name
                rel = p.relative_to(root).as_posix()
                # Source code only; dependency trees and generated runtime are reconstructed.
                if compare and name == "config":
                    skip(label + "/" + rel, "business_connector_configuration_private_transfer")
                elif name in SKIP_DIRS or name in ("evidence", ".harness", "test_quarantined_sessions", "reports") or PRIVATE_NAME.search(name) or name.startswith((".git", ".pytest", "pre-native", "upgrade-baselines")) or is_reparse(p):
                    skip(label + "/" + rel, "generated_private_or_external_directory")
                elif rel.startswith("packages/installer/assets/runtime"):
                    skip(label + "/" + rel, "rebuilt_by_codexpp_installer")
                else:
                    keep.append(name)
            dirs[:] = keep
            for name in sorted(files):
                p = base / name
                rel = p.relative_to(root)
                source = label + "/" + rel.as_posix()
                if PRIVATE_NAME.search(name):
                    skip(source, "private_state_credential_or_backup")
                elif name.startswith(".") and name not in (".gitignore",):
                    skip(source, "local_tool_state")
                elif p.suffix.lower() not in TEXT_SUFFIXES and p.suffix.lower() not in (".png", ".jpg", ".jpeg", ".webp", ".gif", ".ico", ".woff", ".woff2") and name != "LICENSE":
                    skip(source, "binary_or_unselected_file_type")
                elif p.stat().st_size > 10 * 1024 * 1024:
                    raise ValueError(f"Oversized source requires review: {source}")
                elif compare and (compare / rel).is_file() and p.read_bytes() == (compare / rel).read_bytes():
                    reference(compare / rel)
                    inventory.append({"source": source, "disposition": "general_canonical_reference", "general_path": (compare / rel).relative_to(general).as_posix()})
                else:
                    add(p, source, component, target, (Path(prefix) / rel).as_posix(), host, review)

    for host in HOSTS:
        root = roots[host]
        target = {"codex": "CODEX_HOME", "codex_plus_plus": "CODEXPP_HOME", "claude_code": "CLAUDE_HOME"}[host]
        for name in ROOT_FILES:
            p = root / name
            if p.exists():
                add(p, f"{host}/{name}", host, target, name, host)
        for directory in HOST_DIRS:
            tree(root / directory, f"{host}/{directory}", host, target, directory, host)
        for extra_prompt in sorted(root.glob("gpt*.md")):
            if extra_prompt.name != Path(parsed.get((host, "config.toml"), {}).get("model_instructions_file", "")).name:
                add(extra_prompt, f"{host}/unbound-model-instructions/{extra_prompt.name}", host, target, "model-instructions/" + extra_prompt.name + ".txt", host, review=True)
        p = root / "hooks.json"
        if p.exists():
            # Quote the interpreter and script paths; new usernames may contain spaces.
            obj = load_json(p)
            for groups in obj["hooks"].values():
                for group in groups:
                    for hook in group.get("hooks", []):
                        cmd = hook.get("command", "")
                        py = re.search(r"^(.+?python\.exe) (.+?\.py)(.*)$", cmd, re.I)
                        if py:
                            cmd = '"' + py[1] + '" "' + py[2] + '"' + py[3]
                            cmd = re.sub(r"--script (.+?\.py)(?= |$)", lambda m: '--script "' + m[1] + '"', cmd)
                            hook["command"] = cmd
            add(p, f"{host}/hooks.json", host, target, "hooks.json", host, data=json_bytes(obj), changes=["quote executable/script paths"])
        for name in ("config.toml", "settings.json", "settings.local.json"):
            if (host, name) not in parsed:
                continue
            obj = parsed[(host, name)]
            removed = []
            clean = strip_secrets(obj, removed)
            if name == "config.toml":
                for key in ("projects", "notify", "marketplaces", "hooks", "shell_environment_policy"):
                    if key in clean:
                        clean.pop(key)
                        removed.append(key + " (machine-generated or project-local)")
                servers = clean.get("mcp_servers", {})
                if "node_repl" in servers:
                    servers.pop("node_repl")
                    removed.append("mcp_servers.node_repl (native runtime regenerates)")
                if "model_instructions_file" in clean:
                    prompt_ref = clean.pop("model_instructions_file")
                    prompt = (root / prompt_ref).resolve()
                    if not prompt.is_file() or not prompt.is_relative_to(root.resolve()):
                        raise ValueError("Bound prompt must exist inside its explicit host root")
                    add(prompt, f"{host}/bound-model-instructions", host, target, "model-instructions/" + prompt.name + ".txt", host, review=True)
                    removed.append("model_instructions_file (archived for independent review, not enabled)")
                for provider_id, provider in clean.get("model_providers", {}).items():
                    if provider.get("base_url", "").startswith("http://127.0.0.1"):
                        provider["env_key"] = "CODEXPP_GATEWAY_TOKEN"
                    original_provider = obj.get("model_providers", {}).get(provider_id, {})
                    for header in original_provider.get("http_headers", {}):
                        from common import SECRET_KEY
                        if SECRET_KEY.search(header):
                            variable = "CODEXPP_ACTOR_AUTHORIZATION" if header.lower() == "x-openai-actor-authorization" else "CODEXPP_HEADER_" + re.sub(r"[^A-Z0-9]", "_", header.upper())
                            provider.setdefault("env_http_headers", {})[header] = variable
                            removed.append("externalize header " + header + " via " + variable)
                data = toml_bytes(clean)
                tomllib.loads(data.decode("utf-8"))
            else:
                clean.pop("$schema", None)
                if name == "settings.local.json":
                    clean.get("permissions", {}).pop("allow", None)
                    removed.append("permissions.allow (one-task command approvals)")
                data = json_bytes(clean)
            redactions.append({"source": host + "/" + name, "removed_fields": removed})
            add(root / name, f"{host}/{name}", host, target, name, host, data=data, changes=removed)
        for skill in sorted((root / "skills").iterdir()):
            if not skill.is_dir():
                continue
            if skill.name == ".system":
                skills.append({"host": host, "name": skill.name, "mode": "host_bundled_reinstall"})
                continue
            canonical = general / "assets/skills" / skill.name
            if (canonical / "SKILL.md").exists():
                mode = "general_manifest_projection" if skill.name in selected else "general_canonical_on_demand"
                skills.append({"host": host, "name": skill.name, "mode": mode, "general_path": reference(canonical / "SKILL.md")})
                if not is_reparse(skill):
                    tree(skill, f"{host}/skills/{skill.name}", host, target, "skills/" + skill.name, host, review=True, compare=canonical)
            else:
                skills.append({"host": host, "name": skill.name, "mode": "host_local_payload"})
                tree(skill, f"{host}/skills/{skill.name}", host, target, "skills/" + skill.name, host)
        # Describe private surfaces without reading their bytes or hashing credentials.
        for name in ("auth.json", ".credentials.json", "sessions", "memories", "automations", "state_5.sqlite", "MEMORY.md", "history.jsonl"):
            if (root / name).exists():
                skip(f"{host}/{name}", "private_transfer_or_recreate_on_target")

    normal_start = roots["codex"] / "Start-Codex.ps1"
    text = normal_start.read_text(encoding="utf-8-sig")
    text = re.sub(r'^\$env:HOMEDRIVE = .*$', "$env:HOMEDRIVE = [IO.Path]::GetPathRoot($realProfile).TrimEnd('\\')", text, flags=re.M)
    text = re.sub(r'^\$env:HOMEPATH = .*$', "$env:HOMEPATH = $realProfile.Substring($env:HOMEDRIVE.Length)", text, flags=re.M)
    text = text.replace("-HostId codex -Mode Apply", "-HostId codex -SkillsRoot (Join-Path $env:CODEX_HOME 'skills') -Mode Apply")
    add(normal_start, "codex/Start-Codex.ps1", "codex", "CODEX_HOME", "Start-Codex.ps1", "codex", data=text.encode("utf-8"), changes=["derive home drive/path", "pass explicit ordinary SkillsRoot"])
    tree(roots["launcher"], "launcher", "launcher", "LAUNCHER_ROOT")
    tree(roots["adapter"], "adapter", "adapter", "SANITIZER_ROOT")
    if "ccs" in roots:
        for directory in ("mcp", "hooks"):
            tree(roots["ccs"] / directory, "ccs/" + directory, "ccs_mcp", "CCS_ROOT", directory)
    if "claude_user_config" in roots:
        p = roots["claude_user_config"]
        raw = load_json(p).get("mcpServers", {})
        known.update(secret_values(raw))
        removed = []
        clean = strip_secrets(raw, removed)
        add(p, "claude_user_config/mcpServers", "claude_code", "CLAUDE_HOME", "mcp-servers.json", "claude_code", data=json_bytes(clean), changes=["extract only MCP definitions; omit identity, projects and runtime"] + removed)
        redactions.append({"source": "claude_user_config/mcpServers", "removed_fields": removed})
    tree(roots["codexpp_source"], "codexpp_source", "codexpp_source", "CODEXPP_SOURCE")
    tree(roots["codexpp_runtime"] / "tweaks", "codexpp_tweaks", "codexpp_tweaks", "CODEXPP_RUNTIME", "tweaks")
    if runtime_config.exists():
        removed = []
        clean = strip_secrets(load_json(runtime_config), removed)
        add(runtime_config, "codexpp_runtime/config.json", "codexpp_tweaks", "CODEXPP_RUNTIME", "config.json", data=json_bytes(clean), changes=removed)
        redactions.append({"source": "codexpp_runtime/config.json", "removed_fields": removed})
    managed = roots["claude_managed"]
    obj = load_json(managed)
    for groups in obj.get("hooks", {}).values():
        for group in groups:
            for hook in group.get("hooks", []):
                cmd = hook.get("command", "")
                match = re.search(r"^(.+?python\.exe) (.+?\.py)(.*)$", cmd, re.I)
                if match:
                    cmd = '"' + match[1] + '" "' + match[2] + '"' + match[3]
                    cmd = re.sub(r"--script (.+?\.py)(?= |$)", lambda m: '--script "' + m[1] + '"', cmd)
                    hook["command"] = cmd
    add(managed, "claude_managed/managed-settings.json", "claude_managed", "CLAUDE_MANAGED", "managed-settings.json", "claude_code", data=json_bytes(obj), changes=["quote executable/script paths"])

    inventory.extend({"source": source, "disposition": "excluded", "reason": reason, "count": count}
                     for (source, reason), count in sorted(exclusions.items()))
    for entry in entries:
        if entry["template"] and scan_secrets((package / entry["path"]).read_text(encoding="utf-8"), known):
            raise ValueError("Potential credential in final export (value withheld): " + entry["path"])
    manifest = {"schema_version": "host-migration.v1", "snapshot_date": "2026-10-19", "hosts": list(HOSTS),
                "general": {"repository": "https://github.com/genius-jie/prompt_Knowledge.git", "commit": git_head(general), "file_hash_mode": "utf8-text-lf-equivalent_binary-exact", "files": refs, "selected_skills": selected},
                "upstream": {"codex_plus_plus": "https://github.com/b-nnett/codex-plusplus", "source_snapshot": "codexpp_source; includes local compatibility changes; MIT license retained"},
                "entries": sorted(entries, key=lambda x: x["path"]), "skills": skills,
                "redactions": redactions, "inventory": sorted(inventory, key=lambda x: x["source"])}
    (package / "manifest.json").write_bytes(json_bytes(manifest))
    current = {e["path"] for e in entries}
    for old in old_manifest["entries"]:
        if old["path"] not in current:
            rel = safe_relative(old["path"])
            if rel.parts[0] not in ("payload", "review-only"):
                raise ValueError("Old manifest tried to delete outside generated payload")
            obsolete = package / rel
            if obsolete.is_file() and not is_reparse(obsolete):
                obsolete.unlink()
    summary = Counter(x["disposition"] for x in inventory)
    print(json.dumps({"entries": len(entries), "bytes": sum(e["bytes"] for e in entries), "inventory": summary, "general_commit": manifest["general"]["commit"]}, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sources", required=True, type=Path)
    parser.add_argument("--package", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    export(load_json(args.sources), args.package.resolve())
