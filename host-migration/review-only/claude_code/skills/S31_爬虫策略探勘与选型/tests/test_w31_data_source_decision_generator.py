import importlib.util
import json
import subprocess
import sys
from pathlib import Path


SCRIPT_PATH = Path(r'@@GENERAL_ROOT:win@@\tooling\w31\w31_data_source_decision_dry_run.py')
ALLOWED_SOURCE_FAMILIES = {
    "official_source",
    "commerce_marketplace",
    "secondhand_marketplace",
    "social_content",
    "search_news",
    "forum_community",
    "map_poi",
    "review_local",
    "developer_registry",
    "finance_market",
    "regulatory_public",
    "generic_web",
    "all",
}


def load_generator():
    spec = importlib.util.spec_from_file_location("w31_data_source_decision_dry_run", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


GENERATOR = load_generator()


def source_families(sources):
    return {source["source_family"] for source in sources}


def product_sales_research_packet():
    return {
        "scenario": "product_sales",
        "entity_type": "product",
        "region_scope": "cn",
        "entity_normalized": "智能猫砂盆",
        "fact_dimensions": ["price", "sku", "promotion", "review_count", "sales_signal"],
        "discovery_methods": [
            "official_entry_check",
            "marketplace_search",
            "social_platform_search",
            "secondhand_platform_search",
        ],
        "discovery_process": {
            "queries": [
                "智能猫砂盆 官方店 价格 SKU",
                "智能猫砂盆 京东 天猫 SKU 评价",
                "智能猫砂盆 小红书 口碑 价格",
                "智能猫砂盆 闲鱼 二手 残值",
            ],
            "platform_checks": [
                "brand official store seller identity checked",
                "JD/Tmall listing fields checked",
                "xiaohongshu note surface checked",
                "xianyu resale listing surface checked",
            ],
            "official_entry_checks": [
                "brand website product navigation",
                "official store seller identity",
            ],
            "notes": ["Agent 调研确认新品销售事实发生在官方售卖面和电商官方店。"],
        },
        "candidate_sources": [
            {
                "source_id": "brand_official_store_cn",
                "platform": "brand official store",
                "source_family": "official_source",
                "role": "primary_fact_source",
                "priority_rank": 1,
                "score": {
                    "fact_authority": 5,
                    "field_coverage": 4,
                    "freshness": 4,
                    "repeatability": 4,
                    "crawl_friction": 3,
                },
                "authority_basis": "品牌官方售卖面最能代表当前官方标价、SKU、库存和促销口径。",
                "target_fields": ["sku", "list_price", "promotion", "inventory_status"],
                "expected_collection_mode": "query_search_data_collection",
                "probe_hint": "S31A 判断官网/官方店是否走 opencli、API、SSR JSON 或 browser fallback。",
                "evidence": ["Agent 已核验官方售卖面直接承载 SKU、官方标价、促销和库存状态。"],
            },
            {
                "source_id": "jd_tmall_official_store",
                "platform": "JD/Tmall official store",
                "source_family": "commerce_marketplace",
                "role": "primary_fact_source",
                "priority_rank": 2,
                "score": {
                    "fact_authority": 4,
                    "field_coverage": 5,
                    "freshness": 5,
                    "repeatability": 4,
                    "crawl_friction": 3,
                },
                "authority_basis": "电商官方店承载实时价格、促销、评价数和 SKU 事实。",
                "target_fields": ["sale_price", "sku", "promotion", "review_count", "seller_name"],
                "expected_collection_mode": "query_search_data_collection",
                "probe_hint": "优先探 OpenCLI/站点 API/SSR JSON，失败后才使用登录浏览器证据。",
                "evidence": ["Agent 已核验电商官方店能给出价格、评价数、SKU 和卖家身份。"],
            },
            {
                "source_id": "xiaohongshu_product_posts",
                "platform": "xiaohongshu",
                "source_family": "social_content",
                "role": "cross_check_source",
                "priority_rank": 3,
                "score": {
                    "fact_authority": 2,
                    "field_coverage": 3,
                    "freshness": 4,
                    "repeatability": 3,
                    "crawl_friction": 3,
                },
                "authority_basis": "社交内容能验证被提及价格和用户口碑，但不代表销售事实。",
                "target_fields": ["note_count", "sentiment_sample", "mentioned_price"],
                "expected_collection_mode": "content_mining_analysis_summary",
                "probe_hint": "仅作为交叉验证和口碑补充进入 S31C。",
                "evidence": ["Agent 已核验小红书可提供口碑和被提及价格，但无法代表官方成交事实。"],
            },
            {
                "source_id": "xianyu_resale_listing",
                "platform": "xianyu",
                "source_family": "secondhand_marketplace",
                "role": "market_signal_source",
                "priority_rank": 4,
                "score": {
                    "fact_authority": 1,
                    "field_coverage": 3,
                    "freshness": 4,
                    "repeatability": 2,
                    "crawl_friction": 2,
                },
                "authority_basis": "二手挂牌可反映残值，但不能代表新品销售价格。",
                "target_fields": ["resale_price", "condition", "listing_age"],
                "expected_collection_mode": "query_search_data_collection",
                "probe_hint": "除非业务目标改为二手行情，否则不进入主链路。",
                "evidence": ["Agent 已核验闲鱼挂牌价格受成色和议价影响，只能作为残值信号。"],
            },
        ],
        "selected_primary_source_ids": ["brand_official_store_cn", "jd_tmall_official_store"],
        "cross_check_source_ids": ["xiaohongshu_product_posts"],
        "excluded_sources": [
            {
                "source_family": "secondhand_marketplace",
                "reason": "二手挂牌反映残值和转卖供需，不代表新品销售事实。",
                "can_be_reintroduced_as": "market_signal_source",
                "evidence": ["二手价格受成色、议价和卖家急售影响，不能作为新品销售主事实源。"],
            },
            {
                "source_family": "generic_web",
                "reason": "通用网页可做发现入口，但缺少交易事实权威性。",
                "can_be_reintroduced_as": "discovery_source",
                "evidence": ["通用网页可能转载价格或导购内容，来源链路不稳定。"],
            },
        ],
        "decision_trace": [
            "Agent 先把业务目标归为新品商品销售分析，而不是二手行情或纯口碑。",
            "官方售卖面和电商官方店在业务事实权威性上高于社交和二手平台。",
            "社交平台保留为口碑交叉验证，二手平台排除出主链。",
        ],
        "confidence": "high",
    }


def assert_receipt_contract(receipt):
    assert receipt["schema_version"] == "data_source_decision_receipt.v1"
    assert receipt["decision_basis"] == [
        "business_fact_authority",
        "field_coverage",
        "freshness",
        "repeatability",
        "crawl_friction",
    ]

    required = {
        "business_goal",
        "entity_type",
        "region_scope",
        "fact_dimensions",
        "research_depth",
        "discovery_process",
        "source_evidence",
        "candidate_sources",
        "selected_primary_sources",
        "cross_check_sources",
        "excluded_sources",
        "exclusion_evidence",
        "decision_trace",
        "confidence",
        "clarification_needed",
        "next_s31a_targets",
    }
    assert required.issubset(receipt.keys())

    all_sources = (
        receipt["candidate_sources"]
        + receipt["selected_primary_sources"]
        + receipt["cross_check_sources"]
        + receipt["excluded_sources"]
    )
    for source in all_sources:
        assert source["source_family"] in ALLOWED_SOURCE_FAMILIES


def assert_completed_agent_receipt(receipt):
    assert_receipt_contract(receipt)
    assert receipt["analysis_mode"] == "agent_research_compiled"
    assert receipt["source_selection_owner"] == "agent_research"
    assert receipt["research_depth"]["status"] == "completed"
    assert receipt["research_depth"]["minimum_depth_met"] is True
    assert receipt["research_gaps"] == []
    assert receipt["selected_primary_sources"]
    assert receipt["cross_check_sources"]
    assert receipt["next_s31a_targets"]

    for source in receipt["selected_primary_sources"] + receipt["cross_check_sources"]:
        assert source["source_id"] in receipt["source_evidence"]
        assert receipt["source_evidence"][source["source_id"]]

    for source in receipt["excluded_sources"]:
        assert source["source_family"] in receipt["exclusion_evidence"]
        assert receipt["exclusion_evidence"][source["source_family"]]

    for target in receipt["next_s31a_targets"]:
        assert target["source_decision_ref"] == receipt["source_decision_ref"]
        assert target["source_id"]
        assert target["source_family"] in ALLOWED_SOURCE_FAMILIES
        assert target["source_role"]
        assert isinstance(target["source_priority_rank"], int)
        assert target["collection_mode"] in {
            "query_search_data_collection",
            "content_mining_analysis_summary",
        }


def test_generator_without_agent_research_only_emits_research_brief():
    receipt = GENERATOR.generate_receipt(
        "针对某款智能猫砂盆做当前价格、SKU、促销和销售分析",
        source_decision_ref="seed.data_source_decision_receipt.v1.json",
    )

    assert_receipt_contract(receipt)
    assert receipt["analysis_mode"] == "agent_research_brief"
    assert receipt["agent_research_required"] is True
    assert receipt["research_depth"]["status"] == "needs_agent_research"
    assert receipt["research_depth"]["minimum_depth_met"] is False
    assert receipt["source_evidence"] == {}
    assert receipt["selected_primary_sources"] == []
    assert receipt["cross_check_sources"] == []
    assert receipt["next_s31a_targets"] == []
    assert receipt["candidate_sources"]
    assert "agent_research_json_missing" in receipt["research_gaps"]


def test_generator_compiles_agent_research_into_formal_receipt():
    receipt = GENERATOR.generate_receipt(
        "针对某款智能猫砂盆做当前价格、SKU、促销和销售分析",
        source_decision_ref="product_sales.generated.json",
        agent_research=product_sales_research_packet(),
    )

    assert_completed_agent_receipt(receipt)
    assert receipt["scenario"] == "product_sales"
    assert {"official_source", "commerce_marketplace"}.issubset(
        source_families(receipt["selected_primary_sources"])
    )
    assert "social_content" not in source_families(receipt["selected_primary_sources"])
    assert "social_content" in source_families(receipt["cross_check_sources"])
    assert any(source["source_family"] == "secondhand_marketplace" for source in receipt["excluded_sources"])


def test_generator_blocks_incomplete_agent_research_before_s31a():
    research = product_sales_research_packet()
    research["candidate_sources"][0]["evidence"] = []
    research["cross_check_source_ids"] = []
    research["excluded_sources"] = []

    receipt = GENERATOR.generate_receipt(
        "针对某款智能猫砂盆做当前价格、SKU、促销和销售分析",
        agent_research=research,
    )

    assert_receipt_contract(receipt)
    assert receipt["analysis_mode"] == "agent_research_compiled"
    assert receipt["research_depth"]["status"] == "agent_research_incomplete"
    assert receipt["research_depth"]["minimum_depth_met"] is False
    assert receipt["confidence"] == "low"
    assert receipt["research_gaps"]
    assert receipt["next_s31a_targets"] == []


def test_generator_blocks_ambiguous_request_before_research():
    receipt = GENERATOR.generate_receipt("帮我爬一下这个东西看看情况")

    assert_receipt_contract(receipt)
    assert receipt["scenario"] == "ambiguous_request"
    assert receipt["clarification_needed"] is True
    assert receipt["entity_type"] == "unknown"
    assert receipt["region_scope"] == "unknown"
    assert receipt["next_s31a_targets"] == []


def test_generator_cli_writes_completed_receipt_from_agent_research(tmp_path):
    research_path = tmp_path / "agent_research.json"
    output = tmp_path / "pet_sales.data_source_decision_receipt.v1.json"
    research_path.write_text(json.dumps(product_sales_research_packet(), ensure_ascii=False), encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "针对某款智能猫砂盆做价格和销售分析",
            "--agent-research-json",
            str(research_path),
            "--output",
            str(output),
            "--pretty",
        ],
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=30,
    )

    assert result.returncode == 0, result.stderr
    receipt = json.loads(output.read_text(encoding="utf-8"))
    assert_completed_agent_receipt(receipt)
    assert receipt["source_decision_ref"] == output.name
    assert all(target["source_decision_ref"] == output.name for target in receipt["next_s31a_targets"])
