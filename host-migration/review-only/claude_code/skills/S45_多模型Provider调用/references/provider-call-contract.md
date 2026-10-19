---
domain: root-governance
tier: L2
status: active
doc_status: active-reference
related:
  - @@GENERAL_ROOT:win@@\assets\skills\S45_多模型Provider调用\SKILL.md
  - @@GENERAL_ROOT:win@@\assets\skills\S45_多模型Provider调用\config\provider-profiles.json
  - @@GENERAL_ROOT:win@@\assets\skills\S45_多模型Provider调用\scripts\model_provider.py
birth_ceremony_id: bc-s45provider-contract-c8d5b500
birth_ceremony_date: 2026-07-30
---

# S45 Provider 调用契约

## 1. 数据契约

运行时只认以下三件物理资产：

1. provider-credentials.env：恰好 7 个非空变量，不允许额外变量或同名重复。
2. provider-profiles.json：端点、env 映射、默认模型、模型角色、请求/响应适配器。
3. provider-profiles.schema.json：机器可验证的数据形状与重试上限。

调用优先级固定为：

1. CLI 显式 --model。
2. Agent 显式 --model-role。
3. provider default_model。

Python 不根据关键词、模型名字或业务文本自动选择 provider。

## 2. 七个凭证的统一映射

| env | Provider | 用途 |
|:---|:---|:---|
| DASHSCOPE_API_KEY_1 | DashScope 主路 | Qwen 高能力模型 |
| DASHSCOPE_API_KEY_2 | DashScope 备路 | 主 key 不可用时切换 |
| GEMINI_API_KEY | Gemini | 高难推理、多模态 |
| QIANFAN_API_KEY | 百度千帆 | 中文分析与 ERNIE |
| MINIMAX_API_KEY | MiniMax | MiniMax-M3 / Graphify 语义抽取 |
| VOLCENGINE_ARK_API_KEY | 火山方舟 | 豆包高能力模型 |
| AICODELINK_API_KEY | AICodeLink | GPT 代理；当前默认 gpt-5.6-sol |

密钥值只存在 config/provider-credentials.env。文档、回执、日志和命令行不得复制原文。

## 3. MiniMax-M3 规则

### 请求层

- model 固定优先 MiniMax-M3。
- extra_body 必须包含 reasoning_split=true。
- OpenAI SDK max_retries 必须显式为 0。
- 外层 transport retry 默认 1，上限 1，只处理 429/500/502/503/504。

### 响应兼容层

- 交付正文最终只取规范化后的 message.content。
- reasoning_content 与 reasoning_details 只统计存在性和长度，不写入 response。
- reasoning_split 生效时，content 直接作为最终正文。
- 调用器要求模型使用统一 final marker；脚本兼容 marker 位于答案前或答案末尾，并恢复实际正文。
- 若 provider 仍把推理放入 content，脚本剥离任意位置的完整 think 块，再把剩余正文交给 JSON/schema 校验。
- 标签未闭合、出现孤立关闭标签或夹在最终正文中时，脚本只清洗标签并写 compatibility_warnings，不把格式瑕疵升级成调用失败。
- 剥离使用确定性标签状态机，不分析推理语义，也不使用正则猜测最终答案。
- 结构化调用会从清洗结果尾部恢复最后一个完整 JSON value。

### 结构化层

- --expect-json 时只接受单个 JSON value。
- 完整 Markdown fence 可做确定性剥离；除此之外不做“猜 JSON”修复。
- finish_reason=length 且 JSON 无法解析时返回 OUTPUT_TRUNCATED。
- 空正文或 invalid JSON 允许一次 bounded response-envelope repair；重放只要求模型重新输出最终载荷，不做业务语义判断。
- schema failure 和 truncation 不做机械重试，由 Agent 一次只改一个变量：缩小文档 chunk、收窄 schema、降低实体/边数量或提高输出预算。

## 4. 其他 provider 注意事项

### DashScope

