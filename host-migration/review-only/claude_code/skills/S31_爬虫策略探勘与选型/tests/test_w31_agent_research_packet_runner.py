import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


RUNNER_PATH = Path(r'@@GENERAL_ROOT:win@@\tooling\w31\w31_agent_research_packet_runner.py')
GENERATOR_PATH = Path(r'@@GENERAL_ROOT:win@@\tooling\w31\w31_data_source_decision_dry_run.py')


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


RUNNER = load_module("w31_agent_research_packet_runner", RUNNER_PATH)
GENERATOR = load_module("w31_data_source_decision_dry_run", GENERATOR_PATH)


def seed_queries():
    seed = GENERATOR.generate_receipt("针对某款智能猫砂盆做价格和销售分析")
    return seed["discovery_process"]["queries"]


def search_fixture():
    q1, q2, q3, q4 = seed_queries()
    return {
        q1: [
            {
                "title": "Smart Litter Box Official Store - SKU and promotion",
                "url": "https://brand.example/products/smart-litter-box",
                "snippet": "Official product page lists SKU, list price, promotion and inventory status.",
            }
        ],
        q2: [
            {
                "title": "JD/Tmall official store smart litter box reviews",
                "url": "https://mall.example/item/smart-litter-box",
                "snippet": "JD Tmall listing shows sale price, SKU, promotion and review count.",
            }
        ],
        q3: [
            {
                "title": "xiaohongshu smart litter box user notes",
                "url": "https://social.example/note/smart-litter-box",
                "snippet": "Xiaohongshu notes mention user sentiment and prices but not official sales facts.",
            }
        ],
        q4: [
            {
                "title": "xianyu smart litter box resale listings",
                "url": "https://resale.example/search/smart-litter-box",
                "snippet": "Xianyu listings show used price, condition and listing age.",
            }
        ],
    }


def browser_fixture():
    return {
        "https://brand.example/products/smart-litter-box": {
            "title": "Official Smart Litter Box",
            "text_sample": "brand official store SKU list_price promotion inventory",
        },
        "https://mall.example/item/smart-litter-box": {
            "title": "JD Tmall Official Store Smart Litter Box",
            "text_sample": "JD Tmall sale price SKU promotion review count seller name",
        },
        "https://social.example/note/smart-litter-box": {
            "title": "Xiaohongshu user note",
            "text_sample": "xiaohongshu note sentiment mentioned price user experience",
        },
        "https://resale.example/search/smart-litter-box": {
            "title": "Xianyu resale listings",
            "text_sample": "xianyu resale price condition listing age",
        },
    }


class FakePlaywrightPage:
    def __init__(self):
        self.url = ""
        self.closed = False

    def goto(self, url, wait_until, timeout):
        self.url = f"{url}?rendered=1"
        return SimpleNamespace(status=200, url=self.url)

    def wait_for_load_state(self, state, timeout):
        return None

    def title(self):
        return "Rendered Dynamic Product Page"

    def evaluate(self, script):
        if "meta[name=" in script:
            return "Client-rendered description from the page head."
        if "document.body" in script:
            return "Rendered body text with SKU, price, promotion and review count."
        return ""

    def content(self):
        return "<html><body>Rendered body text</body></html>"

    def close(self):
        self.closed = True


class FakePlaywrightContext:
    def __init__(self):
        self.page = FakePlaywrightPage()
        self.closed = False

    def new_page(self):
        return self.page

    def close(self):
        self.closed = True


class FakePlaywrightBrowser:
    def __init__(self):
        self.contexts = []
        self.context = FakePlaywrightContext()

    def new_context(self):
        return self.context


class FakePlaywrightManager:
    def __enter__(self):
        self.browser = FakePlaywrightBrowser()
        self.chromium = SimpleNamespace(connect_over_cdp=lambda endpoint: self.browser)
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def fake_sync_playwright():
    return FakePlaywrightManager()


