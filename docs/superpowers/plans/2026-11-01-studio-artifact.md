# Studio Artifact Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the published AutoEdit Studio Artifact a real remote control for the cine montage on PC-TIMON: smooth LUT grade picking, plan, approve (plan + grade), render, results.

**Architecture:** The Artifact sends each action as a fixed-format comment with `comments.sendToClaude`; one Studio session on PC-TIMON watches the Artifact, turns the request into one allowed `engine` command through `webapp/studio.py`, runs it, and writes state into the Artifact's `db` and `assets`. Grade previews are computed in the browser (WebGL) from ungraded stills plus two LUT stages exported once per project, so tapping and sliding never wait on the PC.

**Tech Stack:** Python 3 (numpy, Flask web app, imageio-ffmpeg), the cine engine (`VIDEO_EDITING_SYSTEM/engine`), claude.ai Artifact runtime contract 0.2.96 (`comments`, `db`, `user`, `assets`), WebGL 1 in a single HTML page.

**Spec:** `docs/superpowers/specs/2026-11-01-studio-artifact-design.md`

## Global Constraints
- Grades are LUTs only; the Odyssey PowerGrade is not driven. Six looks: `reference_film`, `clean_warm`, `moody`, `daylight`, `blue_hour`, `vintage` (no grain).
- Fixed base: Sony `SLog3SGamut3.CineToLC-709TypeA.cube`, exposure default −1.75 stops, applied on S-Log3 code values before the conversion (`exposure * 0.0769`), as `grade.build_lut`.
- Approval covers plan **and** grade (look, strength, exposure). A grade change after approval makes `engine render` refuse until a new `engine approve`.
- `engine approve` only with Timon's own words; `--by Timon`.
- Only `webapp/host.py` `ALLOWED` commands run; arguments validated by code, never free text.
- The Studio session acts only on comments attributed to the artifact's owner; exactly one session watches the Studio Artifact.
- Never commit third-party material (Sony LUT, bought packs, footage stills). The Sony LUT may go only into the private Artifact's assets.
- Assets ≤ 20 MiB each; a render preview is uploaded only if ≤ 20 MiB, else only the review image.
- All Artifact UI text in Dutch; look: dark, JUICT red `#E70002`.
- Work on branch `claude/artifact-brainstorm-ob2lld`; `python tools/doc_check.py` passes before every commit that touches docs.

## Review Focus
- A request that arrives twice (two sends, a retried thread) must not start a second render → `studio.handled()` dedupe test in Task 4.
- Approving, then changing the grade, then pressing *Renderen* → refused with a clear Dutch reason → gate test in Task 2, mapping test in Task 4.
- *Goedkeuren* sent for a plan that changed since the page showed it → refused (plan id mismatch) → Task 4.
- A project whose clips are already Rec.709 (phone/AI) → preview skips the conversion stage → `is_log` false path in Task 5.
- PC offline (no watching session) → page shows it and disables PC buttons, grade preview still works → Task 6 manual check.

---

### Task 1: Three new looks and a look-only LUT export

**Files:**
- Modify: `autoedit/grade.py` (`LOOKS`, new `look_lut`)
- Test: `tests/grade_looks_test.py`

**Interfaces:**
- Produces: `grade.LOOKS` keys incl. `daylight`, `blue_hour`, `vintage`; `grade.look_lut(look: str, size: int = 33) -> np.ndarray` (shape `(size,size,size,3)`, indexed `[b][g][r]` like `identity`, the film look at strength 1 on Rec.709 values; identity grid for `none`).

- [ ] **Step 1: Write the failing test** (script style like `tests/offload_test.py`)

