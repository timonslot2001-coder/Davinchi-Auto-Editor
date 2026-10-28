# VIDEO EDITING SYSTEM — cine montage

Applies the approved Editing DNA (`../EDITING_DNA_PACKAGE/`, profile `P_CINE_MONTAGE`) to new footage.
Claude Code skill: `../.claude/skills/cine-montage/SKILL.md`.

## Layout
| path | what |
|---|---|
| `../EDITING_DNA_PACKAGE/` | the DNA (style_dna.json, rules, components, fonts) — the `dna/` of this system, not duplicated |
| `engine/dna.py` | loads + validates the DNA, refuses unapproved profiles |
| `engine/media.py` | clip inventory (ffprobe), per-segment motion/pan/sharpness/light, song choice (`--song` → project.yaml `song:` → `music/`), music tempo/onsets (cached) |
| `engine/gridflow.py` | Timon's Grid Flow transition (RULE_GRID_FLOW) |
| `engine/planner.py` | DNA rules → EDL (every event cites rule ids) |
| `engine/edl.py` | EDL model + validation (gaps, frame length, one title, no accent on the title) |
| `engine/graphics.py` | captures the DNA's HTML components to transparent PNG with headless Edge |
| `engine/render.py` | FFmpeg decode per event (+ AutoEdit LUT) → numpy devices → FFmpeg H.264/AAC, loudnorm −14 LUFS |
| `engine/storyboard.py` | HTML storyboard + contact sheet from real graded frames |
| `engine/style_checks.py` | style checks on the plan (EDITING_PSYCHOLOGY.md §1/§2): auto-fix accents, ok/warn/fail in the storyboard |
| `engine/qa.py` | size/fps/duration, black/frozen, LUFS/true peak |
| `engine/cli.py` | `validate / plan / check / approve / preview / render / qa` with the approval gate |
| `tests/style_checks_test.py` | style checks + auto-fix on a deliberately broken plan |
| `tests/smoke_test.py` | SYNTHETIC end-to-end test (generated clips + beat) |
| `tests/gridflow_test.py` | Grid Flow variants on real shots of a project (gate C test, not an export) |

## Use
```
cd VIDEO_EDITING_SYSTEM
C:\Users\Timon\.aev\Scripts\python.exe -m engine validate
C:\Users\Timon\.aev\Scripts\python.exe -m engine plan "<project>" --title "UTRECHT"
   → prints the song it took + the style checks; review <project>/cine_montage/storyboard/storyboard.html, get approval
C:\Users\Timon\.aev\Scripts\python.exe -m engine check "<project>"          (style checks again, e.g. after editing edl.json)
C:\Users\Timon\.aev\Scripts\python.exe -m engine approve "<project>" --by Timon --note "..."
C:\Users\Timon\.aev\Scripts\python.exe -m engine render "<project>"
```
Outputs: `<project>/cine_montage/` (inventory cache, EDL, storyboard, APPROVAL.json, qa.json) and `<project>/exports/`.
Originals are never modified.
