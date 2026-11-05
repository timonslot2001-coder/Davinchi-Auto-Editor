---
name: flow
description: "/flow — edit a video in DaVinci Resolve from a few buttons: pick the clips (project or folder), then style, colour, format and captions, and AutoEdit builds, renders and checks the edit, ending with a before/after picture. Use when Timon types /flow or asks to \"edit my video in Resolve\" with choices, like the Flow plugin."
---

# /flow — edit my video in DaVinci Resolve

The button version of AutoEdit (`autoedit run`): Timon chooses, AutoEdit does the work in Resolve. Keep every message
short; the buttons are the conversation.

## 1. Which clips
Run `PY -m autoedit projects` (PY = `C:\Users\Timon\.aev\Scripts\python.exe`, `PYTHONIOENCODING=utf-8`). Ask with
**one** AskUserQuestion: "Welke video?", options = the 3 newest projects that have clips (label = project name,
description = clips + song), Timon can type a folder path under *Other*. A project means its `clips/` folder
(`Videos/AutoEdit Projects/<name>/clips`); a typed path must be an existing folder with video files.

## 2. The choices (one AskUserQuestion, four questions)
| header | question | options (first = default) | flag |
|---|---|---|---|
| Stijl | Welke stijl? | Cinematic (huisstijl) · Travel · Lifestyle · Fitness (Fashion under *Other*) | `--style cinematic / travel / lifestyle / fitness / fashion` |
| Kleur | Welke kleur? | Film (huisstijl) · Natural · Orange & Teal · Laat zo | `--look reference_film / daylight / orange_teal / none` |
| Formaat | Welk formaat? | 9:16 (TikTok/Reels) · 16:9 | `--aspect 9:16 / 16:9` |
| Captions | Ondertitels? | Ja · Nee | `--captions` when Ja |

"Laat zo" still converts S-Log3 to normal colours (the camera's log footage is grey otherwise); it only skips the
film look. Talking-head styles (cutting pauses and slips) are not built yet: say so if Timon asks for them.

## 3. EDIT THE VIDEO
Run in the background (it takes minutes; Resolve must be open and not showing a dialog such as an update notice):
```
PY -m autoedit run "<clips folder>" --style <s> --look <l> --aspect <a> [--captions]
```
Add `--music <song>` only when the project has a song set (`song:` in project.yaml) or Timon names one; otherwise
AutoEdit's default applies. With captions, Resolve transcribes the timeline audio (music is ducked under speech).

## 4. Before showing it (CLAUDE.md: always rewatch)
Read `<base>_review.json`, look at `<base>_review.png` and `<base>_before_after.jpg` (paths in the run's JSON output).
Check every accent has a reason; with captions, that the lines are readable and in time. Fix and re-run once if
needed. Then send Timon the before/after picture (SendUserFile) and the render path, in two or three sentences.

## Never
Approve or post anything, spend money (no Muapi), or touch the cine-montage or client-film tracks from here.
