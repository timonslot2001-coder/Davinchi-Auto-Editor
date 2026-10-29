# Glossary

The words used in the docs and in chat, with the Dutch you might use for them.

| term | Dutch | meaning |
|---|---|---|
| accent | accent, effectje | any transition or effect that is not a plain hard cut: flash, whip, Grid Flow, punch zoom |
| aftermovie / company film | aftermovie, bedrijfsfilm | a client's event or company video; edited by decision 0010 (keep it intact) |
| approval gate (B, C, D) | goedkeuring | the stops where Claude waits for Timon's yes: B = plan + storyboard, C = something new outside the style, D = final render |
| B&W shot | zwart-wit shot | RULE_BW: one black-and-white shot per montage at most |
| card series | witte kaart, fotokaart | RULE_CARD_SERIES: 3-6 related shots shown inside a white "photo" frame |
| cold open | opening, hook | RULE_COLD_OPEN: the burst of very short shots at the start |
| deceleration | uitlopen, rustiger worden | RULE_DECELERATE: shots get longer towards the end; the last shot is the longest |
| director | regisseur | `autoedit/director.py`: places techniques where the moment calls for them |
| EDL | montagelijst | edit decision list, `cine_montage/edl.json`: every shot with in/out, transition and rule |
| eye candy / ear candy | beeld- en geluidseffecten | VFX / SFX techniques in `inventory.yaml` |
| flash | flits | RULE_FLASH: one full-white frame on a scene change |
| Grid Flow | grid flow, 4x4 wipe | RULE_GRID_FLOW: Timon's own 4×4 tile wipe with exposure flash (decision 0006) |
| house style | huisstijl | the `cinematic` style used for every AutoEdit video (decision 0001) |
| inventory | gereedschapskist | `inventory.yaml`: every technique, with when, how often and which sound |
| LUFS / true peak | loudness, volume | loudness measures; exports aim at ≈ −14 LUFS and true peak ≤ −1 dBTP |
| LUT / PowerGrade | kleurcorrectie, grade | colour look: `autoedit/grade.py` bakes S-Log3 → Rec.709 + the film look into one LUT |
| Muapi | betaalde AI | paid AI video service; only after a quote and a yes (decision 0004) |
| P_CINE_MONTAGE | montage-stijl, cine montage | the approved montage style profile (decision 0005) |
| photo snap | foto-snap | a photo landing as a white print on the blurred shot, with flash and camera click (JUICT) |
| project | project | one folder per shoot in `Videos\AutoEdit Projects\<name>` with clips/, music/, exports/ |
| reference | referentie(video) | a video Timon sends as an example; feeds the inventory, never copied (decision 0002) |
| S-Log3 | log-materiaal | the flat colour profile of Timon's Sony A6700; needs conversion before it looks right |
| storyboard | storyboard | the sheet of real frames per planned shot that Timon approves at gate B |
| style checks | stijlcontrole | `engine/style_checks.py`: ok/warn/fail per rule on every plan |
| taste rule | smaakregel | Timon's feedback turned into a rule in `taste.yaml` |
| title | titel | RULE_TITLE: the one big poster title naming the place or topic |
| Wan (local AI) | lokale AI, gratis AI | Wan 2.2 5B in ComfyUI on Timon's GPU; free, ~30 min per clip |
| whip | swipe, whip pan | RULE_WHIP: a directional motion blur across a cut |
