"""Studio requests from the claude.ai Artifact. A button press there arrives as a comment in a Claude session on this
PC; the session runs `python -m webapp studio --thread <id> "<text>"`. The text has one fixed format:

    [studio] actie=<plan|grade|goedkeuren|preview|render|qa|stills> project="<name>"
             [look=.. strength=.. exposure=..] [plan=<edl_sha1>] [notitie="<own words>"]

It comes from a comment, so nothing in it becomes command text: every key and value is checked here and mapped to
exactly one allowed `engine ...` argv (host.ALLOWED + check_args). Each comment thread runs once (data/studio_handled.json).
`state(name)` is the projects/<slug> document the session writes into the Artifact's db; it holds no local paths
(asset URLs - stills, LUTs, render - are filled in by the session)."""
from __future__ import annotations

import argparse
import hashlib
import json
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
KEYS = {"grade": {"look", "strength", "exposure"}, "goedkeuren": {"plan", "notitie"}}
ALL_KEYS = {"actie", "project", "look", "strength", "exposure", "plan", "notitie"}
DEFAULT_GRADE = ("reference_film", 1.0, -1.75)                   # engine gradechoice.Grade()
LABELS = {"plan": "plan maken", "grade": "kleurlook instellen", "goedkeuren": "plan goedkeuren",
          "preview": "voorbeeld", "render": "renderen", "qa": "QA"}


class NotYet(Exception):
    """The action exists in the request format but has no command yet."""


def grade_key(look: str, strength: float, exposure: float) -> str:
    """Same as VIDEO_EDITING_SYSTEM/engine/gradechoice.py key() (tests/studio_test.py checks), without the engine import."""
    return hashlib.sha1(json.dumps([look, round(float(strength), 3), round(float(exposure), 3)]).encode()).hexdigest()[:12]


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "-", name.lower())


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
    if act == "stills":                                          # Task 5: stills/LUT export, not an engine command yet
        raise NotYet("stills: nog niet beschikbaar")
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
        if req.get("plan") is None or req["plan"] != _edl_sha1(p / "cine_montage"):
            raise ValueError("het plan is veranderd sinds je het zag: bekijk het nieuwe plan")
        a = ["engine", "approve", path, "--by", "Timon", "--note", req["notitie"]]
    elif act == "render":
        a = ["engine", "render", path] + grade_args({}, "render", {"cine": query.cine(p)})
    else:                                                        # plan, preview, qa: no options from the Artifact
        a = ["engine", act, path]
    check_args(a)
    return a


# ---------------------------------------------------------------- dedupe

def _handled_list() -> list[str]:
    try:
        return list(json.loads(HANDLED.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        return []


def handled(thread_id: str) -> bool:
    return thread_id in _handled_list()


def mark(thread_id: str) -> None:
    ids = [t for t in _handled_list() if t != thread_id] + [thread_id]
    HANDLED.parent.mkdir(parents=True, exist_ok=True)
    HANDLED.write_text(json.dumps(ids[-KEEP:]), encoding="utf-8")


# ---------------------------------------------------------------- state for the Artifact db

def state(name: str) -> dict:
    p = _project(name)
    work = p / "cine_montage"
    c = query.cine(p)
    g = c["grade"]
    grade = {"look": str(g["look"]), "strength": float(g["strength"]), "exposure": float(g["exposure"])}
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
                    "grade_current": approved_key == grade_key(grade["look"], grade["strength"], grade["exposure"])}
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
    return re.sub(r"(?:[A-Za-z]:[\\/]|\\\\)[^\s\"'<>|]*", lambda m: re.split(r"[\\/]", m.group().rstrip("\\/"))[-1],
                  text)


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
    if handled(args.thread):
        _out({"ok": False, "message": "al afgehandeld"})
        return 1
    mark(args.thread)                                            # before running: a render never runs twice
    act, name = None, None
    try:
        req = parse(args.text)
        act, name = req["actie"], req["project"]
        a = to_args(req)
    except (ValueError, NotYet, PermissionError) as e:
        _out({"ok": False, "action": act, "message": str(e), "state": _state_or_none(name) if name else None})
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
    _out({"ok": ok, "action": act, "slug": slug(name), "message": msg, "state": _state_or_none(name)})
    return 0 if ok else 1


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
