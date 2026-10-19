#!/usr/bin/env python3
"""Build traceable analysis insights from crawler_fact_pack.v1."""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "analysis_insight_pack.v1"
SCRIPT_DIR = Path(__file__).resolve().parent
PRIORITY_VALUES = {"high", "medium", "low"}
TREND_CATEGORIES = {"market_trend", "trend_signal", "trend_judgement"}


def load_sibling_module(module_name: str):
    module_path = SCRIPT_DIR / f"{module_name}.py"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    if not spec or not spec.loader:
        raise RuntimeError(f"cannot load sibling module: {module_path}")
    spec.loader.exec_module(module)
    return module


crawler_fact_pack = load_sibling_module("crawler_fact_pack")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def clone_json(value: Any) -> Any:
    return json.loads(json.dumps(value, ensure_ascii=False))


def as_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float, bool)):
        return str(value)
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def compact_snippet(value: Any, limit: int = 120) -> str:
    text = " ".join(as_text(value).split())
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def finalize_source_fact_pack(fact_pack: dict[str, Any]) -> dict[str, Any]:
    return crawler_fact_pack.finalize_fact_pack(clone_json(fact_pack))


def item_anchor(item: dict[str, Any], item_index: int, field: str, value: Any | None = None) -> dict[str, Any]:
    raw_value = item.get(field) if value is None else value
    return {
        "item_index": item_index,
        "field": field,
        "source_url": as_text(item.get("source_url")),
        "item_title": as_text(item.get("title")),
        "snippet": compact_snippet(raw_value),
    }


def first_item_anchors(items: list[dict[str, Any]], limit: int = 3) -> list[dict[str, Any]]:
    anchors = []
    for index, item in enumerate(items):
        field = "title" if as_text(item.get("title")) else "source_url"
        anchors.append(item_anchor(item, index, field))
        if len(anchors) >= limit:
            break
    return anchors


def find_item_index(items: list[dict[str, Any]], *, source_url: str = "", title: str = "") -> int | None:
    for index, item in enumerate(items):
        if source_url and as_text(item.get("source_url")) == source_url:
            return index
        if title and as_text(item.get("title")) == title:
            return index
    return None


def comment_anchors_for_terms(
    items: list[dict[str, Any]],
    terms: list[str],
    limit: int = 4,
) -> list[dict[str, Any]]:
    anchors: list[dict[str, Any]] = []
    for index, item in enumerate(items):
        for comment in item.get("top_comments") or []:
            text = as_text(comment.get("text") if isinstance(comment, dict) else comment)
            if any(term and term in text for term in terms):
                anchors.append(item_anchor(item, index, "top_comments", text))
                if len(anchors) >= limit:
                    return anchors
    return anchors


def review_text_anchors_for_terms(
    items: list[dict[str, Any]],
    terms: list[str],
    limit: int = 4,
) -> list[dict[str, Any]]:
    anchors = comment_anchors_for_terms(items, terms, limit)
    if len(anchors) >= limit:
        return anchors
    for index, item in enumerate(items):
        body = as_text(item.get("body"))
        if any(term and term.lower() in body.lower() for term in terms):
            anchors.append(item_anchor(item, index, "body", body))
            if len(anchors) >= limit:
                break
    return anchors


def media_anchors(items: list[dict[str, Any]], limit: int = 3) -> list[dict[str, Any]]:
    anchors: list[dict[str, Any]] = []
    for index, item in enumerate(items):
        if item.get("frame_paths"):
            anchors.append(item_anchor(item, index, "frame_paths"))
        elif item.get("media_files"):
            anchors.append(item_anchor(item, index, "media_files"))
        if len(anchors) >= limit:
            break
    return anchors


def missing_field_anchors(items: list[dict[str, Any]], field: str, limit: int = 3) -> list[dict[str, Any]]:
    anchors: list[dict[str, Any]] = []
    for index, item in enumerate(items):
        value = item.get(field)
        if field == "media_evidence":
            missing = not item.get("media_files") and not item.get("frame_paths")
        elif field in {"tags", "metrics", "top_comments"}:
            missing = not value
        else:
            missing = not as_text(value)
        if missing:
            anchor_field = "title" if as_text(item.get("title")) else "source_url"
            anchors.append(item_anchor(item, index, anchor_field))
            if len(anchors) >= limit:
                break
    return anchors


