"""The same seed gives the same edit, another seed another one; the review knows 9:16 from 16:9. No Resolve needed.
usage: python tests/seed_test.py"""
import inspect
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from autoedit import builder, config, pipeline, planner, review   # noqa: E402
from autoedit.analyze import ClipAnalysis, MusicAnalysis, Segment  # noqa: E402

bpm = 120.0
beat = 60 / bpm
music = MusicAnalysis("song.mp3", 40.0, bpm, [i * beat for i in range(80)], [], None, energy=[0.6] * 160, hits=[2.0, 14.0])
clips = [ClipAnalysis(f"C{i:04d}.MP4", 20.0, 25, 3840, 2160, 0.8, 0.1, 0.5, 0.5, False,
                      segments=[Segment(0.5, 6.0, 0.8, 0.5, False), Segment(7.0, 13.0, 0.7, 0.4, False),
                                Segment(14.0, 19.5, 0.75, 0.6, False)]) for i in range(10)]
cfg = config.load()
style = dict(cfg.style("cinematic"), aspect="9:16")
make = lambda seed: planner.make_cinematic_plan(clips, style, cfg, music, seed=seed).to_json()
assert make(3) == make(3), "the same seed must give the same plan"
assert any(make(s) != make(3) for s in range(4, 10)), "another seed never changes the plan"

# the run's seed reaches the planner and the sound library (it used to reach only the director)
src = inspect.getsource(pipeline.run)
assert "seed=run_seed" in src.split("make_cinematic_plan(")[1][:200], "pipeline.run does not pass the seed to the planner"
assert "seed" in inspect.signature(builder.Builder.__init__).parameters, "Builder takes the run's seed for the sounds"
for mod in (builder, pipeline):
    assert "hash(" not in inspect.getsource(mod), f"{mod.__name__}: hash() of a string differs per run; use zlib.crc32"

assert review._aspect_of("edit_A_9x16") == "9:16" and review._aspect_of("edit_A_16x9") == "16:9"
assert review._aspect_of("edit_A") is None
print("seed test ok")
