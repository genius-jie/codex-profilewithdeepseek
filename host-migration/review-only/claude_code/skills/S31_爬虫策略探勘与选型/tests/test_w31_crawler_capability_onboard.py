from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import yaml


SCRIPT = Path(r'@@GENERAL_ROOT:win@@\tooling\w31\w31_crawler_capability_onboard.py')
SPEC = importlib.util.spec_from_file_location("w31_crawler_capability_onboard", SCRIPT)
assert SPEC and SPEC.loader
module = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = module
SPEC.loader.exec_module(module)


def make_capability(
    tmp_path: Path,
    capability_id: str = "fixture.article.detail.v1",
    *,
    status: str = "active",
    selection_priority: int = 50,
) -> dict:
    adapter = tmp_path / f"{capability_id.replace('.', '_')}.py"
    adapter.write_text("print('fixture')\n", encoding="utf-8")
    skill_ref = tmp_path / "fixture-SKILL.md"
    workflow_ref = tmp_path / "fixture-WORKFLOW.md"
    skill_ref.write_text("fixture skill\n", encoding="utf-8")
    workflow_ref.write_text("fixture workflow\n", encoding="utf-8")
    return {
        "capability_id": capability_id,
        "status": status,
        "maturity_status": "verified_live" if status == "active" else "scaffold",
        "selection_priority": selection_priority,
        "business_profiles": ["article_detail"],
        "collection_modes": ["query_search_data_collection"],
        "source_match": {"default_platform": "fixture", "platforms": ["fixture"]},
        "supported_operations": ["detail"],
        "required_nodes": ["S31A", "S31C", "S31D"],
        "fact_pack_profile": "article_detail.v1",
        "failure_states": ["adapter_failed"],
        "adapter": {
            "execution_kind": "governed_pipeline",
            "runtime": "python",
            "entrypoint": str(adapter),
            "required_inputs": {"query": "--query", "output_dir": "--output-dir"},
            "optional_inputs": {},
            "boolean_flags": {},
            "context_inputs": {
                "capability_id": "--capability-id",
                "capability_resolution_ref": "--capability-resolution-ref",
                "crawler_capability_registry_ref": "--capability-registry-ref",
            },
            "output_contract": {
                "adapter_receipt": "adapter_receipt.json",
                "route_receipt": "s31a_route_receipt.v1.json",
                "checked_fact_pack": "crawler_fact_pack.v1.checked.json",
                "w31_handoff": "w31_handoff.v1.json",
            },
            "artifact_assertions": {
                "adapter_receipt": {"status_path": "status", "success_values": ["passed"]},
                "route_receipt": {"schema_version": "s31a_route_receipt.v1"},
                "checked_fact_pack": {
                    "schema_version": "crawler_fact_pack.v1",
                    "status_path": "validation.ok",
                    "success_values": [True],
                },
                "w31_handoff": {
                    "schema_version": "w31_handoff.v1",
                    "status_path": "collection_status",
                    "success_values": ["ok"],
                },
            },
            "success_status_path": "status",
            "success_values": ["passed"],
        },
        "verification": {"live_fixture_required": True},
        "ownership": {
            "skill": str(skill_ref),
            "workflow": str(workflow_ref),
            "project_overlay_policy": "capability_id_reference_only",
        },
    }


def make_manifest(capability: dict) -> dict:
    return {
        "schema_version": module.MANIFEST_SCHEMA,
        "capability": capability,
        "resolution_examples": [{
            "platform": "fixture",
            "business_profile": "article_detail",
            "collection_mode": "query_search_data_collection",
            "expected_capability_id": capability["capability_id"],
        }],
        "evidence": {"live_run_dir": None},
    }


