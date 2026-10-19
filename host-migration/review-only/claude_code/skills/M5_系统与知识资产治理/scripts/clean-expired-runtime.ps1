# 全域运行时治理产物清理脚本 (M5 垃圾回收引擎专属)
# 用途：清理 openclaw-mono/projects/ 下所有项目的治理中间态产物
# 安全边界：只清理 docs/specs、docs/reviews、src/docs/specs、.gemini/scratch
#           绝不碰 scratch/（构建产出）、logs/（运行日志）等功能依赖目录
# 幂等设计：跑一次和跑一万次结果一致
# 编码：UTF-8 无 BOM

[CmdletBinding(SupportsShouldProcess)]
param(
    [string]$ProjectsRoot = "@@OPENCLAW_ROOT:win@@\projects",
    [int]$RetentionDays = 7,
    [string[]]$ProtectedProjectRoots = @(
        "@@OPENCLAW_ROOT:win@@\projects\automation-core"
    )
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $ProjectsRoot)) {
    Write-Host "[M5-RUNTIME-TTL] 目标目录不存在: $ProjectsRoot"
    exit 1
}

$cutoff = (Get-Date).AddDays(-$RetentionDays)

# 安全清理目标：只有这些子路径会被扫描和清理
# 这些都是纯治理中间态，不被任何功能代码依赖
$safeSubPaths = @(
    "docs\specs",
    "docs\reviews",
    "src\docs\specs",
    ".gemini\scratch"
)

$totalExpired = 0
$totalDeleted = 0
$resolvedProtectedRoots = @(
    $ProtectedProjectRoots | ForEach-Object {
        [System.IO.Path]::GetFullPath($_).TrimEnd("\")
    }
)
$projectDirs = Get-ChildItem -LiteralPath $ProjectsRoot -Directory

foreach ($proj in $projectDirs) {
    $resolvedProjectRoot = [System.IO.Path]::GetFullPath($proj.FullName).TrimEnd("\")
    if ($resolvedProtectedRoots -contains $resolvedProjectRoot) {
        Write-Host "[M5-RUNTIME-TTL] SKIP - protected retained archive: $resolvedProjectRoot"
        continue
    }
    foreach ($sub in $safeSubPaths) {
        $targetDir = Join-Path $proj.FullName $sub
        if (-not (Test-Path -LiteralPath $targetDir)) { continue }

        $oldItems = Get-ChildItem -LiteralPath $targetDir | Where-Object { $_.LastWriteTime -lt $cutoff }
        if ($oldItems.Count -eq 0) { continue }

        $totalExpired += $oldItems.Count
        Write-Host "[M5-RUNTIME-TTL] $($proj.Name)\$($sub): $($oldItems.Count) 项过期"

        if ($WhatIfPreference) {
            $oldItems | ForEach-Object {
                $type = if ($_.PSIsContainer) { "DIR" } else { "FILE" }
                Write-Host "  [$type] $($_.Name)  ($($_.LastWriteTime.ToString('yyyy-MM-dd')))"
            }
        } else {
            foreach ($item in $oldItems) {
                if ($item.PSIsContainer) {
                    Remove-Item -LiteralPath $item.FullName -Recurse -Force
                } else {
                    Remove-Item -LiteralPath $item.FullName -Force
                }
                $totalDeleted++
            }
        }
    }
}

if ($totalExpired -eq 0) {
    Write-Host "[M5-RUNTIME-TTL] CLEAN - 全域无过期治理产物 (保留期: ${RetentionDays}天)"
    exit 0
}

if ($WhatIfPreference) {
    Write-Host "[M5-RUNTIME-TTL] WARNING:RUNTIME_EXPIRED_ARTIFACTS_FOUND - 待清理: $totalExpired"
} else {
    Write-Host "[M5-RUNTIME-TTL] DONE - 已清理 $totalDeleted 项过期治理产物"
}
