#requires -Version 7.0

[CmdletBinding()]
param()

# Manual, read-only lifecycle contract audit. This script is deliberately not
# part of Host startup and never repairs files, writes receipts, or owns state.
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$configRoot = '@@LAUNCHER_ROOT:win@@'
$powerShell7 = '@@POWERSHELL_EXE:win@@'
$manifest = '@@GENERAL_ROOT:win@@\control\host-capability-publication-manifest.yaml'
$canonicalSkills = '@@GENERAL_ROOT:win@@\assets\skills'
$profileSkills = '@@CODEXPP_HOME:win@@\skills'
$runtimeRoot = '@@CODEXPP_RUNTIME:win@@'
$projection = '@@GENERAL_ROOT:win@@\tooling\Sync-HostCapabilityProjection.ps1'
$legacyProjection = Join-Path $configRoot 'Sync-HostCapabilityProjection.ps1'
$retiredSkillRoot = '@@GENERAL_ROOT:win@@\skills'
$profileRootContractSource = Join-Path $configRoot 'Assert-CodexPlusPlusProfileRootContract.ps1'
$tweakLinkCheck = Join-Path $configRoot 'Test-CodexPlusPlusTweakLinks.ps1'
$startupRepairDecisionTest = Join-Path $configRoot 'Test-CodexPlusPlusStartupRepairDecision.ps1'
$start = Join-Path $configRoot 'Start-CodexPlusPlus.ps1'
$update = Join-Path $configRoot 'Sync-CodexPlusPlusLatest.ps1'
$repair = Join-Path $configRoot 'Repair-CodexPlusPlusCurrentApp.ps1'
$installerUpdate = Join-Path $configRoot 'Update-CodexPlusPlusInstaller.ps1'
$cliShimTemplate = Join-Path $configRoot 'CodexPlusPlus-ControlledCliShim.cmd.template'
$proxy = Join-Path $configRoot 'Start-CodexPlusPlus-Proxy.cmd'
$vbsProxy = Join-Path $configRoot 'Start-CodexPlusPlus-Proxy.vbs'
$injection = Join-Path $configRoot 'Test-CodexPlusPlusInjection.ps1'
$runtimeBin = Join-Path $runtimeRoot 'bin'
$installerSourceParent = '@@CODEXPP_SOURCE_PARENT:win@@'
$installerSourceRetiredAlias = '@@CODEX_HOME:win@@-plusplus'
$storeRoot = '@@CODEXPP_INSTALL_ROOT:win@@\store-apps'
$wcuRoot = Join-Path $runtimeRoot 'tweaks\co.bennett.windows-computer-use'
$sessionWatcher = Join-Path $configRoot 'Watch-CodexPlusPlusSessionPaths.ps1'
$legacyPowerShell = '@@SYSTEMROOT:win@@\System32\WindowsPowerShell\v1.0\powershell.exe'
$failures = [Collections.Generic.List[string]]::new()

function Add-Failure([string]$Message) {
    $failures.Add($Message)
}

function Require-Leaf([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        Add-Failure "Required file missing: $Path"
    }
}

function Require-Text([string]$Path, [string[]]$Needles) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { return }
    $text = [IO.File]::ReadAllText($Path)
    foreach ($needle in $Needles) {
        if ($text.IndexOf($needle, [StringComparison]::Ordinal) -lt 0) {
            Add-Failure "Required lifecycle contract token missing from $Path : $needle"
        }
    }
}

