"""Performance feedback: pull stats of posted Reels, score them, learn what works.

Score = what the platforms reward now: watch time, sends (DM shares) and saves per reach,
more than likes. Learned results feed back into:
  - hashtag weights (social.py picks your best-performing tags more often)
  - best posting times (config posting.best_times gets updated)
  - style report (which preset / effects / hook did best) → `autoedit report`
"""
from __future__ import annotations

import json
import os
from collections import defaultdict
from datetime import datetime

import requests
import yaml

from . import publish
from .config import DATA, ROOT

PERF = DATA / "performance.json"


def _ig_insights(media_id: str, tok: str) -> dict:
    metrics = "reach,views,saved,shares,likes,comments,total_interactions,ig_reels_avg_watch_time"
    r = requests.get(f"{publish.GRAPH}/{media_id}/insights", params={"metric": metrics, "access_token": tok}, timeout=30)
    if not r.ok:
        return {}
    return {d["name"]: (d.get("values") or [{}])[0].get("value", 0) for d in r.json().get("data", [])}


def score(m: dict) -> float:
    reach = max(1, m.get("reach", 0) or m.get("views", 0))
    watch_s = (m.get("ig_reels_avg_watch_time", 0) or 0) / 1000
    return round(100 * (3 * m.get("shares", 0) + 2 * m.get("saved", 0) + m.get("likes", 0) * 0.5
                        + m.get("comments", 0)) / reach + watch_s, 3)


def refresh() -> dict:
    tok = os.environ.get("IG_ACCESS_TOKEN")
    data = json.loads(PERF.read_text()) if PERF.exists() else {"posts": []}
    known = {p["media_id"]: p for p in data["posts"]}
    for e in publish.entries():
        ig = e.get("results", {}).get("instagram", {})
        if not ig.get("ok") or not tok:
            continue
        m = _ig_insights(ig["media_id"], tok)
        if not m:
            continue
        known[ig["media_id"]] = {
            "media_id": ig["media_id"], "entry": e["id"], "style": e["style"], "posted_at": ig.get("posted_at"),
            "hashtags": ig.get("hashtags", []), "hook": e.get("meta", {}).get("hook"),
            "effects": e.get("meta", {}).get("effects", {}), "metrics": m, "score": score(m),
            "updated": datetime.now().isoformat(timespec="seconds")}
    data["posts"] = list(known.values())
    PERF.write_text(json.dumps(data, indent=1))
    return data


def learn_best_times(min_posts: int = 6) -> dict | None:
    """Move posting slots towards the weekday/hour combinations that scored best for you."""
    data = json.loads(PERF.read_text()) if PERF.exists() else {"posts": []}
    posts = [p for p in data["posts"] if p.get("posted_at")]
    if len(posts) < min_posts:
        return None
    buckets = defaultdict(list)
    for p in posts:
        t = datetime.fromisoformat(p["posted_at"])
        buckets[(t.strftime("%a"), t.hour)].append(p["score"])
    ranked = sorted(buckets.items(), key=lambda kv: -sum(kv[1]) / len(kv[1]))[:4]
    slots = [f"{d} {h:02d}:00" for (d, h), _ in ranked]
    cfg_path = ROOT / "config.yaml"
    text = cfg_path.read_text(encoding="utf-8")
    cfg = yaml.safe_load(text)
    cfg["posting"]["best_times"]["instagram"] = slots
    # keep comments in config.yaml: only rewrite the instagram line
    lines = text.splitlines()
    for i, ln in enumerate(lines):
        if ln.strip().startswith("instagram: [") and "best_times" in "\n".join(lines[max(0, i - 3):i]):
            lines[i] = ln.split("instagram:")[0] + "instagram: " + json.dumps(slots)
    cfg_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"instagram": slots}


def report() -> str:
    data = json.loads(PERF.read_text()) if PERF.exists() else {"posts": []}
    posts = sorted(data["posts"], key=lambda p: -p["score"])
    if not posts:
        return "No stats yet: post something with `autoedit post`, then run `autoedit stats` a day later."
    by_style = defaultdict(list)
    for p in posts:
        by_style[p["style"]].append(p["score"])
    out = ["Score = (3×shares + 2×saves + comments + ½×likes) / reach ×100 + avg watch time (s)", ""]
    out += [f"{s:10} avg {sum(v) / len(v):6.2f}  ({len(v)} posts)" for s, v in by_style.items()]
    out += ["", "Top posts:"]
    out += [f"  {p['score']:6.2f}  {p['style']:9} {p.get('hook') or ''}  {' '.join(p['hashtags'])}" for p in posts[:5]]
    return "\n".join(out)
