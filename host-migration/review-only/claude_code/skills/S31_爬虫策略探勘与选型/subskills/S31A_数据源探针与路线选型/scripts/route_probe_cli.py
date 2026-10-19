from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen


SKILL_DIR = Path(__file__).resolve().parents[1]
DEFAULT_OPENCLI_MAP = SKILL_DIR / "resources" / "opencli_capability_map.md"


def read_text(path: Path | None) -> str:
    if not path:
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def is_http_url(value: str) -> bool:
    return urlparse(value).scheme in {"http", "https"}


def http_get(url: str, timeout: float) -> dict:
    request = Request(
        url,
        headers={
            "User-Agent": "S31A-route-probe/1.0",
            "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
        },
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            body = response.read(512_000)
            encoding = response.headers.get_content_charset() or "utf-8"
            return {
                "status": "ok",
                "url": response.geturl(),
                "status_code": response.status,
                "content_type": response.headers.get("Content-Type", ""),
                "body": body.decode(encoding, errors="replace"),
                "body_bytes": len(body),
            }
    except HTTPError as exc:
        body = exc.read(16_384)
        return {
            "status": "http_error",
            "url": url,
            "status_code": exc.code,
            "content_type": exc.headers.get("Content-Type", "") if exc.headers else "",
            "body": body.decode("utf-8", errors="replace"),
            "body_bytes": len(body),
            "error": str(exc),
        }
    except (URLError, TimeoutError, OSError) as exc:
        return {
            "status": "failed",
            "url": url,
            "status_code": None,
            "content_type": "",
            "body": "",
            "body_bytes": 0,
            "error": str(exc),
        }


def summarize_http_probe(probe: dict) -> dict:
    return {key: value for key, value in probe.items() if key != "body"}


def safe_target_id(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip().lower()).strip("_")
    return cleaned or "unknown"


def platform_from_target(target: str) -> str:
    parsed = urlparse(target)
    host = parsed.netloc or parsed.path
    host = host.split("@")[-1].split(":")[0].lower()
    if host.startswith("www."):
        host = host[4:]
    if not host:
        return safe_target_id(target)
    parts = host.split(".")
    if len(parts) >= 2:
        return parts[-2]
    return safe_target_id(host)


def capability_map_has_adapter(map_text: str, platform: str) -> bool:
    if not map_text or not platform:
        return False
    needle = platform.lower()
    aliases = {
        "rednote": "xiaohongshu",
        "xhs": "xiaohongshu",
        "youtube": "youtube",
        "bilibili": "bilibili",
        "dianping": "dianping",
    }
    candidates = {needle, aliases.get(needle, needle)}
    for candidate in candidates:
        table_pattern = re.compile(rf"^\|\s*{re.escape(candidate)}\s*\|", re.IGNORECASE | re.MULTILINE)
        if table_pattern.search(map_text):
            return True
    return False


def detect_ssr_state(html: str) -> tuple[str, str | None]:
    markers = [
        ("__NEXT_DATA__", "next_data"),
        ("__NUXT__", "nuxt_state"),
        ("window.__INITIAL_STATE__", "initial_state"),
        ("application/ld+json", "json_ld"),
    ]
    for marker, name in markers:
        if marker in html:
            return "available", name
    return "not_found", None


def detect_api_hint(html: str) -> tuple[str, str | None]:
    patterns = [
        (r"\bfetch\s*\(", "fetch_call"),
        (r"\bXMLHttpRequest\b", "xhr_call"),
        (r"['\"]/(?:api|graphql|ajax|rest)/", "api_path"),
        (r"application/json", "json_response_hint"),
    ]
    for pattern, name in patterns:
        if re.search(pattern, html, re.IGNORECASE):
            return "hint_found", name
    return "not_found", None


def extract_api_candidates(html: str, base_url: str, limit: int) -> list[str]:
    candidates: list[str] = []
    patterns = [
        r"\bfetch\s*\(\s*['\"]([^'\"]+)['\"]",
        r"\bXMLHttpRequest\b.*?\.open\s*\(\s*['\"](?:GET|POST)['\"]\s*,\s*['\"]([^'\"]+)['\"]",
        r"['\"]((?:https?://|/)[^'\"]*(?:api|graphql|ajax|rest)[^'\"]*)['\"]",
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, html, re.IGNORECASE | re.DOTALL):
            url = match.group(1).strip()
            if not url or url.startswith(("data:", "javascript:")):
                continue
            resolved = urljoin(base_url, url)
            if resolved not in candidates:
                candidates.append(resolved)
            if len(candidates) >= limit:
                return candidates
    return candidates


def looks_like_json(probe: dict) -> bool:
    content_type = (probe.get("content_type") or "").lower()
    body = (probe.get("body") or "").lstrip()
    return "json" in content_type or body.startswith("{") or body.startswith("[")


def probe_json_api(candidates: list[str], timeout: float) -> tuple[str, str | None, list[dict]]:
    probes: list[dict] = []
    for url in candidates:
        probe = http_get(url, timeout)
        probes.append(summarize_http_probe(probe))
        if probe.get("status") == "ok" and looks_like_json(probe):
            return "available", url, probes
    if probes:
        return "hint_found", candidates[0], probes
    return "not_found", None, probes


def run_opencli_help(opencli: str, platform: str, timeout: float) -> dict:
    argv = [opencli, platform, "--help"]
    try:
        proc = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
        return {
            "tool": "opencli_help",
            "argv": argv,
            "exit_code": proc.returncode,
            "stdout_summary": (proc.stdout or "")[:500],
            "stderr_summary": (proc.stderr or "")[:500],
            "status": "ok" if proc.returncode == 0 else "failed",
        }
    except FileNotFoundError:
        return {
            "tool": "opencli_help",
            "argv": argv,
            "exit_code": None,
            "status": "failed",
            "failure_reason": "opencli_not_found",
        }
    except subprocess.TimeoutExpired:
        return {
            "tool": "opencli_help",
            "argv": argv,
            "exit_code": None,
            "status": "failed",
            "failure_reason": "timeout",
        }


def choose_next_node(collection_mode: str, selected_strategy: str) -> str:
    if selected_strategy == "opencli" and collection_mode == "content_mining_analysis_summary":
        return "S31C"
    if selected_strategy in {"api", "ssr_json", "browser"}:
        return "S31D"
    return "P2"


def build_receipt(args: argparse.Namespace) -> dict:
    target = args.target or args.url or args.platform
    if not target:
        raise SystemExit("--target, --url, or --platform is required")
    platform = args.platform or platform_from_target(target)
    html = read_text(args.html_file)
    http_probe = {"status": "not_run", "url": target}
    if not html and not args.no_http_probe and is_http_url(target):
        fetched = http_get(target, args.timeout)
        http_probe = summarize_http_probe(fetched)
        if fetched.get("status") == "ok":
            html = fetched.get("body", "")
    map_text = read_text(args.opencli_capability_map)

    opencli_available = capability_map_has_adapter(map_text, platform)
    opencli_receipt = {
        "status": "available_from_capability_map" if opencli_available else "not_found_in_capability_map",
        "capability_map": str(args.opencli_capability_map.resolve()) if args.opencli_capability_map else None,
        "platform": platform,
    }
    command_receipts: list[dict] = []
    if args.run_opencli_help:
        command_receipt = run_opencli_help(args.opencli, platform, args.timeout)
        command_receipts.append(command_receipt)
        if command_receipt.get("status") == "ok":
            opencli_available = True
            opencli_receipt["status"] = "available_from_command"

    api_status, api_marker = detect_api_hint(html)
    api_candidates: list[str] = []
    api_probes: list[dict] = []
    if args.api_evidence:
        api_status, api_marker = "evidence_provided", args.api_evidence
    elif html and is_http_url(target) and args.max_api_probes > 0:
        api_candidates = extract_api_candidates(html, str(http_probe.get("url") or target), args.max_api_probes)
        probed_status, probed_marker, api_probes = probe_json_api(api_candidates, args.timeout)
        if probed_status == "available" or api_status == "not_found":
            api_status, api_marker = probed_status, probed_marker
    ssr_status, ssr_marker = detect_ssr_state(html)

    if opencli_available:
        selected_strategy = "opencli"
        reason = "OpenCLI adapter or command surface is available for the target platform."
    elif api_status in {"available", "evidence_provided", "hint_found"}:
        selected_strategy = "api"
        reason = "Structured API evidence is available or strongly hinted in the page."
    elif ssr_status == "available":
        selected_strategy = "ssr_json"
        reason = "SSR state JSON is present in the provided HTML evidence."
    else:
        selected_strategy = "browser"
        reason = "No OpenCLI, API, or SSR evidence was found; browser probing is the fallback."

    next_node = choose_next_node(args.collection_mode, selected_strategy)
    return {
        "schema_version": "s31a_route_receipt.v1",
        "target": target,
        "source_decision_ref": args.source_decision_ref,
        "source_id": args.source_id or safe_target_id(platform),
        "source_family": args.source_family,
        "source_role": args.source_role,
        "source_priority_rank": args.source_priority_rank,
        "selected_strategy": selected_strategy,
        "opencli_tool_receipt": opencli_receipt,
        "map_poi_receipt": {},
        "route_decision": {
            "collection_mode": args.collection_mode,
            "selected_strategy": selected_strategy,
            "next_node": next_node,
            "reason": reason,
        },
        "route_probe": {
            "o0_opencli": opencli_receipt,
            "http": http_probe,
            "api": {
                "status": api_status,
                "marker": api_marker,
                "candidate_urls": api_candidates,
                "probes": api_probes,
            },
            "ssr_json": {"status": ssr_status, "marker": ssr_marker},
            "browser": {
                "status": "fallback" if selected_strategy == "browser" else "not_selected",
                "requires_evidence": selected_strategy == "browser",
            },
        },
        "evidence": [str(args.html_file.resolve())] if args.html_file else ([target] if http_probe.get("status") == "ok" else []),
        "fallback_chain": ["opencli", "api", "ssr_json", "browser"],
        "next_node": next_node,
        "command_receipts": command_receipts,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Probe an S31A target and emit s31a_route_receipt.v1.")
    parser.add_argument("--target")
    parser.add_argument("--url")
    parser.add_argument("--platform")
    parser.add_argument("--collection-mode", default="query_search_data_collection")
    parser.add_argument("--source-decision-ref")
    parser.add_argument("--source-id")
    parser.add_argument("--source-family", default="unknown")
    parser.add_argument("--source-role", default="primary_fact_source")
    parser.add_argument("--source-priority-rank", type=int, default=1)
    parser.add_argument("--html-file", type=Path)
    parser.add_argument("--api-evidence")
    parser.add_argument("--opencli-capability-map", type=Path, default=DEFAULT_OPENCLI_MAP)
    parser.add_argument("--run-opencli-help", action="store_true")
    parser.add_argument("--opencli", default="opencli")
    parser.add_argument("--timeout", type=float, default=5.0)
    parser.add_argument("--no-http-probe", action="store_true")
    parser.add_argument("--max-api-probes", type=int, default=3)
    parser.add_argument("--json-output", type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    receipt = build_receipt(args)
    text = json.dumps(receipt, ensure_ascii=False, indent=2)
    if args.json_output:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(text + "\n", encoding="utf-8")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
