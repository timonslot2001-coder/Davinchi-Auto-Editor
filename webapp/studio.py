"""Studio requests from the claude.ai Artifact. A button press there arrives as a comment in a Claude session on this
PC; the session writes the comment text to data/studio_inbox/<thread>.txt (no shell) and runs
`python -m webapp studio --thread <id> --text-file data/studio_inbox/<thread>.txt`. The text has one fixed format:

    [studio] actie=<plan|grade|goedkeuren|preview|render|qa|stills> project="<name>"
             [look=.. strength=.. exposure=..] [plan=<edl_sha1> grade=<grade key> notitie="<own words>"]

It comes from a comment, so nothing in it becomes command text: every key and value is checked here and mapped to
exactly one allowed `engine ...` argv (host.ALLOWED + check_args). Each comment thread runs once (data/studio_handled.json).
The CLI answers at once: refusals and `stills` print their final line, every engine action starts a detached worker
(`python -m webapp studio-worker`, survives the session) and prints `status: "bezig"`; the worker runs one engine job at
a time (data/studio.lock) and writes data/studio_results/<thread>.json, which `python -m webapp studio-result` prints.
`state(name)` is the projects/<slug> document the session writes into the Artifact's db; it holds no local paths
(asset URLs - stills, LUTs, render - are filled in by the session)."""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from . import query
from .host import check_args
from .validate import LOOKS, _name, _num, _text, grade_args, mode_args

HANDLED = query.REPO / "data" / "studio_handled.json"
HANDLED_LOCK = query.REPO / "data" / "studio_handled.lock"     # around mark()'s read-modify-write
LOCK = query.REPO / "data" / "studio.lock"                     # held by a worker around its engine job
RESULTS = query.REPO / "data" / "studio_results"               # <thread>.job.json (what to run), <thread>.json (result)
INBOX = query.REPO / "data" / "studio_inbox"                   # --text-file must be in here
ASSETS = query.REPO / "data" / "studio_assets"                 # per project slug: stills, LUTs, 720p videos
MAX_UPLOAD = 20 * 1024 * 1024                                  # Artifact asset limit the session keeps to
THREAD = re.compile(r"[A-Za-z0-9_-]{1,100}")
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


class Busy(Exception):
    """file_lock(wait=False): someone else holds the lock."""


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
    elif act == "preview":                                       # the plan's --grade mode, like render
        a = ["engine", "preview", path] + mode_args(query.cine(p))
    else:                                                        # plan, qa: no options from the Artifact
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


@contextlib.contextmanager
def file_lock(path: Path, wait: bool = True):
    """An exclusive lock between processes on this PC (msvcrt on Windows, fcntl elsewhere). wait=False raises Busy."""
    path.parent.mkdir(parents=True, exist_ok=True)
    f = open(path, "a+b")
    locked = False
    try:
        if os.name == "nt":
            import msvcrt
            while True:
                f.seek(0)
                try:
                    msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
                    break
                except OSError:
                    if not wait:
                        raise Busy(path.name) from None
                    time.sleep(0.5)
        else:
            import fcntl
            try:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX | (0 if wait else fcntl.LOCK_NB))
            except BlockingIOError:
                raise Busy(path.name) from None
        locked = True
        yield
    finally:
        if locked:
            if os.name == "nt":
                import msvcrt
                f.seek(0)
                msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        f.close()


def _replace(tmp: Path, dst: Path, what: str) -> None:
    """os.replace with retries: never a half-written file (Windows: a scanner briefly holds the target open)."""
    for attempt in range(20):
        try:
            os.replace(tmp, dst)
            return
        except PermissionError:
            if attempt == 19:
                tmp.unlink(missing_ok=True)
                raise HandledListError(f"{what} is bezet: probeer het zo opnieuw") from None
            time.sleep(0.05 * (attempt + 1))
        except OSError:
            tmp.unlink(missing_ok=True)
            raise HandledListError(f"{what} niet te schrijven") from None


def handled(thread_id: str) -> bool:
    return thread_id in _handled_list()


