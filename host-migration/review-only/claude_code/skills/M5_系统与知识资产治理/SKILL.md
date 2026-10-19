---
name: M5 系统与知识资产治理
type: generic
domain: meta-governance
tier: L2
doc_status: active-ssot
status: active
birth_ceremony_id: bc-m5-1b560f3b
birth_ceremony_date: '2026-05-02'
related:
- @@GENERAL_ROOT:win@@\control\registry\02-skill-catalog.md
- @@GENERAL_ROOT:win@@\assets\skills\M5_系统与知识资产治理\references\治理状态机细则.md
- @@GENERAL_ROOT:win@@\assets\skills\M5_系统与知识资产治理\references\九大检查项.md
- @@GENERAL_ROOT:win@@\assets\skills\M5_系统与知识资产治理\resources\m5报告JSON模板.md
description: '【触发场景】由后置清理任务(W11)、出口验收(W9)或定时的自动巡山打扫唤醒。

  【不触发】单文件小修、无需全域清扫或归档裁决的任务不要用。

  【功能】作为 Agent 系统的治理与清理执行器 (Garbage Collector)。负责全域扫描提取闲置内容、合并互相矛盾的执行规则、执行物理清除与状态重置。'
extends:
- @@GENERAL_ROOT:win@@\assets\rules\execution.md
- @@GENERAL_ROOT:win@@\assets\rules\script.md
- @@GENERAL_ROOT:win@@\assets\references\methodology\09_Asset-Governance-Audit-Protocol.md
- @@GENERAL_ROOT:win@@\assets\references\methodology\30_OpenSpec-Framework-Analysis.md
- @@GENERAL_ROOT:win@@\assets\rules\injection\skill-aop-prelude.md
---
> **【架构定级声明】**：本 Skill 是 Harness 引擎的治理中枢（M 级 generic 主模块）。
> **【AOP 横切依赖】**：严禁在未拉起 `control/orchestration/W1_前置思考.md` 的前提下随性起步删改架构。任何重写与删除动作必须严格遵守 `rules/execution.md` 的最高优先级规则。
> AOP 横切约束（M11 文风/M12 分块/文件编辑微创）统一挂载自 @@GENERAL_ROOT:win@@\assets\rules\injection\skill-aop-prelude.md（本文件不复制正文）。

# M5_系统与知识资产治理 (全域治理与清理执行器)

<context>

## 1. 定位与三权分立 (Trias Politica)
M5 是系统的最高纪律裁决与唯一拥有执行物理删除合法权的模块。
在它的运作下，系统必须严格执行 **Harness Zero-Trust (零信任) 隔离架构**：
- **知识立法权（所有 S系提纯节点）**：只被允许提纯与抽取知识，绝对受到底层文件写权限剥夺与隔离。
- **调度行政权（所有 W系工作流，如 W11）**：只充当触发器和监控器，负责定点唤醒 M5 启动，绝对禁止其直接插手全域环境的物理文件清理。
- **物理执行权锁定（M5 终裁 + W9 复核）**：M5 是全域唯一拥有冗杂文档物理删除、规则合并终裁权的治理执行器。其所有决断受 `W9_出口验收` 进行 AOP 双重熔断复核，稍有差错全盘原子级回滚。删除的物理阻断与回滚由确定性层（hooks 写守卫与 W9 门禁脚本）执行，M5 产出终裁决策与证据。
- **CRUD 终裁权**：Skill / Rule / SOP / Workflow / Index 的 `DELETE / ARCHIVE` 由 M5 终裁；`QUERY / CREATE / UPDATE` 若暴露孤岛、重名、断链、越权，也必须回到 M5 做资产治理判决。

</context>

<rules>

