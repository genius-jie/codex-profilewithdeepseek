#requires -Version 7.0
# Invoke-CodexPlusPlusIdentityLaunch.ps1
# Codex++ 26.915+ 包身份启动适配层（自有文件，Codex++ 升级永不覆盖）。
# Profile must be the physical @@CODEXPP_PROFILE:win@@ root; no C: alias is
# part of the launch contract.
# 由 Start-CodexPlusPlus.ps1 尾部的自动注入行调用；全部身份启动逻辑住在这里，
# 使 Codex++ 主脚本里只残留一行稳定调用，升级被冲掉后由
# Invoke-CodexPlusPlusLauncherCompat.ps1 在下次启动时自动重放。
param(
    [Parameter(Mandatory)][string]$CodexExe,
    [Parameter(Mandatory)][string]$Profile,
    [switch]$DryRun
)

$aliasExe = Join-Path $env:LOCALAPPDATA 'Microsoft\WindowsApps\chatgpt-pp.exe'
$ensureScript = Join-Path $PSScriptRoot 'Ensure-CodexPlusPlusPackageRegistration.ps1'
$launchArgs = @('--password-store=basic', "--user-data-dir=$Profile")

# 只对 store-apps 补丁镜像做身份注册；官方路径直启保持原行为。
if ($CodexExe -like '*store-apps*') {
    if ($DryRun) {
        Write-Host "[DryRun] 将执行 ensure 预检并经包身份别名启动: $aliasExe $launchArgs" -ForegroundColor Cyan
        exit 0
    }
    if (Test-Path -LiteralPath $ensureScript -PathType Leaf) {
        try { & $ensureScript }
        catch { Write-Host "包身份注册预检失败（将回退旧启动方式）: $($_.Exception.Message)" -ForegroundColor Yellow }
    }
    if (Test-Path -LiteralPath $aliasExe -PathType Leaf) {
        Write-Host '>>> Launching via package-identity alias chatgpt-pp.exe ...' -ForegroundColor Green
        Start-Process -FilePath $aliasExe -ArgumentList $launchArgs
        exit 0
    }
    Write-Host 'chatgpt-pp.exe 别名不在位，回退直接路径启动（将无包身份，预期失败）' -ForegroundColor Yellow
}

if ($DryRun) {
    Write-Host "[DryRun] 将直接路径启动: $CodexExe $launchArgs" -ForegroundColor Cyan
    exit 0
}
Start-Process -FilePath $CodexExe -ArgumentList $launchArgs -WorkingDirectory (Split-Path -Parent $CodexExe)
