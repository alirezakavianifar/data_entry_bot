@echo off
cd /d "%~dp0"
title Data Entry Bot - Desktop Application

echo ========================================================
echo       Launching Data Entry Bot Desktop Application...
echo ========================================================
echo.

python gui_app.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] An error occurred while launching the desktop application.
    echo Please make sure all requirements are installed (pip install -r requirements.txt).
    echo.
    pause
)
