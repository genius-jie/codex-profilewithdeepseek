---
name: S31A 数据源探针与路线选型
type: generic
domain: crawler
tier: L3
doc_status: active-ssot
status: active
birth_ceremony_id: bc-s31a-5e167944
birth_ceremony_date: '2026-05-20'
related:
  - @@GENERAL_ROOT:win@@\assets\skills\S31_爬虫策略探勘与选型\SKILL.md
  - @@GENERAL_ROOT:win@@\assets\workflows\W31_爬虫探勘与事实采集工作流.md
  - @@GENERAL_ROOT:win@@\assets\skills\S31_爬虫策略探勘与选型\subskills\S31A_数据源探针与路线选型\resources\opencli_capability_map.md
  - @@GENERAL_ROOT:win@@\assets\skills\S31_爬虫策略探勘与选型\subskills\S31A_数据源探针与路线选型\references\source_priority_sop.md
  - @@GENERAL_ROOT:win@@\assets\skills\S31_爬虫策略探勘与选型\subskills\S31A_数据源探针与路线选型\references\crawler_priority_sop.md
  - @@GENERAL_ROOT:win@@\assets\skills\S31_爬虫策略探勘与选型\subskills\S31A_数据源探针与路线选型\references\competitor_review_route_sop.md
  - @@GENERAL_ROOT:win@@\assets\skills\S31_爬虫策略探勘与选型\subskills\S31A_数据源探针与路线选型\references\platform_crawl_maturity_baseline.yaml
  - @@GENERAL_ROOT:win@@\assets\skills\S31_爬虫策略探勘与选型\subskills\S31A_数据源探针与路线选型\references\high_friction_local_business_sites.md
  - @@GENERAL_ROOT:win@@\assets\skills\S31_爬虫策略探勘与选型\subskills\S31A_数据源探针与路线选型\scripts\route_probe_cli.py
  - @@GENERAL_ROOT:win@@\assets\skills\S31_爬虫策略探勘与选型\subskills\S31D_爬虫事实包契约\SKILL.md
  - @@GENERAL_ROOT:win@@\control\registry\02-skill-catalog.md
description: |
  【触发场景】未知站点需要先判断抓取路线，涉及 OpenCLI/O0、API 抓包、SSR JSON、Browser/Playwright fallback。
  【不触发】平台路线已确定并进入小红书采集、媒体证据或事实包校验时不要继续停留在 S31A。
  【功能】输出最轻可行抓取路线、失败证据、降级条件和交给 W31 后续节点的 route_receipt。
extends:
  - @@GENERAL_ROOT:win@@\assets\rules\execution.md
  - @@GENERAL_ROOT:win@@\assets\references\methodology\02_Exploration-and-Risk-Protocols.md
  - @@GENERAL_ROOT:win@@\assets\references\methodology\10_S-Tier-Execution-Discipline-Protocol.md
---
# S31A_数据源探针与路线选型

## 上游边界

S31A 只负责“选中的源怎么抓”。W31 的 `data_source_decision` 负责先判断哪个数据源最能代表业务事实，并输出 `data_source_decision_receipt.v1`。如果用户只给一句商品或话题需求，且主事实源、交叉验证源和排除源还没有裁决，先回到 W31 的数据源事实源裁决，不直接在 S31A 里用抓取便利性替代业务权威性。

如果上游 `data_source_decision_receipt.v1` 没有 `research_depth.minimum_depth_met=true`，或缺少主源/交叉源/排除源的证据链，S31A 不继续判技术路线。先退回 W31 补调研证据，再接收 `next_s31a_targets[]`。

S31A 接收 `next_s31a_targets[]` 后，只判断 OpenCLI/O0、API、SSR JSON、Browser fallback 等技术路线。抓取摩擦会写入路线 evidence，但不能把低权威平台升成主事实源。

## 路线优先级

按 `O0 -> A -> A1 -> B`，上一级跑通就停止：

| 级别 | 路线 | 判定标准 |
|:---|:---|:---|
| O0 | OpenCLI / 现成适配器 | `resources\opencli_capability_map.md` 中有对应站点或工具面 |
| A | API 抓包 | Fetch/XHR 可复刻，返回结构化 JSON |
| A1 | SSR 状态 JSON | HTML 中存在 `__NEXT_DATA__`、Nuxt state 或同类状态块 |
| B | Browser fallback | 必须动态渲染、交互、登录态、截图或 DOM 内存读取 |

### O0 OpenCLI-first 铁律

OpenCLI 是路线探针的第一选择。探针顺序固定为：

