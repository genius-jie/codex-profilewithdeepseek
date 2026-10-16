---
domain: codex-plusplus-profile
tier: L3
status: active
doc_status: active-reference
last_verified: 2026-09-22
related:
  - D:\CodexPlusPlusProfile\AppData\Roaming\Codex\.codex\skills\S34_Codex认证切换\SKILL.md
  - D:\CodexPlusPlusProfile\AppData\Roaming\Codex\.codex\skills\S34_Codex认证切换\resources\Codex++运行与归档SSOT.md
  - C:\Users\Administrator\.agent\control\host-capability-publication-manifest.yaml
  - C:\Users\Administrator\.agent\tooling\Sync-HostCapabilityProjection.ps1
  - C:\Users\Administrator\.codex-plusplus-config\Start-CodexPlusPlus.ps1
  - C:\Users\Administrator\.codex-plusplus-config\Test-CodexIsolation.ps1
  - D:\CodexPlusPlusProfile\AppData\Roaming\Codex\.codex\config.toml
birth_ceremony_id: bc-s34-codexplusplus-baseline-20260516
birth_ceremony_date: 2026-05-16
---

# Codex++ 隔离配置基线

## 2026-09-22 最终 D-only canonical 规则

当前有效的 Codex++ mutable data owner 只有物理 D 盘：

- CODEX_HOME：`D:\CodexPlusPlusProfile\AppData\Roaming\Codex\.codex`
- runtime/tweaks/log/state：`D:\CodexPlusPlusProfile\AppData\Roaming\codex-plusplus`
- OpenCLI 本地 adapter：`D:\CodexPlusPlusProfile\.opencli\clis`
- Electron user-data-dir：`D:\CodexPlusPlusProfile`
- installer source：`D:\.codex-plusplus`
- 启动前 preflight 日志统一写入 `D:\CodexPlusPlusProfile\AppData\Roaming\codex-plusplus\log`；不得从继承的 `APPDATA` 推导 Codex++ 日志路径。

C 盘 Profile/runtime/source 入口已退役，不得重新成为入口。Windows Store 的 app mirror、普通 Codex、General OS 的 Skill SSOT 和静态 Skill projection 属于外部 owner，不纳入 Codex++ mutable data 迁移。

本文件记录 Codex++ 与普通 Codex 的隔离基线。这里允许记录路径、端口、字段名、存在性和短摘要；禁止记录 `api_key`、OAuth token、`auth.json` 正文或 `config.toml` 密钥原文。

## 1. 身份与边界

历史会话修复以 state_5.sqlite 的 threads.rollout_path 为唯一路径事实；旧 C/D 根和扩展前缀统一改成物理 D nested .codex 普通路径。thread_history_1.sqlite 只按 thread_id 跟随清理，不作为第二路径 SSOT。批量归档是一次性维护动作，按日期保留当天新会话，原文缺失时只能写明原因的安全 stub。

用户明确授权历史清理时，可以直接删除历史 rollout、历史投影和历史备份；必须按日期保留当天新会话，并在清理后重新核对 state DB、session index 和普通 Codex 边界。

| 项目 | Codex++ | 普通 Codex |
|:---|:---|:---|
| HOME / user-data-dir | 物理 `D:\CodexPlusPlusProfile` | `C:\Users\Administrator` |
| Codex 配置目录 | `D:\CodexPlusPlusProfile\AppData\Roaming\Codex\.codex` | `C:\Users\Administrator\.codex` |
| Electron `.codex` 入口 | `D:\CodexPlusPlusProfile\AppData\Roaming\Codex\.codex` | `C:\Users\Administrator\AppData\Roaming\Codex\.codex` |
| 默认认证目标 | 双模式支持：官方账号模式 或 CodexManager `cm` provider | 官方账号 / 原厂配置 |
| `auth.json` 期望 | 官方模式：auth_mode="chatgpt"；代理模式：auth_mode="apikey" 与 api_key 保持一致 | 存在 |
| 全局 skills 入口 | 仅加载隔离 profile 当前任务需要的本地 Skill；不以父级全量镜像作为隔离基线 | 54 个 Junction 指向 `C:\Users\Administrator\.agent\assets\skills` |

红线：
- 不要把 CodexManager API 端口 `48760` 与 Web 页面端口 `48761` 或系统代理端口混为一谈。
- Codex++ 的 `auth.json` 和 `config.toml` 中的 `api_key` 必须保持同步，都指向 CodexManager 平台密钥。
- 启动、一次性更新、基础 repair 与 one-shot session maintenance 在写入前必须验证 `D:\CodexPlusPlusProfile` 及 nested `.codex` 为物理目录；Start 与唯一 maintenance writer Sync 复用根目录校验，内部状态与 session 写入使用 D 盘 canonical root。普通 Codex 只读对照，未获明确授权不得修改。
- installer source 的 canonical root 固定为 `D:\.codex-plusplus`；`C:\Users\Administrator\.codex-plusplus` 已退役，不是第二套 source。受控写入、hash、审计、日志和 rollback 一律使用 D；迁移快照不参与运行链。

## 2. Codex++ `config.toml` 基线

文件：

```text
D:\CodexPlusPlusProfile\AppData\Roaming\Codex\.codex\config.toml
```

当前验收值：

