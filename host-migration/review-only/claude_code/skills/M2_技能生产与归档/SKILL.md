---
name: M2 技能生产与归档
type: generic
domain: meta-governance
tier: L2
doc_status: active-ssot
status: active
birth_ceremony_id: bc-m2-d7f9b977
birth_ceremony_date: '2026-05-02'
related:
- @@GENERAL_ROOT:win@@\assets\references\methodology\20_Legacy-Node-Name-Map.md
- @@GENERAL_ROOT:win@@\assets\skills\M2_技能生产与归档\cases\m3-compatibility-review-sample-advanced.md
- @@GENERAL_ROOT:win@@\assets\skills\M2_技能生产与归档\cases\m3-compatibility-review-sample.md
- @@GENERAL_ROOT:win@@\assets\skills\M2_技能生产与归档\cases\skill-archiving-governance.md
- @@GENERAL_ROOT:win@@\assets\skills\M2_技能生产与归档\cases\skill-description-quality-sample.md
- @@GENERAL_ROOT:win@@\assets\skills\M2_技能生产与归档\references\CLAUDE_MD_TESTING.md
- @@GENERAL_ROOT:win@@\assets\skills\M2_技能生产与归档\references\EXAMPLES_TEMPLATE.md
- @@GENERAL_ROOT:win@@\assets\skills\M2_技能生产与归档\references\REFERENCE_TEMPLATE.md
- @@GENERAL_ROOT:win@@\assets\skills\M2_技能生产与归档\references\SKILL_TEMPLATE.md
- @@GENERAL_ROOT:win@@\assets\skills\M2_技能生产与归档\references\Skill工厂_三件套生成.md
- @@GENERAL_ROOT:win@@\assets\rules\skill-execution-guards.md
- @@GENERAL_ROOT:win@@\control\registry\02-skill-catalog.md
description: 创建新技能、管理技能生命周期、归档技能时使用。

  【不触发】普通业务代码实现、纯内容润色、非 Skill/Rule/SOP/Workflow 资产变更不要用。

  【功能】提示词外围产物审查官。负责审查、治理并归档 Skill、Workflow、Rules 等系统架构护城河资产。
extends:
- @@GENERAL_ROOT:win@@\assets\rules\architecture.md
- @@GENERAL_ROOT:win@@\assets\references\matrix\governance-protocol.md
- @@GENERAL_ROOT:win@@\assets\references\methodology\03_Skill-Lifecycle-Protocols.md
- @@GENERAL_ROOT:win@@\assets\references\methodology\09_Asset-Governance-Audit-Protocol.md
- @@GENERAL_ROOT:win@@\assets\rules\injection\skill-aop-prelude.md
---
> AOP 横切约束（M11 文风/M12 分块/文件编辑微创）统一挂载自 @@GENERAL_ROOT:win@@\assets\rules\injection\skill-aop-prelude.md（本文件不复制正文）。

> **【架构定级声明】**：本 Skill 是 M 级元组件，掌管系统的全域组件繁育库。
# M2_技能生产与归档 (全栈合并槽)

<context>
## 1. 目标与边界
本车间负责创作、评估与修缮所有微内核 Skill、Rule、Workflow 与 SOP 资产，以及接手处理外面送来的技能配置。
- **它负责**：查重拦阻重复造车、精简主逻辑、剔除外部脚本内的相对路径、剥离百科内容与冗余指令至 `references/` 目录；执行 11-Kernel 规范定级归档；判断经验是否有资格升格为 Rule。
- **它绝对不负责**：无视现成底座，盲目堆砌规则废话；把单次事故直接升格成全局 Rule。
- **【S22/M9 分工声明】**：SKILL.md 的**结构治理**（YAML 护照、拆合归档、目录归属）归 M2。`<rules>/<context>` 内的**提示词语义优化**归 `S22_提示词工程治理`。技能**产后运行时巡检**归 `M9_红队审计`。
- **【CRUD 管辖声明】**：凡涉及 Skill / Rule / Workflow / SOP 的新增、查询、修改、归档、删除，都先归 M2 判定对象类型、动作类型、唯一归属、命名空间与双向注册需求；删除和全域清理再移交 M5 终裁。

