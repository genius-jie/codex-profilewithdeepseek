from __future__ import annotations

import importlib.util
import json
import sys
import threading
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "route_probe_cli.py"
SKILL = ROOT / "SKILL.md"


def load_module():
    spec = importlib.util.spec_from_file_location("route_probe_cli", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


route_probe_cli = load_module()


def write_capability_map(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "opencli_capability_map.md"
    path.write_text(body, encoding="utf-8")
    return path


def build(args: list[str]) -> dict:
    return route_probe_cli.build_receipt(route_probe_cli.parse_args(args))


class ProbeHandler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802 - stdlib handler API
        if self.path == "/page":
            body = "<script id='__NEXT_DATA__'>{}</script><script>fetch('/api/items')</script>"
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(body.encode("utf-8"))
            return
        if self.path == "/api/items":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"items":[{"id":"1"}]}')
            return
        self.send_response(404)
        self.end_headers()

    def log_message(self, format, *args):  # noqa: A002 - stdlib signature
        return


def with_probe_server():
    server = ThreadingHTTPServer(("127.0.0.1", 0), ProbeHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def test_opencli_capability_map_wins_before_lower_routes(tmp_path: Path):
    cap_map = write_capability_map(tmp_path, "| xiaohongshu | 小红书 | 搜笔记 |\n")
    html = tmp_path / "page.html"
    html.write_text("<script id='__NEXT_DATA__'>{}</script><script>fetch('/api/list')</script>", encoding="utf-8")

    receipt = build(
        [
            "--target",
            "https://www.xiaohongshu.com/search_result?keyword=AI",
            "--html-file",
            str(html),
            "--opencli-capability-map",
            str(cap_map),
            "--collection-mode",
            "content_mining_analysis_summary",
        ]
    )

    assert receipt["schema_version"] == "s31a_route_receipt.v1"
    assert receipt["selected_strategy"] == "opencli"
    assert receipt["next_node"] == "S31C"
    assert receipt["opencli_tool_receipt"]["status"] == "available_from_capability_map"


def test_api_evidence_wins_before_ssr_json(tmp_path: Path):
    cap_map = write_capability_map(tmp_path, "| other | 其他 | demo |\n")
    html = tmp_path / "page.html"
    html.write_text("<script id='__NEXT_DATA__'>{}</script>", encoding="utf-8")

    receipt = build(
        [
            "--target",
            "https://example.test/items",
            "--html-file",
            str(html),
            "--api-evidence",
            "XHR /api/items returned JSON",
            "--opencli-capability-map",
            str(cap_map),
        ]
    )

    assert receipt["selected_strategy"] == "api"
    assert receipt["route_probe"]["api"]["status"] == "evidence_provided"
    assert receipt["route_probe"]["ssr_json"]["status"] == "available"


def test_http_probe_fetches_page_and_json_api_before_ssr(tmp_path: Path):
    cap_map = write_capability_map(tmp_path, "| other | 其他 | demo |\n")
    server = with_probe_server()
    try:
        target = f"http://127.0.0.1:{server.server_port}/page"
        receipt = build(
            [
                "--target",
                target,
                "--opencli-capability-map",
                str(cap_map),
                "--timeout",
                "2",
            ]
        )
    finally:
        server.shutdown()
        server.server_close()

    assert receipt["selected_strategy"] == "api"
    assert receipt["route_probe"]["http"]["status"] == "ok"
    assert receipt["route_probe"]["api"]["status"] == "available"
    assert receipt["route_probe"]["api"]["marker"].endswith("/api/items")
    assert receipt["route_probe"]["ssr_json"]["status"] == "available"


def test_ssr_json_selected_when_no_opencli_or_api(tmp_path: Path):
    cap_map = write_capability_map(tmp_path, "| other | 其他 | demo |\n")
    html = tmp_path / "page.html"
    html.write_text("<script>window.__INITIAL_STATE__={items:[]}</script>", encoding="utf-8")

    receipt = build(
        [
            "--target",
            "https://directory.example.test",
            "--html-file",
            str(html),
            "--opencli-capability-map",
            str(cap_map),
        ]
    )

    assert receipt["selected_strategy"] == "ssr_json"
    assert receipt["route_probe"]["ssr_json"]["marker"] == "initial_state"


def test_browser_is_last_resort_without_evidence(tmp_path: Path):
    cap_map = write_capability_map(tmp_path, "| other | 其他 | demo |\n")
    html = tmp_path / "page.html"
    html.write_text("<html><body>plain</body></html>", encoding="utf-8")

    receipt = build(
        [
            "--target",
            "https://unknown.example.test",
            "--html-file",
            str(html),
            "--opencli-capability-map",
            str(cap_map),
        ]
    )

    assert receipt["selected_strategy"] == "browser"
    assert receipt["route_probe"]["browser"]["status"] == "fallback"
    assert receipt["fallback_chain"] == ["opencli", "api", "ssr_json", "browser"]


def test_cli_writes_json_output(tmp_path: Path):
    cap_map = write_capability_map(tmp_path, "| other | 其他 | demo |\n")
    output = tmp_path / "s31a_route_receipt.v1.json"

    code = route_probe_cli.main(
        [
            "--target",
            "https://unknown.example.test",
            "--opencli-capability-map",
            str(cap_map),
            "--json-output",
            str(output),
        ]
    )

    saved = json.loads(output.read_text(encoding="utf-8"))
    assert code == 0
    assert saved["selected_strategy"] == "browser"


def test_s31a_skill_registers_route_probe_cli():
    text = SKILL.read_text(encoding="utf-8")

    assert "scripts\\route_probe_cli.py" in text
    assert "s31a_route_receipt.v1" in text
    assert "HTTP" in text
    assert "Fetch/XHR" in text
