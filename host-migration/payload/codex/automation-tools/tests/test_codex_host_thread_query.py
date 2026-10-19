from __future__ import annotations

import importlib.util
import queue
import time
from pathlib import Path

import pytest
import yaml


CODEX_HOME = Path(r"@@CODEX_HOME:win@@")
HELPER_PATH = CODEX_HOME / "automation-tools" / "codex_host_thread_query.py"
CONTRACT_PATH = CODEX_HOME / "contracts" / "codex-host-lifecycle-contract.yaml"
SKILL_PATH = CODEX_HOME / "skills" / "codex-host-lifecycle" / "SKILL.md"


def _module():
    spec = importlib.util.spec_from_file_location("codex_host_thread_query_under_test", HELPER_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_paged_query_has_a_single_global_deadline_before_request(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _module()
    monkeypatch.setattr(module, "request", lambda *args, **kwargs: pytest.fail("request must not run after total deadline"))
    with pytest.raises(module.HostQueryError, match="total deadline"):
        module.collect_thread_pages(
            process=object(),
            events=object(),
            archived=False,
            page_limit=10,
            timeout_seconds=5.0,
            start_request_id=2,
            overall_deadline=time.monotonic() - 0.001,
        )


def test_paged_query_rechecks_global_deadline_after_each_page(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _module()
    responses = [
        {"result": {"data": [{"id": "thread-1"}], "nextCursor": "next"}},
        {"result": {"data": [{"id": "thread-2"}], "nextCursor": None}},
    ]
    calls = 0

    def fake_request(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        return responses.pop(0), []

    monotonic_values = iter((10.0, 10.0, 11.0))
    monkeypatch.setattr(module, "request", fake_request)
    monkeypatch.setattr(module.time, "monotonic", lambda: next(monotonic_values))
    with pytest.raises(module.HostQueryError, match="total deadline"):
        module.collect_thread_pages(
            process=object(),
            events=object(),
            archived=False,
            page_limit=10,
            timeout_seconds=5.0,
            start_request_id=2,
            overall_deadline=10.5,
        )
    assert calls == 1


def test_exact_thread_read_reports_complete_and_turn_readability() -> None:
    module = _module()
    result = module.validate_exact_thread_read(
        {"thread": {"id": "thread-1", "turns": []}},
        thread_id="thread-1",
        include_turns=True,
    )
    assert result["id"] == "thread-1"
    with pytest.raises(module.HostQueryError, match="different exact thread id"):
        module.validate_exact_thread_read(
            {"thread": {"id": "other", "turns": []}},
            thread_id="thread-1",
            include_turns=True,
        )
    with pytest.raises(module.HostQueryError, match="readable turns"):
        module.validate_exact_thread_read(
            {"thread": {"id": "thread-1"}},
            thread_id="thread-1",
            include_turns=True,
        )


def test_request_wait_never_exceeds_the_current_remaining_timeout() -> None:
    module = _module()

    class _In:
        def write(self, _text: str) -> None:
            return None

        def flush(self) -> None:
            return None

    class _Process:
        stdin = _In()

        @staticmethod
        def poll():
            return None

    started = time.monotonic()
    with pytest.raises(module.HostQueryError):
        module.request(
            _Process(),
            queue.Queue(),
            1,
            "thread/list",
            {},
            0.01,
        )
    assert time.monotonic() - started < 0.1


def test_cli_rejects_a_timeout_below_the_supported_total_deadline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _module()
    monkeypatch.setattr(
        module,
        "parse_args",
        lambda: type(
            "Args",
            (),
            {
                "codex_home": str(CODEX_HOME),
                "limit": 10,
                "timeout_seconds": 0.01,
                "read_thread_id": None,
                "goal_thread_id": None,
                "thread_id": None,
                "match": None,
                "archived": "active",
                "include_turns": False,
            },
        )(),
    )
    with pytest.raises(module.HostQueryError, match="at least 1.0"):
        module.main()


def test_contract_retires_only_after_terminal_result_is_presented() -> None:
    contract = yaml.safe_load(CONTRACT_PATH.read_text(encoding="utf-8"))
    retire = contract["objects"]["thread"]["retire"]
    assert retire["precondition"] == "terminal_result_presented_in_exact_review_thread"
    assert "decision_already_written_to_project_local_observation" not in str(retire)


def test_skill_uses_helper_for_exact_read_and_rejects_custom_app_tool_adapter() -> None:
    skill = SKILL_PATH.read_text(encoding="utf-8")
    assert "--read-thread-id <exact-thread-id> --include-turns" in skill
    assert "app-tool pipe/client/adapter" in skill
    assert "renderer read_thread" not in skill


def _automation_runner(thread_id: str = "runner") -> dict[str, str]:
    return {
        "id": thread_id,
        "name": "[OS] Evolution Lifecycle Tick",
        "preview": "Automation: [OS] Evolution Lifecycle Tick\nAutomation ID: os-id\nOS-REVIEW-CARD-v1|x|p|s|review",
    }


def _real_review(thread_id: str = "review") -> dict[str, str]:
    return {
        "id": thread_id,
        "name": "[OS] 审阅",
        "preview": "<codex_delegation>\nReview marker\nOS-REVIEW-CARD-v1|x|p|s|review",
    }


def test_review_marker_filters_only_automation_runner_rows() -> None:
    module = _module()
    marker = "OS-REVIEW-CARD-v1|x|p|s|review"
    for rows, kept, excluded in (
        ([_automation_runner()], [], ["runner"]),
        ([_automation_runner(), _real_review()], ["review"], ["runner"]),
        ([_automation_runner("runner-a"), _automation_runner("runner-b")], [], ["runner-a", "runner-b"]),
    ):
        matched, removed = module.filter_thread_matches(rows, marker, None)
        assert [row["id"] for row in matched] == kept
        assert [row["id"] for row in removed] == excluded


def test_non_review_marker_and_exact_id_are_unchanged() -> None:
    module = _module()
    row = _automation_runner()
    matched, excluded = module.filter_thread_matches([row], "Automation ID:", None)
    assert [item["id"] for item in matched] == ["runner"]
    assert excluded == []
    matched, excluded = module.filter_thread_matches(
        [row], "OS-REVIEW-CARD-v1|x|p|s|review", "runner"
    )
    assert [item["id"] for item in matched] == ["runner"]
    assert excluded == []
