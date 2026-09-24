param(
    [string]$TaskName = "Project Stonks Daily Run"
)

$ErrorActionPreference = "Stop"

$task = Get-ScheduledTask -TaskName $TaskName
$info = Get-ScheduledTaskInfo -TaskName $TaskName
$result = [uint32]$info.LastTaskResult
$win32Code = [int]($result -band 0xFFFF)
$resultMessage = if ($result -eq 0) {
    "Success"
}
else {
    (New-Object ComponentModel.Win32Exception($win32Code)).Message
}

[pscustomobject]@{
    TaskName = $task.TaskName
    State = $task.State
    LastRunTime = $info.LastRunTime
    LastTaskResult = "0x{0:X8}" -f $result
    LastResultMessage = $resultMessage
    NextRunTime = $info.NextRunTime
    NumberOfMissedRuns = $info.NumberOfMissedRuns
    StartWhenAvailable = $task.Settings.StartWhenAvailable
    WakeToRun = $task.Settings.WakeToRun
    RestartCount = $task.Settings.RestartCount
    RestartInterval = $task.Settings.RestartInterval
    LogPath = Join-Path $PSScriptRoot "logs\weekly_scan.log"
} | Format-List
