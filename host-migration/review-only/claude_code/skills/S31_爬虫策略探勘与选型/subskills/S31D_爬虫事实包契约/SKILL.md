---
name: S31D 爬虫事实包契约
type: generic
domain: crawler
tier: L3
doc_status: active-ssot
status: active
birth_ceremony_id: bc-s31d-cf740f73
birth_ceremony_date: '2026-05-20'
related:
  - @@GENERAL_ROOT:win@@\assets\skills\S31_爬虫策略探勘与选型\SKILL.md
  - @@GENERAL_ROOT:win@@\assets\workflows\W31_爬虫探勘与事实采集工作流.md
  - @@GENERAL_ROOT:win@@\assets\skills\S31_爬虫策略探勘与选型\subskills\S31D_爬虫事实包契约\scripts\crawler_fact_pack.py
  - @@GENERAL_ROOT:win@@\assets\skills\S31_爬虫策略探勘与选型\subskills\S31D_爬虫事实包契约\scripts\analysis_insight_pack.py
  - @@GENERAL_ROOT:win@@\assets\skills\S31_爬虫策略探勘与选型\subskills\S31D_爬虫事实包契约\references\business_listing_fact_pack_mapping.md
  - @@GENERAL_ROOT:win@@\assets\skills\S31_爬虫策略探勘与选型\subskills\S31D_爬虫事实包契约\references\analysis_insight_pack_sop.md
  - @@GENERAL_ROOT:win@@\assets\skills\S31_爬虫策略探勘与选型\subskills\S31D_爬虫事实包契约\examples\business_listing\README.md
  - @@GENERAL_ROOT:win@@\assets\skills\S31_爬虫策略探勘与选型\subskills\S31E_跨平台视频源解析\SKILL.md
  - @@GENERAL_ROOT:win@@\assets\skills\S31_爬虫策略探勘与选型\subskills\S31B_媒体证据探针\SKILL.md
  - @@GENERAL_ROOT:win@@\assets\skills\S31_爬虫策略探勘与选型\subskills\S31F_字幕ASR转写后端\SKILL.md
  - @@GENERAL_ROOT:win@@\assets\skills\S31_爬虫策略探勘与选型\subskills\S31G_转录质检与摘要审阅\SKILL.md
  - @@GENERAL_ROOT:win@@\assets\skills\S31_爬虫策略探勘与选型\subskills\S31C_内容平台事实采集\SKILL.md
description: |
  【触发场景】需要组装、校验、补全或交接 `crawler_fact_pack.v1` 爬虫事实包。
  【不触发】只做站点路线探勘、平台采集或媒体抽帧时不要用，除非要做最终契约校验。
  【功能】提供 fact pack helper 和 CLI 校验，保证事实字段、推断字段、质量标记和命令回执不混淆。
extends:
  - @@GENERAL_ROOT:win@@\assets\rules\execution.md
  - @@GENERAL_ROOT:win@@\assets\references\methodology\10_S-Tier-Execution-Discipline-Protocol.md
---
# S31D_爬虫事实包契约

## 脚本

`scripts\crawler_fact_pack.py` 是 `crawler_fact_pack.v1` 的 helper 与 CLI 校验器。

`scripts\analysis_insight_pack.py` 是 `analysis_insight_pack.v1` 的 helper 与 CLI 校验器。它只消费已校验的 `crawler_fact_pack.v1`，并按 `references\analysis_insight_pack_sop.md` 要求把每条 finding、recommendation 和 report claim 锚定回 fact item。

## 命令

```powershell
@@PYTHON_EXE:win@@ `
  @@GENERAL_ROOT:win@@\assets\skills\S31_爬虫策略探勘与选型\subskills\S31D_爬虫事实包契约\scripts\crawler_fact_pack.py `
  --input C:\path\crawler_fact_pack.v1.json `
  --output C:\path\crawler_fact_pack.v1.checked.json

