#requires -Version 7.0

# Start Codex++ with its isolated profile.
# Isolation contract:
# - auth/config/state: @@CODEXPP_HOME:win@@
# - browser/user-data-dir: @@CODEXPP_PROFILE:win@@ (physical root)
# - CodexManager API proxy: configured in the isolated .codex\config.toml
# - HTTP_PROXY env: enabled only when -ProxyMode is supplied

param(
    [switch]$ProxyMode,
    [switch]$SkipConnectorSync,
    [switch]$SkipOpenCliAdapterSync,
    [switch]$RunSessionMaintenance,
    [switch]$SkipSessionPathTest,
    [switch]$SkipRepair,
    [switch]$ForceRepair,
    [switch]$Restart,
    [ValidateRange(0, 300)][int]$StartupGuardWaitSeconds = 0,
    [string]$HttpProxy = "http://127.0.0.1:7890",
    [string]$AllProxy = "socks5://127.0.0.1:7890",
    [string]$NoProxy = "localhost,127.0.0.1,::1"
)

$ErrorActionPreference = "Stop"
$powerShellExe = [IO.Path]::GetFullPath('@@POWERSHELL_EXE:win@@')
$legacyPowerShellExe = [IO.Path]::GetFullPath('@@SYSTEMROOT:win@@\System32\WindowsPowerShell\v1.0\powershell.exe') # codexpp:migration-detector-only
$legacyPowerShellLeaf = [IO.Path]::GetFileName($legacyPowerShellExe)
if (-not (Test-Path -LiteralPath $powerShellExe -PathType Leaf)) {
    throw "PowerShell 7 missing: $powerShellExe"
}

# Serialize the desktop entry so concurrent launches cannot race the UAC-backed
# Windows sandbox setup and leave the UI in an incomplete onboarding state.
$startupMutex = [System.Threading.Mutex]::new($false, "Local\CodexPlusPlusStartupGuard")
$startupLockTaken = $false
try {
    $startupLockTaken = $startupMutex.WaitOne($StartupGuardWaitSeconds * 1000)
} catch [System.Threading.AbandonedMutexException] {
    $startupLockTaken = $true
}
if (-not $startupLockTaken) {
    if ($StartupGuardWaitSeconds -gt 0) {
        throw "Timed out waiting $StartupGuardWaitSeconds seconds for the Codex++ startup guard"
    }
    Write-Host "Codex++ 正在启动，请勿重复点击桌面入口。" -ForegroundColor Yellow
    exit 0
}

