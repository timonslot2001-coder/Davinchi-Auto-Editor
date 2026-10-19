"""After Resolve renders: quality check, loudness to platform standard, 4:5 version, cover frame."""
from __future__ import annotations

import json
import re
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path

import cv2
import numpy as np

from .analyze import FFMPEG


def _run(args: list[str]) -> str:
    return subprocess.run([FFMPEG, "-hide_banner", *args], capture_output=True, text=True, errors="replace").stderr


@dataclass
class QCReport:
    file: str
    width: int = 0
    height: int = 0
    fps: float = 0
    duration: float = 0
    lufs: float | None = None
    true_peak: float | None = None
    black_segments: list[list[float]] = field(default_factory=list)
    frozen_segments: list[list[float]] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.problems


def qc(path: Path, expect=(1080, 1920)) -> QCReport:
    r = QCReport(str(path))
    cap = cv2.VideoCapture(str(path))
    r.width, r.height = int(cap.get(3)), int(cap.get(4))
    r.fps = cap.get(5) or 0
    r.duration = (cap.get(7) or 0) / (r.fps or 25)
    cap.release()
    err = _run(["-i", str(path), "-vf", "blackdetect=d=0.08:pix_th=0.06,freezedetect=n=0.001:d=0.6",
                "-af", "ebur128=peak=true", "-f", "null", "-"])
    r.black_segments = [[float(a), float(b)] for a, b in re.findall(r"black_start:([\d.]+) black_end:([\d.]+)", err)]
    fs = re.findall(r"freeze_start: ([\d.]+)", err)
    fe = re.findall(r"freeze_end: ([\d.]+)", err)
    r.frozen_segments = [[float(a), float(b)] for a, b in zip(fs, fe)]
    m = re.findall(r"I:\s+(-?[\d.]+) LUFS", err)
    r.lufs = float(m[-1]) if m else None
    m = re.findall(r"Peak:\s+(-?[\d.]+) dBFS", err)
    r.true_peak = float(m[-1]) if m else None
    if (r.width, r.height) != tuple(expect):
        r.problems.append(f"resolution {r.width}x{r.height} (expected {expect[0]}x{expect[1]})")
    flashes = [s for s in r.black_segments if s[1] - s[0] < 0.2 and s[0] > 0.1]
    if flashes:
        r.problems.append(f"{len(flashes)} black flash frame(s) at {', '.join(f'{s[0]:.2f}s' for s in flashes)}")
    if r.true_peak is not None and r.true_peak > -0.5:
        r.problems.append(f"audio clipping (true peak {r.true_peak:.1f} dBTP)")
    return r


def _measure(path: Path) -> tuple[float | None, float | None]:
    err = _run(["-i", str(path), "-vn", "-af", "ebur128=peak=true", "-f", "null", "-"])
    i = re.findall(r"I:\s+(-?[\d.]+) LUFS", err)
    pk = re.findall(r"Peak:\s+(-?[\d.]+) dBFS", err)
    return (float(i[-1]) if i else None), (float(pk[-1]) if pk else None)


def loudnorm(src: Path, dst: Path, target: float = -14.0, ceiling: float = 0.84) -> Path:
    """Gain to the platform loudness + 4× oversampled limiter (true peak stays ≈ -1.5 dBTP, even after AAC).
    The limiter eats a little loudness, so it's measured again and corrected (max 3 passes)."""
    i_src, _ = _measure(src)
    if i_src is None or i_src < -60:                                 # silent: just copy
        subprocess.run([FFMPEG, "-y", "-v", "error", "-i", str(src), "-c", "copy", str(dst)], check=True)
        return dst
    gain = target - i_src
    for _ in range(3):
        af = f"volume={gain:.2f}dB,aresample=192000,alimiter=limit={ceiling}:attack=0.5:release=40:level=false,aresample=48000"
        subprocess.run([FFMPEG, "-y", "-v", "error", "-i", str(src), "-c:v", "copy", "-af", af,
                        "-c:a", "aac", "-b:a", "256k", "-movflags", "+faststart", str(dst)], check=True)
        i_out, _ = _measure(dst)
        if i_out is None or abs(i_out - target) <= 0.4:
            break
        gain += min(6.0, target - i_out)
    return dst


def reframe_4x5(src: Path, dst: Path) -> Path:
    """Instagram feed version: 1080×1350 centre crop (the 9:16 safe zone keeps text inside)."""
    subprocess.run([FFMPEG, "-y", "-v", "error", "-i", str(src), "-vf", "crop=1080:1350:0:(ih-1350)/2",
                    "-c:v", "libx264", "-preset", "slow", "-crf", "16", "-pix_fmt", "yuv420p",
                    "-c:a", "copy", "-movflags", "+faststart", str(dst)], check=True)
    return dst


def best_cover(video: Path, dst: Path, avoid_first: float = 0.5) -> Path:
    """Cover/thumbnail: sharpest, most colourful, well-exposed frame (sampled 4×/s)."""
    cap = cv2.VideoCapture(str(video))
    fps = cap.get(5) or 25
    n = int(cap.get(7))
    best, best_score, best_frame = -1, -1e9, None
    for i in range(int(avoid_first * fps), n, max(1, int(fps / 4))):
        cap.set(cv2.CAP_PROP_POS_FRAMES, i)
        ok, frame = cap.read()
        if not ok:
            break
        small = cv2.resize(frame, (270, 480))
        g = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
        sharp = cv2.Laplacian(g, cv2.CV_32F).var()
        b, gch, r = [small[..., k].astype(np.float32) for k in range(3)]
        colour = np.hypot((r - gch).std(), (0.5 * (r + gch) - b).std())
        expo = 1 - abs(g.mean() / 255 - 0.5) * 2
        # penalise grid-ish frames with large black areas
        black = (g < 12).mean()
        score = np.log1p(sharp) * 1.0 + colour / 25 + expo * 2 - black * 4
        if score > best_score:
            best, best_score, best_frame = i, score, frame
    cap.release()
    if best_frame is not None:
        cv2.imwrite(str(dst), best_frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
    return dst


def finish(rendered: Path, out_dir: Path, base: str, target_lufs: float = -14, extra=("4:5",),
           expect=(1080, 1920)) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    tag = "16x9" if expect[0] > expect[1] else "9x16"
    final = loudnorm(rendered, out_dir / f"{base}_{tag}.mp4", target_lufs)
    files = {"9:16" if tag == "9x16" else "16:9": str(final)}
    if "4:5" in extra:
        files["4:5"] = str(reframe_4x5(final, out_dir / f"{base}_4x5.mp4"))
    files["cover"] = str(best_cover(final, out_dir / f"{base}_cover.jpg"))
    report = qc(final, expect)
    (out_dir / f"{base}_qc.json").write_text(json.dumps(asdict(report), indent=1))
    return {"files": files, "qc": asdict(report), "qc_ok": report.ok}
