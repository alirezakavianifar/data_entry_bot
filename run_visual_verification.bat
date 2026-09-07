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
echo   9. BetTOM
echo   10. easyBet
echo   11. 247 Bet
echo   12. Paddy Power
echo   13. Betfair
echo   14. DragonBet
echo   15. DragonBet (Betting Lounge #2)
echo   16. Phase 2 Sites Only (Sequential)
echo   17. All Sites (Sequential)
echo.
set /p choice="Enter option (1-17, default 1): "

if "%choice%"=="1" set target=bresbet
if "%choice%"=="2" set target=starsports
if "%choice%"=="3" set target=planetsportbet
if "%choice%"=="4" set target=betstgeorge
if "%choice%"=="5" set target=fairplaybet
if "%choice%"=="6" set target=betfred
if "%choice%"=="7" set target=quinnbet
if "%choice%"=="8" set target=betgoodwin
if "%choice%"=="9" set target=bettom
if "%choice%"=="10" set target=easybet
if "%choice%"=="11" set target=247bet
if "%choice%"=="12" set target=paddypower
if "%choice%"=="13" set target=betfair
if "%choice%"=="14" set target=dragonbet
if "%choice%"=="15" set target=bettinglounge2
if "%choice%"=="16" set target=phase2
if "%choice%"=="17" set target=all
if "%target%"=="" set target=bresbet

echo.
echo Launching visible browser for '%target%'...
echo.
python scripts\verify_nonheadless.py %target%
echo.
pause
