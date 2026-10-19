#requires -Version 7.0
# Invoke-CodexPlusPlusLauncherCompat.ps1
# 升级免疫自愈注入器（自有文件，Codex++ 升级不覆盖）。
# 由 Start-CodexPlusPlus-Proxy.cmd 在每次调用主脚本前执行：
#   - Start-CodexPlusPlus.ps1 已含身份启动调用行 → 幂等直退（exit 0）
#   - Codex++ 升级重新生成了主脚本（原生直启行回来、注入行丢失）→ 自动重放注入：
#     把 `Start-Process -FilePath $codexExe ...` 直启行替换为一行调用
#     Invoke-CodexPlusPlusIdentityLaunch.ps1（逻辑本体在自有文件里，不内联）。
# 替换前留时间戳备份；锚点行匹配不到（Codex++ 未来改了启动形态）时告警 exit 2，
# 不破坏文件。日志: codex-plusplus\log\launcher_compat_yyyyMMdd.log
param(
    [string]$LauncherPath = '@@LAUNCHER_ROOT:win@@\Start-CodexPlusPlus.ps1',
    [switch]$DryRun
)

$ErrorActionPreference = 'Stop'
$marker = 'Invoke-CodexPlusPlusIdentityLaunch.ps1'
$logDir = '@@CODEXPP_RUNTIME:win@@\log'
$logFile = Join-Path $logDir ("launcher_compat_{0}.log" -f (Get-Date -Format 'yyyyMMdd'))
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir -Force | Out-Null }
function Write-Log([string]$msg) {
    $line = '{0} {1}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $msg
    Add-Content -LiteralPath $logFile -Value $line -Encoding utf8
    Write-Host $line
}

$retiredProfileAlias = '@@USERPROFILE:win@@\AppData\Roaming\CodexPlusPlusProfile'
$canonicalProfileRoot = '@@CODEXPP_PROFILE:win@@'
$nativeMessagingManifest = Join-Path $canonicalProfileRoot 'AppData\Local\OpenAI\extension\com.openai.codexextension.json'
$storeAppsRoot = '@@CODEXPP_INSTALL_ROOT:win@@\store-apps'

function Get-LatestCodexPlusPlusAppRoot {
    $mirror = Get-ChildItem -LiteralPath $storeAppsRoot -Directory -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -match '^OpenAI\.Codex_(\d[\d\.]*)_' } |
        Sort-Object { [version]([regex]::Match($_.Name, '^OpenAI\.Codex_(\d[\d\.]*)_').Groups[1].Value) } -Descending |
        Select-Object -First 1
    if (-not $mirror) { return $null }
    $appRoot = Join-Path $mirror.FullName 'app'
    if (-not (Test-Path -LiteralPath $appRoot -PathType Container)) { return $null }
    return $appRoot
}

function Repair-NativeMessagingManifest {
    $appRoot = Get-LatestCodexPlusPlusAppRoot
    if (-not $appRoot) {
        Write-Log 'WARN 未找到当前 Codex++ 原生包，跳过 Native Messaging 清单修复'
        return
    }
    $extensionHost = Join-Path $appRoot 'resources\plugins\openai-bundled\plugins\chrome\extension-host\windows\x64\extension-host.exe'
    if (-not (Test-Path -LiteralPath $extensionHost -PathType Leaf)) {
        Write-Log "WARN 当前原生包缺少 extension-host，跳过清单修复: $extensionHost"
        return
    }
    $manifest = [ordered]@{
        allowed_origins = @('chrome-extension://hehggadaopoacecdllhhajmbjkdcmajg/')
        description = 'Codex chrome native messaging host'
        name = 'com.openai.codexextension'
        path = [IO.Path]::GetFullPath($extensionHost)
        type = 'stdio'
    }
    $existing = $null
    if (Test-Path -LiteralPath $nativeMessagingManifest -PathType Leaf) {
        try { $existing = Get-Content -LiteralPath $nativeMessagingManifest -Raw | ConvertFrom-Json } catch { $existing = $null }
    }
    $existingPath = if ($existing) { [string]$existing.path } else { '' }
    if ([string]::Equals($existingPath, $manifest.path, [StringComparison]::OrdinalIgnoreCase)) { return }
    New-Item -ItemType Directory -Path (Split-Path -Parent $nativeMessagingManifest) -Force | Out-Null
    [IO.File]::WriteAllText(
        $nativeMessagingManifest,
        ($manifest | ConvertTo-Json -Depth 6) + [Environment]::NewLine,
        [Text.UTF8Encoding]::new($false)
    )
    Write-Log "REPAIRED Native Messaging 清单指向当前原生包: $($manifest.path)"
}