1. 先查 `opencli <site> --help`、`opencli adapter status`、`resources\opencli_capability_map.md`，确认是否已有站点和命令。
2. 若内置 adapter 少一个命令，但 OpenCLI 能以本地私有 adapter 补齐目标字段，优先在 `@@USERPROFILE:win@@\.opencli\clis\<site>\<command>.js` 增加最小命令，再用 `opencli validate <site>` 验证。
3. 只要 OpenCLI 命令实测返回目标字段，route_receipt 的 `selected_strategy` 必须选 `opencli` 或 `opencli+<capability>`；业务脚本只编排调用、落盘、fact pack 和分析，不直接接管浏览器控制。
4. 只有 OpenCLI 命令缺失、字段缺失、登录态不可用、风控/验证码阻断、adapter 校验失败或实测输出不可信时，才允许继续探 API/SSR/Browser。

### OpenCLI Browser Bridge 运行态门禁

当 OpenCLI 需要浏览器登录态、DOM、Network 或截图时，先确认 Browser Bridge 真的连上 daemon：

1. 先保护真人 Profile 2：如果用户已经手动打开浏览器并完成账号登录，不要关闭 Chrome、不要覆盖 Chrome Profile 文件、不要恢复整套三件套。Profile 2 是真人账号容器，登录态和扩展都必须保留。
2. 稳态启动固定使用真人 Chrome Profile。已验证的本地模式是 `@@USERPROFILE:win@@\AppData\Local\Google\Chrome\User Data` + `--profile-directory="Profile 2"`；不得按平台创建临时隔离 Profile。
3. 稳态启动不要使用临时扩展参数：不要加 `--user-data-dir`、`--disable-extensions-except`、`--load-extension`。OpenCLI Bridge 要以 Profile 2 的持久安装扩展加载。
4. 修复扩展断连时，禁止整包恢复或覆盖 Chrome `Local State`、`Preferences`、`Secure Preferences`、`Cookies`、`Login Data`。只能检查并修复 OpenCLI unpacked 扩展在 Profile 2 `Secure Preferences` 里的持久安装条目：扩展 id 存在、`location=4`、`path` 指向 OpenCLI bridge extension current、`disable_reasons=[]`。
5. 运行 `opencli profile list` 和 `opencli doctor`。只有看到 profile connected，且 doctor 同时显示 daemon running、extension connected、connectivity connected，才算 O0 browser-backed 路线可用。
6. 如果 Chrome Profile 2 已打开但 doctor 显示 `Daemon: running` / `Extension: not connected`，不要判定为站点不可抓，也不要马上降级到 Playwright/CDP。先确认持久扩展条目是否还在；条目在但未连接时，先 `opencli daemon restart`，再让现有 Profile 2 或人工重新打开的 Profile 2 重连；条目不在时，只修 OpenCLI 扩展条目，不动登录态文件。
7. 持久条目缺失时，优先走 Chrome 自己的扩展页建设路径，不手工改 Profile 文件：打开真实 `Profile 2` 的 `chrome://extensions`，开启开发者模式，点击“加载未打包的扩展程序”，选择 `@@USERPROFILE:win@@\AppData\Roaming\CodexPlusPlusProfile\opencli-browser-bridge-extension\current`。完成后执行 `opencli daemon restart`，等待 `opencli profile list` 出现 `e2n64eku lijie default — connected`。
8. 验证不要只看配置文件。至少保留三类证据：`opencli --profile e2n64eku doctor` 的 Connectivity OK、一条目标平台真实 OpenCLI 命令的 JSON 返回、业务一键诊断里的 `sampleEvidence.realTimeEvidenceOk=true` 与 `evidenceRows[].collectedAt`。如果 `verify-opencli-bridge.ps1` 只因为 Chrome 未在 `Secure Preferences` 写完整 manifest 而报错，但 UI 中 OpenCLI 扩展存在、profile 已连接、真实命令已跑通，应记录为验证脚本口径债，不要再误判业务采集失败。
9. route_receipt 需要记录运行态证据：`opencli_profile_alias`、`opencli_context_id`、`chrome_profile_directory`、`daemon_status`、`extension_status`、`connectivity_status`、持久扩展检查结果、启动命令或验证脚本路径。

OpenClaw 里已有可复用证据和脚本：

- 共享 Profile 配置：`@@OPENCLAW_ROOT:win@@\projects\tophub-daily-trend-radar\apps\web\data\opencli-shared-chrome-profile.json`
- 启动脚本：`@@OPENCLAW_ROOT:win@@\projects\tophub-daily-trend-radar\apps\web\scripts\opencli-shared-chrome-lijie.cmd`
- 验证脚本：`@@OPENCLAW_ROOT:win@@\projects\tophub-daily-trend-radar\apps\web\scripts\verify-opencli-bridge.ps1`
- 成功 receipt：`@@OPENCLAW_ROOT:win@@\projects\tophub-daily-trend-radar\docs\w11-p3-evidence\opencli-detail-probe-20260612-035723\opencli-detail-deepening-probe-receipt.json`

