# Canonical construction rules:
# 1. This supervisor is the single lifecycle owner for all provider children.
# 2. Each provider is declared once in $configs and owns one unique listener.
# 3. Provider-specific behavior is expressed by the child script and its
#    environment contract, not by a second startup/watchdog path.
# 4. Adding a provider means adding one complete config entry here; do not add
#    another NSSM service or a login Run item for the same provider.
$ErrorActionPreference = 'Stop'

function Resolve-Node {
  $candidates = @()
  foreach ($name in @('CC_SWITCH_SANITIZER_NODE', 'READ_SANITIZER_NODE', 'DEEPSEEK_FILTER_NODE')) {
    $value = [Environment]::GetEnvironmentVariable($name)
    if ($value) { $candidates += $value }
  }
  $nodeCommand = Get-Command node -ErrorAction SilentlyContinue
  if ($nodeCommand) { $candidates += $nodeCommand.Source }
  $candidates += @(
    'E:\nodejs\node-v22.22.0-win-x64\node.exe',
    '@@NODE_EXE:win@@',
    '@@PROGRAMFILES:win@@ (x86)\nodejs\node.exe'
  )
  foreach ($candidate in $candidates) {
    if ($candidate -and (Test-Path -LiteralPath $candidate)) {
      return (Resolve-Path -LiteralPath $candidate).Path
    }
  }
  throw 'node.exe was not found.'
}

function Set-ChildEnvironment {
  param(
    [Parameter(Mandatory = $true)]$ProcessStartInfo,
    [Parameter(Mandatory = $true)][hashtable]$Values
  )

  if ($ProcessStartInfo.PSObject.Properties.Name -contains 'Environment') {
    $target = $ProcessStartInfo.Environment
  } else {
    $target = $ProcessStartInfo.EnvironmentVariables
  }
  foreach ($entry in $Values.GetEnumerator()) {
    $target[[string]$entry.Key] = [string]$entry.Value
  }
}

$node = Resolve-Node
$root = $PSScriptRoot
$readProxy = Join-Path $root 'read-tool-sanitizer-proxy.js'
$deepseekProxy = Join-Path $root 'deepseek-thinking-filter-proxy.js'
$ccSwitchSettingsPath = Join-Path $env:USERPROFILE '.cc-switch\settings.json'
$claudeSettingsPath = Join-Path $env:USERPROFILE '.claude\settings.json'
$deepseekProviderId = $env:CC_SWITCH_DEEPSEEK_PROVIDER_ID
$qwenUpstream = if ($env:CC_SWITCH_QWEN_UPSTREAM) { $env:CC_SWITCH_QWEN_UPSTREAM } else { 'https://api.a2agent.me' }
$glmUpstream = if ($env:CC_SWITCH_GLM_UPSTREAM) { $env:CC_SWITCH_GLM_UPSTREAM } else { 'https://api.a2agent.me' }

function Set-JsonProperty {
  param(
    [Parameter(Mandatory = $true)]$Object,
    [Parameter(Mandatory = $true)][string]$Name,
    [Parameter(Mandatory = $true)]$Value
  )
  if ($Object.PSObject.Properties.Name -contains $Name) {
    $Object.$Name = $Value
  } else {
    $Object | Add-Member -NotePropertyName $Name -NotePropertyValue $Value
  }
}

function Ensure-ClaudeDeepSeekSettings {
  if (-not $deepseekProviderId) { return }
  if (-not (Test-Path -LiteralPath $ccSwitchSettingsPath)) { return }
  if (-not (Test-Path -LiteralPath $claudeSettingsPath)) { return }
  try {
    $ccSwitchSettings = Get-Content -LiteralPath $ccSwitchSettingsPath -Raw | ConvertFrom-Json
    if ($ccSwitchSettings.currentProviderClaude -ne $deepseekProviderId) { return }

    $claudeSettings = Get-Content -LiteralPath $claudeSettingsPath -Raw | ConvertFrom-Json
    if (-not $claudeSettings.env) {
      $claudeSettings | Add-Member -NotePropertyName 'env' -NotePropertyValue ([pscustomobject]@{})
    }
    if ($claudeSettings.env.ANTHROPIC_BASE_URL -ne 'http://127.0.0.1:15735') {
      Set-JsonProperty -Object $claudeSettings.env -Name 'ANTHROPIC_BASE_URL' -Value 'http://127.0.0.1:15735'
      $json = $claudeSettings | ConvertTo-Json -Depth 10
      [IO.File]::WriteAllText($claudeSettingsPath, $json + [Environment]::NewLine, [Text.UTF8Encoding]::new($false))
    }
  } catch {
    # Settings may be temporarily locked; the filter itself must stay alive.
  }
}

