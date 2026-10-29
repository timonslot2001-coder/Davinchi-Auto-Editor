# EDITING PSYCHOLOGY — P_CINE_MONTAGE

Why each decision is made, when **not** to make it, and how to check it was made well. Machine-readable rules:
`style_dna.json → rules[]`; numbers come from there and from `STYLE_DNA.md`.

Every statement carries one label:
- **obs** — measured or seen on the 17 references (evidence in `STYLE_DNA.md`).
- **mech** — a general, well-known perception/film-editing mechanism that explains the observation. It is not measured on
  these references.
- **interp** — our reading of the editor's intent.
- **user** — decided or corrected by Timon on a real project (dated; see §10).

When labels disagree: **user > obs > mech > interp.**

## 0. Decision order for a new edit
1. **Length:** the song caps it (user). Pick the phrase that resolves, not just the first N seconds.
2. **Arc:** fix hook, title, body, wind-down and final shot on that length (§1).
3. **Roles:** give every shot a role and pick the best shot for each role (§4).
4. **Accents:** place them inside the budget (§5), Grid Flow last (§7).
5. **Check:** read the plan against the checks in §1/§2 and the failure table (§9), then show it at gate B.

## 0b. Where this style sits in Murch's six criteria
Walter Murch (*In the Blink of an Eye*) ranks what a cut must serve: **emotion > story > rhythm > eye trace > 2-D screen
plane > 3-D space**. When a cut cannot serve all of them, give up the lowest first. (mech; the ranking is widely quoted,
the exact weights often attached to it are second-hand and not used here.) In a music-only montage the six map onto
this document like this:

| Murch | in this style | where |
|---|---|---|
| emotion | the arc: hook tension → title payoff → momentum → exhale on the final shot | §1, §5 |
| story | place and order: establish, explore, resolve; day → night; process in chronological order | §1, §8 |
| rhythm | the pacing curve and the accent budget, phrase-level music fit (not beat-locked) | §5, §6 |
| eye trace | point of interest kept across hard cuts; brightness jumps only where an accent belongs | §3 |
| 2-D screen plane | whip direction follows the motion; Grid Flow moves left; screen direction on cuts | §2, §7 |
| 3-D space | spatial continuity: mostly irrelevant in a montage, so it is the first thing given up | — |

Consequence for conflicts that the rule priority does not settle: keep the cut that serves the higher criterion. A
perfectly beat-timed cut (rhythm) loses to a shot that lands the arc (emotion); a clean eye-trace match loses to the
right shot order (story).

## 1. The emotional arc
| phase | obs | mech | interp | check |
|---|---|---|---|---|
| **Hook** (0-1.3 s) | shortest shots of the video (first-fifth median 0.36 s; R04 opens with 11 × 0.12 s) | *information gap*: shots too short to read create a question ("where is this?"), and an open question holds attention. *Orienting response*: every cut is a small new stimulus, so a fast burst keeps re-triggering attention | hook before the scroll decision | first 1.3 s: ≥ 2 cuts and median shot ≤ 0.4 s, unless the calm-open exception applies |
| **Orientation** (title) | 11/17 name the place once, one accent colour, in at median 0.54 s, held ~1.3 s, hard cut in/out | closing the gap gives a small payoff, so the hook's tension resolves into a name | poster-like branding; a hard cut reads confident, an animated entrance reads like a template | exactly one title; on a steady establishing shot; hold ≥ 1 s; no accent on its first or last frame |
| **Exploration** (body) | shots 0.4-0.5 s, mostly hard cuts, an accent every ~2 s, sometimes a white-card chapter | *habituation*: a constant stimulus fades from attention, and a periodic change resets it. *Event segmentation*: viewers split a stream into events at changes of place or action, so accents placed there feel "right" | momentum with resets; the card is a texture change that resets attention without slowing down | accent rate ≈ 0.4-0.6 /s; accents land on scene/place changes, not inside a scene |
| **Resolution** (wind-down) | shots lengthen ~50 %; final content shot holds 0.5-2.3 s | *peak-end rule*: the end disproportionately shapes how the whole is remembered | leave a mood instead of a blur | last-fifth median ≥ 1.3 × first-fifth; final shot is the longest of the last five; no accent after the final cut |

Calm-open exception (obs: U2, R16): with fewer than ~8 usable detail shots, open on one held scenic shot instead. A
burst of repeats feels like a loop, not energy.

