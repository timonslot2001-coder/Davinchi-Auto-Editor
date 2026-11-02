"""Preview material for the Artifact grade picker: ungraded stills + the two LUT stages. Runs on the PC only (numpy,
cv2, the engine); `webapp.studio` imports it lazily. Nothing here touches the network; the Studio session uploads the files.

The page does the same maths as the render (autoedit/grade.py build_lut), in two stages so look/strength/exposure
stay live sliders:  x' = clamp(x + exposure*0.0769)  (log stills only)  ->  c = conv(x')  (log only)
                    ->  o = look(c)  ->  out = c + (o - c)*strength."""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CONV = "SLog3SGamut3.CineToLC-709TypeA.cube"                     # same default as grade.build_lut
WIDTH = 1280


def _imports():
    for p in (REPO, REPO / "VIDEO_EDITING_SYSTEM"):
        if str(p) not in sys.path:
            sys.path.insert(0, str(p))
    from autoedit import grade
    from engine import gradechoice, media, render
    return grade, gradechoice, media, render


def _duration(clip: Path) -> float:
    import cv2
    cap = cv2.VideoCapture(str(clip))
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    n = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0
    cap.release()
    return n / fps if n else 0.0


def _spread(items: list, n: int) -> list:
    if len(items) <= n:
        return list(items)
    return [items[int((i + 0.5) * len(items) / n)] for i in range(n)]


def _from_plan(project: Path, n: int) -> list[tuple[Path, float]]:
    import json
    f = project / "cine_montage" / "edl.json"
    if not f.exists():
        return []
    try:
        events = json.loads(f.read_text(encoding="utf-8")).get("events", [])
    except (OSError, ValueError):
        return []
    ok = [e for e in events if e.get("source") and Path(e["source"]).exists()]
    if not ok:
        return []
    picked = ok[:1] + _spread(ok[1:], n - 1)                     # the title event, then body events spread over the plan
    out = []
    for e in picked:
        length = max(0.0, float(e.get("out_out", 0)) - float(e.get("out_in", 0)))
        out.append((Path(e["source"]), float(e.get("src_in", 0)) + length / 2))
    return out


def _from_clips(project: Path, n: int, video_ext) -> list[tuple[Path, float]]:
    clips = sorted(c for c in (project / "clips").glob("*") if c.suffix.lower() in video_ext) \
        if (project / "clips").is_dir() else []
    if not clips:
        return []
    shots = [(c, d) for c in clips if (d := _duration(c)) > 0] or [(c, 0.0) for c in clips]
    out = []
    for i in range(n):                                           # n spots spread over the clips, each at a different time
        c, d = shots[int((i + 0.5) * len(shots) / n)]
        k = sum(1 for j in range(n) if int((j + 0.5) * len(shots) / n) == int((i + 0.5) * len(shots) / n))
        rank = sum(1 for j in range(i) if int((j + 0.5) * len(shots) / n) == int((i + 0.5) * len(shots) / n))
        out.append((c, d * (rank + 0.5) / k))
    return out


def export(project: Path, out_dir: Path, n: int = 4) -> dict:
    grade, gradechoice, media, render = _imports()
    project, out_dir = Path(project), Path(out_dir)
    picks = _from_plan(project, n) or _from_clips(project, n, media.VIDEO_EXT)
    if not picks:
        raise ValueError("geen beeld gevonden: zet clips in de map clips van het project of maak eerst een plan")
    out_dir.mkdir(parents=True, exist_ok=True)
    stills = []
    for i, (clip, t) in enumerate(picks):
        name = f"still_{i}.png"
        r = subprocess.run([media.FF, "-y", "-v", "error", "-ss", f"{max(t, 0):.3f}", "-i", str(clip), "-frames:v", "1",
                            "-vf", f"scale={WIDTH}:-2", str(out_dir / name)], capture_output=True)
        if r.returncode or not (out_dir / name).exists():
            raise ValueError(f"kon geen still maken van {clip.name}")
        stills.append({"file": name, "is_log": bool(render.detect_log(str(clip))),
                       "label": f"{clip.name} {int(t // 60)}:{t % 60:04.1f}"})
    conv = None
    src = Path(grade.SONY) / CONV
    if any(s["is_log"] for s in stills) and src.exists():
        shutil.copyfile(src, out_dir / "conv.cube")
        conv = "conv.cube"
    looks = {}
    for look in gradechoice.LOOKS:
        grade.write_cube(out_dir / f"look_{look}.cube", grade.look_lut(look, 33), f"AutoEdit {look}")
        looks[look] = f"look_{look}.cube"
    return {"stills": stills, "conv": conv, "looks": looks,
            "previews": previews(out_dir, [(out_dir / s["file"], s["is_log"]) for s in stills])}


def previews(out_dir: Path, stills: list[tuple[Path, bool]], width: int = 480) -> dict[str, str]:
    """One finished picture per look: the stills side by side, graded exactly like the render (house exposure -1.75
    stops and the Sony conversion for S-Log3 stills, the look at full strength). Timon taps the one he likes; nothing
    is computed in the browser. Returns {look: file name in out_dir}."""
    import cv2
    import numpy as np
    grade, gradechoice, _, _ = _imports()
    src = []
    for f, is_log in stills:
        img = cv2.imread(str(f), cv2.IMREAD_COLOR)
        if img is None:
            continue
        h = round(img.shape[0] * width / img.shape[1])
        src.append((cv2.resize(img, (width, h), interpolation=cv2.INTER_AREA)[:, :, ::-1] / 255.0, is_log))
    if not src:
        return {}
    h = min(i.shape[0] for i, _ in src)
    out = {}
    for look in gradechoice.LOOKS:
        lut_log = grade.read_cube(grade.build_lut(look, 1.0, -1.75))[0] if any(l for _, l in src) else None
        lut_709 = grade.read_cube(grade.build_lut(look, 1.0, 0.0, conversion=None))[0]
        tiles = []
        for img, is_log in src:
            g = grade.apply_cube(lut_log if is_log else lut_709, img[:h])
            tiles += [g, np.zeros((h, 6, 3))]
        strip = (np.clip(np.hstack(tiles[:-1]), 0, 1) * 255).astype(np.uint8)[:, :, ::-1]
        name = f"preview_{look}.jpg"
        cv2.imwrite(str(out_dir / name), strip, [cv2.IMWRITE_JPEG_QUALITY, 85])
        out[look] = name
    return out
