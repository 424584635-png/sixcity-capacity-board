# Register the fengshen session keep-alive probe (every 15 min, probe only, no re-login)
# Usage:  powershell -ExecutionPolicy Bypass -File agg_board_1122\pipeline\install_keepalive_task.ps1
# Remove: Unregister-ScheduledTask -TaskName 'CapacityBoard-FsKeepalive' -Confirm:$false
# NOTE: keep this file ASCII-only. Windows PowerShell 5.1 decodes UTF-8 without BOM as ANSI.
$ErrorActionPreference = 'Stop'

$node = 'C:\Users\luansha\.workbuddy\binaries\node\versions\22.22.2-6\node.exe'
$script = 'C:\Users\luansha\WorkBuddy\2026-11-07-23-44-13\agg_board_1122\keepalive_fs.mjs'
$vbs = 'C:\Users\luansha\WorkBuddy\2026-11-07-23-44-13\agg_board_1122\keepalive_hidden.vbs'
$logdir = 'C:\Users\luansha\WorkBuddy\2026-11-07-23-44-13\agg_board_1122\pipeline'
$name = 'CapacityBoard-FsKeepalive'

if (-not (Test-Path $script)) { throw "Script not found: $script" }
if (-not (Test-Path $vbs)) { throw "VBS launcher not found: $vbs" }

# 用 wscript 隐藏窗口启动，避免弹出黑色控制台
$action = New-ScheduledTaskAction -Execute 'wscript.exe' -Argument ('"' + $vbs + '"') -WorkingDirectory $logdir
$t1 = New-ScheduledTaskTrigger -Once -At '00:00'
$rep = (New-ScheduledTaskTrigger -Once -At '00:00' `
        -RepetitionInterval (New-TimeSpan -Minutes 15) `
        -RepetitionDuration (New-TimeSpan -Days 3650)).Repetition
$t1.Repetition = $rep

$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" `
    -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 5) -StartWhenAvailable
$settings.Hidden = $true

Register-ScheduledTask -TaskName $name -Action $action -Trigger $t1 `
    -Principal $principal -Settings $settings -Force `
    -Description 'Keep-alive probe for fengshen(aeolus) session: probe only, no re-login' | Out-Null

$t = Get-ScheduledTask -TaskName $name
$i = Get-ScheduledTaskInfo -TaskName $name
Write-Host "OK registered: $($t.TaskName)  State=$($t.State)"
Write-Host "Every 15 min. NextRun=$($i.NextRunTime)"
