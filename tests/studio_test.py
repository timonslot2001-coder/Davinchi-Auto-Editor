"""Studio requests from the Artifact: parse, validate, map to one engine argv, dedupe, state.
usage: python tests/studio_test.py"""
import hashlib
import json
import os
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from webapp import query, studio   # noqa: E402

tmp = Path(tempfile.mkdtemp())
(tmp / "projects").mkdir()
query.roots = lambda: {"projects": str(tmp / "projects"), "music": str(tmp / "music"), "output": str(tmp / "out"),
                       "data": str(tmp / "data")}
studio.HANDLED = tmp / "data" / "studio_handled.json"
studio.RESULTS = tmp / "data" / "studio_results"
studio.LOCK = tmp / "data" / "studio.lock"

proj = tmp / "projects" / "Zomer Shoot"
work = proj / "cine_montage"
work.mkdir(parents=True)
edl = {"duration": 18.0, "music": None, "notes": [], "overlays": [{"component": "title_slam", "params": {"text": "ZOMER"}}],
       "events": [{"id": f"E0{i}", "out_in": i, "out_out": i + 1, "source": f"C:/clips/C{i}.mp4", "src_in": 0,
                   "transition_in": "cut", "treatment": "none", "params": {}} for i in range(3)]}
(work / "edl.json").write_text(json.dumps(edl))
sha = hashlib.sha1((work / "edl.json").read_bytes()).hexdigest()[:12]
P = str(proj.resolve())
G0 = hashlib.sha1(json.dumps(["reference_film", 1.0, -1.75]).encode()).hexdigest()[:12]   # default grade key


def raises(fn, *a, contains=""):
    try:
        fn(*a)
    except ValueError as e:
        assert contains in str(e), (contains, str(e))
        return str(e)
    raise AssertionError(f"no ValueError for {a}")


# ---- parse
note = "mooi zo, a=b werkt & meer"
r = studio.parse(f'[studio] actie=goedkeuren project="Zomer Shoot" plan={sha} grade={G0} notitie="{note}"')
assert r == {"actie": "goedkeuren", "project": "Zomer Shoot", "plan": sha, "grade": G0, "notitie": note}, r
raises(studio.parse, f'[studio] actie=goedkeuren project="Zomer Shoot" plan={sha} grade=moody notitie=ok')
raises(studio.parse, f'[studio] actie=render project="Zomer Shoot" grade={G0}')       # grade key only for goedkeuren
assert studio.parse('  [studio] actie=render project="Zomer Shoot"') == {"actie": "render", "project": "Zomer Shoot"}
raises(studio.parse, 'actie=render project="Zomer Shoot"', contains="[studio]")
raises(studio.parse, '[studio] actie=wis project="Zomer Shoot"', contains="onbekende actie")
raises(studio.parse, '[studio] actie=render project="Zomer Shoot" kleur=rood', contains="onbekende sleutel")
raises(studio.parse, '[studio] actie=render actie=qa project="Zomer Shoot"', contains="dubbel")
raises(studio.parse, '[studio] actie=render project="Zomer Shoot" ; del *')
raises(studio.parse, '[studio] actie=render project="Zomer Shoot"; rm -rf /')
raises(studio.parse, '[studio] actie=render project="Zomer Shoot')                   # unbalanced quote
raises(studio.parse, '[studio] actie=render')                                          # project missing
raises(studio.parse, '[studio] actie=grade project="Zomer Shoot" look=odyssey', contains="look")
raises(studio.parse, '[studio] actie=grade project="Zomer Shoot" look=moody strength=2')
raises(studio.parse, '[studio] actie=grade project="Zomer Shoot" look=moody exposure=nan')
raises(studio.parse, '[studio] actie=render project="Zomer Shoot" look=moody')        # key not for this action
raises(studio.parse, '[studio] actie=render project="../etc"')
raises(studio.parse, '[studio] actie=goedkeuren project="Zomer Shoot" plan=$(whoami) notitie=ok')
raises(studio.parse, f'[studio] actie=goedkeuren project="Zomer Shoot" plan={sha} notitie="--by=Evil"')
raises(studio.parse, "[studio] actie=goedkeuren project=x notitie=\"a\nb\" plan=" + sha)

# ---- to_args
argv = lambda text: studio.to_args(studio.parse(text))   # noqa: E731
assert argv('[studio] actie=render project="Zomer Shoot"') == ["engine", "render", P]
assert argv('[studio] actie=plan project="Zomer Shoot"') == ["engine", "plan", P]
assert argv('[studio] actie=preview project="Zomer Shoot"') == ["engine", "preview", P]
assert argv('[studio] actie=qa project="Zomer Shoot"') == ["engine", "qa", P]
assert argv('[studio] actie=grade project="Zomer Shoot" look=moody strength=0.8 exposure=-1.5') == \
    ["engine", "grade", P, "--look", "moody", "--strength", "0.8", "--exposure", "-1.5"]
assert argv('[studio] actie=grade project="Zomer Shoot" look=vintage') == ["engine", "grade", P, "--look", "vintage"]
raises(argv, '[studio] actie=grade project="Zomer Shoot"', contains="look")
raises(argv, f'[studio] actie=goedkeuren project="Zomer Shoot" plan={sha} grade={G0}', contains="notitie")
raises(argv, f'[studio] actie=goedkeuren project="Zomer Shoot" grade={G0} notitie="ja"', contains="plan is veranderd")
raises(argv, f'[studio] actie=goedkeuren project="Zomer Shoot" plan=0123456789ab grade={G0} notitie="ja"',
       contains="het plan is veranderd sinds je het zag: bekijk het nieuwe plan")