function Test-CodexPlusPlusProfileRunning {
    $profileRoots = @('@@CODEXPP_PROFILE:win@@')
    $storeRoot = '@@CODEXPP_INSTALL_ROOT:win@@\store-apps'
    $storePrefix = [System.IO.Path]::GetFullPath($storeRoot).TrimEnd('\') + '\'
    # Only app-owned executables below the isolated store count as profile
    # processes.  Maintenance scripts often carry an -AppRoot argument that
    # mentions store-apps; their executable name must never make the profile
    # look alive and strand the exit-repair watchdog forever.
    $ownedProcessNames = @(
        'ChatGPT.exe', 'Codex.exe', 'codex.exe',
        'node.exe', 'node_repl.exe', 'codex-code-mode-host.exe'
    )
    return [bool](Get-CimInstance Win32_Process | Where-Object {
        if ($_.ProcessId -eq $PID) { return $false }
        $path = [string]$_.ExecutablePath
        $cmd = [string]$_.CommandLine
        $name = [System.IO.Path]::GetFileName($path)
        $storeOwnedProcess = $path -and
            $path.StartsWith($storePrefix, [StringComparison]::OrdinalIgnoreCase) -and
            ($ownedProcessNames -contains $name)
        $profileArgument = $cmd -and @($profileRoots | Where-Object {
            $cmd.IndexOf("--user-data-dir=$_", [StringComparison]::OrdinalIgnoreCase) -ge 0 -or
            $cmd.IndexOf("--user-data-dir=`"$_`"", [StringComparison]::OrdinalIgnoreCase) -ge 0
        }).Count -gt 0
        $storeOwnedProcess -or $profileArgument
    } | Select-Object -First 1)
}

# Wake, never relaunch.  When the isolated profile is already running, the
# desktop entry may only surface the existing instance's main window; it must
# never spawn a second instance, stop anything, or start a repair transaction.
# The wake target is the store-owned main browser process carrying the exact
# isolated user-data-dir; renderer and child processes carry --type= and never
# qualify.  Fails closed (returns $false) so a second click can never fail.
function Show-CodexPlusPlusRunningMainWindow {
    try {
        $profileRoots = @('@@CODEXPP_PROFILE:win@@')
        $storeRoot = [System.IO.Path]::GetFullPath('@@CODEXPP_INSTALL_ROOT:win@@\store-apps').TrimEnd('\')
        $storePrefix = $storeRoot + '\'
        $mainProcess = Get-CimInstance Win32_Process | Where-Object {
            if ($_.ProcessId -eq $PID) { return $false }
            $path = [string]$_.ExecutablePath
            $cmd = [string]$_.CommandLine
            $name = [System.IO.Path]::GetFileName($path)
            [string]::Equals([string]$_.Name, $name, [StringComparison]::OrdinalIgnoreCase) -and
            ($name -in @('ChatGPT.exe', 'Codex.exe')) -and
            $path.StartsWith($storePrefix, [StringComparison]::OrdinalIgnoreCase) -and
            (@($profileRoots | Where-Object {
                $cmd.IndexOf("--user-data-dir=$_", [StringComparison]::OrdinalIgnoreCase) -ge 0 -or
                $cmd.IndexOf("--user-data-dir=`"$_`"", [StringComparison]::OrdinalIgnoreCase) -ge 0
            }).Count -gt 0) -and
            ($cmd.IndexOf('--type=', [StringComparison]::OrdinalIgnoreCase) -lt 0)
        } | Select-Object -First 1
        if ($null -eq $mainProcess) { return $false }

        # Notify Electron main process internal wake channel
        $wakeEndpointOk = $false
        try {
            $wakeResp = Invoke-RestMethod -Uri "http://127.0.0.1:48763/wake" -Method Get -TimeoutSec 1 -ErrorAction SilentlyContinue
            if ($wakeResp -and $wakeResp.ok -eq $true) { $wakeEndpointOk = $true }
        } catch {}

        if (-not ('CodexPlusPlusWindowWake' -as [type])) {
            Add-Type @'
using System;
using System.Runtime.InteropServices;
using System.Text;
public static class CodexPlusPlusWindowWake {
    public delegate bool EnumWindowsProc(IntPtr hWnd, IntPtr lp);
    [DllImport("user32.dll")] public static extern bool EnumWindows(EnumWindowsProc cb, IntPtr lp);
    [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint pid);
    [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetWindowText(IntPtr hWnd, StringBuilder sb, int max);
    [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetClassName(IntPtr hWnd, StringBuilder sb, int max);
    [StructLayout(LayoutKind.Sequential)] public struct RECT { public int L; public int T; public int R; public int B; }
    [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hWnd, out RECT r);
    [DllImport("user32.dll")] public static extern bool IsIconic(IntPtr hWnd);
    [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
}
'@
        }

        $script:codexPlusPlusWakeHandles = [System.Collections.Generic.List[long]]::new()
        $script:codexPlusPlusWakeTargetPid = [int]$mainProcess.ProcessId
        [CodexPlusPlusWindowWake]::EnumWindows({ param($hWnd, $state)
            $ownerPid = [uint32]0
            [void][CodexPlusPlusWindowWake]::GetWindowThreadProcessId($hWnd, [ref]$ownerPid)
            if ([int]$ownerPid -eq $script:codexPlusPlusWakeTargetPid) {
                $script:codexPlusPlusWakeHandles.Add($hWnd.ToInt64())
            }
            return $true
        }, [IntPtr]::Zero) | Out-Null

        # The real main window is the largest titled Chromium window or an iconic window.
        $bestHandle = [IntPtr]::Zero
        $bestArea = -1
        foreach ($raw in $script:codexPlusPlusWakeHandles) {
            $hWnd = [IntPtr]$raw
            $class = [System.Text.StringBuilder]::new(256)
            [void][CodexPlusPlusWindowWake]::GetClassName($hWnd, $class, 256)
            if (-not [string]::Equals($class.ToString(), 'Chrome_WidgetWin_1', [StringComparison]::Ordinal)) { continue }
            $title = [System.Text.StringBuilder]::new(256)
            [void][CodexPlusPlusWindowWake]::GetWindowText($hWnd, $title, 256)
            if ([string]::IsNullOrWhiteSpace($title.ToString())) { continue }
            if ([CodexPlusPlusWindowWake]::IsIconic($hWnd)) {
                $bestHandle = $hWnd
                break
            }
            $rect = [CodexPlusPlusWindowWake+RECT]::new()
            [void][CodexPlusPlusWindowWake]::GetWindowRect($hWnd, [ref]$rect)
            $w = $rect.R - $rect.L
            $h = $rect.B - $rect.T
            $area = [Math]::Max(0, $w) * [Math]::Max(0, $h)
            if ($area -gt $bestArea) { $bestArea = $area; $bestHandle = $hWnd }
        }
        if ($bestHandle -eq [IntPtr]::Zero) {
            foreach ($raw in $script:codexPlusPlusWakeHandles) {
                $hWnd = [IntPtr]$raw
                $class = [System.Text.StringBuilder]::new(256)
                [void][CodexPlusPlusWindowWake]::GetClassName($hWnd, $class, 256)
                if ([string]::Equals($class.ToString(), 'Chrome_WidgetWin_1', [StringComparison]::Ordinal)) {
                    $bestHandle = $hWnd
                    break
                }
            }
        }
        if ($bestHandle -eq [IntPtr]::Zero) { return $false }

        # SW_RESTORE = 9 for a minimized window, SW_SHOW = 5 for a hidden one.
        $command = if ([CodexPlusPlusWindowWake]::IsIconic($bestHandle)) { 9 } else { 5 }
        [void][CodexPlusPlusWindowWake]::ShowWindow($bestHandle, $command)
        [void][CodexPlusPlusWindowWake]::SetForegroundWindow($bestHandle)
        return $true
    } catch {
        return $false
    }
}

function Test-ExactPowerShellFileProcess {
    param(
        [object]$Process,
        [string]$ScriptPath,
        [string]$RequiredSwitch = '',
        [switch]$AllowLegacyWindowsPowerShell
    )
    if ($null -eq $Process -or [int]$Process.ProcessId -eq $PID) { return $false }
    $executablePath = [string]$Process.ExecutablePath
    if ([string]::IsNullOrWhiteSpace($executablePath)) { return $false }
    $normalizedExecutable = [IO.Path]::GetFullPath($executablePath)
    $isPowerShell7 =
        [string]::Equals([string]$Process.Name, 'pwsh.exe', [StringComparison]::OrdinalIgnoreCase) -and
        [string]::Equals($normalizedExecutable, $powerShellExe, [StringComparison]::OrdinalIgnoreCase)
    $isLegacyPowerShell =
        $AllowLegacyWindowsPowerShell -and
        [string]::Equals([string]$Process.Name, $legacyPowerShellLeaf, [StringComparison]::OrdinalIgnoreCase) -and
        [string]::Equals($normalizedExecutable, $legacyPowerShellExe, [StringComparison]::OrdinalIgnoreCase)
    if (-not $isPowerShell7 -and -not $isLegacyPowerShell) { return $false }
    $cmd = [string]$Process.CommandLine
    if ([string]::IsNullOrWhiteSpace($cmd)) { return $false }
    $exe = [regex]::Escape($normalizedExecutable)
    $leaf = [regex]::Escape([IO.Path]::GetFileName($normalizedExecutable))
    $hostToken = '(?:"' + $exe + '"|' + $exe + '|"?' + $leaf + '"?)'
    $hostOptions = if ($isLegacyPowerShell) {
        '(?:\s+(?:-NoProfile|-NonInteractive|-WindowStyle\s+Hidden|-ExecutionPolicy\s+Bypass))*'
    } else {
        '(?:\s+(?:-NoProfile|-NonInteractive|-WindowStyle\s+Hidden))*'
    }
    $script = [regex]::Escape([IO.Path]::GetFullPath($ScriptPath))
    $scriptToken = '(?:"' + $script + '"|' + $script + ')'
    $prefix = '(?i)^\s*' + $hostToken + $hostOptions + '\s+-File\s+' + $scriptToken
    if ([string]::IsNullOrWhiteSpace($RequiredSwitch)) {
        return [regex]::IsMatch($cmd, $prefix + '\s*$')
    }
    if (-not [string]::Equals($RequiredSwitch, '-Watch', [StringComparison]::OrdinalIgnoreCase)) { return $false }
    $match = [regex]::Match(
        $cmd,
        $prefix + '\s+-Watch(?:\s+-IntervalSeconds\s+(?<interval>[1-9][0-9]{0,4}))?(?:\s+-DurationSeconds\s+(?<duration>[1-9][0-9]{0,6}))?\s*$'
    )
    if (-not $match.Success) { return $false }
    if ($match.Groups['interval'].Success -and [int]$match.Groups['interval'].Value -gt 86400) { return $false }
    if ($match.Groups['duration'].Success -and [int]$match.Groups['duration'].Value -gt 604800) { return $false }
    return $true
}

function Test-ExactCodexPlusPlusTweakHostProcess {
    param([object]$Process)
    if ($null -eq $Process -or [int]$Process.ProcessId -eq $PID) { return $false }
    $executablePath = [string]$Process.ExecutablePath
    $processName = [string]$Process.Name
    $commandLine = [string]$Process.CommandLine
    if ([string]::IsNullOrWhiteSpace($executablePath) -or [string]::IsNullOrWhiteSpace($commandLine)) { return $false }
    try { $executablePath = [IO.Path]::GetFullPath($executablePath) } catch { return $false }
    if (-not (Test-Path -LiteralPath $executablePath -PathType Leaf)) { return $false }
    $leaf = [IO.Path]::GetFileName($executablePath)
    if (-not [string]::Equals($processName, $leaf, [StringComparison]::OrdinalIgnoreCase)) { return $false }
    if ((Get-Item -LiteralPath $executablePath -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) { return $false }

    $tweakRoot = [IO.Path]::GetFullPath('@@CODEXPP_RUNTIME:win@@\tweaks').TrimEnd('\')
    $nodeEntrypoints = @(
        (Join-Path $tweakRoot 'co.bennett.windows-computer-use\scripts\bridge-daemon.js'),
        (Join-Path $tweakRoot 'co.bennett.windows-computer-use\mcp-server.js')
    )
    if ([string]::Equals($leaf, 'node.exe', [StringComparison]::OrdinalIgnoreCase)) {
        $nodeToken = '(?:"' + [regex]::Escape($executablePath) + '"|' + [regex]::Escape($executablePath) + '|"?node\.exe"?)'
        foreach ($entrypoint in $nodeEntrypoints) {
            $scriptToken = '(?:"' + [regex]::Escape($entrypoint) + '"|' + [regex]::Escape($entrypoint) + ')'
            if ([regex]::IsMatch($commandLine, '(?i)^\s*' + $nodeToken + '\s+' + $scriptToken + '\s*$')) { return $true }
        }
        return $false
    }

    if (-not [string]::Equals($leaf, 'pwsh.exe', [StringComparison]::OrdinalIgnoreCase) -or
        -not [string]::Equals($executablePath, $powerShellExe, [StringComparison]::OrdinalIgnoreCase)) { return $false }
    $bridgeScript = Join-Path $tweakRoot 'co.bennett.windows-computer-use\scripts\windows-bridge.ps1'
    $bridgeToken = [regex]::Escape($bridgeScript)
    $powerShellToken = '(?:"' + [regex]::Escape($powerShellExe) + '"|' + [regex]::Escape($powerShellExe) + '|"?pwsh\.exe"?)'
    $allowedOption = '(?:-NoProfile|-NonInteractive|-WindowStyle\s+Hidden)'
    $bridgeScriptToken = '(?:"' + $bridgeToken + '"|' + $bridgeToken + ')'
    $exactBridgeCommand = '(?i)^\s*' + $powerShellToken + '(?:\s+' + $allowedOption + ')*\s+-File\s+' + $bridgeScriptToken + '\s+-Server\s*$'
    return [regex]::IsMatch($commandLine, $exactBridgeCommand)
}

# A second desktop click must never turn into an in-place repair transaction.
# Repair mutates shared app/tweak/config state and is only legal after
# every process using the isolated Codex++ profile has exited.  The guard
# below therefore has three outcomes: wake the healthy running instance and
# exit; fall through into the designed startup cleanup when no main window
# can be presented (residue) or -Restart is explicit; or proceed normally.
$codexPlusPlusResidueRecovery = [bool]$Restart
if ($Restart) {
    Write-Host '已请求重启 Codex++：将清理当前实例并全新启动。' -ForegroundColor Yellow
} elseif (Test-CodexPlusPlusProfileRunning) {
    Write-Host 'Codex++ 已在运行；本次重复启动不会修改、停止或修复现有实例。' -ForegroundColor Yellow
    # Surface the already-running instance instead of leaving the desktop
    # entry dead when its window is hidden in the tray.  This only shows and
    # focuses the existing main window; it never starts a second instance,
    # stops anything, or repairs, so the no-repair contract above still holds.
    $woken = $false
    try { $woken = [bool](Show-CodexPlusPlusRunningMainWindow) } catch { }
    if ($woken) {
        Write-Host '已唤醒现有 Codex++ 主窗口。' -ForegroundColor Green
        if ($startupLockTaken) { [void]$startupMutex.ReleaseMutex() }
        $startupMutex.Dispose()
        exit 0
    }
    # Profile processes exist but no main window can be presented: window
    # crashed residue.  Exiting here would strand the desktop entry forever;
    # fall through into the designed startup cleanup and relaunch instead.
    $codexPlusPlusResidueRecovery = $true
    Write-Host '未找到可唤醒的 Codex++ 主窗口；检测到无响应残留实例，执行设计内清理并重启。' -ForegroundColor Yellow
}

# Auto-detect proxy if not explicitly disabled
if (-not $ProxyMode) {
    $client = [Net.Sockets.TcpClient]::new()
    try {
        $async = $client.BeginConnect('127.0.0.1', 7890, $null, $null)
        if ($async.AsyncWaitHandle.WaitOne(1000)) {
            $client.EndConnect($async)
            $ProxyMode = $true
        }
    } catch { }
    finally { $client.Close() }
}

$plusProfile = "@@CODEXPP_PROFILE:win@@"
$codexPlusPlusCmd = "@@USERPROFILE:win@@\AppData\Local\Microsoft\WindowsApps\codex-plusplus-codex.cmd"
$profileRootContractSource = '@@LAUNCHER_ROOT:win@@\Assert-CodexPlusPlusProfileRootContract.ps1'
if (-not (Test-Path -LiteralPath $profileRootContractSource -PathType Leaf)) {
    throw "Codex++ profile root contract helper is missing: $profileRootContractSource"
}
. $profileRootContractSource

# This is the first operation that can authorize any later write. Fail closed
# unless the D: root and nested CODEX_HOME are physical directories.
$profileRootContract = Assert-CodexPlusPlusProfileRootContract
$canonicalPlusProfile = [string]$profileRootContract.CanonicalRoot
$canonicalCodexHome = [string]$profileRootContract.CanonicalCodexHome

function Assert-CodexPlusPlusPhysicalPathChain {
    param([Parameter(Mandatory = $true)][string]$Path)
    $fullPath = [System.IO.Path]::GetFullPath($Path)
    $pathRoot = [System.IO.Path]::GetPathRoot($fullPath)
    if ([string]::IsNullOrWhiteSpace($pathRoot)) {
        throw "Codex++ launch path has no physical root: $Path"
    }

    $current = $pathRoot
    foreach ($part in @($fullPath.Substring($pathRoot.Length).Split('\') | Where-Object { $_ })) {
        $current = Join-Path $current $part
        if (-not (Test-Path -LiteralPath $current)) {
            throw "Codex++ launch path component is missing: $current"
        }
        $item = Get-Item -LiteralPath $current -Force
        if ($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) {
            throw "Refusing Codex++ launch through a reparse-point path: $current"
        }
    }
    return $fullPath
}

function Assert-CodexPlusPlusLaunchExecutable {
    param(
        [Parameter(Mandatory = $true)][string]$ExecutablePath,
        [Parameter(Mandatory = $true)][string]$ExpectedAppRoot
    )
    $fixedStoreRoot = [System.IO.Path]::GetFullPath('@@CODEXPP_INSTALL_ROOT:win@@\store-apps').TrimEnd('\')
    $appRoot = [System.IO.Path]::GetFullPath($ExpectedAppRoot).TrimEnd('\')
    $candidatePath = [System.IO.Path]::GetFullPath($ExecutablePath)
    $packageRoot = Split-Path -Parent $appRoot
    $packageIdentity = Split-Path -Leaf $packageRoot
    if (-not $appRoot.StartsWith(($fixedStoreRoot + '\'), [System.StringComparison]::OrdinalIgnoreCase) -or
        -not [string]::Equals((Split-Path -Leaf $appRoot), 'app', [System.StringComparison]::OrdinalIgnoreCase) -or
        $packageIdentity -notlike 'OpenAI.Codex_*') {
        throw "Refusing Codex++ launch outside the exact fixed store app root: $appRoot"
    }
    if (-not [string]::Equals((Split-Path -Parent $candidatePath), $appRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing Codex++ launch executable outside the selected app root: $candidatePath"
    }
    if ((Split-Path -Leaf $candidatePath) -notin @('ChatGPT.exe', 'Codex.exe')) {
        throw "Refusing unexpected Codex++ launch executable name: $candidatePath"
    }

    [void](Assert-CodexPlusPlusPhysicalPathChain -Path $candidatePath)
    if (-not (Test-Path -LiteralPath $candidatePath -PathType Leaf)) {
        throw "Codex++ launch executable is not a regular leaf: $candidatePath"
    }
    $endpoint = Get-Item -LiteralPath $candidatePath -Force
    if ($endpoint.PSIsContainer -or -not ($endpoint -is [System.IO.FileInfo]) -or
        ($endpoint.Attributes -band [System.IO.FileAttributes]::ReparsePoint)) {
        throw "Codex++ launch executable endpoint is not a physical regular file: $candidatePath"
    }
    return $candidatePath
}

function Resolve-CodexExe {
    $storeRoot = [IO.Path]::GetFullPath("@@CODEXPP_INSTALL_ROOT:win@@\store-apps").TrimEnd("\")
    $packages = @(Get-AppxPackage -Name "OpenAI.Codex" -ErrorAction SilentlyContinue | Where-Object { $_.InstallLocation })
    if ($packages.Count -ne 1) {
        throw "Expected exactly one official OpenAI.Codex package, found $($packages.Count)"
    }

    # The official Appx is a read-only mirror source, never a launch target.
    # Derive the only legal Codex++ app root from its exact package identity.
    # This removes the shared TEMP cache and prevents a poisoned cache from
    # redirecting stale-process cleanup into ordinary Codex/WindowsApps.
    $packageIdentity = Split-Path -Leaf ([string]$packages[0].InstallLocation)
    if ($packageIdentity -notmatch '^OpenAI\.Codex_[^\\]+$') {
        throw "Invalid official Codex package identity: $packageIdentity"
    }
    $storePackageRoot = [IO.Path]::GetFullPath((Join-Path $storeRoot $packageIdentity)).TrimEnd("\")
    if (-not $storePackageRoot.StartsWith(($storeRoot + "\"), [StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing Codex++ executable outside the fixed store root: $storePackageRoot"
    }
    foreach ($component in @($storeRoot, $storePackageRoot, (Join-Path $storePackageRoot 'app'))) {
        if (Test-Path -LiteralPath $component) {
            $item = Get-Item -LiteralPath $component -Force
            if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) {
                throw "Refusing Codex++ executable through a reparse-point path: $component"
            }
        }
    }

    $appRoot = Join-Path $storePackageRoot 'app'
    $chatGptExe = Join-Path $appRoot 'ChatGPT.exe'
    $legacyExe = Join-Path $appRoot 'Codex.exe'
    if (Test-Path -LiteralPath $chatGptExe -PathType Leaf) { return $chatGptExe }
    if (Test-Path -LiteralPath $legacyExe -PathType Leaf) { return $legacyExe }

    # Return the fixed expected path even when a new Appx version has not yet
    # been mirrored. The Codex++ base repair CLI owns the mirror and loader
    # repair and will create the store copy before launch.
    return $chatGptExe
}

$codexExe = Resolve-CodexExe

function Test-ProxyEndpoint {
    param([string]$ProxyUrl)
    $uri = [Uri]$ProxyUrl
    $client = [Net.Sockets.TcpClient]::new()
    try {
        $async = $client.BeginConnect($uri.Host, $uri.Port, $null, $null)
        if (-not $async.AsyncWaitHandle.WaitOne(1500)) { return $false }
        $client.EndConnect($async)
        return $true
    } catch {
        return $false
    } finally {
        $client.Close()
    }
}

function Assert-CodexPlusPlusIdSanitizerWired {
    # Ensures the CodexIdSanitizer proxy (port 15740) is wired between the
    # Codex++ client and the CodexManager gateway (48760), so that tool call
    # ids from third-party models (msg_*) are rewritten to ctc_/fc_ before
    # reaching OpenAI-native models. Prevents the HTTP 400
    # "Expected an ID that begins with 'ctc'" regression on model switch.
    $sanitizerUrl = 'http://127.0.0.1:15740'
    $configToml = '@@CODEXPP_HOME:win@@\config.toml'
    $requiredBase = 'http://127.0.0.1:15740/v1'
    # The running LocalSystem service and this launcher must share one source
    # of truth. Do not freeze an adapter version here: the proxy source declares
    # the contract that its health endpoint exposes.
    $sanitizerScript = '@@SANITIZER_ROOT:win@@\codex-id-sanitizer-proxy.js'
    if (-not (Test-Path -LiteralPath $sanitizerScript -PathType Leaf)) {
        throw "CodexIdSanitizer source is missing: $sanitizerScript"
    }
    $sanitizerSource = [IO.File]::ReadAllText($sanitizerScript)
    $adapterMatch = [regex]::Match($sanitizerSource, 'const\s+ADAPTER_VERSION\s*=\s*"([^"]+)"')
    if (-not $adapterMatch.Success) {
        throw "CodexIdSanitizer source does not declare ADAPTER_VERSION: $sanitizerScript"
    }
    $expectedAdapter = $adapterMatch.Groups[1].Value

    # 1. Service running + port listening.
    $portUp = Test-ProxyEndpoint $sanitizerUrl
    if (-not $portUp) {
        # Try to start the service once (may need elevation; non-fatal if it fails).
        try {
            $svc = Get-Service -Name 'CodexIdSanitizer' -ErrorAction Stop
            if ($svc.Status -ne 'Running') {
                try { Start-Service -Name 'CodexIdSanitizer' -ErrorAction Stop } catch {}
                Start-Sleep -Seconds 2
                $svc = Get-Service -Name 'CodexIdSanitizer' -ErrorAction Stop
            }
            $portUp = ($svc.Status -eq 'Running') -and (Test-ProxyEndpoint $sanitizerUrl)
        } catch {
            $portUp = $false
        }
        if (-not $portUp) {
            Write-Warning "CodexIdSanitizer service not running or port 15740 not listening. Model-switch id sanitization is OFF; OpenAI-native model may 400 on replayed third-party tool calls. Start it elevated: nssm start CodexIdSanitizer"
        }
    }

    if ($portUp) {
        try {
            $health = Invoke-RestMethod -Uri "$sanitizerUrl/health" -Method Get -TimeoutSec 3 -ErrorAction Stop
            if ([string]$health.status -ne 'ok' -or [string]$health.adapter -ne $expectedAdapter) {
                throw "health=$([string]$health.status); adapter=$([string]$health.adapter); expected=$expectedAdapter"
            }
        } catch {
            throw "CodexIdSanitizer is listening but stale or unhealthy. Expected adapter $expectedAdapter; restart the LocalSystem service from an elevated PowerShell before launching Codex++: $($_.Exception.Message)"
        }
    }

    # 2. config.toml base_url must point at the sanitizer.
    if (Test-Path -LiteralPath $configToml -PathType Leaf) {
        $raw = [IO.File]::ReadAllText($configToml)
        if ($raw -notmatch 'base_url\s*=\s*"' + [regex]::Escape($requiredBase) + '"') {
            # Rewrite any base_url under [model_providers.cm] back to the sanitizer.
            $corrected = $raw -replace 'base_url\s*=\s*"https?://[^"]+"', "base_url = `"$requiredBase`""
            try {
                [IO.File]::WriteAllText($configToml, $corrected, (New-Object Text.UTF8Encoding $false))
                Write-Host "Assert-CodexPlusPlusIdSanitizerWired: config.toml base_url reset to $requiredBase" -ForegroundColor Yellow
            } catch {
                Write-Warning "Assert-CodexPlusPlusIdSanitizerWired: could not rewrite config.toml base_url. Model-switch id sanitization may be bypassed."
            }
        }
    }
}

function Test-CodexPlusPlusAppRootKillTarget {
    param(
        [Parameter(Mandatory = $true)][object]$Candidate,
        [Parameter(Mandatory = $true)][string]$AppRoot,
        [int]$OwnerProcessId = $PID
    )
    if ([int]$Candidate.ProcessId -eq $OwnerProcessId) { return $false }

    $allowedNames = @('ChatGPT.exe', 'Codex.exe', 'codex.exe', 'node.exe', 'node_repl.exe', 'codex-code-mode-host.exe')
    $processName = [string]$Candidate.Name
    $executablePath = [string]$Candidate.ExecutablePath
    if ([string]::IsNullOrWhiteSpace($executablePath)) { return $false }

    try {
        $fixedStoreRoot = [System.IO.Path]::GetFullPath('@@CODEXPP_INSTALL_ROOT:win@@\store-apps').TrimEnd('\')
        $root = [System.IO.Path]::GetFullPath($AppRoot).TrimEnd('\')
        $rootParent = Split-Path -Parent $root
        $packageIdentity = Split-Path -Leaf $rootParent
        $candidatePath = [System.IO.Path]::GetFullPath($executablePath)
        $executableName = [System.IO.Path]::GetFileName($candidatePath)
    } catch {
        return $false
    }

    # A kill authorization is stronger than a live-profile observation.  The
    # target app root must be an exact package app directory below the fixed
    # Codex++ store, and both WMI Name and physical ExecutablePath filename must
    # identify an allowlisted app-owned process.  Process arguments are never
    # evidence for Stop-Process authorization.
    if (-not $root.StartsWith(($fixedStoreRoot + '\'), [System.StringComparison]::OrdinalIgnoreCase)) { return $false }
    if (-not [string]::Equals((Split-Path -Leaf $root), 'app', [System.StringComparison]::OrdinalIgnoreCase)) { return $false }
    if ($packageIdentity -notlike 'OpenAI.Codex_*') { return $false }
    if ($allowedNames -notcontains $processName -or $allowedNames -notcontains $executableName) { return $false }
    if (-not [string]::Equals($processName, $executableName, [System.StringComparison]::OrdinalIgnoreCase)) { return $false }

    $rootPrefix = $root + '\'
    return $candidatePath.StartsWith($rootPrefix, [System.StringComparison]::OrdinalIgnoreCase)
}

function Get-CodexPlusPlusAppRootProcess {
    param([string]$AppRoot)
    Get-CimInstance Win32_Process | Where-Object {
        Test-CodexPlusPlusAppRootKillTarget -Candidate $_ -AppRoot $AppRoot -OwnerProcessId $PID
    }
}

function Get-CodexPlusPlusProfileStoreProcess {
    # Explicit -Restart is allowed to clear stale processes from older
    # Codex++ package roots as well as the currently resolved root.  Keep the
    # same physical store/name allowlist as Test-CodexPlusPlusAppRootKillTarget;
    # this never matches WindowsApps, ordinary Codex, or a process selected by
    # name alone.
    $fixedStoreRoot = [System.IO.Path]::GetFullPath('@@CODEXPP_INSTALL_ROOT:win@@\store-apps').TrimEnd('\')
    $storePrefix = $fixedStoreRoot + '\'
    $allowedNames = @('ChatGPT.exe', 'Codex.exe', 'codex.exe', 'node.exe', 'node_repl.exe', 'codex-code-mode-host.exe')
    Get-CimInstance Win32_Process | Where-Object {
        if ([int]$_.ProcessId -eq $PID) { return $false }
        $path = [string]$_.ExecutablePath
        if ([string]::IsNullOrWhiteSpace($path)) { return $false }
        try {
            $candidatePath = [System.IO.Path]::GetFullPath($path)
            $name = [System.IO.Path]::GetFileName($candidatePath)
        } catch { return $false }
        $candidatePath.StartsWith($storePrefix, [StringComparison]::OrdinalIgnoreCase) -and
            ($allowedNames -contains [string]$_.Name) -and
            ($allowedNames -contains $name) -and
            [string]::Equals([string]$_.Name, $name, [StringComparison]::OrdinalIgnoreCase)
    }
}

function Stop-CodexPlusPlusProfileStoreProcess {
    $targets = @(Get-CodexPlusPlusProfileStoreProcess)
    foreach ($target in $targets) {
        Write-Warning "Stopping stale Codex++ profile process $($target.ProcessId) $($target.Name) from fixed store"
        Stop-Process -Id $target.ProcessId -Force -ErrorAction SilentlyContinue
    }
    if ($targets.Count -gt 0) { Start-Sleep -Milliseconds 800 }
    return @(
        Get-CodexPlusPlusProfileStoreProcess
    ).Count
}

function Stop-CodexPlusPlusAppRootProcess {
    param([string]$AppRoot)
    if (Test-CodexPlusPlusProfileRunning) {
        throw 'WAIT_PROFILE_EXIT_REQUIRED: refusing to stop or repair an app root while the Codex++ profile is running'
    }
    $targets = @(Get-CodexPlusPlusAppRootProcess -AppRoot $AppRoot)
    if ($targets.Count -eq 0) { return 0 }

    foreach ($target in $targets) {
        Write-Warning "Stopping stale Codex++ app-root process $($target.ProcessId) $($target.Name)"
        Stop-Process -Id $target.ProcessId -Force -ErrorAction SilentlyContinue
    }

    Start-Sleep -Milliseconds 800
    return @(Get-CodexPlusPlusAppRootProcess -AppRoot $AppRoot).Count
}

function Get-StaleCodexPlusPlusMainProcess {
    param([string]$AppRoot)
    Get-CodexPlusPlusAppRootProcess -AppRoot $AppRoot | Where-Object {
        $cmd = [string]$_.CommandLine
        $process = Get-Process -Id $_.ProcessId -ErrorAction SilentlyContinue
        $_.Name -in @("Codex.exe", "ChatGPT.exe") -and
        $cmd.IndexOf("--type=", [System.StringComparison]::OrdinalIgnoreCase) -lt 0 -and
        $process -and
        $process.MainWindowHandle -eq 0
    }
}

$electronUserData = Join-Path $canonicalPlusProfile "AppData\Roaming\Codex"
$nestedCodexHome = Join-Path $electronUserData ".codex"
New-Item -ItemType Directory -Path $electronUserData -Force | Out-Null
if (-not (Test-Path -LiteralPath $nestedCodexHome)) {
    New-Item -ItemType Directory -Path $nestedCodexHome -Force | Out-Null
} else {
    $nestedItem = Get-Item -LiteralPath $nestedCodexHome -Force
    if ($nestedItem.Attributes -band [System.IO.FileAttributes]::ReparsePoint) {
        throw "Codex++ nested config path must be a physical D: directory: $nestedCodexHome"
    }
}

$env:USERPROFILE = $plusProfile
$env:HOME = $plusProfile
$env:APPDATA = Join-Path $canonicalPlusProfile 'AppData\Roaming'
# Windows Store package identity and the managed chatgpt-pp.exe alias remain
# system-owned under the real C: LOCALAPPDATA. Codex++ mutable data does not.
$env:LOCALAPPDATA = '@@USERPROFILE:win@@\AppData\Local'
# Keep the complete Codex++ process environment on the physical D: profile.
# The Windows Store app mirror remains an immutable package boundary.
$env:CODEX_HOME = $canonicalCodexHome
$env:CODEX_PLUSPLUS_HOME = Join-Path $canonicalPlusProfile 'AppData\Roaming\codex-plusplus'
$env:HOMEDRIVE = "D:"
$env:HOMEPATH = "\CodexPlusPlusProfile"
$env:CODEX_CHROME_USER_DATA_DIR = "@@USERPROFILE:win@@\AppData\Local\Google\Chrome\User Data"
# Keep Git's global config on the isolated Codex++ profile. This preserves
# normal Git status behavior while preventing a project or machine-level
# fsmonitor setting from starting an extra background file watcher.
$env:GIT_CONFIG_GLOBAL = Join-Path $canonicalPlusProfile ".gitconfig"
$env:GIT_OPTIONAL_LOCKS = "0"
$env:OPENCLAW_CONFIG_PATH = "@@USERPROFILE:win@@\.openclaw\openclaw.json"
$env:OPENCLAW_STATE_DIR = "@@USERPROFILE:win@@\.openclaw"
$personalAiSuiteBin = "@@SUITE_ROOT:win@@\bin"
if (-not (Test-Path -LiteralPath $personalAiSuiteBin -PathType Container)) {
    throw "Personal AI Suite command directory not found: $personalAiSuiteBin"
}
$env:PATH = "$personalAiSuiteBin$([IO.Path]::PathSeparator)$env:PATH"

foreach ($name in @("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY", "http_proxy", "https_proxy", "all_proxy", "no_proxy")) {
    Remove-Item "Env:\$name" -ErrorAction SilentlyContinue
}

if ($ProxyMode) {
    if (-not (Test-ProxyEndpoint $HttpProxy)) {
        throw "ProxyMode requested, but proxy is not listening: $HttpProxy"
    }
    $env:HTTP_PROXY = $HttpProxy
    $env:HTTPS_PROXY = $HttpProxy
    $env:ALL_PROXY = $AllProxy
    $env:NO_PROXY = $NoProxy
    $env:http_proxy = $HttpProxy
    $env:https_proxy = $HttpProxy
    $env:all_proxy = $AllProxy
    $env:no_proxy = $NoProxy
}

$tweakLinkCheck = "@@LAUNCHER_ROOT:win@@\Test-CodexPlusPlusTweakLinks.ps1"
$projectionSync = "@@GENERAL_ROOT:win@@\tooling\Sync-HostCapabilityProjection.ps1"
if ($codexExe) {
    $codexAppRoot = Split-Path -Parent $codexExe
    if ($codexPlusPlusResidueRecovery) {
        # Explicit -Restart, or the guard tripped on residue that cannot
        # present any main window: clear the whole current app root so the
        # profile guard can pass again.  The kill list stays name- and
        # path-bounded to this one store-apps package app directory.
        $remainingProfileStoreProcesses = Stop-CodexPlusPlusProfileStoreProcess
        if ($remainingProfileStoreProcesses -gt 0) {
            Write-Warning "Codex++ profile cleanup left $remainingProfileStoreProcesses fixed-store process(es)"
        }
        $residueProcesses = @(Get-CodexPlusPlusAppRootProcess -AppRoot $codexAppRoot)
        foreach ($target in $residueProcesses) {
            Write-Warning "Stopping Codex++ residue process $($target.ProcessId) $($target.Name)"
            Stop-Process -Id $target.ProcessId -Force -ErrorAction SilentlyContinue
        }
        if ($residueProcesses.Count -gt 0) { Start-Sleep -Milliseconds 800 }
    } else {
        $staleMainProcesses = @(Get-StaleCodexPlusPlusMainProcess -AppRoot $codexAppRoot)
        if ($staleMainProcesses.Count -gt 0) {
            foreach ($target in $staleMainProcesses) {
                Write-Warning "Stopping stale Codex++ main process $($target.ProcessId) $($target.Name)"
                Stop-Process -Id $target.ProcessId -Force -ErrorAction SilentlyContinue
            }
            Start-Sleep -Milliseconds 800
        }
    }
}
if (-not (Test-Path -LiteralPath $tweakLinkCheck)) {
    throw "Codex++ tweak link check not found: $tweakLinkCheck"
}
Write-Host "[LOG 1/9] Checking tweak links without source repair ($tweakLinkCheck)..." -ForegroundColor Yellow
$sw = [System.Diagnostics.Stopwatch]::StartNew()
& $powerShellExe -NoProfile -File $tweakLinkCheck
if ($LASTEXITCODE -ne 0) {
    throw "Codex++ tweak link check failed; source recovery remains owned by the controlled updater."
}
Write-Host "[LOG 1/9] Tweak link check passed (took $($sw.Elapsed.TotalSeconds)s)" -ForegroundColor Green

Write-Host "Starting Codex++" -ForegroundColor Green
Write-Host "Profile: $env:USERPROFILE" -ForegroundColor Cyan
Write-Host "Config : $env:CODEX_HOME" -ForegroundColor Cyan
Write-Host "OpenClaw: $env:OPENCLAW_CONFIG_PATH" -ForegroundColor Cyan
if ($ProxyMode) {
    Write-Host "Proxy  : $env:HTTPS_PROXY / $env:ALL_PROXY" -ForegroundColor Cyan
} else {
    Write-Host "Proxy  : cleared" -ForegroundColor Cyan
}

if (-not $codexExe) {
    throw "ChatGPT.exe/Codex.exe not found under WindowsApps or codex-plusplus store-apps."
}

$codexAppRoot = Split-Path -Parent $codexExe
Write-Host "[LOG 3/9] Stopping stale main processes in app-root: $codexAppRoot..." -ForegroundColor Yellow
$sw.Restart()
$remainingAppRootProcesses = Stop-CodexPlusPlusAppRootProcess -AppRoot $codexAppRoot
if ($remainingAppRootProcesses -gt 0) {
    Write-Warning "Codex++ restart cleanup left $remainingAppRootProcesses app-root process(es): $codexAppRoot"
}
Write-Host "[LOG 3/9] Process cleanup done (took $($sw.Elapsed.TotalSeconds)s)" -ForegroundColor Green

# Reasoning effort stays in Codex per-thread state; do not rewrite global config at startup.

Write-Host "[LOG 4/9] Cleaning up stale tweak host processes..." -ForegroundColor Yellow
$sw.Restart()
$staleTweakProcesses = @(Get-CimInstance Win32_Process | Where-Object {
    Test-ExactCodexPlusPlusTweakHostProcess -Process $_
})
foreach ($target in $staleTweakProcesses) {
    Write-Warning "Stopping stale Codex++ tweak process $($target.ProcessId) $($target.Name)"
    Stop-Process -Id $target.ProcessId -Force -ErrorAction SilentlyContinue
}
Write-Host "[LOG 4/9] Stale tweak hosts cleaned (took $($sw.Elapsed.TotalSeconds)s)" -ForegroundColor Green

function Get-CodexPlusPlusRepairReason {
    param(
        [bool]$RepairDisabled,
        [bool]$ForceRequested,
        [bool]$StoreAppPresent,
        [Nullable[int]]$InjectionPreflightExitCode
    )
    if ($RepairDisabled) { return $null }
    if ($ForceRequested) { return 'force_repair_requested' }
    if (-not $StoreAppPresent) { return 'current_official_store_app_missing' }
    if ($null -eq $InjectionPreflightExitCode) {
        throw 'Healthy-store repair decision requires an injection preflight result.'
    }
    if ($InjectionPreflightExitCode -ne 0) { return 'loader_or_tweak_injection_drift' }
    return $null
}

$codexPlusPlusMaintenance = "@@LAUNCHER_ROOT:win@@\Sync-CodexPlusPlusLatest.ps1"
$injectionGuard = "@@LAUNCHER_ROOT:win@@\Test-CodexPlusPlusInjection.ps1"
if (-not (Test-Path -LiteralPath $injectionGuard -PathType Leaf)) {
    throw "Codex++ injection guard not found: $injectionGuard"
}
$preflightInjectionVerified = $false
$storeAppPresent = Test-Path -LiteralPath $codexExe -PathType Leaf
$injectionPreflightExitCode = $null
if (-not $SkipRepair -and -not $ForceRepair -and $storeAppPresent) {
    $injectionPreflightRaw = @(& $powerShellExe -NoProfile -File $injectionGuard -AppRoot $codexAppRoot 2>&1)
    $injectionPreflightExitCode = $LASTEXITCODE
    if ($injectionPreflightExitCode -eq 0) {
        $preflightInjectionVerified = $true
    } else {
        Write-Warning "Codex++ injection drift requires one-shot repair: $($injectionPreflightRaw -join "`n")"
    }
}
$repairReason = Get-CodexPlusPlusRepairReason `
    -RepairDisabled ([bool]$SkipRepair) `
    -ForceRequested ([bool]$ForceRepair) `
    -StoreAppPresent ([bool]$storeAppPresent) `
    -InjectionPreflightExitCode $injectionPreflightExitCode
$shouldRepair = -not $SkipRepair -and -not [string]::IsNullOrWhiteSpace($repairReason)
$maintenanceHandledProjectionAndInjection = $false
if ($shouldRepair) {
    if (-not (Test-Path -LiteralPath $codexPlusPlusMaintenance -PathType Leaf)) {
        throw "Codex++ one-shot maintenance entry missing: $codexPlusPlusMaintenance"
    }
    Write-Host "[LOG 5/9] Running Codex++ one-shot repair/update maintenance (reason=$repairReason)..." -ForegroundColor Yellow
    $sw.Restart()
    $remainingAppRootProcesses = Stop-CodexPlusPlusAppRootProcess -AppRoot $codexAppRoot
    if ($remainingAppRootProcesses -gt 0) {
        Write-Warning "Codex++ repair skipped because $remainingAppRootProcesses process(es) still hold app root: $codexAppRoot"
    } else {
        $maintenanceArguments = @('-NoLogo', '-NoProfile', '-File', $codexPlusPlusMaintenance, '-Once', '-RequireStoppedProfile')
        if ($ForceRepair) { $maintenanceArguments += '-ForceRepair' }
        $maintenanceRaw = @(& $powerShellExe @maintenanceArguments 2>&1)
        $maintenanceExitCode = $LASTEXITCODE
        if ($maintenanceExitCode -ne 0) {
            throw "Codex++ one-shot maintenance failed before launch (exit $maintenanceExitCode): $($maintenanceRaw -join "`n")"
        }
        $maintenanceHandledProjectionAndInjection = $true
    }
    Write-Host "[LOG 5/9] One-shot maintenance completed (took $($sw.Elapsed.TotalSeconds)s)" -ForegroundColor Green
} elseif ($SkipRepair) {
    Write-Host "[LOG 5/9] Repair skipped by configuration" -ForegroundColor Cyan
} else {
    Write-Host "[LOG 5/9] Current store and injection are healthy; full repair is not required" -ForegroundColor Green
}

if (-not $maintenanceHandledProjectionAndInjection -and (Test-Path -LiteralPath $projectionSync -PathType Leaf)) {
    Write-Host "[HOST CAPABILITIES] Applying canonical Manifest projection..." -ForegroundColor Yellow
$projectionRaw = @(& $powerShellExe -NoProfile -File $projectionSync -HostId codex_plus_plus -SkillsRoot (Join-Path $canonicalCodexHome 'skills') -Mode Apply 2>&1)
    $projectionExitCode = $LASTEXITCODE
    if ($projectionExitCode -ne 0) {
        Write-Warning "Host capability projection reported a non-blocking conflict/failure (exit $projectionExitCode): $($projectionRaw -join "`n")"
    } else {
        Write-Host "[HOST CAPABILITIES] Projection applied." -ForegroundColor Green
    }
} elseif (-not $maintenanceHandledProjectionAndInjection) {
    Write-Warning "Host capability projection script missing; continuing Host launch: $projectionSync"
}

if (-not $maintenanceHandledProjectionAndInjection -and -not $preflightInjectionVerified) {
    Write-Host "[LOG 6/9] Verifying loader injection ($injectionGuard)..." -ForegroundColor Yellow
    $sw.Restart()
    & $powerShellExe -NoProfile -File $injectionGuard -AppRoot $codexAppRoot
    if ($LASTEXITCODE -ne 0) {
        throw "Codex++ injection guard failed; refusing to launch without loader/tweaks: $codexAppRoot"
    }
    Write-Host "[LOG 6/9] Injection verified (took $($sw.Elapsed.TotalSeconds)s)" -ForegroundColor Green
} elseif ($maintenanceHandledProjectionAndInjection) {
    Write-Host "[LOG 6/9] Injection already verified by one-shot maintenance." -ForegroundColor Green
} else {
    Write-Host "[LOG 6/9] Injection already verified by lightweight startup preflight." -ForegroundColor Green
}

# Resolve the executable again after the Codex++ base mirror/repair. The
# preflight may have returned a not-yet-created expected ChatGPT.exe path for a
# newly installed Appx identity, and older packages may still use Codex.exe.
$codexExe = @(
    (Join-Path $codexAppRoot 'ChatGPT.exe'),
    (Join-Path $codexAppRoot 'Codex.exe')
) | Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } | Select-Object -First 1
if (-not $codexExe) {
    throw "Codex++ launch executable is missing after authoritative repair: $codexAppRoot"
}
$codexExe = Assert-CodexPlusPlusLaunchExecutable -ExecutablePath $codexExe -ExpectedAppRoot $codexAppRoot

$syncConnectorsAfterMaintenance = $maintenanceHandledProjectionAndInjection
if (-not $SkipConnectorSync -or $syncConnectorsAfterMaintenance) {
    $connectorSync = "@@LAUNCHER_ROOT:win@@\Sync-CodexPlusPlusConnectors.ps1"
    if (Test-Path -LiteralPath $connectorSync) {
        $connectorSyncReason = if ($syncConnectorsAfterMaintenance -and $SkipConnectorSync) { 'post-maintenance override' } else { 'requested by launch mode' }
        Write-Host "[LOG 7/9] Syncing connectors ($connectorSync; $connectorSyncReason)..." -ForegroundColor Yellow
        $sw.Restart()
        & $connectorSync
        Write-Host "[LOG 7/9] Connectors synced (took $($sw.Elapsed.TotalSeconds)s)" -ForegroundColor Green
    }
} else {
    Write-Host "[LOG 7/9] Connector sync skipped" -ForegroundColor Cyan
}

$syncOpenCliAfterMaintenance = $maintenanceHandledProjectionAndInjection
if (-not $SkipOpenCliAdapterSync -or $syncOpenCliAfterMaintenance) {
    $openCliAdapterSync = "@@LAUNCHER_ROOT:win@@\Sync-OpenCliAdapters.ps1"
    if (Test-Path -LiteralPath $openCliAdapterSync) {
        $openCliSyncReason = if ($syncOpenCliAfterMaintenance -and $SkipOpenCliAdapterSync) { 'post-maintenance override' } else { 'requested by launch mode' }
        Write-Host "[LOG 8/9] Syncing OpenCLI adapters ($openCliAdapterSync; $openCliSyncReason)..." -ForegroundColor Yellow
        $sw.Restart()
        # Codex++ startup may update only its isolated OpenCLI home.  Normal
        # user adapters are managed by their own workflow, not by this host.
        & $openCliAdapterSync -SharedClisRoot (Join-Path $canonicalPlusProfile '.opencli-shared\clis') -TargetHomes @($canonicalPlusProfile)
        Write-Host "[LOG 8/9] OpenCLI adapters synced (took $($sw.Elapsed.TotalSeconds)s)" -ForegroundColor Green
    }
} else {
    Write-Host "[LOG 8/9] OpenCLI adapters sync skipped" -ForegroundColor Cyan
}

# Use the bundled official CLI as the source of truth. If an app update invalidates
# the sandbox marker/users, this performs exactly one UAC-backed repair before the UI starts.
$sandboxCli = Join-Path $codexAppRoot "resources\codex.exe"
if (-not (Test-Path -LiteralPath $sandboxCli)) {
    throw "Codex++ Windows sandbox CLI not found: $sandboxCli"
}
Write-Host "[SANDBOX] Verifying Windows sandbox before launch..." -ForegroundColor Yellow
$sandboxPreflightArgs = @("sandbox", "cmd.exe", "/d", "/c", "exit 0")
$sandboxPreflightOutput = @(& $sandboxCli @sandboxPreflightArgs 2>&1)
$sandboxPreflightExitCode = $LASTEXITCODE
if ($sandboxPreflightExitCode -ne 0) {
    $sandboxPreflightMessage = ($sandboxPreflightOutput | ForEach-Object { [string]$_ }) -join " "
    throw "Codex++ Windows 沙箱初始化失败（退出码 $sandboxPreflightExitCode）。请重新运行桌面入口，并在唯一一次 UAC 弹窗中点击 Yes。详情：$sandboxPreflightMessage"
}
Write-Host "[SANDBOX] Windows sandbox ready." -ForegroundColor Green

$sessionPathWatcher = "@@LAUNCHER_ROOT:win@@\Watch-CodexPlusPlusSessionPaths.ps1"
$sessionPathTest = "@@LAUNCHER_ROOT:win@@\Test-CodexPlusPlusSessionPaths.ps1"
if ($RunSessionMaintenance -and (Test-Path -LiteralPath $sessionPathWatcher)) {
    Write-Host "[LOG 9/9] Running one-shot session maintenance..." -ForegroundColor Yellow
    $sw.Restart()
    $staleSessionWatchers = @(Get-CimInstance Win32_Process | Where-Object {
        Test-ExactPowerShellFileProcess -Process $_ -ScriptPath $sessionPathWatcher -RequiredSwitch '-Watch' -AllowLegacyWindowsPowerShell
    })
    foreach ($target in $staleSessionWatchers) {
        Write-Warning "Stopping stale Codex++ session watcher $($target.ProcessId) $($target.Name)"
        Stop-Process -Id $target.ProcessId -Force -ErrorAction SilentlyContinue
    }

    if (-not $SkipSessionPathTest) {
        & $sessionPathWatcher
        if (-not (Test-Path -LiteralPath $sessionPathTest)) {
            throw "Codex++ session path test not found: $sessionPathTest"
        }
        & $sessionPathTest
    } else {
        Write-Host "Session path verification tests skipped by configuration" -ForegroundColor Cyan
    }

    Write-Host "[LOG 9/9] One-shot session maintenance completed; no background watcher is started (took $($sw.Elapsed.TotalSeconds)s)" -ForegroundColor Green
} elseif (-not $RunSessionMaintenance) {
    Write-Host "[LOG 9/9] Session maintenance skipped by default; rollout_path triggers and the normalizer tweak remain active." -ForegroundColor Cyan
}

$repairToolCallIds = "@@LAUNCHER_ROOT:win@@\Repair-CodexToolCallIds.ps1"
if (Test-Path -LiteralPath $repairToolCallIds) {
    & $repairToolCallIds | Out-Null
}

$nativeMessagingRestore = '@@LAUNCHER_ROOT:win@@\Restore-CodexPlusPlusNativeMessagingHost.ps1'
if (-not (Test-Path -LiteralPath $nativeMessagingRestore -PathType Leaf)) {
    throw "Codex++ Native Messaging Host compare-and-set guard missing: $nativeMessagingRestore"
}
$nativeMessagingSubKey = 'SOFTWARE\Google\Chrome\NativeMessagingHosts\com.openai.codexextension'
$nativeMessagingKey = [Microsoft.Win32.Registry]::CurrentUser.OpenSubKey($nativeMessagingSubKey, $false)
try {
    $nativeMessagingPriorExisted = $nativeMessagingKey -and (@($nativeMessagingKey.GetValueNames()) -contains '')
    $nativeMessagingPriorValue = if ($nativeMessagingPriorExisted) {
        [string]$nativeMessagingKey.GetValue('', $null, [Microsoft.Win32.RegistryValueOptions]::DoNotExpandEnvironmentNames)
    } else { $null }
    $nativeMessagingPriorKind = if ($nativeMessagingPriorExisted) { $nativeMessagingKey.GetValueKind('').ToString() } else { 'String' }
} finally { if ($nativeMessagingKey) { $nativeMessagingKey.Dispose() } }
$nativeMessagingPriorBase64 = if ($nativeMessagingPriorExisted) {
    [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($nativeMessagingPriorValue))
} else { '' }
$nativeMessagingArguments = @(
    '-NoProfile', '-File', $nativeMessagingRestore,
    '-PriorValueBase64', $nativeMessagingPriorBase64,
    '-PriorValueKind', $nativeMessagingPriorKind
)
if ($nativeMessagingPriorExisted) { $nativeMessagingArguments += '-PriorValueExisted' }
Start-Process -FilePath $powerShellExe -ArgumentList $nativeMessagingArguments -WindowStyle Hidden
& "@@LAUNCHER_ROOT:win@@\Sync-CodexPlusPlusModelCatalog.ps1"
Assert-CodexPlusPlusIdSanitizerWired
Write-Host ">>> Launching ChatGPT.exe/Codex.exe via Start-Process..." -ForegroundColor Green
# codexpp:identity-launch-auto: ChatGPT 26.915+ 需包身份，由 Invoke-CodexPlusPlusLauncherCompat.ps1 自动维护，请勿手改
& (Join-Path $PSScriptRoot 'Invoke-CodexPlusPlusIdentityLaunch.ps1') -CodexExe $codexExe -Profile $canonicalPlusProfile
Write-Host 'NativeMessagingHost: compare-and-set restoration guard armed.' -ForegroundColor Cyan

if ($startupLockTaken) {
    $startupMutex.ReleaseMutex()
}
$startupMutex.Dispose()
