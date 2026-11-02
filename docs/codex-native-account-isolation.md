---
domain: codex-isolation
tier: L2
doc_status: active-reference
description: 原生 Codex 账号直连与 Codex++ CM 中转的隔离契约、故障还原、新机部署与验收
related:
  - ../README.md
  - ../scripts/codex_isolation.py
  - ../host-migration/README.md
---

# 原生 Codex 与 Codex++ 隔离整改及新机部署

## 0. 结论先行

两套 Codex 必须使用两套物理目录、两套登录态和两条网络路径：

- **原生 Codex**：`CODEX_HOME=%USERPROFILE%\.codex`，只使用 ChatGPT 账号直连，配置中不得出现 `model_provider = "cm"`、`[model_providers.cm]`、`48760` 或 CM 的 `gateway-models.json`。
- **Codex++**：`CODEX_HOME=<Codex++Profile>\AppData\Roaming\Codex\.codex`，继续使用 CodexManager 中转 `http://127.0.0.1:15740/v1`，保留 `model_provider = "cm"`。
- **CodexManager**：活动 profile 只能是 Codex++；原生 profile 必须保持 `unmanaged`，不得保留 48760 gateway marker。
- **凭据**：不要让 CodexManager 账号池再次登记原生 ChatGPT 账号；Codex++ 应使用独立账号/API Key。两套 `auth.json`、Token、Cookie、CodexManager 数据库都不入库、不互拷。

只读自检：

```powershell
python scripts/codex_isolation.py audit
```

完整验收（会发起一次真实模型请求，消耗账号额度）：

```powershell
python scripts/codex_isolation.py verify --probe
```

## 1. 症状与根因

本次现场（2026-11-02）出现的组合症状：

1. 原生 Codex 界面显示的是 ChatGPT 账号登录，但 `config.toml` 同时存在：
   - `model_provider = "cm"`
   - `model_catalog_json = ...\codexmanager.desktop\codex-profiles\...\gateway-models.json`
   - `[model_providers.cm]`，`base_url = http://localhost:48760/v1`
   - `requires_openai_auth = true`
   - `experimental_bearer_token = <CM token>`
2. 原生账号的 refresh token 已被吊销，真实请求返回 `token_revoked`，但 `codex login status` 仍可能显示 `Logged in using ChatGPT`，容易误判。
3. CodexManager 的 `app_settings` 中保存了原生目录 `%USERPROFILE%\.codex` 的 gateway profile 状态，并在 `codex-profiles\<hash>\profile.json` 留下 48760 gateway marker。

根因不是 Codex++ 本身，而是 **CodexManager 把原生 `~/.codex` 当成可接管 profile 写入了 CM provider**。因此只删除界面登录态或只重启客户端都不够，必须同时清理配置、CodexManager 原生 state/marker 和原生历史 provider。

## 2. 隔离契约

| 项目 | 原生 Codex | Codex++ |
|---|---|---|
| 配置根 | `%USERPROFILE%\.codex` | `<Codex++Profile>\AppData\Roaming\Codex\.codex` |
| `model_provider` | 不设置（官方账号直连） | `"cm"` |
| 网关 | 无，直连 ChatGPT 后端 | `http://127.0.0.1:15740/v1` |
| 模型目录 | 使用应用内置官方目录 | `model_catalog.json` 或 CodexManager 模型目录 |
| 凭据 | 原生 ChatGPT OAuth 登录 | `CODEXPP_GATEWAY_TOKEN` / CodexManager 账号池或 API Key |
| 启动方式 | 官方 Codex 桌面端/CLI | Codex++ 专用启动器 |
| 历史 provider | `openai` | `cm`（仅 Codex++ 历史） |
| 禁止事项 | 不写 CM provider、不指向 48760 | 不接管原生目录、不写原生 `auth.json` |

CodexManager 侧的红线：

- 不要把原生 `~/.codex` 选为 CodexManager 的活动 profile。
- 不要对原生目录执行“应用 gateway / 接管原生 Codex”。
- 原生 profile 状态保持 `unmanaged`，并确保 `codex-profiles\<hash>\profile.json` 中没有 48760 marker。
- CodexManager 账号池不要重复登记原生 ChatGPT 账号；Codex++ 用独立账号或独立 API Key。

