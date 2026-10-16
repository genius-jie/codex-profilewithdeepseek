---
name: P2 技术架构与方案设计
type: generic
domain: planner
tier: L2
doc_status: active-ssot
status: active
birth_ceremony_id: bc-p2-7a4b1dcc
birth_ceremony_date: '2026-05-02'
related:
- C:\Users\Administrator\.agent\assets\references\architecture\engineering-governance-protocol.md
- C:\Users\Administrator\.agent\assets\skills\P2_技术架构与方案设计\resources\architecture_decision.md
- C:\Users\Administrator\.agent\assets\skills\P1_需求法典与标准大闸\SKILL.md
- C:\Users\Administrator\.agent\assets\skills\P2.5_开发任务排期与拆解\SKILL.md
- C:\Users\Administrator\.agent\assets\skills\P2.6_交付物独立评审\SKILL.md
- C:\Users\Administrator\.agent\assets\references\methodology\02_Exploration-and-Risk-Protocols.md
- C:\Users\Administrator\.agent\assets\references\methodology\07_Physical-Decomposition-Engine.md
- C:\Users\Administrator\.agent\assets\references\architecture\state-machine-event-pull-time-window-constraint.md
- C:\Users\Administrator\.agent\control\contracts\artifact-communication-contract.yaml
- C:\Users\Administrator\.agent\assets\workflows\W37_Human-facing Artifact Composition Workflow.md
- C:\Users\Administrator\.agent\control\registry\02-skill-catalog.md
- C:\Users\Administrator\.agent\assets\references\methodology\34_Frontend-Backend-Contract-Collaboration-SOP.md
- C:\Users\Administrator\.agent\assets\skills\P2_技术架构与方案设计\resources\method-composition.schema.json
- C:\Users\Administrator\.agent\assets\skills\P2_技术架构与方案设计\scripts\check_method_composition.py
description: |
  【触发场景】已有需求与验收基线，需要技术方案、架构设计、技术选型或能力扩张裁决。
  【不触发】需求目标尚未收敛，或只是无需架构判断的单点修复。
  【功能】用第一事实 POC、复用扫描和多维权衡，把需求翻译为可实施、可回退、可验证的 Tech Spec。
extends:
- C:\Users\Administrator\.agent\assets\references\methodology\08_Anti-Semantic-Fading-Protocol.md
- C:\Users\Administrator\.agent\assets\rules\architecture.md
- C:\Users\Administrator\.agent\assets\references\methodology\11_P-Tier-Execution-Discipline-Protocol.md
- C:\Users\Administrator\.agent\assets\rules\injection\skill-aop-prelude.md
---
# P2 技术架构与方案设计

## CURRENT_EXECUTION_OWNERSHIP

P2 是General Agent OS 通用的**方案与架构方法资产**，不是流程引擎或状态所有者。

- P2 只读消费 caller 提供的 PRD/需求基线；新版 Core 场景只读消费**同一 thread/checkpoint packet**中的 task、acceptance、stage evidence 与允许读取的项目事实。
- P2 不得创建第二状态，不得推进 checkpoint，不得改变 caller 的执行范围、Agent、工具、重试或完成裁决。
- P2 输出 Tech Spec、POC evidence、ADR、风险与 handoff proposal，全部交回 caller；Core 是否保存、评审、恢复或推进，只由 Core 决定。
- standalone 场景必须有显式 requirement package 和当前项目证据；缺关键事实时只输出 `needs_probe` 或 `needs_human_decision`。
- W1 只建议是否需要 P2，不为 P2 初始化门禁，也不替 P2 做架构判断。

<context>

## 1. 目标与职责

P2 把“做什么”翻译成“为什么这样设计、模块如何协作、如何证明可行、失败时怎么退”。P2 负责技术取舍、边界、数据与接口、部署、观测、测试策略和回退设计；不负责任务排期、业务实现或独立签发 PASS。

</context>

<rules>

## 2. 七步架构方法

### 2.1 输入读验与追溯

确认目标、acceptance、第一事实、未知、不可改变约束与 Out of Scope。每个架构决定必须能回指需求或现场证据；没有需求基线时不凭空选型。

### 2.2 复用与能力边界扫描

