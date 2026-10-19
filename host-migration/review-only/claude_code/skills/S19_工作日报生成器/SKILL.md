---
name: S19 工作日报生成器
type: generic
domain: utility
tier: L3
doc_status: active-ssot
status: ACTIVE
birth_ceremony_id: bc-s19-742b5d47
birth_ceremony_date: '2026-05-02'
related:
- @@GENERAL_ROOT:win@@\evidence\S19_工作日报生成器\daily-reports\README.md
- @@GENERAL_ROOT:win@@\evidence\S19_工作日报生成器\daily-reports\日报0227.md
- @@GENERAL_ROOT:win@@\evidence\S19_工作日报生成器\daily-reports\日报0502.md
- @@GENERAL_ROOT:win@@\evidence\S19_工作日报生成器\daily-reports\日报0520.evidence.md
- @@GENERAL_ROOT:win@@\evidence\S19_工作日报生成器\daily-reports\日报0521.evidence.md
- @@GENERAL_ROOT:win@@\assets\skills\S19_工作日报生成器\scripts\daily-report-cron-manifest.md
- @@GENERAL_ROOT:win@@\assets\skills\S19_工作日报生成器\references\日报合并铁律与约束指标.md
- @@GENERAL_ROOT:win@@\assets\skills\S19_工作日报生成器\resources\降级草稿模板.md
- @@GENERAL_ROOT:win@@\assets\skills\S19_工作日报生成器\resources\报告模板与示例.md
- @@GENERAL_ROOT:win@@\control\registry\02-skill-catalog.md
description: 用户要求生成工作日报、写今日总结、汇报今天做了什么时使用。

extends:
- @@GENERAL_ROOT:win@@\assets\rules\injection\skill-aop-prelude.md
- @@GENERAL_ROOT:win@@\assets\rules\execution.md
- @@GENERAL_ROOT:win@@\assets\references\methodology\10_S-Tier-Execution-Discipline-Protocol.md
---
# Skill: S19_工作日报生成器

<context>

## 1. 目标与定位
自动化收集并整理每日工作项，重点聚焦于**性能观测体系建设、自动化设施维护、质量效能工具优化及生产稳定性治理**，生成符合测试开发专业视角的日报。

</context>

<rules>

## 2. 核心原则
- **细则外置**：完整合并规则、约束指标、质量硬规则见 `references/日报合并铁律与约束指标.md`。
- **铁律摘要**：四源全局扫描（Antigravity/Codex++/独立Codex/VSCode Claude Code）；大标题必须是真实项目级名称；单条 45~90 字；禁止技术黑话与短清单；git 只做辅助校验；用户补充事实优先定稿；知识回流必须走 M4 流程（禁止直写错题本）。

## 3. 输入要求 (Input Contract - 多数据源)

### 3.1 强制上下文校验 (Context Validation)
> **🚨 无上下文防御铁律**: S19 严禁在"零对话上下文"状态下生成正式日报！
> 
> 当满足以下任一条件时，必须触发**防御性降级**：
> 1. 当前会话是新会话（无历史对话记录）
> 2. 用户仅发送"写日报"/"生成日报"等极简指令，无具体工作内容交代
> 3. 无法从当前会话中提取出当天的工作任务语义
>
> **防御动作**: 不得直接生成日报正文，必须：
> - 输出**"上下文不足，日报生成被拒绝"**的明确提示
> - 提供"草稿模式"选项：仅罗列当天文件变更清单，不做工作语义推断
> - 引导用户补充当天工作内容或提供工作会话摘要

