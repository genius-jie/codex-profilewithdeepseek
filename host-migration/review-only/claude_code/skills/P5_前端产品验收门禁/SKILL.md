---
name: P5 产品验收门禁
type: generic
domain: planner
tier: L2
doc_status: active-ssot
status: active
description: |
  【触发场景】当前项目交付完成，或 E Core 已形成 checkpoint-bound p6_final，需要在 W9 前做父级产品验收。
  【不触发】纯底层库可豁免展示交互扩展包，但仍需验产品目标、数据、功能和内容。
  【功能】先跑通用产品验收核心，再按场景加载 UI/报告/前端扩展审计。
extends:
  - @@GENERAL_ROOT:win@@\assets\references\design\design-token-system.yaml
  - @@GENERAL_ROOT:win@@\assets\rules\injection\skill-aop-prelude.md
related:
  - @@GENERAL_ROOT:win@@\assets\skills\S9_高级前端开发\SKILL.md
  - @@GENERAL_ROOT:win@@\assets\references\methodology\28_Modern-SaaS-UI-Aesthetics-Protocol.md
  - @@GENERAL_ROOT:win@@\assets\skills\P2_技术架构与方案设计\SKILL.md
  - @@GENERAL_ROOT:win@@\assets\references\design\design-token-system.yaml
  - @@GENERAL_ROOT:win@@\assets\references\design\design-token-warm-cream.yaml
  - @@GENERAL_ROOT:win@@\assets\references\design\golden-samples\dashboard-pattern.md
  - @@GENERAL_ROOT:win@@\assets\references\design\golden-samples\card-pattern.md
  - @@GENERAL_ROOT:win@@\assets\references\design\golden-samples\list-pattern.md
  - @@GENERAL_ROOT:win@@\assets\references\design\user-persona-to-ui.md
  - @@GENERAL_ROOT:win@@\assets\references\design\agent-tech-stack.yaml
  - @@CORE_ROOT:win@@\docs\runtime-contract-template.md
  - @@CORE_ROOT:win@@\src\pipeline\runner.py
birth_ceremony_id: bc-2026-05-06-bcid-batch
---
> **【架构定位声明】**：本 Skill 是父级外部产品验收能力，不是 E Core 内部 `p5` 节点的实现，也不驱动或改写 Core checkpoint。它专门拦截“代码能跑但产品不成立”的交付质量问题：**站在用户的位置，只看当前任务绑定的最终产品证据，判断是否真的完成第一性需求。**
> P5 的输入只能来自当前项目显式证据，或来自 E Core 同一 `thread_id/checkpoint_id` 的只读 `inspect` 投影及 `p6_final`；旁路证据可包含 S9/S11/S14 新鲜回执，下游为父级 W9。旧 D Automation Core 的 config/code 仅作 archive-only 历史证据，不得活动加载或 fallback。
> AOP 横切约束（M11 文风/M12 分块/文件编辑微创）统一挂载自 @@GENERAL_ROOT:win@@\assets\rules\injection\skill-aop-prelude.md（本文件不复制正文）。

# P5_产品验收门禁 (Product Acceptance Gate)

<context>

## 1. 核心定位与权限边界

**本门禁专属负责**：对已完成的产品交付物执行"用户视角五线审计"，产出可机器验证的 `product_verdict`，供 P5.2 与 W9 消费。

**绝对不负责**：
1. 不写业务代码、不改 CSS、不调组件——发现问题只开缺陷单打回对应 P3/P4 修复链路。
2. 不做架构决策——那是 P2 的事。
3. 不替代 S11 执行功能测试——P5 只审功能验收回执是否能证明用户主流程可用。

**触发时机**：
- `current_project_external` 在当前项目形成真实交付证据后触发
- `e_core_completed` 在同一 checkpoint 已形成 `p6_final` 后触发
- 两种模式都位于父级 W9 出口验收之前，不进入 Core 图
- 展示交互只对有 UI/报告/页面的项目强制；数据、功能、内容和第一性需求验收不因无 UI 豁免

**分层加载边界**：
- P5 核心验收：`GATE_-1` + `GATE_5`，所有项目必走。
- P5 前端/报告扩展包：`GATE_0` 到 `GATE_4.5`，仅当交付物包含 UI、报告页面、可视化工作台、浏览器页面或对外展示交互时强制加载。
- 纯后端 API、CLI、数据管线或底层库不得因为没有 UI 而跳过 P5；这类项目把 `display_interaction.status` 标为 `NOT_APPLICABLE`，并在报告中写明证据来源。

