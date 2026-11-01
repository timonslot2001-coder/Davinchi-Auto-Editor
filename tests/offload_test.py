"""Offload test on a fake camera card in a temp folder (no SD card or SSD needed).
usage: python tests/offload_test.py"""
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from autoedit import offload                 # noqa: E402
from autoedit.config import Config           # noqa: E402

tmp = Path(tempfile.mkdtemp(prefix="offload_test_"))
card, lib, projects = tmp / "card", tmp / "ssd", tmp / "projects"
lib.mkdir()
cfg = Config({"paths": {"library_folder": str(lib), "projects_folder": str(projects)}}, {})
day = time.mktime((2026, 10, 6, 17, 0, 0, 0, 0, -1))


def put(rel, data, t=day):
    p = card / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data)
    os.utime(p, (t, t))
    return p


put("PRIVATE/M4ROOT/CLIP/C0085.MP4", b"sony clip" * 1000)
put("PRIVATE/M4ROOT/CLIP/C0085M01.XML", b"<xml/>")
put("DCIM/100MSDCF/DSC00001.ARW", b"raw" * 500)
put("DCIM/100MSDCF/DSC00001.JPG", b"jpg" * 300)
put("DCIM/DJI_001/DJI_0001.MP4", b"dji clip" * 800)
put("DCIM/DJI_001/DJI_0001.LRF", b"proxy")                     # low-res proxy: skipped

r = offload.offload(cfg, "Beef Tartaar", "koken", cards=[card])
shoot = lib / "Koken" / "2026-10-06 Beef Tartaar"
assert r["copied"] == 5, r
assert sorted(p.name for p in (shoot / "1 Ruw" / "Video").iterdir()) == ["C0085.MP4", "C0085M01.XML", "DJI_0001.MP4"]
assert sorted(p.name for p in (shoot / "1 Ruw" / "Foto").iterdir()) == ["DSC00001.ARW", "DSC00001.JPG"]
for s in offload.SHOOT_DIRS:
    assert (shoot / s).is_dir(), s
assert (shoot / "1 Ruw" / "Video" / "C0085.MP4").read_bytes() == b"sony clip" * 1000
assert abs((shoot / "1 Ruw" / "Video" / "C0085.MP4").stat().st_mtime - day) < 2, "keeps the recording time"
assert not list(shoot.rglob("*.part")), "no half files left"
assert (card / "DCIM/100MSDCF/DSC00001.JPG").exists(), "card untouched"

proj = projects / "Beef Tartaar"
assert (proj / "clips").resolve() == (shoot / "1 Ruw" / "Video").resolve(), "project reads clips from the SSD"
assert (proj / "clips" / "DJI_0001.MP4").exists()
assert 'category: "food"' in (proj / "project.yaml").read_text(encoding="utf-8")

# second run: nothing new
assert offload.offload(cfg, "Beef Tartaar", "koken", cards=[card])["copied"] == 0

# a new photo with a name that is already in the shoot (another camera) → kept next to it, same shoot folder
put("DCIM/101MSDCF/DSC00001.JPG", b"other camera" * 50, day + 86400)
r = offload.offload(cfg, "beef tartaar", "koken", cards=[card])
assert r["copied"] == 1 and r["shoot"] == str(shoot) and Path(r["project"]).name == "Beef Tartaar", r
assert (shoot / "1 Ruw" / "Foto" / "DSC00001_2.JPG").read_bytes() == b"other camera" * 50

# _Inbox: no project made
put("DCIM/100MSDCF/DSC00009.JPG", b"later" * 10, day + 5 * 86400)
r = offload.offload(cfg, "Onbekend", "inbox", cards=[card])
assert r["copied"] == 1 and r["project"] is None and (lib / "_Inbox" / "2026-10-11 Onbekend" / "1 Ruw" / "Foto").is_dir(), r

# _Inbox splits an old card per recording day; the same day again goes into the same day folder
put("DCIM/100MSDCF/DSC00011.JPG", b"day a" * 10, day + 7 * 86400)
put("DCIM/100MSDCF/DSC00012.JPG", b"day b" * 10, day + 8 * 86400)
r = offload.offload(cfg, "Onbekend", "inbox", cards=[card])
assert r["copied"] == 2 and [Path(s).name for s in r["shoots"]] == ["2026-10-13 Onbekend", "2026-10-14 Onbekend"], r
put("DCIM/100MSDCF/DSC00013.JPG", b"day b again" * 10, day + 8 * 86400 + 60)
r = offload.offload(cfg, "Onbekend", "inbox", cards=[card])
assert [Path(s).name for s in r["shoots"]] == ["2026-10-14 Onbekend"], r
assert sorted(p.name for p in (lib / "_Inbox" / "2026-10-14 Onbekend" / "1 Ruw" / "Foto").iterdir()) == ["DSC00012.JPG", "DSC00013.JPG"]

# a copy that does not match the card is thrown away
bad = put("DCIM/100MSDCF/DSC00010.JPG", b"x" * 100)
real_sha1 = offload._sha1
offload._sha1 = lambda p: "0" * 40
try:
    offload.copy_checked(bad, tmp / "out.jpg")
    raise AssertionError("mismatch not detected")
except OSError:
    pass
finally:
    offload._sha1 = real_sha1
assert not (tmp / "out.jpg").exists() and not (tmp / "out.jpg.part").exists()

# names that would leave the library or projects folder are refused
for bad_name in ("..", ".", "a/b", "..\\x", ""):
    try:
        offload.offload(cfg, bad_name, "koken", cards=[card])
        raise AssertionError(f"accepted {bad_name!r}")
    except SystemExit:
        pass

shutil.rmtree(tmp)                           # junctions are removed as links, their targets are inside tmp anyway
print("offload test ok")