## 2. 🧠 强制编排状态机 (Harness State Machine - OpenSpec Artifact Graph 监控)
> **执行纪律**：一旦 M5 启动，必须基于 OpenSpec Artifact Graph 的 DAG 拓扑顺序推进，严格穿透以下五层净化舱，不得跳步。
> 治理文档与错题本合并时，必须严格遵守 Delta Spec (ADDED/MODIFIED/REMOVED/RENAMED) 四级增量生命周期，杜绝产生历史断层。

### [STATE: ORPHAN_SCAVENGER] (遗留脚本清理)
- **定期清理 `scripts/` 目录的遗留脚本**：扫描所有 Python 和 PowerShell 脚本，如果在任何 `SKILL.md` 调度链接中都未被引用，则直接删除。
- 立即执行物理删除 (Remove-Item -Force)！永久废除 `archive/` 冷柜打包法，将历史回退权交给 Git 控制台保管。
- **【测试目录卫生巡检】(🆕 v2.3 补丁)**：扫描范围从 `scripts/` 扩展到 `tests/` 目录。`tests/` 只允许 `test_*.py`、`conftest.py`、`__init__.py` 和 fixtures 子目录。其他命名的 `.py` 文件（如 `verify_*.py`、`check_*.py`、`debug_*.py`）一律判定为一次性调试残骸，直接物理销毁。
- **【管线 Session 残骸回收】(🆕 v2.3 补丁)**：扫描 `docs/` 下由管线执行器运行时创建的临时 session 目录。匹配模式：`gk_audit_session*`、`pipeline_state/` 等。参照 OpenSpec 的 Artifact 生命周期思想，对已完结管线的 session 残骸直接执行物理回收。

### [STATE: ONTOLOGY_GATING_SWEEP] (知识元数据扫描)
- **执行矩阵扫描**：加载 `@@GENERAL_ROOT:win@@\docs\00-harness-oss-index.md`。依据该文件的 `5-Tier Axis` 及 `README.md` 层级边界，清理所有不在 01-05 范围内、或缺乏 YAML 护照的 `.md` 文件。
- **YAML 护照核验**：所有文档顶层必须携带完整护照（字段口径以 birth-ceremony-protocol.md Step 1 为准：domain/tier/doc_status/related/birth_ceremony_id）。
- **【多维矩阵定名与越权清洗】(🆕 核心升格)**：基于”架构角色 × 职责域”审计所有技能阵列。**M系 (Meta-Governor)** 必须专门操作 `.agent/` 治理区；**S系 (Executor)** 必须被限制在用户应用代码库中；**P系** 限于业务蓝图统筹；**W系** 限于生命周期门禁触发。若 M5 发现任何 S 系组件拥有修改规则的权限，或层级名与职责严重不符，立即标记为权限违规并执行删除或重命名。
- **回收机制 (GC 定向清理)**：任何拒不携带高维护照的散落文档、或者被标记为 `tier=04` (快照战报级) 且已失去时效的文档，一律判定为”违规文件”，执行物理删除（Delete）。
- **【嵌套目录克隆检测 (Mirror Nesting Detection)】(🆕 v2.3 补丁)**：参照 OpenSpec 的 Artifact Graph 拓扑思想，M5 必须扫描目录结构中的 `X/X/` 形态镜像嵌套（如 `docs/docs/`、`specs/specs/`）。这类重复结构通常是复制粘贴错误，整个嵌套子树判定为 `MIRROR_NESTING_VIOLATION`，执行物理删除。

### [STATE: CONFLICT_ARBITRATION] (规则冲突裁决)
- 合并 `rules/` 和 `skills/` 中由于历代补丁堆叠产生的矛盾设定。
- 必须且只能保留**唯一的一条最高版规则**，不允许两条冲突的规则在系统中并存。
- **【治理对象 CRUD 终裁】**：凡 M5 接管 Skill / Rule / SOP / Workflow / Index / 三层提示词知识库 的删除、归档、合并、迁移，必须先核验 `GOVERNANCE_OBJECT_CRUD_GATE`。若缺少 `object_class/action/ssot_home/prompt_knowledge_layer/registry_update/blast_radius`，直接退回 M2/W1 补门闸，不得执行物理处置。

