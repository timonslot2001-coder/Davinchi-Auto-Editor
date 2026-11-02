"""SSD library test in a temp folder: list shoots, thumbnails/preview, name + move out of _Inbox (no SSD needed).
usage: python tests/library_test.py"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from autoedit import library, offload        # noqa: E402
from autoedit.config import Config           # noqa: E402

tmp = Path(tempfile.mkdtemp(prefix="library_test_"))
lib, projects = tmp / "ssd", tmp / "projects"
cfg = Config({"paths": {"library_folder": str(lib), "projects_folder": str(projects)}}, {})
library.CACHE = tmp / "cache"
ff = library._ffmpeg()


def day(folder, videos=(), photos=()):
    d = lib / "_Inbox" / folder
    for s in offload.SHOOT_DIRS:
        (d / s).mkdir(parents=True, exist_ok=True)
    for v in videos:
        subprocess.run([ff, "-v", "error", "-f", "lavfi", "-i", "testsrc=duration=3:size=320x180:rate=25",
                        "-pix_fmt", "yuv420p", str(d / "1 Ruw" / "Video" / v)], check=True)
    for p in photos:
        from PIL import Image
        Image.new("RGB", (600, 400), (200, 80, 40)).save(d / "1 Ruw" / "Foto" / p)
    return d


a = day("2026-10-09 SD-kaart", videos=["C0202.MP4"], photos=["DSC00001.JPG"])
b = day("2026-10-10 SD-kaart", videos=["C0230.MP4", "C0202.MP4"])          # same clip name as in a → kept as _2
(b / "1 Ruw" / "Foto" / "DSC00002.ARW").write_bytes(b"raw")
ledger = {"C0230.MP4|1|1": str(b / "1 Ruw" / "Video" / "C0230.MP4")}
(lib / offload.LEDGER).write_text(json.dumps(ledger), encoding="utf-8")

# a project that already reads its clips from day b (junction) must follow the move
import _winapi                                # noqa: E402
old_proj = projects / "Test oud"
old_proj.mkdir(parents=True)
_winapi.CreateJunction(str(b / "1 Ruw" / "Video"), str(old_proj / "clips"))

# list + look
s = library.shoots(cfg)
rows = {r["rel"]: r for r in s["shoots"]}
assert rows["_Inbox/2026-10-09 SD-kaart"]["videos"] == 1 and rows["_Inbox/2026-10-09 SD-kaart"]["photos"] == 1, rows
assert rows["_Inbox/2026-10-10 SD-kaart"]["photos"] == 1 and rows["_Inbox/2026-10-10 SD-kaart"]["project"] == "Test oud"
one = library.shoot(cfg, "_Inbox/2026-10-09 SD-kaart")
assert abs(one["videos"][0]["duration"] - 3) < 0.2 and one["photos"][0]["name"] == "DSC00001.JPG", one
t = Path(library.thumb(cfg, one["videos"][0]["path"]))
assert t.exists() and t.stat().st_size > 500
assert Path(library.thumb(cfg, one["photos"][0]["path"])).exists()
pv = Path(library.preview(cfg, one["videos"][0]["path"]))
assert pv.exists() and pv.suffix == ".mp4"
assert library.thumb(cfg, one["videos"][0]["path"]) == str(t), "cached"

# warm makes every thumbnail ahead of time (cached), for all folders with video
for f in library.CACHE.glob("*.jpg"):
    f.unlink()
assert library.warm(cfg) == 3 and len(list(library.CACHE.glob("*.jpg"))) == 3

# only shoot folders and files on the SSD
for bad in ("..", "_Inbox/..", "Koken", "Nope/x", "_Inbox/2026-10-09 SD-kaart/1 Ruw"):
    try:
        library.resolve_shoot(cfg, bad)
        raise AssertionError(f"accepted {bad!r}")
    except (ValueError, FileNotFoundError):
        pass
try:
    library.thumb(cfg, str(Path(__file__)))
    raise AssertionError("served a file outside the SSD")
except PermissionError:
    pass

# move both days into one shoot under Reizen
r = library.move(cfg, "Ibiza", "reizen", ["_Inbox/2026-10-09 SD-kaart", "_Inbox/2026-10-10 SD-kaart"])
shoot = lib / "Reizen" / "2026-10-09 Ibiza"
assert r["shoot"] == str(shoot) and r["moved"] == 5, r
assert sorted(p.name for p in (shoot / "1 Ruw" / "Video").iterdir()) == ["C0202.MP4", "C0202_2.MP4", "C0230.MP4"]
assert sorted(p.name for p in (shoot / "1 Ruw" / "Foto").iterdir()) == ["DSC00001.JPG", "DSC00002.ARW"]
assert not a.exists() and not b.exists(), "empty day folders are gone"
assert (projects / "Ibiza" / "clips").resolve() == (shoot / "1 Ruw" / "Video").resolve()
assert 'category: "travel"' in (projects / "Ibiza" / "project.yaml").read_text(encoding="utf-8")
assert r["relinked"] == ["Test oud"] and (old_proj / "clips" / "C0230.MP4").exists(), "old project follows its clips"
assert json.loads((lib / offload.LEDGER).read_text())["C0230.MP4|1|1"] == str(shoot / "1 Ruw" / "Video" / "C0230.MP4")

# a later day with the same name joins the same shoot
c = day("2026-10-11 SD-kaart", videos=["C0254.MP4"])
r = library.move(cfg, "ibiza", "reizen", ["_Inbox/2026-10-11 SD-kaart"])
assert r["shoot"] == str(shoot) and (shoot / "1 Ruw" / "Video" / "C0254.MP4").exists() and not c.exists(), r

# pick clips from two shoots into one edit: hard links in _Edits/<name>, the project reads from there
d = day("2026-10-20 SD-kaart", videos=["C0300.MP4", "C0202.MP4"])
kas = lib / "Koken" / "2026-10-20 Kas"
kas.parent.mkdir(parents=True, exist_ok=True)
os.replace(d, kas)
r = library.pick(cfg, "Kort", ["Reizen/2026-10-09 Ibiza/C0230.MP4", "Koken/2026-10-20 Kas/C0300.MP4",
                               "Reizen/2026-10-09 Ibiza/C0202.MP4", "Koken/2026-10-20 Kas/C0202.MP4"])
edits = lib / "_Edits" / "Kort"
assert r["added"] == 4 and r["clips"] == 4, r
assert sorted(p.name for p in edits.iterdir()) == ["2026-10-20 Kas C0202.MP4", "C0202.MP4", "C0230.MP4", "C0300.MP4"]
assert os.path.samefile(edits / "C0230.MP4", shoot / "1 Ruw" / "Video" / "C0230.MP4"), "a hard link, not a copy"
assert (shoot / "1 Ruw" / "Video" / "C0230.MP4").exists(), "the original stays"
assert (projects / "Kort" / "clips").resolve() == edits.resolve()
r = library.pick(cfg, "Kort", ["Reizen/2026-10-09 Ibiza/C0230.MP4", "Reizen/2026-10-09 Ibiza/C0254.MP4"])
assert r["added"] == 1 and r["already"] == 1 and r["clips"] == 5, r
assert library.shoots(cfg)["shoots"] and not any(s["rel"].startswith("_Edits") for s in library.shoots(cfg)["shoots"])
# picking into a project that read a whole shoot keeps its clips (linked into the edit too)
r = library.pick(cfg, "Ibiza", ["Koken/2026-10-20 Kas/C0300.MP4"])
assert r["clips"] == 5 and (projects / "Ibiza" / "clips").resolve() == (lib / "_Edits" / "Ibiza").resolve(), r
assert len(list((shoot / "1 Ruw" / "Video").glob("*.MP4"))) == 4, "the shoot folder itself is untouched"
for bad in (["Reizen/2026-10-09 Ibiza/nope.MP4"], ["Reizen/../C0230.MP4"], ["C:/Windows/x.mp4"], []):
    try:
        library.pick(cfg, "Kort", bad)
        raise AssertionError(f"accepted {bad!r}")
    except SystemExit:
        pass

# bad names / kinds are refused
for args in (("..", "reizen", ["Reizen/2026-10-09 Ibiza"]), ("x", "nope", ["Reizen/2026-10-09 Ibiza"]),
             ("x", "reizen", ["Reizen/../.."]), ("x", "reizen", [])):
    try:
        library.move(cfg, *args)
        raise AssertionError(f"accepted {args!r}")
    except SystemExit:
        pass

for p in projects.iterdir():                  # remove junctions as links before deleting the temp folder
    if (p / "clips").is_junction():
        os.rmdir(p / "clips")
shutil.rmtree(tmp)
print("library test ok")
