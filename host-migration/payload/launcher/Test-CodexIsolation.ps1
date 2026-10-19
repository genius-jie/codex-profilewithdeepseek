#requires -Version 7.0

# Verify Codex / Codex++ profile isolation without printing secrets.

$normal = "@@CODEX_HOME:win@@"
$plus = "@@CODEXPP_HOME:win@@"
$normalElectron = "@@USERPROFILE:win@@\AppData\Roaming\Codex\.codex"
$plusElectron = "@@CODEXPP_HOME:win@@"
$powerShell7 = '@@POWERSHELL_EXE:win@@'
$projectionWriter = '@@GENERAL_ROOT:win@@\tooling\Sync-HostCapabilityProjection.ps1'

function Get-SkillLinkCount {
    param([string]$SkillsPath)

    if (-not (Test-Path -LiteralPath $SkillsPath)) {
        return 0
    }

    return @(
        Get-ChildItem -LiteralPath $SkillsPath -Force |
            Where-Object { $_.LinkType -eq "Junction" -or $_.LinkType -eq "SymbolicLink" }
    ).Count
}

function Get-PathSummary {
    param([string]$Path)

    if (-not (Test-Path -LiteralPath $Path)) {
        return "missing"
    }

    $item = Get-Item -LiteralPath $Path -Force
    if ($item.PSIsContainer) {
        $target = $item.Target
        if ($target) {
            return "dir -> $target"
        }
        return "dir"
    }

    $hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $Path).Hash.Substring(0, 12)
    return "file, $($item.Length) bytes, sha256:$hash"
}

function Get-ProjectionCheck {
    param([string]$HostId, [string]$SkillsPath)

    if (-not (Test-Path -LiteralPath $powerShell7 -PathType Leaf) -or
        -not (Test-Path -LiteralPath $projectionWriter -PathType Leaf)) {
        return [pscustomobject]@{ Pass = $false; Summary = 'PowerShell 7 or General projection writer is missing' }
    }
    $raw = @(& $powerShell7 -NoLogo -NoProfile -NonInteractive -File $projectionWriter -HostId $HostId -SkillsRoot $SkillsPath -Mode Check 2>&1)
    $exitCode = $LASTEXITCODE
    $payload = $null
    try { $payload = $raw[-1] | ConvertFrom-Json -ErrorAction Stop } catch { }
    $summary = if ($payload) {
        "selected=$($payload.selected_count), unchanged=$($payload.unchanged_count), missing=$($payload.missing_count), collisions=$($payload.collision_count)"
    } else {
        ($raw -join "`n")
    }
    return [pscustomobject]@{ Pass = ($exitCode -eq 0); Summary = $summary }
}

