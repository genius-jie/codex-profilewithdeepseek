from __future__ import annotations

import copy
import importlib.util
import json
import sys
from pathlib import Path

import yaml


SCRIPT = Path(r'@@GENERAL_ROOT:win@@\tooling\w31\w31_crawler_capability_dispatch.py')
SPEC = importlib.util.spec_from_file_location("w31_crawler_capability_dispatch", SCRIPT)
assert SPEC and SPEC.loader
module = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = module
SPEC.loader.exec_module(module)


def bundled_registry() -> tuple[Path, dict]:
    return module.load_registry(module.DEFAULT_REGISTRY)


def test_bundled_registry_is_complete() -> None:
    path, data = bundled_registry()
    result = module.validate_registry(data, path)
    assert result["status"] == "passed"
    assert result["capability_count"] >= 1
    assert result["errors"] == []


def test_epub_url_resolves_to_complete_capability() -> None:
    path, data = bundled_registry()
    result = module.resolve_capability(
        data,
        registry_path=path,
        url="https://www.epub.pub/book/example-book",
        business_profile="ebook_single_book_fulltext",
        collection_mode="query_search_data_collection",
    )
    selected = result["selected_capability"]
    assert result["status"] == "resolved"
    assert selected["capability_id"] == "ebook.epub_pub.single_book_fulltext.v1"
    assert selected["required_nodes"] == ["S31A", "S31C", "S31D"]
    assert set(selected["adapter"]["output_contract"]) == {
        "adapter_receipt",
        "route_receipt",
        "checked_fact_pack",
        "w31_handoff",
    }


def test_unknown_url_stays_explicitly_unresolved() -> None:
    path, data = bundled_registry()
    result = module.resolve_capability(
        data,
        registry_path=path,
        url="https://unknown.invalid/item/1",
    )
    assert result["status"] == "capability_not_found"
    assert result["selected_capability"] is None


def test_dry_run_builds_capability_bound_command(tmp_path: Path) -> None:
    path, data = bundled_registry()
    output_dir = tmp_path / "run"
    result = module.dispatch_capability(
        data,
        registry_path=path,
        inputs={"url": "https://www.epub.pub/book/example-book", "output_dir": str(output_dir)},
        url="https://www.epub.pub/book/example-book",
        business_profile="ebook_single_book_fulltext",
        collection_mode="query_search_data_collection",
        dry_run=True,
    )
    assert result["status"] == "planned"
    assert "--capability-id" in result["command"]
    assert "ebook.epub_pub.single_book_fulltext.v1" in result["command"]
    assert "--capability-registry-ref" in result["command"]
    assert (output_dir / "w31_crawler_capability_resolution.v1.json").is_file()
    assert (output_dir / "w31_crawler_capability_dispatch.v1.json").is_file()


