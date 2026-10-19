#requires -Version 7.0

param(
    [string]$ThreadId = "",
    [string]$SummaryPath = "",
    [string]$QuarantinePath = "",
    [ValidateSet("Summary", "Chunk", "Tail", "Restore")]
    [string]$Mode = "Summary",
    [int]$StartLine = 1,
    [int]$MaxLines = 80,
    [int]$MaxCharsPerLine = 1200,
    [string]$QuarantineRoot = ""
)

$ErrorActionPreference = "Stop"

$codexHome = "@@CODEXPP_HOME:win@@"
$defaultQuarantineRoot = Join-Path $codexHome "quarantined_sessions"
$canonicalProfileRoot = '@@CODEXPP_PROFILE:win@@'
$legacyProfileRoot = '@@USERPROFILE:win@@\AppData\Roaming\CodexPlusPlusProfile'
$legacyCodexHome = '@@PROFILE_REPO:win@@'
if ([string]::IsNullOrWhiteSpace($QuarantineRoot)) { $QuarantineRoot = $defaultQuarantineRoot }
$manifestPath = Join-Path $QuarantineRoot "manifest.jsonl"
$readerScript = "@@LAUNCHER_ROOT:win@@\Read-CodexPlusPlusColdSession.ps1"

function Resolve-LatestLifecycleEntry {
    param([string]$Id)
    if ([string]::IsNullOrWhiteSpace($Id)) { return $null }
    if (-not (Test-Path -LiteralPath $manifestPath)) { return $null }
    $match = Select-String -LiteralPath $manifestPath -Pattern $Id -SimpleMatch -ErrorAction SilentlyContinue |
        Select-Object -Last 1
    if (-not $match) { return $null }
    return ($match.Line | ConvertFrom-Json)
}

