@echo off
title Setup Automated Global Follow-up Task in Windows
cd /d "%~dp0"

echo =================================================================
echo  ⚙️ CONFIGURING WINDOWS 24/7 WORLDWIDE FOLLOW-UP TASK SCHEDULER
echo =================================================================
echo.
echo Task 1: RealEstateGlobalHourlyFollowup (Runs every hour)
echo          - Automatically catches ANY country/city in the world
echo            (India, US, UK, Canada, Australia, UAE, Europe) at their
echo            EXACT local 10:00 AM - 10:30 AM morning window!
echo          - Defers all agents sleeping at night.
echo Task 2: RealEstateLeadFollowup (Dedicated India Morning 10:30 AM IST)
echo Task 3: RealEstateLeadFollowup_US (Dedicated US Morning 09:00 PM IST = 10:30 AM EST)
echo Target: %~dp0Run_Daily_Followups.bat
echo.

schtasks /create /tn "RealEstateGlobalHourlyFollowup" /tr "\"%~dp0Run_Daily_Followups.bat\"" /sc hourly /mo 1 /f
schtasks /create /tn "RealEstateLeadFollowup" /tr "\"%~dp0Run_Daily_Followups.bat\"" /sc daily /st 10:30 /f
schtasks /create /tn "RealEstateLeadFollowup_US" /tr "\"%~dp0Run_Daily_Followups.bat\"" /sc daily /st 21:00 /f

if %ERRORLEVEL% EQU 0 (
    echo.
    echo [SUCCESS] Worldwide timezone-aware follow-up tasks registered in Windows Task Scheduler:
    echo  1. Global Hourly Task:  Runs every 1 hour 24/7 (Triggered at local 10:00-10:30 AM anywhere in the world)
    echo  2. India Morning Task: Runs daily at 10:30 AM IST
    echo  3. US Morning Task:    Runs daily at 09:00 PM IST (US Eastern 10:30 AM)
) else (
    echo.
    echo [NOTICE] If registration failed, please right-click this file and choose 'Run as administrator'.
)

echo.
pause