## 3. 本次整改步骤

### 3.1 备份

修改前备份原生配置、CodexManager 原生 profile 状态/marker、原生线程索引和会话文件。备份放在仓库外的私密目录，例如：

```text
%USERPROFILE%\.codex\restore-backup-<timestamp>\
```

本次现场备份目录为 `%USERPROFILE%\.codex\restore-backup-20261102-101508`（仅本机保留，不入库）。

### 3.2 移除原生 CM 配置

从 `%USERPROFILE%\.codex\config.toml` 移除：

- `model_provider = "cm"`
- 指向 `gateway-models.json` 的 `model_catalog_json`
- `[model_providers]` / `[model_providers.cm]` / `[model_providers.cm.http_headers]`

保留 `model`、`model_reasoning_effort`、插件、MCP、项目信任和 hooks 配置。

### 3.3 解除 CodexManager 对原生目录的接管

- `app_settings['codex_profile.state']` 中 `profileDir` 指向原生目录的项改为 `mode = "unmanaged"`，清空 `apiKeyId`、`gatewayBaseUrl`、`providerId` 等 CM 字段。
- 删除原生 profile 的 48760 `profile.json` marker（先备份）。
- 不修改 `app_settings['codex_profile.codex_home']`；该值应继续指向 Codex++。

### 3.4 对齐原生历史

- `state_5.sqlite` 的 `threads.model_provider`：`cm` → `openai`。
- `sessions/**/*.jsonl` 与 `archived_sessions/**/*.jsonl` 的 `session_meta.payload.model_provider`：`cm` → `openai`。
- 备份后再改；应用运行中建议先退出原生 Codex。

### 3.5 重新登录原生账号

原生 token 被吊销时，仅改配置不够，需要重新做 ChatGPT 账号登录：

```powershell
codex login --device-auth
```

若 `codex` 不在 `PATH`，使用官方 Codex CLI 的完整路径；审计/验证脚本会自动探测 `%LOCALAPPDATA%\OpenAI\Codex\bin\*\codex.exe`。按提示打开 `https://auth.openai.com/codex/device` 并输入一次性代码。**在 `auth.json` 落盘前不要终止登录进程**，否则会出现“浏览器显示已登录、CLI 仍是 Not logged in”的假象。

### 3.6 本次现场验收

| 检查 | 结果 |
|---|---|
| 原生 `config.toml` | 无 `cm`、无 48760、无 `gateway-models.json`、无 bearer token |
| 原生登录 | `Logged in using ChatGPT` |
| 原生真实请求 | `codex exec` 返回 `OK` |
| 新会话 provider | `openai` |
| 原生线程索引 | 全部 `openai`，0 条 `cm` |
| 原生会话文件 | 0 个 `cm` |
| Codex++ 配置 | 仍为 `model_provider = "cm"`、`base_url = http://127.0.0.1:15740/v1` |
| CodexManager 活动 profile | Codex++ |
| CodexManager 原生 state | `unmanaged` |
| CodexManager 原生 marker | 已移除 |

`scripts/codex_isolation.py audit` 现场结果为 9 项全 PASS；`verify --probe` 为 10 项全 PASS。

## 4. 新电脑部署顺序

### 4.1 先装原生 Codex，保持官方账号模式

1. 安装官方 OpenAI Codex，使用官方账号登录。
2. 确认真实 `CODEX_HOME` 是 `%USERPROFILE%\.codex`。
3. 不要从旧机复制 `auth.json`；在新机重新登录。
4. 不要导入 CodexManager 的 48760 配置、`gateway-models.json` 或 CM token。
5. 运行一次原生 Codex，使应用生成自己的配置目录。

此时先跑审计；Codex++ 尚未安装时，Codex++ 项会显示 WARN/SKIP：

```powershell
python scripts/codex_isolation.py audit --native-home "$env:USERPROFILE\.codex"
```

### 4.2 再装 Codex++，固定使用 15740 中转

1. 使用独立的 Codex++ Profile 根目录，例如 `D:\CodexPlusPlusProfile`。
2. 其 `CODEX_HOME` 固定为 `<Codex++Profile>\AppData\Roaming\Codex\.codex`。
3. 配置必须保留：

