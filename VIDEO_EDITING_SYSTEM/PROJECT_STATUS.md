# PROJECT STATUS (2026-10-28)

## Verified
- DNA package `../EDITING_DNA_PACKAGE/` loads; profile P_CINE_MONTAGE **approved**; 10 rules (9 from the references +
  RULE_GRID_FLOW from Timon), priority list consistent.
- Dependencies: Python venv `C:\Users\Timon\.aev` (opencv, numpy, librosa, imageio-ffmpeg 7.1, pyyaml), headless
  Microsoft Edge, AutoEdit LUT builder (`autoedit/grade.py`). A new PC is set up with `../setup/install.ps1`.
- `tests/smoke_test.py` PASS on SYNTHETIC footage (10 generated clips, generated beat): plan → storyboard → render gate
  refuses unapproved EDL → test-approval → 1920x1080 25 fps H.264/AAC, 12.0 s, no black/frozen frames, −15.6 LUFS,
  true peak −1.3 dBFS; title at 0.52 s after a cold open; card series cuts hard. Result: `tests/smoke_result.json`.
- Skill file `../.claude/skills/cine-montage/SKILL.md` with valid YAML frontmatter (name, description).
- First real edit **Smoke Sesh** (A6700 S-Log3 + 3 local Wan AI clips, song Austria, title SMOKE SESH): plan approved by
  Timon ("Plan approved, do the final render."), EDL e305441655cd.
  - 2026-10-25: `exports/cine_montage_20261025_1009.mp4`. 1920x1080 25 fps, 13.04 s, no black/frozen frames,
    −14.4 LUFS, TP −1.5 dBFS. S-Log3 detected via the Sony sidecar XML.
  - 2026-10-26: re-rendered as `exports/cine_montage_20261026_1316.mp4` after Timon saw the white card squashed (now
    centre-cropped). Same approved EDL. **This is the current final.** Phone copies: `SMOKE_SESH_phone_v2.mp4`,
    `SMOKE_SESH_easter_egg(_phone).mp4` (1-frame hidden photo at frame 221, on Timon's request).
- RULE_GRID_FLOW (Timon's Grid Flow, approved 2026-10-26): `engine/gridflow.py` + planner placement (1×, 2× from 16 s).
  Test render on real Smoke Sesh shots (`tests/gridflow_test.py`). The Smoke Sesh export predates it.
- Style checks (2026-10-28): `engine/style_checks.py` runs on every plan, auto-removes rule-breaking accents and shows
  ok/warn/fail on the storyboard; `tests/style_checks_test.py` PASS. A re-plan of a Smoke Sesh copy: 17 ok, 0 warn,
  0 fail after one auto-fix. On the approved Smoke Sesh plan it warns that an AI shot carries the title; the planner now
  prefers real footage for title and final shot.
- Song choice (2026-10-28): `engine plan` takes `--song`, then `song:` in project.yaml, then the first file in
  `music/`, like AutoEdit's `project` command. Before this fix a re-plan of Smoke Sesh would have used the wrong song.

## Untested (not claimed working)
- Grid Flow look vs. the original RAM transition inside Resolve (not compared side by side).
- Music onset snapping on a longer song; whip on fast real pans.
- Skill discovery/invocation in a fresh Claude Code session (file is in the documented project-skill location).
- Loudness on full-length songs (single-pass loudnorm; target −14 LUFS).

## Approval state per video
- Smoke Sesh — approved + rendered (2026-10-25), re-rendered with the card fix (2026-10-26).

## Next allowed step
Next project: Timon provides clips + song + title → `plan` → storyboard to Timon → wait for gate B approval.
