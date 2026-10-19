#requires -Version 7.0

# Sync shared OpenCLI adapter code into both normal Codex and Codex++ profiles.
# This copies only .opencli\clis adapter source files. It does not copy cookies,
# browser profiles, traces, auth, plugins, or cache state.

param(
    [string]$SharedClisRoot = "@@USERPROFILE:win@@\.opencli-shared\clis",
    [string]$SeedClisRoot = "@@USERPROFILE:win@@\.opencli\clis",
    [string[]]$TargetHomes = @(
        "@@USERPROFILE:win@@",
        "@@CODEXPP_PROFILE:win@@"
    ),
    [switch]$NoSeed
)

$ErrorActionPreference = "Stop"

function Test-AdapterTreeHasFiles {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) { return $false }
    return [bool](Get-ChildItem -LiteralPath $Path -Recurse -File -Include "*.js","*.mjs","*.json","*.yaml","*.yml" -ErrorAction SilentlyContinue | Select-Object -First 1)
}

function Invoke-RobocopyChecked {
    param(
        [string]$Source,
        [string]$Target
    )

    New-Item -ItemType Directory -Path $Target -Force | Out-Null
    robocopy $Source $Target /E /R:1 /W:1 /NFL /NDL /NJH /NJS /NP | Out-Null
    $code = $LASTEXITCODE
    if ($code -ge 8) {
        throw "robocopy failed: source=$Source target=$Target exitCode=$code"
    }
}

if (-not (Test-AdapterTreeHasFiles -Path $SharedClisRoot)) {
    if ($NoSeed) {
        throw "Shared OpenCLI adapter root is empty or missing: $SharedClisRoot"
    }
    if (-not (Test-AdapterTreeHasFiles -Path $SeedClisRoot)) {
        throw "Cannot seed shared OpenCLI adapters; seed root is empty or missing: $SeedClisRoot"
    }
    New-Item -ItemType Directory -Path $SharedClisRoot -Force | Out-Null
    Invoke-RobocopyChecked -Source $SeedClisRoot -Target $SharedClisRoot
    Write-Host "Seeded shared OpenCLI adapters: $SharedClisRoot" -ForegroundColor Cyan
}

foreach ($targetHome in $TargetHomes) {
    $target = Join-Path $targetHome ".opencli\clis"
    Invoke-RobocopyChecked -Source $SharedClisRoot -Target $target
    Write-Host "Synced OpenCLI adapters into: $target" -ForegroundColor Green
}
