---
domain: crawler
tier: L3
doc_status: active-reference
related:
  - @@GENERAL_ROOT:win@@\assets\skills\S31_爬虫策略探勘与选型\subskills\S31A_数据源探针与路线选型\SKILL.md
  - @@GENERAL_ROOT:win@@\assets\skills\S31_爬虫策略探勘与选型\SKILL.md
  - @@GENERAL_ROOT:win@@\assets\workflows\W31_爬虫探勘与事实采集工作流.md
  - @@GENERAL_ROOT:win@@\assets\skills\S31_爬虫策略探勘与选型\subskills\S31D_爬虫事实包契约\SKILL.md
  - @@GENERAL_ROOT:win@@\tooling\w31\w31_p0_p6_matrix.py
  - @@GENERAL_ROOT:win@@\tooling\w31\w31_p0_p6_acceptance.py
birth_ceremony_id: bc-s31a-crawlerprio-6d8b2f41
birth_ceremony_date: 2026-06-10
---

# 爬虫路线优先级 SOP

## 使用边界

本文件给 S31A 做路线选型用。遇到未知站点、内容平台、文档站、地图/POI、本地生活站或需要浏览器登录的页面时，先按这里排序，再写 `s31a_route_receipt.v1.json`。

它不替代 S31D 的事实包契约，也不把外部工具直接升成 S31 主路线。工具只有通过冒烟测试，且能稳定产出目标字段，才允许进入后续节点。

## 总原则

1. 先选字段最直接、动作最少、可重复执行的路线。
2. 上一级冒烟通过就停止，不并行堆 Browser、Playwright 或人工浏览器。
3. GitHub star 只看生态和维护风险，不决定路线优先级。
4. 工具输出只算原始证据，最终仍要回到 S31D fact pack。
5. 事实字段和推断字段分开。LLM 摘要、重写、判断只能进 `inference[]`。
6. 登录、验证码、字段缺失、selector miss、blocked、partial 必须写成质量状态，不能静默吞掉。

## 路线优先级

| 优先级 | 路线 | 适用场景 | 放行条件 | 降级条件 |
|:---|:---|:---|:---|:---|
| P0 | 官方 API / 公开结构化源 / 地图 POI | 目标字段能从官方接口、开放 API、地图 Web Service 或站点公开 JSON 直接拿到 | 字段覆盖目标，响应可复刻，配额可说明 | 字段缺失、配额不可控、响应不可复刻 |
| P1 | OpenCLI / O0 / 本地私有 adapter | OpenCLI 已有站点命令，或能用最小本地 adapter 补齐字段 | 命令实测返回目标字段，登录态可维持，`opencli validate` 通过 | 命令缺失、字段缺失、`AUTH_REQUIRED`、验证码、adapter 校验失败 |
| P2 | 平台专家工具 | 中文内容平台、社媒平台需要搜索、详情、评论、登录态或平台专门逻辑 | 隔离 POC 通过，依赖可控，输出字段能映射 fact pack | 依赖污染全局环境、只能跑浏览器但无结构化字段、无法复现 |
| P3 | 通用爬虫框架 | 已知 URL/API 结构，需要批量调度、限速、重试、增量、管道化 | Scrapy/Crawlee 等框架能稳定跑通样本并落盘 | 站点强动态、登录态复杂、字段只能靠浏览器内存读取 |
| P4 | 文档/RAG 抽取工具 | 文档站、博客、静态页面、知识库清洗、Markdown/LLM-ready 文本 | Crawl4AI、Firecrawl、ScrapeGraphAI、Jina 等能保留来源和字段边界 | 输出不可追溯、正文被改写、事实和摘要混在一起 |
| P5 | Playwright / Puppeteer / SeleniumBase / CDP | 动态渲染、人工登录会话、小样本验证、adapter 开发辅助 | 截图、DOM、Network 或下载证据完整，样本规模受控 | 可用 OpenCLI/API/SSR 覆盖，或浏览器路线没有稳定字段 |
| P6 | browser-use / Stagehand / agent 自带浏览器 | 人机协同探索、页面调试、失败复现、截图验收 | 只用于探路和取证，不承诺生产批量采集 | 需要稳定、可重复、无人值守的事实采集 |

S31A 原有 `O0 -> A -> A1 -> B` 仍是主判路骨架。上表只是把工具生态放到同一张优先级表里：P1 对应 O0，P0/P3/P4 多数落到 API/结构化采集，P5/P6 才进入 Browser fallback。

## 当前工具口径

- OpenCLI：默认第一探针。只要 adapter 覆盖目标字段，就选 `opencli`，业务脚本只负责编排、落盘和 fact pack。
- MediaCrawler：作为 P2 平台专家工具候选。只允许隔离 POC，不允许全局安装。优先按 `pyproject.toml + uv.lock` 装到项目本地环境；`requirements.txt` 与 `pyproject.toml` 不一致时，不用它污染全局 Python。
- Playwright：作为 P5 fallback 或 adapter 开发工具。默认不优先；只有 OpenCLI/API/SSR 失败或必须复用人工登录会话时才用。
- Scrapy / Crawlee：适合已经明确结构的规模化抓取，不适合替代前置探针。
- Crawl4AI / Firecrawl / ScrapeGraphAI / Jina：适合文档和 RAG 清洗。进入事实包时必须保留来源，不得把 LLM 摘要当原始事实。
- browser-use / Stagehand / agent 自带浏览器：适合交互探索和截图验收，不作为稳定批采路线。

