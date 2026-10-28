@echo off
rem AutoEdit launcher: double-click for the dashboard, or use from a terminal: autoedit run "C:\path\to\clips" --style fitness
rem Python: %USERPROFILE%\.aev (full locked env, see setup\README.md), else the repo's .venv
set PYTHONIOENCODING=utf-8
set "PY=%USERPROFILE%\.aev\Scripts\python.exe"
if not exist "%PY%" set "PY=%~dp0.venv\Scripts\python.exe"
if "%~1"=="" (
  "%PY%" -m autoedit dashboard
) else (
  "%PY%" -m autoedit %*
)
