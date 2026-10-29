# 0011 Own videos stay at 25 fps

- Status: accepted
- Date: 2026-10-29
- Source: Timon, "Oh nee maar dan kan je het gewoon op 25 fps laten"

## Context
Instagram's help centre says Reels should be at least 30 fps. The upload APIs of Instagram and TikTok accept 23-60 fps.
AutoEdit and the cine montage work at 25 fps (`config.yaml`).

## Decision
Stay at 25 fps:
- The A6700 films 50p, exactly 2× 25. Converting 50p to 30 fps drops frames unevenly, and motion stutters.
- The director only allows slow motion on footage with about 2× the timeline rate (taste rule `must_look_good`). 50p
  on a 25p timeline gives a smooth half-speed slow-mo; on 30p it would be switched off.
- Mains power in the Netherlands is 50 Hz, so indoor lights do not flicker at 25/50 fps.

## Consequences
Uploads work as they are. Revisit only when footage is shot at 30p/60p (e.g. a phone set to NTSC rates).
