$ErrorActionPreference = "Stop"
# Cheap off-hours gate: never start Python or contact Schwab outside ET hours.
$eastern = [TimeZoneInfo]::ConvertTimeBySystemTimeZoneId([datetime]::UtcNow, "Eastern Standard Time")
if ($eastern.DayOfWeek -in @("Saturday", "Sunday") -or $eastern.Hour -lt 9 -or $eastern.Hour -gt 16) { exit 0 }

# Avoid shared OAuth refresh contention with the normal scheduled daily scan.
$daily = Get-ScheduledTask -TaskName "Project Stonks Daily Run" -ErrorAction SilentlyContinue
if ($null -ne $daily -and $daily.State -eq "Running") {
    $pauseLogDir = Join-Path $PSScriptRoot "logs"
    New-Item -ItemType Directory -Path $pauseLogDir -Force | Out-Null
    $pauseLog = Join-Path $pauseLogDir ("intraday_options_{0}.log" -f $eastern.ToString("yyyy-MM-dd"))
    Add-Content -LiteralPath $pauseLog -Value "$(Get-Date -Format o) PAUSED_DAILY_SCAN: this interval is a gap"
    exit 0
}

$python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
$collector = Join-Path $PSScriptRoot "src\intraday_option_paths.py"
if (-not (Test-Path -LiteralPath $python)) { throw "Repository Python is missing." }
$logDir = Join-Path $PSScriptRoot "logs"
$scratchDir = Join-Path $PSScriptRoot "data\cache\intraday_runner"
New-Item -ItemType Directory -Path $logDir, $scratchDir -Force | Out-Null
$runId = [guid]::NewGuid().ToString("N")
$stdout = Join-Path $scratchDir "$runId.out"
$stderr = Join-Path $scratchDir "$runId.err"
$log = Join-Path $logDir ("intraday_options_{0}.log" -f $eastern.ToString("yyyy-MM-dd"))
$exitCode = 1
try {
    $process = Start-Process -FilePath $python -ArgumentList @("-u", "`"$collector`"") `
        -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput $stdout -RedirectStandardError $stderr
    if (-not $process.WaitForExit(45000)) {
        $process.Kill()
        $process.WaitForExit()
        Add-Content -LiteralPath $log -Value "$(Get-Date -Format o) HARD_TIMEOUT: unrecorded quotes remain gaps"
    } else {
        $process.Refresh()
        $exitCode = $process.ExitCode
        if (Test-Path -LiteralPath $stdout) {
            Get-Content -LiteralPath $stdout | Add-Content -LiteralPath $log
        }
        # Python suppresses credential-bearing exception details. Do not copy stderr.
        if ($exitCode -ne 0) { Add-Content -LiteralPath $log -Value "$(Get-Date -Format o) COLLECTION_FAILED_OR_PARTIAL exit=$exitCode" }
    }
} finally {
    # Exact, task-created scratch files only; no recursive cleanup or history deletion.
    Remove-Item -LiteralPath $stdout, $stderr -Force -ErrorAction SilentlyContinue
}
exit $exitCode
