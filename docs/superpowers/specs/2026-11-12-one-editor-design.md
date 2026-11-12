# Design: one editor, one flow

Status: **proposal, waiting for Timon's yes.** Evidence: [2026-11-12-one-editor-notes.md](2026-11-12-one-editor-notes.md).
Plan: [../plans/2026-11-12-one-editor.md](../plans/2026-11-12-one-editor.md).

## Intent
AutoEdit does one thing well: Timon picks a shoot, makes four choices, and gets a Resolve timeline in which the bad
footage is already gone, the cuts follow the music without breaking a moment, and his own PowerGrade is on. He does a
last tweak in Resolve and posts. Everything that does not serve that flow is removed, frozen, or kept on a clearly
separate track.

## The flow (the only one for his own videos)
1. **Kies** — shoot (project or folder) and four choices: *song*, *rhythm* (`beat` or `rustig`), *length*
   (`kort` 10 s, `normaal` 20 s, `lang` 30 s), *grade* (one of his PowerGrades, or `basis`). The choices are remembered
   per project, so a second edit is one click.
2. **Knip** — the editor drops unusable moments, keeps filming order, fits the selection to the chosen part of the
   song.
3. **Kleur** — the chosen PowerGrade goes on every clip. The editor never picks a look.
4. **Klaar** — two timelines in Resolve: the edit, and `… · weggeknipt` with the doubtful moments. A 9:16 render and the
   review files. Posting stays a separate, approved step.

## Decisions
Each line is my call unless marked *(Timon)*.

**D1. One editor: AutoEdit in Resolve.** Only Resolve gives him the final tweak and his PowerGrade *(Timon)*. The cine
montage engine is frozen: no new work. Its useful parts move into `autoedit/` (D7). It is archived only after Timon
says yes (plan phase 6).

**D2. One command and one brief.** `autoedit edit <project|folder>` replaces `run` and `project` for his own videos.
The brief is a small dataclass, stored under `edit:` in `project.yaml`:

| field | values | default |
|---|---|---|
| `song` | file name or part of it | none: the command stops and lists the songs. No random song. |
| `song_start` | seconds, or `auto` | `auto` |
| `rhythm` | `beat`, `rustig` | `rustig` |
| `length` | `kort`, `normaal`, `lang` | `normaal` |
| `grade` | a PowerGrade name, or `basis` | none: the command stops and lists the grades |
| `kind` | `auto`, `montage`, `praat` | `auto` |
| `aspect` | `9:16`, `16:9` | `9:16` |

**D3. Cutting by moments, not by clips** (`autoedit/moments.py`). Every clip is scored in 0.5 s windows on shake,
global camera motion, sharpness and speech. Rules, in this order:
- *sure drop*: the first and last 0.5 s of a clip (pressing record); shake above `stabilization.shake_threshold` × 1.5;
  repositioning (high global motion together with low sharpness for ≥ 0.5 s); too dark.
- *doubt drop*: no motion and no speech for ≥ 2 s; shake between the threshold and × 1.5; a near-duplicate of the
  moment before it.
- everything else is *keep*. Kept runs shorter than the shortest shot of the chosen rhythm are doubt drops.
The planner picks only from kept runs. Motion is no longer rewarded in the pick; a calm, sharp moment wins.

**D4. Doubtful cuts are findable.** A second timeline `<edit name> · weggeknipt` holds every doubt drop in filming
order, each with a marker naming the reason (`stil`, `schokkerig`, `dubbel`, `te kort`). Sure drops are only listed in
`<base>_cuts.json`. Nothing is shown to Timon for approval *(Timon: removed without review)*.

**D5. Filming order** *(Timon)*. Clips sorted by recording time; inside a clip, moments in time order. The last shot
is the best late moment of the last clip, clean (already built on `fix/rustiger-knippen`).

