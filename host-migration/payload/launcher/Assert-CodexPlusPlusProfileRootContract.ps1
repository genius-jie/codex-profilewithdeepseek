#requires -Version 7.0

function Assert-CodexPlusPlusProfileRootContract {
    [CmdletBinding()]
    param()

    $profilePath = [IO.Path]::GetFullPath('@@USERPROFILE:win@@\AppData\Roaming\CodexPlusPlusProfile').TrimEnd('\')
    $requiredCanonicalPath = [IO.Path]::GetFullPath('@@CODEXPP_PROFILE:win@@').TrimEnd('\')

    if (Test-Path -LiteralPath $profilePath) {
        throw "Retired Codex++ C: profile alias must be absent: $profilePath"
    }

    # The Electron profile and the CLI must share one physical D: CODEX_HOME.
    # Electron already owns this nested path under its user-data root, so make
    # it the canonical home instead of linking it back through the C: alias.
    $canonicalCodexHome = Join-Path $requiredCanonicalPath 'AppData\Roaming\Codex\.codex'
    $canonicalRuntimeRoot = Join-Path $requiredCanonicalPath 'AppData\Roaming\codex-plusplus'
    $canonicalOpenCliRoot = Join-Path $requiredCanonicalPath '.opencli\clis'
    foreach ($physicalDirectory in @(
        $requiredCanonicalPath,
        (Join-Path $requiredCanonicalPath 'AppData\Roaming\Codex'),
        $canonicalCodexHome,
        $canonicalRuntimeRoot,
        $canonicalOpenCliRoot
    )) {
        if (-not (Test-Path -LiteralPath $physicalDirectory -PathType Container)) {
            throw "Codex++ canonical profile directory is missing: $physicalDirectory"
        }
        $physicalItem = Get-Item -LiteralPath $physicalDirectory -Force
        if (-not ($physicalItem -is [IO.DirectoryInfo]) -or
            $physicalItem.Attributes -band [IO.FileAttributes]::ReparsePoint) {
            throw "Codex++ canonical profile directory must be physical, not a reparse point: $physicalDirectory"
        }
    }

    [pscustomobject]@{
        ProfileAlias = $null
        CanonicalRoot = $requiredCanonicalPath
        CanonicalCodexHome = $canonicalCodexHome
        CanonicalRuntimeRoot = $canonicalRuntimeRoot
        CanonicalOpenCliRoot = $canonicalOpenCliRoot
    }
}
