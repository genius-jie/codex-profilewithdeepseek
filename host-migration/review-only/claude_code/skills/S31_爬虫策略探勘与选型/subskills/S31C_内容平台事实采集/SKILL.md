---
name: S31C 内容平台事实采集
type: generic
domain: crawler
tier: L3
doc_status: active-ssot
status: active
birth_ceremony_id: bc-s31c-d5c41ee0
birth_ceremony_date: '2026-05-20'
related:
  - @@GENERAL_ROOT:win@@\assets\skills\S31_爬虫策略探勘与选型\SKILL.md
  - @@GENERAL_ROOT:win@@\assets\workflows\W31_爬虫探勘与事实采集工作流.md
  - @@GENERAL_ROOT:win@@\assets\skills\S31_爬虫策略探勘与选型\references\crawler_capability_registry.yaml
  - @@GENERAL_ROOT:win@@\tooling\w31\w31_crawler_capability_dispatch.py
  - @@GENERAL_ROOT:win@@\tooling\w31\w31_crawler_capability_onboard.py
  - @@GENERAL_ROOT:win@@\assets\skills\S31_爬虫策略探勘与选型\subskills\S31C_内容平台事实采集\scripts\xiaohongshu_fact_probe.py
  - @@GENERAL_ROOT:win@@\assets\skills\S31_爬虫策略探勘与选型\subskills\S31C_内容平台事实采集\scripts\competitor_review_adapters.py
  - @@GENERAL_ROOT:win@@\assets\skills\S31_爬虫策略探勘与选型\subskills\S31C_内容平台事实采集\scripts\platform_shard_runner.py
  - @@GENERAL_ROOT:win@@\assets\skills\S31_爬虫策略探勘与选型\subskills\S31C_内容平台事实采集\scripts\business_metric_routes.py
  - @@GENERAL_ROOT:win@@\assets\skills\S31_爬虫策略探勘与选型\subskills\S31C_内容平台事实采集\scripts\opencli_health_check.py
  - @@GENERAL_ROOT:win@@\assets\skills\S31_爬虫策略探勘与选型\subskills\S31C_内容平台事实采集\scripts\xhs_collector.py
  - @@GENERAL_ROOT:win@@\assets\skills\S31_爬虫策略探勘与选型\subskills\S31C_内容平台事实采集\scripts\xhs_shard_runner.py
  - @@GENERAL_ROOT:win@@\assets\skills\S31_爬虫策略探勘与选型\subskills\S31C_内容平台事实采集\scripts\xhs_fixed_note_comments.py
  - @@GENERAL_ROOT:win@@\assets\skills\S31_爬虫策略探勘与选型\subskills\S31C_内容平台事实采集\scripts\epub_pub_pipeline.py
  - @@GENERAL_ROOT:win@@\assets\skills\S31_爬虫策略探勘与选型\subskills\S31C_内容平台事实采集\references\epub_pub_book_crawl_sop.md
  - @@GENERAL_ROOT:win@@\assets\skills\S31_爬虫策略探勘与选型\subskills\S31C_内容平台事实采集\references\platform_sops
  - @@GENERAL_ROOT:win@@\assets\skills\S31_爬虫策略探勘与选型\subskills\S31C_内容平台事实采集\references\platform_sops\dianping_crawl_sop.md
  - @@GENERAL_ROOT:win@@\assets\skills\S31_爬虫策略探勘与选型\subskills\S31C_内容平台事实采集\references\platform_sops\pinduoduo_crawl_sop.md
  - @@GENERAL_ROOT:win@@\assets\skills\S31_爬虫策略探勘与选型\subskills\S31C_内容平台事实采集\resources\reports\2026-05-19_AI玩具_周热度舆情研报.md
  - @@GENERAL_ROOT:win@@\assets\skills\S31_爬虫策略探勘与选型\subskills\S31E_跨平台视频源解析\SKILL.md
  - @@GENERAL_ROOT:win@@\assets\skills\S31_爬虫策略探勘与选型\subskills\S31B_媒体证据探针\SKILL.md
  - @@GENERAL_ROOT:win@@\assets\skills\S31_爬虫策略探勘与选型\subskills\S31G_转录质检与摘要审阅\SKILL.md
  - @@GENERAL_ROOT:win@@\assets\skills\S31_爬虫策略探勘与选型\subskills\S31D_爬虫事实包契约\SKILL.md
