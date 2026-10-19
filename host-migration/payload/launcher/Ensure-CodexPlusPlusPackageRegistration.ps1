# Ensure-CodexPlusPlusPackageRegistration.ps1
# Route A compatibility wrapper: gives the Codex++ patched store-apps mirror a
# real MSIX package identity via loose registration (OpenAI.CodexPlusPlus variant),
# so owl bootstrap (26.915+) and the Sparkle updater path stop dying on
# "该进程没有程序包标识符". The variant manifest is built WITHOUT the packaged
# sandbox service (see below) so it never locks the store-apps mirror; package
# identity alone satisfies the owl gate. Auto-elevates only when re-registration is needed.
#
# Usage:
#   pwsh -NoProfile -File Ensure-CodexPlusPlusPackageRegistration.ps1 [-Force]
# Exit 0 = package registered for the current mirror. Non-zero = failed.
param(
    [switch]$Force
)
$ErrorActionPreference = 'Stop'
$variantName   = 'OpenAI.CodexPlusPlus'
$aliasName     = 'chatgpt-pp.exe'
$storeAppsRoot = Join-Path $env:LOCALAPPDATA 'codex-plusplus\store-apps'
$logDir        = '@@CODEXPP_RUNTIME:win@@\log'
$logFile       = Join-Path $logDir ("package_registration_{0}.log" -f (Get-Date -Format 'yyyyMMdd'))
New-Item -ItemType Directory -Path $logDir -Force | Out-Null

function Log([string]$msg) {
    $line = "[{0}] {1}" -f (Get-Date -Format 's'), $msg
    Write-Host $line
    Add-Content -Path $logFile -Value $line
}

# --- self-elevate when registration is required -----------------------------
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$elevated = (New-Object Security.Principal.WindowsPrincipal($identity)).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

# --- locate the newest patched mirror ---------------------------------------
$mirror = Get-ChildItem $storeAppsRoot -Directory -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -match '^OpenAI\.Codex_(\d[\d\.]*)_' } |
    Sort-Object { [version]([regex]::Match($_.Name, '^OpenAI\.Codex_(\d[\d\.]*)_').Groups[1].Value) } -Descending | Select-Object -First 1
if (-not $mirror) { Log "ERROR: no store-apps mirror found under $storeAppsRoot"; exit 1 }
Log "mirror: $($mirror.FullName)"

# --- already registered for this mirror? ------------------------------------
$pkg = Get-AppxPackage -Name $variantName -ErrorAction SilentlyContinue
if (-not $Force -and $pkg -and $pkg.InstallLocation -eq $mirror.FullName -and
    (Test-Path (Join-Path $env:LOCALAPPDATA "Microsoft\WindowsApps\$aliasName"))) {
    Log "registration already current ($($pkg.PackageFullName)); nothing to do"
    exit 0
}
if (-not $elevated) {
    Log "registration needed; relaunching elevated (one UAC prompt)"
    $p = Start-Process pwsh -Verb RunAs -Wait -PassThru -ArgumentList @('-NoProfile','-ExecutionPolicy','Bypass','-File',$PSCommandPath,'-Force')
    exit $p.ExitCode
}

# --- elevated: (re)build the variant registration ----------------------------
Log "elevated registration starting"

# Strip any lingering variant sandbox service a pre-fix manifest created. It runs
# Automatic/LocalSystem straight from the store-apps mirror and locks
# codex-windows-sandbox-service.exe, breaking Codex++ update rotation
# (Access denied / CODEXPP_UPDATE_SYNC_FAIL). Stop + remove so this script is
# self-healing even against its own earlier bad state.
$legacySvcName = 'CodexSandboxService.OpenAI.CodexPlusPlus'
if (Get-Service -Name $legacySvcName -ErrorAction SilentlyContinue) {
    try { Stop-Service -Name $legacySvcName -Force -ErrorAction Stop; Log 'legacy variant sandbox service stopped (mirror lock released)' }
    catch { Log "WARN: could not stop legacy service ${legacySvcName}: $($_.Exception.Message)" }
    & sc.exe delete $legacySvcName 2>$null | Out-Null
}

# Developer mode (required for unsigned loose registration)
$unlock = 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\AppModelUnlock'
if (-not (Test-Path $unlock)) { New-Item -Path $unlock -Force | Out-Null }
Set-ItemProperty -Path $unlock -Name 'AllowDevelopmentWithoutExpLicense' -Value 1 -Type DWord

