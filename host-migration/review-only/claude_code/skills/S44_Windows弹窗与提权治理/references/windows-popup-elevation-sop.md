---
domain: windows-popup-elevation-governance
tier: L4
doc_status: active-reference
status: experimental
related:
  - @@GENERAL_ROOT:win@@\assets\skills\S44_Windows弹窗与提权治理\SKILL.md
  - @@GENERAL_ROOT:win@@\assets\references\methodology\25_Windows-Service-Port-Governance-SOP.md
  - @@OPENCLAW_ROOT:win@@\.agents\skills\S42_OpenClaw网关Session清理与重启\SKILL.md
birth_ceremony_id: bc-7885711f6cc9
birth_ceremony_date: 2026-07-20

---

# Windows 弹窗与提权治理 SOP

## 1. 先分类

| 类别 | 物理证据 | 处理方式 |
|:---|:---|:---|
| 意外控制台闪窗 | 计划任务或父进程直接启动 `pwsh.exe`、`powershell.exe`、`cmd.exe`、BAT | 将首进程改为 GUI 子系统启动器，保持原参数、身份和触发器 |
| 正常交互终端 | 用户主动打开终端，窗口需要输入或展示输出 | 保持可见，不做隐藏 |
| 正常 UAC | Secure Desktop 出现管理员确认 | 保留提示；确认后可隐藏实际执行窗口 |
| Codex 策略阻断 | 错误为 `blocked by policy`，目标进程没有创建 | 检查隔离实例的 `approval_policy`、sandbox 和 rules；不要伪装成 Windows 拒绝 |
| Windows 权限拒绝 | cmdlet/COM/API 已执行，返回 `Access is denied`、`拒绝访问` 或 ACL 错误 | 检查令牌完整性、Administrators deny-only、目标 ACL、任务/服务权限 |
| 固定动作提权代理 | 已注册 `Highest` 计划任务或服务，普通进程只提交有限请求 | 校验动作白名单、请求文件 ACL、回执、超时、probe 和回滚 |

## 2. 十分钟定位顺序

1. 记录窗口出现的分钟和频率。
2. 查同频计划任务、登录启动项、服务恢复动作和常驻 watchdog。
3. 查 Action 的第一个可执行文件，不只看脚本参数。
4. 对照进程命令行、父 PID、运行身份和会话类型。
5. 读取对应事件日志。PowerShell 事件 400/403/600 只能证明宿主生命周期，不能单独证明 Explorer 是父进程。
6. 改造后覆盖至少两个触发周期，并复核原业务回执。

只读探针：

```powershell
& "@@GENERAL_ROOT:win@@\assets\skills\S44_Windows弹窗与提权治理\scripts\Get-WindowsPopupElevationEvidence.ps1"
```

## 3. 无闪窗改造

错误理解：

- `pwsh.exe -WindowStyle Hidden`：控制台进程可能先创建窗口，再执行隐藏参数。
- 计划任务 `Hidden=true`：隐藏的是任务元数据/运行表现，不保证控制台窗口从未创建。
- 把任务改为 SYSTEM：可能破坏浏览器登录态、桌面、剪贴板和用户配置。

推荐结构：

```text
Task Scheduler
  -> wscript.exe launcher.vbs
       -> pwsh.exe -NoProfile -NonInteractive -WindowStyle Hidden -File worker.ps1
```

VBScript 必须使用绝对路径、正确引用参数并返回启动错误。需要长期复用时，优先使用带日志和固定参数的 GUI 启动器，避免通用“任意命令隐藏器”。

## 4. UAC 与自动提权

### 4.1 一次性管理操作

使用 Windows 原生 UAC：Explorer 的“以管理员身份运行”、带 `requireAdministrator` 清单的安装器，或交互式 `Start-Process -Verb RunAs`。UAC 由用户确认；提权后的执行窗口可以隐藏，结果写入回执文件。

