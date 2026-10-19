# 爬虫能力持续进化契约

目标：让一次真实采集中的新经验可复用，同时不把项目样本、业务结论或偶然查询词污染共享 Skill。

## 1. 什么值得回流

优先记录这些跨项目可能复用的事实：

- Provider 新的命令、输出包装、ID/URL 字段或错误码；
- 分页、游标、总量、单页上限和真实结束条件；
- 单条对象失败但批次可继续的处理方式；
- 同源 fallback（官方 RSS、公开作者页、宽查询、替代详情入口）及其证据；
- 结构化解析规则（JSON/XML/Markdown/HTML）和去重键；
- 公开内容的 facet 缺失模式、停止原因和可重试边界。

跨项目优先检验以下经验方向；每条都按原始证据验证适用条件，列表本身不是“所有项目已验证”的声明：

- RSS/XML 的“快照内全量解析”与“平台历史全量”分开命名和计数；
- Apple/Feed 或 API/网页两份列表用 provider 原生 ID，缺失时用规范化标题+日期辅助定位；身份有歧义时保留多条和版本关系，不强行合并；
- 首选 transport 失败、同一来源的 Browser/Feed fallback 成功时，将首选命令标为 `fallback`/`superseded`，保留失败原文但不把成功的整体运行误报为失败；
- 平台 provider 与业务内容形态分离：同一视频平台可承载 Podcast 与 ShortVideo，两者的候选契约由 route spec 选择；
- 原生 Blog adapter 不存在时，`google search → web read` 是通用观察路线；平台归属必须由 URL/页面事实确认，不能从查询词补齐。

以下内容只留在项目 evidence：某篇文章的心理判断、某个账号的用户画像、单次查询词、单个对象的营销结论和整批原始数据。

## 2. 每次真实运行的回流动作

真实 receipt 完成后，在项目 evidence 生成候选：

```powershell
python @@GENERAL_ROOT:win@@\tooling\w31\w31_crawler_experience_capture.py `
  --receipt C:\path\receipt.json `
  --result C:\path\result.json `
  --output C:\path\evidence\crawler-experience-candidate.json `
  --project-root C:\path\project `
  --platform PLATFORM `
  --business-profile PROFILE `
  --collection-mode COLLECTION_MODE
```

该工具只读取 receipt 和可选的 adapter result，候选状态保持 `candidate`，不会修改 Registry、Runtime、source pool 或业务结果。传入 result 后还会保留逐条隔离对象和缺失 facet；若工具在目标环境中未安装，按同一字段契约生成项目级候选，并在交接中标明待 Owner 复核；不要为此另建状态库。

## 3. 候选必须包含的事实

```yaml
schema_version: crawler_experience_candidate.v1
source:
  receipt_ref: <path>
  receipt_sha256: sha256:<hash>
  run_id: <id>
scope:
  platform: <platform>
  route: <route>
facts:
  status: ok|partial|failed|empty|unknown
  completeness: complete|partial|unknown|failed|unreported
  rows_seen: <int-or-null>
  rows_emitted: <int-or-null>
  failures: []
  raw_response_refs: []
lesson:
  kind: provider|pagination|schema|normalization|fallback|failure|completeness|route
  trigger: <observed machine fact>
  reusable_rule: <one precise rule>
  applicability: <platform/operation conditions>
  invalid_when: <known failure or scope boundary>
  proposed_owner: S31A|S31C|S31D|S31E|S31F|S31G|opencli-complete-acquisition
promotion:
  state: candidate
  requires: [fresh_probe, regression_test, human_adoption]
