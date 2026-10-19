---
domain: codex
tier: L0
doc_status: active-ssot
related:
  - @@CODEX_HOME:win@@\AGENTS.md
  - @@OPENCLAW_ROOT:win@@\AGENTS.md
  - @@GENERAL_ROOT:win@@\assets\skills\M1_治理预加载门禁\SKILL.md
  - @@GENERAL_ROOT:win@@\assets\references\matrix\governance-protocol.md
  - @@GENERAL_ROOT:win@@\assets\references\methodology\03_Skill-Lifecycle-Protocols.md
  - @@GENERAL_ROOT:win@@\GLOBAL-ENTRY.md
  - @@OPENCLAW_ROOT:win@@\.agents\index\02-child-knowledge-graph.md
birth_ceremony_id: bc-codexbirth-1ac5fd34
birth_ceremony_date: 2026-05-01
upgraded_date: 2026-05-01
---

# Governed Markdown Entry Gate

> **定位**: 治理 Markdown 的入口门禁，不是总宪法。出生仪式是其中一环，不是全部。
> **原则**: Prompt 不重复法典，只做薄路由。真正判断交给 M1 矩阵、OpenSpec、W9、KG 地图、硬门禁脚本。
> This is a blocking protocol. Do not report completion until all applicable steps are done, or the blocker is reported.

## Applies To

Any created or modified governance Markdown: `AGENTS.md`, `.codex/*.md`, `.agents/**/*.md`, `docs/**/*.md`, `skills/**/*.md`, `workflows/**/*.md`, `rules/**/*.md`, `index/**/*.md`, `references/**/*.md`.

---

## Step 0: Governance Routing Preflight

Before any passport or birth work, classify the asset:

1. **Object class**: Is this a Skill / Rule / SOP / Workflow / Index / Methodology / Governance Script / P-stage Artifact / other governed doc?
2. **CRUD gate**: If it is any of the above, produce `GOVERNANCE_OBJECT_CRUD_GATE` per `M1_治理预加载门禁 §5.1`. Required fields: `object_class / action / ssot_home / prompt_knowledge_layer / parent_child_scope / registry_update / blast_radius`. Missing any field → `GOVERNANCE_CRUD_GATE_UNEVALUATED`, blocked.
3. **Parent/child ownership**: Decide whether this asset belongs to parent (`.agent`), child (`.agents`), or project core-runtime (`projects/<project>`). Consult `12_Document-Asset-Governance-Protocol.md` for boundary rules. Unique SSOT home must be determined — do not create a second SSOT for a category that already has one.
4. **KG forward+reverse edges**: If this asset changes `docs/index/KG` relations, both forward and reverse knowledge-graph links must be updated (parent → child → project forward; symptom/capability-gap → SOP/Skill/Rule → parent methodology reverse). Consult `05-global-knowledge-graph.md §6`.
5. **P-stage artifact check**: If this is a P-stage deliverable (PRD, tech spec, task breakdown, evidence, manifest), it must follow OpenSpec workspace rules: `docs/specs/<task-slug>/...`, `manifest.json`, evidence anchoring, change reason, handoff contract. Passport alone is not sufficient.
6. **ssot_check / map_updated**: Confirm the document's unique home is registered and its map entry (`01-asset-register.md`, `02-skill-catalog.md`, `02-child-knowledge-graph.md §5`) reflects current state.

> If Step 0 determines this is a non-governed file (e.g. pure code, config, data), skip Steps 1–4 entirely.

---

## Step 1: Passport

Frontmatter must include `domain`, `tier`, `doc_status`, `related`, and `birth_ceremony_id`.
Use `birth_ceremony_id: bc-{slug}-{hex8}`. Add missing fields when editing an existing governed file.

---

## Step 2: Birth Registry

For every new `birth_ceremony_id`, append one JSONL line to `@@GENERAL_ROOT:win@@\records\evidence\birth-ceremony-registry.jsonl`:
`{"ceremony_id":"bc-xxx-xxxxxxxx","file_path":"full-path","ceremony_date":"YYYY-MM-DD","type":"codex-self-issued"}`

---

## Step 3: KG / Map / Catalog Registration (if applicable)

Only when Step 0 determined that graph, map, or catalog changes are needed:

