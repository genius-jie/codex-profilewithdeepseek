---
name: S45_多模型Provider调用
type: infrastructure
domain: integration
tier: L3
status: active
doc_status: active-ssot
description: |
  【触发场景】Graphify、Instructor、AutoGen、评测流水线或业务工具需要通过第三方 API Key 调用 DashScope/Qwen、Gemini、百度千帆、MiniMax、火山方舟或 AICodeLink；需要结构化 JSON、模型发现、超时重试、推理正文隔离或脱敏调用回执。
  【不触发】当前 Codex/Claude Code 自身完成语义分析；CodeGraph 本地静态代码索引；不需要外部模型 API 的普通任务。
  【功能】提供 7 个真实密钥的统一 SSOT、provider/最高能力模型契约、MiniMax reasoning_split 适配、显式零 SDK 重试、确定性 JSON 校验和可审计调用入口。
related:
  - @@GENERAL_ROOT:win@@\control\registry\01-asset-register.md
  - @@GENERAL_ROOT:win@@\control\registry\02-skill-catalog.md
  - @@GENERAL_ROOT:win@@\control\registry\05-global-knowledge-graph.md
  - @@GENERAL_ROOT:win@@\assets\skills\S41_cc-switch协议兼容修复\SKILL.md
  - @@GENERAL_ROOT:win@@\assets\skills\S12_系统化调试\SKILL.md
  - @@GENERAL_ROOT:win@@\assets\skills\S46_Graphify知识图谱运行\SKILL.md
  - @@GENERAL_ROOT:win@@\assets\references\methodology\03_Skill-Lifecycle-Protocols.md
  - @@TESTING_ROOT:win@@\.agent\index\02-child-knowledge-graph.md
extends:
  - @@GENERAL_ROOT:win@@\assets\rules\execution.md
  - @@GENERAL_ROOT:win@@\assets\references\methodology\10_S-Tier-Execution-Discipline-Protocol.md
ssot_check: NEW
map_updated: true
birth_ceremony_id: bc-s45provider-c8d5b500
birth_ceremony_date: 2026-07-30
---
# S45 多模型 Provider 调用

## 第一性定位

这个 Skill 解决的是“外部模型接入反复踩同一类坑”，不是替 Agent 思考。

- Agent 负责：理解任务、选择 provider 与模型角色、设计 prompt/schema/chunk、判断语义质量、决定是否缩小输入或改方案。
- Python/SDK 负责：读取密钥、组装 HTTP 请求、限制超时与重试、隔离 reasoning、校验 JSON 语法/schema、写脱敏回执。
- Instructor 可作为结构化语义后的 typed gate；它不是主分析 Agent，也不替代 provider 适配。

禁止用 Python 的字符串匹配、正则或机械评分替代 Agent 对业务语义、模型质量和任务难度的判断。

## SSOT 与目录职责

唯一正式落点是本 Skill：

| 路径 | 职责 |
|:---|:---|
| config/provider-credentials.env | 7 个真实密钥的唯一运行时来源；脚本读取但不回显 |
| config/provider-profiles.json | provider、端点、最高能力默认模型、模型角色、适配器与验证状态 |
| config/provider-profiles.schema.json | provider contract 的机器校验 schema |
| scripts/model_provider.py | validate、models、call、run-tool 四个确定性动作 |
| references/provider-call-contract.md | 调用方法、provider 坑位和故障分类 |
| agents/openai.yaml | Codex Skill 展示与默认入口 |

迁移来源 @@OPENCLAW_ROOT:win@@\projects\marketing-video-crawler\src\.env 只保留为冻结历史来源；新调用不得继续依赖该项目路径。

## 强制调用流程

1. 先运行 validate，确认 7-key 契约、公开 profile 和 schema 一致。
2. Agent 按任务选择 provider 和 model-role；Python 不做语义路由。
3. 高价值或长任务先运行 models，确认模型仍对当前 key 可见。
4. 运行 call；结构化任务必须带 --expect-json，必要时带 --schema。
5. 读取 response 与 receipt；reasoning 只记录“是否存在/长度”，不得混入交付正文。
6. 调用状态机只把“拿到可用最终正文”视为完成；单次报错只是 attempt 结果：
   - 429/5xx：默认一次、最多一次外层 transport retry。
   - 401/403：凭证或权限问题，直接阻断该 provider。
   - 空正文/非法 JSON：允许一次只纠正响应信封的 bounded repair；仍失败时由 Agent 缩小 chunk、简化 schema 或调整输出预算。
   - JSON 截断/schema 不匹配：不做机械语义修复，交回 Agent 决策。
   - content 出现 think 标签：适配器优先恢复 final marker 后正文，再清洗任意位置的完整/残缺标签；以 warning 留痕，不把格式瑕疵升级成终态失败。
   - 错误回执固定 terminal=false；只有 PASS 且 response 已落盘才是 terminal=true。

