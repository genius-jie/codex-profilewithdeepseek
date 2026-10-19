[Console]::InputEncoding = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$raw = [Console]::In.ReadToEnd()
if ([string]::IsNullOrWhiteSpace($raw)) {
  exit 0
}

try {
  $payload = $raw | ConvertFrom-Json
} catch {
  @{ systemMessage = "Read parameter guard: hook input is not valid JSON; leaving tool call unchanged." } | ConvertTo-Json -Depth 10 -Compress
  exit 0
}

if ($payload.tool_name -ne 'Read' -or $null -eq $payload.tool_input) {
  exit 0
}

function Get-Int64OrNull {
  param($Value)

  if ($null -eq $Value) {
    return $null
  }

  $parsed = [int64]0
  if ([int64]::TryParse(([string]$Value), [ref]$parsed)) {
    return $parsed
  }

  return $null
}

function Set-OrderedValue {
  param(
    [System.Collections.Specialized.OrderedDictionary]$Target,
    [string]$Name,
    $Value
  )

  if ($Target.Contains($Name)) {
    $Target[$Name] = $Value
  } else {
    $Target.Add($Name, $Value)
  }
}

function Get-LineCountIfSmall {
  param(
    [string]$Path,
    [int64]$MaxBytes = 20971520
  )

  if ([string]::IsNullOrWhiteSpace($Path)) {
    return $null
  }

  try {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
      return $null
    }

    $item = Get-Item -LiteralPath $Path -ErrorAction Stop
    if ($item.Length -gt $MaxBytes) {
      return $null
    }

    $count = [int64]0
    foreach ($null in [System.IO.File]::ReadLines($item.FullName)) {
      $count++
    }
    return $count
  } catch {
    return $null
  }
}

function Write-ReadGuardEvent {
  param([hashtable]$Record)

  try {
    $logDir = Join-Path $PSScriptRoot 'logs'
    New-Item -ItemType Directory -Path $logDir -Force | Out-Null
    $Record['timestamp'] = (Get-Date).ToUniversalTime().ToString('o')
    $logPath = Join-Path $logDir 'read-guard-events.jsonl'
    ($Record | ConvertTo-Json -Depth 8 -Compress) | Add-Content -LiteralPath $logPath -Encoding UTF8
  } catch {
  }
}

$inputObject = $payload.tool_input
$props = @($inputObject.PSObject.Properties.Name)
$filePath = [string]$inputObject.file_path
$extension = [System.IO.Path]::GetExtension($filePath).ToLowerInvariant()
$hasPages = $props -contains 'pages'
$pagesValue = if ($hasPages) { $inputObject.pages } else { $null }
$pagesText = if ($null -eq $pagesValue) { '' } else { [string]$pagesValue }
$hasBlankPages = $hasPages -and [string]::IsNullOrWhiteSpace($pagesText)
$isPdf = $extension -eq '.pdf'

$shouldRemovePages = $hasPages -and ($hasBlankPages -or (-not $isPdf))
if ($hasPages -and $isPdf -and (-not $hasBlankPages) -and ($pagesText -notmatch '^\d+(?:-\d+)?$')) {
  Write-ReadGuardEvent @{
    action = 'deny'
    file_path = $filePath
    extension = $extension
    pages_present = $true
    reason = 'invalid_pdf_pages'
  }

  @{
    decision = 'block'
    reason = "Read parameter guard blocked invalid PDF pages value '$pagesText'. Use formats like '1-5', '3', or '10-20'. For non-PDF/text files, omit pages entirely."
    hookSpecificOutput = @{
      hookEventName = 'PreToolUse'
      permissionDecision = 'deny'
      permissionDecisionReason = "Invalid Read.pages value for PDF: '$pagesText'."
    }
  } | ConvertTo-Json -Depth 10 -Compress
  exit 0
}

$sanitized = [ordered]@{}
foreach ($name in $props) {
  if ($name -ne 'pages' -or (-not $shouldRemovePages)) {
    $sanitized[$name] = $inputObject.PSObject.Properties[$name].Value
  }
}

$changes = New-Object System.Collections.Generic.List[string]

if ($shouldRemovePages) {
  if ($hasBlankPages) {
    $changes.Add('removed blank Read.pages optional parameter')
  } else {
    $changes.Add("removed Read.pages from non-PDF file '$extension'")
  }
}

$hasLimit = $props -contains 'limit'
$limitValue = if ($hasLimit) { Get-Int64OrNull $inputObject.limit } else { $null }
$effectiveLimit = if ($null -ne $limitValue -and $limitValue -gt 0) { $limitValue } else { [int64]200 }

if ($hasLimit) {
  if ($null -eq $limitValue -or $limitValue -le 0) {
    $effectiveLimit = [int64]120
    Set-OrderedValue $sanitized 'limit' $effectiveLimit
    $changes.Add('normalized invalid Read.limit to 120')
  } elseif ($limitValue -gt 2000) {
    $effectiveLimit = [int64]2000
    Set-OrderedValue $sanitized 'limit' $effectiveLimit
    $changes.Add("clamped Read.limit from $limitValue to 2000")
  }
}

$hasOffset = $props -contains 'offset'
$offsetValue = if ($hasOffset) { Get-Int64OrNull $inputObject.offset } else { $null }

if ($hasOffset) {
  if ($null -eq $offsetValue -or $offsetValue -lt 0) {
    Set-OrderedValue $sanitized 'offset' ([int64]0)
    $changes.Add('normalized invalid Read.offset to 0')
  } else {
    $lineCount = Get-LineCountIfSmall $filePath
    if ($null -ne $lineCount -and $offsetValue -gt $lineCount) {
      $newOffset = [Math]::Max([int64]0, ([int64]$lineCount - [int64]$effectiveLimit))
      Set-OrderedValue $sanitized 'offset' $newOffset
      $changes.Add("clamped Read.offset past EOF from $offsetValue to $newOffset")
    } elseif ($offsetValue -gt 1000000) {
      Set-OrderedValue $sanitized 'offset' ([int64]0)
      $changes.Add("clamped implausible Read.offset from $offsetValue to 0")
    }
  }
}

if ($changes.Count -gt 0) {
  $reason = $changes -join '; '
  Write-ReadGuardEvent @{
    action = 'allow_updated_input'
    file_path = $filePath
    extension = $extension
    pages_present = $hasPages
    changes = @($changes)
  }

  @{
    systemMessage = "Read parameter guard: $reason."
    hookSpecificOutput = @{
      hookEventName = 'PreToolUse'
      permissionDecision = 'allow'
      permissionDecisionReason = $reason
      updatedInput = $sanitized
      additionalContext = "Read guard normalized tool input: optional pages must be omitted unless reading a PDF with an explicit non-empty page range."
    }
  } | ConvertTo-Json -Depth 20 -Compress
  exit 0
}

exit 0
