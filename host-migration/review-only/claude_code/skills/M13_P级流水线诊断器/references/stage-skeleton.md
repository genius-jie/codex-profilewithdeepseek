---
domain: root-governance
tier: L2
doc_status: active-reference
owner_skill: M13_P级流水线诊断器
related:
  - @@GENERAL_ROOT:win@@\assets\skills\M13_P级流水线诊断器\SKILL.md
  - @@GENERAL_ROOT:win@@\assets\skills\M13_P级流水线诊断器\references\diagnostic-checklist.md
birth_ceremony_id: legacy-2f0ac9b2
birth_ceremony_date: pre-ceremony
---

# P 级阶段职责参考

这是一张诊断责任图，不是节点模板。M13 用它判断一个 P 阶段是否把必要职责交给了明确 owner；不得据此要求每阶段复制固定节点、字段或状态机。

## 责任维度

| 责任 | 需要回答的问题 | 可接受载体 |
|:---|:---|:---|
| Context | 目标、事实、未知项和上游约束是否清楚 | caller task package 或当前 checkpoint packet |
| Plan | 方案/步骤与风险是否足够支撑执行 | P1/P2/P2.5 产物或显式 standalone plan |
| Work | 谁拥有副作用与工具执行 | 当前项目执行者或 Automation Core |
| Review | 是否需要独立审查，审查什么 | S13 或条件触发的 P2.6 |
| Human | 哪些取舍必须由人类决定 | 当前 interrupt/decision packet |
| Acceptance | 完成声明如何判定 | request acceptance、项目测试、S14 |
| Evidence | 事实能否由当前文件、命令或产物复核 | artifact refs、diff、测试和物理输出 |
| Recovery | 失败后由谁 retry/revise/resume | 当前 Runtime 或调用方既有机制 |

这些责任可以由同一节点、多个节点、宿主原生流程或 standalone 调用实现；不存在“每阶段必须十节点”的要求。

## 当前 Automation Core 映射

E Core 的结构以自身源代码和测试为准。父级 M13 只读消费其 `request/results/feedback`、checkpoint/interrupt packet、阶段结果和 `p6_final`，不向 Core 增加节点、状态键、数据库表或旁路 receipt。

## Task Context Package

若调用方已有 `task_context_package`，它可以索引目标、上游上下文、artifact refs、Skill/SOP 建议、missing context 和 required decisions。缺少该对象不自动构成失败；等价信息已在当前 caller/checkpoint packet 中时不得再造第二份。

## 产物边界

产物落点由用户指定或项目声明的 `project_root`、request artifact refs 和项目自有契约决定。M13 只检查消费者能否找到当前证据，不要求统一 workspace、manifest 或 graduation seal。

## LEGACY_CONTROL_ARCHIVE_ONLY

旧固定阶段骨架、统一 guard/review/graduate 节点、宏观 GraphState 字段、统一 workspace manifest 与 graduation receipt 仅作历史对照，不得用于扩建 E Core。
