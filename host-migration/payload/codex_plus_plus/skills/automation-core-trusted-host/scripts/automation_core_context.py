from __future__ import annotations

from pathlib import Path
from typing import Any

from pipeline import (
    AgentProfileRule,
    AgentProfileSource,
    KnowledgeRule,
    KnowledgeSource,
    MethodSkillRule,
    MethodSkillSource,
    PromptRule,
    PromptSource,
    build_agent_context_provider,
)


SKILL_ROOT = Path(__file__).resolve().parent.parent
REFERENCES = SKILL_ROOT / "references"
SHARED_SKILLS = Path(r"@@GENERAL_ROOT:win@@\assets\skills")

_STAGES = ("p1", "p2", "p25", "p3", "p4", "p5", "p6")
_PROMPT_IDS = ("global", "project", "role")
_PROFILE_ID = "codexplusplus-host"
_KNOWLEDGE_ID = "runtime-boundary"


def _prompt_rules() -> tuple[PromptRule, ...]:
    return tuple(
        PromptRule(
            _PROMPT_IDS,
            stage=stage,
            kind=kind,
            reason="Codex++ trusted-host three-layer prompt",
        )
        for stage in _STAGES
        for kind in ("work", "review")
    ) + (
        PromptRule(
            _PROMPT_IDS,
            stage="p4",
            kind="lane",
            phase="execution",
            reason="Codex++ trusted-host P4 lane prompt",
        ),
    )


def _knowledge_rules() -> tuple[KnowledgeRule, ...]:
    return tuple(
        KnowledgeRule(
            (_KNOWLEDGE_ID,),
            stage=stage,
            kind=kind,
            reason="Automation Core runtime boundary reference",
        )
        for stage in _STAGES
        for kind in ("work", "review")
    ) + (
        KnowledgeRule(
            (_KNOWLEDGE_ID,),
            stage="p4",
            kind="lane",
            phase="execution",
            reason="Automation Core P4 lane boundary reference",
        ),
    )


def _profile_rules() -> tuple[AgentProfileRule, ...]:
    return tuple(
        AgentProfileRule(
            _PROFILE_ID,
            stage=stage,
            kind=kind,
            reason="Current Codex++ task is the trusted host",
        )
        for stage in _STAGES
        for kind in ("work", "review")
    ) + (
        AgentProfileRule(
            _PROFILE_ID,
            stage="p4",
            kind="lane",
            phase="execution",
            reason="Current Codex++ task executes one isolated P4 lane",
        ),
    )


def agent_context_factory() -> Any:
    """Return the stable profile-local provider used by every write command."""

    return build_agent_context_provider(
        provider_id="codexplusplus-automation-core-trusted-host",
        allowed_skill_roots=(SHARED_SKILLS,),
        skill_sources=(
            MethodSkillSource(
                "S11",
                SHARED_SKILLS / "S11_测试驱动开发" / "SKILL.md",
                resources=(
                    SHARED_SKILLS
                    / "S11_测试驱动开发"
                    / "references"
                    / "test-data-protocol.md",
                ),
            ),
            MethodSkillSource(
                "S12", SHARED_SKILLS / "S12_系统化调试" / "SKILL.md"
            ),
            MethodSkillSource(
                "S13", SHARED_SKILLS / "S13_代码审查" / "SKILL.md"
            ),
            MethodSkillSource(
                "S14", SHARED_SKILLS / "S14_完成前验证" / "SKILL.md"
            ),
        ),
        skill_rules=(
            MethodSkillRule(("S11",), stage="p3", kind="work"),
            MethodSkillRule(
                ("S12",),
                stage="p3",
                kind="work",
                method_tag="systematic-debugging",
            ),
            MethodSkillRule(("S13", "S14"), stage="p3", kind="review"),
            MethodSkillRule(
                ("S11",),
                stage="p4",
                kind="lane",
                phase="execution",
                lane_role="implementation",
            ),
            MethodSkillRule(
                ("S13", "S14"),
                stage="p4",
                kind="lane",
                phase="execution",
                lane_role="verification",
            ),
            MethodSkillRule(
                ("S13", "S14"),
                stage="p4",
                kind="review",
                phase="execution",
            ),
        ),
        allowed_prompt_roots=(REFERENCES,),
        prompt_sources=(
            PromptSource("global", REFERENCES / "global-prompt.txt"),
            PromptSource("project", REFERENCES / "project-prompt.txt"),
            PromptSource("role", REFERENCES / "role-prompt.txt"),
        ),
        prompt_rules=_prompt_rules(),
        allowed_knowledge_roots=(REFERENCES,),
        knowledge_sources=(
            KnowledgeSource(
                _KNOWLEDGE_ID, REFERENCES / "runtime-knowledge.txt"
            ),
        ),
        knowledge_rules=_knowledge_rules(),
        allowed_profile_roots=(REFERENCES,),
        profile_sources=(
            AgentProfileSource(
                _PROFILE_ID, REFERENCES / "trusted-host-profile.txt"
            ),
        ),
        profile_rules=_profile_rules(),
    )
