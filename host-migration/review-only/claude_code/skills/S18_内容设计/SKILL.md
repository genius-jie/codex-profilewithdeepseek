---
name: S18 内容设计
type: generic
domain: execution
tier: L3
doc_status: active-ssot
status: ACTIVE
birth_ceremony_id: bc-s18-f964304b
birth_ceremony_date: '2026-05-02'
related:
- @@GENERAL_ROOT:win@@\control\registry\02-skill-catalog.md
- @@GENERAL_ROOT:win@@\assets\references\methodology\26_front-end-anti-patterns-and-product-thinking-SOP.md
- @@GENERAL_ROOT:win@@\assets\references\methodology\28_Modern-SaaS-UI-Aesthetics-Protocol.md
- @@GENERAL_ROOT:win@@\assets\references\architecture\schemas\frontend-page-plan.schema.json
description: 用户要求整理纪要、编写报告、制作方案文档、结构化内容时使用。

extends:
- @@GENERAL_ROOT:win@@\assets\rules\injection\skill-aop-prelude.md
- @@GENERAL_ROOT:win@@\assets\rules\execution.md
- @@GENERAL_ROOT:win@@\assets\rules\agent-constitution.md
- @@GENERAL_ROOT:win@@\assets\references\methodology\10_S-Tier-Execution-Discipline-Protocol.md
---
> **【S18 专属天条】**：开始执行前必须优先拉取 `@@GENERAL_ROOT:win@@\assets\rules\execution.md` 与 `@@GENERAL_ROOT:win@@\assets\references\harness\orchestration-manual.md` 铁律。TMP 模板引擎只管皮囊（样式和壳），本 S18 引擎负责抽走并在骨头里注入”矩阵逻辑”的骨髓。

# S18_内容设计 (Harness Content Architecture State Machine)

<context>

## 1. 终极防线与职责隔离
- **绝对必须做**：按生命周期（Lifecycle）、对象角色（M/P/S/W）将零散的 Markdown 碎纸提纯为结构化大盘。使用强类型的 L 层级（L0-L6）与四段式（场景/根因/解法/经验）拼装错题本或复盘。
- **绝对不准做**：直接手写 UI 前端代码（那是 S9 的活）；凭空制造未被验证的需求。

</context>

<rules>

## 2. 🧠 矩阵结构化解析状态机 (Harness Content Automata)

### [STATE: MATRIX_AXIS_ALIGNMENT] (一相：定位矩阵分类轴)
- 每拿到一堆碎稿或需求，第一秒钟必须做分类轴映射！
- **问自己**：这篇内容是属于哪个**生命周期**？（数据收集 -> 规划 -> 执行 -> 验收）。它归属于哪个**对象角色**？（是 P系调度的规划，还是 S系前线的战损，或是 M系大法官的判决）。
- 不把这篇内容的 X 轴（功能）和 Y 轴（时间）定死，绝不允许进行文案扩写！

### [STATE: CONTENT_TYPE_FORGING] (二相：内容骨架锻造)
- **拒绝流水账流水线**。根据刚才的矩阵坐标，选用对应的硬派骨架。
- **[方案型]**：必须包含 `WHAT（目标）` -> `HOW（架构决策）` -> `BLAST_RADIUS（爆炸半径）`。
- **[错题本/战败复盘型]**：必须强夯压出：
  - `**【🎬 场景】**`：在哪里触发的？
  - `**【🔍 根因】**`：为什么报的错（不是表面错误，是底层机制漏洞）？
  - `**【💊 解法】**`：怎么堵上的？
  - `**【💡 经验(Axiom)】**`：提炼成不超过 15 个字的公理。

### [STATE: INFORMATION_ARCHITECTURE_PLANNING] (内容信息架构规划)
> **铁律**：S18 先当信息架构师，再当写作者。报告、HTML 文案、看板文案必须先规划用户认知路径，再写正文。