### 3.2 四源用户输入流（主数据源）
- 定时任务模式必须优先读取 `daily-context-YYYY-MM-DD.json` 中的 `user_input_streams.records`，或直接读取 `daily-user-inputs-YYYY-MM-DD.json`；但这只是起点，不是终点。
- 固定主源为 Antigravity、Codex++、VSCode Claude Code、独立 Codex。只收集用户主动输入的任务命令、追问、修改要求、验收反馈和继续执行指令。
- 三入口预采集器当前若只覆盖 Antigravity、Codex++、VSCode Claude Code，Agent 必须额外补扫独立 Codex：优先检查 `@@CODEX_HOME:win@@\session_index.jsonl`、`@@CODEX_HOME:win@@\sessions`、`@@CODEX_HOME:win@@\archived_sessions`、`@@CODEX_HOME:win@@\quarantined_sessions` 中报告日相关会话。
- Codex++ 必须检查 `@@PROFILE_REPO:win@@\session_index.jsonl`、`sessions`、`archived_sessions`、`quarantined_sessions`、必要时检查 `follow-up/suggestions`，防止长线程、归档线程和 hook 中断后的结论漏采。
- Antigravity / VSCode Claude Code 必须结合预采集包和本地真实会话目录交叉检索；遇到用户纠正“扫得不充分”时，必须回到源目录按关键词、人名、项目名、业务对象和生产环境变更重新搜索。
- 写日报时先按四源用户输入和用户当日补充事实归并当天工作主线，再用 git/status/产物正文反查结果；禁止从 git 文件变更反推当天工作主线。
- 若四源输入流缺失、结构不完整或独立 Codex 未确认，必须硬失败或进入降级草稿，不得自动回退到 git-only 正式日报。

### 3.3 多域导航源 (SSOT 反转控制，辅助)
- S19 严禁在脚本或提词中写死硬编码疆界！必须**唯一信源依赖** L1 总线注册表 `@@GENERAL_ROOT:win@@\control\registry\01-asset-register.md`。
  从其《1. 物理层空间锚点》矩阵中实时解析取出当前受控大盘的所有物理 Root，作为扫描底座。

### 3.4 物理代码事实（辅助校验）
- 对 `01-asset-register.md` 中解析出的全部物理根目录域执行终端探针获取 `git log --since="midnight" --name-status` 以及 `git status -s`，用于校验三入口输入流指向的开发结果，不得单独决定日报主线。

### 3.5 操作日志事实（辅助校验）
- 必须利用 `collect_daily_changes.py` 从本地阵列扫盘获取新增文件，防止其脱离 Git 的视线（脚本内部已重构为自动读取 SSOT）。采集结果只代表文件时间戳线索，不能单独推出"完成了某业务工作"；必须和 git/对话/正文证据交叉验证。

### 3.6 噪声排除
- `.gemini`、`antigravity-backup`、`antigravity-ide/code_tracker`、`pipeline_state`、`sessions`、`hook-state` 等缓存、备份、会话状态和流水线中间态不得作为日报工作项的直接证据。

### 3.7 逻辑上下文
- 提取各个工程的文档与大纲，特指 Antigravity Brain 中的工作流逻辑。

### 3.8 状态事实
- 最终汇总的产出 `@@GENERAL_ROOT:win@@\evidence\S19_工作日报生成器\daily-reports\日报MMDD.txt` 文件。

</rules>

<template>

## 4. 输出产物 (Output Contract)
- **更新后的日报**: `@@GENERAL_ROOT:win@@\evidence\S19_工作日报生成器\daily-reports\日报MMDD.txt`
    - **格式**: Plain Text (纯文本)
    - **存储**: 强制存储至指定目录，严禁保存至临时目录。

## 5. 架构约束 (Architectural Constraints)
- **三权分立**: 
    - 脚本是**事实采集器**：优先上报三入口用户输入流，同时附带 git/status/文件变更辅助证据。
    - Agent 是**日报编写者/终审编辑**：基于用户输入流规划工作版图、归并任务主线，再用辅助证据判断任务完成度，严禁凭空编造未发生的工作。
    - Agent 必须保留条目级审计表：每个日报条目都要能回指到有效证据；如果只能回指到缓存/历史/状态文件，必须剔除。
- **单向依赖**: 日报生成依赖于 `User Input Streams + Auxiliary Evidence` -> `Summary`，严禁通过修改日报反推已完成工作。
- **拒绝权 (Power of No)**: 
    - 若三入口用户输入流采集器报错，必须休庭（终止并报错）。
    - 若三入口用户输入流为空且用户没有明确补充工作内容，必须拒绝生成正式日报。

## 6. 执行脚本
### `collect_user_input_streams.py`
- **功能**：采集当天 Antigravity、Codex++、独立 Codex、VSCode Claude Code 四个入口的用户主动输入。
- **输出**：`daily-user-inputs-YYYY-MM-DD.json`，并由 `daily-context-collector.ps1` 嵌入 `daily-context-YYYY-MM-DD.json`。
- **Codex++ 跨天长线程规则**：Codex++ session 文件按线程创建日期落目录，采集器必须读取报告日前 14 天至次日目录，并用文件修改时间兜底；最终只按消息时间过滤到报告日期，防止当前长线程漏采。
- **独立 Codex 硬门规则**：独立 Codex 必须作为 `codex` 单独进入 `required_source_ids` 和 `source_index`，不得被 Codex++ 统计替代；若根目录缺失或当日为空，也必须在 source_index 中显式记录 missing/empty 边界。

