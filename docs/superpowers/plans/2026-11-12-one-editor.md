# One Editor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn AutoEdit into one editor with one flow: four choices (song, rhythm, length, PowerGrade), bad footage
cut away by itself, filming order kept, a Resolve timeline plus a "weggeknipt" timeline, and talking videos that never
cut mid-sentence.

**Architecture:** Everything up to the `Plan` object is pure Python that runs without Resolve and is tested on
synthetic clips; only `builder.py` talks to Resolve. New small modules (`brief.py`, `moments.py`, `music.py`,
`powergrade.py`, `speech.py`, `talk.py`) feed the existing planner, director and builder. The website gets one page
for the flow; the Studio and the cine engine are reduced only after Timon's yes.

**Tech Stack:** Python 3 (`C:\Users\Timon\.aev\Scripts\python.exe`, `PYTHONIOENCODING=utf-8`), DaVinci Resolve
scripting API, ffmpeg via `imageio_ffmpeg`, librosa, OpenCV, faster-whisper (local model
`mobiuslabsgmbh/faster-whisper-large-v3-turbo`, already downloaded), Flask website, plain JS.

**Spec:** [docs/superpowers/specs/2026-11-12-one-editor-design.md](../specs/2026-11-12-one-editor-design.md) (decisions
D1–D13). Evidence: [2026-11-12-one-editor-notes.md](../specs/2026-11-12-one-editor-notes.md).

