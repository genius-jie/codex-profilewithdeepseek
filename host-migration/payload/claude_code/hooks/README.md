# Claude Code 用户级 Hook 层

本目录是 Claude Code 用户级 Hook 的机器执行层。Codex++ 保持自己的隔离脚本与配置；本目录不构成跨宿主共享 Runtime。

> 注册位置（2026-09-20 单一归属迁移）: 用户级 Hook 只注册在 **Claude Code managed settings**：`@@CLAUDE_MANAGED:win@@\managed-settings.json`（官方最高优先级层，用户/项目层无法覆盖或删除，`/hooks` 面板中显示为只读）。`~/.claude/settings.json` 由 CC Switch 全权掌管——其 proxy-apply/takeover 写盘路径整文件重写且不合并 common-config snippet，已两次静默抹掉 hooks（06-20→09-11 窗口、09-20 10:10:47），因此该层**禁止**出现 `hooks` 键；`~/.claude/settings.local.json` 不是官方文档化的设置层，同样禁止承载 `hooks`。cc-switch db 的 `common_config_claude` 已摘除 hooks，防止未来版本回写造成双层合并**重复执行**。项目级 `.claude/settings.local.json` 只放项目专属 Hook。

## 调用链

```
Claude Code 触发事件
        │
        ├─ SessionStart
        │      ├─ python hook_runner.py --event SessionStart --script session_start_capability_projection.py
        │      │      └─ 调用 General 唯一 writer；发生变更时请求 reloadSkills
        │      └─ python hook_runner.py --event SessionStart --script session_start_context.py
        │             └─ 临时输出 HOST_SCOPE_FACT（机械范围事实，不选择 OS、不注入正文）
        │
        ├─ UserPromptSubmit
        │      └─ 当前无用户级 Context Hook
        │
        ├─ PreToolUse (Bash|PowerShell|Edit|Write)
        │      └─ python hook_runner.py --event PreToolUse --script pre_tool_use_guard.py
        │             └─ pre_tool_use_guard.py  → exit 2 阻断 / exit 0 放行
        │
        ├─ PreToolUse (Read)          ← 唯一不走 hook_runner 的特例
        │      └─ powershell read-tool-parameter-guard.ps1
        │             └─ 删除非 PDF 的 pages 非法参数 / 校验 PDF pages 格式
        │
        ├─ PostToolUse (Bash|Edit|Write|MultiEdit|apply_patch)
        │      └─ python hook_runner.py --event PostToolUse --script post_tool_use_audit.py
        │             └─ post_tool_use_audit.py  → 只观察记录,不阻断
        │
        └─ Stop
               └─ python stop_guard_template.py  (项目级路径,直接调不走 runner)
                      └─ loop engineering 完成回执校验
```

## 脚本职责

| 脚本 | 事件 | 作用 | 能否阻断 | 走 runner |
|:---|:---|:---|:---|:---|
| `hook_runner.py` | — | 通用分发器:读 stdin JSON → 起子进程跑 guard → 转发 stdout/stderr + 写事件日志 | 否(框架) | — |
| `session_start_capability_projection.py` | SessionStart | 调用 General 唯一 writer 维护 Manifest-selected Junction；有变更时请求 Claude 原生重扫 Skill；不处理 Manifest 外目录 | 否(报告错误后继续启动) | 是 |
| `session_start_context.py` | SessionStart | 输出临时 `HOST_SCOPE_FACT`：Host、可信 cwd、项目候选、L0 源摘要和 General OS 入口；并机械携带 `GOVERNANCE_ENTRY_OBLIGATION` 入口回执义务提醒（advisory，不选 OS、不注入正文）。同一义务文本在 `.codex` 与 Codex++ Profile 三份独立副本中必须保持逐字一致 | 否(只注入事实) | 是 |
| `claude_context_common.py` | — | 可信 cwd、canonical containment 与机械文件事实 helper；不选择 OS、不加载正文 | 否 | 由 runner/SessionStart 使用 |
| `pre_tool_use_guard.py` | PreToolUse | 破坏性 git 阻断；依赖流程与进程管理提示（advisory，不阻断）；治理 Markdown 改动提示；W11 旧耦合已从 Claude 副本移除 | 仅破坏性 git 为阻断（exit 2） | 是 |
| `read-tool-parameter-guard.ps1` | PreToolUse (Read) | 删除非 PDF 文件的非法 `pages` 参数;校验 PDF 的 pages 格式 | 是 (permissionDecision=deny) | **否,直接 PS** |
| `post_tool_use_audit.py` | PostToolUse | 记录治理 Markdown 改动、git commit/push、命令失败指纹 | 否(只观察) | 是 |

