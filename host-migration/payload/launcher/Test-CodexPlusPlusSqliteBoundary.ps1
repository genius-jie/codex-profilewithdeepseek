#requires -Version 7.0

$ErrorActionPreference = 'Stop'

$powerShell7 = '@@POWERSHELL_EXE:win@@'
$configRoot = '@@LAUNCHER_ROOT:win@@'
$profileAliasRoot = '@@USERPROFILE:win@@\AppData\Roaming\CodexPlusPlusProfile'
$profileCanonicalRoot = '@@CODEXPP_PROFILE:win@@'
$canonicalStateDb = '@@CODEXPP_HOME:win@@\state_5.sqlite'
$aliasStateDb = '@@USERPROFILE:win@@\AppData\Roaming\CodexPlusPlusProfile\AppData\Roaming\Codex\.codex\state_5.sqlite'
$ordinaryStateDb = '@@CODEX_HOME:win@@\state_5.sqlite'
$wrongCanonicalDb = '@@CODEXPP_HOME:win@@\sqlite-boundary-negative.sqlite'
$sqlitePython = '@@CODEXPP_PROFILE:win@@\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$sqliteHelper = Join-Path $configRoot 'Invoke-CodexPlusPlusSqlite.py'
$watcher = Join-Path $configRoot 'Watch-CodexPlusPlusSessionPaths.ps1'
$sessionTest = Join-Path $configRoot 'Test-CodexPlusPlusSessionPaths.ps1'
$profileAliasGuard = Join-Path $configRoot 'Test-CodexPlusPlusProfileAliasBoundary.ps1'
$evidencePath = '@@CODEXPP_HOME:win@@\sqlite-boundary-guard.json'

$checks = [System.Collections.Generic.List[object]]::new()
$failures = [System.Collections.Generic.List[string]]::new()

function Add-Check {
    param(
        [string]$Name,
        [bool]$Passed,
        [object]$Evidence
    )
    [void]$checks.Add([ordered]@{ name = $Name; passed = $Passed; evidence = $Evidence })
    if (-not $Passed) { [void]$failures.Add($Name) }
}

function Get-Sha256 {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { return $null }
    $stream = [IO.File]::OpenRead($Path)
    try {
        $sha = [Security.Cryptography.SHA256]::Create()
        try { return ([BitConverter]::ToString($sha.ComputeHash($stream))).Replace('-', '').ToLowerInvariant() }
        finally { $sha.Dispose() }
    } finally {
        $stream.Dispose()
    }
}

