#requires -Version 7.0
# Invoke-CodexPlusPlusEnsureWorkspace.ps1
# Launch preflight guard: guarantee the Codex++ project-workspace parent chain
# exists before the app starts.
#
# Root cause it prevents: Codex++ creates per-day project dirs at
#   <profile>\Documents\Codex\<YYYY-MM-DD> with a NON-recursive mkdir. If the
#   parent Documents\Codex is not yet present at that instant, the app throws
#   "ENOENT: no such file or directory, mkdir '...\Documents\Codex\<date>'".
# Ensuring the PARENT exists at launch removes that precondition failure. We
# deliberately do NOT pre-create the date leaf (the app owns that; pre-creating
# it would make the app's non-recursive mkdir fail with EEXIST instead).
#
# Writes only on the physical D canonical path. Idempotent.
param(
    [string]$ProfileRoot = '@@CODEXPP_PROFILE:win@@'
)
$ErrorActionPreference = 'SilentlyContinue'
$profileRoot = [IO.Path]::GetFullPath($ProfileRoot).TrimEnd('\')
$codexHome = Join-Path $profileRoot 'AppData\Roaming\Codex\.codex'
$runtimeRoot = Join-Path $profileRoot 'AppData\Roaming\codex-plusplus'
$logDir = Join-Path $runtimeRoot 'log'
New-Item -ItemType Directory -Path $logDir -Force | Out-Null
$log = Join-Path $logDir ("ensure_workspace_{0}.log" -f (Get-Date -Format 'yyyyMMdd'))
function L($m){ $line='[{0}] {1}' -f (Get-Date -Format 's'),$m; Add-Content -Path $log -Value $line; Write-Host $line }

# Guard: the profile root and CODEX_HOME must be physical D directories.
if (-not (Test-Path -LiteralPath $profileRoot -PathType Container) -or
    -not (Test-Path -LiteralPath $codexHome -PathType Container)) {
    throw "Codex++ physical D profile is incomplete: $profileRoot / $codexHome"
}
foreach ($physicalPath in @($profileRoot, (Join-Path $profileRoot 'AppData'), (Join-Path $profileRoot 'AppData\Roaming'), (Join-Path $profileRoot 'AppData\Roaming\Codex'), $codexHome, $runtimeRoot)) {
    $item = Get-Item -LiteralPath $physicalPath -Force
    if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) {
        throw "Codex++ workspace path must be physical: $physicalPath"
    }
}
foreach ($d in @((Join-Path $profileRoot 'Documents'), (Join-Path $profileRoot 'Documents\Codex'))) {
    if (-not (Test-Path $d)) {
        New-Item -ItemType Directory -Path $d -Force | Out-Null
        L "created $d"
    }
}

# Auto-heal: ensure projectlessWorkspaceRoot in config.toml points to canonical D root rather than C junction or date subfolder
$configPath = Join-Path $codexHome 'config.toml'
if (Test-Path $configPath) {
    $content = [System.IO.File]::ReadAllText($configPath, [System.Text.Encoding]::UTF8)
    if ($content -match "projectlessWorkspaceRoot\s*=\s*['""](.*?)['""]") {
        $currRoot = $matches[1]
        $canonicalRoot = Join-Path $ProfileRoot 'Documents\Codex'
        $currIsPhysicalD = $currRoot.StartsWith(($profileRoot + '\\'), [StringComparison]::OrdinalIgnoreCase)
        if ($currRoot -ne $canonicalRoot -and ((-not $currIsPhysicalD) -or $currRoot -match '\\202\d-\d{2}-\d{2}')) {
            $newContent = $content -replace "projectlessWorkspaceRoot\s*=\s*['""][^'""]+['""]", "projectlessWorkspaceRoot = '$canonicalRoot'"
            [System.IO.File]::WriteAllText($configPath, $newContent, (New-Object System.Text.UTF8Encoding $false))
            L "healed projectlessWorkspaceRoot in config.toml to $canonicalRoot"
        }
    }
}

L "workspace parent chain OK under $profileRoot"
exit 0
