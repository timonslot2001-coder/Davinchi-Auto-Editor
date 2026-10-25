"""Input resolver + footage analysis. Originals are never modified; results are cached per file hash."""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path

import cv2
import imageio_ffmpeg
import numpy as np

FF = imageio_ffmpeg.get_ffmpeg_exe()
VIDEO_EXT = {".mp4", ".mov", ".mxf", ".mkv", ".avi", ".m4v", ".mts"}
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff"}
AUDIO_EXT = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg"}


@dataclass
class Segment:
    """A usable stretch inside one clip (between internal scene changes)."""
    clip: str
    start: float
    end: float
    motion: float            # mean frame difference (0-255 scale)
    pan_dx: float            # dominant horizontal motion (px/frame at 160 px width), + = right
    sharp: float             # Laplacian variance (higher = sharper)
    luma: float              # mean luma 0-255
    sat: float               # mean HSV saturation
    score: float = 0.0
    tags: list = field(default_factory=list)


@dataclass
class Clip:
    path: str
    kind: str                # video | image
    width: int
    height: int
    fps: float
    duration: float
    has_audio: bool
    sha1: str
    segments: list = field(default_factory=list)


def probe(path: Path) -> dict:
    info = subprocess.run([FF, "-hide_banner", "-i", str(path)], capture_output=True, text=True, errors="replace").stderr
    dur = re.search(r"Duration: (\d+):(\d+):([\d.]+)", info)
    v = re.search(r"Video: .*?(\d{2,5})x(\d{2,5})", info)
    fps = re.search(r"([\d.]+) fps", info)
    return {"duration": (int(dur[1]) * 3600 + int(dur[2]) * 60 + float(dur[3])) if dur else 0.0,
            "width": int(v[1]) if v else 0, "height": int(v[2]) if v else 0,
            "fps": float(fps[1]) if fps else 0.0, "has_audio": "Audio:" in info}


def file_id(path: Path) -> str:
    h = hashlib.sha1()
    st = path.stat()
    h.update(f"{path.name}{st.st_size}{int(st.st_mtime)}".encode())
    with open(path, "rb") as f:
        h.update(f.read(1 << 20))
    return h.hexdigest()[:16]


def analyse_video(path: Path, meta: dict, step: float = 0.2) -> list[Segment]:
    """Sample every `step` s: motion, horizontal pan, sharpness, light; split at internal scene changes."""
    cap = cv2.VideoCapture(str(path))
    fps = meta["fps"] or cap.get(cv2.CAP_PROP_FPS) or 25
    n = int(meta["duration"] * fps)
    stride = max(1, int(round(step * fps)))
    rows, prev, prev_h = [], None, None
    for idx in range(0, max(n - 1, 1), stride):
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ok, f = cap.read()
        if not ok:
            break
        ok2, f2 = cap.read()                                 # next frame for optical flow / motion
        small = cv2.resize(f, (160, 90))
        g = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
        g2 = cv2.cvtColor(cv2.resize(f2, (160, 90)), cv2.COLOR_BGR2GRAY) if ok2 else g
        flow = cv2.calcOpticalFlowFarneback(g, g2, None, 0.5, 2, 9, 2, 5, 1.1, 0)
        hist = cv2.calcHist([small], [0, 1, 2], None, [8, 8, 8], [0, 256] * 3).flatten()
        hist /= hist.sum() + 1e-9
        cut = prev_h is not None and 0.5 * np.abs(hist - prev_h).sum() > 0.45
        hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)
        rows.append({"t": idx / fps, "motion": float(np.abs(g2.astype(np.float32) - g).mean()),
                     "dx": float(np.median(flow[..., 0])), "sharp": float(cv2.Laplacian(cv2.cvtColor(cv2.resize(f, (640, int(640 * f.shape[0] / f.shape[1]))), cv2.COLOR_BGR2GRAY), cv2.CV_32F).var()),  # same scale for 4K and HD
                     "luma": float(g.mean()), "sat": float(hsv[..., 1].mean()), "cut": cut})
        prev, prev_h = g, hist
    segs, cur = [], []
    for r in rows + [{"cut": True, "t": meta["duration"]}]:
        if cur and not r["cut"] and r["t"] - cur[0]["t"] >= 3.2 and meta["duration"] - r["t"] >= 1.2:
            r = {**r, "cut": True}                           # split long takes into ~3 s windows (variety + per-window scores)
        if r["cut"] and cur:
            a, b = cur[0]["t"], r["t"]
            if b - a >= 0.4:
                segs.append(Segment(str(path), round(a, 3), round(b, 3),
                                    motion=round(float(np.mean([x["motion"] for x in cur])), 2),
                                    pan_dx=round(float(np.mean([x["dx"] for x in cur])), 2),
                                    sharp=round(float(np.median([x["sharp"] for x in cur])), 1),
                                    luma=round(float(np.mean([x["luma"] for x in cur])), 1),
                                    sat=round(float(np.mean([x["sat"] for x in cur])), 1)))
            cur = []
        if "motion" in r:
            cur.append(r)
    return segs


