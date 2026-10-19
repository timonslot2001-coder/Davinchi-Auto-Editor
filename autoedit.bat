@echo off
rem AutoEdit launcher: double-click for the dashboard, or use from a terminal: autoedit run "C:\path\to\clips" --style fitness
set PYTHONIOENCODING=utf-8
if "%~1"=="" (
  "%~dp0.venv\Scripts\python.exe" -m autoedit dashboard
) else (
  "%~dp0.venv\Scripts\python.exe" -m autoedit %*
)
