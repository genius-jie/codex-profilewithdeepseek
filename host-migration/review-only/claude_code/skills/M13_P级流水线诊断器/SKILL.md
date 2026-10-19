---
name: M13 P级流水线诊断器
type: generic
domain: meta-governance
tier: L2
doc_status: active-ssot
status: active
birth_ceremony_id: bc-m13-cbf59657
birth_ceremony_date: '2026-05-02'
extends:
  - @@GENERAL_ROOT:win@@\assets\references\methodology\12_Document-Asset-Governance-Protocol.md
  - @@GENERAL_ROOT:win@@\assets\references\methodology\11_P-Tier-Execution-Discipline-Protocol.md
related:
  - @@GENERAL_ROOT:win@@\assets\skills\P1_需求法典与标准大闸\SKILL.md
  - @@GENERAL_ROOT:win@@\assets\skills\P2_技术架构与方案设计\SKILL.md
  - @@GENERAL_ROOT:win@@\assets\skills\P2.5_开发任务排期与拆解\SKILL.md
  - @@GENERAL_ROOT:win@@\assets\skills\P3_单体极速流水线\SKILL.md
  - @@GENERAL_ROOT:win@@\assets\skills\P4_复杂多体拓扑编排\SKILL.md
  - @@GENERAL_ROOT:win@@\assets\skills\P2.6_交付物独立评审\SKILL.md
  - @@OPENCLAW_ROOT:win@@\.agents\orchestration\Langgraph\docs\langgraph_sop.md
  - @@OPENCLAW_ROOT:win@@\.agents\orchestration\Langgraph\docs\references\methodology\26_P-Pipeline-Governance-SOP.md
  - @@CORE_ROOT:win@@\AGENTS.md
description: |
  【触发场景】诊断 P1/P2/P2.5/P3/P4/P2.6 的职责、交接、证据和项目执行边界。
  【不触发】普通业务开发，或只是调用已明确的单一 Skill。
  【功能】识别方法资产与项目运行时是否错位，给出最小整改和物理验收。
---
# M13 P级流水线诊断器

## Mission

M13 判断一条 P 级交付链是否把“通用方法、项目执行、独立评审、完成证据”放在正确责任人手里。它不是脚手架生成器，不要求每个 P 阶段拥有固定节点，也不把父级方法文档投影成第二状态机。

## Current ownership

| 责任 | Owner |
|:---|:---|
| 任务理解、风险分类、方法建议 | 父级 W1 |
| 需求、架构、拆解、执行方法 | 父级 P1/P2/P2.5/P3/P4 |
| 项目运行、checkpoint、恢复和业务完成 | 当前项目正式运行时；E 分支为 Automation Core |
| 独立评审 | caller 指定 reviewer；E 分支为 checkpoint-bound P2.6 |
| 完成前验证 | S14 / W9 与项目 acceptance |
| 经验加工与采纳 | 人工显式 W7/M4；V4 只提供候选信号 |

## When to use

- 项目出现两套路由、两份状态或两种完成真相；
- P 级方法开始要求项目创建 sidecar、Registry、Ledger 或固定图节点；
- 上游产物、review packet、checkpoint 和测试证据无法绑定；
- W1、TaskRouter、P2.6、W9、V4/W7 的职责边界发生膨胀；
- 需要比较旧实现意图与新版运行载体，而不是复制旧代码。

## Preload

只读最小集合：Governance Protocol、当前父级 P Skills、当前项目公开运行契约，以及项目的实际 acceptance/证据。OpenClaw 场景再读 child governance map、`langgraph_sop.md` 和 26 号 SOP。

## Diagnostic dimensions

1. **Objective**：目标、非目标和完成边界是否明确。
2. **Facts**：事实、推断和未知是否分开；是否来自当前物理证据。
3. **Method**：父级方法是否按任务类型/复杂度/风险选择，而非固定串行全部 Skill。
4. **Execution**：项目是否只有一个执行控制面和一个运行真相。
5. **Handoff**：消费者能否从调用方既有契约获得目标、边界、产物和 blocker。
6. **Review**：独立评审是否读取冻结产物与新鲜证据；E 分支是否绑定同一 checkpoint。
7. **Evidence**：完成声明是否由当前 diff、文件、测试、acceptance 和项目结果覆盖。
8. **Stop**：不可逆、高风险、权限缺失或多轮不收敛时是否真实停下。

## E Automation Core invariants

诊断 E 分支时只核对现有事实：25 个节点、6 条显式边、`request/results/feedback` 三通道、SQLite `checkpoints/writes` 两表、`p6_final` 业务完成。不得建议为方法、W7、P2.6、W9 或任务画像增加节点、状态键、表、后台 scheduler 或第二 CLI。

P2.5 的 `tasks[].executor` 与 route 仍是执行形态权威；可选 `method_tags` 只决定组合根注入哪份父级 Skill 快照，不改变 authority/tools/checkpoint/review schema。

## Severity

- **P0**：存在第二执行控制面；旧实现仍是活动 fallback；无 acceptance/证据也能完成；评审可伪造或跨 checkpoint 复用。
- **P1**：方法或交接信息不足，需要人工补读；职责已模糊但尚未改变运行状态。
- **P2**：命名、索引或说明不清，不影响当前执行和证据。

## Required output

```yaml
P_TIER_PIPELINE_DIAGNOSIS:
  stage: p1|p2|p25|p3|p4|p26|cross-stage
  mode: audit|compare|migration
  verdict: READY|NEEDS_FIX|BLOCKED
  objective_and_acceptance: PASS|FAIL|UNKNOWN
  execution_owner: <current owner>
  state_authority: <current checkpoint/status source>
  method_boundary: PASS|FAIL
  review_binding: PASS|FAIL|NOT_APPLICABLE
  evidence_freshness: PASS|FAIL|UNKNOWN
  p0_findings: []
  p1_findings: []
  p2_findings: []
  smallest_remediation: <one coherent change>
  verification: <physical command or evidence>
```

## Non-negotiables

- 不把父级 Skill 变成项目运行 API。
- 不要求所有任务机械串行走 P1→P4；由任务条件与 caller 决定方法组合。
- 不用治理文档冒充业务证据。
- 不从旧 D 读取当前状态或调用旧 CLI。
- 不把 P2.6/W9/W7/V4 放入 Core 图。
- 不因缺少历史 sidecar 而拒绝合法的当前 checkpoint packet。

## LEGACY_CONTROL_ARCHIVE_ONLY

旧“每阶段十节点骨架”、`p26_review_pX` 图节点、artifact workspace 强制布局、OPA/Instructor/OpenSpec 五件套全覆盖、`pipeline-state.yaml`、current pointer 与旧毕业 receipt 只作历史案例。它们不再是 M13 的默认整改模板。
