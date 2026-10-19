---
name: S31 爬虫策略探勘与选型
type: generic
domain: crawler
tier: L3
doc_status: active-ssot
status: active
birth_ceremony_id: bc-s31-d8d7cb2e
birth_ceremony_date: '2026-05-02'
related:
  - @@GENERAL_ROOT:win@@\assets\workflows\W31_爬虫探勘与事实采集工作流.md
  - @@GENERAL_ROOT:win@@\assets\skills\S31_爬虫策略探勘与选型\subskills\S31A_数据源探针与路线选型\SKILL.md
  - @@GENERAL_ROOT:win@@\assets\skills\S31_爬虫策略探勘与选型\subskills\S31B_媒体证据探针\SKILL.md
  - @@GENERAL_ROOT:win@@\assets\skills\S31_爬虫策略探勘与选型\subskills\S31C_内容平台事实采集\SKILL.md
  - @@GENERAL_ROOT:win@@\assets\skills\S31_爬虫策略探勘与选型\subskills\S31D_爬虫事实包契约\SKILL.md
  - @@GENERAL_ROOT:win@@\assets\skills\S31_爬虫策略探勘与选型\subskills\S31E_跨平台视频源解析\SKILL.md
  - @@GENERAL_ROOT:win@@\assets\skills\S31_爬虫策略探勘与选型\subskills\S31F_字幕ASR转写后端\SKILL.md
  - @@GENERAL_ROOT:win@@\assets\skills\S31_爬虫策略探勘与选型\subskills\S31G_转录质检与摘要审阅\SKILL.md
  - @@GENERAL_ROOT:win@@\assets\skills\S31_爬虫策略探勘与选型\references\new_platform_onboarding_template.md
  - @@GENERAL_ROOT:win@@\assets\skills\S31_爬虫策略探勘与选型\references\crawler_capability_registry.yaml
  - @@GENERAL_ROOT:win@@\tooling\w31\w31_crawler_capability_dispatch.py
  - @@GENERAL_ROOT:win@@\tooling\w31\w31_crawler_capability_onboard.py
  - @@GENERAL_ROOT:win@@\assets\skills\S31_爬虫策略探勘与选型\tests\test_w31_crawler_capability_dispatch.py
  - @@GENERAL_ROOT:win@@\assets\skills\S31_爬虫策略探勘与选型\tests\test_w31_crawler_capability_onboard.py
  - @@GENERAL_ROOT:win@@\assets\skills\S31_爬虫策略探勘与选型\references\project_competitor_review_onboarding_template.md
  - @@GENERAL_ROOT:win@@\assets\skills\S31_爬虫策略探勘与选型\references\s31a_competitor_review_integration_plan.md
  - @@GENERAL_ROOT:win@@\assets\skills\S31_爬虫策略探勘与选型\references\platform_sops_implementation_plan.md
  - @@GENERAL_ROOT:win@@\assets\skills\S31_爬虫策略探勘与选型\references\business_metric_route_registry.yaml
  - @@GENERAL_ROOT:win@@\assets\skills\S31_爬虫策略探勘与选型\resources\错题本.md
  - @@GENERAL_ROOT:win@@\assets\skills\P2_技术架构与方案设计\SKILL.md
  - @@GENERAL_ROOT:win@@\assets\skills\S8_计划执行\SKILL.md
  - @@OPENCLAW_ROOT:win@@\.agents\skills\S32_营销视频研报生成\SKILL.md
  - @@GENERAL_ROOT:win@@\control\registry\02-skill-catalog.md
description: 用户要求抓取网页数据、爬虫、采集网站信息、逆向分析时使用。

extends:
  - @@GENERAL_ROOT:win@@\assets\rules\execution.md
  - @@GENERAL_ROOT:win@@\assets\rules\file_editing.md
  - @@GENERAL_ROOT:win@@\assets\references\methodology\10_S-Tier-Execution-Discipline-Protocol.md
---
# S31_爬虫策略探勘与选型

## 定位

S31 现在是能力簇入口和原则说明，不再拥有正式脚本，也不再作为运行时中转节点。它负责三件事：

1. 判断任务是不是“爬虫探勘与事实采集”。
2. 固定总原则：先打孔探测，再选最轻路线；OpenCLI/O0 优先；事实字段和推断字段分离。
3. 给 `@@GENERAL_ROOT:win@@\assets\workflows\W31_爬虫探勘与事实采集工作流.md` 提供能力边界、节点说明和错题索引；实际运行链路固定为 `W1 -> W31 -> capability_resolver -> governed pipeline / S31A-G -> S32/P2/S8`。

