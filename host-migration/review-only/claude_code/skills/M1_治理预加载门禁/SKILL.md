---
name: M1 治理预加载门禁
type: gate
domain: meta-governance
tier: L1
doc_status: active-ssot
status: active
birth_ceremony_id: bc-m1skill-a3f8e2d1
birth_ceremony_date: 2026-05-01
last_verified: 2026-08-18
related:
- @@GENERAL_ROOT:win@@\assets\references\methodology\12_Document-Asset-Governance-Protocol.md
- @@GENERAL_ROOT:win@@\assets\references\methodology\03_Skill-Lifecycle-Protocols.md
- @@GENERAL_ROOT:win@@\assets\references\methodology\24_Semantic-Dedup-and-Single-Home-Protocol.md
- @@GENERAL_ROOT:win@@\assets\references\matrix\governance-protocol.md
- @@OPENCLAW_ROOT:win@@\.agents\index\02-child-knowledge-graph.md
- @@OPENCLAW_ROOT:win@@\.agents\orchestration\Langgraph\docs\scripts\verify-governance-hard-gate.ps1
- @@GENERAL_ROOT:win@@\assets\references\architecture\p-stage-handoff-contract-schema.md
- @@GENERAL_ROOT:win@@\assets\references\architecture\p-artifact-supersede-protocol.md
- @@GENERAL_ROOT:win@@\records\experience\evolution_candidates.md
- @@GENERAL_ROOT:win@@\control\guards\asset-admission\asset-birth-ceremony.py
- @@GENERAL_ROOT:win@@\records\evidence\birth-ceremony-registry.jsonl
- @@GENERAL_ROOT:win@@\control\registry\02-skill-catalog.md
- @@GENERAL_ROOT:win@@\assets\skills\M14_RAG证据感知\SKILL.md
- @@CORE_ROOT:win@@\docs\runtime-contract-template.md
- @@CORE_ROOT:win@@\src\pipeline\topology.py
- @@CORE_ROOT:win@@\src\pipeline\state.py
- @@CORE_ROOT:win@@\src\pipeline\runner.py
- @@CORE_ROOT:win@@\src\pipeline\__main__.py
description: 执行治理检查、预加载门禁校验时使用。

extends:
- @@GENERAL_ROOT:win@@\assets\rules\execution.md
---
# M1_治理预加载门禁 (Governance Preload Gate + 知识铁律)

> **架构定级**：本 Skill 是 Harness 引擎的元治理门禁（M系 G0 级），优先级高于任何具体治理 Skill。
> **触发铁律**：一旦命中关键词，必须先过本门禁，再做任何分析、命令执行或改码。
> **知识铁律**：本门禁同时承载3条知识治理铁律（唯一归属/护照完整/产物归位），违反即阻断。

---

## 1. 触发关键词

当任务描述、上下文或用户意图命中以下任一关键词时，**强制触发本门禁**：

| 类别 | 关键词 |
|:--|:--|
| 框架层 | LangGraph、AutoGen、OPA、OpenSpec、instructor、Pydantic |
| 阶段层 | P1、P2、P2.5、P3、P4、P2.6、W11、W1、W7、W9 |
| 治理层 | 治理流水线、审计门禁、澄清收敛、first-fact、产物落盘、governance-map |
| 知识治理层 | 知识库治理、去重、瘦身、唯一索引、唯一归属、frontmatter、护照、doc_status、文档降级、SSOT、知识图谱、沙盒自审计、升格提案、自审计协议、三管道注入、声明式注入、skill-rules-config、tool-constraints |
| 制度资产层 | Skill、技能、规则、rules、SOP、Workflow、提示词知识库、父级提示词、子级提示词、项目提示词、增删改查、CRUD、查询入口、双向注册、创建技能、删除技能、修改规则、查询文档、阶段间契约、supersede、schema versioning、传染规则、强关联发布 |
| 症状层 | 文档放哪、SOP散落、父子架构、知识图谱、阶段毕业、文档重复、产物散落、audit文件、状态漂移、state_drift、契约缺口、产物不同步 |

---

## 2. 门禁执行流程

### Step 1：必须按顺序读取这5份文档

