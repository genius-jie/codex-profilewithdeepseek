---
name: S40_三方模型工具调用适配
description: 当前环境为 Codex GPT + DeepSeek-V4-Pro（cm 网关）等第三方模型时的工具调用适配技能；用于防 aborted 卡死、字段名漂移与跨会话复发。出现任务反复失败时使用。
---

# S40 三方模型工具调用适配（DeepSeek-V4-Pro）

## 触发条件
- 会话中反复出现 aborted、工具调用被拒、任务卡死；
- 当前环境为 DeepSeek-V4-Pro / deepseek-v4-pro 等三方模型；
- 新会话接手 E:\hitouch 前后做防漂移自查。

## 核心契约（与 E:\hitouch\AGENTS.md 一致）
- exec_command 唯一合法主字段是 cmd；command 是历史血案字段，一律禁止。
- 入会话探针：tools.exec_command({cmd:"Write-Host probe-ok", yield_time_ms:10000, max_output_tokens:2000})
- 失败签名三查：aborted → 字段名；Hook 拦截 → 读 reason；ParserError → 命令瘦身。
- 成功判定只看 exit_code：0 通过。exec_command 返回 [2] 表示异步会话，必须用 write_stdin 轮询到退出。

## 工具声明类型契约（Codex 26.1027 起）

- 客户端声明只有四类：`function`、`custom`（可按名调用的只有代码模式 `exec`）、`namespace`（MCP 服务包）、`web_search`（内置能力）。后两类不可按名调用。
- 只按声明类型分级，禁止“非 function 即 custom”的二分；`namespace` / `web_search` 不暴露成扁平工具，模型改由 `exec` 内的 `tools.*` 绑定访问。
- 历史项不是工具类型的权威，声明才是；历史 `function_call` / `custom_tool_call` 只能补充声明里缺失的名字，不能反向改写声明。
- 失败签名 `unsupported custom tool call: <name>` 来自宿主工具注册表：该名字未被声明为 custom，整轮直接终止，不是可恢复的工具错误。先取日志里的 `toolShape` 看真实声明类型，再改映射，不要先换模型或改提示词。
- 已知宿主内部别名只有 `exec_command`、`mcp__node_repl__js`，收敛为 `exec`（`tools.exec_command(payload)` / `nodeRepl.write -> text`）；其他未知名称一律不泛化。
- 完整故障链、修复项与回归证据见 `skills/S34_Codex认证切换/resources/错题本.md` 2026-11-06 条目。

## 输出纪律
- 工具调用参数全部显式写出、用字面量；不省略可选字段；不用变量拼参数名。
- 每次 exec 后嵌入 [CODEX_TOOL_RESULT_META] 行报告 exit_code，作为会话内证据。
- 长会话每约 5 次工具调用，复用探针形态自查一次字段漂移。

## 交叉引用
- 项目 SSOT：E:\hitouch\AGENTS.md
- Profile L0：D:\CodexPlusPlusProfile\AppData\Roaming\Codex\.codex\AGENTS.md 第 3.3 节
- 持久笔记：memories/extensions/ad_hoc/notes/20261012-deepseek-v4-toolcall-contract.md

## 激活后结束回执
每次激活本技能，任务结束前输出：探针结果、失败签名、字段自检清单、exit_code 证据。

