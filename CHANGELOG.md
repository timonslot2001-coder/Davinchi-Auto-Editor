# Changelog

What changed, in words you would notice in an edit or on the PC. Newest first. Small fixes are folded into the day's
entry; the full list is in `git log`. Hard-to-reverse choices also get a record in [docs/decisions/](docs/decisions/README.md).

## 2026-11-13 — Your choices first: `autoedit edit`
- One command for your own edits: `autoedit edit "Beef Tartaar" --song escape --grade basis`. Rhythm (*beat* or
  *rustig*) and length (*kort* 10 s, *normaal* 20 s, *lang* 30 s) are your choice; the project remembers them.
- No song or no colour chosen? It stops and lists what you have. It never picks a random song any more.
- Your own PowerGrades are listed from `data/powergrades/` (applying them comes in the next step; until then the
  colour is the measured basis grade).

## 2026-11-12 — A firm base for the one-editor plan
- `--seed` now gives exactly the same edit again, sounds included (it used to reach only the effects).
- A clip that is left out as a double take is named in the log instead of disappearing silently.
- All tests run with one command: `python tools/run_tests.py` (`--quick` skips the 5-minute one).

## 2026-11-11 — JUICT videos in the reel style, a calmer Studio menu
- Every JUICT video the Studio makes now follows the build of the reel you liked, in JUICT colours: one big pink keyword
  per scene on dark blue, numbered steps, the explanation typing itself out in a card, a short conclusion in capitals,
  `juict.nl` as a watermark and the logo on the end card.
- The Studio menu lost *Foto's* and *PC op afstand*; *Instellingen* is a small gear under the PC status.

## 2026-11-09 — The Studio session runs by itself
- No more starting `start-studio-sessie.bat` by hand: run `powershell -ExecutionPolicy Bypass -File setup\autostart-studio.ps1`
  once and it starts when you log in to Windows (minimised). When the session stops it comes back by itself after 15 s;
  close its window to really stop it.
- It keeps itself up to date: it gets the newest code at every start and again before each Studio request, so after a
  merge you no longer pull or restart anything.

