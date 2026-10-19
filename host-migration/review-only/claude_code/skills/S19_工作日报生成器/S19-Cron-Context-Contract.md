---
domain: utility
tier: L3
doc_status: active-ssot
related:
  - @@GENERAL_ROOT:win@@\assets\skills\S19_工作日报生成器\SKILL.md
  - @@GENERAL_ROOT:win@@\assets\skills\S19_工作日报生成器\scripts\collect_user_input_streams.py
  - @@GENERAL_ROOT:win@@\assets\skills\S19_工作日报生成器\scripts\daily-context-collector.ps1
  - @@OPENCLAW_ROOT:win@@\.agents\skills\S28_定时任务编排\SKILL.md
  - @@GENERAL_ROOT:win@@\control\registry\05-global-knowledge-graph.md
  - @@OPENCLAW_ROOT:win@@\.agents\index\02-child-knowledge-graph.md
birth_ceremony_id: bc-s19-cron-contract
birth_ceremony_date: '2026-06-23'
contract_version: s19-cron-context.v1.1
---

# S19 定时任务上下文传递契约

## 1. 目标

每日工作日报的主事实源固定为三入口用户输入流：

- Antigravity
- Codex++
- VSCode Claude Code

日报先回答“指挥官今天让 Agent 做了什么”，再用 git、文件正文和自动产物做辅助校验。不得从 git commit、文件变更或 cron 自动日志反推个人工作主线。

## 2. 预采集产物

日报生成前，`日报上下文预采集` 必须生成两个文件：

```text
@@GENERAL_ROOT:win@@\evidence\S19_工作日报生成器\context\daily-user-inputs-YYYY-MM-DD.json
@@GENERAL_ROOT:win@@\evidence\S19_工作日报生成器\context\daily-context-YYYY-MM-DD.json
```

`daily-user-inputs` 必须包含：

```json
{
  "schema_version": "daily_user_input_streams.v1",
  "date": "YYYY-MM-DD",
  "primary_source": "three_user_input_streams",
  "required_source_ids": ["antigravity", "codexplusplus", "vscode_claude_code"],
  "summary": {
    "total_user_inputs": 0,
    "sources_found": 3,
    "sources_ok": [],
    "sources_missing": [],
    "sources_warn": [],
    "topic_hits": {}
  },
  "source_index": {
    "antigravity": { "user_input_count": 0, "count": 0 },
    "codexplusplus": { "user_input_count": 0, "count": 0 },
    "vscode_claude_code": { "user_input_count": 0, "count": 0 }
  },
  "records": []
}
```

`daily-context` 必须包含：

```json
{
  "contract_version": "1.0",
  "date": "YYYY-MM-DD",
  "date_today_asia_shanghai": "YYYY-MM-DD",
  "summary": "今天收集到 N 条三入口用户输入，git/status 仅作为辅助校验",
  "primary_evidence_source": "three_user_input_streams",
  "user_input_context_path": "@@GENERAL_ROOT:escaped@@\\assets\\skills\\S19_工作日报生成器\\context\\daily-user-inputs-YYYY-MM-DD.json",
  "collection_summary": {
    "user_inputs_count": 0,
    "primary_source": "three_user_input_streams"
  },
  "user_input_streams": {
    "records": [],
    "source_index": {}
  }
}
```

当天某个入口输入数量为 0 不算失败。失败只看采集器是否跑通、三入口 `source_index` 是否齐全、JSON 结构是否完整。

## 3. Codex++ 长线程补采规则

Codex++ session 文件按线程创建日期落目录，但消息可能发生在之后多天。采集器不得只扫报告日期目录，必须：

1. 读取报告日前 14 天到次日的 Codex++ session 目录。
2. 额外读取文件修改时间落在报告日前后一天的 session 文件。
3. 最终只按消息时间过滤到报告日期。
4. 对同一来源、同一时间、同一文本去重。

这条规则用来防止当前 Codex++ 长线程继续跨天漏采。

## 4. 正式日报生成规则

正式日报任务必须：

1. 读取 `daily-context-YYYY-MM-DD.json`。
2. 校验 `primary_evidence_source=three_user_input_streams`。
3. 校验 `user_input_streams.records` 与三入口 `source_index`。
4. 从用户输入归并候选工作主线。
5. 只用 git/status/文件正文做辅助验证。
6. 生成条目级证据表，说明采纳和剔除原因。
7. 只把日报正文投递飞书，执行过程、命令输出、JSON、证据表留在本地文件。

如果三入口上下文缺失或结构不完整，正式日报必须硬失败或降级草稿；不得自动回退到 git-only 正式日报。

## 5. 飞书边界

- `日报上下文预采集` 是内部准备任务：成功回执必须静默，只保留 failureAlert 到飞书。
- `每日工作日报` 是业务投递任务：成功时可以投递飞书日报正文。
- 两类任务失败时都必须保留硬失败摘要，不能用“脚本退出码 0”掩盖 JSON 合同字段缺失。

## 6. 违约处理

命中以下任一情况时，预采集或正式日报必须判失败：

- 三入口采集器不存在、退出码非 0 或未生成输出。
- `daily-user-inputs` 缺少 `summary`、`records`、`required_source_ids` 或 `source_index`。
- `source_index` 缺少 `antigravity`、`codexplusplus`、`vscode_claude_code`。
- `daily-context` 缺少 `date`、`summary`、`date_today_asia_shanghai`、`collection_summary`、`primary_evidence_source`、`user_input_context_path` 或 `user_input_streams`。
- `primary_evidence_source` 不是 `three_user_input_streams`。
- 写出的 JSON 无法读回解析，或日期不是 Asia/Shanghai 当天。

命中失败时，最终摘要以 `CRON_HARD_FAIL:` 开头，并说明缺失字段、目标文件和需要处理的入口。