# Official package manifest of the same version as the mirror
$official = Get-AppxPackage -Name 'OpenAI.Codex' | Sort-Object Version -Descending | Select-Object -First 1
if (-not $official) { Log "ERROR: official OpenAI.Codex package not found"; exit 2 }
$mirrorVersion = [regex]::Match($mirror.Name, '^OpenAI\.Codex_(\d[\d\.]*)_').Groups[1].Value
if ($official.Version -ne $mirrorVersion) {
    Log "WARN: official package version $($official.Version) != mirror version $mirrorVersion; proceeding with official manifest of available version"
}
$officialManifest = Join-Path $official.InstallLocation 'AppxManifest.xml'
if (-not (Test-Path $officialManifest)) { Log "ERROR: cannot read $officialManifest"; exit 2 }

# Package-root files the manifest references
foreach ($pri in @('resources.pri','resources.scale-200.pri','resources.language-is.pri')) {
    $src = Join-Path $official.InstallLocation $pri
    if (Test-Path $src) { Copy-Item $src (Join-Path $mirror.FullName $pri) -Force }
}
$assetsDst = Join-Path $mirror.FullName 'assets'
if (-not (Test-Path $assetsDst)) { Copy-Item (Join-Path $official.InstallLocation 'assets') $assetsDst -Recurse -Force }

# Build the variant manifest (UTF-8 with BOM is mandatory for loose registration)
$xml = [IO.File]::ReadAllText($officialManifest)
$xml = $xml -replace 'Name="OpenAI\.Codex" ProcessorArchitecture', "Name=`"$variantName`" ProcessorArchitecture"
# Remove the packaged sandbox service entirely (do NOT just rename it). The patched
# app.asar still references the official service name CodexSandboxService.OpenAI.Codex,
# so a variant-identity process can never resolve a renamed .CodexPlusPlus service
# anyway; keeping it only registers an Automatic LocalSystem service that runs from
# the mirror and locks its files against update rotation.
$xml = $xml -replace '(?s)<desktop6:Extension Category="windows\.service".*?</desktop6:Extension>', ''
if ($xml -notmatch 'Id="ChatGPTPP"') {
    $newApp = @"
    <Application Id="ChatGPTPP" Executable="app/ChatGPT.exe" EntryPoint="Windows.FullTrustApplication">
      <uap:VisualElements DisplayName="ChatGPT (Codex++ patched)" Description="ChatGPT patched mirror" Square44x44Logo="assets/Square44x44Logo.png" Square150x150Logo="assets/Square150x150Logo.png" BackgroundColor="#3143FF" AppListEntry="none" />
      <Extensions>
        <uap3:Extension Category="windows.appExecutionAlias" Executable="app/ChatGPT.exe" EntryPoint="Windows.FullTrustApplication">
          <uap3:AppExecutionAlias>
            <desktop:ExecutionAlias Alias="$aliasName" />
          </uap3:AppExecutionAlias>
        </uap3:Extension>
      </Extensions>
    </Application>
  </Applications>
"@
    $xml = $xml -replace '</Applications>', $newApp
}
$mfPath = Join-Path $mirror.FullName 'AppxManifest.xml'
[IO.File]::WriteAllText($mfPath, $xml, (New-Object Text.UTF8Encoding($true)))
Log "variant manifest written: $mfPath"

# Replace any stale registration, then register fresh
$stale = Get-AppxPackage -Name $variantName
if ($stale) { $stale | Remove-AppxPackage -ErrorAction SilentlyContinue; Log 'stale registration removed' }
$uri = [Uri]"file:///$($mfPath -replace '\\','/')"
Add-AppxPackage -Register $uri
Log 'Add-AppxPackage -Register completed'

# Verify
$pkg = Get-AppxPackage -Name $variantName
$aliasPath = Join-Path $env:LOCALAPPDATA "Microsoft\WindowsApps\$aliasName"
if ($pkg -and $pkg.InstallLocation -eq $mirror.FullName -and (Test-Path $aliasPath)) {
    Log "SUCCESS: $($pkg.PackageFullName) registered; alias ready: $aliasPath"
    exit 0
}
Log "FAILURE: post-registration verification failed (pkg=$($pkg.PackageFullName) alias=$(Test-Path $aliasPath))"
exit 3
