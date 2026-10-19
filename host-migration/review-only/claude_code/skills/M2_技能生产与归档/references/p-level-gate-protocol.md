---
domain: meta-governance
tier: L3
doc_status: active-reference
related:
  - @@GENERAL_ROOT:win@@\assets\skills\M2_技能生产与归档\SKILL.md
  - @@GENERAL_ROOT:win@@\control\registry\02-skill-catalog.md
  - @@GENERAL_ROOT:win@@\assets\references\methodology\11_P-Tier-Execution-Discipline-Protocol.md
birth_ceremony_id: bc-plevelgateprotocol-2664904b
birth_ceremony_date: 2026-05-02
---

# P 级多步骤交付物纪律协议

## 1. 目标

多步骤 Skill 必须做到步骤可见、产物可回读、风险可中断、重要结果可独立复核。本协议只检查 Skill 的方法纪律，不创建父级状态机，不规定项目必须使用某个 sidecar。

## 2. 四项纪律

### 调用方状态

- 进度、重试和恢复归调用方或项目正式运行时。
- Skill 可在当前返回值中说明已完成步骤、未完成步骤和 blocker，但不得自建全局 lifecycle、Registry 或数据库。
- E Core 任务只认当前 checkpoint；父级 Skill 不读写其 SQLite。

### 写盘回读

- 修改真实文件后，从磁盘重新读取目标区域并核对 diff。
- 只读分析则以原始文件、命令输出或公开运行投影作为证据。
- 不能从生产者摘要或脑内记忆代替物理证据。

### 风险中断

- 低风险、可逆且在授权范围内的步骤可继续。
- 不可逆、高风险、外部权限、范围扩大或多轮不收敛时等待人类决定。
- 机器自动继续不得伪装成人类批准。

### 独立复核

- 候选变更使用 S13；完成声明使用 S14。
- P 级交付物在调用方要求时使用 P2.6；E Core 分支必须绑定同一 checkpoint-bound packet。
- 评审者独立读取当前文件、diff 和新鲜测试，区分事实、推断、未知和证据。

## 3. M2 出站检查

多步骤 P 级 Skill 出站前检查：

1. 是否明确调用方拥有状态与恢复；
2. 是否要求物理回读而非自证；
3. 是否按风险决定中断；
4. 是否指定真实独立复核边界；
5. 是否避免新增项目状态键、第二路由器或旧实现 fallback。

五项全部满足才可放行。调用方没有持久运行时的 standalone 方法任务，可以用本次任务的明确范围和证据清单承接，不得强造 sidecar。

## LEGACY_CONTROL_ARCHIVE_ONLY

旧 `pipeline-state.yaml`、每步人工 token、Gate-0 外部状态机、旧图内审计回执与旧 gatekeeper session 仅作历史设计证据，不是 P 级 Skill 的当前必填实现。
