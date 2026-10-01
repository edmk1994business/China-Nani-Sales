# Registers the daily 11:30 iikoChain export in Windows Task Scheduler.
# Run in PowerShell (as your normal user, NOT as admin is fine):
#   powershell -ExecutionPolicy Bypass -File .\install_task.ps1
$ErrorActionPreference = "Stop"
$TaskName = "iiko Sales Export (AI Dashboard)"
$Bat      = Join-Path $PSScriptRoot "run_export.bat"

$Action    = New-ScheduledTaskAction -Execute $Bat -WorkingDirectory $PSScriptRoot
$Trigger   = New-ScheduledTaskTrigger -Daily -At 11:30
$Settings  = New-ScheduledTaskSettingsSet `
               -StartWhenAvailable `
               -WakeToRun `
               -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
               -ExecutionTimeLimit (New-TimeSpan -Minutes 45) `
               -RestartCount 1 -RestartInterval (New-TimeSpan -Minutes 10) `
               -MultipleInstances IgnoreNew
# Interactive = runs on YOUR desktop session (required for mouse/keyboard automation)
$Principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Limited

Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger `
    -Settings $Settings -Principal $Principal -Force | Out-Null
Write-Host "Task '$TaskName' registered: daily at 11:30 -> $Bat"
Write-Host "Test it now with:  Start-ScheduledTask -TaskName '$TaskName'"