def tag(seg: Segment, sharp_ref: float) -> Segment:
    """Heuristic roles used by the planner (documented, not reference evidence)."""
    t = []
    if abs(seg.pan_dx) > 1.2 or seg.motion > 9:
        t.append("motion")
    if seg.motion < 3.5:
        t.append("static")
    if seg.end - seg.start >= 2.5 and seg.motion < 7:
        t.append("establishing")
    if seg.sharp > sharp_ref * 1.3:
        t.append("detail")
    if seg.luma < 45:
        t.append("dark")
    if seg.sharp < sharp_ref * 0.25:
        t.append("soft")
    seg.tags = t
    # quality score: sharp, well exposed, not too dark/bright, some life
    expo = 1 - min(abs(seg.luma - 110) / 110, 1)
    seg.score = round(0.45 * min(seg.sharp / (sharp_ref + 1e-6), 2) / 2 + 0.35 * expo + 0.2 * min(seg.motion / 12, 1), 3)
    return seg


def inventory(project: Path, cache_dir: Path) -> dict:
    """Scan <project>/clips (+ photos/, music/). Returns a JSON-able dict and writes cache_dir/inventory.json."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_f = cache_dir / "inventory.json"
    cache = json.loads(cache_f.read_text(encoding="utf-8")) if cache_f.exists() else {"clips": {}}
    clips, problems = [], []
    for folder in ("clips", "photos"):
        for p in sorted((project / folder).glob("*")) if (project / folder).exists() else []:
            ext = p.suffix.lower()
            if ext not in VIDEO_EXT | IMAGE_EXT:
                continue
            fid = file_id(p)
            if fid in cache["clips"]:
                clips.append(cache["clips"][fid])
                continue
            if ext in IMAGE_EXT:
                im = cv2.imread(str(p))
                if im is None:
                    problems.append(f"unreadable image {p.name}")
                    continue
                c = Clip(str(p), "image", im.shape[1], im.shape[0], 0, 0, False, fid)
            else:
                meta = probe(p)
                if meta["duration"] < 0.3 or not meta["width"]:
                    problems.append(f"unusable video {p.name}: {meta}")
                    continue
                c = Clip(str(p), "video", meta["width"], meta["height"], meta["fps"], round(meta["duration"], 3),
                         meta["has_audio"], fid, analyse_video(p, meta))
            d = asdict(c)
            cache["clips"][fid] = d
            clips.append(d)
    sharp_ref = float(np.median([s["sharp"] for c in clips for s in c["segments"]] or [1]))
    for c in clips:
        c["segments"] = [asdict(tag(Segment(**s), sharp_ref)) for s in c["segments"]]
    music = sorted(p for p in (project / "music").glob("*") if p.suffix.lower() in AUDIO_EXT) if (project / "music").exists() else []
    inv = {"project": str(project), "clips": clips, "music": [str(m) for m in music], "problems": problems,
           "sharp_ref": sharp_ref}
    cache_f.write_text(json.dumps(cache, indent=1), encoding="utf-8")
    (cache_dir / "inventory_view.json").write_text(json.dumps(inv, indent=1), encoding="utf-8")
    return inv


def music_map(path: Path, cache_dir: Path) -> dict:
    """Tempo, beats, strong onsets and an energy envelope of the song (librosa)."""
    import librosa
    out = cache_dir / f"music_{file_id(path)}.json"
    if out.exists():
        return json.loads(out.read_text(encoding="utf-8"))
    raw = subprocess.run([FF, "-v", "error", "-i", str(path), "-ac", "1", "-ar", "22050", "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    y = np.frombuffer(raw, np.float32)
    tempo, beats = librosa.beat.beat_track(y=y, sr=22050)
    env = librosa.onset.onset_strength(y=y, sr=22050)
    on = librosa.onset.onset_detect(onset_envelope=env, sr=22050)
    strong = on[env[on] > np.percentile(env, 90)]
    rms = librosa.feature.rms(y=y, hop_length=2205)[0]                         # 10 Hz energy
    d = {"path": str(path), "duration": round(len(y) / 22050, 3), "tempo": float(np.atleast_1d(tempo)[0]),
         "beats": [round(float(b), 3) for b in librosa.frames_to_time(beats, sr=22050)],
         "strong_onsets": [round(float(t), 3) for t in librosa.frames_to_time(strong, sr=22050)],
         "energy_10hz": [round(float(v), 4) for v in rms]}
    out.write_text(json.dumps(d), encoding="utf-8")
    return d