**证据绑定（禁止 fallback）**：
- `current_project_external`：必须显式给出当前 `project_root`、当前 acceptance、交付物引用、当前 diff/文件和修改后的新鲜测试或 S14 回执。
- `e_core_completed`：必须显式给出 E Core SQLite、`thread_id` 和 `checkpoint_id`，只读消费 `automation-core inspect` 的同一 checkpoint 投影；仅当 `status=COMPLETE` 且 `results.p6_final` 存在时进入父级完成态验收。
- 两种模式必须二选一。缺少模式、关键引用不存在、checkpoint 已变化或 `p6_final` 缺失时，输出 `EVIDENCE_BINDING_MISSING_OR_STALE` 并 `REJECT`；不得猜测项目路径、读取旧 D 默认配置、回读历史 checkpoint 补证，或降级到另一模式。

**OpenCLI AOP 展示验收前置**
- 对网页、报告页、可视化工作台和外部站点验收，先用 `ag_opencli` 尝试读取页面结构、当前浏览器态或公开 adapter 数据。
- 若 OpenCLI 能拿到页面标题、链接、列表或 JSON，对照 browser screenshot / DOM smoke 做双路径校验；若 Browser Bridge 未连接，写入 `opencli_tool_receipt=NOT_APPLICABLE`，不得替代真实浏览器截图验收。

</context>

<rules>

## 2. 五线产品审计状态机

### [STATE: GATE_-1_FIRST_PRINCIPLE_PRODUCT_ACCEPTANCE] (第一性产品验收总闸)

P5 的第一问不是“页面好不好看”，而是：

> 用户拿到这个产品后，能不能用它完成 P1 冻结的第一性目标？

验收只看当前 `evidence_binding` 绑定的交付物和白名单证据，不读取执行器长上下文，不接受“我已经实现”的自述。P1/P2 的长文背景必须在当前项目压缩成 `acceptance_digest`、`product_acceptance_receipt` 或 `product_view_content_model_ref` 这类证据索引；E Core 模式只读取同一 checkpoint 的 `request/results/feedback/interrupts` 与 `p6_final`，不回头拼接其他 checkpoint。必须拆成五条线：

1. **产品价值**：核心用户任务、首屏判断、关键结论是否完整承接 PRD。
2. **数据可信**：数据来源、样本、入库/读取、失败兜底、去重和时段过滤是否可追溯。
3. **功能可用**：主流程、筛选、搜索、详情、失败态和权限入口是否有可复跑测试或 smoke 证据。
4. **内容可读**：页面文案、标签理由、报告段落是否是用户语言，不能暴露内部字段、规则、调试值或机器口吻。
5. **展示交互**：布局、对齐、字号、间距、层级、空态、错误态和截图矩阵是否能让用户顺畅阅读。

任一强制线缺证据，P5 必须打回对应 P3/P4 修复；只允许把不适用的展示交互标记为 `NOT_APPLICABLE`，不得把产品、数据、功能、内容四条线标成不适用。

### [STATE: GATE_0_DESIGN_TOKEN_COMPLIANCE] (设计令牌合规预检)

从本节点到 `GATE_4.5` 属于 P5 前端/报告扩展包。只有交付物包含 UI、报告页面、可视化工作台、浏览器页面或对外展示交互时才强制执行；纯后端 API、CLI、数据管线或底层库必须跳过本扩展包，并在 `display_interaction` 中标记 `NOT_APPLICABLE`。

对需要展示交互验收的项目，先做技术层面的合规预检：

**强制读取**：`@@GENERAL_ROOT:win@@\assets\references\design\design-token-system.yaml`

**自动化扫描清单**：
1. **非标间距扫描**：用 grep 扫描项目 CSS/TSX 文件中出现的所有 px 数值，标红所有不在 `spacing.scale` 定义中的非标间距（如 5px、7px、13px、15px 等）
2. **硬编码色值扫描**：用 grep 扫描所有 `#[0-9a-fA-F]{3,8}` 和 `rgb/rgba` 值，标红所有未通过 `var(--xxx)` CSS 变量引用的硬编码色值
3. **内联样式扫描**：用 grep 扫描所有 `style={{` 或 `style="` 内联样式，逐条标红
4. **字体大小合规**：扫描所有 font-size 声明，标红不在 `typography.scale` 范围内的值
5. **旧浅绿模板回潮扫描**：扫描是否把 `#eef3f8`、`#edf3f1`、`#f1f5f9`、`#0f8f7d`、`#2e6b57` 或 warm-cream 当成默认主题；除非有明确品牌/历史兼容理由，否则打回 P2/S9 补 `visual_direction_statement`