1. **Knowledge graph**: Update forward and reverse edges in the current parent navigation/index (`GLOBAL-ENTRY.md` → `docs/architecture/knowledge-graph-navigation.md` / `control/registry/knowledge-category-registry.yaml`) or child `02-child-knowledge-graph.md`, according to the asset home. Ensure `related` / `extends` fields in the changed asset point to correct targets, and affected active indexes point back.
2. **Asset register / Skill catalog**: If a new Skill, Rule, SOP, or Workflow was created, register it in the applicable `control/registry/01-asset-register.md`, `control/registry/02-skill-catalog.md`, child `01-child-asset-register.md`, or child `00-domain-catalog.md`.
3. **Unique ownership registry**: If a new knowledge category SSOT was created, register it in `02-child-knowledge-graph.md §5`.
4. **P-stage manifest**: If this is a P-stage artifact, ensure `manifest.json` in the workspace is updated.

> If none of the above apply (e.g. editing an existing doc with no structural change), this step is a no-op.

---

## Step 4: Verify

Verification follows the target asset's SSOT home. The parent protocol must not
turn an OpenClaw-local verifier into a universal parent dependency.

1. **Passport / registry verification**:
   - Parent `.agent` asset: `python @@GENERAL_ROOT:win@@\control\guards\asset-admission\asset-birth-ceremony.py --verify-only --file <changed-file>`.
   - OpenClaw child `.agents` asset: `python @@OPENCLAW_ROOT:win@@\.agents\scripts\reconcile-birth-ceremony.py --dry-run`.
   - Any other child or project asset: use its declared local passport/registry verifier; do not infer an OpenClaw dependency.

2. **Home-local verification profile**:
   - Parent `.agent` asset: run its targeted regression or owner-declared Control Plane evidence after the passport check.
   - OpenClaw child `.agents` asset: choose the G-series profile below.
   - Project or external-host asset: run that project's own test/acceptance entry. A parent or child index is not its runtime gate.

   OpenClaw G-series profiles:

   | Profile | Command | Use when | Blocking rule |
   |:---|:---|:---|:---|
   | `Advisory` | `pwsh -NoProfile -File @@OPENCLAW_ROOT:win@@\.agents\orchestration\Langgraph\docs\scripts\verify-governance-hard-gate.ps1 -GateProfile Advisory` | Constitution, methodology SOP wording, prompt semantics, Skill/Workflow explanatory text, or IA-first thought injection only | WARN and demoted FAIL must be reported, but do not block completion |
   | `Structural` | `pwsh -NoProfile -File @@OPENCLAW_ROOT:win@@\.agents\orchestration\Langgraph\docs\scripts\verify-governance-hard-gate.ps1 -GateProfile Structural` | Knowledge graph, preload manifest, W1/W7/W9/M1, registry, `doc_status`, P-stage artifact landing rules, or other structure rules | FAIL blocks completion |
   | `Runtime` | `pwsh -NoProfile -File @@OPENCLAW_ROOT:win@@\.agents\orchestration\Langgraph\docs\scripts\verify-governance-hard-gate.ps1 -GateProfile Runtime` | General LangGraph/W9 control-plane, Builder/Renderer, OPA policy, and non-topology runtime changes | FAIL blocks completion |
   | `PipelineRuntime` | `pwsh -NoProfile -File @@OPENCLAW_ROOT:win@@\.agents\orchestration\Langgraph\docs\scripts\verify-governance-hard-gate.ps1 -GateProfile PipelineRuntime` | Graph topology, P-stage lifecycle/graduation, stage handoff/schema, pipeline integrity auditor, or `projects/automation-core` pipeline execution contracts | FAIL blocks completion; runs G18 |
   | `FrontendIA` | `pwsh -NoProfile -File @@OPENCLAW_ROOT:win@@\.agents\orchestration\Langgraph\docs\scripts\verify-governance-hard-gate.ps1 -GateProfile FrontendIA` | IA Contract, frontend generator, P2/P2.5 traceability, OPA, reviewer, scenario registry, or frontend product page changes | FAIL blocks completion |

   `Full` remains available for explicit full-suite verification. `Runtime` records G18 as not triggered; only `PipelineRuntime` and `Full` execute the G18 roadtests after their prerequisite pipeline contracts have changed. Existing unrelated FAIL/WARN must be named as baseline debt. These profiles are OpenClaw-local and are not a default parent or external-host verifier.

3. **KG change receipt** (only when Step 3 performed graph changes):
   Output `KNOWLEDGE_GRAPH_CHANGE_RECEIPT` per `M1 §6 Step B3`. Must include `change_type`, `changed_file`, `blast_radius` (skills/indexes/workflows/SOPs affected), `sync_completed`, `remaining_stale`.

4. **CRUD gate completeness** (only when Step 0 produced a CRUD gate):
   Verify all 7 fields of `GOVERNANCE_OBJECT_CRUD_GATE` are populated and consistent with actual changes made.
