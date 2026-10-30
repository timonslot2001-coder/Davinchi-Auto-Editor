@echo off
rem AutoEdit Studio in Docker Desktop: starts the Windows worker (Resolve, GPU, footage) and the container.
rem Then open http://localhost:5060. Stop: close the worker window and run "docker compose down".
set PYTHONIOENCODING=utf-8
set "PY=%USERPROFILE%\.aev\Scripts\python.exe"
if not exist "%PY%" set "PY=%~dp0.venv\Scripts\python.exe"
cd /d "%~dp0"
start "AutoEdit worker" "%PY%" -m webapp worker
timeout /t 3 /nobreak >nul
docker compose up -d --build || (echo Docker Desktop is not running. Start it and run this again. & pause & exit /b 1)
start "" http://localhost:5060