**判定标准**：
- 硬编码色值 > 5 处 → 阻断，打回对应 P3/P4 修复链路
- 内联样式 > 0 处 → 阻断，打回对应 P3/P4 修复链路
- 非标间距 > 10 处 → 警告，附修复建议但不阻断

### [STATE: GATE_1_DEVELOPER_LANGUAGE_AUDIT] (开发语言外露审计)

**核心原则**：用户看到的每一个字，都必须是用户能理解的人话。

**自动化扫描**：用 grep 扫描所有 TSX/JSX 组件中的中文和英文文本内容，逐条匹配以下黑名单：

```yaml
developer_language_blacklist:
  # 数据管道术语
  - "入库"
  - "抓取"
  - "采集"
  - "爬虫"
  - "snapshot"
  - "board_id"
  - "trend_item"
  - "ingest"
  - "pipeline"
  - "worker"
  - "scheduler"
  - "cron"

  # 分类引擎术语
  - "未命中"
  - "归入"
  - "普通热榜"
  - "专题关键字"
  - "classifier"
  - "category_reason"

  # 数据库术语
  - "upsert"
  - "dedup"
  - "migration"
  - "schema"
  - "foreign key"
  - "index"

  # 状态码/错误码
  - "404"
  - "500"
  - "timeout"
  - "null"
  - "undefined"
  - "NaN"
  - "error_json"
```

**判定标准**：
- 黑名单命中 > 0 → 阻断，逐条列出文件路径+行号+原文+建议替换词
- 建议替换词映射表：
  - "入库话题" → "上榜热点"
  - "未命中专题关键字" → "全民热议"
  - "归入普通热榜" → "全网热议"
  - "抓取失败" → "数据暂时无法获取"
  - "snapshot" → "数据快照" 或直接不展示
  - "null/undefined" → 展示友好占位（如"暂无数据"）

### [STATE: GATE_2_CTA_AND_EMPTY_STATE_AUDIT] (行动引导与空态审计)

**CTA 审计**：
1. 页面上每个 `<button>` 和 `<a>` 的文案是否用了用户能理解的动词
2. 主 CTA 是否在视觉焦点区域（fold 线以上）
3. 是否存在"死链接"（href="#" 或 onClick 为空的按钮）

**空态审计**：
- 扫描所有条件渲染（`{xxx.length === 0 && ...}` 或 `{!data && ...}`），检查空态展示内容
- 空态必须包含：(1) 友好提示文案 (2) 引导用户下一步操作的建议
- 禁止的空态表现：空白页面、只有 loading 没有超时兜底、"No data" 裸文本

**错误态审计**：
- 扫描所有 `catch` 和 `error` 相关的渲染逻辑
- 错误信息必须是用户人话，禁止展示堆栈、错误码或技术细节
- 必须提供重试或返回的操作入口

**判定标准**：
- 存在裸 "No data" / "Error" 展示 → 阻断
- 存在死链接 → 阻断
- 空态缺少引导 → 警告

### [STATE: GATE_3_INFORMATION_HIERARCHY_AUDIT] (信息层级审计)

**三秒法则**：用户花 3 秒扫一眼页面，能不能立刻抓住最重要的信息？

**审计方法**：
1. **视觉权重审计**：使用 browser_subagent 打开页面截图，检查：
   - 页面主标题是否是视觉上最大最醒目的元素
   - 核心数据/结论是否在 fold 线以上
   - 辅助信息（时间戳、来源、元数据）是否用了更小字号和更淡颜色
2. **信息优先级审计**：
   - 卡片内容的排列顺序是否按"结论→证据→来源"递进
   - 是否存在"数据字段堆叠"（把所有字段平铺展示而不做优先级区分）
3. **视觉噪音审计**：
   - 页面是否有超过 3 种颜色的 badge/tag
   - 是否有大面积的纯文字区域没有任何视觉分隔

**判定标准**：
- 主标题不是页面最大字号 → 阻断
- fold 线以上无核心信息 → 阻断
- badge 颜色超过 4 种 → 警告

### [STATE: GATE_4_VISUAL_CONSISTENCY_AUDIT] (视觉一致性审计)

**强制读取**：`design-token-system.yaml` 中的 `visual_consistency_checklist`

