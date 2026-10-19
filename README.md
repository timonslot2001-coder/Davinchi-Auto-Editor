# AutoEdit: DaVinci Resolve auto editor for TikTok + Instagram

Drop clips in, and out comes a finished 9:16 edit with your PowerGrade, effects, SFX, music, hook text and captions, plus a 4:5 version, a cover and caption suggestions. Nothing goes online without your OK.

## Getting started
1. Open **DaVinci Resolve Studio** (Preferences → System → General → *External scripting using: Local*, which is already set).
2. Double-click **`autoedit.bat`** to open the dashboard in your browser.
   - Or in a terminal: `autoedit run "C:\Users\Timon\Videos\Shoot" --style fitness --variants AB`

## ⚠️ Do this once: set your PowerGrade to S-Log3
The CST node in the Odyssey PowerGrade can't be set through the API. Without this step, the grade looks flat and grey.
1. Open any clip in Resolve → Color page → right-click in the Gallery → *Import* `OdysseyPowergrade.drx` → drag it onto the clip.
2. **Node 08 "CST"**: Input Color Space = *Sony S-Gamut3.Cine*, Input Gamma = *Sony S-Log3*. Leave Output as the PowerGrade has it.
3. Right-click the viewer → *Grab Still*, then drag that still into a **PowerGrades** album and give it a label containing **"Odyssey"**.
4. Done. AutoEdit picks this version from the Gallery automatically (`grading.gallery_label` in `config.yaml`).

## What it does

| Step | What happens |
|---|---|
| **Analysis** | Per clip: sharpness, shake, exposure, motion, speech, scene cuts, best moments. It skips blurry, dark and duplicate takes |
| **Planner** | Hook (strongest shot first), pacing curve (fast → calm → strong outro), beat sync, variety guard, silence cutter, retention interrupts every 2–3 s, loop ending |
| **Resolve** | Its own `AutoEdit` project. Each build is a **new timeline** (versions, originals never touched) |
| **Grade** | Your PowerGrade on every clip, with the right look per style (the LUT goes on all 7 look nodes → 100% look) |
| **Effects** | Punch zoom, smooth zoom, shake, invert/outvert flash, white flash, whip, glitch, speed ramps on motion peaks |
| **6-panel grid** | 6 clips pop in one after another, each with a sound, placed on the drop of the music |
| **SFX** | Generated set (whoosh, hit, impact, pop, click, shutter, riser, swell, glitch) + your own sounds, sorted by name |
| **Stabilization** | `auto` (only shaky clips), `all`, `none`, or per clip with checkboxes in the dashboard |
| **Audio** | Music bed cut to the drop, faded, ducked under speech; voice isolation; −14 LUFS |
| **Text & captions** | Hook text within the TikTok/Reels safe zones; auto captions (Resolve AI) on speech |
| **Export** | 9:16 + 4:5, automatic cover, QC (black frames, clipping, resolution) |
| **Posting** | 3 caption options + hashtags per platform → you approve → Instagram posts at the best time, TikTok lands in your drafts |
| **Growth** | `autoedit stats` pulls Instagram stats, learns your best times and hashtags. `autoedit ideas` makes a content calendar with shot lists |

## Commands
```
autoedit run <folder> --style fitness|travel|lifestyle|fashion --variants AB --music song.mp3 --stabilize auto|all|none
autoedit analyze <folder>          # quality/shake per clip
autoedit repurpose long.mp4 --count 4
autoedit watch                     # drop-folder mode (subfolder name picks the style)
autoedit dashboard
autoedit queue | approve <id> | post <id> | post-due
autoedit stats | report | ideas --style travel
autoedit save-style fitness my-gym  # own preset → data/user_styles.yaml
```

## Customizing
- `config.yaml`: paths, PowerGrade, stabilization, lengths, loudness, branding, posting times
- `styles.yaml`: the presets (pacing, effect probabilities, SFX per action, look, grid, overlay)
- `trends.yaml`: hooks, formats, keywords and hashtags per niche (see `TRENDS_REPORT.md`)
- Music: put tracks in `paths.music_folder`, or pass `--music`
- Font: install **Montserrat** (Google Fonts) for the hook text; Arial Bold is the fallback