function Get-CodexPlusPlusProxyAuthCheck {
    param([string]$AuthPath, [string]$ConfigPath)

    if (-not (Test-Path -LiteralPath $AuthPath -PathType Leaf) -or
        -not (Test-Path -LiteralPath $ConfigPath -PathType Leaf)) {
        return [pscustomobject]@{
            Pass = $false
            Summary = 'auth.json or config.toml is missing'
        }
    }

    try {
        $auth = Get-Content -LiteralPath $AuthPath -Raw | ConvertFrom-Json -ErrorAction Stop
        $configText = Get-Content -LiteralPath $ConfigPath -Raw
        $providerMatch = [regex]::Match(
            $configText,
            '(?ms)^\s*\[model_providers\.cm\]\s*(?<body>.*?)(?=^\s*\[|\z)'
        )
        $keyMatch = if ($providerMatch.Success) {
            [regex]::Match(
                $providerMatch.Groups['body'].Value,
                '(?m)^\s*api_key\s*=\s*["''](?<value>[^"'']*)["'']\s*$'
            )
        } else {
            $null
        }
        $authKey = [string]$auth.OPENAI_API_KEY
        $configKey = if ($keyMatch -and $keyMatch.Success) {
            [string]$keyMatch.Groups['value'].Value
        } else {
            ''
        }
        $providerSelected = [regex]::IsMatch(
            $configText,
            '(?m)^\s*model_provider\s*=\s*["'']cm["'']\s*$'
        )
        if (-not $providerSelected) {
            $modeOk = ([string]$auth.auth_mode -eq 'chatgpt')
            $hasTokens = ($null -ne $auth.tokens)
            return [pscustomobject]@{
                Pass = ($modeOk -and $hasTokens)
                Mode = 'chatgpt'
                Summary = "official account mode; auth_mode=chatgpt:$modeOk; tokens_present:$hasTokens"
            }
        }
        $providerBody = if ($providerMatch.Success) { $providerMatch.Groups['body'].Value } else { '' }
        $modelMatch = [regex]::Match(
            $configText,
            '(?m)^\s*model\s*=\s*["''](?<value>[^"'']+)["'']\s*$'
        )
        $model = if ($modelMatch.Success) { [string]$modelMatch.Groups['value'].Value } else { '' }
        # DeepSeek/Kimi are exposed by CodexManager as Chat Completions-only
        # models.  Their Responses compatibility is intentionally provided by
        # the local 15740 overlay; native models may still use the 48760
        # gateway directly.  Keep this self-check aligned with the selected
        # model instead of treating one transport as globally valid.
        $chatOnlyModel = $model -in @('deepseek-v4-pro', 'kimi-k3')
        $envKeyAbsent = -not [regex]::IsMatch($providerBody, '(?m)^\s*env_key\s*=')
        $wireApiIsResponses = [regex]::IsMatch(
            $providerBody,
            '(?m)^\s*wire_api\s*=\s*["'']responses["'']\s*$'
        )
        $baseUrlMatch = [regex]::Match(
            $providerBody,
            '(?m)^\s*base_url\s*=\s*["''](?<value>[^"'']+)["'']\s*$'
        )
        # Codex++ uses one 15740 ingress for every model. DeepSeek/Kimi are
        # translated there; native models such as GPT-6A pass through it so
        # model switching keeps the same ID and lifecycle boundary.
        $expectedBaseUrl = 'http://127.0.0.1:15740/v1'
        $baseUrlOk = ($baseUrlMatch.Success -and $baseUrlMatch.Groups['value'].Value -eq $expectedBaseUrl)
        $wireApiOk = if ($chatOnlyModel) { $wireApiIsResponses } else { -not $wireApiIsResponses }
        $authFields = @($auth.PSObject.Properties.Name)
        $oauthFieldsAbsent = @($authFields | Where-Object {
            $_ -in @('tokens', 'access_token', 'refresh_token', 'id_token', 'account_id', 'last_refresh')
        }).Count -eq 0
        $modeOk = ([string]$auth.auth_mode -eq 'apikey')
        # Current Codex++ proxy mode keeps the secret in auth.json and leaves
        # config.toml free of a duplicate api_key.  Accept either the legacy
        # mirrored form or the single-source auth.json form.
        $mirrorOk = if ($configKey.Length -eq 0) {
            $authKey.Length -gt 0
        } else {
            ($authKey.Length -gt 0 -and $authKey -ceq $configKey)
        }
        $keySource = if ($configKey.Length -eq 0) { 'auth.json' } else { 'auth.json+config.toml' }
        return [pscustomobject]@{
            Pass = ($modeOk -and $mirrorOk -and $providerSelected -and $envKeyAbsent -and
                $wireApiOk -and $baseUrlOk -and $oauthFieldsAbsent)
            Summary = "exists; auth_mode=apikey:$modeOk; key_source=$keySource; key_mirror_match=$mirrorOk; key_length=$($authKey.Length); provider_cm=$providerSelected; model=$model; chat_only_model=$chatOnlyModel; expected_base_url=$expectedBaseUrl; base_url_ok=$baseUrlOk; wire_api_ok=$wireApiOk; env_key_absent=$envKeyAbsent; oauth_fields_absent=$oauthFieldsAbsent"
        }
    } catch {
        return [pscustomobject]@{
            Pass = $false
            Summary = 'unable to validate non-secret fields'
        }
    }
}

function New-Check {
    param(
        [string]$Name,
        [string]$Expected,
        [string]$Actual,
        [bool]$Pass,
        [string]$Path
    )

    [pscustomobject]@{
        Status = $(if ($Pass) { "PASS" } else { "FAIL" })
        Name = $Name
        Expected = $Expected
        Actual = $Actual
        Path = $Path
    }
}

$checks = @()

$checks += New-Check "normal auth" "exists" (Get-PathSummary (Join-Path $normal "auth.json")) (Test-Path -LiteralPath (Join-Path $normal "auth.json")) (Join-Path $normal "auth.json")
$checks += New-Check "normal config" "exists" (Get-PathSummary (Join-Path $normal "config.toml")) (Test-Path -LiteralPath (Join-Path $normal "config.toml")) (Join-Path $normal "config.toml")
$checks += New-Check "normal hooks" "exists" (Get-PathSummary (Join-Path $normal "hooks.json")) (Test-Path -LiteralPath (Join-Path $normal "hooks.json")) (Join-Path $normal "hooks.json")
$normalSkillLinks = Get-SkillLinkCount (Join-Path $normal "skills")
$normalProjection = Get-ProjectionCheck 'codex' (Join-Path $normal 'skills')
$checks += New-Check "normal skills" "Manifest-selected projection passes; external Host catalog entries are not compared" "$($normalProjection.Summary); total linked=$normalSkillLinks" $normalProjection.Pass (Join-Path $normal "skills")
$checks += New-Check "normal electron .codex" "junction/dir points to normal .codex" (Get-PathSummary $normalElectron) ((Test-Path -LiteralPath $normalElectron) -and ((Get-Item -LiteralPath $normalElectron -Force).Target -eq $normal)) $normalElectron
$checks += New-Check "normal electron config" "exists through normal electron .codex" (Get-PathSummary (Join-Path $normalElectron "config.toml")) (Test-Path -LiteralPath (Join-Path $normalElectron "config.toml")) (Join-Path $normalElectron "config.toml")

