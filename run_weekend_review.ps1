$ErrorActionPreference = 'Stop'
$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) { throw 'Project Python environment is missing.' }
$logDirectory = Join-Path $PSScriptRoot 'logs'
New-Item -ItemType Directory -Path $logDirectory -Force | Out-Null
$log = Join-Path $logDirectory ('weekend_review_' + (Get-Date -Format 'yyyy-MM-dd') + '.log')
Push-Location $PSScriptRoot
try {
    Add-Content -LiteralPath $log -Value ('Started: ' + (Get-Date -Format o))
    & $python -u 'src\weekend_brief.py' --scheduled --send >> $log 2>&1
    $result = $LASTEXITCODE
    Add-Content -LiteralPath $log -Value ('Finished: ' + (Get-Date -Format o) + '; exit=' + $result)
}
finally { Pop-Location }
exit $result
