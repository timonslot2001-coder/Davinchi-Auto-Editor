"""`autoedit edit`: stops with a plain list when a choice is missing, remembers the choices per project, and hands
the brief to the editor. No Resolve needed (pipeline.run is replaced by a recorder).
usage: python tests/edit_cmd_test.py"""
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import yaml                                                    # noqa: E402
from autoedit import config, pipeline                          # noqa: E402

tmp = Path(tempfile.mkdtemp())
(tmp / "music").mkdir()
(tmp / "music" / "Escape Plan.mp3").write_bytes(b"x")
proj = tmp / "projects" / "Beef Tartaar"
(proj / "clips").mkdir(parents=True)
(proj / "clips" / "C0001.MP4").write_bytes(b"x")
(proj / "project.yaml").write_text("title: Beef\n# a comment Timon wrote\ncategory: food\n", encoding="utf-8")
(tmp / "powergrades").mkdir()
(tmp / "powergrades" / "Film look.drx").write_bytes(b"x")

cfg = config.load()
cfg.raw.setdefault("paths", {}).update(projects_folder=str(tmp / "projects"), music_folder=str(tmp / "music"))
pipeline.POWERGRADES = tmp / "powergrades"
calls = []
pipeline.run = lambda *a, **kw: calls.append((a, kw)) or [{"ok": True}]

assert pipeline.pick_music(cfg, None) is None, "no song chosen must not mean a random song"
assert pipeline.grade_names() == ["basis", "Film look"]

try:
    pipeline.edit(cfg, "beef", {})
    raise AssertionError("an edit without song and grade must stop")
except pipeline.NotReady as e:
    text = str(e)
    assert "Escape Plan.mp3" in text and "Film look" in text and "basis" in text, text
assert not calls, "nothing may be built when a choice is missing"

pipeline.edit(cfg, "beef", {"song": "escape", "grade": "basis", "length": "kort"}, seed=5)
(args, kw), = calls
b = kw["brief"]
assert (b.song, b.grade, b.length, b.rhythm) == ("escape", "basis", "kort", "rustig")
assert kw["seed"] == 5 and kw["aspect"] == "9:16" and kw["category"] == "food" and kw["title"] == "Beef"
assert Path(args[1]) == proj / "clips"
assert Path(args[4]).name == "Escape Plan.mp3", "the song is passed as the file that matched"
saved = (proj / "project.yaml").read_text(encoding="utf-8")
assert "# a comment Timon wrote" in saved, "Timon's own lines in project.yaml stay"
assert yaml.safe_load(saved)["edit"]["song"] == "escape" and yaml.safe_load(saved)["edit"]["length"] == "kort"

calls.clear()
pipeline.edit(cfg, "beef", {"rhythm": "beat"})                  # second edit: the stored choices are reused
b = calls[0][1]["brief"]
assert (b.song, b.grade, b.length, b.rhythm) == ("escape", "basis", "kort", "beat")
assert yaml.safe_load((proj / "project.yaml").read_text(encoding="utf-8"))["edit"]["rhythm"] == "beat"
assert saved.count("edit:") == 1 and (proj / "project.yaml").read_text(encoding="utf-8").count("edit:") == 1

calls.clear()
pipeline.edit(cfg, str(proj / "clips"), {"song": "none", "grade": "basis"})   # a plain folder works, nothing saved
assert calls[0][0][4] == "none"

# the command line stops with exit code 2 and the plain message
r = subprocess.run([sys.executable, "-m", "autoedit", "edit", str(proj / "clips"), "--no-render"], cwd=ROOT,
                   capture_output=True, text=True, encoding="utf-8", errors="replace",
                   env={**__import__("os").environ, "PYTHONIOENCODING": "utf-8"})
assert r.returncode == 2, (r.returncode, r.stdout[-400:], r.stderr[-400:])
assert "Kies een liedje" in r.stdout + r.stderr
print("edit cmd test ok")