```toml
model_provider = “cm”
approval_policy = “never”
sandbox_mode = “danger-full-access”

[windows]
sandbox = “elevated”

[model_providers.cm]
name = “OpenAI”
base_url = “http://127.0.0.1:48760/v1”
api_key = “sk-cm-...”
```

密钥管理 SSOT：
- Codex++ 的 API 密钥存储在 `config.toml` 的 `api_key` 字段和 `auth.json` 的 `OPENAI_API_KEY` 字段。
- 两处必须保持一致，都指向 CodexManager 平台密钥。
- `env_key` 字段必须不存在；否则 Codex CLI 会强制读取该环境变量并在缺失时直接失败，不会回退到 auth.json 或 config.toml api_key。
- 2026-07-10 验证：`api_key_present=True`，`api_key_length=64`，`auth.json.OPENAI_API_KEY` 与 `config.toml.api_key` 一致。
- 不得打印 `api_key` 原文。

`wire_api` 口径：
- `cm` provider 下不应配置 `wire_api = “responses”`。
- 2026-07-10 验证：`cm.wire_api=None`。

`projectlessWorkspaceRoot` 口径（2026-09-21）：
- 无项目任务根目录必须配置为 D 盘规范物理根路径：`D:\CodexPlusPlusProfile\Documents\Codex`（或保持 null 默认值）。
- 严禁配置为带有具体日期的子目录（如 `2026-09-10`），否则跨天后会计算出层级嵌套路径（如 `...\2026-09-10\2026-09-21`）；
- 严禁配置为 C 盘 Junction 别名路径，否则带 MSIX 程序包身份的受限进程跨卷创建目录会遭遇 Windows 文件系统隔离拦截，抛出 `ENOENT: no such file or directory`。

### 2.1 第三方模型协议适配覆盖（2026-09-11）

当 Codex++ 需要使用 DeepSeek/Kimi 等仅提供 Chat Completions 能力的模型时，当前机器使用独立的本地适配器覆盖：

```text
Codex++ -> http://127.0.0.1:15740/v1 -> CodexManager http://127.0.0.1:48760/v1
```

此模式下实际生效的配置可以是：

```toml
[model_providers.cm]
base_url = "http://127.0.0.1:15740/v1"
wire_api = "responses"
```

这里的 `wire_api="responses"` 只在 `15740` sanitizer overlay 场景下成立，不得把它误套到直连 `48760` 的基础 provider 基线。

适配器验收：

- `/health` 必须与源码/重载脚本版本一致；当前源码目标是 `responses-summary-v28-kimi-reasoning-effort-v1`，是否生效以新鲜健康检查为准。
- DeepSeek/Kimi 推理事件使用 `reasoning_summary_*`；工具调用使用 `custom_tool_call.input` 与 `custom_tool_call_input.delta/done`。
- 工具回放保留 `call_id` 关联，不与 item `id` 混用；同批并行调用合并到一条 assistant `tool_calls`，结果按 ID 回接。custom 工具以必填 `input` 字符串传递并双向还原；完整规则以 S34 的“DeepSeek/Kimi 的协议适配不变量”为准。
- 原生 GPT 回放 `store=false` 历史时，summary-only `rs_` reasoning 与对应 `item_reference` 必须清掉，带 `encrypted_content` 的有效 reasoning 必须保留；这是跨模型切换的统一边界。
- 适配器对 DeepSeek/Kimi 工具链实行 single-flight：同一时间一个活动上游请求，后续排队；客户端取消时释放上游请求和队列槽位。
- 上游 SSE 的 `error` 事件必须保留为失败语义，不能转换为空的 `response.completed(output=[])`；只允许对尚未产生输出或工具调用的空错误流做有界重试。
- `kimi-k3` 的适配器最低输出预算为 `max_tokens=1024`，避免推理摘要耗尽预算后没有工具调用；该规则不适用于其他模型。
- 代码模式内部 `tools.exec_command` 使用当前宿主公开的 `cmd/workdir/yield_time_ms` 参数。历史 `command/cwd/timeout` 别名只在已知 shell 桥接处转换，不把旧宿主字段规则推广到其他工具。
- DeepSeek 若把代码执行入口误叫成 `exec_command`，或把 `mcp__node_repl__js` 当成独立 custom tool，适配器必须只把这两个已知别名转成代码模式 `exec`：前者包装为 `tools.exec_command(payload)`，后者提供 `nodeRepl.write -> text` 绑定；其他 custom tool 名称保持原样。
- 独立回归必须执行实际的受限测试工具并回传结果，覆盖同一历史的模型切换与并行调用批次。旧五轮探针只证明预置结果的串行重放，不能代替真实执行或 UI 验收。
- 编辑 `codex-id-sanitizer-proxy.js` 后，必须重启 LocalSystem 服务；健康检查只返回 `status/proxy/port` 时仍是旧进程。

### 2.2 Canonical CODEX_HOME 与新目录写入

- Electron `--user-data-dir`、`USERPROFILE` 及内部写入统一落在物理 `D:\CodexPlusPlusProfile`；普通 Codex 继续使用自己的 C 盘 Profile。
- Codex 内部 `CODEX_HOME` 使用物理 canonical `D:\CodexPlusPlusProfile\AppData\Roaming\Codex\.codex`，避免路径重解析下创建新目录时返回 `ENOENT`。
- 新任务和可视化目录的真实写入验收使用 `D:\CodexPlusPlusProfile\AppData\Roaming\Codex\.codex\visualizations\YYYY\MM\DD\TASK_ID`。
- connector sync 的 TargetRoot 和备份目录使用 D canonical 根；单文件备份前显式创建备份父目录。

