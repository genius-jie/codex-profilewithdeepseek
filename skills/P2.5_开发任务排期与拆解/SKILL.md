---
name: P2.5 开发任务排期与拆解
type: generic
domain: planner
tier: L2
doc_status: active-ssot
status: active
birth_ceremony_id: bc-p25-d6fcebb0
birth_ceremony_date: '2026-05-02'
related:
- C:\Users\Administrator\.agent\assets\skills\P1_需求法典与标准大闸\SKILL.md
- C:\Users\Administrator\.agent\assets\skills\P2_技术架构与方案设计\SKILL.md
- C:\Users\Administrator\.agent\assets\skills\P3_单体极速流水线\SKILL.md
- C:\Users\Administrator\.agent\assets\skills\P4_复杂多体拓扑编排\SKILL.md
- C:\Users\Administrator\.agent\assets\skills\P2.6_交付物独立评审\SKILL.md
- C:\Users\Administrator\.agent\assets\skills\S7_开发任务编排\SKILL.md
- C:\Users\Administrator\.agent\assets\skills\S8_计划执行\SKILL.md
- C:\Users\Administrator\.agent\assets\references\methodology\01_Planning-and-Orchestration-Protocols.md
- C:\Users\Administrator\.agent\assets\references\methodology\18_AutoGen-Pipeline-Governance.md
- C:\Users\Administrator\.agent\control\registry\02-skill-catalog.md
- C:\Users\Administrator\.agent\assets\references\methodology\34_Frontend-Backend-Contract-Collaboration-SOP.md
description: |
  【触发场景】已有需求和架构基线，需要任务拆解、依赖排序、执行策略或开发计划。
  【不触发】方案尚未收敛，或单一小任务已经可以直接执行。
  【功能】把模块级图纸翻译为可独立交接的原子任务、依赖图、证据计划和 P3/P4 方法建议。
extends:
- C:\Users\Administrator\.agent\assets\references\methodology\08_Anti-Semantic-Fading-Protocol.md
- C:\Users\Administrator\.agent\assets\rules\architecture.md
- C:\Users\Administrator\.agent\assets\references\methodology\11_P-Tier-Execution-Discipline-Protocol.md
- C:\Users\Administrator\.agent\assets\rules\injection\skill-aop-prelude.md
---
# P2.5 开发任务排期与拆解

## CURRENT_EXECUTION_OWNERSHIP

P2.5 是General Agent OS 通用的**拆解与执行建议方法资产**，不是调度器或阶段状态机。

- P2.5 只读消费 caller 给出的 PRD、Tech Spec 和 review evidence；新版 Core 场景只读消费**同一 thread/checkpoint packet**中的冻结 task、acceptance、scope、method snapshot 与 evidence refs。
- P2.5 不得创建第二状态，不得推进 checkpoint，不得发放权限，不得改写 caller/Core 已冻结的 executor、allowed tools、write scope 或 acceptance。
- P2.5 可以基于复杂度、隔离和审查需求给出 P3/P4 `route_proposal` 与 `method_tags`；caller/Core 才能将建议写入正式 route 并启动执行。
- standalone 场景只接受显式 task package、当前项目证据和可执行验收条件；输出交回 caller，由 caller 决定谁执行、用什么工具和何时开始。
- W1 只做任务理解和方法建议，不为 P2.5 初始化门禁，也不选择具体 Agent 或工具。

<context>

## 1. 目标与粒度

P2.5 把“模块级架构”翻译为“可独立交接的最小闭环任务”。它负责依赖、并发可能性、里程碑、验收证据和方法建议；不重新做技术选型，不写业务代码，不把计划文档当运行状态。

</context>

<rules>

## 2. 六步拆解方法

### 2.1 输入完整性

核对业务目标、acceptance、Tech Spec、关键 ADR/POC、字段追溯、复用来源、风险和未决事项。缺少会改变拆解结果的事实时，返回上游补齐；P2.5 不脑补技术方案。

### 2.2 原子功能拆解

按可独立交付和验证的闭环拆分，而不是按文件行数或职位分工拆分：

