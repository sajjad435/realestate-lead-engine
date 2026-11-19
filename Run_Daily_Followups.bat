@echo off
title Real Estate Lead Engine - Daily Follow-up Dispatcher
cd /d "%~dp0"

echo =================================================================
echo  📬 RUNNING AUTOMATED FOLLOW-UPS (Day-3 Follow-up Check)
echo =================================================================

.\.venv\Scripts\python.exe main.py --followup

echo.
echo Process complete.
timeout /t 5 >nul
