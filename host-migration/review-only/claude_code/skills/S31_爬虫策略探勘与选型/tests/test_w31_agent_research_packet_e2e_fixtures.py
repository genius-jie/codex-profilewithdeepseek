import json
import subprocess
import sys
from pathlib import Path


RUNNER_PATH = Path(r'@@GENERAL_ROOT:win@@\tooling\w31\w31_agent_research_packet_runner.py')
FIXTURE_DIR = Path(
    r'@@GENERAL_ROOT:win@@\assets\skills\S31_爬虫策略探勘与选型\examples\agent_research_packet_e2e'
)


CASES = [
    {
        "case_id": "airpods_pro_3_product_sales",
        "query": "针对 AirPods Pro 3 做价格 SKU 促销 销售分析",
        "min_candidate_evidence": 4,
        "primary_families": {"official_source", "commerce_marketplace"},
        "cross_families": {"social_content"},
        "excluded_families": {"secondhand_marketplace", "generic_web"},
        "forbidden_primary_families": {"secondhand_marketplace", "social_content"},
        "draft_primary_families": {"official_source", "commerce_marketplace"},
        "draft_cross_families": {"social_content"},
        "draft_excluded_families": {"secondhand_marketplace"},
    },
    {
        "case_id": "ai_companion_robot_privacy_topic",
        "query": "针对 AI 陪伴机器人隐私争议做舆情 热度 负面讨论分析",
        "min_candidate_evidence": 3,
        "primary_families": {"social_content"},
        "cross_families": {"search_news"},
        "excluded_families": {"commerce_marketplace", "official_source"},
        "forbidden_primary_families": {"commerce_marketplace", "official_source"},
        "draft_primary_families": {"social_content"},
        "draft_cross_families": {"search_news"},
        "draft_excluded_families": {"commerce_marketplace", "official_source"},
    },
]


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def case_path(case_id: str, suffix: str) -> Path:
    return FIXTURE_DIR / f"{case_id}.{suffix}"


def generated_case(case: dict, tmp_path: Path) -> tuple[dict, dict]:
    case_id = case["case_id"]
    packet_path = tmp_path / f"{case_id}.w31_agent_research_packet.v1.json"
    draft_path = tmp_path / f"{case_id}.w31_agent_synthesis_draft.v1.json"
    receipt_path = tmp_path / f"{case_id}.data_source_decision_receipt.v1.json"
    source_decision_ref = f"{case_id}.data_source_decision_receipt.v1.json"

    result = subprocess.run(
        [
            sys.executable,
            str(RUNNER_PATH),
            case["query"],
            "--provider",
            "fixture",
            "--search-fixture-json",
            str(case_path(case_id, "search_fixture.json")),
            "--browser-fixture-json",
            str(case_path(case_id, "browser_fixture.json")),
            "--synthesis-json",
            str(case_path(case_id, "agent_synthesis.json")),
            "--output-packet",
            str(packet_path),
            "--output-synthesis-draft",
            str(draft_path),
            "--output-receipt",
            str(receipt_path),
            "--source-decision-ref",
            source_decision_ref,
            "--pretty",
        ],
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=30,
    )

    assert result.returncode == 0, result.stderr
    return load_json(packet_path), load_json(draft_path), load_json(receipt_path)


def family_set(items: list[dict]) -> set[str]:
    return {str(item.get("source_family")) for item in items}


def ids(items: list[dict]) -> set[str]:
    return {str(item.get("source_id")) for item in items}


def assert_packet_and_receipt(case: dict, packet: dict, receipt: dict) -> None:
    assert packet["schema_version"] == "w31_agent_research_packet.v1"
    assert packet["analysis_input_ready"] is True
    assert packet["agent_review_required"] is False
    assert packet["research_execution_chain"]["search_provider"] == "fixture"
    assert packet["research_execution_chain"]["candidate_evidence_count"] >= case["min_candidate_evidence"]
    assert all(source.get("evidence") for source in packet["candidate_sources"])

    assert receipt["schema_version"] == "data_source_decision_receipt.v1"
    assert receipt["analysis_mode"] == "agent_research_compiled"
    assert receipt["source_selection_owner"] == "agent_research"
    assert receipt["research_depth"]["status"] == "completed"
    assert receipt["research_depth"]["minimum_depth_met"] is True
    assert receipt["research_gaps"] == []

    primary_families = family_set(receipt["selected_primary_sources"])
    cross_families = family_set(receipt["cross_check_sources"])
    excluded_families = family_set(receipt["excluded_sources"])
    assert case["primary_families"] <= primary_families
    assert case["cross_families"] <= cross_families
    assert case["excluded_families"] <= excluded_families
    assert primary_families.isdisjoint(case["forbidden_primary_families"])

    selected_ids = ids(receipt["selected_primary_sources"]) | ids(receipt["cross_check_sources"])
    assert ids(receipt["selected_primary_sources"]).isdisjoint(ids(receipt["cross_check_sources"]))
    assert {target["source_id"] for target in receipt["next_s31a_targets"]} == selected_ids
    assert all(
        target["source_decision_ref"] == f"{case['case_id']}.data_source_decision_receipt.v1.json"
        for target in receipt["next_s31a_targets"]
    )
    assert all(item.get("reason") for item in receipt["excluded_sources"])


def test_real_agent_research_packet_fixtures_replay_to_receipts(tmp_path):
    for case in CASES:
        packet, draft, receipt = generated_case(case, tmp_path)
        assert_packet_and_receipt(case, packet, receipt)
        assert packet == load_json(case_path(case["case_id"], "w31_agent_research_packet.v1.json"))
        assert draft == load_json(case_path(case["case_id"], "w31_agent_synthesis_draft.v1.json"))
        assert receipt == load_json(case_path(case["case_id"], "data_source_decision_receipt.v1.json"))
        assert {item["source_family"] for item in draft["candidate_summary"] if item["draft_decision"] == "primary"} == case[
            "draft_primary_families"
        ]
        assert {item["source_family"] for item in draft["candidate_summary"] if item["draft_decision"] == "cross_check"} == case[
            "draft_cross_families"
        ]
        assert {item["source_family"] for item in draft["proposed_excluded_sources"]} == case["draft_excluded_families"]
