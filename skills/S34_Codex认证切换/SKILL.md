---
name: S34_Codex认证切换
description: Codex++ 隔离 profile 的认证、代理、桌面入口、安装修复更新链及与普通 Codex 共存时的运行时内存/文件系统故障排障时使用。
domain: codex-plusplus-profile
tier: L2
doc_status: active-ssot
related:
  - D:\CodexPlusPlusProfile\AppData\Roaming\Codex\.codex\AGENTS.md
  - C:\Users\Administrator\.codex\AGENTS.md
  - C:\Users\Administrator\.agent\control\host-capability-publication-manifest.yaml
  - C:\Users\Administrator\.agent\tooling\Sync-HostCapabilityProjection.ps1
  - D:\CodexPlusPlusProfile\AppData\Roaming\Codex\.codex\skills\S34_Codex认证切换\resources\Codex++隔离配置基线.md
  - D:\CodexPlusPlusProfile\AppData\Roaming\Codex\.codex\skills\S34_Codex认证切换\resources\Codex++运行与归档SSOT.md
  - D:\CodexPlusPlusProfile\AppData\Roaming\Codex\.codex\skills\S34_Codex认证切换\resources\错题本.md
  - C:\Users\Administrator\.agent\records\evidence\CODEXPP-NTFS-COEXISTENCE-S12-20260922.md
birth_ceremony_id: bc-codexauthswitch-a8c9b2e1
birth_ceremony_date: 2026-05-14
---

# S34: Codex 认证状态与代理切换核心处理链

## 🎯 触发场景
当用户指令包含“帮我切回代理”、“切回 CodexManager”、“我要改用 ChatGPT 官方账号登录”、“切换 apiKey / OAuth”、“Codex++ 隔离自检”、“Codex 隔离自检”、“完全访问权限”、“Unable to save”时触发。

运行时可用性故障同样触发：“Codex++ 启动不了”、“点快捷方式没反应”、“Codex++ 卡住了”、“界面点不动”、“窗口出来了但没反应”、“启动一闪而过”。内存/文件系统故障也触发：“非分页池上涨”、“ntfs.sys”、“NtFC”、“内存爆炸”、“Codex++ 与普通 Codex 共存后卡死”、“OtherOps 飙升”。此类先按下节判据分流，**不要先改认证、代理配置，也不要先删除 tweak**。

### 2026-09-22 最终 D 盘运行数据面（当前有效）

Codex++ 的可变运行数据只有一个物理 owner：`D:\CodexPlusPlusProfile`。当前 canonical 路径如下：

- CODEX_HOME：`D:\CodexPlusPlusProfile\AppData\Roaming\Codex\.codex`
- runtime、tweaks、日志和 installer state：`D:\CodexPlusPlusProfile\AppData\Roaming\codex-plusplus`
- OpenCLI 本地 adapter：`D:\CodexPlusPlusProfile\.opencli\clis`
- Electron user-data-dir：`D:\CodexPlusPlusProfile`
- installer source：`D:\.codex-plusplus`
- projectless workspace：`D:\CodexPlusPlusProfile\Documents\Codex`；`Invoke-CodexPlusPlusEnsureWorkspace.ps1` 只在 D 盘建立父链，不预建日期叶子。
- 启动前 preflight 日志（workspace、DB reclaim、launcher compat、包身份注册）统一写入 `D:\CodexPlusPlusProfile\AppData\Roaming\codex-plusplus\log`，不得由继承的 `APPDATA` 把日志写回 C 盘。

运行链不得依赖 C 盘 Profile alias、C 盘 runtime/tweak 副本、D→C 的 nested `.codex` Junction 或 D→C 的 OpenCLI Junction。Windows Store `store-apps` 镜像和 Host/General OS 的静态 Skill 投影属于外部 owner，不算 Codex++ mutable data；不得为了路径统一误删普通 Codex、Store 包或 General OS SSOT。

切换或更新必须先验证以上 D 路径为物理目录，再执行 loader/injection、插件、session、Native Messaging、OpenCLI 和共存回归。旧 C 副本只允许存在于有明确回退证据的迁移快照中；验证完成后不得重新成为入口。

### SSOT 使用顺序

启动、登录模式、历史归档、Windows 沙箱和“Windows 设置未完成”类报错，先读 [Codex++运行与归档SSOT.md](D:\CodexPlusPlusProfile\AppData\Roaming\Codex\.codex\skills\S34_Codex认证切换\resources\Codex++运行与归档SSOT.md)，再调用本 Skill 后面的现有脚本。SSOT 规定唯一 owner、正式入口、归档优先规则和最小验收集；错题本只补充具体事故，不覆盖 SSOT。

迁移后的最小复核集：`Assert-CodexPlusPlusProfileRootContract.ps1`、`Invoke-CodexPlusPlusEnsureWorkspace.ps1`、`Test-CodexPlusPlusProfileAliasBoundary.ps1`、`Test-CodexPlusPlusTweakLinks.ps1`、`Test-CodexPlusPlusInjection.ps1`、`Test-CodexIsolation.ps1`、`Test-OpenCliAdapters.ps1` 和 `Protect-CodexPlusPlusGovernance.ps1`。这些是现有入口的定向检查，不是新的常驻守护链。

迁移验收事实：C Profile/runtime/source 入口均已退役；`D:\CodexPlusPlusProfile\AppData\Roaming\Codex\.codex`、`D:\CodexPlusPlusProfile\AppData\Roaming\codex-plusplus`、`D:\CodexPlusPlusProfile\.opencli\clis` 均为物理目录。回滚快照保留在 `D:\CodexPlusPlusMigration-20260922`，快照不是运行入口。

