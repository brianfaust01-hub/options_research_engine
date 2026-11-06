$ErrorActionPreference = "Stop"
# Cheap off-hours gate: never start Python or contact Schwab outside ET hours.
$eastern = [TimeZoneInfo]::ConvertTimeBySystemTimeZoneId([datetime]::UtcNow, "Eastern Standard Time")
$marketOpen = $eastern.Date.AddHours(9).AddMinutes(30)
$marketClose = $eastern.Date.AddHours(16)
if ($eastern.DayOfWeek -in @("Saturday", "Sunday") -or $eastern -lt $marketOpen -or $eastern -gt $marketClose) { exit 0 }

# Preserve active comparison prices during the scan, without refreshing shared OAuth.
$comparisonDuringScan = $false
$daily = Get-ScheduledTask -TaskName "Project Stonks Daily Run" -ErrorAction SilentlyContinue
if ($null -ne $daily -and $daily.State -eq "Running") {
    $pauseLogDir = Join-Path $PSScriptRoot "logs"
    New-Item -ItemType Directory -Path $pauseLogDir -Force | Out-Null
    $pauseLog = Join-Path $pauseLogDir ("intraday_options_{0}.log" -f $eastern.ToString("yyyy-MM-dd"))
    try {
        $comparisonSettings = Get-Content -LiteralPath (Join-Path $PSScriptRoot "research/six_week_20261029/activation.json") -Raw | ConvertFrom-Json
        $comparisonDuringScan = $comparisonSettings.enabled -and $comparisonSettings.comparison_enabled -and $comparisonSettings.release_status -eq "READY"
    } catch { $comparisonDuringScan = $false }
    if (-not $comparisonDuringScan) {
        Add-Content -LiteralPath $pauseLog -Value "$(Get-Date -Format o) PAUSED_DAILY_SCAN: this interval is a gap"
        exit 0
    }
    Add-Content -LiteralPath $pauseLog -Value "$(Get-Date -Format o) COMPARISON_ONLY_DURING_SCAN: cached authorization; broad research collection paused"
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
    $collectorArguments = @("-u", "`"$collector`"")
    if ($comparisonDuringScan) { $collectorArguments += @("--priority-only", "--cached-auth-only", "--budget-seconds", "10") }
    $process = Start-Process -FilePath $python -ArgumentList $collectorArguments `
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
# Auxiliary structure/VIX research runs only after the existing collector.
# During daily scans preserve current comparison priority and avoid extra traffic.
if (-not $comparisonDuringScan) {
    $studyScript = Join-Path $PSScriptRoot "src\research_observation_runner.py"
    $studyOut = Join-Path $scratchDir "$runId.study.out"
    $studyErr = Join-Path $scratchDir "$runId.study.err"
    try {
        $studyProcess = Start-Process -FilePath $python -ArgumentList @("-u", "`"$studyScript`"") `
            -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -PassThru `
            -RedirectStandardOutput $studyOut -RedirectStandardError $studyErr
        if (-not $studyProcess.WaitForExit(10000)) {
            $studyProcess.Kill()
            $studyProcess.WaitForExit()
            Add-Content -LiteralPath $log -Value "$(Get-Date -Format o) AUXILIARY_RESEARCH_TIMEOUT: unrecorded quotes remain gaps"
        } elseif (Test-Path -LiteralPath $studyOut) {
            Get-Content -LiteralPath $studyOut | Add-Content -LiteralPath $log
        }
    } catch {
        Add-Content -LiteralPath $log -Value "$(Get-Date -Format o) AUXILIARY_RESEARCH_UNAVAILABLE"
    } finally {
        Remove-Item -LiteralPath $studyOut, $studyErr -Force -ErrorAction SilentlyContinue
    }
}
exit $exitCode
