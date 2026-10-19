#requires -Version 7.0

# Verify expected OpenCLI adapter commands under each profile home.

param(
    [string[]]$Profiles = @(
        "@@USERPROFILE:win@@",
        "@@CODEXPP_PROFILE:win@@"
    ),
    [string]$Site = "dianping",
    [string]$ExpectedCommand = "comments",
    [switch]$Json
)

$ErrorActionPreference = "Stop"

function Invoke-OpenCliHelpForProfile {
    param(
        [string]$Profile,
        [string]$Site,
        [string]$ExpectedCommand
    )

    $oldHome = $env:HOME
    $oldUserProfile = $env:USERPROFILE
    $oldCodexHome = $env:CODEX_HOME
    try {
        $env:HOME = $Profile
        $env:USERPROFILE = $Profile
        $env:CODEX_HOME = Join-Path $Profile ".codex"

        $oldErrorActionPreference = $ErrorActionPreference
        $ErrorActionPreference = "Continue"
        try {
            $output = (& opencli $Site --help 2>&1 | ForEach-Object { "$_" }) -join "`n"
            $exitCode = $LASTEXITCODE
        } finally {
            $ErrorActionPreference = $oldErrorActionPreference
        }
        $commands = @()
        foreach ($match in [regex]::Matches($output, "(?m)^\s*([a-z][a-z0-9_-]*)\s+<")) {
            $command = $match.Groups[1].Value
            if ($commands -notcontains $command) { $commands += $command }
        }
        [pscustomobject]@{
            profile = $Profile
            site = $Site
            exit_code = $exitCode
            commands = $commands
            expected_command = $ExpectedCommand
            expected_available = ($commands -contains $ExpectedCommand)
            help_excerpt = (($output -split "`r?`n") | Select-Object -First 12) -join "`n"
        }
    } finally {
        $env:HOME = $oldHome
        $env:USERPROFILE = $oldUserProfile
        if ($null -eq $oldCodexHome) {
            Remove-Item Env:\CODEX_HOME -ErrorAction SilentlyContinue
        } else {
            $env:CODEX_HOME = $oldCodexHome
        }
    }
}

$results = foreach ($profile in $Profiles) {
    Invoke-OpenCliHelpForProfile -Profile $profile -Site $Site -ExpectedCommand $ExpectedCommand
}

if ($Json) {
    $results | ConvertTo-Json -Depth 5
} else {
    $results | Select-Object profile, site, exit_code, expected_command, expected_available, commands | Format-Table -AutoSize
}

if ($results | Where-Object { -not $_.expected_available }) {
    exit 1
}
