@echo off
rem AutoEdit: double-click to open the website (also on your phone when Tailscale is on).
rem From a terminal it runs the editor commands: autoedit run "C:\path\to\clips", autoedit offload "Kas", ...
rem Python: %USERPROFILE%\.aev (full locked env, see setup\README.md), else the repo's .venv
set PYTHONIOENCODING=utf-8
set "PY=%USERPROFILE%\.aev\Scripts\python.exe"
if not exist "%PY%" set "PY=%~dp0.venv\Scripts\python.exe"
if "%~1"=="" (
  cd /d "%~dp0"
  "%PY%" -m webapp --phone
) else (
  "%PY%" -m autoedit %*
)
