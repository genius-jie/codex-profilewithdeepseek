---
domain: openclaw
tier: L3
doc_status: active-ssot
related:
  - @@GENERAL_ROOT:win@@\assets\skills\S19_工作日报生成器\S19-Cron-Context-Contract.md
  - @@GENERAL_ROOT:win@@\assets\skills\S19_工作日报生成器\SKILL.md
  - @@GENERAL_ROOT:win@@\assets\skills\S19_工作日报生成器\scripts\collect_user_input_streams.py
  - @@GENERAL_ROOT:win@@\assets\skills\S19_工作日报生成器\scripts\daily-context-collector.ps1
  - @@OPENCLAW_ROOT:win@@\.agents\skills\S28_定时任务编排\SKILL.md
birth_ceremony_id: bc-s19-cron-manifest
birth_ceremony_date: '2026-06-23'
---

# 每日工作日报定时任务清单

## 1. 运行目标

日报链路分成两个任务：

1. `日报上下文预采集`：每天 19:40 生成三入口输入流上下文，成功静默，失败飞书告警。
2. `每日工作日报`：每天 20:00 读取上下文，生成并投递正式日报正文。

这两个任务共用 `S19-Cron-Context-Contract.md`。预采集只准备事实，不写日报；正式日报只基于三入口事实归并工作主线。

## 2. 预采集任务

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "@@GENERAL_ROOT:win@@\assets\skills\S19_工作日报生成器\scripts\daily-context-collector.ps1" -Date (Get-Date -Format "yyyy-MM-dd")
```

输出：

```text
@@GENERAL_ROOT:win@@\evidence\S19_工作日报生成器\context\daily-user-inputs-YYYY-MM-DD.json
@@GENERAL_ROOT:win@@\evidence\S19_工作日报生成器\context\daily-context-YYYY-MM-DD.json
```

必守规则：

- 先采集 Antigravity、Codex++、VSCode Claude Code 三入口用户输入。
- Codex++ 必须覆盖跨日期长线程，按消息时间过滤到报告日期。
- git/status/文件变更只做辅助校验。
- 写完 `daily-context` 后必须读回校验合同字段。
- 成功不投递飞书；失败通过 `failureAlert` 投递飞书。

## 3. 正式日报任务

正式日报必须先读取：

```text
@@GENERAL_ROOT:win@@\evidence\S19_工作日报生成器\context\daily-context-YYYY-MM-DD.json
```

必守规则：

- `primary_evidence_source` 必须是 `three_user_input_streams`。
- `user_input_streams.records` 必须存在。
- `source_index.antigravity`、`source_index.codexplusplus`、`source_index.vscode_claude_code` 必须存在。
- 每个日报条目至少命中一条今日三入口用户输入。
- 自动 cron 产物默认不写入个人日报，除非用户当天明确要求处理该任务。
- 飞书只投递日报正文，不投递执行过程、命令输出、JSON 或证据表。

## 4. 当前 cron 边界

| 任务 | cron | 成功投递 | 失败投递 |
|:---|:---|:---|:---|
| 日报上下文预采集 | `40 19 * * *` | 静默，`delivery.mode=none` | `failureAlert -> feishu` |
| 每日工作日报 | `0 20 * * *` | 飞书业务日报正文 | cron 失败摘要 |

预采集成功静默不能影响正式日报投递。正式日报是业务功能，不做成功静默。

## 5. 硬失败判定

预采集命中以下情况必须失败：

- 采集脚本不存在、退出码非 0 或超时。
- 未生成 `daily-user-inputs` 或 `daily-context`。
- 任一 JSON 不能解析。
- 缺少三入口 `source_index`。
- `daily-context` 缺少 `date`、`summary`、`date_today_asia_shanghai`、`collection_summary`、`primary_evidence_source`、`user_input_context_path` 或 `user_input_streams`。
- `primary_evidence_source` 不是 `three_user_input_streams`。

正式日报命中以下情况必须失败或降级草稿：

- 没有有效 `daily-context`。
- 三入口输入流为空且用户没有明确补充今日工作。
- 候选条目无法回指到今日三入口用户输入。
- 只靠 git/status/文件变更推断个人工作。

## 6. 验证命令

```powershell
python -m py_compile "@@GENERAL_ROOT:win@@\assets\skills\S19_工作日报生成器\scripts\collect_user_input_streams.py"
powershell -NoProfile -ExecutionPolicy Bypass -File "@@GENERAL_ROOT:win@@\assets\skills\S19_工作日报生成器\scripts\daily-context-collector.ps1" -Date 2026-07-07
```

验收标准：

- `daily-user-inputs` 有三入口 `source_index`。
- 当前 Codex++ 长线程里的当天消息能命中。
- `daily-context` 根字段齐全。
- 预采集成功不投递飞书。
