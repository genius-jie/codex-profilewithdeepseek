---
domain: host-migration
tier: L2
doc_status: active-reference
birth_ceremony_id: project-host-migration-20261019
related:
  - ../AGENTS.md
  - manifest.json
  - tools/restore.py
  - https://github.com/genius-jie/prompt_Knowledge/blob/main/docs/howto/github-windows-handoff.md
---

# 在新 Windows 恢复普通 Codex、Codex++ 与 Claude Code

本包保存三种宿主的可入库配置、全局提示词、上下文入口、宿主专用技能、角色定义和启动钩子，以及现有启动器、模型适配服务和 Codex++ 安装源码。三个宿主各自使用独立目录；通用方法正文继续由 General 仓库维护。

首次接手按本页执行。仓库根部早期的 `config.toml` 与简化启动脚本是旧 Profile 示例；本包从当前三种宿主分别采集，**不要用旧示例覆盖当前配置**。打包不改变原机运行配置，也不会在克隆后自动安装钩子、启动程序或注册服务。

**需要在新机选择 DeepSeek、千问、Kimi、GLM 时，继续执行 [第三方模型完整接入指南](model-setup/README.md)。** 它覆盖原生管理软件中的账号/路由录入、精确模型 ID、正确服务入口、Claude API 格式、模型切换和真实工具结果回传验收；文件恢复完成后还必须完成这条链路。

## 新电脑统一入口

取得本仓与 General 仓库、安装 Python 3.11+ 和 PowerShell 7 后，可直接使用统一入口。它自动取得新机用户目录和可用解释器，只需明确 General 源与隔离 Profile 的位置；默认先预览：

```powershell
pwsh -NoProfile -File .\host-migration\new-computer.ps1 -GeneralRoot D:\AgentAssets\prompt_Knowledge -CodexPlusPlusProfile D:\CodexPlusPlusProfile
pwsh -NoProfile -File .\host-migration\new-computer.ps1 -GeneralRoot D:\AgentAssets\prompt_Knowledge -CodexPlusPlusProfile D:\CodexPlusPlusProfile -Mode Apply -WithSupport -Receipt D:\MigrationPrivate\new-computer.json
```

只恢复普通 Codex 时加 `-Hosts codex`，无需 `-WithSupport`。Claude 系统级钩子额外加 `-Managed` 并使用有写入权限的终端。工具缺失、配置碰撞或目录重叠会直接指出；它不自动安装依赖或更改正在运行的宿主。

配置恢复后，使用同样的路径执行 `-Mode Check -SmokeHooks`，会实际运行本包恢复的 SessionStart 钩子并核对各自全局提示词绑定。它不会执行与本包不同的现有企业/用户钩子。检查输出分别说明配置是否齐全、钩子是否运行、账号与真实模型调用是否仍待目标宿主验证。详细路径选择、私密数据、依赖安装和回退见下文。

## 已保存什么，什么需要私密迁移

| 内容 | 本包如何处理 |
|---|---|
| 三宿主当前全局提示词、规则、Hook 注册与源码 | `payload/codex`、`payload/codex_plus_plus`、`payload/claude_code` 独立保存；原机路径变为模板变量 |
| 普通 Codex 的生命周期契约、查询工具、专用技能、research 配置与角色 | 随普通宿主保存；应用自带 `.system` 技能由应用安装提供 |
| Claude Code 系统级钩子注册 | `payload/claude_managed` 单列；原机只注册于 managed-settings，默认恢复不写系统目录 |
| Claude 的用户 MCP 定义与 CCS 自有服务源码 | 只提取 MCP 定义到 `mcp-servers.json`，CCS 的 mcp/hooks 源码单列 `ccs_mcp`；不复制用户身份、项目授权或 CCS 账号配置 |
| 通用 Skill、Workflow、Context 契约与规则 | 引用 General 仓库及文件摘要；通过其原有发布工具建立清单选中的链接 |
| 宿主中残留的 General 物理副本 | 与 General 相同的文件只记引用，差异保留在 `review-only`；默认不把这些副本投影成第二个正文源 |
| Codex++ 现有启动链、修复及隔离检查 | `payload/launcher`；只复制，恢复工具不执行维护、进程清理、提权或升级 |
| 模型协议适配服务 | `payload/adapter` 保存源码及现有注册入口；不搬原机服务注册或账号数据库 |
| Codex++ 本地安装源码、tweak 源码和可分发资源 | `payload/codexpp_source` 与 `payload/codexpp_tweaks`，保留源码中的许可文件；依赖、产物和原生工具在新机安装生成 |
| 额外模型基础指令替换文件 | 原文保留在 `review-only`，不恢复 `model_instructions_file` 绑定；它是替换内置指令的第三方输入，须独立审查后再决定是否采用 |
| 登录凭据、Token、Cookie、Provider 密钥 | 不入包；重新登录或使用私密渠道配置，字段名示例见 `private-transfer.example.env` |
| General 技能在宿主里的业务连接器配置副本 | 配置目录整体留给私密迁移，机器人 Webhook 视同凭据；不因放在 `review-only` 就允许公开 |
| 聊天记录、记忆、SQLite、自动化状态、日志与历史证据 | 不入包，不读取凭据字节；如需保留，先在宿主关闭后按宿主分别备份，再按产品支持方式恢复与验证 |
| 已有信任摘要、项目授权、原生 Node 通信管道、缓存路径 | 不迁移旧机有效性；由新机重新确认或应用生成 |

