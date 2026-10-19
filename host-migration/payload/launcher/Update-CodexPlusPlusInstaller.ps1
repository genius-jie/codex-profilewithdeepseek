#requires -Version 7.0

[CmdletBinding()]
param(
    [ValidateSet('Check', 'Update')]
    [string]$Mode = 'Update',
    [string]$Repo = '',
    [string]$Ref = '',
    [switch]$Force
)

# Stateless, one-shot owner for Codex++ installer source updates. Native source
# replacement is allowed only inside this transaction so the PowerShell 7
# overlay is reapplied and validated before the updated CLI becomes authoritative.
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

$powerShell7 = '@@POWERSHELL_EXE:win@@'
$nodeExe = 'E:\nodejs\node-v22.22.0-win-x64\node.exe'
$npmExe = 'E:\nodejs\node-v22.22.0-win-x64\npm.cmd'
$sourceRoot = '@@CODEXPP_SOURCE:win@@'
$previousRoot = '@@CODEXPP_SOURCE:win@@.previous'
$nativeCli = Join-Path $sourceRoot 'packages\installer\dist\cli.js'
$syncEntry = '@@LAUNCHER_ROOT:win@@\Sync-CodexPlusPlusLatest.ps1'
$runtimeConfig = '@@CODEXPP_RUNTIME:win@@\config.json'
$runtimeBin = '@@CODEXPP_RUNTIME:win@@\bin'
$canonicalRuntimeRoot = '@@CODEXPP_RUNTIME:win@@'
$publicBin = '@@USERPROFILE:win@@\AppData\Local\Microsoft\WindowsApps'
$cliShimTemplate = '@@LAUNCHER_ROOT:win@@\CodexPlusPlus-ControlledCliShim.cmd.template'
$storeRoot = '@@CODEXPP_INSTALL_ROOT:win@@\store-apps'
$profileRoot = '@@CODEXPP_PROFILE:win@@'
$profileRoots = @($profileRoot)
$watcherTaskNames = @('codex-plusplus-watcher', 'codex-plusplus-watcher-interval', 'codex-plusplus-watcher-hourly', 'codex-plusplus-watcher-daily')
$sourceMutex = $null
$sourceMutexTaken = $false
$env:CODEX_PLUSPLUS_HOME = $canonicalRuntimeRoot

function Enter-SourceUpdateMutex {
    $script:sourceMutex = [Threading.Mutex]::new($false, 'CodexPlusPlusInstallerSourceUpdate')
    try {
        $script:sourceMutexTaken = $script:sourceMutex.WaitOne([TimeSpan]::FromMinutes(5))
    } catch [Threading.AbandonedMutexException] {
        $script:sourceMutexTaken = $true
    }
    if (-not $script:sourceMutexTaken) {
        throw 'Timed out waiting for the Codex++ source/update maintenance lock.'
    }
}

function Exit-SourceUpdateMutex {
    if ($script:sourceMutexTaken -and $script:sourceMutex) {
        $script:sourceMutex.ReleaseMutex()
        $script:sourceMutexTaken = $false
    }
    if ($script:sourceMutex) {
        $script:sourceMutex.Dispose()
        $script:sourceMutex = $null
    }
}

