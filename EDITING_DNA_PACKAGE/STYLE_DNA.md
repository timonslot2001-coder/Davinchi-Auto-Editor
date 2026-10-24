# STYLE DNA — P_CINE_MONTAGE (status: pending user approval)

Source of truth: `style_dna.json`. Every number below is copied from it; evidence IDs are `<ref>-C<cut>` (cut index in
`audio_analysis/events/<ref>_events.json`) or `<ref> <seconds>` on the 480p reference copy.

## 1. What this style is
Music-only cinematic montage of a place, trip or process (city, food, nature). 10-27 s of content. It opens with a burst
of very short shots, names the place once in a big poster title in one accent colour, keeps cutting hard with sparse
1-frame white flashes and whip blurs, may drop a short sub-sequence into a white "photo card", and slows down towards a
lingering final shot. Warm, contrasty, slightly dark film grade. No captions.

References: R02 R03 R04 R05 R06 R07 R08 R10 R11 R12 R13 R14 R16 R17 RA RB U2 (17).

## 2. Structure template (apply to a new montage)
| part | share of length | shot length | what happens | evidence |
|---|---|---|---|---|
| Cold open | first ~5-10 % | 0.1-0.4 s | 2-11 detail/texture shots, flashes allowed | R04 0-1.29 (11 shots), R17 0-0.74, R06 0-1.07 |
| Title | at 0-3 s (median 0.54) | holds 0.33-4.53 s (median 1.26) | D_TITLE on the strongest establishing shot | R02 0.64, R04 1.29, R17 0.74 |
| Body | ~60 % | median 0.44-0.50 s | hard cuts, flashes on scene changes, whips on motion, optional card series | all |
| Wind-down | last ~20 % | median 0.54 s | fewer accents, longer holds | R04 17-26, R08 |
| Final shot | - | 0.5-2.3 s (measured last content shot) | most scenic/resolving image, no title | R08 24.4, R16, U2 |

Pacing curve (median shot length per fifth): **0.36 → 0.44 → 0.50 → 0.55 → 0.54 s**
(`audio_analysis/pacing_curve.png`). Overall p10/p50/p90: 0.16 / 0.51 / 1.45 s.

## 3. If this happens → do this
| ID | When | Do | Never |
|---|---|---|---|
| RULE_COLD_OPEN | video start | 2-11 shots of 0.1-0.4 s | if fewer than ~8 usable detail shots, open calmer (U2/R16) |
| RULE_TITLE | first strong establishing shot after the burst | poster title, accent colour, hard cut in/out, ~1.3 s, may span 2 shots | repeat the title; animate it in letter by letter |
| RULE_FLASH | change of place/scene, energy accent | one full-white frame | two flashes within ~1 s; flash on a title frame |
| RULE_WHIP | outgoing shot already moves | 3-6 frames directional blur in the motion direction | static-to-static cuts |
| RULE_CARD_SERIES | 3-6 related shots (one place/activity) | keep them all inside the white card (69 % × 92 %, #FDFCFD), hard in/out | fewer than 3 shots; more than twice |
| RULE_BW | one contrast/reflective moment | single B&W shot, often after a flash | more than one per video |
| RULE_DECELERATE | second half | lengthen shots ~50 %, end on the longest scenic shot | ending on a fast burst |
| RULE_ONE_ACCENT | always | one accent colour for title + cards, otherwise white | mixing red and orange etc. |
| RULE_NO_TEXT_OVERLOAD | always | no captions; text = title (+ optional labels) only | subtitles, lower thirds |

Conflict priority: NO_TEXT_OVERLOAD > ONE_ACCENT > TITLE > COLD_OPEN > DECELERATE > FLASH > CARD_SERIES > WHIP > BW.

## 4. Transition vocabulary (measured on 423 cut candidates)
| type | share | spec |
|---|---|---|
| T_HARD hard cut | 70.9 % | default |
| T_FLASH white flash | 17.0 % | 1 frame (45 of 49 measured), #FFFFFF |
| T_WHIP whip blur | 12.1 % | 3-6 frames, mostly horizontal (visual estimate) |
| T_BURST light burst | rare | white bloom from centre (R12 9.10) |
| T_DIP dip to black | rare | calm refs only (U2 1.43) |
Accent density: 0.48 non-hard transitions per second of content (≈ one per 2.1 s), clustered in the cold open.

## 5. Typography (title devices)
| variant | refs | font (closest verified free match) | colour | geometry |
|---|---|---|---|---|
| poster_condensed | R17, R11, R06 | Anton, stretched vertically to fill height | #E70002 (R17), #F05F05 (R11) | R17 ink box x 0.024-0.982, y 0.117-0.856 |
| heavy_grotesque | R02 | Archivo wght 900, wdth 88, tracking -0.045 em | #AC0A22 | x 0.137-0.867, y 0.375-0.531 |
| tall_condensed_light | R04 | Bebas Neue + small spaced credit line | #FFFFFF | left third, x 0.09-0.435 |
| slab_display | R16 | unverified heavy slab | #A00004 | centred, 2 lines + 'MALAYSIA.' kicker |
| retro_script | R08 | Lobster-like + 3-D extrusion (approximation) | cream + orange | top half |
| depth_title | R03, R07 | any heavy condensed, BEHIND the subject | - | needs subject matte |
Secondary small lines (optional): bottom-left/right, ~2 % frame height ('SHOT BY SONY ALPHA', 'FRAMES VLOG #08').
Side labels (creator-specific, R05/R13/RA): 'LEFT' / 'RIGHT' framing at mid-height, Archivo wdth125 wght900,
3.7 % frame height, 4.5 % side margin.

## 6. Grade (content shots, n≈420)
CIELAB L* median 36.8 (IQR in json), p5 4.3, p95 76.9, a +1.9, b +5.8; HSV saturation median 97/255.
→ dark-ish mids, crushed but not clipped blacks, rolled-off highlights, warm bias, moderate saturation.
In AutoEdit/Resolve this matches the existing house LUT direction (warm film, −exposure); per-reference values are in
`style_dna.json → grade.per_ref`.

## 7. Audio
Music only in 15/17 refs; reposted loudness −13.0 … −14.4 LUFS. Cuts are **not** measurably locked to beats or onsets
(pooled z ≈ 0.06 at lag 0; see `audio_analysis/beat_lag_scan.png`); only U2, R04, RB show clear sync. Per-transition SFX
could not be demonstrated (high-frequency rise is the same for hard cuts, flashes and whips). → Cut on phrase energy;
snapping to strong onsets is allowed, not required. SFX are optional, not part of the measured DNA.

## 8. Do not
Captions or subtitles · more than one accent colour · typewriter/kinetic title entrances · long dissolves · constant
zoom pulses · talking-head structure · copying the creators' IG watermarks, handles or end cards.
