"""Small, dependency-free helpers for the reviewed host migration package."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import stat
import tempfile

TOKEN = re.compile(r"@@([A-Z][A-Z0-9_]*):(win|forward|escaped)@@")
HOSTS = ("codex", "codex_plus_plus", "claude_code")
TEXT_SUFFIXES = {".md", ".py", ".ps1", ".cmd", ".bat", ".vbs", ".sh", ".js", ".cjs", ".mjs", ".ts", ".tsx", ".json", ".toml", ".yaml", ".yml", ".rules", ".txt", ".template", ".html", ".css", ".svg", ".map"}
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".pytest_cache", ".cache", ".tmp", "tmp", "temp", "logs", "log", "backup", "backups", "storage", "tweak-data", "sessions", "archived_sessions", "memories", "automations", "hook-state", "test-results", "diag-dump", "dist", "store"}
PRIVATE_NAME = re.compile(r"(^\.env($|\.)|credential|auth\.json|secrets?|webhooks?[^/]*\.(?:ya?ml|json|env)$|\.sqlite|\.db($|[-.])|\.bak|\.backup|\.log$|\.jsonl$|history|session_index|installation_id|cap_sid|\.lock$|\.guard$)", re.I)
SECRET_KEY = re.compile(r"(^|[_-])(api[_-]?key|access[_-]?token|refresh[_-]?token|auth[_-]?token|bearer[_-]?token|token|secret|password|authorization|cookie)([_-]|$)|apiKey|authToken|accessToken|refreshToken|clientSecret|x-openai-actor-authorization", re.I)
SECRET_PATTERNS = [
    re.compile(r"-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----"),
    re.compile(r"\b(?:ghp_|github_pat_|sk-proj-)[A-Za-z0-9_\-]{20,}"),
    re.compile(r"\bsk-[A-Za-z0-9]{24,}\b"),
    re.compile(r"\beyJ[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{12,}\b"),
    re.compile(r"https://[^\s\"']*/(?:webhook|webhook_v2|hook)/[A-Za-z0-9_-]{16,}"),
    re.compile(r"https://hooks\.slack\.com/services/[A-Za-z0-9/_-]{20,}"),
    re.compile(r"https://(?:discord\.com|discordapp\.com)/api/webhooks/[A-Za-z0-9/_-]{20,}"),
    re.compile(r"https?://[^\s\"']*[?&](?:access_token|api_key|token)=[A-Za-z0-9_-]{16,}"),
]


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def general_asset_sha256(path: Path) -> str:
    data = fs_path(path).read_bytes()
    binary = path.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".pdf", ".zip", ".docx", ".xlsx", ".pptx", ".woff", ".woff2", ".exe", ".dll"} or b"\0" in data
    if not binary:
        # Also covers extensionless LICENSE/.keep files. No source is rewritten.
        try:
            data.decode("utf-8-sig")
        except UnicodeDecodeError:
            pass
        else:
            data = data.replace(b"\r\n", b"\n")
    return sha256(data)


def load_json(path: Path):
    return json.loads(fs_path(path).read_text(encoding="utf-8-sig"))


def json_bytes(value) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def is_reparse(path: Path) -> bool:
    try:
        return bool(fs_path(path).lstat().st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT)
    except (AttributeError, FileNotFoundError):
        return path.is_symlink()


def fs_path(path: Path) -> Path:
    """Extended Windows names for filesystem I/O, never for rendered config."""
    name = str(path.absolute())
    if os.name == "nt" and not name.startswith("\\\\?\\"):
        name = "\\\\?\\UNC\\" + name[2:] if name.startswith("\\\\") else "\\\\?\\" + name
    return Path(name)


def canonical(path: Path) -> Path:
    name = str(fs_path(path).resolve())
    if name.startswith("\\\\?\\UNC\\"):
        name = "\\\\" + name[8:]
    elif name.startswith("\\\\?\\"):
        name = name[4:]
    return Path(os.path.normcase(name))


def below(path: Path, root: Path) -> bool:
    try:
        canonical(path).relative_to(canonical(root))
        return True
    except ValueError:
        return False


def assert_physical_chain(path: Path) -> None:
    for ancestor in (path, *path.parents):
        if is_reparse(ancestor):
            raise ValueError(f"Reparse/symlink target requires an explicit physical path: {ancestor}")


def safe_relative(value: str) -> Path:
    if "\\" in value or ":" in value:
        raise ValueError("Manifest path must use relative forward slashes")
    p = Path(value)
    if p.is_absolute() or not p.parts or any(x in ("..", ".") for x in p.parts):
        raise ValueError("Unsafe manifest path")
    return p


def tokenize(text: str, bindings: dict[str, str]) -> str:
    replacements = []
    for key, raw in bindings.items():
        value = str(raw).rstrip("\\/")
        if not value:
            continue
        for style, variant in (("escaped", value.replace("\\", "\\\\")), ("forward", value.replace("\\", "/")), ("win", value)):
            replacements.append((variant, f"@@{key}:{style}@@"))
    # Longest match preserves the nested Codex++ home before its profile root.
    for old, new in sorted(replacements, key=lambda item: len(item[0]), reverse=True):
        text = re.sub(re.escape(old), lambda _: new, text, flags=re.I)
    return text


def render(text: str, bindings: dict[str, str]) -> str:
    def replace(match):
        key, style = match.groups()
        if key not in bindings or not bindings[key]:
            raise ValueError(f"Missing layout binding: {key}")
        raw = str(bindings[key])
        if style == "forward":
            return raw.replace("\\", "/")
        if style == "escaped":
            return raw.replace("\\", "\\\\")
        return raw
    return TOKEN.sub(replace, text)


def toml_bytes(obj: dict) -> bytes:
    """Serialize the configuration types present here; validate with tomllib."""
    def key(k):
        return json.dumps(str(k), ensure_ascii=False)
    def value(v):
        if isinstance(v, str):
            return json.dumps(v, ensure_ascii=False)
        if isinstance(v, bool):
            return "true" if v else "false"
        if isinstance(v, (int, float)):
            return repr(v)
        if isinstance(v, list):
            return "[" + ", ".join(value(x) for x in v) + "]"
        if isinstance(v, dict):
            return "{ " + ", ".join(key(k) + " = " + value(x) for k, x in v.items()) + " }"
        raise TypeError(f"Unsupported TOML type: {type(v).__name__}")
    lines = []
    def table(mapping, path):
        if path:
            lines.extend(("", "[" + ".".join(key(k) for k in path) + "]"))
        for k, v in mapping.items():
            if not isinstance(v, dict):
                lines.append(key(k) + " = " + value(v))
        for k, v in mapping.items():
            if isinstance(v, dict):
                table(v, path + [k])
    table(obj, [])
    return ("\n".join(lines).strip() + "\n").encode("utf-8")


def strip_secrets(value, removed: list[str], path=""):
    if isinstance(value, dict):
        clean = {}
        for k, item in value.items():
            name = path + "." + k if path else k
            if k == "env_http_headers" and isinstance(item, dict):
                if not all(isinstance(v, str) and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", v) for v in item.values()):
                    raise ValueError("env_http_headers must contain environment variable names")
                clean[k] = dict(item)
            elif k.endswith("_env_var"):
                clean[k] = item
            elif SECRET_KEY.search(k) and isinstance(item, (str, dict, list)):
                removed.append(name)
            else:
                clean[k] = strip_secrets(item, removed, name)
        return clean
    if isinstance(value, list):
        return [strip_secrets(x, removed, path) for x in value]
    return value


def secret_values(value, result=None):
    result = result if result is not None else set()
    if isinstance(value, dict):
        for key, item in value.items():
            if key == "env_http_headers" or key.endswith("_env_var"):
                continue
            if SECRET_KEY.search(key) and isinstance(item, str) and len(item) >= 8:
                result.add(item)
            else:
                secret_values(item, result)
    elif isinstance(value, list):
        for item in value:
            secret_values(item, result)
    return result


def scan_secrets(text: str, known=()) -> bool:
    return any(x and x in text for x in known) or any(p.search(text) for p in SECRET_PATTERNS)


def write_new(path: Path, data: bytes) -> None:
    """An atomic create without replacing an existing path (including races)."""
    path = fs_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=".host-migration-", dir=path.parent)
    temp = Path(temp_name)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        def native_name(p):
            name = str(p.absolute())
            if os.name == "nt" and not name.startswith("\\\\?\\"):
                return "\\\\?\\UNC\\" + name[2:] if name.startswith("\\\\") else "\\\\?\\" + name
            return name
        os.link(native_name(temp), native_name(path))  # atomic; supports Windows long paths
    finally:
        temp.unlink(missing_ok=True)
