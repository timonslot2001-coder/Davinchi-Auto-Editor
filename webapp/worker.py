"""Windows worker: lets the Docker container run the editor's commands and read its files on this PC.
Every request needs the token from .env (AEV_WORKER_TOKEN); only the commands in host.ALLOWED run, and only files in
the AutoEdit folders are served (host.check_path)."""
from __future__ import annotations

import hmac
import os

from flask import Flask, jsonify, request, send_file

from .host import LocalHost


def create(token: str) -> Flask:
    app = Flask(__name__)
    host = LocalHost()

    @app.before_request
    def auth():
        if request.path != "/health" and not hmac.compare_digest(request.headers.get("X-Token", ""), token):
            return jsonify(error="bad token"), 401

    @app.errorhandler(Exception)
    def err(e):
        code = 403 if isinstance(e, PermissionError) else 404 if isinstance(e, (KeyError, FileNotFoundError)) else 400
        return jsonify(error=str(e)), code

    @app.get("/health")
    def health():
        return {"ok": True}

    @app.post("/jobs")
    def run():
        b = request.get_json()
        return host.run(b["args"], b.get("label", ""), b.get("project"))

    @app.get("/jobs")
    def jobs():
        return jsonify(host.list_jobs())

    @app.get("/jobs/<jid>")
    def job(jid):
        return host.job(jid, int(request.args.get("since", 0)))

    @app.post("/jobs/<jid>/cancel")
    def cancel(jid):
        return host.cancel(jid)

    @app.post("/call/<name>")
    def call(name):
        return jsonify(host.call(name, request.get_json(silent=True) or {}))

    @app.get("/file")
    def file():
        return send_file(host.file_path(request.args["path"]), conditional=True)

    @app.put("/file")
    def put_file():
        return host.write_file(request.args["path"], request.get_data())

    return app


def ensure_token() -> str:
    """AEV_WORKER_TOKEN from the environment or .env; made once and appended to .env (never printed)."""
    from .host import REPO
    tok = os.environ.get("AEV_WORKER_TOKEN")
    env = REPO / ".env"
    if not tok and env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if line.startswith("AEV_WORKER_TOKEN="):
                tok = line.split("=", 1)[1].strip()
    if not tok:
        import secrets
        tok = secrets.token_urlsafe(32)
        with env.open("a", encoding="utf-8") as f:
            f.write(f"\nAEV_WORKER_TOKEN={tok}\n")
    return tok


def serve(port: int = 5061, bind: str = "127.0.0.1") -> None:
    from .app import run_server
    print(f"AutoEdit worker on http://{bind}:{port} (Docker reaches it as host.docker.internal:{port})")
    run_server(create(ensure_token()), bind, port)