| 顺序 | 文档 | 目的 |
|:--|:--|:--|
| 0 | `@@GENERAL_ROOT:win@@\control\registry\05-global-knowledge-graph.md` | 全局总入口，确认父级宪法层与三层域流转 |
| 1 | `@@GENERAL_ROOT:win@@\assets\references\methodology\12_Document-Asset-Governance-Protocol.md` | 三层归属法典，判断父级/子级/project/core-runtime |
| 2 | `@@OPENCLAW_ROOT:win@@\.agents\index\02-child-knowledge-graph.md` | **唯一归属注册表（§5）**，查知识门类归属，防止重复写法典 |
| 3 | `@@OPENCLAW_ROOT:win@@\.agents\index\03-langgraph-governance-map.md` | OpenClaw子级承接图，判定SOP与产物归属 |
| 4 | `@@OPENCLAW_ROOT:win@@\.agents\orchestration\Langgraph\docs\04_AGENT_PRELOAD_MANIFEST.md` | 治理预加载清单，确认完整必读序列 |

### Step 2：输出预加载回执（必须原样包含字段名）

```yaml
PRELOAD_RECEIPT:
  files: 
    - @@GENERAL_ROOT:win@@\control\registry\05-global-knowledge-graph.md
    - @@GENERAL_ROOT:win@@\assets\references\methodology\12_Document-Asset-Governance-Protocol.md
    - @@OPENCLAW_ROOT:win@@\.agents\index\02-child-knowledge-graph.md
    - @@OPENCLAW_ROOT:win@@\.agents\index\03-langgraph-governance-map.md
    - @@OPENCLAW_ROOT:win@@\.agents\orchestration\Langgraph\docs\04_AGENT_PRELOAD_MANIFEST.md
  why_this_task: <本次任务归属：parent / child / core-runtime，并给出一句理由>
  knowledge_domain: <本次任务涉及的知识门类，从02-child-knowledge-graph.md §5唯一归属注册表中查找>
  doc_status_plan: <本次将创建/修改的文档的doc_status：active-ssot / active-reference / historical-reference>
  sop_route: <本次将使用的SOP链路，按先后列出文件名>
```

### Step 3：追加阅读（按场景按需追加）

根据任务场景，按 `04_AGENT_PRELOAD_MANIFEST.md` §2 追加阅读：

| 场景 | 追加文档 |
|:--|:--|
| 图节点/路由/interrupt问题 | `@@OPENCLAW_ROOT:win@@\.agents\orchestration\Langgraph\docs\langgraph_sop.md` |
| OPA或硬规则争议 | `@@OPENCLAW_ROOT:win@@\.agents\orchestration\Langgraph\docs\OPA_sop.md` |
| LLM结构化输出、JSON不稳 | `@@OPENCLAW_ROOT:win@@\.agents\orchestration\Langgraph\docs\Instructor_Pydantic_sop.md` |
| AutoGen执行慢、终止不稳 | `@@OPENCLAW_ROOT:win@@\.agents\orchestration\autogen\docs\autogen_multi_agent_sop.md` + `@@OPENCLAW_ROOT:win@@\.agents\orchestration\autogen\docs\autogen_to_langgraph_runtime_sop.md` |
| 文档归档混乱 | `runtime_sop/01_治理文档流转与归档SOP.md` |
| 产物落盘路径问题 | 当前项目的 `project_root`、request artifact refs、显式交付目录或项目自有 manifest 契约；不得从旧仓布局推断统一目录 |
| **知识库去重/瘦身** | `02-child-knowledge-graph.md` §5（唯一归属注册表） + `24_Semantic-Dedup-and-Single-Home-Protocol.md` |
| **文档护照/frontmatter补全** | `12_Document-Asset-Governance-Protocol.md` + 本文件 §4 知识铁律 |
| **Skill/Rule/SOP/Workflow增删改查** | `references/matrix/governance-protocol.md` + `03_Skill-Lifecycle-Protocols.md` + `09_Asset-Governance-Audit-Protocol.md` |
| **audit文件逸出** | 当前项目显式 `project_root`、artifact/manifest 与父级 `verify-governance-hard-gate.ps1` 对应 GateProfile；不得从旧 D 猜默认目录 |
| **跨阶段路由变更** | `02-skill-catalog.md §8` + E Core `topology.py`/`state.py` 公共结构事实 + 当前 checkpoint 的只读 `automation-core inspect` 投影 |
| **阶段间交接契约/入口快照/contract_schema** | `references/architecture/p-stage-handoff-contract-schema.md` + `references/architecture/p-pipeline-schema-registry.md §2` |
| **产物版本supersede/证据锚定** | `references/architecture/p-artifact-supersede-protocol.md` + `11_P-Tier-Execution-Discipline-Protocol.md` |
| **沙盒自审计/升格提案** | `governance/evolution_candidates.md` 沙盒自审计协议区段 |
| **状态漂移/同态校验** | `p-stage-handoff-contract-schema.md §5` + `verify-governance-hard-gate.ps1` G9 |
| **语义召回/证据盲区/RAG检索** | `skills/M14_RAG证据感知/SKILL.md`（advisory-only 证据发现层） |

