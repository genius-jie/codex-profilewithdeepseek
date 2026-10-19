---
name: P4 复杂多体拓扑编排
type: generic
domain: planner
tier: L2
doc_status: active-ssot
status: active
birth_ceremony_id: bc-p4-038b8470
birth_ceremony_date: '2026-05-02'
related:
- @@GENERAL_ROOT:win@@\assets\references\methodology\18_AutoGen-Pipeline-Governance.md
- @@GENERAL_ROOT:win@@\assets\references\methodology\19_AutoGen-Capability-Injection-Strategy.md
- @@GENERAL_ROOT:win@@\assets\skills\P2.5_开发任务排期与拆解\SKILL.md
- @@GENERAL_ROOT:win@@\assets\skills\P2.6_交付物独立评审\SKILL.md
- @@GENERAL_ROOT:win@@\assets\skills\S10_高级后端开发\SKILL.md
- @@GENERAL_ROOT:win@@\assets\skills\S14_完成前验证\SKILL.md
- @@GENERAL_ROOT:win@@\assets\workflows\W7_知识回流分析.md
- @@GENERAL_ROOT:win@@\assets\references\architecture\p-artifact-supersede-protocol.md
- @@GENERAL_ROOT:win@@\control\registry\02-skill-catalog.md
description: |
  【触发场景】任务确实需要多 Agent 角色分工、并行隔离、独立对抗或人机协同拓扑。
  【不触发】单体原子功能、普通函数编排或单 Agent 已足够时不要用。
  【功能】形成多体拓扑蓝图、角色契约、数据流、终止/回退和验证方案，并把执行权交回 caller/Core。
extends:
- @@GENERAL_ROOT:win@@\assets\references\methodology\08_Anti-Semantic-Fading-Protocol.md
- @@GENERAL_ROOT:win@@\assets\rules\architecture.md
- @@GENERAL_ROOT:win@@\assets\references\methodology\11_P-Tier-Execution-Discipline-Protocol.md
- @@GENERAL_ROOT:win@@\assets\references\architecture\engineering-governance-protocol.md
- @@GENERAL_ROOT:win@@\assets\rules\injection\skill-aop-prelude.md
---
# P4 复杂多体拓扑编排

## CURRENT_EXECUTION_OWNERSHIP

P4 的**九态是作战方法，不是第二状态机**。它帮助设计多体协作，不拥有业务运行生命周期。

- P4 只读消费 caller 的显式 task package；新版 Core 场景只读消费**同一 thread/checkpoint packet**中的冻结目标、scope、route、allowed tools、acceptance、verification 和 evidence refs。
- P4 不得创建第二状态，不得推进 checkpoint，不得自行实例化未获批 Agent、发放工具权限、启动 Dispatcher、恢复任务或裁决完成。
- P4 产出 topology proposal、role contracts、dispatcher specification、risk/evidence plan 和 review request，并向 **caller/Core 交回执行控制权**。
- standalone 场景必须有显式 task package 与当前项目证据；缺架构基线、权限或多体必要性证据时返回 P2/P2.5 或 WAIT_HUMAN。
- W1 只建议是否需要多体方法，不初始化门禁、不选择 Agent/工具、不参与拓扑运行。

<context>

## 1. 第一性判断

多 Agent 不是默认高级方案。只有当独立上下文、并行隔离、角色对抗、人机卡点或不同权限边界能显著提高交付质量时才使用 P4；普通函数、单 Agent 或 P3 能完成时，应选择更短链路。

P4 负责“怎么搭、为何需要这样搭、如何证明不会死锁”，不负责亲自写业务 Dispatcher 或控制正在运行的 Core。

</context>

<rules>

## 2. 九态作战方法

### 2.1 输入绑定

核对 task package、架构基线、第一事实、scope、acceptance、数据契约、风险与停止条件。Core packet 的绑定只读且必须同源；P4 不生成新的线程或 checkpoint 标识。

### 2.2 拓扑博弈

比较普通函数、单 Agent、串行审查、GraphFlow、Swarm、RoundRobin、MapReduce 等候选。说明每增加一个角色/边的必要性、成本和不可替代性；没有证据的多体方案判为过度设计。

### 2.3 蓝图映射

把上游目标、约束和证据逐项映射到：

