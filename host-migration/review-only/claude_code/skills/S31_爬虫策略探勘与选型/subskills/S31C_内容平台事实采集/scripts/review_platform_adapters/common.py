"""Shared contract helpers for S31C competitor review adapters."""

from __future__ import annotations

import html
import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.parse import quote_plus
from urllib.request import Request, urlopen


SCHEMA_VERSION = "s31c_competitor_review_adapter_receipt.v1"
FACT_PACK_VERSION = "crawler_fact_pack.v1"
USER_AGENT = "OpenClaw-S31C/1.0 (+controlled research adapter)"
S31_ROOT = Path(__file__).resolve().parents[4]
S31A_DIR = next((S31_ROOT / "subskills").glob("S31A_*"), None)
DEFAULT_BASELINE = (
    S31A_DIR / "references" / "platform_crawl_maturity_baseline.yaml"
    if S31A_DIR
    else S31_ROOT / "missing-platform_crawl_maturity_baseline.yaml"
)
PLATFORM_SCHEMA_PATH = S31_ROOT / "references" / "platform_data_schema.yaml"
_PLATFORM_SCHEMA_CACHE: dict[str, Any] | None = None
SUPPORTED_PLATFORMS = {
    "amazon",
    "appstore",
    "baidu",
    "bilibili",
    "bing",
    "dianping",
    "douyin",
    "douyin_ecommerce",
    "google",
    "jd",
    "pinduoduo",
    "public_article",
    "reddit",
    "rentio",
    "taobao_tmall",
    "tieba",
    "trustpilot",
    "weibo",
    "xianyu",
    "xiaohongshu",
    "yahoo_chiebukuro",
}
DISCOVERY_PLATFORMS = {"baidu", "bing", "google"}
SKIPPED_PLATFORMS = {"weibo"}
CONTROLLED_PLATFORMS = {
    "douyin",
    "douyin_ecommerce",
    "taobao_tmall",
    "tieba",
    "xianyu",
    "xiaohongshu",
}
PUBLIC_LIVE_PLATFORMS = {
    "amazon",
    "appstore",
    "bilibili",
    "dianping",
    "jd",
    "pinduoduo",
    "public_article",
    "reddit",
    "rentio",
    "trustpilot",
    "yahoo_chiebukuro",
}
SESSION_PREFLIGHT_PLATFORMS = CONTROLLED_PLATFORMS | {
    "bilibili",
    "jd",
    "weibo",
}


@dataclass
class AdapterRequest:
    platform: str
    mode: str
    query: str
    limit: int
    output_dir: Path
    baseline: dict[str, Any]
    url: str = ""
    item_id: str = ""
    app_id: str = ""
    asin: str = ""
    bvid: str = ""
    country: str = "us"
    controlled_input: Path | None = None


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def load_structured(path: Path) -> Any:
    text = path.read_text(encoding="utf-8", errors="replace")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        try:
            import yaml  # type: ignore
        except ModuleNotFoundError as exc:
            raise SystemExit(f"{path} is not JSON-compatible YAML and PyYAML is not installed") from exc
        return yaml.safe_load(text)


def as_list(value: Any) -> list[Any]:
    if value is None or value == "":
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def as_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float, bool)):
        return str(value)
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def safe_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return int(value)
    match = re.search(r"-?\d+(?:\.\d+)?", str(value).replace(",", ""))
    return int(float(match.group(0))) if match else None


