#!/usr/bin/env pwsh
#requires -Version 5.1
<#
.SYNOPSIS
    日报上下文采集器 - 为 S19 日报生成器收集当天工作上下文
.DESCRIPTION
    在定时任务执行前运行，采集当天的工作会话、git commit、文件变更等信息，
    生成 daily-context.json 供 S19 使用。
    这是 S19-Cron-Context-Contract 的物理实现。
#>

param(
    [string]$OutputDir = "@@GENERAL_ROOT:win@@\evidence\S19_工作日报生成器\context",
    [string]$Date = (Get-Date -Format "yyyy-MM-dd"),
    [switch]$Verbose
)

$ErrorActionPreference = "Stop"

# 确保输出目录存在
New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null

$contextFile = Join-Path $OutputDir "daily-context-$Date.json"
$userInputContextFile = Join-Path $OutputDir "daily-user-inputs-$Date.json"

Write-Host "[DailyContextCollector] 采集日期: $Date" -ForegroundColor Cyan
Write-Host "[DailyContextCollector] 输出文件: $contextFile" -ForegroundColor Cyan
Write-Host "[DailyContextCollector] 用户输入流文件: $userInputContextFile" -ForegroundColor Cyan
function Test-JsonProperty {
    param(
        [Parameter(Mandatory = $true)]$Object,
        [Parameter(Mandatory = $true)][string]$Name
    )
    if ($null -eq $Object) {
        return $false
    }
    return $null -ne $Object.PSObject.Properties[$Name]
}

function Write-JsonUtf8NoBom {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)]$Value,
        [int]$Depth = 10
    )
    $jsonText = $Value | ConvertTo-Json -Depth $Depth
    $utf8NoBom = New-Object System.Text.UTF8Encoding $false
    [System.IO.File]::WriteAllText($Path, $jsonText, $utf8NoBom)
}

function Assert-DailyContextContract {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$ExpectedDate
    )
    if (-not (Test-Path -LiteralPath $Path)) {
        throw "daily-context 未生成: $Path"
    }
    $json = Get-Content -LiteralPath $Path -Raw -Encoding UTF8 | ConvertFrom-Json
    foreach ($field in @(
        "date",
        "summary",
        "date_today_asia_shanghai",
        "collection_summary",
        "primary_evidence_source",
        "user_input_context_path",
        "user_input_streams"
    )) {
        if (-not (Test-JsonProperty $json $field)) {
            throw "daily-context 缺失字段 ${field}: $Path"
        }
    }
    if ($json.date -ne $ExpectedDate -or $json.date_today_asia_shanghai -ne $ExpectedDate) {
        throw "daily-context 日期不匹配: date=$($json.date), date_today_asia_shanghai=$($json.date_today_asia_shanghai), expected=$ExpectedDate"
    }
    if ($json.primary_evidence_source -ne "four_user_input_streams") {
        throw "daily-context primary_evidence_source 非 four_user_input_streams: $($json.primary_evidence_source)"
    }
    if (-not (Test-JsonProperty $json.user_input_streams "records")) {
        throw "daily-context.user_input_streams 缺失 records: $Path"
    }
    if (-not (Test-JsonProperty $json.user_input_streams "source_index")) {
        throw "daily-context.user_input_streams 缺失 source_index: $Path"
    }
    foreach ($requiredSource in @("antigravity", "codexplusplus", "codex", "vscode_claude_code")) {
        if (-not (Test-JsonProperty $json.user_input_streams.source_index $requiredSource)) {
            throw "daily-context.user_input_streams.source_index 缺失 $requiredSource"
        }
        $sourceIndex = $json.user_input_streams.source_index.PSObject.Properties[$requiredSource].Value
        foreach ($countField in @("user_input_count", "count")) {
            if (-not (Test-JsonProperty $sourceIndex $countField)) {
                throw "daily-context.user_input_streams.source_index.$requiredSource 缺失 $countField"
            }
        }
    }
    foreach ($summaryField in @("user_inputs_count", "primary_source")) {
        if (-not (Test-JsonProperty $json.collection_summary $summaryField)) {
            throw "daily-context.collection_summary 缺失 $summaryField"
        }
    }
    if ($json.collection_summary.primary_source -ne "four_user_input_streams") {
        throw "daily-context.collection_summary.primary_source 非 four_user_input_streams: $($json.collection_summary.primary_source)"
    }
}

