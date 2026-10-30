# Changelog

What changed, in words you would notice in an edit or on the PC. Newest first. Small fixes are folded into the day's
entry; the full list is in `git log`. Hard-to-reverse choices also get a record in [docs/decisions/](docs/decisions/README.md).

## 2026-10-30 — AutoEdit Studio (website, Docker)
- New website for all functions: projects, cine montage (plan, numbered shots with comment boxes, approve, render,
  QA), AutoEdit builds in Resolve, AI shots (price first for paid models), posting queue, music, insights and tools,
  with a live log per job. Works on a phone too. `start-studio.bat` runs it on this PC; `start-studio-docker.bat` runs
  the website in Docker Desktop and the work on Windows through a worker, because Resolve, the GPU and the footage
  are there. See [webapp/README.md](webapp/README.md).
- Cine montage render: `brighten` per shot for a dark shot (used on the Beef Tartaar ending).

## 2026-10-30 — Grid Flow only once
- New skill `juict-edit`: how a JUICT/client film is made (original intact, brand intro/outro, whole-beat cuts, photo snaps).
- Cine montage: Grid Flow is used at most once per video (it was twice from 16 s), and not at all in cooking or
  clothing videos (`category: food` or `fashion` in project.yaml). Decision [0012](docs/decisions/0012-grid-flow-once-travel-only.md).

## 2026-10-29 — Documentation, round 3 to 5
- Client work is a separate track: `client_edits/` with the JUICT film as a standalone script that reproduces v12
  (no client files or personal names in git). The docs map now starts with *which editor for which goal*, own
  channels first.
- `taste.yaml`: every rule says where the code enforces it (`enforced_by`); `doc_check` fails when that code changes.
  Removed the unused `effects_intensity` knob (the real setting is `config.yaml` → `effects.intensity`), and moved the
  JUICT rule out of `taste.yaml` into decision 0010, because client work is not taste for your own videos.
- `doc_check` also checks that every technique in `inventory.yaml` can actually be placed by the director.
- New [docs/PLATFORM_SPECS.md](docs/PLATFORM_SPECS.md) from Meta's and TikTok's own documentation. Found: Instagram's
  API refuses video above 25 Mbps, and AutoEdit rendered at exactly 25 Mbps. Now 20 Mbps, the 4:5 copy is capped too,
  and the QC flags anything above 25 Mbps.
- `TRENDS_REPORT.md`: re-checked which claims trace back to Instagram itself.
- Documents with a *Review by* date get a warning from `doc_check` once that date has passed.
- Own videos stay at 25 fps on purpose (decision [0011](docs/decisions/0011-stay-at-25-fps.md)): it matches the
  A6700's 50p for smooth slow-mo and avoids flicker under 50 Hz lights.

## 2026-10-29 — Documentation, round 1 and 2
- New: [docs/README.md](docs/README.md), a map that tells you which document answers which question.
- New: decision records ([docs/decisions/](docs/decisions/README.md)), this changelog and a Dutch ↔ English
  [glossary](docs/GLOSSARY.md).
- README rewritten into getting started → tasks → command reference → how it learns. It now lists every command and
  states correctly that the house style renders 16:9 by default (9:16 + 4:5 only with `--aspect 9:16`).
- `CLAUDE.md`: a *Client films* section (JUICT approach) and pointers to the new docs.
- `EDITING_PSYCHOLOGY.md`: the style mapped onto Murch's six cutting criteria; JUICT feedback logged.
- `STYLE_DNA.md`: per rule, what it looks like when it goes wrong, from real runs.
- `tools/doc_check.py`: now also fails when a document is missing from the map, a decision is missing from its index, or
  the README misses a command.

## 2026-10-28
- Client film rule: a finished company film stays intact (`taste.yaml` → `client_film_intact`, from the JUICT edit).
- Python environment moved to a fixed place, `~/.autoedit/venv`, built from `requirements-lock.txt`; `~/.aev` points
  there.
- Every documentation file is checked by `tools/doc_check.py`. `engine plan` now uses the song from `project.yaml`
  (before, a Smoke Sesh re-plan would have picked the wrong song).
- Style checks on every cine montage plan: accents that break a rule are removed automatically, and the storyboard shows
  ok / warn / fail on top.
- `EDITING_PSYCHOLOGY.md` v2: mechanisms, checks, role casting, failure modes, Grid Flow and a feedback log.

## 2026-10-27
- Setup under version control: skills, plugins, Comfy models, the Auto Grade script and the bought packs (by hash),
  restored with `setup/install.ps1`.

## 2026-10-26
- Grid Flow transition added to the cine montage style (1–2× per video).
- The white card centre-crops instead of squashing the shot.
- Local AI: smaller VAE decode tiles after a 720p crash.

## 2026-10-25
- Cine montage: Editing DNA package (17 references measured), style approved, editing engine with approval gates,
  first real edit (Smoke Sesh) rendered and checked.

## 2026-10-22
- Local AI: 720p is the default AI model, a 1080p preset, Super Scale 2x on AI clips under 1080p, ComfyUI starts
  headless by itself.

## 2026-10-21
- AI shots via Muapi (price shown first) and locally via Wan 2.2 on the GPU (free).
- Explainer mode: step-by-step onboarding videos from a script, with optional AI music.

## 2026-10-19
- AutoEdit: DaVinci Resolve auto editor for TikTok and Instagram.
- House style from references, music-driven pacing, title size and corner label.
- Learning loop: technique inventory, director, self-review and taste rules.
- Projects: one folder per shoot, edited by name; the song in `project.yaml` wins.
- FOUR Editors packs: overlays as techniques, 1,882 sounds as ear candy.
