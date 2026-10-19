param(
  [switch]$NoElevate,
  [switch]$KeepHkcuRun
)

$ErrorActionPreference = 'Stop'

$serviceName = 'ReadToolSanitizer'
$root = $PSScriptRoot
$logs = Join-Path $root 'logs'
$startScript = Join-Path $root 'start-read-tool-sanitizer.ps1'
$healthScript = Join-Path $root 'test-read-tool-sanitizer-health.ps1'
$runKey = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run'
$runValueName = 'ReadToolSanitizerWatchdog'

function Test-IsAdmin {
  $principal = [Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()
  return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Resolve-Nssm {
  $candidates = @()
  $command = Get-Command nssm.exe -ErrorAction SilentlyContinue
  if ($command) {
    $candidates += $command.Source
  }

  $candidates += @(
    '@@SYSTEMROOT:win@@\system32\nssm.exe',
    '@@PROGRAMFILES:win@@\GrafanaLabs\nssm-2.24\win64\nssm.exe',
    '@@PROGRAMFILES:win@@\GrafanaLabs\nssm-2.24\win32\nssm.exe',
    '@@PROGRAMFILES:win@@\GrafanaLabs\svc-12.4.2.0\nssm.exe'
  )

  foreach ($candidate in $candidates) {
    if ($candidate -and (Test-Path -LiteralPath $candidate)) {
      return (Resolve-Path -LiteralPath $candidate).Path
    }
  }

  throw 'nssm.exe was not found.'
}

function Write-InstallResult {
  param([hashtable]$Result)

  New-Item -ItemType Directory -Path $logs -Force | Out-Null
  $file = Join-Path $logs ('read-tool-sanitizer-nssm-install-{0}.json' -f (Get-Date -Format 'yyyyMMdd-HHmmss'))
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
    throw 'Administrator privileges are required to install the NSSM service.'
  }

  $arguments = @(
    '-NoProfile',
    '-ExecutionPolicy',
    'Bypass',
    '-File',
    "`"$PSCommandPath`""
  )
  if ($KeepHkcuRun) {
    $arguments += '-KeepHkcuRun'
  }

  Start-Process -FilePath powershell.exe -Verb RunAs -ArgumentList $arguments -Wait
  exit 0
}

$nssm = Resolve-Nssm
$powershell = Join-Path $PSHOME 'powershell.exe'
$stdout = Join-Path $logs 'read-tool-sanitizer-service.stdout.log'
$stderr = Join-Path $logs 'read-tool-sanitizer-service.stderr.log'

New-Item -ItemType Directory -Path $logs -Force | Out-Null

if (-not $KeepHkcuRun) {
  Remove-ItemProperty -Path $runKey -Name $runValueName -ErrorAction SilentlyContinue
}

$existing = Get-Service -Name $serviceName -ErrorAction SilentlyContinue
if ($existing -and $existing.Status -ne 'Stopped') {
  & $nssm stop $serviceName | Out-Null
  Start-Sleep -Seconds 2
}

Get-CimInstance Win32_Process |
  Where-Object {
    $_.CommandLine -and (
      $_.CommandLine -like '*watch-read-tool-sanitizer.ps1*' -or
      $_.CommandLine -like '*read-tool-sanitizer-proxy.js*'
    )
  } |
  ForEach-Object {
    try {
      Stop-Process -Id $_.ProcessId -Force -ErrorAction Stop
    } catch {
      # Best effort cleanup before the service owns port 15722.
    }
  }

if (-not $existing) {
  & $nssm install $serviceName $powershell "-NoProfile -ExecutionPolicy Bypass -File `"$startScript`"" | Out-Null
}

& $nssm set $serviceName Application $powershell | Out-Null
& $nssm set $serviceName AppParameters "-NoProfile -ExecutionPolicy Bypass -File `"$startScript`"" | Out-Null
& $nssm set $serviceName AppDirectory $root | Out-Null
& $nssm set $serviceName Start SERVICE_AUTO_START | Out-Null
& $nssm set $serviceName AppStdout $stdout | Out-Null
& $nssm set $serviceName AppStderr $stderr | Out-Null
& $nssm set $serviceName AppRotateFiles 1 | Out-Null
& $nssm set $serviceName AppRotateOnline 1 | Out-Null
& $nssm set $serviceName AppRotateSeconds 86400 | Out-Null
& $nssm set $serviceName AppRotateBytes 1048576 | Out-Null
& $nssm set $serviceName AppThrottle 1500 | Out-Null
& $nssm set $serviceName AppExit Default Restart | Out-Null

& $nssm start $serviceName | Out-Null

$health = $null
$healthOk = $false
for ($i = 0; $i -lt 20; $i++) {
  Start-Sleep -Seconds 1
  $healthOutput = & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $healthScript -Strict 2>$null
  if ($LASTEXITCODE -eq 0) {
    $healthOk = $true
    try {
      $health = ($healthOutput -join "`n") | ConvertFrom-Json -ErrorAction Stop
    } catch {
      $health = $healthOutput
    }
    break
  }
}

$service = Get-Service -Name $serviceName -ErrorAction Stop
$runValue = $null
try {
  $runValue = (Get-ItemProperty -Path $runKey -Name $runValueName -ErrorAction Stop).$runValueName
} catch {
  $runValue = $null
}

$resultFile = Write-InstallResult @{
  ok = [bool]($service.Status -eq 'Running' -and $healthOk)
  user = [Security.Principal.WindowsIdentity]::GetCurrent().Name
  nssm = $nssm
  service_status = $service.Status.ToString()
  service_start_type = $service.StartType.ToString()
  health_ok = $healthOk
  health = $health
  hkcu_run_present = [bool]$runValue
  hkcu_run_value = $runValue
  stdout = $stdout
  stderr = $stderr
}

[pscustomobject]@{
  Ok = [bool]($service.Status -eq 'Running' -and $healthOk)
  ServiceName = $serviceName
  Status = $service.Status
  StartType = $service.StartType
  HealthOk = $healthOk
  ResultFile = $resultFile
}

if ($service.Status -ne 'Running' -or -not $healthOk) {
  exit 1
}
