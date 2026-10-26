"""Gate C test for T_GRID_FLOW on real footage: six shots of an existing planned project joined by Grid Flow variants.
Writes <project>/cine_montage/tests/gridflow_test.mp4 (+ a frame strip). Not a final export.
usage: python tests/gridflow_test.py "<project dir>" """
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from engine.edl import EDL, Event            # noqa: E402
from engine import render                    # noqa: E402

VARIANTS = [                                  # (label, params) — first one = the .drfx defaults (4x4, wipe left, exposure)
    ("4x4 wipe left, exposure flash (default)", {}),
    ("4x4 diagonal, exposure flash", {"direction": "diag_down_right"}),
    ("5x5 random", {"grid": 5, "direction": "random", "seed": 3}),
    ("3x3 centre out, white flash", {"grid": 3, "direction": "centre_out", "flash": "white"}),
    ("4x4 spiral, no grid lines", {"direction": "spiral", "show_grid": False}),
]
SHOT, TRANS = 1.4, 12                         # seconds per shot, transition frames (0.48 s at 25 fps)

project = Path(sys.argv[1])
base = EDL.load(project / "cine_montage" / "edl.json")
seen, picks = set(), []
for e in base.events:                         # one shot per real clip first, then fill
    if "AI_" not in Path(e.source).name and e.source not in seen and not e.treatment:
        seen.add(e.source)
        picks.append(e)
picks += [e for e in base.events if "AI_" not in Path(e.source).name and e not in picks and not e.treatment]
picks = picks[:len(VARIANTS) + 1]

events, t = [], 0.0
for i, e in enumerate(picks):
    ev = Event(f"G{i:02d}", round(t, 3), round(t + SHOT, 3), e.source, e.src_in, e.src_in + SHOT,
               "T_GRID_FLOW" if i else "T_HARD")
    if i:
        ev.params = {"grid_flow_frames": TRANS, "grid_flow": VARIANTS[i - 1][1], "label": VARIANTS[i - 1][0]}
    events.append(ev)
    t += SHOT
edl = EDL(**{**base.__dict__, "events": events, "overlays": [], "duration": round(t, 3), "notes": ["gridflow test"]})
out_dir = project / "cine_montage" / "tests"
out = out_dir / "gridflow_test.mp4"
res = render.render(edl, out, out_dir / "work")
print(res["out"], res["frames"], "frames")
for ev in events[1:]:
    print(f"  {ev.out_in:5.2f}s  {ev.params['label']}")

# frame strip through the first transition (default variant)
cap = cv2.VideoCapture(str(out))
f0 = int(round(events[1].out_in * edl.fps))
tiles = []
for k in range(0, TRANS, 2):
    cap.set(cv2.CAP_PROP_POS_FRAMES, f0 + k)
    ok, f = cap.read()
    tiles.append(cv2.resize(f, (480, 270)))
cv2.imwrite(str(out_dir / "gridflow_strip.jpg"), np.hstack(tiles))
