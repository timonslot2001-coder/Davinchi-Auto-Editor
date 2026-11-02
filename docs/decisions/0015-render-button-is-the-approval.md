# 0015 On the website, "Ja, renderen" is the approval

- Status: accepted
- Date: 2026-11-02
- Source: Timon, "Ik vind het te ingewikkeld", "fase 3" of [simpler-plan.md](../simpler-plan.md)

## Context
Approving a cine montage on the website meant typing a sentence in your own words, pressing *Goedkeuren*, then
*Renderen*. The rule behind it (render only after Timon's yes on that plan, [0003](0003-nothing-posts-without-approval.md))
is about who decides, not about typing.

## Decision
- The project page shows one path: Clips → Muziek → Bekijken → **Ja, renderen**. Pressing that button records the
  approval of the current plan (`engine approve --note "Ja, renderen (knop in de website)"`) and then renders.
- The button only exists on the website, next to the storyboard of that plan; a new plan needs a new press.
- The grade is the house look unless Timon picks another one under *Zelf bijsturen* (decision
  [0001](0001-one-house-style.md)); there is no grade step on the path.
- When Claude runs a cine montage, it still waits for Timon's explicit yes in chat (CLAUDE.md).

## Consequences
- Two fewer actions per video and no typing.
- The approval record says it came from the button, not what Timon thought of the plan; feedback goes in the shot
  comments or to Claude.
