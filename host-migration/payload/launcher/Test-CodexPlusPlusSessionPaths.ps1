#requires -Version 7.0

$ErrorActionPreference = "Stop"

$codexHome = "@@CODEXPP_HOME:win@@"
$stateDb = Join-Path $codexHome "state_5.sqlite"
$watcher = "@@LAUNCHER_ROOT:win@@\Watch-CodexPlusPlusSessionPaths.ps1"
$codexPlusPlusRuntimeConfig = "@@CODEXPP_RUNTIME:win@@\config.json"
$sessionPathNormalizerIndex = "@@CODEXPP_RUNTIME:win@@\tweaks\co.Arconte112.session-path-normalizer\index.js"
$profileAliasRoot = [IO.Path]::GetFullPath('@@USERPROFILE:win@@\AppData\Roaming\CodexPlusPlusProfile').TrimEnd('\')
$profileCanonicalRoot = [IO.Path]::GetFullPath('@@CODEXPP_PROFILE:win@@').TrimEnd('\')
$canonicalCodexHome = Join-Path $profileCanonicalRoot 'AppData\Roaming\Codex\.codex'
function Convert-TestProfilePathToCanonical([string]$Path) {
    $full = [IO.Path]::GetFullPath(([string]$Path).Replace('\\?\', '')).TrimEnd('\')
    if ([string]::Equals($full, $profileAliasRoot, [StringComparison]::OrdinalIgnoreCase)) { return $profileCanonicalRoot }
    if ($full.StartsWith(($profileAliasRoot + '\'), [StringComparison]::OrdinalIgnoreCase)) {
        $suffix = $full.Substring($profileAliasRoot.Length)
        if ($suffix -ieq '\.codex' -or $suffix -like '\.codex\*') {
            return Join-Path $canonicalCodexHome $suffix.Substring(7).TrimStart('\')
        }
        return $profileCanonicalRoot + $suffix
    }
    $full
}
$sqlitePython = '@@CODEXPP_PROFILE:win@@\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$sqliteHelper = '@@LAUNCHER_ROOT:win@@\Invoke-CodexPlusPlusSqlite.py'
foreach ($dependency in @($sqlitePython, $sqliteHelper)) {
    if (-not (Test-Path -LiteralPath $dependency -PathType Leaf)) {
        throw "Codex++ fixed sqlite dependency missing: $dependency"
    }
}
$sqliteSelfTest = @(& $sqlitePython $sqliteHelper --self-test 2>&1)
if ($LASTEXITCODE -ne 0 -or ($sqliteSelfTest -join "`n") -notmatch 'CODEXPP_SQLITE_HELPER_SELF_TEST_PASS') {
    throw "Codex++ fixed sqlite helper self-test failed: $($sqliteSelfTest -join ' ')"
}
$sqlite = {
    $sqliteArguments = @($args)
    $timeoutMs = 2000
    $offset = 0
    if ($sqliteArguments.Count -ge 2 -and [string]$sqliteArguments[0] -eq '-cmd') {
        if ([string]$sqliteArguments[1] -notmatch '^\.timeout\s+([0-9]{1,5})$') { throw "Unsupported Codex++ sqlite shell command" }
        $timeoutMs = [int]$Matches[1]
        $offset = 2
    }
    if (($sqliteArguments.Count - $offset) -ne 2) { throw "Codex++ sqlite wrapper requires exact database and SQL arguments" }
    $database = [string]$sqliteArguments[$offset]
    $sqlText = [string]$sqliteArguments[$offset + 1]
    $sqlBase64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($sqlText))
    $sqliteOutput = @(& $sqlitePython $sqliteHelper --database $database --timeout-ms $timeoutMs --sql-base64 $sqlBase64 2>&1)
    if ($LASTEXITCODE -ne 0) { throw "Codex++ sqlite helper failed: $($sqliteOutput -join ' ')" }
    $sqliteOutput
}
$quarantineRoot = Join-Path $canonicalCodexHome "test_quarantined_sessions"
$summaryRoot = Join-Path $quarantineRoot "summaries"
$lifecycleIndex = Join-Path $quarantineRoot "lifecycle_index.jsonl"
$testLock = Join-Path $canonicalCodexHome "session-lifecycle-test.lock"

if (-not (Test-Path -LiteralPath $stateDb)) {
    throw "Codex++ state database not found: $stateDb"
}

if (-not (Test-Path -LiteralPath $watcher)) {
    throw "Session path watcher not found: $watcher"
}

if (-not (Test-Path -LiteralPath $codexPlusPlusRuntimeConfig)) {
    throw "Codex++ runtime tweak config not found: $codexPlusPlusRuntimeConfig"
}

if (-not (Test-Path -LiteralPath $sessionPathNormalizerIndex)) {
    throw "Session path normalizer main tweak not found: $sessionPathNormalizerIndex"
}

$tweakConfig = Get-Content -LiteralPath $codexPlusPlusRuntimeConfig -Raw | ConvertFrom-Json
$normalizerEnabled = [bool]$tweakConfig.tweaks.'co.Arconte112.session-path-normalizer'.enabled
$followupEnabled = [bool]$tweakConfig.tweaks.'co.Arconte112.followup'.enabled
$autoFollowupEnabled = [bool]$tweakConfig.tweaks.'com.lobster.auto-follow-up'.enabled
if (-not $normalizerEnabled) {
    throw "Session path normalizer tweak must be enabled before Watch can defer rollout_path ownership"
}
if (-not $followupEnabled -or -not $autoFollowupEnabled) {
    throw "Follow-up surfaces must stay enabled: followup=$followupEnabled auto_followup=$autoFollowupEnabled"
}

$watcherText = Get-Content -LiteralPath $watcher -Raw
$normalizerIndexText = Get-Content -LiteralPath $sessionPathNormalizerIndex -Raw
if ($watcherText -match "CREATE TRIGGER IF NOT EXISTS codexpp_normalize_thread_rollout_path" -or
    $watcherText -match "DROP TRIGGER IF EXISTS codexpp_normalize_thread_rollout_path" -or
    $watcherText -match "Test-RolloutPathStripTriggersPresent") {
    throw "Watch must not own rollout_path trigger creation or repair"
}
if ($normalizerIndexText -notmatch "function ensureNormalizationTriggers" -or
    $normalizerIndexText -notmatch "DROP TRIGGER IF EXISTS codexpp_normalize_thread_rollout_path_ai" -or
    $normalizerIndexText -notmatch "DROP TRIGGER IF EXISTS codexpp_normalize_thread_rollout_path_au" -or
    $normalizerIndexText -notmatch "function shouldReplaceNormalizationTriggers" -or
    $normalizerIndexText -notmatch "substr\(NEW\.rollout_path, 5\)") {
    throw "Session path normalizer main tweak must own rollout_path trigger replacement"
}

function Assert-RendererSafeSessionMeta {
    param(
        [string]$Path,
        [string]$ExpectedId
    )

    $firstLine = Get-Content -LiteralPath $Path -TotalCount 1
    $first = $firstLine | ConvertFrom-Json
    if ($first.type -ne "session_meta") {
        throw "Renderer-safe metadata canary failed: first item is $($first.type)"
    }

    $payload = $first.payload
    foreach ($name in @("id", "timestamp", "cwd", "originator", "cli_version", "source", "thread_source", "model_provider", "base_instructions", "dynamic_tools")) {
        if (-not ($payload.PSObject.Properties.Name -contains $name)) {
            throw "Renderer-safe metadata canary failed: missing $name"
        }
    }
    if ($payload.id -ne $ExpectedId -or $payload.source -ne "vscode" -or $payload.thread_source -ne "user" -or $payload.model_provider -ne "cm") {
        throw "Renderer-safe metadata canary failed: id=$($payload.id) source=$($payload.source) thread_source=$($payload.thread_source) provider=$($payload.model_provider)"
    }
    if ([string]::IsNullOrWhiteSpace([string]$payload.base_instructions.text)) {
        throw "Renderer-safe metadata canary failed: base instructions are empty"
    }
}

function Assert-LifecycleColdStorage {
    param(
        [string]$ThreadId,
        [string]$StubPath,
        [string]$ExpectedReason,
        [int64]$MaxStubBytes
    )

    $stubItem = Get-Item -LiteralPath $StubPath
    $quarantine = @(Get-ChildItem -LiteralPath $quarantineRoot -Filter "*$ThreadId.jsonl" -File -ErrorAction SilentlyContinue | Sort-Object LastWriteTime)
    $summary = @(Get-ChildItem -LiteralPath $summaryRoot -Filter "*$ThreadId.summary.json" -File -ErrorAction SilentlyContinue | Sort-Object LastWriteTime)
    if ($stubItem.Length -ge $MaxStubBytes -or $quarantine.Count -lt 1 -or $summary.Count -lt 1) {
        throw "Lifecycle cold-storage canary failed: thread=$ThreadId length=$($stubItem.Length) quarantine_count=$($quarantine.Count) summary_count=$($summary.Count)"
    }

    $latestSummary = $summary[-1]
    $summaryJson = Get-Content -LiteralPath $latestSummary.FullName -Raw | ConvertFrom-Json
    if ($summaryJson.schema -ne "codexpp_session_lifecycle.v1" -or $summaryJson.lifecycle_tier -ne "cold" -or $summaryJson.reason -ne $ExpectedReason -or $summaryJson.restore.mode -ne "on_demand") {
        throw "Lifecycle summary canary failed: thread=$ThreadId schema=$($summaryJson.schema) tier=$($summaryJson.lifecycle_tier) reason=$($summaryJson.reason) restore=$($summaryJson.restore.mode)"
    }
    if ([string]$summaryJson.restore.command -notmatch "Read-CodexPlusPlusColdSession.ps1" -or [string]$summaryJson.restore.command -notmatch [regex]::Escape($ThreadId)) {
        throw "Lifecycle restore command canary failed: thread=$ThreadId command=$($summaryJson.restore.command)"
    }

    $stubText = ((Get-Content -LiteralPath $StubPath) | ForEach-Object {
        try {
            $stubLine = $_ | ConvertFrom-Json
            if ($stubLine.payload.message) { [string]$stubLine.payload.message }
            foreach ($content in @($stubLine.payload.content)) {
                if ($content.text) { [string]$content.text }
            }
        } catch {
            [string]$_
        }
    }) -join "`n"
    $canonicalSummaryPath = Convert-TestProfilePathToCanonical $latestSummary.FullName
    $hasSummaryReference = $stubText.Contains($canonicalSummaryPath)
    if (-not $stubText.Contains("cold storage") -or -not $hasSummaryReference -or -not $stubText.Contains("Read-CodexPlusPlusColdSession.ps1")) {
        throw "Lifecycle stub canary failed: thread=$ThreadId summary=$($latestSummary.FullName)"
    }
    Assert-RendererSafeSessionMeta -Path $StubPath -ExpectedId $ThreadId

    if (-not (Test-Path -LiteralPath $lifecycleIndex)) {
        throw "Lifecycle index missing: $lifecycleIndex"
    }
    $indexMatches = @(Select-String -LiteralPath $lifecycleIndex -Pattern $ThreadId -SimpleMatch -ErrorAction SilentlyContinue)
    if ($indexMatches.Count -lt 1) {
        throw "Lifecycle index canary failed: thread=$ThreadId not indexed"
    }
    $latestIndex = $indexMatches[-1].Line | ConvertFrom-Json
    $actualSummaryPath = Convert-TestProfilePathToCanonical ([string]$latestIndex.summary_path)
    $expectedSummaryPath = Convert-TestProfilePathToCanonical $latestSummary.FullName
    if (-not [string]::Equals($actualSummaryPath, $expectedSummaryPath, [StringComparison]::OrdinalIgnoreCase) -or $latestIndex.lifecycle_tier -ne "cold" -or $latestIndex.reason -ne $ExpectedReason -or $latestIndex.restore_mode -ne "on_demand") {
        throw "Lifecycle index canary failed: thread=$ThreadId summary_path=$($latestIndex.summary_path) tier=$($latestIndex.lifecycle_tier) reason=$($latestIndex.reason) restore=$($latestIndex.restore_mode)"
    }

    return [pscustomobject]@{
        Quarantine = $quarantine
        Summary = $summary
    }
}

function Assert-ActiveSessionRiskRecorded {
    param(
        [string]$ThreadId,
        [string]$OriginalPath,
        [string]$ExpectedTier,
        [string]$ExpectedReason
    )

    $riskLog = Join-Path $quarantineRoot "active_session_risks.jsonl"
    if (-not (Test-Path -LiteralPath $riskLog)) {
        throw "Active session risk log missing: $riskLog"
    }
    $riskMatches = @(Select-String -LiteralPath $riskLog -Pattern $ThreadId -SimpleMatch -ErrorAction SilentlyContinue)
    if ($riskMatches.Count -lt 1) {
        throw "Active session risk canary failed: thread=$ThreadId not recorded"
    }
    $latestRisk = $riskMatches[-1].Line | ConvertFrom-Json
    $actualRiskPath = Convert-TestProfilePathToCanonical ([string]$latestRisk.original_path)
    $expectedRiskPath = Convert-TestProfilePathToCanonical ([string]$OriginalPath)
    if (-not [string]::Equals($actualRiskPath, $expectedRiskPath, [StringComparison]::OrdinalIgnoreCase) -or $latestRisk.lifecycle_tier -ne $ExpectedTier -or $latestRisk.reason -ne $ExpectedReason -or $latestRisk.action -ne "record_only" -or $latestRisk.protected -ne $true) {
        throw "Active session risk canary failed: thread=$ThreadId path=$($latestRisk.original_path) tier=$($latestRisk.lifecycle_tier) reason=$($latestRisk.reason) action=$($latestRisk.action) protected=$($latestRisk.protected)"
    }
    if (-not (Test-Path -LiteralPath $lifecycleIndex)) {
        throw "Lifecycle index missing: $lifecycleIndex"
    }
    $indexMatches = @(Select-String -LiteralPath $lifecycleIndex -Pattern $ThreadId -SimpleMatch -ErrorAction SilentlyContinue)
    if ($indexMatches.Count -lt 1) {
        throw "Active session risk index canary failed: thread=$ThreadId not indexed"
    }
}

$cleanupProbeIds = @(
    '00000000-0000-4000-8000-000000000001',
    '00000000-0000-4000-8000-000000000002',
    '00000000-0000-4000-8000-000000000003',
    '00000000-0000-4000-8000-000000000004',
    '00000000-0000-4000-8000-000000000005',
    '00000000-0000-4000-8000-000000000006',
    '00000000-0000-4000-8000-000000000007'
)
$cleanupProbeFiles = @(
    '@@CODEXPP_HOME:win@@\sessions\2099\01\01\rollout-future-completed-idle-00000000-0000-4000-8000-000000000007.jsonl',
    '@@CODEXPP_HOME:win@@\sessions\2099\01\01\rollout-future-insert-00000000-0000-4000-8000-000000000001.jsonl',
    '@@CODEXPP_HOME:win@@\sessions\2099\01\01\rollout-future-update-00000000-0000-4000-8000-000000000001.jsonl',
    '@@CODEXPP_HOME:win@@\sessions\2099\01\01\rollout-future-safe-00000000-0000-4000-8000-000000000006.jsonl',
    '@@CODEXPP_HOME:win@@\sessions\2099\01\01\rollout-future-body-00000000-0000-4000-8000-000000000002.jsonl',
    '@@CODEXPP_HOME:win@@\sessions\2099\01\01\rollout-future-abort-00000000-0000-4000-8000-000000000003.jsonl',
    '@@CODEXPP_HOME:win@@\sessions\2099\01\01\rollout-future-stale-00000000-0000-4000-8000-000000000004.jsonl',
    '@@CODEXPP_HOME:win@@\archived_sessions\rollout-future-archived-00000000-0000-4000-8000-000000000005.jsonl'
)
$canonicalTestQuarantineRoot = Convert-TestProfilePathToCanonical $quarantineRoot
$expectedTestQuarantineRoot = '@@CODEXPP_HOME:win@@\test_quarantined_sessions'
$canonicalTestLock = Convert-TestProfilePathToCanonical $testLock
$expectedTestLock = '@@CODEXPP_HOME:win@@\session-lifecycle-test.lock'
if (-not [string]::Equals($canonicalTestQuarantineRoot, $expectedTestQuarantineRoot, [StringComparison]::OrdinalIgnoreCase)) {
    throw "Refusing cleanup outside exact Codex++ lifecycle test quarantine root: $canonicalTestQuarantineRoot"
}
if (-not [string]::Equals($canonicalTestLock, $expectedTestLock, [StringComparison]::OrdinalIgnoreCase)) {
    throw "Refusing cleanup outside exact Codex++ lifecycle test lock: $canonicalTestLock"
}

$testFailure = $null
$cleanupFailures = [System.Collections.Generic.List[string]]::new()
try {
& $watcher

$metadataTriggerCanarySql = @"
PRAGMA busy_timeout = 2000;
DROP TRIGGER IF EXISTS codexpp_normalize_thread_cwd_ai;
DROP TRIGGER IF EXISTS codexpp_normalize_thread_cwd_au;
DROP TRIGGER IF EXISTS codexpp_normalize_thread_title_ai;
DROP TRIGGER IF EXISTS codexpp_normalize_thread_title_au;
DROP TRIGGER IF EXISTS codexpp_normalize_thread_preview_ai;
DROP TRIGGER IF EXISTS codexpp_normalize_thread_preview_au;
DROP TRIGGER IF EXISTS codexpp_fill_blank_thread_title_ai;
DROP TRIGGER IF EXISTS codexpp_fill_blank_thread_title_au;
"@
& $sqlite $stateDb $metadataTriggerCanarySql | Out-Null
& $watcher
$metadataTriggerCheckSql = @"
SELECT
  CASE
    WHEN COUNT(*) = 8 THEN 'watch_metadata_triggers_restored_ok'
    ELSE 'watch_metadata_triggers_restored_bad:' || COUNT(*)
  END
FROM sqlite_master
WHERE type = 'trigger'
  AND name IN (
    'codexpp_normalize_thread_cwd_ai',
    'codexpp_normalize_thread_cwd_au',
    'codexpp_normalize_thread_title_ai',
    'codexpp_normalize_thread_title_au',
    'codexpp_normalize_thread_preview_ai',
    'codexpp_normalize_thread_preview_au',
    'codexpp_fill_blank_thread_title_ai',
    'codexpp_fill_blank_thread_title_au'
  );
"@
$metadataTriggerCheck = (& $sqlite $stateDb $metadataTriggerCheckSql) -join "`n"
if ($metadataTriggerCheck -notmatch "watch_metadata_triggers_restored_ok") {
    throw "Watch metadata trigger ownership verification failed:`n$metadataTriggerCheck"
}

$completedIdleProbeId = "00000000-0000-4000-8000-000000000007"
$completedIdleProbeDir = "@@CODEXPP_HOME:win@@\sessions\2099\01\01"
$completedIdleProbePath = Join-Path $completedIdleProbeDir "rollout-future-completed-idle-$completedIdleProbeId.jsonl"
New-Item -ItemType Directory -Path $completedIdleProbeDir -Force | Out-Null
$completedIdleLine = [string]::new([char]'c', 2100000)
$completedIdleLines = @(
    ('{"timestamp":"2099-01-01T00:00:00.000Z","type":"session_meta","payload":{"id":"' + $completedIdleProbeId + '","source":"test"}}'),
    ('{"timestamp":"2099-01-01T00:00:01.000Z","type":"event_msg","payload":{"type":"agent_message","message":"' + $completedIdleLine + '"}}'),
    '{"timestamp":"2099-01-01T00:00:02.000Z","type":"event_msg","payload":{"type":"task_complete","turn_id":"probe","completed_at":4070908800}}'
)
[System.IO.File]::WriteAllLines($completedIdleProbePath, [string[]]$completedIdleLines, (New-Object System.Text.UTF8Encoding $false))
(Get-Item -LiteralPath $completedIdleProbePath).LastWriteTime = (Get-Date).AddSeconds(-15)
$completedIdleSql = @"
PRAGMA busy_timeout = 2000;
DELETE FROM threads WHERE id = '$completedIdleProbeId';
INSERT INTO threads (
  id, rollout_path, created_at, updated_at, source, model_provider,
  cwd, title, sandbox_policy, approval_mode, tokens_used, archived, preview
) VALUES (
  '$completedIdleProbeId',
  '$completedIdleProbePath',
  4070908800,
  4070908800,
  'vscode',
  'cm',
  '@@LAUNCHER_ROOT:win@@',
  'codexpp completed idle sanitizer probe',
  'dangerFullAccess',
  'never',
  9000007,
  0,
  'codexpp completed idle sanitizer probe'
);
"@
& $sqlite $stateDb $completedIdleSql | Out-Null
Remove-Item -LiteralPath $quarantineRoot -Recurse -Force -ErrorAction SilentlyContinue
& $watcher -QuarantineRootOverride $quarantineRoot
$completedIdleItem = Get-Item -LiteralPath $completedIdleProbePath
$completedIdleArchived = & $sqlite $stateDb "SELECT archived FROM threads WHERE id = '$completedIdleProbeId';"
$completedIdleQuarantine = @(Get-ChildItem -LiteralPath $quarantineRoot -Filter "*$completedIdleProbeId.jsonl" -File -ErrorAction SilentlyContinue)
Assert-ActiveSessionRiskRecorded -ThreadId $completedIdleProbeId -OriginalPath $completedIdleProbePath -ExpectedTier "active_unarchived_recent" -ExpectedReason "terminal_oversized_transcript_record_only"
$completedIdleRiskLog = Join-Path $quarantineRoot "active_session_risks.jsonl"
$completedIdleRiskCountBefore = @(Select-String -LiteralPath $completedIdleRiskLog -Pattern $completedIdleProbeId -SimpleMatch -ErrorAction SilentlyContinue).Count
[System.IO.File]::AppendAllText($completedIdleProbePath, "`n" + '{"timestamp":"2099-01-01T00:00:03.000Z","type":"event_msg","payload":{"type":"agent_message","message":"risk throttle growth probe"}}', (New-Object System.Text.UTF8Encoding $false))
(Get-Item -LiteralPath $completedIdleProbePath).LastWriteTime = (Get-Date).AddSeconds(-15)
& $watcher -QuarantineRootOverride $quarantineRoot
$completedIdleRiskCountAfter = @(Select-String -LiteralPath $completedIdleRiskLog -Pattern $completedIdleProbeId -SimpleMatch -ErrorAction SilentlyContinue).Count
if ($completedIdleRiskCountAfter -ne $completedIdleRiskCountBefore) {
    throw "Active session risk throttle canary failed: before=$completedIdleRiskCountBefore after=$completedIdleRiskCountAfter"
}
if ([string]$completedIdleArchived -ne "0" -or $completedIdleItem.Length -lt 2000000 -or $completedIdleQuarantine.Count -ne 0) {
    throw "Completed idle sanitizer canary failed: archived=$completedIdleArchived length=$($completedIdleItem.Length)"
}
& $sqlite $stateDb "DELETE FROM threads WHERE id = '$completedIdleProbeId';" | Out-Null
Remove-Item -LiteralPath $completedIdleProbePath -Force -ErrorAction SilentlyContinue

[System.IO.File]::WriteAllText($testLock, [DateTimeOffset]::UtcNow.ToString("yyyy-MM-ddTHH:mm:ss.fffZ"), (New-Object System.Text.UTF8Encoding $false))
Remove-Item -LiteralPath $quarantineRoot -Recurse -Force -ErrorAction SilentlyContinue

$probeId = "00000000-0000-4000-8000-000000000001"
$insertPath = "@@CODEXPP_HOME:win@@\sessions\2099\01\01\rollout-future-insert-$probeId.jsonl"
$updatePath = "@@CODEXPP_HOME:win@@\sessions\2099\01\01\rollout-future-update-$probeId.jsonl"
$cwd = "\\?\@@LAUNCHER_ROOT:win@@"
$longTitle = ("Codex++ title normalizer probe`r`n" + ("x" * 400)).Replace("'", "''")
$longPreview = ("Codex++ preview normalizer probe`r`n" + ("y" * 1600)).Replace("'", "''")

$sql = @"
PRAGMA busy_timeout = 2000;
BEGIN IMMEDIATE;
INSERT INTO threads (
  id, rollout_path, created_at, updated_at, source, model_provider,
  cwd, title, sandbox_policy, approval_mode
) VALUES (
  '$probeId',
  '$insertPath',
  4070908800,
  4070908800,
  'vscode',
  'cm',
  '$cwd',
  '$longTitle',
  'dangerFullAccess',
  'never'
);
UPDATE threads
SET preview = '$longPreview'
WHERE id = '$probeId';
UPDATE threads
SET tokens_used = 8000001,
    archived = 0
WHERE id = '$probeId';
SELECT
  CASE
    WHEN instr(rollout_path, '@@CODEXPP_HOME:win@@') = 1 THEN 'insert_ok'
    ELSE 'insert_bad:' || rollout_path
  END
FROM threads
WHERE id = '$probeId';
UPDATE threads
SET rollout_path = '$updatePath'
WHERE id = '$probeId';
SELECT
  CASE
    WHEN instr(rollout_path, '@@CODEXPP_HOME:win@@') = 1 THEN 'update_ok'
    ELSE 'update_bad:' || rollout_path
  END
FROM threads
WHERE id = '$probeId';
SELECT
  CASE
    WHEN hex(substr(cwd, 1, 4)) != '5C5C3F5C' THEN 'cwd_ok'
    ELSE 'cwd_bad:' || cwd
  END
FROM threads
WHERE id = '$probeId';
SELECT
  CASE
    WHEN length(title) <= 180 AND instr(title, char(10)) = 0 AND instr(title, char(13)) = 0 THEN 'title_ok'
    ELSE 'title_bad:' || length(title)
  END
FROM threads
WHERE id = '$probeId';
SELECT
  CASE
    WHEN length(preview) <= 1200 AND instr(preview, char(10)) = 0 AND instr(preview, char(13)) = 0 THEN 'preview_ok'
    ELSE 'preview_bad:' || length(preview)
END
FROM threads
WHERE id = '$probeId';
UPDATE threads
SET title = ''
WHERE id = '$probeId';
SELECT
  CASE
    WHEN length(title) > 0 AND length(title) <= 180 THEN 'blank_title_fill_ok'
    ELSE 'blank_title_fill_bad:' || length(title)
  END
FROM threads
WHERE id = '$probeId';
SELECT
  CASE
    WHEN archived = 0 THEN 'large_token_visible_ok'
    ELSE 'large_token_visible_bad'
  END
FROM threads
WHERE id = '$probeId';
ROLLBACK;
"@

$result = & $sqlite $stateDb $sql
$joined = ($result -join "`n")
if ($joined -notmatch "insert_ok" -or $joined -notmatch "update_ok" -or $joined -notmatch "cwd_ok" -or $joined -notmatch "title_ok" -or $joined -notmatch "preview_ok" -or $joined -notmatch "blank_title_fill_ok" -or $joined -notmatch "large_token_visible_ok") {
    throw "Session state trigger verification failed:`n$joined"
}

$contractSql = @"
SELECT
  CASE
    WHEN COUNT(*) = 0 THEN 'rollout_add_prefix_triggers_absent_ok'
    ELSE 'rollout_add_prefix_triggers_present:' || COUNT(*)
  END
FROM sqlite_master
WHERE type = 'trigger'
  AND name LIKE 'codexpp_normalize_thread_rollout_path%'
  AND sql LIKE '%|| NEW.rollout_path%';
SELECT
  CASE
    WHEN COUNT(*) = 2 THEN 'rollout_strip_prefix_triggers_ok'
    ELSE 'rollout_strip_prefix_triggers_bad:' || COUNT(*)
  END
FROM sqlite_master
WHERE type = 'trigger'
  AND name LIKE 'codexpp_normalize_thread_rollout_path%'
  AND sql LIKE '%substr(NEW.rollout_path, 5)%';
SELECT
  CASE
    WHEN COUNT(*) = 0 THEN 'legacy_sessions_plain_paths_absent_ok'
    ELSE 'legacy_sessions_plain_paths_bad:' || COUNT(*)
  END
FROM threads
WHERE instr(rollout_path, char(92) || 'sessions' || char(92)) > 0
  AND instr(rollout_path, '@@CODEXPP_HOME:win@@') != 1;
"@
$contractResult = & $sqlite $stateDb $contractSql
$contractJoined = ($contractResult -join "`n")
if ($contractJoined -notmatch "rollout_add_prefix_triggers_absent_ok" -or $contractJoined -notmatch "rollout_strip_prefix_triggers_ok" -or $contractJoined -notmatch "legacy_sessions_plain_paths_absent_ok") {
    throw "Session rollout_path contract verification failed:`n$contractJoined"
}

$safeProbeId = "00000000-0000-4000-8000-000000000006"
$safeProbeDir = "@@CODEXPP_HOME:win@@\sessions\2099\01\01"
$safeProbePath = Join-Path $safeProbeDir "rollout-future-safe-$safeProbeId.jsonl"
New-Item -ItemType Directory -Path $safeProbeDir -Force | Out-Null
$safeLine = [string]::new([char]'m', 60000)
$safeProbeLines = @(
    ('{"timestamp":"2099-01-01T00:00:00.000Z","type":"session_meta","payload":{"id":"' + $safeProbeId + '","source":"test"}}'),
    ('{"timestamp":"2099-01-01T00:00:01.000Z","type":"event_msg","payload":{"type":"agent_message","message":"' + $safeLine + '"}}'),
    ('{"timestamp":"2099-01-01T00:00:02.000Z","type":"event_msg","payload":{"type":"agent_message","message":"' + $safeLine + '"}}'),
    ('{"timestamp":"2099-01-01T00:00:03.000Z","type":"event_msg","payload":{"type":"agent_message","message":"' + $safeLine + '"}}'),
    ('{"timestamp":"2099-01-01T00:00:04.000Z","type":"event_msg","payload":{"type":"agent_message","message":"' + $safeLine + '"}}'),
    ('{"timestamp":"2099-01-01T00:00:05.000Z","type":"event_msg","payload":{"type":"task_complete","turn_id":"probe","completed_at":4070908800}}')
)
[System.IO.File]::WriteAllLines($safeProbePath, [string[]]$safeProbeLines, (New-Object System.Text.UTF8Encoding $false))
(Get-Item -LiteralPath $safeProbePath).LastWriteTime = Get-Date

$safeInsertSql = @"
PRAGMA busy_timeout = 2000;
DELETE FROM threads WHERE id = '$safeProbeId';
INSERT INTO threads (
  id, rollout_path, created_at, updated_at, source, model_provider,
  cwd, title, sandbox_policy, approval_mode, tokens_used, archived, preview
) VALUES (
  '$safeProbeId',
  '$safeProbePath',
  4070908800,
  4070908800,
  'vscode',
  'cm',
  '@@LAUNCHER_ROOT:win@@',
  'codexpp safe medium transcript probe',
  'dangerFullAccess',
  'never',
  9000006,
  0,
  'codexpp safe medium transcript probe'
);
"@
& $sqlite $stateDb $safeInsertSql | Out-Null
& $watcher -QuarantineRootOverride $quarantineRoot -BypassIdleBudget
$safeProbeItem = Get-Item -LiteralPath $safeProbePath
$safeProbeArchived = & $sqlite $stateDb "SELECT archived FROM threads WHERE id = '$safeProbeId';"
$safeProbeQuarantine = @(Get-ChildItem -LiteralPath $quarantineRoot -Filter "*$safeProbeId.jsonl" -File -ErrorAction SilentlyContinue)
if ([string]$safeProbeArchived -ne "0" -or $safeProbeItem.Length -lt 200000 -or $safeProbeQuarantine.Count -ne 0) {
    throw "Safe medium session canary failed: archived=$safeProbeArchived length=$($safeProbeItem.Length) quarantine_count=$($safeProbeQuarantine.Count)"
}
& $sqlite $stateDb "DELETE FROM threads WHERE id = '$safeProbeId';" | Out-Null
Remove-Item -LiteralPath $safeProbePath -Force -ErrorAction SilentlyContinue

$bodyProbeId = "00000000-0000-4000-8000-000000000002"
$bodyProbeDir = "@@CODEXPP_HOME:win@@\sessions\2099\01\01"
$bodyProbePath = Join-Path $bodyProbeDir "rollout-future-body-$bodyProbeId.jsonl"
New-Item -ItemType Directory -Path $bodyProbeDir -Force | Out-Null
$bodyProbeText = @(
    ('{"timestamp":"2099-01-01T00:00:00.000Z","type":"session_meta","payload":{"id":"' + $bodyProbeId + '","source":"test"}}'),
    ('{"timestamp":"2099-01-01T00:00:01.000Z","type":"event_msg","payload":{"type":"agent_message","message":"' + ('x' * 1100000) + '"}}'),
    '{"timestamp":"2099-01-01T00:00:02.000Z","type":"event_msg","payload":{"type":"task_complete","turn_id":"probe","completed_at":4070908800}}'
) -join "`n"
[System.IO.File]::WriteAllText($bodyProbePath, $bodyProbeText, (New-Object System.Text.UTF8Encoding $false))
(Get-Item -LiteralPath $bodyProbePath).LastWriteTime = Get-Date

$bodyInsertSql = @"
PRAGMA busy_timeout = 2000;
DELETE FROM threads WHERE id = '$bodyProbeId';
INSERT INTO threads (
  id, rollout_path, created_at, updated_at, source, model_provider,
  cwd, title, sandbox_policy, approval_mode, tokens_used, archived, preview
) VALUES (
  '$bodyProbeId',
  '$bodyProbePath',
  4070908800,
  4070908800,
  'vscode',
  'cm',
  '@@LAUNCHER_ROOT:win@@',
  'codexpp body sanitizer probe',
  'dangerFullAccess',
  'never',
  9000001,
  0,
  'codexpp body sanitizer probe'
);
"@
& $sqlite $stateDb $bodyInsertSql | Out-Null
& $watcher -QuarantineRootOverride $quarantineRoot -BypassIdleBudget

$bodyProbeItem = Get-Item -LiteralPath $bodyProbePath
$bodyProbeArchived = & $sqlite $stateDb "SELECT archived FROM threads WHERE id = '$bodyProbeId';"
$bodyProbeQuarantine = @(Get-ChildItem -LiteralPath $quarantineRoot -Filter "*$bodyProbeId.jsonl" -File -ErrorAction SilentlyContinue)
Assert-ActiveSessionRiskRecorded -ThreadId $bodyProbeId -OriginalPath $bodyProbePath -ExpectedTier "active_unarchived_recent" -ExpectedReason "terminal_oversized_transcript_record_only"
if ([string]$bodyProbeArchived -ne "0" -or $bodyProbeItem.Length -lt 1000000 -or $bodyProbeQuarantine.Count -ne 0) {
    throw "Session body sanitizer canary failed: archived=$bodyProbeArchived length=$($bodyProbeItem.Length)"
}

& $sqlite $stateDb "DELETE FROM threads WHERE id = '$bodyProbeId';" | Out-Null
Remove-Item -LiteralPath $bodyProbePath -Force -ErrorAction SilentlyContinue

$archivedProbeId = "00000000-0000-4000-8000-000000000005"
$archivedProbeDir = Join-Path $codexHome "archived_sessions"
$archivedProbePath = Join-Path $archivedProbeDir "rollout-future-archived-$archivedProbeId.jsonl"
New-Item -ItemType Directory -Path $archivedProbeDir -Force | Out-Null
$archivedProbeText = @(
    ('{"timestamp":"2099-01-01T00:00:00.000Z","type":"session_meta","payload":{"id":"' + $archivedProbeId + '","source":"test"}}'),
    ('{"timestamp":"2099-01-01T00:00:01.000Z","type":"event_msg","payload":{"type":"agent_message","message":"' + ('a' * 650000) + '"}}'),
    '{"timestamp":"2099-01-01T00:00:02.000Z","type":"event_msg","payload":{"type":"task_complete","turn_id":"probe","completed_at":4070908800}}'
) -join "`n"
[System.IO.File]::WriteAllText($archivedProbePath, $archivedProbeText, (New-Object System.Text.UTF8Encoding $false))
(Get-Item -LiteralPath $archivedProbePath).LastWriteTime = Get-Date

$archivedInsertSql = @"
PRAGMA busy_timeout = 2000;
DELETE FROM threads WHERE id = '$archivedProbeId';
INSERT INTO threads (
  id, rollout_path, created_at, updated_at, source, model_provider,
  cwd, title, sandbox_policy, approval_mode, tokens_used, archived, preview
) VALUES (
  '$archivedProbeId',
  '$archivedProbePath',
  4070908800,
  4070908800,
  'vscode',
  'cm',
  '@@LAUNCHER_ROOT:win@@',
  'codexpp archived sanitizer probe',
  'dangerFullAccess',
  'never',
  9000004,
  1,
  'codexpp archived sanitizer probe'
);
"@
& $sqlite $stateDb $archivedInsertSql | Out-Null
& $watcher -QuarantineRootOverride $quarantineRoot -BypassIdleBudget

$archivedProbeItem = Get-Item -LiteralPath $archivedProbePath
$archivedProbeArchived = & $sqlite $stateDb "SELECT archived FROM threads WHERE id = '$archivedProbeId';"
$archivedProbeColdStorage = Assert-LifecycleColdStorage -ThreadId $archivedProbeId -StubPath $archivedProbePath -ExpectedReason "terminal_oversized_transcript" -MaxStubBytes 500000
if ([string]$archivedProbeArchived -ne "1" -or $archivedProbeItem.Length -ge 500000) {
    throw "Archived session sanitizer canary failed: archived=$archivedProbeArchived length=$($archivedProbeItem.Length)"
}

& $sqlite $stateDb "DELETE FROM threads WHERE id = '$archivedProbeId';" | Out-Null
Remove-Item -LiteralPath $archivedProbePath -Force -ErrorAction SilentlyContinue
$archivedProbeColdStorage.Quarantine | Remove-Item -Force -ErrorAction SilentlyContinue
$archivedProbeColdStorage.Summary | Remove-Item -Force -ErrorAction SilentlyContinue

$abortProbeId = "00000000-0000-4000-8000-000000000003"
$abortProbePath = Join-Path $bodyProbeDir "rollout-future-abort-$abortProbeId.jsonl"
$abortProbeText = @(
    ('{"timestamp":"2099-01-01T00:00:00.000Z","type":"session_meta","payload":{"id":"' + $abortProbeId + '","source":"test"}}'),
    ('{"timestamp":"2099-01-01T00:00:01.000Z","type":"event_msg","payload":{"type":"agent_message","message":"' + ('z' * 1100000) + '"}}'),
    '{"timestamp":"2099-01-01T00:00:02.000Z","type":"event_msg","payload":{"type":"turn_aborted","turn_id":"probe"}}'
) -join "`n"
[System.IO.File]::WriteAllText($abortProbePath, $abortProbeText, (New-Object System.Text.UTF8Encoding $false))
(Get-Item -LiteralPath $abortProbePath).LastWriteTime = Get-Date

$abortInsertSql = @"
PRAGMA busy_timeout = 2000;
DELETE FROM threads WHERE id = '$abortProbeId';
INSERT INTO threads (
  id, rollout_path, created_at, updated_at, source, model_provider,
  cwd, title, sandbox_policy, approval_mode, tokens_used, archived, preview
) VALUES (
  '$abortProbeId',
  '$abortProbePath',
  4070908800,
  4070908800,
  'vscode',
  'cm',
  '@@LAUNCHER_ROOT:win@@',
  'codexpp aborted sanitizer probe',
  'dangerFullAccess',
  'never',
  9000002,
  0,
  'codexpp aborted sanitizer probe'
);
"@
& $sqlite $stateDb $abortInsertSql | Out-Null
& $watcher -QuarantineRootOverride $quarantineRoot -BypassIdleBudget

$abortProbeItem = Get-Item -LiteralPath $abortProbePath
$abortProbeArchived = & $sqlite $stateDb "SELECT archived FROM threads WHERE id = '$abortProbeId';"
$abortProbeQuarantine = @(Get-ChildItem -LiteralPath $quarantineRoot -Filter "*$abortProbeId.jsonl" -File -ErrorAction SilentlyContinue)
Assert-ActiveSessionRiskRecorded -ThreadId $abortProbeId -OriginalPath $abortProbePath -ExpectedTier "active_unarchived_recent" -ExpectedReason "interrupted_active_oversized_transcript_record_only"
if ([string]$abortProbeArchived -ne "0" -or $abortProbeItem.Length -lt 1000000 -or $abortProbeQuarantine.Count -ne 0) {
    throw "Aborted active session quarantine canary failed: archived=$abortProbeArchived length=$($abortProbeItem.Length)"
}
$abortProbeText = Get-Content -LiteralPath $abortProbePath -Raw
if (-not $abortProbeText.Contains($abortProbeId) -or $abortProbeText.Contains("cold storage")) {
    throw "Aborted active session protection canary failed: original thread was replaced or cold-stored"
}
$abortResumeHint = & $sqlite $stateDb "SELECT first_user_message FROM threads WHERE id = '$abortProbeId';"
if ([string]$abortResumeHint -match "safe stub" -or [string]$abortResumeHint -match "Cold transcript") {
    throw "Aborted active session protection canary failed: original thread should not be rewritten with safe resume hint"
}
$abortRecoveryCount = & $sqlite $stateDb "SELECT COUNT(*) FROM threads WHERE id <> '$abortProbeId' AND first_user_message LIKE '%$abortProbeId%';"
if ([int]$abortRecoveryCount -ne 0) {
    throw "Aborted active session recovery canary failed: synthetic recovery thread should not be created for $abortProbeId"
}

& $sqlite $stateDb "DELETE FROM threads WHERE id = '$abortProbeId';" | Out-Null
& $sqlite $stateDb "DELETE FROM threads WHERE first_user_message LIKE '%$abortProbeId%';" | Out-Null
Remove-Item -LiteralPath $abortProbePath -Force -ErrorAction SilentlyContinue

$staleProbeId = "00000000-0000-4000-8000-000000000004"
$staleProbePath = Join-Path $bodyProbeDir "rollout-future-stale-$staleProbeId.jsonl"
$staleProbeText = @(
    ('{"timestamp":"2099-01-01T00:00:00.000Z","type":"session_meta","payload":{"id":"' + $staleProbeId + '","source":"test"}}'),
    ('{"timestamp":"2099-01-01T00:00:01.000Z","type":"response_item","payload":{"type":"message","role":"user","content":[{"type":"input_text","text":"' + ('s' * 650000) + '"}]}}')
) -join "`n"
[System.IO.File]::WriteAllText($staleProbePath, $staleProbeText, (New-Object System.Text.UTF8Encoding $false))
(Get-Item -LiteralPath $staleProbePath).LastWriteTime = Get-Date

$staleInsertSql = @"
PRAGMA busy_timeout = 2000;
DELETE FROM threads WHERE id = '$staleProbeId';
INSERT INTO threads (
  id, rollout_path, created_at, updated_at, source, model_provider,
  cwd, title, sandbox_policy, approval_mode, tokens_used, archived, preview
) VALUES (
  '$staleProbeId',
  '$staleProbePath',
  4070908800,
  4070908800,
  'vscode',
  'cm',
  '@@LAUNCHER_ROOT:win@@',
  'codexpp stale sanitizer probe',
  'dangerFullAccess',
  'never',
  9000003,
  0,
  'codexpp stale sanitizer probe'
);
"@
& $sqlite $stateDb $staleInsertSql | Out-Null
& $watcher -QuarantineRootOverride $quarantineRoot -BypassIdleBudget

$staleProbeItem = Get-Item -LiteralPath $staleProbePath
$staleProbeArchived = & $sqlite $stateDb "SELECT archived FROM threads WHERE id = '$staleProbeId';"
$staleProbeQuarantine = @(Get-ChildItem -LiteralPath $quarantineRoot -Filter "*$staleProbeId.jsonl" -File -ErrorAction SilentlyContinue)
Assert-ActiveSessionRiskRecorded -ThreadId $staleProbeId -OriginalPath $staleProbePath -ExpectedTier "active_unarchived_recent" -ExpectedReason "stale_incomplete_oversized_transcript_record_only"
if ([string]$staleProbeArchived -ne "0" -or $staleProbeItem.Length -lt 500000 -or $staleProbeQuarantine.Count -ne 0) {
    throw "Stale active session protection canary failed: archived=$staleProbeArchived length=$($staleProbeItem.Length) quarantine_count=$($staleProbeQuarantine.Count)"
}

& $sqlite $stateDb "DELETE FROM threads WHERE id = '$staleProbeId';" | Out-Null
Remove-Item -LiteralPath $staleProbePath -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath $quarantineRoot -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath $testLock -Force -ErrorAction SilentlyContinue
} catch {
    $testFailure = $_
} finally {
    try {
        if (Test-Path -LiteralPath $canonicalTestLock -PathType Leaf) { [IO.File]::Delete($canonicalTestLock) }
    } catch {
        [void]$cleanupFailures.Add("test lock cleanup failed: $($_.Exception.Message)")
    }
    foreach ($cleanupProbeId in $cleanupProbeIds) {
        try { & $sqlite $stateDb "DELETE FROM threads WHERE id = '$cleanupProbeId';" | Out-Null }
        catch { [void]$cleanupFailures.Add("thread cleanup failed for $cleanupProbeId`: $($_.Exception.Message)") }
    }
    try { & $sqlite $stateDb "DELETE FROM threads WHERE first_user_message LIKE '%00000000-0000-4000-8000-000000000003%';" | Out-Null }
    catch { [void]$cleanupFailures.Add("recovery thread cleanup failed: $($_.Exception.Message)") }
    foreach ($cleanupProbeFile in $cleanupProbeFiles) {
        try {
            if (Test-Path -LiteralPath $cleanupProbeFile -PathType Leaf) { [IO.File]::Delete($cleanupProbeFile) }
        } catch {
            [void]$cleanupFailures.Add("probe file cleanup failed for $cleanupProbeFile`: $($_.Exception.Message)")
        }
    }
    try {
        if (Test-Path -LiteralPath $canonicalTestQuarantineRoot -PathType Container) { [IO.Directory]::Delete($canonicalTestQuarantineRoot, $true) }
    } catch {
        [void]$cleanupFailures.Add("test quarantine cleanup failed: $($_.Exception.Message)")
    }
}
if ($testFailure) {
    if ($cleanupFailures.Count -gt 0) { Write-Warning ("Lifecycle test cleanup also failed: " + ($cleanupFailures -join '; ')) }
    throw $testFailure
}
if ($cleanupFailures.Count -gt 0) { throw ("Lifecycle test cleanup failed: " + ($cleanupFailures -join '; ')) }

Write-Output "PASS Codex++ session lifecycle keeps renderer-safe canonical paths, metadata bounded, archived transcripts cold-stored, and active unarchived oversized transcripts intact with record-only risk entries"
