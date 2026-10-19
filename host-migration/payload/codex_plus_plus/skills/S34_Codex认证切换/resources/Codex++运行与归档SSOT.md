---
domain: codex-plusplus-profile
tier: L3
status: active
doc_status: active-ssot
last_verified: 2026-09-22
related:
  - @@CODEXPP_HOME:win@@\skills\S34_Codex认证切换\SKILL.md
  - @@CODEXPP_HOME:win@@\skills\S34_Codex认证切换\resources\Codex++隔离配置基线.md
  - @@LAUNCHER_ROOT:win@@\Start-CodexPlusPlus.ps1
  - @@LAUNCHER_ROOT:win@@\排查手册.md
---

# Codex++ 运行与归档 SSOT

这份文件是 Codex++ 后续启动、登录、会话归档和运行故障排查的单一操作契约。它描述已有入口的使用顺序，不新增守护进程、状态库、Watcher 或第二控制面。

## 1. 唯一物理 owner 和登录模式

Codex++ 的可变运行数据只允许落在物理 D 盘：

- CODEX_HOME：`@@CODEXPP_HOME:win@@`
- runtime/tweaks/log：`@@CODEXPP_RUNTIME:win@@`
- Electron user-data-dir：`@@CODEXPP_PROFILE:win@@`
- OpenCLI：`@@CODEXPP_PROFILE:win@@\.opencli\clis`
- 固定 store 镜像：`@@CODEXPP_INSTALL_ROOT:win@@\store-apps`

普通 Codex 的 owner 是 `@@CODEX_HOME:win@@`，只读对照，不能混改。

Codex++ 默认是中转登录模式，必须同时满足：

- `auth.json` 的 `auth_mode=apikey`；
- `config.toml` 的 `model_provider=cm`；
- `model_providers.cm.base_url=http://127.0.0.1:15740/v1`；
- `wire_api=responses`；
- 中转端口可连接。

模型协议适配只有一个主机级服务 `CodexIdSanitizer`，源码位于 `@@SANITIZER_ROOT:win@@\codex-id-sanitizer-proxy.js`，监听 `15740` 并转发到 CodexManager `48760`。Codex++ 从 D Profile 的 `cm.base_url` 消费该服务；普通 Codex 的配置独立，不因源码放在 C 盘就推断它也使用此服务。当前源码目标为 `responses-summary-v28-kimi-reasoning-effort-v1`；是否已加载以服务重载退出码和新鲜 `/health` 为准。

从 Agent 的虚拟桌面发起 UAC 时，先在 `WinSta0\Default` 启动一次性普通权限启动器，再由它 `Start-Process -Verb RunAs` 调用现有 `restart-sanitizer.ps1`，仍由用户在 Windows 确认。用 `-Wait -PassThru` 的 `ExitCode` 和 `/health` 判断结果；等待中不等于已看到弹窗，用户取消不等于服务重载。不要重复堆积提升进程，也不新增服务或计划任务。

官方 OAuth 是显式切换场景。启动、迁移或修复时不得把普通 Codex 的 OAuth 状态复制到 Codex++，也不得因为 UI 出现“登录”字样就改写 `auth.json`。

如果文本、旧文档或某个脚本声称 C 盘是 Codex++ canonical，先核对运行进程的 `--user-data-dir`、`CODEX_HOME` 和当前 D state DB。物理事实冲突时停止扩大写入，交回 Owner 决定是否另立迁移任务。

## 2. 唯一启动入口

日常启动链固定为：

`Codex++.lnk → Start-CodexPlusPlus-Proxy.cmd → Start-CodexPlusPlus.ps1 → Invoke-CodexPlusPlusIdentityLaunch.ps1`

这条链负责：

1. 设置 D-only `USERPROFILE`、`APPDATA`、`CODEX_HOME` 和 `CODEX_PLUSPLUS_HOME`；
2. 保留中转配置和清理继承的代理环境变量；
3. 检查 tweak、loader、Manifest projection 和 package identity；
4. 运行 Windows sandbox 预检；
5. 通过 `chatgpt-pp.exe` 启动固定 store 镜像。

不要用裸 `ChatGPT.exe`、裸 `chatgpt-pp.exe` 或临时 shell 直接启动来验证登录。直启可能继承普通 Codex 环境，界面看起来像官方账号登录，即使 D 盘 `auth.json` 没有被修改。

正式入口常用参数：

```powershell
& '@@POWERSHELL_EXE:win@@' -NoProfile -File '@@LAUNCHER_ROOT:win@@\Start-CodexPlusPlus.ps1' -Restart -SkipConnectorSync -SkipOpenCliAdapterSync -SkipSessionPathTest -SkipRepair
```

受控启动成功必须看到 `Windows sandbox ready`、D `CODEX_HOME` 和 D `--user-data-dir`。启动失败时不要绕过入口长期运行；只可用直启做短暂只读诊断，并随后回到正式入口。