raises(argv, f'[studio] actie=goedkeuren project="Zomer Shoot" plan={sha} notitie="ja"',
       contains="de grade is veranderd sinds je hem zag: bekijk de grade opnieuw")
raises(argv, f'[studio] actie=goedkeuren project="Zomer Shoot" plan={sha} grade=0123456789ab notitie="ja"',
       contains="de grade is veranderd sinds je hem zag: bekijk de grade opnieuw")
assert argv(f'[studio] actie=goedkeuren project="Zomer Shoot" plan={sha} grade={G0} notitie="{note}"') == \
    ["engine", "approve", P, "--by", "Timon", "--note", note, "--expect-sha1", sha, "--expect-grade", G0]
raises(argv, '[studio] actie=render project="Bestaat Niet"', contains="project")
try:
    argv('[studio] actie=stills project="Zomer Shoot"')
    raise AssertionError("stills is no engine job")
except studio.NotYet as e:
    assert "geen engine-opdracht" in str(e)
# render sends the approved --grade mode (shared with the web app)
(work / "APPROVAL.json").write_text(json.dumps({"status": "approved", "edl_sha1": sha, "grade_mode": "slog3"}))
assert argv('[studio] actie=render project="Zomer Shoot"') == ["engine", "render", P, "--grade", "slog3"]

# ---- grade key equals the engine's
sys.path.insert(0, str(REPO / "VIDEO_EDITING_SYSTEM"))
from engine import gradechoice   # noqa: E402
for g in [("reference_film", 1.0, -1.75), ("moody", 0.8, -1.5), ("vintage", 0.3333333, 0.5), ("daylight", 0, -3)]:
    assert studio.grade_key(*g) == gradechoice.key(gradechoice.Grade(g[0], float(g[1]), float(g[2]))), g

# ---- handled / mark
assert not studio.handled("t-1")
studio.mark("t-1")
studio.mark("t-1")
assert studio.handled("t-1") and not studio.handled("t-2")
assert json.loads(studio.HANDLED.read_text()).count("t-1") == 1
for i in range(600):
    studio.mark(f"x{i}")
kept = json.loads(studio.HANDLED.read_text())
assert len(kept) == 500 and studio.handled("x599") and not studio.handled("t-1"), len(kept)
assert not list(studio.HANDLED.parent.glob("*.tmp"))                    # atomic write leaves no temp file
good = studio.HANDLED.read_text()
studio.HANDLED.write_text("{kapot")
for fn in (studio.handled, studio.mark):
    try:
        fn("x1")
        raise AssertionError("corrupt handled list accepted")
    except studio.HandledListError:
        pass
studio.HANDLED.write_text(good)

# ---- state
gkey = studio.grade_key("reference_film", 1.0, -1.75)
(work / "APPROVAL.json").write_text(json.dumps({"status": "approved", "edl_sha1": sha, "grade_key": gkey,
                                                "grade_mode": "auto", "by": "Timon", "note": "top", "at": "2026-11-01T10:00:00"}))
s = studio.state("Zomer Shoot")
assert s["name"] == "Zomer Shoot"
assert s["plan"] == {"edl_sha1": sha, "shots": 3, "duration": 18.0, "title": "ZOMER"}, s["plan"]
assert s["approval"] == {"status": "approved", "by": "Timon", "at": "2026-11-01T10:00:00", "note": "top",
                         "current": True, "grade_current": True}, s["approval"]
assert s["grade"] == {"look": "reference_film", "strength": 1.0, "exposure": -1.75, "key": G0, "chosen": False}
assert s["made_with"] == {"sheet": None, "preview": None}, s["made_with"]
assert s["stills"] == [] and s["luts"] == {"conv": None, "looks": {}} and s["render"] is None and s["updated_at"]
(work / "grade.json").write_text(json.dumps({"look": "moody", "strength": 0.8, "exposure": -1.5}))
s = studio.state("Zomer Shoot")
assert s["approval"]["grade_current"] is False and s["approval"]["current"] is True
G1 = studio.grade_key("moody", 0.8, -1.5)
assert s["grade"] == {"look": "moody", "strength": 0.8, "exposure": -1.5, "key": G1, "chosen": True} and G1 != G0
# the page sends what state() shows; a grade change after that is refused
assert argv(f'[studio] actie=goedkeuren project="Zomer Shoot" plan={s["plan"]["edl_sha1"]} grade={s["grade"]["key"]} '
            'notitie=ja')[-4:] == ["--expect-sha1", sha, "--expect-grade", G1]
raises(argv, f'[studio] actie=goedkeuren project="Zomer Shoot" plan={sha} grade={G0} notitie=ja', contains="grade is veranderd")
dump = json.dumps(s)
assert "\\\\" not in dump and "\\" not in dump and ":/" not in dump, dump
h6 = lambda n: hashlib.sha1(n.encode()).hexdigest()[:6]   # noqa: E731
assert studio.slug("Zomer Shoot") == "zomer-shoot-" + h6("Zomer Shoot")
assert studio.slug("Café (2)") == "caf-2-" + h6("Café (2)")
assert studio.slug("Zomer_Shoot") != studio.slug("Zomer Shoot") and studio.slug("Zomer_Shoot").startswith("zomer-shoot-")
empty = tmp / "projects" / "Leeg"
empty.mkdir()
s = studio.state("Leeg")
assert s["plan"] is None and s["approval"] is None


