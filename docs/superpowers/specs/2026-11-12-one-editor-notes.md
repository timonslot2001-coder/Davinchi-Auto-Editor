# Notes: the whole program, read on 2026-11-12

Read-through of `main` at `15aadb1` (four parallel reviews: core editor, website + Studio, other tracks, docs + history)
plus the unmerged branch `fix/rustiger-knippen`. These notes are the evidence for
[2026-11-12-one-editor-design.md](2026-11-12-one-editor-design.md). Nothing was run for these notes.

## 1. What Timon asked for (brainstorm 2026-11-06, his words condensed)
- Pains: **colour grading** and **cutting away unnecessary footage** (very shaky bits, repositioning the camera, dead
  moments). Removed without review; doubtful cuts removed but findable in Resolve.
- Chosen **before** cutting: the song, the rhythm (on the beat or calmer), and which of **his own PowerGrades** to use.
  He has several, usually uses the same one, and the editor never chooses.
- Output: one Instagram/TikTok video, postable after a last tweak in Resolve. About 15–20 s; short / normal / long.
  The editor picks the part of the song around the drop; he can override. Never the whole song.
- Shots stay in the order he filmed them: select, do not reorder.
- Never template-like. A cut never breaks a moment. Fewer effects, calm cutting.
- Talking videos must work: the strongest moment (a complete thought, 15–30 s), no cut mid-sentence, pauses and "eh"
  removed, music low under the voice.
- "Ik snap niet waarom je telkens wat nieuws wilt brouwen": improve what exists, stop building around it.

## 2. What exists
| part | size | what it is |
|---|---|---|
| `autoedit/` | ~5,300 lines, 31 CLI commands | the Resolve editor: analyse → plan → director (accents) → build → render → finish → self-review → queue |
| `VIDEO_EDITING_SYSTEM/engine/` | ~1,880 lines | a second editor ("cine montage"): EDL → storyboard → approval → ffmpeg render, 16:9 only, no Resolve |
| `EDITING_DNA_PACKAGE/` | 42 files | style data for the cine montage; code reads 3 of them |
| `webapp/` website | `app.py` 407, `app.js` 765 | local site on port 5080: projects, cine path, SSD, photos, queue, music, AI shots |
| `webapp/` Studio | `studio.html` 3,329, `studio.py` 911 | claude.ai Artifact + a Claude session on the PC that executes its buttons |
| `client_edits/` | ~690 lines | scripts per client film (separate track, stays) |
| logistics | `offload.py`, `library.py`, `photos.py`, `projects.py` | card → SSD, thumbnails, clip picking, LightCraft looks |
| posting | `publish.py`, `social.py`, `tiktok_auth.py` | queue, Instagram, TikTok |
| AI shots | `aigen.py`, `localgen.py` | paid Muapi, local Wan through ComfyUI |
| docs | 41 documents, 15 decision records | plus `tools/doc_check.py` |

History: 170 commits in 24 days, 45 of them on one day. Three UIs and two editors were added in that time.

## 3. The core editor against the wishes
| wish | today (`main`) | gap |
|---|---|---|
| Remove shaky / repositioning / dead footage | Whole clips rejected only when dark, blurry, under 0.8 s or a duplicate take (`analyze.py:237-276`). Shake is one number per clip and only switches on stabilisation. Segment score **rewards** motion, so repositioning scores well. | No per-moment detection at all. |
| Doubtful cuts findable in Resolve | Removed footage leaves no trace. | Missing. |
| Song chosen first | `--music`; without it a **random** song (`pipeline.py:31`). | Random default must go. |
| Part of the song around the drop | House style always starts the song at 0.0 (`planner.py:492`); the drop is only logged. `best_song_start` exists in the *other* editor (`engine/planner.py:114`). | Port it. |
| Rhythm choice | None. | Missing. |
| Short / normal / long | `length_s: 13` (20 on the branch). | Missing. |
| His own PowerGrade | Default is a baked LUT the editor picks. The PowerGrade path takes one label from config and runs Odyssey-specific node hacks on any grade (`builder.py:125-154`). | No choice per edit, no list, hacks in the way. |
| Filming order | Shots follow an ARC role list from tags. Fixed on the branch (`chronological: true`). | Branch not merged. |
| Calm, few effects, clean ending | Fixed on the branch (min 2 beats, `accents_scale 0.5`, no leak at the end). | Branch not merged. |
| Brighter, less orange | Fixed on the branch (exposure + white balance measured per clip). | Branch not merged. |
| Talking videos | `has_speech` is an FFT guess; no transcript, no sentences. The house style ignores speech and drops clip audio when there is music (`builder.py:212`). Ducking is unreachable (`planner.py:135` vs `builder.py:351`). | Missing. faster-whisper and the large-v3-turbo model work on this PC (tested 2026-11-06). |

