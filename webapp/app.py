"""AutoEdit Studio: the web app. Pages in static/, JSON API below. Every action becomes one of the editor's own
commands (cine montage `engine ...`, AutoEdit `autoedit ...`), built here from form fields, never from raw text.

The approval gates stay: rendering a cine montage needs the Approve button (with your words) on the current plan, paid
AI shots need a price quote and a confirmation, and nothing posts unless you press Post or approve it in the queue."""
from __future__ import annotations

import os
import re
from pathlib import Path

from flask import Flask, Response, jsonify, request, send_file, send_from_directory

STATIC = Path(__file__).with_name("static")
LOOKS = {"reference_film", "clean_warm", "moody"}
GRADES = {"auto", "slog3", "rec709", "none"}


def make_host():
    url = os.environ.get("AEV_WORKER_URL")
    if url:
        from .host import RemoteHost
        return RemoteHost(url, os.environ.get("AEV_WORKER_TOKEN", ""))
    from .host import LocalHost
    return LocalHost()


def _num(v, lo, hi, cast=float):
    if v in (None, ""):
        return None
    x = cast(v)
    if not lo <= x <= hi:
        raise ValueError(f"{x} outside {lo}-{hi}")
    return str(x)


def _text(v, maxlen=200):
    v = (v or "").strip()
    if len(v) > maxlen or any(c in v for c in "\r\n\0"):
        raise ValueError("text too long or has line breaks")
    return v


def _shot(v):
    v = _text(v, 80)
    if v and not re.fullmatch(r"[\w.\-]+(:\d+(\.\d+)?)?", v):
        raise ValueError("shot must look like CLIP or CLIP:seconds")
    return v


