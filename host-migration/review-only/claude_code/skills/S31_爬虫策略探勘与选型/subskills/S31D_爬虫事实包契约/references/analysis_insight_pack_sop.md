---
domain: crawler
tier: L3
doc_status: active-ssot
ssot_check: NEW
map_updated: true
related:
  - @@GENERAL_ROOT:win@@\assets\skills\S31_爬虫策略探勘与选型\subskills\S31D_爬虫事实包契约\SKILL.md
  - @@GENERAL_ROOT:win@@\assets\skills\S31_爬虫策略探勘与选型\subskills\S31D_爬虫事实包契约\scripts\analysis_insight_pack.py
  - @@GENERAL_ROOT:win@@\assets\skills\S31_爬虫策略探勘与选型\subskills\S31D_爬虫事实包契约\scripts\crawler_fact_pack.py
  - @@GENERAL_ROOT:win@@\assets\workflows\W31_爬虫探勘与事实采集工作流.md
birth_ceremony_id: bc-s31d-analysisinsight-7b6d2f1a
birth_ceremony_date: 2026-06-10
---

# analysis_insight_pack.v1 SOP

## 定位

`analysis_insight_pack.v1` 是 `crawler_fact_pack.v1` 之后的分析交接契约。它不重新采集事实，也不替代业务报告；它只负责把可报告的洞察、建议和报告 claim 固定到可回溯的事实 item 上。

第一性边界：

- `crawler_fact_pack.v1` 保存观察到的事实。
- `analysis_insight_pack.v1` 保存基于事实的洞察、推断依据和报告可引用 claim。
- 最终报告只能消费 `analysis_insight_pack.v1.report_claims[]` 或直接引用 fact pack；不得把无来源判断写成事实。

## 最小结构

```json
{
  "schema_version": "analysis_insight_pack.v1",
  "generated_at": "UTC ISO-8601",
  "source_fact_pack": {
    "ref": "crawler_fact_pack.v1.checked.json",
    "schema_version": "crawler_fact_pack.v1",
    "platform": "source platform",
    "query": "source query",
    "collection_status": "ok | partial | failed"
  },
  "coverage": {},
  "findings": [],
  "report_claims": [],
  "recommendations": [],
  "zero_insight_diagnosis": {},
  "validation": {},
  "report_handoff": {}
}
```

## 硬规则

1. 每条 `findings[]` 必须有 `evidence_anchors[]` 和 `source_item_refs[]`，并回指 `crawler_fact_pack.v1.items[]` 的真实 `item_index`。
2. 每条 `findings[]` 必须有 `basis` 和 `confidence`。`basis` 写明为什么这些事实足以支撑该洞察；`confidence` 必须是 0 到 1 的数值。
3. 趋势类洞察（如 `market_trend`、`trend_signal`、`trend_judgement`）必须额外写 `time_window` 和 `comparison_anchor`。没有时间窗和对照锚点时，只能写样本观察，不能写趋势判断。
4. 每条 `report_claims[]` 必须写 `finding_id`、`evidence_anchors[]`、`source_item_refs[]` 和 `source_fact_pack_ref`。报告层不能新增无来源 claim。
5. 负面判断发生在记录抽取之后。非负面评论、普通评论和参考评论仍可作为 `reference` 类 evidence 使用，不得在采集前丢弃。
6. 没有可锚定洞察时必须输出 `zero_insight_diagnosis`，并让 `report_handoff.ready_for_report=false`；禁止为了生成报告而编造 finding。

## 字段说明

| 字段 | 含义 |
|:---|:---|
| `finding_id` | 洞察稳定标识，供报告 claim 和 recommendation 引用 |
| `category` / `insight_type` | 洞察类型，如 `sample_scope`、`metric_signal`、`audience_pain`、`evidence_gap`、`market_trend` |
| `statement` | 可读洞察句子 |
| `basis` | 事实到洞察的推理依据 |
| `confidence` | 0 到 1 的置信度 |
| `evidence_anchors[]` | 回指 item 字段、URL、标题和 snippet 的证据锚 |
| `source_item_refs[]` | 最小来源引用，至少包含 `item_index`、`field`、`source_url` |
| `time_window` | 趋势判断覆盖的时间范围 |
| `comparison_anchor` | 趋势判断的对照来源，如上一周、上一批、同源历史样本 |
| `zero_insight_diagnosis` | 空洞察原因和不交付报告的证据说明 |

## 生成命令

```powershell
@@PYTHON_EXE:win@@ `
  @@GENERAL_ROOT:win@@\assets\skills\S31_爬虫策略探勘与选型\subskills\S31D_爬虫事实包契约\scripts\analysis_insight_pack.py `
  --input C:\path\crawler_fact_pack.v1.checked.json `
  --output C:\path\analysis_insight_pack.v1.json `
  --fact-pack-ref crawler_fact_pack.v1.checked.json
```

## 消费边界

- S18/S32/P2/S8 等报告或分析层只消费 `report_claims[]`、`recommendations[]` 和可回查的 fact item refs。
- 平台 adapter、搜索发现、媒体抽帧、ASR 和评论采集不在本契约内，它们继续由 S31A/S31B/S31C/S31E/S31F/S31G 负责。
- 项目专属竞品、URL、ASIN、商品 ID 和运行证据留在项目 evidence 目录；本 SOP 只保存跨项目通用分析契约。
