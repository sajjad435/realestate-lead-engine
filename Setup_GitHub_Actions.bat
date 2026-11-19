@echo off
title Push Project to GitHub for 24/7 Automated Cloud Follow-ups
cd /d "%~dp0"

echo =================================================================
echo  🚀 INITIALIZING GITHUB REPO FOR 24/7 AUTOMATED CLOUD FOLLOW-UPS
echo =================================================================
echo.
echo This script will help you push your Lead Engine to your private GitHub repo.
echo Once pushed, GitHub Actions will run follow-ups 24/7 in the cloud,
echo EVEN WHEN YOUR LAPTOP IS COMPLETELY SHUT DOWN!
echo.

set /p REPO_URL="Enter your GitHub Repository URL (e.g. https://github.com/yourusername/lead-engine.git): "

if "%REPO_URL%"=="" (
    echo [ERROR] Repository URL cannot be empty.
    pause
    exit /b
)

echo.
echo [1/4] Initializing Git repository...
git init
git branch -M main

echo.
echo [2/4] Staging project files (Excluding local venv)...
git add .
git reset .venv 2>nul

echo.
echo [3/4] Creating initial commit...
git commit -m "Setup 24/7 Worldwide Real Estate Lead & Followup Engine"

echo.
echo [4/4] Connecting remote origin and pushing to GitHub...
git remote remove origin 2>nul
git remote add origin %REPO_URL%
git push -u origin main

if %ERRORLEVEL% EQU 0 (
    echo.
    echo =================================================================
    echo  🎉 SUCCESS! Project pushed to GitHub successfully!
    echo =================================================================
    echo Next steps:
    echo 1. Go to your GitHub repo -> Settings -> Secrets and variables -> Actions
    echo 2. Add these Repository Secrets:
    echo    - SENDER_EMAIL        (Your Gmail address)
    echo    - SENDER_APP_PASSWORD (Your 16-character Gmail App Password)
    echo    - SENDER_NAME         (e.g. Sajjad Wali)
    echo    - PORTFOLIO_URL       (Your portfolio link)
    echo 3. Go to Settings -> Actions -> General -> Workflow permissions:
    echo    Select "Read and write permissions" (so it saves your database).
    echo.
    echo That's it! GitHub Actions will now automatically send follow-ups
    echo at each country's local 10:30 AM 24/7, even when your laptop is OFF!
) else (
    echo.
    echo [NOTICE] Push encountered an issue. Ensure git is installed and credentials are configured.
)

echo.
pause
