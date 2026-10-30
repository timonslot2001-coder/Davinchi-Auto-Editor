@echo off
rem AutoEdit Studio without Docker: the web app runs directly on this PC -> http://127.0.0.1:5060
set PYTHONIOENCODING=utf-8
set "PY=%USERPROFILE%\.aev\Scripts\python.exe"
if not exist "%PY%" set "PY=%~dp0.venv\Scripts\python.exe"
cd /d "%~dp0"
"%PY%" -m webapp %*
