# AutoEdit: DaVinci Resolve auto editor for TikTok, Instagram and YouTube

Drop clips in, and out comes a finished edit in the cinematic house style: graded, cut to the music, with effects and
their sounds, title, captions, cover and caption suggestions. Nothing goes online without your OK.

It is built first for your own channels; client work runs on a separate track. Three ways this repo edits:

| editor | for | start |
|---|---|---|
| **AutoEdit** (`autoedit/`) | your own shoots → Reels / TikTok (9:16) or YouTube (16:9), learns from your feedback | [Edit a shoot](#edit-a-shoot) |
| **Cine montage** (`VIDEO_EDITING_SYSTEM/`) | your own music-only montages in the approved P_CINE_MONTAGE style, with approval gates | [Cine montage](#cine-montage) |
| **Client films** (`client_edits/`) | re-editing a client's finished film: brand intro/outro, remove a shot, photo snaps | [client_edits/README.md](client_edits/README.md) |

Which editor for which goal: [docs/README.md](docs/README.md) → *Which editor for which goal*.

Which document answers which question: [docs/README.md](docs/README.md). What changed: [CHANGELOG.md](CHANGELOG.md).

## Getting started
New PC? First run `setup\install.ps1`. It restores the skills, plugins, Comfy models, Resolve add-ons and the Python
environment; see [setup/README.md](setup/README.md).

1. Open **DaVinci Resolve Studio** (Preferences → System → General → *External scripting using: Local*, already set).
2. Double-click **`autoedit.bat`** to open the dashboard in your browser.
   - Or in a terminal: `autoedit project "smoke"` (a project by name) or `autoedit run "C:\Users\Timon\Videos\Shoot"`.
3. Or just tell Claude: *"start project smoke"* or *"maak een cine montage van smoke"*.

## Edit a shoot
```
autoedit new "Smoke Sesh"          # makes Videos\AutoEdit Projects\Smoke Sesh\ with clips\ music\ exports\ project.yaml
autoedit import "smoke"            # copies new clips from the A6700 SD card (PRIVATE\M4ROOT\CLIP) into clips\
autoedit project "smoke"           # edits it: song from project.yaml or music\, title/label from project.yaml
autoedit projects                  # overview of all projects
```
- **Shape:** the house style renders **16:9** (`styles.yaml` → `cinematic.aspect`). For TikTok/Reels set
  `aspect: "9:16"` in `project.yaml` or pass `--aspect 9:16`; you then also get the 4:5 feed version
  (`format.extra_exports`).
- **Category** (`--category fitness|travel|lifestyle|fashion`) only changes captions and hashtags; the look stays the
  house style (decision [0001](docs/decisions/0001-one-house-style.md)).
- Every build is a new timeline in Resolve's `AutoEdit` project; your originals are never touched.
- After the render the tool rewatches its own video and writes `<name>_review.json` + `<name>_review.png`.

### What happens in a build
| step | what happens |
|---|---|
| **Analysis** | per clip: sharpness, shake, exposure, motion, speech, scene cuts, best moments; skips blurry, dark and duplicate takes |
| **Planner** | hook (strongest shot first), pacing curve (fast → calm → strong outro), beat sync, variety guard, silence cutter, loop ending |
| **Director** | places techniques from `inventory.yaml` only where motivated (music hit, motion, scene change, quiet part), within budget, each with its sound |
| **Grade** | one baked LUT on every clip: Sony S-Log3 → Rec.709 + the `reference_film` look, −1.75 stops (`autoedit/grade.py`, `grading` in `config.yaml`) |
| **Effects** | punch zoom, smooth zoom, shake, invert/white flash, whip, glitch, speed ramps on motion peaks, 6-panel grid on the drop, FOUR Editors overlays |
| **SFX** | generated set (whoosh, hit, impact, pop, click, shutter, riser, swell, glitch) + the FOUR Editors sounds, matched by name |
| **Stabilization** | `auto` (only shaky clips), `all`, `none`, or per clip in the dashboard |
| **Audio** | music bed cut to the drop, faded, ducked under speech; voice isolation; −14 LUFS |
| **Text** | title and corner label in the safe zones; auto captions (Resolve AI) on speech |
| **Export** | QC (black frames, clipping, resolution), loudness, cover frame, extra 4:5 for vertical edits |
| **Review** | rewatches the export: too many effects, sounds too loud or inaudible, black frames; fixes once, then reports |

## Cine montage
A second editor that applies the approved Editing DNA (`EDITING_DNA_PACKAGE/`, profile P_CINE_MONTAGE): a fast cold
open, one poster title, hard cuts with 1-frame white flashes and whips, a white card series, your Grid Flow once (not in cooking or clothing videos), and a
slow, scenic ending.
```
cd VIDEO_EDITING_SYSTEM
C:\Users\Timon\.aev\Scripts\python.exe -m engine plan "smoke" --title "SMOKE SESH"   # plan + storyboard + style checks
C:\Users\Timon\.aev\Scripts\python.exe -m engine approve "smoke" --by Timon --note "<your words>"
C:\Users\Timon\.aev\Scripts\python.exe -m engine render "smoke"                      # refuses without your approval
```
Claude shows you the storyboard first and only renders after your yes
(decision [0003](docs/decisions/0003-nothing-posts-without-approval.md)). Details:
`VIDEO_EDITING_SYSTEM/README_START_HERE.md`; why each choice is made: `EDITING_DNA_PACKAGE/EDITING_PSYCHOLOGY.md`.

## AI shots
Generated B-roll, an intro or a hero shot go straight into a project's clips; the editor uses them like any other clip
(graded with the film look only, since AI footage is already Rec.709).

**Local, free (default)**: Wan 2.2 5B in Comfy Desktop on the RX 9070 XT (AMD ROCm).
```
autoedit generate "drone shot over Utrecht at golden hour" --project smoke                       # local-wan, 1280x704
autoedit generate "..." --project smoke --model local-wan-draft                                 # 480p, quick prompt test
autoedit generate "..." --project smoke --image still.jpg                                       # image-to-video
```
- Speed: ~6.5 min per 5 s clip when first measured (2026-10-21; `local-wan-1080` ~26 min). The image-to-video runs of
  2026-10-26/27 took 32–46 min per clip, after the VAE decode tiles were made smaller to stop a crash. Plan for half an
  hour.
- If ComfyUI isn't running, AutoEdit starts it headless (watch at http://127.0.0.1:8188). Model files live in
  `C:\Users\Timon\AI Models`, hard-linked into Comfy-Desktop/ComfyUI-Shared/models.
- AI clips under 1080p get **Super Scale 2x Enhanced** in Resolve (`local_ai.super_scale` in config.yaml).
- Quality is below Kling/Veo and camera motion is subtle: fine for B-roll and atmosphere. Describe motion explicitly.

**Muapi, costs money per shot** (decision [0004](docs/decisions/0004-local-ai-first.md)):
```
autoedit ai-models                                                      # models + live prices (free)
autoedit generate "..." --project smoke --model kling --quote           # price only
autoedit generate "..." --project smoke --model kling                   # asks y/N first
autoedit ai-balance                                                     # your Muapi credit
```
Setup once: an account on muapi.ai → add credit → Dashboard → API Keys → `MUAPI_KEY=...` in `.env`. Every generation
shows the exact price first, never exceeds `ai_budget_usd` in project.yaml (default $5), and is logged in
`<project>/ai_spend.json`. Failed generations aren't charged. Prices (5 s, 1080p, 2026-10-21): seedance-fast $0.30 ·
kling $0.45 · pixverse/veo3-fast $0.60 · seedance $0.62 · veo3 $2.50. Prompts and uploaded images go to Muapi and the
model providers.

## Explainer videos
`autoedit explainer "<project>"` builds a step-by-step video from `<project>/script.yaml`: per section a b-roll clip +
an animated card (number + title, sub-lines pop in a beat later), an intro card, a full-frame end card, cuts on the
music's beats and a soft whoosh per section change. B-roll and music can be AI-generated (`aigen.generate_audio` for
Suno music). Example: project "M365 Onboarding".

## Posting
Everything waits in the queue until you approve it.
```
autoedit queue                     # waiting / scheduled / posted
autoedit approve <id>              # posts at its scheduled time
autoedit post <id>                 # post an approved video now
```
**Instagram** (Creator account): link the IG account to a Facebook page → app at developers.facebook.com with the
*Instagram Graph API* and `instagram_content_publish` + `instagram_manage_insights` → a long-lived token → copy
`.env.example` to `.env` and fill in `IG_USER_ID` and `IG_ACCESS_TOKEN`.

**TikTok** (posts as drafts): app at developers.tiktok.com → *Content Posting API*, scope `video.upload`, redirect URI
`http://127.0.0.1:8765/callback` → `TIKTOK_CLIENT_KEY` and `TIKTOK_CLIENT_SECRET` in `.env` → `autoedit tiktok-login`.
Videos land in your TikTok inbox; paste the caption (it's in the dashboard) and press post.

**On a schedule:** let Windows Task Scheduler run `autoedit.bat post-due` every 15 min and `autoedit.bat stats` weekly.

## Command reference
| command | what it does |
|---|---|
| `autoedit run <folder>` | analyse → edit in Resolve → render → queue. Options: `--category`, `--aspect 9:16\|16:9`, `--music <file\|name\|none>`, `--bass <dB>`, `--title`, `--label`, `--location`, `--variants AB`, `--stabilize auto\|all\|none`, `--seed`, `--style`, `--no-render` |
| `autoedit new <name>` | create a project folder with clips/, music/, exports/ and project.yaml |
| `autoedit import <name>` | copy new clips from the camera SD card (`--since YYYY-MM-DD`) |
| `autoedit project <name>` | edit a project by (partial) name; `--song`, `--title`, `--variants`, `--seed` |
| `autoedit projects` | list projects with clips, song and exports |
| `autoedit analyze <folder>` | quality / shake / speech per clip |
| `autoedit repurpose <video>` | one long video → several shorts (`--count 4`) |
| `autoedit watch` | drop-folder mode: builds when clips land in a subfolder (the subfolder name picks the category) |
| `autoedit dashboard` | the local dashboard (`--port 5055`) |
| `autoedit queue` / `approve <id>` / `post <id>` / `post-due` | the posting queue (see *Posting*) |
| `autoedit tiktok-login` | one-time TikTok authorisation |
| `autoedit stats` / `report` | pull Instagram stats, learn best times; what performs best |
| `autoedit ideas --style travel` | content calendar + shot lists from current trends (`--weeks 2`) |
| `autoedit save-style <source> <name>` | copy a preset under a new name → `data/user_styles.yaml` |
| `autoedit sfx` | show the SFX library per category |
| `autoedit generate "<prompt>" --project <name>` | AI shot (see *AI shots*): `--model`, `--seconds`, `--aspect`, `--role`, `--image`, `--quote`, `--yes` |
| `autoedit ai-models` / `ai-balance` | Muapi models and prices / your credit |
| `autoedit explainer <name>` | explainer video from `script.yaml` (`--no-render`) |
| `autoedit optimize` | smooth playback in Resolve: proxies, render cache, heavy nodes off (existing timelines too) |
| `engine validate` | DNA approved, Edge + FFmpeg present, documents up to date (run in `VIDEO_EDITING_SYSTEM/`) |
| `engine plan <project>` | cine montage plan + storyboard + style checks (`--title`, `--length`, `--accent`, `--song`, `--seed`) |
| `engine check` / `preview` / `approve` / `render` / `qa` | style checks again / half-size preview / record approval / final render / technical QA |

## Settings
| file | what |
|---|---|
| `config.yaml` | paths, grading, stabilization, format and lengths, loudness, branding (font Montserrat, Arial Bold fallback), posting times |
| `styles.yaml` | the house style `cinematic` + optional presets (pacing, effect chances, SFX per action, look, grid, overlay) |
| `inventory.yaml` | every technique the director may use: trigger, max, cooldown, sound, priority |
| `taste.yaml` | your feedback as rules + the knobs the director reads |
| `trends.yaml` | hooks, formats, keywords and hashtags per niche (see `TRENDS_REPORT.md`) |
| `project.yaml` (per project) | title, label, category, aspect, song, AI budget |
| Music | tracks in `paths.music_folder`, or `--music` |

## How it learns
- `inventory.yaml`: the toolbox. Every eye-candy (VFX) and ear-candy (SFX) technique learned from your reference edits,
  with *when* it's motivated, how often, and which sound belongs to it. References feed this list; they are never
  rebuilt 1:1 (decision [0002](docs/decisions/0002-references-feed-the-inventory.md)).
- `autoedit/director.py`: per video, places techniques only where the moment calls for it, within a budget, varied, and
  always with the matching sound. It prints *why* it chose every accent.
- `autoedit/review.py`: after every render the tool rewatches and relistens its own video and fixes what it can.
- `taste.yaml`: your feedback as rules ("no bouncy pop", "subtle", "bigger title"…). Grows every time.
- `CLAUDE.md`: tells Claude how to keep this loop going in every session.

## Your editor packs (FOUR Editors)
Extracted to `Documents\Editor Packs\` (1080p versions) and wired in:
- **Overlays + overlay transitions** are indexed by category (`autoedit/packs.py`, `paths.pack_folders`) and used by the
  director: light leaks / film burns on cuts, glitch transitions, doodles, ink splashes, viewfinder frames, subtle 16mm
  grain, and a film burn into the final hold. Blend: Screen (light on black); grain: Overlay at low opacity.
- Pack SFX (VHS, film, split frames) are in the sound library.
- In Resolve: the `.drfx` packs (effects, transitions, titles, lower thirds, callouts) in the Fusion Templates folder, the
  50 4E glitch presets as edit effects, and all LUTs (incl. The Everyday LUT) under `LUT\FOUR Editors\`. Restart
  Resolve once to see them.
- Not used automatically (yet): mask-type transitions (Punch Hole, Cinemarkers, CineSnip, Poster Wall) and Abstract
  Brush (contains the Four Editors logo).
- The packs are bought: they are not in this public repo; `setup/install.ps1` restores them from your backup by hash
  (decision [0007](docs/decisions/0007-public-repo-no-third-party-material.md)).

## Optional: the Odyssey PowerGrade instead of the LUT
The default grade is the baked LUT (`grading.mode: "lut"`). The Odyssey PowerGrade only does something after you set it
up by hand, because its CST node can't be set through the API:
1. Resolve → Color page → right-click in the Gallery → *Import* `OdysseyPowergrade.drx` → drag it onto a clip.
2. **Node 08 "CST"**: Input Color Space = *Sony S-Gamut3.Cine*, Input Gamma = *Sony S-Log3*.
3. Right-click the viewer → *Grab Still*, drag it into a **PowerGrades** album with a label containing **"Odyssey"**.
4. Set `grading.mode: "powergrade"` in `config.yaml` (`grading.gallery_label` picks the still).

## Known limits
- Resolve has to be open while building/rendering; never call `comp.Render()` (modal dialog).
- Fusion effects on the Edit page are built through export → import (Resolve ignores API-built comps when rendering);
  the code handles this.
- Smart Reframe is off by default (in tests it shifted the image the wrong way).
- TikTok API: unaudited apps can only upload as drafts; a caption can't be set through the API.
- `av`/faster-whisper is blocked by Windows Smart App Control on this PC
  (decision [0008](docs/decisions/0008-python-env-outside-documents.md)).