- 相互独立、写入面不冲突的任务可并行；
- 有数据/接口/产物依赖的任务显式连边；
- 同一文件同一逻辑强耦合的工作合并；
- 每个任务都必须有明确输入、输出、scope、acceptance 和 evidence plan；
- 不下探到函数内部微操，具体施工由执行 Skill 决定。

### 2.3 保真与增值

P2 已交付方法组合决定时，只承接其中已采用的方法及精确版本、边界、理由和未决义务，不将候选或推导建议自动采用。把事实/契约引用放入任务既有 `inputs`，约束与范围放入 `constraints`，批准方法承接到 `method_tags`，真实链路和补齐事项落实为 `acceptance / verification / depends_on`。不增加第二个组合状态，不依赖未声明的计划顶层字段。缺口只暂停真实依赖它的任务；不在此重新做架构或方法裁决。

每个原子任务必须继承：

- P1 目标、验收、Golden Sample/反例和第一事实引用；
- P2 架构决定、复用来源、POC、数据契约和实现约束；
- 当前任务负责的 nutrient dimensions；
- 风险、停止条件、回退点和必要的人类决定。

同时把模块翻译成可执行边界、依赖和证据，不得只复制模块标题。

### 2.4 依赖图与里程碑

已明确采用 `34_Frontend-Backend-Contract-Collaboration-SOP.md` 时，将契约、前端、后端与集成责任落到现有 task，承接 `method_tags: [frontend-backend-contract]`，把第一条真实用户链路列为可验证任务。只为真正依赖该首片结论的扩大任务建立依赖，不按前端/后端职位拆成两轮大瀑布；标签不改变 executor 或工具权限。

建立无环依赖图，标记 entry、blocking edge、可并发组和 termination。里程碑是人类计划视图，不是运行状态；下游真实完成情况由 caller/Core 的事实记录决定。

### 2.5 P3/P4 方法建议

逐任务选择最小充分的执行方法：

- `P3`：单一心智可连续完成、写入面集中、上下文共享价值高、无需独立并发隔离；
- `P4`：需要多角色对抗、并行隔离、多源防污染、人机共创或复杂拓扑；
- `WAIT_HUMAN`：关键事实、授权或取舍不足。

这只是 `route_proposal`。P2.5 不直接实例化 Agent，不发放工具白名单，不启动 P3/P4。若 caller 已冻结正式 route，P2.5 只能验证一致性并原样保留，不得覆盖。

### 2.6 计划审查与交还

自审核对需求覆盖、架构约束覆盖、依赖无环、任务粒度、scope 冲突、证据可执行和停止条件。复杂或高风险计划形成 P2.6 review request；P2.5 不自填独立 verdict。

## 3. 原子任务包

```json
{
  "id": "Func-001",
  "objective": "one independently verifiable outcome",
  "source_refs": ["PRD", "Tech Spec", "POC evidence"],
  "scope": {"read": [], "write": []},
  "dependencies": [],
  "deliverables": [],
  "acceptance": [],
  "verification": {"commands": [], "evidence_refs": []},
  "constraints": [],
  "nutrient_dimensions": {"required": [], "optional_with_degradation": []},
  "route_proposal": {
    "recommended_method": "P3 | P4 | WAIT_HUMAN",
    "reason": "evidence-based reason",
    "method_tags": []
  },
  "execution_authority": {
    "executor": "preserve-caller-value",
    "allowed_tools": "preserve-caller-value"
  }
}
```

## 4. 计划输出

P2.5 返回：

- 面向人的 `implementation_plan`；
- 面向执行者的 task packages；
- 依赖图和里程碑；
- route proposals 与证据；
- review request 和未决事项。

这些产物由 caller/Core 按自己的正式契约保存和消费。P2.5 不将看板、计划或 payload 解释为运行事实。

## 5. 经验出口

拆解中反复出现的模式只能形成带证据的 `pending_human` 候选，交给General Agent OS W7/M4 人工处理；不得自动写入 Prompt、Skill、Knowledge 或启动夜间回流。

</rules>

## LEGACY_CONTROL_ARCHIVE_ONLY

旧版 P2.5 曾写入旧 D 阶段旁路、调用门禁脚本、直接跃迁 P3/P4/W9，并把计划看板当机器状态。上述控制语义已退役且不可执行；历史实现仅供冷归档审计。
