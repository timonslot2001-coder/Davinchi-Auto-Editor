"""SFX library: your own sounds sorted by category + a generated base set so it always works.

Categories: whoosh, hit, impact, pop, click, shutter, riser, swell, glitch, film.
Drop extra sounds into data/sfx/<category>/ or point config paths.sfx_folders at a pack:
file names containing e.g. "whoosh", "swoosh", "hit", "boom", "riser" are sorted automatically.
"""
from __future__ import annotations

import random
import zlib
from pathlib import Path

import numpy as np
import soundfile as sf

from .config import DATA

SR = 48000
LIB = DATA / "sfx"
CATEGORIES = {
    "whoosh": ["whoosh", "swoosh", "swish", "woosh", "swipe", "transition", "whip"],
    "hit": ["hit", "punch", "kick", "thump", "bass drop", "sub"],
    "impact": ["impact", "boom", "slam", "cinematic hit"],
    "pop": ["pop", "bubble", "plop", "blip"],
    "click": ["click", "tick", "tap", "button", "ui"],
    "shutter": ["shutter", "camera", "snap", "flash"],
    "riser": ["riser", "rise", "build", "uplifter", "sweep up"],
    "swell": ["swell", "reverse", "suck"],
    "glitch": ["glitch", "digital", "static", "noise crack", "error", "bitcrush"],
    "film": ["film", "reel", "projector", "analog", "mechanical", "whir"],
}


# ---------------------------------------------------------------- synthesis

def _env(n, attack, release, curve=4.0):
    t = np.linspace(0, 1, n)
    a = int(n * attack)
    e = np.exp(-curve * np.clip((t - attack) / max(release, 1e-3), 0, None))
    if a:
        e[:a] = np.linspace(0, 1, a) ** 2
    return e


def _bandnoise(n, lo, hi, rng):
    spec = np.fft.rfft(rng.standard_normal(n))
    f = np.fft.rfftfreq(n, 1 / SR)
    spec[(f < lo) | (f > hi)] = 0
    x = np.fft.irfft(spec, n)
    return x / (np.abs(x).max() + 1e-9)


