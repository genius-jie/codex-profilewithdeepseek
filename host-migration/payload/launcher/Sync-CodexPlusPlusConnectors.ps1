#requires -Version 7.0

# Sync normal Codex Electron connector state into the Codex++ isolated Electron profile.
# This copies app connector runtime state only; it does not copy .codex/auth.json.

param(
    [string]$SourceRoot = "@@USERPROFILE:win@@\AppData\Roaming\Codex",
    # Use the canonical D: profile for writes. The public C: profile is a
    # junction; on this host, creating new sibling backup directories through
    # the junction returns a phantom path and Copy-Item then raises ENOENT.
    [string]$TargetRoot = "@@CODEXPP_PROFILE:win@@\AppData\Roaming\Codex"
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path -LiteralPath $SourceRoot)) {
    Write-Host "Connector sync skipped: source profile not found: $SourceRoot" -ForegroundColor Yellow
    return
}

New-Item -ItemType Directory -Path $TargetRoot -Force | Out-Null

$stamp = Get-Date -Format yyyyMMddHHmmss
$backupRoot = "$TargetRoot.connector-backup-$stamp"
New-Item -ItemType Directory -Path $backupRoot -Force | Out-Null

$items = @(
    "Local Storage",
    "Session Storage",
    "Network",
    "Partitions",
    "blob_storage",
    "Local State",
    "Preferences"
)

function Copy-ConnectorItem {
    param(
        [string]$Name,
        [string]$SourceRoot,
        [string]$TargetRoot,
        [string]$BackupRoot
    )

    $source = Join-Path $SourceRoot $Name
    $target = Join-Path $TargetRoot $Name
    $backup = Join-Path $BackupRoot $Name

    # A connector entry can be a regular file (for example `Local State`).
    # Copy-Item requires the destination parent to exist for that shape;
    # create it explicitly so the sync remains valid for both files and
    # directories.
    New-Item -ItemType Directory -Path (Split-Path -Parent $backup) -Force | Out-Null

    if (-not (Test-Path -LiteralPath $source)) {
        return
    }

    if (Test-Path -LiteralPath $target) {
        if ((Get-Item -LiteralPath $target).PSIsContainer) {
            robocopy $target $backup /E /R:0 /W:0 /NFL /NDL /NJH /NJS /NP | Out-Null
        } else {
            Copy-Item -LiteralPath $target -Destination $backup -Force
        }
    }

    if ((Get-Item -LiteralPath $source).PSIsContainer) {
        robocopy $source $target /E /R:0 /W:0 /NFL /NDL /NJH /NJS /NP | Out-Null
    } else {
        Copy-Item -LiteralPath $source -Destination $target -Force
    }
}

foreach ($item in $items) {
    Copy-ConnectorItem -Name $item -SourceRoot $SourceRoot -TargetRoot $TargetRoot -BackupRoot $backupRoot
}

Write-Host "Connector state synced into Codex++ profile." -ForegroundColor Green
Write-Host "Backup: $backupRoot" -ForegroundColor Cyan
