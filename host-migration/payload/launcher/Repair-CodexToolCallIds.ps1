param(
  [switch]$DryRun,
  [string]$Target
)

$ErrorActionPreference = 'Stop'

# Wrapper around Repair-CodexToolCallIds.py.
# Default: full scan of Codex++ sessions (all history, any age, since any old
# session may be replayed when the user switches models mid-session).
# -Target <path>: repair a single file or directory.
# -DryRun: run the Python script's per-file path without writing (still uses
#          the python script; note the python script always writes — DryRun
#          here only prevents the batch invocation, kept for future use).

$pyScript = Join-Path $PSScriptRoot 'Repair-CodexToolCallIds.py'
if (-not (Test-Path -LiteralPath $pyScript)) {
  throw "Repair-CodexToolCallIds.py not found at $pyScript"
}

$python = $null
# Resolve the pinned interpreter first: on a fresh Windows host a bare "python"
# is the Microsoft Store alias, which resolves and then fails without output.
$pinnedPython = '@@PYTHON_EXE:win@@'
if (Test-Path -LiteralPath $pinnedPython -PathType Leaf) {
  $python = [pscustomobject]@{ Source = $pinnedPython }
} else {
  $python = (Get-Command python -ErrorAction SilentlyContinue)
  if (-not $python) {
    $python = (Get-Command py -ErrorAction SilentlyContinue)
  }
}
if (-not $python) {
  throw 'python interpreter not found. Install Python or add it to PATH.'
}
$pythonExe = $python.Source

if ($Target) {
  Write-Host "[Repair] Target mode: $Target"
  & $pythonExe $pyScript $Target
} else {
  Write-Host '[Repair] Full-scan mode: @@CODEXPP_HOME:win@@\sessions (all history)'
  & $pythonExe $pyScript
}

$exit = $LASTEXITCODE
Write-Host "[Repair] Python exit code: $exit"
exit $exit
