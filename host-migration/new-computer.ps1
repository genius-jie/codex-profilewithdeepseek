#requires -Version 7.0
<#
New-computer entry. Preview by default; no dependency install or app launch.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$GeneralRoot,
    [Parameter(Mandatory)][string]$CodexPlusPlusProfile,
    [ValidateSet('Plan','Apply','Check')][string]$Mode = 'Plan',
    [ValidateSet('codex','codex_plus_plus','claude_code')][string[]]$Hosts = @('codex','codex_plus_plus','claude_code'),
    [string]$UserProfile = [Environment]::GetFolderPath('UserProfile'),
    [string]$PythonExe,
    [string]$NodeExe,
    [string]$CodeXPlusPlusSource,
    [string]$WorkspaceRoot,
    [string]$Receipt,
    [switch]$WithSupport,
    [switch]$Managed,
    [switch]$SmokeHooks
)
$ErrorActionPreference = 'Stop'
if (-not $PythonExe) {
    $candidate = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($candidate -and $candidate.Source -notlike '*\Microsoft\WindowsApps\*') {
        $PythonExe = $candidate.Source
    } else {
        throw 'Python 3.11+ was not found. Install it, then pass -PythonExe with its actual path.'
    }
}
& $PythonExe -c 'import sys; assert sys.version_info >= (3, 11), "Python 3.11+ required"'
if ($LASTEXITCODE -ne 0) { throw 'Python preflight failed.' }
if (-not $NodeExe) {
    $nodeCommand = Get-Command node.exe -ErrorAction SilentlyContinue
    $NodeExe = if ($nodeCommand) { $nodeCommand.Source } else { Join-Path $env:ProgramFiles 'nodejs\node.exe' }
}
if (-not $WorkspaceRoot) { $WorkspaceRoot = Join-Path $UserProfile 'Documents\AgentProjects' }
if (-not $CodeXPlusPlusSource) { $CodeXPlusPlusSource = Join-Path (Split-Path -Parent $CodexPlusPlusProfile) 'AgentTools\codex-plusplus\source' }
$layout = [ordered]@{
    user_profile = [IO.Path]::GetFullPath($UserProfile)
    codexpp_profile = [IO.Path]::GetFullPath($CodexPlusPlusProfile)
    general_root = [IO.Path]::GetFullPath($GeneralRoot)
    python_exe = [IO.Path]::GetFullPath($PythonExe)
    powershell_exe = Join-Path $PSHOME 'pwsh.exe'
    node_exe = [IO.Path]::GetFullPath($NodeExe)
    program_files = $env:ProgramFiles
    system_root = $env:SystemRoot
    codexpp_source = [IO.Path]::GetFullPath($CodeXPlusPlusSource)
    suite_root = Join-Path $WorkspaceRoot 'personal-ai-suite'
    core_root = Join-Path $WorkspaceRoot 'personal-ai-suite\automation-core'
    testing_root = Join-Path $WorkspaceRoot 'AI测试用例'
    openclaw_root = Join-Path $WorkspaceRoot 'openclaw-mono'
}
$jsonLayout = $layout | ConvertTo-Json -Depth 8 -Compress
$restore = Join-Path $PSScriptRoot 'tools\restore.py'
if ($Mode -eq 'Check') {
    $readyArgs = @((Join-Path $PSScriptRoot 'tools\readiness.py'), '--layout', '-', '--hosts', ($Hosts -join ','))
    if ($SmokeHooks) { $readyArgs += '--smoke-hooks' }
    $jsonLayout | & $PythonExe -X utf8 @readyArgs
    if ($LASTEXITCODE -ne 0) { throw 'New-computer readiness is incomplete; see the missing items above.' }
    return
}
$restoreArgs = @($restore, $Mode.ToLowerInvariant(), '--layout', '-', '--hosts', ($Hosts -join ','))
if ($Managed) { $restoreArgs += '--managed' }
if ($WithSupport) { $restoreArgs += @('--support', 'launcher,adapter,ccs_mcp,codexpp_source,codexpp_tweaks') }
if ($Mode -eq 'Apply') {
    if (-not $Receipt) { throw 'Apply requires -Receipt pointing to a new private JSON receipt outside the Git repository.' }
    $restoreArgs += @('--receipt', [IO.Path]::GetFullPath($Receipt))
    $jsonLayout | & $PythonExe -X utf8 @restoreArgs
    if ($LASTEXITCODE -ne 0) { throw 'Restore stopped. Existing files were preserved; inspect the receipt if one was created.' }
} else {
    $output = @($jsonLayout | & $PythonExe -X utf8 @restoreArgs)
    if ($LASTEXITCODE -ne 0) { throw 'Migration preview failed.' }
    $plan = ($output -join "`n") | ConvertFrom-Json
    [ordered]@{ create = $plan.create; identical = $plan.identical; collisions = @($plan.collisions); selected_hosts = $Hosts; default_is_preview = $true } | ConvertTo-Json -Depth 8
}
