"""Studio requests from the claude.ai Artifact. A button press there arrives as a comment in a Claude session on this
PC; the session runs `python -m webapp studio --thread <id> "<text>"`. The text has one fixed format:

    [studio] actie=<plan|grade|goedkeuren|preview|render|qa|stills> project="<name>"
             [look=.. strength=.. exposure=..] [plan=<edl_sha1> grade=<grade key> notitie="<own words>"]

It comes from a comment, so nothing in it becomes command text: every key and value is checked here and mapped to
exactly one allowed `engine ...` argv (host.ALLOWED + check_args). Each comment thread runs once (data/studio_handled.json).
`state(name)` is the projects/<slug> document the session writes into the Artifact's db; it holds no local paths
(asset URLs - stills, LUTs, render - are filled in by the session)."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shlex
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from . import query
from .host import check_args
from .validate import LOOKS, _name, _num, _text, grade_args

HANDLED = query.REPO / "data" / "studio_handled.json"
KEEP = 500
ACTIONS = ("plan", "grade", "goedkeuren", "preview", "render", "qa", "stills")
# keys allowed per action, besides actie and project (both required)
KEYS = {"grade": {"look", "strength", "exposure"}, "goedkeuren": {"plan", "grade", "notitie"}}
ALL_KEYS = {"actie", "project", "look", "strength", "exposure", "plan", "grade", "notitie"}
DEFAULT_GRADE = ("reference_film", 1.0, -1.75)                   # engine gradechoice.Grade()
LABELS = {"plan": "plan maken", "grade": "kleurlook instellen", "goedkeuren": "plan goedkeuren",
          "preview": "voorbeeld", "render": "renderen", "qa": "QA"}


PLAN_CHANGED = "het plan is veranderd sinds je het zag: bekijk het nieuwe plan"       # same texts as engine approve
GRADE_CHANGED = "de grade is veranderd sinds je hem zag: bekijk de grade opnieuw"


class NotYet(Exception):
    """The action exists in the request format but has no command yet."""


class HandledListError(Exception):
    """data/studio_handled.json can not be read: run nothing rather than risk running a request twice."""


def grade_key(look: str, strength: float, exposure: float) -> str:
    """Same as VIDEO_EDITING_SYSTEM/engine/gradechoice.py key() (tests/studio_test.py checks), without the engine import."""
    return hashlib.sha1(json.dumps([look, round(float(strength), 3), round(float(exposure), 3)]).encode()).hexdigest()[:12]


def slug(name: str) -> str:
    """Readable and unique: "Zomer Shoot" -> zomer-shoot-<6 hex of sha1(name)>, so "Zomer_Shoot" gets another slug."""
    base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return f"{base}-{hashlib.sha1(name.encode('utf-8')).hexdigest()[:6]}"


def _grade(work: Path) -> dict:
    """grade.json with the engine's defaults (gradechoice.load), plus its key."""
    g = dict(zip(("look", "strength", "exposure"), DEFAULT_GRADE))
    try:
        d = json.loads((work / "grade.json").read_text(encoding="utf-8"))
        g.update({k: d[k] for k in g if k in d})
    except (OSError, ValueError):
        pass
    g = {"look": str(g["look"]), "strength": float(g["strength"]), "exposure": float(g["exposure"])}
    return {**g, "key": grade_key(g["look"], g["strength"], g["exposure"])}


# ---------------------------------------------------------------- request -> argv

def parse(text: str) -> dict:
    text = (text or "").strip()
    if not text.startswith("[studio]"):
        raise ValueError("geen studio-verzoek: de tekst moet met [studio] beginnen")
    try:
        tokens = shlex.split(text[len("[studio]"):])
    except ValueError:
        raise ValueError("verzoek niet te lezen (aanhalingstekens kloppen niet)") from None
    req: dict = {}
    for tok in tokens:
        key, eq, val = tok.partition("=")
        if not eq:
            raise ValueError(f"onverwachte tekst in het verzoek: {tok[:40]!r}")
        if key not in ALL_KEYS:
            raise ValueError(f"onbekende sleutel: {key[:40]!r}")
        if key in req:
            raise ValueError(f"dubbele sleutel: {key}")
        req[key] = val
    act = req.get("actie")
    if act not in ACTIONS:
        raise ValueError(f"onbekende actie: {str(act)[:40]!r} (kies uit {', '.join(ACTIONS)})")
    extra = set(req) - {"actie", "project"} - KEYS.get(act, set())
    if extra:
        raise ValueError(f"onbekende sleutel voor {act}: {', '.join(sorted(extra))}")
    if "project" not in req:
        raise ValueError("project ontbreekt")
    try:
        req["project"] = _name(req["project"])
    except ValueError:
        raise ValueError("ongeldige projectnaam") from None
    if "look" in req and req["look"] not in LOOKS:
        raise ValueError(f"onbekende look {req['look'][:40]!r}: kies uit {', '.join(sorted(LOOKS))}")
    for key, lo, hi in (("strength", 0, 1), ("exposure", -3, 0.5)):
        if key in req:
            try:
                req[key] = _num(req[key], lo, hi)
            except ValueError:
                raise ValueError(f"{key} moet een getal tussen {lo} en {hi} zijn") from None
            if req[key] is None:
                del req[key]
    if "plan" in req and not re.fullmatch(r"[0-9a-f]{12}", req["plan"]):
        raise ValueError("plan moet de 12-teken code van het plan zijn")
    if "grade" in req and not re.fullmatch(r"[0-9a-f]{12}", req["grade"]):
        raise ValueError("grade moet de 12-teken code van de grade zijn")
    if "notitie" in req:
        try:
            req["notitie"] = _text(req["notitie"], 300)
        except ValueError:
            raise ValueError("notitie te lang of met regeleindes") from None
        if req["notitie"].startswith("-"):                       # never looks like an option to the engine's argparse
            raise ValueError("notitie mag niet met - beginnen")
    return req


