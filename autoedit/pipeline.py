"""One call from footage folder to approved-for-posting videos."""
from __future__ import annotations

import copy
import json
import random
from datetime import datetime, timedelta
from pathlib import Path

from rich.console import Console

from . import analyze, export, planner, publish, social
from .config import DATA

con = Console()


def pick_music(cfg, music: str | None) -> Path | None:
    if music == "none":
        return None
    folder = Path(cfg.get("paths.music_folder") or "")
    tracks = sorted(p for p in folder.glob("*") if p.suffix.lower() in analyze.AUDIO_EXT) if folder.exists() else []
    if music:
        if Path(music).exists():
            return Path(music)
        # just type part of the name: --music "orange" picks "Baby Keem - Orange Soda.mp3" from the music folder
        hits = [t for t in tracks if music.lower() in t.stem.lower()]
        if not hits:
            raise SystemExit(f"No song matching '{music}' in {folder}. Songs there: {[t.name for t in tracks] or 'none'}")
        return hits[0]
    return random.choice(tracks) if tracks else None


def list_music(cfg) -> list[str]:
    folder = Path(cfg.get("paths.music_folder") or "")
    folder.mkdir(parents=True, exist_ok=True)
    return sorted(p.name for p in folder.glob("*") if p.suffix.lower() in analyze.AUDIO_EXT)


def analyse_folder(folder: Path, log=con.print) -> list[analyze.ClipAnalysis]:
    videos, _ = analyze.find_media(folder)
    if not videos:
        raise SystemExit(f"No video files found in {folder}")
    clips = []
    for i, v in enumerate(videos, 1):
        log(f"  analysing {i}/{len(videos)}  {v.name}")
        clips.append(analyze.analyze_clip(v))
    clips = analyze.dedupe(clips)
    for c in clips:
        if c.rejected_reason:
            log(f"  [yellow]skipping {c.name}: {c.rejected_reason}[/]")
    return clips


def run(cfg, folder: str | Path, style_name: str | None = None, variants: str = "A", music: str | None = None,
        stab_mode: str | None = None, render: bool = True, queue: bool = True, location: str | None = None,
        clips: list | None = None, title: str | None = None, category: str | None = None,
        aspect: str | None = None, label: str | None = None, out_dir: Path | None = None,
        log=con.print) -> list[dict]:
    from .builder import Builder, render as do_render

    folder = Path(folder)
    style = cfg.style(style_name)
    if aspect:
        style = dict(style, aspect=aspect)
    if label is not None:
        style = dict(style, corner_label=label or None)           # "" = no corner label
    # the category is what the video is ABOUT (captions/hashtags); the style is how it's EDITED (always the same)
    category = category or cfg.get("default_category")
    log(f"[bold]AutoEdit[/] · {folder.name} · style [cyan]{style['label']}[/] · category {category or '-'} · variants {variants}")
    clips = clips or analyse_folder(folder, log)
    mpath = pick_music(cfg, music)
    mus = analyze.analyze_music(mpath) if mpath else None
    if mus:
        log(f"  music: {mpath.name} · {mus.tempo:.0f} BPM · drop at {mus.drop or 0:.1f}s")

    out_root = Path(out_dir) if out_dir else Path(cfg.get("paths.output_folder")) / f"{datetime.now():%Y-%m-%d}_{folder.name}"
    out_root.mkdir(parents=True, exist_ok=True)
    results = []
    for v in variants:
        if style.get("mode") == "cinematic":
            plan = planner.make_cinematic_plan(clips, style, cfg, mus, variant=v, stab_mode=stab_mode,
                                               title=title or style.get("title"))
        else:
            plan = planner.make_plan(clips, style, cfg, mus, variant=v, stab_mode=stab_mode)
        base = f"{category or 'edit'}_{v}"
        overrides: dict = {}
        use_director = style.get("mode") == "cinematic" and style.get("director", True)
        for attempt in range(2):                         # build → render → self-review → (fix once)
            if use_director:
                from .director import direct
                log("[bold]Director[/] (eye + ear candy from inventory.yaml):")
                direct(plan, clips, mus, seed=hash(folder.name) & 0xFFFF, log=log, overrides=overrides)
            (out_root / f"{base}_plan.json").write_text(plan.to_json())
            log(f"[bold]Variant {v}[/]: {len(plan.shots)} shots, {plan.length:.1f}s, hook “{plan.texts[0]['text'] if plan.texts else '-'}”")
            built = Builder(cfg, plan, style, log=log).build()
            res = {"variant": v, "timeline": built["timeline"], "plan": str(out_root / f"{base}_plan.json")}
            if not render:
                break
            raw = do_render(built["timeline"], out_root / "_raw", base, log=log)
            wide = style.get("aspect") == "16:9"
            fin = export.finish(raw, out_root, base, cfg.get("audio.target_lufs", -14),
                                [] if wide else cfg.get("format.extra_exports", []),
                                expect=(1920, 1080) if wide else (1080, 1920))
            res.update(fin)
            from .review import review
            rev = review(Path(fin["files"].get("9:16") or fin["files"]["16:9"]), plan, out_root,
                         base + ("_16x9" if wide else "_9x16"))
            res["review"] = rev
            for g in rev["good"]:
                log(f"  ✓ {g}")
            for i in rev["issues"]:
                log(f"  [yellow]✗ {i}[/]")
            if rev["ok"] or not rev["fixes"] or attempt == 1 or not use_director:
                break
            overrides.update(rev["fixes"])
            log(f"[bold]Self-review fix[/]: rebuilding with {rev['fixes']}")
        if render:
            if not fin["qc_ok"]:
                log(f"[yellow]QC: {', '.join(fin['qc']['problems'])}[/]")
            if queue:
                hook = plan.texts[0]["text"] if plan.texts else style["label"]
                caps = {p: social.suggest(category or "lifestyle", hook, p, location, seed=hash(v))
                        for p in cfg.get("posting.platforms", ["instagram", "tiktok"])}
                when = {p: publish.next_slot(cfg, p) for p in caps}
                effects = {}
                for s in plan.shots:
                    for e in s.effects:
                        effects[e] = effects.get(e, 0) + 1
                entry = publish.enqueue(fin["files"].get("9:16") or fin["files"]["16:9"], fin["files"].get("cover"), category or "general", caps, when,
                                        meta={"hook": hook, "variant": v, "timeline": built["timeline"], "edit_style": style["name"],
                                              "effects": effects, "files": fin["files"]})
                res["queue_id"] = entry["id"]
                log(f"  queued for approval: [bold]{entry['id']}[/]  (dashboard or `autoedit approve {entry['id']}`)")
        results.append(res)
    (out_root / "results.json").write_text(json.dumps(results, indent=1, ensure_ascii=False))
    return results


