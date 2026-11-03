# AutoEdit Studio (web app)

A website for everything the editors can do: projects, the cine montage (plan, shots with comments, approve, render,
QA), AutoEdit builds in Resolve, AI shots, the posting queue, music, insights and tools. Every button runs one of the
editor's own commands (`engine ...` or `autoedit ...`) as a job with a live log, so the website and the command line
always do the same thing.

## Start
| how | what runs where | open |
|---|---|---|
| `autoedit.bat` (double-click) | everything on this PC; on your phone too when Tailscale is on (`--phone`, only your devices) | http://127.0.0.1:5080 |
| `start-studio-docker.bat` | the website in Docker Desktop on the Resolve PC, the work through the worker | http://localhost:5080 |
| `start-worker-for-laptop.bat` + `docker compose up -d --build` | the website in Docker on your laptop, the work on the Resolve PC | http://localhost:5080 on the laptop |

### Docker on another computer (laptop)
The website runs in Docker on the laptop; the editing still happens on the PC with Resolve and the footage.
1. **On the Resolve PC:** double-click `start-worker-for-laptop.bat`. It shows two lines (`AEV_WORKER_URL=...` and
   `AEV_WORKER_TOKEN=...`) and starts the worker. If Windows asks about the firewall, allow Python on *private*
   networks only. Keep the window open.
2. **On the laptop:** clone the repo, copy `.env.example` to `.env` and paste those two lines in (only the
   `AEV_WORKER_*` and `STUDIO_BIND` lines matter there).
3. **On the laptop**, in the repo folder:
   ```
   docker compose up -d --build
   ```
   Open http://localhost:5080. The sidebar shows "Docker → Windows-worker" in green when it reaches the PC.

Both computers must be on the same network. If the laptop can not reach the worker: check that the PC window is
still open, that the address is the PC's 192.168.x.x address, and that the firewall allows Python on private networks.

Why the work stays on Windows: DaVinci Resolve (driven through its scripting API), the GPU for local AI (ComfyUI), the
footage on I: and Edge for the title graphics are all on the Windows host. A Linux container can not drive Resolve.
The container holds the website, its logic and the job queue; the worker (`python -m webapp worker`, port 5061) runs
the commands and serves the files.

## Studio in the Claude app
The page `artifact/studio.html` is published as the claude.ai Artifact **AutoEdit Studio** (its link is `STUDIO_URL`
in `start-studio-sessie.bat`). The Studio artifact and the PC's Claude account must match (same account, or shared
with it with edit rights), otherwise the PC session cannot watch it or write its data. It works from your phone or laptop for the cine montage: grade (instant preview in the
browser), plan + storyboard, preview video, approve, render, QA, result.
- **On the PC:** double-click `start-studio-sessie.bat` and leave the window open. That opens the one Claude Code
  session that runs the buttons (skill `studio-session`). Only that session may watch the Studio; otherwise one click
  runs twice.
- **Each button** sends one `[studio] actie=...` comment; the session checks it with `python -m webapp studio`, which
  starts one `engine` command in a background worker on the PC (one job at a time; it keeps running if the session's
  call ends) and answers at once. The session fetches the result with `python -m webapp studio-result --thread <id>`
  and writes it back into the page. Approving needs your own words; a grade change needs a new approval. A job still
  *bezig* after 3 hours shows as *vastgelopen? start opnieuw*.
- **New version of the page:** publish `artifact/studio.html` again to the same link (Claude: Artifact publish with the
  same file), then stop watching it in that session.
- **PC off:** the page shows *Studio-sessie op je PC is niet bereikbaar*; the grade preview still works.
- **SSD** (also in the Studio): the shoot folders with video on the SSD. *Beelden laden* uploads a contact sheet of the clips, *Preview maken* a 20 s clip of 640 px, and *Start edit* runs `autoedit pick` on the ticked clips (`actie=ssd-...`, see the skill).
Decision: [0013](../docs/decisions/0013-studio-artifact-comment-route.md).

## Approval gates (unchanged)
- **Cine montage:** *Renderen* only works after *Goedkeuren* with your own words, on the current plan (gate B). A new
  plan needs a new approval. *Look opslaan* (look, strength, exposure) runs `engine grade` and writes `cine_montage/grade.json`,
  the one grade source; render takes no `--look`, and *Voorbeeld* may try a look without saving it.
- **Paid AI shots:** first *Prijs vragen*, then a confirmation with the price. Local models (your GPU) are free. The AI
  budget in project.yaml can only go down from the website; raising it is done by hand.
- **Posting:** nothing goes online unless you press *Goedkeuren* (posts at the planned time) or *Nu posten*.

## Safety
- The worker only runs the commands in `host.ALLOWED` and only serves files inside the AutoEdit folders (projects,
  music, output, `data/`, the SSD library and project `clips` links). It writes only `<project>/project.yaml`, `<project>/cine_montage/comments.json` and uploaded songs.
- Every worker request needs `AEV_WORKER_TOKEN`. The worker makes it once and stores it in `.env` (never committed);
  `docker compose` reads it from there. The container gets only this token, no other secrets.
- `start-worker-for-laptop.bat` opens the worker to your home network (needed for the laptop); every request still
  needs the token. Close its window when you are done. The normal worker listens on 127.0.0.1 only.
- The website listens on 127.0.0.1 only. To use it on your phone in the same wifi: start it with `--bind 0.0.0.0`
  (or set the compose port to `"5080:5080"`). There is no login, so only do that on your home network.

