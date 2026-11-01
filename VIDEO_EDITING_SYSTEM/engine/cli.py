"""Command line with approval gates.

  python -m engine validate                      DNA + dependencies
  python -m engine plan  <project> [--title X] [--length 18] [--accent #E70002] [--seed 1]
                         [--title-shot CLIP[:s]] [--final-shot CLIP[:s]] [--order story]
                                                 inventory + EDL + storyboard  -> STOP (gate B)
  python -m engine grade <project> --look L [--strength 0..1] [--exposure -3..0.5]
                                                 the project's grade (cine_montage/grade.json), part of the approval
  python -m engine check <project>              style checks on the current plan (EDITING_PSYCHOLOGY.md)
  python -m engine approve <project> --by "<who>" --note "<user's words>"     record the user's approval of the plan
  python -m engine preview <project>            half-size review render (allowed before approval)
  python -m engine render <project>             final MP4 (refuses unless the current plan and grade are approved)
  python -m engine qa <project>                  re-run QA on the export

<project> = folder path or a name under the AutoEdit projects folder. Work files: <project>/cine_montage/.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path

from . import DNA_DIR, REPO
from . import dna as dna_mod
from . import gradechoice
from . import media, planner, qa, render, storyboard, style_checks
from .edl import EDL

PROJECTS = Path("C:/Users/Timon/Videos/AutoEdit Projects")


def find_project(name: str) -> Path:
    p = Path(name)
    if p.is_dir():
        return p
    hits = [d for d in PROJECTS.iterdir() if d.is_dir() and name.lower() in d.name.lower()] if PROJECTS.exists() else []
    if len(hits) == 1:
        return hits[0]
    raise SystemExit(f"project '{name}' not found (or ambiguous: {[h.name for h in hits]})")


def settings(proj: Path) -> dict:
    f = proj / "project.yaml"
    if f.exists():
        import yaml
        return yaml.safe_load(f.read_text(encoding="utf-8")) or {}
    return {}


def story_order(proj: Path) -> list | str:
    """`order:` from project.yaml (clip names in story order), else "time" (file time)."""
    order = settings(proj).get("order")
    return [str(c) for c in order] if order else "time"


def edl_hash(path: Path) -> str:
    return hashlib.sha1(path.read_bytes()).hexdigest()[:12]


def render_allowed(work: Path, g: gradechoice.Grade) -> tuple[bool, str]:
    """Gate B: the current EDL and grade `g` must be the ones the user approved. Returns (ok, reason)."""
    appr_path = work / "APPROVAL.json"
    appr = json.loads(appr_path.read_text(encoding="utf-8")) if appr_path.exists() else {}
    if appr.get("status") != "approved" or appr.get("edl_sha1") != edl_hash(work / "edl.json"):
        return False, ("the current EDL is not approved (gate B/D). Run plan, show the storyboard, "
                       "and record the user's approval with `approve` first.")
    # approvals made before the grade was part of the approval have no grade_key: they only cover the default grade
    approved = appr.get("grade_key", gradechoice.key(gradechoice.Grade()))
    if approved != gradechoice.key(g):
        return False, "de grade is gewijzigd na de goedkeuring: keur opnieuw goed"
    return True, ""


def effective_grade(work: Path, look: str | None) -> gradechoice.Grade:
    """The project's grade (grade.json, else the default); `--look` overrides only the look for this run."""
    g = gradechoice.load(work)
    return gradechoice.Grade(look, g.strength, g.exposure) if look else g


def print_checks(checks: list[dict], fixed: list[str]) -> None:
    for x in fixed:
        print("  fixed:", x)
    for c in checks:
        print(f"  {c['status'].upper():4} {c['rule']:22} {c['msg']}")
    print("style checks:", style_checks.summary(checks))


