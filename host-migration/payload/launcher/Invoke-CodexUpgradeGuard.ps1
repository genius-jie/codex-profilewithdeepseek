#requires -Version 7.0

<###
  Codex / Codex++ 升级基线与验收入口。

  设计不变量：
  1. 普通 Codex 与 Codex++ 只能有各自的包、数据根和配置根。
  2. 原生 Codex 更新允许改变官方包版本，但不能改变普通 Codex 配置，
     也不能让 Codex++ 绕过 15740 适配层。
  3. Codex++ 的正式升级仍由 Update-CodexPlusPlusInstaller.ps1 负责；
     本脚本只负责冻结基线和升级后的验收，不创建服务、计划任务或 watcher。
  4. 失败时先停止在验收门，不自动覆盖用户配置；已有 updater 的源代码回退
     机制继续作为唯一回退入口。

  用法：
    pwsh -File Invoke-CodexUpgradeGuard.ps1 -Mode Prepare
    # 手动完成原生 Codex 更新后，关闭/启动 Codex++，再执行：
    pwsh -File Invoke-CodexUpgradeGuard.ps1 -Mode Verify
###>

[CmdletBinding()]
param(
    [ValidateSet('Prepare', 'Verify')]
    [string]$Mode = 'Verify',
    [string]$BaselineRoot = '@@LAUNCHER_ROOT:win@@\upgrade-baselines',
    [string]$Tag = ''
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

$powerShell7 = '@@POWERSHELL_EXE:win@@'
$profileRoot = '@@CODEXPP_PROFILE:win@@'
$canonicalCodexHome = Join-Path $profileRoot 'AppData\Roaming\Codex\.codex'
$canonicalRuntimeRoot = Join-Path $profileRoot 'AppData\Roaming\codex-plusplus'
$ordinaryCodexHome = '@@CODEX_HOME:win@@'
$profileAliasRoot = '@@USERPROFILE:win@@\AppData\Roaming\CodexPlusPlusProfile'
$storeRoot = '@@CODEXPP_INSTALL_ROOT:win@@\store-apps'
$nativeConfig = Join-Path $ordinaryCodexHome 'config.toml'
$plusConfig = Join-Path $canonicalCodexHome 'config.toml'
$plusTweakConfig = Join-Path $canonicalRuntimeRoot 'config.json'
$statePath = Join-Path $canonicalRuntimeRoot 'state.json'
$ordinaryAgents = Join-Path $ordinaryCodexHome 'AGENTS.md'
$ordinaryHooks = Join-Path $ordinaryCodexHome 'hooks.json'
$plusAgents = Join-Path $canonicalCodexHome 'AGENTS.md'
$plusHooks = Join-Path $canonicalCodexHome 'hooks.json'
$syncEntry = '@@LAUNCHER_ROOT:win@@\Sync-CodexPlusPlusLatest.ps1'
$installerUpdate = '@@LAUNCHER_ROOT:win@@\Update-CodexPlusPlusInstaller.ps1'
$governanceGuard = '@@LAUNCHER_ROOT:win@@\Protect-CodexPlusPlusGovernance.ps1'
$projectionCheck = '@@GENERAL_ROOT:win@@\tooling\Sync-HostCapabilityProjection.ps1'
$aliasGuard = '@@LAUNCHER_ROOT:win@@\Test-CodexPlusPlusProfileAliasBoundary.ps1'
$tweakGuard = '@@LAUNCHER_ROOT:win@@\Test-CodexPlusPlusTweakLinks.ps1'
$injectionGuard = '@@LAUNCHER_ROOT:win@@\Test-CodexPlusPlusInjection.ps1'
$windowGuard = '@@LAUNCHER_ROOT:win@@\Test-CodexPlusPlusWindowRuntime.ps1'
$fallbackSources = @(
    '@@CODEXPP_RUNTIME:win@@\tweaks\com.lobster.auto-follow-up\index.js'
    '@@CODEXPP_RUNTIME:win@@\tweaks\co.Arconte112.followup\index.js'
    '@@CODEXPP_RUNTIME:win@@\tweaks\co.bennett.goal\index.js'
    '@@CODEXPP_RUNTIME:win@@\tweaks\co.Arconte112.session-path-normalizer\index.js'
    '@@CODEXPP_RUNTIME:win@@\runtime\main.js'
)
$activeProfileSourceRoot = '@@CODEXPP_RUNTIME:win@@'
$trackedFiles = [ordered]@{
    ordinary_config = $nativeConfig
    ordinary_agents = $ordinaryAgents
    ordinary_hooks = $ordinaryHooks
    codexpp_config = $plusConfig
    codexpp_agents = $plusAgents
    codexpp_hooks = $plusHooks
    codexpp_tweak_config = $plusTweakConfig
    codexpp_start = '@@LAUNCHER_ROOT:win@@\Start-CodexPlusPlus.ps1'
    codexpp_sync = $syncEntry
    codexpp_updater = $installerUpdate
    profile_contract = '@@LAUNCHER_ROOT:win@@\Assert-CodexPlusPlusProfileRootContract.ps1'
    alias_guard = $aliasGuard
    injection_guard = $injectionGuard
    window_guard = $windowGuard
    fallback_auto_followup = $fallbackSources[0]
    fallback_followup = $fallbackSources[1]
    fallback_goal = $fallbackSources[2]
    fallback_path_normalizer = $fallbackSources[3]
    fallback_runtime = $fallbackSources[4]
}

function Get-FileRecord {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        return [ordered]@{ path = $Path; exists = $false; sha256 = $null; bytes = $null; last_write = $null }
    }
    $item = Get-Item -LiteralPath $Path -Force
    return [ordered]@{
        path = $Path
        exists = $true
        sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $Path).Hash.ToLowerInvariant()
        bytes = [int64]$item.Length
        last_write = $item.LastWriteTime.ToString('o')
    }
}