## ⚙️ 核心坑点与治理范围（必须全盘扫描）
Codex++ 切换链不能只改一个字段，但默认写入面始终限制在隔离 Profile。Agent 必须同时核对以下三项：
1. **隔离配置**：`D:\CodexPlusPlusProfile\AppData\Roaming\Codex\.codex\config.toml`。
2. **隔离认证镜像**：`D:\CodexPlusPlusProfile\AppData\Roaming\Codex\.codex\auth.json`；官方账号模式下保留 `auth_mode = "chatgpt"` 与官方 OAuth 凭据，代理模式下维护 `auth_mode = "apikey"`；禁止在官方账号模式下强刷为 apikey，也不能触碰普通 Codex 的认证缓存。
3. **协议格式**：隔离配置的代理 `cm` 节点不得残留会改变目标协议的错误 `wire_api` 值；按当前 provider 契约验证，而不是把普通 Codex 配置复制过来。

普通 Codex 的 `C:\Users\Administrator\.codex\config.toml` / `auth.json` 只允许只读对照；只有用户明确点名“修改普通 Codex”时才进入其写入面。

Codex++ 隔离环境的完整路径、启动脚本、权限、hooks、skills、自检和验收口径统一维护在：

`D:\CodexPlusPlusProfile\AppData\Roaming\Codex\.codex\skills\S34_Codex认证切换\resources\Codex++隔离配置基线.md`

排查 Codex++ 时必须先读这份基线；不要凭普通 Codex 的 `C:\Users\Administrator\.codex` 状态推断 Codex++。

### Codex++ 运行时不可用分流（点不开 / 卡死 / 假死）

排查手册是这类故障的操作 SSOT：`C:\Users\Administrator\.codex-plusplus-config\排查手册.md`。本节只定判据，不复制命令表。

> **26.915+ 包身份启动失败归 S50**：若启动后 4~25s 自动退出并报“该进程没有程序包标识符”，根因是缺 MSIX 包身份，**不是认证/代理问题**，由 `S50_Codex++启动器兼容治理` 负责（loose 注册变体包 + `chatgpt-pp.exe` 别名激活 + 变体服务锁移除 + 启动前 DB 膨胀回收）。当前启动链为 `Codex++ 启动.lnk → Start-CodexPlusPlus-Proxy.cmd →（自愈注入器 → DB 回收）→ Start-CodexPlusPlus.ps1 → 身份别名启动`；本节的认证/代理切换与更新闭环不覆盖该层，遇到先转 S50。

**先量事实，再动手。** 判据不是“有没有窗口”，而是**能不能唤醒 + CPU 是否失控**。`Responding=True` 只证明消息泵活着，绝不等于界面可用；卡死实例常常 `Responding=True` 且窗口句柄非 0。必须打印每个 ++ 主进程的 `MainWindowHandle`、`Responding`、`CPU`（累计秒）、`WorkingSet64`、`StartTime`，并按启动时长横向比对 CPU：进程刚起几分钟却累计上万秒 CPU，即为多核空转失控，**只能重启，等待无效**。

三态对应处置（守卫语义见 `C:\Users\Administrator\.codex-plusplus-config\AGENTS.md`）：

| 观测事实 | 处置 |
|---|---|
| 无 ++ 进程 | 正常启动即可 |
| 有进程、窗口可唤醒、CPU 正常 | 健康实例，只唤醒，**禁止杀** |
| 有进程、唤不出任何窗口 | 再点一次桌面入口即可（守卫自动清理重启） |
| 有窗口但点不动 / CPU 失控空转 | `Start-CodexPlusPlus.ps1 -Restart` 整树清理后全新启动 |

**杀伤边界（不可协商）**：只允许清理可执行文件路径落在 `C:\Users\Administrator\AppData\Local\codex-plusplus\store-apps\` 前缀下的进程。原生 Codex（`C:\Program Files\WindowsApps\OpenAI.Codex_*`、`AppData\Local\OpenAI\Codex`、`Roaming\Codex`）一律不动，用户日常在用。清理必须复用脚本内既有的边界函数，不得手写 `Stop-Process` 名字匹配——按进程名匹配会误杀原生实例。

**CPU 失控是症状不是根因**：`-Restart` 只是止血。若同一现象反复出现，需要在发生时抓线程栈定位到具体 tweak/扩展模块，再回流本 Skill 与错题本；不得用“定期重启”当作修复。

### Codex++ 隔离应用更新坑
当用户说“更新 Codex 后 Codex++ 打不开”“代理隔离启动一闪而过”时，先查启动应用包，不要先改代理端口。
- `http://127.0.0.1:48760/v1` 是 CodexManager API 端口；`http://localhost:48761/` 是 Web 页面端口；二者都不是系统 `HTTP_PROXY`。
- **定位真实 Appx 物理路径**：微软商店静默更新 Codex 后，`WindowsApps` 目录下的版本号会改变。由于该目录拥有 TrustedInstaller 的 ACL 限制，普通扫描会遭遇权限拒绝。**最佳实践是使用 `Get-AppxPackage -Name "OpenAI.Codex"`** 动态获取 `InstallLocation` 物理路径，绝不使用 `Get-ChildItem` 盲扫或写死物理路径，避免快捷方式自动修复机制（Shortcut Resolver）错误重定向至 tweaks 镜像目录。
- **Clash 代理精细防污染保留**：启动原生无 tweak 版本时，必须为官方 OAuth 登录预留网络代理。清除环境变量时**严禁一刀切**，必须采用“精细手术”——仅当 `HTTP_PROXY` 等值匹配 Codex++ 端口 `48760` 时才移除，其余 Clash 代理端口（如 `7890`）必须予以保留，确保官方登录跳转不断网。
- 修复优先级：先确认 `Get-AppxPackage` 能够取得最新原版物理路径，再确认 Clash 代理正常保留，最后才检查 `model_provider = "cm"`、`base_url`、`auth.json`。

### 2026-09-22 历史会话迁移后归档规则（当前有效）

