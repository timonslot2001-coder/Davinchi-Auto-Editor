"""Turn footage + the approved DNA into an EDL. Every decision cites a DNA rule id; heuristics are named as such."""
from __future__ import annotations

import random
from pathlib import Path

import numpy as np

from .dna import Profile
from .edl import EDL, Event, Overlay


def _slot_lengths(p: Profile, L: float, title_in: float, title_hold: float, rng: random.Random) -> list[tuple[float, str]]:
    """Shot lengths following the measured pacing curve. Returns [(length, role)]."""
    fifths = p.pacing_by_fifth
    lo, hi = p.data["pacing"]["shot_len_s_p10_p50_p90"][0], p.data["pacing"]["shot_len_s_p10_p50_p90"][2]
    final = min(max(0.9, L * 0.08), 2.2)                      # measured final holds 0.5-2.3 s
    slots, t = [], 0.0
    # cold open burst up to the title (RULE_COLD_OPEN)
    while t < title_in - 0.05:
        s = min(rng.uniform(0.12, 0.32), title_in - t)
        if s < 0.08:
            break
        slots.append((s, "cold_open"))
        t += s
    if slots and t < title_in:                                 # land exactly on title_in
        s, r = slots[-1]
        slots[-1] = (s + title_in - t, r)
        t = title_in
    slots.append((title_hold, "title"))                       # RULE_TITLE
    t += title_hold
    while t < L - final - 0.15:
        x = t / L
        base = float(np.interp(x, [0.1, 0.3, 0.5, 0.7, 0.9], fifths))   # RULE_DECELERATE
        s = float(np.clip(base * np.exp(rng.gauss(0, 0.38)), lo, hi))
        s = min(s, L - final - t)
        if s < 0.12:
            break
        slots.append((s, "body"))
        t += s
    slots.append((L - t, "final"))
    return slots


def _snap(times: list[float], onsets: list[float], fps: float) -> list[float]:
    """Optional: move a cut onto a strong onset only if it is within 2 frames (DNA: sync allowed, not required)."""
    out, keep = [], []
    on = np.array(onsets) if onsets else np.array([])
    for i, t0 in enumerate(times):
        t = t0
        if len(on):
            k = np.argmin(np.abs(on - t))
            if abs(on[k] - t) <= 2 / fps:
                t = float(on[k])
        t = round(round(t * fps) / fps, 4)                    # frame-accurate
        if out and t < out[-1] + 3 / fps:                     # a snap must never collapse a shot below 3 frames
            t = round(round(t0 * fps) / fps, 4)
            if t < out[-1] + 3 / fps:
                continue                                      # merge this tiny shot into the previous one
        out.append(t)
        keep.append(i)
    return out, keep


