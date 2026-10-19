"""Turns analysed clips + music + a style into an edit plan (pure data, no Resolve needed).

The plan is saved as JSON next to the export, so every edit is reproducible and you can
inspect/tweak it before it's built.
"""
from __future__ import annotations

import json
import random

import numpy as np
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .analyze import ClipAnalysis, MusicAnalysis

EFFECTS = ["punch_zoom", "smooth_zoom", "shake", "invert_flash", "white_flash", "whip", "glitch"]
SFX_FOR = {"punch_zoom": "zoom", "smooth_zoom": "zoom", "shake": "zoom", "invert_flash": "flash",
           "white_flash": "flash", "whip": "cut", "glitch": "flash"}


@dataclass
class Shot:
    clip: str
    src_in: float
    src_out: float
    rec_in: float
    effects: list[str] = field(default_factory=list)
    speed_ramp: float | None = None     # seconds into the shot where it slows down
    stabilize: bool = False
    role: str = "body"                  # hook / body / outro / loop

    @property
    def dur(self) -> float:
        return self.src_out - self.src_in


@dataclass
class Grid:
    rec_in: float
    interval: float                     # time between panels popping in
    hold: float
    panels: list[dict]                  # [{clip, src_in}]

    @property
    def dur(self) -> float:
        return self.interval * 6 + self.hold


@dataclass
class Plan:
    style: str
    fps: float
    length: float
    shots: list[Shot]
    grid: Grid | None
    sfx: list[dict]                     # {t, cat, gain_db}
    texts: list[dict]                   # {t0, t1, text, kind}
    markers: list[dict]                 # {t, name, note}
    music: dict | None
    overlay: dict | None
    variant: str = "A"
    mode: str = "montage"               # montage / talking

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=1)

    @staticmethod
    def from_json(s: str) -> "Plan":
        d = json.loads(s)
        d["shots"] = [Shot(**x) for x in d["shots"]]
        d["grid"] = Grid(**d["grid"]) if d["grid"] else None
        return Plan(**d)


def _snap(t: float, grid: list[float], tol: float) -> float:
    if not grid:
        return t
    best = min(grid, key=lambda g: abs(g - t))
    return best if abs(best - t) <= tol else t


def _cut_points(length: float, style: dict, music: MusicAnalysis | None, offset: float) -> list[float]:
    """Cut times on the timeline. With music: on beats, shot length following the pacing curve."""
    pace = style["pacing"]
    hook_end = min(2.0, length * 0.15)
    outro_start = length * 0.82
    beats = [b - offset for b in music.beats if b - offset > 0] if music and style.get("cut_on_beat") else []
    cuts, t = [0.0], 0.0
    while True:
        target = pace["hook"] if t < hook_end else pace["outro"] if t > outro_start else pace["body"]
        nxt = t + target
        if beats:
            nxt = _snap(nxt, [b for b in beats if b > t + 0.3], tol=target * 0.6)
        if nxt >= length - 0.3:
            break
        cuts.append(round(nxt, 3))
        t = nxt
    cuts.append(round(length, 3))
    return cuts


def _split_on_silence(clip: ClipAnalysis, a: float, b: float) -> tuple[float, float]:
    """Silence cutter: trim a window so it doesn't start/end in (or span) a dead moment."""
    for s, e in clip.silences:
        if s <= a < e:
            a = e
        if s < b <= e:
            b = s
        if a < s and e < b:          # silence in the middle → keep the longer side
            b = s if s - a >= b - e else b
            a = a if s - a >= b - e else e
    return a, b


