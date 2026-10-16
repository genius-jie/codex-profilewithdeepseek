---
name: P1 需求法典与标准大闸
type: generic
domain: planner
tier: L2
doc_status: active-ssot
status: active
birth_ceremony_id: bc-p1-ddca82fc
birth_ceremony_date: '2026-05-02'
related:
- C:\Users\Administrator\.agent\assets\skills\P2_技术架构与方案设计\SKILL.md
- C:\Users\Administrator\.agent\assets\skills\P2.6_交付物独立评审\SKILL.md
- C:\Users\Administrator\.agent\assets\references\methodology\02_Exploration-and-Risk-Protocols.md
- C:\Users\Administrator\.agent\assets\references\methodology\07_Physical-Decomposition-Engine.md
- C:\Users\Administrator\.agent\assets\references\methodology\08_Anti-Semantic-Fading-Protocol.md
- C:\Users\Administrator\.agent\assets\references\methodology\16_P1-vs-P2-Governance-Boundary.md
- C:\Users\Administrator\.agent\assets\references\methodology\17_First-Fact-Governance-Protocol.md
- C:\Users\Administrator\.agent\assets\skills\P1_需求法典与标准大闸\resources\visual-companion.md
- C:\Users\Administrator\.agent\control\contracts\artifact-communication-contract.yaml
- C:\Users\Administrator\.agent\assets\workflows\W37_Human-facing Artifact Composition Workflow.md
- C:\Users\Administrator\.agent\control\registry\02-skill-catalog.md
description: |
  【触发场景】用户提出新需求、需要澄清目标、冻结验收标准或编写 PRD。
  【不触发】已有可核验需求基线、只需实现或测试时不要重启 P1。
  【功能】把模糊意图收敛为带第一事实、边界、验收标准和交接证据的 PRD。
extends:
- C:\Users\Administrator\.agent\assets\references\methodology\08_Anti-Semantic-Fading-Protocol.md
- C:\Users\Administrator\.agent\assets\rules\architecture.md
- C:\Users\Administrator\.agent\assets\references\methodology\11_P-Tier-Execution-Discipline-Protocol.md
- C:\Users\Administrator\.agent\assets\rules\injection\skill-aop-prelude.md
---
# P1 需求法典与标准大闸

## CURRENT_EXECUTION_OWNERSHIP

P1 是General Agent OS 通用的**需求与验收方法资产**，不是任务运行引擎。

- P1 只读消费 caller 给出的需求材料；若由新版 Core 调用，只读消费**同一 thread/checkpoint packet**中的 request、acceptance、已确认事实和证据引用。
- P1 不得扩大 caller 已授权的范围，不得选择 Agent 或工具，不得改变执行权限，不得创建第二状态，不得推进 checkpoint。
- P1 产出的 PRD、open questions、acceptance 与 handoff proposal 全部交回 caller；在 Core 场景由 Core 绑定原 thread/checkpoint 保存和推进，在 standalone 场景由当前调用者决定落盘与后续路由。
- W1 只能提供任务理解、风险分类和方法建议；P1 不要求 W1 初始化门禁，也不把 W1 当作 Agent/工具调度器。
- P1 可以建议下一步采用 P2 或 P2.6，但该建议不等于执行授权或阶段跃迁。

<context>

## 1. 目标与边界

P1 把用户口述、附件、现有事实和业务约束翻译成可验证的需求法典。它负责回答：为什么做、给谁用、做到什么程度、哪些不做、什么证据算完成。

P1 不做技术选型、不画实现拓扑、不写业务代码、不替独立评审者签发 PASS。需求缺关键事实时，应输出精确的 open questions；涉及不可逆取舍时，把决定交回用户或 caller。

</context>

<rules>

## 2. 六步需求收敛方法

### 2.1 目标与读者

先确认核心痛点、最终读者、读者拿到结果后要做的决定、最小完成边界和明确的 Out of Scope。已有上下文可以形成待确认推断，但必须标记为推断，不能伪装成事实。

### 2.1.1 Artifact Communication Contract 接入（条件性）

当 PRD 由 Human 阅读、评审或跨角色协作时，P1 在写入正式 Artifact 前读取并应用：

`C:\Users\Administrator\.agent\control\contracts\artifact-communication-contract.yaml`
Contract ID：`artifact-communication-contract.v1`

该 Contract 统一人类交付物的沟通语义；P1 只把它投影到 PRD，不在本 Skill 复制或另建一套表达规则。

当 caller 明确选择 `C:\Users\Administrator\.agent\assets\workflows\W37_Human-facing Artifact Composition Workflow.md` 时，W37 负责公开组合 Contract、Primary Producer、可选 S18、明确采用时的 M11 与已选验证能力。P1 在其中仅作为 PRD 的 Primary Producer；P1 不在 Skill 内直接调用 S18、M11 或验证能力，也不决定 Workflow 的顺序。未选择 W37 时，P1 继续按自身契约直接产出 PRD，不暗示任何隐藏组合。

PRD 的 Contract 投影必须让读者直接找到以下信息：