def plan(p: Profile, inv: dict, music: dict | None, title: str | None, length: float | None = None,
         accent: str | None = None, fps: float = 25.0, size=(1920, 1080), seed: int = 1, card: str = "auto",
         bw: str = "auto", title_variant: str | None = None, grid_flow: str = "auto") -> EDL:
    rng = random.Random(seed)
    segs = [s for c in inv["clips"] if c["kind"] == "video" for s in c["segments"] if "soft" not in s["tags"]]
    notes, questions = [], []
    if not segs:
        raise ValueError("no usable video segments in the project")
    L = length or 18.0
    if music:
        L = min(L, music["duration"] - 0.5)
    L = float(np.clip(L, 8.0, 30.0))
    tt = p.title_timing
    title_in = float(np.clip(tt["in_s_median"], 0.3, 1.2)) if len(segs) >= 8 else 0.0
    if title_in == 0.0:
        notes.append("fewer than 8 usable segments: calm opener without cold-open burst (RULE_COLD_OPEN exception)")
    title_hold = float(tt["hold_s_median"])
    slots = _slot_lengths(p, L, title_in, title_hold, rng)

    # cut times on the frame grid, optionally snapped to strong onsets
    cuts = list(np.cumsum([s for s, _ in slots])[:-1])
    cuts, keep = _snap(cuts, music["strong_onsets"] if music else [], fps)
    # cut i starts slot i+1; a dropped cut merges slot i+1 into slot i (keep the earlier slot's role)
    merged, rank = [slots[0]], {"title": 3, "final": 2, "cold_open": 1, "body": 0}
    kept = set(keep)
    for i, sl in enumerate(slots[1:]):
        if i in kept:
            merged.append(sl)
        elif rank[sl[1]] > rank[merged[-1][1]]:              # a merged slot keeps the more important role
            merged[-1] = (merged[-1][0], sl[1])
    slots = merged
    bounds = [0.0] + cuts + [round(round(L * fps) / fps, 4)]
    if bounds[-1] - bounds[-2] < 3 / fps:                     # never end on a sliver
        bounds.pop(-2); slots.pop(-2)
    L = bounds[-1]

    # ---------------------------------------------------------------- assign footage to slots
    pool = sorted(segs, key=lambda s: -s["score"])
    used: dict[tuple, int] = {}
    clip_uses: dict[str, int] = {}
    n_clips = len({s["clip"] for s in segs})
    cap = {c: (2 if Path(c).name.startswith("AI_") else 99) for c in {s["clip"] for s in segs}}   # own footage leads; AI shots are support

    def capped(s):
        return clip_uses.get(s["clip"], 0) < cap[s["clip"]]

    def pick(role: str, need: float, last_clip: str | None):
        def ok(s):
            return s["end"] - s["start"] >= need and s["clip"] != last_clip and capped(s)

        real = lambda s: not Path(s["clip"]).name.startswith("AI_")             # title/final: real footage first
        prefs = {"cold_open": lambda s: ("detail" in s["tags"] or "motion" in s["tags"]),
                 "title": lambda s: "establishing" in s["tags"] and real(s),
                 "final": lambda s: ("establishing" in s["tags"] or "static" in s["tags"]) and real(s),
                 "body": lambda s: True}[role]
        for stage in (lambda s: ok(s) and prefs(s) and used.get((s["clip"], s["start"]), 0) == 0,
                      lambda s: ok(s) and used.get((s["clip"], s["start"]), 0) == 0,
                      lambda s: ok(s),
                      lambda s: s["end"] - s["start"] >= need):
            cand = [s for s in pool if stage(s)]
            if cand:
                cand.sort(key=lambda s: (used.get((s["clip"], s["start"]), 0), -s["score"]))
                return cand[0]
        return max(pool, key=lambda s: s["end"] - s["start"])

    events, last = [], None
    for i, ((dur_nom, role), a, b) in enumerate(zip(slots, bounds, bounds[1:])):
        need = b - a
        s = pick(role, need, last)
        k = used.get((s["clip"], s["start"]), 0)
        used[(s["clip"], s["start"])] = k + 1
        clip_uses[s["clip"]] = clip_uses.get(s["clip"], 0) + 1
        span = s["end"] - s["start"]
        # take a different window each reuse; centre the first use (heuristic: middle of a segment is steadiest)
        free = max(span - need, 0)
        off = free / 2 if k == 0 else (free * ((k * 0.37) % 1))
        src_in = round(s["start"] + off, 3)
        rule = {"cold_open": ["RULE_COLD_OPEN"], "title": ["RULE_TITLE"], "final": ["RULE_DECELERATE"],
                "body": ["RULE_DECELERATE"]}[role]
        why = {"cold_open": "hook burst: detail/motion shot, 0.1-0.4 s",
               "title": "strongest establishing shot carries the title",
               "final": "scenic resolving shot, longest hold",
               "body": f"pacing curve at {a / L:.0%} of the edit"}[role]
        events.append(Event(f"E{i:02d}", round(a, 4), round(b, 4), s["clip"], src_in, round(src_in + max(need, 0.04), 3),
                            rule=rule, why=why, params={"role": role, "tags": s["tags"], "pan_dx": s["pan_dx"]}))
        last = s["clip"]

    # ---------------------------------------------------------------- transitions (RULE_FLASH / RULE_WHIP), attention budget
    title_ev = next((e for e in events if e.params["role"] == "title"), None)
    t_lo, t_hi = (title_ev.out_in, title_ev.out_out) if title_ev else (-1, -1)
    budget = int(round(p.accents_per_second * L))
    share = p.transition_share
    n_flash = int(round(budget * share["flash_white"] / (share["flash_white"] + share["whip_blur"])))
    n_whip = budget - n_flash
    last_acc = -9.0
    cand = []
    for e_prev, e in zip(events, events[1:]):
        t = e.out_in
        if t_lo - 0.01 <= t <= t_hi + 0.01 or t > L * 0.85:          # never on/inside the title; calm wind-down
            continue
        moving = "motion" in e_prev.params["tags"] and abs(e_prev.params["pan_dx"]) > 0.8
        scene_change = e_prev.source != e.source
        w_cold = 1.6 if t < t_lo else 1.0
        cand.append((t, e, moving, scene_change, w_cold))
    rng.shuffle(cand)
    cand.sort(key=lambda c: -(c[4] + (0.5 if c[3] else 0) + (0.8 if c[2] else 0)))
    placed = []
    for t, e, moving, scene_change, _ in cand:
        if all(abs(t - x) >= 1.0 for x in placed):                 # never two accents within ~1 s
            if moving and n_whip > 0:
                e.transition_in = "T_WHIP"; e.rule.append("RULE_WHIP"); n_whip -= 1
                e.params["whip_dir"] = 1 if events[events.index(e) - 1].params["pan_dx"] >= 0 else -1
            elif scene_change and n_flash > 0:
                e.transition_in = "T_FLASH"; e.rule.append("RULE_FLASH"); n_flash -= 1
            else:
                continue
            placed.append(t)
    if n_whip > 0:
        notes.append(f"{n_whip} whip(s) not placed: not enough moving shots (RULE_WHIP restraint)")

    # ---------------------------------------------------------------- white card series (RULE_CARD_SERIES)
    body = [e for e in events if e.params["role"] == "body" and 0.35 * L < e.out_in < 0.75 * L]
    if card != "off" and len(body) >= 4 and (card == "on" or L >= 12):
        k0 = len(body) // 2 - 2
        run = body[max(k0, 0): max(k0, 0) + 4]
        nxt = events[events.index(run[-1]) + 1] if events.index(run[-1]) + 1 < len(events) else None
        for e in run + ([nxt] if nxt else []):                  # the card cuts in/out hard, no accents inside
            if e in run:
                e.treatment.append("D_CARD_WHITE"); e.rule.append("RULE_CARD_SERIES")
            if e.transition_in != "T_HARD":
                e.rule = [r for r in e.rule if r not in ("RULE_WHIP", "RULE_FLASH")]
                e.transition_in = "T_HARD"
        notes.append(f"white card series on {', '.join(e.id for e in run)}")

    # ---------------------------------------------------------------- one B&W contrast shot (RULE_BW)
    if bw != "off" and L >= 14:
        late = [e for e in events if e.params["role"] == "body" and 0.55 * L < e.out_in < 0.85 * L and not e.treatment]
        if late:
            e = max(late, key=lambda e: e.out_out - e.out_in)
            e.treatment.append("D_BW"); e.rule.append("RULE_BW")
            if e.transition_in == "T_HARD":
                e.transition_in = "T_FLASH"; e.rule.append("RULE_FLASH")

    # ---------------------------------------------------------------- Grid Flow, Timon's own transition (RULE_GRID_FLOW)
    if grid_flow != "off" and "RULE_GRID_FLOW" in p.rules and L >= 8:
        n_gf = 2 if L >= 16 else 1
        frames = 12
        accents = [e.out_in for e in events if e.transition_in != "T_HARD"]
        gcand = []
        for e_prev, e in zip(events, events[1:]):
            t = e.out_in
            if (t <= t_hi + 0.01 or t > L * 0.85 or e.params["role"] == "final" or e.treatment or e_prev.treatment
                    or e_prev.source == e.source or e.out_out - e.out_in < (frames + 2) / fps):
                continue
            calm = 2 - min(abs(e_prev.params["pan_dx"]), 2) - min(abs(e.params["pan_dx"]), 2) / 2
            gcand.append((calm + (e.out_out - e.out_in), e))
        gcand.sort(key=lambda c: -c[0])
        placed = []
        for _, e in gcand:
            if len(placed) == n_gf:
                break
            others = [a for a in accents if abs(a - e.out_in) > 1e-3]
            if all(abs(e.out_in - a) >= 1.0 for a in others + placed):
                if e.transition_in != "T_HARD":                       # replaces the accent that was on this cut
                    accents.remove(e.out_in)
                    e.rule = [r for r in e.rule if r not in ("RULE_WHIP", "RULE_FLASH")]
                e.transition_in = "T_GRID_FLOW"; e.rule.append("RULE_GRID_FLOW")
                e.params.update({"grid_flow_frames": frames, "grid_flow": {}})   # {} = 4x4 wipe left, exposure flash
                placed.append(e.out_in)
        if placed:
            notes.append(f"Grid Flow at {', '.join(f'{t:.2f}s' for t in placed)}")
        else:
            notes.append("Grid Flow not placed: no clean scene change >= 1 s from other accents")

    overlays = []
    if title and title_ev:
        overlays.append(Overlay("O_TITLE", "title_slam", title_ev.out_in, title_ev.out_out,
                                {"text": title.upper(), "variant": title_variant or p.defaults.get("title_variant", "poster_condensed"),
                                 "color": accent or p.defaults.get("accent", "#E70002")},
                                ["RULE_TITLE", "RULE_ONE_ACCENT"], "names the place/topic once, hard cut in/out"))
    elif not title:
        questions.append("No title text given: which place/topic name should the title show (or no title)?")
    if not music:
        questions.append("No song in <project>/music: the profile is music-only. Which song?")
    edl = EDL(str(inv["project"]), p.id, size[0], size[1], fps, L, accent or p.defaults.get("accent", "#E70002"),
              music["path"] if music else None, 0.0, events, overlays, notes, questions)
    return edl
