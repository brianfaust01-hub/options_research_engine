param(
    [string]$PrimaryTaskName = "Project Stonks Daily Run",
    [string]$ProjectRoot = $PSScriptRoot,
    [datetime]$EvaluationTime = (Get-Date),
    [ValidateSet("", "Ready", "Running", "Disabled")]
    [string]$TaskStateOverride = "",
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
$logsDirectory = Join-Path $ProjectRoot "logs"
$watchdogLog = Join-Path $logsDirectory "daily_watchdog.log"
$dateKey = $EvaluationTime.ToString("yyyy-MM-dd")
$successMarker = Join-Path $logsDirectory "daily_success_$dateKey.marker"

New-Item -ItemType Directory -Path $logsDirectory -Force | Out-Null

function Write-WatchdogLog {
    param([string]$Message)
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Add-Content -LiteralPath $watchdogLog -Value "$timestamp | $Message"
    Write-Host $Message
}

if ($EvaluationTime.DayOfWeek -in @(
    [DayOfWeek]::Saturday,
    [DayOfWeek]::Sunday
)) {
    Write-WatchdogLog "SKIP weekend ($dateKey)."
    exit 0
}

if (Test-Path -LiteralPath $successMarker) {
    Write-WatchdogLog "HEALTHY daily run already completed ($dateKey)."
    exit 0
}

$taskState = $TaskStateOverride
if (-not $taskState) {
    $primaryTask = Get-ScheduledTask -TaskName $PrimaryTaskName -ErrorAction Stop
    $taskState = [string]$primaryTask.State
}

if ($taskState -eq "Running") {
    Write-WatchdogLog "HEALTHY daily run is still running; duplicate launch suppressed."
    exit 0
}

if ($DryRun) {
    Write-WatchdogLog "DRY RUN would start '$PrimaryTaskName'; success marker is absent."
    exit 0
}

Start-ScheduledTask -TaskName $PrimaryTaskName
Write-WatchdogLog "RECOVERY started '$PrimaryTaskName'; success marker was absent."
