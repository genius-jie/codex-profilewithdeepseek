$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$coreCommand = '@@SUITE_ROOT:win@@\bin\automation-core.cmd'
$scriptsRoot = Split-Path -Parent $MyInvocation.MyCommand.Path

if (-not (Test-Path -LiteralPath $coreCommand -PathType Leaf)) {
    [Console]::Error.WriteLine("automation-core command not found: $coreCommand")
    exit 2
}

$pathParts = @($scriptsRoot)
if ($env:PYTHONPATH) {
    $pathParts += $env:PYTHONPATH
}
$env:PYTHONPATH = $pathParts -join [IO.Path]::PathSeparator

$forwarded = @($args)
& $coreCommand @forwarded
exit $LASTEXITCODE
