"""Connects to a running DaVinci Resolve Studio (Preferences → System → General →
External scripting using: Local)."""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

API = os.environ.get("RESOLVE_SCRIPT_API",
                     r"C:\ProgramData\Blackmagic Design\DaVinci Resolve\Support\Developer\Scripting")
LIB = os.environ.get("RESOLVE_SCRIPT_LIB", r"C:\Program Files\Blackmagic Design\DaVinci Resolve\fusionscript.dll")
EXE = r"C:\Program Files\Blackmagic Design\DaVinci Resolve\Resolve.exe"

os.environ["RESOLVE_SCRIPT_API"] = API
os.environ["RESOLVE_SCRIPT_LIB"] = LIB
sys.path.append(str(Path(API) / "Modules"))


def _running() -> bool:
    out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq Resolve.exe"], capture_output=True, text=True).stdout
    return "Resolve.exe" in out


def connect(launch: bool = True, timeout: float = 120):
    import DaVinciResolveScript as dvr  # noqa: provided by Resolve

    if not _running() and launch:
        subprocess.Popen([EXE])
    deadline = time.time() + timeout
    while time.time() < deadline:
        resolve = dvr.scriptapp("Resolve")
        if resolve and resolve.GetProjectManager():
            return resolve
        time.sleep(2)
    raise SystemExit(
        "Can't reach DaVinci Resolve.\n"
        "  1. Is Resolve open (and past the startup screen)?\n"
        "  2. Preferences → System → General → 'External scripting using' = Local, then restart Resolve.")


def bmd():
    import DaVinciResolveScript as dvr  # noqa
    return dvr