def test_new_complete_capability_is_runnable_by_registry_only(tmp_path: Path) -> None:
    adapter = tmp_path / "dummy_adapter.py"
    skill_ref = tmp_path / "SKILL.md"
    workflow_ref = tmp_path / "WORKFLOW.md"
    skill_ref.write_text("fixture skill\n", encoding="utf-8")
    workflow_ref.write_text("fixture workflow\n", encoding="utf-8")
    adapter.write_text(
        "import argparse, json\n"
        "from pathlib import Path\n"
        "p=argparse.ArgumentParser(); p.add_argument('--query'); p.add_argument('--output-dir'); "
        "p.add_argument('--capability-id'); p.add_argument('--capability-resolution-ref'); a=p.parse_args()\n"
        "o=Path(a.output_dir); o.mkdir(parents=True, exist_ok=True)\n"
        "(o/'adapter_receipt.json').write_text(json.dumps({'status':'passed'}), encoding='utf-8')\n"
        "(o/'route_receipt.json').write_text(json.dumps({'schema_version':'s31a_route_receipt.v1'}), encoding='utf-8')\n"
        "(o/'crawler_fact_pack.v1.checked.json').write_text(json.dumps({'schema_version':'crawler_fact_pack.v1','validation':{'ok':True}}), encoding='utf-8')\n"
        "(o/'w31_handoff.v1.json').write_text(json.dumps({'schema_version':'w31_handoff.v1','collection_status':'ok'}), encoding='utf-8')\n",
        encoding="utf-8",
    )
    registry_data = {
        "schema_version": "crawler_capability_registry.v1",
        "capabilities": [{
            "capability_id": "fixture.article.detail.v1",
            "status": "active",
            "maturity_status": "test",
            "selection_priority": 1,
            "business_profiles": ["article_detail"],
            "collection_modes": ["query_search_data_collection"],
            "source_match": {"platforms": ["fixture"], "url_patterns": [r"^https://fixture\\.invalid/"]},
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
                },
                "output_contract": {
                    "adapter_receipt": "adapter_receipt.json",
                    "route_receipt": "route_receipt.json",
                    "checked_fact_pack": "crawler_fact_pack.v1.checked.json",
                    "w31_handoff": "w31_handoff.v1.json",
                },
                "artifact_assertions": {
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
            "ownership": {
                "skill": str(skill_ref),
                "workflow": str(workflow_ref),
                "project_overlay_policy": "capability_id_reference_only",
            },
        }],
    }
    registry = tmp_path / "registry.yaml"
    registry.write_text(yaml.safe_dump(registry_data, allow_unicode=True, sort_keys=False), encoding="utf-8")
    path, loaded = module.load_registry(registry)
    output_dir = tmp_path / "output"
    result = module.dispatch_capability(
        loaded,
        registry_path=path,
        inputs={"query": "one", "output_dir": str(output_dir)},
        capability_id="fixture.article.detail.v1",
        platform="fixture",
        business_profile="article_detail",
        collection_mode="query_search_data_collection",
    )
    assert result["status"] == "passed"
    assert result["failures"] == []
    handoff = json.loads((output_dir / "w31_handoff.v1.json").read_text(encoding="utf-8"))
    assert handoff["capability_id"] == "fixture.article.detail.v1"
    assert handoff["capability_resolution_ref"].endswith("w31_crawler_capability_resolution.v1.json")
    assert handoff["capability_dispatch_ref"].endswith("w31_crawler_capability_dispatch.v1.json")
    assert handoff["crawler_capability_registry_ref"] == str(path)

    adapter.write_text(adapter.read_text(encoding="utf-8").replace("'ok':True", "'ok':False"), encoding="utf-8")
    failed = module.dispatch_capability(
        loaded,
        registry_path=path,
        inputs={"query": "two", "output_dir": str(tmp_path / "invalid-output")},
        capability_id="fixture.article.detail.v1",
        platform="fixture",
        business_profile="article_detail",
        collection_mode="query_search_data_collection",
    )
    assert failed["status"] == "failed"
    assert "artifact_status:checked_fact_pack:validation.ok:False" in failed["failures"]


def test_skill_metadata_without_runtime_entrypoint_cannot_be_active_capability(tmp_path: Path) -> None:
    path, data = bundled_registry()
    broken = copy.deepcopy(data)
    broken["capabilities"][0]["adapter"]["entrypoint"] = str(tmp_path / "missing_adapter.py")

    result = module.validate_registry(broken, path)

    assert result["status"] == "failed"
    assert any("adapter_entrypoint_not_found" in item for item in result["errors"])


def test_active_capability_requires_real_skill_and_workflow_owners(tmp_path: Path) -> None:
    path, data = bundled_registry()
    broken = copy.deepcopy(data)
    broken["capabilities"][0]["ownership"]["skill"] = str(tmp_path / "missing-SKILL.md")
    broken["capabilities"][0]["ownership"]["workflow"] = str(tmp_path / "missing-WORKFLOW.md")

    result = module.validate_registry(broken, path)

    assert result["status"] == "failed"
    assert any("ownership_skill_not_found" in item for item in result["errors"])
    assert any("ownership_workflow_not_found" in item for item in result["errors"])
