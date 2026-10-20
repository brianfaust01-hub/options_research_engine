param(
    [string]$WatchdogTime = "10:45"
)

$ErrorActionPreference = "Stop"
$taskName = "Project Stonks Daily Watchdog"
$scriptPath = Join-Path $PSScriptRoot "run_daily_watchdog.ps1"

if (-not (Test-Path -LiteralPath $scriptPath)) {
    throw "Watchdog script not found: $scriptPath"
}

try {
    $scheduledTime = [datetime]::ParseExact(
        $WatchdogTime,
        "HH:mm",
        [Globalization.CultureInfo]::InvariantCulture
    )
}
catch {
    throw "WatchdogTime must use 24-hour HH:mm format, such as 10:45."
}

$powershellPath = (Get-Command powershell.exe -ErrorAction Stop).Source
$action = New-ScheduledTaskAction `
    -Execute $powershellPath `
    -Argument "-NoProfile -NonInteractive -ExecutionPolicy Bypass -File `"$scriptPath`"" `
    -WorkingDirectory $PSScriptRoot

$trigger = New-ScheduledTaskTrigger `
    -Weekly `
    -WeeksInterval 1 `
    -DaysOfWeek Monday, Tuesday, Wednesday, Thursday, Friday `
    -At $scheduledTime

$settings = New-ScheduledTaskSettingsSet `
    -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 15) `
    -StartWhenAvailable `
    -RestartCount 2 `
    -RestartInterval (New-TimeSpan -Minutes 2) `
    -WakeToRun `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries

$windowsUser = [Security.Principal.WindowsIdentity]::GetCurrent().Name
$principal = New-ScheduledTaskPrincipal `
    -UserId $windowsUser `
    -LogonType Interactive `
    -RunLevel Limited

$task = New-ScheduledTask `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Principal $principal `
    -Description "Recovers a missed Project Stonks daily run without duplicating a successful or active run."

Register-ScheduledTask -TaskName $taskName -InputObject $task -Force | Out-Null

$registered = Get-ScheduledTask -TaskName $taskName
$taskInfo = Get-ScheduledTaskInfo -TaskName $taskName

Write-Host "Daily watchdog created successfully."
Write-Host "Task: $($registered.TaskName)"
Write-Host "Schedule: Monday-Friday at $WatchdogTime local time"
Write-Host "Next run: $($taskInfo.NextRunTime)"
Write-Host "Log: $PSScriptRoot\logs\daily_watchdog.log"