function Get-PackageRecord {
    param([string]$Name)
    $package = Get-AppxPackage -Name $Name -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $package) {
        return [ordered]@{ name = $Name; present = $false; version = $null; install_location = $null; package_full_name = $null }
    }
    return [ordered]@{
        name = $package.Name
        present = $true
        version = [string]$package.Version
        install_location = [string]$package.InstallLocation
        package_full_name = [string]$package.PackageFullName
    }
}

function Get-AppRoot {
    if (Test-Path -LiteralPath $statePath -PathType Leaf) {
        try {
            $state = Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json
            if ($state.appRoot) { return [string]$state.appRoot }
        } catch { }
    }
    $package = Get-PackageRecord 'OpenAI.CodexPlusPlus'
    if ($package.present) { return Join-Path $package.install_location 'app' }
    return $null
}

function Invoke-Health {
    param([string]$Url)
    try {
        $response = Invoke-WebRequest -UseBasicParsing -Uri $Url -TimeoutSec 5
        return [ordered]@{ url = $Url; pass = $true; status = [int]$response.StatusCode; body = ([string]$response.Content).Substring(0, [Math]::Min(240, ([string]$response.Content).Length)) }
    } catch {
        return [ordered]@{ url = $Url; pass = $false; status = $null; body = $_.Exception.Message }
    }
}