# ---- CLI (fake host: the job goes queued -> running -> done)
class FakeHost:
    def __init__(self, status="done"):
        self.runs, self.polls, self.final = [], 0, status

    def run(self, args, label="", project=None):
        self.runs.append(args)
        return {"id": "j1", "status": "queued"}

    def job(self, jid, since=0):
        self.polls += 1
        st = "running" if self.polls < 2 else self.final
        return {"id": jid, "status": st, "log": [f"line {i}" for i in range(20)] +
                ["storyboard: C:\\Users\\Timon\\Videos\\Zomer\\sheet.jpg", "klaar met grade"]}


def run(fn, *a, **kw):
    """Call a CLI function; it must print exactly one JSON line. Returns (exit code, that line)."""
    import contextlib
    import io
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = fn(*a, **kw)
    lines = buf.getvalue().strip().splitlines()
    assert len(lines) == 1, lines
    return code, json.loads(lines[0])


def cli(args, host):
    """Start a request with the worker run inline (instead of detached), then read its result like the session does."""
    def inline(thread):
        import contextlib
        import io
        with contextlib.redirect_stdout(io.StringIO()) as quiet:
            studio.work(thread, host=host, poll=0)
        assert quiet.getvalue() == "", quiet.getvalue()                  # the worker writes a file, prints nothing
    code, out = run(studio.cli, args, spawn=inline, host=host, poll=0)   # host: the SSD actions run inline
    if out.get("status") != "bezig":
        return code, out
    assert code == 0 and out["ok"] is True and out["message"] == "gestart" and set(out) == \
        {"ok", "action", "slug", "status", "message"}, out
    return run(studio.result_cli, ["--thread", args[args.index("--thread") + 1]])


h = FakeHost()
code, out = cli(["--thread", "c-100", '[studio] actie=grade project="Zomer Shoot" look=daylight'], h)
assert code == 0 and out["ok"] is True and out["action"] == "grade", out
assert h.runs == [["engine", "grade", P, "--look", "daylight"]] and h.polls >= 2
assert "klaar met grade" in out["message"] and out["state"]["name"] == "Zomer Shoot"
assert set(out) >= {"ok", "action", "message", "state"} and out["slug"] == studio.slug("Zomer Shoot")
assert "sheet.jpg" in out["message"] and "\\" not in out["message"] and ":/" not in out["message"], out["message"]
assert studio.redact("lut D:/AutoEdit/luts/moody.cube ok") == "lut moody.cube ok"
assert studio.redact(r"in \\nas\share\x.mp4") == "in x.mp4"
assert studio.redact("sheet /home/timon/AutoEdit/p/sheet.jpg and /tmp/x.log") == "sheet sheet.jpg and x.log"
assert studio.redact('lut="/Users/t/luts/a.cube"') == 'lut="a.cube"'
assert studio.redact("zie https://claude.ai/x/y en 50/50, and/or") == "zie https://claude.ai/x/y en 50/50, and/or"
# whole Windows paths with spaces in folder names: only the base name stays
assert studio.redact(r"storyboard: C:\Users\Timon\Videos\AutoEdit Projects\Zomer Shoot\cine_montage\sheet.jpg klaar") == \
    "storyboard: sheet.jpg klaar"
assert studio.redact("export: D:/AutoEdit Projects/Beef Tartaar v2/exports/cine_montage_1.mp4") == "export: cine_montage_1.mp4"
assert studio.redact(r"in \\nas\Mijn Video's\x.mp4 ok") == "in x.mp4 ok"
assert studio.redact(r"map C:\AutoEdit Projects\Zomer Shoot") == "map Zomer Shoot"   # spaces in the last part stay
for t in (r"C:\Users\Timon\AutoEdit Projects\a b\c.mp4", "D:/x y/z.cube"):
    assert "Users" not in studio.redact(t) and "AutoEdit" not in studio.redact(t) and "x y" not in studio.redact(t), t
code, out = cli(["--thread", "c-100", '[studio] actie=grade project="Zomer Shoot" look=daylight'], h)
assert out == {"ok": False, "message": "al afgehandeld"} and len(h.runs) == 1, out
code, out = cli(["--thread", "c-101", '[studio] actie=render project="Zomer Shoot" ; del *'], h)
assert code == 1 and out["ok"] is False and len(h.runs) == 1 and studio.handled("c-101"), out
code, out = cli(["--thread", "c-102", '[studio] actie=stills project="Zomer Shoot"'], h)
assert out["ok"] is False and out["action"] == "stills" and "geen beeld" in out["message"] and len(h.runs) == 1, out
# stills run studio_assets.export directly (no engine job); assets paths are repo-relative, state stays path-free
from webapp import studio_assets   # noqa: E402
studio_assets.export = lambda p, o: {"stills": [{"file": "still_0.png", "is_log": True, "label": "A.mp4 0:01.0"}],
                                     "conv": "conv.cube", "looks": {"moody": "look_moody.cube"},
                                     "previews": {"moody": "preview_moody.jpg"}}
