"""Read-side of the web app: everything the pages show, as JSON. Runs on the Windows host (directly, or inside the
worker), because the projects, footage, queue and Resolve live there. Heavy modules are imported inside functions."""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
ENGINE_DIR = REPO / "VIDEO_EDITING_SYSTEM"
VIDEO_EXT = {".mp4", ".mov", ".mxf", ".mkv", ".avi", ".m4v"}
AUDIO_EXT = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg"}


def _cfg():
    sys.path.insert(0, str(REPO))
    from autoedit.config import load
    return load()


def roots() -> dict:
    """Folders the web app may read from (and the few files it may write)."""
    cfg = _cfg()
    return {"projects": str(Path(cfg.get("paths.projects_folder"))), "music": str(Path(cfg.get("paths.music_folder"))),
            "output": str(Path(cfg.get("paths.output_folder") or REPO / "data")), "data": str(REPO / "data"),
            "library": str(Path(cfg.get("paths.library_folder") or "I:/"))}


def project_dir(name: str) -> Path:
    root = Path(roots()["projects"])
    p = (root / name).resolve()
    if p.parent != root.resolve() or not p.is_dir():
        raise ValueError(f"no project named {name!r}")
    return p


def _file(p: Path) -> dict:
    st = p.stat()
    return {"name": p.name, "path": str(p), "size": st.st_size, "mtime": st.st_mtime}


def _settings(p: Path) -> tuple[dict, str]:
    y = p / "project.yaml"
    text = y.read_text(encoding="utf-8") if y.exists() else ""
    return (yaml.safe_load(text) or {}) if text else {}, text


# ---------------------------------------------------------------- status

def status() -> dict:
    cfg = _cfg()
    out = {"python": sys.executable, "repo": str(REPO), "projects_folder": roots()["projects"]}
    try:
        tl = subprocess.run(["tasklist", "/FI", "IMAGENAME eq Resolve.exe", "/NH"], capture_output=True, text=True,
                            timeout=5).stdout
        out["resolve"] = "Resolve.exe" in tl
    except Exception:
        out["resolve"] = None
    try:
        out["ssd"] = Path(roots()["library"]).exists()
    except OSError:
        out["ssd"] = False
    url = (cfg.get("local_ai.url") or "http://127.0.0.1:8188").rstrip("/")
    try:
        import requests
        out["comfyui"] = requests.get(url + "/system_stats", timeout=1.5).ok
    except Exception:
        out["comfyui"] = False
    return out


# ---------------------------------------------------------------- projects

def _thumb(p: Path) -> str | None:
    for c in (p / "cine_montage/storyboard/frames/E03.jpg", p / "cine_montage/storyboard/frames/E00.jpg"):
        if c.exists():
            return str(c)
    covers = sorted((p / "exports").glob("*cover*.jpg")) if (p / "exports").exists() else []
    return str(covers[-1]) if covers else None


def editor(p: Path, s: dict) -> str:
    """Which editor a project uses: `editor:` in project.yaml, else 'klant' for a client film (edit_v*.py in the folder,
    or clips under Klanten on the SSD), 'anders' for an explainer (script.yaml), else 'cine' (the cine montage)."""
    if s.get("editor") in ("cine", "snel", "klant", "anders"):
        return s["editor"]
    if any(p.glob("edit_v*.py")):
        return "klant"
    if (p / "script.yaml").exists():
        return "anders"
    try:
        clips = str((p / "clips").resolve()).replace("\\", "/").lower()
    except OSError:
        clips = ""
    return "klant" if "/klanten/" in clips + "/" else "cine"


