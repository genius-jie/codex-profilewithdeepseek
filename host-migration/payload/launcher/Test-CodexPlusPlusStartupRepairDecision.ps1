#requires -Version 7.0

[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$start = '@@LAUNCHER_ROOT:win@@\Start-CodexPlusPlus.ps1'
$tokens = $null
$errors = $null
$ast = [Management.Automation.Language.Parser]::ParseFile($start, [ref]$tokens, [ref]$errors)
if (@($errors).Count -ne 0) {
    throw "Start-CodexPlusPlus.ps1 parser errors: $(@($errors | ForEach-Object Message) -join '; ')"
}

$functions = @($ast.FindAll({
    param($node)
    $node -is [Management.Automation.Language.FunctionDefinitionAst] -and
        $node.Name -eq 'Get-CodexPlusPlusRepairReason'
}, $true))
if ($functions.Count -ne 1) {
    throw "Expected one Get-CodexPlusPlusRepairReason function, found $($functions.Count)."
}
. ([scriptblock]::Create($functions[0].Extent.Text))

$cases = @(
    @{ id = 'explicit_skip_wins'; args = @{ RepairDisabled = $true; ForceRequested = $true; StoreAppPresent = $false; InjectionPreflightExitCode = $null }; expected = $null },
    @{ id = 'force_requests_one_repair'; args = @{ RepairDisabled = $false; ForceRequested = $true; StoreAppPresent = $true; InjectionPreflightExitCode = $null }; expected = 'force_repair_requested' },
    @{ id = 'missing_current_store_requests_repair'; args = @{ RepairDisabled = $false; ForceRequested = $false; StoreAppPresent = $false; InjectionPreflightExitCode = $null }; expected = 'current_official_store_app_missing' },
    @{ id = 'healthy_restart_skips_full_repair'; args = @{ RepairDisabled = $false; ForceRequested = $false; StoreAppPresent = $true; InjectionPreflightExitCode = 0 }; expected = $null },
    @{ id = 'injection_drift_requests_repair'; args = @{ RepairDisabled = $false; ForceRequested = $false; StoreAppPresent = $true; InjectionPreflightExitCode = 1 }; expected = 'loader_or_tweak_injection_drift' }
)
$results = foreach ($case in $cases) {
    $caseArguments = $case.args
    $actual = Get-CodexPlusPlusRepairReason @caseArguments
    [pscustomobject]@{
        id = $case.id
        pass = [string]::Equals([string]$actual, [string]$case.expected, [StringComparison]::Ordinal)
        expected = $case.expected
        actual = $actual
    }
}

$startText = [IO.File]::ReadAllText($start)
$staticChecks = @(
    [pscustomobject]@{ id = 'no_unconditional_repair_assignment'; pass = -not [regex]::IsMatch($startText, '(?m)^\s*\$shouldRepair\s*=\s*-not\s+\$SkipRepair\s*$') },
    [pscustomobject]@{ id = 'decision_drives_repair_branch'; pass = $startText.Contains('$repairReason = Get-CodexPlusPlusRepairReason') -and $startText.Contains('$shouldRepair = -not $SkipRepair -and -not [string]::IsNullOrWhiteSpace($repairReason)') }
)
$all = @($results) + @($staticChecks)
$failures = @($all | Where-Object { -not $_.pass })
$payload = [ordered]@{
    guard = 'codexplusplus_startup_repair_decision'
    status = if ($failures.Count -eq 0) { 'pass' } else { 'fail' }
    results = $all
}
if ($failures.Count -gt 0) {
    'CODEXPP_STARTUP_REPAIR_DECISION_FAIL'
    $payload | ConvertTo-Json -Depth 6
    exit 1
}
'CODEXPP_STARTUP_REPAIR_DECISION_PASS'
$payload | ConvertTo-Json -Depth 6
exit 0
