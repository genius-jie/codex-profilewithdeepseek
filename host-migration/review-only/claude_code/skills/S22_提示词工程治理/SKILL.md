---
name: S22 提示词工程治理
type: generic
domain: root-governance
tier: L2
doc_status: active-ssot
status: active
birth_ceremony_id: bc-s22-320e8024
birth_ceremony_date: '2026-05-02'
related:
- @@GENERAL_ROOT:win@@\assets\skills\P4_复杂多体拓扑编排\SKILL.md
- @@GENERAL_ROOT:win@@\records\experience\experience_queue.md
- @@OPENCLAW_ROOT:win@@\.agents\index\03-langgraph-governance-map.md
- @@OPENCLAW_ROOT:win@@\.agents\orchestration\autogen\docs\openspec_framework_analysis.md
- @@OPENCLAW_ROOT:win@@\.agents\orchestration\autogen\docs\openspec_integration_plan_v2.md
- @@GENERAL_ROOT:win@@\control\registry\02-skill-catalog.md
- @@GENERAL_ROOT:win@@\assets\skills\P1_需求法典与标准大闸\SKILL.md
- @@TESTING_ROOT:win@@\.agent\skills\A1_1_需求结构化\SKILL.md
- @@GENERAL_ROOT:win@@\assets\references\matrix\governance-protocol.md
description: |
  【触发场景】Agent system message、角色、能力注入规则。
  【不触发】普通文案润色、非提示词资产不要用。
  【功能】治理提示词结构，维护可调用的能力边界。
extends:
- @@GENERAL_ROOT:win@@\assets\rules\injection\skill-aop-prelude.md
- @@GENERAL_ROOT:win@@\assets\rules\execution.md
- @@GENERAL_ROOT:win@@\assets\references\methodology\09_Asset-Governance-Audit-Protocol.md
- @@GENERAL_ROOT:win@@\assets\references\methodology\10_S-Tier-Execution-Discipline-Protocol.md
---
<context type=”domain-specific”>

# S22_提示词工程治理 (Prompt Engineering Governance)

> **定位**: 全域提示词的 **立法者 (Legislator)** 与 **审计官 (Auditor)**。本技能适用于优化打磨所有类型的提示词：无论是语音人格代理、AutoGen Agent 的 SystemMessage、还是 RAG 的检索指令模板。
> **核心宪法**: 必须维护“特征胜于样例 (Features Over Examples)”的绝对纯洁性。所有长篇防漏法则已下放至该技能的 `resources/design_constitution.md`。
> **【M2 分工边界声明】**：S22 仅负责提示词**内容语义层**的优化（如 SystemMessage 的角色漂移修复、Prompt 的特征抽象立法）。SKILL.md 文件的**结构治理**（YAML 护照校验、拆合归档判定、目录归属权划分）归 `M2_技能生产与归档` 管辖，S22 不越权介入。
> **【Product PRD Handoff 语义边界】**：当提示词工程任务涉及“产品 PRD handoff / Visual PRD / 模糊产品想法 / P1 handoff 质量”时，S22 只审计提示词是否能正确唤醒 P1/A1_1 Product PRD Handoff capability 和 LangGraph P1 gate；不得复制该能力的 discovery loop、Visual PRD 00-17 正文或 validator 规则。
> **【架构/框架/平台治理注入边界】**：当提示词工程任务涉及架构、框架、平台、生成器、Builder、Renderer、HTML/报告生成入口、hook 或治理链路时，S22 必须先把 `@@GENERAL_ROOT:win@@\assets\rules\agent-constitution.md` 作为语义基线加载，并要求目标 Prompt 先确认正式入口全集、IA Contract 共同输入、职责边界和架构落点。S22 不得把这类问题降级为新增 hook / Gate / 字符串规则；hook 只能作为 advisory reminder，不能替代 IA-first 生成思想。Constitution / SOP / prompt 语义注入默认走 `GateProfile=Advisory`；只有触碰注册表、runtime/control-plane 或 frontend IA 正式入口时，才分别升级 Structural、Runtime 或 FrontendIA。

</context>

<rules>
## 🧠 提示词反幻觉状态机 (Harness State Machine)

### [STATE: BASELINE_READ] (前置基线研读防盲改)
**【你要做什么】**：如果不读旧资产直接动刀，必然导致历史经验与父链遗漏。在修改任何复杂提示词前，必须建立全景认知基线。
1. **强制动作**：如果任务是修改现有提示词资产，立刻调用 `M12_大文件分块读取` 的标准读取动作。
2. 完整物理阅读待修改的文件，并强制追溯其护照头部的 `extends` 继承法典与 `related` 关联网络！
3. **红线死劫**：严禁凭短期零碎记忆“改一点补一点”。

