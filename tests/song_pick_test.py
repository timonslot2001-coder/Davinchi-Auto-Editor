"""The website sends the song as its full file name ('ESCAPE PLAN.mp3'); a part of the name ('escape') also works.
usage: python tests/song_pick_test.py"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "VIDEO_EDITING_SYSTEM"))
from engine import media                     # noqa: E402

with tempfile.TemporaryDirectory() as d:
    project = Path(d)
    song = project / "music" / "ESCAPE PLAN.mp3"
    song.parent.mkdir()
    song.write_bytes(b"")
    inv = {"music": [str(song)]}
    for choice in ("ESCAPE PLAN.mp3", "escape plan.MP3", "escape"):
        assert media.pick_song(project, inv, choice)[0] == song, choice
    try:
        media.pick_song(project, inv, "other.mp3")
        raise AssertionError("an unknown song must stop the plan")
    except SystemExit:
        pass
print("song pick test ok")