- **Agent Constitution 基线**：先按 `@@GENERAL_ROOT:win@@\assets\rules\agent-constitution.md` 区分事实、认知、行动和证据。S18 负责把事实组织成读者能判断的内容，不负责把系统字段改写成看起来顺眼的字段清单。
- **Business Understanding**：确认读者是谁、读者要做什么决定、这份内容要把他带到哪个行动。开发报告要回答“是否通过、为什么、怎么修、证据在哪”，不是展示内部执行过程。
- **Information Architecture**：定义本页/本文的业务对象、信息角色和模块边界。结果、原因、影响、行动、收益、证据、上下文/日志必须分层。
- **Narrative Planning**：先写阅读路径，再写正文。默认路径：`结论 -> 原因 -> 影响 -> 行动 -> 收益 -> 证据 -> 详情`。
- **Decision-Claim-Evidence Building**：报告起稿固定按 `用户要做什么判断 -> 报告要建立哪些主张 -> 每个主张最少需要什么证据 -> 用最容易理解的形式解释 -> 完整数据按需下钻` 推进。先写主张，再选择证据；不得从 stats、字段清单或已有图表开始删减。
- **最少充分证据**：证据形式服从理解。解释原因优先写因果，表达用户态度优先引用代表性原话，表达差异优先用对比；只有量级、比例、阈值、趋势或不确定性会改变判断时才使用数字。采集完整性不等于正文展示完整性，未进入正文的统计仍保留在事实包、证据区或附录。
- **主张设计表**：`content_plan` 中每条核心主张必须写明 `claim / user_decision_change / evidence_refs / why_sufficient / explanation_form / drilldown_destination`。`why_sufficient` 说明为何这些证据已足够建立主张；`explanation_form` 从 `causal_explanation / representative_quote / comparison / metric / mixed` 中选择。
- **体验移交表**：内容需要转成 HTML/看板时，S18 还要形成 `experience_handoff`：`business_terms / relationship_evidence / primary_view_goal / long_content_refs / drilldown_volume`。它说明哪些内部术语要翻译、哪些主张需要流转/比例/公式/对比、首屏最重要的判断是什么、哪些列表或证据可能很长、完整数据量级如何下钻；S18 不决定卡片数量、固定像素、按钮高度或具体前端组件。
- **Component/Section Mapping**：如果内容会转成 HTML，必须同步给出组件或章节映射：Header、Summary、Root Cause、Action、Evidence、Detail。不要把字段清单改写成卡片清单。
- **出稿输入契约**：正式写作前必须形成 `content_plan`：`content_type / audience / user_goal / business_object / user_decisions / decision_claims / information_roles / reading_order / evidence_strategy / drilldown_strategy / experience_handoff`。纯文本交付可把 `experience_handoff` 标为 `not_applicable`；HTML/看板交付必须给出真实内容。没有主张设计的 `content_plan` 只是整理材料。
- **HTML 交付转换契约**：当用户要求 HTML、可视化研报、分析大盘或“有内容有布局”的最终报告时，必须把 `decision_claims` 转成 `page_plan.claim_contract`，把 `experience_handoff` 转成 `page_plan.experience_contract`，并对齐 `@@GENERAL_ROOT:win@@\assets\references\architecture\schemas\frontend-page-plan.schema.json`；体验构造参考 `@@GENERAL_ROOT:win@@\assets\references\methodology\28_Modern-SaaS-UI-Aesthetics-Protocol.md`，执行前自检使用 `@@GENERAL_ROOT:win@@\assets\references\methodology\27_frontend-agent-preflight-page-plan-template.md`。`analysis.json`、`page_plan.json` 和事实包只能作为机器中间件，不能替代可直接打开的 `.html` 用户交付物，也不能以“最终报告”名义单独移交。
- **门禁边界**：USER_VIEW_SANITIZER 只做合规兜底，不能替代内容规划。发现正文靠审计不断返工时，退回本状态重做信息架构。

### [STATE: USER_VIEW_SANITIZER] (三相：用户视角出稿闸)
> **设计哲学**：这不是"过滤坏内容"的筛子，而是"只放行有决策价值的内容"的闸门。一切规则都从一个测试推导——**陌生读者决策测试**：不了解内部实现的人看了这份输出，能直接做业务判断吗？以下所有子项都是这个测试的具体推导。

- **【SOP §0.0.3 正向生成主链】**：先用“用户判断—决策主张—最少充分证据—易懂解释—按需下钻”完成内容建设，再使用 SOP §6 的过滤、聚合、语境化、排序做末端校正。§6 不能替代主张设计，也不能把报告写作退化为“先堆数据再删减”。
- **【业务认知层总纲】**：面向用户的报告、页面文案和 HTML 内容不是数据字段清单，而是业务认知路径。出稿前必须先确定用户目标、业务对象、信息角色、认知路径和支撑证据，再组织段落、卡片或表格。
- **【信息角色先行】**：核心内容必须分清结果、原因、影响、行动、收益、证据、上下文/日志。不同角色不能平铺成同权条目；结论和行动必须高于采样、耗时、编号、原始字段。
- **【主张驱动内容】**：正文先建立用户需要的判断、原因与行动，再为主张选择最省认知的证据形式。数字只是可选证据；一句因果解释或一条代表性原话已足够时，不追加指标卡制造“统计完整感”。
- **【Header 边界】**：报告首屏 Header 只写身份、状态和一句话总结。背景说明、原因拆解、指标解释、技术定位和原始证据进入正文层级，不得塞进 Header。
- **【三问门禁】**：任何面向用户的报告、看板或 HTML 页面，必须让读者 3 秒内回答“我在看什么、它意味着什么、我下一步做什么”。如果正文只给数据、字段或内部编号，没有结论和行动指向，必须重写信息架构。
- **【问题驱动出稿】**：报告和页面不是字段清单。每个核心模块必须回答“发生了什么、是否异常、为什么、影响多大、下一步做什么”中的至少一个问题；字段名、步骤号、协议名、ID、P95/ms 等原始指标只能作为证据层支撑，不能抢占结论层。
- 出稿前执行陌生读者检查：不了解采集过程的人只看报告能否做业务判断；如果正文里出现工具名、路径、附件表、技术字段名或自述说明，必须重写后再交付。
- **【零中间态泄漏铁律】**：用户可见内容中**绝对禁止**出现以下中间态占位文本：「待分析」「待处理」「待生成」「分析中」「待 Agent 分析」「待深度分析」「待补充」「待完善」「后续补充」「暂未生成」「内容为空」「默认值」「示例数据」「测试数据」。展示的每一条内容**必须是已经 100% 完成处理的最终交付物**。
- **【SOP 禁止话术挂载】**：执行用户视角审计前，必须 `view_file` 物理读取 `@@GENERAL_ROOT:win@@\assets\references\methodology\26_front-end-anti-patterns-and-product-thinking-SOP.md` 第七章 7.1 节禁止话术表，作为全量扫描基准。不可凭记忆猜测。
- **【内容完成度回执】**：涉及前端页面、报告页、大盘、榜单、卡片、空状态或详情面板的可见文案时，必须输出 `FRONTEND_CONTENT_AUDIT_RECEIPT`，包含 `audited_surfaces`、`unfinished_content_violations`（必须为 0）、`data_porter_violations`（必须为 0）、`business_decision_ready`（true/false）、`verdict`。只要用户还不能直接拿来判断或行动，就不能标记 PASS。

