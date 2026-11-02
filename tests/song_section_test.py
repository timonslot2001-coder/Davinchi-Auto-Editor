"""The editor picks the song section itself (engine planner.best_song_start): the drop lands about two thirds in.
usage: python tests/song_section_test.py"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "VIDEO_EDITING_SYSTEM"))
from engine import planner                   # noqa: E402

# 120 s song at 120 BPM: calm intro, a build from 40 s, a drop at 60 s, loud to 90 s, calm outro
t = np.arange(0, 120, 0.1)
energy = np.where(t < 40, 0.2, np.where(t < 60, 0.2 + 0.2 * (t - 40) / 20, np.where(t < 90, 1.0, 0.3)))
music = {"duration": 120.0, "tempo": 120.0, "beats": [round(b, 3) for b in np.arange(0.0, 120.0, 0.5)],
         "strong_onsets": [], "energy_10hz": [round(float(v), 4) for v in energy]}
for length in (12.0, 18.0, 24.0):
    s = planner.best_song_start(music, length)
    pos = (60.0 - s) / length
    assert 0.45 <= pos <= 0.85, (length, s, pos)
    assert s % 2.0 == 0.0, f"starts on a bar (every 4th beat): {s}"
assert planner.best_song_start({"duration": 5.0, "beats": [], "energy_10hz": []}, 18.0) == 0.0, "too little data: start"
print("song section test ok")
