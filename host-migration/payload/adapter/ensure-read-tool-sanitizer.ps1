$ErrorActionPreference = 'Stop'

$root = $PSScriptRoot
$logs = Join-Path $root 'logs'
$testScript = Join-Path $root 'test-read-tool-sanitizer-health.ps1'
$startScript = Join-Path $root 'start-read-tool-sanitizer.ps1'
$watchdogLog = Join-Path $logs 'read-tool-sanitizer-watchdog.jsonl'
$listenHost = '127.0.0.1'
$listenPort = 15722

function Write-WatchdogEvent {
  param([hashtable]$Event)

  New-Item -ItemType Directory -Path $logs -Force | Out-Null
  $payload = [ordered]@{ ts = (Get-Date).ToUniversalTime().ToString('o') }
  foreach ($key in $Event.Keys) {
    $payload[$key] = $Event[$key]
  }
  Add-Content -LiteralPath $watchdogLog -Value ($payload | ConvertTo-Json -Compress -Depth 6) -Encoding UTF8
}

function Invoke-Health {
  $output = & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $testScript 2>$null
  $exitCode = $LASTEXITCODE
  $parsed = $null
  try {
    $parsed = ($output -join "`n") | ConvertFrom-Json -ErrorAction Stop
  } catch {
    $parsed = $null
  }
  return [pscustomobject]@{
    Ok = ($exitCode -eq 0)
    ExitCode = $exitCode
    Result = $parsed
    Raw = $output
  }
}

function Test-TcpPort {
  param(
    [string]$HostName,
    [int]$Port,
    [int]$Timeout = 800
  )

  $client = [System.Net.Sockets.TcpClient]::new()
  try {
    $async = $client.BeginConnect($HostName, $Port, $null, $null)
    if (-not $async.AsyncWaitHandle.WaitOne($Timeout, $false)) {
      return $false
    }
    $client.EndConnect($async)
    return $true
  } catch {
    return $false
  } finally {
    $client.Dispose()
  }
}

$health = Invoke-Health
if ($health.Ok) {
  Write-WatchdogEvent @{ type = 'health_ok'; sanitizer = "http://${listenHost}:${listenPort}" }
  $health.Raw
  exit 0
}

if (Test-TcpPort -HostName $listenHost -Port $listenPort) {
  Write-WatchdogEvent @{
    type = 'health_failed_port_busy'
    sanitizer = "http://${listenHost}:${listenPort}"
    exit_code = $health.ExitCode
  }
  $health.Raw
  exit 2
}

Write-WatchdogEvent @{ type = 'starting_sanitizer'; sanitizer = "http://${listenHost}:${listenPort}" }
Start-Process -FilePath powershell.exe -WindowStyle Hidden -ArgumentList @(
  '-NoProfile',
  '-ExecutionPolicy',
  'Bypass',
  '-File',
  $startScript
)

Start-Sleep -Seconds 2
$after = Invoke-Health
if ($after.Ok) {
  Write-WatchdogEvent @{ type = 'started_sanitizer'; sanitizer = "http://${listenHost}:${listenPort}" }
  $after.Raw
  exit 0
}

Write-WatchdogEvent @{
  type = 'start_failed'
  sanitizer = "http://${listenHost}:${listenPort}"
  exit_code = $after.ExitCode
}
$after.Raw
exit 1
