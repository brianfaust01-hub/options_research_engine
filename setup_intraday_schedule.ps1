param([switch]$Replace)
$ErrorActionPreference = "Stop"
$name = "Project Stonks Intraday Option Research"
$runner = Join-Path $PSScriptRoot "run_intraday_options.ps1"
if (-not (Test-Path -LiteralPath $runner)) { throw "Intraday runner missing." }
$existing = Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue
if ($null -ne $existing -and -not $Replace) {
    throw "Task already exists. Inspect it first; use -Replace to update only this research task."
}
$powershell = Join-Path $env:SystemRoot "System32\WindowsPowerShell\v1.0\powershell.exe"
$action = New-ScheduledTaskAction -Execute $powershell `
    -Argument "-NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$runner`"" `
    -WorkingDirectory $PSScriptRoot
# Repeat daily rather than maintaining a long-running daemon. Eastern calendar
# guards in the collector own holidays/DST/early closes, not local trigger time.
$trigger = New-ScheduledTaskTrigger -Daily -At "00:00"
$repeating = New-ScheduledTaskTrigger -Once -At (Get-Date) `
    -RepetitionInterval (New-TimeSpan -Minutes 1) -RepetitionDuration (New-TimeSpan -Days 1)
$trigger.Repetition = $repeating.Repetition
$settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 1) -StartWhenAvailable -WakeToRun `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
$user = [Security.Principal.WindowsIdentity]::GetCurrent().Name
$principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited
$task = New-ScheduledTask -Action $action -Trigger $trigger -Settings $settings -Principal $principal `
    -Description "Read-only one-minute equity-option bid/ask research; no orders or email."
Register-ScheduledTask -TaskName $name -InputObject $task -Force | Out-Null
Start-ScheduledTask -TaskName $name
Get-ScheduledTask -TaskName $name | Select-Object TaskName, State
Write-Host "Quotes: regular equity hours Eastern; holidays/early closes guarded. Daily scan pauses collection."
Write-Host "Laptop must be awake and user signed in. Expired Schwab authorization causes visible gaps."
Write-Host "Evidence: data\processed\intraday_option_paths; logs: logs\intraday_options_YYYY-MM-DD.log"
