---
name: S41_cc-switch协议兼容修复
description: 【触发场景】Claude Code 经 cc-switch 调用第三方模型出现协议错误。【不触发】非代理链问题。【功能】按 provider 隔离修复、持久化并验证。
type: generic
domain: llm-provider-compatibility
tier: L3
status: experimental
doc_status: active-ssot
birth_ceremony_id: bc-s41-ccswitch-compat-638a5329
birth_ceremony_date: 2026-07-10
related:
  - @@GENERAL_ROOT:win@@\assets\skills\M2_技能生产与归档\SKILL.md
  - @@GENERAL_ROOT:win@@\assets\skills\S12_系统化调试\SKILL.md
  - @@GENERAL_ROOT:win@@\assets\skills\S14_完成前验证\SKILL.md
  - @@GENERAL_ROOT:win@@\assets\skills\S37_封装赋能Skill\SKILL.md
  - @@GENERAL_ROOT:win@@\control\registry\01-asset-register.md
  - @@GENERAL_ROOT:win@@\control\registry\02-skill-catalog.md
  - @@GENERAL_ROOT:win@@\control\registry\05-global-knowledge-graph.md
  - @@SANITIZER_ROOT:win@@\read-tool-sanitizer-proxy.js
---

# S41 cc-switch 协议兼容修复

## 1. 目标与边界

修复 Claude Code、cc-switch 与 OpenAI 兼容上游之间的协议差异。把兼容逻辑放在目标 provider 的代理边界，不修改 Claude Code 内核，不污染其他模型。

执行时遵守以下边界：

1. 先复现并捕获真实请求、响应和路由证据，再判断根因。
2. 共用代理代码可以复用，但每个 provider 使用独立监听端口和独立环境开关。
3. 只启用目标 provider 必需的 sanitizer；禁止用全局改写处理单一模型问题。
4. 保留 `model`、`role`、`tool_call_id`、工具调用顺序、认证头和流式事件顺序。
5. 无法无损转换的多模态或工具语义必须显式报错，禁止静默丢弃。
6. 密钥只确认来源、存在性和长度；日志、命令回显和报告不得输出原文。
7. 默认不修改普通 Codex 配置。只修改用户明确指定的 cc-switch、Claude Code 或隔离代理资产。

## 2. First-Fact 取证

先收集以下最小事实包：

```yaml
provider:
model:
exact_error:
claude_code_endpoint:
cc_switch_route:
upstream_endpoint:
listener_port:
proxy_process:
service_name:
request_shape:
response_shape:
enabled_flags:
```

至少取得这些物理证据：

- Claude Code 展示的完整错误文本和发生时间。
- 去密钥后的失败请求体，以及对应的上游响应体或 SSE 片段。
- cc-switch 数据库中当前 provider、model、base URL 和代理端口映射。
- `Get-NetTCPConnection`、`Get-CimInstance Win32_Process` 和 NSSM 的实际进程、命令行、监听状态。
- sanitizer 脚本的当前版本、语法检查结果和环境变量。

不要把“模型不存在”“余额不足”或“Claude Code 自己有问题”当作默认结论。先确认请求是否到达目标端口、上游返回了什么、代理是否改写了载荷。

## 3. 故障分类

| 类别 | 典型错误 | 修复位置 |
|:---|:---|:---|
| 消息内容不兼容 | `messages.content.type 参数非法`、`Unexpected item type in content` | 请求 sanitizer |
| 工具参数 JSON 损坏 | `InputValidationError`、`__unparsedToolInput`、两个 JSON 对象粘连 | 流式工具参数聚合与 schema-aware repair |
| Read 参数不兼容 | `pages:""` 或目标工具 schema 不接受空 `pages` | Read 专用输入 sanitizer |
| 空思考事件 | 连续出现 `Thought for 0s` | 目标 provider 的响应流 sanitizer |
| 模型发现失败 | selected model may not exist、`/model` 无目标模型 | `/v1/models` 代理与模型 ID 映射 |
| 路由或持久化漂移 | 重启后回到旧端口、服务未启动 | cc-switch 路由、NSSM 与健康检查 |

如果 HTTP 已到达上游且返回业务 4xx，优先检查请求 schema。如果请求没有到达目标代理，先修路由、进程或认证链，不要先写 sanitizer。

## 4. 兼容规则

### 4.1 仅文本 content

对明确只接受文本的 provider 启用内容归一化：

1. 字符串 `content` 原样保留。
2. 数组 `content` 只将可证明为文本的块转换为字符串。
3. `tool_result` 的文本内容可转为字符串，但保留外层 `role` 和 `tool_call_id`。
4. 图片、音频或未知块不能无损表达时返回明确错误，不得直接删除。
5. 不改变 system、assistant、user、tool 的相对顺序。

当前参考实现可使用 `READ_SANITIZER_TEXT_ONLY_MESSAGE_CONTENT` 作为 provider 级开关；实际修改前先以脚本现有变量名为准。

### 4.2 工具参数 JSON

按工具调用 ID 聚合完整 arguments 后再解析，不对半个 SSE 增量做最终判断。

只允许确定性的最小修复：

- 去除 BOM 和首尾空白。
- 当两个连续 JSON 对象分别可解析且内容完全相同时，只保留一个。
- 当 `__unparsedToolInput.raw` 内含一个完整合法对象时，恢复该对象。
- 依据已知工具 schema 修复单个、可唯一判定的结构缺口，并保存修复前摘要。

禁止执行以下操作：

- 用大正则重写任意 JSON。
- 合并两个内容不同的对象。
- 猜测被截断的命令、路径或业务参数。
- 为了通过解析而删除未知字段或工具调用。

修复后必须再次用严格 JSON 解析器和目标工具 schema 校验。无法唯一修复时返回原始错误和诊断信息。

