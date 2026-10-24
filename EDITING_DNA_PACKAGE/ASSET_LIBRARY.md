# ASSET LIBRARY

## Included (redistributable)
| asset | file | source (verified) | license | use |
|---|---|---|---|---|
| Anton | assets/fonts/Anton-Regular.ttf (+ Anton-OFL.txt) | https://github.com/google/fonts/tree/main/ofl/anton | SIL OFL 1.1 | poster_condensed titles |
| Archivo variable (wdth 62-125, wght 100-900) | assets/fonts/Archivo-VF.ttf (+ OFL) | https://github.com/google/fonts/tree/main/ofl/archivo | SIL OFL 1.1 | heavy_grotesque titles, side labels, HUD |
| Bebas Neue | assets/fonts/BebasNeue-Regular.ttf (+ OFL) | https://github.com/google/fonts/tree/main/ofl/bebasneue | SIL OFL 1.1 | tall_condensed_light titles |
| Bodoni Moda variable | assets/fonts/BodoniModa-VF.ttf (+ OFL) | https://github.com/google/fonts/tree/main/ofl/bodonimoda | SIL OFL 1.1 | RB-style serif title (optional) |
| Lobster | assets/fonts/Lobster-Regular.ttf (+ OFL) | https://github.com/google/fonts/tree/main/ofl/lobster | SIL OFL 1.1 | retro_script approximation |
Licence and weight data verified from each family's METADATA.pb in google/fonts (2026-10-25); the Google Fonts specimen
pages are JS-only and could not be read.

## Built from scratch (no external asset needed)
| component | how | file |
|---|---|---|
| D_TITLE title slam | HTML text, font above, measured colour, fit-to-box | animations_and_components/components.html (`c=title_slam`) |
| D_LABELS side labels | HTML text, Archivo wdth125 wght900 | `c=side_labels` |
| D_HUD persistent labels | HTML text | `c=hud_labels` |
| D_CARD_WHITE / D_CARD_COLOUR | CSS box with inset shot | `c=white_card`, `c=colour_card` |
| T_FLASH | one white frame | `c=white_flash` |
| T_WHIP | SVG feGaussianBlur with x-only stdDeviation + translate | `c=whip_blur` |
| D_BW | CSS grayscale + contrast | `c=bw_shot` |

## Needs a non-HTML technique
| element | why | local alternative |
|---|---|---|
| depth_title (R03, R07), cut-out flash (R03, R11, RA) | needs a per-frame subject matte | Resolve Magic Mask, or rembg/SAM locally → PNG matte sequence, then HTML layers text between plate and matte |
| R08 retro script with 3-D extrusion | layered extrusion | stack 6-10 offset copies of the text in CSS (approximation) or Fusion Text+ extrusion |
| R16 slab title | font not identified | ask the user / use a licensed slab (e.g. via Adobe Fonts) |

## Not included (rights)
- Reference videos and all frames extracted from them (`reference_frames/`) are third-party social posts — analysis
  only, keep local, do not publish or redistribute.
- Reference music: not extracted, not reusable.
- Creator logos, IG/TikTok watermarks and end cards: excluded from the style.
- SFX: none required by the evidence. The user's FOUR Editors pack (licensed to the user, see AutoEdit config) may be
  added deliberately, outside the measured DNA.
