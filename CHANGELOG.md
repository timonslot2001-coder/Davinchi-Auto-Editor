# Changelog

What changed, in words you would notice in an edit or on the PC. Newest first. Small fixes are folded into the day's
entry; the full list is in `git log`. Hard-to-reverse choices also get a record in [docs/decisions/](docs/decisions/README.md).

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
