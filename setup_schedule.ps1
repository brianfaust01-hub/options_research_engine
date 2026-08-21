param(
    [string]$RunTime = "10:30"
)

$ErrorActionPreference = "Stop"
$taskName = "Project Stonks Daily Run"
$batchPath = Join-Path $PSScriptRoot "run_daily_stonks.bat"

if (-not (Test-Path -LiteralPath $batchPath)) {
    throw "Daily-run batch file not found: $batchPath"
}

try {
    $scheduledTime = [datetime]::ParseExact(
        $RunTime,
        "HH:mm",
        [Globalization.CultureInfo]::InvariantCulture
    )
}
catch {
    throw "RunTime must use 24-hour HH:mm format, such as 10:30."
}

$existingTask = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if ($null -ne $existingTask) {
    $confirmation = Read-Host "Task '$taskName' exists. Replace it? [y/N]"
    if ($confirmation -notin @("y", "Y", "yes", "YES")) {
        Write-Host "Schedule unchanged."
        exit 0
    }
}

$cmdPath = Join-Path $env:SystemRoot "System32\cmd.exe"
$action = New-ScheduledTaskAction `
    -Execute $cmdPath `
    -Argument "/d /c `"$batchPath`"" `
    -WorkingDirectory $PSScriptRoot

$trigger = New-ScheduledTaskTrigger `
    -Weekly `
    -WeeksInterval 1 `
    -DaysOfWeek Monday, Tuesday, Wednesday, Thursday, Friday `
    -At $scheduledTime

$settings = New-ScheduledTaskSettingsSet `
    -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Hours 4) `
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
    -Description "Runs Project Stonks and emails the daily action brief."

Register-ScheduledTask `
    -TaskName $taskName `
    -InputObject $task `
    -Force | Out-Null

$registered = Get-ScheduledTask -TaskName $taskName
$nextRun = Get-ScheduledTaskInfo -TaskName $taskName

Write-Host "Scheduled task created successfully."
Write-Host "Task: $($registered.TaskName)"
Write-Host "User: $windowsUser"
Write-Host "Schedule: Monday-Friday at $RunTime local time"
Write-Host "Next run: $($nextRun.NextRunTime)"
Write-Host "Log: $PSScriptRoot\logs\weekly_scan.log"