function Get-Snapshot {
    $records = [ordered]@{}
    foreach ($entry in $trackedFiles.GetEnumerator()) {
        $records[$entry.Key] = Get-FileRecord $entry.Value
    }
    $plusText = if (Test-Path -LiteralPath $plusConfig -PathType Leaf) { Get-Content -LiteralPath $plusConfig -Raw } else { '' }
    $nativeText = if (Test-Path -LiteralPath $nativeConfig -PathType Leaf) { Get-Content -LiteralPath $nativeConfig -Raw } else { '' }
    $fallbackTexts = @($fallbackSources | ForEach-Object {
        if (Test-Path -LiteralPath $_ -PathType Leaf) { Get-Content -LiteralPath $_ -Raw } else { '' }
    })
    $legacyFallbackHits = @(@(
        ($fallbackTexts[0] -match 'process\.env\.CODEX_HOME\s*\|\|\s*"C:\\\\Users\\\\Administrator\\\\AppData\\\\Roaming\\\\CodexPlusPlusProfile')
        ($fallbackTexts[1] -match 'process\.env\.CODEX_HOME\s*\|\|\s*path\.join\(os\.homedir')
        ($fallbackTexts[2] -match 'process\.env\.CODEX_HOME\s*\|\|\s*path\.join\(os\.homedir')
        ($fallbackTexts[3] -match 'process\.env\.CODEX_HOME\s*\|\|\s*path\.join\(os\.homedir')
        ($fallbackTexts[4] -match 'process\.env\.CODEX_HOME\s*\|\|\s*\(0, import_node_path9\.join\)')
    ) | Where-Object { $_ })
    $activeSourceFallbackFiles = @(
        Get-ChildItem -LiteralPath (Join-Path $activeProfileSourceRoot 'tweaks'), (Join-Path $activeProfileSourceRoot 'runtime') -File -Recurse -ErrorAction SilentlyContinue |
            Where-Object { $_.Extension -in @('.js','.mjs','.cjs','.ps1') -and $_.FullName -notmatch '\\tests\\' } |
            Select-String -Pattern 'process\.env\.CODEX_HOME\s*\|\|\s*(path\.join\(.*homedir|require\("os"\)\.homedir)|process\.env\.CODEX_HOME\s*\|\|\s*"C:\\\\Users\\\\Administrator\\\\AppData\\\\Roaming\\\\CodexPlusPlusProfile|CODEX_CONFIG_FILE.*homedir' -CaseSensitive:$false |
            Select-Object -ExpandProperty Path -Unique
    )
    $enabledTweaks = @()
    if (Test-Path -LiteralPath $plusTweakConfig -PathType Leaf) {
        $tweakConfig = Get-Content -LiteralPath $plusTweakConfig -Raw | ConvertFrom-Json
        $enabledTweaks = @($tweakConfig.tweaks.PSObject.Properties | Where-Object { $_.Value.enabled -eq $true } | ForEach-Object { $_.Name })
    }
    return [ordered]@{
        schema_version = 'codex-upgrade-baseline.v1'
        captured_at = (Get-Date).ToString('o')
        packages = @(
            (Get-PackageRecord 'OpenAI.Codex')
            (Get-PackageRecord 'OpenAI.CodexPlusPlus')
        )
        paths = [ordered]@{
            ordinary_codex_home = $ordinaryCodexHome
            codexpp_profile_root = $profileRoot
            codexpp_canonical_home = $canonicalCodexHome
            codexpp_runtime_root = $canonicalRuntimeRoot
            codexpp_alias_root_expected_absent = $profileAliasRoot
            codexpp_app_root = (Get-AppRoot)
        }
        invariants = [ordered]@{
            ordinary_chatgpt_base_url = [bool]($nativeText -match 'chatgpt_base_url\s*=\s*"https://chatgpt\.com/backend-api/?"')
            codexpp_provider = [bool]($plusText -match '(?m)^model_provider\s*=\s*"cm"')
            codexpp_base_url = [bool]($plusText -match '(?m)^base_url\s*=\s*"http://127\.0\.0\.1:15740/v1"')
            codexpp_profile_alias_absent = -not (Test-Path -LiteralPath $profileAliasRoot)
            legacy_c_fallback_absent = ($legacyFallbackHits.Count -eq 0)
            active_profile_fallback_absent = ($activeSourceFallbackFiles.Count -eq 0)
            codexpp_enabled_tweaks = $enabledTweaks
        }
        files = $records
        health = @(
            (Invoke-Health 'http://127.0.0.1:15740/health')
            (Invoke-Health 'http://127.0.0.1:15728/health')
            (Invoke-Health 'http://127.0.0.1:15735/health')
            (Invoke-Health 'http://127.0.0.1:48760/health')
        )
    }
}

function Write-AtomicJson {
    param([string]$Path, [object]$Value)
    $temp = "$Path.tmp-$PID-$([guid]::NewGuid().ToString('N'))"
    try {
        $json = $Value | ConvertTo-Json -Depth 12
        [IO.File]::WriteAllText($temp, $json + [Environment]::NewLine, [Text.UTF8Encoding]::new($false))
        [IO.File]::Move($temp, $Path, $true)
    } finally {
        if (Test-Path -LiteralPath $temp -PathType Leaf) { Remove-Item -LiteralPath $temp -Force -ErrorAction SilentlyContinue }
    }
}

function Invoke-ExistingGuard {
    param([string]$Path, [string[]]$Arguments)
    $output = @(& $powerShell7 -NoLogo -NoProfile -File $Path @Arguments 2>&1)
    return [ordered]@{
        path = $Path
        pass = ($LASTEXITCODE -eq 0)
        exit_code = $LASTEXITCODE
        token = [string]($output | Where-Object { [string]$_ -match '^CODEXPP_[A-Z0-9_]+_(PASS|FAIL)$' } | Select-Object -Last 1)
    }
}