完全访问权限口径：
- `approval_policy = "never"` 对应 UI 的 `Never`。
- `sandbox_mode = "danger-full-access"`。
- `[windows] sandbox = "elevated"`。
- 这三项同时满足，才算 Codex++ 具备完整命令执行权限。

## 3. 启动脚本与入口

启动脚本目录：

```text
C:\Users\Administrator\.codex-plusplus-config
```

关键文件：

| 文件 | 作用 |
|:---|:---|
   - Start-CodexPlusPlus.ps1：Codex++ 主启动脚本；默认不扫描历史会话。
| `Start-CodexPlusPlus-Proxy.cmd` | 桌面代理启动入口；调用 Codex++ 启动脚本 |
| `Start-Codex.ps1` | 普通 Codex 隔离启动入口；清理代理变量并指向普通 `.codex` |
| `Test-CodexIsolation.ps1` | 普通 Codex / Codex++ 隔离自检脚本 |
| `C:\Users\Administrator\AppData\Local\Microsoft\WindowsApps\codex-plusplus-codex.cmd` | Codex++ 命令行 shim；必须设置 Codex++ `CODEX_HOME`，不得创建或依赖 `.codex` Junction |

桌面快捷方式口径：

| 快捷方式 | 期望目标 |
|:---|:---|
| `C:\Users\Administrator\Desktop\Codex++ 启动.lnk` | Codex++ 受保护代理隔离启动；目标为 `Start-CodexPlusPlus-Proxy.cmd` |
| `C:\Users\Administrator\Desktop\Codex 官方隔离启动.lnk` | 普通 Codex 官方隔离启动 |
| `C:\Users\Administrator\Desktop\Codex 隔离自检.lnk` | 执行 `Test-CodexIsolation.ps1` |

自检快捷方式目标：

```text
C:\Program Files\PowerShell\7\pwsh.exe
```

自检快捷方式参数：

```text
-NoProfile -NoExit -File "C:\Users\Administrator\.codex-plusplus-config\Test-CodexIsolation.ps1"
```

## 4. Electron `.codex` 物理目录

Codex++ Electron 入口就是物理配置目录，不创建任何重解析目录：

```text
D:\CodexPlusPlusProfile\AppData\Roaming\Codex\.codex
```

普通 Codex Electron 入口必须指回普通配置目录：

```text
C:\Users\Administrator\AppData\Roaming\Codex\.codex
  -> C:\Users\Administrator\.codex
```

普通 Codex 仍使用自己的 C 盘配置目录；两套配置不能交叉指向。