### 当前活动事实与旧 D 边界

- 父级治理是否通过，只以 `@@OPENCLAW_ROOT:win@@\.agents\orchestration\Langgraph\docs\scripts\verify-governance-hard-gate.ps1` 的显式 `GateProfile` 结果为准。
- 新 Automation Core 的公共结构事实只读自 `@@CORE_ROOT:win@@\src\pipeline\topology.py` 的 `NODE_NAMES/EXPLICIT_EDGES` 与 `state.py` 的 `PipelineState`；运行事实只读自 `runner.py` 的 `observe_pipeline/status_pipeline` 或 CLI `inspect` 返回的同一 checkpoint 投影。
- 旧 `@@OPENCLAW_ROOT:win@@\projects\automation-core` 内的 `verify-ssot-consistency.py`、`governance_graph.py`、`pipeline_gate.py` 仅属 `archive-only` 历史证据，不得执行、不得作为当前门禁依据，也不得在当前入口缺失时 fallback。

---

## 3. 门禁阻断规则

| 条件 | 动作 |
|:--|:--|
| 未输出 `PRELOAD_RECEIPT` | **阻断**，不得继续任何操作 |
| 任一必读路径不存在 | **阻断**，报 `PRELOAD_GATE_BLOCKED: <缺失路径>` |
| 任务不属于治理场景 | 不触发本门禁，按普通任务流程执行 |
| 用户明确跳过（如"直接改代码"） | 记录 `SKIP_RECEIPT` 并降级为事后补检建议；是否豁免以用户指令为准（Skill 不否决用户明确指令） |
| **新文档对应的门类在唯一归属注册表已有SSOT** | **阻断**，报 `UNIQUE_HOME_VIOLATION: <门类>已有SSOT <文件>，只允许写本地接入层(active-reference)` |
| **新建文档缺护照（字段口径以 birth-ceremony-protocol.md Step 1 为准：domain/tier/doc_status/related/birth_ceremony_id）** | **阻断**，报 `PASSPORT_INCOMPLETE: 缺<字段列表>` |
| **产物写出用户指定或项目声明的 `project_root`** | **阻断**，报 `ARTIFACT_PROJECT_BOUNDARY_VIOLATION: 产物必须留在当前项目边界` |
| **项目已有 artifact/manifest 契约却绕过它自创目录** | **阻断**，报 `ARTIFACT_CONTRACT_BYPASS: 必须遵守当前项目显式契约` |
| **audit 产物把旧仓统一路径当默认落点** | **阻断**，报 `LEGACY_ARTIFACT_PATH_FALLBACK: 应使用当前项目显式 evidence/artifact refs` |
| **Skill/Rule/SOP/Workflow增删改查未先走矩阵与唯一归属判定** | **阻断**，报 `GOVERNANCE_CRUD_GATE_UNEVALUATED: 必须先判定object_class/action/ssot_home/registry_update/blast_radius` |
| **知识图谱变更后未输出爆炸半径回执** | **阻断**，报 `BLAST_RADIUS_UNEVALUATED: 必须按05-global-knowledge-graph.md §6输出KNOWLEDGE_GRAPH_CHANGE_RECEIPT` |
| **W9 分层验证返回阻断级 FAIL** | **按所选 GateProfile 处置**，报 `GOVERNANCE_PROFILE_GATE_FAILED: 必须先修复 verify-governance-hard-gate.ps1 -GateProfile <profile> 的阻断项`；Constitution/SOP/prompt 语义类 Advisory 只报告 WARN，不默认阻断 |
| **升格提案未通过沙盒自审计或人审就落盘** | **阻断**，报 `EVOLUTION_CANDIDATE_UNEVALUATED: 必须按evolution_candidates.md沙盒自审计协议走完绿灯区/红灯区判定` |
| **强关联缺口被拆分发布** | **阻断**，报 `STRONG_COUPLING_SPLIT: 强关联缺口必须合并发布，禁止分拆` |
| **schema字段从可选升必填缺宽限期声明** | **阻断**，报 `SCHEMA_VERSIONING_INCOMPLETE: 必须声明since_version + grace_period + backward_compat` |
| **新资产落盘未走出生仪式** | **阻断**，报 `BIRTH_CEREMONY_SKIPPED: 必须先运行asset-birth-ceremony.py并签发出生证，或对已有资产运行--verify-only验证` |
| **修改doc_status未同步注册表声明** | **阻断**，报 `DOC_STATUS_DUAL_WRITE_VIOLATION: doc_status变更必须同步注册表声明，禁止只改frontmatter或只改注册表一侧` |
| **SOP示例与实际配置文件schema不一致** | **阻断**，报 `SOP_ACTUAL_DRIFT: SOP中的YAML/Rego/JSON示例top-level key与实际配置文件不一致，必须先对齐再放行` |

