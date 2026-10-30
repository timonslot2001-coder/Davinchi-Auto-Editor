# 0012 Grid Flow once per video, not in cooking or clothing videos

- Status: accepted
- Date: 2026-10-30
- Source: Timon after the Beef Tartaar edit, "Ik kook of kleding videos hoef je die grid overgangen niet toe te voegen
  dit is leuk voor reizen, maar gebruik dat trucje maar 1x in de video anders slaat het echt nergens op"

## Context
Decision 0006 allowed Grid Flow twice from 16 s. The Beef Tartaar recipe got two Grid Flows. For a recipe or a clothing
video the geometric wipe distracts from the subject, and a second one reads as a gimmick.

## Decision
- RULE_GRID_FLOW is used at most once per video, at any length (planner and style check).
- Projects with `category: food`, `cooking`, `fashion` or `clothing` in project.yaml get no Grid Flow. Travel and
  other categories keep the single one. `--grid-flow off` still skips it anywhere.

## Consequences
- Amends 0006. STYLE_DNA, style_dna.json, EDITING_PSYCHOLOGY §7/§10 and the cine-montage skill say "1×".
- Exports made before this date (Mongolie, Beef Tartaar) keep what they had.