### [STATE: IA_FIRST_ROUTING] (架构/平台治理思想注入)
当任务涉及架构、框架、平台、生成器、Builder、Renderer、报告/HTML 生成或 hook 治理时：
1. 先声明目标 Prompt/Agent 要解决的业务目标和用户认知任务。
2. 定义 formal / active 正式入口全集。
3. 检查每个入口是否消费 IA Contract 或等价信息架构契约。
4. 明确 Builder/Renderer/Gate/Hook 的职责边界：Builder 组织业务认知，Renderer 只呈现，Gate/Hook 只做证据提醒。
5. 输出 Prompt 修改时，优先改变思维模型和共享入口，不把新增 Gate 当主方案。
6. 写出 `governance_routing_profile`：Constitution/SOP/prompt 语义为 `Advisory`；注册表/知识图谱为 `Structural`；runtime/control-plane 为 `Runtime`；frontend IA 正式入口为 `FrontendIA`。W1 和 hook 只传递提醒，最终档位由 W9 裁决。

### [STATE: ROOT_CAUSE_ANALYSIS] (溯源与本质定性)
1.  **输入**: 用户反馈 / 错误日志 / 新建需求。
2.  **动作**:
    *   识别 **违规模式/能力短板** (Pattern)。
    *   判断 **本质** (Nature): 是逻辑漏洞、角色漂移、还是单纯的 LLM 幻觉？
    *   **查阅错题本**: `resources/错题本.md`，确认是否为历史复发坑。

### [STATE: LEGISLATION_ABSTRACTION] (立法与特征抽象)
1.  **动作**:
    *   将模式转化为 **抽象特征 (Abstract Feature)**。
    *   定义该特征的 **检测标准 (Detection Criteria)**。
    *   制定 **系统级禁令 (System Constraint)**。
2.  **输出**:
    *   更新目标 Prompt 结构。
    *   更新 `checklist.md`，确保新特征可被程序化核验。

### [STATE: INVARIANT_GOVERNANCE]（不变量从提示词走到工程）
1. 先把一次反馈改写成跨任务成立的关系约束，不能把某次人物、字段或报错原样升格成全局规则。
2. 父级只在 `governance-protocol.md` 定义分层原则；测试场景的接入、消费者和封签留在子级；具体样本、阈值和结果留在项目证据层。
3. 修改 Prompt、角色或能力注入时，必须说明哪个运行消费者加载该规则、用什么 receipt 留下证据。只写在 SystemMessage、文档或注册表而没有真实消费者，判为 `DECLARED_NOT_CONSUMED`。
4. 语义判定使用 `true / false / null`：`null` 表示前置条件未满足，不能包装成通过；服务层、应用状态、模型质量和测试侧故障必须分开归因。
5. 跨场景复发的规则由 W7 提为子级候选；跨项目且经过验证的规则才进入父级候选。S22 只定义提示词语义，不接管子级执行器实现。

### [STATE: REGRESSION_AUDIT] (大满贯回归审计)
1.  **动作**:
    *   执行 **Turing Test Simulation** (模拟演练对抗)。
    *   对照 **Checklist** 进行逐项苛刻核查。
    *   **【出口红线】**：严禁仅仅因为一组弱智 Case 测试通过就认为修复完成。

## 知识资产 (Knowledge Assets)

*   `resources/design_constitution.md`: **设计宪法**。提示词创作最高指导原则。
*   `resources/错题本.md`: **错题本**。记录历史失误教训与特征对抗记录。
*   `resources/checklist.md`: **审计清单**。用于发布前防抖。
*   `@@GENERAL_ROOT:win@@\assets\skills\P1_需求法典与标准大闸\SKILL.md` + `@@TESTING_ROOT:win@@\.agent\skills\A1_1_需求结构化\SKILL.md`: **产品 PRD handoff 语义锚点**。S22 只用于检查 prompt/agent/governance 资产能否正确路由 P1/A1_1 Product PRD Handoff capability，不接管其产品发现方法。

## 📤 标准通信契约 (Harness JSON I/O)

为满足 W1 的【可观测】与【可回滚】天条，S22 结束流转前，必须抛出标准的执行契约：

```json
{
  "harness_metadata": { "phase": "S22_Prompt_Governance", "status": "SUCCESS" },
  "goal": "...",
  "matrix_location": "L2_Governance_Layer -> Prompt Assets",
  "legislation_summary": {
    "abstract_features_added": 2,
    "hardcoded_examples_removed": 1
  },
  "skill_routing": [
    { "step": "Exit", "executor": "W9_出口验收", "validator": "HUMAN_APPROVAL(终极闭环)" }
  ],
  "blast_radius": "说明修改了哪些文件，如何回滚复原"
}
```
</rules>

<template>
</template>