`manifest.json` 逐文件记录来源标签、原文与模板摘要、安装目标、转换项和排除类别。`checksums.json` 覆盖包内源码、模板、文档和清单。排除项只记录范围与原因，不公开私人记录的文件名或正文。通用资产读取不转移任何 OS 的 Runtime、Evidence、Control 或任务选择权。

## 先取得固定版本与工具

准备 Windows、Git、Python 3.11+、PowerShell 7；本包恢复工具只用 Python 标准库，不需要 pip。需要模型适配服务时再准备 Node.js；需要 Codex++ 源码构建时按其 `package.json` 的 Node 版本要求操作。

在长期保留的位置取得两个仓库。请把命令中的目录改为你实际选择的目录，不覆盖已有 clone：

```powershell
git clone -c core.longpaths=true https://github.com/genius-jie/codex-profilewithdeepseek.git D:\AgentAssets\codex-profilewithdeepseek
git clone -c core.longpaths=true https://github.com/genius-jie/prompt_Knowledge.git D:\AgentAssets\prompt_Knowledge
Set-Location D:\AgentAssets\prompt_Knowledge
git checkout 449eee774e717e5813b96fa366f19efadcf567d3
Set-Location D:\AgentAssets\codex-profilewithdeepseek
python .\host-migration\tools\restore.py verify
```

General 可使用后续提交，但清单中绑定的实际文件必须仍匹配；恢复工具会核对。General 的 UTF-8 源码/文档按 LF/CRLF 等价比较，二进制按原字节比较，不重写来源或历史证据。迁移包本身的 `checksums.json` 按原字节核对。General 真实源码必须长期保留，不能在建立技能链接后删除或随意移动。三端 OS 的完整业务项目另按各自接手指南迁移，本包不复制其数据库或未完成任务状态。

## 编辑新机路径，再预览

将 `layout.example.json` 复制到仓库外的本机文件，例如 `D:\MigrationPrivate\layout.json`。填入新机实际路径：

- `user_profile` 必须是新机实际 Windows 用户目录。普通 Codex 保存于其 `.codex`，Claude Code 保存于其 `.claude`。
- `codexpp_profile` 是独立的物理目录。Codex++ 配置固定在该根下的 `AppData\Roaming\Codex\.codex`，运行文件在同根的 `AppData\Roaming\codex-plusplus`，不创建旧 C 盘别名。
- `general_root` 是上一步的 General clone；`codexpp_source` 是将要恢复 Codex++ 源码的位置，与宿主配置、两个仓库都分开。现有安装链使用父目录下的 `source` 子目录，所选路径末级应保持 `source`，且位于可变 Profile 外。
- Python、PowerShell、Node 的路径填写新机安装位置，不复用旧机缓存中的版本目录。
- `suite_root`、`core_root`、`testing_root`、`openclaw_root` 只是保留已有按需引用的目标位置；不使用这些业务项目时不自动安装、启动或加载其正文，实际使用前需单独接手。
- 支持路径带空格及中文。归档脚本中的引号规则不支持路径含单/双引号、反引号、百分号、感叹号或换行；工具会拒绝这些路径，避免生成错误脚本。

```powershell
python .\host-migration\tools\restore.py plan --layout D:\MigrationPrivate\layout.json
```

