"""Unit test for engine/style_checks.py on a hand-made plan that breaks the rules on purpose (no footage needed).
usage: python tests/style_checks_test.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from engine.edl import EDL, Event, Overlay      # noqa: E402
from engine import style_checks                 # noqa: E402


def plan():
    lens = [0.2, 0.2, 0.25, 1.3] + [0.45] * 20 + [0.6, 0.6, 0.7, 0.7, 1.6]
    roles = ["cold_open"] * 3 + ["title"] + ["body"] * 24 + ["final"]
    ev, t = [], 0.0
    for i, (d, r) in enumerate(zip(lens, roles)):
        src = f"C:/x/{'AI_drone' if r == 'final' else f'clip{i % 6}'}.mp4"
        ev.append(Event(f"E{i:02d}", round(t, 3), round(t + d, 3), src, 10.0 * i, 10.0 * i + d,
                        params={"role": r, "tags": [], "pan_dx": 1.0}))
        t += d
    L = round(t, 3)
    title = Overlay("O_TITLE", "title_slam", ev[3].out_in, ev[3].out_out, {"text": "X", "color": "#E70002", "variant": "p"})
    e = EDL("test", "P_CINE_MONTAGE", 1920, 1080, 25, L, "#E70002", None, 0.0, ev, [title])
    # break the rules
    ev[6].transition_in = "T_FLASH"; ev[7].transition_in = "T_FLASH"            # 0.45 s apart
    for k in (10, 11, 12):                                                       # card series ...
        ev[k].treatment.append("D_CARD_WHITE")
    ev[10].transition_in = "T_WHIP"; ev[10].params["whip_dir"] = 1               # ... with an accent on its edge
    ev[15].treatment.append("D_BW"); ev[17].treatment.append("D_BW")             # two B&W shots
    for k in (19, 22, 25):                                                       # three Grid Flows on a ~15 s edit
        ev[k].transition_in = "T_GRID_FLOW"
    return e


def status(res, rule):
    return {r["status"] for r in res if r["rule"] == rule}


e = plan()
before = style_checks.check(e)
assert "fail" in status(before, "RULE_FLASH"), before
assert "fail" in status(before, "RULE_CARD_SERIES")
assert "fail" in status(before, "RULE_BW")
assert "fail" in status(before, "RULE_GRID_FLOW")
assert "warn" in status(before, "AI_SUPPORT")
log = style_checks.fix(e)
after = style_checks.check(e)
for rule in ("RULE_FLASH", "RULE_CARD_SERIES", "RULE_BW", "RULE_GRID_FLOW"):
    assert status(after, rule) == {"ok"}, (rule, [r for r in after if r["rule"] == rule])
assert sum(x.transition_in == "T_GRID_FLOW" for x in e.events) == 1     # Grid Flow beats a flash, max 1 under 16 s
print("fixed:", *log, sep="\n  ")
print("before:", style_checks.summary(before), "| after:", style_checks.summary(after))
print("style_checks_test OK")