**逐条核验**：
1. 同一页面所有按钮 padding 是否统一（不超过 2 种尺寸）
2. 同一页面所有卡片 border-radius 是否统一
3. 同一页面所有标题字重字号是否按层级递减
4. 所有状态色是否只用语义变量，未出现硬编码 hex
5. hover 和 selected 态是否全局一致
6. 间距是否全部为 4px 倍数
7. 字体大小是否全部在 typography.scale 范围内
8. [ADDED] 4 级字号字重阶梯合规 (Level 1: 16-17px 800 | Level 2: 13px 700 buttons/tabs | Level 3: 13px content | Level 4: 12px headers)。同一 Header 内的 Primary/Secondary 按钮强制相同字号字重高
9. [ADDED] 独立卡片内边距与无贴边规则 (Card Padding: 22px 26px，绝对禁止标题/按钮贴紧卡片顶边或侧边)
10. [ADDED] 长列表/长表格渐进折叠审计 (默认置顶首屏 5 条 + 展开按钮；双向收起与 scrollIntoView 视角复位)

**跨页面一致性**（仅在同一项目有多个页面时）：
- 导航栏在所有页面的视觉表现是否一致
- 同类组件（如卡片、列表行）在不同页面的样式是否一致
- 配色方案是否全局统一（不允许一个页面暗色另一个页面亮色）

**判定标准**：
- 跨页面风格不统一 → 阻断（这正是热点雷达和视频战报的血泪教训）
- 单页面视觉不一致 > 3 项 → 阻断
- 单页面视觉不一致 1-3 项 → 警告

### [STATE: GATE_4.5_ARCHITECTURE_SEPARATION_AUDIT] (架构分离合规审计)

**强制读取**：`@@GENERAL_ROOT:win@@\assets\references\design\agent-tech-stack.yaml`

**核心原则**：结构归结构，样式归样式，模板当源码用。

**自动化扫描**：
1. **Headless 合规**：grep 扫描 components/ 中的 `<div onClick`、`<div role="dialog"`、手写 `position: absolute` + `z-index` 管理等自建 UI 原语
2. **shadcn 积木合规**：检查 components/ui/ 中是否存在手写的 Button/Dialog/Table/Input 等基础组件（应该全部来自 shadcn CLI）
3. **模板 Token 适配**：grep 扫描从外部拉入的模板组件中是否残留硬编码色值（#xxx / rgb()）
4. **Tailwind 任意值语法**：grep 扫描 TSX 文件中的 `[#` `[0-9]+px]` 等 Tailwind 任意值语法，标红要求替换为 Token 映射类名

**判定标准**：
- 自建 UI 原语 > 0 → 警告，建议替换为 Headless 库
- 手写基础组件 > 0 → 阻断，要求使用 shadcn 版本
- 模板残留硬编码 > 3 处 → 阻断，要求完成 Token 适配
- Tailwind 任意值 > 5 处 → 阻断，要求替换为 Token 类名

### [STATE: GATE_4.6_SCENARIO_EXTENSION_AUDIT] (场景扩展审计)

本节点只在命中对应场景时加载，不进入 P5 核心验收默认路径。

**加载规则**：
- 报告/看板/可视化工作台：只加载当前 `evidence_binding` 显式给出的 `report_acceptance_refs`、UI/IA Contract、当前产品 artifact 与新鲜浏览器证据；E Core 模式可从同一 checkpoint 的 `p6_final` 和 `results` 解析这些引用。
- 对话质量类报告：在报告/看板扩展包基础上，追加 `dialogue_quality_sampling_contract`、`dialogue_source_truth_result`、P2.6 对话主源审计回执。
- 非 UI、非报告、非看板交付：跳过本节点，写 `scenario_extension_profile=NONE`。
- 报告场景缺少显式 `report_acceptance_refs` 时，写 `scenario_extension_profile=UNRESOLVED` 并阻断；禁止读取旧 D `frontend_report_workbench_weapon_pack.yaml` 或任何默认路径兜底。

**报告型页面概要血缘**：
首屏标题、摘要、总数和三条核心结论必须来自报告级事实源或 artifact。搜索/筛选为空时，页面可以显示 0 条列表，但不得把报告级概要降级成“等待导入”或通用兜底文案。

**报告型页面用户视角读懂**：
P5 必须产出 `p5_report_user_view_receipt`。站在测试、开发、业务负责人三类读者视角检查标题、状态、字段、问题卡、详情弹框、原始日志和处理建议是否一眼能懂。用户可见主内容出现内部状态码、数据库枚举、`trace/session/user`、生硬 evidence path、分页切片等实现语言，或问题卡缺“现象、影响、初判、原因、日志证明、建议归属、处理动作”，一律打回；文案和详情实现回 P3，内容编排、聚类去重和证据粒度回 P4，读者契约缺失回 P2。

