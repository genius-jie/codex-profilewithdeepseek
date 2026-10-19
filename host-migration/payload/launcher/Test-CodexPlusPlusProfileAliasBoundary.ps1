#requires -Version 7.0

[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$configRoot = '@@LAUNCHER_ROOT:win@@'
$profileAliasRoot = [IO.Path]::GetFullPath('@@USERPROFILE:win@@\AppData\Roaming\CodexPlusPlusProfile').TrimEnd('\')
$profileCanonicalRoot = [IO.Path]::GetFullPath('@@CODEXPP_PROFILE:win@@').TrimEnd('\')
$profileRootContractSource = Join-Path $configRoot 'Assert-CodexPlusPlusProfileRootContract.ps1'
$ordinaryConfig = '@@CODEX_HOME:win@@\config.toml'
$ordinaryCodexRoot = Split-Path -Parent $ordinaryConfig

function Test-CodexPlusPlusProfileAliasDescriptor {
    param([IO.FileAttributes]$Attributes, [string]$LinkType, [object[]]$Targets, [string]$ExpectedCanonicalRoot)
    if (-not ($Attributes -band [IO.FileAttributes]::Directory) -or -not ($Attributes -band [IO.FileAttributes]::ReparsePoint)) { return $false }
    if (-not [string]::Equals($LinkType, 'Junction', [StringComparison]::OrdinalIgnoreCase)) { return $false }
    $targetList = @($Targets)
    if ($targetList.Count -ne 1 -or [string]::IsNullOrWhiteSpace([string]$targetList[0])) { return $false }
    [string]::Equals(
        [IO.Path]::GetFullPath([string]$targetList[0]).TrimEnd('\'),
        [IO.Path]::GetFullPath($ExpectedCanonicalRoot).TrimEnd('\'),
        [StringComparison]::OrdinalIgnoreCase
    )
}

function Test-PhysicalPathChain([string]$Path) {
    $full = [IO.Path]::GetFullPath($Path).TrimEnd('\')
    $root = [IO.Path]::GetPathRoot($full)
    $current = $root
    foreach ($part in @($full.Substring($root.Length).Split('\') | Where-Object { $_ })) {
        $current = Join-Path $current $part
        if (-not (Test-Path -LiteralPath $current)) { return $false }
        if ((Get-Item -LiteralPath $current -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) { return $false }
    }
    return $true
}

function Get-FunctionDefinitionText {
    param([Management.Automation.Language.Ast]$Ast, [string]$Name)
    $definitions = @($Ast.FindAll({
        param($node)
        $node -is [Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq $Name
    }, $true))
    if ($definitions.Count -ne 1) { return $null }
    return $definitions[0].Extent.Text
}

$ordinaryHashBefore = if (Test-Path -LiteralPath $ordinaryConfig -PathType Leaf) { (Get-FileHash -LiteralPath $ordinaryConfig -Algorithm SHA256).Hash.ToLowerInvariant() } else { $null }
$checks = [Collections.Generic.List[object]]::new()
function Add-Check([string]$Id, [bool]$Pass, [object]$Details) {
    [void]$checks.Add([pscustomobject]@{ id = $Id; pass = $Pass; details = $Details })
}

if (Test-Path -LiteralPath $profileAliasRoot) {
    Add-Check 'legacy_profile_alias_is_absent' $false @{ reason = 'retired_alias_present'; path = $profileAliasRoot }
} else {
    Add-Check 'legacy_profile_alias_is_absent' $true @{ path = $profileAliasRoot }
}
Add-Check 'profile_alias_parent_is_physical' (Test-PhysicalPathChain -Path (Split-Path -Parent $profileAliasRoot)) @{ path = (Split-Path -Parent $profileAliasRoot) }
Add-Check 'canonical_profile_root_is_physical' (Test-PhysicalPathChain -Path $profileCanonicalRoot) @{ path = $profileCanonicalRoot }
Add-Check 'canonical_codex_home_is_physical' (Test-PhysicalPathChain -Path (Join-Path $profileCanonicalRoot 'AppData\Roaming\Codex\.codex')) @{ path = (Join-Path $profileCanonicalRoot 'AppData\Roaming\Codex\.codex') }

$directoryReparse = [IO.FileAttributes]::Directory -bor [IO.FileAttributes]::ReparsePoint
$descriptorCases = @(
    @{ Id = 'trusted_junction_descriptor_passes'; Attributes = $directoryReparse; LinkType = 'Junction'; Targets = @($profileCanonicalRoot); Expected = $true },
    @{ Id = 'wrong_target_to_user_home_is_rejected'; Attributes = $directoryReparse; LinkType = 'Junction'; Targets = @('@@USERPROFILE:win@@'); Expected = $false },
    @{ Id = 'wrong_target_to_ordinary_codex_is_rejected'; Attributes = $directoryReparse; LinkType = 'Junction'; Targets = @('@@CODEX_HOME:win@@'); Expected = $false },
    @{ Id = 'symbolic_link_type_is_rejected'; Attributes = $directoryReparse; LinkType = 'SymbolicLink'; Targets = @($profileCanonicalRoot); Expected = $false },
    @{ Id = 'multiple_targets_are_rejected'; Attributes = $directoryReparse; LinkType = 'Junction'; Targets = @($profileCanonicalRoot, '@@USERPROFILE:win@@'); Expected = $false },
    @{ Id = 'correct_plus_empty_targets_are_rejected'; Attributes = $directoryReparse; LinkType = 'Junction'; Targets = @($profileCanonicalRoot, ''); Expected = $false },
    @{ Id = 'ordinary_directory_is_rejected'; Attributes = [IO.FileAttributes]::Directory; LinkType = ''; Targets = @(); Expected = $false }
)
foreach ($case in $descriptorCases) {
    $actual = Test-CodexPlusPlusProfileAliasDescriptor -Attributes $case.Attributes -LinkType $case.LinkType -Targets $case.Targets -ExpectedCanonicalRoot $profileCanonicalRoot
    Add-Check $case.Id ([bool]$actual -eq [bool]$case.Expected) @{ expected = [bool]$case.Expected; actual = [bool]$actual }
}

if (Test-Path -LiteralPath $profileRootContractSource -PathType Leaf) {
    try {
        . $profileRootContractSource
        $contractResult = Assert-CodexPlusPlusProfileRootContract
        Add-Check 'shared_profile_root_contract_live_passes' ([string]::Equals([string]$contractResult.CanonicalRoot, $profileCanonicalRoot, [StringComparison]::OrdinalIgnoreCase)) @{ path = $profileRootContractSource; canonical = $contractResult.CanonicalRoot }
    } catch {
        Add-Check 'shared_profile_root_contract_live_passes' $false @{ path = $profileRootContractSource; error = $_.Exception.Message }
    }
} else {
    Add-Check 'shared_profile_root_contract_live_passes' $false @{ path = $profileRootContractSource; error = 'missing' }
}

foreach ($scriptName in @('Start-CodexPlusPlus.ps1', 'Sync-CodexPlusPlusLatest.ps1')) {
    $path = Join-Path $configRoot $scriptName
    $text = if (Test-Path -LiteralPath $path -PathType Leaf) { [IO.File]::ReadAllText($path, [Text.Encoding]::UTF8) } else { '' }
    $pass = $text.Contains('Assert-CodexPlusPlusProfileRootContract.ps1') -and $text.Contains('Assert-CodexPlusPlusProfileRootContract')
    Add-Check ("consumer_contract_" + $scriptName) $pass @{ path = $path }
}
$startPath = Join-Path $configRoot 'Start-CodexPlusPlus.ps1'
$startText = if (Test-Path -LiteralPath $startPath -PathType Leaf) { [IO.File]::ReadAllText($startPath, [Text.Encoding]::UTF8) } else { '' }
$physicalUserDataPass =
    $startText.Contains("-Profile `$canonicalPlusProfile") -and
    $startText.Contains("'@@CODEXPP_PROFILE:win@@'") -and
    $startText.Contains('CODEX_PLUSPLUS_HOME')
Add-Check 'physical_user_data_dir_avoids_profile_junction' $physicalUserDataPass @{ path = $startPath }

foreach ($preflightName in @('Invoke-CodexPlusPlusEnsureWorkspace.ps1', 'Invoke-CodexPlusPlusDbReclaim.ps1', 'Invoke-CodexPlusPlusLauncherCompat.ps1', 'Ensure-CodexPlusPlusPackageRegistration.ps1')) {
    $preflightPath = Join-Path $configRoot $preflightName
    $preflightText = if (Test-Path -LiteralPath $preflightPath -PathType Leaf) { [IO.File]::ReadAllText($preflightPath, [Text.Encoding]::UTF8) } else { '' }
    $preflightDOnly = $preflightText.Contains('@@CODEXPP_PROFILE:win@@') -and -not $preflightText.Contains('$env:APPDATA')
    Add-Check ("preflight_D_only_" + $preflightName) $preflightDOnly @{ path = $preflightPath }
}

$normalizerPath = '@@CODEXPP_RUNTIME:win@@\tweaks\co.Arconte112.session-path-normalizer\index.js'
$normalizerText = if (Test-Path -LiteralPath $normalizerPath -PathType Leaf) { [IO.File]::ReadAllText($normalizerPath, [Text.Encoding]::UTF8) } else { '' }
$normalizerDOnly = $normalizerText.Contains('CANONICAL_CODEX_HOME') -and
    $normalizerText.Contains('function toCanonicalWinPath') -and
    $normalizerText.Contains('WHERE rollout_path IS NOT NULL') -and
    $normalizerText.Contains('SET rollout_path = substr(NEW.rollout_path, 5)') -and
    -not $normalizerText.Contains('WHERE archived = 0')
Add-Check 'session_path_normalizer_historical_root_repair' $normalizerDOnly @{ path = $normalizerPath }

$wcuInstallPath = '@@CODEXPP_RUNTIME:win@@\tweaks\co.bennett.windows-computer-use\scripts\install-codexpp-windows.ps1'
$wcuInstallText = if (Test-Path -LiteralPath $wcuInstallPath -PathType Leaf) { [IO.File]::ReadAllText($wcuInstallPath, [Text.Encoding]::UTF8) } else { '' }
$wcuDOnly = $wcuInstallText.Contains('$env:CODEX_HOME') -and
    $wcuInstallText.Contains('$env:CODEX_PLUSPLUS_HOME') -and
    -not $wcuInstallText.Contains('Join-Path $env:USERPROFILE ".codex')
Add-Check 'windows_computer_use_nested_codex_home_contract' $wcuDOnly @{ path = $wcuInstallPath }

$runtimeMainPath = '@@CODEXPP_RUNTIME:win@@\runtime\main.js'
$runtimeMainText = if (Test-Path -LiteralPath $runtimeMainPath -PathType Leaf) { [IO.File]::ReadAllText($runtimeMainPath, [Text.Encoding]::UTF8) } else { '' }
$runtimeMcpDOnly = $runtimeMainText.Contains('var CODEX_CONFIG_HOME = process.env.CODEX_HOME') -and
    $runtimeMainText.Contains('@@CODEXPP_HOME:escaped@@') -and
    -not $runtimeMainText.Contains('var CODEX_CONFIG_FILE = (0, import_node_path9.join)((0, import_node_os2.homedir)(), ".codex", "config.toml")')
Add-Check 'runtime_mcp_writer_nested_codex_home_contract' $runtimeMcpDOnly @{ path = $runtimeMainPath }

$watcherPath = Join-Path $configRoot 'Watch-CodexPlusPlusSessionPaths.ps1'
$watcherTokens = $null
$watcherParseErrors = $null
$watcherAst = [Management.Automation.Language.Parser]::ParseFile($watcherPath, [ref]$watcherTokens, [ref]$watcherParseErrors)
$watcherText = if (Test-Path -LiteralPath $watcherPath -PathType Leaf) { [IO.File]::ReadAllText($watcherPath, [Text.Encoding]::UTF8) } else { '' }
Add-Check 'session_maintenance_ps7_parse_contract' ($watcherParseErrors.Count -eq 0 -and $watcherText.Contains('#requires -Version 7.0')) @{ path = $watcherPath; errors = @($watcherParseErrors | ForEach-Object { $_.Message }) }
if ($watcherParseErrors.Count -eq 0) {
    $watcherAliasText = Get-FunctionDefinitionText -Ast $watcherAst -Name 'Assert-CodexPlusPlusProfileAlias'
    $watcherBoundaryText = Get-FunctionDefinitionText -Ast $watcherAst -Name 'Assert-CodexPlusPlusProfileWriteBoundary'
    $watcherDescriptorText = Get-FunctionDefinitionText -Ast $watcherAst -Name 'Test-CodexPlusPlusProfileAliasDescriptor'
    $watcherBatchText = Get-FunctionDefinitionText -Ast $watcherAst -Name 'Invoke-CodexPlusPlusSessionMaintenanceBatch'
    $watcherStartupIndex = $watcherText.IndexOf("Assert-CodexPlusPlusProfileAlias -Reason 'watcher_startup'", [StringComparison]::Ordinal)
    $watcherCodexHomeIndex = $watcherText.IndexOf("`$codexHome = Join-Path `$profileCanonicalRoot 'AppData\Roaming\Codex\.codex'", [StringComparison]::Ordinal)
    $watcherStaticPass =
        $watcherAliasText -and $watcherBoundaryText -and $watcherDescriptorText -and $watcherBatchText -and
        $watcherStartupIndex -ge 0 -and $watcherCodexHomeIndex -ge 0 -and $watcherCodexHomeIndex -lt $watcherStartupIndex -and
        $watcherText.Contains('$codexHome = Join-Path $profileCanonicalRoot ''AppData\Roaming\Codex\.codex''') -and
        $watcherDescriptorText.Contains('$targetList.Count -ne 1') -and
        $watcherBoundaryText.Contains('Assert-CodexPlusPlusProfileAlias') -and
        $watcherBoundaryText.Contains('-CanonicalCodexHome $codexHome') -and
        $watcherBoundaryText.Contains('-OrdinaryCodexRoot $ordinaryCodexRoot') -and
        $watcherText.Contains('Test-CodexPlusPlusSessionSourcePathDescriptor -Path $path') -and
        $watcherText.Contains('quarantine root overlap with active or archived session roots') -and
        -not $watcherText.Contains('[switch]$Watch') -and
        -not $watcherText.Contains('session-path-normalizer.pid') -and
        -not $watcherText.Contains('Start-Sleep -Seconds ([Math]::Max(1, $IntervalSeconds))')
    Add-Check 'watcher_alias_canonical_write_static_contract' ([bool]$watcherStaticPass) @{ path = $watcherPath; canonical_home_before_startup = ($watcherCodexHomeIndex -lt $watcherStartupIndex) }

    $pathWithinText = Get-FunctionDefinitionText -Ast $watcherAst -Name 'Test-CodexPlusPlusPathWithinRoot'
    $convertText = Get-FunctionDefinitionText -Ast $watcherAst -Name 'Convert-CodexPlusPlusProfilePathToCanonical'
    $writeDescriptorText = Get-FunctionDefinitionText -Ast $watcherAst -Name 'Test-CodexPlusPlusWritePathDescriptor'
    $sourceDescriptorText = Get-FunctionDefinitionText -Ast $watcherAst -Name 'Test-CodexPlusPlusSessionSourcePathDescriptor'
    if ($pathWithinText -and $convertText -and $writeDescriptorText -and $sourceDescriptorText) {
        $watcherRunner = [scriptblock]::Create(@"
`$profileAliasRoot = '@@USERPROFILE:win@@\AppData\Roaming\CodexPlusPlusProfile'
`$profileCanonicalRoot = '@@CODEXPP_PROFILE:win@@'
`$codexHome = '@@CODEXPP_HOME:win@@'
$pathWithinText
$convertText
$writeDescriptorText
$sourceDescriptorText
"@)
        . $watcherRunner
        $canonicalHome = '@@CODEXPP_HOME:win@@'
        $sessionRoot = Join-Path $canonicalHome 'sessions'
        $archivedRoot = Join-Path $canonicalHome 'archived_sessions'
        $watcherBehaviorCases = @(
            @{ Id = 'watcher_alias_session_path_maps_to_canonical'; Actual = Convert-CodexPlusPlusProfilePathToCanonical '@@USERPROFILE:win@@\AppData\Roaming\CodexPlusPlusProfile\.codex\sessions\x.jsonl'; Expected = '@@CODEXPP_HOME:win@@\sessions\x.jsonl' },
            @{ Id = 'watcher_canonical_session_path_stays_canonical'; Actual = Convert-CodexPlusPlusProfilePathToCanonical '@@CODEXPP_HOME:win@@\sessions\x.jsonl'; Expected = '@@CODEXPP_HOME:win@@\sessions\x.jsonl' },
            @{ Id = 'watcher_canonical_codex_home_write_is_allowed'; Actual = Test-CodexPlusPlusWritePathDescriptor '@@CODEXPP_HOME:win@@\state_5.sqlite' $profileAliasRoot $canonicalHome $ordinaryCodexRoot; Expected = $true },
            @{ Id = 'watcher_alias_write_is_rejected'; Actual = Test-CodexPlusPlusWritePathDescriptor '@@USERPROFILE:win@@\AppData\Roaming\CodexPlusPlusProfile\.codex\state_5.sqlite' $profileAliasRoot $canonicalHome $ordinaryCodexRoot; Expected = $false },
            @{ Id = 'watcher_ordinary_codex_write_is_rejected'; Actual = Test-CodexPlusPlusWritePathDescriptor '@@CODEX_HOME:win@@\state_5.sqlite' $profileAliasRoot $canonicalHome $ordinaryCodexRoot; Expected = $false },
            @{ Id = 'watcher_non_codex_home_profile_write_is_rejected'; Actual = Test-CodexPlusPlusWritePathDescriptor '@@CODEXPP_PROFILE:win@@\AppData\x.json' $profileAliasRoot $canonicalHome $ordinaryCodexRoot; Expected = $false },
            @{ Id = 'watcher_external_write_is_rejected'; Actual = Test-CodexPlusPlusWritePathDescriptor 'C:\Temp\x.json' $profileAliasRoot $canonicalHome $ordinaryCodexRoot; Expected = $false },
            @{ Id = 'watcher_session_source_is_allowed'; Actual = Test-CodexPlusPlusSessionSourcePathDescriptor (Join-Path $sessionRoot '2026\08\x.jsonl') $sessionRoot $archivedRoot; Expected = $true },
            @{ Id = 'watcher_archived_session_source_is_allowed'; Actual = Test-CodexPlusPlusSessionSourcePathDescriptor (Join-Path $archivedRoot 'x.jsonl') $sessionRoot $archivedRoot; Expected = $true },
            @{ Id = 'watcher_other_profile_jsonl_source_is_rejected'; Actual = Test-CodexPlusPlusSessionSourcePathDescriptor (Join-Path $canonicalHome 'memories\x.jsonl') $sessionRoot $archivedRoot; Expected = $false },
            @{ Id = 'watcher_non_jsonl_session_source_is_rejected'; Actual = Test-CodexPlusPlusSessionSourcePathDescriptor (Join-Path $sessionRoot 'x.txt') $sessionRoot $archivedRoot; Expected = $false }
        )
        foreach ($case in $watcherBehaviorCases) {
            $pass = if ($case.Expected -is [bool]) { [bool]$case.Actual -eq [bool]$case.Expected } else { [string]::Equals([string]$case.Actual, [string]$case.Expected, [StringComparison]::OrdinalIgnoreCase) }
            Add-Check $case.Id $pass @{ expected = $case.Expected; actual = $case.Actual }
        }
    } else {
        Add-Check 'watcher_behavior_functions_present' $false @{ path = $watcherPath }
    }
}

$nativePath = Join-Path $configRoot 'Restore-CodexPlusPlusNativeMessagingHost.ps1'
$nativeTokens = $null
$nativeParseErrors = $null
$nativeAst = [Management.Automation.Language.Parser]::ParseFile($nativePath, [ref]$nativeTokens, [ref]$nativeParseErrors)
$nativeText = if (Test-Path -LiteralPath $nativePath -PathType Leaf) { [IO.File]::ReadAllText($nativePath, [Text.Encoding]::UTF8) } else { '' }
Add-Check 'native_restore_ps7_parse_contract' ($nativeParseErrors.Count -eq 0 -and $nativeText.Contains('#requires -Version 7.0')) @{ path = $nativePath; errors = @($nativeParseErrors | ForEach-Object { $_.Message }) }
if ($nativeParseErrors.Count -eq 0) {
    $nativeAliasText = Get-FunctionDefinitionText -Ast $nativeAst -Name 'Assert-CodexPlusPlusProfileAlias'
    $nativeDescriptorText = Get-FunctionDefinitionText -Ast $nativeAst -Name 'Test-CodexPlusPlusProfileAliasDescriptor'
    $nativeAliasStatusText = Get-FunctionDefinitionText -Ast $nativeAst -Name 'Get-CodexPlusPlusProfileAliasStatus'
    $nativeRestoreText = Get-FunctionDefinitionText -Ast $nativeAst -Name 'Get-RestoreDecision'
    $nativeStaticPass =
        $nativeAliasText -and $nativeDescriptorText -and $nativeAliasStatusText -and $nativeRestoreText -and
        $nativeText.Contains("`$expectedIsolatedManifest = '@@CODEXPP_PROFILE:win@@\AppData\Local\OpenAI\extension\com.openai.codexextension.json'") -and
        $nativeText.Contains("`$evidencePath = Join-Path `$canonicalCodexHome 'native-messaging-host-restore.json'") -and
        -not $nativeText.Contains("CodexPlusPlusProfile\.codex\native-messaging-host-restore.json'") -and
        $nativeText.Contains("`$canonicalCodexHome = Join-Path `$profileCanonicalRoot 'AppData\Roaming\Codex\.codex'") -and
        $nativeDescriptorText.Contains('$targetList.Count -ne 1') -and
        $nativeAliasStatusText.Contains('Assert-CodexPlusPlusProfileAlias') -and
        $nativeText.Contains("Get-CodexPlusPlusProfileAliasStatus -Reason 'native_restore_startup_probe'") -and
        $nativeText.Contains("Get-CodexPlusPlusProfileAliasStatus -Reason 'native_restore_observation_probe'") -and
        -not $nativeText.Contains("Assert-CodexPlusPlusProfileAlias -Reason 'native_registry_compare_and_set'") -and
        -not $nativeRestoreText.Contains('ProfileAlias') -and
        $nativeText.Contains('$payload.evidence_written = $true') -and
        $nativeText.Contains('$payload.evidence_write_error = $_.Exception.Message') -and
        $nativeText.Contains("Assert-CodexPlusPlusExistingPathChainPhysical -Path `$evidencePath")
    Add-Check 'native_restore_alias_and_canonical_evidence_static_contract' ([bool]$nativeStaticPass) @{ path = $nativePath }
    if ($nativeRestoreText) {
        $nativeRunner = [scriptblock]::Create("$nativeRestoreText`n")
        . $nativeRunner
        $aliasManifest = '@@CODEXPP_PROFILE:win@@\AppData\Local\OpenAI\extension\com.openai.codexextension.json'
        $nativeBehaviorCases = @(
            @{ Id = 'native_restore_prior_when_alias_value_still_owned'; Actual = Get-RestoreDecision $true $aliasManifest $true 'C:\Prior\manifest.json' $aliasManifest; Expected = 'restore_prior' },
            @{ Id = 'native_remove_alias_when_no_prior_value'; Actual = Get-RestoreDecision $true $aliasManifest $false $null $aliasManifest; Expected = 'remove_isolated' },
            @{ Id = 'native_external_writer_conflict_is_preserved'; Actual = Get-RestoreDecision $true 'C:\External\manifest.json' $true 'C:\Prior\manifest.json' $aliasManifest; Expected = 'external_writer_conflict' },
            @{ Id = 'native_alias_already_prior_is_noop'; Actual = Get-RestoreDecision $true $aliasManifest $true $aliasManifest $aliasManifest; Expected = 'already_prior' },
            @{ Id = 'native_alias_invalid_still_restores_owned_value'; AliasValid = $false; Actual = Get-RestoreDecision $true $aliasManifest $true 'C:\Prior\manifest.json' $aliasManifest; Expected = 'restore_prior' },
            @{ Id = 'native_alias_invalid_external_writer_is_preserved'; AliasValid = $false; Actual = Get-RestoreDecision $true 'C:\External\manifest.json' $true 'C:\Prior\manifest.json' $aliasManifest; Expected = 'external_writer_conflict' }
        )
        foreach ($case in $nativeBehaviorCases) {
            Add-Check $case.Id ([string]::Equals([string]$case.Actual, [string]$case.Expected, [StringComparison]::Ordinal)) @{ expected = $case.Expected; actual = $case.Actual; alias_valid = $case.AliasValid }
        }
    }
}

$ordinaryHashAfter = if (Test-Path -LiteralPath $ordinaryConfig -PathType Leaf) { (Get-FileHash -LiteralPath $ordinaryConfig -Algorithm SHA256).Hash.ToLowerInvariant() } else { $null }
$ordinaryUntouched = $ordinaryHashBefore -eq $ordinaryHashAfter
Add-Check 'ordinary_codex_config_untouched' $ordinaryUntouched @{ before = $ordinaryHashBefore; after = $ordinaryHashAfter }
$failures = @($checks | Where-Object { -not $_.pass })
$payload = [ordered]@{
    guard = 'codexplusplus_profile_alias_boundary_guard'
    status = if ($failures.Count -eq 0) { 'pass' } else { 'fail' }
    checked_at = [DateTimeOffset]::Now.ToString('o')
    profile_alias = $profileAliasRoot
    canonical_root = $profileCanonicalRoot
    ordinary_codex_untouched = $ordinaryUntouched
    checks = @($checks)
    failures = @($failures)
}
if ($failures.Count -gt 0) {
    Write-Output 'CODEXPP_PROFILE_ALIAS_BOUNDARY_GUARD_FAIL'
    $payload | ConvertTo-Json -Depth 10
    exit 1
}
Write-Output 'CODEXPP_PROFILE_ALIAS_BOUNDARY_GUARD_PASS'
$payload | ConvertTo-Json -Depth 10