## 2026-11-09 — Make a JUICT video right in the Studio
- **Maak video** on a werkinstructie: one click and your PC reads the PDF and makes the explainer from its steps (one
  scene per step, the PDF's screenshots where it can, checked against the PDF before it is handed over). It shows up
  under Video's and next to the instruction. The Promptgenerator is still there for when you want to steer it first.
- Werkinstructies get a readable title from the file name (no "JUICT B.V." or export date), and uploading the same PDF
  twice no longer makes a copy.
- Under every prompt in the Promptgenerator there is now **Maak deze video**: give it a title (filled in from the
  prompt) and a series, and your PC makes the Motion film itself. It shows up under JUICT → Video's; no more copying
  the prompt into a separate Claude chat. *Kopiëren* still works. Needs the Studio session on the PC.
- The Studio menu has *Foto's* and *PC op afstand* again (they were missing from the published page).

## 2026-11-06 — Calmer cutting
- Shots run about **one bar** (~1.5 s) instead of one beat: Beef Tartaar on Escape Plan went from 33 cuts to 10 in
  16 s. Loud parts no longer cut faster, no quick 0.25 s cuts at the start, and a cut avoids the middle of a movement.
- **Brighter, less orange grade**: exposure and white balance are measured on the footage itself (per shoot and per
  clip), lamp light is pulled 60% towards neutral, and the film look is at half strength.
- A normal edit runs **~20 s** (was 13), and the final shot never holds longer than 3.5 s.
- Shots follow the **order you filmed** them, and the last shot comes from the end of the shoot.
- In 9:16 your landscape footage stays **whole** with black bars instead of being cropped to fill the screen.

## 2026-11-04 — LightCraft from any device
- LightCraft runs on your PC (your photos are on its SSD); on any other device you see and use it through **Chrome
  Remote Desktop** in the browser. *Openen in LightCraft* from your laptop or phone opens LightCraft on the PC and the
  remote-desktop tab at once; the Studio has *PC op afstand ↗* in its menu.

## 2026-11-04 — Foto's link works from your laptop too
- *Openen in LightCraft* keeps one LightCraft window: a second shoot is added to the open window instead of starting a
  second copy (which could not open the library). LightCraft opened another way gets a clear message.
- The website starts by itself when you log in to Windows (minimised, no browser tab), so the Studio's *Foto's ↗*
  link works after a restart too. `setup/autostart-website.ps1 -Remove` switches that off.
- Once Tailscale is set up, the Studio's *Foto's ↗* link uses the PC's Tailscale address everywhere (PC, laptop, phone);
  127.0.0.1 only ever reached the website on the PC itself.

## 2026-11-03 — Open a shoot in LightCraft
- On the website's *Foto's* page, **Openen in LightCraft** opens the shoot in LightCraft's own window on your PC. Sorting
  out look-alike and blurry photos, comparing, deleting, your own LUTs and every slider are done there; *Kies een look*
  stays as the one-tap shortcut (also on your phone).
- After an update the website always loads its newest pages (no old copy from the browser's cache).

## 2026-11-03 — Foto's link in the Studio
- The website moved from port 5060 to **5080**: Edge and Chrome refuse 5060 (`ERR_UNSAFE_PORT`, it is the internet-phone
  port). The website is now at http://127.0.0.1:5080 (phone: `http://100.x.y.z:5080`).
- `start-studio-sessie.bat` also starts the website (when it is not running yet), so the Studio's *Foto's ↗* link
  always has something to open.
- The Studio (claude.ai) has *Foto's ↗* in its menu: it opens the website's photo page on your PC (or on your phone via
  Tailscale). The website must be running (`autoedit.bat`). No tokens: the photos are not rebuilt inside the Studio.

## 2026-11-03 — Photos: pick a look (LightCraft)
- New page *Foto's* on the website: choose a shoot, tick photos, press *Kies een look*. You see your first photo finished
  in six looks (Automatisch, Zwart-wit… made by LightCraft, a free Lightroom-like editor on your PC). Tap one and every
  chosen photo is developed in that look, full size, into `2 Bewerkt/Foto` of its shoot. A photo with a RAW file is
  developed from the RAW. The originals stay as they are.
- Claude can drive LightCraft too (MCP server `lightcraft` in `.mcp.json`).

## 2026-11-03 — Titles are never squeezed
- The poster title scales evenly now instead of being squeezed sideways to fit. A title of several words goes onto
  two lines when that makes the letters clearly bigger (VAKANTIE / MADEIRA); lines and letters never touch.

## 2026-11-03 — S-Log3 clips picked from the SSD get their grade again
- Clips chosen on the SSD page came without the camera's XML, so the editor had to guess S-Log3 from the picture and
  guessed wrong for bright shots (washed-out, grey video). The XML now comes along when you pick clips (also when you
  pick a clip again for an older edit). Vakantie Madeira is repaired: 8 S-Log3 clips, 1 Rec.709.

## 2026-11-03 — Type what you want (local model, free)
- Under the feedback buttons on the website: type what you want ("korter", "ander nummer", "moody look", "haal C0146
  eruit", "plan met het austria nummer en titel MADEIRA"). A model running on your own PC (LM Studio, gpt-oss-20b)
  picks the right button in about 2 s and the website runs it. Costs no tokens. "Render hem" is not something it
  does: that stays your *Ja, renderen* press.

## 2026-11-03 — Picking a song works
- Choosing a song on the website stopped the plan with "matches no song" (the full file name with `.mp3` was not
  recognised). Fixed, in the cine montage and in AutoEdit.
- Picking a song now starts the new proposal right away; no extra click on *Nieuw voorstel*.

## 2026-11-02 — Pick a look from finished pictures
- No more sliders or half previews for the grade. The Studio's *Grade* step and the website's *Andere look* show six
  finished pictures, one per look: four shots from your project, graded exactly like the render. Tap the one you like
  and that is your grade (then approve again).
- *Voorbeelden maken* in the Studio now uploads six pictures in one go instead of stills plus six LUT files, which
  costs fewer tokens.

## 2026-11-02 — The editor starts the work
- **Card in = proposal ready.** While the website runs, putting a camera card in starts *Kaart gevonden*: everything new
  goes to `_Inbox` (checked, card untouched), and every new day with video gets an edit `<date> voorstel` with all its
  clips and a plan. Open it on the website and press *Ja, renderen*. Switch off with `card_auto: false` in config.yaml.
- **Feedback buttons** under the 4 steps: *Korter*, *Langer*, *Ander nummer*, *Ander voorstel*, and *eruit* on every
  shot. Each makes a new proposal right away (an *eruit* clip stays out via `skip:` in project.yaml) and is logged in
  `cine_montage/feedback.json`, so Claude can turn repeated feedback into style rules.
- **Plannen:** after the render, *Plannen* puts it in the posting queue with a caption and the next good time, shows
  them, and one more tap schedules it.
- The sidebar shows whether the SSD is connected, next to Resolve and ComfyUI.
- Changing the song (step 2 or *Ander nummer*) forgets the old song's start point.
- Automatic shot tags for snelle edits exist but are off: with the face model (`data/models/`) only 4 of 12 Smoke Sesh
  clips matched the hand tags, which is worse than no tag. Turn on with `auto_tags: true` in config.yaml.

## 2026-11-02 — The editor picks the song part; one kind of edit per project
- No `song_start` set? The cine montage now picks the best part of the song itself: the strongest build-up with the
  drop about two thirds into the video (ESCAPE PLAN: 49.9 s, close to the TikTok sound's 48.1 s). The plan notes say
  where it starts; `song_start:` in project.yaml still wins.
- *Nieuw project* asks once what kind of edit it is: **Cine montage** or **Snelle edit** (AutoEdit in Resolve). The
  project opens on that and the home page shows the matching next step. Client films (JUICT) and explainers/intros
  show *via Claude* instead of the 4 steps (`editor:` in project.yaml; recognised automatically).

## 2026-11-02 — A video in 4 steps
- A project's *Cine montage* tab starts with one path: **Clips → Muziek → Bekijken → Ja, renderen**. Pick the song
  from a list, press *Maak voorstel*, look at the storyboard, press *Ja, renderen*. That button is your approval of
  that plan; no sentence to type any more.
- No grade step: every video gets your house look. *Zelf bijsturen* (folded away) still has the plan options, another
  look, the half-size preview and QA.
- The home page shows the next step for every project (*Clips kiezen*, *Voorstel maken*, *Bekijken → Ja, renderen*,
  *Klaar*).

## 2026-11-02 — One app
- Double-click `autoedit.bat` and the website opens: that is now the one app (the old dashboard and
  the separate website start file are no longer the way in). It costs no tokens.
- On your phone: install Tailscale on the PC and the phone, and `autoedit.bat` shows the phone address. Only your own
  devices get in.
- New things are built in the website only. The Studio in the Claude app keeps working as it is, but gets no new
  buttons (every click there costs tokens). Plan and baseline: `docs/simpler-plan.md`.

## 2026-11-02 — Pick clips and start an edit (page SSD)
- The SSD page (website and Studio) no longer moves folders; you sort those in Windows Explorer. Instead you tick
  clips, from one or more folders, give the edit a name (or pick an existing project) and press *Start edit*. The
  project opens straight away, ready for plan, grade and render.
- Nothing is copied: the clips get a hard link in `I:\_Edits\<name>` (no extra space) and the originals stay where
  they are. Also from a terminal: `autoedit pick`.

## 2026-11-02 — Studio shows only your own projects
- The sample projects are gone from the Studio (no *Bekijk met voorbeelddata*, no demo bar). With no projects yet,
  Projecten tells you to start `start-studio-sessie.bat` on the PC; your projects appear once that runs.

## 2026-11-01 — Sort the SSD on the website
- New page **SSD** in the AutoEdit website: the shoot folders with video (_Inbox first) with a thumbnail of every clip.
  Folders with only photos are left out; photos get their own editor later.
  Click a clip to watch it; tick folders, type a name, pick the kind and press *Verplaatsen*. They become one shoot
  (`Reizen\2026-10-09 Ibiza`) with its AutoEdit project. Also from a terminal: `autoedit sort`.
- The same **SSD** page is in the AutoEdit Studio in the Claude app (phone, laptop): *Beelden laden* shows an overview
  of every clip, *Preview maken* a short clip, and *Verplaatsen* names and moves the folders. It needs the
  Studio session running on the PC.
- The SSD page opens faster: thumbnails are made ahead of time (after an offload or a move, or with `autoedit thumbs`),
  and the Studio's *Beelden laden* makes them in parallel.

## 2026-11-01 — Pace from the music (test)
- Cine montage: `engine plan --pacing music` lets the song set the pace instead of a fixed curve: cuts on the beat you
  feel, long flowing shots in a breakdown, a cut and a white-card burst exactly on the drop. `--song-start` starts the
  song where you want (e.g. where the TikTok sound starts). Default pacing is unchanged.

## 2026-11-01 — Offload with a double-click
- `offload.bat`: double-click, type the shoot name, pick the kind (1–6), and the card goes to the SSD. The same
  thing as the *SD-kaart offloaden* button on the website.
- *Weet ik nog niet* (`_Inbox`) now makes one folder per recording day (`2026-10-09 SD-kaart`), so a card with
  months of shoots on it arrives sorted by day.

## 2026-11-01 — AutoEdit Studio in the Claude app
- The Studio is a working page in the Claude app (phone, laptop): pick a grade with an instant preview, make a plan,
  watch the preview and storyboard, approve in your own words, render, and see the result. Six looks, shown by their
  LUT names: `reference_film`, `clean_warm`, `moody` and the new `daylight`, `blue_hour` and `vintage`.
- Each project shows its steps (Grade → Plan → Goedkeuren → Renderen → Resultaat) with what to do next.
- The buttons work while `start-studio-sessie.bat` runs on the PC; without it the page says so and only the grade
  preview works. A grade change after approval needs a new approval.
- New look: a dark grading-suite screen with glowing accents, viewfinder corners on the grade preview and a read-out
  of look, strength, exposure and LUT. Colours: ice blue and silver (IJs).
- *Te doen* on Projecten lists what waits on you per project. On a computer the sidebar shows every project with its
  next step and the latest jobs on the PC. Plan shows shots, length and seconds per shot; Renderen shows a checklist of
  what must be approved first; Taken is a compact log you can open per job.
- *Bekijk met voorbeelddata* fills the Studio with sample projects so you can try every step without the PC; nothing
  is sent or saved.
- The Studio's preview and render videos are a small 720p copy (max 20 MB) made on the PC; a new plan clears the old
  render from the page.
- Long jobs (plan, preview, render) keep running on the PC even if the Studio session's command stops; the PC runs
  one Studio job at a time. A job still *bezig* after 3 hours shows as *vastgelopen? start opnieuw*, and *Renderen* is
  greyed out while a render of that project runs.
- The storyboard and preview say which look they were made with, and warn when the grade changed since. The Grade step
  counts as done only after you picked a grade. Preview uses the plan's grade mode, like render.
- When the page loses its connection it says *Verbinding kwijt* and reconnects once by itself.
- The Studio lives at https://claude.ai/artifact/4YCCLgHK4KozydqGCpjLQR (account timon@juict.nl, the account the
  Claude app on the PC uses); `start-studio-sessie.bat` points there. Every project with a cine montage shows up,
  client projects included.
- *Start edit* (and *Verplaatsen*) on the SSD page wait for nothing: while a plan, preview or render runs on the PC
  they are refused with a short message, so a project's clips never change under a running job. Try again when the
  job is done.

## 2026-10-31 — Offload to your SSD
- New `autoedit offload "<shoot>" --soort koken` (and *SD-kaart offloaden* on the website): copies photos and videos
  from the Sony and DJI card to Timon's SSD in one folder per shoot, `<Soort>\<date> <shoot>\1 Ruw | 2 Bewerkt |
  3 Klaar om te posten`. Every file is checked, the card is never touched, and the project reads its clips from there.
- The SSD is sorted that way now: Koken, Kleding, Smoken, Reizen, Klanten and `_Inbox` (Kas is waiting there to be
  sorted). Beef Tartaar and Mongolie 2025 point to their new folders.

## 2026-10-30 — AutoEdit Studio (website, Docker)
- New website for all functions: projects, cine montage (plan, numbered shots with comment boxes, approve, render,
  QA), AutoEdit builds in Resolve, AI shots (price first for paid models), posting queue, music, insights and tools,
  with a live log per job. Works on a phone too. `autoedit.bat` runs it on this PC; `start-studio-docker.bat` runs
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
