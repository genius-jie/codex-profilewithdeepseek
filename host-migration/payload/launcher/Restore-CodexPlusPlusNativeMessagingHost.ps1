#requires -Version 7.0

[CmdletBinding()]
param(
    [string]$PriorValueBase64 = '',
    [switch]$PriorValueExisted,
    [ValidateSet('String', 'ExpandString')]
    [string]$PriorValueKind = 'String',
    [ValidateRange(5, 120)]
    [int]$DurationSeconds = 35,
    [ValidateRange(1, 10)]
    [int]$IntervalSeconds = 2
)

$ErrorActionPreference = 'Stop'
$utf8NoBom = [Text.UTF8Encoding]::new($false)
$registrySubKey = 'SOFTWARE\Google\Chrome\NativeMessagingHosts\com.openai.codexextension'
$profileAliasRoot = [IO.Path]::GetFullPath('@@USERPROFILE:win@@\AppData\Roaming\CodexPlusPlusProfile').TrimEnd('\')
$profileCanonicalRoot = [IO.Path]::GetFullPath('@@CODEXPP_PROFILE:win@@').TrimEnd('\')
$expectedIsolatedManifest = '@@CODEXPP_PROFILE:win@@\AppData\Local\OpenAI\extension\com.openai.codexextension.json'
$canonicalCodexHome = Join-Path $profileCanonicalRoot 'AppData\Roaming\Codex\.codex'
$evidencePath = Join-Path $canonicalCodexHome 'native-messaging-host-restore.json'

function Test-CodexPlusPlusProfileAliasDescriptor {
    param([IO.FileAttributes]$Attributes, [string]$LinkType, [object[]]$Targets, [string]$ExpectedCanonicalRoot)
    if (-not ($Attributes -band [IO.FileAttributes]::Directory) -or
        -not ($Attributes -band [IO.FileAttributes]::ReparsePoint) -or
        -not [string]::Equals($LinkType, 'Junction', [StringComparison]::OrdinalIgnoreCase)) {
        return $false
    }
    $targetList = @($Targets)
    if ($targetList.Count -ne 1 -or [string]::IsNullOrWhiteSpace([string]$targetList[0])) { return $false }
    try {
        $actualTarget = [IO.Path]::GetFullPath([string]$targetList[0]).TrimEnd('\')
        $expectedTarget = [IO.Path]::GetFullPath($ExpectedCanonicalRoot).TrimEnd('\')
    } catch {
        return $false
    }
    [string]::Equals($actualTarget, $expectedTarget, [StringComparison]::OrdinalIgnoreCase)
}

function Assert-CodexPlusPlusPhysicalPathChain {
    param([Parameter(Mandatory = $true)][string]$Path, [Parameter(Mandatory = $true)][string]$Label, [switch]$RequireContainer)
    $fullPath = [IO.Path]::GetFullPath($Path).TrimEnd('\')
    $pathRoot = [IO.Path]::GetPathRoot($fullPath)
    $current = $pathRoot
    foreach ($part in @($fullPath.Substring($pathRoot.Length).Split('\') | Where-Object { $_ })) {
        $current = Join-Path $current $part
        if (-not (Test-Path -LiteralPath $current)) { throw "Codex++ $Label is missing: $current" }
        $item = Get-Item -LiteralPath $current -Force
        if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) {
            throw "Codex++ $Label contains a reparse point: $current"
        }
    }
    if ($RequireContainer -and -not (Test-Path -LiteralPath $fullPath -PathType Container)) {
        throw "Codex++ $Label is not a directory: $fullPath"
    }
}

function Assert-CodexPlusPlusExistingPathChainPhysical {
    param([Parameter(Mandatory = $true)][string]$Path, [Parameter(Mandatory = $true)][string]$Label)
    $fullPath = [IO.Path]::GetFullPath($Path).TrimEnd('\')
    $pathRoot = [IO.Path]::GetPathRoot($fullPath)
    $current = $pathRoot
    foreach ($part in @($fullPath.Substring($pathRoot.Length).Split('\') | Where-Object { $_ })) {
        $current = Join-Path $current $part
        if (-not (Test-Path -LiteralPath $current)) { return }
        if ((Get-Item -LiteralPath $current -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) {
            throw "Codex++ $Label contains a reparse point: $current"
        }
    }
}

function Assert-CodexPlusPlusProfileAlias {
    param([string]$Reason = 'unspecified')
    # Legacy function name retained for callers; the runtime Profile alias
    # must be absent. Only the physical D: canonical paths are valid.
    if (Test-Path -LiteralPath $profileAliasRoot) {
        throw "Codex++ retired C: profile alias is present during ${Reason}: $profileAliasRoot"
    }
    [void](Assert-CodexPlusPlusPhysicalPathChain -Path $profileCanonicalRoot -Label 'canonical profile root path' -RequireContainer)
    [void](Assert-CodexPlusPlusPhysicalPathChain -Path $canonicalCodexHome -Label 'canonical CODEX_HOME path' -RequireContainer)
}

function Get-CodexPlusPlusProfileAliasStatus {
    param([string]$Reason)
    try {
        Assert-CodexPlusPlusProfileAlias -Reason $Reason
        return [pscustomobject]@{ Valid = $true; Error = $null }
    } catch {
        return [pscustomobject]@{ Valid = $false; Error = $_.Exception.Message }
    }
}

$initialAliasStatus = Get-CodexPlusPlusProfileAliasStatus -Reason 'native_restore_startup_probe'

function Get-RestoreDecision {
    param(
        [bool]$CurrentValueExisted,
        [AllowNull()][string]$CurrentValue,
        [bool]$CapturedPriorExisted,
        [AllowNull()][string]$CapturedPriorValue,
        [string]$ExpectedIsolatedValue
    )
    if ($CurrentValueExisted -and [string]::Equals($CurrentValue, $ExpectedIsolatedValue, [StringComparison]::OrdinalIgnoreCase)) {
        if ($CapturedPriorExisted -and [string]::Equals($CapturedPriorValue, $ExpectedIsolatedValue, [StringComparison]::OrdinalIgnoreCase)) {
            return 'already_prior'
        }
        return $(if ($CapturedPriorExisted) { 'restore_prior' } else { 'remove_isolated' })
    }
    if ($CurrentValueExisted -eq $CapturedPriorExisted) {
        if (-not $CurrentValueExisted -or [string]::Equals($CurrentValue, $CapturedPriorValue, [StringComparison]::OrdinalIgnoreCase)) {
            return 'wait'
        }
    }
    return 'external_writer_conflict'
}

function Read-RegistryDefaultValue {
    $key = [Microsoft.Win32.Registry]::CurrentUser.OpenSubKey($registrySubKey, $false)
    try {
        if (-not $key) { return [pscustomobject]@{ Existed = $false; Value = $null } }
        $existed = @($key.GetValueNames()) -contains ''
        $value = if ($existed) { [string]$key.GetValue('', $null, [Microsoft.Win32.RegistryValueOptions]::DoNotExpandEnvironmentNames) } else { $null }
        [pscustomobject]@{ Existed = $existed; Value = $value }
    } finally { if ($key) { $key.Dispose() } }
}

$priorValue = if ($PriorValueExisted) {
    try { [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($PriorValueBase64)) }
    catch { throw 'Invalid Base64 prior Native Messaging Host value' }
} else { $null }
$priorKindEnum = [Microsoft.Win32.RegistryValueKind]::$PriorValueKind
$deadline = [DateTimeOffset]::Now.AddSeconds($DurationSeconds)
$restoreCount = 0
$conflict = $false
$observations = [Collections.Generic.List[object]]::new()

while ([DateTimeOffset]::Now -lt $deadline) {
    $aliasStatus = Get-CodexPlusPlusProfileAliasStatus -Reason 'native_restore_observation_probe'
    $current = Read-RegistryDefaultValue
    $decision = Get-RestoreDecision -CurrentValueExisted $current.Existed -CurrentValue $current.Value `
        -CapturedPriorExisted ([bool]$PriorValueExisted) -CapturedPriorValue $priorValue `
        -ExpectedIsolatedValue $expectedIsolatedManifest
    [void]$observations.Add([ordered]@{
        at = [DateTimeOffset]::Now.ToString('o')
        decision = $decision
        profile_alias_valid = [bool]$aliasStatus.Valid
        profile_alias_error = $aliasStatus.Error
    })
    if ($decision -eq 'external_writer_conflict') {
        $conflict = $true
        break
    }
    if ($decision -in @('restore_prior', 'remove_isolated')) {
        $key = [Microsoft.Win32.Registry]::CurrentUser.OpenSubKey($registrySubKey, $true)
        try {
            if (-not $key) { throw "Native Messaging Host registry key disappeared during compare-and-set: $registrySubKey" }
            $latestExists = @($key.GetValueNames()) -contains ''
            $latest = if ($latestExists) { [string]$key.GetValue('', $null, [Microsoft.Win32.RegistryValueOptions]::DoNotExpandEnvironmentNames) } else { $null }
            if ($latestExists -and [string]::Equals($latest, $expectedIsolatedManifest, [StringComparison]::OrdinalIgnoreCase)) {
                if ($PriorValueExisted) { $key.SetValue('', $priorValue, $priorKindEnum) }
                else { $key.DeleteValue('', $false) }
                $restoreCount++
            }
        } finally { if ($key) { $key.Dispose() } }
    }
    Start-Sleep -Seconds $IntervalSeconds
}

$final = Read-RegistryDefaultValue
$restored = $final.Existed -eq [bool]$PriorValueExisted -and (
    (-not $final.Existed) -or [string]::Equals($final.Value, $priorValue, [StringComparison]::OrdinalIgnoreCase)
)
$finalAliasStatus = Get-CodexPlusPlusProfileAliasStatus -Reason 'native_restore_final_probe'
$payload = [ordered]@{
    guard = 'codexplusplus_native_messaging_host_compare_and_set_restore'
    checked_at = [DateTimeOffset]::Now.ToString('o')
    expected_isolated_manifest = $expectedIsolatedManifest
    prior_value_existed = [bool]$PriorValueExisted
    restore_count = $restoreCount
    external_writer_conflict = $conflict
    restored_to_captured_prior = $restored
    initial_profile_alias_valid = [bool]$initialAliasStatus.Valid
    initial_profile_alias_error = $initialAliasStatus.Error
    final_profile_alias_valid = [bool]$finalAliasStatus.Valid
    final_profile_alias_error = $finalAliasStatus.Error
    evidence_written = $false
    evidence_write_error = $null
    observations = @($observations)
}
try {
    [void](Assert-CodexPlusPlusPhysicalPathChain -Path $profileCanonicalRoot -Label 'canonical profile root path' -RequireContainer)
    [void](Assert-CodexPlusPlusPhysicalPathChain -Path $canonicalCodexHome -Label 'canonical CODEX_HOME path' -RequireContainer)
    [void](Assert-CodexPlusPlusExistingPathChainPhysical -Path $evidencePath -Label 'native restore evidence path')
    $payload.evidence_written = $true
    [IO.File]::WriteAllText($evidencePath, "$(ConvertTo-Json $payload -Depth 8)`n", $utf8NoBom)
} catch {
    $payload.evidence_written = $false
    $payload.evidence_write_error = $_.Exception.Message
    Write-Warning "Codex++ Native Messaging Host restore evidence could not be written: $($_.Exception.Message)"
}

if ($conflict) {
    Write-Output 'CODEXPP_NATIVE_MESSAGING_HOST_RESTORE_CONFLICT'
    $payload | ConvertTo-Json -Depth 8
    exit 2
}
if (-not $restored) {
    Write-Output 'CODEXPP_NATIVE_MESSAGING_HOST_RESTORE_FAIL'
    $payload | ConvertTo-Json -Depth 8
    exit 1
}
Write-Output 'CODEXPP_NATIVE_MESSAGING_HOST_RESTORE_PASS'
$payload | ConvertTo-Json -Depth 8
