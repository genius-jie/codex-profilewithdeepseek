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

$env:READ_SANITIZER_HOST = '127.0.0.1'
$env:READ_SANITIZER_PORT = '15726'
$env:READ_SANITIZER_UPSTREAM = 'https://api.a2agent.me'
$env:READ_SANITIZER_LOG_DIR = Join-Path $PSScriptRoot 'logs-glm'
$env:READ_SANITIZER_TEXT_ONLY_MESSAGE_CONTENT = '1'
$env:READ_SANITIZER_STRIP_EMPTY_THINKING = '1'

& (Resolve-Node) (Join-Path $PSScriptRoot 'read-tool-sanitizer-proxy.js')