- 两把 key 是主备，不默认并行散射同一语义任务。
- qwen3.7-max 是当前能力优先默认；重大任务先运行 models --contains qwen3.7 复核。
- 视觉任务由 Agent 显式选择 vision role，普通文本调用不自动切到 omni。

### Gemini

- 模型发现走 Google 原生 models API；聊天调用走 OpenAI compatibility endpoint。
- preview 模型可能漂移，交付回执必须记录具体 model。

### 百度千帆

- 默认 ernie-5.1；需要显式深度思考时由 Agent 选择 reasoning role。
- 若 provider 返回完整前置 think 块，采用与 MiniMax 相同的确定性兼容层。

### 火山方舟

- 模型 ID 带日期，代表固定版本；重大任务先查询模型可见性。
- 默认 doubao-seed-2-1-pro-260628，不自动用 flash/lite 取代高能力模型。

### AICodeLink

- 更新 key 在 2026-07-30 查询 models 返回 HTTP 200，可见 10 个模型。
- 默认 gpt-5.6-sol，已通过结构化 chat 实测；gpt-5.6-terra 仅作为 Agent 显式 fast role。

## 5. Graphify 接入

Graphify 是外部语义抽取工具，使用 MiniMax key；CodeGraph 是本地静态分析，两者分工不同。

Graphify custom provider 应满足：

- base_url=https://api.minimaxi.com/v1
- default_model=MiniMax-M3
- env_key=MINIMAX_API_KEY
- extra_body.reasoning_split=true

通过 run-tool 启动时，S45 还会注入：

- GRAPHIFY_MAX_RETRIES=0
- GRAPHIFY_MAX_CONCURRENCY=1
- GRAPHIFY_MAX_OUTPUT_TOKENS=8192
- GRAPHIFY_API_TIMEOUT=240

这只限制机械重试和并发，不替代 Agent 对文档切块、schema 复杂度和抽取目标的判断。

Graphify extract 的 terminal 判定不采信单独的进程退出码：脚本还必须读取 `<out>/graphify-out/graph.json`，确认 nodes>0 且 output_tokens>0。退出 0 但扫描 0 文件、0 节点或 0 token 时，回执为 RETRY_REQUIRED / terminal=false。

稳定性门禁使用增量 SSOT，而不是要求 LLM 强制重抽逐字一致：首次抽取落盘后，未改动文档的再次同步必须保持 graph SHA256 不变；内容哈希发生变化才允许重抽。两次 `--force` 可用于观测模型漂移，但它不是 W7/W9 的发布判据。

## 6. 标准错误分类

| error_class | 含义 | 正确处理 |
|:---|:---|:---|
| AUTH_OR_PERMISSION | 401/403 | 检查凭证/权限，不重试 |
| RATE_LIMIT | 429 | 允许最多一次外层重试 |
| PROVIDER_SERVER_ERROR | 5xx | 允许最多一次外层重试 |
| REASONING_COMPAT_WARNING | think 标签不完整或位置异常但已恢复正文 | 允许交付，Agent 读取 warning 做语义复核 |
| INVALID_JSON | content 非合法 JSON | 先做一次信封修复；仍失败则 Agent 调整 prompt/schema/chunk |
| OUTPUT_TRUNCATED | finish_reason=length 且 JSON 不完整 | 缩小输入或提高预算 |
| SCHEMA_VALIDATION_FAILED | JSON 合法但不符合 schema | Agent 修语义契约 |
| CONTRACT_ERROR | SSOT/schema/变量映射不一致 | 先修 S45 契约，不调用模型 |

## 7. 验收口径

一次调用只有同时满足以下条件才算 PASS：

- provider/model 明确。
- 凭证来自 Skill 内 SSOT。
- SDK 重试为 0。
- MiniMax reasoning 已被分离或确定性兼容剥离。
- expect-json 时 JSON/schema 均通过。
- response 与脱敏 receipt 均已物理落盘。

状态约定：错误 attempt、BLOCKED 或 RETRY_REQUIRED 回执一律 terminal=false；只有上述条件全部满足时才写 terminal=true / completion_state=SUCCEEDED。流水线不得把“脚本报错并退出”误判成任务完成。