默认不要在 S31 根目录下找 `scripts/` 或 `tests/`。脚本按职责收在 `subskills\S31A_...` 到 `subskills\S31G_...`，S31 根目录只保留簇入口、簇级 reference 和错题本。
新平台接入先按 `references\new_platform_onboarding_template.md` 填输入、路线、fact pack 映射和 W31 handoff，再由 `w31_crawler_capability_onboard.py` 完成 `init -> stage -> promote -> check -> apply`，把完整能力原子登记到 `references\crawler_capability_registry.yaml`；模板覆盖 S31A-G，不得只按 A/C/D 三个节点偷跑。已纳入平台的业务指标查询先查 `references\business_metric_route_registry.yaml`，再进入 S31A/S31C 执行。

进入 W31 前先判业务场景，再判平台：

- `内容挖掘分析总结`：给定网站或平台，搜索热门/最新内容，过滤后深挖；内容质量不足时补视频、字幕、抽帧、ASR 或转录审阅。对应 `collection_mode=content_mining_analysis_summary`。
- `查询爬虫搜索获取数据`：围绕明确字段，按关键词、城市、类目或多站点搜索抓取列表/详情/联系方式/评分/价格/地址等数据。对应 `collection_mode=query_search_data_collection`。

平台名只决定后续节点和 source adapter，不替代业务场景判断。

## 簇级铁律

**OpenCLI-first**：任何站点或平台采集需求，先按 S31A 检查 OpenCLI/O0。只要 OpenCLI 已有适配器、外部 CLI 或可用本地私有 adapter 能覆盖目标字段，并且登录态可以通过 OpenCLI session 维持，就选 `opencli`，停止继续探测，不再另写 Browser/Playwright/CDP 重复路线。

只有出现命令缺失、目标字段缺失、OpenCLI 登录态不可用、风控/验证码阻断、`opencli validate` 失败、实测输出缺关键字段等证据时，才允许降级到 API/SSR/Browser。降级必须写入 route receipt：OpenCLI 命令、失败摘要、证据路径、`fallback_chain` 和新的 `selected_strategy`。

OpenCLI 涉及 Browser Bridge 时，先按 S31A 的运行态门禁确认 daemon、Chrome Profile 和扩展连接。`opencli doctor` 里 `Daemon: running` 但 `Extension: not connected` 不是业务采集失败，也不能直接降级到 Browser；先修复 Bridge 连接，再继续探针。

**真人 Profile 保护红线**：OpenCLI Browser Bridge 的稳态浏览器必须是人工登录过的 Chrome `Profile 2`，登录账号和扩展安装状态都视为真人资产。任何爬虫、探针、修复脚本都不得整包恢复或覆盖 Chrome `Local State`、`Preferences`、`Secure Preferences`、`Cookies`、`Login Data`，也不得用临时 `--user-data-dir`、`--load-extension`、`--disable-extensions-except` 替代真实 Profile 2。扩展断连时先建设正确运行态：打开真实 `Profile 2` 的 `chrome://extensions`，开启开发者模式，点击“加载未打包的扩展程序”，选择 `@@USERPROFILE:win@@\AppData\Roaming\CodexPlusPlusProfile\opencli-browser-bridge-extension\current`，再 `opencli daemon restart`。最后用 `opencli profile list`、`opencli doctor` 和一条真实 OpenCLI 采集命令证明 daemon、extension、connectivity 全部 OK。

**地图/POI 数据源**：本地生活任务如果目标是地图商铺、美食、周边、POI、地址、坐标、电话或行政区，高德等地图 Web Service 可作为 `map_poi_source` 主路线；如果目标是大众点评等内容平台，地图源作为 enrichment / cross-check 源。两种情况都由 S31A 判路，S31D 落到 `business_listing` fact pack，不新建专属 Skill。

## 能力簇