Other findings in the core:
- **No tests** for analyze, planner, director, builder, review, export, sfx, pipeline. Only `grade` is covered.
- `Plan` / `Shot` are pure data written to `<base>_plan.json`: the right seam to test without Resolve.
- `--seed` never reaches the planner (`pipeline.py:55-139`), the SFX library is unseeded, `hash(str)` differs per run.
- Bugs: `review.py:125` (`"16" in base` is true for 9:16 too); duplicates are dropped silently (`pipeline.py:48-51`);
  `builder.py:395` bare `next()`.
- Dead yaml knobs: `camera.log_profile`, `captions.burn_in`, `branding.watermark`, `branding.outro`, `format.primary`,
  `posting.require_approval`, `posting.tiktok_mode`, `budget.quiet_start_s`, `budget.keep_last_shot_clean`, `sfx_at`,
  `sfx_per_step`, `effects.pop_in`; four legacy styles and `make_plan` are reachable only through `--style`,
  `repurpose` and `watch`.
- Solid, keep: analysis cache and frame reader, `MusicAnalysis`, `Plan`/`Shot`, `fx.commit`, `export.loudnorm`/`qc`,
  `proxy.py`, `media_prep.music_bed`, `grade.py` cube maths, the builder's frame-exact placement, the director's
  budget/cooldown model, the review contact sheet.

## 4. Two editors
`autoedit/` and `engine/` duplicate clip analysis, beat detection, song choice, planning, story order, QA and approval.
They share only `autoedit/grade.py`. The cine montage cannot give Timon a Resolve timeline or his PowerGrade, and is
16:9 only. Worth keeping from it: `best_song_start`, `order:` / `skip:` from `project.yaml`, the storyboard idea.

## 5. Three user interfaces
- Old dashboard (`autoedit/dashboard.py`): superseded, still documented.
- Website: covers every workflow except JUICT films. One process, one queue, no tokens.
- Studio: needs five things alive at once (artifact, a kept-alive Claude session, exactly one watcher, `git pull`
  before every comment, a detached worker) and costs a Claude turn per click. Decision 0014 froze it on 2026-11-02;
  the JUICT section was built there a week later. For JUICT films it is the right place: making the film *is* Claude work.
- Studio buttons that can never work: `juict-resolve`, `juict-montage` (not in `studio.py` `ACTIONS`), `uitleg`.
  About 200 lines of dead tab code (`studio.html:3118-3320`).
- An edit takes ~8 clicks in either UI; in the Studio also ≥7 Claude turns and no song choice.
- Website and Studio queues do not know each other and can hit Resolve at the same time.

Security points (website): no Host/Origin check on port 5080; the paid-AI gate trusts a client flag (`app.py:318`);
URL names and prompts reach argv unchecked (`app.py:283,296,310`); `/api/file` serves all of `data/`; the laptop worker
binds to the LAN and writes a token into `.env`.

## 6. Docs and process
- Contradicted without a new record: 0014 (Studio frozen), 0013 (page never writes the db; approval in Timon's own
  words), `CLAUDE.md` "commit everything to main" (history is PR merges; the managed policy forbids it).
- Stale: ComfyUI Desktop (uninstalled) in `CLAUDE.md`, `README.md`, `config.yaml`, `setup/*`, `localgen.py`;
  "faster-whisper is blocked" in `CLAUDE.md`, `README.md`, decision 0008; the old dashboard in `README.md`.
- No test runner; 15 scripts run by hand; two thirds of test lines cover the Studio, website and logistics.
- `fix/rustiger-knippen` (6 commits, 2026-11-06) holds the newest taste feedback and is not on `main` or GitHub.

## 7. Rules that survive any redesign
No post or final render without Timon's yes · paid AI only after a quote and his yes for that shot · no third-party
material in the repo · client films stay intact · 25 fps · Python in `~/.aev` · `doc_check` passes · one house style ·
references feed the inventory, never the timeline · rewatch before showing · never `comp.Render()` · originals and
the card are never modified · phone only through Tailscale.

## 8. The five biggest sources of accidental complexity
1. Three UIs over one job.
2. Two editors with duplicate brains.
3. Scope that drifted away from editing (photos, remote desktop, trends, posting stats, local-LLM box).
4. Process heavier than the product: 41 documents, and a core editor without tests.
5. Machine-specific plumbing spread through code and docs.
