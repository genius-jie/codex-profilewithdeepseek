#requires -Version 7.0

$ErrorActionPreference = "Stop"

$reader = "@@LAUNCHER_ROOT:win@@\Read-CodexPlusPlusColdSession.ps1"
if (-not (Test-Path -LiteralPath $reader)) {
    throw "Cold session reader not found: $reader"
}

$root = Join-Path ([System.IO.Path]::GetTempPath()) ("codexpp-cold-reader-" + [Guid]::NewGuid().ToString("N"))
$summaryRoot = Join-Path $root "summaries"
$threadId = "00000000-0000-4000-8000-000000009001"
$quarantinePath = Join-Path $root ("20260523-" + $threadId + ".jsonl")
$summaryPath = Join-Path $summaryRoot ("20260523-" + $threadId + ".summary.json")
$manifestPath = Join-Path $root "manifest.jsonl"

try {
    New-Item -ItemType Directory -Path $summaryRoot -Force | Out-Null

    $lines = @(
        ('{"timestamp":"2099-01-01T00:00:00.000Z","type":"session_meta","payload":{"id":"' + $threadId + '","source":"test","title":"reader probe"}}'),
        '{"timestamp":"2099-01-01T00:00:01.000Z","type":"response_item","payload":{"type":"message","role":"user","content":[{"type":"input_text","text":"first user message"}]}}',
        '{"timestamp":"2099-01-01T00:00:02.000Z","type":"response_item","payload":{"type":"message","role":"assistant","content":[{"type":"output_text","text":"assistant reply"}]}}',
        '{"timestamp":"2099-01-01T00:00:03.000Z","type":"event_msg","payload":{"type":"task_complete","turn_id":"probe"}}'
    )
    [System.IO.File]::WriteAllLines($quarantinePath, [string[]]$lines, (New-Object System.Text.UTF8Encoding $false))

    $summary = [ordered]@{
        schema = "codexpp_session_lifecycle.v1"
        thread_id = $threadId
        title = "reader probe"
        lifecycle_tier = "cold"
        reason = "terminal_oversized_transcript"
        quarantine_path = $quarantinePath
        line_count = $lines.Count
        first_user_preview = "first user message"
        last_assistant_preview = "assistant reply"
        restore = [ordered]@{
            mode = "on_demand"
            instruction = "read in chunks"
        }
    } | ConvertTo-Json -Depth 8
    [System.IO.File]::WriteAllText($summaryPath, $summary + "`n", (New-Object System.Text.UTF8Encoding $false))

    $manifest = [ordered]@{
        schema = "codexpp_session_lifecycle_manifest.v1"
        timestamp = "2099-01-01T00:00:04.000Z"
        thread_id = $threadId
        quarantine_path = $quarantinePath
        summary_path = $summaryPath
        original_bytes = (Get-Item -LiteralPath $quarantinePath).Length
        lifecycle_tier = "cold"
        reason = "terminal_oversized_transcript"
        restore_mode = "on_demand"
    } | ConvertTo-Json -Compress
    [System.IO.File]::WriteAllText($manifestPath, $manifest + "`n", (New-Object System.Text.UTF8Encoding $false))

    $summaryOutput = (& $reader -QuarantineRoot $root -ThreadId $threadId -Mode Summary) -join "`n"
    $summaryJson = $summaryOutput | ConvertFrom-Json
    if ($summaryJson.thread_id -ne $threadId -or $summaryJson.restore.mode -ne "on_demand") {
        throw "Summary reader failed: thread=$($summaryJson.thread_id) restore=$($summaryJson.restore.mode)"
    }

    $chunk = @(& $reader -QuarantineRoot $root -ThreadId $threadId -Mode Chunk -StartLine 2 -MaxLines 2 -MaxCharsPerLine 400)
    if ($chunk.Count -ne 2 -or $chunk[0] -notlike "2`t*" -or $chunk[1] -notlike "3`t*") {
        throw "Chunk reader failed: $($chunk -join ' | ')"
    }

    $tail = @(& $reader -QuarantineRoot $root -ThreadId $threadId -Mode Tail -MaxLines 2 -MaxCharsPerLine 400)
    if ($tail.Count -ne 2 -or $tail[0] -notlike "3`t*" -or $tail[1] -notlike "4`t*") {
        throw "Tail reader failed: $($tail -join ' | ')"
    }

    $restore = (& $reader -QuarantineRoot $root -ThreadId $threadId -Mode Restore -StartLine 2 -MaxLines 2) -join "`n"
    if (-not $restore.Contains($threadId) -or -not $restore.Contains("-Mode Summary") -or -not $restore.Contains("-Mode Chunk")) {
        throw "Restore command output failed: $restore"
    }

    Write-Output "PASS Codex++ cold session reader resolves summary, chunks, tail, and restore commands"
} finally {
    Remove-Item -LiteralPath $root -Recurse -Force -ErrorAction SilentlyContinue
}
