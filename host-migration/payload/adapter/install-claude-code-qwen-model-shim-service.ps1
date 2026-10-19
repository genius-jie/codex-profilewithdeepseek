$ErrorActionPreference = 'Stop'

$serviceName = 'ClaudeCodeQwenModelShim'
$nssm = '@@SYSTEMROOT:win@@\system32\nssm.exe'
$sanitizerDir = '@@SANITIZER_ROOT:win@@'
$startScript = Join-Path $sanitizerDir 'start-claude-code-qwen-model-shim.ps1'
$serviceLogDir = Join-Path $sanitizerDir 'service-logs'

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
$isAdmin = $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdmin) {
  $args = @(
    '-NoProfile',
    '-ExecutionPolicy', 'Bypass',
    '-File', "`"$PSCommandPath`""
  )
  Start-Process -FilePath 'powershell.exe' -ArgumentList $args -Verb RunAs -Wait
  exit 0
}

if (-not (Test-Path -LiteralPath $nssm)) {
  throw "nssm.exe not found: $nssm"
}
if (-not (Test-Path -LiteralPath $startScript)) {
  throw "start script not found: $startScript"
}

New-Item -ItemType Directory -Force -Path $serviceLogDir | Out-Null

$existing = Get-Service -Name $serviceName -ErrorAction SilentlyContinue
if (-not $existing) {
  & $nssm install $serviceName 'powershell.exe'
}

& $nssm set $serviceName AppDirectory $sanitizerDir
& $nssm set $serviceName AppParameters "-NoProfile -ExecutionPolicy Bypass -File `"$startScript`""
& $nssm set $serviceName DisplayName 'Claude Code Qwen Model Shim'
& $nssm set $serviceName Description 'Adds /v1/models compatibility for Claude Code when cc-switch routes to the Qwen sanitizer.'
& $nssm set $serviceName Start SERVICE_AUTO_START
& $nssm set $serviceName AppStdout (Join-Path $serviceLogDir 'claude-code-qwen-model-shim.stdout.log')
& $nssm set $serviceName AppStderr (Join-Path $serviceLogDir 'claude-code-qwen-model-shim.stderr.log')
& $nssm set $serviceName AppRotateFiles 1
& $nssm set $serviceName AppRotateOnline 1
& $nssm set $serviceName AppRotateBytes 1048576

$svc = Get-Service -Name $serviceName
if ($svc.Status -ne 'Running') {
  Start-Service -Name $serviceName
}

Start-Sleep -Seconds 2
Get-Service -Name $serviceName | Select-Object Name,Status,StartType
