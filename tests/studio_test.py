"""Studio requests from the Artifact: parse, validate, map to one engine argv, dedupe, state.
usage: python tests/studio_test.py"""
import hashlib
import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from webapp import query, studio   # noqa: E402

tmp = Path(tempfile.mkdtemp())
(tmp / "projects").mkdir()
query.roots = lambda: {"projects": str(tmp / "projects"), "music": str(tmp / "music"), "output": str(tmp / "out"),
                       "data": str(tmp / "data")}
studio.HANDLED = tmp / "data" / "studio_handled.json"

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
assert s["grade"] == {"look": "reference_film", "strength": 1.0, "exposure": -1.75, "key": G0}
assert s["stills"] == [] and s["luts"] == {"conv": None, "looks": {}} and s["render"] is None and s["updated_at"]
(work / "grade.json").write_text(json.dumps({"look": "moody", "strength": 0.8, "exposure": -1.5}))
s = studio.state("Zomer Shoot")
assert s["approval"]["grade_current"] is False and s["approval"]["current"] is True
G1 = studio.grade_key("moody", 0.8, -1.5)
assert s["grade"] == {"look": "moody", "strength": 0.8, "exposure": -1.5, "key": G1} and G1 != G0
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


def cli(args, host):
    import contextlib
    import io
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = studio.cli(args, host=host, poll=0)
    lines = buf.getvalue().strip().splitlines()
    assert len(lines) == 1, lines
    return code, json.loads(lines[0])


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
code, out = cli(["--thread", "c-100", '[studio] actie=grade project="Zomer Shoot" look=daylight'], h)
assert out == {"ok": False, "message": "al afgehandeld"} and len(h.runs) == 1, out
code, out = cli(["--thread", "c-101", '[studio] actie=render project="Zomer Shoot" ; del *'], h)
assert code == 1 and out["ok"] is False and len(h.runs) == 1 and studio.handled("c-101"), out
code, out = cli(["--thread", "c-102", '[studio] actie=stills project="Zomer Shoot"'], h)
assert out["ok"] is False and out["action"] == "stills" and "geen beeld" in out["message"] and len(h.runs) == 1, out
# stills run studio_assets.export directly (no engine job); assets paths are repo-relative, state stays path-free
from webapp import studio_assets   # noqa: E402
studio_assets.export = lambda p, o: {"stills": [{"file": "still_0.png", "is_log": True, "label": "A.mp4 0:01.0"}],
                                     "conv": "conv.cube", "looks": {"moody": "look_moody.cube"}}
code, out = cli(["--thread", "c-102b", '[studio] actie=stills project="Zomer Shoot"'], h)
d = f"data/studio_assets/{studio.slug('Zomer Shoot')}"
assert code == 0 and out["ok"] and len(h.runs) == 1, out
assert out["assets"] == {"stills": [{"file": f"{d}/still_0.png", "is_log": True, "label": "A.mp4 0:01.0"}],
                         "conv": f"{d}/conv.cube", "looks": {"moody": f"{d}/look_moody.cube"}}, out["assets"]
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
            studio.cli(bad, host=h, poll=0)
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
print("studio test OK")