- 角色及单一职责；
- 输入/输出 schema；
- 边、条件、重试和回退；
- 人机交接点；
- write scope 和数据隔离；
- termination 与失败返回契约。

### 2.4 资产盘点

先复用现有通用角色、团队配置和项目编排骨架。新增角色只形成治理 proposal，需由 M2/S22 和 caller 审批后落地；P4 不在运行中偷偷创建永久 Agent 或 Registry。

### 2.5 能力注入设计

SystemMessage 只承载角色、职责和业务无关纪律；物理工具通过 Dispatcher/host 按已授权 tool role 注入。P4 只描述 `required_capabilities` 与最小权限，不选择或授予真实工具。

结构化输出优先使用明确 schema/Pydantic；富文本与大对象避免经 tool arguments 传输。多源数据必须保留 provenance，不把推断伪装成采集事实。

### 2.6 Dispatcher 规格

P4 输出施工规格供 S10 或 caller 实现，至少包含：

- 角色创建和依赖注入方式；
- 显式图边与条件；
- 节点级超时、外层时间预算和失败上抛；
- 循环的可达退出条件；
- human-in-the-loop pause/resume 约束；
- 日志、trace、最终结果聚合与 DLQ；
- 不同写入者的隔离策略。

P4 不亲自启动该 Dispatcher；caller/Core 决定是否实现和运行。

### 2.7 拓扑红队

审查角色重叠、幽灵边、无出口循环、termination token 误触发、超时缺失、上下文污染、并发写冲突、默认 PASS 和模型输出 schema 破损。复杂或高风险拓扑形成 P2.6 review request，P4 不自签通过。

### 2.8 执行观察与经验候选

若 caller 返回真实运行记录，P4 可分析无异常栈的协同失效：角色互相推诿、上下文丢失、重复对话、数据源串台、审计者被生产者污染。只能形成带 evidence refs 的 `pending_human` 候选，交父级 W7/M4；不得自动修改资产。

### 2.9 五维终检与交还

终检拓扑完整性、职责单一、契约可执行、权限最小、证据充分，并把 blueprint/receipt 交还 caller/Core。此终检只评价设计与证据，不推进任何运行阶段。

## 3. 多体工程不变量

- 多源数据按来源隔离并保留 provenance；
- 每条业务记录使用稳定 ID，避免并发下标错配；
- 生产输出不得混入 Mock/TODO/placeholder；
- LLM 输入按注意力预算分批；
- 长任务提供可观察进度；
- 循环必须有条件退出和整体预算；
- 裁决角色默认拒绝缺字段、空 history 或基础设施失败；
- termination token 只能由指定角色在明确位置产生；
- Agent 只做语义判断，确定性路由、schema 校验和持久化由代码/host 完成；
- P4 内部节点不得直接唤醒宏观治理流，只能把结构化失败交回外层 owner。

## 4. 输出契约

```json
{
  "method": "P4_MULTI_AGENT_TOPOLOGY_DESIGN",
  "status": "DRAFT_READY_FOR_REVIEW | NEEDS_HUMAN | REJECTED",
  "checkpoint_binding": {
    "thread_id": "echo-if-provided",
    "checkpoint_id": "echo-if-provided",
    "source_checkpoint_id": "echo-if-provided"
  },
  "multi_agent_necessity": {"required": true, "evidence_refs": []},
  "topology": {
    "mode": "GraphFlow | Swarm | RoundRobin | MapReduce | other",
    "roles": [],
    "edges": [],
    "termination": [],
    "fallbacks": []
  },
  "required_capabilities": [],
  "dispatcher_spec_ref": "...",
  "verification_plan": [],
  "review_request": {"recommended_method": "P2.6", "verdict": "PENDING"},
  "control_return": "caller/Core"
}
```

所有绑定与授权字段只回显输入；`required_capabilities` 是需求描述，不是工具授权。

</rules>

## LEGACY_CONTROL_ARCHIVE_ONLY

旧版 P4 曾把九态称为独立控制面，并依赖旧 D 的 `pipeline-state.yaml`、`gk_session`、`gatekeeper_state.json`、`pipeline_gate.py` 和 `current_pointer` 推进阶段。上述实现已退役且不可执行；相关 SOP/Dispatcher 备忘只保留在冷归档，不能作为新任务入口。
