#requires -Version 7.0

param(
    [string]$Path = (Get-Location).Path,
    [switch]$Json
)

$ErrorActionPreference = "Stop"

function Write-ProbeResult {
    param([pscustomobject]$Result)

    if ($Json) {
        $Result | ConvertTo-Json -Depth 8
        return
    }

    if ($Result.status -eq "NOT_GIT_WORKTREE") {
        Write-Output ("NOT_GIT_WORKTREE path={0}" -f $Result.path)
        return
    }

    Write-Output ("GIT_WORKTREE path={0} git_root={1}" -f $Result.path, $Result.git_root)
    if ($Result.clean) {
        Write-Output "CLEAN"
        return
    }
    $Result.entries | ForEach-Object { Write-Output $_ }
}

$resolvedPath = [System.IO.Path]::GetFullPath($Path)
if (-not (Test-Path -LiteralPath $resolvedPath)) {
    Write-ProbeResult ([pscustomobject]@{
        status = "PATH_NOT_FOUND"
        path = $resolvedPath
        git_root = $null
        clean = $null
        entries = @()
    })
    exit 2
}

$item = Get-Item -LiteralPath $resolvedPath -Force
$probeDir = if ($item.PSIsContainer) { $item.FullName } else { $item.Directory.FullName }

$gitRoot = ""
$gitRootExitCode = 1
try {
    $gitRoot = (& git -C $probeDir rev-parse --show-toplevel 2>$null)
    $gitRootExitCode = $LASTEXITCODE
} catch {
    $gitRoot = ""
    $gitRootExitCode = 1
}

if ($gitRootExitCode -ne 0 -or [string]::IsNullOrWhiteSpace($gitRoot)) {
    Write-ProbeResult ([pscustomobject]@{
        status = "NOT_GIT_WORKTREE"
        path = $probeDir
        git_root = $null
        clean = $null
        entries = @()
    })
    exit 0
}

$entries = @()
$gitStatusExitCode = 0
try {
    $entries = @(& git -C $gitRoot status --short 2>&1)
    $gitStatusExitCode = $LASTEXITCODE
} catch {
    $entries = @($_.Exception.Message)
    $gitStatusExitCode = 1
}
if ($gitStatusExitCode -ne 0) {
    Write-ProbeResult ([pscustomobject]@{
        status = "GIT_STATUS_FAILED"
        path = $probeDir
        git_root = $gitRoot
        clean = $null
        entries = $entries
    })
    exit $gitStatusExitCode
}

Write-ProbeResult ([pscustomobject]@{
    status = "GIT_WORKTREE"
    path = $probeDir
    git_root = $gitRoot
    clean = ($entries.Count -eq 0)
    entries = $entries
})
