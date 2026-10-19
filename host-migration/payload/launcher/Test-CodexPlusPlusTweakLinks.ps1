#requires -Version 7.0

[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$codexPlusPlusRoot = '@@CODEXPP_RUNTIME:win@@'
$canonicalSourceBase = [IO.Path]::GetFullPath('@@CODEXPP_SOURCE_PARENT:win@@').TrimEnd('\')
$canonicalSourceRoot = Join-Path $canonicalSourceBase 'source'

function Normalize-Path([string]$Path) {
    if ([string]::IsNullOrWhiteSpace($Path)) { return $null }
    [IO.Path]::GetFullPath($Path).TrimEnd('\')
}

function Get-LinkTarget($Item) {
    $targets = @($Item.Target | Where-Object { -not [string]::IsNullOrWhiteSpace([string]$_) })
    if ($targets.Count -ne 1) { return $null }
    [string]$targets[0]
}

$failures = [Collections.Generic.List[string]]::new()
$checked = [Collections.Generic.List[object]]::new()

if (Test-Path -LiteralPath '@@CODEX_HOME:win@@-plusplus') {
    $failures.Add('Retired Codex++ source alias remains on C:')
}

$tweaksDir = Join-Path $codexPlusPlusRoot 'tweaks'
if (-not (Test-Path -LiteralPath $tweaksDir -PathType Container)) {
    $failures.Add("Codex++ tweaks directory missing: $tweaksDir")
} else {
    foreach ($directory in Get-ChildItem -LiteralPath $tweaksDir -Directory -Force) {
        $item = Get-Item -LiteralPath $directory.FullName -Force
        if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) {
            $failures.Add("Codex++ runtime tweak directory must be physical on D: $($item.FullName)")
            continue
        }

        $target = Normalize-Path $item.FullName
        $manifest = Join-Path $item.FullName 'manifest.json'
        $targetKind = 'physical_runtime'
        $manifestPresent = Test-Path -LiteralPath $manifest -PathType Leaf
        $checked.Add([pscustomobject]@{
            id = $item.Name
            link = $item.FullName
            target = $target
            target_kind = $targetKind
            manifest_present = $manifestPresent
        })
        if (-not $manifestPresent) {
            $failures.Add("Broken Codex++ tweak link: $($item.FullName) -> $target")
        }
    }
}

$result = [ordered]@{
    guard = 'codexplusplus_tweak_link_check'
    status = if ($failures.Count -eq 0) { 'pass' } else { 'fail' }
    canonical_source_base = $canonicalSourceBase
    retired_source_alias = $null
    checked = @($checked)
    failures = @($failures)
}

if ($failures.Count -gt 0) {
    'CODEXPP_TWEAK_LINK_CHECK_FAIL'
    $result | ConvertTo-Json -Depth 8
    exit 1
}

'CODEXPP_TWEAK_LINK_CHECK_PASS'
$result | ConvertTo-Json -Depth 8
exit 0