## 快速调用

先定义一次路径：

~~~powershell
$s45 = '@@GENERAL_ROOT:win@@\assets\skills\S45_多模型Provider调用\scripts\model_provider.py'
python $s45 validate
~~~

查看 provider 当前模型：

~~~powershell
python $s45 models --provider minimax
python $s45 models --provider dashscope_primary
~~~

使用 MiniMax-M3 输出严格 JSON：

~~~powershell
python $s45 call --provider minimax --model-role default --prompt-file .\prompt.md --expect-json --response-out .\result.json --receipt-out .\result.receipt.json
~~~

Graphify 的生产调用统一路由到 `S46_Graphify知识图谱运行`。S46 从本 Skill 读取凭证和 Provider profile，再负责 standard incremental、manifest/cache、物理图回执与 Agent 查询签收；本 Skill 不再复制 Graphify 命令和模式规则。

## 模型选择原则

公开 profile 以“能力优先、固定可追溯”为默认：

| Provider | 默认高能力模型 | 主要用途 |
|:---|:---|:---|
| DashScope 主/备 key | qwen3.7-max | 通用分析、结构化输出；双 key 只做故障切换 |
| Gemini | gemini-3.1-pro-preview | 高难推理、多模态语义 |
| 百度千帆 | ernie-5.1 | 中文通用分析 |
| MiniMax | MiniMax-M3 | 深度语义分析；强制 reasoning_split |
| 火山方舟 | doubao-seed-2-1-pro-260628 | 通用高能力分析 |
| AICodeLink | gpt-5.6-sol | 高能力代理模型；已通过 models 与结构化真实调用 |

不得仅凭模型名里的版本号让 Python 自动判“更强”。模型角色由 Agent 结合任务、能力、上下文长度、结构化稳定性和实时可用性选择。

## MiniMax 必须避开的坑

- MiniMax-M3 默认可能把 think 推理正文放入 content。
- 本 Skill 固定注入 extra_body.reasoning_split=true。
- reasoning_content/reasoning_details 不进入 response 文件，只在 receipt 中记录布尔值和长度。
- 调用器要求模型使用统一 final marker；脚本兼容 marker 位于答案前或答案末尾，并恢复实际正文。
- 完整 think 块无论位于开头还是正文之间，都由确定性标签状态机剥离。
- 标签未闭合、只有孤立关闭标签或夹在最终正文中时，脚本清洗标签并记录兼容 warning，不直接打回。
- 结构化任务会从清洗后的尾部恢复最后一个完整 JSON value，避免前置推理破坏 JSON。
- SDK max_retries 固定为 0；外层 transport retry 默认 1、上限 1，且只允许 429/5xx。
- 空正文或 invalid JSON 允许一次响应信封修复重放；它只重申输出格式，不判断业务语义。
- finish_reason=length 或 schema failure 必须由 Agent 调整 chunk/schema/budget，Python 不越权判断。
- 回执中 terminal=true 只随 PASS 出现；任何 ERROR/BLOCKED/RETRY_REQUIRED 均为 terminal=false，流水线必须继续处置。

## 与相邻能力的边界

- S41：只处理 Claude Code 经 cc-switch 的 provider 协议兼容；不承接普通项目模型调用。
- S46 / Graphify：S46 消费本 Skill 的 Provider 环境并治理 Graphify 运行；Graphify 原生负责检测、抽取、缓存、合并和遍历。
- CodeGraph：100% 本地静态分析，不读取本 Skill 密钥。
- 当前 Codex/Claude Code：仍是开发与治理语义 Agent；只有外部工具天然需要第三方模型时才调用本 Skill。

## 完成回执

每次 call 至少产出：

- provider、model、base_url host
- credential env 名、是否存在、长度
- timeout、SDK retry、transport retry
- HTTP/finish_reason/usage
- reasoning 是否存在、content 是否出现 think、是否完成兼容剥离
- JSON/schema 是否通过
- response SHA256、耗时与错误分类

回执不得包含密钥原文、请求 Authorization、reasoning 正文或用户敏感输入全文。
