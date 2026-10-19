"""autoedit — DaVinci Resolve auto editor.  Run `autoedit -h` for all commands."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from rich.console import Console
from rich.table import Table

from .config import ROOT, load, save_user_style

con = Console()


def main(argv=None):
    ap = argparse.ArgumentParser(prog="autoedit", description="DaVinci Resolve auto editor for TikTok + Instagram")
    sub = ap.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("run", help="analyse → edit in Resolve → render → queue for approval")
    a.add_argument("folder")
    a.add_argument("--category", help="what it's about: fitness / travel / fashion / lifestyle (captions + hashtags)")
    a.add_argument("--aspect", choices=["9:16", "16:9"], help="output shape (house style default: 16:9)")
    a.add_argument("--style", help="advanced: use another edit style than your house style")
    a.add_argument("--variants", default="A", help="A/B hook test, e.g. AB or ABC")
    a.add_argument("--music", help="music file, part of a song name from your music folder, or 'none'")
    a.add_argument("--bass", type=float, help="bass in the song in dB (e.g. -6 = less bass, 0 = untouched)")
    a.add_argument("--stabilize", choices=["auto", "all", "none"], help="override config stabilization.mode")
    a.add_argument("--location", help="used in captions, e.g. 'Porto'")
    a.add_argument("--title", help="small spaced-out title over the intro, e.g. 'UTRECHT'")
    a.add_argument("--label", help="tiny corner label over the intro, e.g. your brand/handle")
    a.add_argument("--seed", type=int, help="reproduce an earlier edit exactly")
    a.add_argument("--no-render", action="store_true", help="only build the timeline in Resolve")

    a = sub.add_parser("analyze", help="show quality / shake / speech per clip")
    a.add_argument("folder")

    a = sub.add_parser("repurpose", help="one long video → several shorts")
    a.add_argument("video")
    a.add_argument("--count", type=int, default=4)
    a.add_argument("--style")

    sub.add_parser("watch", help="drop-folder mode: builds automatically when clips land in a subfolder")

    a = sub.add_parser("new", help="create a project folder: clips/ music/ exports/ project.yaml")
    a.add_argument("name")
    a.add_argument("--title", help="title over the intro (default: the project name)")
    sub.add_parser("projects", help="list your projects (clips, song, exports)")
    a = sub.add_parser("import", help="copy new clips from the camera SD card into a project")
    a.add_argument("name")
    a.add_argument("--since", help="only clips from this day on, YYYY-MM-DD")
    a = sub.add_parser("project", help="edit a project by name (partial name is fine)")
    a.add_argument("name")
    a.add_argument("--song", help="override the project's song")
    a.add_argument("--title")
    a.add_argument("--variants")
    a.add_argument("--seed", type=int)
    a = sub.add_parser("dashboard", help="open the local dashboard")
    a.add_argument("--port", type=int, default=5055)

    sub.add_parser("queue", help="list videos waiting for approval / scheduled / posted")
    a = sub.add_parser("approve", help="approve a queued video (it posts at its scheduled time)")
    a.add_argument("id")
    a.add_argument("--caption", type=int, default=0, help="which suggestion (0-2) for all platforms")
    a = sub.add_parser("post", help="post an approved video now")
    a.add_argument("id")
    sub.add_parser("post-due", help="post approved videos whose time has come (for Task Scheduler)")

    sub.add_parser("stats", help="pull Instagram stats + learn best times")
    sub.add_parser("report", help="what performs best for you")
    a = sub.add_parser("ideas", help="content calendar + shot lists from current trends")
    a.add_argument("--style", default="lifestyle")
    a.add_argument("--weeks", type=int, default=2)
    a = sub.add_parser("save-style", help="save a copy of a preset under a new name to tweak")
    a.add_argument("source")
    a.add_argument("name")
    sub.add_parser("tiktok-login", help="one-time TikTok authorisation (stores refresh token in .env)")
    sub.add_parser("sfx", help="show the SFX library per category")
    sub.add_parser("optimize", help="smooth playback: proxies, render cache, heavy nodes off (existing timelines too)")

    args = ap.parse_args(argv)
    cfg = load()

    if args.cmd == "run":
        from . import pipeline
        if args.bass is not None:
            cfg.raw.setdefault("audio", {})["music_bass_db"] = args.bass
        res = pipeline.run(cfg, args.folder, args.style, args.variants, args.music, args.stabilize,
                           render=not args.no_render, location=args.location, title=args.title,
                           category=args.category, aspect=args.aspect, label=args.label, seed=args.seed)
        con.print_json(json.dumps(res, ensure_ascii=False))
    elif args.cmd == "analyze":
        from . import pipeline
        clips = pipeline.analyse_folder(Path(args.folder))
        thr = cfg.get("stabilization.shake_threshold", 0.35)
        t = Table("clip", "len", "sharp", "shake", "stabilize?", "motion", "speech", "best moment", "status")
        for c in clips:
            best = f"{c.segments[0].start:.1f}–{c.segments[0].end:.1f}s" if c.segments else "-"
            t.add_row(c.name, f"{c.duration:.1f}s", f"{c.sharpness:.2f}", f"{c.shake:.2f}", "yes" if c.shake >= thr else "no",
                      f"{c.motion:.2f}", "yes" if c.has_speech else "", best, c.rejected_reason or "ok")
        con.print(t)
    elif args.cmd == "repurpose":
        from . import pipeline
        pipeline.repurpose(cfg, args.video, args.count, args.style)
    elif args.cmd == "watch":
        from .watch import watch
        watch(cfg)
    elif args.cmd == "dashboard":
        import webbrowser
        from .dashboard import serve
        webbrowser.open(f"http://127.0.0.1:{args.port}")
        serve(args.port)
    elif args.cmd == "queue":
        from . import publish
        t = Table("id", "style", "hook", "status", "instagram", "tiktok")
        for e in publish.entries():
            r = e.get("results", {})
            t.add_row(e["id"], e["style"], e["meta"].get("hook", ""), e["status"],
                      r.get("instagram", {}).get("url") or e["scheduled"].get("instagram", ""),
                      r.get("tiktok", {}).get("status") or e["scheduled"].get("tiktok", ""))
        con.print(t)
    elif args.cmd == "approve":
        from . import publish
        e = publish.get(args.id) or sys.exit("unknown id")
        publish.update(args.id, status="approved", chosen={p: args.caption for p in e["options"]})
        con.print(f"[green]Approved[/] {args.id}. Posts at: {e['scheduled']}")
    elif args.cmd == "post":
        from . import publish
        con.print_json(json.dumps(publish.post_entry(args.id, force_now=True)["results"], ensure_ascii=False))
    elif args.cmd == "post-due":
        from . import publish
        for e in publish.post_due():
            con.print(e["id"], e["status"])
    elif args.cmd == "stats":
        from . import performance
        performance.refresh()
        learned = performance.learn_best_times()
        con.print(performance.report())
        if learned:
            con.print(f"[green]Updated best posting times:[/] {learned}")
    elif args.cmd == "report":
        from . import performance
        con.print(performance.report())
    elif args.cmd == "ideas":
        from . import pipeline
        md = pipeline.ideas(cfg, args.style, args.weeks)
        out = ROOT / f"content_plan_{args.style}.md"
        out.write_text(md, encoding="utf-8")
        con.print(md)
        con.print(f"\n[green]Saved[/] {out}")
    elif args.cmd == "save-style":
        save_user_style(args.name, cfg.style(args.source))
        con.print(f"Saved preset '{args.name}' → data/user_styles.yaml (edit it there)")
    elif args.cmd == "tiktok-login":
        from .tiktok_auth import login
        login()
    elif args.cmd == "new":
        from . import projects
        projects.new(cfg, args.name, args.title)
    elif args.cmd == "projects":
        from . import projects
        t = Table("project", "clips", "song", "exports", "title")
        for p in projects.listing(cfg):
            t.add_row(p["name"], str(p["clips"]), p["song"] or "-", str(p["exports"]), p["title"] or "")
        con.print(t)
    elif args.cmd == "import":
        from . import projects
        projects.import_card(cfg, args.name, args.since)
    elif args.cmd == "project":
        from . import projects
        res = projects.run(cfg, args.name, song=args.song, title=args.title, variants=args.variants, seed=args.seed)
        con.print_json(json.dumps(res, ensure_ascii=False, default=str))
    elif args.cmd == "optimize":
        from .builder import optimize_project
        optimize_project(cfg)
    elif args.cmd == "sfx":
        from .sfx import Library
        con.print(Library(cfg.get("paths.sfx_folders", [])).summary())


if __name__ == "__main__":
    main()
