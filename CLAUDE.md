# AutoEdit — how Claude works in this repo

Timon's DaVinci Resolve auto editor (TikTok + Instagram). One **house style** (cinematic) for every
video; the category only changes captions/hashtags. Work only in this repo; commit everything to
`main` and push (Timon wants everything pushed and merged).

## The learning loop (this is the point of the project)

The editor must get better every time, without copying references 1:1.

1. **Timon sends a reference video** → analyse it (cuts/rhythm, grade, text, transitions, sound design)
   and add every *new* technique to `inventory.yaml` as eye candy (VFX) or ear candy (SFX): what it
   is, `trigger` (when it is motivated), `max`, `cooldown_s`, the matching `sfx`, `priority`.
   If the technique needs code, add it to `autoedit/fx.py` (Fusion) and test it with a render.
   **Never rebuild the reference's structure** — references feed the inventory, not the timeline.
   Music from a reference: extract only clean music (no speech, no end-card sound) into the music folder.
2. **Timon gives feedback** ("too much", "bigger title", "that pop looks weird"…) → add a rule to
   `taste.yaml` (quote what he said + the rule) and adjust the knobs/settings so it sticks.
3. **Timon sends clips (+ a song)** → `autoedit run <folder> --music <name> [--title ...] [--label ...]`.
   The director picks techniques only where motivated (music hit, motion, scene change, quiet part),
   within budget; every VFX gets its SFX.
4. **Always rewatch before showing it**: the pipeline writes `<base>_review.json` and
   `<base>_review.png` (a frame of every accent). Read both, look at the frames, and check:
   does each accent have a reason? Is anything distracting, repetitive, too loud, or unmotivated?
   Less is more — remove before adding. Fix and re-render if needed, then send the video.

## Practical notes
- Python: run with the venv that works on this PC (Windows Smart App Control blocks a venv
  created by Claude inside Documents; see README).
- Resolve must be open; never call `comp.Render()` (modal dialog). Fusion comps only render if
  imported from a file (`fx.commit`).
- Grade = one baked LUT (`autoedit/grade.py`): Sony S-Log3 → Rec.709 + `reference_film` look,
  exposure −1.75 stops (Timon's A6700 shoots bright). The Odyssey PowerGrade does nothing by script.
- New footage: A6700 XAVC HS 4K 50p 75M 4:2:0 10-bit S-Log3 (smooth on his AMD GPU).
- Shot tags for story order: `data/tags.json` (look at the clips and tag detail/subject/close/…).
