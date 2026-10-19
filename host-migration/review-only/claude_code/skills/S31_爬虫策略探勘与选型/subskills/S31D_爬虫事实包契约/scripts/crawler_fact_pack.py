#!/usr/bin/env python3
"""crawler_fact_pack.v1 assembly and validation helpers for S31."""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "crawler_fact_pack.v1"
REQUIRED_TOP_LEVEL_FIELDS = {
    "schema_version",
    "platform",
    "query",
    "collected_at",
    "collection_status",
    "items",
    "fact_summary",
    "command_receipts",
    "inference",
}
REQUIRED_ITEM_FIELDS = {
    "title",
    "author",
    "body",
    "tags",
    "metrics",
    "top_comments",
    "source_url",
    "media_files",
    "frame_paths",
    "data_quality_flags",
    "evidence_grade",
}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".m4v", ".webm", ".mkv", ".avi"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}
PAIN_TERMS = (
    "太贵",
    "贵",
    "踩坑",
    "坑",
    "不好用",
    "没用",
    "失败",
    "退货",
    "卡",
    "慢",
    "麻烦",
    "不准",
    "不稳定",
    "焦虑",
    "担心",
    "不会",
    "app issue",
    "not working",
    "stopped working",
    "customer support",
    "troubleshooting",
    "expensive",
    "overpriced",
    "broken",
    "refund",
    "return",
    "connect",
    "connection",
)
STOP_TERMS = {
    "这个",
    "那个",
    "真的",
    "就是",
    "可以",
    "不是",
    "没有",
    "感觉",
    "一下",
    "一个",
    "还是",
    "因为",
    "所以",
    "the",
    "and",
    "for",
    "with",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def as_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float)):
        return str(value)
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def first_text(*values: Any) -> str:
    for value in values:
        text = as_text(value)
        if text:
            return text
    return ""


def safe_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return int(value)
    text = str(value).strip().replace(",", "")
    multiplier = 1
    if text.endswith("万"):
        multiplier = 10000
        text = text[:-1]
    elif text.endswith("千"):
        multiplier = 1000
        text = text[:-1]
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    if not match:
        return None
    return int(float(match.group(0)) * multiplier)


def listify(value: Any) -> list[Any]:
    if value is None or value == "":
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, str):
        parts = [part.strip() for part in re.split(r"[,，#\s]+", value) if part.strip()]
        return parts
    return [value]


def normalize_tags(*values: Any) -> list[str]:
    tags: list[str] = []
    for value in values:
        for item in listify(value):
            text = as_text(item).lstrip("#")
            if text and text not in tags:
                tags.append(text)
    return tags


def normalize_metrics(*sources: dict[str, Any] | None) -> dict[str, int | str | float | bool]:
    metrics: dict[str, int | str | float | bool] = {}
    aliases = {
        "likes": ["likes", "like", "点赞", "赞"],
        "collects": ["collects", "favorites", "收藏"],
        "comments": ["comments", "comment_count", "评论"],
        "shares": ["shares", "share", "转发", "分享"],
        "views": ["views", "view_count", "浏览", "播放"],
    }
    for source in sources:
        if not isinstance(source, dict):
            continue
        for canonical, keys in aliases.items():
            if canonical in metrics:
                continue
            for key in keys:
                if key in source:
                    parsed = safe_int(source.get(key))
                    metrics[canonical] = parsed if parsed is not None else as_text(source.get(key))
                    break
    return metrics


