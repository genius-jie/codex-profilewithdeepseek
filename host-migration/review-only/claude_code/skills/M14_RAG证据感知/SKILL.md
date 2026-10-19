---
name: M14 RAG证据感知
type: advisory-only
domain: meta-governance
tier: L1
doc_status: active-ssot
status: active
related:
- @@GENERAL_ROOT:win@@\assets\skills\M1_治理预加载门禁\SKILL.md
- @@GENERAL_ROOT:win@@\control\orchestration\W1_前置思考.md
- @@GENERAL_ROOT:win@@\control\registry\05-global-knowledge-graph.md
- @@GENERAL_ROOT:win@@\control\registry\02-skill-catalog.md
- @@GENERAL_ROOT:win@@\assets\references\methodology\24_Semantic-Dedup-and-Single-Home-Protocol.md
description: RAG 证据感知层（advisory-only）：在三层知识库智能路由基础上，提供全文级向量检索作为可选辅助。无决策权。
extends:
- @@GENERAL_ROOT:win@@\assets\rules\execution.md
birth_ceremony_id: bc-skill-6fd79ecb
birth_ceremony_date: 2026-06-12
---
# M14_RAG证据感知 (RAG Evidence Awareness)

> **架构定级**：M 系元治理家族，advisory-only 服务。
> **核心定位**：运行时证据发现层——在 Agent 已有的三层知识库智能路由基础上，提供全文级向量检索作为可选的辅助参考。
> **权限边界**：只提供证据召回建议，不做任何决策、不阻断、不修改路由。

---

## 0. 宪法红线

| # | 红线 | 说明 |
|---|------|------|
| R1 | **无决策权** | M14 输出是 advisory，消费者（W1/M1/W9/W7）自行决定是否采纳 |
| R2 | **尊重三层知识层级** | 召回结果必须标注 `prompt_knowledge_layer`（parent/child/project），不得混淆层级权威 |
| R3 | **Token 预算刚性约束** | 每次召回 ≤ 5 片段，每片 ≤ 500 tokens，总注入 ≤ 上下文窗口 15% |

---

## 1. 触发条件

M14 **不独立触发**。由以下消费者在特定时机调用：

| 消费者 | 调用时机 | 场景 |
|--------|---------|------|
| **W1 前置思考** | `GLOBAL_GOVERNANCE_ENTRY_ASSERT` 阶段，Agent 读完 catalog 仍觉得需要更多上下文时 | 辅助全文检索 |
| **M1 治理门禁** | Step 3 追加阅读时，发现任务描述与已有追加场景都不匹配 | 发现隐性关联 |
| **W9 出口验收** | 验收前检查是否遗漏必读文档 | 证据覆盖检查 |
| **W7 知识回流** | 回流前检查是否有旧版文档需要降级 | 冲突/过期发现 |
| **P1 管线** | First-Fact 阶段可选增强 | 管线级证据辅助 |

---

## 2. 技术架构

```text
┌─────────────────┐   HTTPS   ┌─────────────────────┐
│  本地 Windows    │──────────→│  DashScope API      │
│                  │  embed    │  text-embedding-v3  │
│  调用脚本        │←──────────│  (1024d vectors)    │
│       │          │           └─────────────────────┘
│       │ SQL      │
│       ↓          │   TCP    ┌─────────────────────────┐
│  消费者 ←────────┼──────────│  火山引擎 RDS           │
│  (W1/M1/W9/W7)  │          │  PG 17.4 + pgvector 0.8 │
│                  │          │  harness_rag DB         │
└─────────────────┘           └─────────────────────────┘
```

| 组件 | 选型 | 状态 |
|------|------|------|
| Embedding | DashScope `text-embedding-v3` (1024d) | ✅ POC 验证通过 |
| 向量存储 | PostgreSQL 17.4 + pgvector 0.8.0 | ✅ 已建库建表 |
| 数据库 | `harness_rag` | ✅ 索引规模以运行时 rag_search.py --stats 输出为准 |
| 索引 | IVFFlat (lists=64) + 4 个元数据索引 | ✅ 已建 |

---

## 3. 索引元数据（YAML 护照映射）

每个文档片段在 PG 中携带以下元数据，直接映射 YAML frontmatter 护照字段：

```sql
-- harness_knowledge_chunks 表的元数据列
doc_status              TEXT  -- active-ssot | active-reference | historical-reference | archived
domain                  TEXT  -- root-governance | openclaw | testing-engineering
tier                    TEXT  -- L0 | L1 | L2 | L3
prompt_knowledge_layer  TEXT  -- parent-agent | child-agents | project-core-runtime
```

### 3.1 索引范围

