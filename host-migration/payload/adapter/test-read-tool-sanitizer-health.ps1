param(
  [switch]$Strict,
  [int]$TimeoutMs = 1000
)

$ErrorActionPreference = 'Stop'

$listenHost = if ($env:READ_SANITIZER_HOST) { $env:READ_SANITIZER_HOST } else { '127.0.0.1' }
$listenPort = if ($env:READ_SANITIZER_PORT) { [int]$env:READ_SANITIZER_PORT } else { 15722 }
$upstreamUri = if ($env:READ_SANITIZER_UPSTREAM) { [uri]$env:READ_SANITIZER_UPSTREAM } else { [uri]'http://127.0.0.1:48760' }
$upstreamPort = if ($upstreamUri.Port -gt 0) { $upstreamUri.Port } elseif ($upstreamUri.Scheme -eq 'https') { 443 } else { 80 }

function Test-TcpPort {
  param(
    [string]$HostName,
    [int]$Port,
    [int]$Timeout
  )

  $client = [System.Net.Sockets.TcpClient]::new()
  try {
    $async = $client.BeginConnect($HostName, $Port, $null, $null)
    if (-not $async.AsyncWaitHandle.WaitOne($Timeout, $false)) {
      return $false
    }
    $client.EndConnect($async)
    return $true
  } catch {
    return $false
  } finally {
    $client.Dispose()
  }
}

$sanitizerTcp = Test-TcpPort -HostName $listenHost -Port $listenPort -Timeout $TimeoutMs
$sanitizerHttp = $false
$health = $null
$healthError = $null

if ($sanitizerTcp) {
  try {
    $timeoutSec = [Math]::Max(1, [Math]::Ceiling($TimeoutMs / 1000))
    $health = Invoke-RestMethod -Uri "http://${listenHost}:${listenPort}/__read_sanitizer/health" -TimeoutSec $timeoutSec
    $sanitizerHttp = [bool]$health.ok
  } catch {
    $healthError = $_.Exception.Message
  }
}

$upstreamTcp = Test-TcpPort -HostName $upstreamUri.Host -Port $upstreamPort -Timeout $TimeoutMs
$ok = $sanitizerTcp -and $sanitizerHttp
if ($Strict) {
  $ok = $ok -and $upstreamTcp
}

$result = [ordered]@{
  ok = [bool]$ok
  strict = [bool]$Strict
  sanitizer_tcp = [bool]$sanitizerTcp
  sanitizer_http = [bool]$sanitizerHttp
  sanitizer = "http://${listenHost}:${listenPort}"
  upstream_tcp = [bool]$upstreamTcp
  upstream = $upstreamUri.ToString()
  health = $health
  health_error = $healthError
  checked_at = (Get-Date).ToString('o')
}

$result | ConvertTo-Json -Depth 6
if (-not $ok) {
  exit 1
}
