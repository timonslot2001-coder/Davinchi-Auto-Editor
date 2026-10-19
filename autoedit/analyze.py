"""Clip and music analysis: what is good footage, where are the beats, where is the silence.

Everything runs locally with ffmpeg + OpenCV + librosa; results are cached in data/analysis/.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

import cv2
import imageio_ffmpeg
import numpy as np

from .config import DATA

FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
CACHE = DATA / "analysis"
CACHE.mkdir(exist_ok=True)
VIDEO_EXT = {".mp4", ".mov", ".mxf", ".m4v", ".avi", ".mkv", ".braw"}
AUDIO_EXT = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg"}

SAMPLE_FPS = 5
W, H = 320, 180
# OpenCV 5 moved Haar cascades out of the main package; face boost is optional
_face = (cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
         if hasattr(cv2, "CascadeClassifier") else None)


@dataclass
class Segment:
    start: float            # seconds in the source clip
    end: float
    score: float
    motion: float
    face: bool

    @property
    def length(self) -> float:
        return self.end - self.start


@dataclass
class ClipAnalysis:
    path: str
    duration: float
    fps: float
    width: int
    height: int
    sharpness: float        # 0..1 (relative across the clip)
    shake: float            # 0..1, high = shaky → stabilize
    brightness: float       # 0..1
    motion: float           # 0..1
    has_speech: bool
    scene_cuts: list[float] = field(default_factory=list)
    silences: list[list[float]] = field(default_factory=list)   # [[start, end], ...]
    per_second: list[float] = field(default_factory=list)       # quality score per second
    motion_peaks: list[float] = field(default_factory=list)     # moments for speed ramps
    segments: list[Segment] = field(default_factory=list)
    rejected_reason: str | None = None

    @property
    def name(self) -> str:
        return Path(self.path).name


# ---------------------------------------------------------------- helpers

def _key(path: Path) -> str:
    st = path.stat()
    return hashlib.sha1(f"{path.resolve()}|{st.st_size}|{st.st_mtime_ns}|v4".encode()).hexdigest()[:16]


def _probe(path: Path) -> tuple[float, float, int, int]:
    cap = cv2.VideoCapture(str(path))
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    n = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()
    return (n / fps if n else 0.0), fps, w, h


def _frames(path: Path):
    """Yield downscaled RGB frames at SAMPLE_FPS via ffmpeg (fast, handles 10-bit Sony footage)."""
    cmd = [FFMPEG, "-v", "error", "-i", str(path), "-vf",
           f"fps={SAMPLE_FPS},scale={W}:{H}:flags=area", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    size = W * H * 3
    try:
        while True:
            buf = proc.stdout.read(size)
            if len(buf) < size:
                break
            yield np.frombuffer(buf, np.uint8).reshape(H, W, 3)
    finally:
        proc.stdout.close()
        proc.wait()


def load_audio(path: Path, sr: int = 22050) -> np.ndarray:
    cmd = [FFMPEG, "-v", "error", "-i", str(path), "-vn", "-ac", "1", "-ar", str(sr), "-f", "f32le", "-"]
    out = subprocess.run(cmd, capture_output=True).stdout
    return np.frombuffer(out, np.float32)


def _norm(x: np.ndarray) -> np.ndarray:
    if x.size == 0:
        return x
    lo, hi = np.percentile(x, 5), np.percentile(x, 95)
    return np.clip((x - lo) / (hi - lo + 1e-9), 0, 1)


def _silences(audio: np.ndarray, sr: int, min_len: float = 0.35) -> tuple[list[list[float]], bool]:
    if audio.size < sr // 2:
        return [], False
    hop = sr // 20
    frames = audio[: len(audio) // hop * hop].reshape(-1, hop)
    rms = np.sqrt((frames ** 2).mean(axis=1) + 1e-12)
    db = 20 * np.log10(rms)
    thresh = max(np.percentile(db, 20) + 6, -50)
    quiet = db < thresh
    out, start = [], None
    for i, q in enumerate(quiet):
        t = i * hop / sr
        if q and start is None:
            start = t
        elif not q and start is not None:
            if t - start >= min_len:
                out.append([round(start, 2), round(t, 2)])
            start = None
    if start is not None and len(quiet) * hop / sr - start >= min_len:
        out.append([round(start, 2), round(len(quiet) * hop / sr, 2)])
    # crude speech detection: energy concentrated in the voice band, with pauses in between
    spec = np.abs(np.fft.rfft(audio[: sr * 20]))
    freqs = np.fft.rfftfreq(min(len(audio), sr * 20), 1 / sr)
    voice = spec[(freqs > 250) & (freqs < 3500)].sum() / (spec.sum() + 1e-9)
    has_speech = voice > 0.55 and 0.1 < quiet.mean() < 0.7
    return out, bool(has_speech)


# ---------------------------------------------------------------- clips

def analyze_clip(path: str | Path, force: bool = False) -> ClipAnalysis:
    path = Path(path)
    cache = CACHE / f"{_key(path)}.json"
    if cache.exists() and not force:
        d = json.loads(cache.read_text())
        d["segments"] = [Segment(**s) for s in d["segments"]]
        return ClipAnalysis(**d)

    duration, fps, w, h = _probe(path)
    sharp, bright, motion, color, faces, cuts, dx, dy = [], [], [], [], [], [], [], []
    prev_gray, prev_hist = None, None
    for i, rgb in enumerate(_frames(path)):
        gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
        sharp.append(cv2.Laplacian(gray, cv2.CV_32F).var())
        bright.append(gray.mean() / 255)
        rg = rgb[..., 0].astype(np.float32) - rgb[..., 1]
        yb = 0.5 * (rgb[..., 0].astype(np.float32) + rgb[..., 1]) - rgb[..., 2]
        color.append(np.hypot(rg.std(), yb.std()))
        if i % SAMPLE_FPS == 0 and _face is not None:
            faces.append(len(_face.detectMultiScale(gray, 1.2, 5, minSize=(24, 24))) > 0)
        hist = cv2.calcHist([gray], [0], None, [32], [0, 256]).ravel()
        hist /= hist.sum() + 1e-9
        if prev_gray is not None:
            motion.append(float(np.abs(gray.astype(np.int16) - prev_gray).mean()))
            (sx, sy), _ = cv2.phaseCorrelate(np.float32(prev_gray), np.float32(gray))
            dx.append(sx)
            dy.append(sy)
            if 0.5 * np.abs(hist - prev_hist).sum() > 0.45:
                cuts.append(round(i / SAMPLE_FPS, 2))
        else:
            motion.append(0.0)
        prev_gray, prev_hist = gray.astype(np.int16), hist

    n = len(sharp)
    if n == 0:
        return ClipAnalysis(str(path), duration, fps, w, h, 0, 0, 0, 0, False, rejected_reason="unreadable")
    if not duration:
        duration = n / SAMPLE_FPS

    # shake = high-frequency jitter of the camera translation (handheld wobble vs. a smooth pan)
    shake = 0.0
    if len(dx) > 6:
        path_xy = np.cumsum(np.c_[dx, dy], axis=0)
        k = np.ones(SAMPLE_FPS) / SAMPLE_FPS
        smooth = np.c_[np.convolve(path_xy[:, 0], k, "same"), np.convolve(path_xy[:, 1], k, "same")]
        jitter = np.linalg.norm(path_xy - smooth, axis=1)[SAMPLE_FPS:-SAMPLE_FPS]
        # calibrated on Sony test shots: ~0.5 px = tripod, ~9 px = heavy handheld (at 320 px width)
        shake = float(np.clip(np.median(jitter) / 10.0, 0, 1)) if jitter.size else 0.0

    sharp_a, bright_a, motion_a, color_a = map(np.asarray, (sharp, bright, motion, color))
    exposure_ok = 1 - np.clip(np.abs(bright_a - 0.45) / 0.45, 0, 1)
    frame_score = 0.40 * _norm(sharp_a) + 0.25 * _norm(motion_a) + 0.20 * _norm(color_a) + 0.15 * exposure_ok
    secs = int(np.ceil(n / SAMPLE_FPS))
    per_second = [float(frame_score[s * SAMPLE_FPS:(s + 1) * SAMPLE_FPS].mean()) for s in range(secs)]
    face_sec = [bool(faces[s]) if s < len(faces) else False for s in range(secs)]
    for s in range(secs):
        if face_sec[s]:
            per_second[s] = min(1.0, per_second[s] + 0.1)

    # motion peaks (jump, spin, rep) → candidates for speed ramps
    m = _norm(motion_a)
    peaks = [round(i / SAMPLE_FPS, 2) for i in range(2, len(m) - 2)
             if m[i] > 0.85 and m[i] == m[i - 2:i + 3].max()]

    audio = load_audio(path)
    silences, speech = _silences(audio, 22050)

    # segments: cut at scene cuts, then rank windows of 1–3 s
    bounds = [0.0] + [c for c in cuts if 0.3 < c < duration - 0.3] + [duration]
    segments = []
    for a, b in zip(bounds, bounds[1:]):
        t = a + 0.2                              # skip the first frames (camera settling)
        while t + 1.0 <= b - 0.1:
            e = min(t + 3.0, b - 0.1)
            s0, s1 = int(t), max(int(t) + 1, int(np.ceil(e)))
            sc = float(np.mean(per_second[s0:s1]))
            win = m[int(t * SAMPLE_FPS):int(e * SAMPLE_FPS)]
            mo = float(win.mean()) if win.size else 0.0
            segments.append(Segment(round(t, 2), round(e, 2), round(sc, 3), round(mo, 3), any(face_sec[s0:s1])))
            t = e
    segments.sort(key=lambda s: s.score, reverse=True)

    rel_sharp = float(np.median(sharp_a))
    result = ClipAnalysis(
        path=str(path), duration=round(duration, 2), fps=fps, width=w, height=h,
        sharpness=round(float(np.clip(rel_sharp / 400, 0, 1)), 3), shake=round(shake, 3),
        brightness=round(float(bright_a.mean()), 3), motion=round(float(np.mean(m)), 3),
        has_speech=speech, scene_cuts=cuts, silences=silences,
        per_second=[round(x, 3) for x in per_second], motion_peaks=peaks, segments=segments,
    )
    if result.brightness < 0.06:
        result.rejected_reason = "too dark"
    elif rel_sharp < 8:
        result.rejected_reason = "blurry"
    elif duration < 0.8:
        result.rejected_reason = "too short"

    d = asdict(result)
    cache.write_text(json.dumps(d))
    return result


def find_media(folder: str | Path) -> tuple[list[Path], list[Path]]:
    folder = Path(folder)
    files = sorted(p for p in folder.rglob("*") if p.is_file() and "__MACOSX" not in p.parts)
    return ([p for p in files if p.suffix.lower() in VIDEO_EXT],
            [p for p in files if p.suffix.lower() in AUDIO_EXT])


def dedupe(clips: list[ClipAnalysis]) -> list[ClipAnalysis]:
    """Drop near-duplicate takes (same scene filmed twice): keep the best one."""
    sigs = []
    for c in clips:
        frame = next(iter(_frames_at(Path(c.path), c.duration / 2)), None)
        sigs.append(None if frame is None else cv2.resize(cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY), (32, 18)).astype(np.float32))
    keep = []
    for i, c in enumerate(clips):
        dup = False
        for j in keep:
            if sigs[i] is not None and sigs[j] is not None:
                if np.abs(sigs[i] - sigs[j]).mean() < 6 and abs(clips[j].duration - c.duration) < 3:
                    dup = True
                    if np.mean(c.per_second or [0]) > np.mean(clips[j].per_second or [0]):
                        keep[keep.index(j)] = i
                    break
        if not dup:
            keep.append(i)
    dropped = [clips[i] for i in range(len(clips)) if i not in keep]
    for d in dropped:
        d.rejected_reason = d.rejected_reason or "duplicate take"
    return [clips[i] for i in sorted(keep)]


def _frames_at(path: Path, t: float):
    cmd = [FFMPEG, "-v", "error", "-ss", f"{t:.2f}", "-i", str(path), "-frames:v", "1",
           "-vf", f"scale={W}:{H}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
    buf = subprocess.run(cmd, capture_output=True).stdout
    if len(buf) == W * H * 3:
        yield np.frombuffer(buf, np.uint8).reshape(H, W, 3)


# ---------------------------------------------------------------- music

@dataclass
class MusicAnalysis:
    path: str
    duration: float
    tempo: float
    beats: list[float]
    downbeats: list[float]
    drop: float | None          # biggest energy jump → put the hook/grid here
    energy: list[float] = field(default_factory=list)   # loudness per 0.25 s, 0..1 (drives pacing)
    hits: list[float] = field(default_factory=list)     # strongest musical impacts (cut on these)

    def energy_at(self, t: float) -> float:
        if not self.energy:
            return 0.5
        i = int(t / 0.25)
        return self.energy[min(max(i, 0), len(self.energy) - 1)]

    def to_dict(self):
        return asdict(self)


def analyze_music(path: str | Path) -> MusicAnalysis:
    import librosa

    path = Path(path)
    cache = CACHE / f"music2_{_key(path)}.json"
    if cache.exists():
        cached = MusicAnalysis(**json.loads(cache.read_text()))
        if cached.duration > 0 and cached.beats:
            return cached
    sr = 22050
    y = load_audio(path, sr)
    if y.size < sr:                                    # read failed (file busy/still copying) → try once more
        time.sleep(1.0)
        y = load_audio(path, sr)
    if y.size < sr:
        raise SystemExit(f"Couldn't read the song: {path}")
    tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr, units="frames")
    beats = librosa.frames_to_time(beat_frames, sr=sr).tolist()
    onset = librosa.onset.onset_strength(y=y, sr=sr)
    # downbeat = the strongest beat in each group of 4
    strength = [float(onset[min(f, len(onset) - 1)]) for f in beat_frames]
    best_phase = int(np.argmax([np.sum(strength[p::4]) for p in range(4)])) if len(strength) >= 8 else 0
    downbeats = beats[best_phase::4]
    rms = librosa.feature.rms(y=y)[0]
    rms_t = librosa.frames_to_time(np.arange(len(rms)), sr=sr)
    win = int(2 * sr / 512)
    drop = None
    if len(rms) > 2 * win:
        jump = np.array([rms[i:i + win].mean() - rms[i - win:i].mean() for i in range(win, len(rms) - win)])
        drop = float(rms_t[win + int(np.argmax(jump))])
    hop = int(0.25 * sr)
    seg_rms = np.array([np.sqrt(np.mean(y[i:i + hop] ** 2)) for i in range(0, max(1, len(y) - hop + 1), hop)])
    energy = (seg_rms / (np.percentile(seg_rms, 95) + 1e-9)).clip(0, 1) if seg_rms.size else np.array([])
    peaks = librosa.util.peak_pick(onset, pre_max=10, post_max=10, pre_avg=20, post_avg=20, delta=0.5, wait=20)
    order = sorted(peaks, key=lambda f: -onset[f])[:6]
    hits = sorted(round(float(librosa.frames_to_time(f, sr=sr)), 3) for f in order)
    res = MusicAnalysis(str(path), round(len(y) / sr, 2), float(np.atleast_1d(tempo)[0]),
                        [round(b, 3) for b in beats], [round(b, 3) for b in downbeats], drop,
                        [round(float(e), 3) for e in energy], hits)
    if res.duration > 0 and res.beats:                 # never cache a failed analysis
        cache.write_text(json.dumps(res.to_dict()))
    return res
