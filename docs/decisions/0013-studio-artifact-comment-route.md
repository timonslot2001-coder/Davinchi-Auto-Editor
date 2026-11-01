# 0013 The Studio Artifact talks to the PC through comments, with one executing session

- Status: accepted
- Date: 2026-11-01
- Source: Timon, "ik wil gewoon het design verbeteren en functioneel maken"; design
  [2026-11-01-studio-artifact-design.md](../superpowers/specs/2026-11-01-studio-artifact-design.md)

## Context
Timon wants to run the cine montage from the Claude app on his phone or laptop. The local web app only works on the
Resolve PC itself. A claude.ai Artifact cannot reach the PC directly, and calling the Claude Code Remote connector from a
page fails ("connector access isn't confirmed"). A test page proved that a button can send a comment to Claude
(`sendToClaude`) and that a Claude Code session on the PC receives it, but also that every watching session answers.

## Decision
- Every Studio button sends one comment `[studio] actie=... project="..."`. The page never writes the db itself.
- Exactly one Claude Code session on the PC executes them: skill `studio-session`, started with
  `start-studio-sessie.bat`. Any other session that publishes the page stops watching it right after publishing.
- That session runs only `python -m webapp studio`, which validates the text, dedupes the thread and maps it to one
  `engine` command; results (state, stills, LUTs, previews) go back through the Artifact's db and assets.
- The db is readable by whoever can open the page and writable only by the owner (Timon's sessions).

## Consequences
- The PC must be on, with the Studio session open, for buttons to work; the page says so and keeps the grade preview
  working on stills already uploaded.
- Approval gates stay as they are: approving needs Timon's own words, and a grade change needs a new approval.
- The Studio's link lives in `start-studio-sessie.bat`; publishing the page under another account means changing it there.