分层边界：

- OpenCLI adapter 承担站点解析：页面 DOM、站点字段、评论/详情命令和站点登录 session。
- 业务脚本承担业务编排：关键词、城市/类目、limit、resume、JSONL/raw/fact pack/Excel、质量标记和 evidence。
- CDP/Playwright 只作为 OpenCLI 失败后的 fallback，不作为 OpenCLI 路线的并行补采。
- 若 fallback 使用 `127.0.0.1:9222`，必须在 route_receipt 写清这是 browser fallback 的登录态边界，不得把它描述成 OpenCLI 前置条件。

降级必须带失败证据：命令、状态码、响应摘要、Network 观察或截图路径。不能只写“不可用”。

本地生活、高摩擦站点（大众点评、地图、黄页类）按 `references\high_friction_local_business_sites.md` 执行。若 OpenCLI 可通过内置或本地 adapter 覆盖名录、详情、评论等目标字段，必须继续走 OpenCLI session；只有 OpenCLI 证据失败后，才允许在 API/SSR 无稳定结构化来源、且任务只做小样本业务分析时，选择人工登录 Chrome + Playwright CDP 的 browser 路线。route_receipt 仍必须写清 `selected_strategy`、降级链、登录态边界和 evidence。

地图/POI 源（高德等）是 `local_business_listing` 的正式候选源：

- 如果业务目标是地图商铺、美食、周边、POI、地址、坐标或电话查询，允许选 `map_poi_source` / `api` 作为主路线。
- 如果业务目标是大众点评等内容平台，但缺 phone/address/location/category，优先把高德作为 enrichment / cross-check 源。
- 可复用探针包括 IP 定位、地理编码、周边搜索、文本搜索和 POI 详情交叉验证。
- route_receipt 必须写 `map_poi_receipt` 或等价字段，记录 query、center_source、radius、types、matched_poi_id、match_method、match_status。
- 不把高德 Key、签名密钥、配额配置写入 Skill 或样例；只记录配置入口和证据路径。

## 证据归属

S31A 的输出是路线证据，不是业务数据仓库。

- `s31a_route_receipt.v1.json` 写到 W31 分配的 `output_dir`。
- 探针失败的 trace、截图、HTML 片段和命令输出写到 `output_dir\evidence`。
- 能复用的路线经验才进入 `references\`，并且只写方法、判定条件和最小样例。
- 登录态、Cookie、整页原始抓取包、批量业务数据和缓存文件不进入 S31A。

## 交付给 W31

输出 `route_receipt`：

```json
{
  "schema_version": "s31a_route_receipt.v1",
  "target": "platform or url",
  "source_decision_ref": "data_source_decision_receipt.v1",
  "source_id": "source id from next_s31a_targets",
  "source_family": "official_source | commerce_marketplace | social_content | map_poi | ...",
  "source_role": "primary_fact_source | cross_check_source | enrichment_source | ...",
  "source_priority_rank": 1,
  "selected_strategy": "opencli | map_poi_source | api | ssr_json | browser",
  "opencli_tool_receipt": {},
  "map_poi_receipt": {},
  "evidence": [],
  "fallback_chain": [],
  "next_node": "S31C | S31E | S31B | S31F | S31G | S31D | P2"
}
```

## 资源

- OpenCLI 能力表：`@@GENERAL_ROOT:win@@\assets\skills\S31_爬虫策略探勘与选型\subskills\S31A_数据源探针与路线选型\resources\opencli_capability_map.md`
- 数据源事实源优先级 SOP：`@@GENERAL_ROOT:win@@\assets\skills\S31_爬虫策略探勘与选型\subskills\S31A_数据源探针与路线选型\references\source_priority_sop.md`
- 路线探针 CLI：`scripts\route_probe_cli.py`，输出 `s31a_route_receipt.v1`；自动按 OpenCLI 能力表、HTTP 页面探针、Fetch/XHR JSON API、SSR 状态块和 Browser fallback 顺序给出路线建议。

S31A 持有 `route_probe_cli.py` 作为轻量路线探针，不负责平台采集实现。

`s31a_route_receipt.v1` 可由 `route_probe_cli.py` 或 W31 主控根据探针证据写入 `output_dir\s31a_route_receipt.v1.json`，不由下游节点补写。
