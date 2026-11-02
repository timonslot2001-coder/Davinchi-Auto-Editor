"""Gate B covers the grade: `engine grade` stores look/strength/exposure in grade.json (the single source of truth),
`approve` records its key and the --grade mode, and `render` is refused after the grade, the mode or the plan changes
until a new approve. No footage needed.
usage: python tests/grade_gate_test.py"""
import contextlib
import io
import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT.parent))
from engine import cli, gradechoice             # noqa: E402
from engine.edl import EDL                     # noqa: E402
from autoedit import grade                      # noqa: E402


def exits(argv) -> str:
    """Run the CLI, expect a non-zero exit; returns the exit message (argparse output silenced)."""
    try:
        with contextlib.redirect_stderr(io.StringIO()):
            cli.main(argv)
    except SystemExit as e:
        assert e.code not in (0, None), argv
        return str(e.code)
    raise AssertionError(f"no exit: {argv}")


def approve_pending(work: Path, mode: str = "auto") -> None:
    """What `plan` writes (without footage): a pending approval for the current EDL and --grade mode."""
    (work / "APPROVAL.json").write_text(json.dumps({"status": "pending", "edl_sha1": cli.edl_hash(work / "edl.json"),
                                                    "grade_mode": mode}))


tmp = Path(tempfile.mkdtemp(prefix="grade_gate_"))
try:
    proj = str(tmp / "proj")
    work = tmp / "proj" / "cine_montage"; work.mkdir(parents=True); (work / "edl.json").write_text('{"events": []}')
    assert gradechoice.load(work) == gradechoice.Grade()                      # no grade.json -> default
    cli.main(["grade", proj, "--look", "moody", "--strength", "0.8", "--exposure", "-1.5"])
    g = gradechoice.load(work); assert (g.look, g.strength, g.exposure) == ("moody", 0.8, -1.5)
    cli.main(["approve", proj, "--by", "Timon", "--note", "mooi zo"])
    appr = json.loads((work / "APPROVAL.json").read_text())
    assert appr["grade_key"] == gradechoice.key(g) and appr["grade_mode"] == "auto"
    assert cli.render_allowed(work, g) == (True, "")
    cli.main(["grade", proj, "--look", "vintage"])
    ok, why = cli.render_allowed(work, gradechoice.load(work)); assert not ok and "grade" in why.lower()

    # CLI wiring: render refuses before the EDL or footage is touched (edl.json here is not even a full EDL)
    assert exits(["render", proj]).startswith("REFUSED"), "render after a grade change"
    exits(["render", proj, "--look", "vintage"])                              # render has no --look: grade.json only

    before = (work / "grade.json").read_text()
    for bad in (["--look", "odyssey"], ["--look", "moody", "--strength", "1.5"], ["--look", "moody", "--exposure", "-9"]):
        exits(["grade", proj] + bad)                                          # bad values exit non-zero
        assert (work / "grade.json").read_text() == before, bad              # ...and write nothing
    try:
        gradechoice.save(work, gradechoice.Grade("none"))
        raise AssertionError("look none accepted")
    except ValueError:
        pass

    # strength/exposure are stored rounded, so key and LUT agree
    cli.main(["grade", proj, "--look", "clean_warm", "--strength", "0.66666", "--exposure", "-1.23456"])
    assert gradechoice.load(work) == gradechoice.Grade("clean_warm", 0.667, -1.235)
    cli.main(["approve", proj, "--by", "Timon", "--note", "ja"])              # pick a grade, then approve it
    assert cli.render_allowed(work, gradechoice.load(work)) == (True, "")

    # a hand-edited, invalid grade.json is refused, not rendered silently
    (work / "grade.json").write_text(json.dumps({"look": "odyssey", "strength": 1.0, "exposure": -1.75}))
    try:
        gradechoice.load(work)
        raise AssertionError("bad grade.json loaded")
    except ValueError:
        pass
    assert "ongeldig" in exits(["render", proj])
    gradechoice.save(work, gradechoice.Grade("clean_warm", 0.667, -1.235))

    # the --grade mode is part of the approval: plan records it, approve carries it over, render must match
    approve_pending(work, "rec709")
    cli.main(["approve", proj, "--by", "Timon", "--note", "ja"])
    assert json.loads((work / "APPROVAL.json").read_text())["grade_mode"] == "rec709"
    g = gradechoice.load(work)
    assert cli.render_allowed(work, g, "rec709") == (True, "")
    ok, why = cli.render_allowed(work, g, "none"); assert not ok and "grade-modus" in why
    assert "grade-modus" in exits(["render", proj, "--grade", "none"])

    (work / "edl.json").write_text('{"events": [1]}')                         # plan changed -> refused too
    assert not cli.render_allowed(work, gradechoice.load(work), "rec709")[0]

    # approvals made before grade_key/grade_mode existed count for the default grade and "auto" only
    (work / "edl.json").write_text('{"events": []}')
    old = {"status": "approved", "edl_sha1": cli.edl_hash(work / "edl.json"), "by": "Timon", "note": "ok"}
    (work / "APPROVAL.json").write_text(json.dumps(old))
    assert cli.render_allowed(work, gradechoice.Grade()) == (True, "")
    assert not cli.render_allowed(work, gradechoice.Grade("moody"))[0]
    assert not cli.render_allowed(work, gradechoice.Grade(), "slog3")[0]

    # plan --look saves the look to grade.json (keeping strength/exposure); here plan then stops for lack of footage
    gradechoice.save(work, gradechoice.Grade("moody", 0.5, -1.0))
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            cli.main(["plan", proj, "--look", "daylight"])
        raise AssertionError("plan without footage did not stop")
    except (ValueError, SystemExit):
        pass
    assert gradechoice.load(work) == gradechoice.Grade("daylight", 0.5, -1.0)

    # approve --expect-sha1/--expect-grade: refuse unless plan and grade are still the ones the user saw
    approve_pending(work)
    before = (work / "APPROVAL.json").read_text()
    sha, gk = cli.edl_hash(work / "edl.json"), gradechoice.key(gradechoice.load(work))
    base = ["approve", proj, "--by", "Timon", "--note", "ja"]
    assert "plan is veranderd" in exits(base + ["--expect-sha1", "0123456789ab", "--expect-grade", gk])
    assert "grade is veranderd" in exits(base + ["--expect-sha1", sha, "--expect-grade", "0123456789ab"])
    assert (work / "APPROVAL.json").read_text() == before                    # refused -> nothing written
    with contextlib.redirect_stdout(io.StringIO()):
        cli.main(base + ["--expect-sha1", sha, "--expect-grade", gk])
    appr = json.loads((work / "APPROVAL.json").read_text())
    assert appr["status"] == "approved" and appr["edl_sha1"] == sha and appr["grade_key"] == gk

    assert set(gradechoice.LOOKS) == set(grade.LOOKS) - {"none"}, gradechoice.LOOKS
    # render hashes and parses the same bytes of edl.json: one read, no window between gate and render
    (work / "edl.json").write_text('{"events": []}')
    gradechoice.save(work, gradechoice.Grade())
    approve_pending(work)
    with contextlib.redirect_stdout(io.StringIO()):
        cli.main(["approve", proj, "--by", "Timon", "--note", "ja"])
    reads, parsed = [], []
    real_rb, real_rt = Path.read_bytes, Path.read_text

    def rb(self):
        if self.name == "edl.json":
            reads.append("bytes")
        return real_rb(self)

    def rt(self, *a, **kw):
        if self.name == "edl.json":
            reads.append("text")
        return real_rt(self, *a, **kw)

    class Stop(Exception):
        pass

    class FakeEDL:
        @staticmethod
        def load(path):
            raise AssertionError("render must not read edl.json a second time")

        @staticmethod
        def loads(data):
            parsed.append(data)
            raise Stop()

    real_edl, Path.read_bytes, Path.read_text, cli.EDL = cli.EDL, rb, rt, FakeEDL
    try:
        cli.main(["render", proj])
        raise AssertionError("render did not reach the parse")
    except Stop:
        pass
    finally:
        Path.read_bytes, Path.read_text, cli.EDL = real_rb, real_rt, real_edl
    assert reads == ["bytes"] and parsed == [b'{"events": []}'], (reads, parsed)
    ev = {"id": "E01", "out_in": 0, "out_out": 1, "source": None, "src_in": 0, "src_out": 1, "transition_in": "cut",
          "treatment": "none", "params": {}}
    d = {"project": "p", "profile": "P", "width": 1920, "height": 1080, "fps": 25.0, "accent": "#E70002", "music_offset": 0,
         "duration": 1.0, "music": None, "notes": [], "overlays": [], "events": [ev]}
    assert EDL.loads(json.dumps(d).encode()).events[0].id == "E01"            # same result as EDL.load
    # storyboard/preview record the grade they were made with (webapp/studio.py state() reads it)
    mw = work / cli.MADE_WITH["preview"]
    cli.write_made_with(mw, gradechoice.Grade("moody", 0.8, -1.5), "rec709")
    d = json.loads(mw.read_text())
    assert d == {"key": gradechoice.key(gradechoice.Grade("moody", 0.8, -1.5)), "look": "moody", "strength": 0.8,
                 "exposure": -1.5, "grade_mode": "rec709"}, d
    assert cli.MADE_WITH["plan"].as_posix() == "storyboard/made_with.json"
finally:
    shutil.rmtree(tmp, ignore_errors=True)
print("grade gate ok")