def make_plan(clips: list[ClipAnalysis], style: dict, cfg, music: MusicAnalysis | None = None,
              variant: str = "A", seed: int = 7, stab_mode: str | None = None) -> Plan:
    rng = random.Random(f"{seed}{variant}")
    fps = float(cfg.get("camera.fps", 25))
    usable = [c for c in clips if not c.rejected_reason and c.segments]
    if not usable:
        raise SystemExit("No usable clips (all too dark/blurry/short).")

    stab_mode = stab_mode or cfg.get("stabilization.mode", "auto")
    overrides = cfg.get("stabilization.overrides", {}) or {}
    thr = cfg.get("stabilization.shake_threshold", 0.35)

    def stabilize(c: ClipAnalysis) -> bool:
        if c.name in overrides:
            return bool(overrides[c.name])
        return {"all": True, "none": False}.get(stab_mode, c.shake >= thr)

    talking = sum(c.has_speech for c in usable) > len(usable) / 2 and music is None
    max_len, min_len = cfg.get("format.max_length_s", 30), cfg.get("format.min_length_s", 7)
    material = sum(min(c.duration, 6) for c in usable)
    length = max(min_len, min(max_len, material * 0.8))
    offset = 0.0
    if music:
        # start the music so the drop lands ~35% into the video (energy where people drop off)
        if music.drop and music.drop > length * 0.35:
            offset = max(0.0, music.drop - length * 0.35)
            offset = _snap(offset, music.downbeats, 1.0)
        length = min(length, music.duration - offset)

    # ------------------------------------------------ grid section
    grid = None
    want_grid = style.get("grid6") and len(usable) >= 3 and length >= 10
    grid_at = grid_dur = 0.0
    if want_grid:
        beat = 60 / music.tempo if music else 0.4
        interval = max(0.22, min(0.5, beat))
        while interval < 0.3:
            interval *= 2
        hold = 0.9
        grid_dur = interval * 6 + hold
        grid_at = length * 0.55
        if music:
            grid_at = _snap(grid_at, [d - offset for d in music.downbeats], 1.5)

    # ------------------------------------------------ shots
    cuts = _cut_points(length, style, music, offset)
    if want_grid:
        cuts = [c for c in cuts if not (grid_at - 0.2 < c < grid_at + grid_dur + 0.2)]
        cuts = sorted(set(cuts + [round(grid_at, 3), round(grid_at + grid_dur, 3)]))
    # no flash-frame shots: merge cuts closer than 0.28 s (7 frames) (but keep the grid boundaries)
    keep = {round(grid_at, 3), round(grid_at + grid_dur, 3)} if want_grid else set()
    merged = [cuts[0]]
    for c in cuts[1:]:
        if c - merged[-1] < 0.28 and c not in keep and c != cuts[-1]:
            continue
        if c - merged[-1] < 0.28 and merged[-1] not in keep and len(merged) > 1:
            merged[-1] = c
            continue
        merged.append(c)
    cuts = merged

    used: dict[str, list[tuple[float, float]]] = {c.path: [] for c in usable}
    by_path = {c.path: c for c in usable}

    def free(c: ClipAnalysis, a: float, b: float) -> bool:
        return all(b <= x or a >= y for x, y in used[c.path])

    def pick(dur: float, prev: str | None, prefer_motion: bool | None, hook=False) -> tuple[ClipAnalysis, float, float]:
        best, best_score = None, -1e9
        for c in usable:
            for s in c.segments:
                if s.length < min(dur, 0.6):
                    continue
                a = s.start + max(0.0, (s.length - dur) / 2)
                b = min(c.duration - 0.05, a + dur)
                a = max(0.0, b - dur)
                if c.has_speech:
                    a, b = _split_on_silence(c, a, b)
                    if b - a < min(dur, 0.6):
                        continue
                if not free(c, a, b):
                    continue
                score = s.score
                score -= 0.6 if c.path == prev else 0           # variety guard: no same clip twice in a row
                score -= 0.15 * len(used[c.path])                # spread usage across clips
                if prefer_motion is not None:                    # alternate calm / energetic shots
                    score += 0.2 * (s.motion if prefer_motion else 1 - s.motion)
                if hook:
                    score += 0.5 * s.motion + (0.2 if s.face else 0)
                score += rng.uniform(0, 0.08)
                if score > best_score:
                    best, best_score = (c, a, b), score
        if best is None:                                         # everything used: allow reuse
            c = max(usable, key=lambda c: c.segments[0].score)
            s = c.segments[0]
            return c, s.start, min(s.end, s.start + dur)
        return best

    shots: list[Shot] = []
    prev = None
    for i, (a, b) in enumerate(zip(cuts, cuts[1:])):
        if want_grid and abs(a - grid_at) < 0.01:
            continue                                             # grid occupies this slot
        dur = b - a
        role = "hook" if a < 2.0 else "outro" if a > length * 0.82 else "body"
        c, sa, sb = pick(dur, prev, prefer_motion=(i % 2 == 0), hook=(role == "hook"))
        sb = sa + min(dur, sb - sa)
        used[c.path].append((sa, sb))
        shots.append(Shot(c.path, round(sa, 3), round(sb, 3), round(a, 3), role=role, stabilize=stabilize(c)))
        prev = c.path

    # close gaps created by silence trimming (keeps the timeline continuous)
    t, grid_placed = 0.0, False
    for s in shots:
        if want_grid and not grid_placed and s.rec_in >= grid_at - 0.01:
            grid_at, grid_placed = t, True
            t += grid_dur
        s.rec_in = round(t, 3)
        t += s.dur
    if want_grid and not grid_placed:
        grid_at = t
        t += grid_dur
    length = round(t, 3)

    if want_grid:
        panel_clips = sorted(usable, key=lambda c: -c.segments[0].score)[:6]
        while len(panel_clips) < 6:
            panel_clips.append(panel_clips[len(panel_clips) % max(1, len(usable))])
        panels = [{"clip": c.path, "src_in": round(c.segments[min(1, len(c.segments) - 1)].start, 3)}
                  for c in panel_clips]
        grid = Grid(rec_in=round(grid_at, 3), interval=round(interval, 3), hold=hold, panels=panels)

    # ------------------------------------------------ loop ending: last shot flows into the first
    if style.get("loop_ending") and len(shots) > 3:
        first, last = shots[0], shots[-1]
        d = last.dur
        if first.src_in >= d and not by_path[first.clip].has_speech:
            # the final shot shows the moment just before the opening shot → the replay feels seamless
            last.clip = first.clip
            last.src_in, last.src_out = round(first.src_in - d, 3), first.src_in
            last.stabilize = first.stabilize
            last.role = "loop"

    # ------------------------------------------------ effects + speed ramps + retention
    probs = style.get("effects", {})
    sfx_map = style.get("sfx", {})
    sfx: list[dict] = []
    last_event = -9.0
    retention = style.get("retention_interval_s", 2.5)
    for i, s in enumerate(shots):
        if i == 0:
            s.effects.append("punch_zoom")                     # hook: always start with energy
        else:
            for fx in EFFECTS:
                if rng.random() < probs.get(fx, 0) and len(s.effects) < 2:
                    if fx in ("invert_flash", "white_flash", "glitch") and any(
                            e in s.effects for e in ("invert_flash", "white_flash", "glitch")):
                        continue
                    s.effects.append(fx)
        # retention: force a pattern interrupt if nothing happened for too long
        if not s.effects and s.rec_in - last_event >= retention:
            s.effects.append(rng.choice(["punch_zoom", "smooth_zoom", "whip"]))
        c = by_path.get(s.clip)
        peaks = [p - s.src_in for p in (c.motion_peaks if c else []) if s.src_in + 0.3 < p < s.src_out - 0.2]
        if peaks and s.dur >= 0.9 and rng.random() < probs.get("speed_ramp", 0):
            s.speed_ramp = round(peaks[0], 3)
            if sfx_map.get("ramp"):
                sfx.append({"t": round(max(0, s.rec_in + s.speed_ramp - 1.2), 3), "cat": sfx_map["ramp"], "gain_db": -9})
        for fx in s.effects:
            cat = sfx_map.get(SFX_FOR[fx])
            if cat:
                sfx.append({"t": s.rec_in, "cat": cat, "gain_db": 0 if fx != "smooth_zoom" else -4})
        if s.effects:
            last_event = s.rec_in

    if grid:
        for k in range(6):
            sfx.append({"t": round(grid.rec_in + k * grid.interval, 3), "cat": sfx_map.get("grid", "click"), "gain_db": -2})
        sfx.append({"t": round(grid.rec_in + grid.dur, 3), "cat": "whoosh", "gain_db": -3})

    # ------------------------------------------------ text hook
    texts = []
    if style.get("hook_text"):
        from .social import hooks
        bank = hooks(style["name"])
        texts.append({"t0": 0.0, "t1": min(2.5, length), "text": bank[(ord(variant) - 65) % len(bank)], "kind": "hook"})

    markers = [{"t": s.rec_in, "name": "+".join(s.effects) or "cut",
                "note": f"{Path(s.clip).name} {s.src_in:.2f}-{s.src_out:.2f}"} for s in shots]
    overlay = style.get("overlay") if (style.get("overlay") or {}).get("enabled") else None
    music_d = {"path": music.path, "offset": offset, "tempo": music.tempo} if music else None
    return Plan(style["name"], fps, length, shots, grid, sorted(sfx, key=lambda x: x["t"]), texts, markers,
                music_d, overlay, variant, "talking" if talking else "montage")


