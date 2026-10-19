import importlib.util
import json
import subprocess
import sys
from pathlib import Path


S31_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = (
    S31_ROOT
    / "subskills"
    / "S31C_内容平台事实采集"
    / "scripts"
    / "platform_m5_readiness.py"
)


def load_module():
    spec = importlib.util.spec_from_file_location("platform_m5_readiness", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def scheduler_config():
    return {
        "schema_version": "competitor-crawl-scheduler.v1",
        "profiles": {
            "conservative": {
                "daily": {"queryOffsetCycle": 24},
                "risk": {"duplicateDedupeCooldownMinutes": 120},
                "lanes": {
                    "browser": {
                        "sources": [
                            "amazon",
                            "appstore",
                            "bilibili",
                            "douyin_ecommerce",
                            "public_article",
                            "reddit",
                            "rentio",
                            "taobao_tmall",
                            "tieba",
                            "trustpilot",
                            "yahoo_chiebukuro",
                            "jd",
                        ]
                    }
                },
                "sourcePriority": [
                    "amazon",
                    "appstore",
                    "bilibili",
                    "douyin_ecommerce",
                    "public_article",
                    "reddit",
                    "rentio",
                    "taobao_tmall",
                    "tieba",
                    "trustpilot",
                    "yahoo_chiebukuro",
                    "jd",
                ],
            }
        },
    }


def build_matrix(cron_jobs=None, scheduler=None):
    module = load_module()
    closure_meta, closure_index = module.load_optional_json(module.DEFAULT_CLOSURE_INDEX_PATH)
    maturity_meta, maturity_matrix = module.load_optional_json(module.DEFAULT_MATURITY_MATRIX_PATH)
    health_meta, health_matrix = module.load_optional_json(module.DEFAULT_HEALTH_MATRIX_PATH)
    return module.build_readiness_matrix(
        baseline=module.load_yaml(module.BASELINE_PATH),
        registry=module.load_yaml(module.REGISTRY_PATH),
        cron_meta={"path": "test-cron", "exists": True, "job_count": len(cron_jobs or [])},
        cron_jobs=cron_jobs or [],
        scheduler_meta={"path": "test-scheduler", "exists": True},
        scheduler_config=scheduler or {},
        closure_meta=closure_meta,
        closure_index=closure_index,
        maturity_meta=maturity_meta,
        maturity_matrix=maturity_matrix,
        health_meta=health_meta,
        health_matrix=health_matrix,
    )


def test_search_engines_are_discovery_closed_without_m5_requirement():
    matrix = build_matrix()

    assert matrix["ok"], matrix["errors"]
    assert set(matrix["summary"]["discovery_exempt_platforms"]) == {"baidu", "bing", "google"}
    assert {"baidu", "bing", "google"}.isdisjoint(matrix["summary"]["m5_required_platforms"])
    assert {"baidu", "bing", "google"}.isdisjoint(matrix["summary"]["m5_gap_platforms"])
    for platform in ("baidu", "bing", "google"):
        row = matrix["platforms"][platform]
        assert row["source_family"] == "search_news"
        assert row["m5_required"] is False
        assert row["closure_target"] == "discovery_closure"
        assert row["readiness_status"] == "DISCOVERY_CLOSED"
        assert row["missing_m5_gates"] == []


def test_fact_platform_m5_gap_is_frontloaded_before_runtime():
    matrix = build_matrix()
    row = matrix["platforms"]["jd"]

    assert row["m5_required"] is True
    assert row["current_maturity_tier"] == "M5"
    assert row["readiness_status"] == "M5_GAPS"
    assert "cron_schedule_missing" in row["missing_m5_gates"]
    assert "dedupe_gate_missing" in row["missing_m5_gates"]
    assert row["has_repeatable_fact_routes"] is True
    assert row["has_freshness_sla"] is True
    assert row["has_quality_gates"] is True
    assert row["upgrade_bucket"] == "seal_run_stability"
    assert row["next_actions"] == [
        "register_openclaw_cron_schedule",
        "register_platform_dedupe_gate",
    ]


def test_skipped_platform_is_not_counted_as_current_m5_required_source():
    matrix = build_matrix()
    row = matrix["platforms"]["weibo"]

    assert row["current_maturity_tier"] == "M0"
    assert row["m5_required"] is False
    assert row["readiness_status"] == "NOT_ONBOARDED"
    assert row["missing_m5_gates"] == []


def test_schedule_and_dedupe_evidence_can_satisfy_frontloaded_gates():
    cron_jobs = [
        {
            "name": "S31 crawler jd",
            "enabled": True,
            "schedule": {"expr": "0 */6 * * *"},
            "payload": {"message": "opencli jd reviews with dedupe and duplicate guard"},
        }
    ]
    matrix = build_matrix(cron_jobs)
    row = matrix["platforms"]["jd"]

    assert row["has_schedule_registration"] is True
    assert row["has_dedupe_gate"] is True
    assert "cron_schedule_missing" not in row["missing_m5_gates"]
    assert "dedupe_gate_missing" not in row["missing_m5_gates"]
    assert "maturity_not_m5" not in row["missing_m5_gates"]
    assert row["missing_m5_gates"] == []
    assert row["readiness_status"] == "M5_READY"


def test_m5_ready_requires_frontloaded_closure_or_maturity_evidence():
    module = load_module()
    cron_jobs = [
        {
            "name": "竞品每日增量采集-保守发射",
            "enabled": True,
            "schedule": {"expr": "7 6 * * 1-6"},
            "payload": {"message": "scripts\\competitor-crawl-scheduler.mjs --mode launch --profile conservative --commit"},
        },
        {
            "name": "竞品每日增量采集-20分钟收割",
            "enabled": True,
            "schedule": {"expr": "*/20 6-23 * * 1-6"},
            "payload": {
                "message": (
                    "scripts\\competitor-crawl-scheduler.mjs --mode harvest; "
                    "scripts\\competitor-crawl-scheduler.mjs --mode status --receipt out.json --strict"
                )
            },
        },
    ]

    matrix = module.build_readiness_matrix(
        baseline=module.load_yaml(module.BASELINE_PATH),
        registry=module.load_yaml(module.REGISTRY_PATH),
        cron_meta={"path": "test-cron", "exists": True, "job_count": len(cron_jobs)},
        cron_jobs=cron_jobs,
        scheduler_meta={"path": "test-scheduler", "exists": True},
        scheduler_config=scheduler_config(),
        closure_index={},
        maturity_matrix={},
    )
    row = matrix["platforms"]["amazon"]

    assert row["current_maturity_tier"] == "M5"
    assert row["readiness_status"] == "M5_GAPS"
    assert "m5_evidence_missing" in row["missing_m5_gates"]


def test_sop_and_route_registry_consistency_are_frontloaded():
    module = load_module()
    baseline = module.load_yaml(module.BASELINE_PATH)
    amazon = {
        **baseline["platforms"]["amazon"],
        "sop_ref": "subskills/S31C_内容平台事实采集/references/platform_sops/missing_amazon_crawl_sop.md",
    }
    baseline = {
        "closure_policy": baseline["closure_policy"],
        "platforms": {"amazon": amazon},
    }

    matrix = module.build_readiness_matrix(
        baseline=baseline,
        registry={"platform_metric_routes": {}},
        cron_meta={"path": "test-cron", "exists": True, "job_count": 0},
        cron_jobs=[],
        scheduler_meta={"path": "test-scheduler", "exists": True},
        scheduler_config={},
        closure_index={},
        maturity_matrix={},
    )
    row = matrix["platforms"]["amazon"]

    assert row["readiness_status"] == "M5_GAPS"
    assert "sop_file_missing" in row["missing_m5_gates"]
    assert "route_registry_platform_missing" in row["missing_m5_gates"]
    assert matrix["summary"]["gap_groups"]["sop_or_route_registry_drift"] == ["amazon"]
    assert "align_platform_sop_with_baseline" in row["next_actions"]
    assert "register_platform_route_registry" in row["next_actions"]


def test_closed_closure_with_degraded_maturity_is_frontloaded_as_conflict():
    module = load_module()
    cron_jobs = [
        {
            "name": "竞品每日增量采集-保守发射",
            "enabled": True,
            "schedule": {"expr": "7 6 * * 1-6"},
            "payload": {"message": "scripts\\competitor-crawl-scheduler.mjs --mode launch --profile conservative --commit"},
        },
        {
            "name": "竞品每日增量采集-20分钟收割",
            "enabled": True,
            "schedule": {"expr": "*/20 6-23 * * 1-6"},
            "payload": {
                "message": (
                    "scripts\\competitor-crawl-scheduler.mjs --mode harvest; "
                    "scripts\\competitor-crawl-scheduler.mjs --mode status --receipt out.json --strict"
                )
            },
        },
    ]
    baseline = {
        "closure_policy": module.load_yaml(module.BASELINE_PATH)["closure_policy"],
        "platforms": {
            "douyin": {
                **module.load_yaml(module.BASELINE_PATH)["platforms"]["douyin"],
                "maturity_tier": "M5",
            }
        },
    }
    closure_index = {
        "platforms": [
            {
                "platform": "douyin",
                "closure_status": "closed",
                "closure_receipt": {"path": "douyin-closure.json"},
                "acceptance": {"key_dimension_gaps": []},
            }
        ]
    }
    maturity_matrix = {
        "matrix": [
            {
                "columns": {
                    "M2": [
                        {
                            "source": "douyin",
                            "maturity_tier": "M2",
                            "quality_attribution_status": "REFERENCE_FACTS_SEALED_NOT_NEGATIVE",
                            "stability_status": "DEGRADED_OR_RECOVERY",
                            "can_schedule_live_now": False,
                            "hardening_gap_status": "NONE",
                        }
                    ]
                }
            }
        ]
    }
    health_matrix = {
        "platforms": [
            {
                "source": "douyin",
                "status": "auth_or_risk_pause",
                "safe_to_schedule_now": False,
                "anti_risk_manual_clearance_required": True,
                "anti_risk_repeatable_ready": False,
                "anti_risk_posture": "MANUAL_CLEARANCE_REQUIRED",
            }
        ]
    }

    matrix = module.build_readiness_matrix(
        baseline=baseline,
        registry=module.load_yaml(module.REGISTRY_PATH),
        cron_meta={"path": "test-cron", "exists": True, "job_count": len(cron_jobs)},
        cron_jobs=cron_jobs,
        scheduler_meta={"path": "test-scheduler", "exists": True},
        scheduler_config=scheduler_config(),
        closure_index=closure_index,
        maturity_matrix=maturity_matrix,
        health_matrix=health_matrix,
    )
    row = matrix["platforms"]["douyin"]

    assert row["has_m5_evidence"] is False
    assert row["readiness_status"] == "M5_GAPS"
    assert "maturity_evidence_conflict" in row["missing_m5_gates"]
    assert "maturity_baseline_matrix_tier_mismatch" in row["missing_m5_gates"]
    assert "maturity_quality_not_sealed" in row["missing_m5_gates"]
    assert "maturity_stability_not_sealed" in row["missing_m5_gates"]
    assert "maturity_not_schedulable" in row["missing_m5_gates"]
    assert "runtime_manual_clearance_required" in row["missing_m5_gates"]
    assert "runtime_not_safe_to_schedule" in row["missing_m5_gates"]
    assert matrix["summary"]["gap_groups"]["maturity_evidence_conflict"] == ["douyin"]
    assert matrix["summary"]["gap_groups"]["not_schedulable"] == ["douyin"]
    assert matrix["summary"]["gap_groups"]["runtime_manual_clearance_required"] == ["douyin"]
    assert matrix["summary"]["gap_groups"]["runtime_not_safe_to_schedule"] == ["douyin"]
    assert matrix["summary"]["gap_groups"]["maturity_baseline_matrix_tier_mismatch"] == ["douyin"]
    assert "reconcile_baseline_with_maturity_matrix" in row["next_actions"]
    assert "clear_manual_runtime_clearance_before_launch" in row["next_actions"]
    assert "resolve_runtime_health_before_scheduling" in row["next_actions"]
    assert "seal_quality_fact_attribution" in row["next_actions"]
    assert "prove_stable_recent_live_run" in row["next_actions"]
    assert "clear_platform_runtime_risk_or_auth_pause" in row["next_actions"]


def test_unclosed_closure_receipt_dimension_gaps_are_frontloaded():
    module = load_module()
    cron_jobs = [
        {
            "name": "竞品每日增量采集-保守发射",
            "enabled": True,
            "schedule": {"expr": "7 6 * * 1-6"},
            "payload": {"message": "scripts\\competitor-crawl-scheduler.mjs --mode launch --profile conservative --commit"},
        },
        {
            "name": "竞品每日增量采集-20分钟收割",
            "enabled": True,
            "schedule": {"expr": "*/20 6-23 * * 1-6"},
            "payload": {
                "message": (
                    "scripts\\competitor-crawl-scheduler.mjs --mode harvest; "
                    "scripts\\competitor-crawl-scheduler.mjs --mode status --receipt out.json --strict"
                )
            },
        },
    ]
    closure_index = {
        "platforms": [
            {
                "platform": "pinduoduo",
                "closure_status": "accounted_gap_not_closed",
                "closure_receipt": {"path": "pinduoduo-closure.json"},
                "acceptance": {
                    "key_dimension_gaps": [
                        {
                            "dimension": "live_search_acceptance",
                            "status": "blocked",
                            "reason": "system_busy",
                        }
                    ]
                },
            }
        ]
    }
    maturity_matrix = {
        "matrix": [
            {
                "columns": {
                    "M4": [
                        {
                            "source": "pinduoduo",
                            "maturity_tier": "M4",
                            "quality_attribution_status": "M4_PLATFORM_PROOF_TRACEABLE",
                            "stability_status": "STABLE_M4_PLATFORM_PROOF",
                            "can_schedule_live_now": True,
                            "hardening_gap_status": "NOTE",
                        }
                    ]
                }
            }
        ]
    }

    matrix = module.build_readiness_matrix(
        baseline=module.load_yaml(module.BASELINE_PATH),
        registry=module.load_yaml(module.REGISTRY_PATH),
        cron_meta={"path": "test-cron", "exists": True, "job_count": len(cron_jobs)},
        cron_jobs=cron_jobs,
        scheduler_meta={"path": "test-scheduler", "exists": True},
        scheduler_config=scheduler_config(),
        closure_index=closure_index,
        maturity_matrix=maturity_matrix,
    )
    row = matrix["platforms"]["pinduoduo"]

    assert row["readiness_status"] == "M5_GAPS"
    assert "closure_receipt_not_closed" in row["missing_m5_gates"]
    assert "closure_dimension_gaps_present" in row["missing_m5_gates"]
    assert "maturity_hardening_gap_present" in row["missing_m5_gates"]
    assert matrix["summary"]["gap_groups"]["closure_receipt_not_closed"] == ["pinduoduo"]
    assert matrix["summary"]["gap_groups"]["hardening_gap_present"] == ["pinduoduo"]
    assert "close_platform_data_plane_receipt_gaps" in row["next_actions"]


def test_central_scheduler_launch_and_strict_harvest_satisfy_run_stability_gates():
    cron_jobs = [
        {
            "name": "竞品每日增量采集-保守发射",
            "enabled": True,
            "schedule": {"expr": "7 6 * * 1-6"},
            "payload": {"message": "scripts\\competitor-crawl-scheduler.mjs --mode launch --profile conservative --commit"},
        },
        {
            "name": "竞品每日增量采集-20分钟收割",
            "enabled": True,
            "schedule": {"expr": "*/20 6-23 * * 1-6"},
            "payload": {
                "message": (
                    "scripts\\competitor-crawl-scheduler.mjs --mode harvest; "
                    "scripts\\competitor-crawl-scheduler.mjs --mode status --receipt out.json --strict"
                )
            },
        },
    ]
    matrix = build_matrix(cron_jobs, scheduler_config())
    row = matrix["platforms"]["douyin_ecommerce"]

    assert row["has_schedule_registration"] is True
    assert row["schedule_source"] == "central_scheduler"
    assert row["has_dedupe_gate"] is True
    assert row["missing_m5_gates"] == []
    assert row["readiness_status"] == "M5_READY"


def test_real_scheduler_registers_dianping_without_promoting_to_m5():
    module = load_module()
    cron_meta, cron_jobs = module.load_cron_jobs(module.DEFAULT_CRON_PATH)
    scheduler_meta, scheduler_config_data = module.load_scheduler_config(module.DEFAULT_SCHEDULER_CONFIG_PATH)
    closure_meta, closure_index = module.load_optional_json(module.DEFAULT_CLOSURE_INDEX_PATH)
    maturity_meta, maturity_matrix = module.load_optional_json(module.DEFAULT_MATURITY_MATRIX_PATH)
    health_meta, health_matrix = module.load_optional_json(module.DEFAULT_HEALTH_MATRIX_PATH)
    matrix = module.build_readiness_matrix(
        baseline=module.load_yaml(module.BASELINE_PATH),
        registry=module.load_yaml(module.REGISTRY_PATH),
        cron_meta=cron_meta,
        cron_jobs=cron_jobs,
        scheduler_meta=scheduler_meta,
        scheduler_config=scheduler_config_data,
        closure_meta=closure_meta,
        closure_index=closure_index,
        maturity_meta=maturity_meta,
        maturity_matrix=maturity_matrix,
        health_meta=health_meta,
        health_matrix=health_matrix,
    )
    row = matrix["platforms"]["dianping"]

    assert row["has_schedule_registration"] is True
    assert row["has_dedupe_gate"] is True
    assert "cron_schedule_missing" not in row["missing_m5_gates"]
    assert "dedupe_gate_missing" not in row["missing_m5_gates"]
    assert "maturity_matrix_row_missing" not in row["missing_m5_gates"]
    assert "runtime_health_missing" not in row["missing_m5_gates"]
    assert row["readiness_status"] == "M5_GAPS"
    assert "closure_receipt_missing" not in row["missing_m5_gates"]
    assert "closure_receipt_not_closed" in row["missing_m5_gates"]
    assert "closure_dimension_gaps_present" in row["missing_m5_gates"]
    assert row["m5_evidence"]["closure"]["receipt_path"] == (
        "data/crawler-agent-handoffs/20260619-platforms/27-dianping-closure-receipt.json"
    )
    assert row["m5_evidence"]["closure"]["closure_status"] == "accounted_gap_not_closed"
    assert row["m5_evidence"]["maturity"]["explicit"] is True
    assert row["m5_evidence"]["maturity"]["maturity_tier"] == "M2"
    assert row["runtime_health"]["explicit"] is True
    assert row["runtime_health"]["status"] == "auth_or_risk_pause"
    assert "runtime_manual_clearance_required" in row["missing_m5_gates"]
    assert "runtime_not_safe_to_schedule" in row["missing_m5_gates"]


def test_cli_can_write_readiness_matrix_for_agent_handoff(tmp_path):
    output = tmp_path / "platform-m5-readiness.json"

    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--output", str(output)],
        check=True,
        cwd=SCRIPT.parent,
        text=True,
        capture_output=True,
    )
    stdout_payload = json.loads(result.stdout)
    file_payload = json.loads(output.read_text(encoding="utf-8"))

    assert output.exists()
    assert stdout_payload["schema_version"] == "s31_platform_m5_readiness.v1"
    assert file_payload["summary"]["platform_count"] == 21
    assert file_payload["summary"] == stdout_payload["summary"]


