"""Verify, preview and restore selected hosts. Python 3.11+, standard library only."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tomllib

from common import (HOSTS, TOKEN, assert_physical_chain, below, canonical, fs_path, is_reparse,
                    json_bytes, load_json, render, safe_relative, scan_secrets,
                    sha256, write_new, general_asset_sha256)

PACKAGE = Path(__file__).resolve().parents[1]
HOST_ROOTS = {"codex": "CODEX_HOME", "codex_plus_plus": "CODEXPP_HOME", "claude_code": "CLAUDE_HOME"}
SUPPORT_ROOTS = {"launcher": "LAUNCHER_ROOT", "adapter": "SANITIZER_ROOT", "ccs_mcp": "CCS_ROOT", "codexpp_source": "CODEXPP_SOURCE", "codexpp_tweaks": "CODEXPP_RUNTIME", "claude_managed": "CLAUDE_MANAGED"}


def bindings_from_layout(layout: dict, package=PACKAGE):
    required = ("user_profile", "codexpp_profile", "general_root", "python_exe", "powershell_exe", "program_files", "system_root", "node_exe", "suite_root", "core_root", "testing_root", "openclaw_root", "codexpp_source")
    for key in required:
        if not layout.get(key) or not Path(layout[key]).is_absolute():
            raise ValueError(f"Layout requires an absolute path: {key}")
        if any(c in str(layout[key]) for c in "\"'`%!\n\r"):
            raise ValueError(f"Path contains characters unsupported by the archived launch scripts: {key}")
    user = Path(layout["user_profile"])
    pp = Path(layout["codexpp_profile"])
    result = {"USERPROFILE": str(user), "CODEX_HOME": str(user / ".codex"),
              "CLAUDE_HOME": str(user / ".claude"), "CODEXPP_PROFILE": str(pp),
              "CODEXPP_HOME": str(pp / "AppData/Roaming/Codex/.codex"),
              "CODEXPP_RUNTIME": str(pp / "AppData/Roaming/codex-plusplus"),
              "CODEXPP_INSTALL_ROOT": str(user / "AppData/Local/codex-plusplus"),
              "LAUNCHER_ROOT": str(user / ".codex-plusplus-config"),
              "SANITIZER_ROOT": str(user / ".cc-switch/sanitizer"),
              "CCS_ROOT": str(user / ".ccs"),
              "CLAUDE_MANAGED": str(Path(layout["program_files"]) / "ClaudeCode"),
              "PROFILE_REPO": str(package.parent)}
    for key in required:
        if key not in ("user_profile", "codexpp_profile", "program_files", "system_root"):
            result[key.upper()] = str(Path(layout[key]))
    result["PROGRAMFILES"] = str(Path(layout["program_files"]))
    result["SYSTEMROOT"] = str(Path(layout["system_root"]))
    result["CODEX_PYTHON_EXE"] = result["PYTHON_EXE"]
    result["CODEXPP_SOURCE_PARENT"] = str(Path(result["CODEXPP_SOURCE"]).parent)
    if Path(result["CODEXPP_SOURCE"]).name.casefold() != "source" or below(Path(result["CODEXPP_SOURCE"]), pp):
        raise ValueError("Codex++ installer source must end in 'source' and stay outside its mutable profile")
    homes = [Path(result[key]) for key in HOST_ROOTS.values()]
    for i, home in enumerate(homes):
        for other in homes[i+1:]:
            if below(home, other) or below(other, home):
                raise ValueError("Host homes must not overlap")
    if below(pp, user / ".codex") or below(pp, user / ".claude"):
        raise ValueError("Codex++ profile must be separate from ordinary host homes")
    # The source clone, product config, runtime and application mirror are distinct.
    isolated = [Path(result[key]) for key in (*HOST_ROOTS.values(), "LAUNCHER_ROOT", "SANITIZER_ROOT", "CCS_ROOT", "CODEXPP_SOURCE", "GENERAL_ROOT", "PROFILE_REPO")]
    for i, root in enumerate(isolated):
        for other in isolated[i+1:]:
            if below(root, other) or below(other, root):
                raise ValueError("Source and restore roots must not overlap: " + str(root))
    return result


def verify(package=PACKAGE, sealed=True):
    manifest = load_json(package / "manifest.json")
    if manifest.get("schema_version") != "host-migration.v1" or manifest.get("hosts") != list(HOSTS):
        raise ValueError("Unknown or incomplete host manifest")
    seen = set()
    for entry in manifest["entries"]:
        rel = safe_relative(entry["path"])
        path = package / rel
        if entry["path"] in seen or not below(path, package) or is_reparse(path):
            raise ValueError("Duplicate or unsafe package entry")
        seen.add(entry["path"])
        blob = path.read_bytes()
        if sha256(blob) != entry["sha256"] or len(blob) != entry["bytes"]:
            raise ValueError("Payload checksum mismatch: " + entry["path"])
        if entry["installable"]:
            expected = HOST_ROOTS.get(entry["component"], SUPPORT_ROOTS.get(entry["component"]))
            if not expected or expected != entry["target_root"] or rel.parts[0] != "payload":
                raise ValueError("Component target boundary violation")
        elif rel.parts[0] != "review-only":
            raise ValueError("Review-only data has an invalid location")
        safe_relative(entry["target_path"])
        if entry["template"] and scan_secrets(blob.decode("utf-8")):
            raise ValueError("Potential secret in payload: " + entry["path"])
    actual = {p.relative_to(package).as_posix() for d in ("payload", "review-only") for p in (package / d).rglob("*") if p.is_file()}
    if actual != seen:
        raise ValueError("Unlisted or missing payload files")
    if sealed:
        sums = load_json(package / "checksums.json")
        for relative, expected in sums.items():
            path = package / safe_relative(relative)
            if is_reparse(path) or sha256(path.read_bytes()) != expected:
                raise ValueError("Package checksum mismatch: " + relative)
        current = package_files(package)
        if current != set(sums):
            raise ValueError("Unsealed package file")
    return manifest


def package_files(package):
    return {p.relative_to(package).as_posix() for p in package.rglob("*") if p.is_file()
            and p.name != "checksums.json" and "__pycache__" not in p.parts
            and not any(x.startswith(".host-migration-") for x in p.parts)
            and "evidence" not in p.relative_to(package).parts}


def seal(package=PACKAGE):
    verify(package, sealed=False)
    sums = {name: sha256((package / name).read_bytes()) for name in sorted(package_files(package))}
    (package / "checksums.json").write_bytes(json_bytes(sums))
    return {"sealed_files": len(sums), "checksums_sha256": sha256((package / "checksums.json").read_bytes())}


def general_check(manifest, bindings):
    root = Path(bindings["GENERAL_ROOT"])
    for relative, expected in manifest["general"]["files"].items():
        path = root / safe_relative(relative)
        if not path.is_file() or general_asset_sha256(path) != expected:
            raise ValueError("General asset differs from the pinned package: " + relative)


def plan(manifest, bindings, hosts=HOSTS, support=(), managed=False, package=PACKAGE):
    general_check(manifest, bindings)
    operations = []
    for entry in manifest["entries"]:
        if not entry["installable"]:
            continue
        component = entry["component"]
        if component in HOSTS:
            if component not in hosts:
                continue
        elif component == "claude_managed":
            if not managed or "claude_code" not in hosts:
                continue
        elif component not in support:
            continue
        root = Path(bindings[entry["target_root"]])
        target = root / safe_relative(entry["target_path"])
        assert_physical_chain(target)
        if not below(target, root):
            raise ValueError("Target escaped its root")
        data = (package / entry["path"]).read_bytes()
        if entry["template"]:
            data = render(data.decode("utf-8"), bindings).encode("utf-8")
        if target.suffix == ".toml":
            tomllib.loads(data.decode("utf-8"))
        if target.suffix == ".json":
            json.loads(data)
        native_target = fs_path(target)
        status = "create" if not native_target.exists() else ("identical" if native_target.is_file() and native_target.read_bytes() == data else "collision")
        operations.append({"kind": "file", "host": entry["host"], "component": component,
                           "target": str(target), "source": entry["path"], "sha256": sha256(data), "status": status})
    for host in hosts:
        for name in manifest["general"]["selected_skills"]:
            source = Path(bindings["GENERAL_ROOT"]) / "assets/skills" / name
            target = Path(bindings[HOST_ROOTS[host]]) / "skills" / name
            assert_physical_chain(target.parent)
            if not fs_path(target).exists() and not is_reparse(target):
                status = "create"
            elif is_reparse(target) and canonical(target) == canonical(source):
                status = "identical"
            else:
                status = "collision"
            operations.append({"kind": "junction", "host": host, "component": host,
                               "target": str(target), "source": str(source), "status": status})
    targets = [os.path.normcase(x["target"]) for x in operations]
    if len(targets) != len(set(targets)):
        raise ValueError("Duplicate restore target")
    return operations


def save_receipt(path, receipt):
    # This target-local restore/rollback receipt is not task, OS or scheduler state.
    temp = path.with_name(path.name + ".partial")
    temp.write_bytes(json_bytes(receipt))
    os.replace(temp, path)


def apply(manifest, bindings, operations, receipt_path, hosts=HOSTS, package=PACKAGE):
    if any(x["status"] == "collision" for x in operations):
        raise ValueError("Collision detected; no file was written")
    assert_physical_chain(receipt_path)
    if receipt_path.exists():
        raise ValueError("Use a new receipt path; an existing receipt is never overwritten")
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt = {"schema_version": "host-migration-restore.v1", "package_manifest_sha256": sha256((package / "manifest.json").read_bytes()),
               "allowed_roots": sorted({str(Path(bindings[x])) for x in (*HOST_ROOTS.values(), *SUPPORT_ROOTS.values())}),
               "created": [], "created_dirs": [], "status": "in_progress"}
    write_new(receipt_path, json_bytes(receipt))
    try:
        for operation in operations:
            if operation["status"] != "create" or operation["kind"] != "file":
                continue
            target = Path(operation["target"])
            assert_physical_chain(target)
            for directory in reversed((target.parent, *target.parent.parents)):
                if not fs_path(directory).exists():
                    fs_path(directory).mkdir()
                    receipt["created_dirs"].append(str(directory))
                    save_receipt(receipt_path, receipt)
            data = (package / operation["source"]).read_bytes()
            entry = next(e for e in manifest["entries"] if e["path"] == operation["source"])
            if entry["template"]:
                data = render(data.decode("utf-8"), bindings).encode("utf-8")
            if sha256(data) != operation["sha256"]:
                raise ValueError("Plan is stale")
            write_new(target, data)
            receipt["created"].append(operation)
            save_receipt(receipt_path, receipt)
        for host in hosts:
            junctions = [x for x in operations if x["kind"] == "junction" and x["host"] == host and x["status"] == "create"]
            if not junctions:
                continue
            writer = Path(bindings["GENERAL_ROOT"]) / "tooling/Sync-HostCapabilityProjection.ps1"
            skills = Path(bindings[HOST_ROOTS[host]]) / "skills"
            proc = subprocess.run([bindings["POWERSHELL_EXE"], "-NoLogo", "-NoProfile", "-NonInteractive", "-File", str(writer),
                                   "-HostId", host, "-SkillsRoot", str(skills), "-Mode", "Apply"], capture_output=True, text=True, encoding="utf-8", errors="replace")
            # Record even a partial native writer outcome so rollback remains possible.
            for operation in junctions:
                target = Path(operation["target"])
                if is_reparse(target) and canonical(target) == canonical(Path(operation["source"])):
                    receipt["created"].append(operation)
            save_receipt(receipt_path, receipt)
            if proc.returncode:
                raise ValueError("General projection writer reported a collision or failure")
        receipt["status"] = "applied"
    except BaseException:
        receipt["status"] = "failed_preserved_for_rollback"
        raise
    finally:
        save_receipt(receipt_path, receipt)
    return receipt


def rollback(receipt_path):
    receipt = load_json(receipt_path)
    if receipt.get("schema_version") != "host-migration-restore.v1":
        raise ValueError("Unknown restore receipt")
    allowed = [Path(x) for x in receipt["allowed_roots"]]
    for operation in reversed(receipt["created"]):
        target = Path(operation["target"])
        if not any(below(target.parent, root) for root in allowed):
            raise ValueError("Receipt target is outside its allowed restore roots")
        assert_physical_chain(target.parent)
        if operation["kind"] == "junction":
            if is_reparse(target):
                if canonical(target) != canonical(Path(operation["source"])):
                    raise ValueError("Changed junction retained")
                fs_path(target).rmdir()  # junction only; never recurse into its source
            elif fs_path(target).exists():
                raise ValueError("Changed target retained")
        elif fs_path(target).exists():
            if is_reparse(target) or sha256(fs_path(target).read_bytes()) != operation["sha256"]:
                raise ValueError("Changed file retained: " + str(target))
            fs_path(target).unlink()
    for name in reversed(receipt["created_dirs"]):
        path = Path(name)
        if not any(below(path, root) or below(root, path) for root in allowed):
            raise ValueError("Receipt directory is outside restore ancestry")
        assert_physical_chain(path)
        if fs_path(path).exists() and not is_reparse(path):
            try:
                fs_path(path).rmdir()  # only empty directories created by this restore
            except OSError:
                pass
    receipt["status"] = "rolled_back"
    save_receipt(receipt_path, receipt)
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("verify", "seal", "plan", "apply", "check", "rollback"))
    parser.add_argument("--layout", type=Path)
    parser.add_argument("--hosts", default=",".join(HOSTS))
    parser.add_argument("--support", default="", help="launcher,adapter,codexpp_source,codexpp_tweaks; copy only, never execute")
    parser.add_argument("--managed", action="store_true", help="explicitly include Claude machine settings; requires appropriate filesystem access")
    parser.add_argument("--receipt", type=Path)
    args = parser.parse_args()
    if args.action == "seal":
        print(json.dumps(seal()))
        return
    manifest = verify()
    if args.action == "verify":
        print(json.dumps({"verified_entries": len(manifest["entries"]), "hosts": manifest["hosts"]}))
        return
    if args.action == "rollback":
        if not args.receipt:
            parser.error("rollback requires --receipt")
        print(json.dumps({"status": rollback(args.receipt.resolve())["status"]}))
        return
    if not args.layout:
        parser.error("this action requires --layout")
    hosts = tuple(x for x in args.hosts.split(",") if x)
    support = tuple(x for x in args.support.split(",") if x)
    if not hosts or set(hosts) - set(HOSTS) or set(support) - (set(SUPPORT_ROOTS) - {"claude_managed"}):
        parser.error("unknown host or support component")
    layout = json.load(sys.stdin) if str(args.layout) == "-" else load_json(args.layout)
    bindings = bindings_from_layout(layout)
    operations = plan(manifest, bindings, hosts, support, args.managed)
    summary = {"create": sum(x["status"] == "create" for x in operations),
               "identical": sum(x["status"] == "identical" for x in operations),
               "collisions": [x["target"] for x in operations if x["status"] == "collision"]}
    if args.action == "plan":
        print(json.dumps({**summary, "operations": operations}, ensure_ascii=False, indent=2))
    elif args.action == "check":
        print(json.dumps(summary, ensure_ascii=False))
        if summary["create"] or summary["collisions"]:
            sys.exit(2)
    else:
        if not args.receipt:
            parser.error("apply requires --receipt")
        result = apply(manifest, bindings, operations, args.receipt.resolve(), hosts)
        print(json.dumps({"status": result["status"], "created": len(result["created"]), "receipt": str(args.receipt)}))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, KeyError) as exc:
        print("Restore stopped: " + str(exc), file=sys.stderr)
        sys.exit(1)