def main(argv=None):
    ap = argparse.ArgumentParser(prog="engine")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("validate")
    a = sub.add_parser("plan")
    a.add_argument("project"); a.add_argument("--title"); a.add_argument("--length", type=float)
    a.add_argument("--accent"); a.add_argument("--seed", type=int, default=1); a.add_argument("--song")
    a.add_argument("--fps", type=float, default=25.0); a.add_argument("--variant", choices=["poster_condensed", "heavy_grotesque"])
    a.add_argument("--card", choices=["auto", "on", "off"], default="auto"); a.add_argument("--bw", choices=["auto", "off"], default="auto")
    a.add_argument("--grid-flow", choices=["auto", "off"], default="auto")
    a.add_argument("--grade", choices=["auto", "slog3", "rec709", "none"], default="auto")
    a.add_argument("--title-shot", help="clip for the title, CLIP[:seconds], e.g. C0086:7")
    a.add_argument("--final-shot", help="clip for the last shot, CLIP[:seconds]")
    a.add_argument("--order", choices=["best", "story"], default="best",
                   help="story = body shots in shooting order (recipes); uses `order:` from project.yaml, else file time")
    a = sub.add_parser("grade"); a.add_argument("project")
    a.add_argument("--look", choices=gradechoice.LOOKS, required=True, help="film look (autoedit/grade.py)")
    a.add_argument("--strength", type=float, default=1.0, help="look strength 0..1")
    a.add_argument("--exposure", type=float, default=-1.75, help="exposure in stops on log clips, -3..0.5")
    a = sub.add_parser("approve"); a.add_argument("project"); a.add_argument("--by", required=True); a.add_argument("--note", required=True)
    for c in ("check", "preview", "render", "qa"):
        a = sub.add_parser(c); a.add_argument("project")
        a.add_argument("--grade", choices=["auto", "slog3", "rec709", "none"], default="auto")
    for a in (sub.choices[c] for c in ("plan", "preview", "render")):
        a.add_argument("--look", choices=gradechoice.LOOKS, default=None,
                       help="film look for this run only, overrides grade.json (autoedit/grade.py); clean_warm suits food")
    args = ap.parse_args(argv)

    if args.cmd == "validate":
        p = dna_mod.load()
        print("DNA ok:", dna_mod.summary(p))
        from .graphics import browser
        print("browser:", browser())
        print("ffmpeg:", media.FF)
        sys.path.insert(0, str(REPO / "tools"))
        import doc_check                                         # docs vs DNA/code (EDITING_PSYCHOLOGY.md §11)
        doc_check.main()
        return

    proj = find_project(args.project)
    work = proj / "cine_montage"
    work.mkdir(exist_ok=True)
    edl_path, appr_path = work / "edl.json", work / "APPROVAL.json"

    if args.cmd == "grade":
        g = gradechoice.Grade(args.look, args.strength, args.exposure)
        try:
            gradechoice.save(work, g)
        except ValueError as e:
            raise SystemExit(f"grade niet opgeslagen: {e}")
        print(f"grade: {g.look}, strength {g.strength:g}, exposure {g.exposure:g} (key {gradechoice.key(g)}); "
              "an earlier approval no longer covers this grade")
        return
    g = effective_grade(work, getattr(args, "look", None))

    if args.cmd == "plan":
        p = dna_mod.load()
        inv = media.inventory(proj, work / "cache")
        song, song_src = media.pick_song(proj, inv, args.song)
        mus = media.music_map(song, work / "cache") if song else None
        print(f"song: {song.name if song else 'none'} ({song_src})")
        edl = planner.plan(p, inv, mus, args.title, args.length, args.accent, args.fps, seed=args.seed,
                           card=args.card, bw=args.bw, title_variant=args.variant, grid_flow=args.grid_flow,
                           pinned={"title": args.title_shot, "final": args.final_shot},
                           order=story_order(proj) if args.order == "story" else None,
                           category=settings(proj).get("category"))
        fixed = style_checks.fix(edl)
        errs = edl.validate()
        if errs:
            raise SystemExit("EDL invalid: " + "; ".join(errs))
        edl.save(edl_path)
        checks = style_checks.check(edl)
        print_checks(checks, fixed)
        sb = storyboard.build(edl, work / "storyboard", args.grade, checks=checks, grade=g)
        appr_path.write_text(json.dumps({"status": "pending", "edl_sha1": edl_hash(edl_path),
                                         "created": datetime.now().isoformat(timespec="seconds")}, indent=1), encoding="utf-8")
        print(f"plan: {len(edl.events)} events, {edl.duration:.2f} s, problems in footage: {inv['problems'] or 'none'}")
        print("storyboard:", sb)
        print("open questions:", edl.open_questions or "none")
        print("STOP: show the storyboard and EDL to the user and wait for explicit approval (gate B).")
        return

    if args.cmd == "approve":
        if not edl_path.exists():
            raise SystemExit("no plan to approve")
        appr_path.write_text(json.dumps({"status": "approved", "edl_sha1": edl_hash(edl_path),
                                         "grade_key": gradechoice.key(g), "by": args.by, "note": args.note,
                                         "at": datetime.now().isoformat(timespec="seconds")}, indent=1), encoding="utf-8")
        print(f"approved plan {edl_hash(edl_path)} with grade {g.look}/{g.strength:g}/{g.exposure:g}")
        return

    edl = EDL.load(edl_path)
    if args.cmd == "check":
        print_checks(style_checks.check(edl), [])
        return
    if args.cmd == "preview":
        out = work / "preview.mp4"
        res = render.render(edl, out, work / "render", args.grade, preview=True, grade=g)
        print("preview:", res["out"], res["notes"])
        return
    if args.cmd == "render":
        ok, why = render_allowed(work, g)
        if not ok:
            raise SystemExit("REFUSED: " + why)
        out_dir = proj / "exports"
        out_dir.mkdir(exist_ok=True)
        out = out_dir / f"cine_montage_{datetime.now():%Y%m%d_%H%M}.mp4"
        res = render.render(edl, out, work / "render", args.grade, grade=g)
        q = qa.check(out, edl)
        (work / "qa.json").write_text(json.dumps({**res, "qa": q}, indent=1), encoding="utf-8")
        print("export:", out, "\nQA:", q)
        return
    if args.cmd == "qa":
        exports = sorted((proj / "exports").glob("cine_montage_*.mp4"))
        if not exports:
            raise SystemExit("no export yet")
        print(qa.check(exports[-1], edl))