## Offload
*SD-kaart offloaden* on the Projecten page runs `autoedit offload "<name>" --soort <soort>`: photos and videos from
the camera card go to the SSD (`<Soort>\<date> <name>\1 Ruw`), checked, card untouched. The card and the SSD must be
in the Resolve PC, because the worker does the copying. See the main [README](../README.md#offload-a-card-to-your-ssd).

## SSD
The *SSD* page lists every shoot folder with video on the SSD (`_Inbox` first; photo-only folders are left out),
shows a thumbnail per clip and plays a clip (the original where the browser plays HEVC, else a 20 s H.264 preview made on demand). Tick clips
(from one or more folders), give a name or pick a project, and *Start edit* runs `autoedit pick "<name>" <clips>`: hard
links in `<SSD>\_Edits\<name>` (no copy) and the project reads its clips from there; the page then opens the project.
Sorting folders is done in Windows Explorer (`autoedit sort` still exists). Thumbnails and previews are cached in
`data/library_thumbs/`.

## A video in 4 steps
A project's *Cine montage* tab starts with the path Clips → Muziek → Bekijken → **Ja, renderen**. The song list is
your music folder (saved as `song:` in `project.yaml`); *Maak voorstel* runs `engine plan` with the title and song;
*Ja, renderen* runs `engine approve --note "Ja, renderen (knop in de website)"` and then `engine render` (decision
[0015](../docs/decisions/0015-render-button-is-the-approval.md)). Plan options, another look, preview and QA are under
*Zelf bijsturen*. The home page shows each project's next step. *Andere look* there shows one finished picture per look
(`GET /api/projects/<name>/looks`, made by `studio_assets.previews` and kept until the plan changes); a tap saves it
as the grade.

Each project has one kind of edit (`editor:` in `project.yaml`, chosen in *Nieuw project*): `cine` (the 4 steps),
`snel` (AutoEdit in Resolve), `klant` or `anders` (client film, explainer, intro: made via Claude). Without the line
the website recognises it: `edit_v*.py` in the folder or clips under *Klanten* on the SSD = `klant`, a `script.yaml`
= `anders`, else `cine`.

## The editor starts the work
- **Camera card:** while the website runs on the Resolve PC, `cardwatch.py` looks for a card every 10 s; a new card
  starts one job `autoedit card` (offload to `_Inbox`, then per new day an edit `<date> voorstel` with a plan). An
  existing proposal is never overwritten. Off: `card_auto: false` in config.yaml.
- **Feedback:** *Korter* / *Langer* (±3 s), *Ander nummer* (next song in the music folder, old start dropped),
  *Ander voorstel* (new seed), *eruit* per shot (`skip:` in project.yaml). Each runs `engine plan` again and is logged
  in `cine_montage/feedback.json`.
- **Foto's (LightCraft):** the *Foto's* page lists shoots with photos (`GET /api/photos/shoot`, thumbnails via
  `/api/photos/thumb`, RAW without a JPG twin developed small by LightCraft). *Kies een look* shows the first chosen
  photo in six looks (`GET /api/photos/looks`, `autoedit/photos.py`, cached in `data/photo_looks`); a tap runs
  `autoedit photos <look> <photos…>`: LightCraft auto settings + the look's preset, full size, into
  `<shoot>/2 Bewerkt/Foto/<name>_<look>.jpg`, from the RAW when there is one. `lightcraft:` in config.yaml points at
  `lightcraft-cli.exe` (default: the portable copy in `~/.autoedit/lightcraft`).
- **Typ wat je wilt:** the box under the feedback buttons sends the sentence to `POST /api/projects/<name>/ask`.
  `assistant.py` asks a local model in LM Studio on this PC (free, no tokens; default `openai/gpt-oss-20b`, loaded on
  the first question and unloaded after 10 min idle) to pick one of the same buttons: new plan (song, title, length),
  feedback, *eruit* for a clip, or a look. Every value is checked against what exists; the page then runs the usual
  job. Rendering is not one of its buttons. Settings: `local_llm:` {model, url, lms, ttl_s} in config.yaml.
- **Plannen:** `autoedit schedule <project>` queues the newest render with caption and time; the dialog shows them and
  *Plannen* approves the queue entry (it posts at that time, decision 0003).

## Shot comments
On the cine montage tab every shot has a number and a comment box. *Opmerkingen opslaan* writes
`<project>/cine_montage/comments.json` (`{"12": "eruit", ...}`); tell Claude to "verwerk de opmerkingen".

## Files
| file | what |
|---|---|
| `app.py` | website + JSON API; turns form fields into commands (validated, never raw text) |
| `host.py` | `LocalHost` (run jobs, read files on this PC) and `RemoteHost` (the same through the worker) |
| `validate.py` | the form-field checks and the render `--grade` rule, shared by `app.py` and `studio.py` |
| `studio.py` | requests from the claude.ai Artifact: `python -m webapp studio --thread <id> --text-file data/studio_inbox/<id>.txt` checks the fixed `[studio] actie=...` text (from a file, never on the command line) and starts one `engine` command in a detached worker (`studio-worker`, lock `data/studio.lock`), which makes the 720p video copy for the page and writes `data/studio_results/<id>.json`; `python -m webapp studio-result --thread <id>` prints that result; `python -m webapp studio-state "<name>"` prints the project's state for the Artifact; `python -m webapp studio-projects` prints every cine montage project with its state; `python -m webapp studio-ssd` lists the SSD shoot folders; `python -m webapp studio-pc` prints `studio/pc` (host + the website's addresses for the Studio's *Foto's ↗* link) |
| `worker.py` | the Windows worker for Docker (token, allowlist) |
| `query.py` | what the pages show: projects, cine montage state, queue, music, status |
| `static/` | the interface (HTML, CSS, JS; no build step) |
| `../Dockerfile`, `../docker-compose.yml` | the container image (only `webapp/` goes in) |