# ================================================================ cinematic mode
# Modelled on a reference travel edit (LA, Oct 2026): detail → street → subject → architecture → wide
# hold; constant ~2-beat rhythm, only the first cuts fast; no added effects except one dip to black and
# a light leak into the final hold; small spaced-out title. "Less is more."

ARC = ["detail", "detail", "establish", "subject", "subject", "close", "action", "subject",
       "establish", "rest", "close", "subject", "action", "rest"]


def load_tags() -> dict:
    from .config import DATA
    f = DATA / "tags.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}


def make_cinematic_plan(clips: list[ClipAnalysis], style: dict, cfg, music: MusicAnalysis | None = None,
                        variant: str = "A", seed: int = 7, stab_mode: str | None = None,
                        title: str | None = None) -> Plan:
    rng = random.Random(f"{seed}{variant}")
    fps = float(cfg.get("camera.fps", 25))
    usable = [c for c in clips if not c.rejected_reason and c.segments]
    if not usable:
        raise SystemExit("No usable clips.")
    tags = load_tags()
    role_of = {c.path: (tags.get(c.name) or {}).get("role") for c in usable}
    thr = cfg.get("stabilization.shake_threshold", 0.35)
    overrides = cfg.get("stabilization.overrides", {}) or {}
    mode = stab_mode or cfg.get("stabilization.mode", "auto")

    def stabilize(c):
        if c.name in overrides:
            return bool(overrides[c.name])
        return {"all": True, "none": False}.get(mode, c.shake >= thr)

    # rhythm: 2 beats per shot at fast tempos (≈0.75–0.9 s), else 1 beat; fixed fallback without music
    if music and music.tempo:
        beat = 60 / music.tempo
        step = beat * max(1, round(style.get("shot_s", 0.8) / beat))     # whole beats closest to ~0.8 s
    else:
        step = style.get("shot_s", 0.8)
    quick = style.get("intro_cuts", [0.27, 0.25])
    hold = style.get("final_hold", 1.7)
    length = style.get("length_s", 13.0)

    # not every video gets the same structure (taste: no 1:1 copies) → dip to black is a coin flip
    dip_at = 2 if style.get("dip_to_black", True) and rng.random() < style.get("dip_chance", 1.0) else None
    if music and music.beats and style.get("music_driven", True):
        # the song drives the edit (2nd reference): first cut on the first big hit, shot length follows the
        # music's energy (quiet → hold, loud → cut faster), always on a beat; final shot starts on the last hit
        beats = music.beats
        snap = lambda x: min(beats, key=lambda b: abs(b - x))
        end = min(music.duration, length + 3.0)
        late_hits = [h for h in (music.hits or []) if end * 0.6 <= h <= end - 1.0]
        final_start = snap(max(late_hits)) if late_hits else snap(end - hold)
        hold = max(1.2, end - final_start)
        first_hits = [h for h in (music.hits or []) if 0.8 <= h <= 2.6]
        first = snap(first_hits[0]) if first_hits else snap(sum(quick) + step)
        # intro: quick cuts, the last intro shot runs until the first hit
        durs = [d for d in quick if sum(quick) < first - 0.4] or []
        durs.append(round(first - sum(durs), 3))
        intro_n = len(durs)
        t = first
        while t < final_start - 0.3:
            e = music.energy_at(t)
            # quiet → hold, loud → cut faster, very loud → quick bursts (ref A: ~0.27 s per shot)
            want = step * (3.0 if e < 0.12 else 2.0 if e < 0.3 else 1.0 if e < 0.7 else 0.6 if e < 0.9 else 0.5)
            nxt = snap(t + want)
            if nxt <= t + 0.2:
                nxt = t + want
            nxt = min(nxt, final_start)
            if final_start - nxt < 0.35:                    # no sliver before the final shot
                nxt = final_start
            durs.append(round(nxt - t, 3))
            t = nxt
        if dip_at is not None and dip_at < len(durs):
            dip = style.get("dip_s", 0.33)
            if durs[dip_at] - dip >= 0.3:
                durs[dip_at] = round(durs[dip_at] - dip, 3)   # keep the cuts on the beat: dip eats into the shot
            else:
                dip_at = None
        quick = durs[:intro_n]                              # the intro shots (role "hook", title over them)
    else:
        # durations: quick intro cuts, steady body, long final hold; one dip to black after the 3rd shot
        durs = list(quick)
        while sum(durs) + step + hold <= length:
            durs.append(step)

    used: dict[str, list[tuple[float, float]]] = {c.path: [] for c in usable}

    def pick(role: str | None, dur: float, prev: str | None):
        def candidates(strict: bool):
            for c in usable:
                if strict and role and role_of.get(c.path) != role:
                    continue
                if c.path == prev and len(usable) > 1 and not (strict and role == "detail"):
                    continue
                tagged = (tags.get(c.name) or {}).get("best") or []
                # tagged moments first, then every half second through the clip as backup
                best = list(tagged) + [x * 0.5 for x in range(1, int(c.duration * 2))]
                for k, b in enumerate(best):
                    a = max(0.1, min(c.duration - dur - 0.1, b - dur / 2))
                    if a < 0 or a + dur > c.duration:
                        continue
                    if all(a + dur <= x or a >= y for x, y in used[c.path]):
                        q = max((s.score for s in c.segments if s.start <= a + dur / 2 <= s.end), default=0.3)
                        bonus = 0.25 if k < len(tagged) else 0.0
                        yield q + bonus - 0.2 * len(used[c.path]) + rng.uniform(0, 0.05), c, a
        best = max(candidates(True), key=lambda x: x[0], default=None) or \
            max(candidates(False), key=lambda x: x[0], default=None)
        if best is None:
            c = max(usable, key=lambda c: c.segments[0].score)
            return c, c.segments[0].start
        return best[1], best[2]

    shots, t, prev = [], 0.0, None
    roles = ARC[:]
    for i, d in enumerate(durs):
        role = roles[i % len(roles)]
        c, a = pick(role, d, prev)
        used[c.path].append((a, a + d))
        shots.append(Shot(c.path, round(a, 3), round(a + d, 3), round(t, 3),
                          role="hook" if i < len(quick) else "body", stabilize=stabilize(c)))
        t += d
        prev = c.path
        if dip_at is not None and i == dip_at:
            dip = style.get("dip_s", 0.33)
            shots.append(Shot("", 0.0, dip, round(t, 3), role="black"))
            t += dip
    # final hold on the widest, calmest shot (tag hero_wide, else lowest motion + high quality)
    heroes = [c for c in usable if role_of.get(c.path) == "hero_wide"] or \
        sorted(usable, key=lambda c: c.motion - np.mean(c.per_second or [0]))[:1]
    hero = heroes[0]
    hb = ((tags.get(hero.name) or {}).get("best") or [hero.segments[0].start])[-1]
    ha = max(0.1, min(hero.duration - hold - 0.1, hb - hold / 2))
    shots.append(Shot(hero.path, round(ha, 3), round(ha + hold, 3), round(t, 3),
                      effects=["light_leak"] if style.get("light_leak", True) else [], role="outro",
                      stabilize=stabilize(hero)))
    t += hold

    # whip only where it's motivated: the first body shot after the intro, if it moves
    if style.get("whip_first_body", True):
        for s in shots[len(quick):]:
            if s.clip and s.role == "body":
                c = next(c for c in usable if c.path == s.clip)
                if c.motion > 0.35:
                    s.effects.append("whip")
                break

    # accents from refs A/B: a couple of shots as 'photo' frame-in-frame, a couple in black & white
    body = [s for s in shots if s.clip and s.role == "body" and not s.effects and s.dur >= 0.5]
    rng.shuffle(body)
    for s in body[:style.get("frame_in_frame", 0)]:
        s.effects.append("frame_in_frame")
    for s in [b for b in body if not b.effects][:style.get("bw_accents", 0)]:
        s.effects.append("bw")

    sfx = []
    sfx_map = style.get("sfx", {})
    for s in shots:
        if "whip" in s.effects and sfx_map.get("cut"):
            sfx.append({"t": s.rec_in, "cat": sfx_map["cut"], "gain_db": -10})
        if "light_leak" in s.effects and sfx_map.get("leak"):
            sfx.append({"t": s.rec_in, "cat": sfx_map["leak"], "gain_db": -12})

    texts = []
    title = title or style.get("title")
    if title:
        texts.append({"t0": 0.0, "t1": round(sum(quick) + step * 1.2, 3), "text": title, "kind": "minimal"})
    if style.get("corner_label"):
        texts.append({"t0": 0.0, "t1": round(min(t, sum(quick) + step * 3), 3),
                      "text": f"{style['corner_label']}|{(title or '').upper()}", "kind": "corner"})
    markers = [{"t": s.rec_in, "name": s.role if not s.clip else (s.effects[0] if s.effects else "cut"),
                "note": f"{Path(s.clip).name if s.clip else 'BLACK'} {s.src_in:.2f}-{s.src_out:.2f}"} for s in shots]
    music_d = {"path": music.path, "offset": 0.0, "tempo": music.tempo} if music else None
    return Plan(style["name"], fps, round(t, 3), shots, None, sfx, texts, markers, music_d,
                style.get("overlay") if (style.get("overlay") or {}).get("enabled") else None, variant, "cinematic")
