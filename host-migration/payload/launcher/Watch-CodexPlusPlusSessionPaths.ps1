#requires -Version 7.0

# One-shot Codex++ session maintenance batch: normalize session paths and
# thread title/preview/cwd via SQLite triggers, then quarantine oversized
# renderer-unsafe session transcripts into cold storage.  The retired
# background watcher mode must never return (no -Watch switch, PID file,
# or polling loop).

param(
    [string]$QuarantineRootOverride = "",
    [switch]$BypassIdleBudget
)

$ErrorActionPreference = "Stop"

$profileAliasRoot = [System.IO.Path]::GetFullPath('@@USERPROFILE:win@@\AppData\Roaming\CodexPlusPlusProfile').TrimEnd('\')
$profileCanonicalRoot = [System.IO.Path]::GetFullPath('@@CODEXPP_PROFILE:win@@').TrimEnd('\')
$ordinaryCodexRoot = [System.IO.Path]::GetFullPath('@@CODEX_HOME:win@@').TrimEnd('\')

function Test-CodexPlusPlusPathWithinRoot {
    param([string]$Path, [string]$Root)
    try {
        $fullPath = [System.IO.Path]::GetFullPath($Path).TrimEnd('\')
        $fullRoot = [System.IO.Path]::GetFullPath($Root).TrimEnd('\')
    } catch {
        return $false
    }
    [string]::Equals($fullPath, $fullRoot, [System.StringComparison]::OrdinalIgnoreCase) -or
        $fullPath.StartsWith(($fullRoot + '\'), [System.StringComparison]::OrdinalIgnoreCase)
}

function Assert-CodexPlusPlusPhysicalPathChain {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$Label,
        [switch]$RequireContainer
    )
    $fullPath = [System.IO.Path]::GetFullPath($Path).TrimEnd('\')
    $pathRoot = [System.IO.Path]::GetPathRoot($fullPath)
    $current = $pathRoot
    foreach ($part in @($fullPath.Substring($pathRoot.Length).Split('\') | Where-Object { $_ })) {
        $current = Join-Path $current $part
        if (-not (Test-Path -LiteralPath $current)) { throw "Codex++ $Label is missing: $current" }
        $item = Get-Item -LiteralPath $current -Force
        if ($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) {
            throw "Codex++ $Label contains a reparse point: $current"
        }
    }
    if ($RequireContainer -and -not (Test-Path -LiteralPath $fullPath -PathType Container)) {
        throw "Codex++ $Label is not a directory: $fullPath"
    }
    return $fullPath
}

function Assert-CodexPlusPlusExistingPathChainPhysical {
    param([Parameter(Mandatory = $true)][string]$Path, [Parameter(Mandatory = $true)][string]$Label)
    $fullPath = [System.IO.Path]::GetFullPath($Path).TrimEnd('\')
    $pathRoot = [System.IO.Path]::GetPathRoot($fullPath)
    $current = $pathRoot
    foreach ($part in @($fullPath.Substring($pathRoot.Length).Split('\') | Where-Object { $_ })) {
        $current = Join-Path $current $part
        if (-not (Test-Path -LiteralPath $current)) { return $fullPath }
        $item = Get-Item -LiteralPath $current -Force
        if ($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) {
            throw "Codex++ $Label contains a reparse point: $current"
        }
    }
    return $fullPath
}

function Test-CodexPlusPlusProfileAliasDescriptor {
    param([System.IO.FileAttributes]$Attributes, [string]$LinkType, [object[]]$Targets, [string]$ExpectedCanonicalRoot)
    if (-not ($Attributes -band [System.IO.FileAttributes]::Directory) -or
        -not ($Attributes -band [System.IO.FileAttributes]::ReparsePoint) -or
        -not [string]::Equals($LinkType, 'Junction', [System.StringComparison]::OrdinalIgnoreCase)) {
        return $false
    }
    $targetList = @($Targets)
    if ($targetList.Count -ne 1 -or [string]::IsNullOrWhiteSpace([string]$targetList[0])) { return $false }
    try {
        $actualTarget = [System.IO.Path]::GetFullPath([string]$targetList[0]).TrimEnd('\')
        $expectedTarget = [System.IO.Path]::GetFullPath($ExpectedCanonicalRoot).TrimEnd('\')
    } catch {
        return $false
    }
    [string]::Equals($actualTarget, $expectedTarget, [System.StringComparison]::OrdinalIgnoreCase)
}

function Assert-CodexPlusPlusProfileAlias {
    param([string]$Reason = 'unspecified')
    # Legacy function name retained for callers; the runtime Profile alias
    # must be absent. Only the physical D: canonical paths are valid.
    if (Test-Path -LiteralPath $profileAliasRoot) {
        throw "Codex++ retired C: profile alias is present during ${Reason}: $profileAliasRoot"
    }
    [void](Assert-CodexPlusPlusPhysicalPathChain -Path $profileCanonicalRoot -Label 'canonical profile root path' -RequireContainer)
    [void](Assert-CodexPlusPlusPhysicalPathChain -Path $codexHome -Label 'canonical CODEX_HOME path' -RequireContainer)
}

function Convert-CodexPlusPlusProfilePathToCanonical {
    param([Parameter(Mandatory = $true)][string]$Path)
    # This conversion is only for historical path strings found in old session
    # records; it never authorizes a read or write through the retired alias.
    $candidate = [string]$Path
    if ($candidate.StartsWith('\\?\')) { $candidate = $candidate.Substring(4) }
    if ($candidate.StartsWith("\\'\") -or $candidate.StartsWith('\\"\')) { $candidate = $candidate.Substring(3) }
    $fullPath = [System.IO.Path]::GetFullPath($candidate).TrimEnd('\')
    if ([string]::Equals($fullPath, $profileAliasRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
        return $profileCanonicalRoot
    }
    if ($fullPath.StartsWith(($profileAliasRoot + '\'), [System.StringComparison]::OrdinalIgnoreCase)) {
        $suffix = $fullPath.Substring($profileAliasRoot.Length)
        if ($suffix -ieq '\.codex' -or $suffix -like '\.codex\*') {
            return Join-Path $codexHome $suffix.Substring(7).TrimStart('\')
        }
        return Join-Path $profileCanonicalRoot $suffix.TrimStart('\')
    }
    return $fullPath
}

function Test-CodexPlusPlusWritePathDescriptor {
    param(
        [string]$Path,
        [string]$ProfileAliasRoot,
        [string]$CanonicalCodexHome,
        [string]$OrdinaryCodexRoot
    )
    if (Test-CodexPlusPlusPathWithinRoot -Path $Path -Root $ProfileAliasRoot) { return $false }
    if (Test-CodexPlusPlusPathWithinRoot -Path $Path -Root $OrdinaryCodexRoot) { return $false }
    return Test-CodexPlusPlusPathWithinRoot -Path $Path -Root $CanonicalCodexHome
}

function Test-CodexPlusPlusSessionSourcePathDescriptor {
    param([string]$Path, [string]$SessionRoot, [string]$ArchivedSessionRoot)
    try {
        $fullPath = [System.IO.Path]::GetFullPath($Path)
    } catch {
        return $false
    }
    if (-not [string]::Equals([System.IO.Path]::GetExtension($fullPath), '.jsonl', [System.StringComparison]::OrdinalIgnoreCase)) {
        return $false
    }
    ($fullPath.StartsWith(([System.IO.Path]::GetFullPath($SessionRoot).TrimEnd('\') + '\'), [System.StringComparison]::OrdinalIgnoreCase)) -or
        ($fullPath.StartsWith(([System.IO.Path]::GetFullPath($ArchivedSessionRoot).TrimEnd('\') + '\'), [System.StringComparison]::OrdinalIgnoreCase))
}

$codexHome = Join-Path $profileCanonicalRoot 'AppData\Roaming\Codex\.codex'
Assert-CodexPlusPlusProfileAlias -Reason 'watcher_startup'
$canonicalSessionRoot = Join-Path $codexHome 'sessions'
$canonicalArchivedSessionRoot = Join-Path $codexHome 'archived_sessions'
$stateDb = Join-Path $codexHome "state_5.sqlite"
$sessionLifecycleTestLock = Join-Path $codexHome "session-lifecycle-test.lock"
$sqlitePython = '@@CODEXPP_PROFILE:win@@\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$sqliteHelper = '@@LAUNCHER_ROOT:win@@\Invoke-CodexPlusPlusSqlite.py'
foreach ($dependency in @($sqlitePython, $sqliteHelper)) {
    if (-not (Test-Path -LiteralPath $dependency -PathType Leaf)) {
        throw "Codex++ fixed sqlite dependency missing: $dependency"
    }
}
$sqlite = {
    $sqliteArguments = @($args)
    $timeoutMs = 2000
    $offset = 0
    if ($sqliteArguments.Count -ge 2 -and [string]$sqliteArguments[0] -eq '-cmd') {
        if ([string]$sqliteArguments[1] -notmatch '^\.timeout\s+([0-9]{1,5})$') {
            throw "Unsupported Codex++ sqlite shell command: $($sqliteArguments[1])"
        }
        $timeoutMs = [int]$Matches[1]
        $offset = 2
    }
    if (($sqliteArguments.Count - $offset) -ne 2) {
        throw "Codex++ sqlite wrapper requires an exact database and SQL argument"
    }
    $database = [string]$sqliteArguments[$offset]
    $sqlText = [string]$sqliteArguments[$offset + 1]
    $sqlBase64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($sqlText))
    $sqliteOutput = @(& $sqlitePython $sqliteHelper --database $database --timeout-ms $timeoutMs --sql-base64 $sqlBase64 2>&1)
    if ($LASTEXITCODE -ne 0) {
        throw "Codex++ sqlite helper failed: $($sqliteOutput -join ' ')"
    }
    $sqliteOutput
}
$maxThreadTitleLength = 180
$maxThreadPreviewLength = 1200
$maxSessionFileBytes = 2000000
$maxSessionLineChars = 120000
$minSessionIdleSeconds = 120
$completedSessionIdleSeconds = 10
$staleIncompleteSessionSeconds = 300
$activeSessionProtectionSeconds = 86400
$activeSessionRiskSuppressSeconds = 600
$sessionQuarantineRoot = Join-Path $codexHome "quarantined_sessions"
if (-not [string]::IsNullOrWhiteSpace($QuarantineRootOverride)) {
    $sessionQuarantineRoot = Convert-CodexPlusPlusProfilePathToCanonical -Path $QuarantineRootOverride
}
$sessionQuarantineManifest = Join-Path $sessionQuarantineRoot "manifest.jsonl"
$sessionLifecycleIndex = Join-Path $sessionQuarantineRoot "lifecycle_index.jsonl"
$activeSessionRiskLog = Join-Path $sessionQuarantineRoot "active_session_risks.jsonl"
$sessionSummaryRoot = Join-Path $sessionQuarantineRoot "summaries"
$coldSessionReader = "@@LAUNCHER_ROOT:win@@\Read-CodexPlusPlusColdSession.ps1"

function Assert-CodexPlusPlusProfileWriteBoundary {
    param(
        [Parameter(Mandatory = $true)][string[]]$Paths,
        [Parameter(Mandatory = $true)][string]$Reason
    )
    Assert-CodexPlusPlusProfileAlias -Reason $Reason
    foreach ($path in $Paths) {
        $fullPath = [System.IO.Path]::GetFullPath($path).TrimEnd('\')
        if (-not (Test-CodexPlusPlusWritePathDescriptor -Path $fullPath -ProfileAliasRoot $profileAliasRoot `
            -CanonicalCodexHome $codexHome -OrdinaryCodexRoot $ordinaryCodexRoot)) {
            throw "Refusing Codex++ $Reason outside the canonical D: CODEX_HOME: $fullPath"
        }
        [void](Assert-CodexPlusPlusExistingPathChainPhysical -Path $fullPath -Label $Reason)
    }
}

Assert-CodexPlusPlusProfileWriteBoundary -Paths @($sessionQuarantineRoot) -Reason 'quarantine_root_initialization'
if ((Test-CodexPlusPlusPathWithinRoot -Path $sessionQuarantineRoot -Root $canonicalSessionRoot) -or
    (Test-CodexPlusPlusPathWithinRoot -Path $canonicalSessionRoot -Root $sessionQuarantineRoot) -or
    (Test-CodexPlusPlusPathWithinRoot -Path $sessionQuarantineRoot -Root $canonicalArchivedSessionRoot) -or
    (Test-CodexPlusPlusPathWithinRoot -Path $canonicalArchivedSessionRoot -Root $sessionQuarantineRoot)) {
    throw "Refusing Codex++ quarantine root overlap with active or archived session roots: $sessionQuarantineRoot"
}

function Write-Utf8NoBom {
    param(
        [string]$Path,
        [string]$Text
    )
    Assert-CodexPlusPlusProfileWriteBoundary -Paths @($Path) -Reason 'utf8_file_write'
    [System.IO.File]::WriteAllText($Path, $Text, (New-Object System.Text.UTF8Encoding $false))
}

function Get-ColdSessionRestoreCommand {
    param([string]$ThreadId)
    $reader = $coldSessionReader.Replace("'", "''")
    $id = ([string]$ThreadId).Replace("'", "''")
    return "& '@@POWERSHELL_EXE:win@@' -NoProfile -File '$reader' -ThreadId '$id' -Mode Restore"
}
function Test-SessionLifecycleTestLock {
    if (-not (Test-Path -LiteralPath $sessionLifecycleTestLock)) { return $false }
    try {
        $lockItem = Get-Item -LiteralPath $sessionLifecycleTestLock
        $ageSeconds = ((Get-Date) - $lockItem.LastWriteTime).TotalSeconds
        if ($ageSeconds -gt 600) {
            Assert-CodexPlusPlusProfileWriteBoundary -Paths @($sessionLifecycleTestLock) -Reason 'stale_lifecycle_lock_remove'
            Remove-Item -LiteralPath $sessionLifecycleTestLock -Force -ErrorAction SilentlyContinue
            return $false
        }
        return $true
    } catch {
        return $false
    }
}

function Get-JsonString {
    param([string]$Value)
    return ($Value | ConvertTo-Json -Compress)
}

function New-RendererSafeSessionMetaLine {
    param(
        [string]$ThreadId,
        [string]$Timestamp
    )
    $meta = [ordered]@{
        timestamp = $Timestamp
        type = "session_meta"
        payload = [ordered]@{
            id = $ThreadId
            timestamp = $Timestamp
            cwd = "@@LAUNCHER_ROOT:win@@"
            originator = "Codex Desktop"
            cli_version = "0.131.0-alpha.9"
            source = "vscode"
            thread_source = "user"
            model_provider = "cm"
            base_instructions = [ordered]@{
                text = "Codex++ cold-storage stub. Original transcript is preserved outside the renderer-safe rollout."
            }
            dynamic_tools = @()
        }
    }
    return ($meta | ConvertTo-Json -Depth 8 -Compress)
}

function Get-PreviewText {
    param(
        [string]$Text,
        [int]$MaxLength = 320
    )
    if ([string]::IsNullOrWhiteSpace($Text)) { return "" }
    $clean = $Text.Replace("`r", " ").Replace("`n", " ").Trim()
    if ($clean.Length -le $MaxLength) { return $clean }
    return $clean.Substring(0, $MaxLength - 3) + "..."
}

function Get-MaxLineLength {
    param([string]$Path)
    if ($Path.StartsWith("\\?\")) { $Path = $Path.Substring(4) }
    $max = 0
    try {
        $stream = [System.IO.FileStream]::new(
            $Path,
            [System.IO.FileMode]::Open,
            [System.IO.FileAccess]::Read,
            [System.IO.FileShare]::ReadWrite -bor [System.IO.FileShare]::Delete
        )
        $reader = [System.IO.StreamReader]::new($stream)
    } catch [System.IO.IOException] {
        return -1
    }
    try {
        while (-not $reader.EndOfStream) {
            $line = $reader.ReadLine()
            if ($line.Length -gt $max) { $max = $line.Length }
            if ($max -gt $maxSessionLineChars) { break }
        }
    } finally {
        $reader.Close()
        $reader.Dispose()
    }
    return $max
}

function Test-CompletedSessionFile {
    param([string]$Path)
    if ($Path.StartsWith("\\?\")) { $Path = $Path.Substring(4) }
    try {
        $item = Get-Item -LiteralPath $Path
        $length = [int64]$item.Length
        if ($length -le 0) { return $false }
        $window = [Math]::Min($length, 262144)
        $buffer = New-Object byte[] $window
        $stream = [System.IO.FileStream]::new(
            $Path,
            [System.IO.FileMode]::Open,
            [System.IO.FileAccess]::Read,
            [System.IO.FileShare]::ReadWrite -bor [System.IO.FileShare]::Delete
        )
        try {
            [void]$stream.Seek(-1 * $window, [System.IO.SeekOrigin]::End)
            [void]$stream.Read($buffer, 0, $window)
        } finally {
            $stream.Close()
            $stream.Dispose()
        }
        $tail = [System.Text.Encoding]::UTF8.GetString($buffer)
        return $tail.Contains('"type":"task_complete"')
    } catch {
        return $false
    }
}

function Test-InterruptedSessionFile {
    param([string]$Path)
    if ($Path.StartsWith("\\?\")) { $Path = $Path.Substring(4) }
    try {
        $item = Get-Item -LiteralPath $Path
        $length = [int64]$item.Length
        if ($length -le 0) { return $false }
        $window = [Math]::Min($length, 262144)
        $buffer = New-Object byte[] $window
        $stream = [System.IO.FileStream]::new(
            $Path,
            [System.IO.FileMode]::Open,
            [System.IO.FileAccess]::Read,
            [System.IO.FileShare]::ReadWrite -bor [System.IO.FileShare]::Delete
        )
        try {
            [void]$stream.Seek(-1 * $window, [System.IO.SeekOrigin]::End)
            [void]$stream.Read($buffer, 0, $window)
        } finally {
            $stream.Close()
            $stream.Dispose()
        }
        $tail = [System.Text.Encoding]::UTF8.GetString($buffer)
        return (
            $tail.Contains('"type":"turn_aborted"') -or
            $tail.Contains('"type":"thread_rolled_back"')
        )
    } catch {
        return $false
    }
}

function New-SessionLifecycleSummary {
    param(
        [string]$Path,
        [string]$ThreadId,
        [string]$Title,
        [string]$OriginalPath,
        [string]$QuarantinePath,
        [int64]$OriginalBytes,
        [int]$OriginalMaxLineChars,
        [string]$LifecycleTier,
        [string]$Reason
    )
    $eventCounts = @{}
    $lineCount = 0
    $firstUserPreview = ""
    $lastAssistantPreview = ""
    $lastEventType = ""
    $terminalMarker = ""

    try {
        $stream = [System.IO.FileStream]::new(
            $Path,
            [System.IO.FileMode]::Open,
            [System.IO.FileAccess]::Read,
            [System.IO.FileShare]::ReadWrite -bor [System.IO.FileShare]::Delete
        )
        $reader = [System.IO.StreamReader]::new($stream)
    } catch {
        $stream = $null
        $reader = $null
    }

    if ($reader) {
        try {
            while (-not $reader.EndOfStream) {
                $line = $reader.ReadLine()
                $lineCount++
                if ($line -match '"type":"([^"]+)"') {
                    $eventType = $Matches[1]
                    $lastEventType = $eventType
                    if (-not $eventCounts.ContainsKey($eventType)) { $eventCounts[$eventType] = 0 }
                    $eventCounts[$eventType] = [int]$eventCounts[$eventType] + 1
                    if ($eventType -in @("task_complete", "turn_aborted", "thread_rolled_back")) {
                        $terminalMarker = $eventType
                    }
                }

                if ($line.Length -le 200000 -and ($line.Contains('"role":"user"') -or $line.Contains('"role":"assistant"'))) {
                    try {
                        $obj = $line | ConvertFrom-Json
                        $payload = $obj.payload
                        if ($payload -and $payload.type -eq "message") {
                            $text = ""
                            foreach ($content in @($payload.content)) {
                                if ($content.text) { $text += [string]$content.text }
                            }
                            if ($payload.role -eq "user" -and [string]::IsNullOrWhiteSpace($firstUserPreview)) {
                                $firstUserPreview = Get-PreviewText -Text $text
                            }
                            if ($payload.role -eq "assistant") {
                                $lastAssistantPreview = Get-PreviewText -Text $text
                            }
                        }
                    } catch {
                    }
                }
            }
        } finally {
            $reader.Close()
            $reader.Dispose()
        }
    }

    $restoreCommand = Get-ColdSessionRestoreCommand -ThreadId $ThreadId
    return [ordered]@{
        schema = "codexpp_session_lifecycle.v1"
        generated_at = [DateTimeOffset]::UtcNow.ToString("yyyy-MM-ddTHH:mm:ss.fffZ")
        thread_id = $ThreadId
        title = (Get-PreviewText -Text $Title -MaxLength 180)
        lifecycle_tier = $LifecycleTier
        reason = $Reason
        original_path = $OriginalPath
        quarantine_path = $QuarantinePath
        original_bytes = $OriginalBytes
        original_max_line_chars = $OriginalMaxLineChars
        line_count = $lineCount
        last_event_type = $lastEventType
        terminal_marker = $terminalMarker
        first_user_preview = $firstUserPreview
        last_assistant_preview = $lastAssistantPreview
        event_counts = $eventCounts
        restore = [ordered]@{
            mode = "on_demand"
            instruction = "Open the quarantine_path directly for audit/export. Do not point Codex++ renderer at this JSONL without chunking."
            command = $restoreCommand
        }
    }
}

function Write-SessionLifecycleSummary {
    param(
        [string]$SummaryPath,
        [object]$Summary
    )
    $json = $Summary | ConvertTo-Json -Depth 8
    Write-Utf8NoBom -Path $SummaryPath -Text ($json + "`n")
}

function Add-QuarantineManifestEntry {
    param(
        [string]$ThreadId,
        [string]$OriginalPath,
        [string]$QuarantinePath,
        [string]$SummaryPath,
        [int64]$OriginalBytes,
        [int]$OriginalMaxLineChars,
        [bool]$WasArchived,
        [string]$LifecycleTier,
        [string]$Reason
    )
    Assert-CodexPlusPlusProfileWriteBoundary -Paths @($sessionQuarantineManifest, $sessionLifecycleIndex) -Reason 'quarantine_manifest_append'
    $entry = [ordered]@{
        schema = "codexpp_session_lifecycle_manifest.v1"
        timestamp = [DateTimeOffset]::UtcNow.ToString("yyyy-MM-ddTHH:mm:ss.fffZ")
        thread_id = $ThreadId
        original_path = $OriginalPath
        quarantine_path = $QuarantinePath
        summary_path = $SummaryPath
        original_bytes = $OriginalBytes
        original_max_line_chars = $OriginalMaxLineChars
        was_archived = $WasArchived
        lifecycle_tier = $LifecycleTier
        reason = $Reason
        restore_mode = "on_demand"
    } | ConvertTo-Json -Compress
    [System.IO.File]::AppendAllText($sessionQuarantineManifest, $entry + "`n", (New-Object System.Text.UTF8Encoding $false))
    [System.IO.File]::AppendAllText($sessionLifecycleIndex, $entry + "`n", (New-Object System.Text.UTF8Encoding $false))
}

function Test-RecentActiveSessionRiskEntry {
    param(
        [string]$ThreadId,
        [int64]$OriginalBytes,
        [string]$Reason
    )
    if (-not (Test-Path -LiteralPath $activeSessionRiskLog)) { return $false }
    $now = [DateTimeOffset]::UtcNow
    foreach ($line in @(Get-Content -LiteralPath $activeSessionRiskLog -Tail 200 -ErrorAction SilentlyContinue)) {
        try {
            $entry = $line | ConvertFrom-Json
            if ([string]$entry.thread_id -ne $ThreadId) { continue }
            if ([string]$entry.reason -ne $Reason) { continue }
            # Active transcripts can keep growing; suppress by thread and reason, not byte-exact size.
            $timestampMatch = [regex]::Match($line, '"timestamp"\s*:\s*"([^"]+)"')
            $timestampText = if ($timestampMatch.Success) { $timestampMatch.Groups[1].Value } else { [string]$entry.timestamp }
            $ts = [DateTimeOffset]::Parse($timestampText)
            if (($now - $ts).TotalSeconds -lt $activeSessionRiskSuppressSeconds) { return $true }
        } catch {
            continue
        }
    }
    return $false
}

function Add-ActiveSessionRiskEntry {
    param(
        [string]$ThreadId,
        [string]$OriginalPath,
        [int64]$OriginalBytes,
        [int]$OriginalMaxLineChars,
        [bool]$HasTerminalMarker,
        [bool]$HasInterruptedMarker,
        [double]$IdleSeconds,
        [string]$LifecycleTier,
        [string]$Reason
    )
    if (Test-RecentActiveSessionRiskEntry -ThreadId $ThreadId -OriginalBytes $OriginalBytes -Reason $Reason) {
        return
    }
    Assert-CodexPlusPlusProfileWriteBoundary -Paths @($activeSessionRiskLog, $sessionLifecycleIndex) -Reason 'active_session_risk_append'
    $entry = [ordered]@{
        schema = "codexpp_active_session_risk.v1"
        timestamp = [DateTimeOffset]::UtcNow.ToString("yyyy-MM-ddTHH:mm:ss.fffZ")
        thread_id = $ThreadId
        original_path = $OriginalPath
        original_bytes = $OriginalBytes
        original_max_line_chars = $OriginalMaxLineChars
        was_archived = $false
        lifecycle_tier = $LifecycleTier
        reason = $Reason
        action = "record_only"
        protected = $true
        idle_seconds = [Math]::Round($IdleSeconds, 3)
        protection_seconds = $activeSessionProtectionSeconds
        terminal_marker = $HasTerminalMarker
        interrupted_marker = $HasInterruptedMarker
    } | ConvertTo-Json -Compress
    [System.IO.File]::AppendAllText($activeSessionRiskLog, $entry + "`n", (New-Object System.Text.UTF8Encoding $false))
    [System.IO.File]::AppendAllText($sessionLifecycleIndex, $entry + "`n", (New-Object System.Text.UTF8Encoding $false))
}

function Write-SafeSessionStub {
    param(
        [string]$Path,
        [string]$ThreadId,
        [string]$Title,
        [string]$OriginalPath,
        [string]$SummaryPath,
        [int64]$OriginalBytes,
        [int]$OriginalMaxLineChars,
        [string]$LifecycleTier,
        [string]$Reason
    )
    $now = [DateTimeOffset]::UtcNow.ToString("yyyy-MM-ddTHH:mm:ss.fffZ")
    $safeTitle = if ([string]::IsNullOrWhiteSpace($Title)) { "Quarantined oversized Codex++ session" } else { $Title }
    if ($safeTitle.Length -gt 120) { $safeTitle = $safeTitle.Substring(0, 117) + "..." }
    $restoreCommand = Get-ColdSessionRestoreCommand -ThreadId $ThreadId
    $message = "This Codex++ session is in cold storage because its JSONL transcript exceeded the renderer-safe lifecycle budget. You can safely open and continue this thread from this stub. If prior context is needed, use the restore command to read the summary or cold transcript in chunks instead of loading the full transcript into the renderer. Restore command: $restoreCommand. Lifecycle tier: $LifecycleTier. Reason: $Reason. Original transcript: $OriginalPath. Summary: $SummaryPath. Original bytes: $OriginalBytes. Max line chars: $OriginalMaxLineChars. This does not affect workspace code or Git history."
    $line1 = New-RendererSafeSessionMetaLine -ThreadId $ThreadId -Timestamp $now
    $line2 = '{"timestamp":' + (Get-JsonString $now) + ',"type":"event_msg","payload":{"type":"agent_message","message":' + (Get-JsonString $message) + '}}'
    $line3 = '{"timestamp":' + (Get-JsonString $now) + ',"type":"response_item","payload":{"type":"message","role":"assistant","content":[{"type":"output_text","text":' + (Get-JsonString $message) + '}]}}'
    Write-Utf8NoBom -Path $Path -Text (($line1, $line2, $line3) -join "`n")
}

function Get-SqlString {
    param([string]$Value)
    return "'" + ([string]$Value).Replace("'", "''") + "'"
}

function Sanitize-OversizedSessionFiles {
    if (-not (Test-Path -LiteralPath $stateDb)) { return 0 }
    # Materialize the evidence surface before the lifecycle lock can short-circuit
    # destructive work.  A locked test or active session must still leave a
    # real, empty risk log so readers can distinguish "no risk" from "maintenance
    # never ran".
    Assert-CodexPlusPlusProfileWriteBoundary -Paths @($sessionQuarantineRoot) -Reason 'risk_evidence_setup'
    New-Item -ItemType Directory -Path $sessionQuarantineRoot -Force | Out-Null
    if (-not (Test-Path -LiteralPath $activeSessionRiskLog -PathType Leaf)) {
        Write-Utf8NoBom -Path $activeSessionRiskLog -Text ""
    }
    if ((-not $BypassIdleBudget) -and (Test-SessionLifecycleTestLock)) { return 0 }
    Assert-CodexPlusPlusProfileWriteBoundary -Paths @($sessionQuarantineRoot, $sessionSummaryRoot) -Reason 'sanitize_setup'
    New-Item -ItemType Directory -Path $sessionSummaryRoot -Force | Out-Null
    $sql = "SELECT id || char(9) || archived || char(9) || rollout_path || char(9) || title FROM threads WHERE rollout_path LIKE '%.jsonl' AND (instr(rollout_path, '\sessions\') > 0 OR instr(rollout_path, '\archived_sessions\') > 0);"
    $rows = & $sqlite $stateDb $sql
    $changed = 0
    foreach ($row in $rows) {
        $parts = ([string]$row).Split("`t", 4)
        if ($parts.Count -lt 3) { continue }
        $threadId = $parts[0]
        $wasArchived = ([string]$parts[1] -eq "1")
        $path = Convert-CodexPlusPlusProfilePathToCanonical -Path $parts[2]
        $title = if ($parts.Count -ge 4) { $parts[3] } else { "" }
        if (-not (Test-CodexPlusPlusSessionSourcePathDescriptor -Path $path -SessionRoot $canonicalSessionRoot -ArchivedSessionRoot $canonicalArchivedSessionRoot)) { continue }
        if (-not (Test-Path -LiteralPath $path)) { continue }
        Assert-CodexPlusPlusProfileAlias -Reason 'sanitize_session_source_read'
        [void](Assert-CodexPlusPlusExistingPathChainPhysical -Path $path -Label 'sanitize session source read')
        $item = Get-Item -LiteralPath $path
        $idleSeconds = ((Get-Date) - $item.LastWriteTime).TotalSeconds
        $hasTerminalMarker = Test-CompletedSessionFile -Path $path
        $hasInterruptedMarker = Test-InterruptedSessionFile -Path $path
        $requiredIdleSeconds = if ($hasTerminalMarker) { $completedSessionIdleSeconds } else { $minSessionIdleSeconds }
        if ((-not $BypassIdleBudget) -and $idleSeconds -lt $requiredIdleSeconds) { continue }
        if ((-not $wasArchived) -and (-not $hasTerminalMarker) -and (-not $hasInterruptedMarker) -and (-not $BypassIdleBudget) -and $idleSeconds -lt $staleIncompleteSessionSeconds) { continue }
        if ((-not $BypassIdleBudget) -and (-not $hasTerminalMarker) -and $idleSeconds -lt $staleIncompleteSessionSeconds) { continue }
        $reason = if ($hasTerminalMarker) { "terminal_oversized_transcript" } elseif ((-not $wasArchived) -and $hasInterruptedMarker) { "interrupted_active_oversized_transcript" } else { "stale_incomplete_oversized_transcript" }
        $lifecycleTier = "cold"
        $maxLine = 0
        if ($item.Length -le $maxSessionFileBytes) {
            $maxLine = Get-MaxLineLength -Path $path
            if ($maxLine -lt 0) { continue }
            if ($maxLine -le $maxSessionLineChars) { continue }
        } else {
            $maxLine = Get-MaxLineLength -Path $path
            if ($maxLine -lt 0) { continue }
        }
        if (-not $wasArchived) {
            if ($idleSeconds -lt $activeSessionProtectionSeconds) {
                # An unarchived session may still be in flight. The explicit
                # idle bypass can force inspection, but it must never bypass
                # this safety boundary: record the risk only, never move it.
                Add-ActiveSessionRiskEntry -ThreadId $threadId -OriginalPath $path -OriginalBytes $item.Length -OriginalMaxLineChars $maxLine -HasTerminalMarker $hasTerminalMarker -HasInterruptedMarker $hasInterruptedMarker -IdleSeconds $idleSeconds -LifecycleTier "active_unarchived_recent" -Reason "${reason}_record_only"
                continue
            }
            # Older than the protection window and still oversized: freezing
            # the renderer at startup is worse than cold-storing the thread.
            # Fall through into the same quarantine path archived transcripts
            # use; the transcript stays restorable from the quarantine path.
            $lifecycleTier = "active_unarchived_stale"
            $reason = "active_stale_oversized_transcript"
        }
        $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
        $dest = Join-Path $sessionQuarantineRoot ("$stamp-$threadId.jsonl")
        $summaryPath = Join-Path $sessionSummaryRoot ("$stamp-$threadId.summary.json")
        if (-not (Test-CodexPlusPlusPathWithinRoot -Path $dest -Root $sessionQuarantineRoot) -or
            -not (Test-CodexPlusPlusPathWithinRoot -Path $summaryPath -Root $sessionSummaryRoot)) {
            throw "Refusing Codex++ quarantine path escape for thread: $threadId"
        }
        $summary = New-SessionLifecycleSummary -Path $path -ThreadId $threadId -Title $title -OriginalPath $path -QuarantinePath $dest -OriginalBytes $item.Length -OriginalMaxLineChars $maxLine -LifecycleTier $lifecycleTier -Reason $reason
        Assert-CodexPlusPlusProfileWriteBoundary -Paths @($path, $dest, $summaryPath) -Reason 'sanitize_session_move'
        try {
            Move-Item -LiteralPath $path -Destination $dest -Force
        } catch {
            Assert-CodexPlusPlusProfileWriteBoundary -Paths @($path, $dest) -Reason 'sanitize_session_copy_fallback'
            Copy-Item -LiteralPath $path -Destination $dest -Force
        }
        try {
            Write-SessionLifecycleSummary -SummaryPath $summaryPath -Summary $summary
            Write-SafeSessionStub -Path $path -ThreadId $threadId -Title $title -OriginalPath $dest -SummaryPath $summaryPath -OriginalBytes $item.Length -OriginalMaxLineChars $maxLine -LifecycleTier $lifecycleTier -Reason $reason
            Add-QuarantineManifestEntry -ThreadId $threadId -OriginalPath $path -QuarantinePath $dest -SummaryPath $summaryPath -OriginalBytes $item.Length -OriginalMaxLineChars $maxLine -WasArchived $wasArchived -LifecycleTier $lifecycleTier -Reason $reason
            if (-not $wasArchived) {
                $restoreCommand = Get-ColdSessionRestoreCommand -ThreadId $threadId
                $resumeHint = "Continue this Codex++ session from the safe stub. Restore command: $restoreCommand. Summary: $summaryPath. Cold transcript: $dest. Read the cold transcript in chunks only when prior context is needed."
                Assert-CodexPlusPlusProfileWriteBoundary -Paths @($stateDb) -Reason 'sanitize_session_state_commit'
                & $sqlite $stateDb ("PRAGMA busy_timeout = 2000; UPDATE threads SET archived = 0, archived_at = NULL, has_user_event = 1, first_user_message = " + (Get-SqlString $resumeHint) + " WHERE id = " + (Get-SqlString $threadId) + ";") | Out-Null
            }
            $changed++
        } catch {
            continue
        }
    }
    return $changed
}

function Normalize-SessionPaths {
    if (-not (Test-Path -LiteralPath $stateDb)) { return 0 }
    Assert-CodexPlusPlusProfileWriteBoundary -Paths @($stateDb) -Reason 'normalize_state_db'
    $sql = @"
PRAGMA busy_timeout = 2000;
-- rollout_path is owned by co.Arconte112.session-path-normalizer.
DROP TRIGGER IF EXISTS codexpp_normalize_thread_cwd_ai;
DROP TRIGGER IF EXISTS codexpp_normalize_thread_cwd_au;
DROP TRIGGER IF EXISTS codexpp_normalize_thread_title_ai;
DROP TRIGGER IF EXISTS codexpp_normalize_thread_title_au;
DROP TRIGGER IF EXISTS codexpp_normalize_thread_preview_ai;
DROP TRIGGER IF EXISTS codexpp_normalize_thread_preview_au;
DROP TRIGGER IF EXISTS codexpp_fill_blank_thread_title_ai;
DROP TRIGGER IF EXISTS codexpp_fill_blank_thread_title_au;
DROP TRIGGER IF EXISTS codexpp_archive_large_thread_ai;
DROP TRIGGER IF EXISTS codexpp_archive_large_thread_au;
CREATE TRIGGER IF NOT EXISTS codexpp_normalize_thread_cwd_ai
AFTER INSERT ON threads
WHEN substr(NEW.cwd, 1, 4) = '\\?\'
  AND substr(NEW.cwd, 6, 2) = ':\'
BEGIN
  UPDATE threads
  SET cwd = substr(NEW.cwd, 5)
  WHERE id = NEW.id;
END;
CREATE TRIGGER IF NOT EXISTS codexpp_normalize_thread_cwd_au
AFTER UPDATE OF cwd ON threads
WHEN substr(NEW.cwd, 1, 4) = '\\?\'
  AND substr(NEW.cwd, 6, 2) = ':\'
BEGIN
  UPDATE threads
  SET cwd = substr(NEW.cwd, 5)
  WHERE id = NEW.id;
END;
CREATE TRIGGER IF NOT EXISTS codexpp_normalize_thread_title_ai
AFTER INSERT ON threads
WHEN length(trim(replace(replace(NEW.title, char(13), ' '), char(10), ' '))) > $maxThreadTitleLength
  OR instr(NEW.title, char(13)) > 0
  OR instr(NEW.title, char(10)) > 0
BEGIN
  UPDATE threads
  SET title = CASE
    WHEN length(trim(replace(replace(NEW.title, char(13), ' '), char(10), ' '))) > $maxThreadTitleLength
      THEN substr(trim(replace(replace(NEW.title, char(13), ' '), char(10), ' ')), 1, $($maxThreadTitleLength - 3)) || '...'
    ELSE trim(replace(replace(NEW.title, char(13), ' '), char(10), ' '))
  END
  WHERE id = NEW.id;
END;
CREATE TRIGGER IF NOT EXISTS codexpp_normalize_thread_title_au
AFTER UPDATE OF title ON threads
WHEN length(trim(replace(replace(NEW.title, char(13), ' '), char(10), ' '))) > $maxThreadTitleLength
  OR instr(NEW.title, char(13)) > 0
  OR instr(NEW.title, char(10)) > 0
BEGIN
  UPDATE threads
  SET title = CASE
    WHEN length(trim(replace(replace(NEW.title, char(13), ' '), char(10), ' '))) > $maxThreadTitleLength
      THEN substr(trim(replace(replace(NEW.title, char(13), ' '), char(10), ' ')), 1, $($maxThreadTitleLength - 3)) || '...'
    ELSE trim(replace(replace(NEW.title, char(13), ' '), char(10), ' '))
  END
  WHERE id = NEW.id;
END;
CREATE TRIGGER IF NOT EXISTS codexpp_normalize_thread_preview_ai
AFTER INSERT ON threads
WHEN length(trim(replace(replace(NEW.preview, char(13), ' '), char(10), ' '))) > $maxThreadPreviewLength
  OR instr(NEW.preview, char(13)) > 0
  OR instr(NEW.preview, char(10)) > 0
BEGIN
  UPDATE threads
  SET preview = CASE
    WHEN length(trim(replace(replace(NEW.preview, char(13), ' '), char(10), ' '))) > $maxThreadPreviewLength
      THEN substr(trim(replace(replace(NEW.preview, char(13), ' '), char(10), ' ')), 1, $($maxThreadPreviewLength - 3)) || '...'
    ELSE trim(replace(replace(NEW.preview, char(13), ' '), char(10), ' '))
  END
  WHERE id = NEW.id;
END;
CREATE TRIGGER IF NOT EXISTS codexpp_normalize_thread_preview_au
AFTER UPDATE OF preview ON threads
WHEN length(trim(replace(replace(NEW.preview, char(13), ' '), char(10), ' '))) > $maxThreadPreviewLength
  OR instr(NEW.preview, char(13)) > 0
  OR instr(NEW.preview, char(10)) > 0
BEGIN
  UPDATE threads
  SET preview = CASE
    WHEN length(trim(replace(replace(NEW.preview, char(13), ' '), char(10), ' '))) > $maxThreadPreviewLength
      THEN substr(trim(replace(replace(NEW.preview, char(13), ' '), char(10), ' ')), 1, $($maxThreadPreviewLength - 3)) || '...'
    ELSE trim(replace(replace(NEW.preview, char(13), ' '), char(10), ' '))
  END
  WHERE id = NEW.id;
END;
CREATE TRIGGER IF NOT EXISTS codexpp_fill_blank_thread_title_ai
AFTER INSERT ON threads
WHEN length(trim(NEW.title)) = 0
  AND length(trim(replace(replace(NEW.preview, char(13), ' '), char(10), ' '))) > 0
BEGIN
  UPDATE threads
  SET title = CASE
    WHEN length(trim(replace(replace(NEW.preview, char(13), ' '), char(10), ' '))) > $maxThreadTitleLength
      THEN substr(trim(replace(replace(NEW.preview, char(13), ' '), char(10), ' ')), 1, $($maxThreadTitleLength - 3)) || '...'
    ELSE trim(replace(replace(NEW.preview, char(13), ' '), char(10), ' '))
  END
  WHERE id = NEW.id;
END;
CREATE TRIGGER IF NOT EXISTS codexpp_fill_blank_thread_title_au
AFTER UPDATE OF title, preview ON threads
WHEN length(trim(NEW.title)) = 0
  AND length(trim(replace(replace(NEW.preview, char(13), ' '), char(10), ' '))) > 0
BEGIN
  UPDATE threads
  SET title = CASE
    WHEN length(trim(replace(replace(NEW.preview, char(13), ' '), char(10), ' '))) > $maxThreadTitleLength
      THEN substr(trim(replace(replace(NEW.preview, char(13), ' '), char(10), ' ')), 1, $($maxThreadTitleLength - 3)) || '...'
    ELSE trim(replace(replace(NEW.preview, char(13), ' '), char(10), ' '))
  END
  WHERE id = NEW.id;
END;
UPDATE threads
SET cwd = substr(cwd, 5)
WHERE substr(cwd, 1, 4) = '\\?\'
  AND substr(cwd, 6, 2) = ':\';
UPDATE threads
SET title = CASE
  WHEN length(trim(replace(replace(title, char(13), ' '), char(10), ' '))) > $maxThreadTitleLength
    THEN substr(trim(replace(replace(title, char(13), ' '), char(10), ' ')), 1, $($maxThreadTitleLength - 3)) || '...'
  ELSE trim(replace(replace(title, char(13), ' '), char(10), ' '))
END
WHERE length(trim(replace(replace(title, char(13), ' '), char(10), ' '))) > $maxThreadTitleLength
  OR instr(title, char(13)) > 0
  OR instr(title, char(10)) > 0;
UPDATE threads
SET preview = CASE
  WHEN length(trim(replace(replace(preview, char(13), ' '), char(10), ' '))) > $maxThreadPreviewLength
    THEN substr(trim(replace(replace(preview, char(13), ' '), char(10), ' ')), 1, $($maxThreadPreviewLength - 3)) || '...'
  ELSE trim(replace(replace(preview, char(13), ' '), char(10), ' '))
END
WHERE length(trim(replace(replace(preview, char(13), ' '), char(10), ' '))) > $maxThreadPreviewLength
  OR instr(preview, char(13)) > 0
  OR instr(preview, char(10)) > 0;
UPDATE threads
SET title = CASE
  WHEN length(trim(replace(replace(preview, char(13), ' '), char(10), ' '))) > $maxThreadTitleLength
    THEN substr(trim(replace(replace(preview, char(13), ' '), char(10), ' ')), 1, $($maxThreadTitleLength - 3)) || '...'
  ELSE trim(replace(replace(preview, char(13), ' '), char(10), ' '))
END
WHERE length(trim(title)) = 0
  AND length(trim(replace(replace(preview, char(13), ' '), char(10), ' '))) > 0;
SELECT changes();
"@
    Assert-CodexPlusPlusProfileWriteBoundary -Paths @($stateDb) -Reason 'normalize_state_db_commit'
    $result = & $sqlite $stateDb $sql
    $last = ($result | Select-Object -Last 1)
    $changed = 0
    if ([int]::TryParse([string]$last, [ref]$changed)) { return $changed }
    return 0
}

function Invoke-CodexPlusPlusSessionMaintenanceBatch {
    Assert-CodexPlusPlusProfileAlias -Reason 'session_maintenance_batch'
    [void](Normalize-SessionPaths)
    Assert-CodexPlusPlusProfileAlias -Reason 'session_maintenance_between_write_batches'
    [void](Sanitize-OversizedSessionFiles)
}

foreach ($dependency in @($sqlitePython, $sqliteHelper)) {
    [void](Assert-CodexPlusPlusExistingPathChainPhysical -Path $dependency -Label 'fixed sqlite dependency')
}
$sqliteSelfTest = @(& $sqlitePython $sqliteHelper --self-test 2>&1)
if ($LASTEXITCODE -ne 0 -or ($sqliteSelfTest -join "`n") -notmatch 'CODEXPP_SQLITE_HELPER_SELF_TEST_PASS') {
    throw "Codex++ fixed sqlite helper self-test failed: $($sqliteSelfTest -join ' ')"
}

Invoke-CodexPlusPlusSessionMaintenanceBatch
exit 0
