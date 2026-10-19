---
name: self-distill-workflows
description: "Use when the user asks Codex to review recent work, memories, conversations, task history, repeated manual actions, or existing skills/automations to find reusable workflows and turn them into the smallest useful Codex capability: Skill, custom subagent proposal, automation, or skip."
domain: codex
tier: L1
doc_status: active-ssot
related:
  - @@CODEX_HOME:win@@\AGENTS.md
  - @@CODEX_HOME:win@@\birth-ceremony-protocol.md
  - @@GENERAL_ROOT:win@@\skills\M1_治理预加载门禁\SKILL.md
  - @@GENERAL_ROOT:win@@\skills\M2_技能生产与归档\SKILL.md
  - @@GENERAL_ROOT:win@@\skills\S22_提示词工程治理\SKILL.md
  - @@GENERAL_ROOT:win@@\references\methodology\31_Self-Distillation-Workflow-Packaging-Protocol.md
birth_ceremony_id: bc-selfdistillworkflows-7d3f4a91
birth_ceremony_date: 2026-05-26
source_trace:
  article_url: https://mp.weixin.qq.com/s/88rTMq9zb5xRkbEEn78I-A
  extraction_policy: summarize_methodology_only_no_article_text_copy
---

# Self-Distill Workflows

Use this skill to turn repeated manual work into reusable Codex capabilities. The job is not to make more files. The job is to find patterns that are stable enough to deserve tooling, then choose the smallest form that pays for itself.

## Inputs To Check

Read only the sources that are available in the current environment and relevant to the request:

- Recent conversation context and task summaries.
- Codex memories and memory summaries.
- Existing skills under `@@CODEX_HOME:win@@\skills` and, when relevant, shared skills under `@@GENERAL_ROOT:win@@\skills`.
- Existing automations if the user asks for scheduled or recurring work.
- External activity logs such as Chronicle only when the user explicitly grants access or the environment exposes them; use them for discovery, then confirm important details from the original source.

Do not scrape private or external systems just because this skill is active. Ask or use an installed connector only when the user has asked for that source.

## Candidate Test

A repeated workflow is a real candidate only when all of these are true:

- It happened at least twice, or it is clearly likely to recur and the cost of repeating it is high.
- It has stable inputs, a repeatable process, and a concrete output.
- Packaging it would improve speed, quality, reliability, or reviewability.
- No existing skill, script, automation, or documented process already covers it.
- The abstraction is cheaper to maintain than doing the work manually next time.

If the workflow depends on unstable inputs or vague judgment, keep it as a note or a candidate. Do not create a skill from a two-off accident.

## Classification

Choose the smallest useful form:

- `Skill`: repeatable workflow with human-triggered execution and durable procedural knowledge.
- `Custom subagent proposal`: bounded role or investigation lane that benefits from a specialized reviewer or worker. Propose it unless a subagent tool is available and the user asked you to create one.
- `Automation`: scheduled, recurring, monitoring, reminder, or follow-up work. Use the Codex automation tool when available.
- `Script`: deterministic transformation or fragile repeated command sequence that should not be retyped.
- `Skip`: one-off, unclear, already covered, too expensive to maintain, or not enough evidence.

## Workflow

1. Define the review window. Default to the last 30 days when the user does not specify one.
2. Inventory existing capabilities before proposing anything new.
3. Gather candidate repeated workflows from the allowed sources.
4. Score each candidate on recurrence, stability, value, coverage gap, and maintenance cost.
5. Output a candidate table first. Include the chosen form and confidence.
6. Create only high-confidence, low-blast-radius items that are inside the current authorization.
7. Report what was created, what was skipped, what needs more evidence, and where each artifact lives.

## Creation Rules

- Before creating or modifying governed Markdown, follow `@@CODEX_HOME:win@@\birth-ceremony-protocol.md`.
- For Skill / Rule / SOP / Workflow changes, run the local governance CRUD gate from M1/M2 and preserve birth ceremony metadata.
- Prefer updating an existing skill over creating a near-duplicate.
- Keep new `SKILL.md` files short. Move long references, examples, or scripts into bundled folders only when they are actually needed.
- Never copy proprietary article text, chat logs, or private records into the skill. Store only distilled procedures and source links when useful.

## Output Shape

Use this compact structure:

```text
Window: <date range or source range>
Sources checked: <sources actually inspected>

Candidates:
| Workflow | Evidence | Form | Confidence | Decision |

Created:
- <artifact path or automation id>

Skipped:
- <workflow> because <reason>

Needs more evidence:
- <workflow> because <missing proof>
```

When nothing should be created, say so directly and give the strongest skipped candidate with the reason.
