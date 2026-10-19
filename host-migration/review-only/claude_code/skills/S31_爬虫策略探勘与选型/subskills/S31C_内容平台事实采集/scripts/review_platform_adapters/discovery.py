"""Enhanced search discovery adapters for Baidu, Bing, and Google."""

from __future__ import annotations

import html as html_lib
import json
import re
import shutil
import subprocess
import uuid
from urllib.parse import parse_qs, quote_plus, urljoin, urlparse
from urllib.request import Request, urlopen

from .common import AdapterRequest, build_fact_pack, receipt_base, strip_html, to_fact_item
from .public_article import article_rows_from_html


SEARCH_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36"
)
OPENCLI_TIMEOUT_SECONDS = 45
HYDRATE_SEARCH_RESULTS = True
HYDRATE_RESULT_LIMIT = 3


def _opencli_executable() -> str:
    return shutil.which("opencli.cmd") or shutil.which("opencli") or "opencli"


def http_get(url: str, *, as_json: bool, timeout: float = 15.0) -> tuple[object | None, dict]:
    baiduid = f"{uuid.uuid4().hex.upper()}:FG=1"
    request = Request(
        url,
        headers={
            "User-Agent": SEARCH_USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.6",
            "Cookie": f"BAIDUID={baiduid}; BIDUPSID={baiduid[:32]}; PSTM=1710000000; BD_UPN=12314753",
            "Referer": "https://www.baidu.com/",
            "Upgrade-Insecure-Requests": "1",
        },
    )
    receipt = {"url": url, "method": "GET", "user_agent_family": "browser", "cookie_bootstrap": True}
    try:
        with urlopen(request, timeout=timeout) as response:
            payload = response.read()
            receipt.update({"status": "ok", "status_code": response.status, "bytes": len(payload), "final_url": response.geturl()})
            text = payload.decode("utf-8", errors="replace")
            if as_json:
                return json.loads(text), receipt
            return text, receipt
    except Exception as exc:  # noqa: BLE001 - external search failures must be preserved.
        receipt.update({"status": "failed", "error_type": type(exc).__name__, "error": str(exc)[:300]})
        return None, receipt


def _normalize_href(raw_href: str, source_url: str) -> str:
    href = html_lib.unescape(raw_href.strip())
    if not href or href.startswith(("#", "javascript:", "mailto:")):
        return ""
    url = urljoin(source_url, href)
    parsed = urlparse(url)
    if parsed.netloc.lower().endswith("google.com") and parsed.path.lower() == "/url":
        target = parse_qs(parsed.query).get("q", [""])[0]
        if target.startswith(("http://", "https://")):
            url = html_lib.unescape(target)
    parsed = urlparse(url)
    return url if parsed.scheme in {"http", "https"} and parsed.netloc else ""


def _is_internal_search_url(url: str) -> bool:
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    path = parsed.path.lower()
    if host.endswith("baidu.com") and path.startswith("/link"):
        return False
    if host.endswith("baidu.com") and path == "/s":
        return True
    if host.endswith("google.com"):
        return True
    return host.endswith("bing.com") and path == "/search"


def _is_low_value_search_result(url: str, title: str, source_url: str) -> bool:
    source_host = urlparse(source_url).netloc.lower()
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    path = parsed.path.lower()
    if source_host.endswith("baidu.com"):
        baidu_noise_tokens = ("百度图片", "查看全部", "免费AI生图", "变清晰")
        if any(token in title for token in baidu_noise_tokens):
            return True
        return not (host.endswith("baidu.com") and path.startswith("/link"))
    noise_titles = {"feedback", "百度首页", "hao123", "更多产品", "设置", "登录"}
    return title.strip() in noise_titles