**报告型页面红队审计**：
必须检查标题和状态是否像正式测试报告；报告是否先讲测试目标、范围、方法和判定标准，再讲问题；主表是否只展示业务问题，不展示技术 ID、路径、候选池和内部回流策略；同根因问题是否合并，噪声是否过滤；每张问题卡是否给足现象、比例、影响、原因、日志证明、归属和动作；原始日志是否足够开发定位；详情按钮、弹框或抽屉是否能展开完整分析和代表性原始证据；筛选、搜索、详情、导出，以及业务需要的新增、编辑、删除、回滚和权限提示是否可用。任一项缺失，P5 必须写入 `p5_report_user_view_receipt.failed_checks` 并按根因打回，不得用“页面能打开”放行。

**C 线对话质量报告**：
报告要展示全天有效会话总数、可评测会话数和实际抽样数；抽样必须是 20 段跨用户、跨时间段、跨会话轮次数的完整真实会话；每行详情按钮必须打开完整用户/助手对话回放。若详情出现大片系统提示词、角色设定、调试上下文，或只展示截断片段、样本不足 20 段、抽样理由不清，P5 必须打回 P4 数据/内容编排或 P3 展示实现，不得放行。

### [STATE: GATE_5_VERDICT] (终审裁决)

**汇总五线审计结果**，产出结构化裁决报告：

```json
{
  "harness_metadata": { "phase": "P5_PRODUCT_ACCEPTANCE_AUDIT", "status": "PASS|CONDITIONAL_PASS|REJECT" },
  "context_policy": "final_product_and_whitelisted_evidence_only",
  "evidence_binding": {
    "mode": "current_project_external|e_core_completed",
    "project_root": "absolute path",
    "thread_id": "required for e_core_completed",
    "checkpoint_id": "required for e_core_completed",
    "p6_final_ref": "required for e_core_completed"
  },
  "loaded_gate_profile": "core_only|frontend_report_extension",
  "scenario_extension_profile": "NONE|REPORT_WORKBENCH|DIALOGUE_QUALITY_REPORT",
  "audit_dimensions": {
    "product_value":           { "status": "PASS|WARN|FAIL", "issues": [] },
    "data_trust":              { "status": "PASS|WARN|FAIL", "issues": [] },
    "functional_usability":    { "status": "PASS|WARN|FAIL", "issues": [] },
    "content_readability":     { "status": "PASS|WARN|FAIL", "issues": [] },
    "display_interaction":     { "status": "PASS|WARN|FAIL|NOT_APPLICABLE", "issues": [] }
  },
  "blocking_issues_count": 0,
  "warning_issues_count": 0,
  "routing": {
    "PASS":             "P5.2_测试验收轨道；不适用时直达 W9",
    "CONDITIONAL_PASS": "P5.2_测试验收轨道；附带 WARN 交 W9 复验",
    "REJECT":           "对应 P3/P4 修复链路（附带缺陷修复单）"
  }
}
```

**裁决规则**：
- `evidence_binding` 缺失、过期或混用两种模式 → `REJECT`，不得 fallback
- 5 条强制线全部 PASS，或展示交互被合法标记为 NOT_APPLICABLE → `PASS`，进入 P5.2；测试轨道合法不适用时进入 W9
- 存在 WARN 但无 FAIL → `CONDITIONAL_PASS`，放行但 W9 需复验 WARN 项
- 任何强制线 FAIL → `REJECT`，打回对应 P3/P4 并附带逐条修复单
- `loaded_gate_profile=core_only` 时，`GATE_0` 到 `GATE_4.5` 不得出现在阻断项里；只能记录为 `skipped_reason=NO_DISPLAY_SURFACE`

</rules>

<template>

## 3. P5 在父级验收链中的位置

```
当前项目显式交付证据 ───────────────┐
                                   ├─→ 父级 P5 产品验收 → P5.2（适用时）→ W9
E Core inspect + checkpoint + p6_final ┘
```

## 4. 与 P2 上游引导的协同关系

P2 在交付物呈现层设计阶段做的是**引导性设计**——把第一性需求、用户画像、信息架构、数据契约和展示规则提前说清楚。

P5 做的是**防御性审计**——不管 P2 引导得好不好、P3/P4 执行得准不准，P5 都只看最终产品证据，用五线检查表判断交付物是否真的完成第一性需求。

**双轨保证的本质**：
- P2 引导 = 让 P3/P4 一开始就朝对的方向走（减少返工）
- P5 拦截 = 哪怕实现过程走偏了也能在出口前拦住（消灭漏网之鱼）

两者缺一不可。只有 P2 引导没有 P5 拦截，执行偏了没人发现；只有 P5 拦截没有 P2 引导，每次都要返工三五次才能过关。

</template>