```python
import numpy as np
from autoedit import grade
for k in ("reference_film", "clean_warm", "moody", "daylight", "blue_hour", "vintage", "none"):
    assert k in grade.LOOKS
c = np.random.default_rng(1).random((500, 3))
for k in ("daylight", "blue_hour", "vintage"):
    p = grade.LOOKS[k]
    full = grade.film_look(c, p, 1.0)
    assert np.allclose(grade.film_look(c, p, 0.6), c + (full - c) * 0.6, atol=1e-6)   # strength is a linear mix
    assert np.abs(full - c).mean() > 0.01 and np.isfinite(full).all()
    lut = grade.look_lut(k, 17)
    assert lut.shape == (17, 17, 17, 3) and lut.min() >= -1e-6 and lut.max() <= 1 + 1e-6
assert np.allclose(grade.look_lut("none", 9), grade.identity(9))
# daylight warmer than blue_hour on a mid grey
g = np.full((1, 3), 0.5)
d, b = grade.film_look(g, grade.LOOKS["daylight"], 1)[0], grade.film_look(g, grade.LOOKS["blue_hour"], 1)[0]
assert d[0] - d[2] > b[0] - b[2]
print("grade looks ok")
```

- [ ] **Step 2: Run, expect FAIL** — `python tests/grade_looks_test.py` → `AssertionError` on `daylight`.
- [ ] **Step 3: Add the three parameter sets to `LOOKS`** (same keys as `clean_warm`): `daylight` bright, warm skin, fresh sky (warm highlights, `teal_sky` ~0.25, `orange_skin` ~0.25, sat ~1.15, low fade); `blue_hour` cool, soft shadows (blue-shifted shadows and highlights, contrast ~1.0, lift ~0.03, sat ~0.95); `vintage` soft contrast (contrast ~0.92, lift ~0.06, fade ~0.06, sat ~0.85, warm highlights). Tune by eye later on footage (Task 7); the test pins only the direction.
- [ ] **Step 4: Implement `look_lut`** — `film_look(identity(size).reshape(-1,3), LOOKS[look], 1.0)` reshaped, clipped to 0..1; identity for `none`.
- [ ] **Step 5: Run, expect PASS** — `python tests/grade_looks_test.py` → `grade looks ok`.
- [ ] **Step 6: Commit** — `git add autoedit/grade.py tests/grade_looks_test.py && git commit -m "grade: daylight, blue_hour, vintage looks; look-only LUT export"`

### Task 2: Grade choice in the cine engine, part of the approval

**Files:**
- Create: `VIDEO_EDITING_SYSTEM/engine/gradechoice.py`
- Modify: `VIDEO_EDITING_SYSTEM/engine/cli.py` (new `grade` subcommand, approve/render gate, `--look` choices), `VIDEO_EDITING_SYSTEM/engine/render.py` (`lut_for`, `render`), `VIDEO_EDITING_SYSTEM/engine/storyboard.py` (pass the grade)
- Test: `VIDEO_EDITING_SYSTEM/tests/grade_gate_test.py`

**Interfaces:**
- Produces:
  - `gradechoice.Grade` dataclass `(look: str = "reference_film", strength: float = 1.0, exposure: float = -1.75)`
  - `gradechoice.LOOKS: tuple[str, ...]` (the six looks, no `none`)
  - `gradechoice.load(work: Path) -> Grade` (reads `work/grade.json`, default `Grade()` when absent)
  - `gradechoice.save(work: Path, g: Grade) -> None` (validates; `ValueError` in Dutch for a bad value)
  - `gradechoice.key(g: Grade) -> str` (12-hex sha1 of `[look, round(strength,3), round(exposure,3)]`)
  - CLI: `engine grade <project> --look L [--strength 0..1] [--exposure -3..0.5]` writes `cine_montage/grade.json`
  - `cli.render_allowed(work: Path, g: Grade) -> tuple[bool, str]`; `APPROVAL.json` gains `"grade_key"`
  - `render.lut_for(mode: str, clip: str, notes: list, g: Grade | None = None) -> Path | None` (strength/exposure from `g`; exposure only on log clips)

- [ ] **Step 1: Write the failing test** (temp project folder, fake `edl.json` bytes, no footage)

