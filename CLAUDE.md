# AutoEdit — how Claude works in this repo

Timon's DaVinci Resolve auto editor (TikTok + Instagram). One **house style** (cinematic) for every
video; the category only changes captions/hashtags. Work only in this repo; commit everything to
`main` and push (Timon wants everything pushed and merged).

## The learning loop (this is the point of the project)

The editor must get better every time, without copying references 1:1.

1. **Timon sends a reference video** → analyse it (cuts/rhythm, grade, text, transitions, sound design)
   and add every *new* technique to `inventory.yaml` as eye candy (VFX) or ear candy (SFX): what it
   is, `trigger` (when it is motivated), `max`, `cooldown_s`, the matching `sfx`, `priority`.
   If the technique needs code, add it to `autoedit/fx.py` (Fusion) and test it with a render.
   **Never rebuild the reference's structure** — references feed the inventory, not the timeline.
   Music from a reference: extract only clean music (no speech, no end-card sound) into the music folder.
2. **Timon gives feedback** ("too much", "bigger title", "that pop looks weird"…) → add a rule to
   `taste.yaml` (quote what he said + the rule) and adjust the knobs/settings so it sticks.
3. **Timon sends clips (+ a song)** → `autoedit run <folder> --music <name> [--title ...] [--label ...]`.
   The director picks techniques only where motivated (music hit, motion, scene change, quiet part),
   within budget; every VFX gets its SFX.
4. **Always rewatch before showing it**: the pipeline writes `<base>_review.json` and
   `<base>_review.png` (a frame of every accent). Read both, look at the frames, and check:
   does each accent have a reason? Is anything distracting, repetitive, too loud, or unmotivated?
   Less is more — remove before adding. Fix and re-render if needed, then send the video.

## Three kinds of edits
- **AutoEdit** (`autoedit/`, the loop above): Timon's own shoots, built in Resolve. House style renders 16:9;
  `--aspect 9:16` for TikTok/Reels.
- **Cine montage** (`VIDEO_EDITING_SYSTEM/`, skill `.claude/skills/cine-montage/`): applies the approved Editing DNA
  (`EDITING_DNA_PACKAGE/`). Gates: plan + storyboard → **wait for Timon's explicit yes** → `approve` → `render`. Never
  approve or render without his yes on that specific plan. Every plan runs the style checks
  (`engine/style_checks.py`). Feedback on a cine montage goes into `EDITING_DNA_PACKAGE/EDITING_PSYCHOLOGY.md` §10 and
  the skill's "Learnings" (not `taste.yaml`).
- **Client films** (see below): a small script per project that starts from the client's finished film.

## Client films (e.g. JUICT)
Working instructions: `.claude/skills/juict-edit/SKILL.md`.
Decision `docs/decisions/0010-client-films-stay-intact.md`. Client work is a separate track from Timon's own channels:
its feedback never goes into `taste.yaml` or the montage style. Iterate with `edit_v<N>.py` in the project folder
(`Videos/AutoEdit Projects/<name>/`), one version per round of feedback, never overwrite an export. The delivered
version goes into the repo as `client_edits/<client>_<film>/edit.py` (no client files, no personal names; see
`client_edits/README.md`).
- The original stays as delivered. Change only what Timon names: brand intro/outro, a shot to remove, photo snaps. No
  subtitles, name cards or interview changes unless he asks.
- Remove footage in **whole beats** (beat grid from `analysis/beats.npy` or librosa) and cut picture and sound at the
  same frame, so the music stays in time; crossfade the splice ~30 ms.
- Verify before sending: frames match the original at a few times after the cut (mean difference ≈ encoding noise),
  audio lag vs the original is 0 samples, no click at the splice, and a contact sheet of intro, cut, snaps and outro.
- Send a 720p preview, and for uploading a 1080p 2-pass copy under 30 MB (Remote Control limit); the full master stays
  in `exports/`.

## Where things are written down
Map of all docs: `docs/README.md`. A hard-to-reverse decision → a new record in `docs/decisions/` (+ its index). A
change Timon would notice → a line in `CHANGELOG.md`. A new document → add it to `docs/README.md`.

## AI shots — local first (free), Muapi only when asked
Default is `--model local-wan`: Wan 2.2 5B on his own RX 9070 XT via ComfyUI, 1280x704, $0. Recent runs took 32–46 min
per 5 s clip (first measured 6.5 min). `generate` gives up waiting after 60 min while ComfyUI keeps going; then poll
`http://127.0.0.1:8188/queue` and copy the newest file from `%LOCALAPPDATA%/Comfy-Desktop/ComfyUI-Shared/output/autoedit/`. AutoEdit starts ComfyUI headless itself if needed. In Resolve, AI clips under 1080p get Super Scale
2x Enhanced automatically. `local-wan-draft` (480p, ~2 min) for prompt tests; `local-wan-1080` (~26 min)
only if he asks. Local clips barely move the camera — describe motion explicitly in the prompt.

### Muapi — money rule
Muapi models (kling, veo3, …) cost Timon real money. ALWAYS run `autoedit generate ... --quote` first, tell him the model
and price, and only run with `--yes` after he says yes in chat — for that one shot. Never raise
`ai_budget_usd` yourself. Prefer `kling` ($0.45) unless he asks for top quality (`veo3`).

## Practical notes
- Python: `C:\Users\Timon\.aev\Scripts\python.exe` with `PYTHONIOENCODING=utf-8`. Windows Smart App Control blocks
  the venv inside Documents (`.venv` here). `.aev` is a junction to `C:\Users\Timon\.autoedit\venv`, built from
  `requirements-lock.txt`. Never put it under AppData: from inside the Claude app, writes there are redirected into the
  app's package folder. `av`/faster-whisper is blocked by Smart App Control in every venv on this PC (known). After installing a package: `pip freeze` into `requirements-lock.txt` (keep its header).
- New PC / new skill, plugin, pack or model: `setup/install.ps1` and `python setup/snapshot.py` (see `setup/README.md`).
- After changing any document, command or `style_dna.json`: `python tools/doc_check.py` must pass.
- Never commit third-party material: reference frames, the RAM `.drfx`, bought packs, songs from references.
- Resolve must be open; never call `comp.Render()` (modal dialog). Fusion comps only render if
  imported from a file (`fx.commit`).
- Grade = one baked LUT (`autoedit/grade.py`): Sony S-Log3 → Rec.709 + `reference_film` look,
  exposure −1.75 stops (Timon's A6700 shoots bright). The Odyssey PowerGrade does nothing by script.
- New footage: A6700 XAVC HS 4K 50p 75M 4:2:0 10-bit S-Log3 (smooth on his AMD GPU).
- Shot tags for story order: `data/tags.json` (look at the clips and tag detail/subject/close/…).