</context>

<rules>
## 2. 🧠 强制自动机流程 (Harness State Machine - OpenSpec Artifact Graph 约束)
> **铁律**：必须严格遵循 OpenSpec 的 Artifact Graph (DAG 依赖图) 引擎机制，所有对技能的新建、查询、修改、归档、删除与外部引入必须顺序吃透并走完以下物理隔离卡点，绝不跳步！
> 引入修改时，强制使用 OpenSpec Delta Spec (ADDED/MODIFIED/REMOVED/RENAMED) 四级增量原子操作，保证历史可追溯且无冲突。

### [STATE: GOVERNANCE_OBJECT_CRUD_GATE]
- **先声明动作**：所有输入必须先归类为 `CREATE / QUERY / UPDATE / ARCHIVE / DELETE`。未归类不得读写任何制度资产。
- **先判矩阵**：读取 `references/matrix/governance-protocol.md`，输出 `object_class / action / ssot_home / prompt_knowledge_layer / parent_child_scope / registry_update / blast_radius`。缺任一字段，判定 `GOVERNANCE_CRUD_GATE_UNEVALUATED`。
- **Query 不是随便搜**：查询 Skill、Rule、SOP、Workflow 时，必须按 `05-global-knowledge-graph -> 02-child-knowledge-graph -> 02-skill-catalog/00-domain-catalog -> 具体文件` 的顺序定位。`rg` 只能作为索引之后的交叉验证，不能替代 SSOT 路由。
- **Skill 必须带命名空间**：遇到 `S24`、`S15` 等编号或同名 Skill 时，必须写出完整物理路径或明确 `parent-agent / child-agents`，严禁只凭编号派单。
- **Create 先查重**：新增前必须查父级 skill catalog、子级 domain catalog、知识图谱唯一归属表和同类目录。已有 SSOT 时只能新增本地接入层或 related 引用，不得再造新法典。
- **Rule 升格先定层**：经验进入 Rule 前，必须判定它属于父级公共 rule、仓库中立入口、子级 profile、case/reference 还是项目证据；不满足稳定、高频、跨场景、运行时必要的经验，不得升格为 Rule。
- **Update 先读继承链**：修改前必须顺着 `extends` 与 `related` 读直接上游和下游，使用 OpenSpec Delta Spec 的 `MODIFIED` 原子操作描述改动，并更新所有入口索引。
- **Archive/Delete 先断链审计**：删除或归档前必须全域搜索引用，优先改为 `doc_status: historical-reference` 或 `status: archived`；只有用户明确要求物理删除且 M5/W9 通过断链审计，才允许真正删除。

### [STATE: 查重与防撞车]
- **扫描重造轮子**：新建或引入前，必须调用 `list_dir` 查重，或核对 `control/registry/02-skill-catalog.md`。确认存在同功能组件后，立即通报阻断，严禁重复造车。

### [STATE: 起草去敏与剥离]
- **起草新技能**：检查框架底层包支持度。严禁在 `SKILL.md` 内堆砌知识白皮书和长长检查单。知识类内容必须剥离至 `references/` 目录或对接全局库。
- **收编外来技能**：剔除 `npm install` 等环境依赖及相对路径。强制替换为跨环境运行支持的绝对路径。
- **降维强退防线**：处理超大文件时，必须调用 `M12_大文件分块读取` 精确扫描，严禁使用摘要推断。

