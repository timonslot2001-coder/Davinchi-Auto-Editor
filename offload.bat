@echo off
rem Offload the SD card to the SSD: double-click, type the shoot name, pick the kind. Same as: autoedit offload "<name>" --soort <soort>
set PYTHONIOENCODING=utf-8
set "PY=%USERPROFILE%\.aev\Scripts\python.exe"
if not exist "%PY%" set "PY=%~dp0.venv\Scripts\python.exe"
cd /d "%~dp0"
echo.
echo   SD-kaart offloaden naar je SSD
echo   ------------------------------
echo.
set "NAME="
set /p "NAME=  Naam van de shoot (bijv. Beef Tartaar): "
if not defined NAME (
  echo   Geen naam ingevuld, er is niets gekopieerd.
  pause
  exit /b 1
)
echo.
echo   Soort:  1 Koken   2 Kleding   3 Smoken   4 Reizen   5 Klanten   6 Weet ik nog niet
:kies
set "K="
set /p "K=  Kies 1-6: "
if not defined K (
  echo   Niets gekozen, er is niets gekopieerd.
  pause
  exit /b 1
)
set "SOORT="
if "%K%"=="1" set "SOORT=koken"
if "%K%"=="2" set "SOORT=kleding"
if "%K%"=="3" set "SOORT=smoken"
if "%K%"=="4" set "SOORT=reizen"
if "%K%"=="5" set "SOORT=klanten"
if "%K%"=="6" set "SOORT=inbox"
if not defined SOORT goto kies
echo.
echo   %NAME% -^> %SOORT%
"%PY%" -m autoedit offload "%NAME%" --soort %SOORT%
echo.
pause