---

## 4. 为什么必须这样设计

> **根因**：Agent如果没有加载治理上下文，就会：
> - 不确认当前 `project_root` 与项目自有 artifact/manifest 约定，就把产物散落到无归属目录
> - 修改文档不更新知识图谱（导致引用断链）
> - 不知道三层归属铁律（把父级法典写成子级副本）
> - 绕过 request artifact refs 或项目显式交付契约，自创不被下游识别的目录
> - 项目明确要求 manifest 时漏写，导致 P2.6/W9 无法追踪产物
> - **同门类已有SSOT还写新法典**（导致知识重复散落，找知识越找越晕）
> - **新建文档不带护照**（domain/tier/doc_status/related缺失，图谱无法识别归属）
> - **audit产物硬编码输出到specs根**（每次管线跑完都污染根目录）
> - **新建或修改 Skill/Rule/SOP 后不登记图谱**（执行入口找不到，等于没上线）
> - **只按关键词盲查，不先走父级/子级索引**（查到旧文件、漏掉SSOT，后续判断全歪）

本门禁强制Agent在开工前**至少读完5份核心文档**，确保：
1. 知道任务属于哪个域（parent/child/core-runtime）
2. 知道当前用户或项目声明的 `project_root`
3. 知道当前 request artifact refs、显式交付目录和项目自有目录契约
4. 知道仅在项目契约要求时写 manifest，并让 P2.6/W9 可追踪
5. 知道 legacy 路径只读不写，新产物不得 fallback 到旧统一布局
6. **知道唯一归属铁律**：查02-child-knowledge-graph.md §5，同门类已有SSOT只写本地接入层
7. **知道护照铁律**：新文档必须有完整护照（字段口径以 birth-ceremony-protocol.md Step 1 为准）
8. **知道产物归位铁律**：audit 产物必须位于当前项目边界并引用当前显式 evidence/artifact 契约，不能硬编码旧仓目录
9. **知道CRUD总闸**：Skill/Rule/SOP/Workflow 的增删改查都必须先判矩阵坐标、唯一归属、父子承接和双向注册
10. **知道KG契约边界**：知识图谱契约只管“阶段间交接面的必须字段”，不穷举代码内部参数（判例边界见 p-stage-handoff-contract-schema.md §0）
11. **知道schema versioning**：schema 字段从可选升必填时必须声明 since_version + grace_period + backward_compat；宽限期内旧产物 WARN only，宽限期后 FAIL
12. **知道升格自审计**：evolution_candidates.md 中的提案 72 小时无人处理时，Agent 必须按沙盒自审计协议执行自审，绿灯区可自审通过直接落盘
13. **知道出生仪式**：新治理资产落盘必须走 asset-birth-ceremony.py 出生仪式，签发 birth_ceremony_id 并写入登记簿；未签发出生证的资产不允许存在（G10.4 校验）
14. **知道降级路径**：出生仪式脚本不可用时退回 M2 手动清单，但不免除出生证义务——脚本恢复后必须补跑
15. **知道doc_status双写铁律**：修改任何文档的doc_status时，必须同步修改对应注册表声明（05-global-knowledge-graph / 02-child-knowledge-graph / 03-langgraph-governance-map），严禁只改frontmatter或只改注册表一侧。机器守门：父级 `verify-governance-hard-gate.ps1 -GateProfile Structural`；旧 D `verify-ssot-consistency.py` 仅作 archive-only 历史参考。

