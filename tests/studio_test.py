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
code, out = cli(["--thread", "s-6", '[studio] actie=ssd-edit naam="Kort" clips="_Inbox/2026-10-09 SD-kaart/C0202.MP4"'], h)
assert code == 0 and h.runs[-1] == ["autoedit", "pick", "Kort", "_Inbox/2026-10-09 SD-kaart/C0202.MP4"], (out, h.runs)
assert out["slug"] == studio.slug("Kort") and "state" in out, out
n = len(h.runs)
code, out = cli(["--thread", "s-7", '[studio] actie=ssd-edit naam="Kort" clips="_Inbox/2026-10-09 SD-kaart/C9999.MP4"'], h)
assert code == 1 and len(h.runs) == n, "a clip that is not on the SSD never reaches autoedit pick"
for bad in ('[studio] actie=ssd-edit naam="a/b" clips="_Inbox/x/C0001.MP4"', '[studio] actie=ssd-edit naam="K" clips=""',
            '[studio] actie=ssd-edit naam="K" clips="_Inbox/x/../../y.MP4"', '[studio] actie=ssd-edit naam="K" clips="C:/x/C0001.MP4"',
            '[studio] actie=ssd-edit naam="K" clips="_Inbox/x/C0001.exe"', '[studio] actie=ssd-edit naam="K"'):
    try:
        studio.parse(bad)
        raise AssertionError(f"accepted {bad}")
    except ValueError:
        pass
print("studio test OK")
