---
name: M4 知识回流分析
type: generic
domain: meta-governance
tier: L2
doc_status: active-ssot
status: active
birth_ceremony_id: bc-m4-4f5fd8e4
birth_ceremony_date: '2026-05-02'
related:
- @@GENERAL_ROOT:win@@\assets\rules\chunk_production_throttle.md
- @@GENERAL_ROOT:win@@\assets\rules\distillation-quality-gate.md
- @@GENERAL_ROOT:win@@\control\registry\02-skill-catalog.md
- @@GENERAL_ROOT:win@@\assets\references\methodology\31_Self-Distillation-Workflow-Packaging-Protocol.md
description: 任务完成后做知识沉淀、经验提炼、错题回流时使用。

  【不触发】没有复盘、经验沉淀、升格或错题回流需求的普通执行任务不要用。

  【功能】作为知识回流总枢纽（W7 流程的物理承载体）。从执行现场提炼血泪证据，完成知识的鉴别分诊，跨域路由至对应 Skill 进化槽，并打穿闭环核验。
extends:
- @@GENERAL_ROOT:win@@\assets\references\methodology\09_Asset-Governance-Audit-Protocol.md
---
> **【架构定级声明】**：本 Skill 是 Harness 引擎生命周期核心进化大动脉（由原跨域 X7 升级而来的 M 级 generic 绝对中枢）。
> **【AOP 横切依赖】**：它是所有单体作业产出提纯后的终极归宿。开始必须通过 `control/orchestration/W1_前置思考.md` 清洗乱象，并受 `rules/execution.md` 的深层钳制。
> 遵循 `@@GENERAL_ROOT:win@@\assets\rules\injection\skill-aop-prelude.md` 横切注入。
# M4_知识回流分析 (进化与反思中枢 · 轻量态)

<context>
## 1. 目标与边界
**本中枢专属负责**：案发现场的血泪实弹证据提炼、事故根因倒溯、分发路由（审判该经验应归入哪个单体 Skill 错题本或全局系统法典）、以及最终的闭环合规验证。
**本中枢绝对不负责**：越俎代庖直接去修业务代码的 Bug，或者将冗长的分发矩阵长文强行堆积在入口大厅（**必须持续贯彻入口轻量化法则**，方法论已悉数隔离下沉至 `references/` 底层）。

</context>

<rules>
## 2. 🧠 强制编排状态机 (Harness State Machine - OpenSpec Artifact Graph 锁)
> **终极死劫**：所有被要求“反思、记错、回流”的收尾指令，必须严格执行 OpenSpec 的 Artifact Graph DAG 依赖图节点推进，穿透以下三级提纯熔炉，严禁跳步！
> **【知识进化增量引擎】**：在分诊与回流写入时，必须无条件采用 OpenSpec 的 Delta Spec 合并机制，所有修改必须打上 `[ADDED]`、`[MODIFIED]`、`[REMOVED]` 或 `[RENAMED]` 原子操作标签！

### [STATE: EXTRACTION_FURNACE] (T4级暂存队列提取与铁证鉴别)
- **【T4 资产队列提取】**：强制下潜至 `governance/experience_queue.md` (全域活体暂存队列)。提取尚未结账的报错血泪残骸。
- **【M12 强制切片协议 🆕】**：如果积压条目 > 3 条，**绝对禁止大模型直接全量读取和凭记忆瞎写**！必须强制手写一个 Python 游标脚本（Slice 1, Slice 2...），打碎成每次只处理极小批量的切片。**贯彻 MapReduce 分片哲学**：每次大模型只需关注当前 Slice 涉及的 1-2 条报错残骸，不需要一次性消化太多。这种切片机制从根本上保证了代码与语境的“局部可读性”，从而阻绝大模型为了强行闭环而天然激发的“以覆盖率换深度”偷懒天性。
- 严禁凭空臆想！必须收集现场终端抛出的大红报错或用户斥责原话。
- 基于单一变量原则假设剥离，**绝不容忍含糊其辞的归因**，必须死死锁定导致崩溃的核心文件的某一行。提纯后立刻清空 `governance/` 对应的挂起条目。

