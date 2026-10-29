# Client edits

Scripts for one-off work for a client. They stay apart from the editors for Timon's own channels (AutoEdit, cine
montage), so client feedback never changes the house style. How this kind of work is done: `CLAUDE.md` → *Client films*
and decision [0010](../docs/decisions/0010-client-films-stay-intact.md).

## What is (and is not) in here
- In git: the scripts and the motion design code. They name the client's files, but never contain them.
- Not in git (decision [0007](../docs/decisions/0007-public-repo-no-third-party-material.md)): the client's footage,
  logos, photos, music and exports. Those stay in `Videos\AutoEdit Projects\<project>\`.
- No personal data of the people in the film (names, roles) in the scripts.

## Projects
| folder | client / film | final | inputs read from the project folder |
|---|---|---|---|
| [juict_aftermovie/](juict_aftermovie/edit.py) | JUICT, Compain AI aftermovie | v12 (2026-10-28): original film + JUICT intro/outro, booklet shot removed, 3 photo snaps | `source/Aftermovie V2.mp4`, `branding/juict_logo_white_red.png`, `photos/photo_1.jpg`..`photo_3.jpg`, FOUR Editors SFX |

Run, with the AutoEdit Python:
```
cd client_edits\juict_aftermovie
C:\Users\Timon\.aev\Scripts\python.exe edit.py                                   # → <project>\exports\JUICT_aftermovie_v12.mp4
C:\Users\Timon\.aev\Scripts\python.exe edit.py "<other project folder>" --out test.mp4
```
The repo script reproduces the delivered v12 (checked frame by frame and on the audio, 2026-10-29).

## Reusable parts
- `juict_aftermovie/brand_motion.py`, `brand_motion2.py`: the JUICT brand card (line field, slab, letter-by-letter
  logo, red bar, brackets, mono label, grain, layered wipe to footage). Colours and logo are JUICT's; for another brand,
  copy the folder and swap the logo file and the colour constants at the top of `brand_motion.py`.
- `Film.print_frame` in `juict_aftermovie/edit.py`: the photo snap (white print landing on the blurred shot).

## Adding a client project
1. Make a folder `client_edits/<client>_<film>/` with an `edit.py` that reads everything from the project folder.
2. Start from the client's original; change only what Timon names (decision 0010).
3. Before sending: compare frames and audio with the original after every cut, and look at a contact sheet.
4. Add a row to the table above, and the folder to `docs/README.md` if it gets its own document.
