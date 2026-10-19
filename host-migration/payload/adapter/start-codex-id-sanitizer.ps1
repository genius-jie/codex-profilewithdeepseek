$ErrorActionPreference = 'Stop'

function Resolve-Node {
  $candidates = @()
  if ($env:CODEX_SANITIZER_NODE) {
    $candidates += $env:CODEX_SANITIZER_NODE
  }
  $nodeCommand = Get-Command node -ErrorAction SilentlyContinue
  if ($nodeCommand) {
    $candidates += $nodeCommand.Source
  }
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
  throw 'node.exe was not found. Set CODEX_SANITIZER_NODE or install Node.js.'
}

$node = Resolve-Node
$script = Join-Path $PSScriptRoot 'codex-id-sanitizer-proxy.js'

$env:CODEX_SANITIZER_HOST     = '127.0.0.1'
$env:CODEX_SANITIZER_PORT     = '15740'
# Upstream is the local CodexManager gateway (port 48760), which routes to
# either OpenAI-native or third-party models based on the `model` field.
# Do NOT point this at a third-party endpoint directly — the sanitizer must
# sit between the Codex++ client and the gateway so every model switch is
# covered regardless of which upstream the gateway selects.
$env:CODEX_SANITIZER_UPSTREAM = 'http://127.0.0.1:48760'
$env:CODEX_SANITIZER_LOG_DIR  = Join-Path $PSScriptRoot 'logs-codex-id'

New-Item -ItemType Directory -Force -Path $env:CODEX_SANITIZER_LOG_DIR | Out-Null

& $node $script