def _risk_control_reason(text: str, command: dict) -> str:
    if command.get("status") == "failed":
        error = f"{command.get('error_type', '')} {command.get('error', '')}".lower()
        return "http_403_or_blocked" if "403" in error else "http_get_failed"
    lowered = text.lower()
    if re.search(r"did not match any documents|没有找到|未找到相关结果|找不到和.*相关", lowered, flags=re.I):
        return "search_no_results"
    patterns = [
        (r"/sorry/index|captcha|unusual traffic|verify you.?re human|verify.*human", "captcha_challenge"),
        (r"百度安全验证|请输入验证码|安全验证", "captcha_challenge"),
        (r"rate.?limited|too many requests|风控|账号异常|security check", "risk_control"),
    ]
    for pattern, reason in patterns:
        if re.search(pattern, lowered, flags=re.I):
            return reason
    return ""


def _looks_like_baidu_https_redirect(text: str, search_url: str) -> bool:
    return (
        search_url.startswith("https://www.baidu.com/")
        and "location.replace" in text
        and 'replace("https://","http://")' in text
    )


def _dedupe_results(results: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[str] = set()
    unique: list[dict[str, str]] = []
    for row in results:
        if row["url"] in seen:
            continue
        seen.add(row["url"])
        unique.append(row)
    return unique[:20]


def _parse_baidu_html(text: str, source_url: str) -> list[dict[str, str]]:
    results: list[dict[str, str]] = []
    pattern = r'(?is)<h3[^>]*>\s*<a[^>]+href=["\']?([^"\'>\s]+)["\']?[^>]*>(.*?)</a>\s*</h3>'
    for match in re.finditer(pattern, text):
        url = _normalize_href(match.group(1), source_url)
        title = strip_html(match.group(2)).strip()
        if not url or not title or _is_low_value_search_result(url, title, source_url):
            continue
        tail = text[match.end() : match.end() + 1500]
        snippet_match = re.search(r'(?is)<(?:span|div)[^>]+class=["\'][^"\']*(?:content|c-abstract|summary)[^"\']*["\'][^>]*>(.*?)</(?:span|div)>', tail)
        snippet = strip_html(snippet_match.group(1))[:500] if snippet_match else ""
        results.append({"title": title, "snippet": snippet, "url": url})
    return _dedupe_results(results)


def _parse_bing_html(text: str, source_url: str) -> list[dict[str, str]]:
    results: list[dict[str, str]] = []
    for match in re.finditer(r'(?is)<li[^>]+class=["\'][^"\']*b_algo[^"\']*["\'][^>]*>(.*?)</li>', text):
        block = match.group(1)
        title_match = re.search(r'(?is)<h2[^>]*>\s*<a[^>]+href=["\']?([^"\'>\s]+)["\']?[^>]*>(.*?)</a>\s*</h2>', block)
        if not title_match:
            continue
        url = _normalize_href(title_match.group(1), source_url)
        title = strip_html(title_match.group(2)).strip()
        if not url or not title or _is_internal_search_url(url):
            continue
        snippet_match = re.search(r"(?is)<p[^>]*>(.*?)</p>", block)
        snippet = strip_html(snippet_match.group(1))[:500] if snippet_match else ""
        results.append({"title": title, "snippet": snippet, "url": url})
    return _dedupe_results(results)


def _parse_google_html(text: str, source_url: str) -> list[dict[str, str]]:
    if _risk_control_reason(text, {"status": "ok"}) == "captcha_challenge":
        return []
    results: list[dict[str, str]] = []
    pattern = r'(?is)<div[^>]+class=["\'][^"\']*(?:tF2Cxc|yuRUbf|g)[^"\']*["\'][^>]*>(.*?)(?=<div[^>]+class=["\'][^"\']*(?:tF2Cxc|yuRUbf|g)[^"\']*["\']|</body>)'
    for match in re.finditer(pattern, text):
        block = match.group(1)
        link_match = re.search(r'(?is)<a[^>]+href=["\']?([^"\'>\s]+)["\']?[^>]*>', block)
        title_match = re.search(r"(?is)<h3[^>]*>(.*?)</h3>", block)
        if not link_match or not title_match:
            continue
        url = _normalize_href(link_match.group(1), source_url)
        title = strip_html(title_match.group(1)).strip()
        if not url or not title or _is_internal_search_url(url):
            continue
        snippet_match = re.search(r'(?is)<(?:span|div)[^>]+class=["\'][^"\']*(?:aCOpRe|VwiC3b|st)[^"\']*["\'][^>]*>(.*?)</(?:span|div)>', block)
        snippet = strip_html(snippet_match.group(1))[:500] if snippet_match else ""
        results.append({"title": title, "snippet": snippet, "url": url})
    return _dedupe_results(results)


def _parse_search_results_generic(text: str, source_url: str) -> list[dict[str, str]]:
    results: list[dict[str, str]] = []
    pattern = r'(?is)<a[^>]*href=["\']?([^"\'>\s]+)["\']?[^>]*>(.*?)</a>'
    for match in re.finditer(pattern, text):
        url = _normalize_href(match.group(1), source_url)
        if not url or _is_internal_search_url(url):
            continue
        title = strip_html(match.group(2)).strip()
        if not title or len(title) < 3:
            continue
        if _is_low_value_search_result(url, title, source_url):
            continue
        snippet = ""
        tail = text[match.end() : match.end() + 1200]
        snippet_match = re.search(r"(?is)<(?:p|span|div)[^>]*>(.*?)</(?:p|span|div)>", tail)
        if snippet_match:
            snippet = strip_html(snippet_match.group(1))[:500]
        results.append({"title": title, "snippet": snippet, "url": url})

    return _dedupe_results(results)


def _parse_search_results(text: str, source_url: str) -> list[dict[str, str]]:
    host = urlparse(source_url).netloc.lower()
    if host.endswith("baidu.com"):
        return _dedupe_results(_parse_baidu_html(text, source_url) + _parse_search_results_generic(text, source_url))
    if host.endswith("bing.com"):
        return _dedupe_results(_parse_bing_html(text, source_url) + _parse_search_results_generic(text, source_url))
    if host.endswith("google.com"):
        google_rows = _parse_google_html(text, source_url)
        return google_rows or _parse_search_results_generic(text, source_url)
    return _parse_search_results_generic(text, source_url)


def _search_candidate_from_mapping(raw: dict, quality_flag: str) -> dict[str, str] | None:
    url = html_lib.unescape(str(raw.get("url") or raw.get("link") or raw.get("source_url") or "").strip())
    title = strip_html(str(raw.get("title") or raw.get("name") or raw.get("headline") or ""))
    snippet = strip_html(str(raw.get("snippet") or raw.get("body") or raw.get("abstract") or raw.get("content") or raw.get("summary") or ""))
    if not url or not title:
        return None
    return {"url": url, "title": title, "snippet": snippet[:500], "role": "search_result", "quality_flag": quality_flag}


def _search_candidates_from_payload(payload: object, quality_flag: str) -> list[dict[str, str]]:
    if isinstance(payload, dict):
        for key in ("candidate_urls", "results", "items", "rows", "data"):
            value = payload.get(key)
            if isinstance(value, list):
                payload = value
                break
        else:
            payload = [payload]
    if not isinstance(payload, list):
        return []

    rows: list[dict[str, str]] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        row = _search_candidate_from_mapping(item, quality_flag)
        if row:
            rows.append(row)
    return rows


def _opencli_search_candidates(engine: str, req: AdapterRequest) -> tuple[list[dict[str, str]], list[dict]]:
    if engine != "google":
        return [], []
    query = req.query or req.url or req.item_id
    argv = [
        _opencli_executable(),
        engine,
        "search",
        query,
        "--limit",
        str(req.limit),
        "--lang",
        "zh",
        "-f",
        "json",
        "--window",
        "background",
        "--site-session",
        "ephemeral",
    ]
    receipt = {"tool": "opencli_browser_search", "engine": engine, "argv": argv}
    try:
        proc = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=OPENCLI_TIMEOUT_SECONDS,
            check=False,
        )
    except FileNotFoundError as exc:
        receipt.update({"status": "failed", "error_type": type(exc).__name__, "error": str(exc)[:300]})
        return [], [receipt]
    except subprocess.TimeoutExpired as exc:
        receipt.update({"status": "timeout", "timeout_seconds": OPENCLI_TIMEOUT_SECONDS, "error": str(exc)[:300]})
        return [], [receipt]

    stdout = proc.stdout or ""
    stderr = proc.stderr or ""
    receipt.update(
        {
            "status": "ok" if proc.returncode == 0 else "failed",
            "returncode": proc.returncode,
            "stdout_bytes": len(stdout.encode("utf-8", errors="replace")),
            "stderr": stderr[:300],
        }
    )
    if proc.returncode != 0:
        if "NOT_FOUND" in stderr or "No search results found" in stderr:
            receipt["status"] = "not_found"
            receipt["zero_output_reason"] = "search_no_results"
        return [], [receipt]
    if not stdout.strip():
        return [], [receipt]
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError:
        receipt["parse_status"] = "non_json_stdout"
        return [], [receipt]
    rows = _search_candidates_from_payload(payload, f"{engine}_opencli_search_result")
    receipt["parsed_count"] = len(rows)
    return rows[: req.limit], [receipt]


