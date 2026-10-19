---
domain: crawler
tier: L3
doc_status: active-reference
related:
  - @@GENERAL_ROOT:win@@\assets\workflows\W31_爬虫探勘与事实采集工作流.md
  - @@GENERAL_ROOT:win@@\assets\skills\S31_爬虫策略探勘与选型\subskills\S31A_数据源探针与路线选型\SKILL.md
  - @@GENERAL_ROOT:win@@\assets\skills\S31_爬虫策略探勘与选型\subskills\S31D_爬虫事实包契约\SKILL.md
birth_ceremony_id: bc-sourceprioritysop-0f4a9c2e
birth_ceremony_date: 2026-06-10
---

# 数据源事实源优先级 SOP

## 使用边界

本文件给 W31 在 S31A 之前做 `data_source_decision` 使用。它回答“哪个数据源最能代表当前业务事实”，不回答“这个源怎么抓”。选中的源再进入 S31A，由 S31A 输出 `s31a_route_receipt.v1`。

本文件不替代 S31A 的技术路线优先级，也不替代 S31D 的事实包契约。抓取失败只能降低执行可行性，不能把低权威平台自动升成主事实源。源优先级理由进入 `data_source_decision_receipt.v1`、W31 handoff 或 `inference[]`，不得冒充 S31D observed facts。

## 深度调研门禁

`data_source_decision` 不能只按本文件的典型矩阵拍板。非模糊需求必须先完成一轮轻量但真实的源调研，再给结论。

最小调研深度：

1. 解析需求：拆出实体、地域、业务目标、时间窗和事实字段；缺关键项时先澄清。
2. 发现候选源：至少用两种发现方式，例如搜索引擎、平台内搜索、官方入口、行业目录、包仓库、地图/POI、新闻或社区检索。
3. 覆盖源族谱：非模糊需求至少比较三个 `source_family`。如果领域天然少于三个，receipt 必须写明原因。
4. 采集证据：每个主事实源和交叉验证源至少有一条 `source_evidence`，证据要能说明为什么它适合当前事实维度。
5. 反证排除：每个排除源至少有一条 `exclusion_evidence`，说明它为什么不能当主事实源，而不是只写“不适合”。
6. 给置信度：`confidence` 只能来自调研证据。证据不足时写 `low` 或 `medium`，不能写 `high`。

允许使用规则矩阵做初筛，但最终裁决必须由调研证据支持。只看到“平台好抓”不能算源权威；只看到“平台热门”也不能算业务事实。

## 固定评分顺序

数据源评分按下面顺序裁决。前一项明显不足时，后一项不能反向覆盖它：

1. 业务事实权威性：是否是一手事实、官方事实、交易事实或领域内事实发生地。
2. 字段覆盖度：是否覆盖目标字段、口径、区域、时间窗和明细粒度。
3. 时效性：是否能反映目标业务的当前状态或需要的历史窗口。
4. 可复现性：是否有稳定入口、可重复查询、可保存证据和质量状态。
5. 抓取摩擦：登录、风控、限流、成本、配额、动态渲染和维护成本。

输出时可给每项 1 到 5 分。总分只用于排序参考，不能违背上面的固定顺序。

## 数据源族谱

| source_family | 典型来源 | 适合事实 |
|:---|:---|:---|
| `official_source` | 品牌官网、官方店、官方公告、官方文档 | 官方价格、规格、政策、版本、发布日期 |
| `commerce_marketplace` | 天猫、京东、淘宝、拼多多、Amazon、eBay 商品页 | 在售价格、销量线索、库存、评价、SKU |
| `secondhand_marketplace` | 闲鱼、转转、Facebook Marketplace、Mercari | 二手成交/挂牌行情、成色、议价区间 |
| `social_content` | 小红书、抖音、微博、TikTok、YouTube、Instagram | 口碑、趋势、种草、用户表达、传播样本 |
| `search_news` | 搜索引擎、新闻站、RSS、聚合榜单 | 发现入口、新闻事件、舆情覆盖面 |
| `forum_community` | Reddit、知乎、贴吧、Discord、专业论坛 | 深度讨论、问题反馈、技术经验 |
| `map_poi` | 高德、百度地图、Google Maps、Apple Maps | 本地商户、POI、地址、坐标、电话、营业状态 |
| `review_local` | 大众点评、美团、Yelp、Tripadvisor | 本地口碑、评分、评论、门店服务体验 |
| `developer_registry` | GitHub、npm、PyPI、Maven、Docker Hub | 技术对象、版本、依赖、维护活跃度 |
| `finance_market` | 交易所、行情 API、上市公司公告 | 价格行情、成交、财务披露、市场状态 |
| `regulatory_public` | 政府、监管、法院、商标、公开登记 | 资质、备案、处罚、注册、合规事实 |
| `generic_web` | 官网外静态页、博客、黄页、目录站 | 补充线索、发现入口、低权威候选 |

## 源角色

| role | 含义 |
|:---|:---|
| `primary_fact_source` | 当前业务问题的一手或最高权威事实源 |
| `market_signal_source` | 交易、报价、销量、挂牌或市场变化信号 |
| `sentiment_source` | 用户口碑、情绪、趋势和传播证据 |
| `discovery_source` | 找候选源、关键词、实体别名和新闻入口 |
| `enrichment_source` | 补字段、补坐标、补联系人、补类目 |
| `cross_check_source` | 用来验证主源字段、口径或异常 |

