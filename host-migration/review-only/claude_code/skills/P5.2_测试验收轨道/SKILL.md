---
name: P5.2 测试验收轨道
domain: root-governance
tier: L2
status: active
doc_status: active-reference
description: |
  【触发场景】父级 P5 产品验收后，需要基于当前项目或 E Core 已完成 checkpoint 补齐独立测试验收。
  【不触发】普通性能压测、A4/A5/JMeter 脚本生成或不属于 P 级交付验收的测试任务不要用。
  【功能】消费显式绑定的 acceptance、交付物和新鲜测试证据，产出 test_verdict 供父级 W9/S14 外部验收。
related:
  - @@GENERAL_ROOT:win@@\assets\skills\P5_前端产品验收门禁\SKILL.md
  - @@GENERAL_ROOT:win@@\assets\skills\S11_测试驱动开发\SKILL.md
  - @@GENERAL_ROOT:win@@\assets\skills\S14_完成前验证\SKILL.md
  - @@GENERAL_ROOT:win@@\assets\workflows\W9_出口验收.md
  - @@CORE_ROOT:win@@\docs\runtime-contract-template.md
  - @@CORE_ROOT:win@@\src\pipeline\runner.py
birth_ceremony_id: bc-p5t-skill-7b2c9e41
birth_ceremony_date: 2026-06-03
---

# P5.2_测试验收轨道（兼容别名：P5.T / P5T）

## 触发场景

当前项目交付完成后，先由父级 P5 做产品验收，再由 P5.2 补齐测试证据，最终交给父级 W9/S14 综合裁决。`P5.T` 是 P5.2 的兼容别名；本 Skill 不是 E Core 节点，也不写入或推进 Core checkpoint。

## 职责边界

- P5.2/P5.T 只产出 `test_verdict`，不替代 P5.1 产品验收门禁的产品价值、数据可信、功能可用、内容可读和展示交互审计。
- P5.2/P5.T 不固定加载任一仓库的 registry、SOP、config 或 code；外部测试工作台只有被当前任务显式选择并给出证据引用时才能使用。
- P5.2/P5.T 不走 A4/A5/JMeter/性能压测链路。出现 A4、A5、JMeter 或 `performance_testing` 路由时必须阻断。
- 旧 D Automation Core 的 `p5t_acceptance.py`、`p_stage_skill_routes.yaml` 和 `p5_merge_gate` 仅属 archive-only 历史证据，不得活动加载、执行或 fallback。

## 测试验收链路

1. 需求对齐：从当前绑定的 acceptance 与交付物引用拆解测试范围。
2. 测试设计：把接口、功能点和风险基线转成可证伪的测试目录，覆盖正例、反例、边界值和等价类。
3. 执行：以当前修改后的新鲜 S11 结果为基线，再按交付形态选择非性能功能验收；UI/页面/报告走真实浏览器证据，API/后端走 API smoke 或契约校验，CLI/工具走 CLI smoke，复杂链路可补集成 smoke、静态质量、数据完整性、视觉/a11y 证据。
4. 汇总：生成 `test_verdict_receipt.json`，明确 GO / NO_GO / OBSERVE / NOT_APPLICABLE，并回指每项物理证据。

## 输入契约

`evidence_binding` 必须二选一：

- `current_project_external`：显式 `project_root`、当前 acceptance、当前 diff/修改文件、交付物引用和修改后的新鲜测试/S14 回执。
- `e_core_completed`：显式 E Core SQLite、`thread_id`、`checkpoint_id` 与只读 `automation-core inspect` 投影；必须满足 `status=COMPLETE` 且同一 checkpoint 的 `results.p6_final` 存在。

绑定后必备输入：

- `acceptance_refs`：当前 request acceptance、acceptance digest 或等价验收标准引用。
- `delivery_refs`：当前交付物、diff、修改文件和运行结果引用；E Core 模式从同一 checkpoint 的 `results/p6_final` 解析。
- `fresh_test_refs`：修改后的测试、check、smoke 与 S14 证据；只接受当前交付产生或复跑的新鲜结果。

可选输入：

- `baseline_test_receipts`：历史 S11/S14 或外部测试工作台回执，只能用于差异比较，不能替代 `fresh_test_refs`。
- `test_design_refs`：当前项目已有的 testability、test catalog/test cases 或覆盖回执；存在时应复用，不得重复造测试范围。

缺少 `evidence_binding`、关键引用不存在、checkpoint 已变化或两种模式混用时，必须输出 `EVIDENCE_BINDING_MISSING_OR_STALE` 并 `REJECT/NO_GO`；不得猜默认路径、切换模式、读取旧 D 或用历史回执补成 PASS。

## 输出契约

P5.2/P5.T 必须输出：

- `p5t_test_acceptance_receipt`：符合本 Skill 下列内联字段契约，不依赖旧 D schema/code。
- `evidence_binding`：记录模式、`project_root`；E Core 模式另记录 `thread_id/checkpoint_id/p6_final_ref`。
- `test_verdict.status`：`PASS`、`CONDITIONAL_PASS`、`REJECT` 或 `NOT_APPLICABLE`。
- `test_verdict.go_no_go`：`GO`、`NO_GO`、`OBSERVE` 或 `NOT_APPLICABLE`。
- `test_verdict.evidence_refs`：回指当前测试设计、新鲜 S11 结果、已选功能验收适配器和结果汇总证据。
- `upstream_test_evidence`：回指当前 `test_design_refs` 与 acceptance/delivery 覆盖证据；外部工作台回执必须带显式来源。

## 放行规则

- S11 单测和至少一个适配当前交付面的功能验收证据通过时，P5.T 可输出 `PASS/GO`；UI/页面/报告面的功能验收默认由 browser_subagent 承担。
- 测试仍在进行或缺少某一类必需执行证据时，只能输出 `CONDITIONAL_PASS/OBSERVE`，并列出未完成项和上线风险。
- 任一已选执行适配器回执失败时，必须输出 `REJECT/NO_GO`。
- `NOT_APPLICABLE` 只允许纯文档索引修正等确实没有可执行测试范围的任务；API、前端页面、报告、AI 评测、CLI 不得默认跳过。

## 父级外部合流

P5.2/P5.T 不做最终放行，也不调用旧 `p5_merge_gate`。父级 W9/S14 只基于同一 evidence binding 合并产品与测试裁决：

- `product_verdict=PASS` 且 `test_verdict=PASS`：`final_verdict=PASS`。
- `product_verdict=PASS` 且 `test_verdict=CONDITIONAL_PASS`：`final_verdict=CONDITIONAL_PASS`。
- 任一轨道 `REJECT`：`final_verdict=REJECT`。
- 合法 `NOT_APPLICABLE` 只能使测试轨道视为无阻断，不得掩盖产品轨道失败。
- 产品与测试回执的 `project_root/thread_id/checkpoint_id` 不一致时直接拒绝，不允许 fallback 到较旧回执。