## 冒烟测试门槛

新工具进入候选链前，至少跑完这些检查：

1. 本地环境边界：装到隔离目录，不改全局 Python/Node。
2. 启动检查：`--help`、版本号或最小导入能跑通。
3. 样本检查：取 1 到 3 条公开样本，输出 JSON 或可解析文本。
4. 字段检查：目标字段、来源 URL、时间、质量状态能落盘。
5. 失败检查：登录、验证码、限流、字段缺失有明确状态和 evidence。
6. 映射检查：能说明进入 S31D 哪个 fact pack 类型。

没有跑完这些检查，只能写成候选工具，不能写成默认路线。

## P0-P6 契约矩阵证据索引

W31 出口门禁用稳定脚本 `@@GENERAL_ROOT:win@@\tooling\w31\w31_p0_p6_matrix.py` 生成 P0-P6 的确定性路线映射夹具，并全部映射到 `crawler_fact_pack.v1`。运行输出只落 scratch，生成器本身不能落在 scratch。

汇总回执：`@@OPENCLAW_ROOT:win@@\scratch\crawler_mvp\evidence\p0_p6_matrix\p0_p6_matrix_summary.json`

S31D 二次校验目录：`@@OPENCLAW_ROOT:win@@\scratch\crawler_mvp\evidence\p0_p6_matrix\s31d_recheck`

放行结果：`all_fact_packs_valid=true`，P0-P6 的 `route_status=passed`，S31D CLI 复验均为 `ok=true`、`errors=[]`。所有夹具必须同时标记 `evidence_mode=contract_fixture` 和 `live_route_verified=false`；这只证明契约映射，不证明外部路线当前可用。

| 优先级 | 契约夹具 | route receipt | fact pack | 备注 |
|:---|:---|:---|:---|:---|
| P0 | official API 映射 | `P0\s31a_route_receipt.v1.json` | `P0\crawler_fact_pack.v1.checked.json` | `selected_strategy=api` |
| P1 | OpenCLI 映射 | `P1\s31a_route_receipt.v1.json` | `P1\crawler_fact_pack.v1.checked.json` | `selected_strategy=opencli` |
| P2 | 平台专家 adapter 映射 | `P2\s31a_route_receipt.v1.json` | `P2\crawler_fact_pack.v1.checked.json` | 保留 `mapping_fixture_not_live_collection` 质量标记 |
| P3 | Scrapy 映射 | `P3\s31a_route_receipt.v1.json` | `P3\crawler_fact_pack.v1.checked.json` | `tool_route=scrapy` |
| P4 | 本地文档抽取映射 | `P4\s31a_route_receipt.v1.json` | `P4\crawler_fact_pack.v1.checked.json` | `tool_route=local_doc_extractor` |
| P5 | Playwright 映射 | `P5\s31a_route_receipt.v1.json` | `P5\crawler_fact_pack.v1.checked.json` | 不包含实时浏览器或截图成功声明 |
| P6 | agent browser HITL 边界映射 | `P6\s31a_route_receipt.v1.json` | `P6\crawler_fact_pack.v1.checked.json` | 保留 `hitl_exploration_only` 质量标记 |

使用这些夹具时，先打开汇总回执确认 `all_fact_packs_valid=true`，再按优先级进入对应目录查 route receipt 和 fact pack。任何 `contract_fixture` 都不能当成实时采集证据；需要证明平台可用时，必须另跑对应路线并保存 live command receipt。

## route receipt 写法

`selected_strategy` 仍使用 S31A 现有枚举：`opencli | map_poi_source | api | ssr_json | browser`。

外部工具不要新造枚举，放到 receipt 的工具证据里：

```json
{
  "selected_strategy": "browser",
  "tool_route": "mediacrawler",
  "tool_receipt": {
    "install_scope": "isolated",
    "smoke_status": "help_passed | sample_passed | blocked",
    "field_coverage": ["title", "url", "author", "publish_time"],
    "quality_states": ["partial"]
  },
  "fallback_chain": [
    {"strategy": "opencli", "status": "AUTH_REQUIRED"},
    {"strategy": "api", "status": "no_stable_json"},
    {"strategy": "browser", "status": "selected"}
  ],
  "next_node": "S31D"
}
```

如果工具实际走的是结构化 API，`selected_strategy` 写 `api`；如果实际靠浏览器会话，写 `browser`。`tool_route` 只说明实现工具，不替代策略。

## MediaCrawler 隔离 POC 规则

MediaCrawler 只在这些条件同时满足时放行：

1. 安装目录限定在项目 scratch 或工具自己的 `.venv`。
2. 优先使用 `uv.lock`，不把 `requirements.txt` 当唯一权威。
3. 先不安装 Playwright 浏览器驱动；默认 CDP 模式能跑就不扩张依赖。
4. 第一阶段只做 `--help`、配置加载、导入检查和公开样本，不做真实账号采集。
5. 通过后再决定是否给 S31C/S31D 增加 adapter 映射。

不满足以上条件时，MediaCrawler 留在 P2 候选，不进入默认链路。

## 禁止项

- 不因 star 高就跳过 OpenCLI/API/SSR 探针。
- 不把浏览器录制、人工点击或 LLM 抽取当成生产级事实采集。
- 不把登录态、Cookie、token、整页缓存和批量业务数据写入 S31A reference。
- 不把单个平台项目直接升成 S31A 的新策略枚举。