def projects() -> list[dict]:
    root = Path(roots()["projects"])
    out = []
    for p in sorted(root.iterdir(), key=lambda d: d.stat().st_mtime, reverse=True) if root.exists() else []:
        if not p.is_dir():
            continue
        s, _ = _settings(p)
        clips = [f for f in (p / "clips").glob("*") if f.suffix.lower() in VIDEO_EXT] if (p / "clips").exists() else []
        exports = [f for f in (p / "exports").glob("*.mp4")] if (p / "exports").exists() else []
        appr = p / "cine_montage/APPROVAL.json"
        out.append({"name": p.name, "title": s.get("title"), "category": s.get("category"), "clips": len(clips),
                    "exports": len(exports), "thumb": _thumb(p), "mtime": p.stat().st_mtime, "editor": editor(p, s),
                    "cine": json.loads(appr.read_text(encoding="utf-8")).get("status") if appr.exists() else None})
    return out


def project(name: str) -> dict:
    p = project_dir(name)
    s, text = _settings(p)
    clips_dir = p / "clips"
    clips = sorted((_file(f) for f in clips_dir.glob("*") if f.suffix.lower() in VIDEO_EXT), key=lambda f: f["name"]) \
        if clips_dir.exists() else []
    music = [_file(f) for f in sorted((p / "music").glob("*")) if f.suffix.lower() in AUDIO_EXT] \
        if (p / "music").exists() else []
    exports = sorted((_file(f) for f in (p / "exports").glob("*") if f.suffix.lower() in {".mp4", ".mov", ".jpg", ".png"}),
                     key=lambda f: -f["mtime"]) if (p / "exports").exists() else []
    return {"name": p.name, "path": str(p), "settings": s, "yaml": text, "clips": clips, "music": music,
            "editor": editor(p, s),
            "exports": exports, "clips_link": str(clips_dir.resolve()) if clips_dir.exists() else None,
            "cine": cine(p)}


def cine(p: Path) -> dict:
    """State of the cine montage: plan (shots), style checks, approval, QA, comments."""
    work = p / "cine_montage"
    edl_path = work / "edl.json"
    out = {"has_plan": edl_path.exists(), "shots": [], "checks": [], "approval": None, "qa": None, "comments": {},
           "sheet": None, "notes": [], "grade": {"look": "reference_film", "strength": 1.0, "exposure": -1.75}}
    gp = work / "grade.json"
    if gp.exists():
        try:
            g = json.loads(gp.read_text(encoding="utf-8"))
            out["grade"] = {k: g.get(k, v) for k, v in out["grade"].items()}
        except ValueError:
            pass
    if not edl_path.exists():
        return out
    d = json.loads(edl_path.read_text(encoding="utf-8"))
    frames = work / "storyboard/frames"
    for n, e in enumerate(d["events"], 1):
        f = frames / f"{e['id']}.jpg"
        out["shots"].append({"n": n, "id": e["id"], "start": e["out_in"], "end": e["out_out"],
                             "clip": Path(e["source"]).name, "src_in": e["src_in"], "transition": e["transition_in"],
                             "treatment": e["treatment"], "role": e["params"].get("role"), "why": e.get("why", ""),
                             "frame": str(f) if f.exists() else None})
    out.update(duration=d["duration"], music=Path(d["music"]).name if d.get("music") else None, notes=d.get("notes", []),
               title=next((o["params"].get("text") for o in d["overlays"] if o["component"] == "title_slam"), None))
    sheet = work / "storyboard/storyboard_sheet.jpg"
    out["sheet"] = str(sheet) if sheet.exists() else None
    for k, f in (("approval", "APPROVAL.json"), ("qa", "qa.json"), ("comments", "comments.json")):
        if (work / f).exists():
            out[k] = json.loads((work / f).read_text(encoding="utf-8"))
    if out["approval"]:
        import hashlib
        out["approval"]["current"] = hashlib.sha1(edl_path.read_bytes()).hexdigest()[:12] == out["approval"].get("edl_sha1")
    try:
        sys.path.insert(0, str(ENGINE_DIR))
        from engine import style_checks
        from engine.edl import EDL
        out["checks"] = style_checks.check(EDL.load(edl_path))
    except Exception as e:                                          # the page still works without checks
        out["checks"] = [{"rule": "checks", "status": "warn", "msg": f"could not run: {e}"}]
    return out