| 目录 | 层级 | 索引策略 |
|------|------|---------|
| `@@GENERAL_ROOT:win@@\` | parent-agent | L0-L2 实时增量 |
| `@@OPENCLAW_ROOT:win@@\.agents\` | child-agents | L0-L2 实时增量 |
| `@@TESTING_ROOT:win@@\.agent\` | child-agents | L3 定时批量 |

### 3.2 索引更新

- **全量索引**：首次或数据损坏时，运行 `rag_index.py full`（~5 分钟）
- **增量索引**：文件变更后，运行 `rag_index.py incremental`（按 file_hash 判定，已变更才重新 embed）

---

## 4. 输入/输出契约

### 4.1 输入

```yaml
RAG_QUERY_REQUEST:
  query: <string>              # 任务描述或检索关键词
  caller: <string>             # 调用者标识：W1 | M1 | W9 | W7 | P1
  filters:                     # 可选的元数据过滤条件
    doc_status_exclude:        # 排除的状态（默认排除 archived）
      - archived
    domain_include: []         # 限定域（空=不限）
    tier_include: []           # 限定层级（空=不限）
    layer_include: []          # 限定知识层（空=不限）
  top_k: 5                    # 返回片段数（默认 5，上限 5）
```

### 4.2 输出

```yaml
RAG_ADVISORY_PAYLOAD:
  query: <原始查询>
  caller: <调用者>
  timestamp: <ISO 8601>
  results:
    - source_path: <文件绝对路径>
      chunk_index: <片段序号>
      similarity: <0-1 余弦相似度>
      content_preview: <前 200 字符>
      metadata:
        doc_status: <active-ssot | ...>
        domain: <root-governance | ...>
        tier: <L0 | L1 | ...>
        prompt_knowledge_layer: <parent-agent | ...>
  advisory_notes:              # 可选的建议说明
    - type: <COVERAGE_GAP | CONFLICT_DETECTED | STALE_REFERENCE>
      detail: <说明文字>
  next_action: ADVISORY_ONLY   # 固定值，强调无决策权
```

---

## 5. 脚本清单

| 脚本 | 用途 | 调用方式 |
|------|------|---------|
| `scripts/rag_index.py full` | 全量索引 | 首次或损坏修复 |
| `scripts/rag_index.py incremental` | 增量索引 | 文件变更后 |
| `scripts/rag_search.py "<query>"` | 单次检索 | 调试/手动测试 |
| `scripts/rag_search.py --caller W1 --json "<query>"` | JSON 格式检索 | W1/M1 程序化调用 |

---

## 6. 降级策略

| 故障场景 | 降级行为 |
|---------|---------|
| DashScope API 不可用 | M14 返回空 payload + `advisory_notes: [{type: SERVICE_UNAVAILABLE}]` |
| 远程 PG 不可达 | M14 返回空 payload + `advisory_notes: [{type: DB_UNREACHABLE}]` |
| M14 整体故障 | 消费者（W1/M1/W9/W7）继续使用原生三层知识库路由，能力不受影响 |

**关键设计**：M14 故障不会阻断任何消费者的正常工作流。这是 advisory-only 的核心价值——增强但不依赖。

---

## 7. 消费者集成指南

### 7.1 W1 集成点

在 `GLOBAL_GOVERNANCE_ENTRY_ASSERT` 中，Agent 读完 catalog/KG 后仍觉得需要更多全文上下文时（可选）：

```
IF agent_wants_more_context:
    payload = M14.search(task_description, caller="W1")
    IF payload.results:
        CONSIDER payload.results[0..2] as supplementary reading
        LOG "M14_RAG_SUGGESTED: {len(payload.results)} docs found"
    ELSE:
        LOG "M14_RAG_EMPTY: no relevant docs found"
        CONTINUE with normal routing  # Agent 原生路由不受影响
```

### 7.2 P1 集成点

在 P1 First-Fact 阶段（可选接入，Agent 自行判断是否需要）：

```
IF agent_needs_broader_evidence:
    payload = M14.search(task_description, caller="P1", filters={tier_include: ["L0", "L1"]})
    CONSIDER payload.results as supplementary context  # 不强制追加
```

### 7.3 W9 集成点

在出口验收前（可选接入）：

```
payload = M14.search(task_summary, caller="W9")
FOR each result in payload.results:
    IF result.source_path NOT IN files_read_during_task:
        advisory_notes.append(COVERAGE_GAP: "可能遗漏: {result.source_path}")
```

---

## 8. 一句话总结

> **M14 是知识库的"搜索引擎"：你告诉它任务是什么，它返回最相关的 5 个文档片段。它不做决定，只提供证据。W1/M1/W9/W7 自己决定怎么用这些证据。故障时自动降级，不阻断任何工作流。**