按以下顺序检查：框架原生能力 → 成熟项目/高质量 starter → 现有 Skill/SOP → 外部组件 → custom code。能力缺口只形成候选和取舍，不由 P2 自行扩权或创建新能力。

### 2.3 第一事实 POC

- 对关键外部依赖、API、数据源、库版本和部署宿主做真实探针；优先官方文档和可执行 CLI/最小脚本。
- POC 按 `连通性 → 数据可达 → 目标交付` 分级，只有拿到可被下游消费的目标产物才可判 ready。
- 从最终输出字段逆推 Nutrient Checklist，逐维验证数据源能否供给；缺口标记为 `NUTRIENT_GAP`。
- 每个微型 POC 立即记录命令、输出、产物路径、结论和限制。证据留在当前项目，不回写General Agent OS Skill。

Canary / POC PASS 只证明技术可行。若准备将新机制采纳为生产 Runtime、正式入口或长期资产，必须按 `resources\architecture_decision.md` 的“铁律 4.1：Canary 可行性不等于生产采纳”完成双轨复审；结论可以是 `simplify` 或 `observation_only`，不自动形成新的 Change Intent 或实施授权。

### 2.4 多维取舍

候选方案至少比较：目标契合、质量、成本与时间、团队/现有能力、风险与可逆性、扩展性、爆炸半径。推荐项必须有事实和证伪动作；复杂商业取舍保留 `needs_human_decision`，不替用户拍板。

### 2.5 架构图纸

#### 显式采用的方法组合检查

当方案组合多个工程方法，caller 可使用本 Skill 的 `scripts/check_method_composition.py` 中纯函数 `check_method_composition(payload)`；它检查 caller 显式提供的声明，不发现、选择或执行方法。输入形状由 `resources/method-composition.schema.json` 定义，方法声明的唯一源是各自资产 YAML 头部 `method`；不新建独立 manifests 或中心清单。

- 先分清目标来源、建模、体验、内部结构、部署、交互、契约、验证、协作、执行组织、交付与横切质量。分类不产生新驱动模式，也不意味着每个维度必须选一个方法。
- caller 负责显式读文件、拒绝重复 YAML 键、核对身份及版本、核对事实与证据来源，再传入结构化数据。辅助函数只有标准库依赖，零文件/网络/进程 I/O，不读其他 OS 状态。
- `selected` 只接收当前 caller 已明确采用的方法；`candidates` 是附当前理由的候选。依赖闭包仅形成 `proposed`，不得与 `selected` 合并成活动集合。检查器不签发批准；新采用仍交现有方案评审。
- `facts` 区分 `confirmed / inferred / unknown`。确认和推断均须来源；推断与未知均不能满足强制条件。缺事实不视为假；`exists: false` 只对已确认值为 null 成立。
- `scope` 是明确的实际边界名，普通名称精确匹配，`*` 表示明确的全项目声明，关系中的 `$scope` 表示所属方法范围。一个边界的契约不能填补另一边界的义务；同一边界可同时具有多类契约。
- 方法关系分为 method、artifact、evidence、capability；方法依赖要求精确版本。必要关系、任选关系、建议、冲突、替代分别表达，不把每一项产物或证据都变成 Skill。`supersedes` 只表示给定版本与范围的替代建议，不删除显式项。
- 条件只允许 `all / any / eq / in / exists`。条件、依赖和冲突不得夹带任意表达式、脚本或硬编码的业务复杂度策略。
- 可选项没有当前理由、不适用或冲突时可从建议中裁剪，明确采用项不得静默删除。候选仍需设计决定；候选自身缺口仅作建议诊断，不阻断已有效的采用组合。
- `stage` 使用通用语义 `design / plan / implement / review / verify / deliver`，由调用方映射到自己的阶段。`acceptance.required_evidence` 在 verify/deliver 核对；`host.requires` 在 implement/review/verify 核对，能力声明本身不授予工具。未给 stage 只检查基础组合义务，不能当作完成验证。
- 结果 `valid` 只证明所给声明及范围内没有硬缺口；`incomplete` 表示必要事实、产物、采用决定或证据尚缺；`invalid` 表示输入/声明无效或组合冲突。三者均不是独立生产采纳、运行成功或验收裁决。`available` 是 caller 提供的来源断言，不是辅助函数独立验证的证据。

