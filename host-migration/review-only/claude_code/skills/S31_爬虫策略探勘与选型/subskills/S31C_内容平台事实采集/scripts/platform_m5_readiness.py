#!/usr/bin/env python3
"""Generate the S31 platform M5 readiness and gap matrix."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import yaml


SCHEMA_VERSION = "s31_platform_m5_readiness.v1"
S31_ROOT = Path(__file__).resolve().parents[3]
BASELINE_PATH = (
    S31_ROOT
    / "subskills"
    / "S31A_数据源探针与路线选型"
    / "references"
    / "platform_crawl_maturity_baseline.yaml"
)
REGISTRY_PATH = S31_ROOT / "references" / "business_metric_route_registry.yaml"
DEFAULT_CRON_PATH = Path(r"@@USERPROFILE:win@@\.openclaw\cron\jobs.json")
DEFAULT_SCHEDULER_CONFIG_PATH = Path(
    r"@@OPENCLAW_ROOT:win@@\projects\tophub-daily-trend-radar\apps\web\data\config\competitor-crawl-scheduler.yaml"
)
DEFAULT_CLOSURE_INDEX_PATH = Path(
    r"@@OPENCLAW_ROOT:win@@\projects\tophub-daily-trend-radar\apps\web\data\crawler-agent-handoffs\20260619-platforms\00-platform-closure-index.json"
)
DEFAULT_MATURITY_MATRIX_PATH = Path(
    r"@@OPENCLAW_ROOT:win@@\projects\tophub-daily-trend-radar\docs\w11-p3-evidence\s31-platform-fact-maturity-matrix-current.json"
)
DEFAULT_HEALTH_MATRIX_PATH = Path(
    r"@@OPENCLAW_ROOT:win@@\projects\tophub-daily-trend-radar\docs\w11-p3-evidence\s31-platform-health-matrix-current.json"
)
DISCOVERY_ROUTE_LEVELS = {"L0_discovery"}
UNAVAILABLE_ROUTE_LEVELS = {"L0_unavailable", "L0_skipped"}
NON_FACT_ROUTE_LEVELS = DISCOVERY_ROUTE_LEVELS | UNAVAILABLE_ROUTE_LEVELS
SOP_REQUIRED_TOKENS = ("crawler_fact_pack.v1", "zero_output_diagnosis")
FOUNDATION_GATES = {
    "metric_routes_missing",
    "fact_import_routes_missing",
    "repeatable_seed_or_source_field_missing",
    "freshness_sla_missing",
    "quality_gates_missing",
    "fact_pack_paths_missing",
    "sop_ref_missing",
    "sop_file_missing",
    "sop_maturity_mismatch",
    "sop_strategy_mismatch",
    "sop_adapter_capability_mismatch",
    "sop_required_contract_missing",
    "route_registry_platform_missing",
}
RUN_STABILITY_GATES = {
    "cron_schedule_missing",
    "dedupe_gate_missing",
    "maturity_not_schedulable",
    "runtime_health_missing",
    "runtime_manual_clearance_required",
    "runtime_not_safe_to_schedule",
}
MATURITY_GATES = {
    "maturity_not_m5",
    "maturity_evidence_conflict",
    "maturity_matrix_row_missing",
    "maturity_baseline_matrix_tier_mismatch",
    "maturity_quality_not_sealed",
    "maturity_stability_not_sealed",
    "maturity_hardening_gap_present",
}
CLOSURE_GATES = {
    "closure_receipt_missing",
    "closure_receipt_not_closed",
    "closure_dimension_gaps_present",
}
EVIDENCE_GATES = {"m5_evidence_missing"} | CLOSURE_GATES
DISCOVERY_GATES = {
    "discovery_m5_exemption_missing",
    "discovery_closure_target_missing",
    "direct_fact_route_registered_for_discovery_source",
    "discovery_route_missing",
}
ONBOARDING_GATES = {"skipped_source_has_fact_routes", "unavailable_route_missing"}


def load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a YAML object")
    return data


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_cron_jobs(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if not path.exists():
        return {"path": str(path), "exists": False, "job_count": 0}, []
    data = load_json(path)
    if isinstance(data, dict):
        jobs = data.get("jobs") or []
    elif isinstance(data, list):
        jobs = data
    else:
        jobs = []
    typed_jobs = [job for job in jobs if isinstance(job, dict)]
    return {"path": str(path), "exists": True, "job_count": len(typed_jobs)}, typed_jobs


def load_scheduler_config(path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    if not path.exists():
        return {"path": str(path), "exists": False}, {}
    data = load_yaml(path)
    if data.get("schema_version") != "competitor-crawl-scheduler.v1":
        return {"path": str(path), "exists": True, "schema_version": data.get("schema_version")}, {}
    return {"path": str(path), "exists": True, "schema_version": data.get("schema_version")}, data


def load_optional_json(path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    if not path.exists():
        return {"path": str(path), "exists": False}, {}
    data = load_json(path)
    if not isinstance(data, dict):
        return {"path": str(path), "exists": True, "schema_version": None}, {}
    return {"path": str(path), "exists": True, "schema_version": data.get("schema_version")}, data


def discovery_families(baseline: dict[str, Any]) -> set[str]:
    policy = baseline.get("closure_policy") or {}
    return {str(item) for item in policy.get("discovery_source_families") or []}


def is_discovery_source(row: dict[str, Any], baseline: dict[str, Any]) -> bool:
    return row.get("source_family") in discovery_families(baseline) or row.get("closure_target") == "discovery_closure"


def platform_aliases(platform: str) -> set[str]:
    aliases = {
        platform,
        platform.replace("_", "-"),
    }
    if platform == "xiaohongshu":
        aliases.add("xhs")
    if platform == "yahoo_chiebukuro":
        aliases.add("yahoo-chiebukuro")
    if platform == "public_article":
        aliases.add("public-article")
    if platform == "douyin_ecommerce":
        aliases.add("douyin-ecommerce")
    if platform == "taobao_tmall":
        aliases.add("taobao-tmall")
    return {alias.lower() for alias in aliases}


def closure_rows_by_platform(closure_index: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for item in closure_index.get("platforms") or []:
        if not isinstance(item, dict):
            continue
        for key in (item.get("platform"), item.get("slug")):
            if key:
                rows[str(key).lower()] = item
    return rows


def maturity_rows_by_platform(maturity_matrix: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for item in maturity_matrix.get("sources") or []:
        if not isinstance(item, dict):
            continue
        source = item.get("source") or item.get("platform")
        if source:
            rows[str(source).lower()] = item
    for family in maturity_matrix.get("matrix") or []:
        if not isinstance(family, dict):
            continue
        columns = family.get("columns") or {}
        if not isinstance(columns, dict):
            continue
        for items in columns.values():
            for item in items or []:
                if not isinstance(item, dict):
                    continue
                source = item.get("source") or item.get("platform")
                if source:
                    rows[str(source).lower()] = item
    return rows


def health_rows_by_platform(health_matrix: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for item in health_matrix.get("platforms") or health_matrix.get("sources") or []:
        if not isinstance(item, dict):
            continue
        source = item.get("source") or item.get("platform") or item.get("source_id")
        if source:
            rows[str(source).lower()] = item
    return rows


def closure_evidence(platform: str, closure_index: dict[str, Any]) -> dict[str, Any]:
    rows = closure_rows_by_platform(closure_index)
    row = next((rows[alias] for alias in platform_aliases(platform) if alias in rows), {})
    acceptance = row.get("acceptance") or {}
    gaps = acceptance.get("key_dimension_gaps")
    closed = row.get("closure_status") == "closed" and (gaps == [] or gaps is None)
    return {
        "status": "closed" if closed else "missing",
        "closed": closed,
        "closure_status": row.get("closure_status"),
        "receipt_path": (row.get("closure_receipt") or {}).get("path"),
        "key_dimension_gaps": gaps,
    }


def health_evidence(platform: str, health_matrix: dict[str, Any]) -> dict[str, Any]:
    rows = health_rows_by_platform(health_matrix)
    row = next((rows[alias] for alias in platform_aliases(platform) if alias in rows), {})
    explicit = bool(row)
    manual_clearance = row.get("anti_risk_manual_clearance_required") is True
    safe_to_schedule = row.get("safe_to_schedule_now")
    active_cooldown = (row.get("active_cooldown") or {}).get("active") is True
    return {
        "status": row.get("status"),
        "explicit": explicit,
        "safe_to_schedule_now": safe_to_schedule,
        "anti_risk_posture": row.get("anti_risk_posture"),
        "anti_risk_manual_clearance_required": manual_clearance,
        "anti_risk_repeatable_ready": row.get("anti_risk_repeatable_ready"),
        "active_cooldown": active_cooldown,
        "last_clean_live_at": row.get("anti_risk_last_clean_live_at"),
        "last_data_success_path": (row.get("last_data_success") or {}).get("adapter_receipt_path"),
    }


def maturity_evidence(platform: str, maturity_matrix: dict[str, Any]) -> dict[str, Any]:
    rows = maturity_rows_by_platform(maturity_matrix)
    row = next((rows[alias] for alias in platform_aliases(platform) if alias in rows), {})
    explicit = bool(row)
    sealed = (
        row.get("maturity_tier") == "M5"
        and row.get("quality_attribution_status") == "QUALITY_FACTS_SEALED"
        and row.get("stability_status") == "STABLE_RECENT_LIVE"
        and row.get("can_schedule_live_now") is True
        and row.get("hardening_gap_status") in {None, "", "NONE"}
    )
    return {
        "status": "sealed" if sealed else "missing",
        "explicit": explicit,
        "sealed": sealed,
        "maturity_tier": row.get("maturity_tier"),
        "quality_attribution_status": row.get("quality_attribution_status"),
        "stability_status": row.get("stability_status"),
        "can_schedule_live_now": row.get("can_schedule_live_now"),
        "hardening_gap_status": row.get("hardening_gap_status"),
        "health_status": row.get("health_status"),
    }


def has_m5_evidence(platform: str, closure_index: dict[str, Any], maturity_matrix: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    closure = closure_evidence(platform, closure_index)
    maturity = maturity_evidence(platform, maturity_matrix)
    conflict = bool(closure["closed"] and maturity["explicit"] and not maturity["sealed"])
    return (closure["closed"] or maturity["sealed"]) and not conflict, {
        "closure": closure,
        "maturity": maturity,
        "conflict": conflict,
    }


def platform_routes(registry: dict[str, Any], platform: str) -> dict[str, Any]:
    route_root = registry.get("platform_metric_routes") or {}
    platform_entry = route_root.get(platform) or {}
    metrics = platform_entry.get("metrics") or {}
    return metrics if isinstance(metrics, dict) else {}


def sop_evidence(platform: str, row: dict[str, Any]) -> dict[str, Any]:
    sop_ref = row.get("sop_ref")
    if not sop_ref:
        return {"ref": None, "path": None, "exists": False, "missing": ["sop_ref_missing"]}
    path = S31_ROOT / str(sop_ref)
    missing: list[str] = []
    if Path(str(sop_ref)).is_absolute():
        missing.append("sop_ref_absolute")
    if not path.exists():
        return {"ref": sop_ref, "path": str(path), "exists": False, "missing": missing + ["sop_file_missing"]}
    text = path.read_text(encoding="utf-8")
    if str(row.get("maturity_tier") or "") not in text:
        missing.append("sop_maturity_mismatch")
    if str(row.get("selected_strategy") or "") not in text:
        missing.append("sop_strategy_mismatch")
    if str(row.get("adapter_capability") or "") not in text:
        missing.append("sop_adapter_capability_mismatch")
    if any(token not in text for token in SOP_REQUIRED_TOKENS):
        missing.append("sop_required_contract_missing")
    return {
        "ref": sop_ref,
        "path": str(path),
        "exists": True,
        "missing": missing,
    }


def fact_import_allowed(route: dict[str, Any]) -> bool:
    if "fact_import_allowed" in route:
        return bool(route.get("fact_import_allowed"))
    return str(route.get("route_level") or "") not in NON_FACT_ROUTE_LEVELS


def is_fact_route(route: dict[str, Any]) -> bool:
    return fact_import_allowed(route) and str(route.get("route_level") or "") not in NON_FACT_ROUTE_LEVELS


def route_has_freshness_sla(metric_id: str, route: dict[str, Any], registry: dict[str, Any]) -> bool:
    metrics = registry.get("metrics") or {}
    metric = metrics.get(metric_id) or {}
    freshness_slas = registry.get("freshness_slas") or {}
    sla = route.get("freshness_sla") or metric.get("default_freshness_sla")
    return bool(sla and sla in freshness_slas)


def route_has_quality_gates(metric_id: str, route: dict[str, Any], registry: dict[str, Any]) -> bool:
    metrics = registry.get("metrics") or {}
    metric = metrics.get(metric_id) or {}
    return bool(route.get("quality_gates") or metric.get("acceptance_gates"))


def route_has_fact_pack_paths(metric_id: str, route: dict[str, Any], registry: dict[str, Any]) -> bool:
    metrics = registry.get("metrics") or {}
    metric = metrics.get(metric_id) or {}
    return bool(route.get("fact_pack_paths") or metric.get("default_fact_pack_paths"))


def route_has_repeatable_inputs(route: dict[str, Any]) -> bool:
    return bool(route.get("required_seeds") and route.get("source_fields"))


def job_text(job: dict[str, Any]) -> str:
    payload = job.get("payload") or {}
    schedule = job.get("schedule") or {}
    parts = [
        job.get("id"),
        job.get("name"),
        payload.get("message") if isinstance(payload, dict) else None,
        payload.get("command") if isinstance(payload, dict) else None,
        schedule.get("expr") if isinstance(schedule, dict) else None,
    ]
    return "\n".join(str(part) for part in parts if part).lower()


def platform_schedule_registered(platform: str, jobs: list[dict[str, Any]]) -> bool:
    needles = {
        platform.lower(),
        platform.replace("_", "-").lower(),
        platform.replace("_", " ").lower(),
    }
    for job in jobs:
        if job.get("enabled") is False:
            continue
        text = job_text(job)
        if "s31" not in text and "crawler" not in text and "爬虫" not in text and "opencli" not in text:
            continue
        if any(needle in text for needle in needles):
            return True
    return False


def scheduler_sources(config: dict[str, Any]) -> set[str]:
    sources: set[str] = set()
    for profile in (config.get("profiles") or {}).values():
        for lane in (profile.get("lanes") or {}).values():
            sources.update(str(source) for source in lane.get("sources") or [])
        sources.update(str(source) for source in profile.get("sourcePriority") or [])
    return sources


def scheduler_has_dedupe_controls(config: dict[str, Any]) -> bool:
    profiles = config.get("profiles") or {}
    for profile in profiles.values():
        daily = profile.get("daily") or {}
        risk = profile.get("risk") or {}
        if daily.get("queryOffsetCycle") and risk.get("duplicateDedupeCooldownMinutes"):
            return True
    return False


def central_scheduler_registered(platform: str, jobs: list[dict[str, Any]], scheduler_config: dict[str, Any]) -> bool:
    registered_sources = {str(source).lower() for source in scheduler_sources(scheduler_config)}
    if not (platform_aliases(platform) & registered_sources):
        return False
    launch = False
    harvest_strict = False
    for job in jobs:
        if job.get("enabled") is False:
            continue
        text = job_text(job)
        if ("competitor-crawl-scheduler.mjs" in text or "competitor-daily-cron.cmd" in text) and "--mode launch" in text:
            launch = True
        if "competitor-crawl-scheduler.mjs" in text and "--mode harvest" in text and "--mode status" in text and "--strict" in text:
            harvest_strict = True
    return launch and harvest_strict


def dedupe_gate_registered(
    platform: str,
    routes: dict[str, Any],
    jobs: list[dict[str, Any]],
    scheduler_config: dict[str, Any],
) -> bool:
    dedupe_tokens = ("dedupe", "duplicate", "去重", "不重复")
    registered_sources = {str(source).lower() for source in scheduler_sources(scheduler_config)}
    if platform_aliases(platform) & registered_sources and scheduler_has_dedupe_controls(scheduler_config):
        return True
    for route in routes.values():
        gate_text = " ".join(str(gate) for gate in route.get("quality_gates") or [])
        if any(token in gate_text.lower() for token in dedupe_tokens):
            return True
    platform_tokens = {
        platform.lower(),
        platform.replace("_", "-").lower(),
        platform.replace("_", " ").lower(),
    }
    for job in jobs:
        text = job_text(job)
        if any(token in text for token in dedupe_tokens) and any(token in text for token in platform_tokens):
            return True
    return False


def validate_closure_policy(baseline: dict[str, Any]) -> list[str]:
    policy = baseline.get("closure_policy") or {}
    errors: list[str] = []
    if policy.get("fact_source_target") != "M5":
        errors.append("closure_policy.fact_source_target must be M5")
    if policy.get("discovery_source_target") != "discovery_closure":
        errors.append("closure_policy.discovery_source_target must be discovery_closure")
    if policy.get("discovery_m5_exempt") is not True:
        errors.append("closure_policy.discovery_m5_exempt must be true")
    if policy.get("discovery_fact_import_allowed") is not False:
        errors.append("closure_policy.discovery_fact_import_allowed must be false")
    return errors


def upgrade_bucket(status: str, missing: list[str]) -> str:
    missing_set = set(missing)
    if status == "M5_READY":
        return "sealed"
    if status == "DISCOVERY_CLOSED":
        return "discovery_closed"
    if status in {"NOT_ONBOARDED", "ONBOARDING_GAPS"}:
        return "not_onboarded"
    if missing_set & FOUNDATION_GATES:
        return "foundation_route_first"
    if missing_set <= EVIDENCE_GATES:
        return "seal_evidence_first"
    if missing_set <= RUN_STABILITY_GATES:
        return "seal_run_stability"
    if missing_set <= (RUN_STABILITY_GATES | MATURITY_GATES | EVIDENCE_GATES):
        return "maturity_then_run_stability"
    if missing_set & DISCOVERY_GATES:
        return "discovery_policy_repair"
    if missing_set & ONBOARDING_GATES:
        return "onboarding_repair"
    return "manual_review"


def upgrade_priority(row: dict[str, Any], missing: list[str]) -> int:
    bucket = upgrade_bucket(row["readiness_status"], missing)
    bucket_order = {
        "seal_run_stability": 10,
        "maturity_then_run_stability": 20,
        "foundation_route_first": 30,
        "manual_review": 40,
        "not_onboarded": 50,
        "discovery_policy_repair": 60,
        "discovery_closed": 90,
        "sealed": 100,
        "seal_evidence_first": 15,
    }
    tier_order = {"M5": 0, "M4": 1, "M3": 2, "M2": 3, "M1": 4, "M0": 5}
    return bucket_order.get(bucket, 80) + tier_order.get(str(row.get("current_maturity_tier")), 9)


def gap_groups(rows: list[dict[str, Any]]) -> dict[str, list[str]]:
    groups: dict[str, list[str]] = {
        "maturity_evidence_conflict": [],
        "not_schedulable": [],
        "closure_receipt_missing": [],
        "closure_receipt_not_closed": [],
        "maturity_matrix_row_missing": [],
        "maturity_baseline_matrix_tier_mismatch": [],
        "hardening_gap_present": [],
        "scheduler_or_dedupe_missing": [],
        "runtime_health_missing": [],
        "runtime_manual_clearance_required": [],
        "runtime_not_safe_to_schedule": [],
        "sop_or_route_registry_drift": [],
    }
    for row in rows:
        missing = set(row.get("missing_m5_gates") or [])
        platform = str(row.get("platform"))
        if "maturity_evidence_conflict" in missing:
            groups["maturity_evidence_conflict"].append(platform)
        if "maturity_not_schedulable" in missing:
            groups["not_schedulable"].append(platform)
        if "closure_receipt_missing" in missing:
            groups["closure_receipt_missing"].append(platform)
        if "closure_receipt_not_closed" in missing:
            groups["closure_receipt_not_closed"].append(platform)
        if "maturity_matrix_row_missing" in missing:
            groups["maturity_matrix_row_missing"].append(platform)
        if "maturity_baseline_matrix_tier_mismatch" in missing:
            groups["maturity_baseline_matrix_tier_mismatch"].append(platform)
        if "maturity_hardening_gap_present" in missing:
            groups["hardening_gap_present"].append(platform)
        if missing & {"cron_schedule_missing", "dedupe_gate_missing"}:
            groups["scheduler_or_dedupe_missing"].append(platform)
        if "runtime_health_missing" in missing:
            groups["runtime_health_missing"].append(platform)
        if "runtime_manual_clearance_required" in missing:
            groups["runtime_manual_clearance_required"].append(platform)
        if "runtime_not_safe_to_schedule" in missing:
            groups["runtime_not_safe_to_schedule"].append(platform)
        if missing & {
            "sop_ref_missing",
            "sop_file_missing",
            "sop_maturity_mismatch",
            "sop_strategy_mismatch",
            "sop_adapter_capability_mismatch",
            "sop_required_contract_missing",
            "route_registry_platform_missing",
        }:
            groups["sop_or_route_registry_drift"].append(platform)
    return {key: sorted(values) for key, values in groups.items()}


def next_actions(row: dict[str, Any], missing: list[str]) -> list[str]:
    actions: list[str] = []
    missing_set = set(missing)
    if "metric_routes_missing" in missing_set or "fact_import_routes_missing" in missing_set:
        actions.append("register_fact_metric_routes")
    if "repeatable_seed_or_source_field_missing" in missing_set:
        actions.append("fill_repeatable_seed_and_source_fields")
    if "freshness_sla_missing" in missing_set:
        actions.append("register_freshness_sla")
    if "quality_gates_missing" in missing_set:
        actions.append("register_quality_gates")
    if "fact_pack_paths_missing" in missing_set:
        actions.append("register_fact_pack_paths")
    if missing_set & {
        "sop_ref_missing",
        "sop_file_missing",
        "sop_maturity_mismatch",
        "sop_strategy_mismatch",
        "sop_adapter_capability_mismatch",
        "sop_required_contract_missing",
    }:
        actions.append("align_platform_sop_with_baseline")
    if "route_registry_platform_missing" in missing_set:
        actions.append("register_platform_route_registry")
    if "maturity_not_m5" in missing_set:
        actions.append("prove_platform_maturity_to_m5")
    if "maturity_evidence_conflict" in missing_set:
        actions.append("reconcile_maturity_matrix_with_closure_evidence")
    if "maturity_matrix_row_missing" in missing_set:
        actions.append("register_platform_in_maturity_matrix")
    if "maturity_baseline_matrix_tier_mismatch" in missing_set:
        actions.append("reconcile_baseline_with_maturity_matrix")
    if "maturity_quality_not_sealed" in missing_set:
        actions.append("seal_quality_fact_attribution")
    if "maturity_stability_not_sealed" in missing_set:
        actions.append("prove_stable_recent_live_run")
    if "maturity_hardening_gap_present" in missing_set:
        actions.append("clear_maturity_hardening_gap")
    if "maturity_not_schedulable" in missing_set:
        actions.append("clear_platform_runtime_risk_or_auth_pause")
    if "runtime_health_missing" in missing_set:
        actions.append("register_platform_in_health_matrix")
    if "runtime_manual_clearance_required" in missing_set:
        actions.append("clear_manual_runtime_clearance_before_launch")
    if "runtime_not_safe_to_schedule" in missing_set:
        actions.append("resolve_runtime_health_before_scheduling")
    if "closure_receipt_missing" in missing_set:
        actions.append("generate_platform_closure_receipt")
    if "closure_receipt_not_closed" in missing_set or "closure_dimension_gaps_present" in missing_set:
        actions.append("close_platform_data_plane_receipt_gaps")
    if "m5_evidence_missing" in missing_set and "maturity_evidence_conflict" not in missing_set:
        actions.append("attach_platform_closure_or_maturity_evidence")
    if "cron_schedule_missing" in missing_set:
        actions.append("register_openclaw_cron_schedule")
    if "dedupe_gate_missing" in missing_set:
        actions.append("register_platform_dedupe_gate")
    if row["readiness_status"] == "NOT_ONBOARDED":
        actions.append("run_platform_onboarding_probe")
    if row["readiness_status"] == "DISCOVERY_CLOSED":
        actions.append("keep_as_discovery_handoff_source")
    return actions


def evaluate_platform(
    platform: str,
    row: dict[str, Any],
    *,
    baseline: dict[str, Any],
    registry: dict[str, Any],
    cron_jobs: list[dict[str, Any]],
    scheduler_config: dict[str, Any],
    closure_index: dict[str, Any],
    maturity_matrix: dict[str, Any],
    health_matrix: dict[str, Any],
) -> dict[str, Any]:
    routes = platform_routes(registry, platform)
    route_platform_registered = platform in (registry.get("platform_metric_routes") or {})
    sop = sop_evidence(platform, row)
    route_levels = sorted({str(route.get("route_level") or "") for route in routes.values() if isinstance(route, dict)})
    fact_routes = {
        metric_id: route
        for metric_id, route in routes.items()
        if isinstance(route, dict) and is_fact_route(route)
    }
    discovery_routes = {
        metric_id: route
        for metric_id, route in routes.items()
        if isinstance(route, dict) and str(route.get("route_level") or "") in DISCOVERY_ROUTE_LEVELS
    }
    unavailable_routes = {
        metric_id: route
        for metric_id, route in routes.items()
        if isinstance(route, dict) and str(route.get("route_level") or "") in UNAVAILABLE_ROUTE_LEVELS
    }
    is_discovery = is_discovery_source(row, baseline)
    direct_schedule = platform_schedule_registered(platform, cron_jobs)
    central_schedule = central_scheduler_registered(platform, cron_jobs, scheduler_config)
    scheduled = direct_schedule or central_schedule
    dedupe = dedupe_gate_registered(platform, routes, cron_jobs, scheduler_config)
    evidence_ok, evidence = has_m5_evidence(platform, closure_index, maturity_matrix)
    health = health_evidence(platform, health_matrix)
    missing: list[str] = []

    if is_discovery:
        if row.get("m5_required") is not False:
            missing.append("discovery_m5_exemption_missing")
        if row.get("closure_target") != "discovery_closure":
            missing.append("discovery_closure_target_missing")
        if fact_routes:
            missing.append("direct_fact_route_registered_for_discovery_source")
        if not discovery_routes:
            missing.append("discovery_route_missing")
        readiness_status = "DISCOVERY_CLOSED" if not missing else "DISCOVERY_GAPS"
    elif row.get("adapter_capability") == "skipped_receipt_adapter" or row.get("selected_strategy") == "skipped":
        if fact_routes:
            missing.append("skipped_source_has_fact_routes")
        if not unavailable_routes:
            missing.append("unavailable_route_missing")
        readiness_status = "NOT_ONBOARDED" if not missing else "ONBOARDING_GAPS"
    else:
        if row.get("m5_required") is False or row.get("closure_target") == "discovery_closure":
            missing.append("fact_source_m5_target_opted_out")
        if row.get("maturity_tier") != "M5":
            missing.append("maturity_not_m5")
        if evidence.get("conflict"):
            missing.append("maturity_evidence_conflict")
        closure = evidence.get("closure", {})
        if not evidence_ok and not closure.get("closed"):
            if closure.get("receipt_path") or closure.get("closure_status"):
                missing.append("closure_receipt_not_closed")
            else:
                missing.append("closure_receipt_missing")
            if closure.get("key_dimension_gaps"):
                missing.append("closure_dimension_gaps_present")
        maturity = evidence.get("maturity", {})
        if not maturity.get("explicit"):
            missing.append("maturity_matrix_row_missing")
        else:
            if row.get("maturity_tier") != maturity.get("maturity_tier"):
                missing.append("maturity_baseline_matrix_tier_mismatch")
            if maturity.get("quality_attribution_status") != "QUALITY_FACTS_SEALED":
                missing.append("maturity_quality_not_sealed")
            if maturity.get("stability_status") != "STABLE_RECENT_LIVE":
                missing.append("maturity_stability_not_sealed")
            if maturity.get("hardening_gap_status") not in {None, "", "NONE"}:
                missing.append("maturity_hardening_gap_present")
        if (
            maturity.get("explicit")
            and maturity.get("can_schedule_live_now") is False
        ):
            missing.append("maturity_not_schedulable")
        if not health["explicit"]:
            missing.append("runtime_health_missing")
        else:
            if health["anti_risk_manual_clearance_required"]:
                missing.append("runtime_manual_clearance_required")
            if health["safe_to_schedule_now"] is False or health["active_cooldown"]:
                missing.append("runtime_not_safe_to_schedule")
        if not evidence_ok:
            missing.append("m5_evidence_missing")
        if not routes:
            missing.append("metric_routes_missing")
        if not route_platform_registered:
            missing.append("route_registry_platform_missing")
        missing.extend(gate for gate in sop["missing"] if gate in FOUNDATION_GATES)
        if not fact_routes:
            missing.append("fact_import_routes_missing")
        if any(not route_has_repeatable_inputs(route) for route in fact_routes.values()):
            missing.append("repeatable_seed_or_source_field_missing")
        if any(not route_has_freshness_sla(metric_id, route, registry) for metric_id, route in fact_routes.items()):
            missing.append("freshness_sla_missing")
        if any(not route_has_quality_gates(metric_id, route, registry) for metric_id, route in fact_routes.items()):
            missing.append("quality_gates_missing")
        if any(not route_has_fact_pack_paths(metric_id, route, registry) for metric_id, route in fact_routes.items()):
            missing.append("fact_pack_paths_missing")
        if not scheduled:
            missing.append("cron_schedule_missing")
        if not dedupe:
            missing.append("dedupe_gate_missing")
        readiness_status = "M5_READY" if not missing else "M5_GAPS"

    evaluated = {
        "platform": platform,
        "source_family": row.get("source_family"),
        "current_maturity_tier": row.get("maturity_tier"),
        "current_label": row.get("label"),
        "closure_target": row.get("closure_target") or "M5",
        "m5_required": not is_discovery and row.get("adapter_capability") != "skipped_receipt_adapter",
        "selected_strategy": row.get("selected_strategy"),
        "adapter_capability": row.get("adapter_capability"),
        "contract_level": row.get("contract_level"),
        "metric_count": len(routes),
        "fact_metric_count": len(fact_routes),
        "discovery_metric_count": len(discovery_routes),
        "unavailable_metric_count": len(unavailable_routes),
        "route_levels": route_levels,
        "route_registry_platform_registered": route_platform_registered,
        "sop": sop,
        "has_repeatable_fact_routes": bool(fact_routes)
        and all(route_has_repeatable_inputs(route) for route in fact_routes.values()),
        "has_freshness_sla": bool(fact_routes)
        and all(route_has_freshness_sla(metric_id, route, registry) for metric_id, route in fact_routes.items()),
        "has_quality_gates": bool(fact_routes)
        and all(route_has_quality_gates(metric_id, route, registry) for metric_id, route in fact_routes.items()),
        "has_fact_pack_paths": bool(fact_routes)
        and all(route_has_fact_pack_paths(metric_id, route, registry) for metric_id, route in fact_routes.items()),
        "has_schedule_registration": scheduled,
        "schedule_source": "central_scheduler" if central_schedule else "direct_cron" if direct_schedule else "missing",
        "has_dedupe_gate": dedupe,
        "has_m5_evidence": evidence_ok,
        "m5_evidence": evidence,
        "runtime_health": health,
        "readiness_status": readiness_status,
        "missing_m5_gates": missing,
    }
    evaluated["upgrade_bucket"] = upgrade_bucket(readiness_status, missing)
    evaluated["upgrade_priority"] = upgrade_priority(evaluated, missing)
    evaluated["next_actions"] = next_actions(evaluated, missing)
    return evaluated


def build_readiness_matrix(
    *,
    baseline: dict[str, Any],
    registry: dict[str, Any],
    cron_meta: dict[str, Any],
    cron_jobs: list[dict[str, Any]],
    scheduler_meta: dict[str, Any],
    scheduler_config: dict[str, Any],
    closure_meta: dict[str, Any] | None = None,
    closure_index: dict[str, Any] | None = None,
    maturity_meta: dict[str, Any] | None = None,
    maturity_matrix: dict[str, Any] | None = None,
    health_meta: dict[str, Any] | None = None,
    health_matrix: dict[str, Any] | None = None,
) -> dict[str, Any]:
    errors = validate_closure_policy(baseline)
    closure_meta = closure_meta or {"path": "", "exists": False}
    closure_index = closure_index or {}
    maturity_meta = maturity_meta or {"path": "", "exists": False}
    maturity_matrix = maturity_matrix or {}
    health_meta = health_meta or {"path": "", "exists": False}
    health_matrix = health_matrix or {}
    platforms = {
        platform: evaluate_platform(
            platform,
            row,
            baseline=baseline,
            registry=registry,
            cron_jobs=cron_jobs,
            scheduler_config=scheduler_config,
            closure_index=closure_index,
            maturity_matrix=maturity_matrix,
            health_matrix=health_matrix,
        )
        for platform, row in (baseline.get("platforms") or {}).items()
        if isinstance(row, dict)
    }
    fact_sources = [row for row in platforms.values() if row["m5_required"]]
    discovery_sources = [row for row in platforms.values() if row["readiness_status"].startswith("DISCOVERY")]
    m5_ready = [row for row in fact_sources if row["readiness_status"] == "M5_READY"]
    m5_gaps = [row for row in fact_sources if row["readiness_status"] != "M5_READY"]
    by_status: dict[str, int] = {}
    by_bucket: dict[str, int] = {}
    for row in platforms.values():
        by_status[row["readiness_status"]] = by_status.get(row["readiness_status"], 0) + 1
        by_bucket[row["upgrade_bucket"]] = by_bucket.get(row["upgrade_bucket"], 0) + 1
    upgrade_queue = sorted(
        [
            {
                "platform": row["platform"],
                "upgrade_priority": row["upgrade_priority"],
                "upgrade_bucket": row["upgrade_bucket"],
                "current_maturity_tier": row["current_maturity_tier"],
                "missing_m5_gates": row["missing_m5_gates"],
                "next_actions": row["next_actions"],
            }
            for row in platforms.values()
            if row["upgrade_bucket"] not in {"sealed", "discovery_closed"}
        ],
        key=lambda item: (item["upgrade_priority"], item["platform"]),
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "ok": not errors,
        "errors": errors,
        "sources": {
            "baseline": str(BASELINE_PATH),
            "registry": str(REGISTRY_PATH),
            "cron": cron_meta,
            "scheduler": scheduler_meta,
            "closure_index": closure_meta,
            "maturity_matrix": maturity_meta,
            "health_matrix": health_meta,
        },
        "summary": {
            "platform_count": len(platforms),
            "fact_source_count": len(fact_sources),
            "discovery_exempt_count": len(discovery_sources),
            "m5_required_platforms": [row["platform"] for row in fact_sources],
            "m5_ready_platforms": [row["platform"] for row in m5_ready],
            "m5_gap_platforms": [row["platform"] for row in m5_gaps],
            "discovery_exempt_platforms": [row["platform"] for row in discovery_sources],
            "m5_ready_count": len(m5_ready),
            "m5_gap_count": len(m5_gaps),
            "all_required_fact_sources_m5_ready": not m5_gaps,
            "status_counts": by_status,
            "upgrade_bucket_counts": by_bucket,
            "highest_priority_gap": upgrade_queue[0] if upgrade_queue else {},
            "gap_groups": gap_groups(m5_gaps),
        },
        "upgrade_queue": upgrade_queue,
        "platforms": platforms,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate S31 platform M5 readiness matrix.")
    parser.add_argument("--baseline", default=str(BASELINE_PATH))
    parser.add_argument("--registry", default=str(REGISTRY_PATH))
    parser.add_argument("--cron-jobs", default=str(DEFAULT_CRON_PATH))
    parser.add_argument("--scheduler-config", default=str(DEFAULT_SCHEDULER_CONFIG_PATH))
    parser.add_argument("--closure-index", default=str(DEFAULT_CLOSURE_INDEX_PATH))
    parser.add_argument("--maturity-matrix", default=str(DEFAULT_MATURITY_MATRIX_PATH))
    parser.add_argument("--health-matrix", default=str(DEFAULT_HEALTH_MATRIX_PATH))
    parser.add_argument("--output", default="", help="Optional path to write the readiness matrix JSON.")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Return non-zero when any required fact-source platform is not M5-ready.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    baseline = load_yaml(Path(args.baseline))
    registry = load_yaml(Path(args.registry))
    cron_meta, cron_jobs = load_cron_jobs(Path(args.cron_jobs))
    scheduler_meta, scheduler_config = load_scheduler_config(Path(args.scheduler_config))
    closure_meta, closure_index = load_optional_json(Path(args.closure_index))
    maturity_meta, maturity_matrix = load_optional_json(Path(args.maturity_matrix))
    health_meta, health_matrix = load_optional_json(Path(args.health_matrix))
    matrix = build_readiness_matrix(
        baseline=baseline,
        registry=registry,
        cron_meta=cron_meta,
        cron_jobs=cron_jobs,
        scheduler_meta=scheduler_meta,
        scheduler_config=scheduler_config,
        closure_meta=closure_meta,
        closure_index=closure_index,
        maturity_meta=maturity_meta,
        maturity_matrix=maturity_matrix,
        health_meta=health_meta,
        health_matrix=health_matrix,
    )
    payload = json.dumps(matrix, ensure_ascii=False, indent=2)
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(payload + "\n", encoding="utf-8")
    print(payload)
    if not matrix["ok"]:
        return 1
    if args.strict and not matrix["summary"]["all_required_fact_sources_m5_ready"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