## 典型裁决矩阵

| 用户目标 | 主事实源 | 交叉验证源 | 常见排除口径 |
|:---|:---|:---|:---|
| 商品销售、价格、SKU | 官方店、品牌官网、电商平台 | 搜索、社交口碑、历史价格站 | 二手平台不能代表在售价格；社交平台不能代表销售事实 |
| 二手行情、残值、转卖 | 二手平台 | 电商新价、论坛、社交经验帖 | 官方定价不能代表二手成交；新闻只作发现 |
| 口碑、趋势、种草 | 社交内容平台、视频平台、论坛 | 搜索、新闻、电商评价 | 官方宣传不能代表用户口碑；纯电商价格不是趋势事实 |
| 本地商户名录 | 地图/POI | 点评平台、官网、黄页 | 纯社交帖不能作为商户名录主源 |
| 本地服务口碑 | 点评平台、本地评论平台 | 地图/POI、社交、搜索 | 地图字段可补地址坐标，但不能单独代表服务体验 |
| 话题舆情 | 搜索、新闻、社交、论坛 | 官方公告、榜单、内容平台 | 单一平台热度不能代表全网舆情 |
| 海外商品口碑 | Amazon/eBay/品牌官网、Reddit/YouTube/TikTok | Google Search、新闻、专业评测站 | 国内平台不能代表海外口碑主源 |
| 技术对象/开源库 | 官方文档、GitHub、包仓库 | Stack Overflow、论坛、博客 | 二手转述不能替代官方版本和仓库事实 |
| 金融行情/监管事实 | 交易所、行情源、监管公告 | 新闻、公司公告、分析平台 | 社交观点不能代表行情或监管事实 |

需求模糊时，必须先判断是否缺少业务目标、地域、实体类型、时间窗或事实字段。缺少关键要素时写 `clarification_needed=true`，不要强行选择主源。

## `data_source_decision_receipt.v1`

最小回执：

```json
{
  "schema_version": "data_source_decision_receipt.v1",
  "business_goal": "string",
  "entity_type": "product | topic | local_business | technical_object | organization | unknown",
  "region_scope": "cn | global | overseas | local | unknown",
  "fact_dimensions": ["price", "sales", "sentiment"],
  "research_depth": {
    "status": "completed | blocked_by_clarification",
    "entity_normalized": "string",
    "discovery_methods": ["search_engine", "platform_search"],
    "candidate_family_count": 3,
    "evidence_count": 8,
    "minimum_depth_met": true
  },
  "discovery_process": {
    "queries": [],
    "platform_checks": [],
    "official_entry_checks": [],
    "notes": []
  },
  "source_evidence": {},
  "candidate_sources": [],
  "selected_primary_sources": [],
  "cross_check_sources": [],
  "excluded_sources": [],
  "exclusion_evidence": {},
  "decision_trace": [],
  "confidence": "low | medium | high",
  "clarification_needed": false,
  "next_s31a_targets": []
}
```

`candidate_sources[]`、`selected_primary_sources[]` 和 `cross_check_sources[]` 使用同一源对象子集：

```json
{
  "source_id": "official_store_cn",
  "platform": "brand official store",
  "source_family": "official_source",
  "role": "primary_fact_source",
  "priority_rank": 1,
  "score": {
    "fact_authority": 5,
    "field_coverage": 5,
    "freshness": 4,
    "repeatability": 4,
    "crawl_friction": 3,
    "total": 21
  },
  "authority_basis": "Official selling surface for current SKU and list price.",
  "target_fields": ["sku", "price", "inventory", "promotion"],
  "expected_collection_mode": "query_search_data_collection",
  "probe_hint": "Send selected source to S31A for opencli/api/ssr/browser route probing."
}
```

`excluded_sources[]` 至少包含：

```json
{
  "source_family": "social_content",
  "reason": "Useful for口碑 but not authoritative for sales price.",
  "can_be_reintroduced_as": "cross_check_source"
}
```

`next_s31a_targets[]` 是 W31 交给 S31A 的技术路线目标：

```json
{
  "target": "brand official store",
  "platform": "tmall",
  "source_decision_ref": "data_source_decision_receipt.v1",
  "source_id": "tmall_official_store",
  "source_family": "commerce_marketplace",
  "source_role": "primary_fact_source",
  "source_priority_rank": 1,
  "business_goal": "collect current sales price and SKU facts",
  "fact_dimensions": ["price", "sku", "review_count"],
  "collection_mode": "query_search_data_collection"
}
```

## W31 到 S31A 的交接

1. W31 先输出 `data_source_decision_receipt.v1`。
2. 非模糊需求必须至少有一个 `selected_primary_sources[]`，并生成对应 `next_s31a_targets[]`。
3. S31A 对每个 `next_s31a_targets[]` 只判断技术路线，并把 `source_decision_ref`、`source_family`、`source_role`、`source_priority_rank` 原样写入 route receipt。
4. S31D 只接收采集后的 observed facts。源优先级理由、排除理由、业务判断和抓取可行性只能进入 receipt、handoff 或 `inference[]`。
5. 如果主事实源抓取失败，W31 先保留失败 evidence，再决定降级到交叉验证源。降级源必须标记为 `fallback_from_primary`，不能改写成原始主事实源。