def create(host=None) -> Flask:
    app = Flask(__name__, static_folder=None)
    host = host or make_host()
    app.config["MAX_CONTENT_LENGTH"] = 500 * 1024 * 1024

    @app.errorhandler(Exception)
    def err(e):
        code = getattr(e, "code", None) or (403 if isinstance(e, PermissionError) else
                                           404 if isinstance(e, (KeyError, FileNotFoundError)) else 400)
        return jsonify(error=str(e)), code if isinstance(code, int) else 400

    def proj(name):
        return host.call("project", {"name": name})

    def job(args, label, project=None):
        return jsonify(host.run(args, label, project))

    # ------------------------------------------------------------ pages
    @app.get("/")
    def index():
        return send_from_directory(STATIC, "index.html")

    @app.get("/favicon.ico")
    def favicon():
        return "", 204

    @app.get("/static/<path:f>")
    def static_file(f):
        return send_from_directory(STATIC, f)

    # ------------------------------------------------------------ status, files, jobs
    @app.get("/api/status")
    def status():
        return {**host.call("status"), "mode": host.mode}

    @app.get("/api/file")
    def file():
        path = request.args["path"]
        if host.mode == "local":
            return send_file(host.file_path(path), conditional=True)
        fwd = {k: v for k, v in request.headers.items() if k.lower() in ("range", "if-none-match", "if-modified-since")}
        r = host.stream_file(path, fwd)
        keep = {k: v for k, v in r.headers.items() if k.lower() in (
            "content-type", "content-length", "content-range", "accept-ranges", "etag", "last-modified")}
        return Response(r.iter_content(256 * 1024), status=r.status_code, headers=keep)

    @app.get("/api/jobs")
    def jobs():
        return jsonify(host.list_jobs())

    @app.get("/api/jobs/<jid>")
    def job_detail(jid):
        return host.job(jid, int(request.args.get("since", 0)))

    @app.post("/api/jobs/<jid>/cancel")
    def job_cancel(jid):
        return host.cancel(jid)

    # ------------------------------------------------------------ projects
    @app.get("/api/projects")
    def projects():
        return jsonify(host.call("projects"))

    @app.post("/api/projects")
    def new_project():
        b = request.get_json()
        name = _text(b.get("name"), 80)
        if not name or not re.fullmatch(r"[\w .,'&()\-]+", name):
            raise ValueError("use letters, digits, spaces and - _ . , ' & ( ) in the name")
        args = ["autoedit", "new", name] + (["--title", _text(b["title"], 80)] if b.get("title") else [])
        return job(args, f"Nieuw project: {name}", name)

    @app.get("/api/projects/<name>")
    def project(name):
        return proj(name)

    @app.put("/api/projects/<name>/settings")
    def save_settings(name):
        return host.call("save_settings", {"name": name, "text": request.get_json()["yaml"]})

    @app.put("/api/projects/<name>/comments")
    def save_comments(name):
        return host.call("save_comments", {"name": name, "comments": request.get_json()["comments"]})

    @app.post("/api/projects/<name>/import")
    def import_card(name):
        b = request.get_json() or {}
        since = _text(b.get("since"), 10)
        if since and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", since):
            raise ValueError("date as YYYY-MM-DD")
        return job(["autoedit", "import", name] + (["--since", since] if since else []), "SD-kaart importeren", name)

    @app.post("/api/projects/<name>/analyze")
    def analyze(name):
        return job(["autoedit", "analyze", str(Path(proj(name)["path"]) / "clips")], "Clips analyseren", name)

    # ------------------------------------------------------------ cine montage
    @app.post("/api/projects/<name>/cine/plan")
    def cine_plan(name):
        b = request.get_json() or {}
        p = proj(name)["path"]
        a = ["engine", "plan", p]
        for flag, val in (("--title", _text(b.get("title"), 40)), ("--length", _num(b.get("length"), 8, 30)),
                          ("--seed", _num(b.get("seed"), 0, 99999, int)), ("--song", _text(b.get("song"), 120)),
                          ("--title-shot", _shot(b.get("title_shot"))), ("--final-shot", _shot(b.get("final_shot")))):
            if val:
                a += [flag, val]
        if b.get("accent"):
            if not re.fullmatch(r"#[0-9A-Fa-f]{6}", b["accent"]):
                raise ValueError("accent as #RRGGBB")
            a += ["--accent", b["accent"]]
        for flag, key, allowed in (("--look", "look", LOOKS), ("--grade", "grade", GRADES),
                                   ("--order", "order", {"best", "story"}), ("--grid-flow", "grid_flow", {"auto", "off"}),
                                   ("--card", "card", {"auto", "on", "off"}), ("--bw", "bw", {"auto", "off"}),
                                   ("--variant", "variant", {"poster_condensed", "heavy_grotesque"})):
            if b.get(key):
                if b[key] not in allowed:
                    raise ValueError(f"{key}: one of {sorted(allowed)}")
                a += [flag, b[key]]
        return job(a, "Cine montage: plan maken", name)

    def grade_args(b):
        a = []
        if b.get("grade") in GRADES:
            a += ["--grade", b["grade"]]
        if b.get("look") in LOOKS - {"reference_film"}:
            a += ["--look", b["look"]]
        return a

    @app.post("/api/projects/<name>/cine/approve")
    def cine_approve(name):
        note = _text((request.get_json() or {}).get("note"), 300)
        if not note:
            raise ValueError("write in your own words what you approve")
        return job(["engine", "approve", proj(name)["path"], "--by", "Timon", "--note", note], "Plan goedkeuren", name)

    @app.post("/api/projects/<name>/cine/<action>")
    def cine_action(name, action):
        if action not in ("preview", "render", "qa", "check"):
            raise KeyError(action)
        b = request.get_json() or {}
        a = ["engine", action, proj(name)["path"]] + (grade_args(b) if action in ("preview", "render") else [])
        if action == "qa" and b.get("grade") in GRADES:
            a += ["--grade", b["grade"]]
        labels = {"preview": "Voorbeeld (halve grootte)", "render": "Renderen", "qa": "QA", "check": "Stijlchecks"}
        return job(a, f"Cine montage: {labels[action]}", name)

    # ------------------------------------------------------------ AutoEdit (Resolve)
    @app.post("/api/projects/<name>/autoedit")
    def autoedit_build(name):
        b = request.get_json() or {}
        a = ["autoedit", "project", name]
        for flag, val in (("--song", _text(b.get("song"), 120)), ("--title", _text(b.get("title"), 60)),
                          ("--seed", _num(b.get("seed"), 0, 99999, int))):
            if val:
                a += [flag, val]
        if b.get("variants"):
            if not re.fullmatch(r"[ABC]{1,3}", b["variants"]):
                raise ValueError("variants: A, AB or ABC")
            a += ["--variants", b["variants"]]
        return job(a, "AutoEdit: bouwen in Resolve", name)

    @app.post("/api/projects/<name>/explainer")
    def explainer(name):
        return job(["autoedit", "explainer", name], "Explainer-video", name)

    # ------------------------------------------------------------ AI shots
    @app.post("/api/projects/<name>/ai/<action>")
    def ai(name, action):
        if action not in ("quote", "generate"):
            raise KeyError(action)
        b = request.get_json() or {}
        prompt = _text(b.get("prompt"), 600)
        if not prompt:
            raise ValueError("write a prompt")
        model = _text(b.get("model"), 40) or "local-wan"
        if not re.fullmatch(r"[\w\-]+", model):
            raise ValueError("unknown model")
        a = ["autoedit", "generate", prompt, "--project", name, "--model", model,
             "--seconds", _num(b.get("seconds") or 5, 2, 10, int), "--aspect", b.get("aspect") or "16:9",
             "--role", _text(b.get("role"), 30) or "establish"]
        if b.get("aspect", "16:9") not in ("16:9", "9:16", "1:1"):
            raise ValueError("aspect: 16:9, 9:16 or 1:1")
        if action == "quote":
            a.append("--quote")
        elif not model.startswith("local"):
            if not b.get("confirmed_price"):                       # paid model: the page shows the quote first
                raise ValueError("ask for the price first and confirm it")
            a.append("--yes")
        return job(a, f"AI-shot: {'prijs' if action == 'quote' else 'maken'} ({model})", name)

    # ------------------------------------------------------------ queue, music, insights
    @app.get("/api/queue")
    def queue():
        return jsonify(host.call("queue"))

    @app.post("/api/queue/<eid>/choose")
    def queue_choose(eid):
        b = request.get_json()
        return host.call("queue_choose", {"entry_id": eid, "platform": b["platform"], "index": int(b["index"])})

    @app.post("/api/queue/<eid>/<action>")
    def queue_action(eid, action):
        if not re.fullmatch(r"[0-9a-f]{6,16}", eid) or action not in ("approve", "post"):
            raise KeyError(action)
        b = request.get_json() or {}
        a = ["autoedit", action, eid] + (["--caption", str(int(b.get("caption", 0)))] if action == "approve" else [])
        return job(a, "Goedkeuren voor posten" if action == "approve" else "Nu posten")

    @app.get("/api/music")
    def music():
        return jsonify(host.call("music"))

    @app.post("/api/music")
    def music_upload():
        folder = Path(host.call("roots")["music"])
        saved = []
        for f in request.files.getlist("file"):
            name = Path(f.filename).name
            host.write_file(str(folder / name), f.read())
            saved.append(name)
        return {"saved": saved}

    @app.get("/api/ai-models")
    def ai_models():
        return jsonify(host.call("ai_models"))

    @app.get("/api/report")
    def report():
        return {"text": host.call("report")}

    @app.post("/api/tools/<tool>")
    def tools(tool):
        b = request.get_json() or {}
        simple = {"stats": "Instagram-statistieken ophalen", "ai-balance": "Muapi-tegoed", "ai-models": "AI-modellen + prijzen",
                  "sfx": "SFX-bibliotheek", "optimize": "Resolve soepeler maken", "projects": "Projecten",
                  "post-due": "Geplande posts versturen"}
        if tool in simple:
            return job(["autoedit", tool], simple[tool])
        if tool == "ideas":
            style = b.get("style") or "lifestyle"
            if not re.fullmatch(r"[\w\-]+", style):
                raise ValueError("style")
            return job(["autoedit", "ideas", "--style", style, "--weeks", _num(b.get("weeks") or 2, 1, 8, int)],
                       "Contentideeën")
        if tool == "validate":
            return job(["engine", "validate"], "Editor controleren")
        raise KeyError(tool)

    return app


def run_server(app, bind: str, port: int) -> None:
    try:
        from waitress import serve
        serve(app, host=bind, port=port, threads=8)
    except ImportError:
        app.run(host=bind, port=port, threaded=True, use_reloader=False)