## 2. Rule table (trigger → response, with restraint)
| rule | trigger | response | why (label) | restraint (when NOT) | check | conf. |
|---|---|---|---|---|---|---|
| RULE_COLD_OPEN | start | 2-11 shots 0.1-0.4 s | information gap + orienting (mech) | thin footage → calm open | ≥ 2 cuts in 1.3 s; no shot repeated | high |
| RULE_TITLE | first strong establishing shot | poster title, 1 accent colour, ~1.3 s | answers the hook, brands (interp) | no single place/topic; never twice | 1 title; hold ≥ 1 s; readable on a phone | high |
| RULE_FLASH | place/scene change, music accent | 1 white frame | a "shutter blink" marks a new event (mech: segmentation) | never 2 within 1 s; never on title; not on dark→dark night cuts (feels like a glitch) | 1 frame; ≥ 1 s apart | high |
| RULE_WHIP | motion in outgoing shot | 3-6 f directional blur | continues motion across the cut, so the cut hides (mech) | static shots; blur against the motion direction | blur direction = pan direction | medium |
| RULE_CARD_SERIES | 3-6 related shots | white card, hard in/out | "photo album" chapter, texture reset (interp) | < 3 shots; > 2 per video; faces/round objects that would crop badly | shots share place/activity; proportions correct (user) | med-high |
| RULE_BW | one reflective moment | single B&W shot | contrast by subtraction: removing colour draws the eye (mech) | more than once; a shot whose point is its colour (food, sunset) | max 1 | medium |
| RULE_DECELERATE | second half | longer shots, scenic ending | exhale; peak-end (mech) | loop edits | pacing curve rises | high |
| RULE_ONE_ACCENT | always | one accent colour | poster consistency (obs) | — | one hue across title/cards | high |
| RULE_NO_TEXT_OVERLOAD | always | no captions | images + music tell it (obs) | user adds speech | no text besides title (+ labels) | high |
| RULE_GRID_FLOW | clean scene change in the body | 4×4 wipe left + exposure flash, 12 f | Timon's signature; scarce = recognisable (user, §7) | < 8 s edit; title, card, final shot; busy shots | 1× (2× if ≥ 16 s); ≥ 1 s from other accents | user-approved |

Conflict priority (from `style_dna.json`): NO_TEXT_OVERLOAD > ONE_ACCENT > TITLE > COLD_OPEN > DECELERATE > FLASH >
CARD_SERIES > WHIP > BW > GRID_FLOW.

## 3. What makes a cut invisible or felt
The style is 71 % hard cuts (obs). Most of them should not be noticed, and the few accents should be. These are the
levers (mech; standard editing practice, not measured on the refs):
- **Cut on motion.** A cut during movement is noticed least ("edit blindness"). Prefer cut points where the outgoing shot
  is still moving. This is also what makes T_WHIP work.
- **Keep the eye where it is.** At 0.4 s per shot there is no time to search the frame. Match the point of interest
  (subject, brightest area) roughly across the cut. A jump from the left edge to the right edge reads as an accent,
  wanted or not.
- **Brightness jumps are accents.** A big luminance change at a cut feels like a flash. Use it where an accent belongs
  (scene change) and avoid it where the cut should stay clean.
- **Avoid accidental jump cuts.** The same subject at nearly the same size and angle looks like a mistake. Change scale
  (wide ↔ detail) or angle between neighbours.
- **Alternate scale.** wide → detail → medium keeps the body readable. Three wides in a row flatten it.

## 4. Which shot goes where (role casting)
| role | best shot | avoid | why |
|---|---|---|---|
| cold open | details, textures, fast motion, strong colour | faces that need reading, wides that need time | must feel, not be read (obs: detail-heavy openers) |
| title shot | steady wide/establishing shot with calm sky/wall area for the type | handheld shake, busy frames | the title must read in ~1 s on a phone |
| body | alternate scale; scene changes at accents | many near-identical shots | §3 |
| card series | 3-6 shots of one place/activity, similar colour | wide horizons (lose most in the crop), faces near the edge | it should read as one album page |
| B&W | texture/shape shot, people, architecture | food, sunset, neon | colour is the point there |
| final shot | most scenic, calmest, best light, ideally slow motion | a shot already used; text; fast pans | peak-end: this image is the memory |

AI shots are support, not lead (user/learned, Smoke Sesh). They can look sharper than real footage and win the
scoring, so the planner caps them at 2 uses. Never use one as the title or final shot when real footage can fill it.

## 5. Visual attention budget
- obs: never more than one designed element on screen (title OR labels OR card); no flash/whip on a title frame.
- Per moment: **1 graphic + 1 transition accent**, platform overlays excluded.
- Accent rate: 0.48 non-hard transitions/s overall; up to ~1.5/s inside the cold open; ≤ 0.3/s in the wind-down.
- Clean stretches are intentional (obs: R04 17-26 s, R16). mech: habituation works both ways, so accents only stay
  strong if they are scarce.

Worked example, 15 s edit (≈ 30 shots):

| part | time | shots | accents |
|---|---|---|---|
| cold open | 0-1.2 s | 4-6 | 1-2 flashes |
| title | ~1.2-2.5 s | 1-2 | none on the title frames |
| body | 2.5-11.5 s | ~18 | 3-4 flash/whip, 1 Grid Flow, optional card series |
| wind-down + final shot | 11.5-15 s | 5-6 | 0-1 |

## 6. Music relationship (honest finding)
obs: cut times are not closer to beats/onsets than random times (z ≈ 0.06; only U2/R04/RB sync).
interp: these editors cut to **phrase energy and shot motion** rather than to every beat; reposting may also blur sync.
Decisions:
- Build pace from the shot-length curve. Snap a cut to a strong onset only when it is within one or two frames. Never
  stretch a shot to hit a beat.
