# OpenCLI 完整采集回执契约

适用于任何项目的 OpenCLI 公开数据适配器。字段是机械事实，不是语义评分。

```json
{
  "retrieval_scope": {
    "query": "...",
    "requested_limit": 100,
    "provider_reported_total": null,
    "rows_acquired": 0,
    "unique_rows": 0,
    "pagination": "complete|partial|unknown|unsupported",
    "stop_reason": "provider_exhausted|reported_total_reached|limit_reached|provider_no_pagination|access_blocked|error",
    "completeness": "complete|partial|unknown|failed"
  },
  "route": {
    "selected_strategy": "opencli|opencli+rss|opencli+browser|api|ssr_json",
    "fallback_chain": [],
    "capability_probe_ref": null
  },
  "raw_response_refs": [],
  "facet_missing": [],
  "item_failures": [],
  "applied_experience": []
}
```

判定顺序：

1. 发现行数、详情展开数和实际带物理证据的行数分开计数。
2. 服务端有 total、has_more 或 cursor 时原样保留；适配器遵循已登记的分页接口，不猜测下一页。
3. 明确结束且所有声明范围内条目已展开，才使用 `complete`。
   只要声明范围内仍有 `facet_missing`/`missing_facets`，整体回执保持 `partial`，即使发现分页已经结束；各 facet 的缺口单独保留。
4. 裸数组、达到 limit 但没有结束信号、登录/付费墙、安全验证、错误页和空引用分别记录 `unknown`、`partial` 或 `failed`。
5. 详情失败保留原始回执，并沿同一 Provider 的已声明 fallback 查询补充候选；失败的单个对象不阻断其他对象。每次 fallback 都记录来源、触发事实、范围变化和新 receipt。
6. 搜索结果、详情正文和 companion facets 必须分别保存；评论/转录/作者页缺失时写 `facet_missing`，不以数量或标题填补内容。
7. 作者、转述者、评论者、编辑和被引用主体都可提供目标群体心理/情感证据。`source_role` 用于说明来源关系；它不承担准入裁决。第一人称和表达口吻只作内容角色。
8. 经验候选只在第二次独立 probe/fixture、最小回归测试和对应 Owner 采纳后进入共享 Skill；新规则必须在下一次 receipt 中写 `applied_experience`。

跨项目采用时，把字段映射到当前项目的正式 Adapter、Evidence、Runtime 和消费者。Skill 不拥有数据、状态、Registry 或调度器；路线登记继续由 S31/W31 现有 registry/dispatcher 负责。

## 分析复用的回执语义

采集完整性与语义分析覆盖分开记录。在已有 review/run receipt 内映射以下事实，不要求新建账本或替换项目 schema：

- **要求范围**：本次需要覆盖的来源版本、facet/chunk 单元及分析规则引用；
- **新完成**：已有实际分析结果和原文定位的单元；
- **有效复用**：通过内容、旧分析有效性、任务相容性及依赖检查的单元，附旧 review 引用及其 hash；
- **待分析**：首次未读、变更、编辑、上下文失效、旧分析不完整等仍需处理的单元；
- **缺证据**：已知应取得而本次尚未取得的单元/facet，保留原始失败和停止原因；
- **成本**：实际 usage、字符估算、文件字节数分别标注，并纳入剩余深读和重试。

用单元身份集合对账，不只比较数量：要求范围内每一项均归属新完成、有效复用、待分析或缺证据。所有待处理项消解后，才可按原任务标准声明分析完成；索引生成、发送成功、文件存在、缓存命中均不替代这个证明。部分采样的“未观察到”与内容被删除是不同事实。

复用条件详见 [上下文去重](token-optimization.md#3-复用条件与失效处理)。旧记录缺少复用所需事实时，保留为历史参考并重新处理所需范围；索引/短包本身不签发业务准入。