description: |
  【触发场景】内容平台、图文社区、社媒平台、公开文章或电子书站点的搜索、详情、正文、评论、下载、切片采集和内容事实包生成。
  【不触发】路线探勘走 S31A；媒体/ASR 走 S31E/S31B/S31F；fact_pack 校验走 S31D；本地生活名录走 W31。
  【功能】作为内容平台采集 facade，按 platform adapter 执行；小红书只是 `xiaohongshu` adapter/example。
extends:
  - @@GENERAL_ROOT:win@@\assets\rules\execution.md
  - @@GENERAL_ROOT:win@@\assets\references\methodology\10_S-Tier-Execution-Discipline-Protocol.md
---
# S31C_内容平台事实采集

## 定位

S31C 不是具体平台 Skill。它负责“内容平台事实采集”这一类通用流程：

1. 搜索或列表入口采样。
2. 帖子、笔记、动态或内容详情采集。
3. 公开长文或电子书站点的章节、段落、目录、正文和资源完整性采集。
4. 评论、互动指标、发布时间、作者和媒体引用采集。
5. 按平台 adapter 写 checkpoint、样本报告和 `crawler_fact_pack.v1` 草稿。

S31C 的 JSON、checkpoint 和事实包都是机器事实层，不得把 `final_analysis_report*.json` 命名或宣告为用户最终报告。用户明确要求竞品分析、舆情报告或可视化研报时，S31C 完成全量采集与事实校验后，必须把事实引用交给 S18/S9 或对应业务报告 Skill，最终交付至少包含可直接打开的 `.html`；JSON 只作为可追溯中间件随附。

平台差异只能落在 adapter、reference、example 或测试夹具里。新增抖音、B站、论坛、图文社区等平台时，优先在 S31C 下增加 `platform_adapter` 说明和最小样例，不再新建 `S31C1_某平台采集` 这类专属 Skill。

当前内置 adapter：

| adapter | 覆盖范围 | 边界 |
|:---|:---|:---|
| `xiaohongshu` | 搜索、笔记、评论、下载、切片调度和样本报告 | 平台实现样例，不代表 S31C 的 Skill 身份 |
| `competitor_review_adapters` | S31A baseline 中 21 个竞品评价平台的统一 adapter facade | 每个平台都有可执行入口，但能力等级必须如实分为 `public_live_adapter` / `controlled_input_adapter` / `discovery_adapter` / `skipped_receipt_adapter`；不得把 discovery 或 skipped 冒充 observed facts |
| `epub_pub` | 单书元数据、OPF manifest/spine、章节、段落、图片、合并正文和可选评论互动 | 公开资产主路线；Browser 只补动态互动，不替代正文完整性校验 |

当前 21 个竞品评价平台 SOP 以 `references\platform_sops` 为准；淘汰平台不进入 baseline，不参与 metric route 必达校验。`epub_pub` 属于专用内容 adapter，入口和验收口径见 `references\epub_pub_book_crawl_sop.md`。

## Adapter 接口规范

S31C 不做目录扫描式隐式发现。默认由 W31 从 `crawler_capability_registry.yaml` 解析稳定 `capability_id`，调度器再把 capability、adapter 入口和 resolution ref 固化到 route receipt、fact pack 与 handoff；未注册或未命中时才由 S31A 探勘并显式生成 route receipt，不允许凭平台名直接猜实现。

