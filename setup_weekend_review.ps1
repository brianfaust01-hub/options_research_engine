$ErrorActionPreference = 'Stop'
$name = 'Project Stonks Friday Holdings Review'
$runner = Join-Path $PSScriptRoot 'run_weekend_review.ps1'
if (-not (Test-Path -LiteralPath $runner)) { throw 'Friday review runner is missing.' }
if ((Get-TimeZone).Id -ne 'Eastern Standard Time') {
    throw 'This installer expects Windows Eastern Time. Do not register local-time triggers in a different timezone.'
}
$powershell = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
$action = New-ScheduledTaskAction -Execute $powershell `
    -Argument "-NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$runner`"" `
    -WorkingDirectory $PSScriptRoot
# Calendar-aware Python permits 15:00 normally, 12:00 on 13:00 early-close Fridays.
# The other trigger is a no-op, as are holidays and late recovery after the window.
$triggers = @(
    (New-ScheduledTaskTrigger -Weekly -WeeksInterval 1 -DaysOfWeek Friday -At '12:00'),
    (New-ScheduledTaskTrigger -Weekly -WeeksInterval 1 -DaysOfWeek Friday -At '15:00')
)
$settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 20) -StartWhenAvailable -WakeToRun `
    -RestartCount 1 -RestartInterval (New-TimeSpan -Minutes 2) `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
$user = [Security.Principal.WindowsIdentity]::GetCurrent().Name
$principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited
$task = New-ScheduledTask -Action $action -Trigger $triggers -Settings $settings -Principal $principal `
    -Description 'Holdings-only Friday decision brief, one hour before the regular/early close; no orders or new trades.'
Register-ScheduledTask -TaskName $name -InputObject $task -Force | Out-Null
$registered = Get-ScheduledTask -TaskName $name
$info = Get-ScheduledTaskInfo -TaskName $name
if ($registered.Actions.Execute -ne $powershell -or @($registered.Triggers).Count -ne 2) {
    throw 'Registered task does not match the requested Friday runner.'
}
Write-Host "Registered: $name"
Write-Host 'Review: Friday 15:00 Eastern; 12:00 on 13:00 early-close Fridays. Holidays skipped.'
Write-Host "State: $($registered.State); next trigger: $($info.NextRunTime)"
Write-Host 'The 12:00 trigger on a normal Friday and 15:00 after an early close intentionally do nothing.'
Write-Host 'Requires the laptop available and the Windows user signed in, like the existing daily task.'
