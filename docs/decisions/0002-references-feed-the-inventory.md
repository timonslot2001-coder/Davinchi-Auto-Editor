# 0002 References feed the inventory, never the timeline

- Status: accepted
- Date: 2026-10-19
- Source: Timon, "now you made the videos exactly the same as the ones I sent" (`taste.yaml` → `no_copy`)

## Context
Early edits rebuilt the structure of the reference videos shot by shot. They looked copied.

## Decision
A reference is analysed for *techniques* (cuts, flashes, sounds, text). Each new technique goes into `inventory.yaml`
with its trigger, budget and matching sound. The director places techniques per video only where the footage and music
motivate them. A reference's order and timing are never rebuilt.

## Consequences
- Every video is a fresh mix; the style grows with every reference.
- Music from a reference may only be used as clean music, and posting it carries a copyright risk that is named first.
