from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "analysis_insight_pack.py"


def load_module():
    spec = importlib.util.spec_from_file_location("analysis_insight_pack", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


analysis_insight_pack = load_module()


def sample_fact_pack() -> dict:
    return {
        "schema_version": "crawler_fact_pack.v1",
        "platform": "xiaohongshu",
        "query": "AI玩具",
        "collected_at": "2026-06-10T00:00:00Z",
        "collection_status": "ok",
        "items": [
            {
                "title": "AI陪伴玩具避雷",
                "author": "u1",
                "body": "孩子喜欢互动，但价格偏高，家长担心内容不稳定。",
                "tags": ["AI玩具", "陪伴"],
                "metrics": {"likes": 1200, "comments": 18},
                "top_comments": [
                    {"author": "c1", "text": "太贵了但孩子喜欢", "likes": 9},
                    {"author": "c2", "text": "担心内容不稳定", "likes": 3},
                ],
                "source_url": "https://xhs.example/note/1",
                "media_files": [{"path": "cover.jpg", "type": "image"}],
                "frame_paths": [],
                "data_quality_flags": [],
                "evidence_grade": "",
            },
            {
                "title": "AI故事机测评",
                "author": "u2",
                "body": "语音反应快，适合睡前故事，但功能比较单一。",
                "tags": ["故事机"],
                "metrics": {"likes": 800, "comments": 5},
                "top_comments": [{"author": "c3", "text": "睡前故事好用", "likes": 4}],
                "source_url": "https://xhs.example/note/2",
                "media_files": [],
                "frame_paths": [],
                "data_quality_flags": [],
                "evidence_grade": "",
            },
        ],
        "fact_summary": {},
        "command_receipts": [],
        "inference": [],
    }


def test_build_insight_pack_keeps_every_report_claim_anchored():
    pack = analysis_insight_pack.build_analysis_insight_pack(
        sample_fact_pack(),
        fact_pack_ref="crawler_fact_pack.v1.checked.json",
    )

    assert pack["schema_version"] == "analysis_insight_pack.v1"
    assert pack["validation"]["ok"]
    assert pack["source_fact_pack"]["ref"] == "crawler_fact_pack.v1.checked.json"
    assert pack["coverage"]["item_count"] == 2
    assert pack["findings"]
    assert pack["report_claims"]
    assert {finding["finding_id"] for finding in pack["findings"]} >= {
        "metric_likes_leader",
        "pain_terms_from_comments",
    }
    assert all(finding["evidence_anchors"] for finding in pack["findings"])
    assert all(finding["source_item_refs"] for finding in pack["findings"])
    assert all(finding["basis"] for finding in pack["findings"])
    assert all(claim["evidence_anchors"] for claim in pack["report_claims"])
    assert all(claim["source_item_refs"] for claim in pack["report_claims"])
    assert all(claim["finding_id"] in {finding["finding_id"] for finding in pack["findings"]} for claim in pack["report_claims"])


def test_english_review_body_pain_terms_are_report_claims():
    fact_pack = sample_fact_pack()
    fact_pack["platform"] = "tophub_competitor_e2e"
    fact_pack["items"] = [
        {
            "title": "amazon / customer_service",
            "author": "buyer",
            "body": "The app issue kept coming back. It stopped working, would not connect, and customer support asked me to return it.",
            "tags": ["competitor:eilik", "source:amazon", "negative"],
            "metrics": {"negative_signal": 1},
            "top_comments": [],
            "source_url": "https://www.amazon.com/product-reviews/B09XGQMSMB",
            "media_files": [],
            "frame_paths": [],
            "data_quality_flags": [],
            "evidence_grade": "",
        }
    ]

    pack = analysis_insight_pack.build_analysis_insight_pack(fact_pack)
    finding = next(item for item in pack["findings"] if item["finding_id"] == "pain_terms_from_review_text")

    assert pack["validation"]["ok"]
    assert finding["evidence_anchors"][0]["field"] == "body"
    assert "app issue" in finding["statement"]
    assert any(claim["finding_id"] == "pain_terms_from_review_text" for claim in pack["report_claims"])


def test_unanchored_agent_finding_is_rejected():
    pack = analysis_insight_pack.build_analysis_insight_pack(sample_fact_pack())
    pack["findings"].append(
        {
            "finding_id": "agent_fabricated_market_trend",
            "category": "market_trend",
            "priority": "high",
            "statement": "AI玩具已经全面进入爆发期。",
            "confidence": 0.92,
            "evidence_anchors": [],
        }
    )

    validation = analysis_insight_pack.validate_analysis_insight_pack(pack, sample_fact_pack())

    assert not validation["ok"]
    assert "finding_agent_fabricated_market_trend_missing_evidence_anchors" in validation["errors"]
    assert "finding_agent_fabricated_market_trend_missing_basis" in validation["errors"]
    assert "finding_agent_fabricated_market_trend_missing_source_item_refs" in validation["errors"]
    assert "finding_agent_fabricated_market_trend_trend_missing_time_window" in validation["errors"]
    assert "finding_agent_fabricated_market_trend_trend_missing_comparison_anchor" in validation["errors"]


def test_trend_finding_requires_time_window_and_comparison_anchor():
    pack = analysis_insight_pack.build_analysis_insight_pack(sample_fact_pack())
    anchor = pack["findings"][0]["evidence_anchors"][0]
    pack["findings"].append(
        {
            "finding_id": "week_over_week_review_trend",
            "category": "market_trend",
            "insight_type": "market_trend",
            "priority": "high",
            "statement": "本周评论里的价格敏感度高于上周。",
            "basis": "使用本周评论样本与上周同源样本对比得到。",
            "confidence": 0.72,
            "evidence_anchors": [anchor],
            "source_item_refs": analysis_insight_pack.source_item_refs_from_anchors([anchor]),
        }
    )

    validation = analysis_insight_pack.validate_analysis_insight_pack(pack, sample_fact_pack())

    assert not validation["ok"]
    assert "finding_week_over_week_review_trend_trend_missing_time_window" in validation["errors"]
    assert "finding_week_over_week_review_trend_trend_missing_comparison_anchor" in validation["errors"]


def test_zero_item_pack_emits_zero_insight_diagnosis():
    empty_pack = sample_fact_pack()
    empty_pack["items"] = []
    empty_pack["collection_status"] = "failed"
    pack = analysis_insight_pack.build_analysis_insight_pack(empty_pack)

    assert pack["validation"]["ok"]
    assert pack["findings"] == []
    assert pack["report_claims"] == []
    assert pack["report_handoff"]["ready_for_report"] is False
    assert pack["zero_insight_diagnosis"]["reason"] == "no_anchorable_findings"


def test_invalid_item_anchor_is_rejected():
    pack = analysis_insight_pack.build_analysis_insight_pack(sample_fact_pack())
    pack["findings"][0]["evidence_anchors"][0]["item_index"] = 99

    validation = analysis_insight_pack.validate_analysis_insight_pack(pack, sample_fact_pack())

    assert not validation["ok"]
    assert any("anchor_item_index_out_of_range" in error for error in validation["errors"])


def test_cli_writes_analysis_insight_pack(tmp_path: Path):
    input_path = tmp_path / "crawler_fact_pack.v1.checked.json"
    output_path = tmp_path / "analysis_insight_pack.v1.json"
    input_path.write_text(json.dumps(sample_fact_pack(), ensure_ascii=False), encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--input",
            str(input_path),
            "--output",
            str(output_path),
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    written = json.loads(output_path.read_text(encoding="utf-8"))
    assert written["schema_version"] == "analysis_insight_pack.v1"
    assert written["validation"]["ok"]
    assert written["report_handoff"]["ready_for_report"] is True