| 节点 | 入口 | 职责 |
|:---|:---|:---|
| S31A | `@@GENERAL_ROOT:win@@\assets\skills\S31_爬虫策略探勘与选型\subskills\S31A_数据源探针与路线选型\SKILL.md` | OpenCLI/O0、API 抓包、SSR JSON、Browser fallback 路线选型 |
| S31B | `@@GENERAL_ROOT:win@@\assets\skills\S31_爬虫策略探勘与选型\subskills\S31B_媒体证据探针\SKILL.md` | 抽帧、OCR、媒体证据组装 facade；URL 字幕/媒体源委托 S31E，字幕归一/ASR 委托 S31F |
| S31C | `@@GENERAL_ROOT:win@@\assets\skills\S31_爬虫策略探勘与选型\subskills\S31C_内容平台事实采集\SKILL.md` | 内容平台 search/post/note/comments/download、adapter 编排、切片调度、样本与报告；小红书只是当前 adapter |
| S31D | `@@GENERAL_ROOT:win@@\assets\skills\S31_爬虫策略探勘与选型\subskills\S31D_爬虫事实包契约\SKILL.md` | `crawler_fact_pack.v1` 组装、校验、交接契约 |
| S31E | `@@GENERAL_ROOT:win@@\assets\skills\S31_爬虫策略探勘与选型\subskills\S31E_跨平台视频源解析\SKILL.md` | YouTube/Bilibili/抖音/小红书/TikTok/泛 yt-dlp URL 解析、字幕发现、媒体源 receipt |
| S31F | `@@GENERAL_ROOT:win@@\assets\skills\S31_爬虫策略探勘与选型\subskills\S31F_字幕ASR转写后端\SKILL.md` | 字幕归一、faster-whisper、whisper.cpp、显式 OpenAI/火山 ASR provider |
| S31G | `@@GENERAL_ROOT:win@@\assets\skills\S31_爬虫策略探勘与选型\subskills\S31G_转录质检与摘要审阅\SKILL.md` | 转录质检、时间戳观察、关键术语和审阅结论，输出 `transcript_review.v1` |

## 调度规则

运行时统一由 W31 调度，S31 只保留能力层说明。W31 先调用 `@@GENERAL_ROOT:win@@\tooling\w31\w31_crawler_capability_dispatch.py` 解析注册能力；命中后按注册入口执行，未命中才进入 S31A 探勘或新平台接入：

```text
capability registry 解析
  -> 命中：执行已注册 governed pipeline
  -> 未命中：S31A 路线探勘
  -> 可选 S31C 内容平台事实采集
  -> 可选 S31E 视频源/字幕解析
  -> 可选 S31B 媒体证据
  -> 可选 S31F ASR 转写
  -> S31D fact_pack 校验
  -> 可选 S31G 转录审阅
  -> P2 / S8 / S32 交接
```

原子 Skill 可以单独调用，但默认只作为 W31 DAG 的节点运行。

## 资产治理边界

S31 入口只管路由和边界，不保存业务脚本和运行数据。

- 新的通用探针路线写入 S31A。
- 新的平台采集实现先写入对应节点的 adapter、`references\`、`examples\`、`scripts\` 或 `tests\`，再用稳定 `capability_id` 登记到 `crawler_capability_registry.yaml`；平台名本身不能成为新 Skill 身份。
- 注册状态为 `active` 的能力必须有真实 entrypoint，并一次产出 adapter receipt、route receipt、`crawler_fact_pack.v1.checked.json` 和 `w31_handoff.v1.json`，同时声明可机器校验的 artifact assertions；只有 Skill 文案而没有这套运行契约，不算爬虫系统已具备该业务能力。
- 新的事实包映射、校验样例和分析模板写入 S31D。
- 业务运行输出、失败截图、trace、Excel、JSONL 和大样本数据留在业务 `output` 或项目 evidence 目录。
- 收尾时如果发现脚本、样例、trace 或缓存散在 `scratch`、`Temp`、桌面等位置，先按 W31 的资产归位规则处理。

## 能力入口说明

S31 入口不生成运行时 handoff。若被人工、审计或目录索引引用，只输出能力边界说明：

```json
{
  "harness_metadata": { "phase": "S31_CAPABILITY_PRINCIPLE", "status": "REFERENCE_ONLY" },
  "runtime_route": "W1 -> W31 -> capability_resolver -> S31A-G -> S32",
  "execution_owner": "W31_爬虫探勘与事实采集工作流",
  "not_runtime_transit_node": true,
  "target_nodes": ["S31A", "S31C", "S31E", "S31B", "S31F", "S31D", "S31G"],
  "generic_exit": ["P2", "S8", "S32"],
  "facts_must_remain_facts": true,
  "inference_field": "inference[]"
}
```

旧 S31 错题仍保留在 `resources\错题本.md`，用于 W7 回流和排坑，不承载运行脚本。