- state_5.sqlite 的 threads.rollout_path 是会话恢复和归档的唯一路径事实；旧 C Profile、旧 D .codex 根和扩展前缀路径必须归一到物理 D nested .codex，并保存为普通 D 路径。
- thread_history_1.sqlite 只有按 thread_id 的投影，没有独立 rollout 路径；修复时先修 state DB，再按同一批历史 thread_id 清理投影，不能另建第二份历史库。
- 历史会话批量归档只能走一次性迁移/维护入口：将 rollout 移到 archived_sessions、更新 archived=1，原文缺失时生成明确标注的 renderer-safe stub；不得把缺失文件伪装成原文恢复成功。
- 默认处理目标是归档并保留可恢复证据；只有用户明确授权删除时才执行历史 purge。原始 rollout 已不存在的条目只能保留为明确标注的缺失归档投影，不能重新包装成完整历史。
- co.Arconte112.session-path-normalizer 保留原始“规范化路径、保护渲染器”的意图，但现在同时处理 archived rows、旧根和 malformed prefix；数据库触发器只剥离扩展前缀，不再制造新的扩展路径。
- 删除历史会话时按日期保留当天新会话，连同 state rows、thread-history projection、session index 和 quarantine metadata 一并清理；普通 Codex、当天新会话和 General OS Skill projection 不在范围内。
- MCP/tweak 安装脚本不得用 USERPROFILE + .codex 推导配置路径；Codex++ MCP 合并必须写入 CODEX_HOME 下的 nested config.toml，否则会复活 D:\CodexPlusPlusProfile\.codex。
- Windows sandbox 启动预检不能只看 `.sandbox\setup_marker.json`：还必须有与当前本机沙箱用户密码匹配的 `.sandbox-secrets\sandbox_users.json`。旧子配置里的加密凭据可能因密码轮换而失效，禁止把复制旧 JSON 当作永久修复；缺失或失效时只允许通过一次受控、用户可见的 UAC setup 重新生成。
- UI 列表残留排查必须同时检查 Electron global state 的 pendingThreadAssignmentIds、thread-project assignments、prompt-history、queue revision、memory stage1，以及 D-only `sqlite\codex-dev.db` 的 `local_thread_catalog`；清理只标记 canonical state DB 已不存在的 local thread 为 `missing_candidate=1`，不删除项目对象、ChatGPT host 或当前新会话。保留集合必须每次从 canonical state DB 动态读取，不能写死历史 thread id。

### 更新后防复发闭环（Appx、固定 store、插件与连接器）

Codex++ 的顽疾通常不是某个插件单点损坏，而是官方 Codex 更新后只替换了
WindowsApps 包，固定 store 镜像、tweak/loader、插件 marketplace 来源和连接器
状态没有在同一个受控维护事务内重新收敛。典型表现是：旧包仍被启动、界面
渲染层假死、`plugin/list` 返回空列表，或本地插件目录存在但 app-server 没有
对应服务。

以后每次检测到官方 Appx 版本变化、固定 store 缺少当前包、loader 注入漂移、
插件列表为空，或用户报告点击无效，都按下面的责任边界处理：

1. **唯一更新 owner**：官方源码更新只走
   `C:\Users\Administrator\.codex-plusplus-config\Update-CodexPlusPlusInstaller.ps1`；
   Appx → Codex++ 固定 store 镜像、旧镜像清理、loader/tweak repair 只走
   `Sync-CodexPlusPlusLatest.ps1 -Once`。禁止直接调用 native `update`、
   `self-update`、默认 `install`，也不得新增第二个 updater、watcher 或回滚写入者。
2. **更新事务顺序**：先用 `Get-AppxPackage -Name OpenAI.Codex` 取得唯一当前
   `InstallLocation`，再在 Codex++ 进程已退出的条件下完成镜像、资源文件和
   Fuse/loader 校验；repair 与注入验证通过后，才清理旧固定 store 包并继续
   启动。任何 repair/注入失败都不得牺牲上一份可用镜像。
   3. **插件来源不变量**：Electron 公共入口和内部
   `CODEX_HOME` 都必须落到物理 D 盘；当前
   `CODEX_HOME` 为 `D:\CodexPlusPlusProfile\AppData\Roaming\Codex\.codex`，
   `config.toml` 中 `openai-primary-runtime`、`openai-bundled`、
   `openai-curated` 的本地 marketplace `source` 必须是 D 盘 canonical 路径；
   不得写 `\\?\C:\...` 或其他经 Junction 的路径。否则文件“存在”不代表
   marketplace 可加载，`codex plugin list` 会出现空列表。
4. **插件认证边界**：`auth_mode=apikey` 时只把本地 marketplace/已缓存插件
   当作可用事实；ChatGPT 远程插件目录需要 OAuth，遇到 `401 Unauthorized` 或
   “API key auth is not supported” 时不得伪称远程插件已加载，也不得擅自把
   Codex++ 改成 OAuth。若确需远程目录，必须先取得用户明确的认证模式选择。
   API key 模式应保持 `features.remote_plugin=false`，但仍以实际 `plugin list`
   和 MCP 工具目录作为验收，不以开关文字自证。
5. **更新后同步**：维护事务成功后，必须在启动前完成 canonical Manifest
   projection、tweak/injection、沙箱和一次性 session maintenance；即使桌面
   入口传入了 `-SkipConnectorSync` 或 `-SkipOpenCliAdapterSync`，只要本次确实
   发生了 repair/更新，也必须补跑一次现有的连接器和 OpenCLI 同步 owner。健康
   重启不应因此执行完整 repair 或重复全量写入。
6. **启动假死判据**：`Responding=True` 只能说明消息泵存在，不能单独证明可用。
   必须同时核对主窗口句柄、进程启动时长、累计 CPU/5 秒 CPU 增量、命令行中的
    物理 D `--user-data-dir` 且不存在 C Profile 路径，以及只落在 Codex++ `store-apps` 前缀内的进程
   树。窗口存在但点击无效或 CPU 失控时，使用
   `Start-CodexPlusPlus.ps1 -Restart`，等待无效；禁止按进程名裸杀原生 Codex。
7. **插件验收**：更新后至少完成一次 `codex plugin list --available --json`
   的真实读取，确认已安装项、可用项和本地 source；再从 app-server/MCP 工具
   目录确认 `available_server_count` 与 `tool_count` 非零。只看到 cache 目录、
   单个插件 manifest 或 HTTP 200 均不构成“插件已加载”。
