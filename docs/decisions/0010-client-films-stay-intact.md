# 0010 A client's finished film stays as delivered

- Status: accepted
- Date: 2026-10-28
- Source: Timon on the JUICT film, "de orginele bedrijfsfilm mag je intact houden, enkel het IT Synergy boekje weglaten
  ... geen ondertitels, niks" (`taste.yaml` → `client_film_intact`)

## Context
Versions 1–10 of the JUICT aftermovie re-cut the interview, replaced a speaker, and added subtitles and a name card.
Timon wanted the original film instead, with only the JUICT branding and the photo snaps.

## Decision
On a client's finished film:
- swap in our brand intro and outro;
- remove only the shots Timon names, in whole beats, so the music stays in time;
- add only what he asks for (here, the photo snaps);
- verify that picture and sound still line up with the original after the cut.

No subtitles, name cards or interview changes unless he asks for them.

## Consequences
The script for such a film stays small and starts from the original file. The how-to is in `CLAUDE.md` → *Client films*.
