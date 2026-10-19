---
domain: host-migration-tweaks
tier: L2
doc_status: active-reference
birth_ceremony_id: project-host-followup-migration-20261019
related:
  - ../README.md
  - portable-preferences.js
  - ../tools/test_tweaks.py
  - ../payload/codexpp_tweaks/tweaks/com.lobster.auto-follow-up/manifest.json
  - ../payload/codexpp_tweaks/tweaks/co.Arconte112.followup/manifest.json
---

# 换机恢复自动提交建议插件

这里的“提交”是把下一步建议发送到 Codex++ 会话继续执行。它由两个已有插件配合完成，恢复时一起保留：

| 插件 | 负责什么 | 包内版本 |
|---|---|---|
| Codex Follow-up，`co.Arconte112.followup` | 生成建议所需的提示词同步、候选筛选和可点击建议面板 | 0.3.0 |
| Auto Follow-up，`com.lobster.auto-follow-up` | 读取面板里的结构化候选，按当前会话开关、轮数和预算继续发送 | 1.0.0 |

两者的源码、现有测试及启用登记都已随 `codexpp_tweaks` 保存；Auto Follow-up 的开发源码另存于 `codexpp_source/tweaks/auto-follow-up`。它们只安装到 Codex++ 的隔离运行目录。普通 Codex 和 Claude Code 不加载这两个 Codex++ 插件。

## 恢复文件和依赖

先按主指南恢复三宿主；使用统一入口的 `-WithSupport`，或单独选择 `--support codexpp_source,codexpp_tweaks`。还要完成 Codex++ 自身安装和第三方模型接通。Node 使用目标机可用的版本；插件现有离线测试只依赖 Node 自带模块，无须额外安装 npm 包。

假设新机隔离 Profile 仍是 `D:\CodexPlusPlusProfile`，应恢复为：

```text
D:\CodexPlusPlusProfile\AppData\Roaming\codex-plusplus\config.json
D:\CodexPlusPlusProfile\AppData\Roaming\codex-plusplus\tweaks\co.Arconte112.followup
D:\CodexPlusPlusProfile\AppData\Roaming\codex-plusplus\tweaks\com.lobster.auto-follow-up
```

实际安装源码位置使用本机迁移布局中的 `codexpp_source`。迁移模板已将插件校验配置中的 source、runtime、config 和安装状态路径统一绑定到这两个新位置；不再沿用旧机 C 盘的用户级默认目录。

本包恢复的是可校验的物理源码副本。既有校验入口会逐文件比较安装副本与源码，继续运行插件自己的测试；不要求先把副本改成开发 Junction。目标机的 `state.json` / `self-update-state.json` 由原有安装器生成，若存在则核对其源码路径，未生成时不伪造，也不从旧机复制。

## 搬走自己的插件偏好

插件的设置页偏好保存在 **Codex++ renderer 的 localStorage**。只复制 `tweak-data` 或插件文件夹不会带走这些设置。主包保留了全局 `AGENTS.md` 的提示词正文；要同时保留插件编辑框中的自定义内容和显示偏好，使用同目录的 `portable-preferences.js` 进行私密导出/导入。

| 可以带走 | 留在原会话 |
|---|---|
| 默认自动开关、最大轮数、等待时间 | 会话 ID、各会话已执行轮数、各会话开关 |
| 建议面板开关、标题、分隔线、可点击设置 | 历史候选、去重缓存、sidecar、倒计时、已发送队列 |
| 自定义 Follow-up 提示词和同步偏好 | 聊天、凭据和其他插件的任何存储 |

工具只处理上表的字段。导出动作不写设置；导入先检查完整格式和字段类型，再合并这两个插件的偏好。已有目标会话状态及其他插件数据保留，导入不启动会话、不发送建议、不切换模型。

### 在旧机导出

如果当前 Codex++ 构建提供开发者工具，打开**正式隔离启动的 Codex++ 页面的 renderer 控制台**。打开 `portable-preferences.js`，把整个文件内容复制到这个控制台执行一次；它只挂载两个迁移函数。随后执行：

```javascript
copy(JSON.stringify(CodexPlusPlusMigration.exportPreferences(), null, 2))
```