function Get-NormalPath([string]$Path, [string]$BasePath = '') {
    if (-not [IO.Path]::IsPathRooted($Path)) {
        if ([string]::IsNullOrWhiteSpace($BasePath)) { return $null }
        $Path = Join-Path $BasePath $Path
    }
    return [IO.Path]::GetFullPath($Path).TrimEnd('\')
}

function Get-JunctionTarget([IO.FileSystemInfo]$Item) {
    if (-not [string]::Equals([string]$Item.LinkType, 'Junction', [StringComparison]::OrdinalIgnoreCase)) { return $null }
    $targets = @($Item.Target | Where-Object { -not [string]::IsNullOrWhiteSpace([string]$_) })
    if ($targets.Count -ne 1) { return $null }
    $target = [string]$targets[0]
    if ($target.StartsWith('\??\')) { $target = $target.Substring(4) }
    if ($target.StartsWith('\\?\')) { $target = $target.Substring(4) }
    return Get-NormalPath $target $Item.Parent.FullName
}

foreach ($path in @($powerShell7, $manifest, $projection, $profileRootContractSource, $tweakLinkCheck, $startupRepairDecisionTest, $start, $update, $repair, $installerUpdate, $cliShimTemplate, $proxy, $vbsProxy, $injection)) {
    Require-Leaf $path
}
if (-not (Test-Path -LiteralPath $canonicalSkills -PathType Container)) {
    Add-Failure "Canonical Skill root missing: $canonicalSkills"
}
if (-not (Test-Path -LiteralPath $profileSkills -PathType Container)) {
    Add-Failure "Codex++ Skill projection root missing: $profileSkills"
}
if (Test-Path -LiteralPath $legacyProjection) {
    Add-Failure "Retired Host-private projection writer must be absent: $legacyProjection"
}
if (Test-Path -LiteralPath $projection -PathType Leaf) {
    $projectionItem = Get-Item -LiteralPath $projection -Force
    if ($projectionItem.Attributes -band [IO.FileAttributes]::ReparsePoint) {
        Add-Failure "General projection writer must be a physical file: $projection"
    }
}

if (Test-Path -LiteralPath $powerShell7 -PathType Leaf) {
    $pwshItem = Get-Item -LiteralPath $powerShell7 -Force
    if ($pwshItem.Attributes -band [IO.FileAttributes]::ReparsePoint) {
        Add-Failure "PowerShell 7 must be a physical file: $powerShell7"
    }
}

foreach ($script in @($projection, $profileRootContractSource, $tweakLinkCheck, $startupRepairDecisionTest, $start, $update, $repair, $installerUpdate, $injection, $sessionWatcher)) {
    if (-not (Test-Path -LiteralPath $script -PathType Leaf)) { continue }
    $tokens = $null
    $errors = $null
    [void][Management.Automation.Language.Parser]::ParseFile($script, [ref]$tokens, [ref]$errors)
    foreach ($parseError in @($errors)) {
        Add-Failure "PowerShell parser error in $script : $($parseError.Message)"
    }
}

Require-Text $start @(
    '@@POWERSHELL_EXE:win@@',
    'Assert-CodexPlusPlusProfileRootContract.ps1',
    'Assert-CodexPlusPlusProfileRootContract',
    'Test-CodexPlusPlusTweakLinks.ps1',
    '@@GENERAL_ROOT:win@@\tooling\Sync-HostCapabilityProjection.ps1',
    '-HostId codex_plus_plus',
    '-SkillsRoot',
    '-Mode Apply'
)
Require-Text $update @(
    '@@POWERSHELL_EXE:win@@',
    'Assert-CodexPlusPlusProfileRootContract.ps1',
    'Assert-CodexPlusPlusProfileRootContract',
    '@@GENERAL_ROOT:win@@\tooling\Sync-HostCapabilityProjection.ps1',
    'function Remove-StaleStoreCopies',
    'CurrentPackageIdentity',
    'ReparsePoint',
    'Get-CimInstance Win32_Process',
    'Remove-Item -LiteralPath $candidate -Recurse -Force',
    'store_bytes_reclaimed',
    'CodexPlusPlus-ControlledCliShim.cmd.template',
    'ParentOwnsMaintenanceMutex'
)
Require-Text $repair @(
    '@@POWERSHELL_EXE:win@@',
    'Sync-CodexPlusPlusLatest.ps1',
    '-RequireStoppedProfile'
)
Require-Text $installerUpdate @(
    '@@POWERSHELL_EXE:win@@',
    'codexPlusPlus.autoUpdate',
    'CodexPlusPlusInstallerSourceUpdate',
    'update',
    '--no-repair',
    'Invoke-InstallerBuild',
    'Invoke-InstallerTests',
    'Restore-PreviousSource',
    'ParentOwnsMaintenanceMutex'
)
Require-Text $cliShimTemplate @(
    'CODEXPP_CONTROLLED_LIFECYCLE',
    'install" goto :managed_install',
    ':managed_update',
    ':managed_repair',
    'endlocal & exit /b 64'
)
Require-Text $proxy @('@@POWERSHELL_EXE:win@@', 'Start-CodexPlusPlus.ps1')
Require-Text $vbsProxy @('@@POWERSHELL_EXE:win@@', 'Start-CodexPlusPlus.ps1', 'Run(command, 0, True)')
Require-Text $tweakLinkCheck @(
    '@@CODEXPP_SOURCE_PARENT:win@@',
    'retired_source_alias = $null',
    'CODEXPP_TWEAK_LINK_CHECK_PASS'
)

if (Test-Path -LiteralPath $profileRootContractSource -PathType Leaf) {
    try {
        . $profileRootContractSource
        [void](Assert-CodexPlusPlusProfileRootContract)
    } catch {
        Add-Failure "Codex++ profile root contract failed: $($_.Exception.Message)"
    }
}

$activeFiles = @($projection, $profileRootContractSource, $tweakLinkCheck, $startupRepairDecisionTest, $start, $update, $repair, $proxy, $vbsProxy, $injection)
$forbidden = 'WindowsPowerShell\\v1\.0|powershell\.exe|Ensure-CodexPlusPlusHostManifestAdapter|ManifestProductionCutover|ManifestAdapterDurability|AppAsarBaseline|AppAsarFullHash|ACTIVATE_PRODUCTION|host-capability-manifest-replay'
foreach ($path in $activeFiles) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { continue }
    $hits = @(Select-String -LiteralPath $path -Pattern $forbidden -CaseSensitive:$false)
    foreach ($hit in $hits) {
        if ($path -eq $start -and $hit.Line.IndexOf('codexpp:migration-detector-only', [StringComparison]::Ordinal) -ge 0) {
            continue
        }
        Add-Failure "Retired dependency in active file $path line $($hit.LineNumber): $($hit.Line.Trim())"
    }
}

$sessionWatcherProcesses = @(Get-CimInstance Win32_Process | Where-Object {
    $exe = [string]$_.ExecutablePath
    $cmd = [string]$_.CommandLine
    if ([string]::IsNullOrWhiteSpace($exe) -or [string]::IsNullOrWhiteSpace($cmd)) { return $false }
    $normalizedExe = [IO.Path]::GetFullPath($exe)
    $isManagedPowerShell =
        [string]::Equals($normalizedExe, [IO.Path]::GetFullPath($powerShell7), [StringComparison]::OrdinalIgnoreCase) -or
        [string]::Equals($normalizedExe, [IO.Path]::GetFullPath($legacyPowerShell), [StringComparison]::OrdinalIgnoreCase)
    if (-not $isManagedPowerShell) { return $false }
    $script = [regex]::Escape([IO.Path]::GetFullPath($sessionWatcher))
    [regex]::IsMatch($cmd, '(?i)\s-File\s+(?:"' + $script + '"|' + $script + ')\s+-Watch(?:\s|$)')
})
foreach ($process in $sessionWatcherProcesses) {
    Add-Failure "Retired long-running Codex++ session watcher is active: PID $($process.ProcessId)."
}

$sessionWatcherText = if (Test-Path -LiteralPath $sessionWatcher -PathType Leaf) { [IO.File]::ReadAllText($sessionWatcher) } else { '' }
foreach ($retiredToken in @('[switch]$Watch', 'IntervalSeconds = 30', 'DurationSeconds = 43200', 'session-path-normalizer.pid', 'Start-Sleep -Seconds ([Math]::Max(1, $IntervalSeconds))')) {
    if ($sessionWatcherText.IndexOf($retiredToken, [StringComparison]::Ordinal) -ge 0) {
        Add-Failure "Retired session watcher source token remains: $retiredToken"
    }
}
$startText = if (Test-Path -LiteralPath $start -PathType Leaf) { [IO.File]::ReadAllText($start) } else { '' }
if ($startText.IndexOf('Session watcher running in background', [StringComparison]::Ordinal) -ge 0) {
    Add-Failure 'Start entry still launches the retired background session watcher.'
}

$retiredPaths = @(
    (Join-Path $configRoot 'Ensure-CodexPlusPlusHostManifestAdapter.ps1'),
    (Join-Path $configRoot 'Invoke-CodexPlusPlusManifestProductionCutover.ps1'),
    (Join-Path $configRoot 'Restore-CodexPlusPlusManifestProductionCutover.ps1'),
    (Join-Path $configRoot 'Start-CodexPlusPlusUpdateSyncLoop.ps1'),
    (Join-Path $configRoot 'Repair-CodexPlusPlusCurrentAppOnExit.ps1'),
    (Join-Path $configRoot 'Repair-CodexPlusPlusTweakLinks.ps1'),
    (Join-Path $configRoot 'manifest-replay-canary'),
    (Join-Path $runtimeRoot 'tweaks\co.Arconte112.host-capability-manifest-replay')
)
foreach ($path in $retiredPaths) {
    if (Test-Path -LiteralPath $path) {
        Add-Failure "Retired runtime asset still present: $path"
    }
}

$runtimeConfig = Join-Path $runtimeRoot 'config.json'
if (Test-Path -LiteralPath $runtimeConfig -PathType Leaf) {
    try {
        $config = Get-Content -LiteralPath $runtimeConfig -Raw | ConvertFrom-Json
        if ($config.tweaks.PSObject.Properties.Name -contains 'co.Arconte112.host-capability-manifest-replay') {
            Add-Failure 'Retired Manifest replay tweak is still registered in config.json.'
        }
        if ($config.codexPlusPlus.autoUpdate -ne $false) {
            Add-Failure 'Codex++ native autoUpdate must remain false.'
        }
    } catch {
        Add-Failure "Codex++ runtime config is not valid JSON: $($_.Exception.Message)"
    }
}

$watcherTaskNames = @('codex-plusplus-watcher', 'codex-plusplus-watcher-interval', 'codex-plusplus-watcher-hourly', 'codex-plusplus-watcher-daily')
$watcherTasks = @(Get-ScheduledTask -TaskName $watcherTaskNames -ErrorAction SilentlyContinue)
if ($watcherTasks.Count) {
    Add-Failure "Retired Codex++ watcher tasks remain: $($watcherTasks.TaskName -join ', ')"
}
foreach ($path in @((Join-Path $runtimeBin 'watcher.cmd'), (Join-Path $runtimeBin 'watcher.vbs'))) {
    if (Test-Path -LiteralPath $path) {
        Add-Failure "Retired Codex++ watcher launcher remains: $path"
    }
}

if (Test-Path -LiteralPath $cliShimTemplate -PathType Leaf) {
    $expectedShim = [IO.File]::ReadAllText($cliShimTemplate).Replace("`r`n", "`n").Replace("`n", "`r`n")
    foreach ($name in @('codexplusplus.cmd', 'codex-plusplus.cmd')) {
        $runtimeShim = Join-Path $runtimeBin $name
        if (-not (Test-Path -LiteralPath $runtimeShim -PathType Leaf) -or
            -not [string]::Equals([IO.File]::ReadAllText($runtimeShim), $expectedShim, [StringComparison]::Ordinal)) {
            Add-Failure "Controlled CLI shim drifted: $runtimeShim"
        }
        $publicShim = Join-Path '@@USERPROFILE:win@@\AppData\Local\Microsoft\WindowsApps' $name
        if (-not (Test-Path -LiteralPath $publicShim -PathType Leaf)) {
            Add-Failure "Public CLI link missing: $publicShim"
            continue
        }
        $item = Get-Item -LiteralPath $publicShim -Force
        if (-not ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -or
            -not [string]::Equals([IO.Path]::GetFullPath([string]$item.Target), [IO.Path]::GetFullPath($runtimeShim), [StringComparison]::OrdinalIgnoreCase)) {
            Add-Failure "Public CLI link drifted: $publicShim -> $($item.Target)"
        }
    }
}

$sourceBackups = @(Get-ChildItem -LiteralPath $installerSourceParent -Directory -Force -ErrorAction SilentlyContinue | Where-Object Name -Like 'source.previous*')
if ($sourceBackups.Count) {
    Add-Failure "Stale installer source backups remain: $($sourceBackups.FullName -join ', ')"
}

if (Test-Path -LiteralPath $installerSourceRetiredAlias) {
    Add-Failure "Retired Codex++ installer source alias remains: $installerSourceRetiredAlias"
}

$tweakLinkCheckOutput = @()
$tweakLinkCheckExit = $null
if (Test-Path -LiteralPath $tweakLinkCheck -PathType Leaf) {
    $tweakLinkCheckOutput = @(& $powerShell7 -NoLogo -NoProfile -File $tweakLinkCheck 2>&1)
    $tweakLinkCheckExit = $LASTEXITCODE
    if ($tweakLinkCheckExit -ne 0) {
        Add-Failure "Codex++ tweak link check failed: $($tweakLinkCheckOutput -join "`n")"
    }
}

$startupRepairDecisionOutput = @()
$startupRepairDecisionExit = $null
if (Test-Path -LiteralPath $startupRepairDecisionTest -PathType Leaf) {
    $startupRepairDecisionOutput = @(& $powerShell7 -NoLogo -NoProfile -File $startupRepairDecisionTest 2>&1)
    $startupRepairDecisionExit = $LASTEXITCODE
    if ($startupRepairDecisionExit -ne 0) {
        Add-Failure "Codex++ startup repair decision test failed: $($startupRepairDecisionOutput -join "`n")"
    }
}

try {
    $package = @(Get-AppxPackage -Name 'OpenAI.Codex' -ErrorAction Stop | Where-Object InstallLocation)
    if ($package.Count -ne 1) {
        Add-Failure "Expected one official OpenAI.Codex package, found $($package.Count)."
    } elseif (Test-Path -LiteralPath $storeRoot -PathType Container) {
        $currentIdentity = Split-Path -Leaf ([string]$package[0].InstallLocation)
        $storeCopies = @(Get-ChildItem -LiteralPath $storeRoot -Directory -Force | Where-Object Name -Like 'OpenAI.Codex_*')
        if ($storeCopies.Count -ne 1 -or -not [string]::Equals($storeCopies[0].Name, $currentIdentity, [StringComparison]::OrdinalIgnoreCase)) {
            Add-Failure "Codex++ store must contain only current package $currentIdentity; found $($storeCopies.Name -join ', ')."
        }
    }
} catch {
    Add-Failure "Unable to audit Codex++ current-only store boundary: $($_.Exception.Message)"
}

$shell = New-Object -ComObject WScript.Shell
$directShortcutPaths = @(
    '@@USERPROFILE:win@@\Desktop\Codex++.lnk',
    '@@USERPROFILE:win@@\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Codex++.lnk',
    '@@USERPROFILE:win@@\AppData\Roaming\CodexPlusPlusProfile\Desktop\Codex++.lnk',
    '@@USERPROFILE:win@@\AppData\Roaming\CodexPlusPlusProfile\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Codex.lnk',
    '@@USERPROFILE:win@@\AppData\Roaming\CodexPlusPlusProfile\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\ChatGPT.lnk'
)
$storePrefix = [IO.Path]::GetFullPath($storeRoot).TrimEnd('\') + '\'
foreach ($shortcutPath in $directShortcutPaths) {
    if (-not (Test-Path -LiteralPath $shortcutPath -PathType Leaf)) { continue }
    $item = Get-Item -LiteralPath $shortcutPath -Force
    if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) {
        Add-Failure "Codex++ shortcut boundary cannot audit a reparse-point shortcut: $shortcutPath"
        continue
    }
    $shortcut = $shell.CreateShortcut($shortcutPath)
    $target = [IO.Path]::GetFullPath([string]$shortcut.TargetPath)
    if ($target.StartsWith($storePrefix, [StringComparison]::OrdinalIgnoreCase) -and
        [IO.Path]::GetFileName($target) -in @('Codex.exe', 'ChatGPT.exe')) {
        Add-Failure "Direct Codex++ store shortcut bypasses the controlled launcher: $shortcutPath"
    }
}

$isolatedShortcutRoots = @(
    '@@USERPROFILE:win@@\AppData\Roaming\CodexPlusPlusProfile\Desktop',
    '@@USERPROFILE:win@@\AppData\Roaming\CodexPlusPlusProfile\AppData\Roaming\Microsoft\Windows\Start Menu'
)
foreach ($shortcutRoot in $isolatedShortcutRoots) {
    if (-not (Test-Path -LiteralPath $shortcutRoot -PathType Container)) { continue }
    foreach ($shortcutFile in @(Get-ChildItem -LiteralPath $shortcutRoot -Filter '*.lnk' -File -Recurse -Force)) {
        $shortcut = $shell.CreateShortcut($shortcutFile.FullName)
        if ([string]::Equals([IO.Path]::GetFullPath([string]$shortcut.TargetPath), [IO.Path]::GetFullPath($legacyPowerShell), [StringComparison]::OrdinalIgnoreCase)) {
            Add-Failure "Legacy Windows PowerShell shortcut remains inside the Codex++ isolated profile: $($shortcutFile.FullName)"
        }
    }
}

if (Test-Path -LiteralPath $wcuRoot -PathType Container) {
    $wcuFiles = @(Get-ChildItem -LiteralPath $wcuRoot -File -Recurse | Where-Object {
        $_.Extension -in @('.ps1', '.js', '.cjs', '.mjs', '.json') -and
        $_.FullName.IndexOf('\tests\', [StringComparison]::OrdinalIgnoreCase) -lt 0
    })
    $wcuForbiddenPatterns = @(
        'powershell\.exe',
        'WindowsPowerShell',
        '"-ExecutionPolicy"',
        "'-ExecutionPolicy'",
        '-ExecutionPolicy\s+Bypass',
        '"Bypass"'
    )
    $wcuOld = @($wcuFiles | Select-String -Pattern $wcuForbiddenPatterns -CaseSensitive:$false)
    if ($wcuOld.Count) {
        Add-Failure "WCU retired PowerShell dependency remains: $($wcuOld[0].Path):$($wcuOld[0].LineNumber)"
    }
}

$installerCheckOutput = @()
$installerCheckExit = $null
if (Test-Path -LiteralPath $installerUpdate -PathType Leaf) {
    $installerCheckOutput = @(& $powerShell7 -NoLogo -NoProfile -File $installerUpdate -Mode Check 2>&1)
    $installerCheckExit = $LASTEXITCODE
    if ($installerCheckExit -ne 0) {
        Add-Failure "Codex++ installer update boundary check failed: $($installerCheckOutput -join "`n")"
    }
}

$projectionOutput = @()
$projectionExit = $null
if (Test-Path -LiteralPath $projection -PathType Leaf) {
    $projectionOutput = @(& $powerShell7 -NoLogo -NoProfile -File $projection -HostId codex_plus_plus -SkillsRoot $profileSkills -Mode Check 2>&1)
    $projectionExit = $LASTEXITCODE
    if ($projectionExit -ne 0) {
        Add-Failure "Codex++ Manifest projection check failed: $($projectionOutput -join "`n")"
    }
}

$skillJunctionCount = 0
$unresolvedSkillJunctionCount = 0
$retiredSkillRootJunctionCount = 0
if (Test-Path -LiteralPath $profileSkills -PathType Container) {
    $retiredPrefix = (Get-NormalPath $retiredSkillRoot) + '\'
    foreach ($item in @(Get-ChildItem -LiteralPath $profileSkills -Force)) {
        if (-not ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) { continue }
        $skillJunctionCount++
        $target = Get-JunctionTarget $item
        if (-not $target) {
            $unresolvedSkillJunctionCount++
            Add-Failure "Codex++ Skill reparse point is not one single-target Junction: $($item.FullName)"
            continue
        }
        if ($target.StartsWith($retiredPrefix, [StringComparison]::OrdinalIgnoreCase)) {
            $retiredSkillRootJunctionCount++
            Add-Failure "Codex++ Skill Junction targets the retired .agent\\skills root: $($item.FullName) -> $target"
        }
        if (-not (Test-Path -LiteralPath (Join-Path $target 'SKILL.md') -PathType Leaf)) {
            $unresolvedSkillJunctionCount++
            Add-Failure "Codex++ Skill Junction target has no resolvable SKILL.md: $($item.FullName) -> $target"
        }
    }
}

$lifecycleIngressFiles = @($start, $update, $repair)
$lifecycleIngressCount = @($lifecycleIngressFiles | Where-Object { Test-Path -LiteralPath $_ -PathType Leaf }).Count
$directProjectionCallerCount = 0
foreach ($path in @($start, $update)) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { continue }
    $text = [IO.File]::ReadAllText($path)
    if ($text.IndexOf('-HostId codex_plus_plus', [StringComparison]::Ordinal) -ge 0 -and
        $text.IndexOf('-Mode Apply', [StringComparison]::Ordinal) -ge 0) {
        $directProjectionCallerCount++
    }
}
$projectionWriterCount = @($projection, $legacyProjection | Where-Object { Test-Path -LiteralPath $_ -PathType Leaf }).Count
if ($lifecycleIngressCount -ne 3) { Add-Failure "Expected 3 lifecycle ingress files, found $lifecycleIngressCount." }
if ($directProjectionCallerCount -ne 2) { Add-Failure "Expected 2 direct projection callers, found $directProjectionCallerCount." }
if ($projectionWriterCount -ne 1) { Add-Failure "Expected 1 projection writer, found $projectionWriterCount." }

$result = [ordered]@{
    schema_version = 'codexplusplus-lifecycle-contract-audit.v1'
    status = if ($failures.Count) { 'fail' } else { 'pass' }
    power_shell = $PSVersionTable.PSVersion.ToString()
    lifecycle_ingress_count = $lifecycleIngressCount
    direct_projection_caller_count = $directProjectionCallerCount
    projection_writer_count = $projectionWriterCount
    projection_check_exit_code = $projectionExit
    installer_update_check_exit_code = $installerCheckExit
    tweak_link_check_exit_code = $tweakLinkCheckExit
    startup_repair_decision_exit_code = $startupRepairDecisionExit
    skill_junction_count = $skillJunctionCount
    unresolved_skill_junction_count = $unresolvedSkillJunctionCount
    retired_skill_root_junction_count = $retiredSkillRootJunctionCount
    watcher_task_count = $watcherTasks.Count
    session_watcher_process_count = $sessionWatcherProcesses.Count
    installer_source_backup_count = $sourceBackups.Count
    installer_source_canonical_root = $installerSourceParent
    installer_source_retired_alias = $null
    failures = @($failures)
}
if ($failures.Count) {
    'CODEXPP_LIFECYCLE_CONTRACT_FAIL'
    $result | ConvertTo-Json -Depth 6
    exit 1
}
'CODEXPP_LIFECYCLE_CONTRACT_PASS'
$result | ConvertTo-Json -Depth 6
exit 0
