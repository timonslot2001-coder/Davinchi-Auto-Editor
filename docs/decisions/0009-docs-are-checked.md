# 0009 Documents are checked by a script

- Status: accepted
- Date: 2026-10-28
- Source: Timon, "Kan je dit met elk document doen wat je ooit hebt gemaakt" → "Binnen dit project."

## Context
Documents drifted away from the code: a rule was missing from a doc, a command was renamed, a number changed in the DNA.

## Decision
`tools/doc_check.py` (also run by `engine validate`) fails when a rule, number, command, path or document-map entry no
longer matches the code or `style_dna.json`. Every plan runs `engine/style_checks.py`, which applies the same idea to
edits.

## Consequences
A document change is only done when `python tools/doc_check.py` passes. A new document must be added to
`docs/README.md`, and a new decision to `docs/decisions/README.md`.