$plusAuthPath = Join-Path $plus "auth.json"
$plusConfigPath = Join-Path $plus "config.toml"
$plusAuth = Get-CodexPlusPlusProxyAuthCheck $plusAuthPath $plusConfigPath
$expectedPlusAuth = if ($plusAuth.Mode -eq 'chatgpt') { "official account mode (auth_mode=chatgpt with tokens)" } else { "CodexManager apiKey mirror exists, auth_mode=apikey, and matches config.toml" }
$checks += New-Check "plus auth" $expectedPlusAuth $plusAuth.Summary $plusAuth.Pass "$plusAuthPath <-> $plusConfigPath"
$checks += New-Check "plus config" "exists" (Get-PathSummary (Join-Path $plus "config.toml")) (Test-Path -LiteralPath (Join-Path $plus "config.toml")) (Join-Path $plus "config.toml")
$checks += New-Check "plus hooks" "exists" (Get-PathSummary (Join-Path $plus "hooks.json")) (Test-Path -LiteralPath (Join-Path $plus "hooks.json")) (Join-Path $plus "hooks.json")
$plusSkillLinks = Get-SkillLinkCount (Join-Path $plus "skills")
$plusProjection = Get-ProjectionCheck 'codex_plus_plus' (Join-Path $plus 'skills')
$checks += New-Check "plus skills" "Manifest-selected projection passes; external Host catalog entries are not compared" "$($plusProjection.Summary); total linked=$plusSkillLinks" $plusProjection.Pass (Join-Path $plus "skills")
$plusElectronItem = if (Test-Path -LiteralPath $plusElectron) { Get-Item -LiteralPath $plusElectron -Force } else { $null }
$plusElectronPhysical = $plusElectronItem -and -not ($plusElectronItem.Attributes -band [IO.FileAttributes]::ReparsePoint) -and [string]::Equals([IO.Path]::GetFullPath($plusElectron), [IO.Path]::GetFullPath($plus), [StringComparison]::OrdinalIgnoreCase)
$checks += New-Check "plus electron .codex" "physical D: directory is the Codex++ .codex home" (Get-PathSummary $plusElectron) $plusElectronPhysical $plusElectron
$checks += New-Check "plus electron config" "exists through Codex++ electron .codex" (Get-PathSummary (Join-Path $plusElectron "config.toml")) (Test-Path -LiteralPath (Join-Path $plusElectron "config.toml")) (Join-Path $plusElectron "config.toml")

$failed = @($checks | Where-Object { $_.Status -ne "PASS" })

Write-Host ""
if ($failed.Count -eq 0) {
    Write-Host "OVERALL: PASS - Codex and Codex++ are isolated as expected." -ForegroundColor Green
} else {
    Write-Host "OVERALL: FAIL - Isolation check found $($failed.Count) problem(s)." -ForegroundColor Red
}
Write-Host ""

foreach ($row in $checks) {
    $color = if ($row.Status -eq "PASS") { "Green" } else { "Red" }
    Write-Host ("[{0}] {1}" -f $row.Status, $row.Name) -ForegroundColor $color
    Write-Host ("  Expected: {0}" -f $row.Expected)
    Write-Host ("  Actual:   {0}" -f $row.Actual)
    Write-Host ("  Path:     {0}" -f $row.Path)
}

Write-Host ""
Write-Host "Meaning:" -ForegroundColor Yellow
Write-Host "- PASS means the item matches the intended Codex / Codex++ isolation design."
Write-Host "- plus auth should be an apiKey mirror of config.toml; official OAuth token material is not the Codex++ proxy-mode contract."
Write-Host "- Electron .codex paths should point back to their matching real config homes."
Write-Host "- Skill validation compares each Host with the Manifest-selected projection, not with the other Host's whole catalog."

if ($failed.Count -ne 0) {
    exit 1
}