8. **失败收口**：完整启动测试若因测试 harness 与 canonical 路径/临时探针
   不一致而失败，不得伪造风险日志或把失败改写成 PASS；可保留桌面入口已有
   的兼容跳过作为应急启动路径，但必须把测试缺陷单独记录并继续修复。没有
   `START_EXIT=0`、当前包/固定 store 一致、注入通过、插件列表和窗口证据时，
   只能报告“部分恢复”。

这套闭环的核心不是定期重启，而是把“官方更新后的重新收敛”放回现有一次性
维护 owner；不新增状态库、后台循环、第二 Registry、按任务目录补丁或隐式
认证切换。

### Host Capability Projection 生命周期调用契约

S34 只负责 Codex++ 生命周期调用边界，不拥有发布策略、Manifest schema 或 Junction 算法。General OS Publication Policy/Manifest 的唯一 SSOT 是 `C:\Users\Administrator\.agent\control\host-capability-publication-manifest.yaml`；Skill 正文的唯一 canonical root 是 `C:\Users\Administrator\.agent\assets\skills`。

- 正式生命周期入口固定为 `lifecycle_ingress_count=3`：`Start-CodexPlusPlus.ps1`、一次性更新入口 `Sync-CodexPlusPlusLatest.ps1`、基础 repair 入口 `Repair-CodexPlusPlusCurrentApp.ps1`。直接投影 caller 是 Start 与 Sync 两个；Repair 只薄代理到 Sync。
- 投影固定为 `projection_writer_count=1`：`C:\Users\Administrator\.agent\tooling\Sync-HostCapabilityProjection.ps1`，实现归 General OS；Codex++ 目录只保留 lifecycle caller。caller 不得各自实现 Manifest 解析、Junction 修复或第二写路径；Protect 必须从活动文件探测计数，不得用常量自证。
- writer 必须无状态、幂等，只执行 `Manifest -> canonical Skill root -> Host Junction`。不得写 projection receipt、journal、generation 或运行时状态，也不得调用 `skills/extraRoots`。
- collision 只约束发生冲突的单个 Skill 目标：禁止覆盖普通目录、文件或未知目标 Junction，并明确报告该项；collision 不是 Host 全局资格门，不得阻断无冲突条目的投影，也不得阻断 Codex++ 基础启动或 repair。
- `D:\CodexPlusPlusProfile\AppData\Roaming\Codex\.codex\skills` 中由 Manifest 选中的 canonical Junction 就是正式投影；Manifest 外条目保持原状，不复制第二份 Skill 正文。
- 禁止复活任何 Host Replay/adapter tweak、activation/cutover/rollback、Adapter 专用 ASAR baseline、后台 worker/loop/watchdog、receipt/journal/generation/state 或 transaction fixture。历史代码与 evidence 只作退役证据，不能重新成为入口或依赖。
- 所有正式 PowerShell 调用唯一使用物理路径 `C:\Program Files\PowerShell\7\pwsh.exe`；禁止 PATH 解析、别名或旧 Host 依赖。CMD 入口必须原样回传子进程 `%ERRORLEVEL%`。
- public Profile 不存在重解析入口；`D:\CodexPlusPlusProfile` 是唯一物理 owner。Start 与唯一 maintenance writer Sync 在首次写入前都验证 D 根及 nested `.codex` 为物理目录，Repair/Updater 只经 Sync 进入，普通 Codex 未经用户明确点名不得修改。
- 一次性更新入口是原生 repair 后清理的唯一 owner：保留当前官方包镜像；旧 `OpenAI.Codex_*` 只有同时满足固定 store 的直接物理子目录、非当前包、且无进程使用时才允许删除。Start 只在当前 store 缺失、注入漂移或显式 `-ForceRepair` 时调用该 owner；健康重启不得无条件执行 `/MIR`。Repair 始终薄代理到该 owner，不复制清理函数。
- 当前用户快捷方式实体是 `C:\Users\Administrator\Desktop\Codex++ 启动.lnk` → `Start-CodexPlusPlus-Proxy.cmd`（可见控制台，走完整自愈链：LauncherCompat 注入器 → DbReclaim → 主脚本 → 身份别名启动）。注意 `Start-CodexPlusPlus-Proxy.vbs`（零闪窗 shim）当前直连 `Start-CodexPlusPlus.ps1`，**绕过了 cmd 头部的注入器与 DB 回收两步，二者不等价**；若切用 vbs 零闪窗入口，必须先让 vbs 改调 cmd（或补齐同样两步），否则丢自愈。任何入口层改动后必须复核 .lnk 目标与自愈链不被重置。installer 生成的 `Codex++.lnk` 只有在目标确认位于固定 Codex++ store 时才移除；手动生命周期审计不得成为 Host 启动门。
- installer 源码更新的唯一外部 owner 是 `C:\Users\Administrator\.codex-plusplus-config\Update-CodexPlusPlusInstaller.ps1`，只允许一次性执行，不得建立 update worker。`config.json` 的 `codexPlusPlus.autoUpdate` 必须为 `false`，`codex-plusplus-watcher*` 计划任务和 `bin\watcher.cmd`/`watcher.vbs` 必须为 absent。
- installer source 的唯一 canonical identity 是 `D:\.codex-plusplus`；`C:\Users\Administrator\.codex-plusplus` 已退役且不得复活。Manifest、hash、审计、日志、回滚与受控写入一律以 D 路径为权威，迁移快照不得作为第二 source 或恢复 owner。
- 原生 self-update 会整目录替换 `D:\.codex-plusplus\source`，因此不得直接调用 native Node CLI 的 `update/self-update`。受控 updater 必须在同一互斥事务内执行 native `update --no-repair`、重施固定 PS7 overlay、build、Windows installer 定向测试、强制 lifecycle repair、边界复核，并在提交后删除临时 `source.previous`；准备或 repair 失败时恢复旧 source 并重新 repair。
- 两个 public CLI shim 必须与 `CodexPlusPlus-ControlledCliShim.cmd.template` 完全一致，WindowsApps link 必须精确指向它们。无参数 `codexplusplus update/self-update/repair` 只路由受控入口；public `install` 必须拒绝，因为原生 install 默认 `watcher=true` 并会覆盖 launcher。首次/重装只能在 Codex++ 完全退出后按本 Skill 直接调用固定 Node/native CLI 的 `install --no-watcher`，随后立即运行 `Sync-CodexPlusPlusLatest.ps1 -Once -ForceRepair` 与 `Protect-CodexPlusPlusGovernance.ps1`。
- `D:\.codex-plusplus\source.previous*` 只允许作为单次 update 的临时回滚，不得长期保留。WCU tweak 的 local-change fence 可阻止 Store 自动静默覆盖本地 PS7 迁移，但手工卸载/重装仍可回退；任何重装后必须重新跑 PS7 活动调用面检查。
- `Test-CodexPlusPlusTweakLinks.ps1` 只读验证 source Junction 与 manifest；禁止启动链从 `source.previous*` / `source.failed*` 复制回 active source。唯一 source rollback 仍归受控 updater 的互斥事务。
- 长驻 `Watch-CodexPlusPlusSessionPaths.ps1 -Watch` 已退役，正式后台 session watcher 期望数为 `0`。兼容文件名当前只承载启动时/显式 `-Once` session maintenance；SQLite triggers、cold storage 与 reader 保持独立能力，不加入 Manifest/install/update 主链，不维护 PID 或第二状态机。
- S14 只能按本轮列明的输入、命令、边界和未观测项给出 `PASS_WITHIN_DECLARED_SCOPE`；该结论表示声明范围内没有已知未登记债务，不得外推为全局、未来版本或未执行链路“无隐藏债务”。
- workspace `.codex-evidence/**/*.json` 只属于 Hook 当次失败复核的可消费 receipt；对应 pending 已由成功重跑或 S12/W9 receipt 清除后可不保留，也不得冒充 General/Host 的正式长期 Evidence。需要跨轮保留的结论必须写入真实 owner 的 Evidence 位置；General 正式证据使用 `C:\Users\Administrator\.agent\records\evidence`，既有只读证据只追加 correction，不原地改写。

