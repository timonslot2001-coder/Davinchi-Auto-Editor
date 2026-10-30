"""python -m webapp                 the web app on this PC, everything local   → http://127.0.0.1:5060
python -m webapp worker          the Windows worker for the Docker container (port 5061, token from .env)
python -m webapp --bind 0.0.0.0  also reachable from other devices on your network (phone)"""
from __future__ import annotations

import argparse
import webbrowser


def main(argv=None):
    ap = argparse.ArgumentParser(prog="webapp")
    ap.add_argument("role", nargs="?", choices=["app", "worker"], default="app")
    ap.add_argument("--port", type=int)
    ap.add_argument("--bind", default="127.0.0.1")
    ap.add_argument("--no-browser", action="store_true")
    args = ap.parse_args(argv)
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
