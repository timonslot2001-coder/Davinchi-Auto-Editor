"""The website on your phone, through Tailscale (your own private network between your devices, free).

`python -m webapp --phone` (what autoedit.bat does) also listens on the network, but answers only this PC itself and
devices in your tailnet (Tailscale addresses 100.64.0.0/10 and fd7a:115c:a1e0::/48); everyone else gets 403. No
password or token: Tailscale already decides which devices are yours. Without Tailscale it stays on this PC only."""
from __future__ import annotations

import ipaddress
import os
import shutil
import subprocess

TAILNET = (ipaddress.ip_network("100.64.0.0/10"), ipaddress.ip_network("fd7a:115c:a1e0::/48"))


def allowed(remote: str | None) -> bool:
    """This PC or one of your Tailscale devices."""
    try:
        ip = ipaddress.ip_address((remote or "").split("%")[0])
    except ValueError:
        return False
    if getattr(ip, "ipv4_mapped", None):
        ip = ip.ipv4_mapped
    return ip.is_loopback or any(ip in net for net in TAILNET)


def tailscale_ip() -> str | None:
    """This PC's Tailscale IPv4 address, or None when Tailscale is not installed or not logged in."""
    exe = shutil.which("tailscale") or next(
        (p for p in (os.path.expandvars(r"%ProgramFiles%\Tailscale\tailscale.exe"),) if os.path.exists(p)), None)
    if not exe:
        return None
    try:
        out = subprocess.run([exe, "ip", "-4"], capture_output=True, text=True, timeout=5).stdout.split()
    except (OSError, subprocess.SubprocessError):
        return None
    return next((a for a in out if allowed(a) and not ipaddress.ip_address(a).is_loopback), None)


def guard(app) -> None:
    """Refuse every request that is not from this PC or your tailnet."""
    from flask import abort, request

    @app.before_request
    def _only_mine():
        if not allowed(request.remote_addr):
            abort(403)
