# 0006 Grid Flow joins the style, 1–2 times per video

- Status: accepted
- Date: 2026-10-26
- Source: Timon at gate C, "Neem de 4x4 wipe left met exposure flits op in de stijl, maximaal 1–2 keer per video"

## Context
Grid Flow is a transition from Timon's own RAM `.drfx` pack. It is not in the references, and the `.drfx` itself may not
be shipped (it is bought, and the repo is public).

## Decision
RULE_GRID_FLOW is rebuilt from the transition's behaviour in `VIDEO_EDITING_SYSTEM/engine/gridflow.py`: a 4×4 wipe left,
a per-tile exposure flash, white grid lines, 12 frames. It is used once per video, twice from 16 s. It never sits on the
title, a card series or the final shot, and never within 1 s of another accent. It is last in the conflict priority.

## Consequences
- Every document labels it *user* (not reference evidence).
- It has not yet been compared side by side with the original inside Resolve (`ACCURACY_AND_GAPS.md`).