```toml
model_provider = "cm"

[model_providers.cm]
name = "CodexManager"
base_url = "http://127.0.0.1:15740/v1"
wire_api = "responses"
env_key = "CODEXPP_GATEWAY_TOKEN"
supports_websockets = false
```

4. 在 CodexManager 中选择 Codex++ profile 作为活动 profile。
5. **不要**在 CodexManager 中对原生 `~/.codex` 点击“接管 / 应用 gateway”。
6. Codex++ 的账号/API Key 与原生 ChatGPT 账号分开；不要把原生账号加入 CodexManager 账号池。

### 4.3 两侧一起验收

```powershell
python scripts/codex_isolation.py audit --require-codexpp
python scripts/codex_isolation.py verify --probe
```

`verify --probe` 会从原生 `CODEX_HOME` 发起一次最小 `codex exec` 请求，并检查新 session 的 `model_provider` 是否为 `openai`。如果它返回 `cm` 或 `token_revoked`，不要继续，按第 5/6 节排查。

## 5. 一键审计与修复

脚本：`scripts/codex_isolation.py`，需要 Python 3.11+，仅使用标准库；Windows 下可用 `python` 或 `py -3` 调用。

### 5.1 只读审计

```powershell
python scripts/codex_isolation.py audit
```

默认路径：

- 原生：`%USERPROFILE%\.codex`
- Codex++：`C:\CodexPlusPlusProfile\AppData\Roaming\Codex\.codex`
- CodexManager：`%APPDATA%\com.codexmanager.desktop\codexmanager.db`

非标准路径显式传入：

```powershell
python scripts/codex_isolation.py audit `
  --native-home "$env:USERPROFILE\.codex" `
  --codexpp-home "D:\CodexPlusPlusProfile" `
  --codexmanager-db "$env:APPDATA\com.codexmanager.desktop\codexmanager.db"
```

### 5.2 预览修复

```powershell
python scripts/codex_isolation.py repair
```

默认只打印计划，不写文件。它只处理原生侧：

- 删除原生 `config.toml` 中的 CM provider/catalog/token 段；
- 把 CodexManager 原生 state 改为 `unmanaged`；
- 移除原生 48760 marker；
- 线程索引和 session 文件 `cm` → `openai`。

不会修改 Codex++ 的 config，也不会修改 Codex++ 的活动 profile。

### 5.3 执行修复

建议先退出原生 Codex。CodexManager 可以保持运行；若 state 写入被占用，关闭 CodexManager 后重试。

```powershell
python scripts/codex_isolation.py repair --apply `
  --backup-dir "D:\MigrationPrivate\codex-isolation-backup" `
  --receipt "D:\MigrationPrivate\codex-isolation-receipt.json"
