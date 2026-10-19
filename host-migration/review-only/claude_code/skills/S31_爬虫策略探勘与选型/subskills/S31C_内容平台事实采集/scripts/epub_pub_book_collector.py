from __future__ import annotations

import argparse
import hashlib
import html as html_lib
import json
import re
import sys
import threading
import time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path, PurePosixPath
from typing import Any, Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import unquote, urljoin, urlsplit
from urllib.request import Request, urlopen


DEFAULT_URL = "https://www.epub.pub/book/the-mob-boss-pet-by-measha-stone"
DEFAULT_USER_AGENT = "epub-pub-opf-collector/1.0"
RETRYABLE_STATUS = {408, 425, 429, 500, 502, 503, 504}
XHTML_TYPES = {"application/xhtml+xml"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def normalize_space(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def safe_rel_path(href: str) -> Path:
    """Map a manifest href to a safe local relative path."""
    decoded = unquote(href).replace("\\", "/")
    parts = [part for part in PurePosixPath(decoded).parts if part not in {"", ".", "..", "/"}]
    if not parts:
        return Path("unnamed.bin")
    return Path(*parts)


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def element_text(element: ET.Element | None) -> str:
    if element is None:
        return ""
    return normalize_space("".join(element.itertext()))


@dataclass
class FetchResult:
    url: str
    status: int | None
    content_type: str
    body: bytes
    attempts: int
    elapsed_ms: int
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.status == 200 and self.error is None


class HttpFetcher:
    """Bounded, observable HTTP fetcher for public EPUB assets."""

    def __init__(
        self,
        *,
        timeout: float = 30.0,
        retries: int = 2,
        min_interval: float = 0.15,
        user_agent: str = DEFAULT_USER_AGENT,
    ) -> None:
        self.timeout = timeout
        self.retries = max(0, retries)
        self.min_interval = max(0.0, min_interval)
        self.user_agent = user_agent
        self._rate_lock = threading.Lock()
        self._last_request = 0.0

    def _wait_turn(self) -> None:
        with self._rate_lock:
            now = time.monotonic()
            wait_for = self.min_interval - (now - self._last_request)
            if wait_for > 0:
                time.sleep(wait_for)
            self._last_request = time.monotonic()

    def fetch(self, url: str, *, accept: str = "*/*") -> FetchResult:
        started = time.monotonic()
        last_error: str | None = None
        last_status: int | None = None
        last_content_type = ""
        attempts = 0
        for attempt in range(1, self.retries + 2):
            attempts = attempt
            self._wait_turn()
            request = Request(
                url,
                headers={
                    "User-Agent": self.user_agent,
                    "Accept": accept,
                    "Accept-Encoding": "identity",
                },
            )
            try:
                with urlopen(request, timeout=self.timeout) as response:
                    body = response.read()
                    last_status = int(response.status)
                    last_content_type = response.headers.get("Content-Type", "")
                    elapsed = int((time.monotonic() - started) * 1000)
                    if response.status == 200:
                        return FetchResult(url, response.status, last_content_type, body, attempt, elapsed)
                    last_error = f"http_status:{response.status}"
                    if response.status not in RETRYABLE_STATUS:
                        break
            except HTTPError as exc:
                last_status = exc.code
                last_content_type = exc.headers.get("Content-Type", "") if exc.headers else ""
                last_error = f"http_status:{exc.code}:{exc.reason}"
                if exc.code not in RETRYABLE_STATUS:
                    break
            except (URLError, TimeoutError, OSError) as exc:
                last_error = f"transport:{type(exc).__name__}:{exc}"
            if attempt <= self.retries:
                time.sleep(min(3.0, 0.5 * (2 ** (attempt - 1))))
        elapsed = int((time.monotonic() - started) * 1000)
        return FetchResult(url, last_status, last_content_type, b"", attempts, elapsed, last_error or "unknown_error")


class BookPageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title = ""
        self.meta: dict[str, str] = {}
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = {key.lower(): value or "" for key, value in attrs}
        if tag.lower() == "title":
            self._in_title = True
        if tag.lower() == "meta":
            key = attr_map.get("name") or attr_map.get("property")
            if key:
                self.meta[key.lower()] = attr_map.get("content", "")

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title += data


def _first_regex(text: str, patterns: Iterable[str]) -> str:
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        if match:
            return html_lib.unescape(match.group(1)).strip()
    return ""


def _all_regex(text: str, pattern: str) -> list[str]:
    values: list[str] = []
    for value in re.findall(pattern, text, re.IGNORECASE | re.DOTALL):
        value = html_lib.unescape(value).strip()
        if value and value not in values:
            values.append(value)
    return values


def parse_book_page(page_bytes: bytes) -> dict[str, Any]:
    text = page_bytes.decode("utf-8", errors="replace")
    scan_text = text.replace('\\"', '"')
    parser = BookPageParser()
    parser.feed(text)
    ld_json = ""
    ld_match = re.search(r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', text, re.I | re.S)
    if ld_match:
        ld_json = html_lib.unescape(ld_match.group(1))
    ld: dict[str, Any] = {}
    if ld_json:
        try:
            parsed = json.loads(ld_json)
            if isinstance(parsed, dict):
                ld = parsed
        except json.JSONDecodeError:
            pass

    asset_id = _first_regex(scan_text, [r'["\\]?assetId["\\]?\s*:\s*["\\]([^"\\]+)', r'"id"\s*:\s*"([0-9a-f]{20,})"'])
    file_name = _first_regex(scan_text, [r'["\\]?fileName["\\]?\s*:\s*["\\]([^"\\]+)', r'["\\]?name["\\]?\s*:\s*["\\]([^"\\]+\.epub)'])
    full_url = _first_regex(scan_text, [r'["\\]?fullUrl["\\]?\s*:\s*["\\]([^"\\]+)', r'["\\]?fullUrl["\\]?\s*:\s*"([^"]+)'])
    checksum = _first_regex(scan_text, [r'["\\]?checkSum["\\]?\s*:\s*["\\]([^"\\]+)'])
    mime_type = _first_regex(scan_text, [r'["\\]?mimeType["\\]?\s*:\s*["\\]([^"\\]+)'])
    file_size_text = _first_regex(scan_text, [r'["\\]?fileSize["\\]?\s*:\s*(\d+)'])
    toc_labels = _all_regex(scan_text, r'["\\]?navLabel["\\]?\s*:\s*["\\]([^"\\]+)')
    post_ids = _all_regex(scan_text, r'["\\]?postId["\\]?\s*:\s*["\\]([^"\\]+)')
    author = _first_regex(scan_text, [r'"author"\s*:\s*\[?\s*\{[^}]*?"name"\s*:\s*"([^"]+)', r'<strong[^>]*>([^<]+)</strong>'])
    publisher = _first_regex(scan_text, [r'"publisher"\s*:\s*\{[^}]*?"name"\s*:\s*"([^"]+)', r'<strong[^>]*>Publisher:</strong>\s*<span>([^<]+)'])
    views_raw = _first_regex(scan_text, [r'Views\s*(?:<[^>]+>)*\s*([\d.,]+\s*[KkMm]?)'])
    rating_value = _first_regex(scan_text, [r'"ratingValue"\s*:\s*([\d.]+)', r'"value"\s*:\s*([\d.]+)'])
    rating_count = _first_regex(scan_text, [r'"ratingCount"\s*:\s*(\d+)', r'"numReviews"\s*:\s*(\d+)'])
    author_url = _first_regex(scan_text, [r'href=["\'](/author/[^"\']+)["\']'])
    description = str(ld.get("description") or parser.meta.get("description") or "").strip()
    title = str(ld.get("name") or parser.title or "").strip()
    author = str(ld.get("author", {}).get("name") if isinstance(ld.get("author"), dict) else (author or "")).strip()
    publisher = str(ld.get("publisher", {}).get("name") if isinstance(ld.get("publisher"), dict) else (publisher or "")).strip()
    return {
        "title": title,
        "author": author,
        "author_url": author_url,
        "publisher": publisher,
        "description": description,
        "genre": str(ld.get("genre") or "").strip(),
        "published_date": str(ld.get("datePublished") or "").strip(),
        "cover_url": str(ld.get("image") or parser.meta.get("og:image") or "").strip(),
        "views_raw": views_raw,
        "rating_value": float(rating_value) if rating_value else None,
        "rating_count": int(rating_count) if rating_count else None,
        "asset_id": asset_id,
        "file_name": file_name,
        "file_size": int(file_size_text) if file_size_text else None,
        "checksum": checksum,
        "mime_type": mime_type,
        "post_ids": post_ids,
        "toc_labels": toc_labels,
        "page_title": parser.title.strip(),
    }


def parse_reader_asset_url(reader_bytes: bytes) -> str:
    text = reader_bytes.decode("utf-8", errors="replace")
    candidates = _all_regex(text, r'(https://asset\.epub\.pub/epub/[^"\\]+)')
    for candidate in candidates:
        candidate = candidate.replace("\\u002F", "/")
        if "/OEBPS/" in candidate or candidate.endswith(".epub/"):
            return candidate.rstrip("\"' ")
    raise ValueError("reader_asset_url_not_found")


def parse_xml(data: bytes, label: str) -> ET.Element:
    try:
        return ET.fromstring(data)
    except ET.ParseError as exc:
        raise ValueError(f"{label}_xml_parse_failed:{exc}") from exc


def parse_opf(opf_bytes: bytes, opf_url: str) -> dict[str, Any]:
    root = parse_xml(opf_bytes, "opf")
    metadata: dict[str, str] = {}
    for child in root.iter():
        name = local_name(child.tag)
        if name in {"title", "language", "identifier", "creator", "publisher", "description", "date"}:
            metadata[name] = element_text(child)
    manifest: list[dict[str, Any]] = []
    manifest_by_id: dict[str, dict[str, Any]] = {}
    for item in root.iter():
        if local_name(item.tag) != "item":
            continue
        item_id = item.attrib.get("id", "")
        href = item.attrib.get("href", "")
        if not item_id or not href:
            continue
        record = {
            "id": item_id,
            "href": href,
            "url": urljoin(opf_url, href),
            "media_type": item.attrib.get("media-type", ""),
            "properties": item.attrib.get("properties", ""),
        }
        manifest.append(record)
        manifest_by_id[item_id] = record
    spine: list[dict[str, Any]] = []
    for itemref in root.iter():
        if local_name(itemref.tag) != "itemref":
            continue
        idref = itemref.attrib.get("idref", "")
        if idref:
            target = manifest_by_id.get(idref, {})
            spine.append({
                "idref": idref,
                "linear": itemref.attrib.get("linear", "yes") != "no",
                "href": target.get("href", ""),
                "url": target.get("url", ""),
                "media_type": target.get("media_type", ""),
            })
    guide = []
    for reference in root.iter():
        if local_name(reference.tag) == "reference":
            guide.append(dict(reference.attrib))
    return {"metadata": metadata, "manifest": manifest, "spine": spine, "guide": guide}


def parse_ncx(ncx_bytes: bytes, opf_url: str) -> dict[str, str]:
    root = parse_xml(ncx_bytes, "ncx")
    labels: dict[str, str] = {}
    for nav_point in root.iter():
        if local_name(nav_point.tag) != "navpoint":
            continue
        label = ""
        source = ""
        for child in nav_point.iter():
            name = local_name(child.tag)
            if name == "text" and not label:
                label = element_text(child)
            elif name == "content" and not source:
                source = child.attrib.get("src", "").split("#", 1)[0]
        if label and source:
            labels[urljoin(opf_url, source)] = label
    return labels


class XHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title = ""
        self.all_text: list[str] = []
        self.paragraphs: list[dict[str, Any]] = []
        self.headings: list[str] = []
        self.image_refs: list[str] = []
        self._title_open = False
        self._skip_depth = 0
        self._active_block: tuple[str, list[str], dict[str, str]] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        attr_map = {key: value or "" for key, value in attrs}
        if tag in {"script", "style", "noscript"}:
            self._skip_depth += 1
            return
        if self._skip_depth:
            return
        if tag == "title":
            self._title_open = True
        if tag == "img" and attr_map.get("src"):
            self.image_refs.append(attr_map["src"])
        if tag == "p" or re.fullmatch(r"h[1-6]", tag):
            self._active_block = (tag, [], attr_map)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in {"script", "style", "noscript"}:
            self._skip_depth = max(0, self._skip_depth - 1)
            return
        if self._skip_depth:
            return
        if tag == "title":
            self._title_open = False
        if self._active_block and tag == self._active_block[0]:
            block_tag, parts, attrs = self._active_block
            value = normalize_space("".join(parts))
            if value:
                if block_tag == "p":
                    self.paragraphs.append({"tag": block_tag, "text": value, "attrs": attrs})
                else:
                    self.headings.append(value)
            self._active_block = None

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        value = normalize_space(data)
        if value:
            self.all_text.append(value)
        if self._title_open:
            self.title += data
        if self._active_block:
            self._active_block[1].append(data)


def parse_xhtml(data: bytes) -> dict[str, Any]:
    parser = XHTMLParser()
    parser.feed(data.decode("utf-8", errors="replace"))
    paragraphs = parser.paragraphs
    text = "\n\n".join(item["text"] for item in paragraphs)
    if not text:
        text = normalize_space(" ".join(parser.all_text))
    return {
        "title": normalize_space(parser.title),
        "headings": parser.headings,
        "paragraphs": paragraphs,
        "text": text,
        "image_refs": parser.image_refs,
        "paragraph_count": len(paragraphs),
        "character_count": len(text),
        "word_count": len(re.findall(r"\b\w+\b", text, re.UNICODE)),
    }


def safe_json_write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def jsonl_write(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def parse_metric(value: str) -> int | None:
    if not value:
        return None
    compact = value.replace(",", "").replace(" ", "").lower()
    multiplier = 1
    if compact.endswith("k"):
        multiplier, compact = 1000, compact[:-1]
    elif compact.endswith("m"):
        multiplier, compact = 1_000_000, compact[:-1]
    try:
        return int(float(compact) * multiplier)
    except ValueError:
        return None


def build_fact_pack(metadata: dict[str, Any], output_dir: Path, acceptance: dict[str, Any]) -> dict[str, Any]:
    chapter_path = str((output_dir / "chapters.jsonl").resolve())
    body_path = str((output_dir / "normalized" / "book_full.txt").resolve())
    item = {
        "title": metadata.get("title", ""),
        "author": metadata.get("author", ""),
        "body": metadata.get("description", ""),
        "body_ref": body_path,
        "chapter_index_ref": chapter_path,
        "body_char_count": acceptance.get("body_char_count", 0),
        "tags": [metadata.get("genre")] if metadata.get("genre") else [],
        "metrics": {
            key: value
            for key, value in {
                "views": parse_metric(metadata.get("views_raw", "")),
                "rating": metadata.get("rating_value"),
                "rating_count": metadata.get("rating_count"),
            }.items()
            if value is not None
        },
        "top_comments": [],
        "source_url": metadata.get("source_url", ""),
        "media_files": acceptance.get("media_files", []),
        "frame_paths": [],
        "data_quality_flags": [
            "full_body_saved_by_manifest_spine",
            "comments_not_collected",
        ],
        "evidence_grade": "",
    }
    pack = {
        "schema_version": "crawler_fact_pack.v1",
        "platform": "epub_pub",
        "query": metadata.get("title", ""),
        "collected_at": utc_now(),
        "collection_status": acceptance.get("status", "partial"),
        "items": [item],
        "fact_summary": {
            "book_metadata_path": str((output_dir / "book_metadata.json").resolve()),
            "chapters_path": chapter_path,
            "acceptance_path": str((output_dir / "acceptance.json").resolve()),
        },
        "command_receipts": acceptance.get("command_receipts", []),
        "inference": [],
    }
    return pack


class Collector:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.output_dir = Path(args.output_dir).resolve()
        self.raw_dir = self.output_dir / "raw_epub"
        self.evidence_dir = self.output_dir / "evidence"
        self.normalized_dir = self.output_dir / "normalized" / "chapters"
        self.fetcher = HttpFetcher(
            timeout=args.timeout,
            retries=args.retries,
            min_interval=args.min_interval,
            user_agent=args.user_agent,
        )
        self.receipts: list[dict[str, Any]] = []

    def _record_fetch(self, result: FetchResult, *, kind: str, path: str | None = None) -> dict[str, Any]:
        receipt = {
            "kind": kind,
            "url": result.url,
            "status": result.status,
            "content_type": result.content_type,
            "bytes": len(result.body),
            "attempts": result.attempts,
            "elapsed_ms": result.elapsed_ms,
            "sha256": sha256_bytes(result.body) if result.body else None,
            "path": path,
            "error": result.error,
        }
        self.receipts.append(receipt)
        return receipt

    def _save_raw(self, relative_path: str, data: bytes) -> str:
        path = self.raw_dir / safe_rel_path(relative_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return str(path.resolve())

    def run(self) -> dict[str, Any]:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        started = utc_now()
        page_result = self.fetcher.fetch(self.args.url, accept="text/html,application/xhtml+xml;q=0.9,*/*;q=0.8")
        page_path = self.evidence_dir / "book_page.html"
        page_path.parent.mkdir(parents=True, exist_ok=True)
        page_path.write_bytes(page_result.body)
        page_receipt = self._record_fetch(page_result, kind="book_page", path=str(page_path.resolve()))
        if not page_result.ok:
            return self._finish(started, {}, {"status": "failed", "failure_reason": "book_page_fetch_failed", "page": page_receipt})

        metadata = parse_book_page(page_result.body)
        metadata["source_url"] = self.args.url
        if not metadata.get("asset_id"):
            return self._finish(started, metadata, {"status": "failed", "failure_reason": "asset_id_not_found", "page": page_receipt})
        safe_json_write(self.output_dir / "book_metadata.json", metadata)

        reader_url = f"https://spread.epub.pub/epub/{metadata['asset_id']}"
        reader_result = self.fetcher.fetch(reader_url, accept="text/html,application/xhtml+xml;q=0.9,*/*;q=0.8")
        reader_path = self.evidence_dir / "reader.html"
        reader_path.write_bytes(reader_result.body)
        reader_receipt = self._record_fetch(reader_result, kind="reader", path=str(reader_path.resolve()))
        if not reader_result.ok:
            return self._finish(started, metadata, {"status": "failed", "failure_reason": "reader_fetch_failed", "page": page_receipt, "reader": reader_receipt})

        try:
            asset_root_or_opf = parse_reader_asset_url(reader_result.body)
        except ValueError as exc:
            return self._finish(started, metadata, {"status": "failed", "failure_reason": str(exc), "page": page_receipt, "reader": reader_receipt})
        opf_url = asset_root_or_opf if asset_root_or_opf.endswith("content.opf") else urljoin(asset_root_or_opf, "OEBPS/content.opf")
        asset_root = opf_url.rsplit("OEBPS/content.opf", 1)[0]
        metadata["reader_url"] = reader_url
        metadata["asset_root"] = asset_root
        metadata["opf_url"] = opf_url
        safe_json_write(self.output_dir / "book_metadata.json", metadata)

        container_url = urljoin(asset_root, "META-INF/container.xml")
        container_result = self.fetcher.fetch(container_url, accept="application/xml,text/xml;q=0.9,*/*;q=0.8")
        container_path = self.evidence_dir / "container.xml"
        container_path.write_bytes(container_result.body)
        container_receipt = self._record_fetch(container_result, kind="container", path=str(container_path.resolve()))

        opf_result = self.fetcher.fetch(opf_url, accept="application/oebps-package+xml,application/xml;q=0.9,*/*;q=0.8")
        opf_path = self.evidence_dir / "content.opf"
        opf_path.write_bytes(opf_result.body)
        opf_receipt = self._record_fetch(opf_result, kind="opf", path=str(opf_path.resolve()))
        if not opf_result.ok:
            return self._finish(started, metadata, {"status": "failed", "failure_reason": "opf_fetch_failed", "page": page_receipt, "reader": reader_receipt, "container": container_receipt, "opf": opf_receipt})

        try:
            parsed_opf = parse_opf(opf_result.body, opf_url)
        except ValueError as exc:
            return self._finish(started, metadata, {"status": "failed", "failure_reason": str(exc), "page": page_receipt, "reader": reader_receipt, "container": container_receipt, "opf": opf_receipt})
        safe_json_write(self.output_dir / "opf_manifest.json", parsed_opf)

        manifest = parsed_opf["manifest"]
        spine_by_url = {row["url"]: {**row, "spine_index": index} for index, row in enumerate(parsed_opf["spine"])}
        item_results: dict[str, tuple[dict[str, Any], FetchResult, str]] = {}
        with ThreadPoolExecutor(max_workers=max(1, self.args.concurrency)) as pool:
            future_map = {pool.submit(self.fetcher.fetch, item["url"], accept=item["media_type"] or "*/*"): item for item in manifest}
            for future in as_completed(future_map):
                item = future_map[future]
                result = future.result()
                local_path = self._save_raw(item["href"], result.body) if result.ok else ""
                item_results[item["id"]] = (item, result, local_path)
                self._record_fetch(result, kind="manifest_item", path=local_path or None)

        toc_labels_by_url: dict[str, str] = {}
        for item in manifest:
            if item["media_type"] != "application/x-dtbncx+xml":
                continue
            _row_item, result, _local_path = item_results[item["id"]]
            if result.ok:
                toc_labels_by_url.update(parse_ncx(result.body, opf_url))

        assets: list[dict[str, Any]] = []
        chapters: list[dict[str, Any]] = []
        paragraphs: list[dict[str, Any]] = []
        media_files: list[dict[str, Any]] = []
        missing: list[str] = []
        empty_linear: list[str] = []
        body_char_count = 0
        content_hashes: dict[str, list[str]] = {}
        xhtml_counter = 0
        for item in manifest:
            row_item, result, local_path = item_results[item["id"]]
            spine = spine_by_url.get(item["url"])
            asset_row = {
                **item,
                "spine_index": spine["spine_index"] if spine else None,
                "linear": spine["linear"] if spine else False,
                "local_path": local_path,
                "http_status": result.status,
                "content_type": result.content_type,
                "bytes": len(result.body),
                "sha256": sha256_bytes(result.body) if result.body else None,
                "error": result.error,
            }
            assets.append(asset_row)
            if result.ok and item["media_type"].startswith("image/"):
                media_files.append({"path": local_path, "type": "image", "media_type": item["media_type"], "source_url": item["url"]})
            if not result.ok:
                missing.append(item["id"])
                continue
            if item["media_type"] not in XHTML_TYPES and "xhtml" not in item["media_type"]:
                continue
            xhtml_counter += 1
            parsed = parse_xhtml(result.body)
            body_char_count += int(parsed["character_count"])
            content_hashes.setdefault(sha256_bytes(result.body), []).append(item["id"])
            chapter_index = spine["spine_index"] if spine else 10_000 + xhtml_counter
            normalized_path = self.normalized_dir / f"{chapter_index:04d}-{safe_rel_path(item['href']).stem}.txt"
            normalized_path.parent.mkdir(parents=True, exist_ok=True)
            normalized_path.write_text(parsed["text"] + "\n", encoding="utf-8")
            chapter_row = {
                "asset_id": item["id"],
                "spine_index": spine["spine_index"] if spine else None,
                "linear": spine["linear"] if spine else False,
                "href": item["href"],
                "absolute_url": item["url"],
                "toc_label": toc_labels_by_url.get(item["url"], ""),
                "title": parsed["title"] or (parsed["headings"] or [""])[0],
                "raw_xhtml_path": local_path,
                "normalized_text_path": str(normalized_path.resolve()),
                "paragraph_count": parsed["paragraph_count"],
                "character_count": parsed["character_count"],
                "word_count": parsed["word_count"],
                "image_refs": parsed["image_refs"],
                "content_hash": sha256_bytes(result.body),
                "http_status": result.status,
                "content_type": result.content_type,
                "quality_flags": [],
            }
            if not parsed["text"] and spine and spine["linear"]:
                chapter_row["quality_flags"].append("empty_linear_xhtml")
                empty_linear.append(item["id"])
            chapters.append(chapter_row)
            for index, paragraph in enumerate(parsed["paragraphs"]):
                paragraphs.append({
                    "asset_id": item["id"],
                    "chapter_spine_index": spine["spine_index"] if spine else None,
                    "paragraph_index": index,
                    "tag": paragraph["tag"],
                    "class_names": paragraph["attrs"].get("class", ""),
                    "text": paragraph["text"],
                    "text_hash": hashlib.sha256(paragraph["text"].encode("utf-8")).hexdigest(),
                    "source_href": item["href"],
                })

        chapters.sort(key=lambda row: (row["spine_index"] is None, row["spine_index"] or 10_000, row["href"]))
        assets.sort(key=lambda row: row["href"])
        paragraphs.sort(key=lambda row: (row["chapter_spine_index"] is None, row["chapter_spine_index"] or 10_000, row["paragraph_index"]))
        jsonl_write(self.output_dir / "chapters.jsonl", chapters)
        jsonl_write(self.output_dir / "paragraphs.jsonl", paragraphs)
        jsonl_write(self.output_dir / "assets.jsonl", assets)
        body_full_path = self.output_dir / "normalized" / "book_full.txt"
        body_full_path.parent.mkdir(parents=True, exist_ok=True)
        with body_full_path.open("w", encoding="utf-8", newline="\n") as handle:
            for chapter in chapters:
                text_path = Path(chapter["normalized_text_path"])
                title = chapter.get("title") or chapter.get("toc_label") or chapter.get("href")
                handle.write(f"# {title}\n\n")
                handle.write(text_path.read_text(encoding="utf-8").rstrip())
                handle.write("\n\n")

        linear_spine_ids = [row["idref"] for row in parsed_opf["spine"] if row["linear"]]
        fetched_ids = {row["id"] for row in assets if row["http_status"] == 200}
        missing_spine = [item_id for item_id in linear_spine_ids if item_id not in fetched_ids]
        duplicate_hashes = {digest: ids for digest, ids in content_hashes.items() if len(ids) > 1}
        acceptance = {
            "schema_version": "epub_pub_collection_acceptance.v1",
            "status": "ok" if not missing and not missing_spine and not empty_linear else "partial",
            "started_at": started,
            "finished_at": utc_now(),
            "source_url": self.args.url,
            "reader_url": reader_url,
            "asset_root": asset_root,
            "opf_url": opf_url,
            "counts": {
                "manifest_items": len(manifest),
                "spine_items": len(parsed_opf["spine"]),
                "linear_spine_items": len(linear_spine_ids),
                "fetched_items": sum(1 for row in assets if row["http_status"] == 200),
                "xhtml_items": xhtml_counter,
                "chapters_rows": len(chapters),
                "paragraph_rows": len(paragraphs),
                "media_files": len(media_files),
                "toc_entries": len(toc_labels_by_url),
            },
            "body_char_count": body_char_count,
            "body_full_path": str(body_full_path.resolve()),
            "body_full_bytes": body_full_path.stat().st_size,
            "body_full_sha256": sha256_bytes(body_full_path.read_bytes()),
            "missing_manifest_items": missing,
            "missing_linear_spine_items": missing_spine,
            "empty_linear_xhtml": empty_linear,
            "duplicate_content_hashes": duplicate_hashes,
            "completeness": {
                "book_page_ok": page_result.ok,
                "reader_ok": reader_result.ok,
                "container_ok": container_result.ok,
                "opf_ok": opf_result.ok,
                "all_manifest_items_fetched": not missing,
                "all_linear_spine_items_fetched": not missing_spine,
                "all_linear_xhtml_nonempty": not empty_linear,
                "no_silent_loss": not missing and not missing_spine,
            },
            "evidence_refs": [
                str(page_path.resolve()),
                str(reader_path.resolve()),
                str(container_path.resolve()),
                str(opf_path.resolve()),
                str((self.output_dir / "opf_manifest.json").resolve()),
                str((self.output_dir / "chapters.jsonl").resolve()),
                str((self.output_dir / "paragraphs.jsonl").resolve()),
                str((self.output_dir / "assets.jsonl").resolve()),
                str(body_full_path.resolve()),
            ],
            "command_receipts": self.receipts,
            "media_files": media_files,
        }
        safe_json_write(self.output_dir / "acceptance.json", acceptance)
        metadata["opf_metadata"] = parsed_opf["metadata"]
        metadata["manifest_count"] = len(manifest)
        metadata["spine_count"] = len(parsed_opf["spine"])
        safe_json_write(self.output_dir / "book_metadata.json", metadata)
        fact_pack = build_fact_pack(metadata, self.output_dir, acceptance)
        safe_json_write(self.output_dir / "crawler_fact_pack.v1.json", fact_pack)
        return acceptance

    def _finish(self, started: str, metadata: dict[str, Any], acceptance: dict[str, Any]) -> dict[str, Any]:
        acceptance.setdefault("schema_version", "epub_pub_collection_acceptance.v1")
        acceptance.setdefault("status", "failed")
        acceptance.setdefault("started_at", started)
        acceptance.setdefault("finished_at", utc_now())
        acceptance.setdefault("source_url", self.args.url)
        acceptance.setdefault("evidence_refs", [])
        acceptance["command_receipts"] = self.receipts
        safe_json_write(self.output_dir / "acceptance.json", acceptance)
        if metadata:
            safe_json_write(self.output_dir / "book_metadata.json", metadata)
            safe_json_write(self.output_dir / "crawler_fact_pack.v1.json", build_fact_pack(metadata, self.output_dir, acceptance))
        return acceptance


def cli_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Collect one EPUB Pub book through its public OPF manifest/spine route.")
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--min-interval", type=float, default=0.15)
    parser.add_argument("--user-agent", default=DEFAULT_USER_AGENT)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = cli_parser().parse_args(argv)
    try:
        result = Collector(args).run()
    except Exception as exc:  # ensure an observable receipt for unexpected failures
        output_dir = Path(args.output_dir).resolve()
        output_dir.mkdir(parents=True, exist_ok=True)
        safe_json_write(output_dir / "acceptance.json", {
            "schema_version": "epub_pub_collection_acceptance.v1",
            "status": "failed",
            "failure_reason": f"unhandled:{type(exc).__name__}:{exc}",
            "finished_at": utc_now(),
        })
        print(json.dumps({"status": "failed", "failure_reason": str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("status") == "ok" else 2


if __name__ == "__main__":
    sys.exit(main())
