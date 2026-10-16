---
name: S14 完成前验证
type: generic
domain: validator
tier: L3
doc_status: active-ssot
status: ACTIVE
version: 1
method:
  id: S14
  version: 1
  dimensions: [verification, delivery]
  applies_when: {fact: completion_claim, op: eq, value: true}
  requires: [{kind: artifact, id: acceptance-claims}, {kind: artifact, id: candidate-artifacts}]
  stages:
    verify: {consumes: [acceptance-claims, candidate-artifacts], produces: [claim-support-and-limitations]}
    deliver: {consumes: [claim-support-and-limitations], produces: [bounded-verdict]}
  acceptance:
    required_evidence: [{kind: evidence, id: claim-support}]
  host:
    requires: [{kind: capability, id: execute-verification}]
    handoff: [Return unsupported claims to the responsible owner; do not repair during verification.]
  degradation:
    retain: [Evidence gap report]
    withdraw: [Completion approval until every required claim is covered]
birth_ceremony_id: bc-s14-5cd3b671
birth_ceremony_date: '2026-05-02'
related:
- C:\Users\Administrator\.agent\control\registry\02-skill-catalog.md
description: |
  【触发场景】提交/合并/完工前的证据验证。
  【不触发】任务尚未结束、没有物理证据不要用。
  【功能】核对结果、拒绝臆测、给最终放行或打回。
extends:
- C:\Users\Administrator\.agent\assets\rules\injection\skill-aop-prelude.md
- C:\Users\Administrator\.agent\assets\rules\execution.md
- C:\Users\Administrator\.agent\assets\references\methodology\09_Asset-Governance-Audit-Protocol.md
- C:\Users\Administrator\.agent\assets\references\methodology\10_S-Tier-Execution-Discipline-Protocol.md
---
> **【S14 专属加严约束】**：执行任何 `[Completed]` 的宣告前，必须取得与验收标准对应的新鲜物理证据。相关命令返回 Exit 0 是必要条件，但不是目标完成的充分条件。

# S14_完成前验证 (Verification Before Completion)

<context>

## 1. 核心目标与防线边界
**专属负责**：充当所有开发特种兵（S8, S9, S10）在试图提交 PR 或合并分支前的最后一道物理验伤防线。
**绝对不负责**：主观臆测代码已经“看起来修复了”。没有经过终端编译器或 Linter 的绿灯，一切语言安抚视为撒谎。

### 组合工程方法（General Agent OS 通用）

本节是 `C:\Users\Administrator\.agent\assets\rules\agent-constitution.md` §2.1 的验收场景化落地；即使单独加载本 Skill，以下条款也直接生效。

本 Skill 将General Agent OS 共同底座“目标、根因、职责边界、物理证据”翻译成完成前验收动作。各方法按当前问题条件选择和组合；这不是 Automation Core 专属，也不是固定的 S11 → S12 → S13 → S14 串行流水线。

- **输入**：用户目标、当前验收标准、准备声明完成的候选产物，以及逐项需要证明的完成声明。
- **本 Skill 输出**：完成声明到新鲜证据的覆盖关系、命令事实与其证明范围，以及最终 APPROVED 或 REJECTED；只有所有必需声明都有对应证据，才能判断目标达成。
- **证据宣判边界**：按 `C:\Users\Administrator\.agent\control\contracts\evidence-contract.yaml#claim_support_boundary` 区分方案、静态、运行、验收观察面；它们不是成熟度等级，也不要求无关任务机械全量执行。每条 Claim 只能宣判到直接 Evidence 覆盖的范围。
- **条件交接**：REJECTED 将证据交回调用方指定的责任 Owner；出现可重放技术失败且根因未知时建议 S12，缺少行为测试时建议 S11。S14 不自行修代码、不替代 S13 审查，REJECTED 不得进入 S15/S16。

</context>

<rules>

## 2. 🧠 真实验尸状态机 (Harness State Machine)
> **终极死劫**：No Completion Claims Without Fresh Verification Evidence! 

### [STATE: COMPLETION_CLAIMS] (先列完成声明)

- 从用户目标和验收标准列出本次准备宣告的每一项完成声明，再为每项选择能真正证明它的命令、文件检查、运行状态或人工可核验事实。
- Lint、单元测试、构建、安装态、真实运行和用户结果各自证明不同事实；不得拿其中一项替代未覆盖的声明。
- 当完成声明包含 production adoption、耐久性或新增长期运行机制时，除功能结果外还必须覆盖 P2 的生产采纳双轨复审：唯一 Owner / SSOT / 正式入口、现有方案不足的事实与更小解、派生状态可重建且无第二状态源、影响范围及退役条件。测试全绿只证明实现正确，不能单独证明架构必要性；S14 只核对这些证据，不自行批准后续实现。

### [STATE: EVIDENCE_IDENTIFICATION] (寻找定罪级物理指令)
- 针对当前刚刚写完的模块，冷血盘问：**需要跑哪条具体的 Terminal 指令才能证明活干完了？**
- 是 `npm run lint`？`npm test`？还是 `go build ./...`？

### [STATE: COMMAND_EXECUTION] (法外无情的终端轰炸)
- 使用当前环境可用的命令执行入口运行验证。证据必须产生于最后一次相关改动之后，并使用正确的 cwd、target、配置和输入；等待命令完整结束，记录本次 Exit Code 与 Summary。生产者的旧输出只能作为线索。

### [STATE: RESULT_ASSERTION] (验尸单比对与死锁截停)
- 如果命令抛出了红色的 Warning 或 Error (`Exit Code != 0`)：
  - **截停完成声明**：严禁宣称任务完成；记录失败事实及其证明范围，并按调用方契约交回责任 Owner。根因未知时才建议 S12。
- 如果全部命令 Exit 0，但仍有必需完成声明没有证据覆盖，同样判为 REJECTED；命令绿不能替代目标达成。
- 只有 100% 获得纯正的 Green Light：
  - 如果本次产物包含向人类交付测试报告或排故分析日志，须叠加一层 **【M11_去AI文风】** 的定罪拦截：交付物质量评分标准见 M11 SKILL.md 核心原则（无独立评分卡工件），按核心原则核查后仍不合格者，连同废话一起打回原地重写！
  - 只有两道防线全线绿灯，才允许接通后面的 S15 / S16 进行 Git 推盘结算。

</rules>

<template>

## 3. 📤 标准通信契约 (Harness JSON I/O)
退出本中枢前按调用方既有契约返回验证结果。下面只示范全部完成声明已经覆盖时的 APPROVED 成功结果；REJECTED 不伪造成功状态，直接携带缺失证据或失败事实交回调用方：

```json
{
  "harness_metadata": { "phase": "S14_Final_Verification", "status": "APPROVED" },
  "evidence": {
    "command_run": "npm run build && npm run test",
    "exit_code": 0,
    "failures": 0
  },
  "cognitive_diagnosis": "构建与测试均已按本次命令通过，且必需完成声明已有证据覆盖，允许放行",
  "next_routing": "由调用方根据 verdict 决定；APPROVED 才可进入 S15/S16，REJECTED 回责任 Owner"
}
```

> **红灯告警**：永远不要拿 Linter 通过去顶替编译通过，不要拿“Agent 已经重构成功”顶替物理指令的宣判！

</template>
