"""Style checks on a plan (EDL), from the checks in EDITING_PSYCHOLOGY.md §1/§2/§9. `fix` repairs what can be repaired
without re-planning (it only removes accents, never adds or moves shots); `check` reports ok / warn / fail per rule.
Shown at the top of the storyboard and printed by `engine plan` / `engine check`."""
from __future__ import annotations

from pathlib import Path

import numpy as np

from .edl import EDL

ACCENT_GAP = 1.0                    # RULE_FLASH: never two accents within ~1 s
TEXT_COMPONENTS = {"title_slam", "side_labels"}


def _accents(edl: EDL) -> list:
    return [e for e in edl.events if e.transition_in != "T_HARD"]


def _is_ai(e) -> bool:
    return Path(e.source).name.startswith("AI_")


def _card_runs(edl: EDL) -> list[list]:
    runs, cur = [], []
    for e in edl.events:
        if "D_CARD_WHITE" in e.treatment:
            cur.append(e)
        elif cur:
            runs.append(cur); cur = []
    if cur:
        runs.append(cur)
    return runs


def _demote(e, why: str, log: list) -> None:
    log.append(f"{e.id} {e.transition_in} at {e.out_in:.2f}s removed: {why}")
    e.transition_in = "T_HARD"
    e.rule = [r for r in e.rule if r not in ("RULE_FLASH", "RULE_WHIP", "RULE_GRID_FLOW")]
    e.params.pop("grid_flow_frames", None)
    e.params.pop("grid_flow", None)


def fix(edl: EDL) -> list[str]:
    """Remove accents that break a rule. Keeps the more valuable accent of a pair: Grid Flow > the flash into a B&W
    shot > other flash > whip. Returns what was changed."""
    log = []
    keep = {"T_GRID_FLOW": 3, "T_FLASH": 1, "T_WHIP": 0}

    def value(e):
        return keep.get(e.transition_in, 0) + (1.5 if "D_BW" in e.treatment else 0)

    # accents inside or at the edges of a white card series (hard in/out)
    for run in _card_runs(edl):
        i = edl.events.index(run[-1]) + 1
        for e in run + edl.events[i:i + 1]:
            if e.transition_in != "T_HARD":
                _demote(e, "card series cuts hard in/out", log)
    # two accents closer than ACCENT_GAP: drop the less valuable one, repeat until clean
    while True:
        acc = _accents(edl)
        pair = next(((a, b) for a, b in zip(acc, acc[1:]) if b.out_in - a.out_in < ACCENT_GAP - 1e-3), None)
        if not pair:
            break
        a, b = pair
        loser, winner = (b, a) if value(b) <= value(a) else (a, b)
        _demote(loser, f"within {ACCENT_GAP:.0f} s of {winner.id}", log)
    # more than one B&W shot: keep the longest
    bws = [e for e in edl.events if "D_BW" in e.treatment]
    for e in sorted(bws, key=lambda e: e.out_out - e.out_in)[:-1]:
        e.treatment.remove("D_BW"); e.rule = [r for r in e.rule if r != "RULE_BW"]
        log.append(f"{e.id} B&W removed: max one per video")
    # too many Grid Flows: keep the earliest ones
    gfs = [e for e in edl.events if e.transition_in == "T_GRID_FLOW"]
    for e in gfs[_grid_flow_max(edl):]:
        _demote(e, "Grid Flow max 1 per video", log)
    if log:
        edl.notes.extend(f"style fix: {x}" for x in log)
    return log


def _grid_flow_max(edl: EDL) -> int:
    return 0 if edl.duration < 8 else 1                             # once per video (decision 0012)