```python
work = tmp / "proj" / "cine_montage"; work.mkdir(parents=True); (work / "edl.json").write_text('{"events": []}')
cli.main(["grade", str(tmp / "proj"), "--look", "moody", "--strength", "0.8", "--exposure", "-1.5"])
g = gradechoice.load(work); assert (g.look, g.strength, g.exposure) == ("moody", 0.8, -1.5)
cli.main(["approve", str(tmp / "proj"), "--by", "Timon", "--note", "mooi zo"])
assert json.loads((work / "APPROVAL.json").read_text())["grade_key"] == gradechoice.key(g)
assert cli.render_allowed(work, g) == (True, "")
cli.main(["grade", str(tmp / "proj"), "--look", "vintage"])
ok, why = cli.render_allowed(work, gradechoice.load(work)); assert not ok and "grade" in why.lower()
for bad in (["--look", "odyssey"], ["--look", "moody", "--strength", "1.5"], ["--look", "moody", "--exposure", "-9"]):
    try: cli.main(["grade", str(tmp / "proj")] + bad); raise AssertionError(bad)
    except SystemExit: pass
(work / "edl.json").write_text('{"events": [1]}')                       # plan changed -> refused too
assert not cli.render_allowed(work, gradechoice.load(work))[0]
print("grade gate ok")
```

- [ ] **Step 2: Run, expect FAIL** — `cd VIDEO_EDITING_SYSTEM && python tests/grade_gate_test.py` → `invalid choice: 'grade'`.
- [ ] **Step 3: Implement `gradechoice.py`** per Interfaces; ranges: strength 0..1, exposure −3.0..0.5.
- [ ] **Step 4: Wire `cli.py`** — `grade` subparser (`--look` choices `gradechoice.LOOKS`); `approve` writes `grade_key=gradechoice.key(gradechoice.load(work))`; `render` calls `render_allowed` with the effective grade and raises `SystemExit("REFUSED: " + why)`; refusal text for a grade change: `"de grade is gewijzigd na de goedkeuring: keur opnieuw goed"`. Effective grade = `gradechoice.load(work)`, with `--look` (now `default=None`, choices = the six) overriding only the look for that run. `plan/preview/render/check/qa` pass the effective `Grade` down; keep the `--grade auto|slog3|rec709|none` mode as is.
- [ ] **Step 5: Thread `g` through `render.render(..., grade: Grade | None = None)`, `storyboard.build(..., grade=None)` and `lut_for`** — `grade.build_lut(g.look, strength=g.strength, exposure=g.exposure if is_log else 0.0, conversion=...)`.
- [ ] **Step 6: Run, expect PASS**, then the existing suites: `python tests/grade_gate_test.py`, `python tests/style_checks_test.py`, `python tests/gridflow_test.py` (all in `VIDEO_EDITING_SYSTEM`).
- [ ] **Step 7: Commit** — `git commit -m "engine: grade choice per project (look/strength/exposure), part of the approval"`

### Task 3: Local web app parity

**Files:**
- Modify: `webapp/host.py` (`ALLOWED["engine"]` + `"grade"`), `webapp/app.py` (`LOOKS` = the six; `grade_args` drops `--look`; new `POST /api/projects/<name>/cine/grade`), `webapp/static/` (grade select on the cine tab sends to the new route)
- Test: `tests/webapp_grade_test.py`

**Interfaces:**
- Consumes: CLI `engine grade` (Task 2).
- Produces: `POST /api/projects/<name>/cine/grade` body `{"look", "strength", "exposure"}` → job `["engine","grade",<path>,"--look",L,"--strength",S,"--exposure",E]`.

