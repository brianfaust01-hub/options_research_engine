@echo off
cd /d C:\Users\brian\Trading_systems\options_research_engine

if not exist logs mkdir logs

echo. >> logs\weekly_scan.log
echo ================================================== >> logs\weekly_scan.log
echo Project Stonks run started: %date% %time% >> logs\weekly_scan.log
echo ================================================== >> logs\weekly_scan.log

call .venv\Scripts\activate >> logs\weekly_scan.log 2>&1

python -u src\weekly_scan.py >> logs\weekly_scan.log 2>&1

echo Project Stonks run finished: %date% %time% >> logs\weekly_scan.log
echo Exit code: %errorlevel% >> logs\weekly_scan.log