function Get-BacktickWindowsPaths {
    param([Parameter(Mandatory = $true)][string]$Content)
    $parts = $Content.Split('`')
    $paths = @()
    for ($i = 1; $i -lt $parts.Count; $i += 2) {
        $candidate = $parts[$i]
        if ($candidate.Length -ge 3 -and $candidate[1] -eq ':' -and $candidate[2] -eq '\') {
            $paths += $candidate
        }
    }
    return $paths
}

function Get-ProjectRootFromAssetPath {
    param([Parameter(Mandatory = $true)][string]$Path)
    foreach ($marker in @("\.agent", "\.agents")) {
        $index = $Path.IndexOf($marker, [System.StringComparison]::OrdinalIgnoreCase)
        if ($index -gt 0) {
            return $Path.Substring(0, $index)
        }
    }
    return $Path
}

function Test-GitCommitBlock {
    param([Parameter(Mandatory = $true)][string]$Block)
    $firstLine = $Block.Split([char[]]@("`n"))[0].Trim()
    $pipeIndex = $firstLine.IndexOf('|')
    if ($pipeIndex -le 0) {
        return $false
    }
    $hash = $firstLine.Substring(0, $pipeIndex)
    foreach ($char in $hash.ToCharArray()) {
        if (-not [System.Uri]::IsHexDigit($char)) {
            return $false
        }
    }
    return $true
}

function Test-GitNameStatusLine {
    param([string]$Line)
    if ([string]::IsNullOrWhiteSpace($Line)) {
        return $false
    }
    $first = $Line.Trim()[0]
    return $first -in @('A', 'M', 'D')
}

# ========== 1. 采集当天会话记录 ==========
function Get-TodaySessions {
    $sessions = @()
    
    # 尝试从 Antigravity Brain 采集
    $brainPaths = @(
        "@@USERPROFILE:win@@\.gemini\antigravity\brain"
        "@@USERPROFILE:win@@\.antigravity\brain"
    )
    
    foreach ($brainPath in $brainPaths) {
        if (Test-Path $brainPath) {
            $todayFiles = Get-ChildItem -Path $brainPath -File -Recurse -ErrorAction SilentlyContinue |
                Where-Object { $_.LastWriteTime.Date -eq [DateTime]::Today }
            
            foreach ($file in $todayFiles) {
                try {
                    $content = Get-Content -Path $file.FullName -Raw -Encoding UTF8 -ErrorAction SilentlyContinue
                    if ($content -and $content.Length -gt 100) {
                        $sessions += [pscustomobject]@{
                            source = "antigravity-brain"
                            file = $file.Name
                            path = $file.FullName
                            summary = if ($content.Length -gt 500) { $content.Substring(0, 500) + "..." } else { $content }
                            timestamp = $file.LastWriteTime.ToString("yyyy-MM-dd HH:mm:ss")
                        }
                    }
                } catch {
                    # 忽略读取失败的文件
                }
            }
        }
    }
    
    return $sessions
}