function Assert-PhysicalPathChain {
    param([string]$Path)
    $full = [IO.Path]::GetFullPath($Path)
    $root = [IO.Path]::GetPathRoot($full)
    $current = $root.TrimEnd('\')
    foreach ($part in $full.Substring($root.Length).Split(@('\'), [StringSplitOptions]::RemoveEmptyEntries)) {
        $current = if ($current) { $current + '\' + $part } else { $root + $part }
        if (-not (Test-Path -LiteralPath $current)) { throw "Required physical path component missing: $current" }
        $item = Get-Item -LiteralPath $current -Force
        if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) {
            throw "Required physical path component is a reparse point: $current"
        }
    }
}

function Invoke-NativeCommand {
    param(
        [string]$FilePath,
        [string[]]$Arguments
    )
    $priorPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        $output = @(& $FilePath @Arguments 2>&1 | ForEach-Object { [string]$_ })
        $exitCode = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $priorPreference
    }
    [pscustomobject]@{ ExitCode = $exitCode; Output = ($output -join "`n") }
}

function Invoke-SqliteHelper {
    param(
        [string]$Database,
        [string]$Sql,
        [int]$TimeoutMs = 2000
    )
    $sqlBase64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($Sql))
    Invoke-NativeCommand -FilePath $sqlitePython -Arguments @(
        $sqliteHelper,
        '--database', $Database,
        '--timeout-ms', [string]$TimeoutMs,
        '--sql-base64', $sqlBase64
    )
}

function Write-AtomicJson {
    param(
        [string]$Path,
        [object]$Value
    )
    $directory = Split-Path -Parent $Path
    if (-not (Test-Path -LiteralPath $directory -PathType Container)) {
        throw "Evidence directory missing: $directory"
    }
    $temporary = Join-Path $directory ('.sqlite-boundary-guard.' + [Guid]::NewGuid().ToString('N') + '.tmp')
    $backup = Join-Path $directory ('.sqlite-boundary-guard.' + [Guid]::NewGuid().ToString('N') + '.bak')
    try {
        [IO.File]::WriteAllText($temporary, (($Value | ConvertTo-Json -Depth 8) + "`n"), [Text.UTF8Encoding]::new($false))
        if (Test-Path -LiteralPath $Path -PathType Leaf) {
            [IO.File]::Replace($temporary, $Path, $backup)
            [IO.File]::Delete($backup)
        } else {
            [IO.File]::Move($temporary, $Path)
        }
    } finally {
        if (Test-Path -LiteralPath $temporary -PathType Leaf) { [IO.File]::Delete($temporary) }
        if (Test-Path -LiteralPath $backup -PathType Leaf) { [IO.File]::Delete($backup) }
    }
}

$ordinaryConfig = '@@CODEX_HOME:win@@\config.toml'
$ordinaryConfigHashBefore = Get-Sha256 $ordinaryConfig

foreach ($requiredFile in @($powerShell7, $canonicalStateDb, $sqlitePython, $sqliteHelper, $watcher, $sessionTest, $profileAliasGuard)) {
    Add-Check -Name ('required_file_' + [IO.Path]::GetFileName($requiredFile)) -Passed (Test-Path -LiteralPath $requiredFile -PathType Leaf) -Evidence $requiredFile
}

try {
    Assert-PhysicalPathChain -Path $sqlitePython
    Assert-PhysicalPathChain -Path $sqliteHelper
    Add-Check -Name 'fixed_dependencies_have_physical_path_chains' -Passed $true -Evidence @($sqlitePython, $sqliteHelper)
} catch {
    Add-Check -Name 'fixed_dependencies_have_physical_path_chains' -Passed $false -Evidence $_.Exception.Message
}

$aliasProbe = Invoke-NativeCommand -FilePath $powerShell7 -Arguments @('-NoLogo', '-NoProfile', '-File', $profileAliasGuard)
Add-Check -Name 'profile_alias_guard_passes' -Passed ($aliasProbe.ExitCode -eq 0 -and $aliasProbe.Output.Contains('CODEXPP_PROFILE_ALIAS_BOUNDARY_GUARD_PASS')) -Evidence @{ exit_code = $aliasProbe.ExitCode; marker_present = $aliasProbe.Output.Contains('CODEXPP_PROFILE_ALIAS_BOUNDARY_GUARD_PASS') }
Add-Check -Name 'legacy_profile_alias_is_absent' -Passed (-not (Test-Path -LiteralPath $profileAliasRoot)) -Evidence $profileAliasRoot

$selfTest = Invoke-NativeCommand -FilePath $sqlitePython -Arguments @($sqliteHelper, '--self-test')
Add-Check -Name 'fixed_helper_self_test_passes' -Passed ($selfTest.ExitCode -eq 0 -and $selfTest.Output.Contains('CODEXPP_SQLITE_HELPER_SELF_TEST_PASS')) -Evidence $selfTest.Output

$canonicalProbe = Invoke-SqliteHelper -Database $canonicalStateDb -Sql "SELECT 'canonical_state_query_ok';"
Add-Check -Name 'canonical_state_db_is_readable' -Passed ($canonicalProbe.ExitCode -eq 0 -and $canonicalProbe.Output.Trim() -eq 'canonical_state_query_ok') -Evidence $canonicalProbe.Output

$aliasProbeSql = Invoke-SqliteHelper -Database $aliasStateDb -Sql "SELECT 'alias_resolves_to_canonical_ok';"
Add-Check -Name 'retired_alias_is_rejected_before_open' -Passed ($aliasProbeSql.ExitCode -ne 0) -Evidence $aliasProbeSql.Output

$ordinaryProbe = Invoke-SqliteHelper -Database $ordinaryStateDb -Sql "SELECT 'must_not_run';"
$ordinaryRejected = $ordinaryProbe.ExitCode -ne 0 -and $ordinaryProbe.Output.Contains('refusing sqlite database outside fixed Codex++ state DB')
Add-Check -Name 'ordinary_codex_state_db_is_rejected_before_open' -Passed $ordinaryRejected -Evidence $ordinaryProbe.Output

$wrongCanonicalProbe = Invoke-SqliteHelper -Database $wrongCanonicalDb -Sql "SELECT 'must_not_run';"
$wrongCanonicalRejected = $wrongCanonicalProbe.ExitCode -ne 0 -and $wrongCanonicalProbe.Output.Contains('refusing sqlite database outside fixed Codex++ state DB')
Add-Check -Name 'other_profile_database_is_rejected_before_open' -Passed $wrongCanonicalRejected -Evidence $wrongCanonicalProbe.Output
Add-Check -Name 'negative_database_was_not_created' -Passed (-not (Test-Path -LiteralPath $wrongCanonicalDb)) -Evidence $wrongCanonicalDb

$helperText = if (Test-Path -LiteralPath $sqliteHelper -PathType Leaf) { [IO.File]::ReadAllText($sqliteHelper, [Text.Encoding]::UTF8) } else { '' }
$helperTokens = @(
    '@@CODEXPP_HOME:win@@\state_5.sqlite',
    'os.path.realpath',
    'base64.b64decode(args.sql_base64, validate=True)',
    'if not 1 <= args.timeout_ms <= 60000',
    'CODEXPP_SQLITE_HELPER_SELF_TEST_PASS',
    'refusing sqlite database outside fixed Codex++ state DB'
)
for ($helperTokenIndex = 0; $helperTokenIndex -lt $helperTokens.Count; $helperTokenIndex++) {
    $token = $helperTokens[$helperTokenIndex]
    Add-Check -Name ('helper_contract_' + ($helperTokenIndex + 1)) -Passed $helperText.Contains($token) -Evidence $token
}

foreach ($consumer in @($watcher, $sessionTest)) {
    $consumerText = if (Test-Path -LiteralPath $consumer -PathType Leaf) { [IO.File]::ReadAllText($consumer, [Text.Encoding]::UTF8) } else { '' }
    $fixedTokens = @($sqlitePython, $sqliteHelper, 'CODEXPP_SQLITE_HELPER_SELF_TEST_PASS', '--sql-base64')
    for ($fixedTokenIndex = 0; $fixedTokenIndex -lt $fixedTokens.Count; $fixedTokenIndex++) {
        $token = $fixedTokens[$fixedTokenIndex]
        Add-Check -Name (([IO.Path]::GetFileNameWithoutExtension($consumer)) + '_fixed_sqlite_' + ($fixedTokenIndex + 1)) -Passed $consumerText.Contains($token) -Evidence $token
    }
    $pathResolvedSqlite = $consumerText -match '(?im)\$sqlite\s*=\s*["'']sqlite3["'']|Get-Command\s+sqlite3|&\s*["'']?sqlite3(?:\.exe)?["'']?'
    Add-Check -Name (([IO.Path]::GetFileNameWithoutExtension($consumer)) + '_has_no_path_resolved_sqlite3') -Passed (-not $pathResolvedSqlite) -Evidence $pathResolvedSqlite
}

$ordinaryConfigHashAfter = Get-Sha256 $ordinaryConfig
Add-Check -Name 'ordinary_codex_config_untouched' -Passed ($ordinaryConfigHashBefore -eq $ordinaryConfigHashAfter) -Evidence @{ before = $ordinaryConfigHashBefore; after = $ordinaryConfigHashAfter }

$report = [ordered]@{
    schema = 'codexplusplus-sqlite-boundary-guard.v1'
    generated_at = [DateTimeOffset]::UtcNow.ToString('yyyy-MM-ddTHH:mm:ss.fffZ')
    status = if ($failures.Count -eq 0) { 'pass' } else { 'fail' }
    canonical_database = $canonicalStateDb
    alias_database = $aliasStateDb
    sqlite_python = $sqlitePython
    sqlite_helper = $sqliteHelper
    checks = @($checks)
    failures = @($failures)
}

Write-AtomicJson -Path $evidencePath -Value $report
if ($failures.Count -gt 0) {
    'CODEXPP_SQLITE_BOUNDARY_GUARD_FAIL'
    $report | ConvertTo-Json -Depth 8
    exit 1
}
'CODEXPP_SQLITE_BOUNDARY_GUARD_PASS'
$report | ConvertTo-Json -Depth 8