`plan` 只读取并显示目标，不写配置。可通过 `--hosts codex`、`--hosts codex_plus_plus` 或 `--hosts claude_code` 只处理一个宿主。碰撞表示已有文件或链接与本包不同，不能直接覆盖；先查看差异并另行保全旧文件。

## 恢复宿主配置

先安装所需宿主。普通 Codex 和 Codex++ 使用不同应用入口；Claude Code 使用自己的安装与账号。安装后完全退出待恢复的宿主，再预览一次。已有配置与模板不一致时，工具会在任何写入之前停止，不提供强制覆盖参数。

```powershell
python .\host-migration\tools\restore.py apply --layout D:\MigrationPrivate\layout.json --receipt D:\MigrationPrivate\restore-hosts.json
python .\host-migration\tools\restore.py check --layout D:\MigrationPrivate\layout.json
```

`apply` 仅创建缺失文件；内容相同的文件保持原样。清单选中的通用技能由 General 原有 `Sync-HostCapabilityProjection.ps1` 创建 Junction，不引入第二个链接写入器。不同内容、同名普通目录、跨宿主嵌套目标、源与目标重叠、重解析点均会阻止恢复。重复恢复应全部显示相同；每次 `apply` 使用新回执文件。

Claude Code 的系统级注册单独处理。先在计划中明确加入，再用有权限的 PowerShell 执行；不要同时把同一批钩子复制进用户 `settings.json`，否则可能重复执行：

```powershell
python .\host-migration\tools\restore.py plan --layout D:\MigrationPrivate\layout.json --hosts claude_code --managed
python .\host-migration\tools\restore.py apply --layout D:\MigrationPrivate\layout.json --hosts claude_code --managed --receipt D:\MigrationPrivate\restore-claude-managed.json
```

