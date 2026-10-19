"""Projects: one folder per shoot. You say the name, the editor does the rest.

  AutoEdit Projects/
    <Project name>/
      clips/        footage (copy it in, or `autoedit import "<name>"` straight from the camera card)
      music/        optional: the song for this edit (first audio file is used)
      exports/      finished videos, review sheets, plan
      project.yaml  title, corner label, category, format, notes
      tags.json     optional: shot tags (detail / subject / close / hero_wide …) for the story order
"""
from __future__ import annotations

import shutil
import string
from datetime import datetime
from pathlib import Path

import yaml
from rich.console import Console

from .analyze import AUDIO_EXT, VIDEO_EXT

con = Console()

TEMPLATE = """# Project settings — all optional. Edit and save; the next run uses them.
title: "{title}"          # small spaced title over the intro (empty = none)
label: "BUDTHENCINEMATIC" # tiny corner label (empty = none)
category: null            # fitness / travel / fashion / lifestyle → captions + hashtags only
aspect: null              # null = house style default (16:9), or "9:16"
song: null                # name (part) of a song in your music folder (wins over music/); or drop a file in music/
location: null            # used in captions
variants: "A"             # "AB" = two versions with different hooks/choices
notes: ""                 # anything Claude should keep in mind for this edit
created: "{created}"
"""


def root(cfg) -> Path:
    r = Path(cfg.get("paths.projects_folder") or Path.home() / "Videos" / "AutoEdit Projects")
    r.mkdir(parents=True, exist_ok=True)
    return r


def find(cfg, name: str) -> Path:
    """Case-insensitive, partial match: 'smoke' finds 'Smoke Sesh'."""
    projects = [p for p in root(cfg).iterdir() if p.is_dir()]
    exact = [p for p in projects if p.name.lower() == name.lower()]
    if exact:
        return exact[0]
    hits = [p for p in projects if name.lower() in p.name.lower()]
    if len(hits) == 1:
        return hits[0]
    if not hits:
        raise SystemExit(f"No project matching '{name}'. Projects: {[p.name for p in projects] or 'none yet'}")
    raise SystemExit(f"'{name}' matches several projects: {[p.name for p in hits]} — be more specific.")


def new(cfg, name: str, title: str | None = None) -> Path:
    p = root(cfg) / name
    for sub in ("clips", "music", "exports"):
        (p / sub).mkdir(parents=True, exist_ok=True)
    y = p / "project.yaml"
    if not y.exists():
        y.write_text(TEMPLATE.format(title=title if title is not None else name,
                                     created=datetime.now().strftime("%Y-%m-%d")), encoding="utf-8")
    con.print(f"[green]Project ready:[/] {p}\n  put footage in the [bold]clips[/] folder, optional song in the [bold]music[/] folder")
    return p


def settings(p: Path) -> dict:
    y = p / "project.yaml"
    return (yaml.safe_load(y.read_text(encoding="utf-8")) or {}) if y.exists() else {}


def listing(cfg) -> list[dict]:
    out = []
    for p in sorted(root(cfg).iterdir()):
        if not p.is_dir():
            continue
        clips = [f for f in (p / "clips").glob("*") if f.suffix.lower() in VIDEO_EXT] if (p / "clips").exists() else []
        songs = [f for f in (p / "music").glob("*") if f.suffix.lower() in AUDIO_EXT] if (p / "music").exists() else []
        exports = sorted((p / "exports").glob("*_16x9.mp4")) + sorted((p / "exports").glob("*_9x16.mp4")) \
            if (p / "exports").exists() else []
        s = settings(p)
        out.append({"name": p.name, "clips": len(clips), "song": songs[0].name if songs else s.get("song"),
                    "exports": len(exports), "title": s.get("title"), "path": str(p)})
    return out


# ---------------------------------------------------------------- camera card import

def camera_cards() -> list[Path]:
    """Sony cards keep video in PRIVATE/M4ROOT/CLIP (A6700 included)."""
    cards = []
    for letter in string.ascii_uppercase:
        clip = Path(f"{letter}:/PRIVATE/M4ROOT/CLIP")
        try:
            if clip.is_dir():
                cards.append(clip)
        except OSError:
            continue
    return cards


def import_card(cfg, name: str, since: str | None = None) -> int:
    """Copy new clips (+ their XML sidecars) from the camera card into the project's clips folder.
    since: 'YYYY-MM-DD' → only clips recorded on/after that day (default: everything not copied yet)."""
    p = find(cfg, name)
    dst = p / "clips"
    dst.mkdir(exist_ok=True)
    cards = camera_cards()
    if not cards:
        raise SystemExit("No Sony camera card found (looked for <drive>:\\PRIVATE\\M4ROOT\\CLIP). Is the SD card in?")
    cutoff = datetime.strptime(since, "%Y-%m-%d").timestamp() if since else 0
    copied = 0
    for card in cards:
        files = sorted(f for f in card.iterdir() if f.suffix.upper() == ".MP4" and f.stat().st_mtime >= cutoff)
        for i, f in enumerate(files, 1):
            target = dst / f.name
            if target.exists() and target.stat().st_size == f.stat().st_size:
                continue
            con.print(f"  copying {i}/{len(files)}  {f.name}  ({f.stat().st_size / 1e9:.1f} GB)")
            shutil.copy2(f, target)
            xml = f.with_name(f"{f.stem}M01.XML")
            if xml.exists():
                shutil.copy2(xml, dst / xml.name)
            copied += 1
    con.print(f"[green]{copied} clip(s) imported[/] into {dst}")
    return copied


# ---------------------------------------------------------------- run

def run(cfg, name: str, **overrides) -> list[dict]:
    from . import pipeline, planner

    p = find(cfg, name)
    s = settings(p)
    s.update({k: v for k, v in overrides.items() if v is not None})
    clips_dir = p / "clips"
    if not any(f.suffix.lower() in VIDEO_EXT for f in clips_dir.glob("*")):
        raise SystemExit(f"Project '{p.name}' has no clips yet — put footage in {clips_dir}")
    songs = sorted(f for f in (p / "music").glob("*") if f.suffix.lower() in AUDIO_EXT)
    # explicit choice wins: --song, then song: in project.yaml, then the first file in music/
    music = overrides.get("song") or s.get("song") or (str(songs[0]) if songs else None)
    planner.EXTRA_TAGS = p / "tags.json"
    con.print(f"[bold]Project[/] {p.name} · {sum(1 for f in clips_dir.glob('*') if f.suffix.lower() in VIDEO_EXT)} clips"
              f" · song: {Path(music).name if music and Path(music).exists() else music or 'none'}")
    return pipeline.run(cfg, clips_dir, None, s.get("variants") or "A", music,
                        title=s.get("title") or None, label=s.get("label") or None,
                        category=s.get("category"), aspect=s.get("aspect"), location=s.get("location"),
                        out_dir=p / "exports", seed=s.get("seed"))
