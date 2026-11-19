@echo off
title Real Estate Lead Engine - Sajjad Wali
cd /d "%~dp0"
cls
echo =================================================================
echo   REAL ESTATE LEAD GENERATOR ^& COLD OUTREACH ENGINE
echo =================================================================
echo.
set /p CITY="Enter City or State name (e.g. Miami, FL or Texas): "
if "%CITY%"=="" (
    echo [!] No city entered. Exiting.
    pause
    exit /b
)

echo.
echo [*] Starting Live Outreach for: %CITY%...
echo [*] Scraping Google Maps and Instagram...
echo [*] Filtering agents without website...
echo [*] Dispatching cold emails and generating PDF...
echo.

set PYTHONPATH=%~dp0
".venv\Scripts\python.exe" main.py --city "%CITY%" --live

echo.
echo =================================================================
echo   Run complete! See executive summary and report status above.
echo =================================================================
pause