def synthesis():
    return {
        "selected_primary_source_ids": ["brand_official_store_cn", "jd_tmall_official_store"],
        "cross_check_source_ids": ["xiaohongshu_product_posts"],
        "excluded_sources": [
            {
                "source_family": "secondhand_marketplace",
                "reason": "二手挂牌反映残值和转卖供需，不代表新品销售事实。",
                "can_be_reintroduced_as": "market_signal_source",
                "evidence": ["xianyu fixture only showed resale price, condition and listing age."],
            },
            {
                "source_family": "generic_web",
                "reason": "通用网页可做发现入口，但缺少交易事实权威性。",
                "can_be_reintroduced_as": "discovery_source",
                "evidence": ["No generic web source in this packet had official seller identity or SKU authority."],
            },
        ],
        "decision_trace": [
            "Agent read search and browser evidence and classified the task as product sales.",
            "Official store and marketplace pages carry SKU, promotion, price and review facts.",
            "Social content is retained only as reputation cross-check; resale source is excluded from primary facts.",
        ],
        "confidence": "high",
        "basis": "Agent synthesis over search/browser evidence selected fact-source roles.",
    }


def write_fixture(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def packet_without_synthesis():
    return RUNNER.build_research_packet(
        "针对某款智能猫砂盆做价格和销售分析",
        region=None,
        provider="fixture",
        search_fixture=search_fixture(),
        browser_fixture=browser_fixture(),
        max_results=5,
        browser_limit=8,
        timeout=2,
        synthesis=None,
        source_decision_ref="packet.generated.json",
    )


def test_browser_probe_can_collect_playwright_cdp_page_evidence(monkeypatch):
    monkeypatch.setattr(RUNNER, "load_playwright", lambda: fake_sync_playwright)

    receipts = RUNNER.browser_probe(
        ["https://dynamic.example/product"],
        fixture={},
        limit=1,
        timeout=2,
        provider="playwright_cdp",
        cdp_endpoint="http://127.0.0.1:9222",
    )

    assert len(receipts) == 1
    receipt = receipts[0]
    assert receipt["provider"] == "playwright_cdp"
    assert receipt["status"] == "ok"
    assert receipt["http_status"] == 200
    assert receipt["url"] == "https://dynamic.example/product"
    assert receipt["final_url"] == "https://dynamic.example/product?rendered=1"
    assert receipt["domain"] == "dynamic.example"
    assert receipt["title"] == "Rendered Dynamic Product Page"
    assert receipt["description"] == "Client-rendered description from the page head."
    assert "SKU, price, promotion" in receipt["text_sample"]
    assert receipt["body_text_length"] >= len(receipt["text_sample"])
    assert receipt["html_length"] > 0
    assert receipt["cdp_endpoint"] == "http://127.0.0.1:9222"


def test_browser_probe_fixture_stays_deterministic_even_when_cdp_provider_is_requested(monkeypatch):
    def fail_if_playwright_is_loaded():
        raise AssertionError("fixture browser evidence must not invoke Playwright")

    monkeypatch.setattr(RUNNER, "load_playwright", fail_if_playwright_is_loaded)

    receipts = RUNNER.browser_probe(
        ["https://brand.example/products/smart-litter-box"],
        fixture=browser_fixture(),
        limit=1,
        timeout=2,
        provider="playwright_cdp",
        cdp_endpoint="http://127.0.0.1:9222",
    )

    assert receipts == [
        {
            "url": "https://brand.example/products/smart-litter-box",
            "provider": "fixture_browser_probe",
            "status": "ok",
            "http_status": 200,
            "title": "Official Smart Litter Box",
            "description": "",
            "text_sample": "brand official store SKU list_price promotion inventory",
            "domain": "brand.example",
        }
    ]


def test_attach_evidence_requires_platform_url_or_page_match_not_query_only():
    candidates = [
        {
            "source_id": "xiaohongshu_topic_search",
            "platform": "xiaohongshu",
            "source_family": "social_content",
            "hypothesis_role": "sentiment_source",
        }
    ]
    search_receipts = [
        {
            "query": "AI 陪伴机器人隐私争议 小红书 体验 负面",
            "provider": "fixture",
            "status": "ok",
            "results": [
                {
                    "title": "Generic AI tool directory",
                    "url": "https://ai-bot.example/",
                    "snippet": "Directory page with generic AI tools.",
                },
                {
                    "title": "小红书 AI 陪伴机器人隐私争议用户讨论",
                    "url": "https://www.xiaohongshu.com/search_result?keyword=AI",
                    "snippet": "Users discuss privacy concerns and negative experiences.",
                },
            ],
        }
    ]
    browser_receipts = [
        {
            "url": "https://ai-bot.example/",
            "provider": "fixture_browser_probe",
            "status": "ok",
            "title": "AI tool directory",
            "description": "",
            "text_sample": "Generic AI tools and navigation.",
            "domain": "ai-bot.example",
        },
        {
            "url": "https://www.xiaohongshu.com/search_result?keyword=AI",
            "provider": "fixture_browser_probe",
            "status": "ok",
            "title": "小红书 AI 陪伴机器人隐私争议用户讨论",
            "description": "",
            "text_sample": "小红书 用户 负面 体验 隐私 争议",
            "domain": "www.xiaohongshu.com",
        },
    ]

    attached = RUNNER.attach_evidence_to_candidates(candidates, search_receipts, browser_receipts)

    assert attached[0]["observed_urls"] == ["https://www.xiaohongshu.com/search_result?keyword=AI"]
    assert len(attached[0]["evidence"]) == 1
    assert "ai-bot.example" not in attached[0]["evidence"][0]


def test_source_matches_observation_rejects_jd_tmall_query_term_when_result_is_official_page():
    source = {
        "source_id": "jd_tmall_official_store",
        "platform": "JD/Tmall official store",
        "source_family": "commerce_marketplace",
    }
    result = {
        "title": "AirPods - Apple",
        "url": "https://www.apple.com/airpods/",
        "snippet": "Apple official AirPods product family page.",
    }
    page = {
        "title": "AirPods - Apple",
        "description": "",
        "text_sample": "Apple AirPods product comparison.",
    }

    assert (
        RUNNER.source_matches_observation(
            source,
            result,
            page,
            "AirPods Pro 3 SKU 京东 天猫 SKU 评价",
        )
        is False
    )


def test_platform_supplemental_queries_use_candidate_domains_not_query_platform_words():
    candidate = {
        "source_id": "xiaohongshu_topic_search",
        "platform": "xiaohongshu",
        "source_family": "social_content",
        "role": "sentiment_source",
    }

    queries = RUNNER.platform_supplemental_queries(
        "针对 AI 陪伴机器人隐私争议做舆情 热度 负面讨论分析",
        candidate,
        max_queries=2,
    )

    assert queries == [
        'site:xiaohongshu.com "AI 陪伴机器人隐私争议" 小红书',
        'site:xiaohongshu.com "AI 陪伴机器人隐私争议" 负面 体验',
    ]


def test_runner_adds_platform_supplemental_search_when_primary_platform_evidence_is_missing(monkeypatch):
    def fake_generate_receipt(query, region=None, source_decision_ref=""):
        return {
            "scenario": "social_topic_opinion",
            "entity_type": "topic",
            "region_scope": "cn",
            "fact_dimensions": ["mention_volume", "sentiment_sample", "negative_feedback"],
            "decision_basis": ["business_fact_authority"],
            "research_depth": {
                "entity_normalized": "AI 陪伴机器人隐私争议",
                "discovery_methods": ["business_goal_parse"],
            },
            "discovery_process": {
                "queries": ["AI 陪伴机器人隐私争议 小红书 体验 负面"],
                "official_entry_checks": [],
                "notes": [],
            },
            "candidate_sources": [
                {
                    "source_id": "xiaohongshu_topic_search",
                    "platform": "xiaohongshu",
                    "source_family": "social_content",
                    "hypothesis_role": "sentiment_source",
                    "priority_rank": 1,
                    "score": {"total": 21},
                    "authority_basis": "话题口碑发生在小红书。",
                    "target_fields": ["note_title", "note_text"],
                    "expected_collection_mode": "content_mining_analysis_summary",
                }
            ],
        }

    monkeypatch.setattr(RUNNER.GENERATOR, "generate_receipt", fake_generate_receipt)
    search_fixture_data = {
        "AI 陪伴机器人隐私争议 小红书 体验 负面": [
            {
                "title": "Generic AI tool directory",
                "url": "https://ai-bot.example/",
                "snippet": "Directory page with generic AI tools.",
            }
        ],
        'site:xiaohongshu.com "AI 陪伴机器人隐私争议" 小红书': [
            {
                "title": "小红书 AI 陪伴机器人隐私争议用户讨论",
                "url": "https://www.xiaohongshu.com/search_result?keyword=AI",
                "snippet": "小红书用户讨论隐私争议和负面体验。",
            }
        ],
    }
    browser_fixture_data = {
        "https://ai-bot.example/": {
            "title": "AI tool directory",
            "text_sample": "Generic AI tools and navigation.",
        },
        "https://www.xiaohongshu.com/search_result?keyword=AI": {
            "title": "小红书 AI 陪伴机器人隐私争议用户讨论",
            "text_sample": "小红书 用户 负面 体验 隐私 争议",
        },
    }

    packet = RUNNER.assemble_research_packet(
        "针对 AI 陪伴机器人隐私争议做舆情 热度 负面讨论分析",
        region=None,
        provider="fixture",
        search_fixture=search_fixture_data,
        browser_fixture=browser_fixture_data,
        max_results=5,
        browser_limit=8,
        timeout=2,
        source_decision_ref="receipt.generated.json",
    )

    assert packet["candidate_sources"][0]["observed_urls"] == [
        "https://www.xiaohongshu.com/search_result?keyword=AI"
    ]
    assert "ai-bot.example" not in packet["candidate_sources"][0]["evidence"][0]
    supplemental = packet["research_execution_chain"]["platform_supplemental_search"]
    assert supplemental["triggered"] is True
    assert 'site:xiaohongshu.com "AI 陪伴机器人隐私争议" 小红书' in supplemental["queries"]
    assert supplemental["missing_source_ids"] == ["xiaohongshu_topic_search"]


def test_runner_uses_platform_adapter_for_missing_native_platform_evidence(monkeypatch):
    def fake_generate_receipt(query, region=None, source_decision_ref=""):
        return {
            "scenario": "social_topic_opinion",
            "entity_type": "topic",
            "region_scope": "cn",
            "fact_dimensions": ["mention_volume", "sentiment_sample", "negative_feedback"],
            "decision_basis": ["business_fact_authority"],
            "research_depth": {
                "entity_normalized": "AI 陪伴机器人隐私争议",
                "discovery_methods": ["business_goal_parse"],
            },
            "discovery_process": {
                "queries": ["AI 陪伴机器人隐私争议 小红书 体验 负面"],
                "official_entry_checks": [],
                "notes": [],
            },
            "candidate_sources": [
                {
                    "source_id": "xiaohongshu_topic_search",
                    "platform": "xiaohongshu",
                    "source_family": "social_content",
                    "hypothesis_role": "sentiment_source",
                    "priority_rank": 1,
                    "score": {"total": 21},
                    "authority_basis": "话题口碑发生在小红书。需要平台原生搜索补齐真实入口。",
                    "target_fields": ["note_title", "note_text"],
                    "expected_collection_mode": "content_mining_analysis_summary",
                }
            ],
        }

    monkeypatch.setattr(RUNNER.GENERATOR, "generate_receipt", fake_generate_receipt)
    packet = RUNNER.assemble_research_packet(
        "针对 AI 陪伴机器人隐私争议做舆情 热度 负面讨论分析",
        region=None,
        provider="fixture",
        search_fixture={
            "AI 陪伴机器人隐私争议 小红书 体验 负面": [
                {
                    "title": "Generic AI tool directory",
                    "url": "https://ai-bot.example/",
                    "snippet": "Directory page with generic AI tools.",
                }
            ]
        },
        browser_fixture={
            "https://ai-bot.example/": {
                "title": "AI tool directory",
                "text_sample": "Generic AI tools and navigation.",
            },
            "https://www.xiaohongshu.com/explore/abc123": {
                "title": "小红书 AI 陪伴机器人隐私争议用户讨论",
                "text_sample": "小红书 用户 负面 体验 隐私 争议",
            },
        },
        platform_supplemental_provider="adapter",
        platform_adapter_provider="fixture",
        platform_adapter_fixture={
            "xiaohongshu": {
                "AI 陪伴机器人隐私争议": [
                    {
                        "title": "小红书 AI 陪伴机器人隐私争议用户讨论",
                        "url": "https://www.xiaohongshu.com/explore/abc123",
                        "snippet": "小红书用户讨论隐私争议和负面体验。",
                    }
                ]
            }
        },
        max_results=5,
        browser_limit=8,
        timeout=2,
        source_decision_ref="receipt.generated.json",
    )

    assert packet["candidate_sources"][0]["observed_urls"] == ["https://www.xiaohongshu.com/explore/abc123"]
    supplemental = packet["research_execution_chain"]["platform_supplemental_search"]
    assert supplemental["provider"] == "adapter"
    assert supplemental["public_search_receipt_count"] == 0
    assert supplemental["adapter_provider"] == "fixture"
    assert supplemental["adapter_queries"] == ["AI 陪伴机器人隐私争议"]
    assert supplemental["adapter_receipt_count"] == 1
    assert supplemental["adapter_statuses"] == ["xiaohongshu_topic_search:xiaohongshu:ok"]


def test_opencli_platform_adapter_uses_native_search_command_and_normalizes_json(monkeypatch):
    captured = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs
        return SimpleNamespace(
            returncode=0,
            stdout=json.dumps(
                [
                    {
                        "rank": 1,
                        "title": "京东 AirPods Pro 3 官方店",
                        "url": "https://search.jd.com/Search?keyword=AirPods%20Pro%203",
                        "price": "1999",
                        "shop": "Apple 京东自营旗舰店",
                    }
                ],
                ensure_ascii=False,
            ),
            stderr="",
        )

    monkeypatch.setattr(RUNNER.shutil, "which", lambda executable: f"C:/bin/{executable}.cmd")
    monkeypatch.setattr(RUNNER.subprocess, "run", fake_run)
    source = {
        "source_id": "jd_tmall_official_store",
        "platform": "JD/Tmall official store",
        "source_family": "commerce_marketplace",
    }

    receipts = RUNNER.run_platform_adapter_searches(
        [
            {
                "source_id": "jd_tmall_official_store",
                "platform_key": "jd_tmall",
                "adapter_query": "AirPods Pro 3",
            }
        ],
        source_by_id={"jd_tmall_official_store": source},
        provider="opencli",
        fixture={},
        command_config={},
        max_results=5,
        timeout=2,
    )

    assert captured["command"][0] == "C:/bin/opencli.cmd"
    assert captured["command"][1:4] == ["jd", "search", "AirPods Pro 3"]
    assert captured["command"][-2:] == ["-f", "json"]
    assert captured["kwargs"]["shell"] is False
    assert receipts[0]["provider"] == "opencli_platform_adapter"
    assert receipts[0]["adapter_kind"] == "platform_native_search"
    assert receipts[0]["status"] == "ok"
    assert receipts[0]["result_count"] == 1
    assert receipts[0]["results"][0]["url"] == "https://search.jd.com/Search?keyword=AirPods%20Pro%203"
    assert "Apple 京东自营旗舰店" in receipts[0]["results"][0]["snippet"]


def test_targeted_platform_receipt_does_not_bleed_into_other_candidate_sources():
    candidates = [
        {
            "source_id": "xiaohongshu_topic_search",
            "platform": "xiaohongshu",
            "source_family": "social_content",
            "hypothesis_role": "sentiment_source",
        },
        {
            "source_id": "baidu_google_news_search",
            "platform": "search/news",
            "source_family": "search_news",
            "hypothesis_role": "cross_check_source",
        },
    ]
    search_receipts = [
        {
            "query": "AI 陪伴机器人隐私争议",
            "provider": "opencli_platform_adapter",
            "adapter_kind": "platform_native_search",
            "target_source_id": "xiaohongshu_topic_search",
            "status": "ok",
            "results": [
                {
                    "title": "小红书 AI 陪伴机器人隐私争议用户讨论",
                    "url": "https://www.xiaohongshu.com/search_result/abc",
                    "snippet": "小红书用户讨论隐私争议和负面体验。",
                }
            ],
        }
    ]

    attached = RUNNER.attach_evidence_to_candidates(candidates, search_receipts, [])

    assert attached[0]["observed_urls"] == ["https://www.xiaohongshu.com/search_result/abc"]
    assert attached[1]["observed_urls"] == []
    assert attached[1]["evidence"] == []


def test_platform_supplemental_search_filters_results_to_target_platform_domain():
    source = {
        "source_id": "jd_tmall_official_store",
        "platform": "JD/Tmall official store",
        "source_family": "commerce_marketplace",
        "role": "primary_fact_source",
    }
    receipts = [
        {
            "query": 'site:jd.com "AirPods Pro 3" 京东 天猫',
            "provider": "fixture",
            "status": "ok",
            "result_count": 2,
            "results": [
                {
                    "title": "AirPods - Apple",
                    "url": "https://www.apple.com/airpods/",
                    "snippet": "Apple product page.",
                },
                {
                    "title": "京东 AirPods Pro 3 官方店",
                    "url": "https://search.jd.com/Search?keyword=AirPods%20Pro%203",
                    "snippet": "京东商品搜索结果。",
                },
            ],
        }
    ]

    filtered = RUNNER.filter_platform_supplemental_search_receipts(
        receipts,
        {'site:jd.com "AirPods Pro 3" 京东 天猫': source},
    )

    assert filtered[0]["result_count"] == 1
    assert filtered[0]["unfiltered_result_count"] == 2
    assert filtered[0]["target_source_id"] == "jd_tmall_official_store"
    assert filtered[0]["results"][0]["url"] == "https://search.jd.com/Search?keyword=AirPods%20Pro%203"


def test_runner_creates_research_packet_but_does_not_select_sources_without_agent_synthesis():
    packet = RUNNER.build_research_packet(
        "针对某款智能猫砂盆做价格和销售分析",
        region=None,
        provider="fixture",
        search_fixture=search_fixture(),
        browser_fixture=browser_fixture(),
        max_results=5,
        browser_limit=8,
        timeout=2,
        synthesis=None,
        source_decision_ref="packet.generated.json",
    )

    assert packet["schema_version"] == "w31_agent_research_packet.v1"
    assert packet["agent_review_required"] is True
    assert packet["analysis_input_ready"] is True
    assert packet["research_execution_chain"]["candidate_evidence_count"] >= 3
    assert packet["selected_primary_source_ids"] == []
    assert packet["cross_check_source_ids"] == []

    receipt = GENERATOR.generate_receipt(
        "针对某款智能猫砂盆做价格和销售分析",
        source_decision_ref="receipt.generated.json",
        agent_research=packet,
    )
    assert receipt["research_depth"]["status"] == "agent_research_incomplete"
    assert receipt["research_depth"]["minimum_depth_met"] is False
    assert "agent_synthesis_missing" in " ".join(receipt["research_gaps"])
    assert receipt["next_s31a_targets"] == []


def test_runner_with_agent_synthesis_compiles_formal_receipt():
    packet = RUNNER.build_research_packet(
        "针对某款智能猫砂盆做价格和销售分析",
        region=None,
        provider="fixture",
        search_fixture=search_fixture(),
        browser_fixture=browser_fixture(),
        max_results=5,
        browser_limit=8,
        timeout=2,
        synthesis=synthesis(),
        source_decision_ref="receipt.generated.json",
    )

    receipt = GENERATOR.generate_receipt(
        "针对某款智能猫砂盆做价格和销售分析",
        source_decision_ref="receipt.generated.json",
        agent_research=packet,
    )

    assert packet["agent_review_required"] is False
    assert receipt["analysis_mode"] == "agent_research_compiled"
    assert receipt["source_selection_owner"] == "agent_research"
    assert receipt["research_depth"]["status"] == "completed"
    assert receipt["research_depth"]["minimum_depth_met"] is True
    assert receipt["research_gaps"] == []
    assert [source["source_id"] for source in receipt["selected_primary_sources"]] == [
        "brand_official_store_cn",
        "jd_tmall_official_store",
    ]
    assert receipt["cross_check_sources"][0]["source_id"] == "xiaohongshu_product_posts"
    assert len(receipt["next_s31a_targets"]) == 3


def test_runner_builds_reviewable_synthesis_draft_without_collapsing_review_gate():
    packet = packet_without_synthesis()

    draft = RUNNER.build_synthesis_draft(packet)

    assert draft["schema_version"] == "w31_agent_synthesis_draft.v1"
    assert draft["review_status"] == "draft_needs_agent_review"
    assert draft["agent_review_required"] is True
    assert draft["business_goal"] == packet["business_goal"]
    assert draft["proposed_primary_source_ids"] == ["brand_official_store_cn", "jd_tmall_official_store"]
    assert draft["proposed_cross_check_source_ids"] == ["xiaohongshu_product_posts"]
    assert [item["source_id"] for item in draft["candidate_summary"]] == [
        "brand_official_store_cn",
        "jd_tmall_official_store",
        "xiaohongshu_product_posts",
        "xianyu_resale_listing",
    ]
    assert draft["candidate_summary"][0]["draft_decision"] == "primary"
    assert draft["proposed_excluded_sources"][0]["source_family"] == "secondhand_marketplace"
    assert "业务事实权威性" in draft["review_checklist"][1]
    assert draft["final_synthesis_template"]["schema_version"] == "w31_agent_synthesis.v1"
    assert draft["final_synthesis_template"]["selected_primary_source_ids"] == []
    assert packet["agent_review_required"] is True


def test_synthesis_draft_includes_opencli_adapter_status_in_score_review_hints():
    packet = packet_without_synthesis()
    packet["research_execution_chain"]["search_receipts"].append(
        {
            "query": "某款智能猫砂盆",
            "provider": "opencli_platform_adapter",
            "adapter_kind": "platform_native_search",
            "target_source_id": "jd_tmall_official_store",
            "platform_key": "jd_tmall",
            "status": "ok",
            "result_count": 3,
            "adapter_command": "opencli jd search 某款智能猫砂盆 --limit 5 -f json",
            "results": [
                {
                    "title": "京东智能猫砂盆官方店",
                    "url": "https://item.jd.com/123.html",
                    "snippet": "SKU price review count",
                }
            ],
        }
    )
    packet["research_execution_chain"]["search_receipts"].append(
        {
            "query": "某款智能猫砂盆",
            "provider": "opencli_platform_adapter",
            "adapter_kind": "platform_native_search",
            "target_source_id": "xianyu_resale_listing",
            "platform_key": "xianyu",
            "status": "failed",
            "result_count": 0,
            "adapter_command": "opencli xianyu search 某款智能猫砂盆 --limit 5 -f json",
            "error": "adapter_timeout",
            "results": [],
        }
    )

    draft = RUNNER.build_synthesis_draft(packet)
    summary_by_id = {item["source_id"]: item for item in draft["candidate_summary"]}

    jd_summary = summary_by_id["jd_tmall_official_store"]
    assert jd_summary["platform_adapter_status"]["status"] == "ok"
    assert jd_summary["platform_adapter_status"]["result_count"] == 3
    assert jd_summary["platform_adapter_status"]["provider"] == "opencli_platform_adapter"
    assert "可复现性" in " ".join(jd_summary["score_review_hints"])
    assert "抓取摩擦" in " ".join(jd_summary["score_review_hints"])

    xianyu_summary = summary_by_id["xianyu_resale_listing"]
    assert xianyu_summary["platform_adapter_status"]["status"] == "failed"
    assert xianyu_summary["platform_adapter_status"]["error"] == "adapter_timeout"
    assert "不能把低权威源抬成主事实源" in " ".join(xianyu_summary["score_review_hints"])
    assert any("OpenCLI/platform adapter" in item for item in draft["review_checklist"])


def test_runner_rejects_synthesis_draft_and_unfilled_template_as_final_synthesis():
    packet = packet_without_synthesis()
    draft = RUNNER.build_synthesis_draft(packet)

    with pytest.raises(ValueError, match="draft"):
        RUNNER.merge_synthesis(packet, draft)
    with pytest.raises(ValueError, match="selected_primary_source_ids"):
        RUNNER.merge_synthesis(packet, draft["final_synthesis_template"])


def test_runner_cli_writes_packet_and_receipt_from_fixture_chain(tmp_path):
    search_path = tmp_path / "search_fixture.json"
    browser_path = tmp_path / "browser_fixture.json"
    synthesis_path = tmp_path / "synthesis.json"
    packet_path = tmp_path / "agent_research_packet.json"
    draft_path = tmp_path / "w31_agent_synthesis_draft.v1.json"
    receipt_path = tmp_path / "data_source_decision_receipt.v1.json"
    write_fixture(search_path, search_fixture())
    write_fixture(browser_path, browser_fixture())
    write_fixture(synthesis_path, synthesis())

    result = subprocess.run(
        [
            sys.executable,
            str(RUNNER_PATH),
            "针对某款智能猫砂盆做价格和销售分析",
            "--provider",
            "fixture",
            "--search-fixture-json",
            str(search_path),
            "--browser-fixture-json",
            str(browser_path),
            "--synthesis-json",
            str(synthesis_path),
            "--output-packet",
            str(packet_path),
            "--output-synthesis-draft",
            str(draft_path),
            "--output-receipt",
            str(receipt_path),
            "--pretty",
        ],
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=30,
    )

    assert result.returncode == 0, result.stderr
    packet = json.loads(packet_path.read_text(encoding="utf-8"))
    draft = json.loads(draft_path.read_text(encoding="utf-8"))
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert packet["research_execution_chain"]["search_provider"] == "fixture"
    assert draft["schema_version"] == "w31_agent_synthesis_draft.v1"
    assert draft["final_synthesis_template"]["selected_primary_source_ids"] == []
    assert draft["agent_review_required"] is True
    assert draft["region_scope"] == "cn"
    assert receipt["research_depth"]["minimum_depth_met"] is True
    assert all(target["source_decision_ref"] == receipt_path.name for target in receipt["next_s31a_targets"])
