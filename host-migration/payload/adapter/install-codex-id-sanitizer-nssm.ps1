param(
  [switch]$NoElevate
)

$ErrorActionPreference = 'Stop'

$serviceName = 'CodexIdSanitizer'
$root = $PSScriptRoot
$logDir = Join-Path $root 'service-logs'
$startScript = Join-Path $root 'start-codex-id-sanitizer.ps1'

function Resolve-Nssm {
  $candidates = @()
  $command = Get-Command nssm.exe -ErrorAction SilentlyContinue
  if ($command) { $candidates += $command.Source }
  $candidates += @(
    '@@SYSTEMROOT:win@@\system32\nssm.exe',
    '@@PROGRAMFILES:win@@\GrafanaLabs\nssm-2.24\win64\nssm.exe',
    '@@PROGRAMFILES:win@@\GrafanaLabs\svc-12.4.2.0\nssm.exe'
  )
  foreach ($candidate in $candidates) {
    if ($candidate -and (Test-Path -LiteralPath $candidate)) {
      return (Resolve-Path -LiteralPath $candidate).Path
    }
  }
  throw 'nssm.exe was not found.'
}

$nssm = Resolve-Nssm
$powershell = Join-Path $PSHOME 'powershell.exe'
$stdout = Join-Path $logDir 'codex-id-sanitizer.stdout.log'
$stderr = Join-Path $logDir 'codex-id-sanitizer.stderr.log'

New-Item -ItemType Directory -Path $logDir -Force | Out-Null

$existing = Get-Service -Name $serviceName -ErrorAction SilentlyContinue
if ($existing -and $existing.Status -ne 'Stopped') {
  & $nssm stop $serviceName | Out-Null
  Start-Sleep -Seconds 2
}

if (-not $existing) {
  & $nssm install $serviceName $powershell "-NoProfile -ExecutionPolicy Bypass -File `"$startScript`"" | Out-Null
}

& $nssm set $serviceName Application $powershell | Out-Null
& $nssm set $serviceName AppParameters "-NoProfile -ExecutionPolicy Bypass -File `"$startScript`"" | Out-Null
& $nssm set $serviceName AppDirectory $root | Out-Null
& $nssm set $serviceName DisplayName 'Codex ID Sanitizer' | Out-Null
& $nssm set $serviceName Description 'Normalizes tool call IDs and intercepts compaction for third-party models in Codex.' | Out-Null
& $nssm set $serviceName Start SERVICE_AUTO_START | Out-Null
& $nssm set $serviceName AppStdout $stdout | Out-Null
& $nssm set $serviceName AppStderr $stderr | Out-Null
& $nssm set $serviceName AppRotateFiles 1 | Out-Null
& $nssm set $serviceName AppRotateOnline 1 | Out-Null
& $nssm set $serviceName AppRotateSeconds 86400 | Out-Null
& $nssm set $serviceName AppRotateBytes 1048576 | Out-Null
& $nssm set $serviceName AppThrottle 1500 | Out-Null
& $nssm set $serviceName AppExit Default Restart | Out-Null
& $nssm set $serviceName AppRestartDelay 3000 | Out-Null

& $nssm start $serviceName | Out-Null

Write-Host "CodexIdSanitizer service installed and started."
Get-Service -Name $serviceName | Select-Object Name, Status, StartType