def repurpose(cfg, video: str | Path, count: int = 4, style_name: str | None = None, **kw) -> list[dict]:
    """One long video → `count` shorts, each built from a different part of the source."""
    video = Path(video)
    base = analyze.analyze_clip(video)
    chunk = base.duration / count
    out = []
    for i in range(count):
        part = copy.deepcopy(base)
        a, b = i * chunk, (i + 1) * chunk
        part.segments = [s for s in base.segments if a <= s.start and s.end <= b]
        part.motion_peaks = [t for t in base.motion_peaks if a <= t <= b]
        if not part.segments:
            continue
        con.print(f"[bold]Short {i + 1}/{count}[/] from {a:.0f}s–{b:.0f}s")
        out += run(cfg, video.parent, style_name, variants="ABCD"[i % 4], clips=[part], **kw)
    return out


def ideas(cfg, style_name: str, weeks: int = 2, per_week: int = 4) -> str:
    """Content calendar + shot lists, built from the current trend data."""
    t = social.trends()
    d = t.get(style_name, t["lifestyle"])
    rng = random.Random(datetime.now().strftime("%Y%W"))
    lines = [f"# Content plan: {style_name} ({weeks} weeks)", "", f"_Why this works now:_ {d['why_it_works'].strip()}", ""]
    start = datetime.now()
    slot_iter = []
    after = None
    for _ in range(weeks * per_week):
        s = publish.next_slot(cfg, "instagram", after)
        slot_iter.append(s)
        after = datetime.fromisoformat(s) + timedelta(minutes=30)
    shots = {
        "fitness": ["wide establishing shot of the gym/spot", "close-up: hands on the bar/chalk", "full exercise rep from the side (tripod)",
                    "slow-mo of the hardest rep", "face reaction after the set", "detail: shoes / straps"],
        "travel": ["arrival POV (walking in)", "the 'price' shot (menu, ticket, receipt)", "wide hero shot of the spot",
                   "hand-held detail (food, texture)", "you in frame looking at the view", "transition: cover the lens"],
        "fashion": ["mirror fit check", "same action in every outfit (e.g. turn)", "detail: shoes, jewelry, texture",
                    "walk towards camera", "ceiling-fan / shoe-toss transition", "full-body wide in nice light"],
        "lifestyle": ["morning light shot (window)", "hands doing the routine (coffee, journal)", "walk outside",
                      "a small 'win' moment", "evening wind-down", "the loop shot: end where you started"],
    }.get(style_name, [])
    fmts, hks = rng.sample(d["formats"], len(d["formats"])), rng.sample(d["hooks"], len(d["hooks"]))
    for i, when in enumerate(slot_iter):
        fmt, hook = fmts[i % len(fmts)], hks[i % len(hks)]           # no repeats until the bank runs out
        lines += [f"## {datetime.fromisoformat(when):%a %d %b %H:%M} — {fmt}", f"- **Hook (text on screen):** {hook}",
                  f"- **Shot list:** " + "; ".join(rng.sample(shots, min(4, len(shots)))) if shots else "",
                  f"- **Build:** `autoedit run <folder> --category {style_name}`", ""]
    return "\n".join(lines)
