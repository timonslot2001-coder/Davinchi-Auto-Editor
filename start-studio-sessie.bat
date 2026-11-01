@echo off
rem Starts the one Claude Code session that runs the buttons of the AutoEdit Studio Artifact (skill studio-session).
rem Keep this window open. Change STUDIO_URL when the Studio is published under another account.
set "STUDIO_URL=https://claude.ai/artifact/4YCCLgHK4KozydqGCpjLQR"
set PYTHONIOENCODING=utf-8
cd /d "%~dp0"
claude "start de Studio-sessie: %STUDIO_URL%"
