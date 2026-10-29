# 0007 Public repo: no third-party material, toolchain listed by hash

- Status: accepted
- Date: 2026-10-27
- Source: Timon, "alle skills en plugins in de github repo zodat alles reproducable blijft"; the repo is public

## Context
Everything should be reproducible on a new PC, but the repo is public. Some of what the editor uses is licensed to Timon
(FOUR Editors packs, RAM `.drfx`). Some belongs to others (reference videos and their frames, songs from references,
client footage and logos). Some is secret (`.env`).

## Decision
- Own work goes in git: code, skills, the Auto Grade script, OFL fonts.
- Bought packs, reference material and client material stay out. `setup/toolchain.json` lists the packs by name and
  sha256, and `setup/install.ps1` restores them from Timon's own backup, checked by hash.
- Secrets live only in `.env` (gitignored) and are never echoed.

## Consequences
A new PC needs the pack backup next to the repo. Client edit scripts may name client files, but never contain the
footage, logos or music themselves.