def set_setting(text: str, key: str, value) -> str:
    """project.yaml text with `key:` set to `value` (None removes the line); keeps every other line and comment."""
    line = None if value is None else f"{key}: {json.dumps(value, ensure_ascii=False)}"
    pat = re.compile(rf"^{re.escape(key)}:[^\r\n]*(\r?\n)?", re.M)
    if pat.search(text):
        text = pat.sub(lambda m: line + (m.group(1) or "") if line else "", text, count=1)
    elif line:
        text = text.rstrip("\n") + "\n" + line + "\n"
    return text


def feedback(name: str, kind: str, clip: str | None = None) -> dict:
    """Website feedback on the current plan. Changes project.yaml where needed, logs it in
    cine_montage/feedback.json (Claude folds repeated feedback into the style rules), and returns the plan arguments
    for a new proposal."""
    import random as _random
    from datetime import datetime as _dt
    p = project_dir(name)
    c = cine(p)
    if not c["has_plan"]:
        raise ValueError("no plan yet")
    s, text = _settings(p)
    length = float(c.get("duration") or 18)
    seed = None
    note = kind
    if kind == "korter":
        length = max(8.0, length - 3)
    elif kind == "langer":
        length = min(30.0, length + 3)
    elif kind == "ander_voorstel":
        seed = _random.randint(2, 99999)
    elif kind == "ander_nummer":
        songs = [m["name"] for m in music()]
        cur = (s.get("song") or c.get("music") or "").lower()
        now = next((i for i, m in enumerate(songs) if cur and (cur == m.lower() or cur in m.lower())), -1)
        if len(songs) < (2 if now >= 0 else 1):
            raise ValueError("no other song in your music folder")
        nxt = songs[(now + 1) % len(songs)]
        text = set_setting(set_setting(text, "song", nxt), "song_start", None)    # the old start belongs to the old song
        note = f"ander nummer: {nxt}"
    elif kind == "eruit":
        if not clip or not re.fullmatch(r"[\w.\- ]{1,120}", clip):
            raise ValueError("which clip?")
        stem = Path(clip).stem
        skip = [str(x) for x in (s.get("skip") or [])]
        if stem.lower() not in [x.lower() for x in skip]:
            skip.append(stem)
        text = set_setting(text, "skip", skip)
        note = f"eruit: {stem}"
    else:
        raise ValueError("feedback: korter, langer, ander_voorstel, ander_nummer or eruit")
    if text != _settings(p)[1]:
        save_settings(name, text)
    log = p / "cine_montage" / "feedback.json"
    items = json.loads(log.read_text(encoding="utf-8")) if log.exists() else []
    items.append({"at": _dt.now().isoformat(timespec="seconds"), "feedback": note, "plan_seconds": c.get("duration")})
    log.write_text(json.dumps(items, indent=1, ensure_ascii=False), encoding="utf-8")
    args = ["--length", f"{length:g}"] + (["--title", c["title"]] if c.get("title") else []) + (["--seed", str(seed)] if seed else [])
    return {"path": str(p), "args": args, "note": note}


def looks(name: str, fresh: bool = False) -> dict:
    """One finished picture per look for this project (webapp/studio_assets.previews), made once and kept in
    data/studio_assets/<slug>/ until the plan changes or `fresh`. {look: path}."""
    from . import studio_assets
    from .studio import slug
    p = project_dir(name)
    out = REPO / "data" / "studio_assets" / slug(p.name)
    edl = p / "cine_montage" / "edl.json"
    have = {f.stem[len("preview_"):]: f for f in out.glob("preview_*.jpg")} if out.exists() else {}
    newest = edl.stat().st_mtime if edl.exists() else 0
    if fresh or len(have) < 6 or min(f.stat().st_mtime for f in have.values()) < newest:
        res = studio_assets.export(p, out)
        have = {k: out / v for k, v in res["previews"].items()}
    return {k: str(v) for k, v in have.items()}


