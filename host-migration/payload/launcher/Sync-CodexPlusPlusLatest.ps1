#requires -Version 7.0

[CmdletBinding()]
param(
    # Kept for callers that used the old loop entry. This script is always one-shot.
    [switch]$Once,
    # Used only by the compatibility Repair entry: never repair a live profile.
    [switch]$RequireStoppedProfile,
    [switch]$ForceRepair,
    # Internal only: the direct parent Update-CodexPlusPlusInstaller process
    # already owns the shared mutex for the complete source+app transaction.
    [switch]$ParentOwnsMaintenanceMutex
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

$powerShell7 = '@@POWERSHELL_EXE:win@@'
$nodeExe = 'E:\nodejs\node-v22.22.0-win-x64\node.exe'
$nativeCli = '@@CODEXPP_SOURCE:win@@\packages\installer\dist\cli.js'
$cliShimTemplate = '@@LAUNCHER_ROOT:win@@\CodexPlusPlus-ControlledCliShim.cmd.template'
$runtimeBin = '@@CODEXPP_RUNTIME:win@@\bin'
$canonicalRuntimeRoot = '@@CODEXPP_RUNTIME:win@@'
$canonicalSkillsRoot = '@@CODEXPP_HOME:win@@\skills'
$injectionGuard = '@@LAUNCHER_ROOT:win@@\Test-CodexPlusPlusInjection.ps1'
$projectionSync = '@@GENERAL_ROOT:win@@\tooling\Sync-HostCapabilityProjection.ps1'
$profileRootContractSource = '@@LAUNCHER_ROOT:win@@\Assert-CodexPlusPlusProfileRootContract.ps1'
$storeRoot = '@@CODEXPP_INSTALL_ROOT:win@@\store-apps'
$profileRoot = '@@CODEXPP_PROFILE:win@@'
$profileRoots = @($profileRoot)
$maintenanceMutex = $null
$maintenanceMutexTaken = $false
$env:CODEX_PLUSPLUS_HOME = $canonicalRuntimeRoot

function Enter-MaintenanceMutex {
    $script:maintenanceMutex = [Threading.Mutex]::new($false, 'CodexPlusPlusInstallerSourceUpdate')
    try {
        $script:maintenanceMutexTaken = $script:maintenanceMutex.WaitOne([TimeSpan]::FromMinutes(5))
    } catch [Threading.AbandonedMutexException] {
        $script:maintenanceMutexTaken = $true
    }
    if (-not $script:maintenanceMutexTaken) {
        throw 'Timed out waiting for the Codex++ source/update maintenance lock.'
    }
}

function Exit-MaintenanceMutex {
    if ($script:maintenanceMutexTaken -and $script:maintenanceMutex) {
        $script:maintenanceMutex.ReleaseMutex()
        $script:maintenanceMutexTaken = $false
    }
    if ($script:maintenanceMutex) {
        $script:maintenanceMutex.Dispose()
        $script:maintenanceMutex = $null
    }
}

function Assert-ParentMaintenanceOwner {
    $expectedParent = 0
    if (-not [int]::TryParse([string]$env:CODEXPP_MAINTENANCE_PARENT_PID, [ref]$expectedParent) -or $expectedParent -le 0) {
        throw 'Parent-owned maintenance mode requires CODEXPP_MAINTENANCE_PARENT_PID.'
    }
    $selfProcess = Get-CimInstance Win32_Process -Filter "ProcessId=$PID"
    if (-not $selfProcess -or [int]$selfProcess.ParentProcessId -ne $expectedParent) {
        throw 'Parent-owned maintenance mode rejected: direct parent PID does not match.'
    }
}

function Assert-PowerShell7 {
    if ($PSVersionTable.PSVersion.Major -lt 7) {
        throw 'Codex++ maintenance requires PowerShell 7.'
    }
    if (-not (Test-Path -LiteralPath $powerShell7 -PathType Leaf)) {
        throw "PowerShell 7 executable is missing: $powerShell7"
    }
    $item = Get-Item -LiteralPath $powerShell7 -Force
    if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) {
        throw "PowerShell 7 executable must be a physical file: $powerShell7"
    }
}

