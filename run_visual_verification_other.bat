@echo off
title Data Entry Bot - Visual Verification (Remaining Bookmakers)
cd /d "%~dp0"

echo ================================================================
echo    DATA ENTRY BOT - NON-HEADLESS VISUAL VERIFICATION (OTHER)
echo ================================================================
echo.
echo Select target bookmaker to test visually in Chrome:
echo   1. Betfred
echo   2. QuinnBet
echo   3. Betgoodwin
echo   4. Fairplay Bet
echo   5. All Remaining Sites (Sequential)
echo.
set /p choice="Enter option (1-5, default 1): "

if "%choice%"=="1" set target=betfred
if "%choice%"=="2" set target=quinnbet
if "%choice%"=="3" set target=betgoodwin
if "%choice%"=="4" set target=fairplaybet
if "%choice%"=="5" set target=all
if "%target%"=="" set target=betfred

echo.
echo Launching visible browser for '%target%'...
echo.
python scripts\verify_nonheadless_other.py %target%
echo.
pause
