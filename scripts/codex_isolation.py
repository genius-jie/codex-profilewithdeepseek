#!/usr/bin/env python3
"""Audit and repair native Codex vs Codex++ isolation.

Default paths are Windows-specific. No third-party packages are required.
Writes only happen with `repair --apply`; verification probes are opt-in.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

NATIVE_CM_PORT = "48760"
CODEXPP_CM_PORT = "15740"
OFFICIAL_PROVIDER = "openai"
CM_SECTION_RE = re.compile(r"^\s*\[(model_providers\.cm(?:\.[^\]]*)?)\]\s*(?:#.*)?$")
HEADER_RE = re.compile(r"^\s*\[([^\]]+)\]\s*(?:#.*)?$")
CM_PROVIDER_RE = re.compile(r'^\s*model_provider\s*=\s*["\']cm["\']\s*(?:#.*)?$', re.MULTILINE)
MODEL_PROVIDER_RE = re.compile(r'^\s*model_provider\s*=\s*["\']([^"\']+)["\']\s*(?:#.*)?$', re.MULTILINE)
CATALOG_RE = re.compile(r"^\s*model_catalog_json\s*=", re.MULTILINE)
BEARER_RE = re.compile(r"^\s*experimental_bearer_token\s*=", re.MULTILINE)
SESSION_CM_RE = re.compile(rb'"model_provider"\s*:\s*"cm"')
PROXY_VARS = ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy")

Results = list[tuple[str, str, str]]


def configure_stdout() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except AttributeError:
            pass


def expand(path: str | Path) -> Path:
    return Path(os.path.expandvars(os.path.expanduser(str(path)))).resolve()


def same_path(left: str | Path | None, right: str | Path | None) -> bool:
    if not left or not right:
        return False
    return os.path.normcase(os.path.normpath(str(expand(left)))) == os.path.normcase(
        os.path.normpath(str(expand(right)))
    )


def native_home(args: argparse.Namespace) -> Path:
    value = args.native_home or os.environ.get("CODEX_NATIVE_HOME")
    return expand(value) if value else expand(Path.home() / ".codex")


def codexpp_home(args: argparse.Namespace) -> Path:
    for value in (args.codexpp_home, os.environ.get("CODEXPP_CODEX_HOME"), os.environ.get("CODEXPP_HOME")):
        if not value:
            continue
        root = expand(value)
        nested = root / "AppData" / "Roaming" / "Codex" / ".codex"
        if (root / "config.toml").exists():
            return root
        if (nested / "config.toml").exists():
            return nested
        return nested
    root = expand(Path("C:/CodexPlusPlusProfile"))
    return root / "AppData" / "Roaming" / "Codex" / ".codex"


def codexmanager_db(args: argparse.Namespace) -> Path:
    value = args.codexmanager_db or os.environ.get("CODEXMANAGER_DB")
    if value:
        return expand(value)
    appdata = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
    return expand(Path(appdata) / "com.codexmanager.desktop" / "codexmanager.db")


def find_codex_cli() -> Path | None:
    explicit = os.environ.get("CODEX_CLI_PATH")
    if explicit and Path(explicit).is_file() and "codex-plusplus" not in str(explicit).lower():
        return Path(explicit)
    which = shutil.which("codex")
    if which:
        lowered = str(which).lower()
        if "codex-plusplus" not in lowered and "codexplusplusprofile" not in lowered:
            return Path(which)
    roots = [
        Path(os.environ.get("LOCALAPPDATA", "")) / "OpenAI" / "Codex" / "bin",
        Path(os.environ.get("ProgramFiles", "")) / "OpenAI" / "Codex",
    ]
    candidates: list[Path] = []
    for root in roots:
        if root.is_dir():
            candidates.extend(root.glob("**/codex.exe"))
    native = [p for p in candidates if "codex-plusplus" not in str(p).lower()]
    if not native:
        return None
    return max(native, key=lambda p: p.stat().st_mtime)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def status(results: Results, level: str, name: str, detail: str) -> None:
    results.append((level, name, detail))
    print(f"[{level}] {name}: {detail}")


def has_failure(results: Results) -> bool:
    return any(level == "FAIL" for level, _, _ in results)


def fold_lines(lines: Iterable[str]) -> str:
    return "".join(lines)


def remove_empty_model_providers(lines: list[str]) -> list[str]:
    out: list[str] = []
    index = 0
    while index < len(lines):
        if re.match(r"^\s*\[model_providers\]\s*(?:#.*)?$", lines[index]):
            end = index + 1
            while end < len(lines) and not HEADER_RE.match(lines[end]):
                end += 1
            body = lines[index + 1 : end]
            if all(not line.strip() or line.lstrip().startswith("#") for line in body):
                index = end
                continue
        out.append(lines[index])
        index += 1
    return out


def strip_cm_config(text: str) -> tuple[str, list[str]]:
    removed: list[str] = []
    out: list[str] = []
    section: str | None = None
    skip = False
    for line in text.splitlines(keepends=True):
        header = HEADER_RE.match(line)
        if header:
            section = header.group(1).strip()
            skip = section == "model_providers.cm" or section.startswith("model_providers.cm.")
            if skip:
                removed.append(f"[{section}]")
                continue
            out.append(line)
            continue
        if skip:
            continue
        if section is None and CM_PROVIDER_RE.match(line):
            removed.append("model_provider=cm")
            continue
        if section is None and CATALOG_RE.match(line):
            lowered = line.lower()
            if any(marker in lowered for marker in ("gateway-models", "codexmanager", NATIVE_CM_PORT)):
                removed.append("model_catalog_json (CM)")
                continue
        out.append(line)
    out = remove_empty_model_providers(out)
    return fold_lines(out), removed


def write_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.isolation-{os.getpid()}")
    temp.write_text(text, encoding="utf-8", newline="")
    os.replace(temp, path)


def sqlite_read(path: Path) -> sqlite3.Connection:
    return sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)


def sqlite_backup(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    src = sqlite3.connect(str(source))
    dst = sqlite3.connect(str(target))
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()


def cm_state(db: Path) -> tuple[dict[str, Any] | None, str | None]:
    try:
        con = sqlite_read(db)
        try:
            row = con.execute("select value from app_settings where key='codex_profile.state'").fetchone()
        finally:
            con.close()
    except sqlite3.Error as exc:
        return None, str(exc)
    if not row:
        return None, None
    try:
        return json.loads(row[0]), None
    except (TypeError, json.JSONDecodeError) as exc:
        return None, str(exc)


def cm_active_home(db: Path) -> tuple[str | None, str | None]:
    try:
        con = sqlite_read(db)
        try:
            row = con.execute("select value from app_settings where key='codex_profile.codex_home'").fetchone()
        finally:
            con.close()
    except sqlite3.Error as exc:
        return None, str(exc)
    return (row[0] if row else None), None


def native_markers(db: Path, state: dict[str, Any] | None, home: Path) -> list[Path]:
    if not state or not same_path(state.get("profileDir"), home):
        return []
    root = db.parent / "codex-profiles"
    if not root.is_dir():
        return []
    markers: list[Path] = []
    for marker in root.glob("*/profile.json"):
        try:
            payload = json.loads(read_text(marker))
        except (OSError, json.JSONDecodeError):
            continue
        if payload.get("providerId") != "cm":
            continue
        if NATIVE_CM_PORT not in str(payload.get("gatewayBaseUrl", "")):
            continue
        if state.get("apiKeyId") and payload.get("apiKeyId") != state.get("apiKeyId"):
            continue
        markers.append(marker)
    return markers


def state_needs_fix(state: dict[str, Any] | None, home: Path) -> bool:
    if not state:
        return False
    if state.get("profileDir") and not same_path(state.get("profileDir"), home):
        return False
    return (
        state.get("mode") in {"gateway", "managed", "managed_unknown"}
        or state.get("providerId") == "cm"
        or NATIVE_CM_PORT in str(state.get("gatewayBaseUrl", ""))
    )


def unmanaged_state(state: dict[str, Any], home: Path) -> dict[str, Any]:
    return {
        "profileDir": str(home),
        "mode": "unmanaged",
        "accountId": None,
        "apiKeyId": None,
        "aggregateApiId": None,
        "gatewayBaseUrl": None,
        "aggregateApiBaseUrl": None,
        "supportsWebsockets": False,
        "providerId": None,
        "previousModelCatalogJson": None,
        "managedModelSlugs": [],
        "updatedAt": int(datetime.now().timestamp()),
    }


def session_files(home: Path) -> list[Path]:
    files: list[Path] = []
    for name in ("sessions", "archived_sessions"):
        base = home / name
        if base.is_dir():
            files.extend(base.rglob("*.jsonl"))
    return files


def cm_session_files(home: Path) -> list[Path]:
    return [path for path in session_files(home) if SESSION_CM_RE.search(path.read_bytes())]


def thread_cm_count(home: Path) -> tuple[int | None, str | None]:
    db = home / "state_5.sqlite"
    if not db.exists():
        return None, None
    try:
        con = sqlite_read(db)
        try:
            row = con.execute(
                "select count(*) from threads where model_provider='cm'"
            ).fetchone()
        finally:
            con.close()
    except sqlite3.Error as exc:
        return None, str(exc)
    return int(row[0]), None


def run_codex(
    cli: Path,
    args: list[str],
    home: Path,
    timeout: int = 30,
    cwd: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["CODEX_HOME"] = str(home)
    return subprocess.run(
        [str(cli), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        env=env,
        cwd=str(cwd) if cwd else None,
    )


def audit_configs(native: Path, cpp: Path, db: Path, require_codexpp: bool) -> Results:
    results: Results = []
    native_config = native / "config.toml"
    if not native_config.exists():
        status(results, "FAIL", "原生配置", f"缺少 {native_config}")
        native_text = ""
    else:
        native_text = read_text(native_config)
        cm_key = bool(CM_PROVIDER_RE.search(native_text))
        cm_section = bool(re.search(r"^\s*\[model_providers\.cm(?:\.[^\]]*)?\]", native_text, re.MULTILINE))
        cm_port = NATIVE_CM_PORT in native_text
        cm_catalog = "gateway-models.json" in native_text.lower() or "codexmanager" in native_text.lower()
        if cm_key or cm_section or cm_port or cm_catalog:
            details = []
            if cm_key:
                details.append("model_provider=cm")
            if cm_section:
                details.append("[model_providers.cm]")
            if cm_port:
                details.append(NATIVE_CM_PORT)
            if cm_catalog:
                details.append("CM catalog")
            status(results, "FAIL", "原生配置", "仍含 CM 接管标记: " + ", ".join(details))
        else:
            status(results, "PASS", "原生配置", "无 CM provider / 48760 / CM catalog")
        other_provider = MODEL_PROVIDER_RE.search(native_text)
        if other_provider and other_provider.group(1) != "cm":
            status(results, "WARN", "原生 provider", f"存在非 CM provider: {other_provider.group(1)}")
        if CATALOG_RE.search(native_text) and not cm_catalog:
            status(results, "WARN", "原生 catalog", "存在非 CM 的 model_catalog_json，请确认是否必要")
        if BEARER_RE.search(native_text) and not cm_section:
            status(results, "WARN", "原生令牌", "存在 experimental_bearer_token（非 CM 段），请确认用途")

    cpp_config = cpp / "config.toml"
    if not cpp_config.exists():
        level = "FAIL" if require_codexpp else "WARN"
        status(results, level, "Codex++ 配置", f"未找到 {cpp_config}")
    else:
        cpp_text = read_text(cpp_config)
        checks = {
            'model_provider = "cm"': bool(CM_PROVIDER_RE.search(cpp_text)),
            "[model_providers.cm]": bool(
                re.search(r"^\s*\[model_providers\.cm(?:\.[^\]]*)?\]", cpp_text, re.MULTILINE)
            ),
            CODEXPP_CM_PORT: CODEXPP_CM_PORT in cpp_text,
            "CODEXPP_GATEWAY_TOKEN": "CODEXPP_GATEWAY_TOKEN" in cpp_text,
        }
        missing = [name for name, ok in checks.items() if not ok]
        if missing:
            status(results, "FAIL", "Codex++ 配置", "中转契约缺失: " + ", ".join(missing))
        else:
            status(results, "PASS", "Codex++ 配置", f"仍为 CM/{CODEXPP_CM_PORT} 中转")

    if not db.exists():
        status(results, "SKIP", "CodexManager", f"未找到 {db}")
        return results
    state, state_error = cm_state(db)
    if state_error:
        status(results, "WARN", "CodexManager state", f"读取失败: {state_error}")
    elif state_needs_fix(state, native):
        status(
            results,
            "FAIL",
            "CodexManager 原生 state",
            f"仍为 {state.get('mode')} / provider={state.get('providerId')} / {state.get('gatewayBaseUrl')}",
        )
    elif state and same_path(state.get("profileDir"), native):
        level = "PASS" if state.get("mode") == "unmanaged" else "WARN"
        status(results, level, "CodexManager 原生 state", f"mode={state.get('mode')}")
    else:
        status(results, "PASS", "CodexManager 原生 state", "未登记为原生接管")

    active_home, active_error = cm_active_home(db)
    if active_error:
        status(results, "WARN", "CodexManager 活动 profile", f"读取失败: {active_error}")
    elif active_home and same_path(active_home, native):
        status(results, "FAIL", "CodexManager 活动 profile", "当前活动 profile 指向原生目录")
    elif active_home:
        level = "PASS" if same_path(active_home, cpp) else "WARN"
        status(results, level, "CodexManager 活动 profile", active_home)
    else:
        status(results, "SKIP", "CodexManager 活动 profile", "未设置 codex_profile.codex_home")

    markers = native_markers(db, state, native)
    if markers:
        status(results, "FAIL", "CodexManager 原生 marker", ", ".join(str(p) for p in markers))
    else:
        status(results, "PASS", "CodexManager 原生 marker", "未发现 48760 gateway marker")
    return results


def audit_history(native: Path) -> Results:
    results: Results = []
    count, error = thread_cm_count(native)
    if error:
        status(results, "WARN", "原生线程索引", f"读取失败: {error}")
    elif count is None:
        status(results, "SKIP", "原生线程索引", "未找到 state_5.sqlite")
    elif count:
        status(results, "FAIL", "原生线程索引", f"{count} 条线程仍为 model_provider=cm")
    else:
        status(results, "PASS", "原生线程索引", "无 cm provider")

    files = cm_session_files(native)
    if files:
        status(results, "FAIL", "原生会话文件", f"{len(files)} 个 rollout 仍为 cm")
    else:
        status(results, "PASS", "原生会话文件", "无 cm provider")
    return results


def audit_auth(native: Path) -> Results:
    results: Results = []
    auth = native / "auth.json"
    if not auth.exists():
        status(results, "FAIL", "原生登录", f"缺少 {auth}，请运行 codex login --device-auth")
        return results
    cli = find_codex_cli()
    if not cli:
        status(results, "WARN", "原生登录", "未找到原生 Codex CLI，无法核对 login status")
        return results
    try:
        proc = run_codex(cli, ["login", "status"], native, timeout=20)
    except (OSError, subprocess.TimeoutExpired) as exc:
        status(results, "WARN", "原生登录", f"login status 失败: {exc}")
        return results
    output = (proc.stdout + proc.stderr).strip()
    if "Logged in using ChatGPT" in output:
        status(results, "PASS", "原生登录", "Logged in using ChatGPT")
    elif "Not logged in" in output:
        status(results, "FAIL", "原生登录", "Not logged in，请重新登录")
    else:
        status(results, "WARN", "原生登录", output[-300:] or f"exit={proc.returncode}")
    return results


def audit_proxy() -> Results:
    results: Results = []
    for name in PROXY_VARS:
        value = os.environ.get(name)
        if not value:
            continue
        if NATIVE_CM_PORT in value:
            status(results, "FAIL", "代理环境", f"{name} 指向 CM 网关: {value}")
        else:
            status(results, "WARN", "代理环境", f"{name}={value}")
    if not any(os.environ.get(name) for name in PROXY_VARS):
        status(results, "PASS", "代理环境", "未设置 HTTP/HTTPS/ALL_PROXY")
    return results


def run_audit(native: Path, cpp: Path, db: Path, include_auth: bool, require_codexpp: bool) -> Results:
    results: Results = []
    results += audit_configs(native, cpp, db, require_codexpp)
    results += audit_history(native)
    results += audit_proxy()
    if include_auth:
        results += audit_auth(native)
    return results


def print_summary(results: Results) -> None:
    fails = sum(1 for level, _, _ in results if level == "FAIL")
    warns = sum(1 for level, _, _ in results if level == "WARN")
    print(f"\n结果: FAIL={fails} WARN={warns} PASS={sum(1 for level, _, _ in results if level == 'PASS')}")
    if fails:
        print("隔离未完成：先修复 FAIL 项，再运行 verify。")
    elif warns:
        print("隔离主链路通过；WARN 项请人工确认。")
    else:
        print("隔离检查全部通过。")


def timestamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def make_backup_dir(requested: str | None) -> Path:
    if requested:
        base = expand(requested)
        if base.exists():
            base = base.with_name(f"{base.name}-{timestamp()}")
        return base
    base = Path.home() / ".codex-isolation-backup" / timestamp()
    candidate = base
    index = 1
    while candidate.exists():
        candidate = base.with_name(f"{base.name}-{index}")
        index += 1
    return candidate


def read_db_state_row(db: Path) -> tuple[str | None, str | None]:
    try:
        con = sqlite_read(db)
        try:
            row = con.execute("select value from app_settings where key='codex_profile.state'").fetchone()
        finally:
            con.close()
    except sqlite3.Error as exc:
        return None, str(exc)
    return (row[0] if row else None), None


def apply_repair(
    native: Path,
    cpp: Path,
    db: Path,
    backup_dir: Path,
    receipt: Path,
    config_text: str,
    new_text: str,
    removed: list[str],
    state: dict[str, Any] | None,
    markers: list[Path],
    thread_count: int | None,
    session_cm: list[Path],
) -> tuple[list[str], list[str]]:
    actions: list[str] = []
    errors: list[str] = []
    backup_dir.mkdir(parents=True, exist_ok=True)

    if removed:
        config = native / "config.toml"
        shutil.copy2(config, backup_dir / "config.toml")
        write_atomic(config, new_text)
        actions.append("原生 config.toml 移除: " + ", ".join(removed))

    if state_needs_fix(state, native) and state:
        row, error = read_db_state_row(db)
        if error:
            errors.append(f"读取 CodexManager state 失败: {error}")
        elif row:
            (backup_dir / "codexmanager-codex-profile-state.json").write_text(
                json.dumps(
                    {"key": "codex_profile.state", "value": row, "backup_at": datetime.now().isoformat()},
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            try:
                con = sqlite3.connect(str(db), timeout=15)
                con.execute("PRAGMA busy_timeout=15000")
                con.execute("BEGIN IMMEDIATE")
                con.execute(
                    "update app_settings set value=?, updated_at=? where key='codex_profile.state'",
                    (
                        json.dumps(unmanaged_state(state, native), ensure_ascii=False, separators=(",", ":")),
                        int(datetime.now().timestamp()),
                    ),
                )
                con.commit()
                con.close()
                actions.append("CodexManager 原生 state -> unmanaged")
            except sqlite3.Error as exc:
                errors.append(f"写入 CodexManager state 失败: {exc}")

    for marker in markers:
        try:
            relative = marker.relative_to(db.parent)
            target = backup_dir / "codexmanager-markers" / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(marker, target)
            marker.unlink()
            actions.append(f"移除原生 gateway marker: {marker}")
        except OSError as exc:
            errors.append(f"移除 marker 失败 {marker}: {exc}")

    history_db = native / "state_5.sqlite"
    if thread_count:
        try:
            sqlite_backup(history_db, backup_dir / "state_5.sqlite")
            con = sqlite3.connect(str(history_db), timeout=15)
            con.execute("PRAGMA busy_timeout=15000")
            con.execute("BEGIN IMMEDIATE")
            updated = con.execute(
                "update threads set model_provider=? where model_provider='cm'",
                (OFFICIAL_PROVIDER,),
            ).rowcount
            con.commit()
            con.close()
            actions.append(f"原生线程索引 cm -> {OFFICIAL_PROVIDER}: {updated} 条")
        except sqlite3.Error as exc:
            errors.append(f"更新原生线程索引失败: {exc}")

    for session in session_cm:
        try:
            relative = session.relative_to(native)
            target = backup_dir / "sessions" / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            data = session.read_bytes()
            target.write_bytes(data)
            updated = SESSION_CM_RE.sub(
                f'"model_provider":"{OFFICIAL_PROVIDER}"'.encode("utf-8"),
                data,
            )
            temp = session.with_name(f".{session.name}.isolation-{os.getpid()}")
            temp.write_bytes(updated)
            os.replace(temp, session)
            actions.append(f"会话 provider cm -> {OFFICIAL_PROVIDER}: {relative}")
        except OSError as exc:
            errors.append(f"改写会话失败 {session}: {exc}")

    receipt.parent.mkdir(parents=True, exist_ok=True)
    receipt.write_text(
        json.dumps(
            {
                "generated_at": datetime.now().isoformat(),
                "native_home": str(native),
                "codexpp_home": str(cpp),
                "backup_dir": str(backup_dir),
                "actions": actions,
                "errors": errors,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return actions, errors


def plane(args: argparse.Namespace) -> tuple[Path, Path, Path, Path | None]:
    native = native_home(args)
    cpp = codexpp_home(args)
    db = codexmanager_db(args)
    if same_path(native, cpp):
        raise SystemExit("原生目录与 Codex++ 目录相同，拒绝继续。")
    return native, cpp, db, find_codex_cli()


def command_audit(args: argparse.Namespace) -> int:
    native, cpp, db, _ = plane(args)
    results = run_audit(native, cpp, db, include_auth=True, require_codexpp=args.require_codexpp)
    print_summary(results)
    return 1 if has_failure(results) else 0


def command_repair(args: argparse.Namespace) -> int:
    native, cpp, db, _ = plane(args)
    config = native / "config.toml"
    if not config.exists():
        print(f"[FAIL] 原生配置不存在: {config}")
        return 1
    text = read_text(config)
    new_text, removed = strip_cm_config(text)
    state, state_error = cm_state(db) if db.exists() else (None, None)
    if state_error:
        print(f"[WARN] CodexManager state 读取失败: {state_error}")
    markers = native_markers(db, state, native) if db.exists() else []
    thread_count, thread_error = thread_cm_count(native)
    if thread_error:
        print(f"[WARN] 原生线程索引读取失败: {thread_error}")
    session_cm = cm_session_files(native)

    print(f"原生目录: {native}")
    print(f"Codex++ 目录: {cpp}")
    print(f"CodexManager: {db}")
    changes = []
    if removed:
        changes.append("config.toml 移除 " + ", ".join(removed))
    if state_needs_fix(state, native):
        changes.append("CodexManager 原生 state -> unmanaged")
    if markers:
        changes.append(f"移除 {len(markers)} 个原生 gateway marker")
    if thread_count:
        changes.append(f"线程索引 cm -> {OFFICIAL_PROVIDER}: {thread_count} 条")
    if session_cm:
        changes.append(f"会话文件 cm -> {OFFICIAL_PROVIDER}: {len(session_cm)} 个")

    if not changes:
        print("未发现需要修复的项。")
        return 0
    print("计划:")
    for change in changes:
        print(f"  - {change}")

    if not args.apply:
        print("\n当前为预览模式；确认后加 --apply 执行写入。")
        return 0

    backup_dir = make_backup_dir(args.backup_dir)
    receipt = expand(args.receipt) if args.receipt else backup_dir / "receipt.json"
    actions, errors = apply_repair(
        native, cpp, db, backup_dir, receipt, text, new_text, removed,
        state, markers, thread_count, session_cm,
    )
    print(f"\n备份目录: {backup_dir}")
    print(f"回执: {receipt}")
    for action in actions:
        print(f"[DONE] {action}")
    for error in errors:
        print(f"[ERROR] {error}")

    post = run_audit(native, cpp, db, include_auth=False, require_codexpp=False)
    print("\n修复后隔离检查:")
    print_summary(post)
    if errors or has_failure(post):
        return 1
    print("修复完成。请重启原生 Codex 桌面端；若登录失效，再运行 codex login --device-auth。")
    return 0


def probe_output_ok(output: str) -> bool:
    for line in output.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        item = event.get("item") or {}
        if item.get("type") == "agent_message" and str(item.get("text", "")).strip() == "OK":
            return True
    return '"text":"OK"' in output


def command_verify(args: argparse.Namespace) -> int:
    native, cpp, db, cli = plane(args)
    results = run_audit(native, cpp, db, include_auth=True, require_codexpp=args.require_codexpp)
    if args.probe and not has_failure(results):
        if not cli:
            status(results, "FAIL", "直连探针", "未找到原生 Codex CLI")
        else:
            probe_start = datetime.now().timestamp()
            work = Path(tempfile.mkdtemp(prefix="codex-isolation-probe-"))
            try:
                proc = run_codex(
                    cli,
                    [
                        "exec",
                        "--json",
                        "--skip-git-repo-check",
                        "-s",
                        "read-only",
                        "-c",
                        'model_reasoning_effort="low"',
                        "-c",
                        'service_tier="default"',
                        "Reply with exactly OK",
                    ],
                    native,
                    timeout=240,
                    cwd=work,
                )
                output = proc.stdout.strip()
                if proc.returncode != 0 or not probe_output_ok(output):
                    tail = (proc.stderr or output)[-1500:]
                    status(results, "FAIL", "直连探针", f"exit={proc.returncode}; {tail}")
                else:
                    new_files = [
                        path
                        for path in (native / "sessions").rglob("*.jsonl")
                        if path.stat().st_mtime >= probe_start - 2
                    ]
                    provider = None
                    if new_files:
                        newest = max(new_files, key=lambda path: path.stat().st_mtime)
                        try:
                            first = json.loads(read_text(newest).splitlines()[0])
                            provider = (first.get("payload") or {}).get("model_provider")
                        except (OSError, json.JSONDecodeError, IndexError):
                            provider = None
                    if provider == OFFICIAL_PROVIDER:
                        status(results, "PASS", "直连探针", f"真实请求返回 OK，session provider={provider}")
                    elif provider:
                        status(results, "FAIL", "直连探针", f"真实请求返回 OK，但 session provider={provider}")
                    else:
                        status(results, "WARN", "直连探针", "真实请求返回 OK，未定位到新 session provider")
            except (OSError, subprocess.TimeoutExpired) as exc:
                status(results, "FAIL", "直连探针", str(exc))
            finally:
                shutil.rmtree(work, ignore_errors=True)
    print_summary(results)
    return 1 if has_failure(results) else 0


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--native-home", help="原生 CODEX_HOME，默认 %USERPROFILE%\\.codex")
    common.add_argument("--codexpp-home", help="Codex++ Profile 根或嵌套 .codex，默认 C:\\CodexPlusPlusProfile")
    common.add_argument("--codexmanager-db", help="CodexManager codexmanager.db 路径")
    common.add_argument("--require-codexpp", action="store_true", help="Codex++ 配置缺失时视为失败")

    parser = argparse.ArgumentParser(description="Audit and repair native Codex vs Codex++ isolation.")
    sub = parser.add_subparsers(dest="command", required=True)

    audit = sub.add_parser("audit", parents=[common], help="只读检查")
    audit.set_defaults(func=command_audit)

    repair = sub.add_parser("repair", parents=[common], help="预览或修复原生侧")
    repair.add_argument("--apply", action="store_true", help="执行写入；默认只预览")
    repair.add_argument("--backup-dir", help="备份目录，默认 ~\\.codex-isolation-backup\\<timestamp>")
    repair.add_argument("--receipt", help="回执 JSON 路径，默认备份目录内 receipt.json")
    repair.set_defaults(func=command_repair)

    verify = sub.add_parser("verify", parents=[common], help="检查并可选发起真实直连请求")
    verify.add_argument("--probe", action="store_true", help="发起一次最小 codex exec 请求（消耗账号额度）")
    verify.set_defaults(func=command_verify)
    return parser


def main(argv: list[str] | None = None) -> int:
    configure_stdout()
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except SystemExit as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
