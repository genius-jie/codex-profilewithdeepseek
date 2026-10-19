---
domain: host-migration-models
tier: L2
doc_status: active-reference
birth_ceremony_id: project-host-model-setup-20261019
related:
  - ../README.md
  - model-check.example.json
  - cc-switch-provider-reference.json
  - ../tools/check_models.py
  - ../payload/codex_plus_plus/model_catalog.json
---

# 在新电脑上接通 DeepSeek、千问、Kimi 和 GLM

本页从“已恢复宿主文件”继续，完成上游账号、模型路由、客户端选择与调用验收。完成条件是目标模型能够接收请求、发出工具调用，并在收到真实工具结果后继续回答。模型出现在下拉框、健康接口返回成功，只分别证明目录和服务可达。

这里复用当前已有的 CodexManager、CC Switch、CodexIdSanitizer 与 CcSwitchSanitizerSupervisor，不创建第二套模型路由器。模型 ID 来自源机当前模型与路由登记，账号权限、余额、上游版本和供应商可用性仍由新机实际账号决定。主迁移工具不会代填秘密，也不会自动切换原机正在使用的供应商。

## 先理解两个使用入口

| 使用者 | 新机请求经过哪里 | 在哪里切换模型 |
|---|---|---|
| Codex++ | Codex++ → `127.0.0.1:15740/v1` → CodexManager `127.0.0.1:48760` → 被选模型的上游 | Codex++ 会话模型选择器；CodexManager 中为各模型启用正确路由 |
| Claude Code | Claude Code → CC Switch 原生代理 `127.0.0.1:15733` → 当前供应商；千问/GLM 5.2 供应商再经过各自适配端口 | 先在 CC Switch 启用供应商，再开 Claude Code 新会话；需要时用 `/model` 选择该供应商已经配置的模型 |
| 普通 Codex | 默认保留官方账号和自己的配置目录 | 默认继续使用官方模型；若明确要接第三方，采用本页的自定义 provider 配置，但只写普通 Codex 自己的用户配置，认证与 Codex++ 分开 |

不要把 `15740`、`48760`、`15733` 当作系统 HTTP 代理端口填入 Clash 或 Windows 代理设置。Codex++ 与普通 Codex 的用户目录、认证缓存和 Electron 数据目录仍按主指南隔离。

## 安装和准备顺序

1. 按主指南安装目标宿主，恢复其配置、钩子、技能及 `-WithSupport` 源码。安装器写出的初始配置若与恢复模板冲突，先查看差异并保全原文件，由 Owner 合并；恢复工具不会强制覆盖。
2. 安装 Node.js 20+ 和 PowerShell 7。准备 CodexManager、CC Switch；使用自己的账号/供应商地址和 Key。Windows 常驻服务需要 NSSM 和管理员权限；首次连通也可以先以前台方式运行源码，无须先注册服务。
3. 在 CodexManager 桌面管理界面完成上游供应商和模型路由；在 CC Switch 完成 Claude 供应商与原生代理设置。
4. 运行下面列出的正式适配入口。先确认端口与服务 Owner，再开始注册或启动；已有不同 Owner 时先核对，不覆盖或同时启动第二份。
5. 按宿主逐个选择模型并验收，完成后再设置 CodexManager/CC Switch 自己的开机启动。后台适配仍由现有两个服务分别管理。

本次源机的软件基线为 CodexManager `0.6.3`、CC Switch `4.0.4`。新机应使用具备本页模型路由与协议设置能力的对应版本，界面名称以实际安装版本为准；不要用早期安装包替代后续模型路由能力。

