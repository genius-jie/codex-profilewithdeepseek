param(
  [int]$IntervalSeconds = 60
)

$ErrorActionPreference = 'Continue'

$ensureScript = Join-Path $PSScriptRoot 'ensure-read-tool-sanitizer.ps1'
$logs = Join-Path $PSScriptRoot 'logs'
$watchdogLog = Join-Path $logs 'read-tool-sanitizer-watchdog.jsonl'
$mutex = [System.Threading.Mutex]::new($false, 'Local\ReadToolSanitizerWatchdog')
$hasMutex = $false

function Write-WatchdogEvent {
  param([hashtable]$Event)

  New-Item -ItemType Directory -Path $logs -Force | Out-Null
  $payload = [ordered]@{ ts = (Get-Date).ToUniversalTime().ToString('o') }
  foreach ($key in $Event.Keys) {
    $payload[$key] = $Event[$key]
  }
  Add-Content -LiteralPath $watchdogLog -Value ($payload | ConvertTo-Json -Compress -Depth 6) -Encoding UTF8
}

try {
  $hasMutex = $mutex.WaitOne(0)
} catch {
  $hasMutex = $false
}

if (-not $hasMutex) {
  Write-WatchdogEvent @{ type = 'watchdog_already_running' }
  exit 0
}

try {
  Write-WatchdogEvent @{ type = 'watchdog_started'; interval_seconds = $IntervalSeconds }

  while ($true) {
    try {
      & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $ensureScript | Out-Null
      $exitCode = $LASTEXITCODE
      if ($exitCode -ne 0) {
        Write-WatchdogEvent @{ type = 'ensure_failed'; exit_code = $exitCode }
      }
    } catch {
      Write-WatchdogEvent @{ type = 'watchdog_error'; message = $_.Exception.Message }
    }

    Start-Sleep -Seconds $IntervalSeconds
  }
} finally {
  if ($hasMutex) {
    $mutex.ReleaseMutex() | Out-Null
  }
  $mutex.Dispose()
}
