<!-- 拆自 P2.6 SKILL.md §3（2026-08-15 走查 SKSEM-11） -->

### 3.1 P1 交付物评审清单（PRD / 需求法典）

> **武器来源**：P1 SKILL.md 死亡红线 + Harness 天条 + 01_Planning 方法论 + 02_风控计分卡

| # | 检查项 | PASS 标准 | FAIL 触发条件 | 准则出处 |
|:--|:--|:--|:--|:--|
| P1-01 | **业务边界是否清晰** | 存在显式的 in-scope 和 out-of-scope 列表 | 边界模糊或含糊措辞 | P1 SKILL.md |
| P1-02 | **数据契约是否完整** | 每个接口有 JSON Schema 或字段表 | 存在"待定"字段 | architecture.md §1 数据主权 |
| P1-03 | **验收标准是否可测试** | AC 使用 Given-When-Then | 只有"功能正常"等主观描述 | P1 SKILL.md TDD 条款 |
| P1-04 | **是否越权涉及技术选型** | PRD 只描述"做什么" | 出现 "使用 PostgreSQL" 等 | architecture.md §1 分层三权分立 |
| P1-05 | **TDD 边界场景是否定义** | 至少提出 5 大异常风控边界（强制包含全链路卡壳防锁：如大模型超时、大文件MapReduce切分、依赖服务断联自愈拉起重试等） | 仅停留于浅层业务异常，完全无视执行链路上的算力耗尽、无限死等或僵死卡壳风险 | architecture.md §1 5+X 分析法 |
| P1-06 | **下游路由声明是否存在** | 有显式的交付给 P2 的声明 | 结尾悬空 | architecture.md §3 依赖强校验 |
| P1-07 | **第一事实铁律合规 (First-Fact)** | 数据 Schema 字段附带物理样本来源标注（如“来自 API 抓包”或“来自用户提供截图”） | Schema 字段无源头标注，纯属模型脑补 | P1 SKILL.md v3.1.0 First-Fact Doctrine |
| P1-08 | **Golden Sample 存在性** | 涉及大模型生成的环节附带了 Few-Shot 满分样本（热气腾腾的大白话伪造数据） | 只有干瘦的 JSON 结构没有实例填充 | P1 SKILL.md PHASE_2 条款 3.5 |
| P1-09 | **养料维度覆盖率** | PRD 对 p-pipeline-schema-registry §9 的养料维度给出 required/optional/unknown 裁决，并解释缺口如何进入 P2 探测 | 只写业务字段，不说明数据源、样本、缺失维度和后续探测责任 | p-pipeline-schema-registry §9 |