def _mark(thread_id: str) -> None:
    ids = [t for t in _handled_list() if t != thread_id] + [thread_id]
    HANDLED.parent.mkdir(parents=True, exist_ok=True)
    tmp = HANDLED.with_name(HANDLED.name + f".{os.getpid()}.tmp")
    tmp.write_text(json.dumps(ids[-KEEP:]), encoding="utf-8")
    _replace(tmp, HANDLED, "afgehandeld-lijst")


def mark(thread_id: str) -> None:
    with file_lock(HANDLED_LOCK):
        _mark(thread_id)


def claim(thread_id: str) -> bool:
    """Mark the thread as handled; False if it already was. One lock around check and write: two sessions (or two
    quick calls) can never both run the same thread."""
    with file_lock(HANDLED_LOCK):
        if handled(thread_id):
            return False
        _mark(thread_id)
        return True


# ---------------------------------------------------------------- state for the Artifact db

def _made_with(info: Path, made: Path) -> dict | None:
    """{key, look} of the grade the engine made `made` with (its json next to it), or None if unknown."""
    if not made.exists():
        return None
    try:
        d = json.loads(info.read_text(encoding="utf-8"))
        key, look = d["key"], d["look"]
    except (OSError, ValueError, KeyError, TypeError):
        return None
    if not (isinstance(key, str) and re.fullmatch(r"[0-9a-f]{12}", key) and look in LOOKS):
        return None
    return {"key": key, "look": look}