Claude 的 managed-settings 可能由企业管理员管理；若已有不同内容，保留它并由该配置的 Owner 合并，恢复工具不会绕过。当前 [Claude 官方配置说明](https://code.claude.com/docs/en/settings) 与 [Hooks 说明](https://code.claude.com/docs/en/hooks) 是新机行为核对入口。Codex 的用户/项目配置层次见 [OpenAI 官方说明](https://learn.chatgpt.com/docs/config-file/config-basic)。

## 恢复启动器和模型服务源码

以下组件可以逐项选择，也可合并：`launcher`、`adapter`、`ccs_mcp`、`codexpp_source`、`codexpp_tweaks`。它们仅复制文件，不安装依赖、不注册服务、不启动网络监听：

```powershell
python .\host-migration\tools\restore.py plan --layout D:\MigrationPrivate\layout.json --support launcher,adapter,ccs_mcp,codexpp_source,codexpp_tweaks
python .\host-migration\tools\restore.py apply --layout D:\MigrationPrivate\layout.json --support launcher,adapter,ccs_mcp,codexpp_source,codexpp_tweaks --receipt D:\MigrationPrivate\restore-support.json
```

随后按依赖顺序接手，不要用本包旧版路径操作原机：

1. 安装官方 Codex 与 Claude Code，重新登录；普通 Codex 保持官方账号模式。
2. 要使用 Codex++ 时，在恢复出的 `codexpp_source` 目录查看其 README 与 package.json，使用该项目的 lockfile 安装项目依赖、构建并安装；不要全局安装 Python 包。现有安装器需要生成 runtime、原生工具及 Store 应用镜像，本包不分发 WindowsApps 程序。再核对恢复出的启动器 `AGENTS.md` 和隔离基线，使用 `Start-CodexPlusPlus-Proxy.cmd`，不能把仓库根简化启动脚本当作正式隔离入口。
3. Codex++ 的外层 Profile、嵌套 CODEX_HOME、runtime、OpenCLI 目录按恢复出的 `Assert-CodexPlusPlusProfileRootContract.ps1` 验证；所需目录由原有安装/启动入口准备，禁止伪造业务证据。安装器写过配置后，重新 `plan` 看差异，由 Owner 合并所需内容，不强制覆盖。
4. 要使用三方模型时，先安装和配置 CodexManager/CC Switch 的实际账号。现有 Codex 适配器监听 `127.0.0.1:15740` 并转发至 `127.0.0.1:48760`；Claude 的环境与实际服务选择从其独立 settings 读取。Token 通过本机环境传入，不提交到仓库。服务先以前台方式验证，再按恢复出的既有安装脚本选择单一服务 Owner，确认端口无占用后注册；本包不会恢复旧服务或计划任务。
5. 插件与原生计算机工具通过各宿主重新安装/连接；应用管理的 marketplace、Node 管道、可信摘要和 OAuth 不复用旧值。源码包中未包含的二进制资源由上述安装入口提供。

Codex++ 网关凭据使用 `CODEXPP_GATEWAY_TOKEN`；原有 actor 路由头通过 `env_http_headers` 绑定 `CODEXPP_ACTOR_AUTHORIZATION`，需要该路由时提供完整请求头值。两者分别配置，不能把一个凭据猜作另一个。对应字段由 [OpenAI 官方配置参考](https://learn.chatgpt.com/docs/config-file/config-reference) 支持；实际账号与模型仍需在新机验证。

Claude 的用户 MCP 注册采用 Claude 原生入口。先接手 CCS/CodeGraph 的实际工具与账号，再查看恢复后的 `.claude\mcp-servers.json`。使用 `claude mcp add-json --scope user <名称> '<该名称的 JSON 定义>'` 逐项导入；遇到已有同名服务先核对，不能覆盖。文件保存本身不等于已注册或服务可用。CCS 服务需要的私密 Provider 配置与 CodeGraph 可执行文件，由它们各自的现有安装入口提供。

迁移包保存了现有权限偏好，没有替新机签发任务权限。Hook 信任由宿主在新机重新核对，不能用旧 `trusted_hash` 跳过。`model_instructions_file` 的旧文件只作为审查输入，恢复默认使用宿主内置指令与各自全局提示词。

## 验收、私密数据与回退

完成配置恢复后至少验证：三个启动入口读取各自目录；各宿主能发现并实际采用所选技能；SessionStart 钩子在自己的目录运行；普通 Codex 没有被切到 Codex++ 网关；Claude 钩子只执行一次。再分别跑一个轻量工具调用。模型网关、插件账号和真实业务场景只有在新机实际运行后才能声明可用。

本包自带测试在临时用户目录验证三宿主隔离、路径带空格/中文、钩子执行、全量清单、秘密排除、碰撞阻断、幂等与回退。源机隔离演练不等于另一台物理电脑已验收；在线账号、软件安装、提权注册和业务恢复仍在目标机验证。

需要旧记忆/聊天/自动化时，保留三宿主各自的私密备份。数据库需一致性备份，不能在应用运行中只复制主 SQLite 文件；登录态可能绑定原机。自动化的目录、模型和绑定会话在新机重新核对，默认不激活旧定时任务。日志和业务 Evidence 按本域 Owner 原有归属保留，不复制到 General。

恢复工具的回退只删除本次创建且仍保持原内容的文件与原 Junction，不动既有文件，也不递归删除源目录；用户已经修改的文件会被保留并停止回退：

```powershell
python .\host-migration\tools\restore.py rollback --receipt D:\MigrationPrivate\restore-support.json
python .\host-migration\tools\restore.py rollback --receipt D:\MigrationPrivate\restore-claude-managed.json
python .\host-migration\tools\restore.py rollback --receipt D:\MigrationPrivate\restore-hosts.json
```

回退不撤销你另行执行的应用安装、服务注册、账号登录或业务操作，这些由其原有入口处理。回执保存在本机私密目录，不入 Git。

## 后续更新这个包

源配置只读采集，先复制 `source-layout.example.json` 到仓库外并填写本次明确授权的真实来源与路径映射；不要扫描猜测其他 Profile。运行 `tools/export.py --sources <私密来源清单>` 更新导出，再运行本包测试和 `tools/restore.py seal`、`verify`。导出器仅清理旧 manifest 精确列明且不再产出的生成文件，不清空目录。它不会修改任何源宿主文件。

测试前先 `seal`，再设置 `HOST_MIGRATION_GENERAL_ROOT` 为本次已经核对的 General clone；测试会在系统临时目录创建独立用户与 Profile，实际调用原有技能发布入口和三宿主钩子，结束时回退。可用 `python -m unittest discover -s .\host-migration\tools -p test_migration.py -v` 执行。不要把测试临时目录放在源码仓库或现有宿主目录内部，源与恢复目标的重叠会被拒绝。

`review-only` 内容、General 差异副本和第三方基础提示词仍是待审材料；归档不代表启用。更新后审阅 staged diff、凭据扫描及私密数据排除结果，提交推送并核对远端。该包不拥有 Agent 调度、OS 选择或运行时状态。