**D6. Rhythm and length.**
| | `beat` | `rustig` |
|---|---|---|
| shot length | 2 beats; 1 beat allowed on a hit, never under 0.6 s | 1 bar (4 beats); never under 2 beats or 0.8 s |
| louder parts cut faster | yes | no |
Length sets the target: 10 / 20 / 30 s, ended on a bar. A cut never lands within 0.25 s of a motion peak.

**D7. The part of the song around the drop.** Port `best_song_start` from `VIDEO_EDITING_SYSTEM/engine/planner.py:114`
into `autoedit/music.py`, working on `MusicAnalysis`. `song_start: auto` uses it; a number overrides it. The music bed
starts there (`plan.music["offset"]`).

**D8. Grade: his PowerGrade, by name.** PowerGrades live as `.drx` files in `data/powergrades/` (he exports each once
from the Resolve gallery: right-click the still → Export). `autoedit grades` lists them; `grade: <name>` applies that
file to every log clip with `ApplyGradeFromDRX`. No Odyssey-specific node code, no LUT on top, no black-and-white accent
that overwrites node 1. `grade: basis` is the neutral fallback: S-Log3 → Rec.709 with exposure and white balance
measured per clip, no look. If the Resolve API on his version can read the PowerGrade album, `autoedit grades --sync`
exports the stills for him; the folder stays the source of truth either way.

**D9. Talking videos** (`kind: praat`, chosen automatically when most kept footage has speech).
`autoedit/speech.py` transcribes with faster-whisper (the local large-v3-turbo model, audio fed as an array) into words
with times, grouped into sentences. `autoedit/talk.py` builds candidate passages of whole sentences, 15–30 s, removes
pauses over 0.6 s and filler words, and ranks them (fewest restarts and fillers, most speech per second). The best one
becomes the edit; the top three are written to `<base>_passages.json` so another can be chosen with
`--passage 2`. Cuts fall only between sentences or in a removed pause. Music is ducked under the voice.

**D10. Effects stay small.** The director stays as it is on the branch (`accents_scale: 0.5`, self-review can only
lower). No new effects in this redesign. In `praat` the director is off except for the title.

**D11. One UI: the website.** It gets one page, *Nieuwe edit*, with the four choices and a Start button, and loses the
cine path when D1's archive step happens. The Studio keeps only JUICT (Video's, Werkinstructies, Promptgenerator);
its project, SSD and colour pages go. That removal waits for Timon's yes (plan phase 5).

**D12. Tests without Resolve.** Everything up to the `Plan` is tested on synthetic clips and songs. One runner,
`python tools/run_tests.py`, runs every test script. The Resolve build keeps its by-eye review.

**D13. Clean-up.** Delete `dashboard.py`, `watch.py`, `repurpose`, `import_card`, the four legacy styles with
`make_plan`, the dead yaml knobs, the Docker/worker path. Fix the three bugs and the seed. Add a Host/Origin check to
the website, check the AI quote on the server, validate names before they reach a command line.

## Non-goals
- No new effects, no new UI, no new track.
- No change to client films, JUICT films, offload, photos, posting or AI shots beyond what D13 names.
- No cloud, no accounts, no paid services.
- The "word behind the head" effect is not part of this; it can follow as an option of `praat`.

## Anti-goals
- An edit that looks like the previous one with other footage.
- A cut in the middle of a movement or a sentence.
- The editor choosing a look.
- A second way to do the same thing.

## What stays untouched
`client_edits/`, the `juict-edit` skill, the Studio's JUICT section and `juict-film`, `offload.py`, `library.py`,
`photos.py`, `publish.py`, `social.py`, `aigen.py`, `fx.py`, `export.py`, `proxy.py`, `inventory.yaml`, the rules in
the notes §7.

## Open points for Timon
1. Archive the cine montage (D1)? It is the approved montage style of 2026-10-25, 16:9 only.
2. Strip the Studio down to JUICT (D11)?
3. The names `kort / normaal / lang` = 10 / 20 / 30 s: right?
