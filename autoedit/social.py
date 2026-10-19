"""Caption + hashtag suggestions per platform, built from trends.yaml and your performance history."""
from __future__ import annotations

import json
import random
from pathlib import Path

import yaml

from .config import DATA, ROOT


def trends() -> dict:
    return yaml.safe_load((ROOT / "trends.yaml").read_text(encoding="utf-8"))


def hooks(style: str) -> list[str]:
    t = trends()
    return t.get(style, t["lifestyle"])["hooks"]


def _hashtag_weights(style: str) -> dict[str, float]:
    """Tags that did well on your own posts get picked more often (see performance.py)."""
    f = DATA / "performance.json"
    if not f.exists():
        return {}
    w: dict[str, list[float]] = {}
    for post in json.loads(f.read_text()).get("posts", []):
        if post.get("style") == style:
            for tag in post.get("hashtags", []):
                w.setdefault(tag, []).append(post.get("score", 0))
    return {k: sum(v) / len(v) for k, v in w.items()}


def suggest(style: str, hook: str, platform: str, location: str | None = None, n: int = 3,
            seed: int = 0) -> list[dict]:
    """Returns n caption options: {caption, hashtags, full}."""
    t = trends()
    d = t.get(style, t["lifestyle"])
    rng = random.Random(f"{seed}{platform}{style}")
    max_tags = t["rules"]["max_hashtags"].get(platform, 5)
    weights = _hashtag_weights(style)
    kw = d["keywords"]
    loc = f" in {location}" if location else ""
    templates = [
        lambda: f"{hook}{loc} 👀\n{rng.choice(kw).capitalize()} that actually works — save this for later.",
        lambda: f"{rng.choice(kw).capitalize()}{loc} — {hook}\nWhich one would you try first? 👇",
        lambda: f"{hook}{loc}\nSend this to the friend who needs a {rng.choice(kw)} reminder 📩",
        lambda: f"{rng.choice(kw).capitalize()} diary{loc} 🎬\n{hook}. Part 2?",
    ]
    rng.shuffle(templates)
    out = []
    for i in range(n):
        pool = sorted(d["hashtags"], key=lambda h: -(weights.get(h, 0) + rng.random() * 0.5))
        if platform == "tiktok" and style == "fitness" and "#gymtok" not in pool[:max_tags]:
            pool.insert(0, "#gymtok")
        if platform == "tiktok" and style == "travel" and "#traveltok" not in pool[:max_tags]:
            pool.insert(0, "#traveltok")
        tags = [h for h in pool if h not in t["rules"]["avoid_hashtags"]
                and not (platform == "instagram" and h.endswith("tok"))][:max_tags]
        caption = templates[i % len(templates)]()
        out.append({"caption": caption, "hashtags": tags, "full": f"{caption}\n\n{' '.join(tags)}"})
    return out
