@echo off
rem Run this on the PC with DaVinci Resolve and the footage, so AutoEdit Studio in Docker on another computer
rem (your laptop) can use it. It shows the address and token to put in the laptop's .env, then starts the worker.
rem The worker is reachable on your home network (token required). Windows may ask to allow Python through the
rem firewall: allow it for private networks only. Stop it by closing this window.
set PYTHONIOENCODING=utf-8
set "PY=%USERPROFILE%\.aev\Scripts\python.exe"
if not exist "%PY%" set "PY=%~dp0.venv\Scripts\python.exe"
cd /d "%~dp0"
"%PY%" -m webapp laptop-info
"%PY%" -m webapp worker --bind 0.0.0.0
pause
