---
name: P3 单体极速流水线
type: generic
domain: planner
tier: L2
doc_status: active-ssot
status: active
birth_ceremony_id: bc-p3-0e9d4e2e
birth_ceremony_date: '2026-05-02'
related:
- C:\Users\Administrator\.agent\assets\skills\P1_需求法典与标准大闸\SKILL.md
- C:\Users\Administrator\.agent\assets\skills\P2_技术架构与方案设计\SKILL.md
- C:\Users\Administrator\.agent\assets\skills\P2.5_开发任务排期与拆解\SKILL.md
- C:\Users\Administrator\.agent\assets\skills\P2.6_交付物独立评审\SKILL.md
- C:\Users\Administrator\.agent\assets\skills\S11_测试驱动开发\SKILL.md
- C:\Users\Administrator\.agent\assets\skills\S12_系统化调试\SKILL.md
- C:\Users\Administrator\.agent\assets\skills\S14_完成前验证\SKILL.md
- C:\Users\Administrator\.agent\assets\workflows\W7_知识回流分析.md
- C:\Users\Administrator\.agent\control\registry\02-skill-catalog.md
description: |
  【触发场景】caller/Core 已给出单一原子任务、执行范围、允许工具和验收标准，需要连续单体执行方法。
  【不触发】需要并行隔离、多角色对抗、多模块重新拆解，或缺少显式任务包时不要用。
  【功能】在既有授权内完成单体深潜、TDD/调试、证据核收和结构化回执；不取得运行控制权。
extends:
- C:\Users\Administrator\.agent\assets\references\methodology\08_Anti-Semantic-Fading-Protocol.md
- C:\Users\Administrator\.agent\assets\rules\architecture.md
- C:\Users\Administrator\.agent\assets\rules\injection\skill-aop-prelude.md
---
# P3 单体极速流水线

## CURRENT_EXECUTION_OWNERSHIP

P3 是General Agent OS 通用的单体执行方法，不是第二执行引擎。

- P3 只读消费 caller/Core 已冻结的 objective、scope、executor、allowed tools、acceptance、verification 和 evidence refs。
- P3 不得选择新的 Agent 或工具，不得扩大写入面，不得创建第二状态，不得推进 checkpoint，不得替 caller/Core 决定重试、恢复或完成。
- P3 的执行结果只形成 artifact/evidence/receipt，交回原 caller/Core；是否保存、独立评审、resume 或进入下一阶段由原执行控制面决定。
- W1 只做任务理解、风险分类和方法建议，不参与 P3 派工，也不为 P3 初始化任何运行门禁。

<context>

## 1. 输入边界

P3 只承接一个可独立验证的原子任务。输入必须给出：目标、当前事实、读写 scope、允许工具、验收、验证命令/证据标准、停止条件和返回契约。任务超过单原子闭环时，返回 caller 请求 P2.5/P4，不在 P3 内扩建拓扑。

</context>

<rules>

## 2. 路由优先级

### 2.1 E/Core checkpoint-bound 当前分支（最高优先级）

当调用来自 `E:\personal-ai-suite\automation-core` 时，P3 只读消费新版 Automation Core 的 checkpoint-bound packet：

- `thread_id`、`checkpoint_id` 与 `source_checkpoint_id` 必须指向同一当前绑定；
- task、allowed tools、write scope、acceptance/verification 与 `stage_review_basis` 以 packet 为准；
- E/Core checkpoint-bound 分支不要求 `gatekeeper_audit_trail`，也不要求任何旧 D 蓝队报告或旁路状态；
- P3 不调用 Core 内部模块，不直接写 Core 数据库，只通过 caller 给出的公共执行/回执边界返回结果；
- P3 不 resume、不提交人工 verdict、不推进 checkpoint。

### 2.2 standalone 分支