```yaml
artifact_communication:
  contract: artifact-communication-contract.v1
  artifact_type: prd
  audience: [product, delivery, tester] # 按当前任务增删
  intent:
    objective: "要解决的业务问题和预期结果"
    decision_required: "当前需要 Human 确认的需求取舍；没有则明确为 none"
  human_first_sequence: [why, what, boundary, how, evidence]
  layer_separation: [human, engineering, machine]
  human_summary: "按 Contract 的 why → what → boundary → how → evidence 顺序说明；how 在 PRD 中只描述用户流程、交付与验收，不替代 P2 技术选型"
  decision_points: "HITL、open questions、已确认决定及未决影响的位置"
  boundaries:
    included: "in scope 的能力和验收范围"
    excluded: "out of scope、约束与回退条件"
  evidence_refs: "first_fact_refs 和需求 traceability"
  technical_detail_placement: "数据/字段/状态契约置于深层章节、附录或独立 schema"
```

内部 D1、状态、对象或字段名称首次出现时先给出用户语言解释。JSON Schema、API Contract、Runtime State 与机器回执保留各自精确格式，不纳入此 Human-facing PRD 投影。

### 2.2 第一事实与未知

- Schema、字段、对象状态和业务流程必须锚定真实样例、用户原话、接口回包、现有文件或可复现探针。
- 将 `observed facts / assumptions / unknowns / human decisions` 分开记录。
- 报告、分析、调研类需求必须同时取得正面样本、反面样本和交付价值锚；拿不到时输出信息缺口，不凭行业印象补造。

### 2.3 验收与反例

为每个核心目标定义可证伪的验收标准：

- 使用 Given-When-Then 或等价黑盒表达；
- 覆盖正常、空值、污染、时序、外部依赖失败、重复触发等边界；
- 内容型交付物要列出具体的空话黑名单、证据展示粒度和最低样本门槛；
- 说明性能、恢复、数据保护和人工验收边界；
- 需要大模型生成的环节同时给出高质量 Golden Sample 与禁止样例。

### 2.4 需求结构化

PRD 至少包含：

1. 业务目标、读者与使用场景；
2. 范围与不做事项；
3. 真实样例和第一事实来源；
4. 功能、对象、状态与数据契约；
5. 验收标准、边界、反例和质量门槛；
6. 风险、未知、HITL 决策点和回退条件；
7. 每条需求到原始证据的 traceability。

复杂文档按自然章节分片完成，每片写盘后回读并核对证据来源；分片是注意力管理方法，不是新的运行状态机。

### 2.5 Product PRD Handoff 条件增强

产品、功能、UI/研发/QA 交接场景可调用 P1 内部 Product PRD Handoff capability，补齐 Visual PRD、对象状态、页面状态、acceptance、decision log 与 open questions。活动校验器为：

`C:\Users\Administrator\.agent\assets\skills\P1_需求法典与标准大闸\scripts\validate_product_prd_handoff.py`

该能力只产生 PRD 证据，不形成独立阶段，也不替代 P1 澄清或 P2.6 独立评审。

### 2.6 独立评审交接

P1 完成蓝队自审后输出 `review_request`，由 caller 决定是否调用 P2.6。P1 不得自行填写独立评审结论；收到真实 verdict 后，只能原样引用 verdict 与证据位置。

## 3. 交接契约

```json
{
  "method": "P1_REQUIREMENT_AND_ACCEPTANCE",
  "status": "DRAFT_READY_FOR_REVIEW",
  "checkpoint_binding": {
    "thread_id": "echo-if-provided",
    "checkpoint_id": "echo-if-provided",
    "source_checkpoint_id": "echo-if-provided"
  },
  "artifacts": {
    "prd_ref": "absolute-or-caller-relative-ref",
    "acceptance_ref": "section-or-artifact-ref",
    "first_fact_refs": [],
    "open_questions": [],
    "artifact_communication_ref": {
      "contract": "artifact-communication-contract.v1",
      "artifact_type": "prd",
      "audience": [],
      "intent": {"objective": "...", "decision_required": "...|none"},
      "human_summary_ref": "section-or-artifact-ref",
      "decision_points_ref": "section-or-artifact-ref",
      "boundaries_ref": "section-or-artifact-ref",
      "evidence_refs": [],
      "technical_details_ref": "deep-section-or-appendix-ref"
    }
  },
  "review_request": {
    "recommended_method": "P2.6",
    "verdict": "PENDING"
  },
  "handoff_proposal": {
    "recommended_next_method": "P2",
    "reason": "requirements-and-acceptance-are-ready"
  }
}
```

规则：checkpoint binding 只回显 caller 提供的绑定；P1 不生成新 ID，不修改绑定，不把 `recommended_next_method` 当作已执行路由。

</rules>

## LEGACY_CONTROL_ARCHIVE_ONLY

旧版 P1 曾要求创建运行旁路文件、写阶段指针、自动封版并直接跃迁下游。上述做法属于旧 D 控制语义，现已退役且不可执行；历史材料只可在冷归档中审计，不得恢复为General Agent OS Skill 的运行前置。