`\\?\` 前缀注意事项：
- Codex CLI (Rust) 内部对 session rollout 路径调用 `std::fs::canonicalize()`。Windows 上 `canonicalize()` 会解析 Junction 目标并加 `\\?\` 扩展路径前缀。
- 这导致 CLI 存储的路径（`\\?\C:\...\rollout.jsonl`）与前端 resume 时用的路径（`C:\...\rollout.jsonl`）不一致，触发 "stale path" 假阳性错误。
- 已在 Codex++ runtime preload 注入 `startStalePathGuard()` 自动过滤此假阳性 toast。
- 详见错题本 `2026-05-21` 条目。

## 5. hooks 基线

Codex++ hooks：

```text
D:\CodexPlusPlusProfile\AppData\Roaming\Codex\.codex\hooks.json
D:\CodexPlusPlusProfile\AppData\Roaming\Codex\.codex\hooks\
```

普通 Codex hooks：

```text
C:\Users\Administrator\.codex\hooks.json
C:\Users\Administrator\.codex\hooks\
```

状态隔离：

```text
Codex++: D:\CodexPlusPlusProfile\AppData\Roaming\Codex\.codex\hook-state\openclaw-mono-pending.json
normal:  C:\Users\Administrator\.codex\hook-state\openclaw-mono-pending.json
```

治理逻辑可以同步，但 `hook-state` 必须按各自 `CODEX_HOME` 分开落盘。

Stop hook 自动接续口径：
- 有明显“下一步 / 接下来 / 还要做”的 assistant final response 时，Stop hook 应返回 `continue: true` 和 `[HOOK:STOP_GUARD]` 的 `systemMessage`，让 agent 自动继续。
- 已完成、无剩余待办时，返回纯 `{"continue": true}`，不乱续。
- 重复同一条接续文本时，触发 `[HOOK:LOOP_GUARD]` 防循环。
- 不得输出当前 Codex 不接受的 `decision` 或 `hookSpecificOutput.decision` 字段。

## 6. skills 基线

普通 Codex 的技能入口：

```text
C:\Users\Administrator\.codex\skills
```

Codex++ 的技能入口：

```text
D:\CodexPlusPlusProfile\AppData\Roaming\Codex\.codex\skills
```

2026-08-18 验收：
- 普通 Codex：54 个 linked skill，目标均为父级 `assets\skills`。
- Codex++：保持隔离 profile 的本地 Skill 集，不以与普通 Codex 相同数量的 Junction 作为正确性条件。
- 父级 M1 的唯一 SSOT 为 `C:\Users\Administrator\.agent\assets\skills\M1_治理预加载门禁\SKILL.md`；Codex++ 仅在任务触发时按其自身入口加载所需能力。

技能发布策略：
- 不复制实体技能目录，也不把普通 Codex 的全部 Skill 批量镜像到 Codex++。
- General OS Publication Policy/Manifest 的唯一 SSOT 是 `C:\Users\Administrator\.agent\control\host-capability-publication-manifest.yaml`，Skill 正文只来自 `C:\Users\Administrator\.agent\assets\skills`。
- 当前 Manifest 选中的 canonical Junction 就是正式 Host 投影；不需要 Replay、cutover、回退包或第二份 Skill 正文。
- 生命周期只有 3 个 caller 和 1 个 writer；S34 与 Host 入口不复制 Manifest schema 或 Junction 算法。

### 6.1 更新后插件 marketplace canonical 边界（2026-09-11）

Codex++ 内部 `CODEX_HOME` 使用 `D:\CodexPlusPlusProfile\AppData\Roaming\Codex\.codex` 时，本地
marketplace 的来源必须使用 D 盘 canonical 路径：

```text
openai-primary-runtime -> D:\CodexPlusPlusProfile\AppData\Roaming\Codex\.codex\.cache\codex-runtimes\codex-primary-runtime\plugins\openai-primary-runtime
openai-bundled         -> D:\CodexPlusPlusProfile\AppData\Roaming\Codex\.codex\.tmp\bundled-marketplaces\openai-bundled
openai-curated         -> D:\CodexPlusPlusProfile\AppData\Roaming\Codex\.codex\plugins\cache\openai-curated
```

不要把 C 盘旧路径或 `\\?\` 重解析路径
写回 `config.toml` 的 `marketplaces.*.source`。这类路径虽然可能读取
已有文件，但 Codex++ plugin loader 会把 marketplace 解析成空列表；更新后必须
由 `Sync-CodexPlusPlusLatest.ps1` 在 repair 成功后重新校回 canonical 来源。

API key 模式只验收本地插件：2026-09-11 重启后 `codex plugin list --available
--json` 实际返回 7 个已安装、49 个可用；app-server/MCP 工具目录返回
`available_server_count=5`、`tool_count=93`。远程插件目录需要 ChatGPT OAuth，
API key 下的 401 或 `api key auth is not supported` 是认证边界，不得靠复制缓存、
重启循环或静默切换认证模式伪造通过。

## 7. CodexManager 端口

| 端口 | 作用 | 用法 |
|:---|:---|:---|
| `48760` | CodexManager API | `http://127.0.0.1:48760/v1`，写入 `cm.base_url` |
| `48761` | CodexManager Web 页面 | 浏览器管理页，不是 API base_url |
| `7890` | 系统代理常见端口 | 只有用户明确要求系统 HTTP/SOCKS 代理时才讨论 |

排查顺序：
1. 先查 Codex++ `config.toml` 是否 `model_provider = "cm"`。
2. 再查 `cm.base_url` 是否为 `http://127.0.0.1:48760/v1`。
3. 再查 Codex++ `auth.json` 是否存在、`auth_mode = "apikey"`，且 `OPENAI_API_KEY` 是否与 `config.toml` 的 `cm.api_key` 一致（只输出布尔结果和长度，不输出值）。
4. 再查 `48760` 是否监听。
5. 不要把 `48761` 写进 `base_url`。

## 8. 自检脚本验收

命令：

```powershell
& 'C:\Program Files\PowerShell\7\pwsh.exe' -NoProfile -File "C:\Users\Administrator\.codex-plusplus-config\Test-CodexIsolation.ps1"
```

合格输出顶部必须包含：

```text
OVERALL: PASS - Codex and Codex++ are isolated as expected.
```

关键 PASS 项：
- `normal auth`: exists
- `normal config`: exists
- `normal hooks`: exists
- `normal skills`: skill links exist
- `normal electron .codex`: points to `C:\Users\Administrator\.codex`
- `plus auth`: exists, OPENAI_API_KEY matches config.toml api_key (CodexManager platform key)
- `plus config`: exists, model_provider = "cm"
- `plus hooks`: exists
- `plus skills`: isolation-profile local set; no parent-mirror count assertion
- `plus electron .codex`: points to `D:\CodexPlusPlusProfile\AppData\Roaming\Codex\.codex`

安全要求：
- 自检脚本不得打印 `auth.json` 正文。
- 自检脚本不得打印 `config.toml` 正文。
- 自检脚本不得打印 token、`api_key`、Bearer 字符串。
- 可以打印路径、存在性、文件大小、短 hash 和链接数量。
- 可以校验 auth.json.OPENAI_API_KEY 与 config.toml.api_key 的一致性（只显示"一致/不一致"）。

## 9. 过期文件与入口

`C:\Users\Administrator\.codex-plusplus-config` 下当前保留：
- `Start-Codex.ps1`
- `Start-CodexPlusPlus.ps1`
- `Start-CodexPlusPlus-Proxy.cmd`
- `Test-CodexIsolation.ps1`

