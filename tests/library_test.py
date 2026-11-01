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