## W11 旧耦合边界（历史说明）

Claude 这份全局副本已移除对旧 D 盘交付清单校验器的调用；本次变更不宣告项目侧 W11 规则退役。项目范围的完成授权由项目自己的控制入口负责，宿主全局 PreToolUse 不承担这项职责。

- 依赖流程与进程管理命中时只给提示，继续走宿主原生权限与项目流程。
- 依赖流程提示只判断命令是否带 `-r` / `--requirement` 选项；它不宣称检测虚拟环境或全局安装位置。
- governed Markdown（skills/rules/workflows/index/AGENTS.md/CLAUDE.md）改动会提示先走出生仪式（非阻断），先读相应协议。
- 破坏性 git 仅对 Bash 与 PowerShell 命令通道做阻断；Edit/Write 不扫描文件正文。
- 双引擎各自维护独立 hook 配置与脚本副本；Claude 副本的 W11 旧耦合 removal 不自动同步到其他宿主。

## PreToolUse 当前生效配置与验证边界

- 当前 `managed-settings.json` 已注册 PreToolUse（matcher `Bash|PowerShell|Edit|Write`，经 `hook_runner.py` 调 `pre_tool_use_guard.py`）。本段描述的是当前生效配置，不是待发布候选。
- 当前批准的阻断行为：破坏性 git 对 Bash 与 PowerShell 命令通道硬阻断（exit 2 + stderr reason，stdout 保持空）；`pip`/`taskkill`/进程管理与治理 Markdown 改动为 advisory 提示，不阻断；`pip install -r/--requirement` 是依赖清单流程，不宣称检测虚拟环境。
- 验证证据必须走真实 `hook_runner.py` 调用链的放行、阻断和异常协议测试；只调用 guard 文件本身不能替代这条证据。注册与回滚边界不变：发布失败时只撤销对应注册项，保留既有 SessionStart 和其他无关配置；历史缺陷复现材料只能作为测试证据，不能作为生产回滚入口。

> `superpowers` 等第三方插件可以有自己的插件-owned Hook；它们不属于 General Agent OS Context 路由，本目录不复制或改写其正文。是否启用由 Claude 插件配置决定。

> 跨宿主 SessionStart 事件矩阵（2026-09-20 正式记录，差异为宿主语义而非漂移）：Claude managed 层 matcher = `startup|resume|clear|compact|fork`（Claude Code 的 SessionStart source 枚举含 compact/fork）；Codex 原生与 Codex++ 的 `hooks.json` matcher = `startup|resume|clear`（其宿主无对应 source，不强造）。义务文本为“一个语义源（M1/L0/S22）+ 三宿主字节一致投影”，由 fixture 差分守护，不引入共享模块（引擎隔离）。

> `post_tool_use_audit.py` 不做项目范围选择，因此不读取 cwd；所有需要范围判断的自有 Hook（SessionStart、CodeGraph、PreToolUse 写时关）统一通过 `claude_context_common.py` 的可信解析。

`stop_guard_template.py` 不在本目录,位于项目级:
`@@OPENCLAW_ROOT:win@@\.agents\orchestration\templates\loop_engineering\stop_guard_template.py`

## 为什么 Read guard 走 PS 而不走 runner

Read 参数清洗需要**就地改写 tool_input**(updatedInput),PowerShell 的 `ConvertFrom-Json` / `ConvertTo-Json` 处理 `[ordered]` 哈希重组更直观,且 PS 编码控制由脚本头 `[Console]::OutputEncoding = UTF8` 显式保证,避免 Python 子进程在 cmd 管道下的 stdin 首字节丢失风险。

## 日志位置

| 文件 | 写入者 | 内容 |
|:---|:---|:---|
| `logs/hook-events.jsonl` | hook_runner.py | 每次 guard 调用的 started/completed 记录(含 returncode、耗时、stdout 预览) |
| `logs/post-tool-audit.jsonl` | post_tool_use_audit.py | 命中审计条件时(governed md / git / 失败)的审计记录 |

## 阻断约定

- **Python guard (经 runner)**: 子进程 `exit 2` = 阻断,runner 原样转发 returncode。
- **PreToolUse 阻断输出**: 采用 `exit 2 + stderr reason`，stdout 保持为空，避免把非 Claude 决策 schema 的 JSON 送入宿主解析。
- **PowerShell Read guard**: 输出 `{"hookSpecificOutput.permissionDecision":"deny"}` 阻断,`allow` + `updatedInput` 放行并改写参数。
- **Stop guard**: runtime=claude 时 `print(stderr)+exit 2` 阻断;runtime=codex 时输出 `{"decision":"block"}` + `exit 0`。