可疑或历史项：
- `Start-CodexPlusPlus-Direct.cmd`：可选重复入口，不是桌面主入口。
- `Codex隔离验证报告.md`：历史报告，可能引用旧版本路径。

桌面旧快捷方式若硬编码旧 WindowsApps 版本，应删除或改名为“过期勿用”。

## 10. SSOT 密钥管理架构

### 密钥存储位置

Codex++ 的 API 密钥现在收敛为单一事实来源(SSOT),不再依赖环境变量:

| 存储位置 | 路径/名称 | 角色 | 说明 |
|:---|:---|:---|:---|
| `config.toml` | `[model_providers.cm] api_key` | **SSOT（唯一事实来源）** | Codex CLI 直接读取 |
| `auth.json` | `OPENAI_API_KEY` | 镜像 | 与 config.toml api_key 保持一致，作为兜底 |

### 密钥读取优先级（Codex CLI 0.144 实测）

Codex CLI 按以下顺序读取 API 密钥：
1. 环境变量（由 `env_key` 指定，如 `CM_API_KEY`）—— **已禁用，config.toml 不含 env_key**
2. `auth.json` 的 `OPENAI_API_KEY`
3. `config.toml` 的 `[model_providers.cm] api_key`

**关键坑点**：只要 config.toml 里写了 `env_key = "XXX"`，Codex CLI 0.144 就会强制要求环境变量 `XXX` 存在，找不到就直接报 `Missing environment variable`，**不会 fallback** 到 api_key 或 auth.json。所以 SSOT=config.toml api_key 的前提是：**config.toml 里不能有 env_key 字段**。

### 密钥一致性要求

- `config.toml.api_key` 与 `auth.json.OPENAI_API_KEY` 必须完全相同（都是 CodexManager 平台密钥）。
- 密钥轮换时，同步更新这两处即可。
- 更新后必须重启 Codex++ 进程（`ChatGPT.exe`）才能生效。

### 密钥轮换操作顺序

1. 获取新的 CodexManager 平台密钥。
2. 更新 `config.toml` 的 `[model_providers.cm] api_key` 字段。
3. 更新 `auth.json` 的 `OPENAI_API_KEY`：
   ```powershell
   $auth = 'D:\CodexPlusPlusProfile\AppData\Roaming\Codex\.codex\auth.json'
   @{ OPENAI_API_KEY = '新密钥'; auth_mode = 'apikey' } | ConvertTo-Json | Set-Content $auth -Encoding UTF8
   ```
4. 重启 Codex++（杀进程或关窗口，然后重新通过桌面快捷方式启动）。

### 环境变量清理（2026-07-10 已完成）

历史上 key 曾同时存在三处：环境变量 `CM_API_KEY`（User/Machine）、auth.json、config.toml。其中环境变量优先级最高，会压过另外两处，导致轮换时遗漏环境变量就出 403。

2026-07-10 已删除环境变量 `CM_API_KEY`（User 和 Machine 级别），理由：
- Codex++ config.toml 的 `env_key` 字段已移除，Codex CLI 不再读环境变量。
- 普通 Codex 走 OAuth token（auth.json 里的 tokens），根本不读 `CM_API_KEY`。
- 全盘 grep 确认：活跃配置文件均不引用 `CM_API_KEY`，命中只在历史 session 日志和 .bak 备份。

**残留风险**：cc-switch 未来切换 provider 时，理论上有可能把 `env_key = "CM_API_KEY"` 写回 config.toml。2026-07-10 重启验证未发现写回，但需长期观察。若将来再出 403 且报错含 "Missing environment variable"，优先检查 config.toml 是否被写回了 env_key。

### 当前密钥状态（2026-07-10 验证）

- User `CM_API_KEY`: **已删除**
- Machine `CM_API_KEY`: **已删除**
- `config.toml.api_key`: present=true, length=64（SSOT；不记录值或局部指纹）
- `auth.json.OPENAI_API_KEY`: present=true, length=64, matches_config=true（镜像；不记录值或局部指纹）

## 11. 网络拓扑

### 普通 Codex 启动链路

```
codex.exe (CLI)
  ↓ 读取环境变量 CM_API_KEY
  ↓ 请求 http://127.0.0.1:15723/v1 (cc-switch)
  ↓
cc-switch (端口 15723)
  ↓ 转发到配置的 provider
  ↓
CodexManager (端口 48760)
  ↓
OpenAI API
```

### Codex++ 启动链路

```
桌面快捷方式 (Codex++ 代理隔离启动.lnk)
  ↓
Start-CodexPlusPlus-Proxy.cmd
  ↓
Start-CodexPlusPlus.ps1 (完整版，包含 tweaks 注入)
  ↓ 设置环境变量和隔离 profile
  ↓
ChatGPT.exe --user-data-dir=D:\CodexPlusPlusProfile
  ↓ 读取 config.toml 的 api_key (或 auth.json)
  ↓ 请求 http://127.0.0.1:48760/v1 (CodexManager)
  ↓
CodexManager (端口 48760)
  ↓
OpenAI API
```

### 端口分配

| 端口 | 服务 | 用途 | 启动方式 |
|:---|:---|:---|:---|
| 48760 | CodexManager | Codex++ API 入口 | 开机自启（计划任务） |
| 48761 | CodexManager Web | 管理界面（默认不启用） | 手动启动 |
| 15723 | cc-switch | 普通 Codex 代理 | 开机自启（启动文件夹） |