### 会话健康前置门禁

账号态、登录态或高风险平台的 live adapter 必须先做 `session_preflight`，再采商品、帖子、评论或详情。preflight 只判断平台是否可采，不产出事实行。

阻断条件包括：未登录、登录过期、二维码、验证码、短信验证、账号风险、空白页、系统繁忙、live 空返回但会话未验证。遇到任一条件，adapter 必须停止本轮 live retry，并在 receipt 写：

- `session_preflight.status=blocked`
- `zero_output_diagnosis.human_action_required=true`
- 登录/二维码/验证码/短信/会话不确定时 `zero_output_diagnosis.requires_human_login=true`
- `zero_output_diagnosis.empty_result_is_not_no_data=true`
- `zero_output_diagnosis.live_retry_allowed=false`

这类结果不能进入 `items[]`，不能算作真实无评论、无评价或无数据。只有公开低风险源且 preflight 不要求登录时，空返回才可以标记为普通 `zero_rows`。

物理归位：

- 父级可复用样例、最小脚本和测试放在 S31C 的 `scripts\`、`examples\`、`references\` 或 `tests\`。
- 项目级生产 adapter 放在 `projects\<project>\adapters\<platform>.py` 或该项目既有 adapter 目录，并在项目 README / REQUIRED_READING / route receipt 中登记入口。
- 一次性业务脚本只能作为项目运行资产；如果沉淀为通用能力，先补 S31C 最小样例或 reference，再更新 adapter 表。

最小接口：

| 函数 | 必需 | 输入 | 输出 |
|:---|:---|:---|:---|
| `search(query, limit, context)` | 是 | 关键词、数量、登录态/排序/时间窗等上下文 | `list[dict]`，每条至少包含稳定 id 或 url、title/source_url/raw |
| `detail(item, context)` | 需要详情字段时 | `search` 返回的单条 item | `dict`，只放观察事实和失败质量标记 |
| `comments(item, limit, context)` | 需要评论时 | 单条 item 和评论上限 | `list[dict]`，失败时返回质量标记或命令回执 |
| `download_media(item, output_dir, context)` | 需要媒体时 | 单条 item 和输出目录 | `list[dict]`，返回本地文件、远程 URL 或失败状态 |
| `to_fact_pack_item(raw, context)` | 是 | adapter 原始记录 | 可映射到 `crawler_fact_pack.v1.items[]` 的事实对象 |

接口边界：

- 函数返回裸事实和质量标记，不返回营销结论、业务建议或摘要判断。
- 登录态、OpenCLI 命令、HTTP 请求和 Browser fallback 的失败必须进入 `command_receipts[]` 或 route evidence。
- adapter 可以用 Python dict 作为薄接口，但字段映射必须能回填 `new_platform_onboarding_template.md` 的 fact pack mapping 表。

## 脚本

| 脚本 | 职责 |
|:---|:---|
| `scripts\competitor_review_adapters.py` | 竞品评价 21 平台统一 adapter facade，输出 `s31c_competitor_review_adapter_receipt.v1` 和 `crawler_fact_pack.v1` |
| `scripts\platform_shard_runner.py` | 21 平台通用 OpenCLI + shard 计划/执行器，输出 `platform_shard_plan.v1.json`、`platform_shard_state.v1.json` 和 `platform_shard_run_receipt.v1`，把 list/details/comments/finalize 固定成可复跑分片。内置 Phase 0 doctor 门禁、Phase 1 autofix 3 轮自修复、network 拦截和视觉风控截图 |
| `scripts\business_metric_routes.py` | 业务指标路由查询与校验入口，读取 S31 `business_metric_route_registry.yaml`，把 platform + metric_id 映射到 required seeds、fact_pack 字段、freshness SLA、质量门禁和 `platform_shard_runner.py` 命令模板 |
| `scripts\opencli_health_check.py` | OpenCLI Phase 0 健康检查模块：封装 `opencli doctor`/`profile list`/`list -f json` 三条连通性验证，产出 `opencli_health_receipt.v1.json`，是 `platform_shard_runner.py` 的前置门禁 |
| `scripts\xiaohongshu_fact_probe.py` | `xiaohongshu` adapter 编排器，输出 `crawler_fact_pack.v1.json` 和 checkpoint |
| `scripts\xhs_collector.py` | `xiaohongshu` 浏览器侧筛选采集器 |
| `scripts\xhs_shard_runner.py` | `xiaohongshu` 切片调度器，内部调用同目录 `xhs_collector.py` |
| `scripts\xhs_fixed_note_comments.py` | 固定链接全量评论采集器；默认走低频签名 API，也可切换可见 DOM 路线。只有唯一评论 ID 数量匹配运行时总量，且不存在重复、缺失或未知层级时才返回 `status=ok` |
| `scripts\epub_pub_book_collector.py` | EPUB.pub 公开 OPF manifest/spine 整本采集实现，生成元数据、章节、段落、资源清单、合并正文和 fact pack 草稿 |
| `scripts\epub_pub_interactions.py` | 把 Chrome 只读页面观察到的评论、相关推荐和作者其他作品合并进 fact pack |
| `scripts\epub_pub_verify.py` | 独立复验资产状态、哈希、章节、段落、目录、正文和 W31 handoff |
| `scripts\epub_pub_pipeline.py` | 一条命令串联 S31A 路线回执、S31C 整本采集、可选互动合并、S31D 校验和 W31 交接 |
| `examples\adapter_contract\minimal_adapter.py` | S31C adapter 最小接口样例，固定 search/detail/comments/download_media/to_fact_pack_item 边界 |

跨 Skill 依赖：

- 不在 import 期加载 S31B/S31D 兄弟脚本；通过子进程和 JSON/文件契约调用。
- S31B 抽帧脚本默认路径可用 `S31B_MEDIA_FRAME_PROBE_SCRIPT` 覆盖。
- S31B 转录 facade 默认路径可用 `S31B_MEDIA_TRANSCRIPT_PROBE_SCRIPT` 覆盖。
- S31D fact_pack 校验脚本默认路径可用 `S31D_CRAWLER_FACT_PACK_SCRIPT` 覆盖。
- 需要跨平台视频源、字幕发现或媒体 URL receipt 时交给 S31E。
- `--transcript-mode auto` 只产出台词证据；是否调用 S31G 生成 `transcript_review.v1` 由 W31 主控在 S31D 事实包校验之后接力，review 路径写入 `w31_handoff.transcript_review_refs[]`。

## 命令

W31 注册能力统一入口（默认）：

```powershell
@@PYTHON_EXE:win@@ `
  @@GENERAL_ROOT:win@@\tooling\w31\w31_crawler_capability_dispatch.py run `
  --url "https://www.epub.pub/book/BOOK-SLUG" `
  --business-profile ebook_single_book_fulltext `
  --collection-mode query_search_data_collection `
  --output-dir C:\path\epub_pub_book_run
```