输入示意（实际声明由 caller 从唯一资产加载，不在项目复制方法正文）：

```json
{
  "schema_version": "method-composition.v1",
  "stage": "design",
  "methods": [],
  "selected": [{"id": "frontend-backend-contract", "version": 1, "scope": "orders-http"}],
  "candidates": [],
  "facts": [
    {"id": "has_contract_boundary", "scope": "orders-http", "status": "confirmed", "value": true, "source": "approved-spec#boundary"},
    {"id": "interaction_kind", "scope": "orders-http", "status": "confirmed", "value": "http", "source": "approved-spec#boundary"}
  ],
  "available": [
    {"kind": "artifact", "id": "user-scenarios", "scope": "orders-http", "source": "approved-scenarios"},
    {"kind": "artifact", "id": "fact-sources", "scope": "orders-http", "source": "source-probe"},
    {"kind": "artifact", "id": "contract-definition", "scope": "orders-http", "source": "project-contract"},
    {"kind": "artifact", "id": "http-contract", "scope": "orders-http", "source": "project-openapi"}
  ]
}
```

示意中的空 `methods` 必须由 caller 用实际声明填入；直接传入会被判为悬空引用，不是可批准样例。

检查后，把事实引用、逐边界契约、采用方法/版本/范围/理由、延后项、阶段资源和证据义务写进当前 Tech Spec。采用 Core 的项目可保存在既有 `results.p2.data.composition_decision`；它不复制 request 模式、任务执行者或权限，也不变成流程状态。P2.5 通过自己现有任务字段承接；资源冻结与版本恢复由原 caller 负责，不由本 Skill 重算历史。

caller 明确采用前后端契约协同时，读取 `assets/references/methodology/34_Frontend-Backend-Contract-Collaboration-SOP.md` 并将配套 `assets/references/methodology/templates/frontend-backend-contract-alignment.md` 纳入本项目 Tech Spec：先对齐用户场景、事实来源、共同契约与 Owner，再定义首个真实链路和变更/回滚。它跨两种驱动模式复用，不增加模式、门禁或固定技术栈；本 Skill 不隐式调用执行能力。

Tech Spec 依据任务类型选择最小充分章节，通常包括：

1. 系统边界、模块拓扑、核心时序和调用链；
2. 数据模型、API/消息契约、字段级需求追溯；
3. 错误分类、超时、幂等、降级与回滚；
4. 运行节点、部署宿主、端口/协议和服务托管；
5. 配置分层、观测、日志、告警和恢复；
6. 测试策略、fixture 来源、集成边界与性能基线；
7. 人类可见交付物的信息架构、视觉/内容规格和触达方式；
8. 关键 ADR、复用来源与 POC evidence refs。

### 2.5.1 物理落盘与文件生命周期设计（双轨必选）

P2 设计 LangGraph 流水时，必须同时交付一份**物理资产方案**。它与流程状态是两条相互引用但不互相替代的轨道：

- **逻辑状态轨**：`request`、`results`、`feedback` 和 LangGraph checkpoint 只表达需求、流程位置、当前结果与反馈；不得把文件目录、临时文件清单、清理标记或第二账本塞进 `PipelineState`、checkpoint 或 SQLite。
- **物理文件轨**：文件系统只保存有明确 Owner、直接 Consumer、用途和生命周期的业务产物、验证证据或人工可读交付物；文件路径是结果引用，不是流程状态来源。Core 不因文件存在就推断阶段完成，也不从目录扫描恢复流程。

Tech Spec 必须逐项写清以下内容，不能只写“保存到项目目录”或“运行结束后清理”：