---

## 5. 三条知识铁律（口诀版）

> **铁律1 · 唯一归属**：同一个知识门类只能有一个SSOT户籍，已有SSOT的门类只许写本地接入层（active-reference），不许再写独立法典。
>
> **铁律2 · 护照完整**：每个文档/产物必须携带完整护照（字段口径以 birth-ceremony-protocol.md Step 1 为准），没护照的文档不允许存在。
>
> **铁律3 · 产物归位**：产物必须落在用户指定或项目声明的 `project_root`，并遵守当前 request artifact refs、显式交付目录或项目自有 manifest 契约；不得硬编码旧仓统一布局。

### 5.1 治理对象 CRUD 总闸

> 本节不新增“知识铁律”数量，而是把三条铁律落到所有治理对象的增删改查上。

任何 Skill / Rule / SOP / Workflow / Index / Methodology 的 `Create / Query / Update / Delete(Archive)` 都必须先输出内部判定：

```yaml
GOVERNANCE_OBJECT_CRUD_GATE:
  object_class: <Prompt-KB / Skill / Rule / SOP / Workflow / Index / Methodology / Artifact>
  action: <CREATE / QUERY / UPDATE / DELETE / ARCHIVE>
  ssot_home: <parent / child / project / core-runtime + 具体文件>
  prompt_knowledge_layer: <parent-agent / child-agents / project-core-runtime>
  parent_child_scope: <父级法典 / 子级承接 / 项目证据>
  registry_update: <需要更新的 skill catalog / asset register / knowledge graph / manifest>
  blast_radius: <需要同步的入口、索引、SOP、workflow、脚本>
```

缺任一字段，按 `GOVERNANCE_CRUD_GATE_UNEVALUATED` 阻断。

三层提示词知识库边界：

| 层级 | 可写内容 | 不可写内容 |
|:--|:--|:--|
| 父级 `.agent` | 跨项目通用 rules / skills / workflows / methodology / matrix | 单仓库 SOP、项目 PRD、运行证据 |
| 子级 `.agents` | 本仓库 orchestration、repo-local SOP、域规则接入层 | 父级法典正文副本、项目证据正文 |
| 项目/core-runtime `projects/<project>` | REQUIRED_READING、项目契约、运行证据、manifest、receipt | 全局提示词宪法、子级作战手册正文 |

## 6. 写后爆炸半径评估 (Post-Write Blast Radius)

> 门禁不只是"先读再干"，还要"写完查半径"。
> 当本次任务涉及知识图谱变更（新增/删除/归档门类、新增预加载文档、铁律变更、doc_status变更、文件迁移）时，
> 必须在交卷前执行以下流程，否则报 BLAST_RADIUS_UNEVALUATED 阻断。

### Step B1：识别变更类型

| 变更类型 | 触发条件 |
|:--|:--|
| 新增知识门类 | 在注册表中新增了一行 |
| 删除/归档知识门类 | 在注册表中删除或归档了一行 |
| Skill/Rule/SOP/Workflow CRUD | 治理对象被新增、查询固化、修改、归档、删除或迁移 |
| 新增预加载文档 | M1_治理预加载门禁 §2 必读列表变了 |
| doc_status变更 | 任何文档的doc_status字段被修改 |
| 文件迁移/改名 | 文件路径发生变更 |
| 铁律/阻断规则新增 | §3 或 §5 的规则被修改 |

### Step B2：按影响矩阵扫描下游

按 `05-global-knowledge-graph.md` §6.1 影响矩阵，扫描以下文件类别是否需要同步：

| 类别 | 扫描方法 | 必扫等级 |
|:--|:--|:--|
| **Workflows** | **W1/W7/W9/W11（父级+子级）是否引用旧路径或旧数量** | **🔴 必扫（2026-05-01升级：S27归档+路径迁移后漏扫Workflow导致4处断链的历史教训）** |
| Skills | rg -l "被变更关键词" --type md | 🟡 常规 |
| Indexes | 检查 02-skill-catalog / 01-asset-register / 02-child-knowledge-graph 是否引用旧内容 | 🟡 常规 |
| SOP/Manifests | 检查 04_AGENT_PRELOAD_MANIFEST 是否同步 | 🟡 常规 |
| CRUD门闸 | 检查 `governance-protocol.md`、`03_Skill-Lifecycle-Protocols.md`、M2、W1/W7/W9 是否同步 | 🟡 常规 |

