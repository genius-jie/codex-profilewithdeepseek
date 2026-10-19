from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "crawler_fact_pack.py"


def load_module():
    spec = importlib.util.spec_from_file_location("crawler_fact_pack", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


crawler_fact_pack = load_module()


def test_fact_pack_fields_and_summary_are_complete(tmp_path: Path):
    pack = crawler_fact_pack.new_fact_pack("xiaohongshu", "AI玩具")
    pack["items"].append(
        crawler_fact_pack.build_item(
            search_record={"title": "视频笔记", "author": "tester", "likes": "1.2万", "url": "https://example.test/note/1"},
            detail={"content": "这是一条正文 #AI玩具", "tags": ["AI玩具"]},
            comments=[{"author": "u1", "text": "太贵了但是有用", "likes": 9}, {"author": "u2", "text": "踩坑了吗", "likes": 3}],
            media_files=[{"path": str(tmp_path / "video.mp4"), "type": "video"}],
            frame_paths=[str(tmp_path / "frame.jpg")],
            data_quality_flags=["video_note"],
        )
    )

    finalized = crawler_fact_pack.finalize_fact_pack(pack)
    finalized["items"][0]["transcript_segments"] = [{"start": 1.0, "end": 2.0, "text": "口播台词", "source": "asr:test"}]
    finalized = crawler_fact_pack.finalize_fact_pack(finalized)

    assert finalized["validation"]["ok"]
    assert finalized["fact_summary"]["item_count"] == 1
    assert finalized["fact_summary"]["media_type_mix"]["video_count"] == 1
    assert finalized["fact_summary"]["transcript_coverage"]["items_with_transcript"] == 1
    assert finalized["items"][0]["metrics"]["likes"] == 12000
    assert finalized["items"][0]["evidence_grade"] == "A_media_frames_comments"
    assert finalized["media_source_receipts"] == []
    assert finalized["media_receipts"] == []
    assert finalized["transcript_review_refs"] == []
    assert finalized["inference"] == []


def test_video_item_without_media_requires_zero_media_flag():
    pack = crawler_fact_pack.new_fact_pack("xiaohongshu", "AI玩具")
    pack["items"].append(
        crawler_fact_pack.build_item(
            search_record={"title": "疑似视频", "url": "https://example.test/note/2"},
            detail={"content": "正文"},
            comments=[],
            media_files=[],
            frame_paths=[],
            data_quality_flags=["video_note"],
        )
    )

    validation = crawler_fact_pack.validate_fact_pack(crawler_fact_pack.finalize_fact_pack(pack))

    assert not validation["ok"]
    assert any("video_without_media_evidence" in error for error in validation["errors"])

    pack["items"][0]["data_quality_flags"].append("zero_media_extracted")
    validation = crawler_fact_pack.validate_fact_pack(crawler_fact_pack.finalize_fact_pack(pack))

    assert validation["ok"]


def test_missing_fields_are_reported():
    pack = crawler_fact_pack.new_fact_pack("generic", "query")
    pack["items"].append(crawler_fact_pack.build_item(search_record={}, detail={}, comments=[]))
    finalized = crawler_fact_pack.finalize_fact_pack(pack)

    assert finalized["validation"]["ok"]
    assert finalized["fact_summary"]["missing_fields"]["title"] == 1
    assert finalized["fact_summary"]["missing_fields"]["media_evidence"] == 1


def test_review_body_pain_terms_include_english_reviews():
    pack = crawler_fact_pack.new_fact_pack("amazon", "Eilik")
    pack["items"].append(
        crawler_fact_pack.build_item(
            search_record={"title": "Eilik app issue", "url": "https://www.amazon.com/product-reviews/B09XGQMSMB"},
            detail={"content": "It stopped working and would not connect. Customer support told me to return it."},
            comments=[],
        )
    )

    finalized = crawler_fact_pack.finalize_fact_pack(pack)
    terms = {row["term"] for row in finalized["fact_summary"]["review_text_high_frequency_pain_terms"]}

    assert finalized["validation"]["ok"]
    assert {"stopped working", "connect", "customer support", "return"} <= terms
