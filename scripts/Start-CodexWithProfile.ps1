#requires -Version 7.0
<#
.SYNOPSIS
    Starts OpenAI Codex / Codex++ bound to this customized profile.
#>

param(
    [string]$ProfileRoot = $PSScriptRoot | Split-Path -Parent,
    [switch]$SkipModelSync
)

$ErrorActionPreference = "Stop"

function Resolve-CodexExe {
    $pkg = Get-AppxPackage -Name "OpenAI.Codex" -ErrorAction SilentlyContinue
    if ($pkg -and $pkg.InstallLocation) {
        $candidate = Join-Path $pkg.InstallLocation "app\Codex.exe"
        if (Test-Path -LiteralPath $candidate) { return $candidate }
        $candidate = Join-Path $pkg.InstallLocation "app\ChatGPT.exe"
        if (Test-Path -LiteralPath $candidate) { return $candidate }
    }
    
    # Store app path fallback
    $storePath = "C:\Users\Administrator\AppData\Local\codex-plusplus\store-apps"
    if (Test-Path -LiteralPath $storePath) {
        $found = Get-ChildItem -Path $storePath -Filter "codex.exe" -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($found) { return $found.FullName }
    }
    return $null
}

if (-not $SkipModelSync) {
    $syncScript = Join-Path $PSScriptRoot "Sync-ModelCatalog.ps1"
    if (Test-Path -LiteralPath $syncScript) {
        & $syncScript -ProfileRoot $ProfileRoot
    }
}

$codexExe = Resolve-CodexExe
if (-not $codexExe) {
    Write-Warning "Codex executable not found in Appx or Store. Setting CODEX_HOME for CLI environment."
}

$env:CODEX_HOME = $ProfileRoot
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host " Codex Profile with DeepSeek Initialized   " -ForegroundColor Green
Write-Host " Profile Root: $ProfileRoot               " -ForegroundColor Yellow
Write-Host " CODEX_HOME  : $env:CODEX_HOME            " -ForegroundColor Yellow
Write-Host "==========================================" -ForegroundColor Cyan

if ($codexExe) {
    Write-Host "Launching Codex Desktop: $codexExe" -ForegroundColor Cyan
    Start-Process -FilePath $codexExe -WorkingDirectory (Split-Path -Parent $codexExe)
} else {
    Write-Host "Profile environment ready. You can now run `codex` from command line." -ForegroundColor Green
}