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

echo Project Stonks run finished: %date% %time% >> logs\weekly_scan.log
echo Exit code: %STONKS_EXIT_CODE% >> logs\weekly_scan.log
exit /b %STONKS_EXIT_CODE%
