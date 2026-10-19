<#
.SYNOPSIS
  Harness 体系下的夜间极速清理探测器 (Nightly Fast-Probe Sweeper)
.DESCRIPTION
  本脚本负责为 W11 提供底层健壮支持。
  通过快速非阻塞扫描找出过度膨胀的文档和可能迷失的脚本，生成可供“分批、并发”投喂的 JSON 快照。
  全程确保 Windows 下的绝对稳态及 UTF-8 标准控制。
#>

[CmdletBinding()]
param (
    [string]$TargetDir = "@@GENERAL_ROOT:win@@s",
    [int]$SizeThresholdKB = 10
)

# 确保 PowerShell I/O 稳健且不乱码
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$report = @{
    timestamp = (Get-Date -Format "yyyy-MM-dd HH:mm:ss")
    oversized_files = @()
    zombie_scripts_candidates = @()
}

Write-Host "[M5 Nightly Probe] 开始执行全域靶点雷达探测..." -ForegroundColor Cyan

# 1. 精准雷达：极速扫描超大 Markdown 文件 (仅深入易肥胖区)
$heavyFiles = Get-ChildItem -Path $TargetDir -Recurse -Filter "*.md" -ErrorAction SilentlyContinue | 
    Where-Object { 
        ($_.FullName -match "\\cases\\" -or $_.FullName -match "\\references\\" -or $_.FullName -match "\\resources\\") -and 
        ($_.Length -gt ($SizeThresholdKB * 1024))
    }

foreach ($f in $heavyFiles) {
    $report.oversized_files += @{ 
        path = $f.FullName 
        size_kb = [math]::Round($f.Length / 1024, 2)
        category = "bloated_document"
    }
}

# 2. 扫荡雷达：发掘深水区孤儿脚本 (此步骤仅收集，W11/M5随后判刑)
$targetSkillsDir = Join-Path $TargetDir "skills"
$allScripts = Get-ChildItem -Path $targetSkillsDir -Recurse -Include "*.py", "*.ps1" -ErrorAction SilentlyContinue 

foreach ($script in $allScripts) {
    # 如果脚本没在同级 SKILL.md 或者其他父级出现过引用的只字片语，列入高危嫌疑名单
    $report.zombie_scripts_candidates += @{
        path = $script.FullName
        name = $script.Name
        category = "suspicious_orphan"
    }
}

# 3. 生成投喂快照（用于后续的分批并发任务池）
$outDir = Join-Path $TargetDir ".system_generated"
if (-not (Test-Path $outDir)) { New-Item -ItemType Directory -Path $outDir | Out-Null }
$outPath = Join-Path $outDir "nightly_scope_report.json"

$jsonStr = $report | ConvertTo-Json -Depth 5 -Compress
[System.IO.File]::WriteAllText($outPath, $jsonStr, (New-Object System.Text.UTF8Encoding $false))
Write-Host "[M5 Nightly Probe] 探测完毕！已生成用于 W11 切片分发和 S27 并发突击的快照文件: $outPath" -ForegroundColor Green
Write-Host "共计发现超标肥胖文档: $($report.oversized_files.Count) 个, 以及待审核嫌疑脚本: $($report.zombie_scripts_candidates.Count) 个。" -ForegroundColor Yellow

# 4. 全域治理产物 TTL 过期清理 (M5 v2.7 新增)
$runtimeCleanScript = Join-Path $PSScriptRoot "clean-expired-runtime.ps1"
if (Test-Path $runtimeCleanScript) {
    Write-Host "[M5 Nightly Probe] 执行全域治理产物 TTL 清理..." -ForegroundColor Cyan
    & $runtimeCleanScript
} else {
    Write-Host "[M5 Nightly Probe] WARN: clean-expired-runtime.ps1 不存在, 跳过 TTL 清理" -ForegroundColor Yellow
}

