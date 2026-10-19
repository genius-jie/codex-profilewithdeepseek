# Provider 路线与回退作战手册

这份手册把“一个站点抓不到就换入口/换对象”的经验固化为跨项目流程。它只规定技术事实和回执，不替业务 Owner 选择主事实源，也不把某个项目的查询词变成固定规则。

## 1. 先区分两种故障

| 故障层级 | 典型表现 | 处理 | 结束条件 |
|---|---|---|---|
| 对象级 | 某个 URL、帖子、剧集或评论读取失败；错误页；字段缺失 | 保留该对象的原始回执，标记 `quarantined` 或 `item_failed`，继续处理同一批其他对象 | 批次结束后汇总失败对象和可用对象 |
| 路线级 | 命令缺失、字段整体不返回、分页能力缺失、会话/Provider 全部失败 | 保留原路线 receipt，按已登记 fallback 顺序切换到同源或公开替代入口 | 新路线单独产生 receipt，并写 `fallback_chain` 与 `selected_strategy` |

一个对象失败不代表站点路线失败；一个对象成功也不代表路线完整。只有重复、可复现的路线事实才进入共享能力经验。

## 2. 能力探针阶梯

从最薄的现成能力开始，逐级下探，成功后停止继续造轮子：

1. **O0 — OpenCLI 原生命令**：
   `opencli <site> --help -f yaml` → `opencli validate <site>`（可用时）→ 最小真实 probe。
2. **O1 — OpenCLI 结构化输出**：优先 `-f json` / `-f yaml`；确认返回字段、对象 ID/URL 和错误码。
3. **O2 — 已登记公开替代入口**：官方 RSS、公开 API、站点 SSR 数据或同 Provider 的另一命令；每个入口单独回执。
4. **O3 — OpenCLI Browser Bridge**：只有目标页面需要动态渲染、交互、公开 DOM、Network 或页面内 JSON/XML 时使用 `browser open/extract/eval`。页面状态、session 和原始输出必须保留。
5. **O4 — 项目既有 fallback**：只在 O0–O3 的失败证据支持时采用；接入前回到 S31A/W31，不能在业务脚本里临时复制一套爬虫。

探针记录至少包含：命令帮助快照或引用、实际命令、返回格式、字段覆盖、分页信号、会话要求、原始响应路径、选择原因和下一步。

## 3. 通用采集循环

```text
能力探针
  -> discover/search（保留每一行）
  -> detail/read（逐对象尝试）
  -> companion facets（评论、转录、作者页、剧集、引用等）
  -> 结构化归一化（ID/URL/时间/数量/哈希）
  -> completeness 评估
  -> Agent 语义分析
  -> 人工准入或下游交接
```

### 3.1 发现阶段

- 发现结果全部保留为 `candidate`、`reference_only` 或 `quarantined`，不因标题、排名或关键词静默丢弃。
- `limit` 是请求上限，不是全量证明；若 Provider 返回超过请求上限的行，全部保留并记录实际行数。
- 搜索结果与详情结果分开计数。详情循环应处理单条异常后继续下一条。

### 3.2 详情和伴随维度

- 每个业务要求的 facet 都要有 `present`、`missing`、`partial` 或 `failed` 状态。
- 评论/互动数字不能替代评论正文；剧集总数不能替代剧集列表；文章署名不能替代作者页；视频元数据不能替代字幕/转录。
- 任何转述、引用、编辑摘要或评论都可以作为证据，但记录 `source_role`、`relation_to_subject`、`evidence_scope` 和原文边界，不能把它改写成另一主体的原话。

## 4. 完整性判定

优先复用目标项目的 `from_payload` / `assess_receipt`。统一输出：

```yaml
discovered_rows: 0
detail_expanded_rows: 0
actual_fetched_rows: 0
reference_only_rows: 0
quarantined_rows: 0
failure_count: 0
pagination:
  status: complete|partial|unknown|unsupported
  provider_total: null
  has_more: null
  next_cursor: null
stop_reason: provider_exhausted|reported_total_reached|limit_reached|provider_no_pagination|access_blocked|error
completeness: complete|partial|unknown|failed
```

只有同时满足以下条件才写 `complete`：

- Provider 明确报告列表结束、总量已覆盖，或已登记公开替代 feed 明确结束；
- 声明范围内的每个发现对象都已尝试详情；
- 必需 facet 已按其独立回执取得，且没有未解释的失败/隔离项；
- 实际有物理证据的条目数与声明范围一致。

裸数组、达到 limit、分页字段缺失或只读到一页都写 `partial` / `unknown`。这不是失败，而是对证据范围的准确描述。

