"""Grade as one baked 3D LUT: Sony S-Log3/S-Gamut3.Cine → Rec.709 conversion + a creative film look.

Why: the Odyssey PowerGrade is a manual tool (its look nodes are keyed off and its CST isn't set), so applied
by script it changes nothing. A single LUT on a clean node is deterministic, renders correctly and can be
matched to a reference by numbers.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

SONY = Path(r"C:\ProgramData\Blackmagic Design\DaVinci Resolve\Support\LUT\Sony")
LUT_ROOT = Path(r"C:\ProgramData\Blackmagic Design\DaVinci Resolve\Support\LUT")
OUT_DIR = LUT_ROOT / "AutoEdit"

# Film looks (all operate on display-referred Rec.709 values 0..1)
LOOKS = {
    # matched to the LA reference: warm/orange highlights, teal-cyan skies, milky lifted blacks, soft contrast
    # tuned by numbers against the reference (luma/saturation/warmth/clipping) on Sony S-Log3 footage
    "reference_film": dict(contrast=1.04, pivot=0.45, lift=0.045, gain=0.98, sat=1.8,
                           shadows=(-0.010, 0.012, 0.022), highlights=(0.045, 0.012, -0.040),
                           teal_sky=0.35, orange_skin=0.25, hue_greens=-0.04, fade=0.03),
    "clean_warm": dict(contrast=1.10, pivot=0.45, lift=0.01, gain=1.0, sat=1.08,
                       shadows=(0.0, 0.004, 0.010), highlights=(0.03, 0.01, -0.02),
                       teal_sky=0.15, orange_skin=0.15, hue_greens=-0.02, fade=0.0),
    "moody": dict(contrast=1.15, pivot=0.42, lift=0.02, gain=0.94, sat=0.85,
                  shadows=(-0.01, 0.01, 0.03), highlights=(0.02, 0.0, -0.02),
                  teal_sky=0.4, orange_skin=0.2, hue_greens=-0.08, fade=0.02),
    "none": None,
}


# ---------------------------------------------------------------- cube io

def read_cube(path: Path) -> tuple[np.ndarray, int]:
    size, rows = None, []
    for line in path.read_text(errors="ignore").splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if s.upper().startswith("LUT_3D_SIZE"):
            size = int(s.split()[-1])
        elif s[0].isdigit() or s[0] in "-.":
            parts = s.split()
            if len(parts) == 3:
                rows.append([float(x) for x in parts])
    a = np.asarray(rows, np.float64)
    # .cube order: red fastest → reshape to [b][g][r]
    return a.reshape(size, size, size, 3), size


def write_cube(path: Path, lut: np.ndarray, title: str) -> None:
    n = lut.shape[0]
    lines = [f'TITLE "{title}"', f"LUT_3D_SIZE {n}", "DOMAIN_MIN 0 0 0", "DOMAIN_MAX 1 1 1"]
    flat = np.clip(lut, 0, 1).reshape(-1, 3)
    lines += [f"{r:.6f} {g:.6f} {b:.6f}" for r, g, b in flat]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n")


def apply_cube(lut: np.ndarray, rgb: np.ndarray) -> np.ndarray:
    """Trilinear lookup. rgb: (..., 3) in 0..1. lut indexed [b][g][r]."""
    n = lut.shape[0]
    x = np.clip(rgb, 0, 1) * (n - 1)
    i0 = np.floor(x).astype(int)
    i1 = np.minimum(i0 + 1, n - 1)
    f = x - i0
    r0, g0, b0 = i0[..., 0], i0[..., 1], i0[..., 2]
    r1, g1, b1 = i1[..., 0], i1[..., 1], i1[..., 2]
    fr, fg, fb = f[..., 0:1], f[..., 1:2], f[..., 2:3]

    def L(b, g, r):
        return lut[b, g, r]
    c00 = L(b0, g0, r0) * (1 - fr) + L(b0, g0, r1) * fr
    c01 = L(b0, g1, r0) * (1 - fr) + L(b0, g1, r1) * fr
    c10 = L(b1, g0, r0) * (1 - fr) + L(b1, g0, r1) * fr
    c11 = L(b1, g1, r0) * (1 - fr) + L(b1, g1, r1) * fr
    c0 = c00 * (1 - fg) + c01 * fg
    c1 = c10 * (1 - fg) + c11 * fg
    return c0 * (1 - fb) + c1 * fb


def identity(n: int = 33) -> np.ndarray:
    v = np.linspace(0, 1, n)
    b, g, r = np.meshgrid(v, v, v, indexing="ij")
    return np.stack([r, g, b], axis=-1)


# ---------------------------------------------------------------- look maths

def _luma(c):
    return c[..., 0:1] * 0.2126 + c[..., 1:2] * 0.7152 + c[..., 2:3] * 0.0722


def film_look(c: np.ndarray, p: dict, strength: float = 1.0) -> np.ndarray:
    o = c.copy()
    y = _luma(o)
    # split toning: cool/teal shadows, warm highlights
    sh = np.clip(1 - y * 2.2, 0, 1)
    hi = np.clip((y - 0.45) * 1.9, 0, 1)
    o = o + sh * np.asarray(p["shadows"]) + hi * np.asarray(p["highlights"])
    # hue-targeted: blue/cyan (sky) → teal; orange/skin → warmer
    r, g, b = o[..., 0:1], o[..., 1:2], o[..., 2:3]
    blueish = np.clip((b - r) * 3, 0, 1) * np.clip((b - g + 0.15) * 3, 0, 1)
    o = o + blueish * p["teal_sky"] * np.concatenate([-0.06 * np.ones_like(r), 0.03 * np.ones_like(r), -0.01 * np.ones_like(r)], -1)
    orange = np.clip((r - b) * 2.5, 0, 1) * np.clip(1 - np.abs(g - (r + b) / 2) * 4, 0, 1)
    o = o + orange * p["orange_skin"] * np.concatenate([0.04 * np.ones_like(r), 0.01 * np.ones_like(r), -0.03 * np.ones_like(r)], -1)
    greenish = np.clip((g - np.maximum(r, b)) * 4, 0, 1)
    o = o + greenish * np.concatenate([-p["hue_greens"] * 0.5 * np.ones_like(r), p["hue_greens"] * np.ones_like(r), np.zeros_like(r)], -1)
    # saturation
    y = _luma(o)
    o = y + (o - y) * p["sat"]
    # contrast around pivot, lift/gain, filmic fade of the blacks
    o = (o - p["pivot"]) * p["contrast"] + p["pivot"]
    o = p["lift"] + o * (p["gain"] - p["lift"])
    o = o + p["fade"] * (1 - o) * np.clip(1 - o * 3, 0, 1)
    # soft highlight roll-off
    o = np.where(o > 0.85, 0.85 + (1 - np.exp(-(o - 0.85) * 4)) * 0.15 / (1 - np.exp(-0.6)), o)
    return c + (o - c) * strength


# ---------------------------------------------------------------- build

def build_lut(look: str = "reference_film", strength: float = 1.0, exposure: float = -1.75,
              conversion: str = "SLog3SGamut3.CineToLC-709TypeA.cube",
              creative_cube: str | None = None, creative_mix: float = 0.0, size: int = 33) -> Path:
    """Bake conversion (+ optional creative .cube) + film look into one LUT in Resolve's LUT folder."""
    key = hashlib.sha1(json.dumps([look, strength, exposure, conversion, creative_cube, creative_mix, size,
                                   LOOKS.get(look)]).encode()).hexdigest()[:8]
    out = OUT_DIR / f"AutoEdit_{look}_{key}.cube"
    if out.exists():
        return out
    grid = identity(size)
    if conversion:
        conv, _ = read_cube(SONY / conversion)
        # exposure in S-Log3 space: one stop ≈ 0.0769 code value (261.5·log10(2)/1023)
        c = apply_cube(conv, np.clip(grid + exposure * 0.0769, 0, 1))
    else:
        c = grid                                         # footage that is already Rec.709 (AI shots, phone clips)
    if creative_cube and creative_mix > 0:
        cr, _ = read_cube(Path(creative_cube))
        c = c + (apply_cube(cr, c) - c) * creative_mix
    if LOOKS.get(look):
        c = film_look(c, LOOKS[look], strength)
    write_cube(out, c, f"AutoEdit {look}")
    return out


def relative(path: Path) -> str:
    """Resolve wants LUT paths relative to its LUT folder."""
    return str(path.relative_to(LUT_ROOT))