```

候选还应列出 `fallback_chain`、`provider_capability_snapshot_ref` 和 `reproduction_commands`（如已有）。敏感查询参数只保存脱敏版本，原始凭据和登录态不进入候选。

编译器同时读取 receipt 顶层的 `facet_missing`/`missing_facets`、复数
`raw_response_refs` 和嵌套 `result.receipt`；逐条失败会脱敏并去重。候选
输出是追加式证据：若目标文件已经存在，只有 receipt/result hash 完全匹配
时才返回 `reused`，否则保留原文件并报告冲突，不覆盖旧事实。
调用方未传 `--platform` 时，候选会从 receipt 的 `platform`、`source_type`
或 `source.platform` 回填；这只是来源标签归一化，不代表该 Provider 的
字段能力已经验证。

## 4. 晋级条件

经验从项目候选进入共享能力，按以下顺序：

1. **复核事实**：重新读取 receipt，检查 receipt hash、原始响应引用和字段关系；
2. **重复验证**：在第二次独立运行、不同对象或合成 fixture 中复现同一机械行为；
3. **最小回归**：覆盖成功、失败和边界路径，不只测试成功样例；
4. **选择 Owner**：分页/路线进 S31A，内容采集进 S31C，事实包进 S31D，视频/字幕进 S31E-G，跨项目完整性进本 Skill；
5. **人工采纳**：Owner 记录采纳理由、适用范围和失效条件；
6. **追加演变**：下一次运行引用新规则并追加 receipt，旧经验保持可读，不覆盖历史。

单次成功、高 limit、Provider 在列表中出现、一个热门对象或一条业务结论都不足以晋级。

### 4.1 性能和上下文优化的额外验收

采用 [能力守恒不变量](../SKILL.md#能力守恒不变量) 与 [上下文复用验收场景](token-optimization.md#验收场景)。先证明等范围和等分析要求，再比较重复开销；不得把减少必须完成的工作当作优化收益。

经验说明应绑定：优化前基线、优化后证据、两侧要求的单元集合、实际完成/有效复用/待分析/缺失集合、复用与失效原因、成本计量口径、回归结果、适用条件和失效条件。沿现有候选/回执字段承载，缺证据时保持候选，不为此另建性能账本。

“越用越强”以同类失败减少、重复分析减少且覆盖保持、能力被下一次真实消费者复用为证据，不以新增规则数量、持续扩张未审素材或估算节省比例替代。反例出现时保留原证据，按实际 Owner 撤销或收窄规则，恢复原分析路径。

更新 Skill 是约束固化，项目实现符合约束是另一项待证事实；测试通过只覆盖测试实际触达的场景。不要把 Skill 更新顺带扩大成 OpenCLI 安装升级、跨项目运行控制或新的默认模型策略。

## 5. 共享 Skill 的最小变更

采纳经验时只更新已有入口：

- `opencli-complete-acquisition/SKILL.md`：通用采集边界和回执规则；
- `references/receipt-contract.md`：公共字段和完整性判定；
- `S31A`：路线探针、fallback 和 Provider 能力事实；
- `S31C`：内容平台 adapter 与结构化采集；
- `S31D`：事实包映射和校验；
- `W31` registry/dispatcher：已登记可运行能力。

不要因为一个平台出现一次就新建专属 Skill；先判断经验是否跨项目稳定，再在原有节点增加最小规则或示例。大样本和项目正文继续留在项目 evidence。

## 6. 下一次运行的验证回路

每个被采纳的经验都要在下一次 route receipt 中留下：

```yaml
applied_experience:
  candidate_id: CRAWLER-EXP-...
  owner: <owner>
  rule_version: <version-or-ref>
  probe_result: passed|not_reproduced|superseded
  evidence_refs: []
```

`not_reproduced` 不是静默删除；保留原候选和新鲜失败事实，回到 Owner 判断规则是否过期或只适用于原平台。

已采纳规则的引用可在下一次 W31 dispatcher 运行中重复传入
`--applied-experience <candidate-or-rule-ref>`。dispatcher 只记录引用和本次
结果，不自动扩大规则适用范围；没有引用时记录空列表。

## 7. 与业务准入的关系

能力回流只改变“怎么采、怎么记、怎么验证”的通用能力，不改变目标群体定义、业务准入、人审结果、源宇宙状态或周报内容。语义分析仍由 Agent 按当前任务完成，正式准入仍由现有人工/Admission 入口完成。
