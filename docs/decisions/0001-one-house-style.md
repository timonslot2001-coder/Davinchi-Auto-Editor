# 0001 One cinematic house style for every video

- Status: accepted
- Date: 2026-10-19
- Source: Timon, "make the editor global, I give the category, but it all has to be the same style" (`taste.yaml` → `one_style`)

## Context
The first version had a preset per niche (fitness, travel, fashion, lifestyle), each with its own pacing and effects.
Videos from different niches looked like different channels.

## Decision
Every video uses the `cinematic` house style (`config.yaml` → `default_style`). The category only changes captions and
hashtags (`--category`). The other presets in `styles.yaml` stay available, but only with an explicit `--style`.

## Consequences
- One recognisable look across the channel; new references improve that one style.
- The house style renders 16:9 by default (`styles.yaml` → `cinematic.aspect`); `--aspect 9:16` gives the vertical
  version plus the 4:5 feed copy.