### [STATE: AXIOM_ELEVATION] (知识提炼收敛)
- 当遇到几百字记叙文式流水账错题集，直接提炼成一句【绝对不超过 15 个字】的核心常识公理（Axiom），并写入上游索引。

### [STATE: PYRAMID_STRUCTURING] (版面结构重整)
- 强制对因时间推移变得散乱的 markdown 文件进行结构重整。将一切过期的内容移到文件底部附录区，保证所有入口文件符合【入口轻量化法则】。

### [STATE: OVERRIDE_AUDIT] (跨层继承链排查)
- 排查所有非法私搭的越格子目录。若某个项目节点试图私自切断底层的继承链（Extends），则将其独立文件合并还原为系统全局快捷连接。

### [STATE: P_TIER_ASSET_GOVERNANCE] (P 级资产归属验证与证据审计)
- **一句话职责**：业务交付物路径收敛、全局入口口径断言、父子项目三级归属裁决、护照与血缘穿透、第一事实验证、知识图谱双向注册、产物落盘合规、运行时产物 TTL 回收。
- **细则外置**：完整 v2.3~v2.7 补丁群细则见 `references/治理状态机细则.md`。
- **铁律摘要**：产物必须落 `projects/<project>/` 或 `docs/specs/<task-slug>/` workspace；全局入口 `05-global-knowledge-graph.md` 口径禁止漂移；子域 Skill 必须双向注册（本地 catalog + 父级 related）。违规判 `GLOBAL_ENTRY_DRIFT` / `GHOST_ASSET_VIOLATION` / `ARTIFACT_LANDING_PATH_VIOLATION`。

### [STATE: P1_HANDOFF_CONSISTENCY_GOVERNANCE] (P1 交付一致性治理闸)
> 目标：防止“图状态已毕业，但文档口径未收敛”的假闭环。

- **【PRD 澄清位与图状态一致】**：若图状态 `clarification_status=RESOLVED`，则 P1 PRD 不得保留 `未回答是否阻断：True` 的阻断项；否则判定 `P1_CLARIFICATION_DRIFT`。
- **【First-Fact 单一真相】**：`first-fact-packet`、state、图审计三方状态必须一致；若出现 `HUMAN_REQUIRED` 与 `CANDIDATE/SCHEMA_READY` 并存，判定 `FIRST_FACT_STATUS_SPLIT`。
- **【Handoff 布尔位禁空壳】**：`blocking_questions_resolved=true` 时，必须携带运行时答案实参（正样本锚、反样本锚、归一化规则、异常规则、可追溯策略）；缺任一项判定 `HANDOFF_EMPTY_RESOLVED`。
- **【P2 合约字段最小集】**：P1 PRD 必须显式携带首事实核心字段契约（`code/name/title/type/updateTime/data[].id/title/timestamp/hot/url/mobileUrl`）；缺失判定 `P2_CONTRACT_UNDERSPEC`。
- **【Manifest/State 可发现性】**：manifest 若为空壳 `artifacts:{}` 或 state 仍 `audit_status:PENDING` 与 P1 PASS 冲突，首轮记 `WARNING`，连续两轮升级 `BLOCKER`。

### [STATE: ANTI_LAZINESS_COMPLIANCE_AUDIT] (九大检查项合规巡检)
- **一句话职责**：逐条核验九大防偷懒检查项（`execution.md §7.1`）在 W1/P 系/S 系各层的物理落实。
- **细则外置**：完整 ALW-01~09 检查项表与整改强制力见 `references/九大检查项.md`。
- **铁律摘要**：`VIOLATION`→BLOCKER 冻结下游；`CANARY_MISS`→报告作废；`FORMAT_VIOLATION`/`SINGLE_VIEW_RISK`→WARNING 写经验队列。

</rules>

<template>

