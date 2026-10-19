#requires -Version 7.0

[CmdletBinding()]
param([switch]$ForceRepair)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$powerShell7 = '@@POWERSHELL_EXE:win@@'
$updateEntry = '@@LAUNCHER_ROOT:win@@\Sync-CodexPlusPlusLatest.ps1'

if (-not (Test-Path -LiteralPath $powerShell7 -PathType Leaf)) {
    Write-Error "PowerShell 7 executable is missing: $powerShell7"
    exit 1
}
if (-not (Test-Path -LiteralPath $updateEntry -PathType Leaf)) {
    Write-Error "Codex++ one-shot maintenance entry is missing: $updateEntry"
    exit 1
}

$arguments = @('-NoLogo', '-NoProfile', '-File', $updateEntry, '-Once', '-RequireStoppedProfile')
if ($ForceRepair) { $arguments += '-ForceRepair' }
& $powerShell7 @arguments
exit $LASTEXITCODE
