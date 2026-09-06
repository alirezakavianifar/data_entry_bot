@echo off
title Data Entry Bot - Visual Non-Headless Verification
cd /d "%~dp0"

echo ================================================================
echo        DATA ENTRY BOT - NON-HEADLESS VISUAL VERIFICATION
echo ================================================================
echo.
echo Select target bookmaker to test visually in Chrome:
echo   1. BresBet
echo   2. Star Sports
echo   3. Planet Sport Bet
echo   4. Bet St George
echo   5. Fairplay Bet
echo   6. Betfred
echo   7. QuinnBet
echo   8. Betgoodwin
echo   9. All Sites (Sequential)
echo.
set /p choice="Enter option (1-9, default 1): "

if "%choice%"=="1" set target=bresbet
if "%choice%"=="2" set target=starsports
if "%choice%"=="3" set target=planetsportbet
if "%choice%"=="4" set target=betstgeorge
if "%choice%"=="5" set target=fairplaybet
if "%choice%"=="6" set target=betfred
if "%choice%"=="7" set target=quinnbet
if "%choice%"=="8" set target=betgoodwin
if "%choice%"=="9" set target=all
if "%target%"=="" set target=bresbet

echo.
echo Launching visible browser for '%target%'...
echo.
python scripts\verify_nonheadless.py %target%
echo.
pause