### `build_daily_report_closure_evidence.py`
- **功能**：读取 `daily-user-inputs-YYYY-MM-DD.json`，生成四源采集回执；可读取 APP/Jira coverage JSON 生成缺陷逐项覆盖矩阵。
- **输出**：建议保存为 `日报MMDD.closure.evidence.md`，作为正式日报前的闭环证据。
- **硬门**：四源回执为 FAIL 时，日报不得宣称“全量采集完成”；用户给出缺陷清单但未提供 coverage matrix 时，只能输出待确认草稿或明确证据边界。

### `daily-context-collector.ps1`
- **功能**：先采集三入口用户输入流，再采集 git/status/文件变更等辅助证据，生成定时任务上下文。
- **写后自验**：保存 `daily-context-YYYY-MM-DD.json` 后必须读回校验 date、summary、date_today_asia_shanghai、collection_summary、primary_evidence_source、user_input_context_path、user_input_streams 与三入口 source_index；缺任一字段必须硬失败。

### `collect_daily_changes.py`
- **功能**：扫描工作目录，列出今日（基于系统时间）新增或修改的文件，仅作为辅助校验。
- **输出**：JSON 格式的变更列表，供 Agent 参考。

## 6. 🧠 发版提油状态机 (Harness State Machine)

### [STATE: CONTEXT_VALIDATION] (上下文验证 - 新增前置关卡)

> **🚨 无上下文防御铁律**: S19 严禁在"零对话上下文"状态下生成正式日报！

**入场检查清单**:
1. **对话上下文检查**: 当前会话是否有历史对话记录？
2. **用户指令检查**: 用户是否提供了具体工作内容描述？
3. **定时任务上下文检查**: 是否接收到包含 `user_input_streams.records` 的 `daily-context.json` 文件？

**分支处理**:
- **Branch A - 人工模式**: 如果当前会话有对话上下文，用户明确交代了工作内容 → 进入 [STATE: CROSS_DOMAIN_OMNISCIENCE]
- **Branch B - 定时任务模式**: 如果检测到 `--context-file` 参数 → 验证三入口用户输入流结构有效性 → 有效则进入 [STATE: CROSS_DOMAIN_OMNISCIENCE]，无效则进入 [STATE: DEGRADED_DRAFT]
- **Branch C - 无上下文模式**: 如果既无对话上下文，又无定时任务上下文 → **强制进入 [STATE: DEGRADED_DRAFT]**

### [STATE: DEGRADED_DRAFT] (降级草稿模式)
当无法获取有效工作上下文时，S19 不得生成正式日报，必须输出**降级草稿**。
- **模板外置**：降级草稿完整模板见 `resources/降级草稿模板.md`。
- **铁律摘要**：仅罗列当天文件变更清单（物理事实），不做工作语义推断；必须提示人工确认后发布。

### [STATE: CROSS_DOMAIN_OMNISCIENCE] (全境防漏基底侦测)
- **强制首发动作**：绝对禁止直接抓瞎式撰写！接单后，必须通过调度指令获得所有受控工作区的物理根路径。

> **🚨 跨域取证铁律 (The Omniscience Extraction Ironclad Rule)**:
> 定时任务模式必须先从 `daily-context.json` 读取 `user_input_streams.records`，把 Antigravity、Codex++、VSCode Claude Code 三入口用户输入流作为初始日报主线；随后必须补扫独立 Codex，并执行以下全局校验：
> 1. **四源用户输入事实**：读取 `daily-user-inputs-YYYY-MM-DD.json` 或 `daily-context.json.user_input_streams.records`，并额外检查独立 Codex 当天会话索引与归档目录。
> 2. **人名/交接/APP/生产变更漏项检索**：围绕当天用户补充的人名、项目名、业务对象、APP 功能、生产环境服务名执行关键词交叉搜索；命中不足时保留用户补充事实为事实锚点，不得丢弃。
> 3. **Git 已落盘事实**：`git log --since="midnight" --name-status`。
> 4. **Git 游离态事实**：`git status -s`（只用于校验用户输入流指向的工作结果）。
> 5. **本地资产变动**：运行 `python @@GENERAL_ROOT:win@@\assets\skills\S19_工作日报生成器\collect_daily_changes.py` 动态扫描所有被赋权的 Mtime 阵营，结果仅作辅助。
> 6. **定时任务上下文溯源**（如适用）：如果调用来自定时任务，必须读取 `daily-context.json` 并校验 `primary_evidence_source=three_user_input_streams`，但不能因此跳过独立 Codex 补扫。
> 7. **证据边界说明**：若某条用户补充事项在本地会话未命中，但用户当日明确补充，日报可采纳为“用户补充事实”；若最终向用户汇报扫描过程，必须如实说明哪些源头命中、哪些只来自用户补充。

