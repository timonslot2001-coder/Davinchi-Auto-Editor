# AutoEdit Studio (web app)

A website for everything the editors can do: projects, the cine montage (plan, shots with comments, approve, render,
QA), AutoEdit builds in Resolve, AI shots, the posting queue, music, insights and tools. Every button runs one of the
editor's own commands (`engine ...` or `autoedit ...`) as a job with a live log, so the website and the command line
always do the same thing.

## Start
| how | what runs where | open |
|---|---|---|
| `start-studio.bat` | everything on this PC | http://127.0.0.1:5060 |
| `start-studio-docker.bat` | the website in Docker Desktop on the Resolve PC, the work through the worker | http://localhost:5060 |
| `start-worker-for-laptop.bat` + `docker compose up -d --build` | the website in Docker on your laptop, the work on the Resolve PC | http://localhost:5060 on the laptop |

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
   Open http://localhost:5060. The sidebar shows "Docker → Windows-worker" in green when it reaches the PC.

Both computers must be on the same network. If the laptop can not reach the worker: check that the PC window is
still open, that the address is the PC's 192.168.x.x address, and that the firewall allows Python on private networks.

Why the work stays on Windows: DaVinci Resolve (driven through its scripting API), the GPU for local AI (ComfyUI), the
footage on I: and Edge for the title graphics are all on the Windows host. A Linux container can not drive Resolve.
The container holds the website, its logic and the job queue; the worker (`python -m webapp worker`, port 5061) runs
the commands and serves the files.

## Approval gates (unchanged)
- **Cine montage:** *Renderen* only works after *Goedkeuren* with your own words, on the current plan (gate B). A new
  plan needs a new approval.
- **Paid AI shots:** first *Prijs vragen*, then a confirmation with the price. Local models (your GPU) are free. The AI
  budget in project.yaml can only go down from the website; raising it is done by hand.
- **Posting:** nothing goes online unless you press *Goedkeuren* (posts at the planned time) or *Nu posten*.

## Safety
- The worker only runs the commands in `host.ALLOWED` and only serves files inside the AutoEdit folders (projects,
  music, output, `data/`, and project `clips` links). It writes only `<project>/project.yaml`, `<project>/cine_montage/comments.json` and uploaded songs.
- Every worker request needs `AEV_WORKER_TOKEN`. The worker makes it once and stores it in `.env` (never committed);
  `docker compose` reads it from there. The container gets only this token, no other secrets.
- `start-worker-for-laptop.bat` opens the worker to your home network (needed for the laptop); every request still
  needs the token. Close its window when you are done. The normal worker listens on 127.0.0.1 only.
- The website listens on 127.0.0.1 only. To use it on your phone in the same wifi: start it with `--bind 0.0.0.0`
  (or set the compose port to `"5060:5060"`). There is no login, so only do that on your home network.

## Shot comments
On the cine montage tab every shot has a number and a comment box. *Opmerkingen opslaan* writes
`<project>/cine_montage/comments.json` (`{"12": "eruit", ...}`); tell Claude to "verwerk de opmerkingen".

## Files
| file | what |
|---|---|
| `app.py` | website + JSON API; turns form fields into commands (validated, never raw text) |
| `host.py` | `LocalHost` (run jobs, read files on this PC) and `RemoteHost` (the same through the worker) |
| `worker.py` | the Windows worker for Docker (token, allowlist) |
| `query.py` | what the pages show: projects, cine montage state, queue, music, status |
| `static/` | the interface (HTML, CSS, JS; no build step) |
| `../Dockerfile`, `../docker-compose.yml` | the container image (only `webapp/` goes in) |
