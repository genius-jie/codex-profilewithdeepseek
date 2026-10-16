---
name: S13 代码审查
type: generic
domain: validator
tier: L3
doc_status: active-ssot
status: ACTIVE
version: 1
method:
  id: S13
  version: 1
  dimensions: [verification, cross_cutting_quality]
  requires: [{kind: artifact, id: change-set}, {kind: artifact, id: acceptance-criteria}]
  stages:
    review: {consumes: [change-set, acceptance-criteria], produces: [independent-findings, review-scope]}
  acceptance:
    required_evidence: [{kind: evidence, id: independent-review}]
  host:
    requires: [{kind: capability, id: inspect-changes}]
    handoff: [Review independently; return findings to the change owner.]
  degradation:
    retain: [Clearly bounded review observations]
    withdraw: [Full acceptance or verification outside reviewed scope]
birth_ceremony_id: bc-s13-2637892e
birth_ceremony_date: '2026-05-02'
related:
- C:\Users\Administrator\.agent\control\registry\02-skill-catalog.md
description: 用户要求做Code Review、审查代码质量、检查安全漏洞时使用。

extends:
- C:\Users\Administrator\.agent\assets\rules\injection\skill-aop-prelude.md
- C:\Users\Administrator\.agent\assets\rules\execution.md
- C:\Users\Administrator\.agent\assets\references\methodology\09_Asset-Governance-Audit-Protocol.md
- C:\Users\Administrator\.agent\assets\references\methodology\10_S-Tier-Execution-Discipline-Protocol.md
---
# S13_代码审查 (Code Review)

<context>

## 📌 核心目标

不空谈“命名是否规范”，而是像一个**无情的漏洞检测仪**，针对被审查的 Diff 代码段进行毁灭性的攻击测试与逻辑穿透。

### 组合工程方法（General Agent OS 通用）

本节是 `C:\Users\Administrator\.agent\assets\rules\agent-constitution.md` §2.1 的审查场景化落地；即使单独加载本 Skill，以下条款也直接生效。

本 Skill 将General Agent OS 共同底座“目标、根因、职责边界、物理证据”翻译成审查动作。各方法按当前问题条件选择和组合；这不是 Automation Core 专属，也不是固定的 S11 → S12 → S13 → S14 串行流水线。

- **输入**：当前目标与验收契约、冻结边界、责任 Owner，以及从磁盘独立回读的当前变更集、相关调用点和测试；生产者总结只能作为定位线索。
- **本 Skill 输出**：独立审查 verdict（APPROVED 或 REJECTED）与逐项 finding；每项 finding 分开写已观察事实和证据、风险推断与影响、尚未确认项。
- **条件交接**：缺少行为覆盖时建议调用方补 S11；出现可重放故障且根因未知时建议调用方使用 S12；是否进入 S14 或后续交付由调用方契约决定。REJECTED 不得进入 S15/S16。

---

</context>

<rules>

## 2. 🧠 无情扫雷状态机 (Harness State Machine)

在收到审查请求时，必须逐项打勾执行以下防爆舱阶段：

### [STATE: REVIEW_SCOPE_AND_ACCEPTANCE] (目标、范围与验收映射)

- 先说明本次变更要实现的目标、验收条件、冻结边界与实际 Diff 范围；清单只检查适用项，不能替代任务正确性审查。
- 从当前磁盘读取变更文件、调用关系和相关测试。历史报告、施工者总结和旧命令结果只作线索，不直接作为独立裁决。

### [STATE: CRITICAL_SECURITY_AUDIT] (致命缺陷与越权检查)

- [ ] **信息泄露核查**：代码中是否硬编码了任何密码、Secret、Token 或内部 IP 地址？
- [ ] **日志越权掩埋**：是否存在 `try {} catch {}` 块直接吞掉了异常（不做任何 `logger.error` 或向上抛出）？
- [ ] **未校验的空指针**：对于外部传入的变量或数据库查询的单个返回值，是否有直接解构或访问其属性，而没有做 `null / undefined` 判空防护？

### [STATE: CONCURRENCY_AND_OOM_CHECK] (并发与物理内存压测)

- [ ] **N+1 连环爆炸**：是否在 `for`、`map` 等循环体内加入了数据库操作（如 `SELECT` / `UPDATE`）或第三方 API 调用？
- [ ] **超大内存加载**：是否存在从数据库中 `SELECT *` 而不加上 `LIMIT`，或者读取全量文件的操作，导致潜在的 OOM（内存溢出）？
- [ ] **锁与竞态**：并发更新同一行数据时，是否缺少了乐观锁、Redis 分布式锁或适当的事务隔离？

### [STATE: ARCHITECTURE_COMPATIBILITY_REVIEW] (架构基线与副作用审查)

- [ ] **向后兼容性破坏**：修改了现有的 public 函数签名或 API 接口的 JSON 结构，是否会导致老客户端崩溃？
- [ ] **状态机泄露**：对于带有状态机流转的数据（如 待支付->已支付），是否有防止跳跃或逆向流转的判断？
- [ ] **副作用残留**：执行失败退出时，是否有残留的部分数据没被清理（缓存与数据库不一致，或者未 Commit/Rollback）？

### [STATE: EVIDENCE_REASONING_AND_HANDOFF] (事实、推断与条件交接)

- 每项 finding 必须给出触发条件、文件/行或命令证据、影响和修复方向；把观察事实、风险推断和未知项分开，不能用语气强度代替证据。
- `0 findings` 只表示在已审范围内没有发现问题，不代表系统绝对正确，也不能替代 S14 对完成声明的验证。
- APPROVED 只放行当前审查范围；REJECTED 返回责任 Owner。根因未知时才建议 S12，缺行为保护时才建议 S11，不自动串联其他 Skill。

---

</rules>

<template>

## 3. 📤 标准通信契约 (Harness JSON & Output)

除了抛出人类可读的审查清单外，按调用方既有契约返回判决。下面只示范可被成功回执消费者接受的 APPROVED 结果；REJECTED 不伪造成功状态，直接携带 findings 交回调用方：

```json
{
  "harness_metadata": { "phase": "S13_Code_Review", "status": "APPROVED" },
  "reviewed_files": ["src/app.py"],
  "reviewed_tests": ["tests/test_app.py"],
  "findings_open": 0,
  "blocking_findings": 0,
  "evidence_ref": "s13-review.json",
  "summary": "在声明的变更集与验收范围内未发现阻断项",
  "audit_diagnostics": {
    "security_leaks": 0,
    "concurrency_risks": "在已审范围内未发现阻断项",
    "architecture_compatibility": "在已审范围内未发现兼容性破坏"
  },
  "execution_actions": [],
  "next_routing": "由调用方根据 verdict 决定；APPROVED 才可进入提交，REJECTED 回责任 Owner"
}
```

> **绝对禁止**向外部早已粉碎的历史文档转移核心判决规则！所有的护城河原则，即以此文档为最高法典。
</template>
