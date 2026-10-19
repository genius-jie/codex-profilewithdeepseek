---
description: 运行 W9 工作流阶段，在写完代码准备提交前，做最后一遍检查拦截。
type: core-workflow
domain: root-governance
tier: L3
status: active
doc_status: active-reference
shell_kind: thin-shell-pointer
last_verified: 2026-08-16
extends:
  - @@GENERAL_ROOT:win@@\assets\workflows\W9_出口验收.md
override: []
related:
  - @@GENERAL_ROOT:win@@\assets\workflows\W9_出口验收.md
  - @@GENERAL_ROOT:win@@\control\registry\05-global-knowledge-graph.md
  - @@GENERAL_ROOT:win@@\control\registry\03-workflow-catalog.md
birth_ceremony_id: legacy-25c8e925
birth_ceremony_date: pre-ceremony

---
# W9_出口验收（斜杠命令薄壳）

> **【薄壳声明 (Thin Shell)】**：本命令文件是 `W9_出口验收` 的斜杠命令入口薄壳，**不承载 W9 检查清单正文**。W9 的 G0-G20 分层验证矩阵、Git 仓库卫生四段式审计、治理硬门禁出口核验、W31 P0-P6 验收联动全部以下方本体文件为唯一事实来源（SSOT）。

> **唯一事实来源**：`@@GENERAL_ROOT:win@@\assets\workflows\W9_出口验收.md`
> 执行本命令时，Agent 必须**物理读取**上述本体文件并按其完整检查清单执行，严禁仅凭本薄壳或记忆执行。

> **执行入口**：按本体文件 `@@GENERAL_ROOT:win@@\assets\workflows\W9_出口验收.md` 的检查项顺序执行：语法/路径死链/硬编码检查 → Git 卫生审计（涉 commit 时）→ 治理硬门禁出口核验（涉治理资产变更时）→ W7 候选链核验。

> **溯源备注**：本薄壳于 2026-08-16 由过期全量副本转换而来；覆写前原件已快照至 `@@CLAUDE_HOME:win@@\backups\commands-snapshot-20260816-taskC.tar.gz`。副本中差异内容（update_asset_health.py 旧调用、2026-04-30 版 git 卫生旧口径等）均为已被本体 2026-07-29 重构取代的陈旧状态，非新增域知识。