1. **目录树与边界**：以 `project_root` 为根，区分 `.automation-core/` 运行文件、临时工作区、候选稿、正式交付物、验证证据和归档；目录位置首先由**直接消费者身份与 Owner**判定，再由生命周期和访问边界细分，阶段名只能作为组织层标签，不能仅凭文件名或阶段名决定落点。临时目录也必须带 `<consumer-id>`；声明每个目录的 Owner、直接 Consumer、允许的文件类型，以及禁止在项目根或父目录散落生成文件。
2. **命名规则**：文件名只承担稳定、可读的标识，使用小写 `kebab-case` 或项目既有规范；需要关联运行时才使用受限的 `thread/stage/attempt` 标识，不把时间戳、随机串或模型输出直接当作唯一命名规则。文件名不能反向决定目录位置；同一目录不得同时放不同生命周期的文件。
3. **写入方式**：先写同一目标目录下的临时文件，完成内容校验后原子替换；失败留下的 `.partial`、锁文件和下载缓存必须有明确清理动作，不得伪装成正式产物。跨目录移动、覆盖、改名和并发写入的幂等语义要写进方案。
4. **生命周期表**：至少区分 `ephemeral`（单次调用/单个 packet 后删除）、`candidate`（等待评审期间保留）、`accepted`（通过评审且有消费者后保留）和 `archive`（只读审计需要时保留）。每类写明创建条件、晋级条件、删除/归档触发者、失败恢复和最长保留边界；没有消费者的中间文件默认不落盘。
5. **回退与重做**：同阶段返工不得把每一轮草稿无限累积；当前候选只保留评审所需版本，旧稿只有在验收或审计明确需要时才进入只读归档。回到上游时，物理产物处理必须与 `revision_reference` 的非权威语义一致，不能被旧文件反向当成当前结果。
6. **物理验收证据**：为目录存在性、路径边界、文件命名、原子写入、成功后的临时文件清零、失败清理、重启/恢复和归档可读性分别指定可执行检查。单次文件存在或单项测试通过，不等于生命周期闭环完成。

P2 应把上述设计写成 `results.p2.data.artifact_plan`：每项至少包含 `consumer_id`、`owner`、`purpose`、`path_prefix`、`filename_pattern`、`lifecycle` 和 `cleanup_trigger`。P2.5 只能继承这些字段并补充 `producer_task_id`；P3/P4 只允许对应 Producer 在声明目录和文件名模式内提交，P5 再核对每个绑定的持久化计划项都已 materialize，且不把 `ephemeral` 文件带入验收。

从零启动的新项目应在启动契约的 `request.acceptance.output_schema` 中把 `artifact_plan` 列为 P2 `data` 的必填字段；历史项目未声明该字段时只保留兼容路径，不由 P2 或 Runtime 猜测目录。

物理落盘方案还必须按 P2.6 的**双规记录**交付：

- **责任轨**：明确 Architecture 负责目录/边界与拓扑，Runtime 负责按既有入口执行写入和清理，Evidence 负责证明字节与生命周期事实，Control 负责需要人工确认的保留/归档取舍，Experience 只承接重复摩擦模式；任何角色不得越权替另一责任域建立状态或账本。
- **收敛轨**：说明复用了哪份目录 SSOT、现有写入/归档入口和验证能力，为什么不新增第二状态、Registry、Ledger、守护进程或全局 TTL；把“可行的清理机制”和“是否值得正式生产化”分开记录。

该节必须与 `docs/project-layout.md`（或消费者项目等价的目录 SSOT）和运行时契约保持一致。P2 只设计和交付规则，不在方案里凭空增加清理守护进程、第二状态库、全局 TTL 服务或旁路回执账本。技术上可行的清理机制与是否正式采纳仍按 P2 的双轨复审分别判断。

多 Agent 方案额外说明角色职责、数据传递、终止条件、失败边和为什么单 Agent/普通函数不足；不得因“看起来高级”而使用多 Agent。

### 2.5.1 Artifact Communication Contract 接入（条件性）

当 Tech Spec、架构说明、验收说明或交付说明由 Human 阅读并参与协作决策时，P2 在产出前读取并应用：

`C:\Users\Administrator\.agent\control\contracts\artifact-communication-contract.yaml`
Contract ID：`artifact-communication-contract.v1`

该 Contract 统一人类交付物的沟通语义；P2 只把它投影到技术方案，不在本 Skill 复制或另建一套表达规则。

当 caller 明确选择 `C:\Users\Administrator\.agent\assets\workflows\W37_Human-facing Artifact Composition Workflow.md` 时，W37 负责公开组合 Contract、Primary Producer、可选 S18、明确采用时的 M11 与已选验证能力。P2 在其中仅作为 Tech Spec / 架构说明的 Primary Producer；P2 不在 Skill 内直接调用 S18、M11 或验证能力，也不决定 Workflow 的顺序。未选择 W37 时，P2 继续按自身契约直接产出技术方案，不暗示任何隐藏组合。

