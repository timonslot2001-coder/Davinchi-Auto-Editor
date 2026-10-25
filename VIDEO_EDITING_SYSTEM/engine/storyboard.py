"""Local HTML storyboard for edit-plan approval: one real frame per event (graded, with devices + title applied),
the EDL table with rule ids, and open questions. Frames come from the same renderer code as the final export."""
from __future__ import annotations

import html
from pathlib import Path

import cv2
import numpy as np

from .edl import EDL
from . import graphics
from .render import bw, card, lut_for, over, read_event


def build(edl: EDL, outdir: Path, grade_mode: str = "auto") -> Path:
    outdir.mkdir(parents=True, exist_ok=True)
    fr_dir = outdir / "frames"
    fr_dir.mkdir(exist_ok=True)
    W, H = edl.width // 2, edl.height // 2
    small = type(edl)(**{**edl.__dict__, "width": W, "height": H})
    notes, luts, gfx = [], {}, {}
    for o in edl.overlays:
        if o.component == "title_slam":
            gfx[o.id] = graphics.title_png(o.params["text"], o.params["color"], o.params["variant"], (W, H), outdir / "gfx")
    cards = []
    for ev in edl.events:
        if ev.source not in luts:
            luts[ev.source] = lut_for(grade_mode, ev.source, notes)
        frames = read_event(ev, small, luts[ev.source])
        f = frames[len(frames) // 2]
        if "D_BW" in ev.treatment:
            f = bw(f)
        if "D_CARD_WHITE" in ev.treatment:
            f = card(f)
        mid = (ev.out_in + ev.out_out) / 2
        for o in edl.overlays:
            if o.id in gfx and o.out_in <= mid < o.out_out:
                f = over(f, gfx[o.id])
        p = fr_dir / f"{ev.id}.jpg"
        cv2.imwrite(str(p), f, [cv2.IMWRITE_JPEG_QUALITY, 85])
        cards.append((ev, p.relative_to(outdir).as_posix()))
    e = html.escape
    tiles = "".join(
        f'<div class="t"><img src="{src}"><div class="cap"><b>{ev.id}</b> {ev.out_in:.2f}-{ev.out_out:.2f}s '
        f'<span class="tr {ev.transition_in}">{ev.transition_in}</span> {" ".join(ev.treatment)}<br>'
        f'<small>{e(Path(ev.source).name)} @ {ev.src_in:.2f}s · {e(", ".join(ev.rule))}</small></div></div>'
        for ev, src in cards)
    rows = "".join(f"<tr><td>{ev.id}</td><td>{ev.out_in:.2f}</td><td>{ev.out_out:.2f}</td><td>{ev.out_out - ev.out_in:.2f}</td>"
                   f"<td>{e(Path(ev.source).name)}</td><td>{ev.src_in:.2f}</td><td>{ev.transition_in}</td><td>{' '.join(ev.treatment)}</td>"
                   f"<td>{e(', '.join(ev.rule))}</td><td>{e(ev.why)}</td></tr>" for ev in edl.events)
    ovs = "".join(f"<li>{o.id} {o.component} {o.out_in:.2f}-{o.out_out:.2f}s · {e(str(o.params))} · {e(', '.join(o.rule))}</li>" for o in edl.overlays)
    qs = "".join(f"<li>{e(q)}</li>" for q in edl.open_questions) or "<li>none</li>"
    ns = "".join(f"<li>{e(n)}</li>" for n in edl.notes + notes)
    doc = f"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Storyboard</title><style>
body{{margin:0;background:#111;color:#eee;font:14px/1.45 system-ui,Segoe UI,sans-serif}} main{{max-width:1300px;margin:auto;padding:16px}}
.g{{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:10px}} .t img{{width:100%;display:block;border-radius:4px}}
.cap{{padding:4px 2px;font-size:12px}} .tr{{padding:0 5px;border-radius:6px;background:#333}} .T_FLASH{{background:#eee;color:#111}} .T_WHIP{{background:#2a5ba8}}
table{{border-collapse:collapse;width:100%;font-size:12px}} td,th{{border:1px solid #333;padding:3px 5px}} h2{{margin-top:28px}}
</style></head><body><main>
<h1>Storyboard — {e(Path(edl.project).name)}</h1>
<p>Profile {edl.profile} · {edl.width}x{edl.height} @ {edl.fps} fps · {edl.duration:.2f} s · accent {edl.accent} ·
music: {e(Path(edl.music).name) if edl.music else 'NONE'}</p>
<p><b>Status: waiting for approval.</b> Frames are real source frames with the planned grade, card/B&W and title applied
(half resolution). Flash = 1 white frame at the start of the event; whip = blur over the cut.</p>
<h2>Open questions</h2><ul>{qs}</ul>
<h2>Frames</h2><div class="g">{tiles}</div>
<h2>Overlays</h2><ul>{ovs or '<li>none</li>'}</ul>
<h2>Edit decision list</h2><table><tr><th>id</th><th>in</th><th>out</th><th>len</th><th>source</th><th>src in</th><th>trans</th><th>device</th><th>rules</th><th>why</th></tr>{rows}</table>
<h2>Notes</h2><ul>{ns}</ul></main></body></html>"""
    out = outdir / "storyboard.html"
    out.write_text(doc, encoding="utf-8")
    # contact sheet for chat/phone review
    imgs = [cv2.imread(str(outdir / src)) for _, src in cards]
    tw = 320
    th = int(tw * H / W)
    tl = []
    for (ev, _), im in zip(cards, imgs):
        im = cv2.resize(im, (tw, th))
        cv2.rectangle(im, (0, 0), (tw, 18), (0, 0, 0), -1)
        cv2.putText(im, f"{ev.id} {ev.out_in:.2f}s {ev.transition_in[2:]} {' '.join(x[2:] for x in ev.treatment)}", (3, 13), 0, 0.4, (255, 255, 255), 1)
        tl.append(im)
    per = 5
    while len(tl) % per:
        tl.append(np.zeros_like(tl[0]))
    cv2.imwrite(str(outdir / "storyboard_sheet.jpg"), np.vstack([np.hstack(tl[i:i + per]) for i in range(0, len(tl), per)]))
    return out