def add_finding(
    findings: list[dict[str, Any]],
    *,
    finding_id: str,
    category: str,
    priority: str,
    statement: str,
    basis: str,
    confidence: float,
    evidence_anchors: list[dict[str, Any]],
    time_window: dict[str, Any] | None = None,
    comparison_anchor: dict[str, Any] | None = None,
) -> None:
    if not evidence_anchors:
        return
    finding = {
        "finding_id": finding_id,
        "category": category,
        "insight_type": category,
        "priority": priority,
        "statement": statement,
        "basis": basis,
        "confidence": round(float(confidence), 2),
        "evidence_anchors": evidence_anchors,
        "source_item_refs": source_item_refs_from_anchors(evidence_anchors),
    }
    if time_window is not None:
        finding["time_window"] = time_window
    if comparison_anchor is not None:
        finding["comparison_anchor"] = comparison_anchor
    findings.append(finding)


def source_item_refs_from_anchors(anchors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    seen: set[tuple[Any, str, str]] = set()
    for anchor in anchors:
        ref = {
            "item_index": anchor.get("item_index"),
            "field": as_text(anchor.get("field")),
            "source_url": as_text(anchor.get("source_url")),
        }
        key = (ref["item_index"], ref["field"], ref["source_url"])
        if key in seen:
            continue
        seen.add(key)
        refs.append(ref)
    return refs


def build_metric_findings(
    items: list[dict[str, Any]],
    rankings: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    metric_labels = {
        "likes": "点赞",
        "views": "播放/浏览",
        "comments": "评论",
        "collects": "收藏",
        "shares": "分享",
    }
    for metric in ("likes", "views", "comments", "collects", "shares"):
        rows = rankings.get(metric) or []
        if not rows:
            continue
        leader = rows[0]
        item_index = find_item_index(
            items,
            source_url=as_text(leader.get("source_url")),
            title=as_text(leader.get("title")),
        )
        if item_index is None:
            continue
        item = items[item_index]
        label = metric_labels.get(metric, metric)
        title = as_text(item.get("title")) or "未命名样本"
        value = as_text(leader.get("value"))
        add_finding(
            findings,
            finding_id=f"metric_{metric}_leader",
            category="metric_signal",
            priority="medium",
            statement=f"{title} 是本批样本里 {label} 最高的记录，数值为 {value}。",
            basis=f"metric_rankings.{metric} 的首位记录回指到同一 source_url/title 的 item。",
            confidence=0.82,
            evidence_anchors=[item_anchor(item, item_index, "metrics")],
        )
    return findings


def build_analysis_findings(fact_pack: dict[str, Any]) -> list[dict[str, Any]]:
    items = fact_pack.get("items") or []
    summary = fact_pack.get("fact_summary") or {}
    findings: list[dict[str, Any]] = []

    if items:
        add_finding(
            findings,
            finding_id="sample_scope",
            category="sample_scope",
            priority="medium",
            statement=f"本次采集到 {len(items)} 条 {as_text(fact_pack.get('platform')) or 'unknown'} 记录，可作为报告分析的样本池。",
            basis="crawler_fact_pack.v1.items[] 的记录数量和首批 item anchor 构成样本范围依据。",
            confidence=0.75,
            evidence_anchors=first_item_anchors(items),
        )

    findings.extend(build_metric_findings(items, summary.get("metric_rankings") or {}))

    comment_pain_terms = summary.get("comment_high_frequency_pain_terms") or []
    review_text_pain_terms = summary.get("review_text_high_frequency_pain_terms") or []
    pain_terms = comment_pain_terms or review_text_pain_terms
    if pain_terms:
        from_comments = bool(comment_pain_terms)
        top_terms = [as_text(row.get("term")) for row in pain_terms[:5] if isinstance(row, dict)]
        term_text = "、".join(
            f"{as_text(row.get('term'))}({as_text(row.get('count'))})"
            for row in pain_terms[:5]
            if isinstance(row, dict)
        )
        add_finding(
            findings,
            finding_id="pain_terms_from_comments" if from_comments else "pain_terms_from_review_text",
            category="audience_pain",
            priority="high",
            statement=f"{'评论里' if from_comments else '评论正文/帖子正文里'}反复出现的痛点是：{term_text}。",
            basis=(
                "fact_summary.comment_high_frequency_pain_terms 与 top_comments 命中项共同支撑痛点归因。"
                if from_comments
                else "fact_summary.review_text_high_frequency_pain_terms 与 body/top_comments 命中项共同支撑痛点归因。"
            ),
            confidence=0.8,
            evidence_anchors=comment_anchors_for_terms(items, top_terms)
            if from_comments
            else review_text_anchors_for_terms(items, top_terms),
        )

    media_mix = summary.get("media_type_mix") or {}
    media_anchor_rows = media_anchors(items)
    if media_anchor_rows:
        add_finding(
            findings,
            finding_id="media_evidence_available",
            category="evidence_quality",
            priority="medium",
            statement=(
                f"样本里有 {media_mix.get('video_count', 0)} 条视频证据、"
                f"{media_mix.get('image_count', 0)} 条图片证据，可支撑视觉或素材分析。"
            ),
            basis="media_type_mix 汇总和 item 内 media_files/frame_paths anchor 均显示存在媒体证据。",
            confidence=0.74,
            evidence_anchors=media_anchor_rows,
        )
    elif items:
        add_finding(
            findings,
            finding_id="media_evidence_gap",
            category="evidence_gap",
            priority="high",
            statement="本批样本没有媒体文件或抽帧证据，报告不能把文本观察写成视觉结论。",
            basis="所有 item 均缺少 media_files/frame_paths，视觉类判断需要降级。",
            confidence=0.88,
            evidence_anchors=first_item_anchors(items),
        )

    missing = summary.get("missing_fields") or {}
    if missing:
        for field, count in sorted(missing.items(), key=lambda row: row[1], reverse=True)[:2]:
            anchors = missing_field_anchors(items, field)
            add_finding(
                findings,
                finding_id=f"missing_{field}",
                category="evidence_gap",
                priority="high" if field in {"source_url", "top_comments", "media_evidence"} else "medium",
                statement=f"有 {count} 条记录缺少 {field}，报告使用该字段时需要降级标注。",
                basis=f"fact_summary.missing_fields.{field} 与缺字段 item anchor 共同支撑该质量缺口。",
                confidence=0.84,
                evidence_anchors=anchors,
            )
    return findings


def build_recommendations(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    recommendations = []
    by_id = {finding["finding_id"]: finding for finding in findings}
    templates = [
        ("pain_terms_from_comments", "report_angle", "报告先写用户痛点，再写功能或卖点。"),
        ("media_evidence_gap", "quality_label", "报告里标注素材不足，不输出视觉类判断。"),
        ("media_evidence_available", "case_selection", "有素材证据的样本优先进入案例拆解。"),
        ("metric_likes_leader", "case_selection", "把最高互动样本作为第一批拆解对象。"),
    ]
    for finding_id, kind, recommendation in templates:
        finding = by_id.get(finding_id)
        if not finding:
            continue
        recommendations.append(
            {
                "recommendation_id": f"{kind}_{finding_id}",
                "kind": kind,
                "statement": recommendation,
                "based_on_findings": [finding_id],
                "evidence_anchors": finding.get("evidence_anchors", []),
            }
        )
    return recommendations


def build_report_claims(findings: list[dict[str, Any]], fact_pack_ref: str) -> list[dict[str, Any]]:
    claims = []
    for index, finding in enumerate(findings, start=1):
        claims.append(
            {
                "claim_id": f"claim_{index:03d}",
                "finding_id": finding["finding_id"],
                "claim": finding["statement"],
                "source_fact_pack_ref": fact_pack_ref,
                "evidence_anchors": finding.get("evidence_anchors", []),
                "source_item_refs": finding.get("source_item_refs", []),
            }
        )
    return claims


def validate_anchor(anchor: dict[str, Any], items: list[dict[str, Any]], context: str) -> list[str]:
    errors: list[str] = []
    item_index = anchor.get("item_index")
    if not isinstance(item_index, int) or item_index < 0 or item_index >= len(items):
        return [f"{context}_anchor_item_index_out_of_range:{item_index}"]
    item = items[item_index]
    field = as_text(anchor.get("field"))
    if not field:
        errors.append(f"{context}_anchor_missing_field")
    elif field not in item:
        errors.append(f"{context}_anchor_field_not_in_item:{field}")
    if not as_text(anchor.get("snippet")):
        errors.append(f"{context}_anchor_missing_snippet")
    item_url = as_text(item.get("source_url"))
    anchor_url = as_text(anchor.get("source_url"))
    if item_url and anchor_url != item_url:
        errors.append(f"{context}_anchor_source_url_mismatch")
    return errors


def validate_analysis_insight_pack(pack: dict[str, Any], fact_pack: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    source = finalize_source_fact_pack(fact_pack)
    items = source.get("items") or []

    if pack.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version_mismatch:{pack.get('schema_version')}")
    findings = pack.get("findings")
    if not isinstance(findings, list):
        errors.append("findings_not_list")
        findings = []
    finding_ids: set[str] = set()
    for index, finding in enumerate(findings):
        if not isinstance(finding, dict):
            errors.append(f"finding_{index}_not_object")
            continue
        finding_id = as_text(finding.get("finding_id"))
        if not finding_id:
            errors.append(f"finding_{index}_missing_finding_id")
        elif finding_id in finding_ids:
            errors.append(f"finding_{finding_id}_duplicate")
        finding_ids.add(finding_id)
        if not as_text(finding.get("statement")):
            errors.append(f"finding_{finding_id or index}_missing_statement")
        if not as_text(finding.get("basis")):
            errors.append(f"finding_{finding_id or index}_missing_basis")
        if finding.get("priority") not in PRIORITY_VALUES:
            errors.append(f"finding_{finding_id or index}_invalid_priority:{finding.get('priority')}")
        confidence = finding.get("confidence")
        if not isinstance(confidence, (int, float)) or not (0 <= confidence <= 1):
            errors.append(f"finding_{finding_id or index}_invalid_confidence:{confidence}")
        insight_type = as_text(finding.get("insight_type") or finding.get("category"))
        if insight_type in TREND_CATEGORIES:
            if not finding.get("time_window"):
                errors.append(f"finding_{finding_id or index}_trend_missing_time_window")
            if not finding.get("comparison_anchor"):
                errors.append(f"finding_{finding_id or index}_trend_missing_comparison_anchor")
        source_item_refs = finding.get("source_item_refs")
        if not isinstance(source_item_refs, list) or not source_item_refs:
            errors.append(f"finding_{finding_id or index}_missing_source_item_refs")
        anchors = finding.get("evidence_anchors")
        if not isinstance(anchors, list) or not anchors:
            errors.append(f"finding_{finding_id or index}_missing_evidence_anchors")
            continue
        for anchor_index, anchor in enumerate(anchors):
            if not isinstance(anchor, dict):
                errors.append(f"finding_{finding_id}_anchor_{anchor_index}_not_object")
                continue
            errors.extend(validate_anchor(anchor, items, f"finding_{finding_id}"))

    claims = pack.get("report_claims")
    if not isinstance(claims, list):
        errors.append("report_claims_not_list")
        claims = []
    elif not claims and findings:
        errors.append("report_claims_missing")
    elif not findings and not claims and not pack.get("zero_insight_diagnosis"):
        errors.append("zero_insight_diagnosis_missing")
    for index, claim in enumerate(claims):
        if not isinstance(claim, dict):
            errors.append(f"claim_{index}_not_object")
            continue
        finding_id = as_text(claim.get("finding_id"))
        if finding_id not in finding_ids:
            errors.append(f"claim_{index}_unknown_finding_id:{finding_id}")
        if not as_text(claim.get("claim")):
            errors.append(f"claim_{index}_missing_claim")
        source_item_refs = claim.get("source_item_refs")
        if not isinstance(source_item_refs, list) or not source_item_refs:
            errors.append(f"claim_{index}_missing_source_item_refs")
        anchors = claim.get("evidence_anchors")
        if not isinstance(anchors, list) or not anchors:
            errors.append(f"claim_{index}_missing_evidence_anchors")
            continue
        for anchor_index, anchor in enumerate(anchors):
            if not isinstance(anchor, dict):
                errors.append(f"claim_{index}_anchor_{anchor_index}_not_object")
                continue
            errors.extend(validate_anchor(anchor, items, f"claim_{index}"))

    for index, recommendation in enumerate(pack.get("recommendations") or []):
        for finding_id in recommendation.get("based_on_findings") or []:
            if finding_id not in finding_ids:
                errors.append(f"recommendation_{index}_unknown_finding_id:{finding_id}")

    return {"ok": not errors, "errors": errors}


def build_analysis_insight_pack(
    fact_pack: dict[str, Any],
    *,
    fact_pack_ref: str = "",
) -> dict[str, Any]:
    source = finalize_source_fact_pack(fact_pack)
    ref = fact_pack_ref or "crawler_fact_pack.v1.checked.json"
    findings = build_analysis_findings(source)
    recommendations = build_recommendations(findings)
    report_claims = build_report_claims(findings, ref)
    pack = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": utc_now(),
        "source_fact_pack": {
            "ref": ref,
            "schema_version": source.get("schema_version"),
            "platform": source.get("platform"),
            "query": source.get("query"),
            "collected_at": source.get("collected_at"),
            "collection_status": source.get("collection_status"),
        },
        "coverage": {
            "item_count": len(source.get("items") or []),
            "evidence_grades": source.get("fact_summary", {}).get("evidence_grades", {}),
            "missing_fields": source.get("fact_summary", {}).get("missing_fields", {}),
            "media_type_mix": source.get("fact_summary", {}).get("media_type_mix", {}),
            "transcript_coverage": source.get("fact_summary", {}).get("transcript_coverage", {}),
        },
        "findings": findings,
        "report_claims": report_claims,
        "recommendations": recommendations,
    }
    if not findings:
        pack["zero_insight_diagnosis"] = {
            "reason": "no_anchorable_findings",
            "item_count": len(source.get("items") or []),
            "collection_status": source.get("collection_status"),
            "rule": "Do not fabricate analysis when no finding can be traced to crawler_fact_pack.v1.items[].",
        }
    validation = validate_analysis_insight_pack(pack, source)
    pack["validation"] = validation
    pack["report_handoff"] = {
        "ready_for_report": validation["ok"] and bool(report_claims),
        "consumer": "S18/S32/P2/S8",
        "rule": "Every report claim must carry evidence_anchors back to crawler_fact_pack.v1.items[].",
    }
    return pack


def load_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path: str | Path, data: Any) -> None:
    output_path = Path(path).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build analysis_insight_pack.v1 from crawler_fact_pack.v1.")
    parser.add_argument("--input", required=True, help="Input crawler_fact_pack.v1 JSON.")
    parser.add_argument("--output", required=True, help="Output analysis_insight_pack.v1 JSON.")
    parser.add_argument("--fact-pack-ref", default="", help="Stable ref/path written into report claims.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    input_path = Path(args.input).resolve()
    fact_pack = load_json(input_path)
    ref = args.fact_pack_ref or input_path.name
    insight_pack = build_analysis_insight_pack(fact_pack, fact_pack_ref=ref)
    write_json(args.output, insight_pack)
    print(json.dumps(insight_pack["validation"], ensure_ascii=False, indent=2))
    return 0 if insight_pack["validation"]["ok"] else 2


if __name__ == "__main__":
    sys.exit(main())