## 5. 回退矩阵

| 首路线事实 | 首选回退 | 保留内容 | 不要做的事 |
|---|---|---|---|
| 单条详情失败 | 同一查询的下一个 URL/ID | 失败回执、失败对象、成功对象 | 让整批任务提前结束 |
| 搜索返回空 | 同一 Provider 的已声明宽查询或同源入口 | 原查询 receipt、fallback query、结果差异 | 把宽查询结果冒充原查询结果 |
| 站点命令字段不足 | 官方 RSS/API/SSR 或 Browser 页面内公开数据 | 字段缺口、替代路线 receipt | 在 Python 里猜隐藏分页或私有接口 |
| 评论/互动缺失 | 平台公开评论命令、页面公开评论或关联社区 | 缺失原因、已取得互动数字、替代入口 | 用点赞/评论总数生成评论内容 |
| 转录/字幕缺失 | 官方转录、RSS show notes、公开字幕或另一条内容对象 | 原始失败、候选对象、来源关系 | 用标题或摘要代替音频正文 |
| 分页无游标 | 提高已声明上限、官方 feed、下一次新鲜 probe | 实际返回量、上限、停止原因 | 把一次大 limit 写成全量 |

每次回退必须追加一个 `fallback_chain` 项：`from_route`、`to_route`、`trigger`、`receipt_ref`、`selected_strategy`、`scope_change`、`status`。

## 5.1 Feed / RSS fallback

Feed 是同源替代入口，不是自动的全历史证明。推荐顺序：

```text
原生 search/list
→ provider 官方 feed
→ Browser Bridge 读取页面内原始 XML/JSON
→ 标准解析器提取 item/entry
→ provider-native ID（GUID 等）+ 规范化标题/日期去重
```

回执同时保存原生列表数量、Feed item 数量、去重后数量、Feed URL、解析器和快照完整性。`complete_for_feed_snapshot` 只表示该快照内的 item 已解析；当供应方声明总数超过返回量、Feed 可能截断或没有归档边界时，整体保持 `partial`/`unknown`。备用 Browser 确实补齐同一目标与范围后，首选 Feed 传输失败可标 `fallback`/`superseded`，失败原文仍保留；其他未完成 facet 继续计为缺口，不随单项恢复升级。换源也保持原任务要求，见 [能力守恒不变量](../SKILL.md#能力守恒不变量)。

## 5.2 Blog / publication provider

优先使用已登记的原生命令；没有专用适配器时，使用 `google search`（带 `site:` 或已知作者域）→ `web read`。通用路线必须把平台归属当作待核验事实：页面域名、页面元数据和正文分别保留，平台不明时使用 `platform_unverified`。WordPress、Ghost、Blogger、Tumblr、Beehiiv、Patreon 等自托管或分散域名不应被硬编码成一个站点适配器。

## 5.3 内容形态与平台分离

平台是 provider，业务类型由内容形态和来源关系决定。同一 YouTube provider 可以产生两类候选：有频道/播放列表/剧集关系的长对话进入 Podcast 路线，独立短片进入 ShortVideo 路线。使用哪条路线应由调用方的 route spec 明确，Agent 只分析已取得的内容证据；不要从平台名称自动推导业务分类。

## 6. OpenCLI Browser Bridge

当 O0 命令需要浏览器时，先用项目/宿主既有健康检查确认 session；不要把 daemon、扩展或登录状态问题误归因于目标站点。对公开 XML/JSON 页面，优先读取页面内原始节点，再交给标准解析库；对长页面用 `browser extract --start` 的返回偏移续读，每块保存 `raw_ref`、字符起止和哈希。

浏览器读取成功只证明页面可见，不证明分页已结束。每次 `open`、`extract`、`eval` 都要进入原始命令回执；页面返回验证页、空壳、登录墙或错误页时，保留原文并进入 `partial` / `failed`。

## 7. 交接字段

通用交接最少包括：

```json
{
  "capability_id": "...",
  "selected_strategy": "opencli|opencli+rss|opencli+browser|api|ssr_json",
  "route_receipt_ref": "...",
  "adapter_receipt_ref": "...",
  "raw_response_refs": [],
  "fallback_chain": [],
  "completeness": "complete|partial|unknown|failed",
  "facet_missing": [],
  "item_failures": [],
  "next_hops": [],
  "next_owner": "..."
}
```

下游只消费其正式契约允许的记录。候选、参考、隔离和失败数据可以支持后续探勘，但不自动成为正式业务事实。