非 Core 场景必须同时具备**显式 task package**与**当前项目证据**。task package 至少含 objective、scope、allowed tools、acceptance、verification 和 return contract。缺一项即返回缺口，不从聊天摘要或历史项目状态反推权限。

## 3. 六步单体执行方法

### 3.1 物理读验

读取任务包、目标文件和证据引用，区分 observed facts、unknowns 与 assumptions。确认当前工作确实是一个原子闭环，并核对所有目标文件在 scope 内。

### 3.2 微型执行蓝图

将任务翻译成可直接施工的短蓝图：

1. WHY：目标和来源；
2. WHAT：交付物和成功标准；
3. HOW：已批准技术方案、允许工具和复用来源；
4. WHERE：读写路径；
5. RULES：约束、边界、回退和停止条件；
6. VERIFY：可证伪测试、证据与验收命令。

蓝图只解释如何在现有授权内完成任务，不改变任务包。

### 3.3 条件组合工程方法

- 新行为：使用 S11 的 RED → GREEN → REFACTOR，先证明测试会失败；
- 未知故障：先用 S12 查根因，再决定是否修改；
- 候选变更：按风险请求 S13 或 P2.6 独立审查；
- 完成声明：始终用 S14 对最终修改运行新鲜验证。

这些是按因果条件组合的方法，不是固定的第二流水线。caller 未授权的 Skill/工具只可作为建议返回，不得自行调用。

### 3.4 执行与止损

执行期间遵守：零输入不生成、空数据不覆写、核心实现不留占位、外部请求有超时/重试、错误不静默吞掉。遇到范围扩大、不可逆动作、权限缺失或连续失败时停止并返回 blocker；不得私自降级到偏离架构的路径。

首次出现新持久状态、新后台进程（Worker / Watcher）、新 transaction / journal、第二 Guard、Host 私有内部 patch 或跨 Plane Owner 扩张中的任一项时，当前工作不再是原子闭环。停止继续实现，向 caller 交回已观察事实和 `architecture_reassessment_required`，建议返回 P2 的生产采纳双轨复审；不得用再加一层机制把它留在 P3。Follow-up、Observation、候选下一步和 review proposal 都不是新的 Change Intent 或写入授权。

### 3.5 证据核收

回执不能只写“已通过”。至少包含：

- 实际修改文件；
- 实际执行命令与退出码；
- 测试/运行结果摘要；
- acceptance 对照；
- 未知、剩余风险和 blocker；
- 当前 diff 或等价物理证据引用。

### 3.6 交还与经验候选

P3 把 final receipt 交回原 caller/Core。重复风险只能形成带 evidence refs 的 `pending_human` 提案，交General Agent OS W7/M4 人工处理；不得自动修改 Prompt、Skill、Knowledge 或启动定时回流。

## 4. 返回契约

```json
{
  "method": "P3_SINGLE_ATOMIC_EXECUTION",
  "status": "SUCCESS | PARTIAL | FAIL | WAIT_HUMAN",
  "checkpoint_binding": {
    "thread_id": "echo-if-provided",
    "checkpoint_id": "echo-if-provided",
    "source_checkpoint_id": "echo-if-provided"
  },
  "artifacts": [],
  "files_touched": [],
  "commands_executed": [],
  "acceptance_results": [],
  "fresh_evidence_refs": [],
  "blockers": [],
  "review_proposal": {"recommended_method": "S14 or P2.6", "reason": "..."}
}
```

绑定字段只原样回显输入；P3 不生成或改写 checkpoint 标识。`review_proposal` 不是已执行审查。

</rules>

## LEGACY_CONTROL_ARCHIVE_ONLY

旧版 P3 的 `Legacy Gate 路由`、`旧 Graph-Native 路由`、`pipeline-state.yaml`、`gk_session`、`gatekeeper_state.json`、`pipeline_gate.py` 与 `current_pointer` 均已退役，不可执行。旧文档中的“如果两种契约均不存在”回退判据不再适用于新任务；旧实现只允许在冷归档中审计。
