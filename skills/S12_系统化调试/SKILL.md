---
name: S12 系统化调试
type: generic
domain: validator
tier: L3
doc_status: active-ssot
status: ACTIVE
version: 1
method:
  id: S12
  version: 1
  dimensions: [verification, cross_cutting_quality]
  applies_when: {fact: reproducible_failure, op: eq, value: true}
  requires: [{kind: artifact, id: failure-reproduction}]
  stages:
    implement: {consumes: [failure-reproduction], produces: [root-cause, minimal-repair]}
    verify: {consumes: [root-cause, minimal-repair], produces: [failure-and-healthy-path-results]}
  acceptance:
    required_evidence: [{kind: evidence, id: failure-and-healthy-path-results}]
  host:
    requires: [{kind: capability, id: execute-verification}]
    handoff: [Keep unknown causes explicit and return unavailable probes to their owner.]
  degradation:
    retain: [Observed facts and ranked hypotheses]
    withdraw: [Root cause or repair completion without direct results]
birth_ceremony_id: bc-s12-ab02e55a
birth_ceremony_date: '2026-05-02'
related:
- C:\Users\Administrator\.agent\assets\skills\S12_系统化调试\resources\CREATION-LOG.md
- C:\Users\Administrator\.agent\assets\skills\S12_系统化调试\resources\test-academic.md
- C:\Users\Administrator\.agent\control\registry\02-skill-catalog.md
description: 用户遇到报错、Bug、程序异常、需要排查问题时使用。

extends:
- C:\Users\Administrator\.agent\assets\rules\injection\skill-aop-prelude.md
- C:\Users\Administrator\.agent\assets\rules\error_handling.md
- C:\Users\Administrator\.agent\assets\references\methodology\10_S-Tier-Execution-Discipline-Protocol.md
---
> **【S12 专属天条】**：进场调试前必须强行挂载 `rules/execution.md`。高压天条：**未完成根因（Root Cause）实锤调查前，谁敢写一行修复代码，立刻判决违规断电！**

# S12_系统化调试 (Systematic Debugging Core)

<context>

## 1. 核心目标与防线边界
**专属负责**：应对测试链红盘、构建崩溃、生产报错、性能宕机时的“冷血验尸官”。
**绝对不负责**：无明确报错方向的纯架构性瞎改（此类归 `P2` 管）；仅仅因为代码不符合审美就发起改写（此归 `S13` 管）。

### 组合工程方法（General Agent OS 通用）

本节是 `C:\Users\Administrator\.agent\assets\rules\agent-constitution.md` §2.1 的调试场景化落地；即使单独加载本 Skill，以下条款也直接生效。

本 Skill 将General Agent OS 共同底座“目标、根因、职责边界、物理证据”翻译成调试动作。各方法按当前问题条件选择和组合；这不是 Automation Core 专属，也不是固定的 S11 → S12 → S13 → S14 串行流水线。

- **输入**：目标与正常预期、从正式入口取得的可重放失败、可比较的健康对照，以及当前已知的责任边界；根因未知可以作为诚实输入，不能伪造结论。
- **本 Skill 输出**：已观察事实、被排除的假设、根因与责任层、已经由根因解释的最小修复，以及原始失败路径和正常路径的物理结果。
- **条件交接**：修复需要建立新的行为契约或独立的 RED-GREEN 保护时，携带根因与复现证据交回 S11，避免重复造测试；已有稳定变更集才按风险考虑 S13，准备完成声明时才按调用方契约考虑 S14。

</context>

<rules>

## 2. 第一性原理：先定性，再修根因

S12 的目的不是把每个报错做成一套新机制，而是用最短路径让同类问题不再发生。开始排障前，先用原生入口的事实把问题放进且只放进一类：

1. **业务或人工边界**：需求、权限、输入或决策尚未具备。回 Owner，不改平台。
2. **一次性脏数据或旧残留**：只影响某个项目或历史对象。手工清理、隔离或重建，不把它写成永久规则。
3. **共享引擎缺陷**：能在干净环境、共享主路径稳定复现。修对应引擎的正式入口，并加入 DDT。
4. **监督或协同缺陷**：错误分类、错误路由、重复派工或角色越界。修监督 Harness 自己，不去改业务或目标引擎来掩盖它。

项目已有宪章、角色边界或协调者时，项目宪章优先。协调者负责派工、复审和关闭；施工者只提交施工结果；审计者只给出通过或精确退回点。没有这类项目约定时，S12 不额外发明角色、账本或流程。

## 3. 最小排障闭环

### [STATE: NATIVE_EVIDENCE]

- 从出错的正式入口开始，拿到可重放的失败事实；跨组件时沿真实调用链追到产生错误的一层。
- 找一个健康对照或正常路径。日志不足时，只补足定位根因所需的观测，不顺手搭建新的监控系统。

### [STATE: CLASSIFY_AND_EXPLAIN]

- 写出一句明确判断：问题属于哪一类、根因在哪里、为什么不是其他三类。
- 如果症状是注册项、输入格式或消费者断裂，同一问题上一次列出这项能力的当前入口、配置/输入和实际消费者；不要每轮只补眼前一个字段。
- 还不能确定根因时如实停在这里，补证据或回 Owner；不靠猜测写修复。

### [STATE: DIRECT_REPAIR_OR_ONE_TIME_CLEANUP]

- 共享问题只修真正的引擎入口、生成源或共享能力；一次性问题只做一次性清理。
- 不用新增哈希、冻结包、账本、旁路、无关字段、重复 Gate 或第二套流程来遮住表象。只有它们本身就是已复现根因时才讨论保留。
- 每次只实现已经被当前根因解释的一组最小改动；不要借修复顺手重构无关模块。

### [STATE: DDT_AND_INDEPENDENT_CHECK]

- 永久 DDT 至少包含：原始共享失败场景、同一正式入口的正常场景，以及业务/脏数据不会误触发平台整改的边界场景。
- 历史残留、偶发单项目数据和人为输入缺失只留一次性处理记录，不进入永久 DDT。
- 施工者先跑原始与正常场景并报告事实；若项目设有独立审计，审计者只核对是否直修入口、是否过度设计和 DDT 是否覆盖主流链路。

### [STATE: STOP_AND_REPLAN]

- 同一问题被两次因不同根因退回，或原始与正常场景无法同时解释时，停止叠加补丁，重新做分类、入口链和责任边界判断。
- 同一实现路线连续暴露多个环境、生命周期或宿主内部缺陷，尤其每次修补都开始要求新增 state、Worker、journal 或 Guard 时，`architecture_mismatch_or_production_overreach` 是一等根因候选。保留失败事实并交回 P2 的生产采纳双轨复审；S12 不自行裁决生产采纳，也不继续叠加补丁。
- 结案只意味着原始场景和正常场景都已证明改善；业务恢复仍由业务 Owner 决定。

</rules>

<template>

## 4. 交接说明

除非调用方已经规定结构化回执，使用五句白话即可：问题分类、正式入口与根因、处理方式（修复或一次性清理）、原始与正常场景结果、由谁接下一步。

不要为了交接再造 JSON、状态字段或验收协议。只有已经存在的项目格式要求结构化结果时，才按那个格式填写。

</template>