### 4.3 Read 的空 pages

仅当工具名为 `Read` 且 `pages` 为 `""`、`null` 或空数组时删除该字段。非空 `pages` 必须保留，其他工具不得套用此规则。

不要把请求读取超过文件总行数当作 `pages` 问题。行范围错误应独立验证 `offset`、`limit` 和真实文件行数。

### 4.4 空 thought

仅对已确认会产生空 reasoning/thinking 事件的 provider 启用响应过滤：

- 删除文本为空或仅含空白的 reasoning/thinking 事件。
- 保留非空思考、最终文本、工具调用、usage 和结束事件。
- 保证 SSE 帧格式、事件顺序和结束标记不变。

当前参考实现可使用 `READ_SANITIZER_STRIP_EMPTY_THINKING`；不要在其他 provider 端口启用。

### 4.5 模型列表

代理 `/v1/models` 时：

1. 优先透传上游模型列表。
2. 上游没有兼容接口时，按当前 provider 配置生成最小列表。
3. 返回的 `id` 必须与 Claude Code 配置、cc-switch provider 配置和实际请求 model 完全一致。
4. 模型别名映射必须显式记录，禁止靠模糊匹配猜测。

当前参考实现可使用 `READ_SANITIZER_MODELS_LIST` 和 `READ_SANITIZER_MODELS_UPSTREAM`；先核对脚本实际实现。

## 5. 实施状态机

1. **快照**：备份 sanitizer、NSSM 参数和 cc-switch 数据库；记录监听端口与进程命令行。
2. **定位**：复现失败，关联 Claude Code 时间、代理日志和上游响应。
3. **分类**：从第 3 节选择单一主根因；多个问题分开开关，避免捆绑修补。
4. **实现**：优先编写纯函数完成请求或响应转换，再接入 HTTP/SSE 转发层。
5. **隔离**：为目标 provider 分配独立本地端口，只在该服务实例设置对应环境变量。
6. **路由**：更新 cc-switch provider 的 base URL、模型 ID 或 `/models` 路由；不要改其他 provider 行。
7. **持久化**：使用 NSSM 固化可执行文件、参数、工作目录、环境变量、日志和自动重启策略。
8. **验证**：执行语法、函数、HTTP、真实 Claude Code、跨 provider 和重启后验证。
9. **清理**：停止并删除废弃服务、旧监听、旧启动项和失效配置引用；保留有效备份和审计日志。

当前机器的常见端口只可作为探针线索，例如 `15722`、`15723`、`15725`、`15726`、`15727`。每次都以实时监听、数据库和 NSSM 配置为事实源。

## 6. 验证矩阵

完成前必须提供以下证据：

| 验证项 | 通过条件 |
|:---|:---|
| 静态语法 | `node --check` 或对应解析器通过 |
| 纯函数样例 | 失败载荷被最小修复；正常载荷字节语义不变 |
| 健康检查 | 目标端口返回预期状态，上游可达性单独记录 |
| 模型发现 | `/v1/models` 含当前选择的精确 model ID |
| 工具调用 | Read、PowerShell、TodoWrite 等代表性工具参数可严格解析 |
| 消息内容 | GLM/Qwen 等目标 provider 不再返回 content 类型错误 |
| 流式响应 | 无重复空 thought，文本、工具和结束事件完整 |
| 隔离回归 | 未启用该开关的 provider 请求和响应不变 |
| 持久化 | NSSM 服务状态正确，重启服务后端口与环境变量仍正确 |
| 残留清理 | 无旧监听、旧进程、旧启动项或数据库旧路由 |

真实请求验证不能只用手写 curl 代替。至少新建一个 Claude Code 会话，执行会触发目标故障类型的最小任务，并将 UI 结果与代理日志时间对应。

## 7. 常用探针

```powershell
Get-NetTCPConnection -State Listen |
  Where-Object LocalPort -In 15722,15723,15725,15726,15727

Get-CimInstance Win32_Process |
  Where-Object CommandLine -Match 'cc-switch|sanitizer|1572'

node --check "@@SANITIZER_ROOT:win@@\read-tool-sanitizer-proxy.js"

Invoke-RestMethod "http://127.0.0.1:<port>/health"
Invoke-RestMethod "http://127.0.0.1:<port>/v1/models"
```

查询 SQLite 前先识别实际数据库和表结构。输出 provider 记录时屏蔽 token，只显示名称、model、URL、端口和密钥长度。

## 8. 阻断条件

遇到以下情况停止扩大改动面并报告证据：

- 目标请求无法复现，且没有原始请求或代理日志。
- 同一 payload 在直连上游也失败，表明不是 cc-switch 边界问题。
- 修复需要丢弃未知多模态或工具语义。
- 连续三次修改仍不能通过同一最小复现。
- 端口或服务归属不清，可能影响其他正在使用的 provider。

## 9. 输出契约

```json
{
  "harness_metadata": {
    "phase": "S41_cc_switch_compatibility",
    "status": "COMPLETED|BLOCKED"
  },
  "root_cause": {
    "layer": "claude_code|cc_switch|sanitizer|upstream",
    "evidence": []
  },
  "provider_scope": {
    "provider": "",
    "model": "",
    "listener": "",
    "enabled_flags": []
  },
  "changes": [],
  "verification": {
    "syntax": "",
    "health": "",
    "models": "",
    "real_claude_code_request": "",
    "cross_provider_regression": "",
    "restart_persistence": ""
  },
  "residuals": [],
  "source_trace": {
    "proxy_file": "",
    "database": "",
    "service": "",
    "logs": []
  }
}
```

只有真实 Claude Code 请求、目标 provider 修复、其他 provider 不受影响、服务重启后仍正常且无废弃残留时，才能标记 `COMPLETED`。
