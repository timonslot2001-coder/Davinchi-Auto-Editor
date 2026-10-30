# Documentation map

Which document answers which question. Sorted by what you want to do (after the Diátaxis split: learn, do a task, look
something up, understand why). Every tracked document is listed here; `python tools/doc_check.py` fails when one is
missing.

## Which editor for which goal
Timon's own channels come first; client work runs on a separate track so it never changes the house style.

| goal | editor | output |
|---|---|---|
| Own Instagram Reels / TikTok | AutoEdit, `--aspect 9:16` (or `aspect: "9:16"` in project.yaml) | 9:16 + 4:5 feed copy, captions, queued for approval |
| Own YouTube / 16:9 videos | AutoEdit (house style default) | 16:9 |
| Own montage posts (travel, food, a place) | Cine montage (P_CINE_MONTAGE) | 16:9 montage after storyboard approval |
| How-to / onboarding videos | AutoEdit explainer mode | step-by-step video from `script.yaml` |
| A client's film (event, company) | a script in [client_edits/](../client_edits/README.md) | the client's film, intact + only the asked changes |

## I want to get something done (how-to)
| question | open |
|---|---|
| Do everything from a website (also in Docker Desktop) | [webapp/README.md](../webapp/README.md) |
| Edit a shoot into a TikTok/Reel or 16:9 video | [README.md](../README.md) → *Edit a shoot* |
| Make a cine montage in the approved style | [VIDEO_EDITING_SYSTEM/README_START_HERE.md](../VIDEO_EDITING_SYSTEM/README_START_HERE.md) |
| Re-edit a client's finished film (intro/outro, remove a shot, photo snaps) | [client_edits/README.md](../client_edits/README.md), [CLAUDE.md](../CLAUDE.md) → *Client films* |
| Make an AI shot (free local, or paid Muapi) | [README.md](../README.md) → *AI shots* |
| Post to Instagram / TikTok | [README.md](../README.md) → *Posting* |
| Set up a new PC | [setup/README.md](../setup/README.md) |

## I want to look something up (reference)
| question | open |
|---|---|
| Every command and option | [README.md](../README.md) → *Command reference* |
| The cine montage rules and numbers | [EDITING_DNA_PACKAGE/STYLE_DNA.md](../EDITING_DNA_PACKAGE/STYLE_DNA.md) (source: `style_dna.json`) |
| Which fonts/components exist, and their rights | [EDITING_DNA_PACKAGE/ASSET_LIBRARY.md](../EDITING_DNA_PACKAGE/ASSET_LIBRARY.md) |
| What is measured vs estimated | [EDITING_DNA_PACKAGE/ACCURACY_AND_GAPS.md](../EDITING_DNA_PACKAGE/ACCURACY_AND_GAPS.md) |
| The approved style and its limits | [VIDEO_EDITING_SYSTEM/STYLE_SELECTION.md](../VIDEO_EDITING_SYSTEM/STYLE_SELECTION.md) |
| Where the engine stands, what is tested | [VIDEO_EDITING_SYSTEM/PROJECT_STATUS.md](../VIDEO_EDITING_SYSTEM/PROJECT_STATUS.md) |
| Upload limits, frame rate, bitrate, safe zones per platform | [PLATFORM_SPECS.md](PLATFORM_SPECS.md) |
| Trends, hooks, hashtags per niche | [TRENDS_REPORT.md](../TRENDS_REPORT.md) (data: `trends.yaml`) |
| A word you don't know (Dutch ↔ English) | [GLOSSARY.md](GLOSSARY.md) |
| Settings | `config.yaml`, `styles.yaml`, `inventory.yaml`, `taste.yaml` (each explains itself in its header) |

## I want to understand why (explanation)
| question | open |
|---|---|
| Why the montage cuts the way it does | [EDITING_DNA_PACKAGE/EDITING_PSYCHOLOGY.md](../EDITING_DNA_PACKAGE/EDITING_PSYCHOLOGY.md) |
| How the editor learns from your feedback | [README.md](../README.md) → *How it learns* |
| Why something was decided the way it was | [decisions/](decisions/README.md) |
| What changed and when | [CHANGELOG.md](../CHANGELOG.md) |

## Start pages and records
| file | what |
|---|---|
| [EDITING_DNA_PACKAGE/README_START_HERE.md](../EDITING_DNA_PACKAGE/README_START_HERE.md) | start of the style package (Stage 1) |
| [EDITING_DNA_PACKAGE/CLAUDE_CODE_IMPLEMENTATION_PROMPT.md](../EDITING_DNA_PACKAGE/CLAUDE_CODE_IMPLEMENTATION_PROMPT.md) | the Stage 2 brief, kept as a record |
| [.claude/skills/cine-montage/SKILL.md](../.claude/skills/cine-montage/SKILL.md) | Claude's working instructions for a cine montage |
| [.claude/skills/juict-edit/SKILL.md](../.claude/skills/juict-edit/SKILL.md) | Claude's working instructions for a JUICT / client film |
| [CLAUDE.md](../CLAUDE.md) | how Claude works in this repo (loaded every session) |

## Keeping the docs true
- After changing a document, `style_dna.json` or a command: `python tools/doc_check.py` must pass.
- A decision that is hard to reverse gets a record in [decisions/](decisions/README.md); a change you would notice gets a
  line in [CHANGELOG.md](../CHANGELOG.md); feedback on an edit goes into `taste.yaml` (AutoEdit) or `EDITING_PSYCHOLOGY.md`
  §10 (cine montage).
