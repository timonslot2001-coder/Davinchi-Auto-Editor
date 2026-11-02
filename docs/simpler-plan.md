# Simpler AutoEdit: baseline and plan

Goal: from camera card to a scheduled post with as few steps, choices and tokens as possible. Each phase is measured
against the baseline below; what does not save time, clicks or tokens is removed again.

## Baseline (2026-11-02)
| measure | now |
|---|---|
| ways in | 3 apps (old dashboard, website, Studio Artifact) + 33 command rows + "tell Claude" |
| editors to choose between | 2 (AutoEdit house style, cine montage) |
| steps card → post (cine montage) | 9: offload, sort, pick clips, grade, plan, approve (type a sentence), render, look, queue |
| choices per video | grade (look, strength, exposure), song, title, approval text |
| tokens per action | website 0; Studio 1 Claude turn per click (also for looking: *Beelden laden*, *Preview maken*) |
| build cost per feature | 2× (website and Studio) |
| minutes card → post | not measured yet: time the next video from card in to *Plannen* |

## Phases
1. **Measure** (this page). Time the next video end to end; count clicks.
2. **Tidy up** (done 2026-11-02, decision [0014](decisions/0014-one-app-the-website.md)): one app (the website,
   `autoedit.bat`), on the phone through Tailscale, no more building everything twice; the Studio is frozen.
3. **Shorter path**: no grade step (house look by default, *andere look* with example pictures for the exception);
   one path *Nieuwe video* in 4 steps (Clips → Muziek → Bekijken → *Ja, renderen*, that button is the approval); the
   app picks the editor once per project; the editor picks the best part of the song; the home page shows the next
   step per project.
4. **The editor starts the work**: card in → offload, day sorted and a first rough edit ready, with a phone message;
   feedback buttons on the result (*korter*, *rustiger*, *ander nummer*, *dit shot eruit*) that also become taste
   rules; shots recognised automatically instead of `tags.json`; a project lives on the SSD next to its footage;
   result → *Plannen* with caption and time filled in; one status light (Resolve, SSD, ComfyUI); Claude only for
   creative work (references, taste rules).

## After each phase
Fill in the same table again (and the minutes). Score: the baseline is 100; phase 2+3 aim at 130, phase 4 at 150.