def _sweep_noise(n, f0, f1, rng, q=0.5):
    """Noise through a moving band-pass (classic whoosh/riser), done in short blocks."""
    out = np.zeros(n)
    block = 1024
    noise = rng.standard_normal(n + block)
    for i in range(0, n, block // 2):
        c = f0 + (f1 - f0) * (i / n)
        seg = noise[i:i + block] * np.hanning(block)
        spec = np.fft.rfft(seg)
        f = np.fft.rfftfreq(block, 1 / SR)
        spec *= np.exp(-((f - c) / (c * q + 1)) ** 2)
        y = np.fft.irfft(spec, block)
        out[i:i + block] += y[: max(0, min(block, n - i))]
    return out / (np.abs(out).max() + 1e-9)


def _stereo(x, width=0.3, rng=None):
    d = int(SR * 0.004 * width)
    l, r = x, np.r_[np.zeros(d), x[:-d]] if d else x
    st = np.c_[l, r]
    return 0.89 * st / (np.abs(st).max() + 1e-9)


def _gen(cat: str, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    v = rng.uniform(0.85, 1.15)
    if cat == "whoosh":
        n = int(SR * 0.45 * v)
        x = _sweep_noise(n, 300 * v, 4000 * v, rng) * np.sin(np.linspace(0, np.pi, n)) ** 1.5
        x += 0.3 * _sweep_noise(n, 120, 600, rng) * np.sin(np.linspace(0, np.pi, n)) ** 2
    elif cat == "hit":
        n = int(SR * 0.6)
        t = np.arange(n) / SR
        f = 55 * v + 120 * np.exp(-t * 35)
        x = np.sin(2 * np.pi * np.cumsum(f) / SR) * _env(n, 0.002, 0.25, 5)
        x += 0.35 * _bandnoise(n, 1500, 8000, rng) * _env(n, 0.0, 0.02, 8)
        x = np.tanh(2.2 * x)
    elif cat == "impact":
        n = int(SR * 1.4)
        t = np.arange(n) / SR
        f = 40 * v + 90 * np.exp(-t * 20)
        x = np.sin(2 * np.pi * np.cumsum(f) / SR) * _env(n, 0.001, 0.5, 4)
        x += 0.5 * _bandnoise(n, 80, 3000, rng) * _env(n, 0.0, 0.15, 6)
        x = np.tanh(2.5 * x)
    elif cat == "pop":
        n = int(SR * 0.12)
        t = np.arange(n) / SR
        f = 900 * v * np.exp(-t * 18) + 250
        x = np.sin(2 * np.pi * np.cumsum(f) / SR) * _env(n, 0.01, 0.4, 6)
    elif cat == "click":
        n = int(SR * 0.05)
        x = _bandnoise(n, 2000 * v, 9000, rng) * _env(n, 0.0, 0.05, 10)
        x += 0.5 * np.sin(2 * np.pi * 1800 * v * np.arange(n) / SR) * _env(n, 0, 0.1, 10)
    elif cat == "shutter":
        n = int(SR * 0.22)
        a = _bandnoise(n, 1500, 9000, rng) * _env(n, 0.0, 0.06, 9)
        b = np.roll(_bandnoise(n, 800, 6000, rng) * _env(n, 0.0, 0.06, 9), int(SR * 0.075 * v))
        x = a + 0.8 * b
    elif cat == "riser":
        n = int(SR * 1.6 * v)
        t = np.linspace(0, 1, n)
        x = _sweep_noise(n, 200, 7000, rng, q=0.35) * t ** 2
        x += 0.4 * np.sin(2 * np.pi * np.cumsum(110 * v * 2 ** (3 * t)) / SR) * t ** 2
    elif cat == "swell":
        n = int(SR * 0.9 * v)
        t = np.linspace(0, 1, n)
        x = _sweep_noise(n, 2000, 400, rng) * t ** 3
    elif cat == "glitch":
        n = int(SR * 0.3 * v)
        x = np.zeros(n)
        pos = 0
        while pos < n:
            ln = int(SR * rng.uniform(0.008, 0.04))
            kind = rng.integers(3)
            seg = (np.sign(np.sin(2 * np.pi * rng.uniform(200, 2000) * np.arange(ln) / SR)) if kind == 0
                   else rng.standard_normal(ln) if kind == 1 else np.zeros(ln))
            x[pos:pos + ln] = seg[: n - pos] * rng.uniform(0.3, 1)
            pos += ln
        x = np.round(x * 6) / 6
    else:
        raise ValueError(cat)
    return _stereo(x)


def build_library(variants: int = 4) -> None:
    for cat in [c for c in CATEGORIES if c != "film"]:
        d = LIB / cat
        d.mkdir(parents=True, exist_ok=True)
        for i in range(variants):
            p = d / f"gen_{cat}_{i + 1}.wav"
            if not p.exists():
                sf.write(p, _gen(cat, zlib.crc32(f"{cat}{i}".encode())), SR, subtype="PCM_24")


# ---------------------------------------------------------------- library

def categorize(name: str) -> str | None:
    n = name.lower()
    for cat, words in CATEGORIES.items():
        if any(w in n for w in words):
            return cat
    return None


class Library:
    def __init__(self, extra_folders: list[str] | None = None, seed: int | None = None):
        build_library()
        self.by_cat: dict[str, list[Path]] = {c: [] for c in CATEGORIES}
        self.rng = random.Random(seed)
        self._last: dict[str, Path] = {}
        for p in LIB.rglob("*.wav"):
            self.by_cat.setdefault(p.parent.name, []).append(p)
        for folder in extra_folders or []:
            for p in Path(folder).rglob("*"):
                if p.suffix.lower() in {".wav", ".mp3", ".aif", ".aiff"} and "__MACOSX" not in p.parts:
                    cat = categorize(p.stem) or categorize(p.parent.name)
                    if cat:
                        # your own sounds first: they are listed twice so they're picked more often
                        self.by_cat[cat] += [p, p]

    def pick(self, cat: str) -> Path | None:
        pool = self.by_cat.get(cat) or []
        if not pool:
            return None
        choices = [p for p in pool if p != self._last.get(cat)] or pool   # no same sound twice in a row
        p = self.rng.choice(choices)
        self._last[cat] = p
        return p

    def summary(self) -> dict[str, int]:
        return {c: len(set(v)) for c, v in self.by_cat.items()}
