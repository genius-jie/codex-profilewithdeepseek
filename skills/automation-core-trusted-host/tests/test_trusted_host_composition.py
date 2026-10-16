from __future__ import annotations

import importlib
import json
import re
import subprocess
import sys
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_ROOT = SKILL_ROOT / "scripts"
CORE_SRC = Path(r"E:\personal-ai-suite\automation-core\src")
ACTIVE_PARENT_SKILLS = Path(r"C:\Users\Administrator\.agent\assets\skills")


def _load_context_module():
    for path in (CORE_SRC, SCRIPTS_ROOT):
        value = str(path)
        if value not in sys.path:
            sys.path.insert(0, value)
    return importlib.import_module("automation_core_context")


def test_context_factory_instantiates_from_active_parent_skill_assets() -> None:
    module = _load_context_module()

    assert module.SHARED_SKILLS == ACTIVE_PARENT_SKILLS
    provider = module.agent_context_factory()

    p3_work = provider({"stage": "p3", "kind": "work"})
    assert [item["skill_id"] for item in p3_work["skill_snapshot"]] == ["S11"]
    assert all(
        Path(item["source_ref"]).is_relative_to(ACTIVE_PARENT_SKILLS)
        for item in p3_work["skill_snapshot"]
    )


def test_start_guide_names_every_required_pipeline_request_field() -> None:
    from pipeline.state import PipelineRequest, RequestAcceptance

    guide = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
    match = re.search(
        r"Create `<project-root>\\\.automation-core\\request\.json`.*?"
        r"Include at least (?P<fields>.*?`project_root`)\.",
        guide,
        flags=re.DOTALL,
    )
    assert match is not None, "trusted-host start guide must declare request fields"
    declared = {
        field.split(".", 1)[0]
        for field in re.findall(r"`([a-z_.]+)`", match.group("fields"))
    }

    assert declared == set(PipelineRequest.__required_keys__)

    acceptance_match = re.search(
        r"Under `acceptance`, include (?P<fields>.*?)\.", guide, flags=re.DOTALL
    )
    assert acceptance_match is not None
    acceptance_fields = set(
        re.findall(r"`([a-z_]+)`", acceptance_match.group("fields"))
    )
    assert acceptance_fields == set(RequestAcceptance.__required_keys__)


def test_launcher_hands_off_one_checkpoint_bound_p1_packet(tmp_path: Path) -> None:
    launcher = SCRIPTS_ROOT / "automation_core.ps1"
    project_root = tmp_path / "policy-registry"
    project_root.mkdir()
    request_path = project_root / "request.json"
    database = project_root / "checkpoints.sqlite"
    request = {
        "task_id": "phase-a-g0-smoke",
        "objective": "Create a deterministic policy registry CLI.",
        "project_root": str(project_root.resolve()),
        "principles": {"P-001": "Keep behavior deterministic and verifiable."},
        "requirements": {"R-001": "Provide a rules CRUD command surface."},
        "constraints": {"C-001": "Do not use network services."},
        "non_goals": {"N-001": "Do not create a web application."},
        "acceptance": {
            "criteria": [
                {"id": "AC-001", "text": "A P1 work packet is handed off."}
            ],
            "input_schema": {"type": "object"},
            "output_schema": {"type": "object"},
            "max_auto_reworks": 0,
        },
    }
    request_path.write_text(
        json.dumps(request, ensure_ascii=False), encoding="utf-8"
    )

    completed = subprocess.run(
        [
            "pwsh",
            "-NoProfile",
            "-File",
            str(launcher),
            "run",
            "--db",
            str(database),
            "--thread-id",
            "phase-a-g0-smoke",
            "--project-root",
            str(project_root),
            "--request",
            str(request_path),
            "--context-factory",
            "automation_core_context:agent_context_factory",
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["status"] == "WAITING_INPUT"
    assert payload["agent_run"]["stop_reason"] == "agent_unavailable"
    interrupts = payload["observation"]["interrupts"]
    assert len(interrupts) == 1
    packet = interrupts[0]
    assert packet["stage"] == "p1"
    assert packet["kind"] == "work"
    assert packet["agent_context"]["skill_snapshot"] == []
    assert [
        item["prompt_id"]
        for item in packet["agent_context"]["prompt_snapshot"]
    ] == ["global", "project", "role"]
    assert database.is_file()