### [STATE: FIRST_PRINCIPLES_DELIVERY_AUDIT] (四相：高质量交付审计)
- 面向业务决策的报告不能停在“名单 + 几个推荐理由”。必须从第一性目的反推结构：这份报告要帮谁做什么决定，对方拿到后要先联系谁、谈什么、为什么有证据、哪里不能下结论。
- 写作顺序固定为：事实库存 -> 证据信号 -> 业务场景 -> 行动建议 -> 证据边界。事实库存包括能拿到的全部有用信息；没有拿到的字段也要说清楚，不能悄悄消失。
- 每个关键结论必须能回指到具体事实：数量、排名、命中词、样本摘录、价格带、区域、用户原话或明确缺口。只有形容词、泛泛判断、口号式推荐，一律视为证据链断裂。
- 对调研型报告，必须把“观察到的事实”与“由事实推出的判断”分开写。推断可以存在，但不能冒充事实；数据不足时必须写“不足以支撑”，不能为了报告好看补结论。
- 如果用户指出报告没有第一性原理、没有吃透事实、没有服务真实业务目标，执行者必须先修正文，再把暴露出来的写作规则沉淀回 S18 或对应业务 Skill。不能只回复解释。

#### 用户向出稿回归清单
- [ ] 路由来源是否清楚：必须先由 W1 记录 catalog 解析结果，再进入目标 Skill；不能在写作入口里绕过 catalog 直接点名某个 Skill。
- [ ] Skill 原文是否已读：确认执行者已读取 catalog 解析出的目标 `SKILL.md`，并按该 Skill 原文处理写作任务。
- [ ] 正文是否面向读者：只保留业务判断需要的信息，不把工具名、文件名、附件用途表、内部字段或 Agent 自述写入可转发正文。
- [ ] 第一性目的是否贯穿：报告是否回答了“读者要做什么决定”，而不是只展示整理过的材料。
- [ ] 证据链是否闭合：关键结论是否能回指到具体事实、样本、数量、原话或明确缺口。
- [ ] 事实是否被充分消化：已采集的高价值信息是否进入了业务推导；没有使用的信息是否说明了原因或边界。
- [ ] 行动是否可执行：推荐对象、切入场景、沟通重点、风险边界是否清楚到可以直接进入下一步。

### [STATE: KNOWLEDGE_MOUNTING] (五相：向下沉静与孤儿防爆)
- 内容写好了，它就成了一份新文档。
- **孤儿极刑防线**：任何一份由 S18 产出的文档，不能成为孤魂野鬼。必须在结尾指明它是由哪一个 `index/`，哪一个 `Workflow`，或者哪一个 `Skill` 负责领养和索引（利用引用链接指向对应的主文件）。如果它无处挂载，说明内容设计是个伪命题，当场撤销（ABORT）！

</rules>

<template>

## 3. 📤 强制出炉契约 (I/O Contract)
一旦文章组装完毕并写盘，S18 必须抛出完全去感性化的 JSON 移交单：
```json
{
  "harness_metadata": { "phase": "S18_Content_Architecture", "status": "SUCCESS" },
  "content_matrix": {
    "lifecycle_stage": "P2_工程拆解层",
    "role_axis": "架构指导"
  },
  "structure_applied": "应用了[方案型]内容骨架，并完成了防爆孤儿挂签",
  "artifact_generated": ".agents/references/methodology/architecture-decomposition-protocol.md",
  "mounted_to": "由 S8_计划执行 挂靠 AOP 消费",
  "next_action": "PROCEED to W9"
}
```

## 4. 📦 脚本资产清单 (Script Asset Registry)

| 脚本 | 路径 | 用途 |
|:---|:---|:---|
| `block_registry.py` | `@@GENERAL_ROOT:win@@\assets\skills\S18_内容设计\block_registry.py` | 内容块类型注册与管理引擎 |
| `content_engine.py` | `@@GENERAL_ROOT:win@@\assets\skills\S18_内容设计\content_engine.py` | 矩阵结构化内容生成引擎 |

</template>