## 12. 启动脚本架构

### 脚本位置

```
C:\Users\Administrator\.codex-plusplus-config\
```

### 关键文件

| 文件名 | 作用 | 状态 |
|:---|:---|:---|
| `Start-CodexPlusPlus.ps1` | 完整版启动器（包含 tweaks 注入、governance 检查、session path 测试） | ✓ 主启动脚本 |
| `Start-CodexPlusPlus-Proxy.cmd` | 桌面快捷方式入口（调用 Start-CodexPlusPlus.ps1） | ✓ 活跃 |
| `Start-CodexPlusPlus-Minimal.ps1` | 精简版启动器（跳过 tweaks 注入） | ✗ 已删除（历史残骸） |
| `Test-CodexPlusPlusSessionPaths.ps1` | Session 路径与 one-shot maintenance 行为测试 | ✓ 活跃 |
| `Watch-CodexPlusPlusSessionPaths.ps1` | 兼容文件名；只执行一次 session maintenance，`-Watch` 已退役 | ✓ one-shot |

### 启动流程

1. 用户点击桌面快捷方式 `Codex++ 启动.lnk`。
2. 快捷方式调用 `Start-CodexPlusPlus-Proxy.cmd`。
3. `.cmd` 调用 `Start-CodexPlusPlus.ps1`（完整版）。
4. `Start-CodexPlusPlus.ps1` 执行：
   - 设置隔离环境变量（`CODEX_HOME`、`USERPROFILE` 等）。
   - 清理旧的 Codex++ 进程（`ChatGPT.exe`）。
   - 解析最新的 Appx 包路径（优先 `ChatGPT.exe`，兼容旧版 `Codex.exe`）。
   - 注入 tweaks（`follow-up`、`auto-save` 等增强插件）。
   - 只读检查 tweak link；禁止从历史 source 复制恢复。
   - 健康 store 只运行轻量 injection/Manifest 校验；仅缺失、漂移或显式强制时进入完整 repair。
   - 默认跳过全量 session maintenance；需要时显式传入 -RunSessionMaintenance 执行一次维护与测试；不启动后台 watcher。
   - 启动 `ChatGPT.exe`（带 `--user-data-dir` 参数）。
   - 修复 NativeMessagingHost 注册表（15秒延迟）。
5. Codex++ 主进程启动，tweaks 子进程自动拉起。

## 13. 更新事故排查顺序

当 Codex++ 更新后打不开、一闪而过、401、405、502、Cloudflare、请求没进 CodexManager 时，按顺序查：

1. 当前进程命令行是否包含：
   ```text
   --user-data-dir=D:\CodexPlusPlusProfile
   ```
2. `CODEX_HOME` 是否为：
   ```text
   D:\CodexPlusPlusProfile\AppData\Roaming\Codex\.codex
   ```
3. Codex++ `config.toml` 是否 `model_provider = "cm"`。
4. `cm.base_url` 是否为 `http://127.0.0.1:48760/v1`。
5. Codex++ `auth.json` 是否存在，且 `OPENAI_API_KEY` 与 `config.toml` 的 `api_key` 是否一致。
6. `127.0.0.1:48760` 是否监听。
7. Codex++ 专用 `store-apps\OpenAI.Codex_*` 是否是当前版本完整包，且包含 `ChatGPT.exe`（26.707+）、`icudtl.dat`、`resources.pak`、`v8_context_snapshot.bin`。
8. `codex-plusplus-codex.cmd` 或桌面快捷方式是否仍写死旧版 `OpenAI.Codex_*`。
9. config.toml 是否被写回了 `env_key` 字段（2026-07-10 已移除 env_key 并删除环境变量；若报错含 "Missing environment variable"，说明 env_key 被某进程写回了，需再次移除）。

只有用户明确要求系统 HTTP/SOCKS 代理时，才讨论 `7890`、`HTTP_PROXY`、`ALL_PROXY`。

## 14. 已知问题与修复记录

### 2026-08-27 固化：one-shot session maintenance SQLite 固定边界

本机没有可由 PATH 解析的 `sqlite3.exe`，one-shot session maintenance 与生命周期测试若依赖裸 `sqlite3`，会在启动/修复/更新后的新环境直接失效。正式链固定使用 `D:\CodexPlusPlusProfile\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe` 与 `C:\Users\Administrator\.codex-plusplus-config\Invoke-CodexPlusPlusSqlite.py`。

helper 只允许打开 canonical `D:\CodexPlusPlusProfile\AppData\Roaming\Codex\.codex\state_5.sqlite`；C 盘 Profile、其他 Profile 文件和任意临时数据库都在打开前拒绝。`Test-CodexPlusPlusSqliteBoundary.ps1` 固定验证 D 盘物理链、helper 自检、trigger/多 SELECT/ROLLBACK、普通 Codex 拒绝、禁止 consumer 回退到 PATH `sqlite3`。依赖被更新移除或行为不兼容时，one-shot maintenance 与手动 governance audit 必须 fail-closed；不得以此复活后台 watcher。

### 2026-08-27 固化：无状态 Host Capability Projection

Host 统一 Skill 发布的正式链路是：

