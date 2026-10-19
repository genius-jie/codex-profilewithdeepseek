---
name: S44 Windows弹窗与提权治理
type: generic
domain: windows-popup-elevation-governance
tier: L3
doc_status: active-ssot
status: experimental
related:
  - @@GENERAL_ROOT:win@@\control\registry\02-skill-catalog.md
  - @@GENERAL_ROOT:win@@\assets\rules\execution.md
  - @@GENERAL_ROOT:win@@\assets\skills\S12_系统化调试\SKILL.md
  - @@GENERAL_ROOT:win@@\assets\references\methodology\25_Windows-Service-Port-Governance-SOP.md
  - @@OPENCLAW_ROOT:win@@\.agents\skills\A8_Windows自动化人机协同执行指南\SKILL.md
  - @@OPENCLAW_ROOT:win@@\.agents\skills\S42_OpenClaw网关Session清理与重启\SKILL.md
description: |
  【触发场景】Windows 反复闪现黑框、pwsh/cmd 控制台弹窗、UAC 不出现、blocked by policy、拒绝访问、计划任务静默运行或固定管理动作需要后台提权。
  【不触发】普通桌面点击输入、单纯端口/NSSM 故障、OpenClaw session 清理、无需诊断的正常交互式终端。
  【功能】追踪弹窗来源，区分 Codex 执行策略与 Windows 权限边界，选择无闪窗启动方式，并设计保留 UAC 的窄权限提权代理。
extends:
  - @@GENERAL_ROOT:win@@\assets\rules\execution.md
  - @@GENERAL_ROOT:win@@\assets\references\methodology\10_S-Tier-Execution-Discipline-Protocol.md
birth_ceremony_id: bc-64fba6ae1154
birth_ceremony_date: 2026-07-20
---
# Windows 弹窗与提权治理

<context>

用户要的是两件事：后台任务不闪黑框；需要管理员权限时，UAC 和系统管理命令仍能正常工作。两者不能混为“全部隐藏”。

详细分诊、改造模式和案例见 [Windows 弹窗与提权治理 SOP](references/windows-popup-elevation-sop.md)。

</context>

<rules>

## 执行顺序

1. 先运行只读探针：

   ```powershell
   & "<Skill目录>\scripts\Get-WindowsPopupElevationEvidence.ps1"
   ```

   每周启动入口巡检使用基线差分包装器。首次显式初始化当前已知项，后续仅在出现新的控制台计划任务 Action 时返回告警退出码 `2`；Windows 计划任务本身始终只读：

   ```powershell
   & "<Skill目录>\scripts\Invoke-WindowsStartupEntryAudit.ps1" -InitializeBaseline
   & "<Skill目录>\scripts\Invoke-WindowsStartupEntryAudit.ps1"
   ```

   默认基线与回执位于 Codex++ 隔离目录 `@@USERPROFILE:win@@\AppData\Roaming\CodexPlusPlusProfile\.codex\automation-state`。每次巡检以本次观测覆盖基线，因此新增或消失后再次出现的 Action 会各告警一次；无变化返回 `0`，探针异常返回 `1`。

2. 用进程父子关系、计划任务 Action、触发频率和真实错误文本确定来源。仅凭窗口标题或文件名不得归因。
3. 按 SOP 分成六类：意外控制台闪窗、正常交互终端、正常 UAC、Codex 策略阻断、Windows 权限拒绝、固定动作提权代理。
4. 只修改真正的启动入口。修改后复核功能、触发器、运行身份、网络/浏览器会话和窗口可见性。

## 不可混淆的边界

- `blocked by policy`：命令在创建进程前被执行策略拒绝。它不等于 Windows `Access is denied`。
- `拒绝访问`：命令已到达 Windows，但当前令牌、ACL 或服务权限不足。
- COM、CIM、cmdlet 和 `schtasks.exe` 只是调用入口；换 API 不会自动产生管理员令牌。
- 一次性管理操作保留标准 UAC。不得关闭 UAC、降低提示级别或添加通用 `RunAs` 放行规则。
- 无人值守的固定管理动作使用预先安装的窄权限代理：固定任务/服务、固定动作白名单、结构化请求、结果回执、安全探针和回滚。

## 无闪窗规则

- `-WindowStyle Hidden` 和计划任务 XML 的 `Hidden` 不能保证第一个控制台进程不闪。
- 真正需要无窗口时，第一个用户态进程必须是 GUI 子系统入口，例如 `wscript.exe`、受控 GUI 启动器或目标程序自身的 GUI 版本。
- 浏览器登录态、剪贴板、桌面 UI 等任务不得为了隐藏窗口改成无交互 Session 或 SYSTEM 身份。

## 完成条件

- 连续覆盖至少两个触发周期，未出现意外窗口。
- 原业务回执或健康检查仍通过。
- UAC 配置未被削弱；显式管理员操作仍由用户确认。
- 固定提权代理的 `probe` 证明管理员身份和目标资源访问正常，且不执行业务破坏动作。

</rules>

<template>

```json
{
  "classification": "unexpected_console | interactive_console | uac | codex_policy | windows_access_denied | elevation_broker",
  "root_cause_evidence": [],
  "entrypoint_changed": "",
  "function_verification": [],
  "visibility_verification": [],
  "uac_preserved": true,
  "rollback": ""
}
```

</template>
