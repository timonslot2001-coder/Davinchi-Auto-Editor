"""Playback proxies.

Sony 4K H.264 4:2:2 10-bit can't be hardware-decoded by AMD GPUs (they only decode 4:2:0), so Resolve
decodes every frame on the CPU — six of them at once in the grid. We make 1080p ProRes Proxy copies
(intra-frame, very cheap to decode), link them in Resolve and play from those. Renders still use the
4K originals (Resolve only renders from proxies if you explicitly tell it to).
"""
from __future__ import annotations

import hashlib
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .analyze import FFMPEG


def proxy_path(src: Path, folder: Path) -> Path:
    h = hashlib.sha1(f"{src.resolve()}|{src.stat().st_size}".encode()).hexdigest()[:8]
    return folder / f"{src.stem}_{h}_proxy.mov"


def _timecode(src: Path) -> str | None:
    """Sony keeps the start timecode in the sidecar XML (C0183M01.XML) — Resolve uses it too."""
    xml = src.with_name(f"{src.stem}M01.XML")
    if xml.exists():
        import re
        m = re.search(r'LtcChange[^>]*frameCount="0"[^>]*value="(\d{8})"', xml.read_text(errors="ignore"))
        if m:
            v = m.group(1)                       # BCD-ish "ffssmmhh" in Sony XML
            ff, ss, mm, hh = v[0:2], v[2:4], v[4:6], v[6:8]
            return f"{hh}:{mm}:{ss}:{ff}"
    return None


def make_proxy(src: Path, folder: Path) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    out = proxy_path(src, folder)
    if out.exists() and out.stat().st_size > 0:
        return out
    tmp = out.with_suffix(".part.mov")
    cmd = [FFMPEG, "-y", "-v", "error", "-i", str(src), "-map", "0:v:0", "-map", "0:a?",
           "-vf", "scale=1920:-2:flags=bilinear", "-c:v", "prores_ks", "-profile:v", "0",
           "-pix_fmt", "yuv422p10le", "-c:a", "pcm_s16le", "-map_metadata", "0"]
    tc = _timecode(src)
    if tc:
        cmd += ["-timecode", tc]
    subprocess.run(cmd + [str(tmp)], check=True)
    tmp.replace(out)
    return out


def ensure_proxies(sources: list[Path], folder: Path, workers: int = 3, log=print) -> dict[str, Path]:
    todo = [s for s in sources if not proxy_path(s, folder).exists()]
    if todo:
        log(f"  making {len(todo)} playback prox{'y' if len(todo) == 1 else 'ies'} (one-time, 1080p ProRes Proxy)…")
    with ThreadPoolExecutor(workers) as ex:
        paths = list(ex.map(lambda s: make_proxy(s, folder), sources))
    return {str(s): p for s, p in zip(sources, paths)}
