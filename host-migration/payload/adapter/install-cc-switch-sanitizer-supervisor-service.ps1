$ErrorActionPreference = 'Stop'

$serviceName = 'CcSwitchSanitizerSupervisor'
$nssm = '@@SYSTEMROOT:win@@\system32\nssm.exe'
$sanitizerDir = '@@SANITIZER_ROOT:win@@'
$startScript = Join-Path $sanitizerDir 'start-cc-switch-sanitizer-supervisor.ps1'
$serviceLogDir = Join-Path $sanitizerDir 'service-logs'

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
$isAdmin = $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
  $args = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', "`"$PSCommandPath`"")
  Start-Process -FilePath 'powershell.exe' -ArgumentList $args -Verb RunAs -Wait
  exit 0
}

if (-not (Test-Path -LiteralPath $nssm)) { throw "nssm.exe not found: $nssm" }
if (-not (Test-Path -LiteralPath $startScript)) { throw "supervisor script not found: $startScript" }
New-Item -ItemType Directory -Force -Path $serviceLogDir | Out-Null

$existing = Get-Service -Name $serviceName -ErrorAction SilentlyContinue
if (-not $existing) { & $nssm install $serviceName 'powershell.exe' | Out-Null }

& $nssm set $serviceName AppDirectory $sanitizerDir | Out-Null
& $nssm set $serviceName AppParameters "-NoProfile -ExecutionPolicy Bypass -File `"$startScript`"" | Out-Null
& $nssm set $serviceName DisplayName 'CC Switch Sanitizer Supervisor' | Out-Null
& $nssm set $serviceName Description 'Canonical supervisor for Qwen, GLM, Codex-compatible, and DeepSeek sanitizer children.' | Out-Null
& $nssm set $serviceName Start SERVICE_AUTO_START | Out-Null
& $nssm set $serviceName AppStdout (Join-Path $serviceLogDir 'cc-switch-sanitizer-supervisor.stdout.log') | Out-Null
& $nssm set $serviceName AppStderr (Join-Path $serviceLogDir 'cc-switch-sanitizer-supervisor.stderr.log') | Out-Null
& $nssm set $serviceName AppRotateFiles 1 | Out-Null
& $nssm set $serviceName AppRotateOnline 1 | Out-Null
& $nssm set $serviceName AppRotateBytes 1048576 | Out-Null

$svc = Get-Service -Name $serviceName
if ($svc.Status -ne 'Running') { Start-Service -Name $serviceName }
Start-Sleep -Seconds 2
Get-Service -Name $serviceName | Select-Object Name,DisplayName,Status,StartType