## 3. Windows sandbox 设置

`setup_marker.json` 存在不代表 setup 完成。必须同时存在当前本机密码匹配的：

`@@CODEXPP_HOME:win@@\.sandbox-secrets\sandbox_users.json`

正式修复命令由官方 CLI 执行，并需要一次用户可见的 UAC 提升：

```powershell
codex.exe sandbox setup --elevated --user Administrator --codex-home @@CODEXPP_HOME:win@@
```

成功后用 D 环境 smoke 验证：

```powershell
codex.exe sandbox cmd.exe /d /c exit 0
```

不要直接执行 `codex-windows-sandbox-setup.exe --help`。这个 helper 只接受 Codex CLI 传入的 provisioning payload，独立 `--help` 会报 payload 解码错误；该错误不能作为 sandbox setup 失败的根因。

不要从 Instagram、TikTok 或其他 profile 复制旧的 `sandbox_users.json`。凭据包含 DPAPI 密文，Windows 用户密码轮换后旧文件会失效。不要关闭 elevated sandbox，也不要添加后台重试器。

## 4. 历史会话归档

会话恢复和归档的唯一事实是：

`@@CODEXPP_HOME:win@@\state_5.sqlite` 的 `threads.rollout_path`。

当前 D-only 布局下，归档的 native app-server 也必须绑定同一个
`CODEX_HOME=@@CODEXPP_HOME:win@@` 和当前固定
store 的 `app\resources\codex.exe`。旧 C→D profile、旧 `@@PROFILE_REPO:win@@`
根、普通 Codex host，都会造成“找不到 Codex thread”或归档调用没有真正到达当前
app-server。专用归档 Skill 的 `scripts\archive_codexplusplus_threads.py` 是当前
精确归档 fallback；它先 exact-read、拒绝 `active/running`、发送 native
`thread/archive`，再核对 archived rollout path 和 state-only archived list。

归档优先规则：

1. 先把 rollout 移入 `archived_sessions`；
2. 更新 `archived=1` 和归档时间；
3. 同步 `thread_history_1.sqlite`、session index 和相关投影；
4. 原始 rollout 缺失时，只生成明确标注的 renderer-safe stub 或缺失归档投影；
5. 只有用户明确授权删除时，才执行历史 purge。

当前 UI 有两个列表消费者，必须一起核对：

- Electron global state：pending assignments、project assignments、prompt history、queue revision、memory stage1；
- `@@CODEXPP_HOME:win@@\sqlite\codex-dev.db` 的 `local_thread_catalog`。

`local_thread_catalog` 中不在 canonical state DB 的 local 条目只能标记 `missing_candidate=1`，不能把缺失内容伪装成完整历史，也不能删除项目对象。保留集合必须动态读取当前 state DB，不能硬编码旧 thread ID。

## 5. Windows UI / Computer Use 报错分流

“Windows 设置未完成 / 设置已停止”优先按 Codex 核心 sandbox setup 分流：

- 检查 `.sandbox` marker 和 `.sandbox-secrets\sandbox_users.json`；
- 运行官方 elevated setup；
- 重新走 `Start-CodexPlusPlus.ps1`，确认 `Windows sandbox ready`。

`co.bennett.windows-computer-use` 的 `windows_computer_use_setup_check` 是另一条 WCU 桥接诊断：它检查 UIA、截图、输入和 overlay。它返回 `ready` 只能证明桥接依赖可用，不能替代核心 sandbox provisioning；`process-elevated=false` 只是控制管理员目标窗口时的 caveat。

WCU 的 `start_computer_use` 是 warmup 事件，不是 sandbox 安装器。桥接状态 ready 后仍应回到核心 sandbox/正式启动链验收。

## 6. NTFS 非分页池与共存不变量

已确认的事故链是 Codex++ 的历史 C/重解析路径和高频 GB 级 SQLite/日志 I/O 放大 Windows NTFS 文件操作，最终推高 `ntfs.sys` 的非分页池。Codex++ 进程工作集不是唯一泄漏位置。

修复保留全部 tweak、插件和普通 Codex 共存意图，只收敛物理 I/O owner：

- Electron、session、SQLite、logs、OpenCLI 和 MCP writer 全部使用物理 D；
- 普通 Codex 继续使用自己的 C owner；
- 不删除 tweak；
- 不以定时重启、常驻 Watch、第二状态库或新 Guard 代替根因修复；
- 重启只回收已经积累的内核池，不是长期修复。

## 7. 最小验收集

完成修复或启动前，按实际范围运行已有检查：

```powershell
& '@@POWERSHELL_EXE:win@@' -NoProfile -File '@@LAUNCHER_ROOT:win@@\Test-CodexPlusPlusSessionPaths.ps1'
& '@@LAUNCHER_ROOT:win@@\Test-CodexPlusPlusWindowRuntime.ps1' -AllowNoWindow
& '@@LAUNCHER_ROOT:win@@\Test-CodexPlusPlusInjection.ps1'
& '@@LAUNCHER_ROOT:win@@\Test-CodexIsolation.ps1'
```

