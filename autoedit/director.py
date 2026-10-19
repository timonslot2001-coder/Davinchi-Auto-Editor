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
        title_end = max((x["t1"] for x in plan.texts if x.get("kind") != "corner"), default=1.2)
        if i == 0 or s.rec_in < max(1.2, title_end):
            m.tags.add("intro")                          # the title is on screen
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
        beat = 60 / music.tempo if music and music.tempo else 0.5
        if s.dur >= max(0.75, 1.6 * beat):
            m.tags.add("long")                           # room for a step zoom (3 half-beat steps)
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
    if not hasattr(plan, "_orig_texts"):
        plan._orig_texts = [dict(t) for t in plan.texts]
    plan.texts = [dict(t) for t in plan._orig_texts]
    beat = 60 / music.tempo if music and music.tempo else 0.5

    ms = moments(plan, clips, music)
    by_path = {c.path: c for c in clips}
    used_t: list[float] = [s.rec_in for s in plan.shots if s.effects]          # light leak counts
    count: dict[str, int] = {"light_leak": sum("light_leak" in s.effects for s in plan.shots)}
    last_at: dict[str, float] = {}
    accents = len(used_t)

    # photo series: 3 shots in a row as 'photos' (counts as one accent)
    ser = tech.get("photo_series") or {}
    if ser and accents < max_accents and rng.random() < ser.get("chance", 0.3):
        n = ser.get("length", 3)
        mids = [m for m in ms if not (set(ser.get("avoid", [])) & m.tags)]
        for k in range(len(mids) - n + 1):
            run = [plan.shots[mm.idx] for mm in mids[k:k + n]]
            idxs = [mm.idx for mm in mids[k:k + n]]
            if idxs != list(range(idxs[0], idxs[0] + n)):
                continue
            if any(sh.effects or sh.role != "body" or sh.dur < 0.3 for sh in run):
                continue
            if any(abs(run[0].rec_in - u) < min_gap for u in used_t):
                continue
            for sh in run:
                sh.effects.append("frame_in_frame")
                sh.extra["series"] = True
            # the whole series is one moment: keep breathing room before and after it
            used_t.extend([sh.rec_in for sh in run] + [round(run[-1].rec_in + run[-1].dur, 3)])
            accents += 1
            decisions.append(f"{run[0].rec_in:5.2f}s  photo_series   ({n} shots) because calm stretch")
            break

    # one fair auction over all (technique, moment) pairs: priority + how well the moment fits + a bit of
    # chance, minus a penalty for repeating a technique → varied, creative, but always motivated
    pool = [(k, v) for k, v in tech.items() if v.get("type") == "vfx" and k not in ("dip_to_black", "light_leak")
            and rng.random() < v.get("chance", 1.0)                # occasional techniques sit out some videos
            and not (k == "speed_ramp" and knobs.get("drop_speed_ramp"))]
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
                if set(t.get("avoid", [])) & m.tags:          # e.g. no photo-frame under the title
                    continue
                if any(abs(m.t - u) < min_gap for u in used_t) and "hit" not in m.tags:
                    continue
                if name in last_at and abs(m.t - last_at[name]) < t.get("cooldown_s", 0):
                    continue
                if name == "speed_ramp":
                    c = by_path.get(s.clip)
                    # real slow motion needs real frames: only footage shot at ≥ 2× the timeline rate (50p in 25p)
                    if not c or c.fps < 1.9 * plan.fps:
                        continue
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
        if name == "step_zoom":
            s.extra["beat"] = beat / 2                      # steps on the half beat, like the reference
        if name == "color_wipe":
            s.extra["wipe_color"] = rng.choice([(0.84, 0.15, 0.12), (0.95, 0.91, 0.86)])
        s.effects.append(name)
        used_t.append(m.t)
        count[name] = count.get(name, 0) + 1
        last_at[name] = m.t
        accents += 1
        decisions.append(f"{m.t:5.2f}s  {name:14} because {'+'.join(sorted(set(t.get('trigger', [])) & m.tags))}")

    # title treatment: how the title appears is decided per video (never the same recipe every time)
    ts = tech.get("title_styles") or {}
    tidx = next((i for i, t in enumerate(plan.texts) if t.get("kind") == "minimal"), None)
    if ts and tidx is not None:
        title_txt = plan.texts[tidx]["text"]
        opts = dict(ts.get("options", {"minimal": 1}))
        if len(title_txt.split()) < 2:
            opts.pop("kinetic", None)
        style = rng.choices(list(opts), weights=list(opts.values()))[0]
        t0 = plan.texts[tidx]
        if style == "big":
            t0.update(kind="big", color=ts.get("big_color", "#D7261E"))
        elif style == "card_flash":
            plan.texts.pop(tidx)
            cols = ts.get("card_colors", [["#F3E9DC", "#D7261E"]])
            for k in range(3):
                fg, bg = cols[k % len(cols)]
                plan.texts.append({"t0": round(k * beat, 3), "t1": round((k + 1) * beat, 3), "text": title_txt,
                                   "kind": "card", "color": fg, "bg": bg})
                plan.sfx.append({"t": round(k * beat, 3), "cat": ts.get("sfx_card", "hit"), "gain_db": -13, "why": "title"})
        elif style == "kinetic":
            plan.texts.pop(tidx)
            for k, w in enumerate(title_txt.split()):
                plan.texts.append({"t0": round(k * beat, 3), "t1": round((k + 1) * beat if k + 1 < len(title_txt.split())
                                                                        else (k + 2) * beat, 3),
                                   "text": w, "kind": "word", "color": "#FFFFFF"})
                plan.sfx.append({"t": round(k * beat, 3), "cat": ts.get("sfx_word", "click"), "gain_db": -14, "why": "title"})
        decisions.append(f" 0.00s  title          as '{style}'")
        if rng.random() < ts.get("bookend_chance", 0):
            last = plan.shots[-1]
            kind = "big" if style in ("big", "card_flash") else "minimal"
            plan.texts.append({"t0": round(last.rec_in + 0.3, 3), "t1": round(plan.length - 0.1, 3), "text": title_txt,
                               "kind": kind, "color": ts.get("big_color", "#D7261E") if kind == "big" else None})
            decisions.append(f"{last.rec_in:5.2f}s  title bookend  ({kind}) over the final hold")

    # ear candy: the matching sound for every visual, timed so it lands ON the visual
    lvl = knobs.get("sfx_level_db", 0)
    for s in plan.shots:
        for e in s.effects:
            t = tech.get(e) or {}
            if not t.get("sfx"):
                continue
            at = s.rec_in + (s.speed_ramp or 0) if e == "speed_ramp" else s.rec_in
            if e == "step_zoom":
                for k in range(1, 4):
                    if k * beat / 2 < s.dur - 0.1:
                        plan.sfx.append({"t": round(s.rec_in + k * beat / 2, 3), "cat": t["sfx"],
                                         "gain_db": t.get("sfx_gain_db", -14) + lvl, "why": e})
                continue
            if e == "frame_in_frame" and s.extra.get("series"):
                ser_t = tech.get("photo_series") or {}
                plan.sfx.append({"t": s.rec_in, "cat": ser_t.get("sfx", "shutter"),
                                 "gain_db": ser_t.get("sfx_gain_db", -13) + lvl, "why": "photo_series"})
                continue
            plan.sfx.append({"t": round(max(0.0, at - t.get("sfx_lead_s", 0)), 3), "cat": t["sfx"],
                             "gain_db": t.get("sfx_gain_db", -10) + lvl, "why": e})
    dip = tech.get("dip_to_black") or {}
    for i, s in enumerate(plan.shots):
        if not s.clip and dip.get("sfx") and i + 1 < len(plan.shots):
            plan.sfx.append({"t": plan.shots[i + 1].rec_in, "cat": dip["sfx"],
                             "gain_db": dip.get("sfx_gain_db", -12) + lvl, "why": "dip_to_black"})
            decisions.append(f"{s.rec_in:5.2f}s  dip_to_black   (planner) + {dip['sfx']} on return")
    title = tech.get("title") or {}
    if plan.texts and title.get("sfx") and not any(x["why"] == "title" for x in plan.sfx):
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