对应版本的下载入口：[CodexManager v0.6.3](https://github.com/qxcnm/Codex-Manager/releases/tag/v0.6.3)、[CC Switch v4.0.4](https://github.com/farion1231/cc-switch/releases/tag/v4.0.4)。先核对软件来源与版本，再使用自己的凭据接入；本次不在旧电脑执行安装或升级。

上游 API Key、上游地址中的私人部分、平台 Key、CC Switch 本机代理凭据都由本人在新机填写。它们不是同一种凭据，不要互相替换。若原来的供应商是聚合服务，继续使用该聚合服务给出的地址/Key；不要把聚合 Key 填到模型厂商官方地址。

## Codex++：先配置 CodexManager

在 CodexManager 的上游供应商/聚合 API 设置中添加自己实际使用的服务，填写其 OpenAI 兼容基础地址及上游 Key，先执行管理软件提供的连通或模型发现。每个供应商保存自己的认证，原机的数据库和供应商 ID 不直接导入新机。

源机这些模型的来源类型是 CodexManager 的聚合 API `provider_type=codex`。这是 CodexManager 自己的来源类型；Claude 的 `openai_chat` 则是 CC Switch 的协议格式字段，两者不要混填。

随后在模型管理/模型路由设置中逐项确认：

| 模型系列 | 源机已登记的精确 ID | 初次建议验收 |
|---|---|---|
| DeepSeek | `deepseek-v4-pro`、`deepseek-v4-flash`、`deepseek-v4.1-flash` | `deepseek-v4-pro` |
| 千问 | `qwen3.8-max`、`qwen3.8-flash`、`qwen3.8-max-0902` | `qwen3.8-max` |
| Kimi | `kimi-k3`、`kimi-k2.7-code` | `kimi-k3` |
| GLM | `glm-5.2`、`glm-5.3`、`glm-5.3-flash` | `glm-5.3-flash` |

每一行的客户端模型 ID 必须有一条**启用的**路由，指向新机真实可用的供应商，并填写该供应商接受的上游模型 ID。源机千问使用 A2Agent 的启用路由，另一个同名来源已停用；新机也应明确选定有权限的来源，避免错误负载分流。上游没有某个 ID 时，按真实服务提供的映射设置，不能只在客户端目录里新增一个名字。

在 CodexManager 创建给 Codex++ 使用的平台 Key，并允许它访问上述目标模型/模型组。源机平台 Key 的模型绑定为空，按请求里的 `model` 路由；新机需要同样的“随请求选择模型”能力时，不要把 Key 固定到 GPT 或单一模型。上游 Key 留在 CodexManager，客户端只持有平台 Key。

## 启动适配服务

假设已恢复的适配目录是新用户下的 `.cc-switch\sanitizer`。先用一个前台 PowerShell 7 启动 Codex 适配器：

```powershell
$AdapterRoot = Join-Path $env:USERPROFILE '.cc-switch\sanitizer'
$env:CODEX_SANITIZER_NODE = (Get-Command node.exe).Source
& (Join-Path $AdapterRoot 'start-codex-id-sanitizer.ps1')
```

它应监听 `127.0.0.1:15740`，上游为本机 CodexManager `48760`。打开另一个终端检查 `/health`，核对适配版本与当前恢复源码；还要使用平台 Key 访问 `/v1/models`。CodexManager 的普通 `/health` 在不同版本可能不是 JSON，不能据此推断模型网关不可用。

Claude 的兼容子进程只由下面这一个现有 supervisor 启动：

```powershell
$AdapterRoot = Join-Path $env:USERPROFILE '.cc-switch\sanitizer'
$env:CC_SWITCH_SANITIZER_NODE = (Get-Command node.exe).Source
# 如果使用别的上游，在本机明确填写下面两个环境变量；默认保留源机 A2Agent 路由。
# $env:CC_SWITCH_QWEN_UPSTREAM = 'https://YOUR_OPENAI_COMPATIBLE_UPSTREAM'
# $env:CC_SWITCH_GLM_UPSTREAM = 'https://YOUR_OPENAI_COMPATIBLE_UPSTREAM'
& (Join-Path $AdapterRoot 'start-cc-switch-sanitizer-supervisor.ps1')
```

| 监听 | 现有 Owner / 用途 |
|---|---|
| `15740` | CodexIdSanitizer：Codex Responses、工具调用、远程压缩适配 |
| `15733` | CC Switch 自己的 Claude 代理及 OpenAI Chat → Anthropic 协议转换 |
| `15727` | supervisor 的千问子进程，上游默认 A2Agent |
| `15726` | supervisor 的 GLM 5.2 子进程，上游默认 A2Agent |
| `15735` | supervisor 的可选 DeepSeek 思考流过滤，转到 `15733` |
| `15728` / `15729` | supervisor 保留的 Codex/Claude 兼容路径；不是本次四厂商首次配置的必选路径 |
| `15722` | 现有 ReadToolSanitizer 的 CodexManager 兼容入口；仅在相应 Claude 供应商明确采用时启动 |

不要同时运行 `start-qwen-request-sanitizer.ps1`、`start-glm-request-sanitizer.ps1`、旧 watcher 和 supervisor；旧独立千问脚本保留了历史上游地址，不作为本页的新机启动入口。也不要为 supervisor 的每个子进程再注册一份独立服务。

前台验收后，如需开机运行，在**管理员 PowerShell 7**中调用原有两个安装入口：

```powershell
& (Join-Path $AdapterRoot 'install-codex-id-sanitizer-nssm.ps1')
& (Join-Path $AdapterRoot 'install-cc-switch-sanitizer-supervisor-service.ps1')
Get-Service CodexIdSanitizer,CcSwitchSanitizerSupervisor
```

本迁移包的导出模板使用新机选定的绝对 PowerShell 7 路径，修正了从 PowerShell 7 的 `$PSHOME` 拼出不存在的 `powershell.exe` 的问题。NSSM 先从当前 PATH 查找，再尝试 System32 的既有位置；先让管理员终端的 `Get-Command nssm.exe` 能找到自己的安装。安装后仍需核对 NSSM Application、AppParameters、AppDirectory、Node 路径及真实监听；注册脚本返回成功不能代替实际端口和调用结果。

服务进程的环境不等于用户终端环境。Node 不在系统路径时，在对应 NSSM 服务的 Environment 页面 / `AppEnvironmentExtra` 填写 `CODEX_SANITIZER_NODE` / `CC_SWITCH_SANITIZER_NODE` 的实际绝对路径。千问/GLM 使用自定义上游时，也把 `CC_SWITCH_QWEN_UPSTREAM` / `CC_SWITCH_GLM_UPSTREAM` 配置到 supervisor 服务环境；只在前台终端赋值不会自动传给服务。编辑时保留已有环境条目，再由该服务 Owner 重启并重新验收。

迁移模板默认不复用原机 DeepSeek 的供应商 UUID，也不因此改写新机 Claude 设置。`15735` 的旧式自动设置不是本页必选步骤；若确实需要，由 Owner 同时核对 CC Switch 的正确 ID、服务运行用户及其配置路径，再配置 `CC_SWITCH_DEEPSEEK_PROVIDER_ID`。未设置时这项自动改写保持关闭。

## Codex++：填客户端配置并选模型

确认以下内容位于 **Codex++ 自己**的 `CODEX_HOME/config.toml`。`model_catalog_json` 填主指南恢复出来的实际绝对路径：

```toml
model_provider = "cm"
model = "deepseek-v4-pro"
model_catalog_json = 'D:\CodexPlusPlusProfile\AppData\Roaming\Codex\.codex\model_catalog.json'
model_auto_compact_token_limit = 160000

[model_providers.cm]
name = "OpenAI"
base_url = "http://127.0.0.1:15740/v1"
wire_api = "responses"
env_key = "CODEXPP_GATEWAY_TOKEN"
supports_websockets = false

[model_providers.cm.env_http_headers]
x-openai-actor-authorization = "CODEXPP_ACTOR_AUTHORIZATION"
```

通过本机私密环境提供 `CODEXPP_GATEWAY_TOKEN`。若所用网关路由需要 actor 请求头，再提供 `CODEXPP_ACTOR_AUTHORIZATION` 的完整值。桌面快捷方式启动的进程不一定继承另一个终端中刚设置的环境变量，必须从实际启动入口核对。不要将真实 Key 粘入本仓 TOML 或提交记录。[OpenAI provider 配置参考](https://learn.chatgpt.com/docs/config-file/config-reference)、[网关接入说明](https://learn.chatgpt.com/docs/enterprise/connect-to-a-gateway)。

在**新电脑自己的 PowerShell 7**中，可用下面的方法隐藏输入并保存 Codex 凭据。它只写本机当前用户和当前进程的环境，不写仓库或机器级环境；普通 Codex 如需第三方接入，使用它自己的变量名和 Key。

```powershell
function Set-PrivateCodexVariable {
  param([ValidateSet('CODEXPP_GATEWAY_TOKEN','CODEXPP_ACTOR_AUTHORIZATION','CODEX_GATEWAY_TOKEN','CODEX_ACTOR_AUTHORIZATION')][string]$Name)
  $privateSecret = Read-Host "$Name（输入隐藏）" -AsSecureString
  try {
    $privateValue = [System.Net.NetworkCredential]::new('', $privateSecret).Password
    if ([string]::IsNullOrWhiteSpace($privateValue)) { throw '凭据不能为空' }
    [Environment]::SetEnvironmentVariable($Name, $privateValue, 'User')
    [Environment]::SetEnvironmentVariable($Name, $privateValue, 'Process')
  } finally {
    $privateValue = $null
    $privateSecret.Dispose()
  }
}
Set-PrivateCodexVariable CODEXPP_GATEWAY_TOKEN
# 仅当自己的网关需要 actor 请求头时，再执行：
# Set-PrivateCodexVariable CODEXPP_ACTOR_AUTHORIZATION
```

保存后退出 Windows 当前用户并重新登录，再从正式隔离快捷方式启动 Codex++，让桌面进程取得新环境。凭据只留在新机；不要把本机环境或注册表导出提交到仓库。Claude 的凭据继续由 CC Switch 管理，无须把 `ANTHROPIC_AUTH_TOKEN` 设为全局用户环境。

新机如果需要 API Key 登录引导，先确认当前命令的 `CODEX_HOME` 只指向 Codex++，再按 `codex login --help` / [官方认证说明](https://learn.chatgpt.com/docs/auth) 通过标准输入提供平台 Key。登录记录仅留本机；普通 Codex 的官方 OAuth 不参与复制、删除或改写。

用正式隔离启动器启动 Codex++，新建会话后打开模型选择器，逐个选择上表已经完成路由的模型。模型不存在时先核对当前配置指向的目录文件、精确 slug 和网关认证模型列表，不运行仓库根早期的 `Sync-ModelCatalog.ps1` 覆盖正式目录。

这里的 160k 是初次接入的保守压缩基线，避免沿用部分目录项的 900k 阈值直到网关请求超过字符限制。它不替代真实长会话测试，也不是对无限上下文的保证。图片能力同样按具体模型、当前上游与实际图片请求分别验收。

## Claude Code：在 CC Switch 配供应商

参考同目录 `cc-switch-provider-reference.json`，在 CC Switch 的 Claude 供应商编辑界面逐项填写。它是表单参考，不是 CC Switch 原生数据库/自动导入文件；`FILL_LOCALLY` 必须换成自己的实际值。

| 供应商 | API 格式 | 供应商基础地址 | 模型 ID |
|---|---|---|---|
| DeepSeek | OpenAI Chat Completions，`openai_chat` | 自己的 OpenAI 兼容上游地址 | `deepseek-v4-pro` |
| 千问 | OpenAI Chat Completions，`openai_chat` | `http://127.0.0.1:15727`；真实上游由 supervisor 指定 | `qwen3.8-max` |
| Kimi | OpenAI Chat Completions，`openai_chat` | 自己的 OpenAI 兼容上游地址 | 源机 Claude 配置为 `kimi-k2.7-code` |
| GLM Flash | Anthropic，`anthropic` | 自己供应商提供的 Anthropic 兼容地址 | `glm-5.3-flash` |
| GLM 5.2 兼容路径 | OpenAI Chat Completions，`openai_chat` | `http://127.0.0.1:15726` | `glm-5.2` |

Key 填对应的上游供应商凭据。把 Sonnet、Opus、Haiku 和本版本存在的 Fable/子代理模型字段映射到该供应商真正提供的模型；不要只修改显示名称。Codex++ 中的 Kimi K3 和源机 Claude 中的 Kimi 2.7 是不同配置，不能仅因同属 Kimi 就把 ID 互换。

启用 CC Switch 的 Claude 原生代理，监听本机 `15733`，然后激活一个供应商。CC Switch 会将 Claude 客户端指向自己的代理并完成对应格式转换。接管后的 `settings.json` 里可能保留 Claude 家族别名，界面名称也可能使用 `*_MODEL_NAME`；实际所用上游以当前供应商记录和请求日志为准。

本迁移流程只操作 CC Switch 的 **Claude 面板和 Claude 接管开关**。不要因此启用它对普通 Codex 的接管；Codex++ 的 provider/认证由隔离目录维护，普通 Codex 的官方配置保持独立。

**切换顺序是：CC Switch 激活供应商 → 新建 Claude Code 会话 → `/model` 选择已映射模型 → 做一次工具验收。** CC Switch 当前供应商是全局选择；验收脚本不会替你切换，也不会向当前 DeepSeek 供应商发送千问 ID 后就声称千问已经接通。[Claude 官方模型配置](https://code.claude.com/docs/en/model-config)、[CC Switch 项目说明](https://github.com/farion1231/cc-switch)。

## 普通 Codex 的边界

普通 Codex 默认继续官方账号模式。若本人明确要让它也接第三方，在它自己的用户级 `config.toml` 中采用上面的 provider/目录设置，并使用普通 Codex 自己的目录与认证；不要覆盖或链接到 Codex++ 的 auth、state 或 Electron Profile。第三方账号配置放用户级配置，不能只放项目 `.codex/config.toml` 期待其接管 provider。这里提供配置方法，不自动改变现有普通 Codex 的默认模式。

普通 Codex 若单独采用第三方接入，使用自己的平台 Key 和环境变量名，例如 `CODEX_GATEWAY_TOKEN` / `CODEX_ACTOR_AUTHORIZATION`，不要直接复制 Codex++ 的登录缓存。模型目录也放在普通 Codex 自己的目录内。

## 每个模型的实际验收

先把 `model-check.example.json` 复制到仓库外的私密配置目录，例如保存为用户目录下的 `.host-migration\model-check.local.json`，按本机实际端点调整。配置里只写凭据的**环境变量名**，不写凭据值。下面的 `$ModelCheckConfig` 必须指向你实际保存的文件。

在启动测试进程的私密环境里准备好平台 Key，再测试 Codex++ 的四个代表模型：

```powershell
$ModelCheckConfig = Join-Path $env:USERPROFILE '.host-migration\model-check.local.json'
python .\host-migration\tools\check_models.py --config "$ModelCheckConfig" --target codex_plus_plus --models deepseek-v4-pro,qwen3.8-max,kimi-k3,glm-5.3-flash --catalog D:\CodexPlusPlusProfile\AppData\Roaming\Codex\.codex\model_catalog.json --smoke
```

`--smoke` 会产生真实上游请求和用量。它逐个请求一个无参数的受限测试工具，实际读取本机临时测试文件，把结果回传给模型，并要求模型消费结果。它不执行模型生成的 shell/代码、不读取你的业务文件、不改变当前模型路由、不写配置或注册服务。输出只保留检查结论，HTTP 原始错误与凭据不会打印。

Claude 每次只验收 CC Switch 当前已经激活的一个供应商。下面以 DeepSeek 为例，从新机被 CC Switch 接管后的 Claude 设置中读取本机代理凭据到**当前测试进程**，不会显示它的值：

```powershell
$privateClaudeSettings = Get-Content (Join-Path $env:USERPROFILE '.claude\settings.json') -Raw | ConvertFrom-Json
$env:ANTHROPIC_AUTH_TOKEN = $privateClaudeSettings.env.ANTHROPIC_AUTH_TOKEN
python .\host-migration\tools\check_models.py --config "$ModelCheckConfig" --target claude_code --models deepseek-v4-pro --cc-switch-db "$env:USERPROFILE\.cc-switch\cc-switch.db" --smoke
```

再到 CC Switch 切换千问，开新会话，并将 `--models` 换成 `qwen3.8-max` 重跑；Kimi/GLM 同理。只读数据库检查会拒绝“当前供应商与所验收模型不同”的情况，不会输出供应商凭据。省略 `--smoke` 只能做发现/配置检查，不能获得调用成功结论。

若当前正在使用别的 Claude 供应商，不希望切换它，可先单独测试千问的供应商/适配入口。此时使用千问**上游 Key**，不是 CC Switch 的本机代理凭据：

```powershell
$privateQwenKey = Read-Host '千问供应商的上游 Key（输入隐藏）' -AsSecureString
try { $env:QWEN_UPSTREAM_API_KEY = [System.Net.NetworkCredential]::new('', $privateQwenKey).Password }
finally { $privateQwenKey.Dispose() }
python .\host-migration\tools\check_models.py --config "$ModelCheckConfig" --target openai_chat_provider --models qwen3.8-max --smoke
```

这个入口默认访问 `15727/v1`，从私密环境读取 `QWEN_UPSTREAM_API_KEY`，不更改 CC Switch 当前供应商。它只证明千问上游与对应适配的工具往返可用；Claude 完整会话仍需之后切换供应商验收。

最后在真实 Codex++ 和 Claude Code 各新建一个会话，让所选模型读取你创建的测试文本并复述其中的随机标记，确认实际工具执行、结果回传、持续回答。再验证自己需要的图片、推理档位、模型间切换和长会话压缩。协议探针通过与真实桌面/会话验收分别记录，未做的项目保持待验收。

## 问题发生时看哪里

| 现象 | 优先核对 |
|---|---|
| 下拉框没有模型 | 当前宿主的目录路径、精确 slug、是否已重开会话 |
| 有名字但 401/403 | 平台 Key / 上游 Key 用途、环境是否被实际启动进程继承、模型组权限 |
| 404 或 model not found | 原生供应商/路由里的真实上游 ID，不能以显示名称代替 |
| 工具参数错误或只说一句就停 | 15740 适配器版本、CC Switch API 格式、正确 provider 级适配端口 |
| `tool_choice` 与思考模式不兼容 | 使用正常客户端的自动工具选择，并核对模型确实调用工具；不要为探针强制选择工具而改变供应商推理设置 |
| 千问/GLM 返回内容类型错误 | 是否误运行旧独立脚本、是否把错误的官方地址与聚合 Key 混用 |
| Claude 切了模型仍像旧供应商 | CC Switch 当前供应商、新建会话、实际请求记录；不要只看角色别名 |
| 重启后连接失败 | 原生管理软件自启、服务 Owner、Node/PowerShell 物理路径及环境、端口占用 |
| 探针超时但配置没有报错 | 先看当前请求/队列和上游健康，待服务空闲后显式重试并保留初次失败；一次重试成功不代表长期稳定 |
| 聊很久压缩失败 | 真实请求大小、当前模型阈值、15740 的压缩分支和真实长会话证据 |

不要通过换密钥、删除聊天、改普通 Codex、重复注册服务或增加 watchdog 掩盖路由问题。修复继续归属原有管理软件、S34/S41 和现有适配入口。