def _edl_sha1(work: Path) -> str | None:
    f = work / "edl.json"
    return hashlib.sha1(f.read_bytes()).hexdigest()[:12] if f.exists() else None


def _project(name: str) -> Path:
    try:
        return query.project_dir(name)
    except ValueError:
        raise ValueError(f"geen project met de naam {name!r}") from None


def to_args(req: dict) -> list[str]:
    act = req["actie"]
    if act == "stills":                                          # no engine job: cli() runs studio_assets.export itself
        raise NotYet("stills: geen engine-opdracht")
    p = _project(req["project"])
    path = str(p)
    if act == "grade":
        if "look" not in req:
            raise ValueError("kies een look")
        a = ["engine", "grade", path, "--look", req["look"]]
        for key in ("strength", "exposure"):
            if key in req:
                a += [f"--{key}", req[key]]
    elif act == "goedkeuren":
        if not req.get("notitie"):
            raise ValueError("schrijf in een notitie wat je goedkeurt")
        work = p / "cine_montage"
        if req.get("plan") is None or req["plan"] != _edl_sha1(work):
            raise ValueError(PLAN_CHANGED)
        if req.get("grade") is None or req["grade"] != _grade(work)["key"]:
            raise ValueError(GRADE_CHANGED)
        # the engine checks both again at the moment it writes APPROVAL.json (no check-then-act gap)
        a = ["engine", "approve", path, "--by", "Timon", "--note", req["notitie"],
             "--expect-sha1", req["plan"], "--expect-grade", req["grade"]]
    elif act == "render":
        a = ["engine", "render", path] + grade_args({}, "render", {"cine": query.cine(p)})
    else:                                                        # plan, preview, qa: no options from the Artifact
        a = ["engine", act, path]
    check_args(a)
    return a


# ---------------------------------------------------------------- dedupe

