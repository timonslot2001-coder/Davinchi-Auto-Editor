"""LightCraft in the browser, from anywhere: Apache Guacamole (Docker) shows only LightCraft's window, run on this PC
next to the SSD (RDP RemoteApp), at http://<Tailscale address>:8085/guacamole/ and http://127.0.0.1:8085/guacamole/.
Nothing is reachable from the internet: the port is bound to this PC and its Tailscale address only.

  python setup/lightcraft_web.py up        # write the config (first time) and start the two containers
  python setup/lightcraft_web.py down      # stop them
  python setup/lightcraft_web.py password  # new password for the Guacamole login (written to the file below)

The Guacamole login (user `timon`) gets a random password, stored only as a SHA-256 hash in the config; the plain
password is written once to data/guacamole/WACHTWOORD.txt for Timon. Windows asks for the Windows password itself
when LightCraft opens; it is never stored. Needs: Docker Desktop, Remote Desktop on, LightCraft registered as a
RemoteApp (see setup/README.md)."""
from __future__ import annotations

import hashlib
import os
import secrets
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "data" / "guacamole"                                # gitignored
PORT = 8085
IMAGES = ("guacamole/guacd:1.5.5", "guacamole/guacamole:1.5.5")

COMPOSE = """services:
  guacd:
    image: {guacd}
    restart: unless-stopped
  guacamole:
    image: {web}
    restart: unless-stopped
    depends_on: [guacd]
    environment:
      GUACD_HOSTNAME: guacd
      GUACAMOLE_HOME: /config
    volumes:
      - ./config:/config:ro
    ports:
{ports}
    extra_hosts:
      - "host.docker.internal:host-gateway"
"""

MAPPING = """<user-mapping>
  <authorize username="timon" password="{hash}" encoding="sha256">
    <connection name="LightCraft">
      <protocol>rdp</protocol>
      <param name="hostname">host.docker.internal</param>
      <param name="port">3389</param>
      <param name="security">nla</param>
      <param name="ignore-cert">true</param>
      <param name="remote-app">||lightcraft</param>
      <param name="resize-method">display-update</param>
      <param name="enable-wallpaper">false</param>
      <param name="color-depth">24</param>
    </connection>
  </authorize>
</user-mapping>
"""


def docker() -> str:
    exe = shutil.which("docker") or r"C:\Program Files\Docker\Docker\resources\bin\docker.exe"
    if not Path(exe).exists():
        raise SystemExit("Docker Desktop is not installed (winget install Docker.DockerDesktop)")
    return exe


def tailscale_ip() -> str | None:
    sys.path.insert(0, str(REPO))
    from webapp.phone import tailscale_ip as ip
    return ip()


def set_password() -> None:
    pw = secrets.token_urlsafe(14)
    (OUT / "config").mkdir(parents=True, exist_ok=True)
    (OUT / "config" / "user-mapping.xml").write_text(
        MAPPING.format(hash=hashlib.sha256(pw.encode()).hexdigest()), encoding="utf-8")
    (OUT / "WACHTWOORD.txt").write_text(
        f"LightCraft in de browser\ngebruiker: timon\nwachtwoord: {pw}\n", encoding="utf-8")
    print(f"new Guacamole password written to {OUT / 'WACHTWOORD.txt'}")


def write_compose() -> list[str]:
    ip = tailscale_ip()
    binds = ["127.0.0.1"] + ([ip] if ip else [])
    ports = "\n".join(f'      - "{b}:{PORT}:8080"' for b in binds)
    (OUT / "docker-compose.yml").write_text(COMPOSE.format(guacd=IMAGES[0], web=IMAGES[1], ports=ports),
                                            encoding="utf-8")
    return [f"http://{b}:{PORT}/guacamole/" for b in binds]


def main(argv: list[str]) -> int:
    cmd = argv[0] if argv else "up"
    OUT.mkdir(parents=True, exist_ok=True)
    if cmd == "password":
        set_password()
        cmd = "up"
    if cmd == "up":
        if not (OUT / "config" / "user-mapping.xml").exists():
            set_password()
        urls = write_compose()
        subprocess.run([docker(), "compose", "up", "-d", "--force-recreate"], cwd=OUT, check=True)
        print("LightCraft in de browser: " + "  ".join(urls))
        return 0
    if cmd == "down":
        subprocess.run([docker(), "compose", "down"], cwd=OUT, check=True)
        return 0
    raise SystemExit(__doc__)


if __name__ == "__main__":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    sys.exit(main(sys.argv[1:]))