- Where it is free, put structure on phrase boundaries: title in on a downbeat or phrase start, final cut on the last
  phrase. mech: a structural change that lands with the music feels intended.
- The song caps the length (user). A 13 s song gives a 13 s edit; say so at gate B instead of looping the music.
- Music fades with the final hold (the engine does this). Never end on a hard audio cut mid-phrase.

## 7. Grid Flow — why rare, and where (user, 2026-10-26)
Not from the references: it is Timon's own transition (4×4 wipe left, per-tile exposure flash, white grid lines,
12 frames).
- **Why scarce.** A structured, geometric transition is much louder than a 1-frame flash. Used once or twice, it reads as
  a signature. Used often, it reads as a template pack (mech: habituation).
- **Where.** A clean scene change in the body: after the title, before the wind-down. Steady shots on both sides, so the
  tiles are the only motion on screen and the grid reads.
- **Not:** on the title, in or out of a card series, on the final shot, or within 1 s of another accent. Skip it when no
  clean change exists; a forced Grid Flow is worse than none.

## 8. Situations
- **Reveal of a landmark or food result.** Put it after a flash and hold it longer than its neighbours (R08 final dish
  4.75 s incl. end card, R12 landmarks).
- **People and selfie moments.** Keep them short in the body; they are texture, not story (R05, R13). Do not put faces
  near the edge in a white card.
- **Process (recipe).** Keep chronological order; macro details 0.2-1.3 s. A PiP inset may show the measured quantity
  (R08 scale over bowl).
- **Night vs day.** If both exist, move day → night (R13). The night section is slightly denser. Avoid white flashes
  between two dark shots.
- **Thin footage (< ~15 usable shots).** Calm open, fewer and longer shots, no card series. Do not repeat a shot in the
  first half.
- **Ordinary filler shots.** No accent; leave clean.
- **Phone viewing.** These edits are watched small and often without sound. The title must read in about 1 s at phone
  size, and the image story must work muted.

## 9. Failure modes (symptom → cause → fix)
| symptom on the preview | likely cause | fix |
|---|---|---|
| feels like a slideshow | shots too even; no hook; few cuts on motion | shorten the cold open; follow the pacing curve; cut during motion |
| feels chaotic / tiring | accent rate too high outside the cold open; brightness jumps everywhere | drop accents to ≤ 0.5/s; match brightness on clean cuts |
| title unreadable | held < 1 s, busy background, or an accent touching it | steadier title shot, hold ~1.3 s, clear its frames |
| ending feels cut off | no deceleration; final shot short or busy; music not resolving | lengthen the last five shots; scenic final shot; end on the phrase |
| a cut looks like a mistake | jump cut (same subject/size) or eye jumps across the frame | change scale/angle; match the point of interest |
| card looks squashed or crops heads | 16:9 frame resized into the inset; wide or face-at-edge shots | centre-crop (the engine now does this); pick centred shots (user) |
| AI shot stands out | too sharp/clean next to real footage, or used too often | cap 2; keep it in the body; never title/final |
| Grid Flow feels cheap | used on a busy cut or too often | once on a clean change between steady shots |

## 10. Learned from Timon's feedback (keep adding)
| date | project | feedback / decision | rule change |
|---|---|---|---|
| 2026-10-25 | Smoke Sesh | the song is 13 s, so the edit is 13 s | §0/§6: song caps length; say so at gate B |
| 2026-10-25 | Smoke Sesh | AI drone shots were picked too often | §4: AI = support, cap 2 |
| 2026-10-26 | Smoke Sesh | "the video in the frame looks squashed" | §2/§9: card centre-crops; check proportions |
| 2026-10-26 | — | "4x4 wipe left with exposure flash, max 1-2 per video" | RULE_GRID_FLOW, §7 |
| 2026-10-28 | JUICT (client film, not a montage) | "de orginele bedrijfsfilm mag je intact houden … geen ondertitels" | none here: client films are out of this style's scope (decision 0010, `CLAUDE.md` → *Client films*). The photo snap he liked is a candidate device, not part of P_CINE_MONTAGE |

## 11. Confidence and what would raise it
- obs rows rest on 17 reposted 480p references; see `ACCURACY_AND_GAPS.md`.
- mech rows are standard perception and editing knowledge. They explain the observations; they were not tested on
  these references.
- Automated: `engine plan` runs `engine/style_checks.py` on every plan. It first removes accents that break a rule
  (too close, on a card edge, a second B&W, too many Grid Flows), then lists the checks from §1/§2 as ok, warn or fail
  at the top of the storyboard. `engine check <project>` re-runs them. `engine qa` checks the export technically.
  Not automatable from the EDL: eye trace, brightness jumps and scale changes (§3). Read those on the storyboard frames.
- Each real project with Timon's feedback adds a row to §10. That is how this document improves.
