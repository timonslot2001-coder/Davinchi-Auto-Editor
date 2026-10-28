# EDITING DNA PACKAGE — start here

Stage 1 output (style extraction) for Timon's AutoEdit project. Status of profile **P_CINE_MONTAGE: approved (2026-10-25)**;
RULE_GRID_FLOW added by Timon on 2026-10-26. Stage 2 (the editing engine) is built: `../VIDEO_EDITING_SYSTEM/`.

## Open first
1. `visual_report.html` — the visual report (open in a browser by double-click; everything is relative/local).
2. `STYLE_DNA.md` — how to apply the style, with if-this-then-that rules.
3. `EDITING_PSYCHOLOGY.md` — why each decision is made, and when not to.

## Files
| file | what |
|---|---|
| `style_dna.json` | machine-readable source of truth (profiles, tokens, rules, evidence, confidence) |
| `STYLE_DNA.md` | application guide |
| `EDITING_PSYCHOLOGY.md` | decision rules + attention budget |
| `ASSET_LIBRARY.md` | fonts, components, rights |
| `ACCURACY_AND_GAPS.md` | verified vs inferred vs approximated |
| `CLAUDE_CODE_IMPLEMENTATION_PROMPT.md` | copy-paste prompt for Stage 2 (editing system + skill) |
| `reference_manifest.json` | the 22 reference files with sha256 — **user-supplied footage, not included** |
| `reference_frames/` | extracted frames, contact sheets, cut strips, ANNOTATIONS.md (third-party, analysis only; local, not in git) |
| `annotated_comparisons/` | reference vs **synthetic** HTML reconstruction, side by side (local, not in git) |
| `animations_and_components/` | `components.html` (reusable components) + `capture.py` (headless Edge capture) |
| `audio_analysis/` | pacing curve, beat-sync test, per-reference event lists |
| `assets/fonts/` | OFL fonts + licences |

## Dependencies (verified on this PC)
- Microsoft Edge (headless capture): `C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe`
- Python with opencv-python, numpy, imageio-ffmpeg, librosa (the AutoEdit venv `C:\Users\Timon\.aev`)
- FFmpeg via imageio-ffmpeg.

## Component demo
Open `animations_and_components/components.html?c=title_slam&text=UTRECHT&width=0.9&height=0.6&play=1`
(any browser; `c=` one of title_slam, side_labels, white_card, colour_card, white_flash, whip_blur, bw_shot, hud_labels).
Re-render the comparisons: `python animations_and_components/capture.py`.

## Choosing a profile
Only `P_CINE_MONTAGE` is extracted. `P_VERTICAL_VLOG` and `P_TALKING_CAPTIONS` are listed but not extracted.

## How it is used now
Stage 2 is done (`CLAUDE_CODE_IMPLEMENTATION_PROMPT.md` is kept as the record of what was asked). New raw footage goes in
an AutoEdit project folder (`Videos/AutoEdit Projects/<name>/clips`). The `cine-montage` skill runs
`VIDEO_EDITING_SYSTEM/engine`. Every plan gets automatic style checks; every new video needs its own plan and storyboard
approval before a final render.

## Keeping these documents true
`style_dna.json` is the source of truth. After changing it or any document here, run `python tools/doc_check.py` from
the repo root. It checks that every rule appears in the docs, that the numbers match the JSON, and that the paths and
commands named in the docs exist.