## Global Constraints
- Every phase is its own branch (`feature/<phase-name>`) in its own worktree under
  `..\Davinchi-Auto-Editor-worktrees\`, and its own pull request to `main`. Never commit on `main`, never force-push.
  Open the PR only after Timon says yes; the PR needs: all tests green, `doc_check` green, a secrets check of the diff.
- Run everything with `C:\Users\Timon\.aev\Scripts\python.exe` and `PYTHONIOENCODING=utf-8`. No ffmpeg on PATH: use
  `imageio_ffmpeg.get_ffmpeg_exe()`.
- Tests are scripts with bare `assert`s that end with `print("<name> test ok")`; run all with
  `python tools/run_tests.py` (Task 0.2). Tests never need Resolve, the SSD, or real footage.
- After any change to a document, command or yaml: `python tools/doc_check.py` must print `0 problem(s)`.
  `taste.yaml` `enforced_by` entries have the form `'<file>: <text found in that file>'`.
- Files in this repo use CRLF. Edit with the Edit tool or a script that reads and writes bytes; do not let a tool
  rewrite line endings.
- 25 fps. 9:16 is the default aspect of the new flow. Originals and the camera card are never modified.
- Never call `comp.Render()`. Fusion comps only through `fx.commit`.
- No render for posting and no post without Timon's yes. Paid AI only after `--quote` and his yes for that shot.
- Never read, print or copy values from `.env`. Never commit third-party material (songs, packs, reference frames,
  `.drx` files: `data/` is git-ignored and stays so).
- A change Timon would notice gets a line in `CHANGELOG.md`; feedback of his gets a rule in `taste.yaml`.
- Do not touch `client_edits/`, the `juict-edit` skill, or the Studio's JUICT pages outside Phase 8.
- Phase 8 changes nothing until Timon has answered the three open points in the spec.
- User-facing words in the CLI and the website are Dutch, plain, without code terms.

## Review Focus
1. **A shoot with one long clip** (10 minutes, handheld): moments must still give ≥ 5 separate shots, not one.
   Test in Task 2.2.
2. **A song shorter than the chosen length** or with no clear drop: the edit shrinks to the song, start is 0.0, no
   crash. Test in Task 3.1.
3. **A PowerGrade name that matches two files or none**: the command stops with the list of names; nothing is graded.
   Test in Task 4.1.
4. **A clip with no usable moment at all** (everything shaky): it is skipped with a line in `_cuts.json`; if every
   clip is skipped the command stops with a plain Dutch message. Test in Task 2.2.
5. **Speech that the model gets wrong or a clip in another language**: passages are still whole "sentences" by pause;
   an empty transcript falls back to `montage`. Test in Task 5.2.

---

## Phase 0 — Baseline (branch `feature/baseline`)

### Task 0.1: Bring the unmerged taste work onto `main`
**Files:** the 6 newest commits of local branch `fix/rustiger-knippen` (`2840fdd` … `a9e80ab`); skip `f29b5cb` and
`9e0b563` if they are already on `main` (`git branch -r --contains <sha>`).
- [ ] Create the worktree from `origin/main`; `git cherry-pick` the commits in order.
- [ ] Conflicts in `CHANGELOG.md` and `taste.yaml`: keep both sides, newest entry first.
- [ ] Run `python tests/pacing_test.py` → `pacing test ok`. Run `python tools/doc_check.py` → `0 problem(s)`.
- [ ] Commit (the cherry-picks are the commits).

### Task 0.2: One test runner
**Files:** Create `tools/run_tests.py`; Modify `docs/README.md` (reference table: "Run all tests").
**Interfaces:** Produces `python tools/run_tests.py [-k text]` → runs every `tests/*_test.py` and
`VIDEO_EDITING_SYSTEM/tests/*_test.py` (skip `gridflow_test.py`: needs real footage) plus
`node tests/studio_page_lut_test.js` when `node` exists; prints one line per test and `N passed, M failed`; exit code
1 on any failure.
- [ ] Write `tests/run_tests_test.py`: runs the runner with `-k grade_looks` in a subprocess, asserts exit code 0 and
  `1 passed, 0 failed` in the output.
- [ ] Run it: fails (no runner). Implement. Run it: passes. Run the full runner; note any test already failing on
  `main` in the PR text, do not fix unrelated ones.
- [ ] Commit.

### Task 0.3: Reproducible runs and three bugs
**Files:** Modify `autoedit/pipeline.py` (`run`), `autoedit/builder.py:38,280,395`, `autoedit/review.py:125`,
`autoedit/pipeline.py:48-51,125`; Test `tests/seed_test.py`.
**Interfaces:** `pipeline.run(..., seed: int | None = None)` passes `seed` to `make_cinematic_plan`, and
`Builder(cfg, plan, style, log, seed=...)` passes it to `sfx.Library(..., seed=seed)`. Replace `hash(str)` with
`zlib.crc32(str.encode())`.
- [ ] Test: build two plans from the same synthetic clips (helper from `tests/pacing_test.py`) with `seed=3`, assert
  `plan.to_json()` equal; with `seed=4`, assert different. Assert `review._aspect_of("x_9x16") == "9:16"` and
  `"x_16x9"` → `"16:9"` (extract that helper from `review.py:125`).
- [ ] Fix: aspect helper; log `skipping <name>: dubbele opname` for dropped duplicates; `next(..., None)` with a
  plain error in `builder.render`.
- [ ] Runner green. Commit. Propose the PR.

---

## Phase 1 — The brief and the `edit` command (branch `feature/edit-brief`)

### Task 1.1: `Brief`
**Files:** Create `autoedit/brief.py`; Test `tests/brief_test.py`.
**Interfaces (produces):**
```python
LENGTHS = {"kort": 10.0, "normaal": 20.0, "lang": 30.0}
RHYTHMS = ("beat", "rustig")
@dataclass
class Brief:
    song: str | None = None
    song_start: float | None = None      # None = auto
    rhythm: str = "rustig"
    length: str = "normaal"
    grade: str | None = None             # PowerGrade name or "basis"
    kind: str = "auto"                   # auto / montage / praat
    aspect: str = "9:16"
    @property
    def seconds(self) -> float: ...
def from_project(settings: dict) -> Brief            # reads settings.get("edit", {}); unknown keys ignored
def merge(base: Brief, **overrides) -> Brief         # None overrides are skipped
def problems(b: Brief, songs: list[str], grades: list[str]) -> list[str]   # Dutch sentences; empty = ready
def to_project(b: Brief) -> dict                     # the dict stored under "edit"
```
- [ ] Test: defaults; `merge(Brief(), length="kort").seconds == 10.0`; `problems(Brief(), ["a.mp3"], ["Film"])`
  contains one sentence naming the missing song and one naming the missing grade, each listing the choices;
  `Brief(rhythm="snel")` → a problem; `from_project({"edit": {"song": "x", "bogus": 1}}).song == "x"`.
- [ ] Fail, implement, pass, commit.

### Task 1.2: Rhythm and length in the planner
**Files:** Modify `autoedit/planner.py` (`make_cinematic_plan`), `styles.yaml` (cinematic: remove `length_s`,
`shot_s`, `min_beats`, `min_shot_s`, `energy_speedup` once the planner reads them from the brief);
Test `tests/pacing_test.py` (extend).
**Interfaces:** `make_cinematic_plan(clips, style, cfg, music=None, variant="A", seed=7, stab_mode=None, title=None,
brief: Brief | None = None)`; without a brief it behaves as today. Rhythm table (spec D6): `beat` → step 2 beats,
floor `max(1 beat, 0.6 s)`, energy speed-up on; `rustig` → step 4 beats, floor `max(2 beats, 0.8 s)`, speed-up off.
Target length `brief.seconds`, ended on the nearest downbeat.
- [ ] Test with the 152 BPM synthetic song: `rustig`/`normaal` → every body shot ≥ 2 beats, `19 ≤ plan.length ≤ 23`;
  `beat`/`kort` → median shot ≤ 2 beats + 0.05 s, `9 ≤ plan.length ≤ 12`, no shot < 0.6 s; in both no cut within
  0.25 s of a motion peak.
- [ ] Fail, implement, pass, commit.

### Task 1.3: `autoedit edit`
**Files:** Modify `autoedit/__main__.py`, `autoedit/pipeline.py`, `autoedit/projects.py`; Test `tests/edit_cmd_test.py`.
**Interfaces:** `autoedit edit <project|folder> [--song S] [--song-start N] [--ritme beat|rustig]
[--lengte kort|normaal|lang] [--grade NAME] [--soort auto|montage|praat] [--aspect 9:16|16:9] [--seed N]
[--no-render]`. `pipeline.edit(cfg, target, brief: Brief, seed=None, render=True) -> list[dict]`: resolves a project
name to its `clips/` folder, merges the stored brief with the flags, stops with `brief.problems(...)` (exit code 2,
nothing built) when not ready, saves the brief back to `project.yaml`, then calls `run` with the brief. `pick_music`
loses the random fallback: no song → `None`.
- [ ] Test (no Resolve): monkeypatch `pipeline.run` to record its arguments; `edit` on a temp project without a song
  → exit code 2 and the song list in the message; with `--song x --grade basis` → `run` called once with
  `brief.song == "x"`, and `project.yaml` now has `edit: {song: x, grade: basis, …}`; a second call without flags
  reuses them.
- [ ] Fail, implement, pass. Add `edit` to `README.md` (*Edit a shoot*) and `CLAUDE.md` step 3; `doc_check`. Commit.
  Propose the PR.

---

## Phase 2 — Cutting by moments (branch `feature/moments`)

### Task 2.1: Per-window measurements
**Files:** Modify `autoedit/analyze.py` (`ClipAnalysis`, `analyze_clip`, cache key version); Test `tests/moments_test.py`.
**Interfaces:** `ClipAnalysis` gains `windows: list[dict]`, one per 0.5 s:
`{"t": float, "shake": 0..1, "pan": 0..1, "sharp": 0..1, "bright": 0..1, "speech": bool}`. `shake` = jitter of the
frame-to-frame global shift (high-frequency part), `pan` = size of the smoothed global shift (camera being moved),
both from the phase correlation / optical flow the function already computes for `shake`. Bump the cache key so old
caches are rebuilt.
- [ ] Test on three generated 6 s clips (OpenCV `VideoWriter`, 320×180, 25 fps): a static textured frame → all
  `shake < 0.2`, `pan < 0.2`; the same frame jittered ±6 px per frame → `shake > 0.6` in ≥ 10 of 12 windows; a slow
  pan for 2 s then a fast 300 px sweep with motion blur for 1 s → `pan > 0.6` and `sharp` lower in the sweep windows
  than in the first ones.
- [ ] Fail, implement, pass, commit.

### Task 2.2: `moments.py`
**Files:** Create `autoedit/moments.py`; Modify `config.yaml` (new block `cutting:` with the thresholds below);
Test `tests/moments_test.py` (extend).
**Interfaces (produces):**
```python
@dataclass
class Moment:
    clip: str; start: float; end: float
    verdict: str          # "keep" / "doubt" / "drop"
    reason: str           # "" / "stil" / "schokkerig" / "dubbel" / "te kort" / "camera verplaatst" / "begin-eind" / "te donker"
def label(clip: ClipAnalysis, cfg, min_shot: float) -> list[Moment]     # covers the clip end to end, no gaps
def keeps(moments: list[Moment]) -> list[Moment]
def report(all_moments: list[Moment]) -> dict     # {"kept_s", "doubt_s", "dropped_s", "by_reason": {...}, "clips_without_keep": [...]}
```
Rules exactly as spec D3; thresholds in `config.yaml`: `cutting: {edge_s: 0.5, shake_drop: 1.5, pan_drop: 0.6,
still_s: 2.0, still_motion: 0.05, dark: 0.08}` (`shake_drop` multiplies `stabilization.shake_threshold`).
- [ ] Test with hand-made `windows`: 0.5 s edges are `drop`/`begin-eind`; a 1.5 s block of `pan 0.8, sharp 0.2` is
  `drop`/`camera verplaatst`; 3 s of no motion, no speech is `doubt`/`stil`; a 0.7 s keep between two drops with
  `min_shot=1.6` becomes `doubt`/`te kort`; moments are contiguous and sum to the duration. Review Focus 1: one 600 s
  clip with a drop block every 20 s → `len(keeps(...)) >= 5`. Review Focus 4: an all-shaky clip → `keeps == []` and
  it appears in `report(...)["clips_without_keep"]`.
- [ ] Fail, implement, pass, commit.

### Task 2.3: The planner picks only from kept moments
**Files:** Modify `autoedit/planner.py` (`make_cinematic_plan`: candidate generation and score),
`autoedit/pipeline.py` (`run`: call `moments.label` per clip, write `<base>_cuts.json`, stop with
`"Geen bruikbaar beeld gevonden in deze map."` when no clip has a keep); Test `tests/pacing_test.py` (extend).
**Interfaces:** `make_cinematic_plan(..., moments: dict[str, list[Moment]] | None = None)`. Each shot lies inside one
keep moment. Score per candidate = sharpness + exposure + face bonus − reuse; **no** motion reward.
`Plan` gains `cuts: list[dict]` (`{clip, start, end, verdict, reason}`) for doubt and drop moments.
- [ ] Test: synthetic clips where seconds 4–6 of every clip are `drop` → no shot overlaps 4–6; shots are still in
  filming order; `plan.cuts` lists those ranges.
- [ ] Fail, implement, pass, commit.

### Task 2.4: The "weggeknipt" timeline
**Files:** Modify `autoedit/builder.py` (new method `build_cuts`, called at the end of `build`);
Test `tests/cuts_timeline_test.py`.
**Interfaces:** pure helper `builder.cuts_layout(plan, fps) -> list[dict]` (`{clip, src_in_f, src_out_f, rec_f,
marker}`): every `doubt` cut, filming order, back to back, marker text = the reason; `Builder.build_cuts()` creates
timeline `"<edit timeline name> · weggeknipt"` from it (video only, same grade as the edit) and returns its name in the
build result under `"cuts_timeline"`. No doubt cuts → no timeline.
- [ ] Test `cuts_layout` only: three doubt cuts and one drop → three entries, contiguous `rec_f`, markers
  `stil`/`schokkerig`/`te kort`, the drop absent.
- [ ] Fail, implement, pass. Then, with Resolve open, run `autoedit edit "Beef Tartaar" --song "ESCAPE PLAN"
  --grade basis --seed 1`; read `_review.json`, `_review.png`, `_cuts.json`; check by eye that the second timeline
  exists and its markers name reasons. Record what you saw in the PR text.
- [ ] `taste.yaml`: rule `cut_bad_moments` quoting Timon ("extreem schokkende beelden of dat ik mijn camera verplaats
  hoef ik niet terug te zien"), `enforced_by: 'autoedit/moments.py: camera verplaatst'`. `CHANGELOG.md`. Commit. PR.

---

## Phase 3 — The part of the song (branch `feature/song-section`)

### Task 3.1: `music.best_start`
**Files:** Create `autoedit/music.py`; Modify `autoedit/analyze.py` (`MusicAnalysis`: add `energy_10hz: list[float]`
if the 0.25 s `energy` is too coarse for the ported code; bump the music cache key), `autoedit/planner.py`
(`plan.music["offset"]`), `autoedit/media_prep.py` (`music_bed` must honour the offset: verify, it may already);
Test `tests/song_start_test.py`.
**Interfaces:** `music.best_start(m: MusicAnalysis, length: float) -> float` — port of
`VIDEO_EDITING_SYSTEM/engine/planner.py:114` (`best_song_start`): a bar start whose window has the biggest build-up
into the drop, the drop about two thirds into the edit. The planner uses `brief.song_start` when set, else
`best_start`; beats, downbeats, hits and energy are shifted by the offset before pacing.
- [ ] Test: synthetic 90 s song, quiet until 40 s, loud from 40 s, 120 BPM → `best_start(m, 20)` is on a bar and
  `40 - 20 * 0.8 <= start <= 40 - 20 * 0.5`; Review Focus 2: an 8 s song with `length=20` → `0.0`; flat energy →
  `0.0`; `brief.song_start=12.0` → `plan.music["offset"] == 12.0`.
- [ ] Fail, implement, pass. `CHANGELOG.md`. Commit. PR.

---

## Phase 4 — His PowerGrade, by name (branch `feature/powergrade`)

### Task 4.0: Spike — what the Resolve API offers (no code kept)
- [ ] With Resolve open, in a scratch script: does `project.GetGallery()` expose the PowerGrade album and
  `ExportStills(..., "drx")` on this version? Does `ApplyGradeFromDRX(path, 0)` work on a timeline item of a new
  timeline in project "AutoEdit" with a `.drx` exported by hand from the gallery? Does it keep the node tree intact
  (compare node count with `GetNodeGraph().GetNumNodes()`)?
- [ ] Write the answers into the PR text. If `ApplyGradeFromDRX` fails: stop and report to Timon; do not invent a
  workaround.

### Task 4.1: `powergrade.py`
**Files:** Create `autoedit/powergrade.py`; Modify `autoedit/__main__.py` (command `grades`); Test `tests/powergrade_test.py`.
**Interfaces:**
```python
FOLDER = DATA / "powergrades"
def available() -> list[str]                       # ["basis"] + sorted stems of FOLDER/*.drx
def resolve(name: str) -> Path | None              # None for "basis"; case-insensitive; exact stem, else unique substring
class GradeError(ValueError)                       # message in Dutch, lists available()
```
`autoedit grades` prints the names and, when the folder is empty, three plain lines on how to export a PowerGrade
(gallery → right-click the still → Export → `.drx` → this folder). `grades --sync` only if Task 4.0 showed the API
can export; otherwise leave it out.
- [ ] Test (temp folder via monkeypatching `FOLDER`): `available()` starts with `basis`; `resolve("film")` finds
  `Film look.drx`; Review Focus 3: two matches → `GradeError` naming both; no match → `GradeError` listing all;
  `resolve("basis") is None`.
- [ ] Fail, implement, pass, commit.

### Task 4.2: Apply it
**Files:** Modify `autoedit/builder.py` (`_grade`, delete `_powergrade_drx`, `LOOK_NODES`, the Denoise and
copy-LUT-to-branches code at `:125-154`, and the `bw` accent's `SetCDL` at `:273`), `autoedit/director.py` (never
plan `bw` when a PowerGrade is used), `config.yaml` (remove `grading.mode`, `gallery_label`, `drx_file`, `look`,
`denoise`, `grade_look`, `strength`); Test `tests/grade_choice_test.py`.
**Interfaces:** pure helper `builder.grade_plan(items: list[dict], grade: str) -> list[dict]` (`{name, action}` with
action `"drx:<path>"`, `"basis"` or `"skip"`): log clips get the DRX; AI clips (`AI_` prefix) and non-log clips get
`skip` with a PowerGrade and the look-free LUT with `basis`. `Builder._grade` executes it: `ResetAllGrades()`, then
`ApplyGradeFromDRX(path, 0)` per item, or the per-clip auto-balance LUT with look `none` for `basis`.
- [ ] Test `grade_plan`: 3 log clips + 1 `AI_` clip with `grade="Film"` → 3 `drx:` actions, 1 `skip`; with `basis` →
  4 `basis`.
- [ ] Fail, implement, pass. With Resolve open and one exported PowerGrade: run the Beef Tartaar edit with
  `--grade <name>`, open `_before_after.jpg`, confirm the grade is his (not the LUT). Record it in the PR.
- [ ] `taste.yaml` rule `own_powergrade` ("daar wil ik zelf volledige controle over hebben"),
  `enforced_by: 'autoedit/powergrade.py: def resolve'`. Update `CLAUDE.md` (the Grade line under Practical notes),
  `README.md`. `doc_check`. Commit. PR.

---

## Phase 5 — Talking videos (branch `feature/praat`)

### Task 5.1: `speech.py`
**Files:** Create `autoedit/speech.py`; Test `tests/speech_test.py`.
**Interfaces:**
```python
@dataclass
class Word: text: str; start: float; end: float
@dataclass
class Sentence: words: list[Word]; start: float; end: float; text: str
def transcribe(path: str | Path, language: str = "nl") -> list[Word]     # cached in data/cache like clip analysis
def sentences(words: list[Word], gap: float = 0.6) -> list[Sentence]    # split on . ! ? or a pause > gap
FILLERS = {"eh", "ehm", "uh", "uhm", "euh", "hmm"}
```
`transcribe`: audio → 16 kHz mono float32 array through ffmpeg, `WhisperModel(MODEL, device="cpu",
compute_type="int8", local_files_only=True)`, `word_timestamps=True`, no initial prompt; each word start moved later
to the audio onset when the signal is still quiet there (never earlier). If the model is missing: raise with one Dutch
line; never download.
- [ ] Test `sentences` only (no model): words with a 0.9 s gap split; punctuation splits; one-word input works; empty
  input → `[]`. Test the onset helper on a synthetic array (silence then a tone at 0.30 s, word start 0.20 → 0.30).
- [ ] Fail, implement, pass, commit.

### Task 5.2: `talk.py`
**Files:** Create `autoedit/talk.py`; Modify `autoedit/pipeline.py` (`kind` decision: `praat` when ≥ 60 % of kept
seconds have speech; writes `<base>_passages.json`), `autoedit/__main__.py` (`--passage N`), `autoedit/builder.py`
(keep clip audio and duck the music by `audio.music_duck_db` whenever `plan.mode == "talking"`; fix the unreachable
ducking), `autoedit/director.py` (in `talking`: title only); Test `tests/talk_test.py`.
**Interfaces:**
```python
@dataclass
class Passage: clip: str; sentences: list[Sentence]; score: float; text: str
def passages(per_clip: dict[str, list[Sentence]], lo: float = 15.0, hi: float = 30.0) -> list[Passage]   # best first
def cut_list(p: Passage, pause: float = 0.6) -> list[tuple[float, float]]   # source ranges to keep, in order
def make_talk_plan(p: Passage, style: dict, cfg, music: MusicAnalysis | None, brief: Brief) -> Plan      # mode="talking"
```
A passage is consecutive whole sentences of one clip, total kept length within `lo..hi` (a single clip shorter than
`lo` gives one passage with everything). Score = speech seconds / total seconds − 0.05 per filler − 0.1 per restart
(a sentence under 3 words followed by a sentence starting with the same word). `cut_list` removes pauses longer than
`pause` (keeping 0.15 s of air on each side) and filler words; a range boundary is always in silence, never inside a
word.
- [ ] Test: 10 sentences of 4 s with 1 s pauses → every passage starts at a sentence start and ends at a sentence
  end; kept length within 15–30 s; a 2 s pause inside is cut to 0.3 s; an "eh" between two words is removed; no range
  boundary falls between `word.start` and `word.end` of any kept word. Review Focus 5: `passages({}) == []` and the
  pipeline then uses `montage`.
- [ ] Fail, implement, pass. With Resolve open: `autoedit edit "Gesprek met Milan" --song <one> --grade basis
  --soort praat`; listen is not possible for the agent, so check `_passages.json` reads as whole sentences and the
  timeline cuts sit in the gaps of the waveform image (`ffmpeg showwavespic`). Say plainly in the PR that the sound
  was not listened to.
- [ ] `taste.yaml` rule `no_cut_mid_sentence` ("er werd telkens geknipt midden in een gesprek"),
  `enforced_by: 'autoedit/talk.py: never inside a word'`. `CHANGELOG.md`, `CLAUDE.md`. Commit. PR.

---

## Phase 6 — The website shows the flow (branch `feature/website-nieuwe-edit`)

### Task 6.1: API
**Files:** Modify `webapp/app.py`, `webapp/host.py` (`ALLOWED["autoedit"]` gains `edit`, `grades`),
`webapp/query.py`; Test `tests/webapp_edit_test.py`.
**Interfaces:** `GET /api/edit/options?project=<name>` → `{songs: [...], grades: [...], brief: {...}, problems: [...]}`;
`POST /api/projects/<name>/edit` with the brief as JSON → validates with `brief.problems`, queues
`autoedit edit <name> …` as one job, returns `{job}` or `400 {problems}`.
- [ ] Test with Flask's test client and a fake host that records commands: options lists `basis`; POST without a song
  → 400 with a Dutch problem; a valid POST queues exactly one command whose argv contains `edit`, the project name,
  `--song`, `--grade`; a project name starting with `-` or containing `..` → 400.
- [ ] Fail, implement, pass, commit.

### Task 6.2: The page
**Files:** Modify `webapp/static/app.js` (new view `nieuw`, the project page's primary button goes there),
`webapp/static/index.html` (menu item *Nieuwe edit* first), `webapp/static/style.css`.
- [ ] One screen: shoot (project dropdown), **Liedje**, **Ritme** (Op de beat / Rustig), **Lengte** (Kort 10 s /
  Normaal 20 s / Lang 30 s), **Kleur** (his PowerGrades, then *Basis*), and one button **Maak edit**. Problems from
  the API show next to the field they belong to. After Start: the job log, then the result with the render, the
  before/after picture and the line "In Resolve staan twee tijdlijnen: de edit en wat is weggeknipt."
- [ ] Verify in the browser pane with the `preview_start` dev server (`.claude/launch.json`): load the page, pick
  values, press the button with a fake project, read the network request body, check phone width (375 px). Screenshot
  in the PR.
- [ ] Commit.

### Task 6.3: Safer website
**Files:** Modify `webapp/app.py`; Test `tests/webapp_guard_test.py`.
- [ ] Test, then implement: a request whose `Host` is not `127.0.0.1:5080`, `localhost:5080` or the Tailscale
  address gets 403; a POST with an `Origin` from another site gets 403; `ai/generate` refuses unless a quote for the
  same project, model and prompt was made in this server process within 10 minutes (replace the client flag at
  `app.py:318`); `/api/file` refuses paths under `data/` except `data/webapp_jobs/`.
- [ ] Pass. `webapp/README.md`, `CHANGELOG.md`. Commit. PR.

---

## Phase 7 — Clean-up that needs no decision (branch `chore/opruimen`)

### Task 7.1: Dead code and dead knobs
**Files:** Delete `autoedit/dashboard.py`, `autoedit/watch.py`; Modify `autoedit/__main__.py` (remove `dashboard`,
`watch`, `repurpose`, `import`, `run`, `project`: `edit` replaces the last two), `autoedit/pipeline.py`
(`repurpose`), `autoedit/projects.py` (`import_card`), `autoedit/aigen.py` (`generate_audio`),
`autoedit/planner.py` (`make_plan`, `Grid`, `_cut_points`, `Plan.from_json`), `styles.yaml` (fitness, travel,
lifestyle, fashion), `config.yaml` and `inventory.yaml` (the dead knobs listed in the notes §3), `webapp/app.py`
(the `import` route), `webapp/host.py`.
- [ ] Before each deletion: `Grep` for callers in `autoedit/`, `webapp/`, `VIDEO_EDITING_SYSTEM/`, `tests/`,
  `tools/`, `.claude/`. A caller outside this list → leave the code and note it in the PR.
- [ ] Runner green, `doc_check` green after each group. One commit per group.

### Task 7.2: Docs that are no longer true
**Files:** `CLAUDE.md`, `README.md`, `setup/README.md`, `config.yaml:115`, `docs/decisions/0008-python-env-outside-documents.md`.
- [ ] Remove "faster-whisper is blocked". Mark local Wan as "needs a ComfyUI you start yourself" (Comfy Desktop is
  uninstalled); keep the Muapi money rule word for word. Replace "commit everything to `main`" with the branch + PR
  rule. Remove the old dashboard. `doc_check`. Commit. PR.

---

## Phase 8 — Only after Timon's yes on the three open points

### Task 8.1: Record the decisions
**Files:** Create `docs/decisions/0016-one-editor-resolve.md`, `docs/decisions/0017-studio-is-juict-only.md`; Modify
`docs/decisions/README.md`, mark 0013 and 0014 as amended, `docs/README.md` ("Which editor for which goal").
- [ ] Write each record from the spec (D1, D11) with Timon's own words as the reason. `doc_check`. Commit.

### Task 8.2: Studio keeps only JUICT (if yes on point 2)
**Files:** Modify `webapp/artifact/studio.html` (remove routes `#/`, `#/p/…`, `#/ssd`, the dead tab code at
`:3118-3320`, the actions `plan`, `preview`, `render`, `qa`, `grade`, `goedkeuren`, `stills`, `ssd-*`, `uitleg`;
either implement or remove the `juict-resolve` / `juict-montage` buttons: ask Timon which), `webapp/studio.py`,
`.claude/skills/studio-session/SKILL.md`, `tests/studio_test.py`.
- [ ] Tests first for what remains (`juict-film` parse, PDF list). Remove. Runner green. Publish the Artifact only
  after Timon's yes on the changed page; read the live page in full before replacing it.

### Task 8.3: Archive the cine montage (if yes on point 1)
**Files:** Move `VIDEO_EDITING_SYSTEM/` and `EDITING_DNA_PACKAGE/` to `archive/`; Modify `webapp/app.py`,
`webapp/static/app.js` (remove the cine tab), `webapp/host.py`, `autoedit/library.py:449` (`card` proposes
`autoedit edit`), `tools/doc_check.py` (paths), `.claude/skills/cine-montage/` (move to `archive/`), `CLAUDE.md`.
- [ ] `Grep` for `engine` and `cine_montage` first; projects on disk keep their `cine_montage/` folders untouched.
  Runner and `doc_check` green. Commit. PR.

---

## Order and size
| phase | depends on | rough size |
|---|---|---|
| 0 Baseline | — | small |
| 1 Brief + `edit` | 0 | medium |
| 2 Moments | 1 | large (the core of the redesign) |
| 3 Song section | 1 | small |
| 4 PowerGrade | 1 | medium, has a spike |
| 5 Talking | 2 | large |
| 6 Website | 1, 4 | medium |
| 7 Clean-up | 1 | medium |
| 8 Gated | 6, 7 and Timon's answers | medium |

Phases 2, 3 and 4 touch different files apart from `planner.py` and `builder.py`; run them one after another, not in
parallel. After every phase: show Timon the Beef Tartaar edit again and ask for his verdict before the next one.