### [STATE: 拆合判定与归属权划分]
- **拆分与职责卡点**：审计核心功能成分。严禁混合代码检查、运行路由与知识字典（违规混装）。强制执行单一功能点原则：知识入 `references`，代码入 `scripts`，路由转归 `W1` 调度。
- **管辖权分配**：通用型 Python 动作与 Prompt 控制器归入全域 `.agent/assets/skills/`；OpenClaw 仓库专属业务流组件与调度配置归入 `@@OPENCLAW_ROOT:win@@\.agents\`；项目事实、receipt 和运行证据归入 `projects\<project>\docs` 或 `docs\specs`。

### [STATE: 物理落盘与发通关证]
- **出站扣章**：对照官方 `skill-frontmatter-template.md` 的 YAML 模板骨架验明正身。Description 标签栏绝不可含有流程命令。
- **双向注册扣章**：新增或修改 Skill / Workflow / Rules / SOP 后，必须运行 `python @@GENERAL_ROOT:win@@\control\guards\asset-admission\asset-birth-ceremony.py --input ceremony_input.json` 执行资产出生仪式并输出出生证。若脚本不可用，退回手动清单：必须同步检查父级 `control/registry/02-skill-catalog.md`、`control/registry/01-asset-register.md`、子级 `00-domain-catalog.md`、`02-child-knowledge-graph.md`、相关 `related/extends` 反向指针。只写文件不登记，视为未上线。
- **基因注入：上下游血缘锚定 (Traceability)**：在起草新 Skill 的 `I/O Contract (输出格式契约)` 时，必须强制约束该 Agent 在未来执行并输出业务包裹时包含 `Source Trace / 凭据溯源` 的挂载，以从新兵源头防堵系统的孤岛断代症。
- 🚨 **P 级多步骤纪律校验**：如果 P 级 Skill 含多个顺序步骤，按 `references/p-level-gate-protocol.md` 检查调用方状态归属、物理回读、风险中断、独立复核与无旧实现 fallback。不得为了让 Skill“可运行”而自建 `pipeline-state`、任务生命周期或第二控制面。
- 输出具体的安家物理路径，转接给 `W9_出口验收` 做最终入库。

</rules>

<template>
## 3. 标准协议输出出口 (I/O Contract - OpenSpec Template)
无论由于触发了新建、导入还是防重名拦截，只要是在编写内部约束/I/O模版，都必须向控制台与下游输出标准 JSON（特别注意必填的 `source_trace` 血缘锁）：
```json
{
  "harness_metadata": { "phase": "M2_Creator_Archiver", "status": "COMPLETED_OR_FAILED" },
  "crud_gate": {
    "object_class": "Skill | Rule | Workflow | SOP",
    "action": "QUERY_OR_CREATE_OR_UPDATE_OR_ARCHIVE_OR_DELETE",
    "ssot_home": "parent | child | project | core-runtime + absolute path",
    "prompt_knowledge_layer": "parent-agent | child-agents | project-core-runtime",
    "registry_update": ["index/02-skill-catalog.md", "index/01-asset-register.md", "child domain catalog or graph"]
  },
  "cognitive_diagnosis": "已剥离多重职责并压实主状态机，已净化外部诱导陷阱包",
  "execution_actions": [ { "target": "绝对路径/SKILL.md", "action": "QUERY_OR_CREATE_OR_UPDATE_OR_ARCHIVE_OR_DELETE" } ],
  "source_trace": { "upstream_requirement_ref": "必须注入此血缘基因约束，以要求新 Agent 产出时携带父级依据" }
}
```

</template>

<rules>
## 4. 📦 引用清单与防踩坑大盘 (Scripts & References)
**如果觉得不确定，立马去调同目录下的说明书抄作业：**

- **防发散校验表**：去查阅 `references/planner-anti-hallucination-audit.md`
- **做拆分与合并的裁决图**：查阅 `references/skill-split-or-merge-decision.md`
- **查看真实的红黄牌打分判例**：`cases/skill-authoring-governance.md` 与 `cases/skill-classification-boundary-sample.md`
- **外来包归航指南**：查阅 `templates/reports/skill-archiving-checklist.md`
- **P 级多步骤纪律协议**：`references/p-level-gate-protocol.md` — 检查调用方状态、回读证据、风险中断、独立复核和控制面边界。
- **外接脚本验证清单**（供在系统验证时手动传参）：`scripts/quick_validate.py`, `scripts/package_skill.py` 等指令。
- **治理硬门禁脚本**：`@@OPENCLAW_ROOT:win@@\.agents\orchestration\Langgraph\docs\scripts\verify-governance-hard-gate.ps1` — 当 CRUD 影响知识图谱、索引、W1/W7/W9、M1 或阻断规则时必须运行；FAIL 不得交卷。
</rules>

<template>
</template>
