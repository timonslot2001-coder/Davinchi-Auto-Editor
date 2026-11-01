"""Command line with approval gates.

  python -m engine validate                      DNA + dependencies
  python -m engine plan  <project> [--title X] [--length 18] [--accent #E70002] [--seed 1]
                         [--title-shot CLIP[:s]] [--final-shot CLIP[:s]] [--order story] [--look L]
                                                 inventory + EDL + storyboard  -> STOP (gate B)
  python -m engine grade <project> --look L [--strength 0..1] [--exposure -3..0.5]
                                                 the project's grade (cine_montage/grade.json), part of the approval
  python -m engine check <project>              style checks on the current plan (EDITING_PSYCHOLOGY.md)
  python -m engine approve <project> --by "<who>" --note "<user's words>"     record the user's approval of the plan
                         [--expect-sha1 H] [--expect-grade K]   refuse unless the plan / grade are still the ones seen
  python -m engine preview <project> [--look L]  half-size review render (allowed before approval; --look = try-out only)
  python -m engine render <project>             final MP4 (refuses unless the current plan, grade.json and --grade mode
                                                 are the approved ones)
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
    return sha12(path.read_bytes())


def sha12(data: bytes) -> str:
    return hashlib.sha1(data).hexdigest()[:12]


def render_allowed(work: Path, g: gradechoice.Grade, mode: str = "auto",
                   edl_bytes: bytes | None = None) -> tuple[bool, str]:
    """Gate B: the current EDL, grade `g` and --grade `mode` must be the ones the user approved. Returns (ok, reason).
    `edl_bytes`: the edl.json bytes the caller will render (hash and parse one read), else the file is read here."""
    appr_path = work / "APPROVAL.json"
    appr = json.loads(appr_path.read_text(encoding="utf-8")) if appr_path.exists() else {}
    sha = sha12(edl_bytes) if edl_bytes is not None else edl_hash(work / "edl.json")
    if appr.get("status") != "approved" or appr.get("edl_sha1") != sha:
        return False, ("the current EDL is not approved (gate B/D). Run plan, show the storyboard, "
                       "and record the user's approval with `approve` first.")
    # approvals made before the grade was part of the approval have no grade_key: they only cover the default grade
    approved = appr.get("grade_key", gradechoice.key(gradechoice.Grade()))
    if approved != gradechoice.key(g):
        return False, "de grade is gewijzigd na de goedkeuring: keur opnieuw goed"
    if appr.get("grade_mode", "auto") != mode:                    # approvals without grade_mode were made with "auto"
        return False, f"de grade-modus wijkt af van de goedkeuring ({mode} vs {appr.get('grade_mode', 'auto')})"
    return True, ""


def write_made_with(path: Path, g: gradechoice.Grade, mode: str) -> None:
    """The grade a storyboard sheet / preview was made with, next to it (the Studio labels them with it)."""
    path.write_text(json.dumps({"key": gradechoice.key(g), "look": g.look, "strength": g.strength,
                                "exposure": g.exposure, "grade_mode": mode}), encoding="utf-8")


MADE_WITH = {"plan": Path("storyboard") / "made_with.json", "preview": Path("preview_made_with.json")}


def effective_grade(work: Path, look: str | None) -> gradechoice.Grade:
    """The project's grade (grade.json = the single source of truth, else the default); `--look` on preview overrides
    only the look for that run."""
    try:
        g = gradechoice.load(work)
    except ValueError as e:
        raise SystemExit(f"grade.json ongeldig: {e}")
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
    a.add_argument("--expect-sha1", help="edl hash the user saw (12 hex); refuse if the plan changed since")
    a.add_argument("--expect-grade", help="grade key the user saw (12 hex); refuse if the grade changed since")
    for c in ("check", "preview", "render", "qa"):
        a = sub.add_parser(c); a.add_argument("project")
        a.add_argument("--grade", choices=["auto", "slog3", "rec709", "none"], default="auto")
    sub.choices["plan"].add_argument("--look", choices=gradechoice.LOOKS, default=None,
                                     help="film look, saved to grade.json (autoedit/grade.py); clean_warm suits food")
    sub.choices["preview"].add_argument("--look", choices=gradechoice.LOOKS, default=None,
                                        help="try a film look in this preview only (not saved, not approved)")
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
        g = gradechoice.load(work)
        print(f"grade: {g.look}, strength {g.strength:g}, exposure {g.exposure:g} (key {gradechoice.key(g)}); "
              "an earlier approval no longer covers this grade")
        return
    if args.cmd == "plan" and args.look:                         # plan's look is the project's grade (grade.json)
        old = effective_grade(work, None)
        gradechoice.save(work, gradechoice.Grade(args.look, old.strength, old.exposure))
    g = effective_grade(work, args.look if args.cmd == "preview" else None)

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
        (work / MADE_WITH["plan"]).unlink(missing_ok=True)
        sb = storyboard.build(edl, work / "storyboard", args.grade, checks=checks, grade=g)
        write_made_with(work / MADE_WITH["plan"], g, args.grade)
        appr_path.write_text(json.dumps({"status": "pending", "edl_sha1": edl_hash(edl_path), "grade_mode": args.grade,
                                         "created": datetime.now().isoformat(timespec="seconds")}, indent=1), encoding="utf-8")
        print(f"plan: {len(edl.events)} events, {edl.duration:.2f} s, problems in footage: {inv['problems'] or 'none'}")
        print("storyboard:", sb)
        print("open questions:", edl.open_questions or "none")
        print("STOP: show the storyboard and EDL to the user and wait for explicit approval (gate B).")
        return

    if args.cmd == "approve":
        if not edl_path.exists():
            raise SystemExit("no plan to approve")
        prev = json.loads(appr_path.read_text(encoding="utf-8")) if appr_path.exists() else {}
        sha, gkey = edl_hash(edl_path), gradechoice.key(g)        # what is checked is what gets recorded
        if args.expect_sha1 is not None and args.expect_sha1 != sha:
            raise SystemExit("het plan is veranderd sinds je het zag: bekijk het nieuwe plan")
        if args.expect_grade is not None and args.expect_grade != gkey:
            raise SystemExit("de grade is veranderd sinds je hem zag: bekijk de grade opnieuw")
        appr_path.write_text(json.dumps({"status": "approved", "edl_sha1": sha,
                                         "grade_key": gkey, "grade_mode": prev.get("grade_mode", "auto"),
                                         "by": args.by, "note": args.note,
                                         "at": datetime.now().isoformat(timespec="seconds")}, indent=1), encoding="utf-8")
        print(f"approved plan {sha} with grade {g.look}/{g.strength:g}/{g.exposure:g}")
        return

    edl_bytes = None
    if args.cmd == "render":                                     # gate first: refuse before touching the footage
        edl_bytes = edl_path.read_bytes() if edl_path.exists() else b""   # one read: what is approved is rendered
        ok, why = render_allowed(work, g, args.grade, edl_bytes)
        if not ok:
            raise SystemExit("REFUSED: " + why)
    edl = EDL.loads(edl_bytes) if edl_bytes is not None else EDL.load(edl_path)
    if args.cmd == "check":
        print_checks(style_checks.check(edl), [])
        return
    if args.cmd == "preview":
        out = work / "preview.mp4"
        (work / MADE_WITH["preview"]).unlink(missing_ok=True)
        res = render.render(edl, out, work / "render", args.grade, preview=True, grade=g)
        write_made_with(work / MADE_WITH["preview"], g, args.grade)
        print("preview:", res["out"], res["notes"])
        return
    if args.cmd == "render":
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
