# 0003 Nothing is posted or rendered final without Timon's yes

- Status: accepted
- Date: 2026-10-19 (posting), 2026-10-25 (cine montage gates)
- Source: README, "Nothing goes online without your OK"; the Stage 2 brief, gates B/C/D

## Context
The tool can post to Instagram and TikTok and render finals unattended. A wrong post is public and hard to undo.

## Decision
- AutoEdit queues every video and posts only after `autoedit approve <id>`. TikTok uploads land as drafts.
- Cine montage: plan + storyboard → **gate B**, Timon's explicit yes on that plan → `engine approve` → `engine render`.
  New fonts, colours or effects → **gate C** (show a test first). The render refuses an EDL that changed after approval
  (**gate D**).
- Claude never approves or renders on his behalf, and never treats approval of the style as approval of a video.

## Consequences
One extra message per video. In return, nothing reaches the public or the final export by accident.
