param(
  [switch]$NoElevate
)

$ErrorActionPreference = 'Stop'

$serviceName = 'ReadToolSanitizer'
$root = $PSScriptRoot
$logs = Join-Path $root 'logs'
$healthScript = Join-Path $root 'test-read-tool-sanitizer-health.ps1'

function Test-IsAdmin {
  $principal = [Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()
  return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Write-TestResult {
  param([hashtable]$Result)

  New-Item -ItemType Directory -Path $logs -Force | Out-Null
  $file = Join-Path $logs ('read-tool-sanitizer-nssm-recovery-{0}.json' -f (Get-Date -Format 'yyyyMMdd-HHmmss'))
  $payload = [ordered]@{
    ts = (Get-Date).ToUniversalTime().ToString('o')
    service_name = $serviceName
  }
  foreach ($key in $Result.Keys) {
    $payload[$key] = $Result[$key]
  }
  $json = $payload | ConvertTo-Json -Depth 8
  [System.IO.File]::WriteAllText($file, $json, [System.Text.UTF8Encoding]::new($false))
  return $file
}

if (-not (Test-IsAdmin)) {
  if ($NoElevate) {
    throw 'Administrator privileges are required to test NSSM recovery.'
  }

  Start-Process -FilePath powershell.exe -Verb RunAs -ArgumentList @(
    '-NoProfile',
    '-ExecutionPolicy',
    'Bypass',
    '-File',
    "`"$PSCommandPath`""
  ) -Wait
  exit 0
}

$oldConnection = Get-NetTCPConnection -LocalAddress 127.0.0.1 -LocalPort 15722 -State Listen -ErrorAction Stop |
  Select-Object -First 1
$oldPid = [int]$oldConnection.OwningProcess
$oldProcess = Get-CimInstance Win32_Process -Filter "ProcessId=$oldPid" |
  Select-Object -First 1 ProcessId, Name, CommandLine

Stop-Process -Id $oldPid -Force

$newPid = $null
$deadline = (Get-Date).AddSeconds(45)
while ((Get-Date) -lt $deadline) {
  Start-Sleep -Seconds 1
  $newConnection = Get-NetTCPConnection -LocalAddress 127.0.0.1 -LocalPort 15722 -State Listen -ErrorAction SilentlyContinue |
    Select-Object -First 1
  if ($newConnection -and $newConnection.OwningProcess -and $newConnection.OwningProcess -ne $oldPid) {
    $newPid = [int]$newConnection.OwningProcess
    break
  }
}

$newProcess = if ($newPid) {
  Get-CimInstance Win32_Process -Filter "ProcessId=$newPid" |
    Select-Object -First 1 ProcessId, Name, CommandLine
} else {
  $null
}

$healthOutput = & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $healthScript -Strict 2>$null
$healthOk = $LASTEXITCODE -eq 0
$health = $null
try {
  $health = ($healthOutput -join "`n") | ConvertFrom-Json -ErrorAction Stop
} catch {
  $health = $healthOutput
}

$service = Get-Service -Name $serviceName -ErrorAction Stop
$ok = [bool]($newPid -and $healthOk -and $service.Status -eq 'Running')
$resultFile = Write-TestResult @{
  ok = $ok
  old_pid = $oldPid
  old_process = $oldProcess
  new_pid = $newPid
  new_process = $newProcess
  health_ok = $healthOk
  health = $health
  service_status = $service.Status.ToString()
  service_start_type = $service.StartType.ToString()
}

[pscustomobject]@{
  Ok = $ok
  OldPid = $oldPid
  NewPid = $newPid
  HealthOk = $healthOk
  ServiceStatus = $service.Status
  ResultFile = $resultFile
}

if (-not $ok) {
  exit 1
}