function Resolve-ExistingPath {
    param([string]$Path)
    if ([string]::IsNullOrWhiteSpace($Path)) { return "" }
    $literal = [string]$Path
    if ($literal.StartsWith('\\?\')) { $literal = $literal.Substring(4) }
    if ($literal.StartsWith("\\'\") -or $literal.StartsWith('\\"\')) { $literal = $literal.Substring(3) }
    if ($literal.StartsWith($legacyProfileRoot, [StringComparison]::OrdinalIgnoreCase)) {
        $suffix = $literal.Substring($legacyProfileRoot.Length)
        if ($suffix -ieq '\.codex' -or $suffix.StartsWith('\.codex\', [StringComparison]::OrdinalIgnoreCase)) {
            $literal = $codexHome + $suffix.Substring(7)
        } else {
            $literal = $canonicalProfileRoot + $suffix
        }
    } elseif ($literal.StartsWith($legacyCodexHome, [StringComparison]::OrdinalIgnoreCase)) {
        $literal = $codexHome + $literal.Substring($legacyCodexHome.Length)
    }
    if (Test-Path -LiteralPath $literal) { return $literal }
    return $literal
}

function Write-Chunk {
    param(
        [string]$Path,
        [int]$FirstLine,
        [int]$Limit
    )
    $limit = [Math]::Max(1, [Math]::Min($Limit, 200))
    $charLimit = [Math]::Max(200, [Math]::Min($MaxCharsPerLine, 8000))
    $first = [Math]::Max(1, $FirstLine)
    $stream = [System.IO.FileStream]::new(
        $Path,
        [System.IO.FileMode]::Open,
        [System.IO.FileAccess]::Read,
        [System.IO.FileShare]::ReadWrite -bor [System.IO.FileShare]::Delete
    )
    $reader = [System.IO.StreamReader]::new($stream)
    try {
        $lineNumber = 0
        $written = 0
        while (-not $reader.EndOfStream -and $written -lt $limit) {
            $line = $reader.ReadLine()
            $lineNumber++
            if ($lineNumber -lt $first) { continue }
            if ($line.Length -gt $charLimit) {
                $line = $line.Substring(0, $charLimit) + "... [truncated]"
            }
            "{0}`t{1}" -f $lineNumber, $line
            $written++
        }
    } finally {
        $reader.Close()
        $reader.Dispose()
        $stream.Dispose()
    }
}

function Write-Tail {
    param(
        [string]$Path,
        [int]$Limit
    )
    $limit = [Math]::Max(1, [Math]::Min($Limit, 200))
    $charLimit = [Math]::Max(200, [Math]::Min($MaxCharsPerLine, 8000))
    $queue = New-Object System.Collections.Generic.Queue[object]
    $stream = [System.IO.FileStream]::new(
        $Path,
        [System.IO.FileMode]::Open,
        [System.IO.FileAccess]::Read,
        [System.IO.FileShare]::ReadWrite -bor [System.IO.FileShare]::Delete
    )
    $reader = [System.IO.StreamReader]::new($stream)
    try {
        $lineNumber = 0
        while (-not $reader.EndOfStream) {
            $line = $reader.ReadLine()
            $lineNumber++
            if ($line.Length -gt $charLimit) {
                $line = $line.Substring(0, $charLimit) + "... [truncated]"
            }
            $queue.Enqueue([pscustomobject]@{ LineNumber = $lineNumber; Text = $line })
            if ($queue.Count -gt $limit) { [void]$queue.Dequeue() }
        }
    } finally {
        $reader.Close()
        $reader.Dispose()
        $stream.Dispose()
    }
    foreach ($item in $queue) { "{0}`t{1}" -f $item.LineNumber, $item.Text }
}

function Get-PsQuotedString {
    param([string]$Value)
    return "'" + ([string]$Value).Replace("'", "''") + "'"
}

function Write-RestoreCommand {
    param(
        [object]$Summary,
        [string]$ColdPath,
        [string]$ResolvedSummaryPath
    )
    $id = [string]$Summary.thread_id
    $lineCount = [int]($Summary.line_count | ForEach-Object { if ($_ -ne $null) { $_ } else { 0 } })
    $start = [Math]::Max(1, $StartLine)
    $limit = [Math]::Max(1, [Math]::Min($MaxLines, 200))
    $quotedReader = Get-PsQuotedString -Value $readerScript
    $quotedId = Get-PsQuotedString -Value $id

    "Codex++ cold session restore packet"
    "thread_id: $id"
    "title: $($Summary.title)"
    "reason: $($Summary.reason)"
    "summary_path: $ResolvedSummaryPath"
    "quarantine_path: $ColdPath"
    "line_count: $lineCount"
    "first_user_preview: $($Summary.first_user_preview)"
    "last_assistant_preview: $($Summary.last_assistant_preview)"
    ""
    "Restore command:"
    "  & '@@POWERSHELL_EXE:win@@' -NoProfile -File $quotedReader -ThreadId $quotedId -Mode Summary"
    "  & '@@POWERSHELL_EXE:win@@' -NoProfile -File $quotedReader -ThreadId $quotedId -Mode Chunk -StartLine $start -MaxLines $limit"
    "  & '@@POWERSHELL_EXE:win@@' -NoProfile -File $quotedReader -ThreadId $quotedId -Mode Tail -MaxLines $limit"
}

$entry = Resolve-LatestLifecycleEntry -Id $ThreadId
if ($entry) {
    if ([string]::IsNullOrWhiteSpace($SummaryPath)) { $SummaryPath = [string]$entry.summary_path }
    if ([string]::IsNullOrWhiteSpace($QuarantinePath)) { $QuarantinePath = [string]$entry.quarantine_path }
}

$SummaryPath = Resolve-ExistingPath -Path $SummaryPath
$QuarantinePath = Resolve-ExistingPath -Path $QuarantinePath

if ($Mode -eq "Summary" -or $Mode -eq "Restore") {
    if (-not (Test-Path -LiteralPath $SummaryPath)) {
        throw "Cold-session summary not found. Provide -ThreadId or -SummaryPath."
    }
    $summaryJson = Get-Content -LiteralPath $SummaryPath -Raw | ConvertFrom-Json
    if ($Mode -eq "Summary") {
        $summaryJson | ConvertTo-Json -Depth 12
        return
    }
    if (-not (Test-Path -LiteralPath $QuarantinePath)) {
        throw "Cold transcript not found. Provide -ThreadId or -QuarantinePath."
    }
    Write-RestoreCommand -Summary $summaryJson -ColdPath $QuarantinePath -ResolvedSummaryPath $SummaryPath
    return
}

if (-not (Test-Path -LiteralPath $QuarantinePath)) {
    throw "Cold transcript not found. Provide -ThreadId or -QuarantinePath."
}

if ($Mode -eq "Tail") {
    Write-Tail -Path $QuarantinePath -Limit $MaxLines
} else {
    Write-Chunk -Path $QuarantinePath -FirstLine $StartLine -Limit $MaxLines
}
