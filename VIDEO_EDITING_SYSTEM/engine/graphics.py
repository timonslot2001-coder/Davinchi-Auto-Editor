"""Render the DNA's HTML components (EDITING_DNA_PACKAGE/animations_and_components/components.html) to transparent
RGBA PNGs with headless Microsoft Edge. Static devices (title, labels) are captured once and composited per frame."""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from urllib.parse import urlencode

import cv2
import numpy as np

from . import DNA_DIR

EDGE_CANDIDATES = [Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
                   Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
                   Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")]
COMPONENTS = DNA_DIR / "animations_and_components" / "components.html"


def browser() -> Path:
    for p in EDGE_CANDIDATES:
        if p.exists():
            return p
    raise RuntimeError("no Chromium browser found for HTML capture (Edge/Chrome)")


def capture(params: dict, size: tuple[int, int], cache: Path) -> np.ndarray:
    """RGBA uint8 (BGRA order) of one component frame on a transparent background."""
    cache.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha1(json.dumps([params, size, COMPONENTS.stat().st_mtime]).encode()).hexdigest()[:12]
    out = cache / f"gfx_{params.get('c')}_{key}.png"
    if not out.exists():
        url = COMPONENTS.as_uri() + "?" + urlencode({**params, "transparent": 1})
        subprocess.run([str(browser()), "--headless=new", "--disable-gpu", "--hide-scrollbars",
                        "--allow-file-access-from-files", "--default-background-color=00000000",
                        "--virtual-time-budget=4000", f"--window-size={size[0]},{size[1]}", f"--screenshot={out}", url],
                       check=True, capture_output=True, timeout=90)
    img = cv2.imread(str(out), cv2.IMREAD_UNCHANGED)
    if img is None or img.shape[2] != 4:
        raise RuntimeError(f"capture failed or not transparent: {out}")
    if img.shape[1] != size[0]:
        img = cv2.resize(img, size, interpolation=cv2.INTER_AREA)
    return img


TITLE_VARIANTS = {
    "poster_condensed": {"width": "0.92", "height": "0.70"},
    "heavy_grotesque": {"width": "0.73", "font": "grotesque"},
}


def title_png(text: str, color: str, variant: str, size, cache: Path) -> np.ndarray:
    v = TITLE_VARIANTS.get(variant, TITLE_VARIANTS["poster_condensed"])
    return capture({"c": "title_slam", "text": text, "color": color, **v}, size, cache)


def labels_png(left: str, right: str, size, cache: Path) -> np.ndarray:
    return capture({"c": "side_labels", "text": left, "text2": right}, size, cache)