- **🚨 反幻觉铁律**：对于敏感文件（如测试报告、PRD），**必须使用 view_file 打开读取正文**，严禁凭文件名臆测内容。

### [STATE: ATOMIC_AUDIT] (原子审计与合并碰撞)
    - **严禁使用** `run_command` (cat/Get-Content) 读取旧日报。
    - **强制使用** `view_file` 内置工具。该工具是受信任的，不会触发用户确认压力。

3.  **原子化审计与生成**:
    - 在内存中完成语义碰撞、去重和合并。
    - 直接通过 `write_to_file` 或 `multi_replace_file_content` 更新结果。

4. **冲突处理与追加 (Atomic Update)**:
   - **读取旧档**: 若当日日报已存在，必须先 `Read` 全文。
   - **语义碰撞**: 将新采集的工作项与旧档进行比对。
   - **增量更新**: 相似项进行合并增强，新项追加至工作内容部分，严禁重复标题。

5. **质量自检 (Audit) - 🚨 必须遵守全局宪法【反生僻词汇堆积法则】**:
   - **绝对禁止黑话与宏大叙事**：永远严禁用高深词汇、生僻词汇、抽象黑话去包装报告（如：塌陷、掩蔽、反噬、全息通讯、高维降维、热力跃迁、底层熔断、上帝视角、多维聚合等）。
   - **强制大白话与 5W1H 极简口语表达**：必须像平时同事之间聊天一样，直接交代核心（干了啥、为什么干、怎么干的）。
   - **禁止堆砌底层技术细节**：不要在日报里暴露极其琐碎的技术实现细节（如：修改了 `openclaw.json`，重写了 `xx.js` 脚本等）。**只需要汇报工作任务点和最终完成了什么成果即可！** 
   - **去碎块化对比示例 💡**: 
       - ❌ 错误（无意义技术堆砌）：修改了 `status-*.js` 里的 `18e4` 参数延时。
       - ✅ 正确（汇报产出与结果）：放宽了桌面自动化服务的启动时间限制，彻底解决了频繁超时闪退的问题。
   - **核心审查指标**: 让不写代码的主管也能一眼看懂每天的产出价值。围绕 5W1H 讲故事，杜绝罗列枯燥的系统函数。

## 7. 报告模板
- **模板外置**：日报正文模板与合格/不合格条目示例见 `resources/报告模板与示例.md`。
- **铁律摘要**：大标题必须是真实项目级名称（如【Codex 自动化治理】）；每条工作描述 45~90 中文字符；禁止短清单和技术黑话；Jira 缺陷必须写清现象+影响+责任人优先级。

## 8. 📤 标准通信契约 (Harness JSON I/O)

日报撰写完毕并写盘后，必须使用 JSON 单抛出：

```json
{
  "harness_metadata": { "phase": "S19_Daily_Report_Gen", "status": "SUCCESS" },
  "report_summary": {
    "projects_covered": ["OpenClaw 基础设施", "PatchX 后端"],
    "total_bullets_generated": 5,
    "saved_path": "@@GENERAL_ROOT:escaped@@\\assets\\skills\\S19_工作日报生成器\\日报\\日报0331.txt"
  },
  "next_routing": "User_Review"
}
```

## 9. 定时任务飞书边界

- `日报上下文预采集` 是内部准备任务：成功回执静默，失败用 failureAlert 投递飞书。
- `每日工作日报` 是业务投递任务：成功时只向飞书输出日报正文，不输出执行过程、命令回显、英文思考、JSON、证据表或文件清单。
- 证据表、原始输入流和辅助校验结果只写本地文件；飞书正文只保留领导可读的日报内容。
</template>