- [ ] **Step 1: Failing test** — `app.create(host=FakeHost())` where `FakeHost.run(args, label, project)` records `args` and `FakeHost.call("project", name)` returns `{"path": "/p/x"}` (match how `proj()` reads the host; check `app.py:70`). Assert: posting `{"look":"blue_hour","strength":0.7,"exposure":-1.5}` records exactly the argv above; `{"look":"odyssey"}` → HTTP 400; `{"strength": 2}` → 400.
- [ ] **Step 2: Run, expect FAIL** — `python tests/webapp_grade_test.py` → 404 on the route.
- [ ] **Step 3: Implement** with `_num(v, 0, 1)` / `_num(v, -3, 0.5)`; add a look select + two sliders on the cine tab that call the route.
- [ ] **Step 4: Run, expect PASS.**
- [ ] **Step 5: Commit** — `git commit -m "webapp: choose the cine grade (look, strength, exposure)"`

### Task 4: Studio request handling (`python -m webapp studio`)

**Files:**
- Create: `webapp/studio.py`
- Modify: `webapp/__main__.py` (role `studio`, `studio-state`)
- Test: `tests/studio_test.py`

**Interfaces:**
- Consumes: `query.project_dir`, `query.cine`, `host.check_args`, `LocalHost.run`, app validators `_num/_text/_name` (move them to `webapp/validate.py` if importing `app` pulls Flask into the worker path; keep one copy).
- Produces:
  - Request text format (the page builds exactly this): `[studio] actie=<plan|grade|goedkeuren|preview|render|qa|stills> project="<name>" [look=.. strength=.. exposure=..] [plan=<edl_sha1>] [notitie="<own words>"]`, parsed with `shlex.split` after the `[studio]` tag.
  - `studio.parse(text: str) -> dict` (`ValueError` in Dutch on: missing tag, unknown action, unknown key, duplicate key)
  - `studio.to_args(req: dict) -> list[str]` (one `engine ...` argv; `goedkeuren` requires `notitie` and `plan` equal to the current `edl_sha1`, else `ValueError("het plan is veranderd sinds je het zag: bekijk het nieuwe plan")`; `stills` maps to Task 5, not to `engine`)
  - `studio.handled(thread_id: str) -> bool` and `studio.mark(thread_id: str)` (file `data/studio_handled.json`, keeps the last 500)
  - `studio.state(name: str) -> dict` — the `projects/<slug>` db document (layout below)
  - CLI: `python -m webapp studio --thread <id> "<text>"` runs synchronously, prints one JSON line `{"ok", "action", "message", "state"}`; exits early with `{"ok": false, "message": "al afgehandeld"}` for a handled thread. `python -m webapp studio-state "<name>"` prints `state`.
- **db layout** (the page in Task 6 and the skill in Task 7 use exactly this):
  - `studio/pc`: `{host, seen_at}` written by the session on start and after each request
  - `projects/<slug>` (slug = lowercase ascii, `-` for other chars): `{name, plan: {edl_sha1, shots, duration, title} | null, approval: {status, by, at, note, current: bool, grade_current: bool} | null, grade: {look, strength, exposure}, stills: [{url, is_log, label}], luts: {conv: url|null, looks: {<look>: url}}, render: {at, review_url, preview_url|null} | null, updated_at}` (no local paths)
  - `jobs/<thread_id>`: `{project, action, status: "bezig"|"klaar"|"fout", message, started_at, finished_at}`

- [ ] **Step 1: Failing tests** — parse round-trip with a quoted note containing spaces and `=`; unknown action `wis` → `ValueError`; `actie=render` → `["engine","render",<path>]`; `actie=grade look=moody strength=0.8 exposure=-1.5` → engine grade argv; `look=odyssey` → error; `goedkeuren` without `notitie` → error; with stale `plan=` → the Dutch "plan is veranderd" error; with current plan → `["engine","approve",<path>,"--by","Timon","--note",<words>]`; extra free text after the tag (`; del *`) → error; `handled/mark` round-trip and dedupe; `state()` on a temp project (fake `edl.json`, `APPROVAL.json`, `grade.json`) gives `approval.grade_current == False` after a grade change and contains no `\\` or `:/` path strings. Use a temp `projects` root by pointing `query.roots` at it (monkeypatch).
- [ ] **Step 2: Run, expect FAIL** — `python tests/studio_test.py` → `ModuleNotFoundError: webapp.studio`.
- [ ] **Step 3: Implement** per Interfaces; run the command through `host.check_args` then `LocalHost().run` and wait for the job to finish (poll its status) so the CLI returns the outcome.
- [ ] **Step 4: Run, expect PASS** — `python tests/studio_test.py`.
- [ ] **Step 5: Commit** — `git commit -m "webapp: studio requests from the Artifact (parse, validate, dedupe, state)"`