def _fetch_search_candidates(search_url: str, attempted: set[str]) -> tuple[list[dict[str, str]], list[dict], str]:
    commands: list[dict] = []
    if search_url in attempted:
        return [], commands, ""
    attempted.add(search_url)
    text, cmd = http_get(search_url, as_json=False)
    commands.append(cmd)
    active_url = search_url
    if isinstance(text, str) and _looks_like_baidu_https_redirect(text, search_url):
        redirect_url = search_url.replace("https://", "http://", 1)
        if redirect_url not in attempted:
            attempted.add(redirect_url)
            text, redirect_cmd = http_get(redirect_url, as_json=False)
            commands.append(redirect_cmd)
            active_url = redirect_url
    candidate_urls: list[dict[str, str]] = []
    if isinstance(text, str) and text:
        candidate_urls = [
            {"url": row["url"], "title": row["title"], "snippet": row["snippet"], "role": "search_result"}
            for row in _parse_search_results(text, active_url)
        ]
    risk_reason = _risk_control_reason(text if isinstance(text, str) else "", commands[-1])
    return candidate_urls, commands, risk_reason


def _hydrate_candidate_pages(req: AdapterRequest, candidate_urls: list[dict[str, str]]) -> tuple[list[dict], list[dict]]:
    rows: list[dict] = []
    commands: list[dict] = []
    limit = min(req.limit, HYDRATE_RESULT_LIMIT, len(candidate_urls))
    for index, candidate in enumerate(candidate_urls[:limit], start=1):
        url = candidate.get("url", "")
        if not url:
            continue
        text, cmd = http_get(url, as_json=False)
        cmd.update({"tool": "search_candidate_detail_fetch", "candidate_rank": index, "candidate_url": url})
        commands.append(cmd)
        if not isinstance(text, str) or not text:
            continue
        detail_url = str(cmd.get("final_url") or url)
        for row in article_rows_from_html(text, detail_url):
            flags = set(row.get("data_quality_flags") or [])
            flags.update({"search_candidate_hydrated", f"{req.platform}_search_to_fact"})
            row["data_quality_flags"] = sorted(flags)
            row["search_candidate_url"] = url
            row["search_candidate_title"] = candidate.get("title", "")
            row["search_candidate_snippet"] = candidate.get("snippet", "")
            row["search_candidate_rank"] = index
            rows.append(row)
            break
    return rows, commands


