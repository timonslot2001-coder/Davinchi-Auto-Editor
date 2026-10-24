# ACCURACY AND GAPS

## Verified (measured from the files)
- File identity, resolution, fps, duration, loudness of all 22 references (`reference_manifest.json`).
- 423 cut candidates on 17 P_CINE_MONTAGE refs, each inspected on 5-frame strips (`reference_frames/cut_strips/`).
- Shot-length distribution and pacing curve (440 shots).
- Transition shares (hard 70.9 %, flash 17.0 %, whip 12.1 %) — automatic classification, spot-checked on
  `reference_frames/verify_*.jpg`; some whip/flash labels may be swapped (≈ 1 in 8 on the spot check).
- White flash length: 45 of 49 = 1 frame.
- White card geometry on RA (3 frames): 69 % × 92 % centred, background #FDFCFD.
- Title colours sampled: #E70002 (R17), #AC0A22 (R02), #A00004 (R16), #F05F05 (R11); ink boxes in `style_dna.json`.
- Beat/onset sync test vs random baseline and a ±300 ms lag scan.
- Font files and OFL licences (google/fonts METADATA.pb).

## Inferred (interpretation, labelled as such)
- All "why" statements in EDITING_PSYCHOLOGY.md.
- Whip duration 3-6 frames and direction (visual estimate, not measured per frame).
- Colour-card geometry (R06/RB) — not measured.

## Approximated
- Fonts: no reference title font is confirmed. Anton (stretched) matches R17/R11 closely
  (`annotated_comparisons/title_slam_HUARAZ_compare.jpg`); Archivo 900 approximates R02; side labels use Archivo
  wdth125 where the original looks like an extended grotesque (Monument Extended-like — its licence page could not be
  checked: HTTP 429).
- '++' arrows in side labels are typed plus signs; the original glyph is a small double-arrow.
- R16 slab and R08 script are not identified.

## Limits of the material
- The 17 R-files and RA/RB are 480p re-downloads (originals unavailable): fine typography and exact pixel positions
  have ~±1.5 % uncertainty.
- Audio is the reposted mix: music, possible SFX and compression are inseparable; SFX conclusions are inconclusive.
- Cut detection misses very soft dissolves; none were confirmed visually, so dissolves are recorded as absent.

## Not done in this stage
- P_VERTICAL_VLOG and P_TALKING_CAPTIONS are inventoried only.
- No ZIP yet — created after your approval (Checkpoint 8).

## What would improve accuracy
1. Higher-resolution versions of any 3-4 refs with titles (R02, R04, R17, R05).
2. The names of the title fonts if you know the creators' templates.
3. Your choice of the default title variant (poster_condensed vs heavy_grotesque) and accent colour for your own work.