UAC 启动后 stdout/stderr 通常不会回到原终端。安装器应写结构化回执，调用方只轮询回执，不等待不可见输出。

### 4.2 无人值守固定动作

适合计划任务/服务代理的条件：

- 动作固定，例如 `restart`、`probe`；不接受任意 PowerShell 文本。
- 代理在一次 UAC 安装后以 `Highest` 或服务身份运行。
- 请求文件只包含版本、动作、请求 ID 和有限参数。
- 代理校验路径、动作和超时，写完成回执并清理请求。
- `probe` 只检查管理员身份和目标资源访问，不重启、不删除、不改配置。

不合格的做法：关闭 UAC、把任意命令塞进最高权限任务、让所有 `RunAs` 免审批、给目录授予宽泛写权限。

## 5. Codex++ 执行策略分诊

Codex++ 隔离配置只检查：

`@@USERPROFILE:win@@\AppData\Roaming\CodexPlusPlusProfile\.codex`

不要修改普通 Codex 的 `@@CODEX_HOME:win@@`。

判定顺序：

1. 目标进程是否创建。
2. 错误是否为执行层的 `blocked by policy`。
3. 当前 `approval_policy` 是否允许请求批准；`never` 不会弹 Codex 审批。
4. 当前 Windows 令牌是否为管理员、高完整性。
5. Windows API 是否返回权限错误。

结论规则：调用 COM 不等于绕过策略或自动提权。只读 COM 查询成功，只能证明接口可达；管理操作仍受任务 ACL 和当前令牌约束。

## 6. 2026-07-20 案例

### TopHub 每分钟 pwsh 黑框

表象：`@@POWERSHELL_EXE:win@@` 黑框按分钟闪现。

根因：五个 `\TopHub\DataSource\` 计划任务分别在每小时 `:00/:10/:20/:30/:45` 直接启动 PowerShell。Explorer/Store shell extension 的初始假设没有父进程或任务证据支持。

修复：任务首进程改为：

`@@SYSTEMROOT:win@@\System32\wscript.exe`

启动器：

`@@OPENCLAW_ROOT:win@@\projects\tophub-daily-trend-radar\ops\data-source-lobster-windowless-launcher.vbs`

验收：五个任务的触发器、参数和业务契约不变；测试 `7 passed`；连续观察无闪窗。

### S42 自动提权桥

错误假设：`schtasks.exe` 被运行时行为检测或 AppContainer capability 拦截，换 COM 即可绕过。

物理证据：

- `Start-Process -Verb RunAs` 在 Codex 执行通道返回 `blocked by policy`，目标进程未创建。
- `Register-ScheduledTask` 到达 Windows 后返回 `拒绝访问`。
- 当前令牌为 Medium，Administrators 为 deny-only。
- `Schedule.Service` 只读查询成功，不代表管理操作已提权。

正确结构：一次 UAC 安装 `Highest` 固定任务；日常只提交 `restart` 或无副作用 `probe`；任务写回管理员身份、服务访问和执行结果。

### Codex++ 桌面重定向

Codex++ 当前 Desktop 由注册表重定向到：

`@@USERPROFILE:win@@\AppData\Roaming\CodexPlusPlusProfile\Desktop`

创建人工入口前先读取 `HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders\Desktop`，再展开环境变量。硬编码 `@@USERPROFILE:win@@\Desktop` 会把入口放到普通 Codex/普通用户桌面，造成“点了但不是同一文件”的假象。

## 7. 验收清单

- [ ] 记录触发频率、父进程、命令行、TaskPath/TaskName。
- [ ] 原业务身份、Session、触发器和参数未改变。
- [ ] 连续两个周期没有意外窗口。
- [ ] UAC 注册表值未降低。
- [ ] `blocked by policy` 与 `拒绝访问` 分开记录。
- [ ] 固定代理的 `probe` 成功且无业务副作用。
- [ ] 回滚路径和安装前备份可用。