function Assert-FixedEnvironment {
    foreach ($leaf in @($powerShell7, $nodeExe, $npmExe, $nativeCli, $syncEntry, $runtimeConfig, $cliShimTemplate)) {
        if (-not (Test-Path -LiteralPath $leaf -PathType Leaf)) {
            throw "Required Codex++ update file is missing: $leaf"
        }
    }
    if ($PSVersionTable.PSVersion.Major -lt 7) {
        throw 'Codex++ installer update requires PowerShell 7.'
    }
    $resolvedSource = [IO.Path]::GetFullPath((Resolve-Path -LiteralPath $sourceRoot).Path).TrimEnd('\')
    if (-not [string]::Equals($resolvedSource, [IO.Path]::GetFullPath($sourceRoot).TrimEnd('\'), [StringComparison]::OrdinalIgnoreCase)) {
        throw "Codex++ source root resolved unexpectedly: $resolvedSource"
    }
    if ((Get-Item -LiteralPath $resolvedSource -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) {
        throw "Codex++ source root must be physical: $resolvedSource"
    }
}

function Test-CodexPlusPlusProfileRunning {
    $storePrefix = [IO.Path]::GetFullPath($storeRoot).TrimEnd('\') + '\'
    $ownedNames = @('ChatGPT.exe', 'Codex.exe', 'codex.exe', 'node.exe', 'node_repl.exe', 'codex-code-mode-host.exe')
    return [bool](Get-CimInstance Win32_Process | Where-Object {
        $path = [string]$_.ExecutablePath
        $commandLine = [string]$_.CommandLine
        $name = if ($path) { [IO.Path]::GetFileName($path) } else { '' }
        ($path -and $path.StartsWith($storePrefix, [StringComparison]::OrdinalIgnoreCase) -and ($ownedNames -contains $name)) -or
        ($commandLine -and @($profileRoots | Where-Object {
            $commandLine.IndexOf("--user-data-dir=$_", [StringComparison]::OrdinalIgnoreCase) -ge 0 -or
            $commandLine.IndexOf("--user-data-dir=`"$_`"", [StringComparison]::OrdinalIgnoreCase) -ge 0
        }).Count -gt 0)
    } | Select-Object -First 1)
}

function Get-OverlayPlan {
    $constantPath = Join-Path $sourceRoot 'packages\installer\src\windows-powershell.ts'
    $constantText = @'
/** The only supported PowerShell host for Codex++ on Windows. */
export const WINDOWS_POWERSHELL_7_EXE = "@@POWERSHELL_EXE:escaped@@";
'@
    $specs = @(
        [pscustomobject]@{
            Path = Join-Path $sourceRoot 'packages\installer\src\platform.ts'
            Import = 'import { WINDOWS_POWERSHELL_7_EXE } from "./windows-powershell.js";'
            Anchor = 'import { readPlist } from "./plist.js";'
        },
        [pscustomobject]@{
            Path = Join-Path $sourceRoot 'packages\installer\src\commands\debug.ts'
            Import = 'import { WINDOWS_POWERSHELL_7_EXE } from "../windows-powershell.js";'
            Anchor = 'import { userPaths, type UserPaths } from "../paths.js";'
        },
        [pscustomobject]@{
            Path = Join-Path $sourceRoot 'packages\installer\src\windows-cleanup.ts'
            Import = 'import { WINDOWS_POWERSHELL_7_EXE } from "./windows-powershell.js";'
            Anchor = 'import { join } from "node:path";'
        },
        [pscustomobject]@{
            Path = Join-Path $sourceRoot 'packages\installer\src\commands\install.ts'
            Import = 'import { WINDOWS_POWERSHELL_7_EXE } from "../windows-powershell.js";'
            Anchor = 'import { openCodex, quitCodex } from "../alerts.js";'
        }
    )

    $updates = [ordered]@{}
    foreach ($spec in $specs) {
        if (-not (Test-Path -LiteralPath $spec.Path -PathType Leaf)) {
            throw "Installer PowerShell call site changed; manual review required: $($spec.Path)"
        }
        $text = [IO.File]::ReadAllText($spec.Path)
        if ($text.IndexOf('WINDOWS_POWERSHELL_7_EXE', [StringComparison]::Ordinal) -lt 0 -and
            $text.IndexOf('powershell.exe', [StringComparison]::OrdinalIgnoreCase) -lt 0) {
            throw "Installer PowerShell call shape changed; manual review required: $($spec.Path)"
        }
        $text = $text.Replace('"powershell.exe"', 'WINDOWS_POWERSHELL_7_EXE')
        $text = $text.Replace("'powershell.exe'", 'WINDOWS_POWERSHELL_7_EXE')
        $text = [regex]::Replace($text, '"-ExecutionPolicy"\s*,\s*"Bypass"\s*,\s*', '', [Text.RegularExpressions.RegexOptions]::IgnoreCase)
        if ($text.IndexOf($spec.Import, [StringComparison]::Ordinal) -lt 0) {
            $anchorCount = ([regex]::Matches($text, [regex]::Escape($spec.Anchor))).Count
            if ($anchorCount -ne 1) {
                throw "Installer import anchor changed; manual review required: $($spec.Path)"
            }
            $newline = if ($text.Contains("`r`n")) { "`r`n" } else { "`n" }
            $text = $text.Replace($spec.Anchor, $spec.Anchor + $newline + $spec.Import)
        }
        if ($text -match '(?i)powershell\.exe|WindowsPowerShell|ExecutionPolicy|\bBypass\b') {
            throw "Retired PowerShell dependency remains after overlay planning: $($spec.Path)"
        }
        $updates[$spec.Path] = $text
    }
    $updates[$constantPath] = $constantText

    # Profile migration invariant: the runtime must never fall back to the
    # Windows user's C: home when CODEX_HOME is missing. Reapply this overlay
    # after every upstream source update so the newest official package keeps
    # the D: profile contract.
    $profileOverlaySpecs = @(
        [pscustomobject]@{
            Path = Join-Path $sourceRoot 'packages\runtime\src\main.ts'
            Old = 'const CODEX_CONFIG_FILE = join(homedir(), ".codex", "config.toml");'
            New = 'const CODEX_CONFIG_HOME = process.env.CODEX_HOME || "@@CODEXPP_HOME:escaped@@";`nconst CODEX_CONFIG_FILE = join(CODEX_CONFIG_HOME, "config.toml");'
        },
        [pscustomobject]@{
            Path = Join-Path $sourceRoot 'packages\runtime\dist\main.js'
            Old = 'var CODEX_CONFIG_FILE = (0, import_node_path9.join)((0, import_node_os2.homedir)(), ".codex", "config.toml");'
            New = 'var CODEX_CONFIG_HOME = process.env.CODEX_HOME || "@@CODEXPP_HOME:escaped@@";`nvar CODEX_CONFIG_FILE = (0, import_node_path9.join)(CODEX_CONFIG_HOME, "config.toml");'
        },
        [pscustomobject]@{
            Path = Join-Path $sourceRoot 'packages\installer\assets\runtime\main.js'
            Old = 'var CODEX_CONFIG_FILE = (0, import_node_path9.join)((0, import_node_os2.homedir)(), ".codex", "config.toml");'
            New = 'var CODEX_CONFIG_HOME = process.env.CODEX_HOME || "@@CODEXPP_HOME:escaped@@";`nvar CODEX_CONFIG_FILE = (0, import_node_path9.join)(CODEX_CONFIG_HOME, "config.toml");'
        },
        [pscustomobject]@{
            Path = Join-Path $sourceRoot 'tweaks\auto-follow-up\index.js'
            Old = 'return process.env.CODEX_HOME || "@@USERPROFILE:escaped@@\\AppData\\Roaming\\CodexPlusPlusProfile\\.codex";'
            New = 'return process.env.CODEX_HOME || "@@CODEXPP_HOME:escaped@@";'
        }
    )
    foreach ($spec in $profileOverlaySpecs) {
        if (-not (Test-Path -LiteralPath $spec.Path -PathType Leaf)) {
            throw "Codex++ D: profile overlay source missing: $($spec.Path)"
        }
        $text = [IO.File]::ReadAllText($spec.Path)
        if ($text.Contains($spec.New.Replace('`n', "`n"))) {
            $updates[$spec.Path] = $text
            continue
        }
        if (-not $text.Contains($spec.Old)) {
            throw "Codex++ D: profile overlay anchor changed; manual review required: $($spec.Path)"
        }
        $updates[$spec.Path] = $text.Replace($spec.Old, $spec.New.Replace('`n', "`n"))
    }
    return $updates
}

function Write-OverlayPlan([object]$Plan) {
    $encoding = [Text.UTF8Encoding]::new($false)
    foreach ($entry in $Plan.GetEnumerator()) {
        [IO.File]::WriteAllText([string]$entry.Key, [string]$entry.Value, $encoding)
    }
}

function Invoke-InstallerBuild {
    Push-Location -LiteralPath $sourceRoot
    try {
        $output = @(& $npmExe run build 2>&1)
        $exitCode = $LASTEXITCODE
    } finally {
        Pop-Location
    }
    if ($exitCode -ne 0) {
        throw "Codex++ installer build failed: $($output -join "`n")"
    }
}

function Invoke-InstallerTests {
    $groups = @(
        @('--import', 'tsx', '--test', '--test-name-pattern=parsePsOutput', 'packages/installer/test/debug.test.ts'),
        @('--import', 'tsx', '--test', '--test-name-pattern=inferCodexChannel', 'packages/installer/test/platform.test.ts'),
        @('--import', 'tsx', '--test', 'packages/installer/test/install-preflight.test.ts', 'packages/installer/test/windows-cleanup.test.ts')
    )
    Push-Location -LiteralPath $sourceRoot
    try {
        foreach ($arguments in $groups) {
            $output = @(& $nodeExe @arguments 2>&1)
            if ($LASTEXITCODE -ne 0) {
                throw "Codex++ installer targeted tests failed: $($output -join "`n")"
            }
        }
    } finally {
        Pop-Location
    }
}

function Assert-OverlayOnDisk {
    $roots = @(
        (Join-Path $sourceRoot 'packages\installer\src'),
        (Join-Path $sourceRoot 'packages\installer\dist')
    )
    $files = @(foreach ($root in $roots) {
        Get-ChildItem -LiteralPath $root -File -Recurse | Where-Object { $_.Extension -in @('.ts', '.js', '.map') }
    })
    $hits = @($files | Select-String -Pattern 'powershell\.exe|WindowsPowerShell|ExecutionPolicy|\bBypass\b' -CaseSensitive:$false)
    if ($hits.Count) {
        throw "Retired PowerShell dependency remains in installer src/dist: $($hits[0].Path):$($hits[0].LineNumber)"
    }
    $barePwshHits = @($files | Select-String -Pattern '"pwsh(?:\.exe)?"|''pwsh(?:\.exe)?''' -CaseSensitive:$false)
    if ($barePwshHits.Count) {
        throw "Bare pwsh lookup remains in installer src/dist: $($barePwshHits[0].Path):$($barePwshHits[0].LineNumber)"
    }
    foreach ($relative in @('platform.ts', 'commands\debug.ts', 'windows-cleanup.ts', 'commands\install.ts')) {
        $path = Join-Path (Join-Path $sourceRoot 'packages\installer\src') $relative
        $count = ([regex]::Matches([IO.File]::ReadAllText($path), 'WINDOWS_POWERSHELL_7_EXE')).Count
        if ($count -ne 2) {
            throw "Installer PS7 consumer must have exactly one import and one call: $path (count=$count)"
        }
    }
    foreach ($relative in @('platform.js', 'commands\debug.js', 'windows-cleanup.js', 'commands\install.js')) {
        $path = Join-Path (Join-Path $sourceRoot 'packages\installer\dist') $relative
        $count = ([regex]::Matches([IO.File]::ReadAllText($path), 'WINDOWS_POWERSHELL_7_EXE')).Count
        if ($count -ne 2) {
            throw "Built installer PS7 consumer must have exactly one import and one call: $path (count=$count)"
        }
    }
    $constantPath = Join-Path $sourceRoot 'packages\installer\src\windows-powershell.ts'
    $constant = [IO.File]::ReadAllText($constantPath)
    if ($constant.IndexOf('@@POWERSHELL_EXE:escaped@@', [StringComparison]::Ordinal) -lt 0) {
        throw 'Installer PowerShell 7 constant is missing or drifted.'
    }

    $profileSourceChecks = @(
        @{ Path = Join-Path $sourceRoot 'packages\runtime\src\main.ts'; Required = 'const CODEX_CONFIG_HOME = process.env.CODEX_HOME'; Forbidden = 'const CODEX_CONFIG_FILE = join(homedir(), ".codex", "config.toml");' },
        @{ Path = Join-Path $sourceRoot 'packages\runtime\dist\main.js'; Required = 'var CODEX_CONFIG_HOME = process.env.CODEX_HOME'; Forbidden = 'var CODEX_CONFIG_FILE = (0, import_node_path9.join)((0, import_node_os2.homedir)(), ".codex", "config.toml");' },
        @{ Path = Join-Path $sourceRoot 'packages\installer\assets\runtime\main.js'; Required = 'var CODEX_CONFIG_HOME = process.env.CODEX_HOME'; Forbidden = 'var CODEX_CONFIG_FILE = (0, import_node_path9.join)((0, import_node_os2.homedir)(), ".codex", "config.toml");' },
        @{ Path = Join-Path $sourceRoot 'tweaks\auto-follow-up\index.js'; Required = '@@CODEXPP_HOME:escaped@@'; Forbidden = '@@USERPROFILE:escaped@@\\AppData\\Roaming\\CodexPlusPlusProfile\\.codex' }
    )
    foreach ($check in $profileSourceChecks) {
        if (-not (Test-Path -LiteralPath $check.Path -PathType Leaf)) { throw "Codex++ D: profile overlay source missing: $($check.Path)" }
        $text = [IO.File]::ReadAllText($check.Path)
        if (-not $text.Contains($check.Required)) { throw "Codex++ D: profile overlay missing: $($check.Path)" }
        if ($text.Contains($check.Forbidden)) { throw "Codex++ C: profile fallback remains: $($check.Path)" }
    }
}

function Assert-UpdateBoundary {
    $config = Get-Content -LiteralPath $runtimeConfig -Raw | ConvertFrom-Json
    if ($config.codexPlusPlus.autoUpdate -ne $false) {
        throw 'Codex++ native auto-update must remain disabled.'
    }
    $watcherCmd = Join-Path $runtimeBin 'watcher.cmd'
    $watcherVbs = Join-Path $runtimeBin 'watcher.vbs'
    foreach ($path in @($watcherCmd, $watcherVbs)) {
        if (Test-Path -LiteralPath $path) {
            throw "Codex++ legacy watcher launcher remains: $path"
        }
    }
    $tasks = @(Get-ScheduledTask -TaskName $watcherTaskNames -ErrorAction SilentlyContinue)
    if ($tasks.Count) {
        throw "Codex++ legacy watcher tasks remain: $($tasks.TaskName -join ', ')"
    }
    $expectedShim = [IO.File]::ReadAllText($cliShimTemplate).Replace("`r`n", "`n").Replace("`n", "`r`n")
    $installRoute = $expectedShim.IndexOf('if /I "%~1"=="install" goto :managed_install', [StringComparison]::Ordinal)
    $nativePassthrough = $expectedShim.IndexOf('"E:\nodejs\node-v22.22.0-win-x64\node.exe" "@@CODEXPP_SOURCE:win@@\packages\installer\dist\cli.js" %*', [StringComparison]::Ordinal)
    $installLabel = $expectedShim.IndexOf("`r`n:managed_install`r`n", [StringComparison]::Ordinal)
    $nextLabel = $expectedShim.IndexOf("`r`n:managed_update`r`n", [StringComparison]::Ordinal)
    if ($installRoute -lt 0 -or $nativePassthrough -lt 0 -or $installRoute -gt $nativePassthrough -or
        $installLabel -lt 0 -or $nextLabel -le $installLabel -or
        $expectedShim.Substring($installLabel, $nextLabel - $installLabel).IndexOf('endlocal & exit /b 64', [StringComparison]::Ordinal) -lt 0) {
        throw 'Controlled CLI template no longer blocks native install before passthrough.'
    }
    foreach ($name in @('codexplusplus.cmd', 'codex-plusplus.cmd')) {
        $path = Join-Path $runtimeBin $name
        if (-not (Test-Path -LiteralPath $path -PathType Leaf) -or
            -not [string]::Equals([IO.File]::ReadAllText($path), $expectedShim, [StringComparison]::Ordinal)) {
            throw "Codex++ controlled CLI shim is missing or drifted: $path"
        }
        if ((Get-Item -LiteralPath $path -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) {
            throw "Codex++ runtime CLI shim must be physical: $path"
        }
        $publicPath = Join-Path $publicBin $name
        if (-not (Test-Path -LiteralPath $publicPath -PathType Leaf)) {
            throw "Codex++ public CLI link is missing: $publicPath"
        }
        $publicItem = Get-Item -LiteralPath $publicPath -Force
        $publicTarget = [string]$publicItem.Target
        if (-not ($publicItem.Attributes -band [IO.FileAttributes]::ReparsePoint) -or
            -not [string]::Equals([IO.Path]::GetFullPath($publicTarget), [IO.Path]::GetFullPath($path), [StringComparison]::OrdinalIgnoreCase)) {
            throw "Codex++ public CLI link drifted: $publicPath -> $publicTarget"
        }
    }
}

function Remove-SafePreviousSource {
    if (-not (Test-Path -LiteralPath $previousRoot -PathType Container)) { return $false }
    $resolved = [IO.Path]::GetFullPath((Resolve-Path -LiteralPath $previousRoot).Path).TrimEnd('\')
    $expected = [IO.Path]::GetFullPath($previousRoot).TrimEnd('\')
    $expectedParent = [IO.Path]::GetFullPath('@@CODEXPP_SOURCE_PARENT:win@@').TrimEnd('\')
    $actualParent = [IO.Path]::GetFullPath([IO.Directory]::GetParent($resolved).FullName).TrimEnd('\')
    if (-not [string]::Equals($resolved, $expected, [StringComparison]::OrdinalIgnoreCase) -or
        -not [string]::Equals($actualParent, $expectedParent, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to remove unexpected installer rollback root: $resolved"
    }
    if ((Get-Item -LiteralPath $resolved -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) {
        throw "Refusing to remove reparse-point installer rollback root: $resolved"
    }
    Remove-Item -LiteralPath $resolved -Recurse -Force
    return $true
}

function Restore-PreviousSource {
    if (-not (Test-Path -LiteralPath $previousRoot -PathType Container)) {
        throw 'Native installer source changed but its rollback copy is missing.'
    }
    $expectedParent = [IO.Path]::GetFullPath('@@CODEXPP_SOURCE_PARENT:win@@').TrimEnd('\')
    foreach ($path in @($previousRoot)) {
        $resolved = [IO.Path]::GetFullPath((Resolve-Path -LiteralPath $path).Path).TrimEnd('\')
        $actualParent = [IO.Path]::GetFullPath([IO.Directory]::GetParent($resolved).FullName).TrimEnd('\')
        if (-not [string]::Equals($actualParent, $expectedParent, [StringComparison]::OrdinalIgnoreCase) -or
            (Get-Item -LiteralPath $resolved -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) {
            throw "Refusing unsafe installer rollback directory: $resolved"
        }
    }
    $sourceExists = Test-Path -LiteralPath $sourceRoot -PathType Container
    if ($sourceExists) {
        $resolvedSource = [IO.Path]::GetFullPath((Resolve-Path -LiteralPath $sourceRoot).Path).TrimEnd('\')
        $sourceParent = [IO.Path]::GetFullPath([IO.Directory]::GetParent($resolvedSource).FullName).TrimEnd('\')
        if (-not [string]::Equals($resolvedSource, [IO.Path]::GetFullPath($sourceRoot).TrimEnd('\'), [StringComparison]::OrdinalIgnoreCase) -or
            -not [string]::Equals($sourceParent, $expectedParent, [StringComparison]::OrdinalIgnoreCase) -or
            (Get-Item -LiteralPath $resolvedSource -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) {
            throw "Refusing unsafe active installer source during rollback: $resolvedSource"
        }
    }
    $failedRoot = '@@CODEXPP_SOURCE:win@@.failed-controlled'
    if (Test-Path -LiteralPath $failedRoot) {
        $resolvedFailed = [IO.Path]::GetFullPath((Resolve-Path -LiteralPath $failedRoot).Path).TrimEnd('\')
        $failedParent = [IO.Path]::GetFullPath([IO.Directory]::GetParent($resolvedFailed).FullName).TrimEnd('\')
        if (-not [string]::Equals($resolvedFailed, [IO.Path]::GetFullPath($failedRoot).TrimEnd('\'), [StringComparison]::OrdinalIgnoreCase) -or
            -not [string]::Equals($failedParent, $expectedParent, [StringComparison]::OrdinalIgnoreCase) -or
            (Get-Item -LiteralPath $resolvedFailed -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) {
            throw "Refusing unsafe failed-source cleanup directory: $resolvedFailed"
        }
        Remove-Item -LiteralPath $failedRoot -Recurse -Force
    }
    if ($sourceExists) {
        [IO.Directory]::Move($sourceRoot, $failedRoot)
    }
    [IO.Directory]::Move($previousRoot, $sourceRoot)
    if (Test-Path -LiteralPath $failedRoot -PathType Container) {
        Remove-Item -LiteralPath $failedRoot -Recurse -Force
    }
}

function Write-Result([string]$Token, [System.Collections.IDictionary]$Payload) {
    $Token
    $Payload | ConvertTo-Json -Depth 6 -Compress
}

$sourceChanged = $false
$sourcePrepared = $false
$lifecycleCommitted = $false
try {
    Assert-FixedEnvironment

    if ($Mode -eq 'Check') {
        Assert-OverlayOnDisk
        Assert-UpdateBoundary
        Write-Result 'CODEXPP_INSTALLER_UPDATE_CHECK_PASS' ([ordered]@{
            schema_version = 'codexplusplus-installer-update.v1'
            status = 'pass'
            mode = 'check'
            power_shell = $PSVersionTable.PSVersion.ToString()
            source_root = $sourceRoot
        })
        exit 0
    }

    if ($Mode -eq 'Update' -and (Test-CodexPlusPlusProfileRunning)) {
        throw 'WAIT_PROFILE_EXIT_REQUIRED: close the Codex++ profile before updating its installer source.'
    }

    Enter-SourceUpdateMutex
    Assert-UpdateBoundary

    # Native self-update uses this exact sibling as its rollback copy. Remove a
    # stale prior copy before invocation so existence afterward is an unambiguous
    # receipt that this invocation replaced the whole source tree, including
    # same-version --force updates.
    $stalePreviousRemoved = Remove-SafePreviousSource
    $arguments = @($nativeCli, 'update', '--no-repair')
    if ($Repo) { $arguments += @('--repo', $Repo) }
    if ($Ref) { $arguments += @('--ref', $Ref) }
    if ($Force) { $arguments += '--force' }
    $nativeOutput = @(& $nodeExe @arguments 2>&1)
    $nativeExitCode = $LASTEXITCODE
    $sourceChanged = Test-Path -LiteralPath $previousRoot -PathType Container
    if ($nativeExitCode -ne 0) {
        throw "Native Codex++ source update failed: $($nativeOutput -join "`n")"
    }

    if ($sourceChanged) {
        $plan = Get-OverlayPlan
        Write-OverlayPlan $plan
        Invoke-InstallerBuild
        # The build may regenerate runtime dist/assets; reapply the same
        # canonical overlay after build before any validation or publication.
        Write-OverlayPlan (Get-OverlayPlan)
    } else {
        # Up-to-date is a no-write path: validate the already-authoritative
        # overlay instead of rebuilding active dist without a rollback copy.
        Assert-OverlayOnDisk
    }
    Assert-OverlayOnDisk
    Invoke-InstallerTests
    $sourcePrepared = $true

    $priorParentPid = $env:CODEXPP_MAINTENANCE_PARENT_PID
    try {
        $env:CODEXPP_MAINTENANCE_PARENT_PID = [string]$PID
        $syncOutput = @(& $powerShell7 -NoLogo -NoProfile -File $syncEntry -Once -RequireStoppedProfile -ForceRepair -ParentOwnsMaintenanceMutex 2>&1)
        $syncExitCode = $LASTEXITCODE
    } finally {
        if ($null -eq $priorParentPid) {
            Remove-Item Env:CODEXPP_MAINTENANCE_PARENT_PID -ErrorAction SilentlyContinue
        } else {
            $env:CODEXPP_MAINTENANCE_PARENT_PID = $priorParentPid
        }
    }
    if ($syncExitCode -ne 0) {
        $repairFailure = "Codex++ post-update lifecycle repair failed: $($syncOutput -join "`n")"
        if ($sourceChanged) {
            Restore-PreviousSource
            $sourceChanged = $false
            try {
                $env:CODEXPP_MAINTENANCE_PARENT_PID = [string]$PID
                $recoveryOutput = @(& $powerShell7 -NoLogo -NoProfile -File $syncEntry -Once -RequireStoppedProfile -ForceRepair -ParentOwnsMaintenanceMutex 2>&1)
                $recoveryExitCode = $LASTEXITCODE
            } finally {
                if ($null -eq $priorParentPid) {
                    Remove-Item Env:CODEXPP_MAINTENANCE_PARENT_PID -ErrorAction SilentlyContinue
                } else {
                    $env:CODEXPP_MAINTENANCE_PARENT_PID = $priorParentPid
                }
            }
            if ($recoveryExitCode -ne 0) {
                $repairFailure += " | previous_source_repair_failed=$($recoveryOutput -join "`n")"
            } else {
                $repairFailure += ' | previous_source_restored_and_repaired=true'
            }
        }
        throw $repairFailure
    }
    $lifecycleCommitted = $true

    # These checks and cleanup occur after the source+runtime/app commit. They
    # may fail the command, but must never roll an already-committed system back.
    Assert-UpdateBoundary
    $previousRemoved = Remove-SafePreviousSource
    Exit-SourceUpdateMutex

    Write-Result 'CODEXPP_INSTALLER_UPDATE_PASS' ([ordered]@{
        schema_version = 'codexplusplus-installer-update.v1'
        status = 'pass'
        mode = $Mode.ToLowerInvariant()
        power_shell = $PSVersionTable.PSVersion.ToString()
        source_root = $sourceRoot
        source_changed = $sourceChanged
        stale_previous_removed = $stalePreviousRemoved
        previous_source_removed = $previousRemoved
    })
    exit 0
} catch {
    $failure = [string]$_.Exception.Message
    try {
        if (-not $lifecycleCommitted -and $sourceChanged) {
            Restore-PreviousSource
        }
    } catch {
        $failure += " | rollback_failed=$($_.Exception.Message)"
    } finally {
        Exit-SourceUpdateMutex
    }
    Write-Result 'CODEXPP_INSTALLER_UPDATE_FAIL' ([ordered]@{
        schema_version = 'codexplusplus-installer-update.v1'
        status = 'failed'
        mode = $Mode.ToLowerInvariant()
        power_shell = $PSVersionTable.PSVersion.ToString()
        source_root = $sourceRoot
        source_changed = $sourceChanged
        source_prepared = $sourcePrepared
        lifecycle_committed = $lifecycleCommitted
        error = $failure
    })
    exit 1
}