$configs = @(
  [pscustomobject]@{
    Name = 'qwen'; Port = '15727'; Upstream = $qwenUpstream; Script = $readProxy
    LogDir = (Join-Path $root 'logs-qwen'); EnsureSettings = $false
    Env = @{
      READ_SANITIZER_HOST = '127.0.0.1'; READ_SANITIZER_PORT = '15727'; READ_SANITIZER_UPSTREAM = $qwenUpstream
      READ_SANITIZER_LOG_DIR = (Join-Path $root 'logs-qwen'); READ_SANITIZER_STRIP_EMPTY_THINKING = '1'
      READ_SANITIZER_TEXT_ONLY_MESSAGE_CONTENT = '0'; READ_SANITIZER_PROMOTE_TOOL_TEXT = '1'
      READ_SANITIZER_ENFORCE_READ_FILE_PATH = '1'; READ_SANITIZER_MODELS_LIST = 'qwen3.8-max'
    }
  },
  [pscustomobject]@{
    Name = 'glm'; Port = '15726'; Upstream = $glmUpstream; Script = $readProxy
    LogDir = (Join-Path $root 'logs-glm'); EnsureSettings = $false
    Env = @{
      READ_SANITIZER_HOST = '127.0.0.1'; READ_SANITIZER_PORT = '15726'; READ_SANITIZER_UPSTREAM = $glmUpstream
      READ_SANITIZER_LOG_DIR = (Join-Path $root 'logs-glm'); READ_SANITIZER_STRIP_EMPTY_THINKING = '1'
      READ_SANITIZER_TEXT_ONLY_MESSAGE_CONTENT = '1'; READ_SANITIZER_PROMOTE_TOOL_TEXT = '1'
    }
  },
  [pscustomobject]@{
    Name = 'codex'; Port = '15729'; Upstream = 'https://chatgpt.com/backend-api/codex'; Script = $readProxy
    LogDir = (Join-Path $root 'logs-codex'); EnsureSettings = $false
    Env = @{
      READ_SANITIZER_HOST = '127.0.0.1'; READ_SANITIZER_PORT = '15729'; READ_SANITIZER_UPSTREAM = 'https://chatgpt.com/backend-api/codex'
      READ_SANITIZER_LOG_DIR = (Join-Path $root 'logs-codex'); READ_SANITIZER_STRIP_EMPTY_THINKING = '1'
      READ_SANITIZER_TEXT_ONLY_MESSAGE_CONTENT = '1'; READ_SANITIZER_PROMOTE_TOOL_TEXT = '0'
      READ_SANITIZER_ENFORCE_READ_FILE_PATH = '1'; READ_SANITIZER_REPAIR_TOOL_JSON = '1'
    }
  },
  [pscustomobject]@{
    Name = 'codex-claude'; Port = '15728'; Upstream = 'http://127.0.0.1:15733'; Script = $readProxy
    LogDir = (Join-Path $root 'logs-codex-claude'); EnsureSettings = $false
    Env = @{
      READ_SANITIZER_HOST = '127.0.0.1'; READ_SANITIZER_PORT = '15728'; READ_SANITIZER_UPSTREAM = 'http://127.0.0.1:15733'
      READ_SANITIZER_LOG_DIR = (Join-Path $root 'logs-codex-claude'); READ_SANITIZER_TEXT_ONLY_MESSAGE_CONTENT = '1'
      READ_SANITIZER_ENFORCE_READ_FILE_PATH = '1'; READ_SANITIZER_STRIP_EMPTY_THINKING = '0'
      READ_SANITIZER_REPAIR_TOOL_JSON = '1'; READ_SANITIZER_PROMOTE_TOOL_TEXT = '0'
    }
  },
  [pscustomobject]@{
    Name = 'deepseek'; Port = '15735'; Upstream = 'http://127.0.0.1:15733'; Script = $deepseekProxy
    LogDir = (Join-Path $root 'logs-deepseek'); EnsureSettings = $true
    Env = @{
      DEEPSEEK_FILTER_HOST = '127.0.0.1'; DEEPSEEK_FILTER_PORT = '15735'; DEEPSEEK_FILTER_UPSTREAM = 'http://127.0.0.1:15733'
      DEEPSEEK_FILTER_LOG_DIR = (Join-Path $root 'logs-deepseek')
    }
  }
)

function Start-Child($Config) {
  New-Item -ItemType Directory -Force -Path $Config.LogDir | Out-Null
  $psi = [Diagnostics.ProcessStartInfo]::new()
  $psi.FileName = $node
  $psi.Arguments = "`"$($Config.Script)`""
  $psi.WorkingDirectory = $root
  $psi.UseShellExecute = $false
  Set-ChildEnvironment -ProcessStartInfo $psi -Values $Config.Env
  $proc = [Diagnostics.Process]::Start($psi)
  Write-Host "Started $($Config.Name) sanitizer on port $($Config.Port) (PID $($proc.Id))"
  return $proc
}

$active = @{}
foreach ($config in $configs) {
  if ($config.EnsureSettings) { Ensure-ClaudeDeepSeekSettings }
  $active[$config.Name] = Start-Child $config
}

try {
  while ($true) {
    Start-Sleep -Seconds 5
    foreach ($config in $configs) {
      if ($config.EnsureSettings) { Ensure-ClaudeDeepSeekSettings }
      $proc = $active[$config.Name]
      if (-not $proc -or $proc.HasExited) {
        Write-Host "$($config.Name) sanitizer on port $($config.Port) exited. Restarting..."
        $active[$config.Name] = Start-Child $config
      }
    }
  }
} finally {
  foreach ($proc in $active.Values) {
    if ($proc -and -not $proc.HasExited) {
      Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
    }
  }
}