以下能力与 Host Capability Projection 相互独立，必须保留但不得升级为发布门：基础 repair 只负责当前官方包到 Codex++ 固定 store 的修复；Chrome Native Messaging Host 继续由 `Restore-CodexPlusPlusNativeMessagingHost.ps1` compare-and-set 恢复；session SQLite 继续使用固定 Python 与 `Invoke-CodexPlusPlusSqlite.py`，且只接受 canonical `D:\CodexPlusPlusProfile\AppData\Roaming\Codex\.codex\state_5.sqlite`。

### Codex / Codex++ 隔离自检验收
当用户说“Codex 隔离自检看不懂”“Codex++ 无法完整赋权”“Unable to save”时，不要只看 UI 文案，要同时查真实配置、Electron userData 入口和自检脚本输出。

必须优先确认这些路径：
- 普通 Codex 配置目录：`C:\Users\Administrator\.codex`
- Codex++ 配置目录：`D:\CodexPlusPlusProfile\AppData\Roaming\Codex\.codex`
- 普通 Electron 入口：`C:\Users\Administrator\AppData\Roaming\Codex\.codex`
- Codex++ Electron 入口：`D:\CodexPlusPlusProfile\AppData\Roaming\Codex\.codex`
- 隔离启动脚本目录：`C:\Users\Administrator\.codex-plusplus-config`

自检脚本：
```powershell
& 'C:\Program Files\PowerShell\7\pwsh.exe' -NoProfile -File "C:\Users\Administrator\.codex-plusplus-config\Test-CodexIsolation.ps1"
```

合格输出必须有醒目的总判定：
```text
OVERALL: PASS - Codex and Codex++ are isolated as expected.
```

判定口径：
- `normal auth` 应存在：普通 Codex 保留官方账号登录缓存。
- `plus auth` 应存在且只作为 CodexManager API key 镜像：`auth_mode = "apikey"`，`OPENAI_API_KEY` 与 `config.toml` 的 `[model_providers.cm].api_key` 完全一致；不得混入官方 OAuth token 字段。
- 两个 Electron `.codex` 入口都应指向各自真实配置目录，不能交叉指到对方。
- `normal config` 和 `normal electron config` 的短 hash 应一致；`plus config` 和 `plus electron config` 的短 hash 应一致。
- 自检脚本不得打印 `auth.json`、`config.toml` 正文、token、`api_key`；只能显示存在性、路径、大小和短 hash。

完全访问权限的配置验收值：
- `approval_policy = "never"` 对应 UI 的 `Never`。
- `sandbox_mode = "danger-full-access"`。
- `[windows] sandbox = "elevated"`。
- Codex++ 仍应保持 `model_provider = "cm"`，普通 Codex 是否使用官方账号按用户明确指令决定。

如果桌面快捷方式要跑自检，目标应对齐：
```text
C:\Program Files\PowerShell\7\pwsh.exe
```
参数应包含：
```text
-NoProfile -NoExit -File "C:\Users\Administrator\.codex-plusplus-config\Test-CodexIsolation.ps1"
```

### Hook 错误与隔离配置的边界
如果 UI 显示 `hook returned invalid stop hook JSON output`，先不要把它误判为 Codex++ 认证或权限配置失败。优先查 Stop hook 输出 schema：
- `D:\CodexPlusPlusProfile\AppData\Roaming\Codex\.codex\hooks\stop_guard.py`
- `C:\Users\Administrator\.codex\hooks\stop_guard.py`

Stop hook 用于继续执行时，应优先输出当前 Codex 可接受的简洁形态：
```json
{"continue": true, "systemMessage": "..."}
```
不要在 Stop hook 输出里额外塞当前 Codex 不接受的 `decision` 或 `hookSpecificOutput.decision` 字段。治理逻辑可同步到两边 hook，但 `hook-state` 必须继续按各自 `CODEX_HOME` 分开落盘。

### 2026-09-11 外部模型连续执行、适配器单飞与可视化目录 ENOENT