验收要同时覆盖：

- `auth_mode=apikey`、`cm` provider 和中转端口；
- `/health` 版本与当前源码、重载脚本和启动检查一致；
- `@@SANITIZER_ROOT:win@@\test-kimi-tool-message-name.js` 本地工具调用/结果回归；
- `@@SANITIZER_ROOT:win@@\test-gpt-switch-reasoning-replay.js` 跨模型 reasoning 回放回归；
- `@@SANITIZER_ROOT:win@@\test-live-gpt-switch-reasoning.js` 真实 GPT-6 切换 smoke；
- `@@SANITIZER_ROOT:win@@\test-live-model-switch-history.js` 同一历史跨模型回放、真实受限工具执行和文件内容回传；该脚本是手动验收，不挂接日常启动或定时任务；
- D `CODEX_HOME`、D user-data-dir 和固定 store app；
- sandbox marker、users file 和 `sandbox cmd.exe` smoke；
- session path、archive state 和 local catalog visible stale count；
- loader/tweak 注入和普通 Codex 配置未改变。

本次模型适配验收以 [模型适配验证-20260923.json](模型适配验证-20260923.json) 为准：包含源码哈希、真实失败结构的对照、四模型 12 个切换方向和实际文件读回。独立测试进程已退出，正式 15740 的加载与原会话 UI 结果分别记录；前述旧 PASS 不等同于这些范围已经完成。

已有分阶段回执（各自仅证明当时执行的范围）：

- `@@GENERAL_ROOT:win@@\records\evidence\CODEXPP-SANDBOX-PROVISIONING-SUCCESS-20260922.json`
- `D:\CodexPlusPlusMigration-20260922\historical-session-purge-20260922-152212\abandoned-session-archive.receipt.json`
- `@@GENERAL_ROOT:win@@\records\evidence\CODEXPP-SANDBOX-REPEATED-FAILURE-REVIEW-20260922.json`
- `@@GENERAL_ROOT:win@@\records\evidence\CODEXPP-KIMI-TOOL-NAME-S14-20260922.json`
- `@@GENERAL_ROOT:win@@\records\evidence\CODEXPP-KIMI-CLOSURE-S14-20260922.json`
- `@@GENERAL_ROOT:win@@\records\evidence\CODEXPP-CROSS-MODEL-REPLAY-CLOSURE-S14-20260922.json`
- `@@GENERAL_ROOT:win@@\records\evidence\CODEXPP-CROSS-MODEL-TOOL-ID-CLOSURE-S14-20260922.json`

## 8. 双规治理回执

### 责任轨：PASS

- **主责任域**：Codex++ Profile Runtime；Profile 配置和启动事实由 D canonical owner 持有。
- **唯一 SSOT**：本文件与 S34 Skill；普通 Codex 的 C owner 只做隔离对照。
- **正式入口**：`Start-CodexPlusPlus-Proxy.cmd` → `Start-CodexPlusPlus.ps1` → `Invoke-CodexPlusPlusIdentityLaunch.ps1`。
- **Runtime 消费者**：Start/Sync/Update、session-path-normalizer、Windows sandbox CLI、Windows Computer Use bridge、local catalog reconciliation。
- **Evidence 消费者**：S12/S14 回执、归档回执和窗口/注入/隔离测试；Evidence 只记录，不反向写运行状态。
- **Control 边界**：归档是默认动作，purge 需要用户明确授权；UAC setup 由用户可见的系统确认完成。
- **Experience 回流**：`resources\错题本.md` 记录案例，不能覆盖本 SSOT，也不成为第二运行入口。

### 收敛轨：LOW / PASS

- 复用了现有启动、归档、normalizer、catalog projection 和官方 sandbox setup 入口。
- 没有新增常驻 Watch、定时重启、第二 Registry、第二状态库、旁路 Engine、重试器或登录入口。
- `codex-dev.db` 的 local catalog 只是可重建投影；canonical state DB 仍是会话事实源。
- archive receipt 和 S12/M9 evidence 是审计记录，不是运行时状态源。
- 独立 `codex-windows-sandbox-setup.exe --help` 已被归类为错误调用协议；正式 setup 只走 `codex.exe sandbox setup`。

### 观察项

- 外部输入中曾出现 C canonical 声明；活动入口、AGENTS、S34、启动脚本和治理检查已核对为 D-only。该 C 文本按过期/非运行输入处理，不得覆盖当前 SSOT，也不触发回迁。
- S34 frontmatter 尚未单独声明 `owner/consumer/target_os` 字段；事实已在正文、related 和本 SSOT 中可追溯。若以后纳入 General OS registry，再按既有 Skill-owner 流程补元数据。
