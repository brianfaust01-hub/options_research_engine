param(
    [datetime]$Since = (Get-Date).Date.AddDays(-1)
)

$ErrorActionPreference = "Continue"
$taskNames = @(
    "Project Stonks Daily Run",
    "Project Stonks Intraday Option Research",
    "Project Stonks Daily Watchdog"
)
$logsDirectory = Join-Path $PSScriptRoot "logs"
$outputPath = Join-Path $logsDirectory (
    "task_scheduler_diagnostic_{0}.txt" -f (Get-Date -Format "yyyyMMdd_HHmmss")
)

New-Item -ItemType Directory -Path $logsDirectory -Force | Out-Null

function Write-DiagnosticSection {
    param(
        [string]$Name,
        [scriptblock]$Body
    )
    Write-Host "Collecting: $Name"
    "=== $Name ===" | Out-File -LiteralPath $outputPath -Append -Encoding utf8 -Width 300
    & $Body 2>&1 | Out-File -LiteralPath $outputPath -Append -Encoding utf8 -Width 300
    "" | Out-File -LiteralPath $outputPath -Append -Encoding utf8 -Width 300
}

& {
    "PROJECT STONKS TASK SCHEDULER DIAGNOSTIC"
    "Generated: $(Get-Date -Format o)"
    "Since: $($Since.ToString('o'))"
    "Computer: $env:COMPUTERNAME"
    "User: $([Security.Principal.WindowsIdentity]::GetCurrent().Name)"
    ""
} | Out-File -LiteralPath $outputPath -Encoding utf8 -Width 300

Write-DiagnosticSection "OPERATING SYSTEM AND SCHEDULER SERVICE" {
    Get-CimInstance Win32_OperatingSystem |
        Select-Object LastBootUpTime, LocalDateTime, Caption, Version |
        Format-List
    Get-Service -Name Schedule |
        Select-Object Name, Status, StartType |
        Format-List
}

Write-DiagnosticSection "TASK STATE AND LAST RESULTS" {
    foreach ($taskName in $taskNames) {
        "--- $taskName ---"
        $task = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
        if ($null -eq $task) {
            "NOT FOUND"
            continue
        }
        $info = Get-ScheduledTaskInfo -TaskName $taskName
        [pscustomobject]@{
            State = $task.State
            Enabled = $task.Settings.Enabled
            LastRunTime = $info.LastRunTime
            LastTaskResult = $info.LastTaskResult
            NextRunTime = $info.NextRunTime
            NumberOfMissedRuns = $info.NumberOfMissedRuns
            UserId = $task.Principal.UserId
            LogonType = $task.Principal.LogonType
            StartWhenAvailable = $task.Settings.StartWhenAvailable
            WakeToRun = $task.Settings.WakeToRun
        } | Format-List
        "Triggers:"
        $task.Triggers | Format-List *
        "Actions:"
        $task.Actions | Select-Object Execute, Arguments, WorkingDirectory |
            Format-List
    }
}

Write-DiagnosticSection "TASK SCHEDULER OPERATIONAL LOG STATUS" {
    Get-WinEvent -ListLog "Microsoft-Windows-TaskScheduler/Operational" |
        Select-Object LogName, IsEnabled, RecordCount, LastWriteTime |
        Format-List
}

Write-DiagnosticSection "PROJECT STONKS TASK EVENTS (LATEST 5000 SINCE START)" {
    Get-WinEvent -FilterHashtable @{
        LogName = "Microsoft-Windows-TaskScheduler/Operational"
        StartTime = $Since
    } -MaxEvents 5000 -ErrorAction SilentlyContinue |
        Where-Object {
            $message = $_.Message
            $message -match "Project Stonks"
        } |
        Sort-Object TimeCreated |
        Select-Object TimeCreated, Id, LevelDisplayName, Message |
        Format-List
}

Write-DiagnosticSection "REBOOT, SLEEP, AND WAKE EVENTS" {
    Get-WinEvent -FilterHashtable @{
        LogName = "System"
        StartTime = $Since
        Id = @(1, 12, 13, 41, 42, 107, 109, 6005, 6006, 6008)
    } -MaxEvents 300 -ErrorAction SilentlyContinue |
        Sort-Object TimeCreated |
        Select-Object TimeCreated, Id, ProviderName, LevelDisplayName, Message |
        Format-List
}

Write-Host "Diagnostic written to: $outputPath"