code, out = cli(["--thread", "c-102b", '[studio] actie=stills project="Zomer Shoot"'], h)
d = f"data/studio_assets/{studio.slug('Zomer Shoot')}"
assert code == 0 and out["ok"] and len(h.runs) == 1, out
assert out["assets"] == {"stills": [{"file": f"{d}/still_0.png", "is_log": True, "label": "A.mp4 0:01.0"}],
                         "conv": f"{d}/conv.cube", "looks": {"moody": f"{d}/look_moody.cube"},
                         "previews": {"moody": f"{d}/preview_moody.jpg"}}, out["assets"]
assert "assets" not in out["state"] and d not in json.dumps(out["state"])
code, out = cli(["--thread", "c-103", '[studio] actie=render project="Zomer Shoot"'], FakeHost("failed"))
assert code == 1 and out["ok"] is False and out["action"] == "render", out


class BrokenHost(FakeHost):
    def run(self, args, label="", project=None):
        raise RuntimeError("worker weg")


code, out = cli(["--thread", "c-104", '[studio] actie=qa project="Zomer Shoot"'], BrokenHost())
assert code == 1 and out["ok"] is False and "worker weg" in out["message"], out


class WeirdHost(FakeHost):
    def job(self, jid, since=0):
        raise KeyError(jid)


code, out = cli(["--thread", "c-105", '[studio] actie=qa project="Zomer Shoot"'], WeirdHost())
assert code == 1 and out["ok"] is False, out
studio.HANDLED.write_text("[kapot")
code, out = cli(["--thread", "c-106", '[studio] actie=qa project="Zomer Shoot"'], h)
assert out == {"ok": False, "message": "afgehandeld-lijst onleesbaar"} and len(h.runs) == 1, out
orig = studio.to_args
studio.to_args = lambda req: 1 / 0
studio.HANDLED.write_text("[]")
code, out = cli(["--thread", "c-107", '[studio] actie=qa project="Zomer Shoot"'], h)
assert code == 1 and out["ok"] is False and len(h.runs) == 1, out
studio.to_args = orig

# ---- project list and files to upload after a job
(tmp / "projects" / "Geen Cine").mkdir()
assert studio.projects() == ["Zomer Shoot"], studio.projects()
assert studio.local_files("Zomer Shoot", "render") == {}
(work / "storyboard").mkdir()
(work / "storyboard" / "storyboard_sheet.jpg").write_bytes(b"x")
(work / "preview.mp4").write_bytes(b"x")
(proj / "exports").mkdir()
for stamp in ("20261101_1000", "20261101_1200"):
    (proj / "exports" / f"cine_montage_{stamp}.mp4").write_bytes(b"x")
same = lambda a, b: Path(a).resolve() == Path(b).resolve()   # noqa: E731  (Windows short vs long temp names)
lf = studio.local_files("Zomer Shoot", "plan")
assert list(lf) == ["sheet"] and same(lf["sheet"], work / "storyboard" / "storyboard_sheet.jpg"), lf
assert same(studio.local_files("Zomer Shoot", "preview")["video"], work / "preview.mp4")
assert studio.local_files("Zomer Shoot", "render")["video"].endswith("cine_montage_20261101_1200.mp4")
assert studio.local_files("Zomer Shoot", "qa") == {}

# ---- --text-file: the session writes the comment to data/studio_inbox/<thread>.txt (no shell) and passes only its path
studio.INBOX = tmp / "data" / "studio_inbox"
studio.INBOX.mkdir(parents=True, exist_ok=True)
(work / "APPROVAL.json").unlink()
(work / "grade.json").unlink()
tricky = 'zeg "hoi" \'x\' \'@ $HOME $(whoami) `whoami` %PATH% & | ; met  spaties'
quote = lambda v: '"' + v.replace("\\", "\\\\").replace('"', '\\"') + '"'   # noqa: E731  (studio.html quote())
fb = studio.INBOX / "f-1.txt"
fb.write_text(f'[studio] actie=goedkeuren project="Zomer Shoot" plan={sha} grade={G0} notitie={quote(tricky)}\n',
              encoding="utf-8")
assert studio.parse(fb.read_text(encoding="utf-8"))["notitie"] == tricky
h = FakeHost()
code, out = cli(["--thread", "f-1", "--text-file", str(fb)], h)
assert code == 0 and out["ok"] and h.runs[-1][:2] == ["engine", "approve"], out
assert h.runs[-1][h.runs[-1].index("--note") + 1] == tricky, h.runs[-1]
fb2 = studio.INBOX / "f-2.txt"
fb2.write_text(f'[studio] actie=goedkeuren project="Zomer Shoot" plan={sha} grade={G0} notitie="a\nb"', encoding="utf-8")
code, out = cli(["--thread", "f-2", "--text-file", str(fb2)], h)
assert code == 1 and out["ok"] is False and "regeleindes" in out["message"] and len(h.runs) == 1, out
fb3 = studio.INBOX / "f-3.txt"
fb3.write_bytes(b'[studio] actie=qa project="Zomer Shoot"\r\n')                # CRLF from Windows: one newline stripped
code, out = cli(["--thread", "f-3", "--text-file", str(fb3)], h)
assert code == 0 and h.runs[-1] == ["engine", "qa", P], out
# text and --text-file together, or neither: refused (argparse exits 2), nothing run
for bad in (["--thread", "f-4", "--text-file", str(fb3), '[studio] actie=qa project="Zomer Shoot"'], ["--thread", "f-4"]):
    try:
        import contextlib, io   # noqa: E401
        with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
            studio.cli(bad, spawn=lambda t: None)
        raise AssertionError(f"accepted {bad}")
    except SystemExit as e:
        assert e.code == 2
