"""Your SSD library: see what is in each shoot folder, pick clips for an edit, or name and move a folder.

  autoedit pick "Smoke Sesh kort" "Smoken/2026-07-25 Smoke Sesh/C0184.MP4" "Smoken/2026-08-16 Gesprek met Milan/C0191.MP4"

hard-links those clips into `_Edits/Smoke Sesh kort/` on the SSD (no copy, no extra space) and the AutoEdit project of
that name reads its clips from there.

  autoedit sort "Ibiza" --soort reizen "_Inbox/2026-10-09 SD-kaart" "_Inbox/2026-10-10 SD-kaart"

moves those folders into one shoot `Reizen/2026-10-09 Ibiza/` (1 Ruw/Video, 1 Ruw/Foto, ...), links the AutoEdit
project of that name to it, and repoints any project whose clips were in a moved folder. Files are only moved on the
SSD itself (a rename, no copy); nothing is deleted except the empty folders left behind.

The web app (page *SSD*) shows the shoots, a thumbnail per clip and photo, and a short preview of a clip, all made on
demand and cached in data/library_thumbs/.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from rich.console import Console

from . import offload
from .config import ROOT

con = Console()

CACHE = ROOT / "data" / "library_thumbs"
PHOTO_SHOWN = {".jpg", ".jpeg", ".png"}                 # RAW files are counted, not shown (the JPG twin is)
PREVIEW_S = 20


def _ffmpeg() -> str:
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def kind_of(folder: str) -> str | None:
    return next((k for k, (d, _) in offload.KINDS.items() if d == folder), None)


def resolve_shoot(cfg, rel: str) -> Path:
    """'<Kind folder>/<shoot folder>' → the folder on the SSD; anything else is refused."""
    parts = re.split(r"[\\/]", str(rel).strip())
    if len(parts) != 2 or kind_of(parts[0]) is None or not parts[1] or parts[1] in (".", ".."):
        raise ValueError(f"not a shoot folder: {rel!r} (expected '<Soort>/<datum naam>')")
    p = offload.library(cfg) / parts[0] / parts[1]
    if not p.is_dir():
        raise FileNotFoundError(f"{rel} is not on the SSD")
    return p


def _media(shoot: Path):
    vids, photos, raw, size = [], [], 0, 0
    for dp, _, fs in os.walk(shoot):
        for n in fs:
            f = Path(dp) / n
            ext = f.suffix.lower()
            try:
                size += f.stat().st_size
            except OSError:
                continue
            if ext in offload.VIDEO:
                vids.append(f)
            elif ext in PHOTO_SHOWN:
                photos.append(f)
            elif ext in offload.PHOTO:
                raw += 1
    return sorted(vids), sorted(photos), raw, size


def _linked_projects(cfg) -> dict[str, str]:
    """clips folder (resolved, lower case) → project name."""
    from . import projects
    out = {}
    for p in projects.root(cfg).iterdir():
        c = p / "clips"
        try:
            if p.is_dir() and c.exists():
                out[str(c.resolve()).lower()] = p.name
        except OSError:
            pass
    return out


def shoots(cfg) -> dict:
    """Every shoot folder on the SSD, _Inbox first, with counts and the project that reads its clips."""
    lib = offload.library(cfg)
    if not lib.exists():
        return {"library": str(lib), "connected": False, "kinds": [], "shoots": []}
    linked = _linked_projects(cfg)
    rows = []
    for kind, (folder, _) in sorted(offload.KINDS.items(), key=lambda kv: (kv[0] != "inbox", kv[1][0])):
        kdir = lib / folder
        for d in sorted(kdir.iterdir()) if kdir.is_dir() else []:
            if not d.is_dir():
                continue
            vids, photos, raw, size = _media(d)
            video_dir = d / "1 Ruw" / "Video"
            m = re.match(r"(\d{4}-\d{2}-\d{2}) (.+)", d.name)
            rows.append({"rel": f"{folder}/{d.name}", "kind": kind, "kind_folder": folder, "folder": d.name,
                         "date": m[1] if m else None, "name": m[2] if m else d.name, "videos": len(vids),
                         "photos": len(photos) + raw, "size": size,
                         "project": linked.get(str(video_dir.resolve()).lower()) if video_dir.exists() else None})
    return {"library": str(lib), "connected": True,
            "kinds": [{"kind": k, "folder": f} for k, (f, _) in offload.KINDS.items()], "shoots": rows}


def _key(f: Path) -> str:
    st = f.stat()
    return hashlib.sha1(f"{f}|{st.st_size}|{int(st.st_mtime)}".encode()).hexdigest()[:20]


def duration(f: Path) -> float:
    meta = CACHE / f"{_key(f)}.json"
    if meta.exists():
        return json.loads(meta.read_text())["duration"]
    err = subprocess.run([_ffmpeg(), "-hide_banner", "-i", str(f)], capture_output=True, text=True,
                         errors="ignore").stderr
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", err)
    d = int(m[1]) * 3600 + int(m[2]) * 60 + float(m[3]) if m else 0.0
    CACHE.mkdir(parents=True, exist_ok=True)
    meta.write_text(json.dumps({"duration": d}))
    return d


def shoot(cfg, rel: str) -> dict:
    """The clips (with length) and the viewable photos of one shoot."""
    p = resolve_shoot(cfg, rel)
    vids, photos, raw, size = _media(p)
    with ThreadPoolExecutor(8) as ex:
        durs = list(ex.map(duration, vids))
    return {"rel": rel, "path": str(p), "size": size, "raw": raw,
            "videos": [{"name": f.name, "path": str(f), "size": f.stat().st_size, "duration": d}
                       for f, d in zip(vids, durs)],
            "photos": [{"name": f.name, "path": str(f)} for f in photos]}


def _inside_library(cfg, path: str) -> Path:
    f = Path(path).resolve()
    lib = offload.library(cfg).resolve()
    if lib not in f.parents or not f.is_file():
        raise PermissionError("only files on the SSD library")
    return f


def thumb(cfg, path: str) -> str:
    """A 320 px still of a clip (at 40 %) or a photo, cached; returns its path."""
    f = _inside_library(cfg, path)
    out = CACHE / f"{_key(f)}.jpg"
    if out.exists():
        return str(out)
    CACHE.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".part.jpg")
    if f.suffix.lower() in offload.VIDEO:
        t = duration(f) * 0.4
        subprocess.run([_ffmpeg(), "-v", "error", "-y", "-ss", f"{t:.2f}", "-i", str(f), "-frames:v", "1",
                        "-vf", "scale=320:-2", "-q:v", "4", str(tmp)], capture_output=True, timeout=120)
    else:
        from PIL import Image, ImageOps
        with Image.open(f) as im:
            im.draft("RGB", (640, 640))
            im = ImageOps.exif_transpose(im).convert("RGB")
            im.thumbnail((320, 320))
            im.save(tmp, quality=80)
    if not tmp.exists():
        raise RuntimeError(f"could not make a thumbnail of {f.name}")
    os.replace(tmp, out)
    return str(out)


def warm(cfg, rels: list[str] | None = None, workers: int = 6) -> int:
    """Make the lengths and thumbnails of every clip ahead of time (all folders with video, or just `rels`), so the SSD
    page opens at once. Cached, so a second run only does what is new. Returns the number of clips."""
    if rels is None:
        rels = [r["rel"] for r in shoots(cfg)["shoots"] if r["videos"]]
    clips = []
    for rel in rels:
        try:
            clips += _media(resolve_shoot(cfg, rel))[0]
        except (ValueError, FileNotFoundError):
            continue
    def one(f):
        try:
            duration(f)
            thumb(cfg, str(f))
        except Exception as e:                                    # one odd clip never stops the rest
            con.print(f"[yellow]  thumbnail of {f.name} failed: {e}[/]")
    with ThreadPoolExecutor(workers) as ex:
        list(ex.map(one, clips))
    return len(clips)


def preview(cfg, path: str) -> str:
    """A small H.264 clip (20 s from 10 % in, 640 px, no sound) that every browser plays; cached; returns its path."""
    f = _inside_library(cfg, path)
    if f.suffix.lower() not in offload.VIDEO:
        raise ValueError("only clips have a preview")
    out = CACHE / f"{_key(f)}_preview.mp4"
    if out.exists():
        return str(out)
    CACHE.mkdir(parents=True, exist_ok=True)
    d = duration(f)
    start = d * 0.1 if d > PREVIEW_S * 1.5 else 0
    tmp = out.with_name(out.stem + ".part.mp4")
    subprocess.run([_ffmpeg(), "-v", "error", "-y", "-ss", f"{start:.2f}", "-i", str(f), "-t", str(PREVIEW_S), "-an",
                    "-vf", "scale=640:-2,format=yuv420p", "-c:v", "libx264", "-preset", "veryfast", "-crf", "28",
                    "-movflags", "+faststart", str(tmp)], capture_output=True, timeout=600)
    if not tmp.exists():
        raise RuntimeError(f"could not make a preview of {f.name}")
    os.replace(tmp, out)
    return str(out)


# ---------------------------------------------------------------- moving


def _move_tree(src: Path, dst: Path) -> int:
    """Move every file under src to the same place under dst (a rename on the same drive); returns the count."""
    n = 0
    for dp, _, fs in os.walk(src):
        rel = Path(dp).relative_to(src)
        for name in fs:
            target_dir = dst / rel
            target_dir.mkdir(parents=True, exist_ok=True)
            target = offload._free_name(target_dir, name)
            os.replace(Path(dp) / name, target)
            n += 1
    for dp, _, _ in sorted(os.walk(src), key=lambda w: -len(w[0])):      # deepest first; only empty folders go
        try:
            os.rmdir(dp)
        except OSError:
            pass
    return n


def _repoint(cfg, old_video: Path, new_video: Path) -> list[str]:
    """Projects whose clips junction pointed into a moved folder now point at the new place."""
    import _winapi
    from . import projects
    moved = []
    for p in projects.root(cfg).iterdir():
        c = p / "clips"
        try:
            target = os.readlink(c)
        except (OSError, ValueError):
            continue                                              # not a link (real clips folder) or missing
        target = target[4:] if target.startswith("\\\\?\\") else target
        if os.path.normcase(os.path.normpath(target)) == os.path.normcase(os.path.normpath(str(old_video))):
            os.rmdir(c)                                           # removes the junction only, never the footage
            _winapi.CreateJunction(str(new_video), str(c))
            moved.append(p.name)
    return moved


def move(cfg, name: str, kind: str, sources: list[str], link: bool = True) -> dict:
    """Merge the source shoot folders into '<Kind>/<earliest date> <name>' and link the project."""
    if kind not in offload.KINDS:
        raise SystemExit(f"--soort must be one of: {', '.join(offload.KINDS)}")
    name = name.strip()
    if not name or name[0] == "." or name[-1] == "." or any(c in name for c in '\\/:*?"<>|'):
        raise SystemExit(f"'{name}' can not be a folder name (no \\ / : * ? \" < > |, no leading or trailing dot)")
    if not sources:
        raise SystemExit("name at least one shoot folder to move")
    lib = offload.library(cfg)
    srcs = []
    for rel in sources:
        try:
            srcs.append(resolve_shoot(cfg, rel))
        except (ValueError, FileNotFoundError) as e:
            raise SystemExit(str(e))
    dates = [m[1] for s in srcs if (m := re.match(r"(\d{4}-\d{2}-\d{2}) ", s.name))]
    date = min(dates) if dates else __import__("datetime").date.today().isoformat()
    target = offload.shoot_folder(lib, kind, name, date)
    ledger_path = lib / offload.LEDGER
    ledger = json.loads(ledger_path.read_text(encoding="utf-8")) if ledger_path.exists() else {}
    total, relinked = 0, []
    for s in srcs:
        if s.resolve() == target.resolve():
            con.print(f"  {s.name}: already there")
            continue
        n = _move_tree(s, target)
        total += n
        old = str(s)
        for k, v in ledger.items():                               # keep the offload ledger pointing at the files
            if v.startswith(old + os.sep) or v.startswith(old + "/"):
                ledger[k] = str(target) + v[len(old):]
        relinked += _repoint(cfg, s / "1 Ruw" / "Video", target / "1 Ruw" / "Video")
        con.print(f"  {s.parent.name}/{s.name} → {n} file(s)")
    if ledger:
        ledger_path.write_text(json.dumps(ledger, indent=1), encoding="utf-8")
    project = None
    if link and kind != "inbox":
        project = offload.link_project(cfg, target.name[11:], target / "1 Ruw" / "Video", offload.KINDS[kind][1])
    con.print(f"[green]{total} file(s) moved[/] → {target}")
    if relinked:
        con.print(f"  project(s) {', '.join(sorted(set(relinked)))} now read their clips from the new place")
    if total:
        warm(cfg, [f"{target.parent.name}/{target.name}"])       # thumbnails ready for the SSD page
    if project and (project / "clips").resolve() == (target / "1 Ruw" / "Video").resolve():
        con.print(f"  AutoEdit project [bold]{project.name}[/] reads its clips from {target / '1 Ruw' / 'Video'}")
    return {"moved": total, "shoot": str(target), "project": str(project) if project else None,
            "relinked": sorted(set(relinked))}


# ---------------------------------------------------------------- picking clips for an edit

EDITS = "_Edits"


def _folder_name(name: str) -> str:
    name = name.strip()
    if not name or name[0] == "." or name[-1] == "." or any(c in name for c in '\\/:*?"<>|'):
        raise SystemExit(f"'{name}' can not be a folder name (no \\ / : * ? \" < > |, no leading or trailing dot)")
    return name


def resolve_clip(cfg, ref: str) -> Path:
    """'<Soort>/<datum naam>/<clip>' → that video file in the shoot folder; anything else is refused."""
    parts = re.split(r"[\/]", str(ref).strip())
    if len(parts) != 3:
        raise ValueError(f"not a clip: {ref!r} (expected '<Soort>/<datum naam>/<clip>')")
    shoot_dir = resolve_shoot(cfg, "/".join(parts[:2]))
    hits = [f for f in _media(shoot_dir)[0] if f.name == parts[2]]
    if not hits:
        raise FileNotFoundError(f"{parts[2]} is not a clip in {parts[0]}/{parts[1]}")
    return hits[0]


def _link_into(edits: Path, src: Path) -> str:
    """Hard link src into the edit folder; 'added', or 'there' when that clip is already in it."""
    dst = edits / src.name
    if dst.exists() and os.path.samefile(dst, src):
        return "there"
    if dst.exists():                                              # same clip name from another shoot: '<shoot> C0001.MP4'
        shoot_dir = src.parent.parent.parent if src.parent.name == "Video" else src.parent
        dst = offload._free_name(edits, f"{shoot_dir.name} {src.name}")
    os.link(src, dst)
    return "added"


def pick(cfg, name: str, refs: list[str]) -> dict:
    """Put the chosen clips in one edit: hard links in <SSD>/_Edits/<name> (no copy, no extra space, the originals stay
    where they are) and the AutoEdit project <name> reads its clips from there. A second pick adds to the same edit."""
    import _winapi
    from . import projects

    name = _folder_name(name)
    if not refs:
        raise SystemExit("pick at least one clip")
    try:
        srcs = [resolve_clip(cfg, r) for r in refs]
    except (ValueError, FileNotFoundError) as e:
        raise SystemExit(str(e))
    edits = offload.library(cfg) / EDITS / name
    edits.mkdir(parents=True, exist_ok=True)
    p = projects.root(cfg) / name
    if not p.exists():
        projects.new(cfg, name)
    clips = p / "clips"
    keep = []                                                     # clips the project already had (on the SSD)
    if clips.exists() and clips.resolve() != edits.resolve():
        here = [f for f in clips.iterdir() if f.is_file() and f.suffix.lower() in offload.VIDEO]
        if not clips.is_junction() and here:
            raise SystemExit(f"Project '{name}' has its own clips on C: ({clips}); pick under another name")
        if clips.is_junction():
            if os.path.splitdrive(str(clips.resolve()))[0].lower() != os.path.splitdrive(str(edits))[0].lower():
                raise SystemExit(f"Project '{name}' reads its clips from another drive; pick under another name")
            keep = here
        added_keep = [_link_into(edits, f) for f in keep]
        os.rmdir(clips)                                           # junction or empty folder; never footage
        _winapi.CreateJunction(str(edits), str(clips))
        if keep:
            con.print(f"  the {len(added_keep)} clip(s) the project already had are in the edit too")
    elif not clips.exists():
        _winapi.CreateJunction(str(edits), str(clips))
    added = there = 0
    for src in srcs:
        r = _link_into(edits, src)
        added += r == "added"
        there += r == "there"
    total = sum(1 for f in edits.iterdir() if f.suffix.lower() in offload.VIDEO)
    con.print(f"[green]{added} clip(s) in edit {name}[/]" + (f", {there} were already in it" if there else "")
              + f" · {total} in total → {edits}")
    con.print(f"  AutoEdit project [bold]{name}[/] reads its clips from there; the originals stay where they are")
    return {"project": str(p), "edits": str(edits), "added": added, "already": there, "clips": total}


# ---------------------------------------------------------------- camera card in -> proposal ready

def card(cfg) -> list[dict]:
    """What the website runs when a camera card goes in: offload everything new to _Inbox (one folder per day, checked,
    card untouched), then per new day with video an edit '<date> voorstel' with all of that day's clips and a cine
    montage plan (storyboard) for it. Nothing is rendered: that waits for "Ja, renderen"."""
    import subprocess
    import sys

    res = offload.offload(cfg, "SD-kaart", "inbox")
    out = []
    for shoot_path in res.get("shoots") or []:
        shoot_dir = Path(shoot_path)
        rel = f"{shoot_dir.parent.name}/{shoot_dir.name}"
        vids = _media(shoot_dir)[0]
        if not vids:
            continue
        name = f"{shoot_dir.name[:10]} voorstel"
        from . import projects
        if (projects.root(cfg) / name / "cine_montage" / "edl.json").exists():
            con.print(f"  {name} heeft al een voorstel; niets overschreven")
            continue
        r = pick(cfg, name, [f"{rel}/{v.name}" for v in vids])
        engine = ROOT / "VIDEO_EDITING_SYSTEM"
        con.print(f"[bold]Voorstel[/] {name}: plan maken ({len(vids)} clips)…")
        done = subprocess.run([sys.executable, "-m", "engine", "plan", r["project"]], cwd=str(engine)).returncode == 0
        out.append({"project": name, "clips": len(vids), "plan": done})
        con.print(f"[green]Voorstel klaar:[/] {name}" if done else f"[yellow]Plan voor {name} lukte niet; maak hem op de website[/]")
    if not out:
        con.print("Geen nieuwe video's op de kaart.")
    return out
