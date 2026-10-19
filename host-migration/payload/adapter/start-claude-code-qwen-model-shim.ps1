$ErrorActionPreference = 'Stop'

function Resolve-Node {
  $candidates = @()
  if ($env:READ_SANITIZER_NODE) {
    $candidates += $env:READ_SANITIZER_NODE
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

  throw 'node.exe was not found. Set READ_SANITIZER_NODE or install Node.js.'
}

$node = Resolve-Node
$script = Join-Path $PSScriptRoot 'read-tool-sanitizer-proxy.js'

$env:READ_SANITIZER_HOST = '127.0.0.1'
$env:READ_SANITIZER_PORT = '15725'
$env:READ_SANITIZER_UPSTREAM = 'http://127.0.0.1:15723'
$env:READ_SANITIZER_MODELS_UPSTREAM = 'http://127.0.0.1:15727/v1/models'
$env:READ_SANITIZER_LOG_DIR = Join-Path $PSScriptRoot 'logs-claude-code-qwen-model-shim'

& $node $script
