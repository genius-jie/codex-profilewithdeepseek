# Restart CodexIdSanitizer service.
# If launched from a normal shell, request one standard UAC elevation and
# return the elevated operation's exit code to the caller.

$ErrorActionPreference = "Stop"
$expectedAdapterPrefix = "responses-summary-v39-qwen-vision-v1"

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    $pwsh = (Get-Command pwsh -ErrorAction Stop).Source
    $child = Start-Process -FilePath $pwsh -Verb RunAs -ArgumentList @(
        '-NoLogo', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $PSCommandPath
    ) -Wait -PassThru
    exit $child.ExitCode
}

try {
    Write-Host "Stopping CodexIdSanitizer service..."
    Stop-Service -Name "CodexIdSanitizer" -Force -ErrorAction Stop
    (Get-Service -Name "CodexIdSanitizer").WaitForStatus(
        [System.ServiceProcess.ServiceControllerStatus]::Stopped,
        [TimeSpan]::FromSeconds(20)
    )

    Write-Host "Starting CodexIdSanitizer service..."
    Start-Service -Name "CodexIdSanitizer" -ErrorAction Stop
    (Get-Service -Name "CodexIdSanitizer").WaitForStatus(
        [System.ServiceProcess.ServiceControllerStatus]::Running,
        [TimeSpan]::FromSeconds(20)
    )
    Start-Sleep -Seconds 2

    Write-Host "Checking health..."
    $health = Invoke-RestMethod -Uri "http://127.0.0.1:15740/health" -ErrorAction Stop
    if ([string]$health.status -ne "ok") {
        throw "CodexIdSanitizer health status is '$($health.status)'"
    }
    if ([string]$health.adapter -ne $expectedAdapterPrefix) {
        throw "CodexIdSanitizer adapter is '$($health.adapter)', expected '$expectedAdapterPrefix'"
    }
    Write-Host "Service status: $($health.status)" -ForegroundColor Green
    Write-Host "Adapter version: $($health.adapter)" -ForegroundColor Green
    exit 0
} catch {
    Write-Error ("CodexIdSanitizer restart/health check failed: " + $_.Exception.Message)
    exit 1
}