### [STATE: TRIAGE_ROUTING] (精准分诊引流)
- **定位坐标**：这条经验属于哪个层级？是单体兵刃（Skill）特有的坑，还是全局法典（Rules）的破绽，抑或工作流（Workflow）的断层架构病？
- **单体错题本对接受理**：如果是单体战术坑，强行接驳打通该对应 Skill 专属的 `resources/错题本.md`，将解法翻译成大白话（5W1H）硬性刻录进去。
- **执行落盘切割**：强制挂载 `@@GENERAL_ROOT:win@@\docs\00-harness-oss-index.md`。依据 `README.md` 执行矩阵分类落盘：全局宗庙级架构警示必须强制入库 T3 `cases/`；单体局部报错强制回流至对应战术兵团的 T2 `resources/错题本.md`。

### [STATE: CLOSED_LOOP_CHECK] (强制举证闭环与 W9 收口)
- **【防线一：物理写盘即时落地】（治"脑内自审"）**：在每个极其微小切片 (Slice) 完成物理写入 Append 后，大模型**不能仅凭执行器不报错就结束任务**。必须在写入的一瞬间，强制跟上 `view_file` 或 Python 内核 `read` 指令*从文件重新读取来验证*。**验证对象必须是磁盘上的物理文本，绝不是脑内幻象**！终端见到自己亲手写入的心跳文本才算成功。**“没有回显比对 = 没有执行落盘”**！
- **【防线二：关键片跨脑盲审】（治"合理化偏见"）**：当切片追溯矩阵（如 Slice 3）和 Reduce 流（端到端验证）即将收口时，面对高维治理法则的升格修改，必须挂载第三方抽查或跨脑盲审（脱离当前上下文），以击碎模型在自我造物时容易产生的“合理化偏见”打分放水。
- 反向自省该经验的质量：是否满足“大白话、有现象、有解法”的三要素防御标准？
- 所有合规动作收拢后，强接 `workflows/W9_出口验收.md` 接受五维防线搜身。

</rules>

<template>
## 3. 标准协议输出出口 (I/O Contract - OpenSpec Template)
一旦经验挂载闭环大成功，向主控全息屏抛出极其冷酷的 JSON 标准执行简报：
```json
{
  "harness_metadata": { "phase": "M4_Reflexer", "status": "COMPLETED" },
  "triage_coordinates": { "target_layer": "M12_大文件分块读取", "asset_type": "错题本进化槽位" },
  "cognitive_diagnosis": "已从 governance/ 提取幽灵资产撕裂 BUG，提纯落地为大白话错题集并清理原中转站黑板",
  "execution_actions": [ 
    { "target": "governance/experience_queue.md", "action": "QUEUE_POP_CLEARED" },
    { "target": "skills/M12_大文件分块读取/resources/错题本.md", "action": "APPEND" }
  ]
}
```

</template>

<rules>
## 4. 🗂️ 动态导航教典大盘
**所有底层原理均已清拆下沉！遇到复杂的世纪路由判例分歧时，立即带参下潜调取以下弹药库支援：**
- **矩阵分类降维打击定位**：当无法确定经验资产的层级时，必须强制翻阅矩阵系统总导航 `@@GENERAL_ROOT:win@@\docs\00-harness-oss-index.md`，校验其属于 L1-L4 的哪一层分类轴！
- **知识流转机制出现卡壳时**：立刻研读知识流转治理判例 `@@GENERAL_ROOT:win@@\assets\cases\governance\knowledge-circulation-governance.md`。
- **防止自身脑体发生失控膨胀**：随时回顾前人血泪判例总结 `@@GENERAL_ROOT:win@@\assets\cases\governance\knowledge-circulation-governance.md`。
- **寻找标准化资产入位模板**：执行前回溯大字典 `@@GENERAL_ROOT:win@@\assets\templates\` 寻找对应规矩骨架。

---
**最后更新**: 2026-03-31 | **版本**: v2.1.0 (Harness 11-Kernel 全域归一化重塑版)
</rules>

<template>
</template>
