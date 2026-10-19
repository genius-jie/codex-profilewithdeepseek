#requires -Version 7.0
param(
    [switch]$SkipOpenCliAdapterSync
)

# Start normal Codex with the real Windows user profile.
# Isolation contract:
# - auth/config/state: @@CODEX_HOME:win@@
# - proxy env: cleared for this process
# - Codex++ profile is not touched

$ErrorActionPreference = "Stop"

$realProfile = "@@USERPROFILE:win@@"

function Resolve-CodexExe {
    $pkg = Get-AppxPackage -Name "OpenAI.Codex" -ErrorAction SilentlyContinue
    if ($pkg -and $pkg.InstallLocation) {
        $candidate = Join-Path $pkg.InstallLocation "app\ChatGPT.exe"
        if (Test-Path -LiteralPath $candidate) { return $candidate }
        $candidate = Join-Path $pkg.InstallLocation "app\Codex.exe"
        if (Test-Path -LiteralPath $candidate) { return $candidate }
    }
    return $null
}

$codexExe = Resolve-CodexExe
if (-not $codexExe) {
    throw 'The official OpenAI.Codex package executable could not be resolved through Get-AppxPackage.'
}

$normalElectronUserData = "@@USERPROFILE:win@@\AppData\Roaming\Codex"
$normalNestedCodexHome = Join-Path $normalElectronUserData ".codex"
New-Item -ItemType Directory -Path $normalElectronUserData -Force | Out-Null
if (-not (Test-Path -LiteralPath $normalNestedCodexHome)) {
    New-Item -ItemType Junction -Path $normalNestedCodexHome -Target (Join-Path $realProfile ".codex") | Out-Null
} else {
    $nestedItem = Get-Item -LiteralPath $normalNestedCodexHome -Force
    if ($nestedItem.LinkType -ne "Junction" -or $nestedItem.Target -ne (Join-Path $realProfile ".codex")) {
        throw "Normal Codex nested config path is not linked to the real CODEX_HOME: $normalNestedCodexHome"
    }
}

$env:USERPROFILE = $realProfile
$env:HOME = $realProfile
$env:CODEX_HOME = (Join-Path $realProfile ".codex")
$env:HOMEDRIVE = [IO.Path]::GetPathRoot($realProfile).TrimEnd('\')
$env:HOMEPATH = $realProfile.Substring($env:HOMEDRIVE.Length)

foreach ($name in @("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy")) {
    $val = Get-Item "Env:\$name" -ErrorAction SilentlyContinue
    if ($val -and $val.Value -match "48760") {
        Remove-Item "Env:\$name" -ErrorAction SilentlyContinue
    }
}

Write-Host "Starting normal Codex" -ForegroundColor Green
Write-Host "Profile: $env:USERPROFILE" -ForegroundColor Cyan
Write-Host "Config : $env:CODEX_HOME" -ForegroundColor Cyan
Write-Host "Proxy  : cleared" -ForegroundColor Cyan

if (-not $SkipOpenCliAdapterSync) {
    $openCliAdapterSync = "@@LAUNCHER_ROOT:win@@\Sync-OpenCliAdapters.ps1"
    if (Test-Path -LiteralPath $openCliAdapterSync) {
        & $openCliAdapterSync
    }
}

$powerShell7 = '@@POWERSHELL_EXE:win@@'
$projectionWriter = '@@GENERAL_ROOT:win@@\tooling\Sync-HostCapabilityProjection.ps1'
if (Test-Path -LiteralPath $projectionWriter -PathType Leaf) {
    $projectionOutput = @(& $powerShell7 -NoLogo -NoProfile -NonInteractive -File $projectionWriter -HostId codex -SkillsRoot (Join-Path $env:CODEX_HOME 'skills') -Mode Apply 2>&1)
    $projectionExitCode = $LASTEXITCODE
    if ($projectionExitCode -ne 0) {
        Write-Warning "Host capability projection reported a non-blocking conflict/failure (exit $projectionExitCode): $($projectionOutput -join "`n")"
    }
} else {
    Write-Warning "Host capability projection writer is missing; continuing ordinary Codex launch: $projectionWriter"
}

Start-Process -FilePath $codexExe -WorkingDirectory (Split-Path -Parent $codexExe)
