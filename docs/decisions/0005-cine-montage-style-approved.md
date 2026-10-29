# 0005 P_CINE_MONTAGE is the approved montage style

- Status: accepted
- Date: 2026-10-25
- Source: Timon, "Ik keur het goed" (`VIDEO_EDITING_SYSTEM/STYLE_SELECTION.md`)

## Context
17 reference montages were measured (cuts, transitions, titles, grade) into `EDITING_DNA_PACKAGE/style_dna.json`.

## Decision
The profile P_CINE_MONTAGE drives the cine montage engine. Defaults: title variant `poster_condensed` (Anton, fitted),
accent `#E70002`. Per video, the title text, accent and variant are confirmed at gate B (see 0003).
P_VERTICAL_VLOG and P_TALKING_CAPTIONS are listed but not extracted, and may not be borrowed from.

## Consequences
The numbers in `STYLE_DNA.md` bind the engine and are checked by `tools/doc_check.py` and `engine/style_checks.py`.
A change to the style needs a new decision record.
