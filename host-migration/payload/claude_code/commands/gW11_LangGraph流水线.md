---
description: 人工强制拉起 P 级 LangGraph 治理管线的唯一入口
type: core-workflow
domain: root-governance
tier: L2
status: active
doc_status: active-reference
shell_kind: thin-shell-pointer
last_verified: 2026-08-16
extends:
  - @@GENERAL_ROOT:win@@\assets\workflows\W11_LangGraph流水线.md
override: []
related:
  - @@GENERAL_ROOT:win@@\assets\workflows\W11_LangGraph流水线.md
  - @@GENERAL_ROOT:win@@\control\registry\05-global-knowledge-graph.md
  - @@GENERAL_ROOT:win@@\control\registry\03-workflow-catalog.md
birth_ceremony_id: legacy-5302841f
birth_ceremony_date: pre-ceremony

---
# W11_LangGraph流水线（斜杠命令薄壳）

> **【薄壳声明 (Thin Shell)】**：本命令文件是 `W11_LangGraph流水线` 的斜杠命令入口薄壳，**不承载 W11 发车脚本与状态机正文**。W11 的触发条件、Codex 会话单次发车铁律、validate_task 发车流程、Resume-Interrupt 分支与 Agent 行为纪律全部以下方本体文件为唯一事实来源（SSOT）。

> **唯一事实来源**：`@@GENERAL_ROOT:win@@\assets\workflows\W11_LangGraph流水线.md`
> 执行本命令时，Agent 必须**物理读取**上述本体文件并按其完整流程执行，严禁仅凭本薄壳或记忆执行。

> **执行入口**：按本体文件 `@@GENERAL_ROOT:win@@\assets\workflows\W11_LangGraph流水线.md` 执行：触发条件确认（W1 已裁决 P_PIPELINE）→ validate_task.py 发车前核验 → 发车脚本（PowerShell 全文见本体）→ interrupt/resume 分支 → W9 出口验收。

> **溯源备注**：本薄壳于 2026-08-16 由过期全量副本转换而来；覆写前原件已快照至 `@@CLAUDE_HOME:win@@\backups\commands-snapshot-20260816-taskC.tar.gz`。副本中差异内容（`.w11-pipeline-launched.json` 旧发车标记脚本、fact_id JSON 样例、RoundRobin Debate 微观审计等）均为已被本体 2026-07-22 版取代的陈旧状态（发车标记已迁至 `.w11-runtime/<owner_scope>/`，微观审计流已改 Post Guard/P2.6 链路），非新增域知识。
