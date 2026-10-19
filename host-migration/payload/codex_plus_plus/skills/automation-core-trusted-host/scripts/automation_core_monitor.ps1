param(
    [Parameter(Mandatory = $true)][string]$Database,
    [Parameter(Mandatory = $true)][string]$ThreadId,
    [Parameter(Mandatory = $true)][string]$TargetId,
    [Parameter(Mandatory = $true)][string]$OwnerId,
    [string]$Signal = "",
    [string]$SupervisorRoot = "@@SUITE_ROOT:win@@\multi-agent-supervisor"
)

$ErrorActionPreference = "Stop"
$suiteBin = "@@SUITE_ROOT:win@@\bin"
$supervisorCommand = Join-Path $suiteBin "automation-supervisor.cmd"
$scriptsRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$endpointName = "automation-core:$TargetId"

try {
    if (-not (Test-Path -LiteralPath $supervisorCommand -PathType Leaf)) {
        throw "automation-supervisor command not found: $supervisorCommand"
    }
    $env:PATH = "$suiteBin$([IO.Path]::PathSeparator)$env:PATH"
    $pythonParts = @($scriptsRoot)
    if ($env:PYTHONPATH) {
        $pythonParts += $env:PYTHONPATH
    }
    $env:PYTHONPATH = $pythonParts -join [IO.Path]::PathSeparator
    $endpointConfig = @{
        $endpointName = @{
            db_path = $Database
            thread_id = $ThreadId
            signal = $Signal
        }
    }
    $env:AUTOMATION_CORE_MONITOR_ENDPOINTS = $endpointConfig | ConvertTo-Json -Compress

    & $supervisorCommand --root $SupervisorRoot register-target `
        --target-id $TargetId `
        --owner-id $OwnerId `
        --observation-endpoint $endpointName | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "automation-supervisor register-target failed: $LASTEXITCODE"
    }

    & $supervisorCommand --root $SupervisorRoot poll-targets `
        --endpoint-factory automation_core_monitor:endpoint_mapping `
        --target-id $TargetId | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "automation-supervisor poll-targets failed: $LASTEXITCODE"
    }
} catch {
    Write-Warning "V4 monitoring is unavailable; Core remains authoritative: $($_.Exception.Message)"
} finally {
    Remove-Item Env:\AUTOMATION_CORE_MONITOR_ENDPOINTS -ErrorAction SilentlyContinue
}

exit 0