该入口先写 `w31_crawler_capability_resolution.v1.json`，再执行 registry 指定的 governed pipeline，并检查 adapter receipt、route receipt、checked fact pack 和 W31 handoff 是否齐全且满足 artifact assertions。EPUB.pub pipeline 直接调用只用于已知入口的调试或兼容：

```powershell
@@PYTHON_EXE:win@@ `
  @@GENERAL_ROOT:win@@\assets\skills\S31_爬虫策略探勘与选型\subskills\S31C_内容平台事实采集\scripts\epub_pub_pipeline.py `
  --url "https://www.epub.pub/book/BOOK-SLUG" `
  --output-dir C:\path\epub_pub_book_run
```

评论、相关推荐和作者其他作品已经由 Chrome 只读观察落盘时，追加 `--interaction-observation C:\path\interaction_observation.v1.json --require-interactions`。完整口径见 `references\epub_pub_book_crawl_sop.md`。

快速采集：

```powershell
@@PYTHON_EXE:win@@ `
  @@GENERAL_ROOT:win@@\assets\skills\S31_爬虫策略探勘与选型\subskills\S31C_内容平台事实采集\scripts\xiaohongshu_fact_probe.py `
  --query "AI玩具" `
  --top 2 `
  --comments-per-note 2 `
  --output-dir C:\path\xhs_fact_run
```

