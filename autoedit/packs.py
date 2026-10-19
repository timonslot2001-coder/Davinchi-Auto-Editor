"""Index of your bought editor packs (FOUR Editors overlays, overlay-transitions, film textures).

Every 1080p overlay file is indexed by category with its duration/fps, so the director can pick a real
light leak / film burn / doodle / glitch instead of a generated one. Cached in data/packs_index.json.
"""
from __future__ import annotations

import json
import random
from pathlib import Path

import cv2

from .config import DATA

INDEX = DATA / "packs_index.json"
VIDEO = {".mp4", ".mov"}
# categories we never use automatically (branding in the file, or needs a luma track matte = future)
SKIP = {"Abstract Brush", "Punch Hole", "Cinemarkers", "CineSnip", "Poster Wall", "Granular", "Split Frames"}


def _category(path: Path, root: Path) -> str | None:
    parts = path.relative_to(root).parts
    for i, p in enumerate(parts):
        if p.lower() in ("1080p", "4k"):
            return parts[i - 1].strip() if i else None
    return parts[-2].strip() if len(parts) > 1 else None


def build(roots: list[str], force: bool = False) -> dict:
    if INDEX.exists() and not force:
        idx = json.loads(INDEX.read_text(encoding="utf-8"))
        if idx.get("roots") == roots:
            return idx
    cats: dict[str, list[dict]] = {}
    for r in roots:
        root = Path(r)
        if not root.exists():
            continue
        for f in root.rglob("*"):
            if f.suffix.lower() not in VIDEO or "__MACOSX" in f.parts or "4K" in f.parts:
                continue
            cat = _category(f, root)
            if not cat or cat in SKIP:
                continue
            cap = cv2.VideoCapture(str(f))
            fps = cap.get(5) or 25.0
            n = cap.get(7) or 0
            cap.release()
            if n <= 0:
                continue
            cats.setdefault(cat, []).append({"path": str(f), "dur": round(n / fps, 3), "fps": round(fps, 3)})
    idx = {"roots": roots, "categories": {k: sorted(v, key=lambda x: x["path"]) for k, v in sorted(cats.items())}}
    INDEX.write_text(json.dumps(idx, indent=1), encoding="utf-8")
    return idx


class Packs:
    def __init__(self, cfg, seed: int = 0):
        self.idx = build(cfg.get("paths.pack_folders", []) or [])
        self.rng = random.Random(seed)
        self.used: set[str] = set()

    @property
    def available(self) -> bool:
        return bool(self.idx.get("categories"))

    def pick(self, categories: list[str], min_dur: float = 0.0, max_dur: float = 99.0) -> dict | None:
        pool = [f for c in categories for f in self.idx["categories"].get(c, []) if min_dur <= f["dur"] <= max_dur]
        fresh = [f for f in pool if f["path"] not in self.used] or pool
        if not fresh:
            return None
        f = self.rng.choice(fresh)
        self.used.add(f["path"])
        return f

    def summary(self) -> dict[str, int]:
        return {k: len(v) for k, v in self.idx.get("categories", {}).items()}