def make_registry(path: Path, capabilities: list[dict] | None = None) -> None:
    path.write_text(
        yaml.safe_dump(
            {"schema_version": "crawler_capability_registry.v1", "capabilities": capabilities or []},
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def make_evidence(path: Path, capability_id: str) -> None:
    path.mkdir(parents=True)
    context = {
        "capability_id": capability_id,
        "capability_resolution_ref": str(path.resolve() / "w31_crawler_capability_resolution.v1.json"),
        "capability_dispatch_ref": str(path.resolve() / "w31_crawler_capability_dispatch.v1.json"),
        "crawler_capability_registry_ref": str(path.resolve() / "candidate_registry.yaml"),
    }
    write_json(path / "adapter_receipt.json", {"status": "passed", **context})
    write_json(path / "s31a_route_receipt.v1.json", {
        "schema_version": "s31a_route_receipt.v1",
        **context,
    })
    write_json(path / "crawler_fact_pack.v1.checked.json", {
        "schema_version": "crawler_fact_pack.v1",
        **context,
        "validation": {"ok": True},
    })
    write_json(path / "w31_handoff.v1.json", {
        "schema_version": "w31_handoff.v1",
        **context,
        "collection_status": "ok",
    })
    write_json(path / "w31_crawler_capability_dispatch.v1.json", {
        "status": "passed",
        "capability_id": capability_id,
    })
    write_json(path / "w31_crawler_capability_resolution.v1.json", {
        "status": "resolved",
        "selected_capability": {"capability_id": capability_id},
    })


def test_init_creates_experimental_manifest_that_passes_contract_check(tmp_path: Path) -> None:
    entrypoint = tmp_path / "adapter.py"
    entrypoint.write_text("print('ok')\n", encoding="utf-8")
    manifest_path = tmp_path / "manifest.yaml"
    completed = subprocess.run([
        sys.executable,
        str(SCRIPT),
        "init",
        "--capability-id", "fixture.query.v1",
        "--entrypoint", str(entrypoint),
        "--platform", "fixture",
        "--business-profile", "article_detail",
        "--collection-mode", "query_search_data_collection",
        "--fact-pack-profile", "article_detail.v1",
        "--skill-ref", "fixture-skill",
        "--required-input", "query=--query",
        "--required-input", "output_dir=--output-dir",
        "--manifest-output", str(manifest_path),
    ], capture_output=True, text=True, encoding="utf-8", check=False)
    assert completed.returncode == 0, completed.stderr
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    registry_path = tmp_path / "registry.yaml"
    make_registry(registry_path)

    receipt, _ = module.evaluate_onboarding(
        manifest,
        {"schema_version": "crawler_capability_registry.v1", "capabilities": []},
        registry_path=registry_path,
    )

    assert manifest["capability"]["status"] == "experimental"
    assert receipt["status"] == "passed"
    assert receipt["registration_action"] == "add"

    evidence_dir = tmp_path / "live-evidence"
    promoted = subprocess.run([
        sys.executable,
        str(SCRIPT),
        "promote",
        "--manifest", str(manifest_path),
        "--evidence-dir", str(evidence_dir),
    ], capture_output=True, text=True, encoding="utf-8", check=False)
    promoted_manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    assert promoted.returncode == 0, promoted.stderr
    assert promoted_manifest["capability"]["status"] == "active"
    assert promoted_manifest["evidence"]["live_run_dir"] == str(evidence_dir.resolve())


def test_active_capability_requires_live_evidence(tmp_path: Path) -> None:
    capability = make_capability(tmp_path)
    registry_path = tmp_path / "registry.yaml"
    make_registry(registry_path)

    receipt, _ = module.evaluate_onboarding(
        make_manifest(capability),
        {"schema_version": "crawler_capability_registry.v1", "capabilities": []},
        registry_path=registry_path,
    )

    assert receipt["status"] == "failed"
    assert "active_live_evidence_required" in receipt["failures"]


def test_stage_writes_candidate_registry_without_mutating_source(tmp_path: Path) -> None:
    capability = make_capability(tmp_path, status="experimental")
    manifest_path = tmp_path / "manifest.yaml"
    manifest_path.write_text(
        yaml.safe_dump(make_manifest(capability), allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    registry_path = tmp_path / "registry.yaml"
    make_registry(registry_path)
    original = registry_path.read_text(encoding="utf-8")
    staged_path = tmp_path / "candidate-registry.yaml"

    completed = subprocess.run([
        sys.executable,
        str(SCRIPT),
        "stage",
        "--manifest", str(manifest_path),
        "--registry", str(registry_path),
        "--candidate-registry-output", str(staged_path),
    ], capture_output=True, text=True, encoding="utf-8", check=False)
    staged = yaml.safe_load(staged_path.read_text(encoding="utf-8"))

    assert completed.returncode == 0, completed.stderr
    assert registry_path.read_text(encoding="utf-8") == original
    assert staged["capabilities"][0]["capability_id"] == capability["capability_id"]

    rejected = subprocess.run([
        sys.executable,
        str(SCRIPT),
        "stage",
        "--manifest", str(manifest_path),
        "--registry", str(registry_path),
        "--candidate-registry-output", str(registry_path),
    ], capture_output=True, text=True, encoding="utf-8", check=False)
    assert rejected.returncode == 2
    assert "candidate_registry_must_not_overwrite_source_registry" in rejected.stdout
    assert registry_path.read_text(encoding="utf-8") == original


def test_apply_registers_active_capability_and_is_idempotent(tmp_path: Path) -> None:
    capability = make_capability(tmp_path)
    manifest_path = tmp_path / "manifest.yaml"
    manifest_path.write_text(
        yaml.safe_dump(make_manifest(capability), allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    registry_path = tmp_path / "registry.yaml"
    make_registry(registry_path)
    evidence_dir = tmp_path / "evidence"
    make_evidence(evidence_dir, capability["capability_id"])
    receipt_path = tmp_path / "receipt.json"

    command = [
        sys.executable,
        str(SCRIPT),
        "apply",
        "--manifest", str(manifest_path),
        "--registry", str(registry_path),
        "--evidence-dir", str(evidence_dir),
        "--receipt", str(receipt_path),
    ]
    first = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", check=False)
    second = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", check=False)
    updated = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
    second_receipt = json.loads(second.stdout)

    assert first.returncode == 0, first.stderr
    assert second.returncode == 0, second.stderr
    assert [item["capability_id"] for item in updated["capabilities"]] == [capability["capability_id"]]
    assert second_receipt["registration_action"] == "already_registered"
    assert second_receipt["registry_written"] is False
    assert json.loads(receipt_path.read_text(encoding="utf-8"))["status"] == "passed"


def test_onboarding_rejects_ambiguous_resolution(tmp_path: Path) -> None:
    existing = make_capability(tmp_path, "fixture.existing.v1")
    candidate = make_capability(tmp_path, "fixture.candidate.v1")
    evidence_dir = tmp_path / "evidence"
    make_evidence(evidence_dir, candidate["capability_id"])
    registry_path = tmp_path / "registry.yaml"
    make_registry(registry_path, [existing])

    receipt, _ = module.evaluate_onboarding(
        make_manifest(candidate),
        {"schema_version": "crawler_capability_registry.v1", "capabilities": [existing]},
        registry_path=registry_path,
        evidence_dir=evidence_dir,
    )

    assert receipt["status"] == "failed"
    assert any("resolution_example_failed:ambiguous" in item for item in receipt["failures"])


def test_apply_refuses_concurrent_registry_change(monkeypatch, tmp_path: Path) -> None:
    capability = make_capability(tmp_path)
    manifest_path = tmp_path / "manifest.yaml"
    manifest_path.write_text(
        yaml.safe_dump(make_manifest(capability), allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    registry_path = tmp_path / "registry.yaml"
    make_registry(registry_path)
    evidence_dir = tmp_path / "evidence"
    make_evidence(evidence_dir, capability["capability_id"])
    calls = 0

    def drifting_hash(_: Path) -> str:
        nonlocal calls
        calls += 1
        return "before" if calls <= 2 else "changed"

    monkeypatch.setattr(module.dispatcher, "sha256_file", drifting_hash)
    result = module.run_check_or_apply(SimpleNamespace(
        manifest=manifest_path,
        registry=registry_path,
        evidence_dir=evidence_dir,
        replace=False,
        receipt=None,
    ), apply=True)

    assert result["status"] == "failed"
    assert "registry_changed_during_onboarding" in result["failures"]
    assert yaml.safe_load(registry_path.read_text(encoding="utf-8"))["capabilities"] == []