Tech Spec 的 Contract 投影必须让读者直接找到以下信息：

```yaml
artifact_communication:
  contract: artifact-communication-contract.v1
  artifact_type: technical_spec
  audience: [architect, developer, operator] # 按当前任务增删
  intent:
    objective: "要实现或改变的能力，以及方案要解决的约束"
    decision_required: "当前需要 Human 决定的取舍；没有则明确为 none"
  human_first_sequence: [why, what, boundary, how, evidence]
  layer_separation: [human, engineering, machine]
  human_summary: "按 Contract 的 why → what → boundary → how → evidence 顺序说明；包含推荐方案、核心取舍、影响与风险"
  decision_points: "ADR、needs_human_decision、已选方案与尚未定案方案的位置"
  boundaries:
    included: "系统边界、已承接能力和实施范围"
    excluded: "非目标、约束、失败与回退范围"
  evidence_refs: "POC、ADR、需求追溯和关键事实引用"
  technical_detail_placement: "模块、字段、时序、配置、命令和机器契约置于深层章节、附录或独立 schema"
```

机器 schema、API Contract、Runtime State 和命令回执保留各自精确格式，不以人类正文替代。P5 在最终产品验收中只核验人类交付的沟通信息是否可定位，不为该 Contract 另设文风评分。

### 2.6 分片铸造与蓝队自审

长 Tech Spec 可以按拓扑、选型、数据、呈现/测试、错误/运维五类自然切片写盘回读。分片仅用于注意力和证据完整性，不是外部状态机；不得要求旁路状态文件或人类签章才能继续。

蓝队自审核对：

- P1 需求和字段是否 100% 有落位；
- 每条关键决定是否有证据；
- 实现约束是否可验证；
- P2.5 能否直接拆分；
- 未知、风险和人工决策是否诚实保留。

### 2.7 独立评审与交还

P2 只输出 `DRAFT_READY_FOR_P26_REVIEW`。由 caller 将 Tech Spec、当前 diff/文件、测试/POC 和 acceptance 交给 P2.6。P2 不自填独立 verdict；真实 verdict 返回后原样引用，再由 caller 决定是否进入 P2.5。

## 3. 输出契约

```json
{
  "method": "P2_ARCHITECTURE_AND_TRADEOFF",
  "status": "DRAFT_READY_FOR_P26_REVIEW",
  "checkpoint_binding": {
    "thread_id": "echo-if-provided",
    "checkpoint_id": "echo-if-provided",
    "source_checkpoint_id": "echo-if-provided"
  },
  "artifacts": {
    "tech_spec_ref": "...",
    "architecture_diagram_refs": [],
    "poc_evidence_refs": [],
    "adr_refs": [],
    "traceability_ref": "...",
    "artifact_communication_ref": {
      "contract": "artifact-communication-contract.v1",
      "artifact_type": "technical_spec",
      "audience": [],
      "intent": {"objective": "...", "decision_required": "...|none"},
      "human_summary_ref": "section-or-artifact-ref",
      "decision_points_ref": "section-or-artifact-ref",
      "boundaries_ref": "section-or-artifact-ref",
      "evidence_refs": [],
      "technical_details_ref": "deep-section-or-appendix-ref"
    }
  },
  "decision_readiness": "ready | needs_probe | needs_human_decision | rejected",
  "review_request": {"recommended_method": "P2.6", "verdict": "PENDING"},
  "handoff_proposal": {"recommended_next_method": "P2.5", "reason": "..."}
}
```

绑定字段只回显 caller 输入。`review_request` 和 `handoff_proposal` 是建议，不是运行命令、授权或状态跃迁。

## 4. 经验分层

项目 POC、日志和业务事实留在项目；仓库局部 SOP 留在 Specialized Agent OS；跨项目稳定原则只形成 `pending_human` 候选，经 General Agent OS W7/M4 人工采纳后才能更新资产。

</rules>

## LEGACY_CONTROL_ARCHIVE_ONLY

旧版 P2 曾依赖旧 D 的旁路状态、门禁会话、逐 Slice 外部签章和阶段跃迁脚本。它们不再属于General Agent OS P2 的活动契约，禁止执行或恢复；历史实现只保留在冷归档作审计证据。
