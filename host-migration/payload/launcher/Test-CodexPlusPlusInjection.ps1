#requires -Version 7.0

param(
    [string]$AppRoot,
    [string]$ProfileRoot = "@@CODEXPP_PROFILE:win@@",
    [string]$CodexPlusPlusRoot = "@@CODEXPP_RUNTIME:win@@",
    [string[]]$RequiredTweaks = @(
        "co.Arconte112.followup",
        "com.lobster.auto-follow-up",
        "co.bennett.windows-computer-use"
    ),
    [switch]$SkipProcessCheck
)

$ErrorActionPreference = "Stop"

function Add-Failure {
    param(
        [System.Collections.Generic.List[string]]$Failures,
        [string]$Message
    )
    [void]$Failures.Add($Message)
}

function Resolve-StateAppRoot {
    $statePath = Join-Path $CodexPlusPlusRoot "state.json"
    if (-not (Test-Path -LiteralPath $statePath)) { return $null }
    try {
        $state = Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json
        return $state.appRoot
    } catch {
        return $null
    }
}

function Test-AppAsarHasCodexPlusPlusMarker {
    param([string]$Root)

    if (-not $Root) { return $false }
    $asar = Join-Path $Root "resources\app.asar"
    if (-not (Test-Path -LiteralPath $asar)) { return $false }

    $encoding = [System.Text.Encoding]::GetEncoding(28591)
    $text = [System.IO.File]::ReadAllText($asar, $encoding)
    return (
        $text.IndexOf("codex-plusplus-loader", [System.StringComparison]::OrdinalIgnoreCase) -ge 0 -or
        $text.IndexOf("codex-plusplus", [System.StringComparison]::OrdinalIgnoreCase) -ge 0
    )
}

function Get-AppRootFromExecutablePath {
    param([string]$ExecutablePath)

    if (-not $ExecutablePath) { return $null }
    $parent = Split-Path -Parent $ExecutablePath
    if (-not $parent) { return $null }
    if ((Split-Path -Leaf $parent) -ieq "resources") {
        return Split-Path -Parent $parent
    }
    if ((Split-Path -Leaf $ExecutablePath) -iin @("Codex.exe", "ChatGPT.exe")) {
        return $parent
    }
    return $null
}

$failures = [System.Collections.Generic.List[string]]::new()

if (-not $AppRoot) {
    $AppRoot = Resolve-StateAppRoot
}
if (-not $AppRoot) {
    Add-Failure $failures "No Codex++ app root was supplied and state.json has no appRoot."
} else {
    $AppRoot = [System.IO.Path]::GetFullPath($AppRoot).TrimEnd("\")
    if (-not (Test-Path -LiteralPath $AppRoot)) {
        Add-Failure $failures "Codex++ app root missing: $AppRoot"
    } elseif (-not (Test-AppAsarHasCodexPlusPlusMarker -Root $AppRoot)) {
        Add-Failure $failures "Codex++ loader marker missing from app.asar: $AppRoot"
    }
}

$tweaksRoot = Join-Path $CodexPlusPlusRoot "tweaks"
$configPath = Join-Path $CodexPlusPlusRoot "config.json"
if (-not (Test-Path -LiteralPath $configPath)) {
    Add-Failure $failures "Codex++ tweak config missing: $configPath"
} else {
    $config = Get-Content -LiteralPath $configPath -Raw | ConvertFrom-Json
    foreach ($tweakId in $RequiredTweaks) {
        $tweakDir = Join-Path $tweaksRoot $tweakId
        if (-not (Test-Path -LiteralPath $tweakDir)) {
            Add-Failure $failures "Required Codex++ tweak directory missing: $tweakDir"
        }
        $manifestPath = Join-Path $tweakDir "manifest.json"
        if (-not (Test-Path -LiteralPath $manifestPath)) {
            Add-Failure $failures "Required Codex++ tweak manifest missing: $manifestPath"
        }
        $entry = $config.tweaks.$tweakId
        if (-not $entry -or $entry.enabled -ne $true) {
            Add-Failure $failures "Required Codex++ tweak not enabled: $tweakId"
        }
    }
}

$activeRoots = @()
if (-not $SkipProcessCheck) {
    $profileNeedles = @([System.IO.Path]::GetFullPath($ProfileRoot).TrimEnd("\"))
    $activeRoots = Get-CimInstance Win32_Process |
        Where-Object {
            $cmd = $_.CommandLine
            $cmd -and @($profileNeedles | Where-Object {
                $cmd.IndexOf($_, [System.StringComparison]::OrdinalIgnoreCase) -ge 0
            }).Count -gt 0
        } |
        ForEach-Object { Get-AppRootFromExecutablePath -ExecutablePath $_.ExecutablePath } |
        Where-Object { $_ } |
        ForEach-Object { [System.IO.Path]::GetFullPath($_).TrimEnd("\") } |
        Sort-Object -Unique

    foreach ($root in $activeRoots) {
        if (-not (Test-AppAsarHasCodexPlusPlusMarker -Root $root)) {
            Add-Failure $failures "Active Codex++ process is running without Codex++ loader marker: $root"
        }
    }
}

$result = [pscustomobject]@{
    guard = "codexplusplus_injection"
    status = if ($failures.Count -eq 0) { "pass" } else { "fail" }
    appRoot = $AppRoot
    requiredTweaks = $RequiredTweaks
    activeCodexPlusPlusAppRoots = $activeRoots
    failures = @($failures)
}

if ($failures.Count -gt 0) {
    Write-Output "CODEXPP_INJECTION_GUARD_FAIL"
    $result | ConvertTo-Json -Depth 6
    exit 1
}

Write-Output "CODEXPP_INJECTION_GUARD_PASS"
$result | ConvertTo-Json -Depth 6