assert len(h.runs) == 2 and not studio.handled("f-4")
# the file must be inside data/studio_inbox/
outside = tmp / "elders.txt"
outside.write_text('[studio] actie=qa project="Zomer Shoot"', encoding="utf-8")
for path in (str(outside), str(studio.INBOX / ".." / "elders.txt"), str(studio.INBOX / "nope.txt"), "elders.txt"):
    code, out = cli(["--thread", "f-5", "--text-file", path], h)
    assert code == 1 and out["ok"] is False and len(h.runs) == 2, (path, out)
assert not studio.handled("f-5")                                     # refused before marking: the session can retry
# thread ids: letters, digits, _ and - only, 1..100
for bad in ("", "a b", "../x", "x;rm", "t\n1", "é", "x" * 101):
    code, out = cli(["--thread", bad, '[studio] actie=qa project="Zomer Shoot"'], h)
    assert code == 1 and out == {"ok": False, "message": "ongeldige thread-id"} and len(h.runs) == 2, (bad, out)
assert not studio.handled("a b") and studio.handled("f-1")
code, out = cli(["--thread", "A_z-9" * 20, '[studio] actie=qa project="Zomer Shoot"'], h)
assert code == 0 and len(h.runs) == 3, out

# ---- 720p copy after preview/render: listed only if it fits (<= 20 MiB); the original is never listed
calls = []


def fake_transcode(src, dst, size=1000):
    calls.append((Path(src).name, Path(dst)))
    Path(dst).parent.mkdir(parents=True, exist_ok=True)
    Path(dst).write_bytes(b"v" * size)


studio.transcode_720 = fake_transcode
assets = tmp / "data" / "studio_assets"
studio.ASSETS = assets
code, out = cli(["--thread", "v-1", '[studio] actie=preview project="Zomer Shoot"'], h)
d720 = assets / studio.slug("Zomer Shoot")
assert code == 0 and calls[-1] == ("preview.mp4", d720 / "preview_720.mp4"), (out, calls)
assert same(out["local_files"]["video"], d720 / "preview_720.mp4") and "sheet" in out["local_files"], out
code, out = cli(["--thread", "v-2", '[studio] actie=render project="Zomer Shoot"'], h)
assert calls[-1] == ("cine_montage_20261101_1200.mp4", d720 / "render_720.mp4"), calls
assert same(out["local_files"]["video"], d720 / "render_720.mp4"), out
studio.transcode_720 = lambda src, dst: fake_transcode(src, dst, 20 * 1024 * 1024 + 1)
code, out = cli(["--thread", "v-3", '[studio] actie=render project="Zomer Shoot"'], h)
assert code == 0 and "video" not in out["local_files"] and not (d720 / "render_720.mp4").exists(), out
assert "te groot" in out["message"], out


def broken_transcode(src, dst):
    raise RuntimeError("ffmpeg weg")


studio.transcode_720 = broken_transcode
code, out = cli(["--thread", "v-4", '[studio] actie=preview project="Zomer Shoot"'], h)
assert code == 0 and out["ok"] and "video" not in out["local_files"] and "geen voorbeeldvideo" in out["message"], out
n = len(calls)
code, out = cli(["--thread", "v-5", '[studio] actie=qa project="Zomer Shoot"'], h)
assert len(calls) == n and "local_files" not in out, out                # qa: no video, no transcode

# ---- mark(): any OSError from the replace leaves no temp file behind
import os   # noqa: E402
real_replace = os.replace


def deny(a, b):
    raise OSError(22, "invalid")


os.replace = deny
try:
    studio.mark("m-1")
    raise AssertionError("mark ignored OSError")
except studio.HandledListError:
    pass
finally:
    os.replace = real_replace
assert not list(studio.HANDLED.parent.glob("*.tmp")), list(studio.HANDLED.parent.glob("*.tmp"))
# ---- detached start: validation answers at once; the work runs in a worker that writes data/studio_results/<id>.json
started = []
code, out = run(studio.cli, ["--thread", "d-1", '[studio] actie=render project="Zomer Shoot"'], spawn=started.append)
assert code == 0 and out == {"ok": True, "action": "render", "slug": studio.slug("Zomer Shoot"), "status": "bezig",
                             "message": "gestart"}, out
assert started == ["d-1"] and studio.handled("d-1")
code, res = run(studio.result_cli, ["--thread", "d-1"])
assert code == 0 and res["ok"] is True and res["status"] == "bezig" and res["action"] == "render", res
job = json.loads((studio.RESULTS / "d-1.job.json").read_text(encoding="utf-8"))
assert job["args"] == ["engine", "render", P] and job["project"] == "Zomer Shoot", job
h = FakeHost()
studio.transcode_720 = fake_transcode
with __import__("contextlib").redirect_stdout(__import__("io").StringIO()) as quiet:
    studio.work("d-1", host=h, poll=0)
