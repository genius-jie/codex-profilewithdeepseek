# Codex Profile with DeepSeek

> **三宿主换机入口**：当前普通 Codex、Codex++、Claude Code 的配置与提示词迁移，使用 [host-migration 接手说明](host-migration/README.md)。其中提供按宿主隔离的模板、钩子、专用技能、启动依赖、校验清单、统一新机入口与回退；下文的根目录配置和简化启动脚本保留为早期 Profile 示例，不代表当前三个宿主的完整运行配置。

> **基于 OpenAI Codex / Codex++ 架构的第三方大模型（DeepSeek、Qwen、Kimi）本地化工程 Profile 解决方案。**
> 借助本地反向代理网关（CodexManager / “可乐”），打破模型壁垒，在本地维护高效、高自主性、上下文超长的 Agent 开发执行环境。

[![GitHub License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Codex Ready](https://img.shields.io/badge/Codex-Compatible-success.svg)]()
[![Model DeepSeek-V4](https://img.shields.io/badge/Model-DeepSeek--V4--Pro-blueviolet.svg)]()

---

## 🌟 核心背景与设计理念

在日常全栈软件开发与复杂任务自动化中，OpenAI 官方 Codex 客户端及 CLI 工具拥有强大的环境感知能力与工具执行链条。然而，很多开发者在实际工程落地时面临以下挑战：

1. **官方模型成本与网络限制**：希望使用性价比更高、国内访问更稳定、数学推理与代码能力顶级的国产开源/商用模型（如 **DeepSeek-V4-Pro**、**Qwen-3.8-Max**、**Kimi-K3**）。
2. **三方模型直接接入 Codex 易崩溃**：
   - **字符数截断危机**：本地网关（CodexManager / CM）通常限制请求上限为 1,048,576 字符，若直接将上下文拉到 900k tokens，工具调用历史很容易突破字符上限导致网关直接 400/500 报错。
   - **工具调用字段漂移（Aborted 卡死）**：DeepSeek 等模型在进行系统命令调用时，历史常将 `exec_command` 的主要字段误写为 `command`（Codex 正确标准为 `cmd`），从而被前端或网关直接拦截抛出 `aborted`，导致 Agent 任务卡死中断。
3. **缺少统一工程治理体系**：缺乏开箱即用的测试驱动开发（TDD）、需求拆解、调试与代码审查技能闭环。

**本项目（Codex Profile with DeepSeek）正是为了彻底解决上述痛点而打造的工业级 Profile 配置体系。**

---

## 🧩 架构全景

```
+-------------------------------------------------------------+
|               开发者终端 / Codex 桌面端 (Codex++)            |
+-------------------------------------------------------------+
                              | (标准 OpenAI 协议)
                              v
+-------------------------------------------------------------+
|         本地转发网关: CodexManager (俗称“可乐” / CM)         |
|         监听地址: http://127.0.0.1:48760/v1 (或 15740)      |
+-------------------------------------------------------------+
                              |
        +---------------------+---------------------+
        |                                           |
        v                                           v
+-------------------------------+   +-------------------------------+
|  DeepSeek-V4-Pro (代码/推理)   |   |   Qwen / Kimi (多模态/大上下文) |
+-------------------------------+   +-------------------------------+
```

---

## 🚀 关键技术特性与独家优化

### 1. 深度适配 DeepSeek 专有上下文紧凑策略 (`model_catalog.json`)
针对网关 1MB 字符限制，我们在 `model_catalog.json` 中为 `deepseek-v4-pro` 配置了定制阈值：
- **最大上下文**：1,000,000 tokens
- **自动紧凑阈值 (`auto_compact_token_limit`)**：精准设定为 **160,000 tokens**。在工具调用历史膨胀到网关字符上限前平滑触发历史摘要与紧凑，永不爆字符！

### 2. S40 三方模型工具调用常驻防卡死契约 (`skills/S40...` & `AGENTS.md`)
- **字段名强校验**：强制 `cmd` 为唯一合法字段，严禁使用过期的 `command`。
- **探针机制**：会话建立时与长任务过程中自动注入轻量探针，实时检测参数字段是否发生漂移，保障数十轮自动编码开发流畅不中断。

### 3. 开箱即用的工程开发技能矩阵 (`skills/`)
集成专业级 Agent 开发辅助技能：
- **`S40_三方模型工具调用适配`**：防 aborted 卡死核心护城河。
- **`S34_Codex认证切换`**：官方账号模式与 CodexManager 本地代理模式一键切换。
- **`S11_测试驱动开发`**：红-绿-重构循环，杜绝虚假覆盖。
- **`S12_系统化调试`**：精准定位根因，基于日志与退出码物理排错。
- **`S13_代码审查` & `S14_完成前验证`**：严密的出栈质量卡点。

---

## 📂 目录结构说明

```
.codex/
├── config.toml                 # 核心运行配置（指向本地 CM 网关及模型参数）
├── config.example.toml         # 配置文件示例与说明
├── model_catalog.json          # 扩展模型元数据（含 DeepSeek、Qwen、Kimi 定义）
├── AGENTS.md                   # Agent 全局行为宪法与执行约束（SSOT）
├── .gitignore                  # 严防敏感凭证、私有会话数据库泄露
├── README.md                   # 架构与实战文档
├── scripts/
│   ├── Sync-ModelCatalog.ps1   # 模型目录同步与校验自动化脚本
│   └── Start-CodexWithProfile.ps1 # 一键绑定当前 Profile 启动脚本
└── skills/                     # 精选配套技能库
    ├── S40_三方模型工具调用适配/
    ├── S34_Codex认证切换/
    ├── S11_测试驱动开发/
    ├── S12_系统化调试/
    ├── S13_代码审查/
    └── ...
```

---

## 🛠️ 快速上手

### 步骤 1：准备前置依赖
1. 安装 **OpenAI Codex** 或 **Codex++** 桌面客户端/CLI；
2. 启动本地反向代理网关（如 **CodexManager**），确认其监听在 `127.0.0.1:48760`（可在设置中配置你的 DeepSeek API 密钥）。

### 步骤 2：配置 Profile
复制并调整 `config.toml`：
```toml
model = "deepseek-v4-pro"
model_provider = "cm"
model_catalog_json = "./model_catalog.json"

[model_providers.cm]
name = "OpenAI"
base_url = "http://127.0.0.1:48760/v1"
env_key = "CM_API_KEY"
api_key = "YOUR_API_KEY_OR_TOKEN"
```

### 步骤 3：一键启动与执行
使用自带的 PowerShell 启动脚本加载该 Profile：
```powershell
pwsh ./scripts/Start-CodexWithProfile.ps1
```
启动后，Codex 将自动识别并切换至 `DeepSeek-V4-Pro`，同时加载防漂移契约与本地开发流水线！

---

## 🔒 安全与脱敏规范

- **零密钥入库**：本项目坚决不在任何代码或配置文件中硬编码真实 API Key，全部采用环境变量或示例占位符；
- **纯净本地态**：会话数据库（`*.sqlite`）、临时运行缓存（`tmp/`）、敏感认证（`auth.json`）已被 `.gitignore` 完全排除，保障开源与共享安全。

---

## 📄 开源许可证

本项目基于 [MIT License](LICENSE) 开源。