function Prepare-Baseline {
    $tagValue = if ([string]::IsNullOrWhiteSpace($Tag)) { Get-Date -Format 'yyyyMMdd-HHmmss' } else { $Tag }
    $directory = Join-Path $BaselineRoot $tagValue
    if (Test-Path -LiteralPath $directory) { throw "Baseline already exists: $directory" }
    New-Item -ItemType Directory -Path (Join-Path $directory 'files') -Force | Out-Null
    $snapshot = Get-Snapshot
    foreach ($entry in $trackedFiles.GetEnumerator()) {
        if ($snapshot.files[$entry.Key].exists) {
            Copy-Item -LiteralPath $entry.Value -Destination (Join-Path (Join-Path $directory 'files') ($entry.Key + [IO.Path]::GetExtension($entry.Value))) -Force
        }
    }
    $snapshot.baseline_directory = $directory
    $snapshot.backup_files_are_local_only = $true
    Write-AtomicJson -Path (Join-Path $directory 'baseline.json') -Value $snapshot
    New-Item -ItemType Directory -Path $BaselineRoot -Force | Out-Null
    Write-AtomicJson -Path (Join-Path $BaselineRoot 'current.json') -Value ([ordered]@{ schema_version = 'codex-upgrade-baseline-pointer.v1'; baseline_directory = $directory; created_at = (Get-Date).ToString('o') })
    'CODEX_UPGRADE_GUARD_PREPARE_PASS'
    $snapshot | ConvertTo-Json -Depth 12 -Compress
}

