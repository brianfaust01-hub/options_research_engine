$ErrorActionPreference = "Stop"

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
$isAdministrator = $principal.IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator
)

if (-not $isAdministrator) {
    Write-Host "Administrator access is required; requesting elevation..."
    $arguments = @(
        "-NoProfile",
        "-ExecutionPolicy", "Bypass",
        "-File", "`"$PSCommandPath`""
    )
    $process = Start-Process `
        -FilePath "powershell.exe" `
        -ArgumentList $arguments `
        -Verb RunAs `
        -Wait `
        -PassThru
    exit $process.ExitCode
}

$legacyAction = "C:\Users\brian\Trading_systems\options_research_engine\run_daily_stonks.bat"
$targets = @(
    @{ TaskPath = "\"; TaskName = "Project Stonks Daily Scan" },
    @{ TaskPath = "\AWCC\"; TaskName = "Project Stonks Daily Scan" }
)

foreach ($target in $targets) {
    $task = Get-ScheduledTask `
        -TaskPath $target.TaskPath `
        -TaskName $target.TaskName `
        -ErrorAction Stop

    $actions = @($task.Actions)
    if ($actions.Count -ne 1 -or $actions[0].Execute -ne $legacyAction) {
        throw (
            "Safety check failed for {0}{1}; expected the obsolete action '{2}'." -f `
                $target.TaskPath, $target.TaskName, $legacyAction
        )
    }

    Disable-ScheduledTask -InputObject $task -ErrorAction Stop | Out-Null
    Write-Host "Disabled: $($target.TaskPath)$($target.TaskName)"
}

Write-Host "Legacy Project Stonks tasks are disabled. No tasks were deleted."
Write-Host "Current daily, intraday, and watchdog tasks were not changed."
