"""python -m webapp                 the web app on this PC, everything local   → http://127.0.0.1:5060
python -m webapp worker          the Windows worker for the Docker container (port 5061, token from .env)
python -m webapp laptop-info     address + token for a Docker container on another computer
python -m webapp --bind 0.0.0.0  also reachable from other devices on your network (phone)"""
from __future__ import annotations

import argparse
import webbrowser


def main(argv=None):
    ap = argparse.ArgumentParser(prog="webapp")
    ap.add_argument("role", nargs="?", choices=["app", "worker", "laptop-info"], default="app")
    ap.add_argument("--port", type=int)
    ap.add_argument("--bind", default="127.0.0.1")
    ap.add_argument("--no-browser", action="store_true")
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
    from .app import create, run_server
    port = args.port or 5060
    app = create()
    if not args.no_browser:
        webbrowser.open(f"http://127.0.0.1:{port}")
    print(f"AutoEdit Studio on http://{args.bind}:{port}")
    run_server(app, args.bind, port)


if __name__ == "__main__":
    main()