def _discovery_enhanced(req: AdapterRequest, search_urls: str | list[str]) -> tuple[dict, dict]:
    urls = [search_urls] if isinstance(search_urls, str) else search_urls
    commands: list[dict] = []
    candidate_urls: list[dict[str, str]] = []
    risk_reason = ""
    attempted: set[str] = set()
    if req.platform in {"baidu", "bing", "google"}:
        candidate_urls, opencli_commands = _opencli_search_candidates(req.platform, req)
        commands.extend(opencli_commands)
        risk_reason = next((cmd.get("zero_output_reason", "") for cmd in opencli_commands if cmd.get("zero_output_reason")), "")
    for search_url in urls:
        if candidate_urls or risk_reason == "search_no_results":
            break
        candidate_urls, batch_commands, batch_risk = _fetch_search_candidates(search_url, attempted)
        commands.extend(batch_commands)
        risk_reason = batch_risk or risk_reason
        if candidate_urls:
            break

    hydrated_rows: list[dict] = []
    if candidate_urls and HYDRATE_SEARCH_RESULTS:
        hydrated_rows, hydrate_commands = _hydrate_candidate_pages(req, candidate_urls)
        commands.extend(hydrate_commands)
    if hydrated_rows:
        items = [to_fact_item(row, req.platform) for row in hydrated_rows[: req.limit]]
        receipt = receipt_base(req, "ok", commands)
        receipt["maturity_tier"] = "M4"
        receipt["adapter_capability"] = "search_to_fact_adapter"
        receipt["candidate_urls"] = candidate_urls
        receipt["candidate_url_count"] = len(candidate_urls)
        receipt["items_count"] = len(items)
        receipt["quality_flags"] = ["search_discovery_structured", "search_hydrated_fact_items", f"{req.platform}_m4_search_to_fact"]
        pack = build_fact_pack(req, "ok", items, commands)
        pack["candidate_urls"] = candidate_urls
        pack["fact_summary"]["maturity_tier"] = "M4"
        pack["fact_summary"]["adapter_capability"] = "search_to_fact_adapter"
        return receipt, pack

    receipt = receipt_base(req, "discovery_only")
    no_results = risk_reason == "search_no_results"
    receipt["candidate_urls"] = candidate_urls or ([] if no_results else [{"url": urls[0], "role": "candidate_url_search"}])
    receipt["candidate_url_count"] = len(receipt["candidate_urls"])
    receipt["quality_flags"] = ["search_discovery_structured" if candidate_urls else ("search_no_results" if no_results else "search_discovery_not_fact")]
    if not candidate_urls:
        receipt["zero_output_diagnosis"] = {
            "status": "stopped",
            "reason": risk_reason or "search_discovery_not_fact",
            "human_action_required": bool(risk_reason and not no_results),
            "requires_human_login": False,
            "live_retry_allowed": False,
            "empty_result_is_not_no_data": bool(risk_reason and not no_results),
        }
        if risk_reason and not no_results:
            receipt["quality_flags"].append("risk_control_or_search_blocked")
    receipt["command_receipts"] = commands
    pack = build_fact_pack(req, "discovery_only", [], commands)
    pack["candidate_urls"] = candidate_urls
    return receipt, pack


def live_baidu(req: AdapterRequest) -> tuple[dict, dict]:
    query = quote_plus(req.query or req.url or req.item_id)
    return _discovery_enhanced(req, [f"https://www.baidu.com/s?wd={query}", f"http://www.baidu.com/s?wd={query}"])


def live_bing(req: AdapterRequest) -> tuple[dict, dict]:
    query = quote_plus(req.query or req.url or req.item_id)
    return _discovery_enhanced(req, f"https://www.bing.com/search?q={query}")


def live_google(req: AdapterRequest) -> tuple[dict, dict]:
    query = quote_plus(req.query or req.url or req.item_id)
    return _discovery_enhanced(req, f"https://www.google.com/search?q={query}")