这是一条已验证的 Codex++ 第三方模型适配规则，适用于 DeepSeek/Kimi 等通过本地协议适配器接入的模型。

#### 先判定是哪一层

| 现象 | 第一事实 | 处理方向 |
|---|---|---|
| 返回一句话后约 10–20 秒结束 | `logs_2.sqlite` 出现 `unhandled responses event`、`failed to parse ResponseItem`，并且 `needs_follow_up=false` | 先查适配器事件格式和服务是否载入新代码；不要先换模型或重刷密钥 |
| 新任务第一条消息报 `ENOENT ... .codex\\visualizations\\YYYY\\MM\\DD\\TASK_ID` | Node 仍拿到旧路径，或公共 parent 未在 D 盘建立 | 将内部 `CODEX_HOME`、Electron `--user-data-dir` 和新目录写入统一切到物理 `D:\CodexPlusPlusProfile`；不得创建 C alias |

#### DeepSeek/Kimi 的协议适配不变量

- 当前 sanitizer 链路为 `Codex++ -> http://127.0.0.1:15740/v1 -> CodexManager 48760`。当 `config.toml` 的 `cm.base_url` 指向 `15740` 且 `wire_api="responses"` 时，这是有意启用的第三方模型适配覆盖，不按直连 `48760` 的基础基线判断。
- 代理健康检查必须与当前源码、`restart-sanitizer.ps1` 和正式启动脚本的期望版本一致；当前 Codex++ 远程压缩回放版本目标是 `responses-summary-v39-qwen-vision-v1`。编辑源文件不等于运行进程已经加载，必须核对服务重载退出码、进程创建时间和 `/health`。服务重载本身不要求删除会话或重启电脑。
- 推理摘要使用 `response.reasoning_summary_part.added`、`response.reasoning_summary_text.delta/done`、`response.reasoning_summary_part.done`。`response.reasoning_text.done` 在 Codex++ 26.901 解析器中会被记录为未处理事件。
- `custom_tool_call` 使用 `input` 字段；流式工具调用必须包含 `response.custom_tool_call_input.delta` 和 `response.custom_tool_call_input.done`。`arguments` 只用于 `function_call`。
- Responses 的 `id` 是 item 标识，`call_id` 是调用与结果的关联标识。只规范 item ID；已有 `call_id` 按不透明字符串原样保留。转 Chat 时用 `call_id` 生成 `tool_calls[].id`，结果的 `tool_call_id` 必须精确匹配它，名称来自对应调用。不能把 `fc_/ctc_` 的 item 前缀要求套到 `call_id`。
- 同一批连续 Responses 工具调用须合并为一条 assistant 消息的 `tool_calls` 数组；结果按关联 ID 回接，允许乱序。用户消息和工具结果之间的批次边界须保留。Kimi 的“工具名无法解析”也可能来自批次被拆散，不能仅凭错误文案推断名字或历史缺失。
- 自由文本 custom 工具转 Chat function 时声明必填字符串 `input`，历史参数编码为同一信封，回程还原原文。不得把代码模式 `exec` 声明成无参数函数；收到空 `exec` 参数时返回明确失败，不能执行 `{}` 后声称工具成功。
- 跨模型继续执行时，`store=false` 历史中的 `reasoning` 项只有在携带 `encrypted_content` 时才可重放；适配器生成或历史残留的 summary-only `rs_` 项及其 `item_reference` 必须在请求入口移除，避免 GPT 返回 `Item with id ... not found`。有效的加密 reasoning 保留，消息和工具结果继续保留。
- 名称兼容只能使用精确关联、无歧义别名、当前批次唯一未消费调用，或明确的唯一 custom 工具声明；声明列表顺序不是调用顺序。歧义输入明确报错，保留原历史，不编造工具名或输出。
- “命令没有输出”先对照原始 `custom_tool_call.input`、真实 output、转换后的参数。若输入是 `{}`，这是空调用，不能据此断言会话输出通道损坏，也不以贴正文、删历史或新建会话替代修复。
- 适配器回归至少要观察：HTTP 200、`response.completed`、`custom_tool_call_input.done` 和非空工具输入；只看到 SSE 文件存在或一条文本不构成通过证据。
- 代码模式内部 `tools.exec_command` 使用当前公开的 `cmd/workdir/yield_time_ms`。只对已观察到的 shell 参数别名做窄兼容，其他工具按各自声明传参；旧直接 shell 路由器的字段名不能套到当前代码模式。
- DeepSeek 若把宿主内部的 `exec_command` 或 `mcp__node_repl__js` 直接作为 custom tool 名返回，适配器只将这两个已知别名转换成代码模式 `exec`：`exec_command` 通过 `tools.exec_command(payload)` 执行，`mcp__node_repl__js` 提供 `nodeRepl.write -> text` 绑定；不得把其他未知名称泛化为工具别名。
- 若日志出现 `tool exec_command invoked with incompatible payload`，随后反复出现 `Custom tool call output is missing for call id: ctc_...`，这是第一条工具调用失败后旧 call id 卡住了后续轮次；停止当前坏轮次、重启 Codex++ 清空上下文，再用新任务回归，不要让模型继续重试同一个 call id。
- 适配器必须对同一第三方工具链实行 single-flight：同一时间只允许一个活动上游请求，后续请求排队；客户端 `aborted`/响应 `close` 时立即取消上游并释放队列槽位，避免旧请求占用供应商并发槽并把后续调用误报为并发限制。
- 上游 SSE 可能以 HTTP 200 携带 `error` 事件；不得丢弃该错误后合成 `response.completed(output=[])`。只有尚未产生任何模型内容或工具调用的空错误流才允许有限退避重试；一旦已产生输出或工具调用，禁止重放以避免副作用重复执行。
- 完成判断区分回放结构、真实 API、工具执行、原会话 UI 四层。旧 `test-live-deepseek-five-turns.js` 使用预置工具结果，只证明串行协议探针；不能作为实际工具执行或双向切换证据。混合历史验收用 `test-live-model-switch-history.js`：同一历史、真实受限工具执行、结果回传、下一模型采样和最后一次结果消费。只汇报本次实际通过的模型方向。
- 2026-09-23 的根因对照、四模型 12 个方向及文件读回结果见 [模型适配验证-20260923.json](resources/模型适配验证-20260923.json)。该记录区分源码/独立线上测试和正式服务加载；未取得后者时不把它解释成原会话 UI 已恢复。
- `kimi-k3` 可能在小输出预算下耗尽推理摘要额度而不发工具调用；适配器对该模型保持最低 `max_tokens=1024` 的窄覆盖，不把该预算规则泛化到其他模型。
- 对 DOCX 内容任务，先独立验证文件存在、`word/document.xml` 可读和文本可提取，再判断模型改写逻辑；“网络查重率小于某阈值”还必须有明确查重服务和结果证据，不能把模型声称已查重当成验证结果。

