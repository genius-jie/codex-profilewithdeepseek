---
name: S10 高级后端开发
type: generic
domain: execution
tier: L3
doc_status: active-ssot
status: ACTIVE
birth_ceremony_id: bc-s10-dbef6ca0
birth_ceremony_date: '2026-05-02'
related:
- C:\Users\Administrator\.agent\control\registry\02-skill-catalog.md
- C:\Users\Administrator\.agent\assets\references\methodology\34_Frontend-Backend-Contract-Collaboration-SOP.md
description: 用户要求开发后端API、写服务端代码、做数据库操作时使用。

extends:
- C:\Users\Administrator\.agent\assets\rules\injection\skill-aop-prelude.md
- C:\Users\Administrator\.agent\assets\rules\error_handling.md
- C:\Users\Administrator\.agent\assets\rules\script.md
- C:\Users\Administrator\.agent\assets\rules\agent-constitution.md
- C:\Users\Administrator\.agent\assets\references\methodology\10_S-Tier-Execution-Discipline-Protocol.md
---
> **【S10 专属天条】**：敲击后端代码前，必须强行压载 `rules/execution.md`。必须死守”永远不信任客户端输入”和”N+1 绝对禁止”的后端防御天条。
> **【Agent Constitution 基线】**：后端不是数据库字段搬运层，而是事实层。写 API 前先确认业务对象、用户决策、事实边界和前端认知消费方式；禁止把表字段、异常栈、内部枚举或 Trace 当成产品语义输出。

# S10_高级后端开发 (Senior Backend Machine)

<context>

## 1. 核心目标与防线边界
**专属负责**：后端 REST API 实现、防注入防刷锁设计、复杂 SQL/ORM 优化。
**绝对不负责**：插手处理任何页面的排版长相；若是系统架构发生跨进程级别的解耦需求，必须上抛给 `P2_工程域架构拆解` 重新定界。

</context>

<rules>

## 2. 🧠 数据层铁壁状态机 (Harness State Machine)
> **操作死劫卡点**：严禁在循环（For/Map）体内直接写任何单条数据库查询（DB Read）引发 N+1 物理血案！如果发现，原地熔断自毁！

### [STATE: BUSINESS_FACT_CONTRACT] (业务事实契约)

caller 明确采用 `34_Frontend-Backend-Contract-Collaboration-SOP.md` 时，与前端 Owner 消费同一权威契约，按配套对齐单供给用户任务所需事实，并验证真实入口、失败场景和同步变更。本 Skill 不复制页面规划、不隐式调度 S9；角色分工不强制独立仓库、部署或多个 Agent。
- 写接口前先确认：用户要判断什么、前端要解释什么、后端需要提供哪些事实。
- 输出模型必须围绕业务对象组织，而不是围绕表结构、DTO 命名或内部枚举组织。
- 面向前端的数字必须带单位、时间窗口、分母或基准；否则前端无法把它翻译成用户可理解的结论。
- 错误响应只暴露稳定的业务原因、可重试性和必要定位线索；数据库异常、Trace、内部状态码只能进入日志或证据层。
- 如果前端页面需要判断好坏、原因、影响或行动，但接口没有足够事实，应回到 API contract 补字段，不允许前端猜结论。

### [STATE: API_CONTRACT_DEFINITION] (接口防泄漏契约对齐)
- 在写入实际业务前，必须强制锁定输入/输出 JSON 模型（如 Zod 或 Pydantic）。
- 绝不信任外部调用方，若发现缺失强类型校验（Type Guard），立即拒绝对接。

### [STATE: DEFENSIVE_IMPLEMENTATION] (防御性实战编码)
- **参数防暴击**：所有入口参数强制挂载校验器，失败立刻 Fail-fast 抛 400，绝不放进内存脏转。
- **凭证遮罩**：API Key、数据库账号密码绝对禁止硬编码明文写入，强制索取 `os.environ` 或 `.env` 的配置句柄。
- **幂等性隔离**：若是写接口（Create/Update），强迫注入乐观锁（Version/Token）防御超大并发重放。

### [STATE: PERFORMANCE_AND_SECURITY_AUDIT] (核爆沙盘演习与脱敏)
- 审查：日志抛出时有没有直接把底层 DB SQLException 原样透传给前端？（必须打掩码或统转 `500 Server Error`）。
- 任何外部调用的崩溃代码，必须打出带源参的 StackTrace 留底控制台。

</rules>

<template>

## 3. 📤 标准通信契约 (Harness Execution Contract)
切结移交前，抛出 JSON 代码：
```json
{
  "harness_metadata": { "phase": "S10_Backend_Dev", "status": "SUCCESS" },
  "endpoints_touched": ["POST /api/v1/auth/login", "Db Schema: users_table"],
  "security_audit": "入参 Validator 已上膛，凭据全部走 .env 暗桥，未发现循环查库隐患",
  "next_routing": "W9_出口验收 或 S11_单元测试联动"
}
```

## 4. 📦 脚本资产清单 (Script Asset Registry)

| 脚本 | 路径 | 用途 |
|:---|:---|:---|
| `api_load_tester.py` | `./scripts/api_load_tester.py` | API 负载压力测试工具 |
| `api_scaffolder.py` | `./scripts/api_scaffolder.py` | REST API 脚手架生成器 |
| `database_migration_tool.py` | `./scripts/database_migration_tool.py` | 数据库迁移辅助工具 |

</template>
