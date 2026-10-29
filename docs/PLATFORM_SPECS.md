# Platform specs (Instagram Reels, TikTok)

Review by: 2027-01-29

What the platforms accept and recommend, with how sure each number is. **official** = the platform's own documentation;
**vendor guidance** = the platform's ads/marketing pages; **third-party** = blogs and tool vendors (indicative only).
Checked 2026-10-29.

## Upload limits (official)
| | Instagram Reels (Graph API) | TikTok (Content Posting API) |
|---|---|---|
| container | MP4 or MOV, moov atom at the front, no edit lists | MP4 (recommended), MOV, WebM |
| video codec | H.264 or HEVC, progressive, closed GOP, 4:2:0 | H.264 (recommended), H.265, VP8, VP9 |
| frame rate | 23-60 fps | 23-60 fps |
| resolution | max 1920 px wide; aspect 0.01:1-10:1, 9:16 recommended | each side 360-4096 px |
| video bitrate | VBR, **max 25 Mbps** | — |
| audio | AAC, max 48 kHz, mono/stereo | — |
| duration / size | 3 s - 15 min, max 300 MB | up to 10 min via the API (per creator: `max_video_post_duration_sec`), max 4 GB |
| other | the video must be on a public URL (Meta fetches it); a cover is JPEG ≤ 8 MB | unaudited apps post private only; AutoEdit uploads as drafts |

Sources: [Meta, IG User Media reference](https://developers.facebook.com/docs/instagram-platform/instagram-graph-api/reference/ig-user/media/),
[TikTok, Media Transfer Guide](https://developers.tiktok.com/docs/en/content-posting-api-media-transfer-guide),
[TikTok, Direct Post](https://developers.tiktok.com/docs/en/content-posting-api-reference-direct-post).

## Recommendations
| item | value | confidence | source |
|---|---|---|---|
| Reels aspect | 1.91:1 to 9:16 accepted; 9:16 best | official | [Instagram Help: Reel size](https://help.instagram.com/1038071743007909/) |
| Reels frame rate | "minimum 30 fps" in the help centre (the API accepts 23-60) | official, inconsistent | same |
| Reels resolution | at least 720 px | official | same |
| text safe zone, Reels | keep ~14 % top, ~35 % bottom, ~6 % each side free | vendor guidance (ads) | [Meta Ads Guide, Reels](https://www.facebook.com/business/ads-guide/update/image/instagram-reels) |
| text safe zone, TikTok | ~120 px top, ~250 px bottom, ~150 px right (1080×1920) | third-party | [ScreenSnap TikTok guide](https://www.screensnap.pro/blog/tiktok-video-size-guide) |
| loudness | about −14 LUFS | third-party, no platform source | several spec blogs |
| upload bitrate | 8-12 Mbps is plenty; platforms re-encode | third-party | [LunaBloom Reels specs](https://blog.lunabloomai.com/instagram-reels-specifications/) |

## How our exports compare
| item | AutoEdit | cine montage | client films | status |
|---|---|---|---|---|
| codec / container | H.264 or HEVC MP4 from Resolve, faststart after loudness | H.264 MP4, CRF 16 | H.264 MP4, CRF 16 | ok |
| bitrate | Resolve `VideoQuality` 20000 (20 Mbps); 4:5 copy capped at 20 Mbps; QC flags > 25 Mbps | CRF 16, uncapped (a 13 s Smoke Sesh export ≈ 25 Mbps) | ≈ 10 Mbps (JUICT v12) | AutoEdit ok since 2026-10-29; montage: make an upload copy before posting through the API |
| frame rate | 25 fps (`config.yaml`) | 25 fps | 29.97 fps (client source) | ok: 25 fps on purpose (decision [0011](decisions/0011-stay-at-25-fps.md)), inside the API's 23-60 |
| safe zone (9:16) | top 260, bottom 480, left 70, right 160 px (`autoedit/media_prep.py`) | 16:9, n/a | 16:9, n/a | top/sides meet Meta's ad guidance; bottom 480 px is less than Meta's 35 % (672 px) but more than TikTok's 250 px |
| loudness | −14 LUFS, true peak ≈ −1.5 dBTP | −14 LUFS, TP ≤ −1 | original mix (client) | ok |

## Keeping this current
Platforms change their docs without notice. Re-check the official links above before the *Review by* date, update the
tables and the date. `tools/doc_check.py` warns when a document's *Review by* date has passed.
