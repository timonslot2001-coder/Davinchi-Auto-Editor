# 0004 AI shots: local Wan first, paid Muapi only after a quote and a yes

- Status: accepted
- Date: 2026-10-21 (Muapi), 2026-10-22 (local Wan default)
- Source: commits `814ff63` and `189dfbe`; the money rule in CLAUDE.md

## Context
Muapi models (kling, veo3, …) cost real money per shot. Wan 2.2 5B runs for free on the RX 9070 XT through ComfyUI, but
slowly (6.5 min per clip when first measured, 32–46 min in later image-to-video runs) and with less camera motion.

## Decision
`--model local-wan` is the default. A Muapi model runs only after `autoedit generate ... --quote`, the price told to
Timon, and his yes in chat for that one shot. `ai_budget_usd` in `project.yaml` is a hard cap that Claude never raises.

## Consequences
- AI shots are free by default but take about half an hour each; plan for that.
- AI shots are support footage. The cine montage planner caps them at 2 uses and keeps them off the title and the final
  shot.
