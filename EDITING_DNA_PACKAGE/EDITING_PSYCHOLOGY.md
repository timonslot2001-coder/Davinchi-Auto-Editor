# EDITING PSYCHOLOGY — P_CINE_MONTAGE

Each rule separates **observed** behaviour (measured or seen on the strips) from **interpretation** (why an editor would
do it). Machine-readable versions: `style_dna.json → rules[]`.

## The emotional arc of these edits
1. **Hook (0-1.3 s) — curiosity through overload.** obs: the shortest shots of the whole video sit here (first-fifth
   median 0.36 s; R04 opens with 11 shots of 0.12 s). interp: the viewer cannot read the shots, only feel energy and
   texture; the brain wants the "where am I?" answer, which creates the pull into the title.
2. **Orientation (title) — payoff.** obs: 11/17 name the place/topic once, in one accent colour, median 0.54 s in, held
   ~1.3 s, hard cut in and out. interp: the title answers the question the hook raised and brands the piece like a
   poster; a hard cut feels confident, an animated entrance would feel like a template.
3. **Exploration (body) — rhythm with resets.** obs: shots 0.4-0.5 s, mostly hard cuts; every ~2 s an accent
   (flash/whip); sometimes a white-card "chapter". interp: steady pace keeps momentum; accents mark new beats of the
   journey; the white card changes texture so attention resets without slowing down.
4. **Resolution (wind-down) — exhale.** obs: shots lengthen ~50 % by the end; the final content shot holds 0.5-2.3 s.
   interp: the viewer is given time to take in one beautiful image, which leaves a mood instead of a blur.

## Rule table (trigger → response, with restraint)
| rule | trigger | response | why | restraint (when NOT) | conf. |
|---|---|---|---|---|---|
| RULE_COLD_OPEN | start | 2-11 shots 0.1-0.4 s | hook by overload | thin footage → open calm | high |
| RULE_TITLE | first strong establishing shot | poster title, 1 accent colour, ~1.3 s | answer + brand | no single place/topic; never twice | high |
| RULE_FLASH | place/scene change, music accent | 1 white frame | 'shutter blink' = new beat | never 2 within 1 s, never on title | high |
| RULE_WHIP | motion in outgoing shot | 3-6 f directional blur | carries momentum | static shots | medium |
| RULE_CARD_SERIES | 3-6 related shots | white card, hard in/out | 'photo album' chapter, attention reset | <3 shots, >2 per video | med-high |
| RULE_BW | one reflective moment | single B&W shot | contrast by subtraction | more than once | medium |
| RULE_DECELERATE | second half | longer shots, scenic ending | exhale, lingering mood | loop edits | high |
| RULE_ONE_ACCENT | always | one accent colour | poster consistency | — | high |
| RULE_NO_TEXT_OVERLOAD | always | no captions | images + music tell it | user adds speech | high |

## Visual attention budget
- obs: never more than one designed element (title OR labels OR card) on screen; no flash/whip lands on a title frame.
- Budget per moment: **1 graphic + 1 transition accent**, platform overlays excluded.
- Accent rate: 0.48 non-hard transitions per second overall; allow up to ~1.5/s inside the cold open, ≤0.3/s in the
  wind-down.
- Clean stretches are intentional: R04 17-26 s and R16 run several cuts with no accents at all.

## Music relationship (honest finding)
obs: across the set, cut times are not closer to beats/onsets than random times (z ≈ 0.06; only U2/R04/RB sync).
interp: these editors cut to **phrase energy and shot motion** rather than to every beat; reposting may also blur sync.
Decision for new edits: build pace from the shot-length curve; snap a cut to a strong onset only when it is within one
frame or two — never stretch a shot to hit a beat.

## Situations
- **Reveal of a landmark / food result:** put it after a flash, hold it longer than its neighbours (R08 final dish 4.75 s
  incl. end card, R12 landmarks).
- **People/selfie moments:** keep them short in the body; they are texture, not story (R05, R13).
- **Process (recipe):** keep chronological order; macro details 0.2-1.3 s; PiP inset may show the measured quantity
  (R08 scale over bowl).
- **Night vs day:** if both exist, move day → night (R13); night section slightly denser.
- **Ordinary filler shots:** no accent — leave clean.