#### 2026-09-27 远程压缩 v2 与跨模型回放经验（当前 SSOT）

完整的故障链、字段不变量和验证顺序见 [远程压缩与回放经验](resources/远程压缩与回放经验.md)。本节只保留必须影响决策的规则：

- Codex 核心的 remote compaction v2 使用普通 `/v1/responses`，在 `input` 末尾追加 `type: "compaction_trigger"`；不能把它当成旧的 `/v1/responses/compact`，也不能把普通 Chat 输出当作压缩结果。
- Chat-only 模型的现有 15740 适配入口必须保留原始正常 Responses 路径，同时对压缩请求生成唯一 `type: "compaction"` 输出项；禁止用空 compaction 或静默成功掩盖未压缩上下文。
- 适配器自有 compaction 摘要回放到原生 Responses 时，`cmp_` 私有项必须降级成 assistant `message`，重新生成 `msg_` ID，assistant 内容必须是 `output_text`；`input_text` 只能用于 user/developer 输入。
- UI/state 中手动选择的模型和 reasoning effort 是当前线程事实。核心可能在预压缩阶段按 `ModelDownshift` 使用历史模型；这不是把 UI 选择改回旧模型，不能通过硬编码全局模型掩盖它。Responses 的 `reasoning.effort` 必须映射到 Chat provider 的 `reasoning_effort`，保留 `ultra/max` 等有效值。
- 源码版本、服务进程和 `/health` 必须三方一致；若源码是 v39、运行服务仍是 v35/v36/v37/v38，不能宣称修复已生效。先重载 15740，再按需要走 `Start-CodexPlusPlus.ps1 -Restart`；正常 Codex 与普通账号配置不在写入范围。
- 验收按四层区分：语法检查、loopback 协议回归、服务已加载的 health/PID 证据、真实长会话压缩。前两层通过不能替代后两层；真实客户端未触发新的压缩时，只能报告“运行态已就绪，真实压缩待触发”。
- 修复继续归属现有 15740 适配器和 S34 生命周期入口，不新增压缩工作流、状态库、watcher、第二代理或旁路控制面。
- GLM-5.2、GLM-5.3、GLM-5.3-Flash 纳入同一第三方模型合同：模型目录提供 reasoning levels，15740 将 Responses 转到现有 Chat 适配入口，`reasoning.effort` 映射为上游 `reasoning_effort`；只改目录而不改请求入口会造成 UI 可选但上游仍记录 `reasoning=none`。其中只有已验证的 GLM-5.3-Flash 在目录中声明 `input_modalities=["text","image"]`；GLM-5.2/5.3 仍保持文本模型。其他第三方模型也逐项按真实上游能力审计；当前 Kimi K3、Qwen 3.8 Max/Flash、DeepSeek 的既有视觉路由和 GLM-5.3-Flash进入图片名单，Qwen 请求必须走 active A2Agent。

#### D-only 新目录写入规则

- connector sync 的 `TargetRoot`、备份目录和可视化路径统一使用 `D:\CodexPlusPlusProfile\AppData\Roaming\Codex` 与 `D:\CodexPlusPlusProfile\AppData\Roaming\Codex\.codex\visualizations\YYYY\MM\DD\TASK_ID`；备份单文件前显式创建父目录。
- **2026-09-21 projectless 任务目录**：`projectlessWorkspaceRoot` 使用 `D:\CodexPlusPlusProfile\Documents\Codex`；启动前只保证 D base 父链存在，不预建日期叶子，避免 App 非递归 mkdir 撞 EEXIST。凡新增 App 侧目录写入都必须以 D canonical base 为根。

#### 2026-09-22 共存内存爆炸：NTFS 非分页池根因与 D-only 修复

这次事故不是“Codex++ 进程自己的内存没有释放”，也不是要求停掉普通 Codex 或删除 tweak。决定性事实是：普通 Codex 与 Codex++ 同时运行时，Codex++ 的 Electron/Windows 文件路径层经过重解析入口会持续放大文件操作，内核非分页池随之上涨；把所有 tweak/preload 关闭后仍可复现，说明触发点不在某个 tweak。将 Codex++ Electron user-data-dir 固定到物理 D 盘后，在普通 Codex 继续运行的条件下，空闲 90 秒非分页池增量约 0.7MB，读写任务约 0MB，OtherOps 回到约百次/秒量级。

原始意图必须保留：Codex++ 仍保留全部 tweak、插件、隔离 Profile、`CODEX_HOME` 和普通 Codex 共存。改变的是物理 I/O 边界：

- Electron 主进程及其子进程必须使用 `--user-data-dir=D:\CodexPlusPlusProfile`；
- `CODEX_HOME`、connector、session、visualization 和 marketplace 的内部写入统一使用 `D:\CodexPlusPlusProfile`；
- C Profile alias 已退役，Electron 主数据目录和内部写入只允许使用物理 D；
- 普通 Codex 的启动、Profile、认证和进程树不在本 Skill 的写入范围，不能用“止血”名义杀掉或改写它。