assert quiet.getvalue() == "" and h.runs == [["engine", "render", P]]
code, res = run(studio.result_cli, ["--thread", "d-1"])
assert code == 0 and res["ok"] is True and res["status"] == "klaar" and res["action"] == "render", res
assert res["state"]["name"] == "Zomer Shoot" and "video" in res["local_files"], res
code, res = run(studio.result_cli, ["--thread", "nooit-gestart"])
assert code == 1 and res["ok"] is False and "onbekend" in res["message"], res
code, res = run(studio.result_cli, ["--thread", "../x"])
assert code == 1 and res == {"ok": False, "message": "ongeldige thread-id"}, res
code, res = run(studio.cli, ["--thread", "d-1", '[studio] actie=render project="Zomer Shoot"'], spawn=started.append)
assert res == {"ok": False, "message": "al afgehandeld"} and started == ["d-1"], res
# refusals and stills stay synchronous: no worker
code, out = run(studio.cli, ["--thread", "d-2", '[studio] actie=render project="Bestaat Niet"'], spawn=started.append)
assert code == 1 and out["ok"] is False and "status" not in out and started == ["d-1"], out
code, out = run(studio.cli, ["--thread", "d-3", '[studio] actie=stills project="Zomer Shoot"'], spawn=started.append)
assert out["action"] == "stills" and "status" not in out and started == ["d-1"], out   # its final line at once


def nospawn(thread):
    raise OSError("geen python")


code, out = run(studio.cli, ["--thread", "d-4", '[studio] actie=qa project="Zomer Shoot"'], spawn=nospawn)
assert code == 1 and out["ok"] is False and "kon niet starten" in out["message"], out
code, res = run(studio.result_cli, ["--thread", "d-4"])
assert res["ok"] is False and res["status"] == "fout", res                 # never stuck on "bezig"
# a worker that crashes still writes a result
studio.RESULTS.joinpath("d-5.job.json").write_text(json.dumps({"thread": "d-5", "action": "qa", "project": "Zomer Shoot",
                                                               "args": ["engine", "del", "x"]}), encoding="utf-8")
studio.work("d-5", host=FakeHost(), poll=0)
code, res = run(studio.result_cli, ["--thread", "d-5"])
assert code == 1 and res["ok"] is False and res["status"] == "fout", res

# the default spawn starts `python -m webapp studio-worker --thread <id>` detached from the session
import subprocess   # noqa: E402
seen = {}


class FakePopen:
    def __init__(self, cmd, **kw):
        seen.update(cmd=cmd, **kw)


real_popen, subprocess.Popen = subprocess.Popen, FakePopen
try:
    studio._spawn_detached("d-6")
finally:
    subprocess.Popen = real_popen
assert seen["cmd"][1:] == ["-m", "webapp", "studio-worker", "--thread", "d-6"], seen["cmd"]
assert seen["stdin"] == subprocess.DEVNULL and Path(seen["cwd"]) == query.REPO
if os.name == "nt":
    assert seen["creationflags"] & 0x8 and seen["creationflags"] & 0x200, seen      # DETACHED | NEW_PROCESS_GROUP
else:
    assert seen["start_new_session"] is True, seen

# ---- lock: one engine job at a time; a second worker waits (and says so) until the first is done
import threading   # noqa: E402
h = FakeHost()
run(studio.cli, ["--thread", "l-1", '[studio] actie=qa project="Zomer Shoot"'], spawn=lambda t: None)
with studio.file_lock(studio.LOCK):
    try:
        with studio.file_lock(studio.LOCK, wait=False):
            raise AssertionError("lock taken twice")
    except studio.Busy:
        pass
    w = threading.Thread(target=studio.work, args=("l-1",), kwargs={"host": h, "poll": 0})
    w.start()
    for _ in range(100):
        if "wacht" in json.loads((studio.RESULTS / "l-1.json").read_text(encoding="utf-8"))["message"]:
            break
        time.sleep(0.02)
    code, res = run(studio.result_cli, ["--thread", "l-1"])
    assert res["status"] == "bezig" and "wacht" in res["message"] and h.runs == [], res
w.join(10)
assert not w.is_alive() and h.runs == [["engine", "qa", P]]
assert run(studio.result_cli, ["--thread", "l-1"])[1]["status"] == "klaar"
with studio.file_lock(studio.LOCK, wait=False):                           # released after the job
    pass
# mark(): its read-modify-write holds its own lock (not the engine lock, so a start never waits for a render)
with studio.file_lock(studio.LOCK):
    run(studio.cli, ["--thread", "l-2", '[studio] actie=qa project="Zomer Shoot"'], spawn=lambda t: None)
assert studio.handled("l-2")
got = []
with studio.file_lock(studio.HANDLED_LOCK):
    m = threading.Thread(target=lambda: got.append(studio.claim("l-3")))
    m.start()
    time.sleep(0.2)
    assert got == [] and not studio.handled("l-3")                        # waits for the lock
m.join(10)
assert got == [True] and studio.handled("l-3") and studio.claim("l-3") is False

# ---- preview uses the plan's --grade mode (pending or approved), like render
(work / "APPROVAL.json").write_text(json.dumps({"status": "pending", "edl_sha1": sha, "grade_mode": "rec709"}))
assert argv('[studio] actie=preview project="Zomer Shoot"') == ["engine", "preview", P, "--grade", "rec709"]
(work / "APPROVAL.json").write_text(json.dumps({"status": "approved", "edl_sha1": sha, "grade_mode": "slog3"}))
assert argv('[studio] actie=preview project="Zomer Shoot"') == ["engine", "preview", P, "--grade", "slog3"]
(work / "APPROVAL.json").write_text(json.dumps({"status": "pending", "edl_sha1": sha, "grade_mode": "auto"}))
assert argv('[studio] actie=preview project="Zomer Shoot"') == ["engine", "preview", P]
(work / "APPROVAL.json").unlink()