def state(name: str) -> dict:
    p = _project(name)
    work = p / "cine_montage"
    c = query.cine(p)
    grade = {**_grade(work), "chosen": (work / "grade.json").exists()}
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
    made_with = {"sheet": _made_with(work / "storyboard" / "made_with.json", work / "storyboard" / "storyboard_sheet.jpg"),
                 "preview": _made_with(work / "preview_made_with.json", work / "preview.mp4")}
    return {"name": p.name, "plan": plan, "approval": approval, "grade": grade, "made_with": made_with, "stills": [],
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
    # C:\..., \\server\..., D:/...: folders may hold spaces (a folder ends at the path's own separator); the last part
    # (the file name) ends at a space
    text = re.sub(r"(?:(?<!\w)[A-Za-z]:\\|\\\\)(?:[^\\/\r\n\"<>|:*?]+\\)*[^\s\\/\"'<>|]*", last, text)
    text = re.sub(r"(?<!\w)[A-Za-z]:/(?:[^\\/\r\n\"<>|:*?]+/)*[^\s\\/\"'<>|]*", last, text)
    return re.sub(r"(?<![\w.:/~-])/(?!/)[^\s\"'<>|]+", last, text)                  # /home/..., /tmp/... (not URLs)


def _out(d: dict) -> None:
    print(json.dumps(d, ensure_ascii=False))


def _state_or_none(name):
    try:
        return state(name)
    except Exception:
        return None


def _read_text_file(arg: str) -> str:
    """The comment text from a file inside data/studio_inbox/ (UTF-8, one trailing newline stripped)."""
    f = Path(arg)
    if not f.is_absolute():
        f = query.REPO / f
    f = f.resolve()
    if not f.is_relative_to(INBOX.resolve()) or not f.is_file():
        raise ValueError("tekstbestand moet in data/studio_inbox/ staan")
    try:
        text = f.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        raise ValueError("tekstbestand niet te lezen") from None
    return text[:-1] if text.endswith("\n") else text          # read_text already turned \r\n into \n


def _thread_ok(thread: str) -> bool:
    if THREAD.fullmatch(thread):
        return True
    _out({"ok": False, "message": "ongeldige thread-id"})
    return False


def _write_json(path: Path, d: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + f".{os.getpid()}.tmp")
    tmp.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    _replace(tmp, path, path.name)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def cli(argv=None, spawn=None) -> int:
    """Validate, mark handled, start the work detached and answer at once (one JSON line). `spawn(thread)` starts the
    worker; tests pass their own."""
    ap = argparse.ArgumentParser(prog="webapp studio")
    ap.add_argument("--thread", required=True)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--text-file", help="file in data/studio_inbox/ with the comment text (the session's route)")
    src.add_argument("text", nargs="?", help="the comment text itself (tests, by hand)")
    args = ap.parse_args(argv)
    if not _thread_ok(args.thread):
        return 1
    if args.text_file is not None:
        try:
            args.text = _read_text_file(args.text_file)
        except ValueError as e:                                  # nothing marked: the session can fix it and retry
            _out({"ok": False, "message": str(e)})
            return 1
    try:
        if not claim(args.thread):                               # before running: a render never runs twice
            _out({"ok": False, "message": "al afgehandeld"})
            return 1
    except (HandledListError, OSError) as e:
        _out({"ok": False, "message": str(e) if isinstance(e, HandledListError) else "afgehandeld-lijst niet te schrijven"})
        return 1
    act, name = None, None
    try:
        req = parse(args.text)
        act, name = req["actie"], req["project"]
        if act == "stills":                                      # quick and no engine job: answered right here
            return _stills(name)
        a = to_args(req)
    except Exception as e:                                       # refused or broken: still one JSON line
        msg = str(e) if isinstance(e, (ValueError, NotYet, PermissionError)) else f"fout: {type(e).__name__}: {e}"
        _out({"ok": False, "action": act, "message": redact(msg), "state": _state_or_none(name) if name else None})
        return 1
    head = {"action": act, "slug": slug(name)}
    try:
        _write_json(RESULTS / f"{args.thread}.job.json", {"thread": args.thread, "action": act, "project": name,
                                                          "args": a, "started_at": _now()})
        _write_json(RESULTS / f"{args.thread}.json", {"ok": True, **head, "status": "bezig", "message": "gestart",
                                                      "started_at": _now()})
        (spawn or _spawn_detached)(args.thread)
    except Exception as e:
        out = {"ok": False, **head, "status": "fout", "message": f"kon niet starten: {redact(str(e))}",
               "state": _state_or_none(name)}
        with contextlib.suppress(Exception):
            _write_json(RESULTS / f"{args.thread}.json", out)
        _out(out)
        return 1
    _out({"ok": True, **head, "status": "bezig", "message": "gestart"})
    return 0


def _spawn_detached(thread: str) -> None:
    """`python -m webapp studio-worker --thread <id>` as its own process: it keeps running when the session's shell
    call (or the whole session) ends."""
    RESULTS.mkdir(parents=True, exist_ok=True)
    cmd = [sys.executable, "-m", "webapp", "studio-worker", "--thread", thread]
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUNBUFFERED": "1"}
    with open(RESULTS / f"{thread}.log", "ab") as log:
        kw = dict(cwd=str(query.REPO), env=env, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                  close_fds=True)
        if os.name == "nt":
            flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
            try:                                                 # also leave the session's job object if allowed
                subprocess.Popen(cmd, creationflags=flags | subprocess.CREATE_BREAKAWAY_FROM_JOB, **kw)
            except OSError:
                subprocess.Popen(cmd, creationflags=flags, **kw)
        else:
            subprocess.Popen(cmd, start_new_session=True, **kw)


def work(thread: str, host=None, poll: float = 1.0) -> None:
    """The detached worker: run the job file's engine argv (one job at a time on this PC), then write the final
    result line (the same shape the CLI used to print) into data/studio_results/<thread>.json. Never raises."""
    res_path = RESULTS / f"{thread}.json"
    act, name = None, None
    try:
        job = json.loads((RESULTS / f"{thread}.job.json").read_text(encoding="utf-8"))
        act, name, a = job["action"], job["project"], job["args"]
        check_args(a)
        head = {"action": act, "slug": slug(name)}
        try:
            with file_lock(LOCK, wait=False):
                out = _run_job(host, a, act, name, poll)
        except Busy:
            _write_json(res_path, {"ok": True, **head, "status": "bezig", "started_at": job.get("started_at"),
                                   "message": "wacht tot de vorige taak op de PC klaar is"})
            with file_lock(LOCK):
                out = _run_job(host, a, act, name, poll)
    except Exception as e:                                       # never stuck on "bezig"
        out = {"ok": False, "action": act, "slug": slug(name) if name else None,
               "message": f"{LABELS.get(act, act or 'taak')}: mislukt\n{redact(f'{type(e).__name__}: {e}')}",
               "state": _state_or_none(name) if name else None}
    out["status"] = "klaar" if out["ok"] else "fout"
    out["finished_at"] = _now()
    _write_json(res_path, out)


def _run_job(host, a: list[str], act: str, name: str, poll: float) -> dict:
    if host is None:
        from .host import LocalHost
        host = LocalHost()
    try:
        j = _wait(host, host.run(a, f"Studio: {LABELS.get(act, act)}", name)["id"], poll)
    except Exception as e:
        return {"ok": False, "action": act, "slug": slug(name), "message": f"kon niet starten: {redact(str(e))}",
                "state": _state_or_none(name)}
    ok = j["status"] == "done"
    log = redact("\n".join(j.get("log", [])[-8:]))
    msg = (f"{LABELS.get(act, act)}: klaar" if ok else f"{LABELS.get(act, act)}: mislukt ({j['status']})") + \
        (f"\n{log}" if log else "")
    out = {"ok": ok, "action": act, "slug": slug(name), "message": msg, "state": _state_or_none(name)}
    if ok:
        files = local_files(name, act)
        if "video" in files:                                     # the session uploads only the 720p copy
            video, note = _video_720(name, act, Path(files.pop("video")))
            if video:
                files["video"] = video
            out["message"] += f"\n{note}" if note else ""
        if files:
            out["local_files"] = files
    return out


def worker_cli(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="webapp studio-worker")
    ap.add_argument("--thread", required=True)
    args = ap.parse_args(argv)
    if not THREAD.fullmatch(args.thread):
        return 1
    work(args.thread)
    return 0


def result_cli(argv=None) -> int:
    """The result of a started request: the final line, or {ok: true, status: "bezig"} while it runs."""
    ap = argparse.ArgumentParser(prog="webapp studio-result")
    ap.add_argument("--thread", required=True)
    args = ap.parse_args(argv)
    if not _thread_ok(args.thread):
        return 1
    try:
        d = json.loads((RESULTS / f"{args.thread}.json").read_text(encoding="utf-8"))
    except FileNotFoundError:
        _out({"ok": False, "message": "onbekende taak: niet gestart"})
        return 1
    except (OSError, ValueError):                                # being replaced right now: ask again
        d = {"ok": True, "status": "bezig", "message": "even opnieuw vragen"}
    _out(d)
    return 0 if d.get("ok") else 1


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


def transcode_720(src: Path, dst: Path) -> None:
    """A small H.264 copy for the Artifact (imageio_ffmpeg like the engine's media.FF; PC only, imported here)."""
    import subprocess

    import imageio_ffmpeg
    dst.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-v", "error", "-i", str(src), "-vf", "scale=-2:720",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "veryfast", "-crf", "28",
                    "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(dst)], check=True, capture_output=True, timeout=1800)


def _video_720(name: str, act: str, src: Path) -> tuple[str | None, str]:
    """data/studio_assets/<slug>/<preview|render>_720.mp4 if it fits the upload limit, else (None, why not)."""
    dst = ASSETS / slug(name) / f"{act}_720.mp4"
    try:
        transcode_720(src, dst)
    except Exception as e:
        dst.unlink(missing_ok=True)
        return None, f"geen voorbeeldvideo: {redact(str(e))[:200]}"
    if not dst.exists() or dst.stat().st_size > MAX_UPLOAD:
        dst.unlink(missing_ok=True)
        return None, "geen voorbeeldvideo: 720p-versie te groot voor de Studio (max 20 MB)"
    return str(dst), ""


def projects() -> list[str]:
    """Projects with a cine montage folder: the ones the Studio shows."""
    root = Path(query.roots()["projects"])
    if not root.exists():
        return []
    return [p.name for p in sorted(root.iterdir(), key=lambda d: d.stat().st_mtime, reverse=True)
            if p.is_dir() and (p / "cine_montage").is_dir()]


def projects_cli(argv=None) -> int:
    """Every Studio project with its state document: [{name, slug, state}]. Folder names the validator refuses are
    skipped, so no odd name ever reaches the session's commands or the db."""
    argparse.ArgumentParser(prog="webapp studio-projects").parse_args(argv)
    out = []
    for n in projects():
        try:
            out.append({"name": n, "slug": slug(n), "state": state(_name(n))})
        except Exception:
            continue
    _out(out)
    return 0


def stills_dir(name: str) -> Path:
    return ASSETS / slug(name)


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