function Verify-Baseline {
    $pointerPath = Join-Path $BaselineRoot 'current.json'
    if (-not (Test-Path -LiteralPath $pointerPath -PathType Leaf)) { throw "No current baseline pointer: $pointerPath" }
    $pointer = Get-Content -LiteralPath $pointerPath -Raw | ConvertFrom-Json
    $baselinePath = Join-Path ([string]$pointer.baseline_directory) 'baseline.json'
    if (-not (Test-Path -LiteralPath $baselinePath -PathType Leaf)) { throw "Baseline manifest missing: $baselinePath" }
    $baseline = Get-Content -LiteralPath $baselinePath -Raw | ConvertFrom-Json
    $current = Get-Snapshot
    $checks = [Collections.Generic.List[object]]::new()
    $checks.Add([pscustomobject]@{ id = 'ordinary_config_routing_invariant'; pass = [bool]$current.invariants.ordinary_chatgpt_base_url; detail = "baseline_hash=$($baseline.files.ordinary_config.sha256);current_hash=$($current.files.ordinary_config.sha256);model_fields_may_change=true" })
    $nativePackage = @($current.packages | Where-Object { $_.name -eq 'OpenAI.Codex' }) | Select-Object -First 1
    $plusPackage = @($current.packages | Where-Object { $_.name -eq 'OpenAI.CodexPlusPlus' }) | Select-Object -First 1
    $checks.Add([pscustomobject]@{ id = 'package_versions_aligned'; pass = [bool]($nativePackage.present -and $plusPackage.present -and $nativePackage.version -eq $plusPackage.version); detail = "native=$($nativePackage.version);codexpp=$($plusPackage.version)" })
    $adapterHealthUrl = 'http://127.0.0.1:15740/health'
    $baselineAdapter = $null
    $currentAdapter = $null
    $baselineAdapterHealth = @($baseline.health | Where-Object { $_.url -eq $adapterHealthUrl }) | Select-Object -First 1
    $currentAdapterHealth = @($current.health | Where-Object { $_.url -eq $adapterHealthUrl }) | Select-Object -First 1
    try { $baselineAdapter = [string](($baselineAdapterHealth.body | ConvertFrom-Json).adapter) } catch { $baselineAdapter = $null }
    try { $currentAdapter = [string](($currentAdapterHealth.body | ConvertFrom-Json).adapter) } catch { $currentAdapter = $null }
    $checks.Add([pscustomobject]@{ id = 'codexpp_adapter_version_aligned'; pass = [bool]($baselineAdapter -and $currentAdapter -and $baselineAdapter -eq $currentAdapter); detail = "baseline=$baselineAdapter;current=$currentAdapter" })
    $checks.Add([pscustomobject]@{ id = 'ordinary_context_files_unchanged'; pass = ($current.files.ordinary_agents.sha256 -eq $baseline.files.ordinary_agents.sha256 -and $current.files.ordinary_hooks.sha256 -eq $baseline.files.ordinary_hooks.sha256); detail = 'AGENTS.md + hooks.json' })
    $checks.Add([pscustomobject]@{ id = 'codexpp_config_routing_invariant'; pass = [bool]($current.invariants.codexpp_provider -and $current.invariants.codexpp_base_url); detail = "baseline_hash=$($baseline.files.codexpp_config.sha256);current_hash=$($current.files.codexpp_config.sha256);model_fields_may_change=true" })
    $checks.Add([pscustomobject]@{ id = 'codexpp_context_files_unchanged'; pass = ($current.files.codexpp_agents.sha256 -eq $baseline.files.codexpp_agents.sha256 -and $current.files.codexpp_hooks.sha256 -eq $baseline.files.codexpp_hooks.sha256); detail = 'AGENTS.md + hooks.json' })
    $checks.Add([pscustomobject]@{ id = 'profile_alias_absent'; pass = [bool]$current.invariants.codexpp_profile_alias_absent; detail = $profileAliasRoot })
    $checks.Add([pscustomobject]@{ id = 'legacy_c_fallback_absent'; pass = [bool]$current.invariants.legacy_c_fallback_absent; detail = 'active Codex++ runtime/Tweak sources must resolve D: CODEX_HOME' })
    $checks.Add([pscustomobject]@{ id = 'active_profile_fallback_absent'; pass = [bool]$current.invariants.active_profile_fallback_absent; detail = 'no active Tweak/runtime may fall back through os.homedir() to .codex' })
    $checks.Add([pscustomobject]@{ id = 'ordinary_base_url'; pass = [bool]$current.invariants.ordinary_chatgpt_base_url; detail = 'https://chatgpt.com/backend-api/' })
    $checks.Add([pscustomobject]@{ id = 'codexpp_provider_route'; pass = [bool]($current.invariants.codexpp_provider -and $current.invariants.codexpp_base_url); detail = 'cm -> http://127.0.0.1:15740/v1' })
    $requiredTweaks = @('co.Arconte112.followup','com.lobster.auto-follow-up','co.Arconte112.session-path-normalizer','co.bennett.windows-computer-use')
    $requiredTweakCount = @($requiredTweaks | Where-Object { $current.invariants.codexpp_enabled_tweaks -contains $_ }).Count
    $checks.Add([pscustomobject]@{ id = 'required_tweaks'; pass = ($requiredTweakCount -eq $requiredTweaks.Count); detail = ($current.invariants.codexpp_enabled_tweaks -join ',') })

    $checks.Add((Invoke-ExistingGuard -Path $aliasGuard -Arguments @()))
    $checks.Add((Invoke-ExistingGuard -Path $tweakGuard -Arguments @()))
    $appRoot = [string]$current.paths.codexpp_app_root
    $checks.Add((Invoke-ExistingGuard -Path $injectionGuard -Arguments @('-AppRoot', $appRoot, '-SkipProcessCheck')))
    $checks.Add((Invoke-ExistingGuard -Path $installerUpdate -Arguments @('-Mode', 'Check')))
    $checks.Add((Invoke-ExistingGuard -Path $governanceGuard -Arguments @()))
    $checks.Add((Invoke-ExistingGuard -Path $projectionCheck -Arguments @('-HostId', 'codex_plus_plus', '-SkillsRoot', (Join-Path $canonicalCodexHome 'skills'), '-Mode', 'Check')))
    $checks.Add((Invoke-ExistingGuard -Path $windowGuard -Arguments @('-ProfileRoot', $profileRoot, '-StoreRoot', $storeRoot, '-AllowNoWindow')))
    foreach ($health in @($current.health)) { $checks.Add([pscustomobject]@{ id = "health_$($health.url.Split('/')[-2])"; pass = [bool]$health.pass; detail = $health.body }) }

    $failures = @($checks | Where-Object { -not $_.pass })
    $result = [ordered]@{
        schema_version = 'codex-upgrade-verification.v1'
        status = if ($failures.Count -eq 0) { 'pass' } else { 'fail' }
        verified_at = (Get-Date).ToString('o')
        baseline_directory = [string]$pointer.baseline_directory
        native_version_change_allowed = $true
        codexpp_version = @($current.packages | Where-Object { $_.name -eq 'OpenAI.CodexPlusPlus' })[0].version
        checks = @($checks)
        failures = @($failures)
    }
    if ($failures.Count -gt 0) { 'CODEX_UPGRADE_GUARD_VERIFY_FAIL' } else { 'CODEX_UPGRADE_GUARD_VERIFY_PASS' }
    $result | ConvertTo-Json -Depth 12 -Compress
    if ($failures.Count -gt 0) { exit 1 }
}

if ($Mode -eq 'Prepare') { Prepare-Baseline; exit 0 }
Verify-Baseline
