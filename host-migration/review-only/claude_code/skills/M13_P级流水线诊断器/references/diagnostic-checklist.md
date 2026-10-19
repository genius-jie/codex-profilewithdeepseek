---
domain: root-governance
tier: L2
doc_status: active-reference
owner_skill: M13_P级流水线诊断器
related:
  - @@GENERAL_ROOT:win@@\assets\skills\M13_P级流水线诊断器\SKILL.md
  - @@GENERAL_ROOT:win@@\assets\skills\M13_P级流水线诊断器\references\stage-skeleton.md
birth_ceremony_id: legacy-96d643be
birth_ceremony_date: pre-ceremony
---

# P 级流水线诊断清单

先识别当前 owner 和载体，再把每项标为 PASS、FAIL 或 N/A，并附当前证据。此清单诊断职责覆盖，不规定实现拓扑。

## 目标与边界

1. 任务目标、acceptance、项目根和决策权限明确。
2. 已知事实、风险推断和未知项分开。
3. P1/P2/P2.5/P3/P4 各自只承担本阶段方法职责，不拥有 Runtime 状态。
4. W1 只做任务理解、风险分类、方法建议和语义交接。

## Runtime 与恢复

5. 唯一执行 owner 明确；不存在第二路由器、第二状态机或旁路数据库。
6. checkpoint/interrupt/retry/revise/resume 由当前 Runtime 或调用方既有机制拥有。
7. 恢复后的 packet 与当前 checkpoint 匹配，旧证据不会被当作新事实。
8. 长任务有调用方已有的超时、预算或中断策略；不为此创建父级运行状态。

## 契约与证据

9. 上游目标与 acceptance 在交接中没有丢失。
10. 当前 diff、文件、配置、测试和物理产物可独立读取。
11. 研究结论或选型有必要的真实探针，不能只靠模型推测。
12. artifact refs 位于当前项目边界并能被消费者解析。
13. Schema 只约束真实交接面，不穷举实现内部字段。

## Review 与人机协作

14. S13/P2.6 只在调用方或风险要求时独立审查；生产者不自填 verdict。
15. 人类只处理不可逆、权限、范围扩大或多种有效方案的真实取舍。
16. 决策包包含选项、事实、影响和推荐，不用抽象状态掩盖缺口。
17. P2.6 结论不自动推进 Core 或切换产物版本。

## 完成与经验

18. S14 证据晚于最后相关改动，cwd/target/config 正确且完整结束。
19. `p6_final` 与父级发布/治理批准分开裁决。
20. W7/M4 候选保持 `pending_human`，不自动修改资产。

## 严重度

- P0：双控制面、状态权威冲突、错误 checkpoint、不可逆越权、伪造完成证据。
- P1：目标/acceptance 丢失、证据不新鲜、独立性不足、消费者找不到产物。
- P2：命名、导航或非阻断说明不一致。

## LEGACY_CONTROL_ARCHIVE_ONLY

旧固定 guard/executor/review/revise/retro/graduate 节点清单、统一 policy/session/workspace/seal 仅用于历史比较，不是当前诊断通过条件。