```text
C:\Users\Administrator\.agent\control\host-capability-publication-manifest.yaml
  -> C:\Users\Administrator\.agent\assets\skills
  -> Host canonical Junction
  -> Host 原生 catalog
  -> 任务按需选中 Skill 正文
```

General OS Publication Policy 与 Manifest 由同一 SSOT 承担；S34 只是生命周期 caller，不复制其 schema、资格判断或 Junction 算法。正式调用图固定如下：

- `lifecycle_ingress_count=3`：`Start-CodexPlusPlus.ps1`、一次性更新入口 `Sync-CodexPlusPlusLatest.ps1`、基础 repair 入口 `Repair-CodexPlusPlusCurrentApp.ps1`。
- `direct_projection_caller_count=2`：Start 与 Sync；Repair 只薄代理到 Sync。
- `projection_writer_count=1`：`C:\Users\Administrator\.agent\tooling\Sync-HostCapabilityProjection.ps1`，实现归 General OS，Host 目录不保留副本。Protect 从活动文件探测这三个计数，不以常量自证。
- writer 无状态、幂等，不写 receipt/journal/generation/state，不调用 `skills/extraRoots`；只按 Manifest 与 canonical root 对当前 Host 做投影，并保留 Manifest 外条目。
- 普通目录、文件或未知目标 Junction 的 collision 只阻止该冲突项被覆盖并产生明确报告；它不是 Host 全局资格门，不阻断其他无冲突条目，也不阻断基础启动或 repair。
- 禁止恢复 Host Replay/adapter tweak、activation/cutover/rollback、Adapter 专用 ASAR baseline、后台 worker/loop/watchdog、receipt/journal/generation/state 或 transaction fixture。
- 正式 PowerShell 唯一物理路径为 `C:\Program Files\PowerShell\7\pwsh.exe`；生命周期 caller 与 writer 均不得依赖 PATH、别名或旧 Host。

当前 Manifest 选中的 canonical Junction 就是正式投影，不得删除、迁入回退包或复制为第二份 Skill 正文。基础 repair、Native Messaging compare-and-set 与 session SQLite 固定 Python/helper 边界继续独立生效，但不得成为 Host Publication 的全局门。

隔离 store 只保留当前官方包镜像。`Sync-CodexPlusPlusLatest.ps1` 是原生 repair、旧镜像清理与快捷方式收敛的唯一一次性 owner：旧 `OpenAI.Codex_*` 必须同时是固定 store 的直接物理子目录、不是当前包、且无进程使用，才允许删除。Start 只在当前 store 缺失、注入漂移或显式 `-ForceRepair` 时调用该 owner，健康重启不做完整 `/MIR`；`Repair-CodexPlusPlusCurrentApp.ps1` 始终薄代理到该 owner。唯一用户入口固定为 `C:\Users\Administrator\Desktop\Codex++ 启动.lnk` → `Start-CodexPlusPlus-Proxy.cmd`；installer 创建的 `Codex++.lnk` 只在目标确认位于固定 store 时移除。`Protect-CodexPlusPlusGovernance.ps1` 只做手动、只读、无状态审计，不参与日常 Host 启动。

installer 自身的源码更新与应用包 repair 是两个责任边界。`Update-CodexPlusPlusInstaller.ps1` 是前者唯一的外部 one-shot owner；native `autoUpdate=false`，所有 `codex-plusplus-watcher*` 任务与 `watcher.cmd/vbs` 均必须 absent。native self-update 整目录替换 source 后，受控入口在同一互斥事务中重施 PS7 overlay、build、定向测试，再调用后者的 Sync owner 强制 repair，并在提交后删除临时 `source.previous`。public CLI 的 `update/self-update/repair` 只允许受控路由；`install` 默认会创建 watcher，故 public 入口固定拒绝。首次/重装时只允许固定 Node/native CLI `install --no-watcher`，并立即执行 Sync 与手动 audit。

`D:\.codex-plusplus` 是 installer source 的唯一 canonical identity；`C:\Users\Administrator\.codex-plusplus` 已退役。`Test-CodexPlusPlusTweakLinks.ps1` 只读校验 D runtime 的物理 tweak 与 manifest；已退役的 `Repair-CodexPlusPlusTweakLinks.ps1` 不得恢复，任何 `source.previous*` / `source.failed*` → active source 的启动时复制都属于第二 rollback writer。

installer/update watcher 与 session maintenance 是两个不同对象：前者继续保持任务/launcher 为零；后者只在启动或显式命令执行一次。正式后台 session watcher 期望数为 `0`，不得以 `PS7 watcher=1` 作为成功指标。

安装、修复、更新或 Host 启动链完成前，S14 只能对明确列出的文件、命令、运行版本和未观测项签发 `PASS_WITHIN_DECLARED_SCOPE`。它只证明声明范围内没有已知未登记债务，不证明未来 Store/Codex++ 版本、未执行的真实重启或其他 Host 全局没有隐藏债务。

`.codex-evidence/**/*.json` 是 Hook 当次失败复核可消费的 executable receipt，不是 General 或 Host 的正式长期 Evidence；对应 pending 被成功重跑或 S12/W9 receipt 清除后无需恢复。跨轮保留的结论必须归真实 owner 的 Evidence 路径；General 的正式证据放在 `C:\Users\Administrator\.agent\records\evidence`，对只读历史证据采用追加 correction，而非原地改写。

