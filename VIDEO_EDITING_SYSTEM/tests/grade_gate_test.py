"""Gate B covers the grade: `engine grade` stores look/strength/exposure, `approve` records its key, and `render`
is refused after the grade (or the plan) changes until a new approve. No footage needed.
usage: python tests/grade_gate_test.py"""
import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT.parent))
from engine import cli, gradechoice             # noqa: E402

tmp = Path(tempfile.mkdtemp(prefix="grade_gate_"))
try:
    work = tmp / "proj" / "cine_montage"; work.mkdir(parents=True); (work / "edl.json").write_text('{"events": []}')
    assert gradechoice.load(work) == gradechoice.Grade()                      # no grade.json -> default
    cli.main(["grade", str(tmp / "proj"), "--look", "moody", "--strength", "0.8", "--exposure", "-1.5"])
    g = gradechoice.load(work); assert (g.look, g.strength, g.exposure) == ("moody", 0.8, -1.5)
    cli.main(["approve", str(tmp / "proj"), "--by", "Timon", "--note", "mooi zo"])
    assert json.loads((work / "APPROVAL.json").read_text())["grade_key"] == gradechoice.key(g)
    assert cli.render_allowed(work, g) == (True, "")
    cli.main(["grade", str(tmp / "proj"), "--look", "vintage"])
    ok, why = cli.render_allowed(work, gradechoice.load(work)); assert not ok and "grade" in why.lower()
    before = (work / "grade.json").read_text()
    for bad in (["--look", "odyssey"], ["--look", "moody", "--strength", "1.5"], ["--look", "moody", "--exposure", "-9"]):
        try:
            cli.main(["grade", str(tmp / "proj")] + bad)
            raise AssertionError(bad)
        except SystemExit as e:
            assert e.code not in (0, None), bad                                 # bad values exit non-zero
        assert (work / "grade.json").read_text() == before, bad                 # ...and write nothing
    try:
        gradechoice.save(work, gradechoice.Grade("none"))
        raise AssertionError("look none accepted")
    except ValueError:
        pass
    (work / "edl.json").write_text('{"events": [1]}')                         # plan changed -> refused too
    assert not cli.render_allowed(work, gradechoice.load(work))[0]

    # approvals made before grade_key existed count for the default grade only
    (work / "edl.json").write_text('{"events": []}')
    old = {"status": "approved", "edl_sha1": cli.edl_hash(work / "edl.json"), "by": "Timon", "note": "ok"}
    (work / "APPROVAL.json").write_text(json.dumps(old))
    assert cli.render_allowed(work, gradechoice.Grade()) == (True, "")
    assert not cli.render_allowed(work, gradechoice.Grade("moody"))[0]

    from autoedit import grade
    assert set(gradechoice.LOOKS) == set(grade.LOOKS) - {"none"}, gradechoice.LOOKS
finally:
    shutil.rmtree(tmp, ignore_errors=True)
print("grade gate ok")