function Get-OfficialCodexPackage {
    $packages = @(Get-AppxPackage -Name 'OpenAI.Codex' -ErrorAction Stop | Where-Object { $_.InstallLocation })
    if ($packages.Count -ne 1) {
        throw "Expected exactly one installed OpenAI.Codex package, found $($packages.Count)."
    }
    return $packages[0]
}

function Test-CodexPlusPlusProfileRunning {
    $storePrefix = [IO.Path]::GetFullPath($storeRoot).TrimEnd('\') + '\'
    $ownedNames = @('ChatGPT.exe', 'Codex.exe', 'codex.exe', 'node.exe', 'node_repl.exe', 'codex-code-mode-host.exe')
    return [bool](Get-CimInstance Win32_Process | Where-Object {
        $path = [string]$_.ExecutablePath
        $commandLine = [string]$_.CommandLine
        $name = if ($path) { [IO.Path]::GetFileName($path) } else { '' }
        $storeOwned = $path -and
            $path.StartsWith($storePrefix, [StringComparison]::OrdinalIgnoreCase) -and
            ($ownedNames -contains $name)
        $profileOwned = $commandLine -and @($profileRoots | Where-Object {
            $commandLine.IndexOf("--user-data-dir=$_", [StringComparison]::OrdinalIgnoreCase) -ge 0 -or
            $commandLine.IndexOf("--user-data-dir=`"$_`"", [StringComparison]::OrdinalIgnoreCase) -ge 0
        }).Count -gt 0
        $storeOwned -or $profileOwned
    } | Select-Object -First 1)
}

function Invoke-ProjectionSync {
    if (-not (Test-Path -LiteralPath $projectionSync -PathType Leaf)) {
        return [pscustomobject]@{
            Status = 'unavailable'
            ExitCode = $null
            Output = "Optional Host capability projection entry is missing: $projectionSync"
        }
    }
    $raw = @(& $powerShell7 -NoProfile -File $projectionSync -HostId codex_plus_plus -SkillsRoot $canonicalSkillsRoot -Mode Apply 2>&1)
    return [pscustomobject]@{
        Status = if ($LASTEXITCODE -eq 0) { 'pass' } else { 'reported_failure' }
        ExitCode = $LASTEXITCODE
        Output = ($raw -join "`n")
    }
}

function Remove-StaleStoreCopies {
    param([Parameter(Mandatory = $true)][string]$CurrentPackageIdentity)

    if (-not (Test-Path -LiteralPath $storeRoot -PathType Container)) {
        return @()
    }

    $resolvedRoot = [IO.Path]::GetFullPath((Resolve-Path -LiteralPath $storeRoot).Path).TrimEnd('\')
    if (-not [string]::Equals($resolvedRoot, [IO.Path]::GetFullPath($storeRoot).TrimEnd('\'), [StringComparison]::OrdinalIgnoreCase)) {
        throw "Codex++ store root resolved unexpectedly: $resolvedRoot"
    }
    $rootItem = Get-Item -LiteralPath $resolvedRoot -Force
    if ($rootItem.Attributes -band [IO.FileAttributes]::ReparsePoint) {
        throw "Codex++ store root must be physical: $resolvedRoot"
    }

    $currentPath = [IO.Path]::GetFullPath((Join-Path $resolvedRoot $CurrentPackageIdentity)).TrimEnd('\')
    $processPaths = @(Get-CimInstance Win32_Process | ForEach-Object { [string]$_.ExecutablePath } | Where-Object { $_ })
    $results = [Collections.Generic.List[object]]::new()

    foreach ($directory in @(Get-ChildItem -LiteralPath $resolvedRoot -Directory -Force)) {
        $candidate = [IO.Path]::GetFullPath($directory.FullName).TrimEnd('\')
        $parent = [IO.Path]::GetFullPath([IO.Directory]::GetParent($candidate).FullName).TrimEnd('\')
        if (-not [string]::Equals($parent, $resolvedRoot, [StringComparison]::OrdinalIgnoreCase)) {
            throw "Store cleanup candidate escaped the fixed root: $candidate"
        }
        if ([string]::Equals($candidate, $currentPath, [StringComparison]::OrdinalIgnoreCase)) {
            continue
        }
        if ($directory.Name -notmatch '^OpenAI\.Codex_[0-9][A-Za-z0-9._-]*$') {
            $results.Add([pscustomobject]@{ path = $candidate; status = 'skipped_unrecognized'; bytes = 0 })
            continue
        }
        if ($directory.Attributes -band [IO.FileAttributes]::ReparsePoint) {
            $results.Add([pscustomobject]@{ path = $candidate; status = 'skipped_reparse'; bytes = 0 })
            continue
        }

        $candidatePrefix = $candidate + '\'
        $inUse = @($processPaths | Where-Object {
            $_.StartsWith($candidatePrefix, [StringComparison]::OrdinalIgnoreCase)
        }).Count -gt 0
        if ($inUse) {
            $results.Add([pscustomobject]@{ path = $candidate; status = 'skipped_in_use'; bytes = 0 })
            continue
        }

        $files = @(Get-ChildItem -LiteralPath $candidate -File -Recurse -Force)
        $bytes = if ($files.Count) {
            [long](($files | Measure-Object -Property Length -Sum).Sum)
        } else {
            0L
        }
        Remove-Item -LiteralPath $candidate -Recurse -Force
        if (Test-Path -LiteralPath $candidate) {
            throw "Stale Codex++ store copy still exists after cleanup: $candidate"
        }
        $results.Add([pscustomobject]@{ path = $candidate; status = 'removed'; bytes = $bytes })
    }
    return @($results)
}

function Sync-CanonicalShortcutBoundary {
    $proxy = '@@LAUNCHER_ROOT:win@@\Start-CodexPlusPlus-Proxy.cmd'
    $canonical = '@@USERPROFILE:win@@\Desktop\Codex++ 启动.lnk'
    $directPaths = @(
        '@@USERPROFILE:win@@\Desktop\Codex++.lnk',
        '@@USERPROFILE:win@@\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Codex++.lnk',
        '@@USERPROFILE:win@@\AppData\Roaming\CodexPlusPlusProfile\Desktop\Codex++.lnk',
        '@@USERPROFILE:win@@\AppData\Roaming\CodexPlusPlusProfile\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Codex.lnk',
        '@@USERPROFILE:win@@\AppData\Roaming\CodexPlusPlusProfile\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\ChatGPT.lnk'
    )
    if (-not (Test-Path -LiteralPath $proxy -PathType Leaf)) {
        throw "Canonical Codex++ launcher is missing: $proxy"
    }

    $shell = New-Object -ComObject WScript.Shell
    $actions = [Collections.Generic.List[object]]::new()
    foreach ($path in $directPaths) {
        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { continue }
        $item = Get-Item -LiteralPath $path -Force
        if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) {
            $actions.Add([pscustomobject]@{ path = $path; status = 'skipped_reparse' })
            continue
        }
        $shortcut = $shell.CreateShortcut($path)
        $target = [IO.Path]::GetFullPath([string]$shortcut.TargetPath)
        $storePrefix = [IO.Path]::GetFullPath($storeRoot).TrimEnd('\') + '\'
        $targetLeaf = [IO.Path]::GetFileName($target)
        if (-not $target.StartsWith($storePrefix, [StringComparison]::OrdinalIgnoreCase) -or
            $targetLeaf -notin @('Codex.exe', 'ChatGPT.exe')) {
            $actions.Add([pscustomobject]@{ path = $path; status = 'skipped_non_store_target' })
            continue
        }
        Remove-Item -LiteralPath $path -Force
        if (Test-Path -LiteralPath $path) {
            throw "Direct Codex++ shortcut remains after cleanup: $path"
        }
        $actions.Add([pscustomobject]@{ path = $path; status = 'removed_direct_store_shortcut' })
    }

    $canonicalNeedsWrite = $true
    if (Test-Path -LiteralPath $canonical -PathType Leaf) {
        $item = Get-Item -LiteralPath $canonical -Force
        if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) {
            throw "Canonical Codex++ shortcut must be a physical file: $canonical"
        }
        $existing = $shell.CreateShortcut($canonical)
        $canonicalNeedsWrite =
            -not [string]::Equals(
                [IO.Path]::GetFullPath([string]$existing.TargetPath),
                [IO.Path]::GetFullPath($proxy),
                [StringComparison]::OrdinalIgnoreCase
            ) -or
            -not [string]::IsNullOrEmpty([string]$existing.Arguments) -or
            -not [string]::Equals(
                [IO.Path]::GetFullPath([string]$existing.WorkingDirectory),
                [IO.Path]::GetFullPath((Split-Path -Parent $proxy)),
                [StringComparison]::OrdinalIgnoreCase
            )
    }
    if ($canonicalNeedsWrite) {
        $shortcut = $shell.CreateShortcut($canonical)
        $shortcut.TargetPath = $proxy
        $shortcut.Arguments = ''
        $shortcut.WorkingDirectory = Split-Path -Parent $proxy
        $shortcut.Save()
        $actions.Add([pscustomobject]@{ path = $canonical; status = 'created_or_repaired_canonical' })
    } else {
        $actions.Add([pscustomobject]@{ path = $canonical; status = 'canonical_unchanged' })
    }
    return @($actions)
}

function Sync-ManagedCliShims {
    $resolvedBin = [IO.Path]::GetFullPath($runtimeBin).TrimEnd('\')
    $expectedBin = [IO.Path]::GetFullPath('@@CODEXPP_RUNTIME:win@@\bin').TrimEnd('\')
    if (-not [string]::Equals($resolvedBin, $expectedBin, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Codex++ CLI bin root drifted: $resolvedBin"
    }
    if (-not (Test-Path -LiteralPath $resolvedBin -PathType Container)) {
        [IO.Directory]::CreateDirectory($resolvedBin) | Out-Null
    }
    $binItem = Get-Item -LiteralPath $resolvedBin -Force
    if ($binItem.Attributes -band [IO.FileAttributes]::ReparsePoint) {
        throw "Codex++ CLI bin root must be physical: $resolvedBin"
    }

    $contents = [IO.File]::ReadAllText($cliShimTemplate).Replace("`r`n", "`n").Replace("`n", "`r`n")
    $encoding = [Text.UTF8Encoding]::new($false)
    $results = [Collections.Generic.List[object]]::new()
    foreach ($name in @('codexplusplus.cmd', 'codex-plusplus.cmd')) {
        $path = Join-Path $resolvedBin $name
        if (Test-Path -LiteralPath $path) {
            $item = Get-Item -LiteralPath $path -Force
            if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) {
                throw "Codex++ managed CLI shim must be physical: $path"
            }
        }
        $current = if (Test-Path -LiteralPath $path -PathType Leaf) { [IO.File]::ReadAllText($path) } else { $null }
        if ([string]::Equals($current, $contents, [StringComparison]::Ordinal)) {
            $results.Add([pscustomobject]@{ path = $path; status = 'unchanged' })
            continue
        }
        [IO.File]::WriteAllText($path, $contents, $encoding)
        $results.Add([pscustomobject]@{ path = $path; status = 'created_or_repaired' })
    }
    return @($results)
}

function Sync-CodexPlusPlusPluginConfiguration {
    $canonicalProfileRoot = [IO.Path]::GetFullPath('@@CODEXPP_PROFILE:win@@').TrimEnd('\')
    $canonicalCodexHome = Join-Path $canonicalProfileRoot 'AppData\Roaming\Codex\.codex'
    $configPath = Join-Path $canonicalCodexHome 'config.toml'
    $authPath = Join-Path $canonicalCodexHome 'auth.json'
    if (-not (Test-Path -LiteralPath $configPath -PathType Leaf)) {
        throw "Codex++ plugin configuration is missing: $configPath"
    }

    $authMode = $null
    if (Test-Path -LiteralPath $authPath -PathType Leaf) {
        try {
            $authMode = [string]((Get-Content -LiteralPath $authPath -Raw | ConvertFrom-Json).auth_mode)
        } catch {
            throw "Codex++ auth mode could not be read for plugin reconciliation: $($_.Exception.Message)"
        }
    }

    # These are local marketplace sources, so they must follow the same
    # canonical D: write/read boundary as CODEX_HOME. Electron and plugin paths
    # use the physical D profile directly.
    $desired = [ordered]@{
        'marketplaces.openai-primary-runtime' = [ordered]@{
            source_type = '"local"'
            source = "'@@CODEXPP_PROFILE:win@@\.cache\codex-runtimes\codex-primary-runtime\plugins\openai-primary-runtime'"
        }
        'marketplaces.openai-bundled' = [ordered]@{
            source_type = '"local"'
            source = "'@@CODEXPP_HOME:win@@\.tmp\bundled-marketplaces\openai-bundled'"
        }
        'marketplaces.openai-curated' = [ordered]@{
            source_type = '"local"'
            source = "'@@CODEXPP_HOME:win@@\plugins\cache\openai-curated'"
        }
    }
    if ([string]::Equals($authMode, 'apikey', [StringComparison]::OrdinalIgnoreCase)) {
        # ChatGPT remote plugin catalog endpoints reject API-key auth.  Keep
        # local plugins enabled, but do not advertise remote-plugin support in
        # this profile or silently change the user's authentication mode.
        $desired['features'] = [ordered]@{ remote_plugin = 'false' }
    }

    $lines = [IO.File]::ReadAllLines($configPath)
    $output = [Collections.Generic.List[string]]::new()
    $seenSections = @{}
    $seenKeys = @{}
    $changes = [Collections.Generic.List[string]]::new()
    $currentSection = $null

    $flushSection = {
        param([string]$Section)
        if (-not $Section -or -not $desired.Contains($Section)) { return }
        foreach ($entry in $desired[$Section].GetEnumerator()) {
            $identity = "$Section|$($entry.Key)"
            if (-not $seenKeys.ContainsKey($identity)) {
                $output.Add("$($entry.Key) = $($entry.Value)")
                $seenKeys[$identity] = $true
                $changes.Add("added:$identity")
            }
        }
    }

    foreach ($line in $lines) {
        if ($line -match '^\[([^\]]+)\]\s*$') {
            & $flushSection $currentSection
            $currentSection = [string]$Matches[1]
            $seenSections[$currentSection] = $true
            $output.Add($line)
            continue
        }
        if ($currentSection -and $desired.Contains($currentSection) -and $line -match '^\s*([A-Za-z0-9_-]+)\s*=') {
            $key = [string]$Matches[1]
            if ($desired[$currentSection].Contains($key)) {
                $identity = "$currentSection|$key"
                $replacement = "$key = $($desired[$currentSection][$key])"
                $seenKeys[$identity] = $true
                if (-not [string]::Equals($line, $replacement, [StringComparison]::Ordinal)) {
                    $output.Add($replacement)
                    $changes.Add("updated:$identity")
                } else {
                    $output.Add($line)
                }
                continue
            }
        }
        $output.Add($line)
    }
    & $flushSection $currentSection

    foreach ($section in $desired.Keys) {
        if ($seenSections.ContainsKey($section)) { continue }
        if ($output.Count -gt 0 -and $output[$output.Count - 1] -ne '') { $output.Add('') }
        $output.Add("[$section]")
        foreach ($entry in $desired[$section].GetEnumerator()) {
            $output.Add("$($entry.Key) = $($entry.Value)")
            $changes.Add("added:$section|$($entry.Key)")
        }
    }

    if ($changes.Count -gt 0) {
        $encoding = [Text.UTF8Encoding]::new($false)
        $tempPath = "$configPath.tmp-$PID-$([guid]::NewGuid().ToString('N'))"
        try {
            [IO.File]::WriteAllText($tempPath, ([string]::Join("`r`n", $output) + "`r`n"), $encoding)
            [IO.File]::Move($tempPath, $configPath, $true)
        } finally {
            if (Test-Path -LiteralPath $tempPath -PathType Leaf) {
                Remove-Item -LiteralPath $tempPath -Force -ErrorAction SilentlyContinue
            }
        }
    }

    return [pscustomobject]@{
        status = if ($changes.Count -gt 0) { 'reconciled' } else { 'unchanged' }
        config_path = $configPath
        auth_mode = $authMode
        changes = @($changes)
    }
}

function Write-Result {
    param(
        [Parameter(Mandatory = $true)][string]$Token,
        [Parameter(Mandatory = $true)][object]$Payload
    )
    Write-Output $Token
    Write-Output ($Payload | ConvertTo-Json -Depth 6 -Compress)
}

try {
    Assert-PowerShell7
    foreach ($required in @($nodeExe, $nativeCli, $cliShimTemplate, $injectionGuard, $profileRootContractSource)) {
        if (-not (Test-Path -LiteralPath $required -PathType Leaf)) {
            throw "Required Codex++ maintenance file is missing: $required"
        }
    }
    . $profileRootContractSource
    [void](Assert-CodexPlusPlusProfileRootContract)
    if ($ParentOwnsMaintenanceMutex) {
        Assert-ParentMaintenanceOwner
    } else {
        Enter-MaintenanceMutex
    }

    $package = Get-OfficialCodexPackage
    $packageIdentity = Split-Path -Leaf ([string]$package.InstallLocation)
    if ($packageIdentity -notmatch '^OpenAI\.Codex_[^\\]+$') {
        throw "Unexpected official package identity: $packageIdentity"
    }
    $officialAppRoot = [IO.Path]::GetFullPath((Join-Path ([string]$package.InstallLocation) 'app')).TrimEnd('\')
    $expectedAppRoot = [IO.Path]::GetFullPath((Join-Path (Join-Path $storeRoot $packageIdentity) 'app')).TrimEnd('\')
    if (-not $expectedAppRoot.StartsWith(([IO.Path]::GetFullPath($storeRoot).TrimEnd('\') + '\'), [StringComparison]::OrdinalIgnoreCase)) {
        throw "Derived Codex++ app root escaped the fixed store: $expectedAppRoot"
    }

    $profileRunning = Test-CodexPlusPlusProfileRunning
    if ($profileRunning -and $RequireStoppedProfile) {
        Write-Result -Token 'CODEXPP_REPAIR_WAIT_PROFILE_EXIT' -Payload ([ordered]@{
            schema_version = 'codexplusplus-repair.v3'
            status = 'wait_profile_exit'
            error = 'WAIT_PROFILE_EXIT_REQUIRED'
        })
        Exit-MaintenanceMutex
        exit 2
    }

    $storeCleanup = @()
    $repairExitCode = $null
    $injectionExitCode = $null
    $cliShims = @()
    $pluginConfiguration = [pscustomobject]@{
        status = 'skipped_profile_running'
        config_path = '@@CODEXPP_HOME:win@@\config.toml'
        auth_mode = $null
        changes = @()
    }
    $status = if ($profileRunning) { 'pending_profile_exit' } else { 'synced' }

    if (-not $profileRunning) {
        try {
            # The official installer owns WindowsApps -> store mirror and app.asar patching.
            $repairArguments = @('repair', '--app', $officialAppRoot, '--quiet')
            if ($ForceRepair) { $repairArguments += '--force' }
            $repairOutput = @(& $nodeExe $nativeCli @repairArguments 2>&1)
            $repairExitCode = $LASTEXITCODE
            if ($repairExitCode -ne 0) {
                throw "Codex++ native repair failed (exit $repairExitCode): $($repairOutput -join "`n")"
            }

            $launchExecutable = @(
                (Join-Path $expectedAppRoot 'ChatGPT.exe'),
                (Join-Path $expectedAppRoot 'Codex.exe')
            ) | Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } | Select-Object -First 1
            if (-not $launchExecutable) {
                throw "Codex++ native repair did not create the expected current store app: $expectedAppRoot"
            }

            $guardOutput = @(& $powerShell7 -NoProfile -File $injectionGuard -AppRoot $expectedAppRoot -SkipProcessCheck 2>&1)
            $injectionExitCode = $LASTEXITCODE
            if ($injectionExitCode -ne 0) {
                throw "Codex++ injection verification failed (exit $injectionExitCode): $($guardOutput -join "`n")"
            }
        } finally {
            # Native install() rewrites both runtime shims before patching. Always
            # restore the controlled routes, including every failure path.
            $cliShims = @(Sync-ManagedCliShims)
        }
    } else {
        $cliShims = @(Sync-ManagedCliShims)
    }

    if (-not $profileRunning) {
        $pluginConfiguration = Sync-CodexPlusPlusPluginConfiguration
    }

    # Commit cleanup only after the new current package has been repaired and
    # its injection has been verified. A failed repair must not sacrifice the
    # last known-good old mirror.
    $storeCleanup = @(Remove-StaleStoreCopies -CurrentPackageIdentity $packageIdentity)

    $shortcutBoundary = @(Sync-CanonicalShortcutBoundary)

    # Projection failure is local to this publication pass; it is reported but
    # never promoted into a permanent Host/update gate.
    $projection = Invoke-ProjectionSync
    if ($projection.Status -ne 'pass') {
        Write-Warning "Host capability projection reported drift/collision: $($projection.Output)"
    }

    $removedStoreCopies = @($storeCleanup | Where-Object status -eq 'removed')
    $reclaimedBytes = if ($removedStoreCopies.Count) {
        [long](($removedStoreCopies | Measure-Object -Property bytes -Sum).Sum)
    } else {
        0L
    }
    $payload = [ordered]@{
        schema_version = 'codexplusplus-update-sync.v2'
        status = $status
        power_shell = $PSVersionTable.PSVersion.ToString()
        official_version = [string]$package.Version
        official_install_location = [string]$package.InstallLocation
        expected_app_root = $expectedAppRoot
        profile_running = $profileRunning
        repair_exit_code = $repairExitCode
        injection_exit_code = $injectionExitCode
        projection_status = $projection.Status
        projection_exit_code = $projection.ExitCode
        projection_output = $projection.Output
        store_cleanup = $storeCleanup
        store_bytes_reclaimed = $reclaimedBytes
        cli_shims = $cliShims
        shortcut_boundary = $shortcutBoundary
        plugin_configuration = $pluginConfiguration
    }
    Exit-MaintenanceMutex
    Write-Result -Token 'CODEXPP_UPDATE_SYNC_PASS' -Payload $payload
    exit 0
} catch {
    Exit-MaintenanceMutex
    $payload = [ordered]@{
        schema_version = 'codexplusplus-update-sync.v2'
        status = 'failed'
        power_shell = $PSVersionTable.PSVersion.ToString()
        error = [string]$_.Exception.Message
    }
    Write-Result -Token 'CODEXPP_UPDATE_SYNC_FAIL' -Payload $payload
    exit 1
}
