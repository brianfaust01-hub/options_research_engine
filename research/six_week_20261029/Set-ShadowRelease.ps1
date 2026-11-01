param([switch]$Disable)
$ErrorActionPreference = 'Stop'
$releaseDir = $PSScriptRoot
$repoRoot = (Resolve-Path (Join-Path $releaseDir '../..')).Path
if (-not $Disable) {
    $easternNow = [TimeZoneInfo]::ConvertTimeBySystemTimeZoneId([datetime]::UtcNow, 'Eastern Standard Time')
    if ($easternNow.Date -lt [datetime]'2026-11-01') { throw 'Shadow activation is reserved for Sunday November 1 or later.' }
    $releaseState = Get-Content -LiteralPath (Join-Path $releaseDir 'activation.json') -Raw | ConvertFrom-Json
    if ($releaseState.release_status -ne 'READY' -or $releaseState.comparison_enabled -ne $true -or $releaseState.diagnostic_forecast -ne $false) { throw 'Trading comparison scope requires review and ledger integration; forecast-only activation is superseded.' }
    $manifest = Get-Content -LiteralPath (Join-Path $releaseDir 'release_manifest.json') -Raw | ConvertFrom-Json
    if ($manifest.version -ne 'OPTION-CONFIG-COMPARISON-2026-10-29-v1') { throw 'Trading comparison manifest is missing or superseded.' }
    $repositoryPython = Join-Path $repoRoot '.venv/Scripts/python.exe'
    if (-not (Test-Path -LiteralPath $repositoryPython)) { throw 'Repository Python is missing.' }
    $fingerprintCode = 'import sys; from pathlib import Path; sys.path.insert(0,sys.argv[1]); from shadow_comparison_runtime import fingerprint; print(fingerprint(Path(sys.argv[1]).parent))'
    $runtimeFingerprint = & $repositoryPython -c $fingerprintCode (Join-Path $repoRoot 'src')
    if ($LASTEXITCODE -ne 0 -or $runtimeFingerprint.Trim() -ne $manifest.expected_initial_fingerprint) { throw 'Reviewed policy or Python dependency versions changed; revalidate the release.' }
    foreach ($taskName in @('Project Stonks Daily Run','Project Stonks Intraday Option Research')) {
        try { $scheduledTask = Get-ScheduledTask -TaskName $taskName -ErrorAction Stop }
        catch { throw "Cannot verify scheduled job '$taskName'. Run activation from your normal Windows PowerShell session." }
        if ($scheduledTask.State -eq 'Disabled') { throw "Scheduled job is disabled: $taskName" }
        $targetText = ($scheduledTask.Actions | ForEach-Object { "$($_.Execute) $($_.Arguments) $($_.WorkingDirectory)" }) -join ' '
        if ($targetText.IndexOf($repoRoot, [System.StringComparison]::OrdinalIgnoreCase) -lt 0) {
            throw "Scheduled job does not point to this reviewed checkout: $taskName"
        }
    }
    if ($manifest.hash_mode -ne 'UTF8_NO_BOM_LF') { throw 'Unknown release hash format.' }
    foreach ($entry in $manifest.files) {
        $candidatePath = Join-Path $repoRoot $entry.path
        $candidateText = [System.IO.File]::ReadAllText($candidatePath, [System.Text.Encoding]::UTF8).Replace("`r`n", "`n").Replace("`r", "`n")
        $hashAlgorithm = [System.Security.Cryptography.SHA256]::Create()
        try { $actualHash = ([BitConverter]::ToString($hashAlgorithm.ComputeHash([System.Text.Encoding]::UTF8.GetBytes($candidateText)))).Replace('-', '').ToLowerInvariant() }
        finally { $hashAlgorithm.Dispose() }
        if ($actualHash -ne $entry.sha256) { throw "Reviewed release file changed: $($entry.path)" }
    }
}
$currentState = Get-Content -LiteralPath (Join-Path $releaseDir 'activation.json') -Raw | ConvertFrom-Json
$currentState.enabled = (-not $Disable)
$settings = $currentState | ConvertTo-Json -Depth 10
[System.IO.File]::WriteAllText((Join-Path $releaseDir 'activation.json'), $settings, [System.Text.UTF8Encoding]::new($false))
if ($Disable) { Write-Output 'Shadow release disabled; historical evidence retained.' }
else { Write-Output 'Shadow release enabled for the next normal daily run. Baseline guidance retained.' }
