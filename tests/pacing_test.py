"""Calm cutting (Timon 2026-11-06: "rustiger knippen"): on a loud 152 BPM song no shot is shorter than 2 beats,
and a cut avoids landing right on a motion peak. No Resolve needed.
usage: python tests/pacing_test.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from autoedit import config, planner                          # noqa: E402
from autoedit.analyze import ClipAnalysis, MusicAnalysis, Segment  # noqa: E402

bpm = 152.0
beat = 60 / bpm
music = MusicAnalysis("song.mp3", 40.0, bpm, [i * beat for i in range(int(40 / beat))], [], None,
                      energy=[0.85] * 160, hits=[1.58, 12.0])           # loud the whole way through
clips = [ClipAnalysis(f"C{i:04d}.MP4", 20.0, 25, 3840, 2160, 0.8, 0.1, 0.5, 0.5, False,
                      motion_peaks=[5.0, 10.0], segments=[Segment(0.5, 19.5, 0.8, 0.5, False)]) for i in range(12)]
cfg = config.load()
plan = planner.make_cinematic_plan(clips, dict(cfg.style("cinematic"), aspect="9:16"), cfg, music)
body = [s for s in plan.shots if s.clip and s.role != "black"]
short = [round(s.dur, 2) for s in body if s.dur < 2 * beat - 0.03]
assert not short, f"shots shorter than 2 beats: {short}"
assert len(body) <= 14, f"{len(body)} shots in {plan.length:.0f} s is not calm"
chopped = [s for s in body for p in (5.0, 10.0) if abs(p - s.src_in) < 0.25 or abs(p - s.src_out) < 0.25]
assert not chopped, "a cut lands right on a motion peak"
print(f"pacing test ok ({len(body)} shots, shortest {min(s.dur for s in body):.2f} s)")
