---
description: 思考强制调用工作流 - 确保 Agent 在试图进行任何代码修改、系统配置、架构分析前，极度强制自我切断执行，进行发包拆解与合规路由。
type: core-workflow
domain: root-governance
tier: L2
status: active
doc_status: active-ssot
last_verified: 2026-08-15
extends:
  - @@GENERAL_ROOT:win@@\control\orchestration\W1_前置思考.md
children:
  - assets/workflows/W7_知识回流分析.md
  - assets/workflows/W9_出口验收.md
override: []
related:
  - @@GENERAL_ROOT:win@@\control\orchestration\W1_前置思考.md
  - control/registry/05-global-knowledge-graph.md
  - control/registry/03-workflow-catalog.md
  - @@GENERAL_ROOT:win@@\assets\templates\contracts\task-manifest.contract.md
schema_ref: orchestration/workflow-schema.yaml
birth_ceremony_id: legacy-719ee6bd
birth_ceremony_date: pre-ceremony

---
# W1_前置思考（斜杠命令薄壳）

> **【薄壳声明 (Thin Shell)】**：本命令文件是 `W1_前置思考` 的斜杠命令入口薄壳，**不承载 W1 状态机正文**。W1 的完整状态机、双轨路由网、冻结锁、断点卷宗条款全部以下方本体文件为唯一事实来源（SSOT）。

> **唯一事实来源**：`@@GENERAL_ROOT:win@@\control\orchestration\W1_前置思考.md`
> 执行本命令时，Agent 必须**物理读取**上述本体文件并按其完整状态机执行，严禁仅凭本薄壳或记忆执行。

> **【断点卷宗条款】**：W1 在 ROUTING/CALIBRATION 定稿目标 Skill 后，与派工 JSON 契约同一时刻在工作区根目录写入 `.task-manifest.yaml`。schema 与恢复契约见 `@@GENERAL_ROOT:win@@\assets\templates\contracts\task-manifest.contract.md`。上下文被 `/compact` 压缩后第一动作读此文件接续，禁止重跑 W1 全流程。

> **执行入口**：按本体文件 `@@GENERAL_ROOT:win@@\control\orchestration\W1_前置思考.md` 的状态机顺序执行：
> EVIDENCE_PROBE → GLOBAL_GOVERNANCE_ENTRY_ASSERT → P0_INIT → TASK_TYPE_CLASSIFIER → P0_FAST_TRACK → MATRIX_MODELING → PLANNER → ROUTING → CALIBRATION_CHAMBER → AOP_MOUNT → PIPELINE_PHYSICAL_LOCK
