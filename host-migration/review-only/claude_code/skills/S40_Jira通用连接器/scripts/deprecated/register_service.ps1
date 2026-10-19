# JIRA 飞书双发网关服务注册脚本（需管理员权限运行）
$nssm = "nssm"
$svc = "jira-feishu-bridge"

Write-Output "正在停止并清理旧服务..."
& $nssm stop $svc confirm 2>$null
& $nssm remove $svc confirm 2>$null

Write-Output "正在注册服务: $svc..."
& $nssm install $svc "@@USERPROFILE:win@@\.gemini\antigravity-ide\brain\ac7b9707-7125-4765-83fb-ee329e167c75\scratch\run_bridge.bat"
& $nssm set $svc AppDirectory "@@GENERAL_ROOT:win@@\assets\skills\S40_Jira通用连接器\scripts"
& $nssm set $svc Description "JIRA Feishu notification double dispatch bridge"
& $nssm set $svc Start SERVICE_AUTO_START
& $nssm set $svc AppStdout "@@GENERAL_ROOT:win@@\skills\S40_Jira通用连接器\logs\stdout.log"
& $nssm set $svc AppStderr "@@GENERAL_ROOT:win@@\skills\S40_Jira通用连接器\logs\stderr.log"
& $nssm set $svc AppRotateFiles 1
& $nssm set $svc AppRotateBytes 10485760

Write-Output "正在启动服务..."
& $nssm start $svc

$status = Get-Service $svc 2>$null
if ($status -and $status.Status -eq "Running") {
    Write-Output "✅ 服务 $svc 注册并启动成功！"
} else {
    Write-Output "❌ 服务启动失败，请检查 @@GENERAL_ROOT:win@@\skills\S40_Jira通用连接器\logs\stderr.log 中的日志。"
}