### Task 5: Preview stills and LUT export (`actie=stills`)

**Files:**
- Create: `webapp/studio_assets.py`
- Test: `tests/studio_assets_test.py`

**Interfaces:**
- Consumes: `grade.look_lut`, `grade.write_cube`, `grade.SONY`, `render.detect_log`, `media.FF`, `gradechoice.LOOKS`.
- Produces: `studio_assets.export(project: Path, out_dir: Path, n: int = 4) -> dict` writing `still_<i>.png` (ungraded, 1280 px wide, from the plan's title/body events spread over the plan, else spread over the clips), `conv.cube` (copy of the Sony LUT, only when present and any still is log), `look_<name>.cube` (33³, `look_lut`) for the six looks; returns `{"stills": [{"file", "is_log", "label"}], "conv": file|None, "looks": {name: file}}`. The Studio session uploads these files (Task 7); nothing here touches the network.
- Browser maths the page must match: `x' = clamp(x + exposure·0.0769)` (log stills only) → `c = conv(x')` (log only) → `o = look(c)` → `out = c + (o − c)·strength`.

- [ ] **Step 1: Failing test** — make a 2 s test clip with `media.FF` (`-f lavfi -i testsrc2=size=640x360:rate=25`), a temp project with it in `clips/`, a temp Sony dir with an identity `.cube` monkeypatched as `grade.SONY`; assert 4 PNGs exist and are 1280 wide, six look files, each look file has `LUT_3D_SIZE 33`, `is_log` is a bool; and the two-stage maths in numpy on a sample equals `grade.apply_cube(build_lut-equivalent)` within 2/255 for `moody`, strength 0.7, exposure −1.75 (build the reference with `grade.film_look` + `apply_cube` on the temp identity conversion).
- [ ] **Step 2: Run, expect FAIL.**
- [ ] **Step 3: Implement**; map `actie=stills` in `studio.py` to `export(...)` into `data/studio_assets/<slug>/`.
- [ ] **Step 4: Run, expect PASS.**
- [ ] **Step 5: Commit** — `git commit -m "webapp: preview stills and LUT stages for the Artifact grade picker"`

### Task 6: The Studio Artifact page

**Files:**
- Create: `webapp/artifact/studio.html` (source of the published page, no data inside)
- Publish: to the existing **AutoEdit Studio** artifact `https://claude.ai/artifact/4YCCLgHK4KozydqGCpjLQR` (`Artifact` action `read` first, then publish with `url`), capabilities `{"comments": {}, "db": {"rules": [{"path": "", "read": "view", "write": "owner"}]}, "user": {}, "assets": {}}`. After publishing, stop watching it in that session (`ArtifactComments` watch `on: false`).

**Interfaces:**
- Consumes: db layout and request format (Task 4), browser maths (Task 5).
- Produces: buttons that each make one `comments.sendToClaude({anchor: await comments.anchorFor(button), text})` with the Task 4 format.

- [ ] **Step 1: Pages** — Projecten (list of `projects/*`), Project: *Grade* (stills, six look chips, strength 0–100 %, exposure −3…+0.5 stops, swipe before/after, **Kies deze grade**, **Stills verversen** = `actie=stills`), *Plan* (shots, duration, title, **Plan maken**, **Voorbeeld**), *Goedkeuren* (plan id shown, text box for own words, button disabled while empty; shows "grade gewijzigd: opnieuw goedkeuren" when `approval.grade_current` is false), *Renderen* (enabled only when `approval.current && approval.grade_current`), *Resultaat* (review image, preview video if present). A jobs strip from `jobs/*` (newest first). Keep the existing Studio look.
- [ ] **Step 2: WebGL grade** — upload the still and the two 33³ LUTs as 2D textures (33 slices side by side), trilinear lookup in the fragment shader, uniforms for exposure, strength, `is_log`; no PC round trip on tap/slide.
- [ ] **Step 3: Offline state** — `canSendToClaude()`: anything but `available` → banner "Studio-sessie op je PC is niet bereikbaar" with `studio/pc.seen_at`, PC buttons disabled; grade preview keeps working.
- [ ] **Step 4: Check the maths once** — run the shader's lookup logic as plain JS in node on 5 sample pixels against numpy from Task 5's function: max error ≤ 2/255.
- [ ] **Step 5: Preview + publish** — one preview look, publish, then one `ArtifactData list` of `projects` (empty is fine) and tell Timon what was exercised.
- [ ] **Step 6: Commit** — `git commit -m "Studio Artifact: grade picker, plan, approve, render over the comment route"`

### Task 7: The Studio session on the PC

**Files:**
- Create: `.claude/skills/studio-session/SKILL.md`, `start-studio-sessie.bat` (opens Claude Code in the repo with the prompt "start de Studio-sessie")
- Modify: `webapp/README.md` (section *Studio in de Claude-app*), `CHANGELOG.md`, `docs/README.md`, `docs/decisions/0011-studio-artifact-comment-route.md` (+ index)

**Interfaces:**
- Consumes: `python -m webapp studio --thread <id> "<text>"`, `studio-state`, `actie=stills` output folder, db layout.

- [ ] **Step 1: Write the skill** — on start: `ArtifactComments watch` the Studio URL, write `studio/pc`. On each comment sent to Claude: act only if the attribution is the owner ("the user (owner)") and the text starts with `[studio]`; else reply "Alleen Timon kan de Studio bedienen" / "Onbekend verzoek" and resolve. Write `jobs/<thread>` `bezig`, run the CLI, upload new files with `Artifact` (`asset: true`, `file_paths`), write `projects/<slug>` from `studio-state` plus asset URLs, write `jobs/<thread>` `klaar`/`fout` with the message, reply one short Dutch line, resolve. Never run anything else; never approve without `notitie`; never raise budgets; Muapi stays out of scope. Renders: after `render`, upload `<base>_review.png` and the 720p preview only if ≤ 20 MiB.
- [ ] **Step 2: Docs** — README section (how to start it, that it must be the only watcher, what each button does), CHANGELOG line, decision record 0011 (why the comment route, why not the connector, why one executor), docs map entry. Run `python tools/doc_check.py` → `0 problem(s)`.
- [ ] **Step 3: Commit** — `git commit -m "Studio session skill + docs"`

### Task 8: Acceptance on PC-TIMON (with Timon)

- [ ] Timon starts the Studio session (`start-studio-sessie.bat`); the page shows the PC as reachable.
- [ ] On a real project (e.g. Beef Tartaar v2): **Stills verversen** → stills appear; tapping looks and sliders is instant; the three new looks look right on his footage (tune `LOOKS` if not, rerun Task 1 test).
- [ ] **Kies deze grade** → `grade.json` written; **Voorbeeld** renders with that grade (compare a frame to the browser preview).
- [ ] **Goedkeuren** with own words → approved; change the grade → page shows "opnieuw goedkeuren", **Renderen** refused by the engine as well; approve again → render runs once, result appears.
- [ ] Press **Renderen** twice quickly → one job only.
- [ ] Open the page with the session stopped → offline banner, preview still works.
- [ ] Open the PR to `main` after tests and `doc_check` pass; ask Timon before creating it.