def normalize_comment(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        text = first_text(value.get("text"), value.get("content"), value.get("body"), value.get("comment"))
        return {
            "author": first_text(value.get("author"), value.get("nickname"), value.get("user")),
            "text": text,
            "likes": safe_int(value.get("likes")) or 0,
            "raw": value,
        }
    return {"author": "", "text": as_text(value), "likes": 0, "raw": value}


def normalize_comments(comments: Any, limit: int | None = None) -> list[dict[str, Any]]:
    rows = [normalize_comment(item) for item in listify(comments)]
    rows = [row for row in rows if row.get("text")]
    rows.sort(key=lambda row: int(row.get("likes") or 0), reverse=True)
    return rows[:limit] if limit else rows


def media_type_from_path(path: str) -> str:
    suffix = Path(path).suffix.lower()
    if suffix in VIDEO_EXTENSIONS:
        return "video"
    if suffix in IMAGE_EXTENSIONS:
        return "image"
    return "file"


def normalize_media_file(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        path = first_text(value.get("path"), value.get("file"), value.get("url"))
        media_type = first_text(value.get("type"), value.get("media_type")) or media_type_from_path(path)
        item = dict(value)
        item.update({"path": path, "type": media_type})
        return item
    path = as_text(value)
    return {"path": path, "type": media_type_from_path(path)}


def evidence_grade(item: dict[str, Any]) -> str:
    has_media = bool(item.get("media_files") or item.get("frame_paths"))
    has_frames = bool(item.get("frame_paths"))
    has_body = bool(item.get("body"))
    has_comments = bool(item.get("top_comments"))
    if has_frames and has_comments:
        return "A_media_frames_comments"
    if has_media and has_comments:
        return "B_media_comments"
    if has_media or has_frames:
        return "C_media_only"
    if has_body and has_comments:
        return "D_text_comments"
    if has_body or item.get("title"):
        return "E_text_or_metadata"
    return "F_metadata_only"


def build_item(
    *,
    search_record: dict[str, Any] | None = None,
    detail: dict[str, Any] | None = None,
    comments: Any = None,
    media_files: Any = None,
    frame_paths: Any = None,
    data_quality_flags: Any = None,
    source_url: str | None = None,
) -> dict[str, Any]:
    search_record = search_record or {}
    detail = detail or {}
    item = {
        "title": first_text(detail.get("title"), detail.get("标题"), search_record.get("title")),
        "author": first_text(detail.get("author"), detail.get("作者"), detail.get("nickname"), search_record.get("author"), search_record.get("nickname")),
        "body": first_text(detail.get("content"), detail.get("body"), detail.get("正文"), detail.get("desc"), detail.get("description"), search_record.get("desc")),
        "tags": normalize_tags(detail.get("tags"), detail.get("标签"), search_record.get("tags")),
        "metrics": normalize_metrics(search_record, detail),
        "top_comments": normalize_comments(comments),
        "source_url": first_text(source_url, detail.get("url"), search_record.get("url"), search_record.get("link")),
        "media_files": [normalize_media_file(media) for media in listify(media_files)],
        "frame_paths": [as_text(path) for path in listify(frame_paths) if as_text(path)],
        "data_quality_flags": sorted({as_text(flag) for flag in listify(data_quality_flags) if as_text(flag)}),
        "evidence_grade": "",
    }
    item["evidence_grade"] = evidence_grade(item)
    return item


def new_fact_pack(platform: str, query: str, collection_status: str = "ok") -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "platform": platform,
        "query": query,
        "collected_at": utc_now(),
        "collection_status": collection_status,
        "items": [],
        "fact_summary": {},
        "command_receipts": [],
        "inference": [],
    }


def body_length_distribution(items: list[dict[str, Any]]) -> dict[str, Any]:
    lengths = [len(as_text(item.get("body"))) for item in items]
    if not lengths:
        return {"count": 0, "min": 0, "max": 0, "mean": 0, "median": 0, "buckets": {"0": 0, "1-100": 0, "101-300": 0, "301+": 0}}
    buckets = {"0": 0, "1-100": 0, "101-300": 0, "301+": 0}
    for length in lengths:
        if length == 0:
            buckets["0"] += 1
        elif length <= 100:
            buckets["1-100"] += 1
        elif length <= 300:
            buckets["101-300"] += 1
        else:
            buckets["301+"] += 1
    return {
        "count": len(lengths),
        "min": min(lengths),
        "max": max(lengths),
        "mean": round(float(statistics.mean(lengths)), 2),
        "median": round(float(statistics.median(lengths)), 2),
        "buckets": buckets,
    }


def media_mix(items: list[dict[str, Any]]) -> dict[str, Any]:
    video = 0
    image = 0
    text_only = 0
    for item in items:
        files = item.get("media_files") or []
        has_video = bool(item.get("frame_paths")) or any((media.get("type") == "video") for media in files if isinstance(media, dict))
        has_image = any((media.get("type") == "image") for media in files if isinstance(media, dict))
        if has_video:
            video += 1
        elif has_image:
            image += 1
        else:
            text_only += 1
    total = max(1, len(items))
    return {
        "video_count": video,
        "image_count": image,
        "text_only_count": text_only,
        "video_ratio": round(video / total, 4),
        "image_ratio": round(image / total, 4),
    }


def tokenize_comment_text(text: str) -> list[str]:
    terms = re.findall(r"[A-Za-z0-9_]{2,}|[\u4e00-\u9fff]{2,4}", text.lower())
    return [term for term in terms if term not in STOP_TERMS]


def term_in_text(term: str, text: str) -> bool:
    return term.lower() in text.lower()


def comment_terms(items: list[dict[str, Any]]) -> dict[str, Any]:
    counter: Counter[str] = Counter()
    pain_counter: Counter[str] = Counter()
    for item in items:
        for comment in item.get("top_comments") or []:
            text = as_text(comment.get("text") if isinstance(comment, dict) else comment)
            counter.update(tokenize_comment_text(text))
            for term in PAIN_TERMS:
                if term_in_text(term, text):
                    pain_counter[term] += 1
    return {
        "high_frequency_terms": [{"term": term, "count": count} for term, count in counter.most_common(20)],
        "high_frequency_pain_terms": [
            {"term": term, "count": count, "source": "comment_text_exact_match"}
            for term, count in pain_counter.most_common(20)
        ],
    }


def review_text_terms(items: list[dict[str, Any]]) -> dict[str, Any]:
    counter: Counter[str] = Counter()
    pain_counter: Counter[str] = Counter()
    for item in items:
        texts = [as_text(item.get("body"))]
        texts.extend(as_text(comment.get("text") if isinstance(comment, dict) else comment) for comment in item.get("top_comments") or [])
        for text in texts:
            if not text:
                continue
            counter.update(tokenize_comment_text(text))
            for term in PAIN_TERMS:
                if term_in_text(term, text):
                    pain_counter[term] += 1
    return {
        "high_frequency_terms": [{"term": term, "count": count} for term, count in counter.most_common(20)],
        "high_frequency_pain_terms": [
            {"term": term, "count": count, "source": "review_body_or_comment_exact_match"}
            for term, count in pain_counter.most_common(20)
        ],
    }


def metric_rankings(items: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    rankings: dict[str, list[dict[str, Any]]] = {}
    metric_names = sorted({key for item in items for key in (item.get("metrics") or {}).keys()})
    for metric in metric_names:
        rows = []
        for index, item in enumerate(items):
            value = safe_int((item.get("metrics") or {}).get(metric))
            if value is not None:
                rows.append({"rank": index + 1, "title": item.get("title", ""), "source_url": item.get("source_url", ""), "value": value})
        rows.sort(key=lambda row: row["value"], reverse=True)
        if rows:
            rankings[metric] = rows[:10]
    return rankings


def transcript_coverage(items: list[dict[str, Any]]) -> dict[str, Any]:
    source_counter: Counter[str] = Counter()
    item_count = 0
    segment_count = 0
    text_chars = 0
    for item in items:
        segments = item.get("transcript_segments") or []
        if segments:
            item_count += 1
        segment_count += len(segments)
        for segment in segments:
            if isinstance(segment, dict):
                source_counter[as_text(segment.get("source")) or "unknown"] += 1
                text_chars += len(as_text(segment.get("text")))
    total = max(1, len(items))
    return {
        "items_with_transcript": item_count,
        "transcript_item_ratio": round(item_count / total, 4),
        "segment_count": segment_count,
        "text_chars": text_chars,
        "sources": dict(sorted(source_counter.items())),
    }


def missing_fields(items: list[dict[str, Any]]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for item in items:
        for field in ("title", "author", "body", "source_url"):
            if not as_text(item.get(field)):
                counts[field] += 1
        if not item.get("tags"):
            counts["tags"] += 1
        if not item.get("metrics"):
            counts["metrics"] += 1
        if not item.get("top_comments"):
            counts["top_comments"] += 1
        if not item.get("media_files") and not item.get("frame_paths"):
            counts["media_evidence"] += 1
    return dict(sorted(counts.items()))


def summarize_fact_pack(pack: dict[str, Any]) -> dict[str, Any]:
    items = pack.get("items") or []
    grades = Counter(item.get("evidence_grade", "") for item in items)
    comment_summary = comment_terms(items)
    review_text_summary = review_text_terms(items)
    return {
        "item_count": len(items),
        "body_length_distribution": body_length_distribution(items),
        "media_type_mix": media_mix(items),
        "comment_high_frequency_terms": comment_summary["high_frequency_terms"],
        "comment_high_frequency_pain_terms": comment_summary["high_frequency_pain_terms"],
        "review_text_high_frequency_terms": review_text_summary["high_frequency_terms"],
        "review_text_high_frequency_pain_terms": review_text_summary["high_frequency_pain_terms"],
        "transcript_coverage": transcript_coverage(items),
        "metric_rankings": metric_rankings(items),
        "missing_fields": missing_fields(items),
        "evidence_grades": dict(sorted(grades.items())),
    }


def is_video_item(item: dict[str, Any]) -> bool:
    files = item.get("media_files") or []
    if item.get("frame_paths"):
        return True
    for media in files:
        if isinstance(media, dict) and (media.get("type") == "video" or Path(as_text(media.get("path"))).suffix.lower() in VIDEO_EXTENSIONS):
            return True
    flags = set(item.get("data_quality_flags") or [])
    return "video_note" in flags


def validate_fact_pack(pack: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    missing_top = sorted(REQUIRED_TOP_LEVEL_FIELDS - set(pack.keys()))
    for field in missing_top:
        errors.append(f"missing_top_level_field:{field}")
    if pack.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version_mismatch:{pack.get('schema_version')}")
    if not isinstance(pack.get("items"), list):
        errors.append("items_not_list")
        return {"ok": False, "errors": errors}
    for index, item in enumerate(pack.get("items") or []):
        if not isinstance(item, dict):
            errors.append(f"item_{index}_not_object")
            continue
        missing_item = sorted(REQUIRED_ITEM_FIELDS - set(item.keys()))
        for field in missing_item:
            errors.append(f"item_{index}_missing_field:{field}")
        flags = set(item.get("data_quality_flags") or [])
        if is_video_item(item) and not (item.get("media_files") or item.get("frame_paths") or "zero_media_extracted" in flags):
            errors.append(f"item_{index}_video_without_media_evidence_or_zero_media_extracted")
        if item.get("inference"):
            errors.append(f"item_{index}_inference_inside_fact_item")
    if not isinstance(pack.get("inference"), list):
        errors.append("inference_not_list")
    return {"ok": not errors, "errors": errors}


def finalize_fact_pack(pack: dict[str, Any]) -> dict[str, Any]:
    pack["schema_version"] = SCHEMA_VERSION
    pack.setdefault("collected_at", utc_now())
    pack.setdefault("media_source_receipts", [])
    pack.setdefault("media_receipts", [])
    pack.setdefault("transcript_review_refs", [])
    pack.setdefault("command_receipts", [])
    pack.setdefault("inference", [])
    for item in pack.get("items") or []:
        item.setdefault("data_quality_flags", [])
        item.setdefault("media_files", [])
        item.setdefault("frame_paths", [])
        item.setdefault("top_comments", [])
        item.setdefault("metrics", {})
        item["evidence_grade"] = evidence_grade(item)
    pack["fact_summary"] = summarize_fact_pack(pack)
    pack["validation"] = validate_fact_pack(pack)
    return pack


def write_fact_pack(pack: dict[str, Any], path: str | Path) -> dict[str, Any]:
    finalized = finalize_fact_pack(pack)
    output_path = Path(path).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(finalized, ensure_ascii=False, indent=2), encoding="utf-8")
    return finalized


def load_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate and finalize crawler_fact_pack.v1 JSON.")
    parser.add_argument("--input", required=True, help="Input JSON pack or list of items.")
    parser.add_argument("--output", required=True, help="Output fact pack JSON path.")
    parser.add_argument("--platform", default="generic")
    parser.add_argument("--query", default="")
    parser.add_argument("--status", default="ok")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    data = load_json(args.input)
    if isinstance(data, dict) and data.get("schema_version") == SCHEMA_VERSION:
        pack = data
    else:
        pack = new_fact_pack(args.platform, args.query, args.status)
        if isinstance(data, list):
            pack["items"] = data
        elif isinstance(data, dict) and isinstance(data.get("items"), list):
            pack["items"] = data["items"]
            pack["command_receipts"] = data.get("command_receipts", [])
            pack["inference"] = data.get("inference", [])
        else:
            raise SystemExit("input must be a crawler_fact_pack.v1 object, {items: [...]}, or item list")
    finalized = write_fact_pack(pack, args.output)
    print(json.dumps(finalized["validation"], ensure_ascii=False, indent=2))
    return 0 if finalized["validation"]["ok"] else 2


if __name__ == "__main__":
    sys.exit(main())
