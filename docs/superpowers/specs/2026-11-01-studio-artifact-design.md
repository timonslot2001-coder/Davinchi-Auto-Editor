# AutoEdit Studio as a working Artifact: design

Date: 2026-11-01 · Status: built (Studio session: skill `studio-session`, decision 0013)

## Why
Timon wants to drive his editor from the Claude app (phone, laptop), not from `http://127.0.0.1:5060`. That link only
works on the Resolve PC itself, so from the couch or the laptop "the local link doesn't work". The published Artifact
**AutoEdit Studio** (its live link is the `STUDIO_URL` setting in `start-studio-sessie.bat`; that file is the one place
that holds it) was a demo on sample data. This design
makes it a real remote control for the editor on his PC, starting with the grade, the cine plan, approval and render.

The work itself must stay on the Windows PC (PC-TIMON): DaVinci Resolve, the GPU, footage on the SSD (I:), the venv and
the editor commands all live there. The Artifact only sends requests and shows results.

## What was proven (spike, 2026-11-01)
A throwaway page (`Studio Koppeltest`, https://claude.ai/artifact/NP3749UxfT6drF8y97Cv4D) tested two routes.

- **Works: comment route.** The page calls the `comments` capability's `sendToClaude({anchor, text})` from a button.
  Every Claude session that watches the artifact (`ArtifactComments` action `watch`), and the session that
  published it, receives it as a turn: "the user (owner), posted by the artifact, sent to you". A Claude Code session
  on PC-TIMON (Remote Control) watched the artifact, ran `hostname` and replied in the thread
  "Aangekomen op de PC: PC-TIMON". Replies and status can be written back with `ArtifactData` (the page's `db`).
- **Does not work: connector route.** Calling the `Claude Code Remote` connector (`send_message`) from the page fails:
  claude.ai shows "Couldn't load this connector" and calls reject `upstream_error: connector access isn't confirmed`.
  Not used.
- **Found: several sessions answer one click.** The PC session and a cloud session (the publisher) both replied to
  the same comment. The real Studio must have exactly one session that executes.
- Cloud sessions cannot message sessions on the PC (`elevated_session_untrusted_device`). Not needed by this design.

## Goals
1. From the Claude app, Timon can: open a project, pick a grade with an instant preview, make a cine plan, read the
   plan and storyboard, approve it in his own words, start a render, and see when it is done (or why it failed).
2. **Grade picking feels smooth.** Tapping a grade changes the preview at once (no round trip to the PC). Sliders for
   strength and exposure update live. Before/after by swiping over the image. Only **Kies deze grade** goes to the PC.
3. A grade library of six looks, each one LUT on top of the fixed Sony S-Log3 → Rec.709 conversion at −1.75 stops:
   - existing: `reference_film` (house style), `clean_warm`, `moody`
   - new, made by us: `daylight` (bright, warm skin, fresh sky), `blue_hour` (cool, soft shadows),
     `vintage` (soft contrast, a little grain feel)
   Timon agreed to this set.
4. One fixed **Studio session** on PC-TIMON executes every click. Timon's working sessions (e.g. "Editor history")
   are not disturbed.
5. Every result is visible in the Artifact: job status (queued / running / done / failed with the reason), the plan,
   the storyboard and review frames, and for a finished render a short preview (see *Render result*).

## Non-goals (for this version)
- Music, posting queue, AI shots, SD-card offload, insights/tools. They come later, through the same route.
- Replacing the local web app. `start-studio.bat` stays; the Artifact is an extra way in.
- Tailscale or any other way to expose the PC to the internet.
- Driving the Odyssey PowerGrade. It does nothing when applied by script (known; see CLAUDE.md), so grades are LUTs.

## Anti-goals (would make it a failure even if it "works")
- A render or Resolve build starts twice because two sessions answered one click.
- A render starts without Timon's approval of that exact plan (gate B), or a paid AI shot runs without a quote. The
  Artifact must never make these easier to bypass.
- The Studio session runs anything a comment asks beyond the allowed editor commands (a comment is the owner's
  request, but its text is still parsed, never executed as free text).
- Grade picking that waits on the PC for every tap.
- Copying the bought Odyssey looks (or any bought pack) into the repo or the Artifact. (Sony's free S-Log3 conversion
  LUT may go into the private Artifact's assets for the preview; it is never committed. Claude's call.)
- Footage, client files or personal data ending up in the Artifact beyond the few preview stills Timon picks from.

## Constraints
- Artifact runtime contract 0.2.96. Capabilities used: `comments` (full form, for `sendToClaude`), `db`, `user`,
  `assets` (stills, LUT files, previews; 20 MiB per file). No `mcp`.
- `sendToClaude` is for editors of the artifact only, needs the viewer's own recent gesture, and is "held to a human
  cadence" (rate limited). Each send makes a comment thread; the artifact has a thread limit. So: one send per real
  action, never on load, never in a loop.
- The Artifact page cannot reach the PC directly (no fetch to other hosts). All data comes through `db` and `assets`.
- The Studio session must be a Claude Code session on PC-TIMON connected through Remote Control, with the
  `ArtifactComments`, `ArtifactData` and `Artifact` tools available (the spike's PC session had them).
- Commands: only what `webapp/host.py` `ALLOWED` permits, with the same argument validation as `webapp/app.py`
  (`grade_args`, project-name checks). Reuse that code; don't write a second validator.
- Approval gates are unchanged: `engine approve` only with Timon's own words on the current plan; a new plan needs a
  new approval; paid AI only after `--quote` and his yes.
- Repo rules: docs/README.md lists every document (`tools/doc_check.py` must pass); a change Timon notices goes in
  `CHANGELOG.md`; a hard-to-reverse decision gets a record in `docs/decisions/`.
- Branch: work on `claude/artifact-brainstorm-ob2lld` (this session's branch), merged by PR.

## Scope settled after the builder check (Claude's calls unless marked)
- **Pipeline: the cine montage engine only** (`engine plan / approve / render`), as discussed with Timon. AutoEdit
  `run` / Resolve builds are not in this version; the request parser maps only to `engine` subcommands. Projects shown
  are those with a `cine_montage/` folder.
- **Strength and exposure must reach the cine render.** Today the engine takes the look from `--look` only and fixes
  exposure −1.75 / strength 1.0 (`engine/render.py`). Add `--strength` and `--exposure` to `engine preview/render/qa`,
  pass them through `render.lut_for` and `webapp/app.py grade_args`. Otherwise the sliders would lie.
- **The choice is stored per project** in the cine montage's own state (next to the plan), read by the engine
  commands the Studio session runs, so preview and render use it.
- **Browser preview = the same maths as the render:** Sony's conversion LUT plus our look, exposure applied on the
  S-Log3 values before the conversion, exactly as `grade.build_lut`. 
- **`vintage` has no grain** (a 3D LUT can't carry grain): soft contrast and colour only.
- **A grade change needs a new approval (Timon's decision).** "Grade wissel moet ook goedkeuring hebben, dat is
  gewoon het mooiste." The approval covers the plan *and* its grade (look, strength, exposure): put the grade into
  what `engine approve` records (e.g. into the hash the approval checks), so choosing another grade after approval
  makes the approval stale and `engine render` refuses until Timon approves again. The Artifact shows this clearly
  ("grade gewijzigd: opnieuw goedkeuren").
- **Only the owner's requests run.** The Studio session acts only on comments attributed to the artifact's owner
  (Timon); anything from another editor gets a polite refusal in the thread.
- **Branch/PR:** this session's branch `claude/artifact-brainstorm-ob2lld`, one PR to `main`; run `tools/doc_check.py`
  and the tests before the PR.

## How it works (decided)

### The pieces
1. **Studio Artifact** — the existing AutoEdit Studio artifact (same link, republished), now with real data.
2. **Studio session** — one Claude Code session on PC-TIMON, started by Timon, that watches the Studio Artifact and
   handles its requests. It is the only session that watches it; Timon's other sessions don't.
3. **The page's `db`** — what the page shows: projects, jobs, plan, grade choice. Only the Studio session writes it.

**The PC is central.** Every fact lives in files on PC-TIMON: the grade in `<project>/cine_montage/grade.json`, the
plan and approval in `cine_montage/`, the handled comment threads in `data/studio_handled.json`, job results in
`data/studio_results/`. The `db` is a copy the Studio session writes from the CLI's output (`python -m webapp
studio-projects` / the result line of each request); the page never decides anything itself.

**Same account.** The Studio artifact and the Claude account the PC session runs under must match: the same account,
or the artifact shared with that account with edit rights. Otherwise the PC session cannot `watch` the artifact (no
button presses arrive) and cannot write its `db`. When the Studio is published under another account, change
`STUDIO_URL` in `start-studio-sessie.bat`.

**All projects (Timon's decision, 2026-11-02).** "Alles moet in de Studio": every project with a `cine_montage/`
folder shows up, client projects (e.g. JUICT) included. Their stills go into the private Studio artifact only.

### A click, end to end
1. Timon presses a button (e.g. *Plan maken*, *Kies deze grade*, *Goedkeuren*).
2. The page writes nothing itself to start work; it calls `comments.sendToClaude` with a short, fixed-format request
   anchored on that button, e.g. `[studio] actie=grade project=Beef Tartaar v2 look=moody strength=0.8 exposure=-1.75`.
   For *Goedkeuren* the text includes Timon's own words, typed in the page.
3. The Studio session receives the comment and passes it, through a file, to `python -m webapp studio`, which parses
   the fixed format and maps it to one allowed editor command (through the web app's validation). Engine work (grade,
   plan, approve, preview, render, QA) starts in a detached worker on the PC that survives the session's shell call;
   the worker runs one job at a time (`data/studio.lock`) and writes its result, which the session fetches with
   `python -m webapp studio-result`. `stills` answers at once. The session then uploads files, writes the job's status
   and results into `db`, replies once in the thread (short) and resolves it.
4. The page shows the job live from `db` (`onSnapshot`).

### Grade picking (smooth)
- Once per project (on first open, or when Timon asks), the Studio session uploads to the Artifact's `assets`:
  a few ungraded S-Log3 stills from the project (3–5, chosen to show skin, sky, shadows) and the six look LUTs as
  `.cube` files (or a compact image form of them).
- The page applies the LUT to the still **in the browser** (WebGL, trilinear, like `grade.apply_cube`), with exposure
  and strength applied the way `grade.build_lut` does. Tapping, sliding and before/after need no PC.
- **Kies deze grade** sends one request; the Studio session runs `engine grade`, which writes the look (and
  strength/exposure) into `<project>/cine_montage/grade.json`, so the next plan/preview/render uses it. The grade is
  part of the approval: a grade change after approval needs a new approval. Storyboard and preview record the grade
  they were made with, and the page says so (warning when the grade changed since).

### New looks
`daylight`, `blue_hour` and `vintage` are added to `autoedit/grade.py` `LOOKS` as our own parameter sets (same
`film_look` maths), and to the allowed values in `webapp/app.py` and the engine's `--look` handling. Tested with a
render on Timon's footage before they appear in the Artifact.

### Approval stays strict
The *Goedkeuren* button needs Timon's own words in a text box; the request carries them; the Studio session runs
`engine approve` only for the plan currently shown (the plan id/hash is in the request and must match). If the plan
changed, it refuses and says so in the Artifact.

### One executor
Only the Studio session watches the Studio Artifact. The session that publishes the Artifact (in a later build
session) must stop watching it after publishing (`ArtifactComments` watch `on: false`), as in the spike. The Studio
session ignores a request whose thread already has a Claude reply, and the CLI records each handled thread id in
`data/studio_handled.json` on the PC (under a file lock) before it starts anything, so a retry or duplicate never runs
a job twice.

## Render result (Claude's call, Timon can change it)
Timon did not choose yet. Default: the Artifact shows the review image (for a cine montage: the storyboard sheet) and,
when it fits under 20 MiB, a 720p preview video that the worker makes. The full 1080p export stays on the PC in
`exports/`.

## Left to the builder
- The exact request format, `db` layout, and how job progress is reported (polling the job log vs. writing at the end).
- How the Studio session is started on the PC (a .bat file that opens Claude Code with a skill, or a skill Timon invokes
  in a new session), as long as it is one click or one sentence for Timon.
- Which stills to pick per project and how many.
- WebGL details and the LUT transport format.
- The page design, keeping the existing Studio artifact's look (dark, JUICT red #E70002, Dutch text).
- What the page shows when the Studio session is offline (PC off): say so clearly, keep grade preview working on the
  stills already uploaded, disable buttons that need the PC.
