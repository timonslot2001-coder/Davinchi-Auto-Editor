"""Preview stills + LUT stages for the Artifact grade picker.
usage: python tests/studio_assets_test.py"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import cv2
import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "VIDEO_EDITING_SYSTEM"))
from autoedit import grade                      # noqa: E402
from engine import media, render                # noqa: E402
from webapp import studio_assets as sa          # noqa: E402

tmp = Path(tempfile.mkdtemp())
proj = tmp / "Proj"
(proj / "clips").mkdir(parents=True)
clip = proj / "clips" / "A001.mp4"
subprocess.run([media.FF, "-y", "-v", "error", "-f", "lavfi", "-i", "testsrc2=size=640x360:rate=25", "-t", "2",
                "-pix_fmt", "yuv420p", str(clip)], check=True)
sony = tmp / "Sony"
grade.write_cube(sony / sa.CONV, grade.identity(17), "identity")
grade.SONY = sony

# ---- from the clips folder
out = tmp / "out"
res = sa.export(proj, out)
assert len(res["stills"]) == 4, res
for s in res["stills"]:
    im = cv2.imread(str(out / s["file"]))
    assert im is not None and im.shape[1] == 1280, s
    assert isinstance(s["is_log"], bool) and "A001.mp4" in s["label"], s
assert len({s["label"] for s in res["stills"]}) == 4                  # four different moments
from engine import gradechoice                  # noqa: E402
assert set(res["looks"]) == set(gradechoice.LOOKS) and len(res["looks"]) == 6
for f in res["looks"].values():
    assert "LUT_3D_SIZE 33" in (out / f).read_text(), f

# ---- conv.cube only when a still is log
render.detect_log = lambda c: False
shutil_out = tmp / "out_nolog"
assert sa.export(proj, shutil_out)["conv"] is None and not (shutil_out / "conv.cube").exists()
render.detect_log = lambda c: True
res = sa.export(proj, tmp / "out_log")
assert res["conv"] == "conv.cube" and (tmp / "out_log" / "conv.cube").exists() and all(s["is_log"] for s in res["stills"])
grade.SONY = tmp / "NoSony"                                          # LUT absent: no conv, no crash
assert sa.export(proj, tmp / "out_nosony")["conv"] is None
grade.SONY = sony

# ---- from the plan: first event + body events spread, at the middle of each event
work = proj / "cine_montage"
work.mkdir()
ev = [{"id": f"E{i}", "out_in": i, "out_out": i + 0.5, "source": str(clip), "src_in": 0.2 * i} for i in range(8)]
ev.append({"id": "X", "out_in": 9, "out_out": 10, "source": str(tmp / "weg.mp4"), "src_in": 0})   # missing source: skipped
(work / "edl.json").write_text(json.dumps({"events": ev}))
res = sa.export(proj, tmp / "out_plan", n=3)
assert len(res["stills"]) == 3 and res["stills"][0]["label"].endswith("0:00.2"), res["stills"]   # E0: 0 + 0.5/2
(work / "edl.json").unlink()
work.rmdir()
try:
    sa.export(tmp, tmp / "o2")
    raise AssertionError("no footage should raise")
except ValueError as e:
    assert "geen beeld" in str(e)

# ---- the browser maths (two stages) equals the baked render maths
look, strength, exposure = "moody", 0.7, -1.75
conv, _ = grade.read_cube(sony / sa.CONV)
lk, _ = grade.read_cube(out / "look_moody.cube")
rng = np.random.default_rng(1)
x = rng.random((2000, 3))
xs = np.clip(x + exposure * 0.0769, 0, 1)
c = grade.apply_cube(conv, xs)
page = c + (grade.apply_cube(lk, c) - c) * strength
# the render's reference: build_lut bakes conversion + film look into one 33^3 LUT, then a trilinear lookup
grid = grade.identity(33)
baked = grade.film_look(grade.apply_cube(conv, np.clip(grid + exposure * 0.0769, 0, 1)), grade.LOOKS[look], strength)
ref = grade.apply_cube(np.clip(baked, 0, 1), x)
err = np.abs(page - ref).max() * 255
assert err < 2, err
print("studio_assets OK (max diff %.2f/255)" % err)