这条修复不引入第二套控制面：仍由 `Start-CodexPlusPlus.ps1` 作为唯一桌面启动 owner，`Sync-CodexPlusPlusLatest.ps1` 作为唯一更新/repair owner，session maintenance 仍是显式 one-shot。`Watch-CodexPlusPlusSessionPaths.ps1` 的 `-Watch` 长驻模式继续退役；`active_session_risks.jsonl` 由 one-shot 入口预热并由风险记录逻辑写入，活动未归档会话只记风险、不删除数据。新增常驻 Watch、定时重启、旁路状态库或第二 Guard 都属于过度设计，禁止以本事故为由加入。

举一反三的固化不变量：

1. 所有启动入口（桌面快捷方式、Store 遗留快捷方式、脚本、更新后的直接 shim）都必须最终落到 `Start-CodexPlusPlus-Proxy.cmd`，并在进程命令行看到物理 D `--user-data-dir`；
2. Codex++ Profile 专用 `.gitconfig` 保持 `core.fsmonitor=false`、`core.untrackedcache=true`、`core.fscache=true`，并设置 `GIT_OPTIONAL_LOCKS=0`，不能改普通 Codex 的 Git 配置；
3. `session-path-normalizer` 继续启用，但生命周期必须可重复启动/停止，stop 必须绑定 tweak 实例并释放 timer/DB；其扫描节流是降 I/O 的实现细节，不替代物理 D 边界；
4. 看到非分页池上涨时先分开记录“进程工作集、文件 I/O、内核池、服务重启”四条证据；不能把单次进程内存下降或没有 WSL 误写成根因证明；
5. 重启只能回收已经泄漏的内核池，不能代替修复。根治验收必须在普通 Codex 仍运行时，对 Codex++ 走物理 D 路径做冷启动、空闲和真实任务三种观察。

最低回归证据：`Test-CodexPlusPlusProfileAliasBoundary.ps1`、`Test-CodexPlusPlusInjection.ps1`、`Protect-CodexPlusPlusGovernance.ps1`、`Test-CodexPlusPlusSessionPaths.ps1` 均通过；主进程命令行含 `--user-data-dir=D:\CodexPlusPlusProfile`，普通 Codex 进程仍在且未被启动脚本清理。动态池/I/O 采样和限制记录在 `C:\Users\Administrator\.agent\records\evidence\CODEXPP-NTFS-COEXISTENCE-S12-20260922.md`。若测试环境已有旧 C 路径运行造成的池残留，先记录残留再重启回收，不能把回收结果冒充为新路径回归。

#### 启动与收口验收

1. 用物理路径 `C:\Program Files\PowerShell\7\pwsh.exe` 执行 `Start-CodexPlusPlus.ps1 -Restart`，正常路径不得依赖 `-SkipConnectorSync` 或 `-SkipOpenCliAdapterSync` 作为最终修复。
2. 启动日志应出现 connector sync、OpenCLI adapter sync、sandbox ready 和 `START_EXIT=0`；全量 session maintenance 仅在显式传入 `-RunSessionMaintenance` 时执行，默认跳过且不启动后台 watcher。
3. `/health` 应带新 adapter 版本；Codex++ 主进程命令行必须带物理 `--user-data-dir=D:\CodexPlusPlusProfile`。
4. 发送一个明确需要工具的 DeepSeek 或 Kimi 任务，确认模型推理、工具调用、工具结果回传和下一轮请求连续发生，并至少完成五轮连续工具调用。
5. 若仍看到旧的 `reasoning_text.done`，先回到 `/health` 和服务 PID 判定旧进程，不要继续修改模型配置、认证模式或 prompt。

---

## 🛠️ 执行动作 1：切向【代理 API Key 直连模式 (CodexManager)】
1. **注入代理指针**：
   - 只在 Codex++ 隔离配置 `D:\CodexPlusPlusProfile\AppData\Roaming\Codex\.codex\config.toml` 中注入 `model_provider = "cm"`。
2. **净化代理节点**：
   - 检查 `[model_providers.cm]` 节点：当前默认走 `base_url = "http://127.0.0.1:15740/v1"` 的消毒代理适配器，此时 `wire_api = "responses"` 是**有意配置，必须保留**（见 §214）。
   - **仅当** `cm.base_url` 直连 CodexManager `48760` 时，才抹除该节点下的 `wire_api = "responses"`（直连态不接受 responses 协议）。先判 base_url 端口再决定，不得一刀切抹除。
3. **同步 Codex++ 隔离认证镜像**：
   - 将隔离 `auth.json` 维护为 `auth_mode = "apikey"`，并让 `OPENAI_API_KEY` 与隔离 `config.toml` 的 `cm.api_key` 一致；不得写入官方 OAuth token，也不得删除、覆盖或迁移普通 Codex 的 `C:\Users\Administrator\.codex\auth.json`。
4. **后续通知**：提示人类重开终端使可能存在的 `$env:CM_API_KEY` 及本地进程上下文立刻刷新。

---

## 🛠️ 执行动作 2：切向【官方账号 OAuth 登录模式】
1. **拔除代理指针**：
   - 只在 Codex++ 隔离配置中删除或注释 `model_provider = "cm"`；普通 Codex 配置仍不在本 Skill 的写入范围。
2. **唤起登录授权**：
   - 建议用户在前台交互式终端执行 `codex --login` 进行 OAuth 网页授权。
3. **后续通知**：告知用户必须完成 Web 授权并看到 "Login successful"，本地重新生成了最新的 `auth.json` 强缓存后，才算成功切回官方模式。

---

## 🚨 GOVERNANCE_OBJECT_CRUD_GATE
- **object_class**: Skill
- **action**: UPDATE
- **ssot_home**: CodexPlusPlusProfile/.codex/skills
- **prompt_knowledge_layer**: executor-profile / L2
- **parent_child_scope**: profile-local; not a parent prompt-engineering asset, OpenClaw asset, or E Core capability
- **registry_update**: Codex++ profile `AGENTS.md` and parent W7 incident pointer now reference this profile-local Skill; OpenClaw domain catalog no longer registers it
- **blast_radius**: LOW (Codex++ local troubleshooting protocol and private mistake notebook only)
