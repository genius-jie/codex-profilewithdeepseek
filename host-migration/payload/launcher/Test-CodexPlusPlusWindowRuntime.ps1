#requires -Version 7.0

param(
    [string]$ProfileRoot = "@@CODEXPP_PROFILE:win@@",
    [string]$StoreRoot = "@@CODEXPP_INSTALL_ROOT:win@@\store-apps",
    [string]$OutputDir = "@@CODEXPP_INSTALL_ROOT:win@@\windows-computer-use",
    [double]$MaxWhiteishRatioForBlank = 0.985,
    [int]$MinDistinctSampledColors = 16,
    [switch]$AllowNoWindow
)

$ErrorActionPreference = "Stop"

$win32Source = @"
using System;
using System.Runtime.InteropServices;

public static class CodexPlusPlusWindowRuntimeWin32 {
    [StructLayout(LayoutKind.Sequential)]
    public struct RECT {
        public int Left;
        public int Top;
        public int Right;
        public int Bottom;
    }

    [DllImport("user32.dll")]
    public static extern bool GetWindowRect(IntPtr hWnd, out RECT lpRect);
}
"@

try {
    Add-Type -TypeDefinition $win32Source -ErrorAction Stop
} catch {
    if (-not ($_.Exception.Message -match "already exists")) { throw }
}
Add-Type -AssemblyName System.Drawing