# ========== 2. 采集 Git 变更 ==========
function Get-TodayGitChanges {
    $changes = @()
    
    # 读取资产注册表获取项目根路径
    $assetRegister = "@@GENERAL_ROOT:win@@\control\registry\01-asset-register.md"
    if (Test-Path $assetRegister) {
        $content = Get-Content -Path $assetRegister -Raw -Encoding UTF8
        $paths = Get-BacktickWindowsPaths $content
                
        # 去重：同一个 git 仓库只扫描一次（资产注册表中 .agent/ 和 .agent/skills/ 会映射到同一个根）
        $uniqueRoots = @{}
        foreach ($path in $paths) {
            $projectRoot = Get-ProjectRootFromAssetPath $path
            if ($projectRoot -and -not $uniqueRoots.ContainsKey($projectRoot)) {
                if (Test-Path (Join-Path $projectRoot ".git")) {
                    $uniqueRoots[$projectRoot] = $true
                }
            }
        }
                
        foreach ($projectRoot in $uniqueRoots.Keys) {
            try {
                Push-Location $projectRoot
                $gitLog = git log --since="midnight" --pretty=format:"%H|%s|%b" --name-status 2>$null
                if ($gitLog) {
                    $commits = $gitLog.Split([string[]]@("`n`n"), [System.StringSplitOptions]::RemoveEmptyEntries) |
                        Where-Object { Test-GitCommitBlock $_ }
                    foreach ($commit in $commits) {
                        $lines = $commit.Split([char[]]@("`n"))
                        $header = $lines[0].Split('|')
                        if ($header.Count -ge 2) {
                            $changes += [pscustomobject]@{
                                project = Split-Path -Leaf ($projectRoot.TrimEnd('\'))
                                commit_hash = $header[0].Substring(0, 8)
                                message = $header[1]
                                body = if ($header.Count -gt 2) { $header[2] } else { "" }
                                files = $lines[1..($lines.Count-1)] | Where-Object { Test-GitNameStatusLine $_ }
                                timestamp = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
                            }
                        }
                    }
                }
                Pop-Location
            } catch {
                Pop-Location
            }
        }
    }
    
    return $changes
}

# ========== 3. 生成采集摘要 ==========
function Generate-SessionSummary($userInputCount, $sessions, $gitChanges) {
    if ($userInputCount -gt 0) {
        return "今天收集到 $userInputCount 条四入口用户输入，git/status 仅作为辅助校验"
    }

    $parts = @()
    
    if ($sessions.Count -gt 0) {
        $parts += "有 $($sessions.Count) 个工作会话记录"
    }

    if ($gitChanges.Count -gt 0) {
        $parts += "辅助索引包含 $($gitChanges.Count) 个 git commit"
    }
    
    if ($parts.Count -eq 0) {
        return "今天未采集到有效四入口用户输入"
    }
    
    return $parts -join "，"
}

# ========== 4. 采集四入口用户输入流 ==========
function Collect-UserInputStreams($Date, $OutputPath) {
    $scriptDir = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Path }
    $collectorScript = Join-Path $scriptDir "collect_user_input_streams.py"
    if (-not (Test-Path $collectorScript)) {
        throw "四入口用户输入流采集器不存在: $collectorScript"
    }

    $pythonCmd = Get-Command python -ErrorAction SilentlyContinue
    if (-not $pythonCmd) {
        throw "未找到 python，无法采集四入口用户输入流"
    }

    $collectorOutput = & $pythonCmd.Source $collectorScript --date $Date --output $OutputPath 2>&1
    if ($LASTEXITCODE -ne 0) {
        $collectorText = ($collectorOutput | ForEach-Object { $_.ToString() }) -join "`n"
        if ($collectorText) {
            Write-Host "[DailyContextCollector] 用户输入流采集器输出: $collectorText" -ForegroundColor Red
        }
        throw "四入口用户输入流采集失败，退出码: $LASTEXITCODE"
    }
    $collectorText = ($collectorOutput | ForEach-Object { $_.ToString() }) -join "`n"
    if ($collectorText) {
        Write-Host "[DailyContextCollector] 用户输入流采集器输出: $collectorText" -ForegroundColor DarkGray
    }
    if (-not (Test-Path $OutputPath)) {
        throw "四入口用户输入流采集未生成输出文件: $OutputPath"
    }

    $json = Get-Content -LiteralPath $OutputPath -Raw -Encoding UTF8 | ConvertFrom-Json
    if (-not $json.summary -or $null -eq $json.summary.total_user_inputs) {
        throw "四入口用户输入流输出缺失 summary.total_user_inputs: $OutputPath"
    }

    foreach ($requiredSource in @("antigravity", "codexplusplus", "codex", "vscode_claude_code")) {
        if (-not $json.source_index -or -not $json.source_index.PSObject.Properties[$requiredSource]) {
            throw "四入口用户输入流输出缺失 source_index.$requiredSource"
        }
    }

    return $json
}

# ========== 主执行流程 ==========
Write-Host "[DailyContextCollector] 开始采集..." -ForegroundColor Yellow

# 采集数据
$userInputStreams = Collect-UserInputStreams $Date $userInputContextFile
$userInputCount = [int]$userInputStreams.summary.total_user_inputs
Write-Host "[DailyContextCollector] 采集到 $userInputCount 条四入口用户输入" -ForegroundColor Green

$sessions = Get-TodaySessions
Write-Host "[DailyContextCollector] 采集到 $($sessions.Count) 个会话记录" -ForegroundColor Green

$gitChanges = Get-TodayGitChanges
Write-Host "[DailyContextCollector] 采集到 $($gitChanges.Count) 个 git commit" -ForegroundColor Green

$sessionSummary = Generate-SessionSummary $userInputCount $sessions $gitChanges
$auxiliaryProjects = @(
    $gitChanges |
        ForEach-Object { $_.project } |
        Where-Object { $_ -and $_.ToString().Trim().Length -gt 0 } |
        Select-Object -Unique
)
$collectionSummary = @{
    user_inputs_count = $userInputCount
    primary_source = "four_user_input_streams"
    sessions_count = $sessions.Count
    git_commits_count = $gitChanges.Count
    auxiliary_projects_count = $auxiliaryProjects.Count
}

# 构建上下文对象
$context = @{
    contract_version = "1.0"
    date = $Date
    date_today_asia_shanghai = $Date
    summary = $sessionSummary
    generated_at = (Get-Date -Format "yyyy-MM-ddTHH:mm:ss+08:00")
    generator = "lobster-daily-context-collector"
    primary_evidence_source = "four_user_input_streams"
    user_input_context_path = $userInputContextFile
    collection_summary = $collectionSummary
    user_input_streams = $userInputStreams
    context = @{
        date = $Date
        session_summary = $sessionSummary
        primary_evidence_source = "four_user_input_streams"
        # The canonical stream is the top-level user_input_streams field.
        # Re-embedding it here duplicated the full payload and exhausted the
        # isolated cron Agent when the daily input stream became large.
        user_input_context_path = $userInputContextFile
        auxiliary_git_projects = $auxiliaryProjects
        collection_summary = $collectionSummary
    }
    evidence_sources = @(
        "Antigravity user input stream"
        "Codex++ user input stream"
        "Independent Codex user input stream"
        "VSCode Claude Code user input stream"
        "git log --since=midnight"
        "@@GENERAL_ROOT:win@@\control\registry\01-asset-register.md"
        "@@USERPROFILE:win@@\.gemini\antigravity-ide\brain"
    )
    raw_data = @{
        user_inputs_count = $userInputCount
        sessions_count = $sessions.Count
        git_commits_count = $gitChanges.Count
        auxiliary_projects_count = $auxiliaryProjects.Count
    }
}

# 保存上下文文件
Write-JsonUtf8NoBom -Path $contextFile -Value $context -Depth 20
Assert-DailyContextContract -Path $contextFile -ExpectedDate $Date

Write-Host "[DailyContextCollector] 上下文文件已保存: $contextFile" -ForegroundColor Green
Write-Host "[DailyContextCollector] 完成!" -ForegroundColor Green

# 输出摘要
Write-Host "`n========== 上下文摘要 ==========" -ForegroundColor Cyan
Write-Host "日期: $Date"
Write-Host "四入口用户输入: $userInputCount"
Write-Host "会话摘要: $sessionSummary"
Write-Host "辅助项目索引: $($context.context.auxiliary_git_projects -join ', ')"
Write-Host "================================" -ForegroundColor Cyan

# 返回文件路径（供调用者使用）
return $contextFile
