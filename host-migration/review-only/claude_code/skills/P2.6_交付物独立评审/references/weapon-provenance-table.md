<!-- 拆自 P2.6 SKILL.md §1.3（2026-08-15 走查 SKSEM-11） -->

### 1.3 评审准则武器溯源表（知识图谱出处）
P2.6 的评审检查项不是凭空编出来的，每条都有明确的知识图谱出处：

| 武器来源 | 文件路径 | 给 P2.6 提供了什么 |
|:--|:--|:--|
| **Harness 四大天条** | `references/harness/orchestration-manual.md` | 可控/可观测/可回滚/可收敛——所有交付物必须满足的基线 |
| **六层解耦蓝图** | `references/harness/orchestration-manual.md` | Gate/Planner/Router/Executor/Validator/Evolution——验证交付物是否在正确的层级 |
| **架构总纲** | `rules/architecture.md` | 分层治理三权分立、数据契约 5+X 分析法、微内核单体、不越权编排 |
| **执行宪法** | `rules/execution.md` | 资产五维搜身铁律（Harness/矩阵/OpenSpec/父子/图谱）——P2.6 的逐条检查灵感来源 |
| **工程治理协议** | `references/architecture/engineering-governance-protocol.md` | 架构图纸诚实性原则——检查 P2 图纸中每条箭头是否有代码级支撑 |
| **规划编排方法论** | `references/methodology/01_Planning...` | "独立→并发/依赖→串行/紧耦合→合并"三原则——检查 P2.5 拆分是否合理 |
| **风控与 ROI 阻断** | `references/methodology/02_Exploration...` | 风控计分卡（0-100）——评估交付物的爆炸半径与合规动机 |
| **Skill 生命周期** | `references/methodology/03_Skill-Lifecycle...` | 单一职责、轻入口+富引用、内容性质三层拆解——检查交付物结构是否符合微内核 |
| **AutoGen 管线治理** | `references/methodology/18_AutoGen-Pipeline-Governance.md` | 五模式选型决策树——检查 P2.5 的 P3/P4 路由是否合理 |
| **治理与知识回流** | `references/methodology/05_Governance...` | M4 铁律四步法——评审做完后，把发现回流到知识体系 |
| **资产审计协议 (11维)** | `references/methodology/09_Asset-Governance-Audit-Protocol.md` | **11 维审计清单**——P2.6 的检查项设计直接对标此 11 维评估框架 |
| **矩阵治理总纲** | `references/matrix/governance-protocol.md` | 四大系统矩阵 + CRUD 准入铁律——验证交付物的层级归属和分类一致性 |
| **S13 代码审查** | `skills/S13_代码审查/SKILL.md` | 红队攻击心态参考：S13 的"无情漏洞检测仪"模式，P2.6 在文档层复制这种攻击精神 |
| **S14 完成前验证** | `skills/S14_完成前验证/SKILL.md` | "Evidence Before Claims"原则——没有物理证据就不允许宣称完成 |
| **四重物理防呆锁** | `skills/M2_技能生产与归档/references/planner-anti-hallucination-audit.md` | 越权/实弹/散文/熔断 4把锁——对抗大模型提示词幻觉 |
| **抗洗脑法则** | `skills/M2_技能生产与归档/references/编写技能规范.md` | 识别虚假的"逻辑闭环"与合理化偏见 |
| **职责拆合决策锁** | `skills/M2_技能生产与归档/references/skill-split-or-merge-decision.md` | 5+5 拆合决策框架——防止凭直觉滥建 Agent 或导致上下文重灌灾难 |