@@PYTHON_EXE:win@@ `
  @@GENERAL_ROOT:win@@\assets\skills\S31_爬虫策略探勘与选型\subskills\S31D_爬虫事实包契约\scripts\analysis_insight_pack.py `
  --input C:\path\crawler_fact_pack.v1.checked.json `
  --output C:\path\analysis_insight_pack.v1.json `
  --fact-pack-ref crawler_fact_pack.v1.checked.json
```

## 顶层契约

```json
{
  "schema_version": "crawler_fact_pack.v1",
  "platform": "xiaohongshu",
  "query": "AI玩具",
  "collected_at": "UTC ISO-8601",
  "collection_status": "ok | partial | failed",
  "items": [],
  "fact_summary": {},
  "media_source_receipts": [],
  "media_receipts": [],
  "transcript_review_refs": [],
  "command_receipts": [],
  "inference": []
}
```

## 适用边界

`crawler_fact_pack.v1` 是采集事实包，不是所有数据产物的总格式。它适合这些场景：

- 搜索结果、内容帖子、笔记、评论和媒体证据等条目列表采集。
- 商户名录、POI、黄页、招聘、论坛等“列表 + 详情 + 质量标记”采集。
- 可被 W31 handoff 引用的事实证据输入，供 P2/S8/S32 或业务脚本继续消费。

它不承担这些产物的唯一表示：

- 快照型热榜或趋势数据，例如按 `snapshot_date`、`snapshot_slot`、`rank`、`hot_value` 组织的 TopHub 快照；这类产物可以在 W31 handoff 中作为 `raw_data_path` 或业务输出引用，不强行改写为 fact pack。
- 分析型报告，例如营销案例研报、业务判断、可复用打法、合作建议和最终展示页面；这些只能消费 fact pack 或引用其证据，不能把报告本身冒充为 observed facts。
- 分析洞察交接使用 `analysis_insight_pack.v1`；任何 report claim 都必须回指 `crawler_fact_pack.v1.items[]`，趋势判断还必须写时间窗和对照锚点。
- 已有成熟项目模型可以保留自己的领域 schema；只有进入 W31/S31D 交接边界的采集事实需要映射到本契约。

规则：

- 事实字段只放观察到的数据。
- 推断只能进入顶层 `inference[]`，并写 `type`、`basis`、`confidence`。
- S31E/S31B/S31F/S31G 的 receipt 可以作为可选引用字段存在；没有这些字段的旧 fact pack 仍然有效。
- `transcript_review.v1` 是审阅/推断材料，只能作为 `transcript_review_refs[]` 或 `inference[]` 的依据，不得写进 item observed facts。
- W31 的 canonical 路径是先由 S31D 校验事实包，再由 S31G 作为 review tail 生成审阅材料；S31D 只校验已有 `transcript_review_refs[]` 不串入 facts，不负责调用 S31G。
- 视频条目必须有 `media_files` 或 `frame_paths`；没有素材时写 `zero_media_extracted`。
- 命令失败也要落 `command_receipts[]`、`collection_status` 和 `failure_reason`。
- 本地生活商户名录使用 `references\business_listing_fact_pack_mapping.md`，仍保持 `crawler_fact_pack.v1`，只新增 item 里的 `business` 扩展对象。

## 样例包

本地生活商户名录样例放在 `examples\business_listing\README.md`。里面保存了大众点评月子中心采集脚本、分析脚本、测试和 OpenCLI 未登录样例输出；真实运行输出仍留在业务目录，由样例 README 索引，不塞进 Skill 正文。

样例包只收四类内容：

- 可复用脚本和测试。
- 最小失败样例或最小成功样例。
- fact pack 映射说明。
- 能证明路线选择的 receipt 或命令摘要。

这些内容不进入样例包：整批抓取数据、登录态文件、浏览器缓存、`__pycache__`、完整页面归档、临时 Excel、一次性调试目录。需要保留时，把它们放在业务 evidence 目录，并在 README 里写链接或说明。

## 测试

```powershell
@@PYTHON_EXE:win@@ -m pytest `
  @@GENERAL_ROOT:win@@\assets\skills\S31_爬虫策略探勘与选型\subskills\S31D_爬虫事实包契约\tests
```
