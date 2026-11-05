"""Self-review: rewatch + relisten to the rendered video and judge it against the budget and your taste.

Checks (all measured on the final file):
  - accent density and stacking (too much eye candy / effects on consecutive shots)
  - every SFX: does it jump out above the music (too loud) or vanish (inaudible)?
  - black/flash frames, black start/end, a real final hold
Fixable issues come back as 'fixes' (knob changes) so the pipeline can rebuild once.
Also writes a contact sheet of every accent for a visual check (Claude looks at it).
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import numpy as np

from .analyze import FFMPEG
from .director import load_inventory, load_taste
from .export import qc
from .planner import Plan


def _momentary(path: Path) -> tuple[np.ndarray, np.ndarray]:
    err = subprocess.run([FFMPEG, "-hide_banner", "-i", str(path), "-vn", "-af", "ebur128=framelog=verbose",
                          "-f", "null", "-"], capture_output=True, text=True, errors="replace").stderr
    rows = re.findall(r"t:\s*([\d.]+)\s+TARGET:.*?M:\s*(-?[\d.]+|-inf)", err)
    t = np.array([float(a) for a, _ in rows])
    m = np.array([float(b) if b != "-inf" else -70.0 for _, b in rows])
    return t, m


def before_after(plan: Plan, video: Path, out: Path) -> Path:
    """One picture: the raw first shot of the edit (as it came out of the camera) next to the same moment of the finished
    video, labelled Before / After."""
    import cv2
    s = next((s for s in plan.shots if Path(s.clip).exists()), None)
    if s is None:
        raise FileNotFoundError("no source clip for the before picture")
    t_src, t_out = (s.src_in + s.src_out) / 2, s.rec_in + (s.src_out - s.src_in) / 2

    def grab(path, t):
        r = subprocess.run([FFMPEG, "-v", "error", "-ss", f"{t:.2f}", "-i", str(path), "-frames:v", "1", "-vf",
                            "scale=-2:720,format=bgr24", "-f", "rawvideo", "-"], capture_output=True)
        w = len(r.stdout) // (720 * 3)
        return np.frombuffer(r.stdout, np.uint8)[:720 * w * 3].reshape(720, w, 3).copy()
    before, after = grab(s.clip, t_src), grab(video, t_out)
    if before.shape[1] > after.shape[1]:                          # same framing: the centre of the wide camera frame
        x = (before.shape[1] - after.shape[1]) // 2
        before = np.ascontiguousarray(before[:, x:x + after.shape[1]])
    for img, label in ((before, "Before"), (after, "After")):
        cv2.putText(img, label, (24, 690), cv2.FONT_HERSHEY_DUPLEX, 1.6, (0, 0, 0), 6)
        cv2.putText(img, label, (24, 690), cv2.FONT_HERSHEY_DUPLEX, 1.6, (255, 255, 255), 2)
    gap = np.full((720, 16, 3), 20, np.uint8)
    cv2.imwrite(str(out), np.hstack([before, gap, after]), [cv2.IMWRITE_JPEG_QUALITY, 88])
    return out


def review(video: Path, plan: Plan, out_dir: Path, base: str) -> dict:
    inv, taste = load_inventory(), load_taste()
    budget = inv["budget"]
    issues, fixes, good = [], {}, []

    # ---- eye candy density / stacking
    # a photo series (several shots in a row) is one accent, not three
    accents = [s for i, s in enumerate(plan.shots) if (s.effects or not s.clip)
               and not (s.extra.get("series") and i > 0 and plan.shots[i - 1].extra.get("series"))]
    ov_acc = [o for o in getattr(plan, "overlays", []) if not o.get("ambient") and o.get("why") != "light_leak"]
    per10 = (len(accents) + len(ov_acc)) / max(plan.length, 1) * 10
    allowed = budget["accents_per_10s"] * (taste.get("knobs", {}) or {}).get("accents_scale", 1.0)
    if per10 > allowed * 1.15:
        issues.append(f"too much eye candy: {per10:.1f} accents/10s (budget {allowed:.1f})")
        fixes["accents_scale"] = round(allowed / per10 * 0.95, 2)
    else:
        good.append(f"accent density ok ({per10:.1f}/10s)")
    run = best = 0
    for i, s in enumerate(plan.shots):
        in_series = s.extra.get("series") and i > 0 and plan.shots[i - 1].extra.get("series")
        run = run if in_series else (run + 1 if s.effects else 0)
        best = max(best, run)
    if best >= 3:
        issues.append(f"{best} shots in a row with effects — feels overdone")
        fixes["accents_scale"] = min(fixes.get("accents_scale", 1.0), 0.8)

    # ---- ear candy: each SFX relative to the music around it
    t, m = _momentary(video)
    loud, quiet = [], []
    for ev in plan.sfx:
        if t.size == 0:
            break
        win = (t >= ev["t"]) & (t <= ev["t"] + 0.5)
        ctx = (t >= ev["t"] - 1.6) & (t <= ev["t"] - 0.2)
        if not win.any() or not ctx.any():
            continue
        delta = m[win].max() - np.median(m[ctx])
        if delta > 6.0:
            loud.append(f"{ev['t']:.2f}s {ev['cat']} (+{delta:.1f} LU)")
        elif delta < 0.3 and ev.get("why") not in ("bw", "title"):
            quiet.append(f"{ev['t']:.2f}s {ev['cat']}")
    if loud:
        issues.append("SFX jumps out above the music: " + ", ".join(loud))
        fixes["sfx_level_db"] = -3
    if quiet and len(quiet) > len(plan.sfx) / 2:
        issues.append("most SFX are inaudible under the music: " + ", ".join(quiet))
        fixes["sfx_level_db"] = fixes.get("sfx_level_db", 0) + 3
    if not loud and plan.sfx:
        good.append(f"{len(plan.sfx)} sounds sit inside the mix")

    # ---- slow motion must be smooth: look for repeated or near-identical frames inside the slowed part
    import cv2
    cap = cv2.VideoCapture(str(video))
    vfps = cap.get(5) or plan.fps
    for s in plan.shots:
        if "speed_ramp" not in s.effects or s.speed_ramp is None:
            continue
        src = cv2.VideoCapture(s.clip)
        src_fps = src.get(5) or 0
        src.release()
        if src_fps < 1.9 * plan.fps:
            # cause, not symptom: slowing down footage without enough real frames always looks choppy/ghosty
            issues.append(f"slow-mo at {s.rec_in:.2f}s is on {src_fps:.0f}p footage — can't be smooth, drop it")
            fixes["drop_speed_ramp"] = True
            continue
        a = s.rec_in + max(0.0, s.speed_ramp - 0.3)
        # frame strip of the slowed part, for the visual check
        strip = out_dir / f"{base}_slowmo_{s.rec_in:.2f}.png"
        subprocess.run([FFMPEG, "-y", "-v", "error", "-ss", f"{a:.2f}", "-t", "0.8", "-i", str(video),
                        "-vf", "scale=160:-2,tile=10x2", "-frames:v", "1", str(strip)])
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(a * vfps))
        prev, diffs = None, []
        for _ in range(int(0.8 * vfps)):
            ok, fr = cap.read()
            if not ok:
                break
            g = cv2.cvtColor(cv2.resize(fr, (192, 108)), cv2.COLOR_BGR2GRAY).astype(np.float32)
            if prev is not None:
                diffs.append(float(np.abs(g - prev).mean()))
            prev = g
        if diffs:
            med = np.median(diffs) + 1e-6
            stutter = sum(d < 0.25 * med for d in diffs) / len(diffs)
            if stutter > 0.15:
                issues.append(f"slow-mo at {s.rec_in:.2f}s stutters ({stutter:.0%} repeated frames) — drop it")
                fixes["drop_speed_ramp"] = True
            else:
                good.append(f"slow-mo at {s.rec_in:.2f}s is smooth")
    cap.release()

    # ---- picture problems
    expect = (1920, 1080) if plan.shots and plan.length and "16" in base else None
    q = qc(video, expect or (1080, 1920))
    issues += [p for p in q.problems if not p.startswith("resolution")]
    if q.black_segments and q.black_segments[0][0] < 0.05:
        issues.append("video starts on black")
    if q.black_segments and abs(q.black_segments[-1][1] - q.duration) < 0.1:
        issues.append("video ends on black")
    if plan.shots and plan.shots[-1].dur < 1.0:
        issues.append("no real final hold (last shot < 1 s)")

    # ---- contact sheet of every accent (for the visual check)
    times = sorted({round(s.rec_in + min(0.12, s.dur / 2), 2) for s in plan.shots if s.effects}
                   | {round(o.get("at", o["t"]) + 0.1, 2) for o in getattr(plan, "overlays", []) if not o.get("ambient")}) or [0.5]
    sheet = out_dir / f"{base}_review.png"
    vf = "scale=240:-2,tile={}x1".format(min(10, len(times)))
    inputs = []
    for tt in times[:10]:
        inputs += ["-ss", f"{tt}", "-i", str(video)]
    if inputs:
        n = len(times[:10])
        fc = "".join(f"[{i}:v]scale=240:-2,setsar=1[v{i}];" for i in range(n)) + "".join(f"[v{i}]" for i in range(n)) + f"hstack=inputs={n}" if n > 1 else "scale=240:-2"
        subprocess.run([FFMPEG, "-y", "-v", "error", *inputs, "-frames:v", "1",
                        *(["-filter_complex", fc] if n > 1 else ["-vf", fc]), str(sheet)])

    report = {"video": str(video), "ok": not issues, "issues": issues, "good": good, "fixes": fixes,
              "accents": [{"t": s.rec_in, "fx": s.effects} for s in plan.shots if s.effects]
                         + [{"t": o.get("at", o["t"]), "overlay": o["why"], "file": Path(o["path"]).name}
                            for o in getattr(plan, "overlays", []) if not o.get("ambient")],
              "sfx": plan.sfx, "contact_sheet": str(sheet)}
    (out_dir / f"{base}_review.json").write_text(json.dumps(report, indent=1, ensure_ascii=False))
    return report
