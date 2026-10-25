"""Frame-accurate compositor: EDL -> MP4. Sources are decoded per event with FFmpeg (trim, optional LUT, scale/crop
to the output frame); transitions and devices are applied in numpy; graphics come from graphics.py; the encoder is
FFmpeg (H.264 + AAC)."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import cv2
import imageio_ffmpeg
import numpy as np

from . import REPO
from .edl import EDL
from . import graphics

FF = imageio_ffmpeg.get_ffmpeg_exe()
CARD = {"inset_w": 0.69, "inset_h": 0.92, "bg": (0xFD, 0xFC, 0xFD)}      # style_dna D_CARD_WHITE (RGB)


# ---------------------------------------------------------------- grade
def detect_log(clip: str) -> bool:
    """S-Log detection: Sony sidecar XML (<stem>M01.XML, CaptureGammaEquation) when present, else a heuristic
    (lifted blacks, low saturation). Logged in the render notes."""
    import re
    side = Path(clip).with_name(Path(clip).stem + "M01.XML")
    if side.exists():
        m = re.search(r'CaptureGammaEquation"\s+value="([^"]+)"', side.read_text(encoding="utf-8", errors="ignore"))
        if m:
            return "log" in m[1].lower()
    cap = cv2.VideoCapture(clip)
    n = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 1
    cap.set(cv2.CAP_PROP_POS_FRAMES, int(n / 2))
    ok, f = cap.read()
    if not ok:
        return False
    g = cv2.cvtColor(f, cv2.COLOR_BGR2GRAY)
    sat = cv2.cvtColor(f, cv2.COLOR_BGR2HSV)[..., 1].mean()
    return np.percentile(g, 2) > 28 and np.percentile(g, 98) < 225 and sat < 60


def lut_for(mode: str, clip: str, notes: list) -> Path | None:
    if mode == "none":
        return None
    sys.path.insert(0, str(REPO))
    from autoedit import grade                                   # AutoEdit's baked film-look LUTs
    is_log = detect_log(clip) if mode == "auto" else mode == "slog3"
    p = grade.build_lut("reference_film", conversion="SLog3SGamut3.CineToLC-709TypeA.cube" if is_log else None,
                        exposure=-1.75 if is_log else 0.0)
    notes.append(f"grade {Path(clip).name}: {'S-Log3 conversion + ' if is_log else ''}reference_film LUT ({p.name})")
    return p


def _ff_path(p: Path) -> str:
    return str(p).replace("\\", "/").replace(":", "\\:")


# ---------------------------------------------------------------- source decoding
def read_event(ev, edl: EDL, lut: Path | None) -> np.ndarray:
    """All output frames of one event as an array (n, H, W, 3) uint8 BGR."""
    W, H, fps = edl.width, edl.height, edl.fps
    n = int(round((ev.out_out - ev.out_in) * fps))
    dur = n / fps + 0.2
    vf = []
    if lut:
        vf.append(f"lut3d=file='{_ff_path(lut)}'")
    vf += [f"scale={W}:{H}:force_original_aspect_ratio=increase:flags=lanczos", f"crop={W}:{H}", f"fps={fps}"]
    raw = subprocess.run([FF, "-v", "error", "-ss", f"{ev.src_in:.3f}", "-t", f"{dur:.3f}", "-i", ev.source,
                          "-vf", ",".join(vf), "-pix_fmt", "bgr24", "-f", "rawvideo", "-"], capture_output=True, check=True).stdout
    frames = np.frombuffer(raw, np.uint8).reshape(-1, H, W, 3)
    if len(frames) < n:                                          # hold the last frame if the source runs short
        pad = np.repeat(frames[-1:], n - len(frames), axis=0) if len(frames) else np.zeros((n, H, W, 3), np.uint8)
        frames = np.concatenate([frames, pad])
    return frames[:n].copy()


# ---------------------------------------------------------------- devices
def card(frame: np.ndarray) -> np.ndarray:
    H, W = frame.shape[:2]
    w, h = int(W * CARD["inset_w"]), int(H * CARD["inset_h"])
    out = np.empty_like(frame)
    out[:] = CARD["bg"][::-1]
    x0, y0 = (W - w) // 2, (H - h) // 2
    out[y0:y0 + h, x0:x0 + w] = cv2.resize(frame, (w, h), interpolation=cv2.INTER_AREA)
    return out


def bw(frame: np.ndarray) -> np.ndarray:
    g = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY).astype(np.float32)
    g = np.clip((g - 128) * 1.15 + 128, 0, 255).astype(np.uint8)
    return cv2.cvtColor(g, cv2.COLOR_GRAY2BGR)


def whip(frame: np.ndarray, strength: float, direction: int) -> np.ndarray:
    """Horizontal motion blur + slide; strength 0..1."""
    if strength <= 0.02:
        return frame
    H, W = frame.shape[:2]
    k = max(3, int(W * 0.09 * strength) | 1)
    kernel = np.zeros((1, k), np.float32)
    kernel[0, :] = 1.0 / k
    blurred = cv2.filter2D(frame, -1, kernel, borderType=cv2.BORDER_REFLECT)
    shift = int(direction * W * 0.12 * strength)
    m = np.float32([[1 + 0.06 * strength, 0, -W * 0.03 * strength + shift], [0, 1 + 0.06 * strength, -H * 0.03 * strength]])
    return cv2.warpAffine(blurred, m, (W, H), borderMode=cv2.BORDER_REFLECT)


def over(dst: np.ndarray, rgba: np.ndarray) -> np.ndarray:
    a = rgba[..., 3:4].astype(np.float32) / 255
    return (rgba[..., :3].astype(np.float32) * a + dst.astype(np.float32) * (1 - a)).astype(np.uint8)


# ---------------------------------------------------------------- audio
def audio_track(edl: EDL, path: Path, sr: int = 48000) -> Path:
    n = int(edl.duration * sr)
    if edl.music:
        raw = subprocess.run([FF, "-v", "error", "-ss", f"{edl.music_offset:.3f}", "-t", f"{edl.duration + 0.1:.3f}",
                              "-i", edl.music, "-ac", "2", "-ar", str(sr), "-f", "f32le", "-"], capture_output=True, check=True).stdout
        a = np.frombuffer(raw, np.float32).reshape(-1, 2)[:n].copy()
        a = np.pad(a, ((0, n - len(a)), (0, 0)))
        fade = int(min(1.2, edl.duration * 0.08) * sr)              # the music resolves with the final hold
        a[-fade:] *= np.linspace(1, 0, fade)[:, None] ** 1.5
        a[: int(0.01 * sr)] *= np.linspace(0, 1, int(0.01 * sr))[:, None]
    else:
        a = np.zeros((n, 2), np.float32)
    a.tofile(path)
    return path


# ---------------------------------------------------------------- main render
def render(edl: EDL, out: Path, work: Path, grade_mode: str = "auto", preview: bool = False, log=print) -> dict:
    work.mkdir(parents=True, exist_ok=True)
    W, H, fps = edl.width, edl.height, edl.fps
    if preview:                                                  # cheap review clip: half size
        W, H = W // 2, H // 2
        edl = EDL(**{**edl.__dict__, "width": W, "height": H})
    notes = []
    luts = {}
    for ev in edl.events:
        if ev.source and ev.source not in luts:
            luts[ev.source] = lut_for(grade_mode, ev.source, notes)
    gfx = {}
    for o in edl.overlays:
        if o.component == "title_slam":
            gfx[o.id] = graphics.title_png(o.params["text"], o.params["color"], o.params["variant"], (W, H), work / "gfx")
        elif o.component == "side_labels":
            gfx[o.id] = graphics.labels_png(o.params["left"], o.params["right"], (W, H), work / "gfx")
    pcm = audio_track(edl, work / "audio.f32")
    enc = subprocess.Popen([FF, "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H}", "-r", str(fps),
                            "-i", "-", "-f", "f32le", "-ar", "48000", "-ac", "2", "-i", str(pcm),
                            "-c:v", "libx264", "-preset", "veryfast" if preview else "slow", "-crf", "23" if preview else "16",
                            "-pix_fmt", "yuv420p", "-af", "loudnorm=I=-14:TP=-1.5:LRA=11", "-ar", "48000", "-c:a", "aac", "-b:a", "320k", "-shortest", "-movflags", "+faststart", str(out)],
                           stdin=subprocess.PIPE)
    frame_no = 0
    events = edl.events
    for k, ev in enumerate(events):
        frames = read_event(ev, edl, luts.get(ev.source))
        nxt = events[k + 1] if k + 1 < len(events) else None
        for i, f in enumerate(frames):
            t = ev.out_in + i / fps
            if "D_BW" in ev.treatment:
                f = bw(f)
            if "D_CARD_WHITE" in ev.treatment:
                f = card(f)
            # whip: blur ramps up over the last 2 frames of the outgoing shot and down over the first 3 of the incoming
            if ev.transition_in == "T_WHIP" and i < 3:
                f = whip(f, 1 - i / 3, -ev.params.get("whip_dir", 1))
            if nxt is not None and nxt.transition_in == "T_WHIP" and i >= len(frames) - 2:
                f = whip(f, (i - (len(frames) - 3)) / 2, -nxt.params.get("whip_dir", 1))
            if ev.transition_in == "T_FLASH" and i == 0:          # single full-white frame (RULE_FLASH)
                f = np.full_like(f, 255)
            for o in edl.overlays:
                if o.id in gfx and o.out_in - 1e-6 <= t < o.out_out - 1e-6:
                    f = over(f, gfx[o.id])
            enc.stdin.write(np.ascontiguousarray(f).tobytes())
            frame_no += 1
        log(f"  {ev.id} {ev.out_in:6.2f}-{ev.out_out:6.2f} {Path(ev.source).name[:28]:28} {ev.transition_in} {' '.join(ev.treatment)}")
    enc.stdin.close()
    enc.wait()
    if enc.returncode:
        raise RuntimeError("encoder failed")
    return {"out": str(out), "frames": frame_no, "notes": notes}