def check(edl: EDL) -> list[dict]:
    res = []

    def add(rule, ok, msg, warn_only=False):
        res.append({"rule": rule, "status": "ok" if ok else ("warn" if warn_only else "fail"), "msg": msg})

    L, ev = edl.duration, edl.events
    lens = np.array([e.out_out - e.out_in for e in ev])
    roles = [e.params.get("role", "") for e in ev]
    acc = _accents(edl)

    # RULE_TITLE
    titles = [o for o in edl.overlays if o.component == "title_slam"]
    if titles:
        t = titles[0]
        hold = t.out_out - t.out_in
        add("RULE_TITLE", len(titles) == 1 and hold >= 1.0 - 1e-3,
            f"{len(titles)} title, {hold:.2f} s in view" + ("" if hold >= 1.0 - 1e-3 else " (< 1 s: hard to read on a phone)"))
        on_title = [e for e in acc if t.out_in - 1e-3 <= e.out_in <= t.out_out + 1e-3]
        add("RULE_TITLE", not on_title, "no accent on the title frames" if not on_title
            else f"accent on the title: {', '.join(e.id for e in on_title)}")
    else:
        add("RULE_TITLE", False, "no title in the plan", warn_only=True)

    # RULE_COLD_OPEN (skipped for the calm-open exception)
    co = [e for e, r in zip(ev, roles) if r == "cold_open"]
    if co:
        early = lens[[e.out_in < 1.3 for e in ev]]
        cuts = sum(1 for e in ev[1:] if e.out_in < 1.3)
        med = float(np.median(early)) if len(early) else 0
        add("RULE_COLD_OPEN", cuts >= 2 and med <= 0.4 + 1e-3, f"{cuts} cuts in the first 1.3 s, median shot {med:.2f} s")
        wins = [(e.source, round(e.src_in, 1)) for e in co]
        add("RULE_COLD_OPEN", len(set(wins)) == len(wins), "no repeated shot in the hook" if len(set(wins)) == len(wins)
            else "a shot repeats inside the hook (feels like a loop)", warn_only=True)
    else:
        add("RULE_COLD_OPEN", True, "calm open (thin footage exception)")

    # accent spacing + rate (RULE_FLASH, attention budget)
    gaps = [b.out_in - a.out_in for a, b in zip(acc, acc[1:])]
    close = [(a.id, b.id) for a, b, g in zip(acc, acc[1:], gaps) if g < ACCENT_GAP - 1e-3]
    add("RULE_FLASH", not close, f"accents >= {ACCENT_GAP:.0f} s apart" if not close
        else "accents too close: " + ", ".join(f"{a}/{b}" for a, b in close))
    rate = len(acc) / L
    add("budget", 0.25 <= rate <= 0.75, f"{len(acc)} accents = {rate:.2f}/s (target ~0.48)", warn_only=True)
    tail = [e for e in acc if e.out_in >= 0.8 * L]
    tail_rate = len(tail) / (0.2 * L)
    add("budget", tail_rate <= 0.3 + 1e-3, f"wind-down {tail_rate:.2f} accents/s (max 0.3)", warn_only=True)

    # RULE_WHIP: blur follows the outgoing pan
    bad = [e.id for i, e in enumerate(ev) if e.transition_in == "T_WHIP" and i
           and np.sign(ev[i - 1].params.get("pan_dx", 0) or 1) != e.params.get("whip_dir", 1)]
    if any(e.transition_in == "T_WHIP" for e in ev):
        add("RULE_WHIP", not bad, "whips follow the motion" if not bad else f"whip against the motion: {', '.join(bad)}",
            warn_only=True)

    # RULE_DECELERATE
    part = np.array([min(4, int(e.out_in / L * 5)) for e in ev])
    first, last = (float(np.median(lens[part == i])) if (part == i).any() else 0 for i in (0, 4))
    ratio = last / first if first else 0
    add("RULE_DECELERATE", ratio >= 1.3, f"end {ratio:.1f}x slower than the start ({first:.2f} -> {last:.2f} s)",
        warn_only=not co)
    fin = lens[-1]
    add("RULE_DECELERATE", fin >= 0.5 and fin >= max(lens[-5:]) - 1e-3,
        f"final shot {fin:.2f} s" + ("" if fin >= max(lens[-5:]) - 1e-3 else " (not the longest of the last five)"),
        warn_only=True)

    # RULE_CARD_SERIES
    runs = _card_runs(edl)
    if runs:
        sizes = [len(r) for r in runs]
        add("RULE_CARD_SERIES", len(runs) <= 2 and all(3 <= s <= 6 for s in sizes),
            f"{len(runs)} card series ({', '.join(map(str, sizes))} shots; 3-6 each, max 2)")
        edges = []
        for r in runs:
            i = ev.index(r[-1]) + 1
            edges += [e.id for e in r + ev[i:i + 1] if e.transition_in != "T_HARD"]
        add("RULE_CARD_SERIES", not edges, "card cuts hard in/out" if not edges else f"accent at the card: {', '.join(edges)}")

    # RULE_BW
    n_bw = sum("D_BW" in e.treatment for e in ev)
    add("RULE_BW", n_bw <= 1, f"{n_bw} B&W shot(s) (max 1)")

    # RULE_GRID_FLOW
    gfs = [e for e in ev if e.transition_in == "T_GRID_FLOW"]
    gmax = _grid_flow_max(edl)
    wrong = [e.id for e in gfs if e.treatment or ev[ev.index(e) - 1].treatment or e.params.get("role") in ("title", "final")
             or (titles and titles[0].out_in - 1e-3 <= e.out_in <= titles[0].out_out + 1e-3)]
    add("RULE_GRID_FLOW", len(gfs) <= gmax and not wrong,
        f"Grid Flow {len(gfs)}x (max {gmax})" + (f"; wrong place: {', '.join(wrong)}" if wrong else ""))

    # AI shots are support (Smoke Sesh learning)
    uses: dict[str, int] = {}
    for e in ev:
        if _is_ai(e):
            uses[e.source] = uses.get(e.source, 0) + 1
    lead = [e.id for e, r in zip(ev, roles) if _is_ai(e) and r in ("title", "final")]
    if uses or lead:
        over = [Path(s).name for s, n in uses.items() if n > 2]
        add("AI_SUPPORT", not over and not lead, f"AI shots {sum(uses.values())}x, none as title/final" if not over and not lead
            else "; ".join(x for x in (f"used > 2x: {', '.join(over)}" if over else "",
                                       f"AI as title/final: {', '.join(lead)}" if lead else "") if x), warn_only=True)

    # accidental jump cuts: same clip, nearly the same moment, back to back
    jumps = [b.id for a, b in zip(ev, ev[1:]) if a.source == b.source and abs(b.src_in - a.src_out) < 0.5]
    add("cut", not jumps, "no accidental jump cuts" if not jumps else f"same clip back to back: {', '.join(jumps)}",
        warn_only=True)

    # RULE_ONE_ACCENT / RULE_NO_TEXT_OVERLOAD
    cols = {o.params.get("color", "").upper() for o in titles} - {""}
    add("RULE_ONE_ACCENT", cols <= {edl.accent.upper()}, f"accent colour {edl.accent}" if cols <= {edl.accent.upper()}
        else f"title colour {cols} differs from accent {edl.accent}")
    extra = [o.component for o in edl.overlays if o.component not in TEXT_COMPONENTS]
    add("RULE_NO_TEXT_OVERLOAD", not extra, "only title text" if not extra else f"extra text: {extra}")
    return res


def summary(res: list[dict]) -> str:
    n = {s: sum(r["status"] == s for r in res) for s in ("ok", "warn", "fail")}
    return f"{n['ok']} ok, {n['warn']} warning(s), {n['fail']} fail(s)"
