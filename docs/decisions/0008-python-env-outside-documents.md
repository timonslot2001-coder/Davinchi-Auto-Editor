# 0008 The Python environment lives in ~/.autoedit/venv

- Status: accepted
- Date: 2026-10-28
- Source: commit `a7c3031`

## Context
Windows Smart App Control blocks a venv inside Documents. Writes to `%LOCALAPPDATA%` from inside the Claude app are
silently redirected into the app's package folder. A venv in a session folder disappears with the session.

## Decision
The venv is built from `requirements-lock.txt` in `%USERPROFILE%\.autoedit\venv`. `%USERPROFILE%\.aev` is a junction to
it, so every script uses `C:\Users\Timon\.aev\Scripts\python.exe`. `autoedit.bat` falls back to the repo's `.venv`.

## Consequences
- After installing a package, `pip freeze` into `requirements-lock.txt` (keep its header).
- `av`/faster-whisper stays blocked by Smart App Control in every venv on this PC. This is known and not fixed here.
