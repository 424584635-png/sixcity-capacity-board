# Register local Task Scheduler job: capacity board pipeline, every 30 min from 08:00 to 23:50 (fully local)
# Usage:  powershell -ExecutionPolicy Bypass -File agg_board_1122\pipeline\install_task.ps1
# Remove: Unregister-ScheduledTask -TaskName 'CapacityBoard-HalfHourly' -Confirm:$false
# NOTE: keep this file ASCII-only. Windows PowerShell 5.1 decodes UTF-8 without BOM as ANSI.
$ErrorActionPreference = 'Stop'

$vbs  = 'C:\Users\luansha\WorkBuddy\2026-11-07-23-44-13\agg_board_1122\pipeline\run_pipeline.vbs'
$name = 'CapacityBoard-HalfHourly'
$logdir = 'C:\Users\luansha\WorkBuddy\2026-11-07-23-44-13\agg_board_1122\pipeline'

if (-not (Test-Path $vbs)) { throw "Launcher not found: $vbs" }

$action = New-ScheduledTaskAction -Execute 'wscript.exe' -Argument ('"' + $vbs + '"')

# Daily anchor at 08:00, repeat every 30 min for 15h30m -> 08:00, 08:30 ... 23:30 (32 rounds)
$t1 = New-ScheduledTaskTrigger -Daily -At '08:00'
$rep = (New-ScheduledTaskTrigger -Once -At '08:00' `
        -RepetitionInterval (New-TimeSpan -Minutes 30) `
        -RepetitionDuration (New-TimeSpan -Hours 15 -Minutes 30)).Repetition
$t1.Repetition = $rep

# Tail round at 23:50 to match the requested 08:00-23:50 window
$t2 = New-ScheduledTaskTrigger -Daily -At '23:50'

$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" `
    -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 25) -StartWhenAvailable
$settings.Hidden = $true
$settings.WakeToRun = $false

Register-ScheduledTask -TaskName $name -Action $action -Trigger @($t1, $t2) `
    -Principal $principal -Settings $settings -Force `
    -Description 'Capacity board: crawl -> build -> screenshot -> GitHub upload -> DingTalk push (08:00-23:50 every 30 min)' | Out-Null

$t = Get-ScheduledTask -TaskName $name
$i = Get-ScheduledTaskInfo -TaskName $name
Write-Host "OK registered: $($t.TaskName)  State=$($t.State)"
Write-Host "Triggers: $($t.Triggers.Count)"
foreach ($tr in $t.Triggers) { Write-Host "  - start $($tr.StartBoundary)  repeat $($tr.Repetition.Interval)/$($tr.Repetition.Duration)" }
Write-Host "Next run: $($i.NextRunTime)"
Write-Host "Log: $logdir\pipeline.log"
