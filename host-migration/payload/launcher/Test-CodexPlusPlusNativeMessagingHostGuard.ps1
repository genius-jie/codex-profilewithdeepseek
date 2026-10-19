#requires -Version 7.0

[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$guardScript = '@@LAUNCHER_ROOT:win@@\Restore-CodexPlusPlusNativeMessagingHost.ps1'
$subKey = 'SOFTWARE\Google\Chrome\NativeMessagingHosts\com.openai.codexextension'
$expected = '@@CODEXPP_PROFILE:win@@\AppData\Local\OpenAI\extension\com.openai.codexextension.json'
$prior = '@@USERPROFILE:win@@\AppData\Local\OpenAI\extension\com.openai.codexextension.json'

function Read-Current {
    $key = [Microsoft.Win32.Registry]::CurrentUser.OpenSubKey($subKey, $false)
    try {
        if (-not $key) { return [pscustomobject]@{ Existed = $false; Value = $null } }
        $exists = @($key.GetValueNames()) -contains ''
        [pscustomobject]@{ Existed = $exists; Value = if ($exists) { [string]$key.GetValue('') } else { $null } }
    } finally { if ($key) { $key.Dispose() } }
}

$before = Read-Current
$tokens = $null
$parseErrors = $null
$ast = [Management.Automation.Language.Parser]::ParseFile($guardScript, [ref]$tokens, [ref]$parseErrors)
if ($parseErrors.Count -gt 0) { throw "Native Messaging Host guard parse failed: $($parseErrors[0].Message)" }
$definition = @($ast.FindAll({
    param($node)
    $node -is [Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq 'Get-RestoreDecision'
}, $true))
if ($definition.Count -ne 1) { throw "Expected one Get-RestoreDecision function, found $($definition.Count)" }
$runner = [scriptblock]::Create("param(`$a,`$b,`$c,`$d,`$e)`n$($definition[0].Extent.Text)`nGet-RestoreDecision -CurrentValueExisted `$a -CurrentValue `$b -CapturedPriorExisted `$c -CapturedPriorValue `$d -ExpectedIsolatedValue `$e")
$cases = @(
    @('wait_on_unchanged_prior', $true, $prior, $true, $prior, 'wait'),
    @('restore_only_isolated_value', $true, $expected, $true, $prior, 'restore_prior'),
    @('remove_isolated_when_prior_absent', $true, $expected, $false, $null, 'remove_isolated'),
    @('wait_when_prior_absent', $false, $null, $false, $null, 'wait'),
    @('do_not_overwrite_external_writer', $true, 'C:\external\owner.json', $true, $prior, 'external_writer_conflict')
)
$checks = foreach ($case in $cases) {
    $actual = [string](& $runner ([bool]$case[1]) $case[2] ([bool]$case[3]) $case[4] $expected)
    [ordered]@{ id = $case[0]; expected = $case[5]; actual = $actual; pass = $actual -eq $case[5] }
}
$after = Read-Current
$registryUnchanged = $before.Existed -eq $after.Existed -and [string]$before.Value -eq [string]$after.Value
$failures = @($checks | Where-Object { -not $_.pass })
if (-not $registryUnchanged) { $failures += [ordered]@{ id = 'probe_is_read_only'; pass = $false } }
$payload = [ordered]@{
    guard = 'codexplusplus_native_messaging_host_guard'
    status = if ($failures.Count -eq 0) { 'pass' } else { 'fail' }
    registry_unchanged = $registryUnchanged
    checks = @($checks)
}
if ($failures.Count -gt 0) {
    Write-Output 'CODEXPP_NATIVE_MESSAGING_HOST_GUARD_FAIL'
    $payload | ConvertTo-Json -Depth 6
    exit 1
}
Write-Output 'CODEXPP_NATIVE_MESSAGING_HOST_GUARD_PASS'
$payload | ConvertTo-Json -Depth 6
