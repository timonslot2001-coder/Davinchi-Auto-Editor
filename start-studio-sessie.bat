@echo off
rem Starts the one Claude Code session that runs the buttons of the AutoEdit Studio Artifact (skill studio-session).
rem Starts by itself at Windows log-in (setup\autostart-studio.ps1) and comes back by itself when the session stops:
rem close this window to really stop it. Every start first gets the newest code (git pull), and the session itself pulls
rem again before each Studio request, so a merged change works without restarting anything.
rem STUDIO_URL is the Studio owned by timon@juict.nl; the Claude app on this PC must be signed in with that account.
set "STUDIO_URL=https://claude.ai/artifact/4YCCLgHK4KozydqGCpjLQR"
set PYTHONIOENCODING=utf-8
cd /d "%~dp0"
title AutoEdit Studio-sessie
rem The website (autoedit.bat) too, unless it already runs: the Studio's Foto's link opens it.
powershell -NoProfile -Command "if (Get-NetTCPConnection -LocalPort 5080 -State Listen -ErrorAction SilentlyContinue) { exit 0 } else { exit 1 }"
if errorlevel 1 start "AutoEdit website" /min "%~dp0autoedit.bat"
:loop
git pull --ff-only --quiet || echo (bijwerken lukte niet: verder met de code die er is)
claude "start de Studio-sessie: %STUDIO_URL%"
echo.
echo Studio-sessie gestopt. Over 15 seconden start hij opnieuw; sluit dit venster om te stoppen.
timeout /t 15 >nul
goto loop
