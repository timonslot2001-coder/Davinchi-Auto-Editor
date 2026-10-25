---
name: cine-montage
description: Edit raw footage into a cinematic montage in Timon's approved P_CINE_MONTAGE style (cold-open burst, one poster title, hard cuts with 1-frame white flashes and whips, white card series, decelerating pacing). Use when Timon asks for a cine montage / "in de montage-stijl" / to apply the Editing DNA to a new project. Plans first and waits for approval before any final render.
---

# cine-montage

Applies `EDITING_DNA_PACKAGE/` (approved profile `P_CINE_MONTAGE`) with the engine in `VIDEO_EDITING_SYSTEM/engine`.
Load details from disk only when needed: `EDITING_DNA_PACKAGE/STYLE_DNA.md` (rules), `EDITING_PSYCHOLOGY.md` (why/when not),
`ACCURACY_AND_GAPS.md` (what is approximate). Never re-analyse the references.

Python: `C:\Users\Timon\.aev\Scripts\python.exe` (run from `VIDEO_EDITING_SYSTEM/`, prefix `PYTHONIOENCODING=utf-8`).

## Inputs
- Required: an AutoEdit project folder (`C:\Users\Timon\Videos\AutoEdit Projects\<name>`) with video in `clips/`.
- Optional: song in `music/` (the style is music-only — ask if missing), title text (place/topic), accent colour
  (default #E70002), length (default 18 s), title variant (poster_condensed | heavy_grotesque).
- Footage may be S-Log3 (Timon's A6700) or Rec.709; `--grade auto` detects it; say which grade was used.

## Steps and approval gates
1. `python -m engine validate` — DNA approved + Edge + FFmpeg present.
2. `python -m engine plan "<project>" --title "<TEXT>" [--length 18] [--accent #HEX] [--seed N]`
   → `<project>/cine_montage/edl.json`, `storyboard/storyboard.html`, `storyboard/storyboard_sheet.jpg`.
3. Look at the storyboard sheet yourself first (does each shot make sense, title readable, no ugly frames?). Re-plan with
   another `--seed`/length if needed. Then send Timon the sheet + a short summary (length, song, title, accents, open
   questions). **STOP — gate B. Wait for an explicit yes in chat.** Style approval is not approval of this video.
4. Optional review clip before approval: `python -m engine preview "<project>"` (half size).
5. New fonts/colours/effects outside the DNA → show a test and ask first (gate C).
6. Only after Timon's yes: `python -m engine approve "<project>" --by Timon --note "<his words>"`, then
   `python -m engine render "<project>"` (refuses if the EDL changed after approval) → `<project>/exports/cine_montage_*.mp4` + QA.
7. Watch the QA (size, duration, black/frozen, LUFS ≈ −14, true peak ≤ −1) and look at frames around the title, flashes,
   card series and the last shot. Fix and re-render if needed, then send the MP4 (or a <30 MB preview for the phone).

## Rules of thumb (from the DNA)
No captions · one accent colour · one title only · no flash/whip on the title · card series 3-6 shots cut hard ·
≤ ~0.5 accents/s · end on the longest scenic shot · do not copy any reference creator's handles or end cards.

## Known limits
Depth titles and cut-out flashes need a subject matte (not built). Fonts are verified OFL approximations. Cuts are
paced, not beat-locked (snapped to a strong onset only within 2 frames).