## 3. 标准通信契约 (Harness JSON I/O)
- **JSON 模板外置**：完整 JSON 模板与 governance_budget 治理预算镜口径见 `resources/m5报告JSON模板.md`。
- **铁律摘要**：`governance_budget` 是 advisory 镜子（非门禁）——`net_delta = rules_added - (rules_deleted + rules_merged)`；`trend=EXPANDING` 时 `self_reflection` 必答“加 gate 是否比修根因省事”；连续多轮 EXPANDING 是 M5 该对自己动刀的信号，不是继续加规则的理由。

## 4. 🗂️ 核心依赖与工具集
**主控文件已精简，M5 可按需加载以下外部工具：**
- **清理探针清单**：读取位于 `@@GENERAL_ROOT:win@@\assets\skills\M5_系统与知识资产治理\resources\m5_garbage_collection_prompt.md` 的辅助提示文件。
- **全局文件健康检查**：触发执行 `@@GENERAL_ROOT:win@@\tooling\audit\os_global_linter.py`，扫描过长的文件。
- **父子级联修复工具**：触发执行 `@@GENERAL_ROOT:win@@\tooling\os_parent_child_syncer.py`，修复继承关系。
- **夜间自动清理工具**：`@@GENERAL_ROOT:win@@\assets\skills\M5_系统与知识资产治理\scripts\os_nightly_sweeper.ps1`，定时执行全域清理与健康巡检。

## 5. 📦 脚本资产清单 (Script Asset Registry)

| 脚本 | 路径 | 用途 |
|:---|:---|:---|
| `os_global_linter.py` | `@@GENERAL_ROOT:win@@\tooling\audit\os_global_linter.py` | 全域文件健康度扫描工具 |
| `os_global_linter.py`（编号唯一性/样板扫描） | `@@GENERAL_ROOT:win@@\tooling\audit\os_global_linter.py` | NEW-4 编号撞号扫描（NUMBERING_COLLISION）+ NEW-2 SKILL 样板禁复制扫描（SKILL_BOILERPLATE_COPY），W9 自动调用 |
| `asset-birth-ceremony.py --audit-registry` | `@@GENERAL_ROOT:win@@\control\guards\asset-admission\asset-birth-ceremony.py` | 登记簿巡检：逐行核验 birth-ceremony-registry.jsonl 的 file_path 存活，死链报 REGISTRY_DEAD_LINK（有死链退出码非 0） |
| `generate_catalog.py --check` | `@@GENERAL_ROOT:win@@\tooling\generate_catalog.py` | 账实比对：从磁盘事实生成式重建 scripts 账本，--check 对账 06-scripts-catalog.md（漏登 MISSING_ENTRY/虚登 PHANTOM_ENTRY/职能漂移 FUNCTION_DRIFT），差异清零后由 M5 刷新账本 |
| `os_parent_child_syncer.py` | `@@GENERAL_ROOT:win@@\tooling\os_parent_child_syncer.py` | 父子级联修复工具 |
| `os_nightly_sweeper.ps1` | `@@GENERAL_ROOT:win@@\assets\skills\M5_系统与知识资产治理\scripts\os_nightly_sweeper.ps1` | 夜间自动清理与巡检 |
| `clean-expired-runtime.ps1` | `@@GENERAL_ROOT:win@@\assets\skills\M5_系统与知识资产治理\scripts\clean-expired-runtime.ps1` | 全域治理产物 7 天 TTL 过期清理（W9/sweeper 消费） |
| `clean-expired-specs.ps1` | `@@GENERAL_ROOT:win@@\assets\skills\M5_系统与知识资产治理\scripts\clean-expired-specs.ps1` | 单点 Specs 目录清理（已被 runtime 通用版覆盖，保留向后兼容） |

---
**最后更新**: 2026-07-12 | **版本**: v2.9.0 (去戏剧化：97处戏剧化措辞中性化；新增 governance_budget 治理预算镜 v2.8；非门禁，不阻断)

</template>