def http_get(url: str, *, as_json: bool, timeout: float = 15.0) -> tuple[Any | None, dict[str, Any]]:
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json,text/html;q=0.9,*/*;q=0.8"})
    receipt: dict[str, Any] = {"url": url, "method": "GET"}
    try:
        with urlopen(request, timeout=timeout) as response:
            payload = response.read()
            receipt.update({"status": "ok", "status_code": response.status, "bytes": len(payload)})
            text = payload.decode("utf-8", errors="replace")
            if as_json:
                return json.loads(text), receipt
            return text, receipt
    except Exception as exc:  # noqa: BLE001 - receipt must preserve external failure type.
        receipt.update({"status": "failed", "error_type": type(exc).__name__, "error": str(exc)[:300]})
        return None, receipt


def strip_html(raw: str) -> str:
    raw = re.sub(r"(?is)<script.*?</script>|<style.*?</style>", " ", raw)
    raw = re.sub(r"(?s)<[^>]+>", " ", raw)
    raw = html.unescape(raw)
    return re.sub(r"\s+", " ", raw).strip()


def extract_title(raw: str) -> str:
    match = re.search(r"(?is)<title[^>]*>(.*?)</title>", raw)
    return strip_html(match.group(1)) if match else ""


def evidence_grade(item: dict[str, Any]) -> str:
    if item.get("top_comments") and item.get("body"):
        return "D_text_comments"
    if item.get("body") or item.get("title"):
        return "E_text_or_metadata"
    return "F_metadata_only"


def normalize_comment(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        text = as_text(value.get("text") or value.get("body") or value.get("content") or value.get("comment"))
        return {
            "author": as_text(value.get("author") or value.get("user") or value.get("nickname")),
            "text": text,
            "likes": safe_int(value.get("likes")) or 0,
            "raw": value,
        }
    return {"author": "", "text": as_text(value), "likes": 0, "raw": value}


def metric_aliases(metrics: dict[str, Any]) -> dict[str, Any]:
    aliases: dict[str, Any] = {}
    alias_pairs = {
        "like_count": "likes",
        "forward_count": "reposts",
        "comment_count": "comments_count",
        "danmu_count": "danmaku_count",
        "favorite_count": "favorites",
        "current_price": "price",
        "asking_price": "price",
    }
    for source, alias in alias_pairs.items():
        value = metrics.get(source)
        if value not in (None, "") and alias not in metrics:
            aliases[alias] = value
    if "danmu_count" in metrics and "danmaku" not in metrics:
        aliases["danmaku"] = metrics["danmu_count"]
    if "comment_count" in metrics and "comments" not in metrics:
        aliases["comments"] = metrics["comment_count"]
    return aliases


def to_fact_item(raw: dict[str, Any], platform: str) -> dict[str, Any]:
    comments = [normalize_comment(comment) for comment in as_list(raw.get("comments") or raw.get("top_comments"))]
    comments = [comment for comment in comments if comment.get("text")]
    metrics = dict(raw.get("metrics") or {})
    if "rating" in raw and raw["rating"] not in (None, ""):
        metrics.setdefault("rating", raw["rating"])
    pf = extract_platform_fields(raw, platform)
    for key, value in pf.items():
        metrics.setdefault(key, value)
    for key, value in metric_aliases(metrics).items():
        metrics.setdefault(key, value)
    item = {
        "title": as_text(raw.get("title") or raw.get("name")),
        "author": as_text(raw.get("author") or raw.get("user") or raw.get("nickname")),
        "body": as_text(raw.get("body") or raw.get("text") or raw.get("content") or raw.get("summary")),
        "tags": [as_text(tag) for tag in as_list(raw.get("tags")) if as_text(tag)],
        "metrics": metrics,
        "platform_fields": pf,
        "top_comments": comments[:10],
        "source_url": as_text(raw.get("source_url") or raw.get("url") or raw.get("link")),
        "media_files": [media if isinstance(media, dict) else {"url": as_text(media)} for media in as_list(raw.get("media_files"))],
        "frame_paths": [as_text(path) for path in as_list(raw.get("frame_paths")) if as_text(path)],
        "data_quality_flags": sorted({as_text(flag) for flag in as_list(raw.get("data_quality_flags")) if as_text(flag)}),
        "raw": dict(raw),
    }
    item["raw"].setdefault("platform", platform)
    item["evidence_grade"] = evidence_grade(item)
    missing = validate_platform_fields(pf, platform)
    if missing:
        item["data_quality_flags"] = sorted(set(item["data_quality_flags"]) | {"missing_required_platform_field"})
        item["missing_platform_fields"] = missing
    return item


def build_fact_pack(req: AdapterRequest, status: str, items: list[dict[str, Any]], command_receipts: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": FACT_PACK_VERSION,
        "platform": req.platform,
        "query": req.query,
        "collected_at": utc_now(),
        "collection_status": status,
        "items": items,
        "fact_summary": {
            "item_count": len(items),
            "adapter_facade": "competitor_review_adapters.py",
            "adapter_capability": adapter_capability(req.platform, baseline_row(req)),
        },
        "command_receipts": command_receipts,
        "inference": [],
    }


def baseline_row(req: AdapterRequest) -> dict[str, Any]:
    platforms = req.baseline.get("platforms") or {}
    row = platforms.get(req.platform) or {}
    return row if isinstance(row, dict) else {}


def adapter_capability(platform: str, row: dict[str, Any]) -> str:
    if platform in SKIPPED_PLATFORMS or row.get("maturity_tier") == "M0":
        return "skipped_receipt_adapter"
    if platform in DISCOVERY_PLATFORMS or row.get("maturity_tier") == "M1":
        return "discovery_adapter"
    if platform in PUBLIC_LIVE_PLATFORMS:
        return "public_live_adapter"
    if platform in CONTROLLED_PLATFORMS or row.get("maturity_tier") == "M2":
        return "controlled_input_adapter"
    return "controlled_or_reference_adapter"


def receipt_base(req: AdapterRequest, status: str, command_receipts: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    row = baseline_row(req)
    return {
        "schema_version": SCHEMA_VERSION,
        "platform": req.platform,
        "status": status,
        "mode": req.mode,
        "query": req.query,
        "collected_at": utc_now(),
        "maturity_tier": row.get("maturity_tier", "M0"),
        "source_family": row.get("source_family"),
        "selected_strategy": row.get("selected_strategy"),
        "adapter_capability": adapter_capability(req.platform, row),
        "adapter_ref": "subskills/S31C_内容平台事实采集/scripts/competitor_review_adapters.py",
        "items_count": 0,
        "candidate_url_count": 0,
        "quality_flags": [],
        "command_receipts": command_receipts or [],
        "zero_output_diagnosis": None,
        "session_preflight": session_preflight_policy(req),
    }


def parse_controlled_input(path: Path) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8", errors="replace")
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        if "\n" in text and any(line.strip().startswith("{") for line in text.splitlines()):
            rows = [json.loads(line) for line in text.splitlines() if line.strip()]
            return [row for row in rows if isinstance(row, dict)]
        title = extract_title(text)
        body = strip_html(text)[:2000]
        return [{"title": title, "body": body, "source_url": "", "data_quality_flags": ["controlled_html_input"]}]

    if isinstance(data, list):
        return [row for row in data if isinstance(row, dict)]
    if not isinstance(data, dict):
        return []
    for key in ("items", "records", "reviews", "comments", "data"):
        value = data.get(key)
        if isinstance(value, list):
            return [row for row in value if isinstance(row, dict)]
    return [data]


def skipped(req: AdapterRequest) -> tuple[dict[str, Any], dict[str, Any]]:
    row = baseline_row(req)
    receipt = receipt_base(req, "skipped")
    receipt["quality_flags"] = ["skipped_by_baseline"]
    receipt["zero_output_diagnosis"] = {
        "status": "stopped",
        "reason": row.get("skip_reason", "skipped_by_decision"),
        "live_retry_allowed": False,
    }
    pack = build_fact_pack(req, "skipped", [], receipt["command_receipts"])
    return receipt, pack


def discovery(req: AdapterRequest) -> tuple[dict[str, Any], dict[str, Any]]:
    query = quote_plus(req.query or req.url or req.item_id)
    urls = {
        "google": f"https://www.google.com/search?q={query}",
        "bing": f"https://www.bing.com/search?q={query}",
        "baidu": f"https://www.baidu.com/s?wd={query}",
    }
    receipt = receipt_base(req, "discovery_only")
    receipt["candidate_urls"] = [{"url": urls.get(req.platform, ""), "role": "candidate_url_search"}]
    receipt["candidate_url_count"] = len(receipt["candidate_urls"])
    receipt["quality_flags"] = ["search_discovery_not_fact"]
    pack = build_fact_pack(req, "discovery_only", [], receipt["command_receipts"])
    return receipt, pack


def controlled_required(req: AdapterRequest) -> tuple[dict[str, Any], dict[str, Any]]:
    receipt = receipt_base(req, "controlled_input_required")
    receipt["quality_flags"] = ["no_controlled_input", "live_not_attempted"]
    receipt["zero_output_diagnosis"] = {
        "status": "stopped",
        "reason": "controlled_input_required",
        "human_action_required": True,
        "live_retry_allowed": False,
    }
    pack = build_fact_pack(req, "controlled_input_required", [], receipt["command_receipts"])
    return receipt, pack


def controlled(req: AdapterRequest) -> tuple[dict[str, Any], dict[str, Any]]:
    assert req.controlled_input is not None
    rows = parse_controlled_input(req.controlled_input)
    items = [to_fact_item(row, req.platform) for row in rows]
    receipt = receipt_base(req, "ok")
    receipt["items_count"] = len(items)
    receipt["quality_flags"] = ["controlled_input"]
    receipt["command_receipts"].append(
        {"tool": "controlled_input", "path": str(req.controlled_input), "record_count": len(rows), "status": "ok"}
    )
    pack = build_fact_pack(req, "ok" if items else "empty", items, receipt["command_receipts"])
    return receipt, pack


def live_result(req: AdapterRequest, rows: list[dict[str, Any]], commands: list[dict[str, Any]]) -> tuple[dict[str, Any], dict[str, Any]]:
    items = [to_fact_item(row, req.platform) for row in rows]
    status = "ok" if items else "empty"
    session_preflight = session_preflight_policy(req)
    if items and session_preflight["required"]:
        session_preflight["status"] = "passed"
    blocker_reason = command_blocker_reason(commands)
    if not items and (session_preflight["required"] or blocker_reason):
        status = "session_preflight_blocked"
        session_preflight["status"] = "blocked"
        blocker_reason = blocker_reason or "session_not_verified_empty_output"
    receipt = receipt_base(req, status, commands)
    receipt["items_count"] = len(items)
    receipt["session_preflight"] = session_preflight
    if not items:
        if status == "session_preflight_blocked":
            receipt["quality_flags"] = ["zero_rows", "session_preflight_blocked"]
            receipt["zero_output_diagnosis"] = session_blocked_diagnosis(blocker_reason)
        else:
            receipt["quality_flags"] = ["zero_rows"]
            receipt["zero_output_diagnosis"] = {"status": "stopped", "reason": "zero_rows", "live_retry_allowed": False}
    pack = build_fact_pack(req, status, items, commands)
    return receipt, pack


def controlled_schema_adapter(
    req: AdapterRequest,
    parser: Callable[[list[dict[str, Any]]], list[dict[str, Any]]],
    schema_label: str,
    *,
    platform: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Adapter that parses controlled input rows through a platform-specific parser."""
    if req.controlled_input is None:
        return controlled_required(req)
    raw_rows = parse_controlled_input(req.controlled_input)
    parsed = parser(raw_rows)
    plat = platform or req.platform
    items = [to_fact_item(row, plat) for row in parsed]
    receipt = receipt_base(req, "ok" if items else "empty")
    receipt["items_count"] = len(items)
    receipt["quality_flags"] = ["controlled_input", schema_label]
    receipt["command_receipts"].append(
        {"tool": "controlled_input", "path": str(req.controlled_input), "record_count": len(raw_rows), "parser": schema_label, "status": "ok"}
    )
    if not items:
        friction = next(
            (
                as_text(row.get("friction_state") or row.get("friction") or row.get("reason"))
                for row in raw_rows
                if as_text(row.get("friction_state") or row.get("friction") or row.get("reason"))
            ),
            "",
        )
        if friction:
            receipt["quality_flags"].append("controlled_input_friction")
            receipt["zero_output_diagnosis"] = {
                "status": "stopped",
                "reason": friction,
                "human_action_required": True,
                "live_retry_allowed": False,
            }
    pack = build_fact_pack(req, "ok" if items else "empty", items, receipt["command_receipts"])
    return receipt, pack


# ---------------------------------------------------------------------------
# OpenCLI helpers (added post-commit for adapter support)
# ---------------------------------------------------------------------------

def opencli_executable() -> str:
    return shutil.which("opencli.cmd") or shutil.which("opencli.exe") or shutil.which("opencli") or "opencli"


def opencli_profile_args(platform: str) -> list[str]:
    env_name = f"S31C_OPENCLI_PROFILE_{re.sub(r'[^A-Z0-9]+', '_', platform.upper()).strip('_')}"
    profile = os.environ.get(env_name)
    return ["--profile", profile] if profile else []


OPENCLI_DEFAULT_TIMEOUT = 90.0


def opencli_error_type(text: str) -> tuple[str, str]:
    """Classify opencli error text into (error_type, friction_type).

    Returns a 2-tuple where the second element is a friction label for
    receipt tagging (empty string if no friction applies).
    """
    lowered = text.lower()
    # Captcha / slider / security challenge
    if any(tok in lowered for tok in (
        "captcha", "slider", "验证码", "滑块", "安全验证",
        "yoda", "verify", "_$jsvmprt", "异常访问",
    )):
        return "captcha_challenge", "captcha_challenge"
    # Auth / login required
    if any(tok in lowered for tok in (
        "login", "session expired", "auth", "unauthorized", "登录",
        "未登录", "请先登录", "请登录", "sign-in", "login-modal",
    )):
        return "auth_required", "session_expired"
    # Weibo visitor system loop
    if "passport.weibo.com/visitor" in lowered or "sina visitor system" in lowered:
        return "auth_required", "visitor_system_loop"
    # OpenCLI command not registered
    if "unknown command" in lowered or "error: command" in lowered:
        return "opencli_command_not_registered", ""
    return "opencli_command_failed", ""


def run_opencli_json(
    argv: list[str],
    *,
    timeout: float = OPENCLI_DEFAULT_TIMEOUT,
    provider: str = "opencli_platform_adapter",
) -> tuple[Any | None, dict[str, Any]]:
    """Run an opencli CLI command and return (parsed_json, receipt).

    This is the **single** place in the codebase where opencli subprocesses
    are launched.  All platform adapters MUST use this function instead of
    rolling their own subprocess.run wrappers.
    """
    receipt: dict[str, Any] = {
        "tool": "opencli",
        "provider": provider,
        "argv": argv,
        "status": "planned",
    }
    try:
        result = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    except FileNotFoundError as exc:
        receipt.update({"status": "failed", "error_type": "opencli_unavailable", "error": str(exc)[:300]})
        return None, receipt
    except subprocess.TimeoutExpired:
        receipt.update({"status": "timeout", "error_type": "opencli_timeout", "error": "opencli command timed out"})
        return None, receipt
    except Exception as exc:  # noqa: BLE001 – must capture any external failure
        receipt.update({"status": "failed", "error_type": type(exc).__name__, "error": str(exc)[:300]})
        return None, receipt

    receipt.update({
        "status": "ok" if result.returncode == 0 else "failed",
        "returncode": result.returncode,
        "stderr_tail": (result.stderr or "")[-500:],
    })
    if result.returncode != 0:
        error_type, friction_type = opencli_error_type(f"{result.stderr}\n{result.stdout}")
        receipt.update({"error_type": error_type, "error": error_type})
        if friction_type:
            receipt["friction_type"] = friction_type
        return None, receipt
    stdout = (result.stdout or "").strip()
    if not stdout:
        return [], receipt
    try:
        return json.loads(stdout), receipt
    except json.JSONDecodeError as exc:
        error_type, friction_type = opencli_error_type(stdout)
        if error_type == "opencli_command_failed":
            error_type = "opencli_invalid_json"
        receipt.update({"status": "failed", "error_type": error_type, "error": str(exc)[:300]})
        if friction_type:
            receipt["friction_type"] = friction_type
        return None, receipt


def opencli_hard_stop(commands: list[dict[str, Any]]) -> bool:
    """Return True if any receipt indicates a non-retryable error."""
    hard_errors = {
        "opencli_unavailable",
        "opencli_command_not_registered",
        "opencli_command_failed",
        "opencli_timeout",
        "opencli_invalid_json",
        "auth_required",
        "captcha_challenge",
    }
    return any(as_text(cmd.get("error_type")) in hard_errors for cmd in commands)


def session_preflight_policy(req: AdapterRequest) -> dict[str, Any]:
    row = baseline_row(req)
    capability = adapter_capability(req.platform, row)
    friction = as_text(row.get("known_friction")).lower()
    requires = capability not in {"skipped_receipt_adapter", "discovery_adapter"} and (
        req.platform in SESSION_PREFLIGHT_PLATFORMS
        or any(token in friction for token in ["登录", "風控", "风控", "captcha", "auth", "login", "qr"])
    )
    return {
        "required": requires,
        "status": "not_run" if requires else "not_required",
        "rule": "Run platform login/session health preflight before live crawling.",
        "blocking_reasons": [
            "auth_required", "qr_code_challenge", "captcha_challenge",
            "sms_verification", "risk_control", "blank_page",
            "system_busy", "session_not_verified_empty_output",
        ],
    }


def command_blocker_reason(commands: list[dict[str, Any]]) -> str:
    text = "\n".join(as_text(command) for command in commands).lower()
    patterns = [
        (r"qr|二维码|扫码", "qr_code_challenge"),
        (r"captcha|验证码|滑块|安全验证|verify.*human|human.*verify", "captcha_challenge"),
        (r"sms|短信", "sms_verification"),
        (r"auth_required|login|required|登录|unauthorized|session.*expired|sign-?in|signin", "auth_required"),
        (r"risk|rate.?limited|风控|账号异常|security|robot check|forbidden|http error 403|precondition failed|http error 412", "risk_control"),
        (r"system_busy|系统繁忙|busy", "system_busy"),
        (r"blank|空白|unready", "blank_page"),
    ]
    for pattern, reason in patterns:
        if re.search(pattern, text, flags=re.I):
            return reason
    return ""


def session_blocked_diagnosis(reason: str, *, last_visible_state: str = "") -> dict[str, Any]:
    requires_login = reason in {
        "auth_required", "qr_code_challenge", "captcha_challenge",
        "sms_verification", "session_not_verified_empty_output",
    }
    return {
        "status": "stopped",
        "reason": reason,
        "last_visible_state": last_visible_state,
        "human_action_required": True,
        "requires_human_login": requires_login,
        "live_retry_allowed": False,
        "empty_result_is_not_no_data": True,
    }


# ---------------------------------------------------------------------------
# Platform data schema helpers (platform_fields infrastructure)
# ---------------------------------------------------------------------------

def load_platform_schema() -> dict[str, Any]:
    """Load and cache the platform data schema."""
    global _PLATFORM_SCHEMA_CACHE  # noqa: PLW0603
    if _PLATFORM_SCHEMA_CACHE is not None:
        return _PLATFORM_SCHEMA_CACHE
    if not PLATFORM_SCHEMA_PATH.exists():
        _PLATFORM_SCHEMA_CACHE = {}
        return _PLATFORM_SCHEMA_CACHE
    try:
        import yaml  # type: ignore
        _PLATFORM_SCHEMA_CACHE = yaml.safe_load(PLATFORM_SCHEMA_PATH.read_text(encoding="utf-8")) or {}
    except Exception:  # noqa: BLE001
        _PLATFORM_SCHEMA_CACHE = {}
    return _PLATFORM_SCHEMA_CACHE


def platform_field_keys(platform: str) -> dict[str, dict[str, Any]]:
    """Return the platform_fields schema for a given platform."""
    schema = load_platform_schema()
    platform_def = (schema.get("platforms") or {}).get(platform) or {}
    return platform_def.get("platform_fields") or {}


def extract_platform_fields(raw: dict[str, Any], platform: str) -> dict[str, Any]:
    """Extract platform-specific fields from raw adapter output."""
    field_defs = platform_field_keys(platform)
    if not field_defs:
        return {}
    sources: dict[str, Any] = {}
    sources.update(raw)
    sources.update(raw.get("metrics") or {})
    sources.update(raw.get("platform_fields") or {})
    result: dict[str, Any] = {}
    for field_name, field_def in field_defs.items():
        value = sources.get(field_name)
        if value is None or value == "":
            continue
        expected_type = field_def.get("type", "string") if isinstance(field_def, dict) else "string"
        if expected_type == "int":
            parsed = safe_int(value)
            if parsed is not None:
                result[field_name] = parsed
        elif expected_type == "float":
            try:
                result[field_name] = float(value)
            except (ValueError, TypeError):
                pass
        elif expected_type == "bool":
            result[field_name] = bool(value)
        elif expected_type.startswith("list"):
            if isinstance(value, list):
                result[field_name] = value
        else:
            result[field_name] = as_text(value)
    return result


def validate_platform_fields(platform_fields: dict[str, Any], platform: str) -> list[str]:
    """Return list of missing required fields for quality flagging."""
    field_defs = platform_field_keys(platform)
    missing = []
    for field_name, field_def in field_defs.items():
        if isinstance(field_def, dict) and field_def.get("required") and field_name not in platform_fields:
            missing.append(field_name)
    return missing

