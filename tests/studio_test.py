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


def raises(fn, *a, contains=""):
    try:
        fn(*a)
    except ValueError as e:
        assert contains in str(e), (contains, str(e))
        return str(e)
    raise AssertionError(f"no ValueError for {a}")


# ---- parse
note = "mooi zo, a=b werkt & meer"
r = studio.parse(f'[studio] actie=goedkeuren project="Zomer Shoot" plan={sha} notitie="{note}"')
assert r == {"actie": "goedkeuren", "project": "Zomer Shoot", "plan": sha, "notitie": note}, r
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
raises(argv, f'[studio] actie=goedkeuren project="Zomer Shoot" plan={sha}', contains="notitie")
raises(argv, '[studio] actie=goedkeuren project="Zomer Shoot" notitie="ja"', contains="plan is veranderd")
raises(argv, '[studio] actie=goedkeuren project="Zomer Shoot" plan=0123456789ab notitie="ja"',
       contains="het plan is veranderd sinds je het zag: bekijk het nieuwe plan")
assert argv(f'[studio] actie=goedkeuren project="Zomer Shoot" plan={sha} notitie="{note}"') == \
    ["engine", "approve", P, "--by", "Timon", "--note", note]
raises(argv, '[studio] actie=render project="Bestaat Niet"', contains="project")
try:
    argv('[studio] actie=stills project="Zomer Shoot"')
    raise AssertionError("stills should not map to engine yet")
except studio.NotYet as e:
    assert "nog niet beschikbaar" in str(e)
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

# ---- state
gkey = studio.grade_key("reference_film", 1.0, -1.75)
(work / "APPROVAL.json").write_text(json.dumps({"status": "approved", "edl_sha1": sha, "grade_key": gkey,
                                                "grade_mode": "auto", "by": "Timon", "note": "top", "at": "2026-11-01T10:00:00"}))
s = studio.state("Zomer Shoot")
assert s["name"] == "Zomer Shoot"
assert s["plan"] == {"edl_sha1": sha, "shots": 3, "duration": 18.0, "title": "ZOMER"}, s["plan"]
assert s["approval"] == {"status": "approved", "by": "Timon", "at": "2026-11-01T10:00:00", "note": "top",
                         "current": True, "grade_current": True}, s["approval"]
assert s["grade"] == {"look": "reference_film", "strength": 1.0, "exposure": -1.75}
assert s["stills"] == [] and s["luts"] == {"conv": None, "looks": {}} and s["render"] is None and s["updated_at"]
(work / "grade.json").write_text(json.dumps({"look": "moody", "strength": 0.8, "exposure": -1.5}))
s = studio.state("Zomer Shoot")
assert s["approval"]["grade_current"] is False and s["approval"]["current"] is True
assert s["grade"] == {"look": "moody", "strength": 0.8, "exposure": -1.5}
dump = json.dumps(s)
assert "\\\\" not in dump and "\\" not in dump and ":/" not in dump, dump
assert studio.slug("Zomer Shoot") == "zomer-shoot" and studio.slug("Café (2)") == "caf---2-"
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
assert set(out) >= {"ok", "action", "message", "state"} and out["slug"] == "zomer-shoot"
assert "sheet.jpg" in out["message"] and "\\" not in out["message"] and ":/" not in out["message"], out["message"]
assert studio.redact("lut D:/AutoEdit/luts/moody.cube ok") == "lut moody.cube ok"
assert studio.redact(r"in \\nas\share\x.mp4") == "in x.mp4"
code, out = cli(["--thread", "c-100", '[studio] actie=grade project="Zomer Shoot" look=daylight'], h)
assert out == {"ok": False, "message": "al afgehandeld"} and len(h.runs) == 1, out
code, out = cli(["--thread", "c-101", '[studio] actie=render project="Zomer Shoot" ; del *'], h)
assert code == 1 and out["ok"] is False and len(h.runs) == 1 and studio.handled("c-101"), out
code, out = cli(["--thread", "c-102", '[studio] actie=stills project="Zomer Shoot"'], h)
assert out["ok"] is False and "nog niet beschikbaar" in out["message"] and len(h.runs) == 1, out
code, out = cli(["--thread", "c-103", '[studio] actie=render project="Zomer Shoot"'], FakeHost("failed"))
assert code == 1 and out["ok"] is False and out["action"] == "render", out


class BrokenHost(FakeHost):
    def run(self, args, label="", project=None):
        raise RuntimeError("worker weg")


code, out = cli(["--thread", "c-104", '[studio] actie=qa project="Zomer Shoot"'], BrokenHost())
assert code == 1 and out["ok"] is False and "worker weg" in out["message"], out
print("studio test OK")
