---
name: opencli-complete-acquisition
description: Preserve acquisition and analysis coverage in public-data crawler or OpenCLI tasks; handle multi-facet evidence, item-level fallback, verified analysis reuse, and reusable capability learning.
---

# OpenCLI 完整采集

在使用 OpenCLI 或其他已登记采集适配器抓取公开数据、需要多维证据、逐条回退或判断“是否完整”时使用本 Skill。它提供跨项目的采集边界和回执口径；实际访问仍由当前项目已登记的 Provider/Adapter 执行。

详细字段契约见 [references/receipt-contract.md](references/receipt-contract.md)。出现分页、失败补位或跨项目复用时先读该参考。
在需要优化 token 或上下文成本时，再读 [references/token-optimization.md](references/token-optimization.md)；优化不得减少原始采集范围或丢弃 facet。
需要选择路线、处理单条失败或设计替代入口时，读 [references/provider-playbook.md](references/provider-playbook.md)。
需要把实战中的新字段、失败形态或回退路径沉淀为跨项目能力时，读 [references/capability-evolution.md](references/capability-evolution.md)。
遇到 RSS/Feed、博客平台或同一平台承载多种内容形态时，再读 [references/provider-playbook.md](references/provider-playbook.md) 的 Feed、Blog 和内容形态章节；不要把平台名直接当作业务分类。

## 目标

把每次采集做成可复核的证据包：搜索/发现、详情、正文或摘要、评论/互动、作者或节目关系、时间、地域线索、关联来源、失败和停止原因分别保存。作者、受访者、转述者、评论者、编辑和被引用主体都可以成为证据来源；第一人称和表达口吻只作为内容角色。

## 能力守恒不变量

**先保持原任务的功能、证据与分析要求，再减少重复工作；成本下降是结果，不是缩小任务的理由。** 适用于所有采用本 Skill 的爬虫任务，而非某个平台或周报项目。