# ---- made_with: the grade the storyboard sheet / preview were made with (engine writes a small json next to them)
(work / "storyboard" / "made_with.json").write_text(json.dumps({"key": G1, "look": "moody", "strength": 0.8,
                                                                "exposure": -1.5, "grade_mode": "auto"}))
(work / "preview_made_with.json").write_text(json.dumps({"key": G0, "look": "reference_film"}))
s = studio.state("Zomer Shoot")
assert s["made_with"] == {"sheet": {"key": G1, "look": "moody"}, "preview": {"key": G0, "look": "reference_film"}}, s
(work / "preview.mp4").unlink()                                           # no preview -> no label
(work / "preview_made_with.json").write_text("{kapot")
assert studio.state("Zomer Shoot")["made_with"] == {"sheet": {"key": G1, "look": "moody"}, "preview": None}

# ---- studio-projects: every project's state (with slug); names the validator refuses are skipped
(tmp / "projects" / "Rare;Naam" / "cine_montage").mkdir(parents=True)
(tmp / "projects" / " spatie" / "cine_montage").mkdir(parents=True)
code, lst = run(studio.projects_cli, [])
assert code == 0 and [x["name"] for x in lst] == ["Zomer Shoot"], lst
assert lst[0]["slug"] == studio.slug("Zomer Shoot") and lst[0]["state"]["name"] == "Zomer Shoot", lst
assert lst[0]["state"]["grade"]["chosen"] is False

# ---- SSD page: parse (no project), then list / look / preview / move on a temp SSD
assert studio.parse("[studio] actie=ssd-ververs") == {"actie": "ssd-ververs"}
r = studio.parse('[studio] actie=ssd-verplaats naam="Ibiza" soort=reizen mappen="_Inbox/2026-10-09 SD-kaart|_Inbox/2026-10-10 x"')
assert r["mappen"] == ["_Inbox/2026-10-09 SD-kaart", "_Inbox/2026-10-10 x"] and r["naam"] == "Ibiza", r
for bad in ('[studio] actie=ssd-bekijk', '[studio] actie=ssd-bekijk map="_Inbox/../.."', '[studio] actie=ssd-bekijk map="C:/Windows"',
            '[studio] actie=ssd-bekijk map="_Inbox/x" project="Zomer Shoot"', '[studio] actie=ssd-clip map="_Inbox/x" clip="../a.mp4"',
            '[studio] actie=ssd-verplaats naam="a/b" soort=reizen mappen="_Inbox/x"',
            '[studio] actie=ssd-verplaats naam="Ibiza" soort=vakantie mappen="_Inbox/x"',
            '[studio] actie=ssd-verplaats naam="Ibiza" soort=reizen mappen=""', '[studio] actie=ssd-ververs naam="x"'):
    raises(studio.parse, bad)

import subprocess                                                  # noqa: E402
from autoedit import library, offload                              # noqa: E402
from autoedit.config import Config                                 # noqa: E402
ssd = tmp / "ssd"
day = ssd / "_Inbox" / "2026-10-09 SD-kaart"
(day / "1 Ruw" / "Video").mkdir(parents=True)
subprocess.run([library._ffmpeg(), "-v", "error", "-f", "lavfi", "-i", "testsrc=duration=2:size=320x180:rate=25",
                "-pix_fmt", "yuv420p", str(day / "1 Ruw" / "Video" / "C0202.MP4")], check=True)
fotos = ssd / "_Inbox" / "2026-10-08 SD-kaart" / "1 Ruw" / "Foto"          # photos only: not on the video SSD page
fotos.mkdir(parents=True)
(fotos / "DSC00001.JPG").write_bytes(b"jpg")
lcfg = Config({"paths": {"library_folder": str(ssd), "projects_folder": str(tmp / "projects")}}, {})
library.CACHE = tmp / "thumbs"
studio.SSD_ASSETS = tmp / "data" / "studio_assets" / "ssd"
query.REPO = tmp                                                   # sheet paths are reported repo-relative
studio._lib = lambda: (library, lcfg)
docs = studio.ssd_docs()
assert docs["connected"] and [d["rel"] for d in docs["shoots"]] == ["_Inbox/2026-10-09 SD-kaart"], docs
assert "sheet_url" not in docs["shoots"][0] and docs["shoots"][0]["id"] == studio.slug("_Inbox/2026-10-09 SD-kaart")
assert "photos" not in docs["shoots"][0]
code, out = cli(["--thread", "s-1", '[studio] actie=ssd-bekijk map="_Inbox/2026-10-09 SD-kaart"'], h)
assert code == 0 and out["clips"][0]["name"] == "C0202.MP4" and (tmp / out["assets"]["sheet"]).exists(), out
assert "photos" not in out["assets"]
code, out = cli(["--thread", "s-2", '[studio] actie=ssd-clip map="_Inbox/2026-10-09 SD-kaart" clip="C0202.MP4"'], h)
assert code == 0 and Path(out["local_files"]["video"]).exists(), out
code, out = cli(["--thread", "s-3", '[studio] actie=ssd-clip map="_Inbox/2026-10-09 SD-kaart" clip="C9999.MP4"'], h)
assert code == 1 and "staat niet" in out["message"], out
code, out = cli(["--thread", "s-4", '[studio] actie=ssd-verplaats naam="Ibiza" soort=reizen mappen="_Inbox/2026-10-09 SD-kaart"'], h)
assert code == 0 and h.runs[-1] == ["autoedit", "sort", "Ibiza", "_Inbox/2026-10-09 SD-kaart", "--soort", "reizen"], (out, h.runs)
assert out["ssd"]["shoots"], out
n = len(h.runs)
code, out = cli(["--thread", "s-5", '[studio] actie=ssd-verplaats naam="Ibiza" soort=reizen mappen="_Inbox/2026-01-01 bestaat niet"'], h)
assert code == 1 and len(h.runs) == n, "a folder that is not on the SSD never reaches autoedit sort"
with studio.file_lock(studio.LOCK):                                 # never move files while an engine job runs
    code, out = cli(["--thread", "s-6", '[studio] actie=ssd-verplaats naam="Ibiza" soort=reizen mappen="_Inbox/2026-10-09 SD-kaart"'], h)
