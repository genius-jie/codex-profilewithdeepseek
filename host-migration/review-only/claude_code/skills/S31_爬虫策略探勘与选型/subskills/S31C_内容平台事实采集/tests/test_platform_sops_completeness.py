import re
from pathlib import Path

import yaml


S31_ROOT = Path(__file__).resolve().parents[3]
S31C_ROOT = S31_ROOT / "subskills" / "S31C_内容平台事实采集"
BASELINE = (
    S31_ROOT
    / "subskills"
    / "S31A_数据源探针与路线选型"
    / "references"
    / "platform_crawl_maturity_baseline.yaml"
)
SOP_DIR = S31C_ROOT / "references" / "platform_sops"
SKILL = S31C_ROOT / "SKILL.md"
SHARD_RUNNER_REF = "subskills/S31C_内容平台事实采集/scripts/platform_shard_runner.py"

REQUIRED_SECTIONS = [
    "平台概况",
    "认证与会话",
    "数据获取路线",
    "反爬与节奏控制",
    "数据质量校验",
    "故障恢复",
    "已知坑和最佳实践",
    "命令示例",
]


def load_baseline() -> dict:
    return yaml.safe_load(BASELINE.read_text(encoding="utf-8"))


def read_sop(platform: str, row: dict) -> tuple[Path, str]:
    sop_ref = row.get("sop_ref")
    assert sop_ref, platform
    assert not Path(sop_ref).is_absolute(), platform
    path = S31_ROOT / sop_ref
    assert path.exists(), platform
    assert path.parent == SOP_DIR, platform
    assert path.name == f"{platform}_crawl_sop.md", platform
    return path, path.read_text(encoding="utf-8")


def frontmatter(text: str) -> dict:
    match = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    assert match, "missing yaml frontmatter"
    return yaml.safe_load(match.group(1))


def test_every_baseline_platform_has_reachable_sop_ref():
    baseline = load_baseline()
    platforms = baseline["platforms"]

    assert len(platforms) == len(list(SOP_DIR.glob("*_crawl_sop.md")))
    assert SOP_DIR.exists()

    for platform, row in platforms.items():
        read_sop(platform, row)


def test_platform_sops_have_passport_and_required_sections():
    baseline = load_baseline()

    for platform, row in baseline["platforms"].items():
        path, text = read_sop(platform, row)
        metadata = frontmatter(text)

        assert metadata["domain"] == "crawler", platform
        assert metadata["tier"] == "L3", platform
        assert metadata["doc_status"] == "active-reference", platform
        assert metadata["birth_ceremony_id"].startswith(f"bc-s31c-{platform.replace('_', '-')}-sop-"), platform
        assert str(metadata["birth_ceremony_date"]) in {"2026-06-10", "2026-06-11", "2026-06-12"}, platform
        assert str(BASELINE) in metadata["related"], platform

        for section in REQUIRED_SECTIONS:
            assert f"## {section}" in text, f"{platform}: {section}"

        assert "crawler_fact_pack.v1" in text, platform
        assert "zero_output_diagnosis" in text, platform
        assert "competitor_review_adapters.py" in text, platform
        assert "OpenCLI + shard 标杆路线" in text, platform
        assert "OpenCLI provider：" in text, platform
        assert "platform_shard_runner.py" in text, platform
        assert "platform_shard_run_receipt.v1" in text, platform
        assert " run --output-dir " in text, platform
        assert "--resume" in text, platform
        assert "phase=list" in text, platform
        assert "phase=details" in text, platform
        assert "phase=comments" in text, platform
        assert path.name in text, platform


def test_every_platform_targets_opencli_shard_standard():
    baseline = load_baseline()

    for platform, row in baseline["platforms"].items():
        assert row.get("execution_standard") == "opencli_shard", platform
        assert row.get("shard_runner_ref") == SHARD_RUNNER_REF, platform
        assert row.get("opencli_provider") in {"site_adapter", "browser_bridge"}, platform
        assert (S31_ROOT / row["shard_runner_ref"]).exists(), platform


def test_session_a_platforms_are_registered_as_m4():
    baseline = load_baseline()
    expected_capability = {
        "taobao_tmall": "controlled_input_adapter",
        "xianyu": "controlled_input_adapter",
    }

    for platform, capability in expected_capability.items():
        row = baseline["platforms"][platform]
        assert row["maturity_tier"] == "M4", platform
        assert row["label"] == "Stable Reference Route", platform
        assert row["adapter_capability"] == capability, platform
        assert row["execution_standard"] == "opencli_shard", platform
        assert row["opencli_provider"] == "site_adapter", platform


def test_closed_data_plane_platforms_are_registered_as_m5():
    baseline = load_baseline()
    expected_provider = {
        "amazon": "site_adapter",
        "appstore": "browser_bridge",
        "bilibili": "site_adapter",
        "jd": "site_adapter",
        "public_article": "site_adapter",
        "reddit": "site_adapter",
        "rentio": "site_adapter",
        "tieba": "site_adapter",
        "trustpilot": "browser_bridge",
        "yahoo_chiebukuro": "browser_bridge",
    }

    for platform, provider in expected_provider.items():
        row = baseline["platforms"][platform]
        assert row["maturity_tier"] == "M5", platform
        assert row["label"] == "Sealed Fact Source", platform
        assert row["execution_standard"] == "opencli_shard", platform
        assert row["opencli_provider"] == provider, platform


def test_session_c_platforms_are_registered_as_m5():
    baseline = load_baseline()
    row = baseline["platforms"]["reddit"]

    assert row["maturity_tier"] == "M5"
    assert row["label"] == "Sealed Fact Source"
    assert row["adapter_capability"] == "public_live_adapter"
    assert row["execution_standard"] == "opencli_shard"
    assert row["opencli_provider"] == "site_adapter"


def test_s31c_skill_registers_platform_sop_directory():
    text = SKILL.read_text(encoding="utf-8")

    assert "references\\platform_sops" in text
    assert "21 个平台 SOP" in text
    assert "platform_shard_runner.py" in text