### 2026-07-10 修复：Codex 更新后主进程改名

**问题**：Codex 26.707.3748.0+ 版本将主进程从 `Codex.exe` 改名为 `ChatGPT.exe`，导致启动脚本找不到可执行文件。

**修复**：
- 更新 `Start-CodexPlusPlus.ps1` 的 `Resolve-CodexExe` 函数，优先尝试 `ChatGPT.exe`，失败时回退到 `Codex.exe`。
- 更新 `Start-CodexPlusPlus-Minimal.ps1` 的进程清理逻辑，匹配 `ChatGPT.exe`。
- 更新本基线文档第 13 节第 7 条，反映新的可执行文件名。

### 2026-07-10 修复：密钥 SSOT 不一致导致 403

**问题**：环境变量 `CM_API_KEY`（User/Machine 级别）与 `auth.json`、`config.toml` 的密钥不一致，Codex CLI 优先读取环境变量中的旧密钥，导致 403 Forbidden。

**修复**：
- 统一更新所有位置的密钥为 CodexManager 平台密钥 `bddb027d...31d6`。
- 更新本基线文档，新增第 10 节"SSOT 密钥管理架构"，明确密钥存储位置和一致性要求。

### 2026-07-10 修复：完整版启动器 session path 测试失败

**问题**：`Start-CodexPlusPlus.ps1` 在启动前运行 `Test-CodexPlusPlusSessionPaths.ps1`，断言 `active_session_risks.jsonl` 必须存在，但该文件只在 watcher 发现风险时才生成。

**历史修复与 2026-09-22 更正**：
- `-SkipSessionPathTest` 只保留为显式诊断开关；它不是正常启动的长期绕过。
- `Start-CodexPlusPlus.ps1` 默认跳过全量 session maintenance，显式 `-RunSessionMaintenance` 才执行一次性维护和测试；不启动后台 watcher。
- one-shot 入口在测试前预热 `active_session_risks.jsonl`，所以“没有风险记录文件”不再被误判为本次 tweak/运行时改动通过；活动未归档会话仍只记录风险，不删除历史。
- `Test-CodexPlusPlusSessionPaths.ps1` 已覆盖该边界，必须以其最新一次通过结果为准。

### 2026-09-22 固化：普通 Codex 与 Codex++ 共存的 NTFS 非分页池防爆边界

**根因**：Codex++ 的 Electron 主进程曾通过 C 盘重解析入口访问 D 盘数据。普通 Codex 同时运行时，带 MSIX 身份的 Electron/NTFS 路径产生高频文件操作，表现为 `OtherOps` 飙升和 `ntfs.sys`/`NtFC` 非分页池持续上涨。安全模式关闭所有 tweak 仍复现；因此不能把责任归给某个 tweak，也不能删除 tweak。

**固定方案**：
- C Profile alias 已退役；Electron 主进程和所有子进程固定使用物理 `--user-data-dir=D:\CodexPlusPlusProfile`。
- `CODEX_HOME`、session、connector、marketplace、visualization 和 Git 辅助写入固定使用 D canonical；普通 Codex 的 C 盘配置和进程不改。
- `session-path-normalizer` 继续启用，采用绑定 stop、可重复启动、节流扫描；它负责原有路径规范化，不承担内核泄漏的“监控器”职责。
- 禁止新增常驻 Watch、定时重启、第二状态库或第二控制面；session 风险处理只走启动/显式调用的一次性维护。

**共存验收**：普通 Codex 保持运行时，Codex++ 冷启动、空闲和真实任务都必须观察主进程命令行的物理 D 参数，并记录非分页池与 OtherOps 的前后增量。重启只用于回收已经积累的内核池，不是根因修复本身。

动态采样、命令回执和未覆盖的 PoolMon 限制见 `C:\Users\Administrator\.agent\records\evidence\CODEXPP-NTFS-COEXISTENCE-S12-20260922.md`；本基线只保留可复用的不变量。

### 2026-07-10 清理：删除历史残骸

**问题**：`Start-CodexPlusPlus-Minimal.ps1` 是精简版启动器，不包含 tweaks 注入，导致 Codex++ 缺少 `follow-up` 等增强插件。

**修复**：
- 删除 `Start-CodexPlusPlus-Minimal.ps1`。
- 更新 `Start-CodexPlusPlus-Proxy.cmd`，直接调用完整版 `Start-CodexPlusPlus.ps1`。

### 2026-07-10 收敛：删除冗余环境变量 CM_API_KEY（SSOT 终态）

**问题**：key 曾同时存在三处（环境变量 `CM_API_KEY`、auth.json、config.toml api_key），环境变量优先级最高，轮换时极易遗漏导致 403。违反 SSOT 原则。

**修复**：
- 删除环境变量 `CM_API_KEY`（User 和 Machine 级别）。
- SSOT 收敛为 `config.toml.api_key`，`auth.json.OPENAI_API_KEY` 作镜像兜底。
- 全盘 grep 确认无活跃配置文件引用 `CM_API_KEY`。
- 重启 Codex++ 验证：主进程正常启动，config.toml env_key 未被写回，tweaks 进程正常。

**残留观察点**：cc-switch 未来切 provider 理论上可能写回 env_key，需长期观察。