def _handled_list() -> list[str]:
    if not HANDLED.exists():
        return []
    try:
        ids = json.loads(HANDLED.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise HandledListError("afgehandeld-lijst onleesbaar") from None
    if not isinstance(ids, list) or not all(isinstance(t, str) for t in ids):
        raise HandledListError("afgehandeld-lijst onleesbaar")
    return ids


def handled(thread_id: str) -> bool:
    return thread_id in _handled_list()


def mark(thread_id: str) -> None:
    ids = [t for t in _handled_list() if t != thread_id] + [thread_id]
    HANDLED.parent.mkdir(parents=True, exist_ok=True)
    tmp = HANDLED.with_name(HANDLED.name + f".{os.getpid()}.tmp")
    tmp.write_text(json.dumps(ids[-KEEP:]), encoding="utf-8")
    os.replace(tmp, HANDLED)                                     # never a half-written list


# ---------------------------------------------------------------- state for the Artifact db

def state(name: str) -> dict:
    p = _project(name)
    work = p / "cine_montage"
    c = query.cine(p)
    grade = _grade(work)
    plan = None
    if c["has_plan"]:
        plan = {"edl_sha1": _edl_sha1(work), "shots": len(c["shots"]), "duration": c.get("duration"),
                "title": c.get("title")}
    approval = None
    if c["approval"]:
        a = c["approval"]
        approved_key = a.get("grade_key", grade_key(*DEFAULT_GRADE))   # like the engine's render_allowed
        approval = {"status": a.get("status"), "by": a.get("by"), "at": a.get("at"), "note": a.get("note"),
                    "current": bool(a.get("current")),
                    "grade_current": approved_key == grade["key"]}
    return {"name": p.name, "plan": plan, "approval": approval, "grade": grade, "stills": [],
            "luts": {"conv": None, "looks": {}}, "render": None,
            "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}


# ---------------------------------------------------------------- CLI

def _wait(host, jid: str, poll: float) -> dict:
    while True:
        j = host.job(jid)
        if j["status"] not in ("queued", "running"):
            return j
        time.sleep(poll)


def redact(text: str) -> str:
    """Local paths in a log line -> their last part (the job message goes into the shared db, which has no paths)."""
    last = lambda m: re.split(r"[\\/]", m.group().rstrip("\\/"))[-1] or m.group()   # noqa: E731
    text = re.sub(r"(?:(?<!\w)[A-Za-z]:[\\/]|\\\\)[^\s\"'<>|]*", last, text)           # C:\..., D:/..., \\server\...
    return re.sub(r"(?<![\w.:/~-])/(?!/)[^\s\"'<>|]+", last, text)                  # /home/..., /tmp/... (not URLs)


def _out(d: dict) -> None:
    print(json.dumps(d, ensure_ascii=False))


def _state_or_none(name):
    try:
        return state(name)
    except Exception:
        return None


def cli(argv=None, host=None, poll: float = 1.0) -> int:
    ap = argparse.ArgumentParser(prog="webapp studio")
    ap.add_argument("--thread", required=True)
    ap.add_argument("text")
    args = ap.parse_args(argv)
    try:
        if handled(args.thread):
            _out({"ok": False, "message": "al afgehandeld"})
            return 1
        mark(args.thread)                                        # before running: a render never runs twice
    except HandledListError as e:
        _out({"ok": False, "message": str(e)})
        return 1
    act, name = None, None
    try:
        req = parse(args.text)
        act, name = req["actie"], req["project"]
        if act == "stills":
            return _stills(name)
        a = to_args(req)
    except Exception as e:                                       # refused or broken: still one JSON line
        msg = str(e) if isinstance(e, (ValueError, NotYet, PermissionError)) else f"fout: {type(e).__name__}: {e}"
        _out({"ok": False, "action": act, "message": redact(msg), "state": _state_or_none(name) if name else None})
        return 1
    if host is None:
        from .host import LocalHost
        host = LocalHost()
    try:
        j = _wait(host, host.run(a, f"Studio: {LABELS.get(act, act)}", name)["id"], poll)
    except Exception as e:                                       # still one JSON line for the session
        _out({"ok": False, "action": act, "slug": slug(name), "message": f"kon niet starten: {redact(str(e))}",
              "state": _state_or_none(name)})
        return 1
    ok = j["status"] == "done"
    log = redact("\n".join(j.get("log", [])[-8:]))
    msg = (f"{LABELS.get(act, act)}: klaar" if ok else f"{LABELS.get(act, act)}: mislukt ({j['status']})") + \
        (f"\n{log}" if log else "")
    out = {"ok": ok, "action": act, "slug": slug(name), "message": msg, "state": _state_or_none(name)}
    if ok:
        files = local_files(name, act)
        if files:
            out["local_files"] = files
    _out(out)
    return 0 if ok else 1


def local_files(name: str, act: str) -> dict:
    """Files on this PC the session uploads after a job (never written to the db: they are local paths)."""
    p = _project(name)
    work = p / "cine_montage"
    files = {}
    sheet = work / "storyboard" / "storyboard_sheet.jpg"
    if act in ("plan", "preview", "render") and sheet.exists():
        files["sheet"] = str(sheet)
    if act == "preview" and (work / "preview.mp4").exists():
        files["video"] = str(work / "preview.mp4")
    if act == "render":
        exports = sorted((p / "exports").glob("cine_montage_*.mp4"))
        if exports:
            files["video"] = str(exports[-1])
    return files


def projects() -> list[str]:
    """Projects with a cine montage folder: the ones the Studio shows."""
    root = Path(query.roots()["projects"])
    if not root.exists():
        return []
    return [p.name for p in sorted(root.iterdir(), key=lambda d: d.stat().st_mtime, reverse=True)
            if p.is_dir() and (p / "cine_montage").is_dir()]


def projects_cli(argv=None) -> int:
    argparse.ArgumentParser(prog="webapp studio-projects").parse_args(argv)
    _out([{"name": n, "slug": slug(n)} for n in projects()])
    return 0


def stills_dir(name: str) -> Path:
    return query.REPO / "data" / "studio_assets" / slug(name)


def _stills(name: str) -> int:
    """actie=stills: write stills + LUT stages into data/studio_assets/<slug>/ and report their repo-relative paths in
    "assets" (the PC session uploads them; state() stays path-free)."""
    try:
        from . import studio_assets                              # numpy/cv2/engine: PC only, never in the web image
        out_dir = stills_dir(name)
        res = studio_assets.export(_project(name), out_dir)
    except Exception as e:
        msg = str(e) if isinstance(e, ValueError) else f"fout: {type(e).__name__}: {e}"
        _out({"ok": False, "action": "stills", "slug": slug(name), "message": f"voorbeelden: mislukt\n{redact(msg)}",
              "state": _state_or_none(name)})
        return 1
    rel = lambda f: (out_dir / f).relative_to(query.REPO).as_posix() if f else None   # noqa: E731
    assets = {"stills": [{**s, "file": rel(s["file"])} for s in res["stills"]], "conv": rel(res["conv"]),
              "looks": {k: rel(v) for k, v in res["looks"].items()}}
    _out({"ok": True, "action": "stills", "slug": slug(name), "message": f"voorbeelden: klaar ({len(assets['stills'])} stills)",
          "assets": assets, "state": _state_or_none(name)})
    return 0


def state_cli(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="webapp studio-state")
    ap.add_argument("name")
    args = ap.parse_args(argv)
    try:
        _out(state(_name(args.name)))
    except ValueError as e:
        _out({"ok": False, "message": str(e)})
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(cli())
