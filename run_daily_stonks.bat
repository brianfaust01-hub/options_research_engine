@echo off
setlocal
cd /d "%~dp0"

if not exist logs mkdir logs

echo. >> logs\weekly_scan.log
echo ================================================== >> logs\weekly_scan.log
echo Project Stonks run started: %date% %time% >> logs\weekly_scan.log
echo ================================================== >> logs\weekly_scan.log

call .venv\Scripts\activate >> logs\weekly_scan.log 2>&1

python -u src\daily_run.py >> logs\weekly_scan.log 2>&1
set "STONKS_EXIT_CODE=%errorlevel%"

if "%STONKS_EXIT_CODE%"=="0" (
    powershell.exe -NoProfile -NonInteractive -Command "$marker = Join-Path '%~dp0logs' ('daily_success_' + (Get-Date -Format 'yyyy-MM-dd') + '.marker'); Set-Content -LiteralPath $marker -Value ('completed_at=' + (Get-Date -Format 'o')) -Encoding ascii"
)

echo Project Stonks run finished: %date% %time% >> logs\weekly_scan.log
echo Exit code: %STONKS_EXIT_CODE% >> logs\weekly_scan.log
exit /b %STONKS_EXIT_CODE%
