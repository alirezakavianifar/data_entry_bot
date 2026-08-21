@echo off
cd /d "%~dp0"
title Data Entry Client Signup Bot

echo ===================================================
echo     Data Entry Client Signup Automation Bot
echo ===================================================
echo.

python app.py --headed --source excel --input Test.xlsx --sites fairplaybet --limit 5

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] An error occurred during bot execution. Check logs/error.log for details.
)

echo.
echo ===================================================
echo Bot execution finished. Check logs/bot.log for details.
echo ===================================================
pause
