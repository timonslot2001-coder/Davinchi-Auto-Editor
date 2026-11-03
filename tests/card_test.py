"""Camera card in -> offload + proposal (webapp/cardwatch.py, autoedit/library.card), without a real card or engine.
usage: python tests/card_test.py"""
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from autoedit import library, offload        # noqa: E402
from autoedit.config import Config           # noqa: E402
from webapp import cardwatch                 # noqa: E402

# --- the watcher starts one job per card that goes in, again only after it was out
runs = []


class FakeHost:
    def run(self, args, label="", project=None):
        runs.append(args)


cards = [[], ["E:\\"], ["E:\\"], [], ["E:\\"]]
state = {"i": 0}


def find():
    i = min(state["i"], len(cards) - 1)
    state["i"] += 1
    return cards[i]


cardwatch.start(FakeHost(), poll=0.05, find=find)
time.sleep(0.6)
assert runs == [["autoedit", "card"], ["autoedit", "card"]], runs

# --- card(): per new day with video an edit '<date> voorstel' and a plan; an existing plan is never overwritten
tmp = Path(tempfile.mkdtemp(prefix="card_test_"))
lib, projects = tmp / "ssd", tmp / "projects"
cfg = Config({"paths": {"library_folder": str(lib), "projects_folder": str(projects)}}, {})
library.CACHE = tmp / "cache"
day = lib / "_Inbox" / "2026-11-02 SD-kaart"
for s in offload.SHOOT_DIRS:
    (day / s).mkdir(parents=True, exist_ok=True)
subprocess.run([library._ffmpeg(), "-v", "error", "-f", "lavfi", "-i", "testsrc=duration=2:size=320x180:rate=25",
                "-pix_fmt", "yuv420p", str(day / "1 Ruw" / "Video" / "C0500.MP4")], check=True)
offload.offload = lambda cfg, name, kind: {"copied": 1, "shoots": [str(day)]}
plans = []
real_run = subprocess.run
subprocess.run = lambda args, **kw: (plans.append(args), type("R", (), {"returncode": 0})())[1]
try:
    out = library.card(cfg)                                      # no song picked yet: no plan, wait for step 2
    assert out == [{"project": "2026-11-02 voorstel", "clips": 1, "plan": False, "needs_song": True}], out
    assert not plans, "nothing is edited before the music is chosen"
    (projects / "2026-11-02 voorstel" / "project.yaml").write_text('song: "Escape Plan"\n', encoding="utf-8")
    assert library.has_song(projects / "2026-11-02 voorstel")
    out = library.card(cfg)
    assert out == [{"project": "2026-11-02 voorstel", "clips": 1, "plan": True}], out
    assert plans and plans[-1][-1].endswith("2026-11-02 voorstel"), plans
    assert (lib / "_Edits" / "2026-11-02 voorstel" / "C0500.MP4").exists()
    (projects / "2026-11-02 voorstel" / "cine_montage").mkdir(parents=True, exist_ok=True)
    (projects / "2026-11-02 voorstel" / "cine_montage" / "edl.json").write_text("{}")
    n = len(plans)
    assert library.card(cfg) == [] and len(plans) == n, "an existing proposal is left alone"
finally:
    subprocess.run = real_run
for p in projects.iterdir():
    if (p / "clips").is_junction():
        os.rmdir(p / "clips")
shutil.rmtree(tmp)
print("card test ok")
