---
name: juict-edit
description: Edit a film for JUICT (or another client) the way the approved JUICT aftermovie was made - keep the client's finished film intact, swap in the JUICT brand intro/outro, remove only the shots Timon names in whole beats, add photo snaps on request. Use when Timon asks for a JUICT film, a client film "in de JUICT-stijl", or a brand intro/outro on an existing film. Not for his own channel videos (that is cine-montage / AutoEdit).
---

# juict-edit

Client work is its own track (decision `docs/decisions/0010-client-films-stay-intact.md`, `CLAUDE.md` → *Client films*).
Its feedback never goes into `taste.yaml` or the cine montage style.

Python: `C:\Users\Timon\.aev\Scripts\python.exe`. Reference build: `client_edits/juict_aftermovie/edit.py` (v12, approved
2026-10-28; reproduces the delivered film frame for frame).

## Building blocks (reuse, don't rebuild)
- `client_edits/juict_aftermovie/brand_motion.py` (+ `brand_motion2.py`): the JUICT intro/outro - navy field with slanted
  lines, logo that draws itself on letter by letter, red bar, brackets, mono label, grain, layered wipe to the footage.
  Every shape follows the italic slant of the logo. Another brand: copy the folder, swap the logo file and the colour
  constants at the top of `brand_motion.py`.
- `Film.print_frame` in `edit.py`: the photo snap (white flash, white print landing on the blurred shot, camera click
  from the FOUR Editors SFX pack).

## Inputs (read from the project folder, never committed - the repo is public)
`Videos\AutoEdit Projects\<project>\`: `source/<original film>.mp4`, `branding/juict_logo_white_red.png`,
`photos/photo_N.jpg` (for snaps). Ask Timon which shots to remove and where the snaps go if he has not said.

## Steps
1. Copy `client_edits/juict_aftermovie/edit.py` to the project folder as `edit_v<N>.py` (N = 1 to start); point
   `PROJECT` and the cut list at the new film. One version per round of feedback; never overwrite an export.
2. Start from the original. Change only what Timon names: brand intro instead of the opening card, outro instead of the
   end card, shots to remove, photo snaps. No subtitles, name cards or interview changes unless he asks.
3. Remove footage in **whole beats** (beat grid from librosa) and cut picture and sound on the same frame; ~30 ms
   crossfade on the splice so the music stays in time.
4. Verify before sending: frames after each cut match the original (mean difference ≈ encoding noise), audio lag vs
   the original 0 samples, no click at the splice, and a contact sheet of intro, cuts, snaps and outro.
5. Send a 720p preview. Nothing is delivered or posted without Timon's OK. For upload: a 1080p 2-pass copy under 30 MB
   (Remote Control limit); the full master stays in `exports/`.
6. When approved: put the final script in `client_edits/<client>_<film>/edit.py` (no client files, no personal names of
   people in the film), add a row to `client_edits/README.md`, and add a line to `CHANGELOG.md`.

## Learnings
- 2026-10-28 (JUICT aftermovie): versions 1-10 re-cut the interview, swapped a speaker and added subtitles and a name
  card; Timon wanted the original intact ("de orginele bedrijfsfilm mag je intact houden ... geen ondertitels, niks").
  v12 = original + JUICT intro/outro, the IT Synergy booklet shot out (48 frames = 4 beats), 3 photo snaps.
