"""/flow pieces without Resolve: captions are burnt into a video (ASS, house font) and the Orange & Teal look exists.
usage: python tests/flow_test.py"""
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from autoedit import export, grade          # noqa: E402

assert "orange_teal" in grade.LOOKS and grade.LOOKS["orange_teal"]
assert export._ass_time(3661.5) == "1:01:01.50" and export._ass_time(-1) == "0:00:00.00"
tmp = Path(tempfile.mkdtemp())
src = tmp / "in.mp4"
subprocess.run([export.FFMPEG, "-v", "error", "-f", "lavfi", "-i", "color=c=black:s=270x480:d=2", "-f", "lavfi",
                "-i", "anullsrc=r=48000:cl=stereo", "-t", "2", "-shortest", "-c:v", "libx264", "-c:a", "aac", str(src)],
               check=True)
out = export.burn_captions(src, [(0.2, 1.8, "Hallo {wereld}")], tmp / "out.mp4")
assert out.exists() and "Hallo (wereld)" in (tmp / "out.ass").read_text(encoding="utf-8"), "braces can't break ASS"
frame = subprocess.run([export.FFMPEG, "-v", "error", "-ss", "1", "-i", str(out), "-frames:v", "1", "-f", "rawvideo",
                        "-pix_fmt", "gray", "-"], capture_output=True).stdout
assert max(frame) > 200, "white caption pixels on the black frame"
long = export.burn_captions(src, [(0.2, 1.8, "jefeed aan de achterkant van de hele lange zin hier")], tmp / "long.mp4")
assert "\\N" in (tmp / "long.ass").read_text(encoding="utf-8"), "long lines are broken by us, not run off the edge"
print("flow test ok")