function Normalize-PathString {
    param([string]$Path)
    if ([string]::IsNullOrWhiteSpace($Path)) { return "" }
    return [System.IO.Path]::GetFullPath($Path).TrimEnd("\")
}

function Get-AppRootFromExecutablePath {
    param([string]$ExecutablePath)

    if ([string]::IsNullOrWhiteSpace($ExecutablePath)) { return "" }
    if ((Split-Path -Leaf $ExecutablePath) -inotin @("Codex.exe", "ChatGPT.exe")) { return "" }
    $parent = Split-Path -Parent $ExecutablePath
    if ((Split-Path -Leaf $parent) -ine "app") { return "" }
    return (Normalize-PathString $parent)
}

function Resolve-LatestCodexPlusPlusAppRoot {
    if (-not (Test-Path -LiteralPath $StoreRoot)) { return "" }

    Get-ChildItem -LiteralPath $StoreRoot -Directory -Filter "OpenAI.Codex_*" -ErrorAction SilentlyContinue |
        ForEach-Object {
            $versionText = $_.Name -replace "^OpenAI\.Codex_([^_]+)_.*$", '$1'
            $exePath = Join-Path $_.FullName "app\ChatGPT.exe"
            if (-not (Test-Path -LiteralPath $exePath)) {
                $exePath = Join-Path $_.FullName "app\Codex.exe"
            }
            if (Test-Path -LiteralPath $exePath) {
                [pscustomobject]@{
                    AppRoot = Normalize-PathString (Join-Path $_.FullName "app")
                    Version = [version]$versionText
                }
            }
        } |
        Sort-Object @{ Expression = "Version"; Descending = $true } |
        Select-Object -First 1 -ExpandProperty AppRoot
}

function Test-AppAsarHasCodexPlusPlusMarker {
    param([string]$AppRoot)

    if ([string]::IsNullOrWhiteSpace($AppRoot)) { return $false }
    $asarPath = Join-Path $AppRoot "resources\app.asar"
    if (-not (Test-Path -LiteralPath $asarPath)) { return $false }
    $encoding = [System.Text.Encoding]::GetEncoding(28591)
    $text = [System.IO.File]::ReadAllText($asarPath, $encoding)
    return (
        $text.IndexOf("codex-plusplus-loader", [System.StringComparison]::OrdinalIgnoreCase) -ge 0 -or
        $text.IndexOf("codex-plusplus", [System.StringComparison]::OrdinalIgnoreCase) -ge 0
    )
}

function Get-PrimaryCodexPlusPlusProcess {
    $profileNeedle = Normalize-PathString $ProfileRoot
    $storeNeedle = Normalize-PathString $StoreRoot

    Get-CimInstance Win32_Process | Where-Object { $_.Name -in @("Codex.exe", "ChatGPT.exe") } |
        Where-Object {
            $cmd = [string]$_.CommandLine
            $exe = Normalize-PathString $_.ExecutablePath
            $cmd -and
            $cmd.IndexOf("--type=", [System.StringComparison]::OrdinalIgnoreCase) -lt 0 -and
            $cmd.IndexOf($profileNeedle, [System.StringComparison]::OrdinalIgnoreCase) -ge 0 -and
            $exe.IndexOf($storeNeedle, [System.StringComparison]::OrdinalIgnoreCase) -eq 0
        } |
        Sort-Object ProcessId |
        Select-Object -First 1
}

function Measure-BitmapBlankness {
    param([System.Drawing.Bitmap]$Bitmap)

    $width = $Bitmap.Width
    $height = $Bitmap.Height
    $step = [Math]::Max(1, [int]([Math]::Min($width, $height) / 90))
    $sampleCount = 0
    $whiteishCount = 0
    $darkishCount = 0
    $colors = [System.Collections.Generic.HashSet[string]]::new()

    for ($y = 0; $y -lt $height; $y += $step) {
        for ($x = 0; $x -lt $width; $x += $step) {
            $pixel = $Bitmap.GetPixel($x, $y)
            $sampleCount++
            if ($pixel.R -ge 245 -and $pixel.G -ge 245 -and $pixel.B -ge 245) { $whiteishCount++ }
            if ($pixel.R -le 16 -and $pixel.G -le 16 -and $pixel.B -le 16) { $darkishCount++ }
            [void]$colors.Add(("{0:X2}{1:X2}{2:X2}" -f $pixel.R, $pixel.G, $pixel.B))
        }
    }

    $whiteishRatio = if ($sampleCount -gt 0) { $whiteishCount / $sampleCount } else { 1 }
    $darkishRatio = if ($sampleCount -gt 0) { $darkishCount / $sampleCount } else { 0 }

    [pscustomobject]@{
        sampleCount = $sampleCount
        sampleStep = $step
        whiteishRatio = [Math]::Round($whiteishRatio, 4)
        darkishRatio = [Math]::Round($darkishRatio, 4)
        distinctSampledColors = $colors.Count
        blankWhiteScreen = ($whiteishRatio -ge $MaxWhiteishRatioForBlank -or $colors.Count -lt $MinDistinctSampledColors)
    }
}

$latestAppRoot = Resolve-LatestCodexPlusPlusAppRoot
$processInfo = Get-PrimaryCodexPlusPlusProcess

if (-not $processInfo) {
    $result = [pscustomobject]@{
        guard = "codexplusplus_window_runtime"
        status = if ($AllowNoWindow) { "skip" } else { "fail" }
        reason = "no_active_codexplusplus_main_window_process"
        profileRoot = Normalize-PathString $ProfileRoot
        latestAppRoot = $latestAppRoot
    }
    if ($AllowNoWindow) {
        Write-Output "CODEXPP_WINDOW_RUNTIME_GUARD_SKIP"
        $result | ConvertTo-Json -Depth 6
        exit 0
    }
    Write-Output "CODEXPP_WINDOW_RUNTIME_GUARD_FAIL"
    $result | ConvertTo-Json -Depth 6
    exit 1
}

$process = Get-Process -Id $processInfo.ProcessId -ErrorAction Stop
$windowHandle = $process.MainWindowHandle
$appRoot = Get-AppRootFromExecutablePath -ExecutablePath $processInfo.ExecutablePath
$loaderMarkerPresent = Test-AppAsarHasCodexPlusPlusMarker -AppRoot $appRoot

if ($windowHandle -eq [IntPtr]::Zero) {
    if ($AllowNoWindow) {
        Write-Output "CODEXPP_WINDOW_RUNTIME_GUARD_SKIP"
        [pscustomobject]@{
            guard = "codexplusplus_window_runtime"
            status = "skip"
            reason = "main_window_handle_zero_allowed"
            processId = $process.Id
            activeAppRoot = $appRoot
            latestAppRoot = $latestAppRoot
            loaderMarkerPresent = $loaderMarkerPresent
        } | ConvertTo-Json -Depth 6
        exit 0
    }
    Write-Output "CODEXPP_WINDOW_RUNTIME_GUARD_FAIL"
    [pscustomobject]@{
        guard = "codexplusplus_window_runtime"
        status = "fail"
        reason = "main_window_handle_missing"
        processId = $process.Id
        activeAppRoot = $appRoot
        latestAppRoot = $latestAppRoot
        loaderMarkerPresent = $loaderMarkerPresent
    } | ConvertTo-Json -Depth 6
    exit 1
}

$maxRetries = 5
$retryCount = 0
$rect = New-Object CodexPlusPlusWindowRuntimeWin32+RECT
$width = 0
$height = 0

while ($retryCount -lt $maxRetries) {
    if ([CodexPlusPlusWindowRuntimeWin32]::GetWindowRect($windowHandle, [ref]$rect)) {
        $width = $rect.Right - $rect.Left
        $height = $rect.Bottom - $rect.Top
        if ($width -ge 200 -and $height -ge 200 -and $rect.Left -gt -10000) {
            break
        }
    }
    $retryCount++
    if ($retryCount -lt $maxRetries) {
        Start-Sleep -Seconds 2
    }
}

if ($width -lt 200 -or $height -lt 200) {
    Write-Output "CODEXPP_WINDOW_RUNTIME_GUARD_FAIL"
    [pscustomobject]@{
        guard = "codexplusplus_window_runtime"
        status = "fail"
        reason = "window_bounds_too_small"
        processId = $process.Id
        activeAppRoot = $appRoot
        latestAppRoot = $latestAppRoot
        bounds = @{ left = $rect.Left; top = $rect.Top; right = $rect.Right; bottom = $rect.Bottom; width = $width; height = $height }
        loaderMarkerPresent = $loaderMarkerPresent
    } | ConvertTo-Json -Depth 6
    exit 1
}

[System.IO.Directory]::CreateDirectory($OutputDir) | Out-Null
$screenshotPath = Join-Path $OutputDir ("codex-window-pid{0}.png" -f $process.Id)
$bitmap = [System.Drawing.Bitmap]::new($width, $height)
$graphics = [System.Drawing.Graphics]::FromImage($bitmap)
try {
    $graphics.CopyFromScreen($rect.Left, $rect.Top, 0, 0, $bitmap.Size)
    $metrics = Measure-BitmapBlankness -Bitmap $bitmap
    $bitmap.Save($screenshotPath, [System.Drawing.Imaging.ImageFormat]::Png)
} finally {
    $graphics.Dispose()
    $bitmap.Dispose()
}

$activeMatchesLatest = (
    -not [string]::IsNullOrWhiteSpace($latestAppRoot) -and
    (Normalize-PathString $appRoot) -ieq (Normalize-PathString $latestAppRoot)
)

$failures = [System.Collections.Generic.List[string]]::new()
if (-not $activeMatchesLatest) { [void]$failures.Add("active Codex++ app root is not the latest managed app root") }
if (-not $loaderMarkerPresent) { [void]$failures.Add("active app.asar does not contain Codex++ loader marker") }
if ($metrics.blankWhiteScreen) { [void]$failures.Add("Codex++ window screenshot is blank or white-screen-like") }

$result = [pscustomobject]@{
    guard = "codexplusplus_window_runtime"
    status = if ($failures.Count -eq 0) { "pass" } else { "fail" }
    processId = $process.Id
    windowTitle = $process.MainWindowTitle
    activeAppRoot = Normalize-PathString $appRoot
    latestAppRoot = Normalize-PathString $latestAppRoot
    activeMatchesLatest = $activeMatchesLatest
    loaderMarkerPresent = $loaderMarkerPresent
    profileRoot = Normalize-PathString $ProfileRoot
    commandLine = [string]$processInfo.CommandLine
    screenshotPath = $screenshotPath
    bounds = @{ left = $rect.Left; top = $rect.Top; right = $rect.Right; bottom = $rect.Bottom; width = $width; height = $height }
    metrics = $metrics
    failures = @($failures)
}

if ($failures.Count -gt 0) {
    Write-Output "CODEXPP_WINDOW_RUNTIME_GUARD_FAIL"
    $result | ConvertTo-Json -Depth 8
    exit 1
}

Write-Output "CODEXPP_WINDOW_RUNTIME_GUARD_PASS"
$result | ConvertTo-Json -Depth 8