## Setting up posting (one time)
**Instagram** (Creator account ✓):
1. Link your IG account to a Facebook page.
2. Create an app at developers.facebook.com → *Instagram Graph API*, with permissions `instagram_content_publish` and `instagram_manage_insights`.
3. Generate a long-lived token. Copy `.env.example` → `.env` and fill in `IG_USER_ID` and `IG_ACCESS_TOKEN`.

**TikTok** (posts as drafts):
1. Create an app at developers.tiktok.com → *Content Posting API*, scope `video.upload`, redirect URI `http://127.0.0.1:8765/callback`.
2. Put `TIKTOK_CLIENT_KEY` and `TIKTOK_CLIENT_SECRET` in `.env` → run `autoedit tiktok-login`.
3. Videos land in your TikTok inbox; you paste the caption (it's in the dashboard) and press post.

**Automatic posting at the best time:** let Windows Task Scheduler run `autoedit.bat post-due` every 15 min.
**Weekly trend tracker / stats:** schedule `autoedit.bat stats` weekly.

## Known limits
- Resolve has to be open while building/rendering.
- Edit-page Fusion effects are built through export → import (Resolve ignores API-built comps when rendering), which is solved inside the code.
- Smart Reframe is off by default (in tests it shifted the image the wrong way).
- TikTok API: unaudited apps can only upload as drafts; a caption can't be set through the API.

## How it learns (inventory · director · self-review · taste)
- `inventory.yaml` — the toolbox: every eye-candy (VFX) and ear-candy (SFX) technique learned from your
  reference edits, with *when* it's motivated, how often, and which sound belongs to it.
- `autoedit/director.py` — per video, places techniques only where the moment calls for it (music hit,
  motion, scene change, quiet part), within a budget, varied, and always with the matching sound.
  It prints *why* it chose every accent.
- `autoedit/review.py` — after every render the tool rewatches/relistens its own video: too many effects?
  SFX jumping out or inaudible? black frames? It fixes what it can (one rebuild) and writes
  `<name>_review.json` + `<name>_review.png` (a frame of every accent).
- `taste.yaml` — your feedback as rules ("no bouncy pop", "subtle", "bigger title"…). Grows every time.
- `CLAUDE.md` — tells Claude how to keep this loop going in every session.

## Projects (one folder per shoot)
```
autoedit new "Smoke Sesh"          # makes Videos\AutoEdit Projects\Smoke Sesh\ with clips\ music\ exports\ project.yaml
autoedit import "smoke"            # copies new clips from the A6700 SD card (PRIVATE\M4ROOT\CLIP) into clips\
autoedit project "smoke"           # edits it: song from music\ (or project.yaml), title/label from project.yaml
autoedit projects                  # overview of all projects
```
Or just tell Claude: *"start project smoke"*.

## Your editor packs (FOUR Editors)
Extracted to `Documents\Editor Packs\` (1080p versions) and wired in:
- **Overlays + overlay transitions** are indexed by category (`autoedit/packs.py`, `paths.pack_folders`) and used
  by the director as skills: real light leaks / film burns on cuts, glitch transitions, doodles, ink splashes,
  viewfinder frames, subtle 16mm grain, and a real film burn into the final hold. Blend: Screen (light on black),
  grain: Overlay at low opacity.
- Pack SFX (VHS, film, split frames) are added to the sound library.
- Installed in Resolve: the `.drfx` packs (effects, transitions, titles, lower thirds, callouts) in the Fusion
  Templates folder, the 50 4E glitch presets as edit effects, and all LUTs (incl. The Everyday LUT) under
  `LUT\FOUR Editors\`. Restart Resolve once to see them in the Effects library.
- Not used automatically (yet): mask-type transitions (Punch Hole, Cinemarkers, CineSnip, Poster Wall) and
  Abstract Brush (contains the Four Editors logo).