```

- `--backup-dir` 必须是仓库外的私密目录；已存在时脚本会自动追加时间戳，避免覆盖旧备份。
- 备份包含 `config.toml`、CodexManager state/marker、`state_5.sqlite` 和受影响的 session 文件。
- 执行后脚本会再跑一次不含登录项的隔离检查；最后请重启原生 Codex 桌面端。
- 若原生登录已失效，再执行第 3.5 节的 `codex login --device-auth`。

### 5.4 完整验证

```powershell
python scripts/codex_isolation.py verify --probe
```

`--probe` 是可选项，会消耗一次账号额度；不带 `--probe` 时只做配置、DB、历史、登录状态和代理环境检查。

## 6. 手工验收清单

如果不使用脚本，至少核对以下内容。

### 6.1 原生配置

```powershell
$native = "$env:USERPROFILE\.codex\config.toml"
Select-String -Path $native -Pattern 'model_provider|model_providers|48760|gateway-models|experimental_bearer_token'
```

期望：没有任何输出。

### 6.2 Codex++ 配置

```powershell
$cpp = "C:\CodexPlusPlusProfile\AppData\Roaming\Codex\.codex\config.toml"
Select-String -Path $cpp -Pattern 'model_provider = "cm"|15740|CODEXPP_GATEWAY_TOKEN'
```

期望：三项都能命中。Codex++ 不应被“还原原生”操作改动。

### 6.3 原生登录

```powershell
& "<官方 Codex CLI 路径>\codex.exe" login status
```

期望：`Logged in using ChatGPT`。注意：吊销的 token 也可能短暂显示已登录，最终以 `verify --probe` 的真实请求为准。

### 6.4 历史 provider

```powershell
python -c "import os, sqlite3; p=os.path.join(os.environ['USERPROFILE'], '.codex', 'state_5.sqlite'); c=sqlite3.connect(p); print(c.execute('select model_provider,count(*) from threads group by model_provider').fetchall())"
```

期望：只出现 `openai`，不出现 `cm`。

### 6.5 CodexManager

在 CodexManager 界面确认：

- 活动 profile 是 Codex++，不是原生 `~/.codex`；
- 原生 profile 状态是未接管/`unmanaged`；
- 原生目录下没有 48760 gateway marker。

## 7. 常见故障

### 7.1 `token_revoked`

现象：浏览器已完成登录，但 CLI 报 `refresh token was revoked`，或 `auth.json` 不存在。

处理：

1. 确认登录进程仍在运行，不要提前结束；
2. 重新执行 `codex login --device-auth`；
3. 在 `auth.json` 出现且包含 `tokens.refresh_token` 后，再执行 `codex login status`；
4. 重启原生 Codex 桌面端；
5. 再跑 `python scripts/codex_isolation.py verify --probe`。

### 7.2 CodexManager 又把原生配置写回 CM

现象：`audit` 再次报 `model_provider=cm` 或 48760 marker。

处理：

1. 关闭 CodexManager；
2. `python scripts/codex_isolation.py repair --apply ...`；
3. 打开 CodexManager，确认原生 profile 不再被选中/接管；
4. 再启动原生 Codex，重新 `audit`；
5. 若仍被回写，检查 CodexManager 的“接管原生 Codex”类入口是否被启用，并保持关闭。

### 7.3 Codex++ 自己连不上

不要用“把原生也切到 CM”来解决。依次检查：

- CodexManager 是否在 `127.0.0.1:15740` 监听；
- Codex++ 的 `CODEXPP_GATEWAY_TOKEN` 是否存在；
- Codex++ `config.toml` 是否仍是 `cm`/15740；
- CodexManager 活动 profile 是否仍是 Codex++。

### 7.4 同一 ChatGPT 账号互相影响

原生登录和 CodexManager 账号池登记同一个 ChatGPT 账号时，任一侧的重新认证、刷新或账号安全操作都可能影响另一侧。要求凭据级隔离时：

- Codex++ 使用独立账号或独立 API Key；
- 从 CodexManager 账号池移除原生账号；
- 不要把原生 `auth.json` 导入 CodexManager。

## 8. 回滚

脚本备份目录结构：

```text
<backup-dir>\
├── config.toml
├── codexmanager-codex-profile-state.json
├── codexmanager-markers\<hash>\profile.json
├── state_5.sqlite
├── sessions\<相对路径>.jsonl
└── receipt.json
```

回滚步骤：

1. 退出原生 Codex 和 CodexManager；
2. 将 `config.toml`、`state_5.sqlite`、session 文件复制回原生目录；
3. 将 CodexManager state/marker 备份恢复到 `codexmanager.db` 与 `codex-profiles`；
4. 重启应用；
5. 运行 `python scripts/codex_isolation.py audit` 确认回滚后的状态。

回滚是人工操作；脚本不会自动删除用户后来产生的新会话或新配置。

## 9. 安全边界

- 不把 `auth.json`、`*.sqlite`、`codexmanager.db`、`gateway-token`、`CODEXPP_GATEWAY_TOKEN`、真实 `experimental_bearer_token` 提交到 Git。
- 不把备份目录放在仓库内。
- 脚本不会打印 Token 原文；审计只报告字段是否存在。
- `verify --probe` 会消耗账号额度，默认关闭。
- 脚本不安装 Codex/Codex++/CodexManager，不配置代理，不注册服务，不自动登录。

## 10. 残余风险

本次整改完成了配置、CodexManager 原生接管状态、历史 provider 和登录态的隔离，但 CodexManager 账号池仍可能登记同一个 ChatGPT 账号。只要两侧共用同一账号的登录凭据，就仍存在账号级联动风险。要彻底隔离，必须让 Codex++ 使用独立账号/API Key，或从 CodexManager 账号池移除原生账号；配置层隔离不能替代凭据层隔离。
