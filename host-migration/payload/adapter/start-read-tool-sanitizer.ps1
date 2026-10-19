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
$env:READ_SANITIZER_PORT = '15722'
$env:READ_SANITIZER_UPSTREAM = 'http://127.0.0.1:48760'
$env:READ_SANITIZER_LOG_DIR = Join-Path $PSScriptRoot 'logs'
$env:READ_SANITIZER_REPAIR_TOOL_JSON = '1'

& $node $script