assert code == 1 and "bezig" in out["message"] and len(h.runs) == n, out
code, out = cli(["--thread", "s-8", '[studio] actie=ssd-edit naam="Kort" clips="_Inbox/2026-10-09 SD-kaart/C0202.MP4"'], h)
assert code == 0 and h.runs[-1] == ["autoedit", "pick", "Kort", "_Inbox/2026-10-09 SD-kaart/C0202.MP4"], (out, h.runs)
assert out["slug"] == studio.slug("Kort") and "state" in out, out
n = len(h.runs)
code, out = cli(["--thread", "s-9", '[studio] actie=ssd-edit naam="Kort" clips="_Inbox/2026-10-09 SD-kaart/C9999.MP4"'], h)
assert code == 1 and len(h.runs) == n, "a clip that is not on the SSD never reaches autoedit pick"
for bad in ('[studio] actie=ssd-edit naam="a/b" clips="_Inbox/x/C0001.MP4"', '[studio] actie=ssd-edit naam="K" clips=""',
            '[studio] actie=ssd-edit naam="K" clips="_Inbox/x/../../y.MP4"', '[studio] actie=ssd-edit naam="K" clips="C:/x/C0001.MP4"',
            '[studio] actie=ssd-edit naam="K" clips="_Inbox/x/C0001.exe"', '[studio] actie=ssd-edit naam="K"'):
    try:
        studio.parse(bad)
        raise AssertionError(f"accepted {bad}")
    except ValueError:
        pass
n = len(h.runs)
with studio.file_lock(studio.LOCK):                                 # never repoint clips while an engine job runs
    code, out = cli(["--thread", "s-10", '[studio] actie=ssd-edit naam="Kort" clips="_Inbox/2026-10-09 SD-kaart/C0202.MP4"'], h)
assert code == 1 and "bezig" in out["message"] and len(h.runs) == n, out
# ---- JUICT film from the Promptgenerator: checked here, made by the session (no engine, no worker)
ff = studio.INBOX / "jf-1.txt"
ff.write_text('[studio] actie=juict-film titel="Printix: aanmelden" serie="" prompt="Maak een uitlegvideo.\n'
              '1. Titel (4 sec): \\"Printix\\"\n2. Stap 1 (8 sec)"\n', encoding="utf-8")
code, out = cli(["--thread", "jf-1", "--text-file", str(ff)], FakeHost())
assert code == 0 and out["action"] == "juict-film" and out["status"] == "klaar", out
assert out["film"].pop("id") == "film-" + hashlib.sha1(b"jf-1").hexdigest()[:10], out
assert out["film"] == {"titel": "Printix: aanmelden", "serie": "Losse video's",
                       "prompt": 'Maak een uitlegvideo.\n1. Titel (4 sec): "Printix"\n2. Stap 1 (8 sec)'}, out
code, out = cli(["--thread", "jf-1", "--text-file", str(ff)], FakeHost())
assert code == 1 and out["message"] == "al afgehandeld", out
for bad in ('[studio] actie=juict-film titel="" prompt="x"', '[studio] actie=juict-film titel="a" prompt=""',
            '[studio] actie=juict-film titel="a\nb" prompt="x"', '[studio] actie=juict-film titel="a" serie="b\nc" prompt="x"',
            '[studio] actie=juict-film titel="a" prompt="x" project="Zomer Shoot"',
            f'[studio] actie=juict-film titel="a" prompt="{"x" * 6001}"', '[studio] actie=juict-film titel="a" prompt="x\x07"',
            '[studio] actie=juict-film titel="a" pdf=../x', '[studio] actie=juict-film titel="a" pdf=0123abcd doc=../x',
            '[studio] actie=juict-film titel="a" doc=d-1'):
    raises(studio.parse, bad)
r = studio.parse('[studio] actie=juict-film titel="Printix" serie="" pdf=0123456789abcdef0123456789abcdef doc=d-mh2x9k1')
assert r["pdf"] == "0123456789abcdef0123456789abcdef" and r["doc"] == "d-mh2x9k1" and r["prompt"] == "", r
ff2 = studio.INBOX / "jf-2.txt"
ff2.write_text('[studio] actie=juict-film titel="Printix" pdf=0123456789abcdef0123456789abcdef doc=d-mh2x9k1\n', encoding="utf-8")
code, out = cli(["--thread", "jf-2", "--text-file", str(ff2)], FakeHost())
assert code == 0 and out["film"]["pdf"] == "0123456789abcdef0123456789abcdef" and out["film"]["doc"] == "d-mh2x9k1", out

print("studio test OK")
