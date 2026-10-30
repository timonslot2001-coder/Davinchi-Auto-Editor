# AutoEdit Studio (web app)

A website for everything the editors can do: projects, the cine montage (plan, shots with comments, approve, render,
QA), AutoEdit builds in Resolve, AI shots, the posting queue, music, insights and tools. Every button runs one of the
editor's own commands (`engine ...` or `autoedit ...`) as a job with a live log, so the website and the command line
always do the same thing.

## Start
| how | what runs where | open |
|---|---|---|
| `start-studio.bat` | everything on this PC | http://127.0.0.1:5060 |
| `start-studio-docker.bat` | the website in Docker Desktop, the work on Windows through the worker | http://localhost:5060 |

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
  music, output, `data/`, and project `clips` links). It writes only `project.yaml`, `comments.json` and uploaded songs.
- Every worker request needs `AEV_WORKER_TOKEN`. The worker makes it once and stores it in `.env` (never committed);
  `docker compose` reads it from there. The container gets only this token, no other secrets.
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
