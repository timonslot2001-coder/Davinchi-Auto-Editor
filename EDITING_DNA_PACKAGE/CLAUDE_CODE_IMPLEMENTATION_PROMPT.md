# Stage 2 — apply the Editing DNA to new footage (copy-paste prompt for Claude Code)

You are the video-editing director, motion designer, implementer and QA lead for this repository. Use the Editing DNA
package in `EDITING_DNA_PACKAGE/` to build a reusable editing system and, when footage and approvals exist, deliver a
finished MP4. Do not use Remotion. Default composition: HTML/CSS/SVG/JS components captured with headless Microsoft Edge
plus FFmpeg; Resolve (via the existing `autoedit` package) may be used for grading/cutting where it is the stronger tool.

## 1. Load and validate (no re-analysis)
- Read `README_START_HERE.md`, `style_dna.json`, `STYLE_DNA.md`, `EDITING_PSYCHOLOGY.md`, `ASSET_LIBRARY.md`,
  `ACCURACY_AND_GAPS.md`.
- Parse `style_dna.json`; check every file path it names exists. Report the approval state per profile. Only profiles
  with `approval == "approved"` may drive creative defaults; otherwise ask.
- Do not re-run reference extraction. Reopen a reference frame only to resolve a contradiction, and log that.
- Never promote an item from ACCURACY_AND_GAPS "inferred/approximated" to "verified".
- Write `PROJECT_STATUS.md` (paths, profile IDs, approvals, dependencies, next allowed step).

## 2. Build the engine even without footage
`VIDEO_EDITING_SYSTEM/` with: `engine/` (input resolver, timeline/EDL model, component renderer reusing
`animations_and_components/components.html`, audio mixer, exporter), `previews/`, `exports/`, `tests/`,
`STYLE_SELECTION.md`, and a project skill at `.claude/skills/cine-montage/SKILL.md` (YAML frontmatter: name,
description). Smoke-test: DNA parses, every component captures a frame, a 3-second synthetic test (labelled SYNTHETIC)
encodes to a playable MP4. Mark untested capabilities as untested.

## 3. New raw footage
- Inventory every clip (ffprobe: codec, fps, resolution, duration, audio). Preserve originals.
- Speech present → transcribe with timestamps; none → do not invent a script. Music → tempo/onsets.
- Rate shots: establishing / detail / motion / people / scenic-ending candidates; flag unusable shots.

## 4. Edit decision list (mandatory approval gate B)
Build a timecoded EDL covering the whole output. For each event: source clip + in/out, output in/out, cue (music/visual),
rule ID from `style_dna.json → rules[]`, component + parameters, accent colour, audio treatment, confidence, assets
needed. Follow the structure in STYLE_DNA.md §2 and the pacing curve; respect the attention budget (1 graphic + 1
transition accent at a time; ~0.5 accents/s) and the restraint clauses. Then render an HTML storyboard with real frames
(before/peak/after for the title, flashes, whips, card series, final shot) in the delivery aspect ratio.
**STOP. Ask for approval of the EDL + storyboard.** Approval of the DNA is not approval of a video.

## 5. New assets or departures (gate C)
New fonts, colours, effects or anything not in the DNA → show a still/motion test and ask first.

## 6. Final execution (gate D, only after B and C)
Render components frame-accurately, composite with FFmpeg (or Resolve), mix audio without clipping (true peak ≤ −1 dBTP,
platform loudness ≈ −14 LUFS), export MP4 (H.264, the approved resolution/fps). QA: duration, no black/frozen frames,
title text spelled right, safe areas, sync. Compare final frames with the storyboard; report divergences honestly.
Deliver: MP4, change log, EDL, component/asset paths, QA notes.

## 7. Skill
After the first approved real edit, update `.claude/skills/cine-montage/SKILL.md` with what QA taught you. The skill must
load the DNA from disk, list required inputs (clips; optional song, title text, accent colour), keep the B/C/D approval
gates, and reuse components instead of re-analysing references.