function Remove-RetiredProfileAlias {
    if (-not (Test-Path -LiteralPath $retiredProfileAlias)) { return }
    $item = Get-Item -LiteralPath $retiredProfileAlias -Force
    if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) {
        throw "Retired Codex++ C: profile alias is a reparse point; refusing automatic deletion: $retiredProfileAlias"
    }
    $resolved = [IO.Path]::GetFullPath($item.FullName).TrimEnd('\')
    if (-not [string]::Equals($resolved, $retiredProfileAlias.TrimEnd('\'), [StringComparison]::OrdinalIgnoreCase)) {
        throw "Retired Codex++ alias resolved outside the exact cleanup target: $resolved"
    }
    $files = @([IO.Directory]::GetFiles($resolved, '*', [IO.SearchOption]::AllDirectories))
    foreach ($file in $files) {
        [IO.File]::SetAttributes($file, [IO.FileAttributes]::Normal)
        [IO.File]::Delete($file)
    }
    $directories = @([IO.Directory]::GetDirectories($resolved, '*', [IO.SearchOption]::AllDirectories) | Sort-Object Length -Descending)
    foreach ($directory in $directories) { [IO.Directory]::Delete($directory, $false) }
    [IO.Directory]::Delete($resolved, $false)
    Write-Log "REMOVED retired C: profile alias residual: $retiredProfileAlias"
}

Repair-NativeMessagingManifest
Remove-RetiredProfileAlias

if (-not (Test-Path -LiteralPath $LauncherPath -PathType Leaf)) {
    Write-Log "FAIL 主启动脚本不存在: $LauncherPath"
    exit 1
}

$lines = [string[]](Get-Content -LiteralPath $LauncherPath -Encoding utf8)
if (($lines -join "`n") -match [regex]::Escape($marker)) {
    Write-Log 'OK 身份启动注入在位，无需处理'
    exit 0
}

# 锚点：直启镜像 exe 的 Start-Process 行（Codex++ 原生形态，稳定引用 $codexExe）。
$pattern = '^\s*Start-Process\s+-FilePath\s+\$codexExe\b'
$hits = @(for ($i = 0; $i -lt $lines.Count; $i++) { if ($lines[$i] -match $pattern) { $i } })
if ($hits.Count -eq 0) {
    Write-Log 'WARN 未找到原生直启锚点行且无注入标记（Codex++ 启动形态已变化？），本次不改动文件，需人工复核'
    exit 2
}
if ($hits.Count -gt 1) {
    Write-Log ("WARN 锚点行命中 {0} 处（行号 {1}），取最后一处替换" -f $hits.Count, ($hits -join ','))
}
$target = $hits[-1]
$indent = ([regex]::Match($lines[$target], '^\s*')).Value
$replacement = @(
    ($indent + '# codexpp:identity-launch-auto: ChatGPT 26.915+ 需包身份，由 Invoke-CodexPlusPlusLauncherCompat.ps1 自动维护，请勿手改')
    ($indent + "& (Join-Path `$PSScriptRoot 'Invoke-CodexPlusPlusIdentityLaunch.ps1') -CodexExe `$codexExe -Profile `$plusProfile")
)

if ($DryRun) {
    Write-Log "[DryRun] 将在第 $($target + 1) 行替换: $($lines[$target])"
    exit 0
}

$backup = "$LauncherPath.bak-codexpp-auto-$(Get-Date -Format 'yyyyMMdd-HHmmss')"
Copy-Item -LiteralPath $LauncherPath -Destination $backup
$newLines = @($lines[0..($target - 1)]) + $replacement + @($lines[($target + 1)..($lines.Count - 1)])
# 与 Codex++ 原生形态一致写 UTF-8 无 BOM（入口固定用 pwsh 7，无 BOM 安全），使重放后的文件与原生最小差异
[IO.File]::WriteAllLines($LauncherPath, [string[]]$newLines, (New-Object Text.UTF8Encoding($false)))
Write-Log ("PATCHED 已重放身份启动注入（第 {0} 行 → 2 行），备份 {1}" -f ($target + 1), (Split-Path -Leaf $backup))
exit 0
