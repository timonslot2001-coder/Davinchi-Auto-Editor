"""python -m webapp                 the web app on this PC, everything local   → http://127.0.0.1:5080
python -m webapp worker          the Windows worker for the Docker container (port 5061, token from .env)
python -m webapp laptop-info     address + token for a Docker container on another computer
python -m webapp --phone         also on your phone through Tailscale; only this PC and your tailnet get in (phone.py)
python -m webapp --bind 0.0.0.0  reachable from every device on your network (no login: only on a network you trust)
python -m webapp studio --thread <id> --text-file data/studio_inbox/<id>.txt
                                 one request from the claude.ai Artifact (see studio.py): validates and starts it
                                 detached, JSON out at once ({status: "bezig"} or the refusal)
python -m webapp studio-result --thread <id>     that request's result line ({status: "bezig"} while it runs)
python -m webapp studio-projects                 every Studio project with its state document, JSON out
python -m webapp studio-state "<name>"           the project's state document for the Artifact db, JSON out
python -m webapp studio-ssd                      the SSD shoot folders for the Artifact db (ssd/<id>), JSON out"""
from __future__ import annotations

import argparse
import sys
import webbrowser


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    studio_cmds = ("studio", "studio-result", "studio-worker", "studio-state", "studio-projects", "studio-ssd", "studio-pc")
    if argv and argv[0] in studio_cmds:                                      # own arguments; no Flask needed
        from . import studio
        return {"studio": studio.cli, "studio-result": studio.result_cli, "studio-worker": studio.worker_cli,
                "studio-state": studio.state_cli, "studio-projects": studio.projects_cli,
                "studio-ssd": studio.ssd_cli, "studio-pc": studio.pc_cli}[argv[0]](argv[1:])
    ap = argparse.ArgumentParser(prog="webapp")
    ap.add_argument("role", nargs="?", choices=["app", "worker", "laptop-info"], default="app")
    ap.add_argument("--port", type=int)
    ap.add_argument("--bind", default="127.0.0.1")
    ap.add_argument("--no-browser", action="store_true")
    ap.add_argument("--phone", action="store_true", help="also on your phone through Tailscale (only your devices)")
    args = ap.parse_args(argv)
    if args.role == "laptop-info":                     # shown only in this PC's own window, for the laptop's .env
        import socket
        from .worker import ensure_token
        ips = sorted({i[4][0] for i in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET)
                      if not i[4][0].startswith("127.")})
        print("\nPut these lines in .env next to docker-compose.yml on the laptop:\n")
        for ip in ips or ["<this PC's IP>"]:
            print(f"  AEV_WORKER_URL=http://{ip}:{args.port or 5061}")
        print(f"  AEV_WORKER_TOKEN={ensure_token()}\n")
        if len(ips) > 1:
            print("  (several addresses: use the one in the same network as the laptop, usually 192.168.x.x)\n")
        return
    if args.role == "worker":
        from .worker import serve
        serve(args.port or 5061, args.bind)
        return
    from .app import create, make_host, run_server
    port = args.port or 5080
    host = make_host()
    app = create(host)
    if host.mode == "local":                                     # camera card in -> offload + proposal (cardwatch.py)
        from . import cardwatch
        if cardwatch.start(host):
            print("Camera card: goes in -> offloaded to _Inbox and a proposal per day (card_auto: false to switch off)")
    bind = args.bind
    if args.phone:
        from . import phone
        ts = phone.tailscale_ip()
        if ts:
            phone.guard(app)                                     # only this PC and your Tailscale devices
            bind = "0.0.0.0"
            print(f"On your phone (Tailscale on): http://{ts}:{port}")
        else:
            print("On your phone: install Tailscale on this PC and your phone (README, 'On your phone'). "
                  "Until then the website is on this PC only.")
    if not args.no_browser:
        webbrowser.open(f"http://127.0.0.1:{port}")
    print(f"AutoEdit on http://127.0.0.1:{port}")
    run_server(app, bind, port)


if __name__ == "__main__":
    sys.exit(main())