def test_central_scheduler_without_strict_harvest_does_not_satisfy_schedule_gate():
    cron_jobs = [
        {
            "name": "竞品每日增量采集-保守发射",
            "enabled": True,
            "schedule": {"expr": "7 6 * * 1-6"},
            "payload": {"message": "scripts\\competitor-crawl-scheduler.mjs --mode launch --profile conservative --commit"},
        }
    ]
    matrix = build_matrix(cron_jobs, scheduler_config())
    row = matrix["platforms"]["douyin_ecommerce"]

    assert row["has_schedule_registration"] is False
    assert row["schedule_source"] == "missing"
    assert "cron_schedule_missing" in row["missing_m5_gates"]
    assert row["has_dedupe_gate"] is True


def test_upgrade_queue_prioritizes_nearest_m5_fact_source_and_skips_discovery_sources():
    cron_jobs = [
        {
            "name": "竞品每日增量采集-保守发射",
            "enabled": True,
            "schedule": {"expr": "7 6 * * 1-6"},
            "payload": {"message": "scripts\\competitor-crawl-scheduler.mjs --mode launch --profile conservative --commit"},
        },
        {
            "name": "竞品每日增量采集-20分钟收割",
            "enabled": True,
            "schedule": {"expr": "*/20 6-23 * * 1-6"},
            "payload": {
                "message": (
                    "scripts\\competitor-crawl-scheduler.mjs --mode harvest; "
                    "scripts\\competitor-crawl-scheduler.mjs --mode status --receipt out.json --strict"
                )
            },
        },
    ]
    matrix = build_matrix(cron_jobs, scheduler_config())
    queue = matrix["upgrade_queue"]

    assert matrix["platforms"]["appstore"]["readiness_status"] == "M5_READY"
    assert matrix["platforms"]["amazon"]["readiness_status"] == "M5_READY"
    assert matrix["platforms"]["jd"]["readiness_status"] == "M5_READY"
    assert matrix["platforms"]["taobao_tmall"]["readiness_status"] == "M5_READY"
    assert "appstore" not in {item["platform"] for item in queue}
    assert "amazon" not in {item["platform"] for item in queue}
    assert "jd" not in {item["platform"] for item in queue}
    assert "taobao_tmall" not in {item["platform"] for item in queue}
    assert queue[0]["platform"] == "pinduoduo"
    assert queue[0]["upgrade_bucket"] == "maturity_then_run_stability"
    assert queue[0]["current_maturity_tier"] == "M4"
    assert "baidu" not in {item["platform"] for item in queue}
    assert "bing" not in {item["platform"] for item in queue}
    assert "google" not in {item["platform"] for item in queue}
    assert matrix["summary"]["highest_priority_gap"]["platform"] == "pinduoduo"


def test_cli_generation_returns_zero_in_report_mode():
    module = load_module()

    assert module.main([]) == 0
