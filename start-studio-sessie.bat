@echo off
rem Starts the one Claude Code session that runs the buttons of the AutoEdit Studio Artifact (skill studio-session).
rem Keep this window open. STUDIO_URL is the Studio owned by timon@juict.nl; the Claude app on this PC must be signed in with that account.
set "STUDIO_URL=https://claude.ai/artifact/4YCCLgHK4KozydqGCpjLQR"
set PYTHONIOENCODING=utf-8
cd /d "%~dp0"
rem The website (autoedit.bat) too, unless it already runs: the Studio's Foto's link opens it.
powershell -NoProfile -Command "if (Get-NetTCPConnection -LocalPort 5080 -State Listen -ErrorAction SilentlyContinue) { exit 0 } else { exit 1 }"
if errorlevel 1 start "AutoEdit website" /min "%~dp0autoedit.bat"
claude "start de Studio-sessie: %STUDIO_URL%"
