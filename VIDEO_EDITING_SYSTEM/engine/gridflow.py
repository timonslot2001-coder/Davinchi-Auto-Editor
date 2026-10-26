"""Grid Flow transition: the frame is split into an n x n grid and each tile switches from shot A to shot B at its own
moment (ordered by a direction pattern), with a short per-tile exposure flash and thin grid lines that fade in and out.
Re-implemented from the behaviour of Timon's RAM Grid Flow Resolve transition (controls and defaults match); the
.drfx itself is third-party and not shipped. Approved by Timon 2026-10-26 as RULE_GRID_FLOW: 4x4 wipe left + exposure flash, max 1-2x per video."""
from __future__ import annotations

import numpy as np

DIRECTIONS = ("left", "right", "up", "down", "diag_down_right", "diag_up_left", "diag_down_left", "diag_up_right",
              "centre_out", "edges_in", "random", "checkerboard", "spiral")


def _smooth(x):
    x = np.clip(x, 0, 1)
    return x * x * (3 - 2 * x)


def tile_order(n: int, direction: str = "left", seed: int = 0) -> np.ndarray:
    """(n, n) array in 0..1: when each tile switches, relative to the transition. Row 0 = top."""
    r, c = np.mgrid[0:n, 0:n].astype(np.float64)
    m = n - 1
    if direction == "left":                    # starts at the right edge, travels left
        o = (m - c) / m
    elif direction == "right":
        o = c / m
    elif direction == "up":                    # starts at the bottom
        o = (m - r) / m
    elif direction == "down":
        o = r / m
    elif direction == "diag_down_right":
        o = (c + r) / (2 * m)
    elif direction == "diag_up_left":
        o = (2 * m - c - r) / (2 * m)
    elif direction == "diag_down_left":
        o = (m - c + r) / (2 * m)
    elif direction == "diag_up_right":
        o = (c + m - r) / (2 * m)
    elif direction in ("centre_out", "edges_in"):
        d = np.hypot(c - m / 2, r - m / 2)
        o = (d - d.min()) / (d.max() - d.min())
        o = o if direction == "centre_out" else 1 - o
    elif direction == "random":
        o = np.random.default_rng(seed).permutation(n * n).reshape(n, n) / (n * n - 1)
    elif direction == "checkerboard":          # one colour of the board first, then the other, each in reading order
        idx = r * n + c
        first = (r + c) % 2 == 0
        rank = np.empty_like(idx)
        rank[first] = np.argsort(np.argsort(idx[first]))
        rank[~first] = np.argsort(np.argsort(idx[~first])) + first.sum()
        o = rank / (n * n - 1)
    elif direction == "spiral":                # clockwise from the top-left corner inwards
        rank, k = np.zeros((n, n)), 0
        top, left, bottom, right = 0, 0, m, m
        while top <= bottom and left <= right:
            for j in range(left, right + 1):
                rank[top, j], k = k, k + 1
            for i in range(top + 1, bottom + 1):
                rank[i, right], k = k, k + 1
            if top < bottom:
                for j in range(right - 1, left - 1, -1):
                    rank[bottom, j], k = k, k + 1
            if left < right:
                for i in range(bottom - 1, top, -1):
                    rank[i, left], k = k, k + 1
            top, left, bottom, right = top + 1, left + 1, bottom - 1, right - 1
        o = rank / (n * n - 1)
    else:
        raise ValueError(f"unknown grid flow direction {direction!r}; one of {DIRECTIONS}")
    return o


EASE = {"linear": lambda x: x,
        "ease_in": lambda x: np.sqrt(np.maximum(0, x)),
        "ease_out": lambda x: 1 - np.sqrt(np.maximum(0, 1 - x)),
        "ease_in_out": lambda x: np.where(x < 0.5, np.sqrt(np.maximum(0, x / 2)), 1 - np.sqrt(np.maximum(0, (1 - x) / 2)))}


def grid_flow(a: np.ndarray, b: np.ndarray, grid: int = 4, direction: str = "left", timing: str = "linear",
              tile_blend: int = 2, flash: str = "exposure", exposure: float = 4.0, white: float = 1.0,
              rise: int = 2, fall: int = 2, show_grid: bool = True, grid_white: bool = True,
              thickness: float = 0.005, seed: int = 0) -> np.ndarray:
    """a, b: (N, H, W, 3) uint8 frames of the outgoing and incoming shot over the transition. Returns (N, H, W, 3)."""
    N, H, W = a.shape[:3]
    D = N - 1                                                          # frame 0 = pure A, frame N-1 = pure B
    n = grid
    rise, fall = (rise, fall) if flash != "off" else (0, 0)
    k = min(1, max(0, (D - 2) / (2 * max(1e-5, max(tile_blend / 2, rise) + max(tile_blend / 2, fall)))))
    blend, rise, fall = tile_blend * k, rise * k, fall * k                # short transitions shrink the per-tile timings
    s1 = max(1, int(np.ceil(max(blend / 2, rise) - 1e-6)))
    s2 = max(1, int(np.ceil(max(blend / 2, fall) - 1e-6)))
    order = EASE[timing](tile_order(n, direction, seed))
    switch = np.floor(s1 + max(0, D - s1 - s2) * order + 0.5001) if D >= 2 else np.full((n, n), float(D))
    rows = np.minimum(n - 1, (np.arange(H) * n) // H)
    cols = np.minimum(n - 1, (np.arange(W) * n) // W)
    # grid lines: distance to the nearest tile border, anti-aliased, `thickness` of the short side
    gy = np.abs(((np.arange(H) + 0.5) / H * n + 0.5) % 1 - 0.5) * H / n
    gx = np.abs(((np.arange(W) + 0.5) / W * n + 0.5) % 1 - 0.5) * W / n
    line = np.clip(thickness * min(W, H) / 2 + 0.5 - np.minimum(gy[:, None], gx[None, :]), 0, 1) if show_grid else None
    line_rgb = 255.0 if grid_white else 0.0
    out = np.empty_like(a)
    for t in range(N):
        if blend > 0:
            mix = np.clip((t - switch) / blend + 0.5, 0, 1)
        else:
            mix = (t >= switch).astype(np.float64)
        mix = np.zeros((n, n)) if t <= 0 else np.ones((n, n)) if t >= D else _smooth(mix)
        if flash != "off" and 0 < t < D:
            g = np.where(np.abs(t - switch) < 1e-5, 1.0,
                         np.where(t < switch, np.maximum(0, 1 - (switch - t) / max(1e-5, rise)) if rise > 0 else 0.0,
                                  np.maximum(0, 1 - (t - switch) / max(1e-5, fall)) if fall > 0 else 0.0))
            g = _smooth(g)
        else:
            g = np.zeros((n, n))
        m = mix[rows][:, cols][..., None]
        gp = g[rows][:, cols][..., None]
        f = a[t].astype(np.float32) * (1 - m) + b[t].astype(np.float32) * m
        if flash == "exposure":
            f = f * np.power(2.0, exposure * gp)
        elif flash == "white":
            f = f * (1 - white * gp) + 255 * white * gp
        if line is not None:
            fade = _smooth(min(t, D - t) / max(1e-5, min(2, D / 2)))
            la = (line * fade)[..., None]
            f = f * (1 - la) + line_rgb * la
        out[t] = np.clip(f, 0, 255).astype(np.uint8)
    return out
