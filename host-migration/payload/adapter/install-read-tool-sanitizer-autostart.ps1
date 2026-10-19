param(
  [switch]$NoStart
)

$ErrorActionPreference = 'Stop'

$taskName = 'ReadToolSanitizerWatchdog'
$watchScript = Join-Path $PSScriptRoot 'watch-read-tool-sanitizer.ps1'
$ensureScript = Join-Path $PSScriptRoot 'ensure-read-tool-sanitizer.ps1'
$userId = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$runKey = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run'
$runValueName = 'ReadToolSanitizerWatchdog'
$watchCommand = "powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$watchScript`""

$action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$watchScript`""
$trigger = New-ScheduledTaskTrigger -AtLogOn
$principal = New-ScheduledTaskPrincipal -UserId $userId -LogonType Interactive
$settings = New-ScheduledTaskSettingsSet `
  -AllowStartIfOnBatteries `
  -DontStopIfGoingOnBatteries `
  -ExecutionTimeLimit (New-TimeSpan -Seconds 0) `
  -MultipleInstances IgnoreNew `
  -RestartCount 3 `
  -RestartInterval (New-TimeSpan -Minutes 1)

$installMode = 'scheduled_task'
$scheduledTaskError = $null

try {
  Register-ScheduledTask `
    -TaskName $taskName `
    -Action $action `
    -Trigger $trigger `
    -Principal $principal `
    -Settings $settings `
    -Description 'Keeps the Claude Code Read tool sanitizer proxy alive on 127.0.0.1:15722.' `
    -Force | Out-Null
} catch {
  $installMode = 'hkcu_run'
  $scheduledTaskError = $_.Exception.Message
  New-Item -Path $runKey -Force | Out-Null
  Set-ItemProperty -Path $runKey -Name $runValueName -Value $watchCommand
}

if (-not $NoStart) {
  & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $ensureScript | Out-Null
  if ($installMode -eq 'scheduled_task') {
    Start-ScheduledTask -TaskName $taskName
  } else {
    Start-Process -FilePath powershell.exe -WindowStyle Hidden -ArgumentList @(
      '-NoProfile',
      '-ExecutionPolicy',
      'Bypass',
      '-File',
      $watchScript
    )
  }
}

[pscustomobject]@{
  InstallMode = $installMode
  TaskName = if ($installMode -eq 'scheduled_task') { $taskName } else { $null }
  RunKey = if ($installMode -eq 'hkcu_run') { $runKey } else { $null }
  RunValueName = if ($installMode -eq 'hkcu_run') { $runValueName } else { $null }
  ScheduledTaskError = $scheduledTaskError
}