def save_settings(name: str, text: str) -> dict:
    """Write project.yaml. The AI budget can not be raised from the web app (only Timon, by hand)."""
    p = project_dir(name)
    new = yaml.safe_load(text) or {}
    if not isinstance(new, dict):
        raise ValueError("project.yaml must be a mapping (key: value)")
    old, _ = _settings(p)
    if float(new.get("ai_budget_usd", 0) or 0) > float(old.get("ai_budget_usd", 0) or 0):
        raise ValueError("ai_budget_usd can only be raised by hand in project.yaml, not from the web app")
    (p / "project.yaml").write_text(text, encoding="utf-8")
    return {"saved": True}


def save_comments(name: str, comments: dict) -> dict:
    """Per-shot comments on the cine montage plan ({shot number: text}); Claude reads them from comments.json."""
    work = project_dir(name) / "cine_montage"
    work.mkdir(exist_ok=True)
    clean = {str(k): str(v).strip() for k, v in comments.items() if str(v).strip()}
    (work / "comments.json").write_text(json.dumps(clean, indent=1, ensure_ascii=False), encoding="utf-8")
    return {"saved": len(clean)}


# ---------------------------------------------------------------- queue, music, insights

def queue() -> list[dict]:
    sys.path.insert(0, str(REPO))
    from autoedit import publish
    out = list(reversed(publish.entries()))
    for e in out:                                                # old entries can point at deleted exports
        e["video_exists"] = bool(e.get("video")) and Path(e["video"]).exists()
        e["cover_exists"] = bool(e.get("cover")) and Path(e["cover"]).exists()
    return out


def queue_choose(entry_id: str, platform: str, index: int) -> dict:
    sys.path.insert(0, str(REPO))
    from autoedit import publish
    e = publish.get(entry_id) or {}
    if platform not in e.get("options", {}):
        raise ValueError("unknown platform")
    chosen = {**e.get("chosen", {}), platform: int(index)}
    return publish.update(entry_id, chosen=chosen)


def music() -> list[dict]:
    folder = Path(roots()["music"])
    return [_file(f) for f in sorted(folder.glob("*")) if f.suffix.lower() in AUDIO_EXT] if folder.exists() else []


def report() -> str:
    sys.path.insert(0, str(REPO))
    from autoedit import performance
    return performance.report()


def ai_models() -> list[dict]:
    sys.path.insert(0, str(REPO))
    from autoedit import aigen
    local = [{"id": m, "note": n, "local": True} for m, n in (
        ("local-wan", "own GPU via ComfyUI, 1280x704, free"), ("local-wan-draft", "480p, ~2 min, for prompt tests"),
        ("local-wan-1080", "1080p, ~26 min"))]
    return local + [{"id": k, "note": v.get("note", ""), "local": False} for k, v in aigen.PRESETS.items()]


# ---------------------------------------------------------------- SSD library (page "SSD")

def _library():
    sys.path.insert(0, str(REPO))
    from autoedit import library
    return library


def library() -> dict:
    return _library().shoots(_cfg())


def library_shoot(rel: str) -> dict:
    return _library().shoot(_cfg(), rel)


def library_thumb(path: str) -> str:
    return _library().thumb(_cfg(), path)


def library_preview(path: str) -> str:
    return _library().preview(_cfg(), path)


def ask(name: str, text: str) -> dict:
    """A typed request -> one website action, via the local model (webapp/assistant.py)."""
    from . import assistant
    p = project(name)
    songs = list(dict.fromkeys([m["name"] for m in p["music"]] + [m["name"] for m in music()]))
    return assistant.ask(p, text, songs, _cfg())


CALLS = {"status": status, "roots": roots, "projects": projects, "project": project, "save_settings": save_settings,
         "feedback": feedback, "looks": looks, "ask": ask,
         "save_comments": save_comments, "queue": queue, "queue_choose": queue_choose, "music": music,
         "report": report, "ai_models": ai_models, "library": library, "library_shoot": library_shoot,
         "library_thumb": library_thumb, "library_preview": library_preview}