筛选和切片：

```powershell
@@PYTHON_EXE:win@@ `
  @@GENERAL_ROOT:win@@\assets\skills\S31_爬虫策略探勘与选型\subskills\S31C_内容平台事实采集\scripts\xiaohongshu_fact_probe.py `
  --mode shard `
  --query "AI玩具" `
  --sort liked --range week `
  --top 10 --comments-per-note 10 `
  --shard-profile fast `
  --output-dir C:\path\xhs_fact_run `
  --frame-strategy periodic --frame-interval 120
```

默认 `--transcript-mode off`；需要台词证据时显式传 `--transcript-mode auto`。

`--timeout` 保留为抽帧超时兼容别名；新调用优先使用 `--frame-timeout`。字幕/ASR 使用独立 `--transcript-timeout`，默认 300 秒，避免 ASR 被抽帧预算误杀。

固定链接全量评论实验入口：

```powershell
@@PYTHON_EXE:win@@ `
  @@GENERAL_ROOT:win@@\assets\skills\S31_爬虫策略探勘与选型\subskills\S31C_内容平台事实采集\scripts\xhs_fixed_note_comments.py `
  --url "<signed-xhs-explore-url>" `
  --output C:\path\fixed-note-comments.json
```

此入口的完成条件以运行时页面总量为准，不允许写死某次样本的评论数。签名链接只作为本次运行输入，不写入 Skill 文档或治理记录。

固定链接路线与反风控规则：

- 默认使用 `--route signed_api --risk-profile conservative`：每批最多 3 个请求，请求间随机等待 1.8–2.6 秒，总请求预算 200；不提供激进档。
- 已登录页面的短时中断优先使用 `--reuse-current-tab --resume-page-state` 续接现有页状态，不重新打开笔记、不重复已完成分页。
- 签名 API 遇到游标停滞、接口技术失败或签名器不可用时，同一路线不重试；下一次运行改用 `--route visible_dom`。可见 DOM 仍必须通过同一动态总量契约，不能因为换路线降低完整性标准。
- 页面出现验证码、短信验证、扫码登录或账号风险时立即停止，禁止在同一账号会话内自动换路线。
- `xsec_token` 只在进程内用于本次请求；输出 JSON、命令回执和错误文本必须去掉签名查询参数，只保存无查询串的笔记 URL。
- `conservative` 是默认档；`balanced` 使用每批最多 5 个请求、1.2–1.7 秒随机间隔，只在会话稳定且任务明确要求提速时使用。

## 资源

- 跨项目运行能力注册表：`@@GENERAL_ROOT:win@@\assets\skills\S31_爬虫策略探勘与选型\references\crawler_capability_registry.yaml`。
- 平台 SOP：`references\platform_sops\`（21 个平台 SOP，路径由 baseline 的 `sop_ref` 字段注册）。
- EPUB.pub 单书 SOP：`references\epub_pub_book_crawl_sop.md`。
- 样本：`resources\samples\`
- 报告：`resources\reports\`

报告和样本属于 S31C adapter example，不再放回 S31 簇入口；真实业务运行输出仍留在业务目录。

## 测试

```powershell
@@PYTHON_EXE:win@@ -m pytest `
  @@GENERAL_ROOT:win@@\assets\skills\S31_爬虫策略探勘与选型\subskills\S31C_内容平台事实采集\tests
```
