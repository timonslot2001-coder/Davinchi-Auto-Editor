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
- Song (the style is music-only — ask if missing): `--song`, else `song:` in project.yaml (name part, also searched in
  AutoEdit's music folder), else the first file in `music/`. The plan prints which one it took; say it at gate B.
- Optional: title text (place/topic), accent colour
  (default #E70002), length (default 18 s), title variant (poster_condensed | heavy_grotesque).
- Footage may be S-Log3 (Timon's A6700) or Rec.709; `--grade auto` detects it; say which grade was used.

## Steps and approval gates
1. `python -m engine validate` — DNA approved + Edge + FFmpeg present.
2. `python -m engine plan "<project>" --title "<TEXT>" [--length 18] [--accent #HEX] [--seed N]`
   → `<project>/cine_montage/edl.json`, `storyboard/storyboard.html`, `storyboard/storyboard_sheet.jpg`.
   The plan step also runs the style checks (`engine/style_checks.py`, from EDITING_PSYCHOLOGY.md). It auto-removes
   rule-breaking accents and prints ok/warn/fail; they also sit at the top of the storyboard. `engine check` re-runs them.
3. Look at the storyboard sheet yourself first (does each shot make sense, title readable, no ugly frames?). Re-plan with
   another `--seed`/length if needed, and on any `FAIL`. Then send Timon the sheet + a short summary (length, song, title, accents, open
   questions). **STOP — gate B. Wait for an explicit yes in chat.** Style approval is not approval of this video.
4. Optional review clip before approval: `python -m engine preview "<project>"` (half size).
5. New fonts/colours/effects outside the DNA → show a test and ask first (gate C).
6. Only after Timon's yes: `python -m engine approve "<project>" --by Timon --note "<his words>"`, then
   `python -m engine render "<project>"` (refuses if the EDL changed after approval) → `<project>/exports/cine_montage_*.mp4` + QA.
7. Watch the QA (size, duration, black/frozen, LUFS ≈ −14, true peak ≤ −1) and look at frames around the title, flashes,
   card series and the last shot. Fix and re-render if needed, then send the MP4 (or a <30 MB preview for the phone).

## Rules of thumb (from the DNA)
No captions · one accent colour · one title only · no flash/whip/grid flow on the title · card series 3-6 shots cut hard ·
Grid Flow (Timon's own transition, 4x4 wipe left + exposure flash, 0.48 s) 1× per video, none in cooking/clothing videos (`category: food|fashion` skips it; `--grid-flow off` to skip) ·
≤ ~0.5 accents/s · end on the longest scenic shot · do not copy any reference creator's handles or end cards.

## Known limits
Depth titles and cut-out flashes need a subject matte (not built). Fonts are verified OFL approximations. Cuts are
paced, not beat-locked (snapped to a strong onset only within 2 frames).

## Learnings from real runs
- 2026-10-29 (Mongolie 2025, 69 clips): with many clips the planner put one clip in 11 of 34 shots, because it only
  avoided reusing the same *segment*. It now prefers clips that are not yet in the edit (34 clips in 34 shots). Title
  and final are always the top-scoring shot, whatever the seed, and the top "establishing" shot was a hoodie close-up:
  look at the title/final on the sheet and pin better ones with `--title-shot CLIP[:s]` / `--final-shot CLIP[:s]`.
  Large footage on another drive: link it as `clips/` with a junction (`mklink /J`) instead of copying.
- 2026-10-29 (Beef Tartaar, recipe): a recipe needs cooking order, and the planner picks by score. `--order story`
  puts the body shots in shooting order (the cold open stays a teaser). `order:` in project.yaml lists the clips in story
  order, and `NAME:a-b` uses only those seconds; clips that are not listed are left out (empty sink, tap). Build that
  list by content: the DJI clock ran 1 h off the Sony. Dim kitchen footage looked milky with reference_film; `--look
  clean_warm` keeps food natural. The score likes sharp, empty frames (a bare counter), so check the sheet for them.
  Timon still picked B (reference_film). On render, `--grade auto` took one DJI clip (no sidecar) for S-Log3: the
  pot shots came out oversaturated. Read the "grade" notes in qa.json after every render; when all footage is
  Rec.709, render with `--grade rec709` (same EDL, the approval stays valid).
  2026-10-30: Timon spotted near-identical consecutive shots (same clip, same framing) on the sheet. Story order puts
  two windows of one clip next to each other; merge such pairs into one longer shot before gate B. A run of shots
  where something changes (knife cutting further) can stay. Without Grid Flow (food) seed 1 had only 3 accents:
  compare a few seeds and pick one with ~5 spread accents and 0 warnings.
- 2026-10-28: `engine plan` ignored `song:` in project.yaml and took the first file in `music/`. A re-plan of Smoke
  Sesh would have used the Shanghai track instead of Austria. Fixed; always state the song and its source at gate B.
- 2026-10-28: style checks on the approved Smoke Sesh plan flagged the AI drone shot as the title shot. The planner now
  prefers real footage for title/final. On a re-plan, the B&W entry flash landed within 1 s of another accent, and the
  checks removed it.
- Smoke Sesh (2026-10-25, first real edit): song length caps the edit — a 13 s song gives a 13 s video; say so at gate B.
- Sony S-Log3 clips are detected from the `<stem>M01.XML` sidecar; the pixel heuristic missed two of them. Keep sidecars
  next to the clips.
- AI drone clips can look sharper than real footage and get picked too often; the planner caps them at 2 uses — mention
  near-duplicate AI shots in the plan summary.
- Final 1080p export of 13 s is ~40 MB (CRF 16); make a smaller phone copy before sending over Remote Control.
- A song lifted from a reference video is fine for private use but flag the copyright risk before posting.
- 2026-10-26: Timon saw the white-card image squashed — the 16:9 frame was resized into the ~4:3 inset. The card now
  centre-crops (cover). Check proportions (faces, round objects) on card frames at QA.