1. **范围守恒**：优化前后沿用同一采集范围、必需 facet、刷新要求和验收标准；复用分析不等于免除本轮采集或刷新。
2. **双覆盖守恒**：原始证据保留与语义分析完成分别核算。索引已生成、内容已发送或文件仍在，都不等于已读完；未覆盖部分保持待处理。
3. **证据关系守恒**：保留对象、版本、来源、父子关系、时间和原文定位。相同 ID 的不同版本、相同文本的不同叙述者均保留，去重只减少重复载荷。
4. **复用须有证据**：内容未变、旧分析有效且覆盖所需单元、问题/规则/相关上下文均相容，才复用。只有 hash 或 review 路径不够；详见 [复用条件与失效处理](references/token-optimization.md#3-复用条件与失效处理)。
5. **变化完整传播**：新增、修改、删除和影响语义的顺序/上下文变化都进入待分析范围；变化使依赖它的综合结论失效。证据不足时正常重读，不静默跳过。
6. **经验按证据演进**：每项优化要同时证明不丢证据、不漏分析和减少了哪种重复；重复验证后进入已有 Owner 的采纳流程。Skill 修改、一次成功或测试全绿不等于所有适配器已经达标。

## 执行规则

1. 先定位当前项目的正式 Adapter、route spec、直接消费者和 Evidence 目录。若项目已有 `completeness` 模块（例如 `backend/discovery/completeness.py`），直接复用 `from_payload` / `assess_receipt`，不要再造第二套判定器。
2. 先做能力探针：运行 `opencli <site> --help -f yaml`，必要时运行 `opencli validate <site>` 和最小真实 probe，确认命令、字段、分页和会话状态；命令在列表中出现不等于目标字段已经可用。
3. 采集按“发现 → 详情 → companion facets → 归一化”推进。发现返回的每一行都保留；详情循环逐条尝试。一条对象失败时写失败回执并继续下一条，整条路线失败时进入已声明 fallback。
4. 每个外部调用保存分离的 stdout/stderr、命令、开始/结束时间、return code、超时、run_id 和 raw response 引用。原始响应先保存，再做结构化提取。
5. 回执至少区分：`discovered_rows`、`detail_expanded_rows`、`actual_fetched_rows`、`reference_only_rows`、`quarantined_rows`、失败操作、`has_more`、`next_cursor`、provider total、停止原因和 `facet_missing`。
6. `complete` 需要明确的 provider exhaustion、reported total reached 或等价结束证据，同时所有声明范围内条目已展开且必需 facet 没有未解释的 `facet_missing`。裸数组、达到 limit 但没有结束信号、分页未暴露、错误页、安全验证或登录墙均记录为 `partial` / `unknown` / `failed`。
7. 首选 Provider 原生分页、游标、总量和已登记公开替代入口。替代入口建立新 receipt 并保留原失败；不猜测下一页 URL，不绕过登录、安全验证或平台控制。
   - 同源 fallback 采用“先保留失败、再记录成功”的状态：备用入口确实补齐同一目标、同一范围的证据后，首选传输失败可标 `fallback`/`superseded`；其他未完成 facet 和缺口仍单独保留，单项恢复不自动升级整轮完整性。
8. 逐维写清必需 companion facets。缺失时写 `facet_missing` 和原因；平台互动数字不替代评论正文，书目不替代作者/读者材料，节目元数据不替代转录。
9. 语义层保留来源关系：作者、受访者、转述者、评论者、编辑和被引用主体都可以提供证据；第一人称和表达口吻只作内容角色。不要把转述改写成当事人原话，也不要让来源角色代替内容证据。
10. 运行结束后按 [references/capability-evolution.md](references/capability-evolution.md) 生成经验候选；候选先留在项目 evidence，经过重复验证、回归测试和 Owner 采纳后才进入共享能力。

## 复用边界

该 Skill 是通用路由和契约层；项目实现通过自身正式入口采用这些不变量，具体目录、字段名和运行方式沿用项目契约。

- 同一项目：复用已有完整性判定、正式适配器、质量回执、分析记录和测试；项目提供 `from_payload` / `assess_receipt` 等公共能力时沿用原接口。
- 其他项目：采用本 Skill 的契约和验证口径，并把字段映射到该项目的正式 Adapter、Evidence 和消费者；保留目标项目的 Owner、Runtime、Registry 和发布入口。
- OpenCLI Provider 可见不代表每个站点 Adapter 都具备同样能力。先做 `opencli <site> <command> --help -f yaml`、`validate`（可用时）和最小真实探针，再声明可用范围；帮助输出是当前能力事实，静态能力表只作索引。
- 跨项目的路线选择和能力登记沿用 S31/W31：`S31A` 负责路线探勘，W31 resolver/dispatcher 负责已登记能力，S31D 负责事实包校验。本 Skill 是采集完整性契约，不取代这些 Owner，也不创建新的 Registry。
- Skill 负责路由和决策约束，不持有业务数据、不建立第二 Runtime、第二状态库、第二爬虫或动态授权层。

## 能力增强回流

每次真实采集结束后，若发现新的分页边界、字段归一化模式、Provider 错误形态、fallback 成功路径、单条跳过策略或可复用停止条件，先在项目 evidence 生成 `crawler_experience_candidate.v1`，再按 S31/W31 的经验回流契约提交候选。项目若有正式周度入口，优先让入口自动调用同一个 W31 编译器；其他适配器沿用下面的显式命令。若有 adapter `result.json`，一并传入以保留逐条失败和缺失 facet。推荐入口：

```text
@@GENERAL_ROOT:win@@\tooling\w31\w31_crawler_experience_capture.py
```

候选必须绑定原始 receipt、receipt hash、机器事实、适用平台/操作、失效条件和拟归属 Owner；它保持 `candidate`，经过 fresh probe、回归测试和人工采纳后，才更新 S31A-G、W31 registry 说明或本 Skill。单次命令成功、高 limit、Provider 可见、项目局部查询词或单个帖子正文都不自动成为通用规则。

项目周度入口自动回流时，候选路径和 `candidate_id` 写入 Tick 回执的
`experience_capture` / `artifact_refs`；采集回执在候选编译前已经落盘，之后不再原地改写，确保 receipt hash 可复核。候选编译失败只在 Tick 回执写出告警，原始采集证据保留，可单独重试编译；它不会把候选直接升级为共享规则或业务准入。

能力升级采用“事实先行、最小变更、可回退”循环：

```text
真实 receipt
  -> 项目经验候选
  -> 第二次独立 probe / fixture
  -> 最小回归测试
  -> 对应 Owner 采纳
  -> 更新既有 S31A-G / W31 / OpenCLI Skill
  -> 下一次运行验证并追加演变记录
```

同一 Provider 的单条内容失败是 item 级问题，继续换下一条；同一命令连续暴露字段或分页缺口才形成 route/provider 级经验。不要因为一个对象失败就把整个平台写成不可用，也不要因为一个对象成功就把平台写成完整。

## 交付检查

输出前核对：能力探针和正式入口已定位；实际行数与平台总量分开；每个 facet 有状态；每条失败和 fallback 有原始引用；完整性结论与结束证据相符；单条失败不会掩盖其他成功条目；候选仍带来源关系；经验候选已绑定 receipt hash；下游只消费已有正式准入记录。项目存在本地规格时，优先读取 `docs/specs/data-completeness-spec.md` 和 `docs/specs/source-discovery-contracts.md`。

涉及上下文或分析优化时，再按 [不降能力验收](references/token-optimization.md#验收场景) 核对逐单元覆盖、有效复用与依赖失效；以优化前后的实际证据和分析覆盖对照验收，不只比较输入字节数。