把剪贴板保存到仓库外的私密文件，例如 `D:\MigrationPrivate\codexpp-tweak-preferences.local.json`，通过自己的私密渠道带到新机。文件可能含自定义提示词，作为个人配置保管，不提交 Git。不要导出整个 localStorage、Electron 用户目录或浏览器数据库。

旧构建如果没有开发者工具，可在原设置页记录自己的最大轮数、默认开关和建议面板选项，并从 Follow-up 的 Editable prompt 保存自定义提示词；在新机通过相同设置页填写。此时使用人工迁移路径，不把界面偏好说成已经自动导出。

### 在新机导入

1. 文件恢复后、首次启用前，先在新机隔离 runtime 的 `config.json` 中将上述两个插件的 `enabled` 暂设为 `false`，保留其余配置。备份刚恢复的 Codex++ `CODEX_HOME/AGENTS.md`，避免首次启动的默认提示词同步先覆盖自定义段落。
2. 从正式隔离入口启动 Codex++，在同一 renderer 控制台加载 `portable-preferences.js`。将私密 JSON 文件的完整内容复制到剪贴板后执行下面的导入；也可以直接把文件里的 JSON 对象作为函数参数粘贴。

   ```javascript
   CodexPlusPlusMigration.importPreferences(await navigator.clipboard.readText())
   ```

3. 完整退出并重新启动 Codex++，在 Settings → Tweaks 先开启 **Codex Follow-up**，核对 Editable prompt 与同步设置；再开启 **Auto Follow-up**。不要在导入前点击 Reset default。原构建没有控制台时，先从备份的提示词/原设置记录填写对应设置，再同步。
4. 在新会话核对悬浮面板：能识别当前会话，计数从 0 开始，最大轮数与自己的偏好一致；当前会话的自动开关单独确认。旧会话的开关和剩余轮数不用于新会话。

`navigator.clipboard.readText()` 受当前构建的剪贴板权限约束；无法读取时使用直接粘贴 JSON 对象的方式，或按设置页人工恢复。迁移工具不修改系统剪贴板权限。

默认设置未自定义时，源码默认自动开关为开、最大 10 轮、等待 2000 毫秒；设置页可选择 5 / 10 / 15 / 20 轮。第一次使用新机前，按自己的需要核对这些值和当前会话开关。全局提示词同步应落到新机 **Codex++ 自己的** `CODEX_HOME/AGENTS.md`。

## 验收它能继续工作

文件恢复后可以先运行既有的只读校验入口。下面的 `$CodexPlusPlusSource` 改成本机布局里真正的源码目录：

```powershell
$CodexPlusPlusSource = 'D:\AgentTools\codex-plusplus\source'
node (Join-Path $CodexPlusPlusSource 'tweaks\auto-follow-up\scripts\verify-auto-follow-up-contract.js')
```

它核对隔离路径、两个插件的启用状态、八个 Auto Follow-up 文件的源/安装一致性，以及原有自动选择和界面初始化测试。若提示两个插件仍关闭，先完成上面的偏好导入和启用步骤。校验不自动启用插件、不重建安装状态、不写 AGENTS。迁移副本不接受 `--repair`，开发链接维护仍归原有开发入口。

随后在新机真实 Codex++ 会话完成下面的检查：

1. 在 Settings → Tweaks 能看到两个插件、Follow-up 设置页和自动提交悬浮面板。
2. 完成一个小的测试任务，确认出现的是经过筛选的建议，并且显示的开关、轮数对应当前会话。
3. 开启测试会话的自动提交，确认合格建议只发送一次，执行结束后计数增加；切到另一会话确认开关与计数互相独立。
4. 关闭自动提交或达到轮数上限后，确认继续发送停止。

现有策略只自动发送已完成任务之后合格的 P0/P1 候选；P0 优先，同级保持原顺序。P2/P3、未完成任务、无结构化候选、重复内容或超过预算的情况不会继续发送。实际策略以打包的两插件正文和原有测试为准。

离线测试证明恢复、设置传输和插件规则可工作；它不能证明另一台电脑的设置页已挂载、建议已经被模型生成或自动发送已经在界面触发。真实界面验收仍在目标机完成。
