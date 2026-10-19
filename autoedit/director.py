"""Director: places eye candy (VFX) + ear candy (SFX) from inventory.yaml — only where it's motivated.

For every cut it builds a picture of the moment (music hit? downbeat? motion? scene change? quiet?),
then lets the techniques bid for the moments that match their trigger. Budget, cooldowns and your
taste.yaml keep it natural: no effect is better than a random effect, and every visual gets the sound
that belongs to it (risers/swells start early so they land ON the visual).
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .analyze import ClipAnalysis, MusicAnalysis
from .config import ROOT
from .planner import Plan

VFX_IN_FX = {"whip", "light_leak", "frame_in_frame", "punch_zoom", "white_flash", "glitch", "shake", "smooth_zoom"}


def load_inventory() -> dict:
    return yaml.safe_load((ROOT / "inventory.yaml").read_text(encoding="utf-8"))


def load_taste() -> dict:
    f = ROOT / "taste.yaml"
    return yaml.safe_load(f.read_text(encoding="utf-8")) if f.exists() else {"knobs": {}}


@dataclass
class Moment:
    idx: int                     # shot index in plan.shots
    t: float                     # cut time on the timeline
    tags: set = field(default_factory=set)
    strength: float = 0.0        # how strong the musical moment is (0..1)
    motion: float = 0.0


def _segment_motion(c: ClipAnalysis, t: float) -> float:
    for s in c.segments:
        if s.start - 0.3 <= t <= s.end + 0.3:
            return s.motion
    return c.motion


def moments(plan: Plan, clips: list[ClipAnalysis], music: MusicAnalysis | None) -> list[Moment]:
    by_path = {c.path: c for c in clips}
    hits = list(music.hits) if music and music.hits else []
    downs = list(music.downbeats) if music else []
    out = []
    shots = plan.shots
    for i, s in enumerate(shots):
        if not s.clip:
            continue
        m = Moment(i, s.rec_in)
        c = by_path.get(s.clip)
        m.motion = _segment_motion(c, s.src_in) if c else 0.0
        if i == 0 or s.rec_in < 1.2:
            m.tags.add("intro")
        if s.role == "outro":
            m.tags.add("last_hit")
        near_hit = [h for h in hits if abs(h - s.rec_in) <= 0.12]
        if near_hit:
            m.tags.add("hit")
            m.strength = 1.0 if (hits and near_hit[0] == min(hits)) else 0.8
            if hits and abs(near_hit[0] - hits[0]) < 0.01:
                m.tags.add("first_hit")
        if any(abs(d - s.rec_in) <= 0.1 for d in downs):
            m.tags.add("downbeat")
            m.strength = max(m.strength, 0.5)
        e = music.energy_at(s.rec_in) if music else 0.5
        if e < 0.3:
            m.tags.add("quiet")
        if m.motion > 0.45:
            m.tags.add("motion")
        prev = shots[i - 1] if i > 0 else None
        if prev is not None and prev.clip and prev.clip != s.clip:
            m.tags.add("scene")
        out.append(m)
    return out


def direct(plan: Plan, clips: list[ClipAnalysis], music: MusicAnalysis | None, seed: int = 0,
           log=print, overrides: dict | None = None) -> list[str]:
    """Rewrites plan.shots[*].effects and plan.sfx. Returns a human-readable list of decisions."""
    inv, taste = load_inventory(), load_taste()
    knobs = dict(taste.get("knobs", {}) or {})
    knobs.update(overrides or {})
    budget = inv["budget"]
    tech = inv["techniques"]
    rng = random.Random(f"director{seed}{plan.variant}")
    length = plan.length
    max_accents = max(1, round(budget["accents_per_10s"] * length / 10 * knobs.get("accents_scale", 1.0)))
    max_sfx = max(1, round(budget["sfx_per_10s"] * length / 10 * knobs.get("sfx_scale", 1.0)))
    min_gap = budget.get("min_gap_s", 1.4)

    # structural pieces the planner already decided (dip to black, light leak on the final hold) are kept;
    # everything else is re-decided here
    for s in plan.shots:
        s.effects = [e for e in s.effects if e == "light_leak"]
        s.speed_ramp = None
    plan.sfx = []
    decisions = []

    ms = moments(plan, clips, music)
    by_path = {c.path: c for c in clips}
    used_t: list[float] = [s.rec_in for s in plan.shots if s.effects]          # light leak counts
    count: dict[str, int] = {"light_leak": sum("light_leak" in s.effects for s in plan.shots)}
    last_at: dict[str, float] = {}
    accents = len(used_t)

    # one fair auction over all (technique, moment) pairs: priority + how well the moment fits + a bit of
    # chance, minus a penalty for repeating a technique → varied, creative, but always motivated
    pool = [(k, v) for k, v in tech.items() if v.get("type") == "vfx" and k not in ("dip_to_black", "light_leak")]
    while accents < max_accents:
        best = None
        for name, t in pool:
            if count.get(name, 0) >= t.get("max", 1):
                continue
            trig = set(t.get("trigger", []))
            for m in ms:
                s = plan.shots[m.idx]
                if s.effects or s.role in ("outro", "black") or not (trig & m.tags):
                    continue
                if any(abs(m.t - u) < min_gap for u in used_t) and "hit" not in m.tags:
                    continue
                if name in last_at and abs(m.t - last_at[name]) < t.get("cooldown_s", 0):
                    continue
                if name == "speed_ramp":
                    c = by_path.get(s.clip)
                    if s.dur < 0.9 or not any(s.src_in + 0.3 < p < s.src_out - 0.2 for p in (c.motion_peaks if c else [])):
                        continue
                fit = len(trig & m.tags) + 2 * m.strength + (2 * m.motion if "motion" in trig else 0)
                score = 0.35 * t.get("priority", 0) + fit + rng.uniform(0, 2.0) - 3.0 * count.get(name, 0)
                if best is None or score > best[0]:
                    best = (score, name, t, m)
        if best is None:
            break
        _, name, t, m = best
        s = plan.shots[m.idx]
        if name == "speed_ramp":
            c = by_path.get(s.clip)
            s.speed_ramp = round(next(p for p in c.motion_peaks if s.src_in + 0.3 < p < s.src_out - 0.2) - s.src_in, 3)
        s.effects.append(name)
        used_t.append(m.t)
        count[name] = count.get(name, 0) + 1
        last_at[name] = m.t
        accents += 1
        decisions.append(f"{m.t:5.2f}s  {name:14} because {'+'.join(sorted(set(t.get('trigger', [])) & m.tags))}")

    # ear candy: the matching sound for every visual, timed so it lands ON the visual
    lvl = knobs.get("sfx_level_db", 0)
    for s in plan.shots:
        for e in s.effects:
            t = tech.get(e) or {}
            if not t.get("sfx"):
                continue
            at = s.rec_in + (s.speed_ramp or 0) if e == "speed_ramp" else s.rec_in
            plan.sfx.append({"t": round(max(0.0, at - t.get("sfx_lead_s", 0)), 3), "cat": t["sfx"],
                             "gain_db": t.get("sfx_gain_db", -10) + lvl, "why": e})
    dip = tech.get("dip_to_black") or {}
    for i, s in enumerate(plan.shots):
        if not s.clip and dip.get("sfx") and i + 1 < len(plan.shots):
            plan.sfx.append({"t": plan.shots[i + 1].rec_in, "cat": dip["sfx"],
                             "gain_db": dip.get("sfx_gain_db", -12) + lvl, "why": "dip_to_black"})
            decisions.append(f"{s.rec_in:5.2f}s  dip_to_black   (planner) + {dip['sfx']} on return")
    title = tech.get("title") or {}
    if plan.texts and title.get("sfx"):
        plan.sfx.append({"t": 0.05, "cat": title["sfx"], "gain_db": title.get("sfx_gain_db", -16) + lvl, "why": "title"})
    # sfx budget: keep the most important sounds
    prio = {k: v.get("priority", 0) for k, v in tech.items()}
    prio["dip_to_black"] = tech.get("dip_to_black", {}).get("priority", 5)
    plan.sfx.sort(key=lambda x: -prio.get(x["why"], 0))
    plan.sfx = sorted(plan.sfx[:max_sfx], key=lambda x: x["t"])

    for s in plan.shots:
        if "light_leak" in s.effects:
            decisions.append(f"{s.rec_in:5.2f}s  light_leak     because last_hit (final hold)")
    decisions.sort()
    plan.markers = [{"t": s.rec_in, "name": (s.effects[0] if s.effects else ("black" if not s.clip else "cut")),
                     "note": next((d for d in decisions if d.startswith(f"{s.rec_in:5.2f}s")), "")}
                    for s in plan.shots]
    for d in decisions:
        log(f"  🎬 {d}")
    log(f"  accents {accents}/{max_accents}, sounds {len(plan.sfx)}/{max_sfx}")
    return decisions
