<!-- 拆自 P2.6 SKILL.md §4 [STATE: REVIEW_REPORT_OUTPUT]（2026-08-15 走查 SKSEM-11） -->

# P2.6 红队评审报告

## 评审对象
- 来源：P1 / P2 / P2.5
- 文档路径：xxx
- 评审时间：2026-04-XX

## 蓝队自审摘要
蓝队自审声称 X 项检查全部 PASS。红队对蓝队自审质量的判断：[走实/走过场]

## 逐条检查结果
| # | 检查项 | 蓝队自审 | 红队裁决 | 证据/缺陷描述 | 准则出处 |
|:--|:--|:--|:--|:--|:--|
| P1-01 | 业务边界 | ✅ | ✅ PASS | PRD §2 有 in/out-of-scope | P1 SKILL.md |
| P1-02 | 数据契约 | ✅ | 🔍 BLUE_MISS | email 字段类型未定义 | architecture.md §1 |

## 通用审计维度
| # | 检查项 | 结果 | 说明 |
|:--|:--|:--|:--|
| U-01 | YAML 护照 | ✅ | domain/tier/status 齐全 |

## 最终裁决
🟡 CONDITIONAL_PASS / 🔴 REJECTED / 🟢 APPROVED

## 🎯 红队改进建议清单（回流给蓝队）
1. [P1-02] email 字段类型未定义 → 建议补充 VARCHAR(255) NOT NULL UNIQUE
2. ...

## 上下文隔离声明
本次评审在 [全新上下文 / 继承上下文⚠️] 中执行。

## 改进建议清单写法示例（供格式参考，拆自 §4 [STATE: RED_TEAM_ATTACK]）
  - 例如："P1 的 PRD 第 4 节缺少 users 表 email 字段类型定义，建议补充为 VARCHAR(255) NOT NULL UNIQUE"
  - 例如："P2 的 Tech Spec 中 Redis 选型缺少 POC 证据，建议补充 `redis-cli ping` 连通性测试截图"
  - 例如："P2.5 的 Func-201 原子功能缺少 Output Template，建议补充交付件清单：API 契约文档 + 单元测试"
