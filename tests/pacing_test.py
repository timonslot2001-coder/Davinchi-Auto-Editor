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
assert len(body) <= plan.length / 1.5, f"{len(body)} shots in {plan.length:.0f} s is not calm"
chopped = [s for s in body for p in (5.0, 10.0) if abs(p - s.src_in) < 0.25 or abs(p - s.src_out) < 0.25]
assert not chopped, "a cut lands right on a motion peak"
print(f"pacing test ok ({len(body)} shots, shortest {min(s.dur for s in body):.2f} s)")

# ---- the brief: rhythm and length are Timon's choice (autoedit/brief.py)
from statistics import median                                  # noqa: E402
from autoedit.brief import Brief                                # noqa: E402

style = dict(cfg.style("cinematic"), aspect="9:16")
calm = planner.make_cinematic_plan(clips, style, cfg, music, brief=Brief(rhythm="rustig", length="normaal"))
cb = [s for s in calm.shots if s.clip and s.role != "black"]
assert all(s.dur >= 2 * beat - 0.03 for s in cb), "rustig: a shot under 2 beats"
assert 19 <= calm.length <= 23, f"normaal should be about 20 s, got {calm.length:.1f}"
quick = planner.make_cinematic_plan(clips, style, cfg, music, brief=Brief(rhythm="beat", length="kort"))
qb = [s for s in quick.shots if s.clip and s.role != "black"]
assert 9 <= quick.length <= 12, f"kort should be about 10 s, got {quick.length:.1f}"
assert all(s.dur >= 0.6 - 0.03 for s in qb), "beat: a shot under 0.6 s"
assert median(s.dur for s in qb[:-1]) <= 2 * beat + 0.05, "beat: shots should run about 2 beats"
assert median(s.dur for s in cb[:-1]) > median(s.dur for s in qb[:-1]), "rustig must cut slower than beat"
for p_ in (calm, quick):
    for s in [x for x in p_.shots if x.clip and x.role != "black"]:
        assert not any(abs(pk - s.src_in) < 0.25 or abs(pk - s.src_out) < 0.25 for pk in (5.0, 10.0)), "cut on a motion peak"
long_ = planner.make_cinematic_plan(clips, style, cfg, music, brief=Brief(length="lang"))
assert 28 <= long_.length <= 33, f"lang should be about 30 s, got {long_.length:.1f}"
print("brief pacing ok")