> **Workflow必扫的根因**：Workflow是Agent执行的入口文件，W1路由发牌、W7知识回流、W9出口验收、W11合规审查——这些文件中的路径断链不会被运行时捕获，只会导致Agent跳过关键步骤。**路径迁移/技能归档/目录合并后，Workflow是第一级联波及面，不是"可选项"。**

> **技能重命名场景**：如果变更是技能改名，直接使用治本工具 `skill_rename_cascade.py` 一键级联（已含Workflow扫描 step6c）：
> `python .agent/tooling/skill_rename_cascade.py --old 旧名 --new 新名 --dry-run`

### Step B2.5：执行机器分层验证

知识图谱、预加载文档、唯一归属注册表、铁律或 P 级产物落盘规则发生变更后，必须先按 W9 的 G0-G20 分层验证矩阵选择 `GateProfile`，再运行：

```powershell
pwsh -NoProfile -File @@OPENCLAW_ROOT:win@@\.agents\orchestration\Langgraph\docs\scripts\verify-governance-hard-gate.ps1 -GateProfile <Advisory|Structural|Runtime|FrontendIA>
```

档位口径：

| Profile | 适用改动 | 处置 |
|:--|:--|:--|
| `Advisory` | Constitution、方法论 SOP、提示词语义、Skill/Workflow 说明性文字、Agent 思维模型注入 | WARN 和降级 FAIL 必须报告，但不阻断 |
| `Structural` | 知识图谱、预加载清单、注册表、`doc_status`、W1/W7/W9/M1、产物落盘规则 | FAIL 阻断 |
| `Runtime` | LangGraph/W9/P-stage runtime、Builder/Renderer、OPA、schema、handoff、控制平面 | FAIL 阻断 |
| `FrontendIA` | IA Contract、前端生成器、页面/报告正式入口、P2/P2.5 traceability、frontend reviewer | FAIL 阻断 |

判定规则：

| 输出 | 处置 |
|:--|:--|
| `FAIL > 0` | 按所选 profile 的阻断口径处置；`Advisory` 不默认阻断，其他 profile 立即阻断 |
| `WARN > 0` | 可继续，但必须写入 `KNOWLEDGE_GRAPH_CHANGE_RECEIPT.remaining_stale` 或说明为何不阻断 |
| `PASS` | 允许进入人工回执 |

`Full` 只保留为显式全量兼容档，不作为 Constitution/SOP/prompt 语义改动的默认值。如果有落盘式回执文件，追加 `-ReceiptPath <receipt.yaml>` 验证回执字段完整性。

### Step B3：输出变更回执

```yaml
KNOWLEDGE_GRAPH_CHANGE_RECEIPT:
  change_type: <新增门类 / 删除门类 / 新增预加载文档 / doc_status变更 / 文件迁移 / 铁律新增>
  changed_file: <被变更的文件绝对路径>
  blast_radius:
    skills_affected: [<受影响的skill文件列表>]
    indexes_affected: [<受影响的index文件列表>]
    workflows_affected: [<受影响的workflow文件列表>]
    sops_affected: [<受影响的SOP文件列表>]
  sync_completed: <true / false>
  remaining_stale: [<未能同步的文件列表，附原因>]
```

## 7. 一句话总结

> **先读再干，不读就拦。查表再写，重复就挡。增删改查，先过矩阵。契约只管交接面，不管穷举。升格先自审，强关联必合批。带护照才能入库，按当前项目边界与显式 artifact 契约落盘。写完查半径，不查不交卷。改doc_status必须双写注册表，严禁只改一侧。**
> 没输出 `PRELOAD_RECEIPT`，不许碰任何代码或文档。违反铁律1/2/3任一条，立即阻断。治理对象 CRUD 未输出 `GOVERNANCE_OBJECT_CRUD_GATE` 不许落盘。升格提案未过沙盒自审计不许落盘。schema 必填项缺宽限期声明不许落盘。W9 分层验证有阻断级 FAIL 不许交卷；Constitution/SOP/prompt 语义类默认 Advisory，只报告不硬拦。知识图谱变更后没输出 `KNOWLEDGE_GRAPH_CHANGE_RECEIPT`，不许交卷。doc_status 变更未同步注册表，不许交卷。
