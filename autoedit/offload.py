"""Offload: camera cards → one folder per shoot on your SSD, sorted by kind of video.

  I:/
    Koken/ Kleding/ Smoken/ Reizen/ Klanten/ _Inbox/
      2025-10-06 Beef Tartaar/
        1 Ruw/       Video/ (Sony + DJI, original names)   Foto/ (RAW + JPG)
        2 Bewerkt/   Video/ Foto/
        3 Klaar om te posten/

Every file is checked after copying (size + SHA-1 of the copy against the card). Nothing is ever deleted from the card.
A ledger in the library remembers what was offloaded, so a card with older shoots on it only copies what is new.
The AutoEdit project of the same name reads its clips straight from `1 Ruw/Video` (a junction), no second copy on C:.
"""
from __future__ import annotations

import ctypes
import hashlib
import json
import os
import shutil
import string
from datetime import datetime
from pathlib import Path

from rich.console import Console

con = Console()

KINDS = {   # --soort → folder on the SSD, project.yaml category (None = leave it empty)
    "koken": ("Koken", "food"),
    "kleding": ("Kleding", "fashion"),
    "smoken": ("Smoken", "lifestyle"),
    "reizen": ("Reizen", "travel"),
    "klanten": ("Klanten", None),
    "inbox": ("_Inbox", None),
}
SHOOT_DIRS = ("1 Ruw/Video", "1 Ruw/Foto", "2 Bewerkt/Video", "2 Bewerkt/Foto", "3 Klaar om te posten")
VIDEO = {".mp4", ".mov", ".mxf", ".avi"}
PHOTO = {".jpg", ".jpeg", ".arw", ".dng", ".hif", ".heic", ".cr3", ".nef", ".raf", ".png"}
SIDECAR = {".xml"}                      # Sony keeps clip metadata in <clip>M01.XML next to the clip
SKIP = {".lrf", ".thm"}                 # DJI/GoPro low-res proxies and thumbnails
LEDGER = ".autoedit-offload.json"
CHUNK = 8 * 1024 * 1024


def library(cfg) -> Path:
    return Path(cfg.get("paths.library_folder") or "I:/")


def _removable(letter: str) -> bool:
    try:
        return ctypes.windll.kernel32.GetDriveTypeW(f"{letter}:\\") == 2       # DRIVE_REMOVABLE
    except (AttributeError, OSError):
        return False


def find_cards() -> list[Path]:
    """Removable drives that look like a camera card (Sony PRIVATE/M4ROOT or a DCIM folder)."""
    cards = []
    for letter in string.ascii_uppercase:
        if not _removable(letter):
            continue
        root = Path(f"{letter}:/")
        try:
            if (root / "PRIVATE" / "M4ROOT").is_dir() or (root / "DCIM").is_dir():
                cards.append(root)
        except OSError:
            continue
    return cards


def card_files(card: Path) -> list[tuple[Path, str]]:
    """(file, 'Video' | 'Foto') for everything worth keeping on a card."""
    out = []
    for base in (card / "PRIVATE" / "M4ROOT" / "CLIP", card / "DCIM"):
        if not base.is_dir():
            continue
        for f in sorted(base.rglob("*")):
            ext = f.suffix.lower()
            if not f.is_file() or ext in SKIP or f.name.startswith("."):
                continue
            if ext in VIDEO or ext in SIDECAR:
                out.append((f, "Video"))
            elif ext in PHOTO:
                out.append((f, "Foto"))
    return out


def _key(f: Path) -> str:
    st = f.stat()
    return f"{f.name}|{st.st_size}|{int(st.st_mtime)}"


def _sha1(path: Path) -> str:
    h = hashlib.sha1()
    with open(path, "rb") as fh:
        while chunk := fh.read(CHUNK):
            h.update(chunk)
    return h.hexdigest()


def copy_checked(src: Path, dst: Path) -> None:
    """Copy via a .part file, hashing the card while reading; compare with a hash of the copy, then rename."""
    part = dst.with_name(dst.name + ".part")
    h = hashlib.sha1()
    with open(src, "rb") as a, open(part, "wb") as b:
        while chunk := a.read(CHUNK):
            h.update(chunk)
            b.write(chunk)
    if part.stat().st_size != src.stat().st_size or _sha1(part) != h.hexdigest():
        part.unlink()
        raise OSError(f"copy of {src.name} does not match the card; nothing kept, try again")
    shutil.copystat(src, part)
    os.replace(part, dst)


def _free_name(folder: Path, name: str) -> Path:
    """Same name from another card/camera (DSC00001.JPG twice) → DSC00001_2.JPG."""
    p = folder / name
    n = 2
    while p.exists():
        p = folder / f"{Path(name).stem}_{n}{Path(name).suffix}"
        n += 1
    return p


def shoot_folder(lib: Path, kind: str, name: str, date: str) -> Path:
    """Reuse '<any date> <name>' in that kind's folder, else make '<date> <name>' with all subfolders."""
    kdir = lib / KINDS[kind][0]
    kdir.mkdir(parents=True, exist_ok=True)
    for d in kdir.iterdir():
        if d.is_dir() and d.name[11:].lower() == name.lower() and d.name[:10].count("-") == 2:
            shoot = d
            break
    else:
        shoot = kdir / f"{date} {name}"
    for s in SHOOT_DIRS:
        (shoot / s).mkdir(parents=True, exist_ok=True)
    return shoot


def link_project(cfg, name: str, video_dir: Path, category: str | None) -> Path | None:
    """The AutoEdit project of this name reads its clips from the SSD (junction clips → 1 Ruw/Video)."""
    from . import projects

    p = projects.root(cfg) / name
    if not p.exists():
        projects.new(cfg, name)
    clips = p / "clips"
    if clips.exists() and clips.resolve() == video_dir.resolve():
        return p
    if clips.exists():
        if any(clips.iterdir()):
            con.print(f"[yellow]{clips} already has footage; left as it is (clips stay on C:).[/]")
            return p
        clips.rmdir()
    import _winapi                                       # Windows only; a junction needs no admin rights
    _winapi.CreateJunction(str(video_dir), str(clips))
    if category:
        y = p / "project.yaml"
        text = y.read_text(encoding="utf-8")
        if "\ncategory: null" in text:
            y.write_text(text.replace("\ncategory: null", f'\ncategory: "{category}"', 1), encoding="utf-8")
    return p


def offload(cfg, name: str, kind: str = "inbox", since: str | None = None, cards: list[Path] | None = None,
            link: bool = True) -> dict:
    """Copy everything new from the camera card(s) into <library>/<kind>/<date> <name>/1 Ruw/."""
    if kind not in KINDS:
        raise SystemExit(f"--soort must be one of: {', '.join(KINDS)}")
    name = name.strip()
    if not name or name[0] == "." or name[-1] == "." or any(c in name for c in '\\/:*?"<>|'):
        raise SystemExit(f"'{name}' can not be a folder name (no \\ / : * ? \" < > |, no leading or trailing dot)")
    lib = library(cfg)
    if not lib.exists():
        raise SystemExit(f"Library {lib} not found. Is the SSD connected? (config.yaml → paths.library_folder)")
    cards = find_cards() if cards is None else cards
    if not cards:
        raise SystemExit("No camera card found (looked for PRIVATE\\M4ROOT or DCIM on removable drives). Is the SD card in?")

    ledger_path = lib / LEDGER
    ledger = json.loads(ledger_path.read_text(encoding="utf-8")) if ledger_path.exists() else {}
    cutoff = datetime.strptime(since, "%Y-%m-%d").timestamp() if since else 0
    todo = [(f, sub) for card in cards for f, sub in card_files(card)
            if f.stat().st_mtime >= cutoff and _key(f) not in ledger]
    if not todo:
        con.print("[green]Nothing new on the card[/] (everything was offloaded before).")
        return {"copied": 0, "skipped": 0, "shoot": None}

    first = min(f.stat().st_mtime for f, _ in todo)
    shoot = shoot_folder(lib, kind, name, datetime.fromtimestamp(first).strftime("%Y-%m-%d"))
    total = sum(f.stat().st_size for f, _ in todo)
    con.print(f"[bold]Offload[/] {len(todo)} files ({total / 1e9:.1f} GB) → {shoot}")
    copied = skipped = 0
    done_bytes = 0
    for i, (f, sub) in enumerate(todo, 1):
        folder = shoot / "1 Ruw" / sub
        same = folder / f.name
        if same.exists() and same.stat().st_size == f.stat().st_size:
            skipped += 1                                  # copied earlier without the ledger (e.g. by hand)
            ledger[_key(f)] = str(same)
            continue
        dst = _free_name(folder, f.name)
        con.print(f"  {i}/{len(todo)}  {f.name} → {sub}/{dst.name}  ({f.stat().st_size / 1e6:.0f} MB, "
                  f"{100 * done_bytes / max(total, 1):.0f}%)")
        copy_checked(f, dst)
        ledger[_key(f)] = str(dst)
        copied += 1
        done_bytes += f.stat().st_size
        if copied % 20 == 0:                              # survive a pulled card halfway
            ledger_path.write_text(json.dumps(ledger, indent=1), encoding="utf-8")
    ledger_path.write_text(json.dumps(ledger, indent=1), encoding="utf-8")

    project = None
    if link and kind != "inbox":                          # project named like the shoot folder, not like the typing
        project = link_project(cfg, shoot.name[11:], shoot / "1 Ruw" / "Video", KINDS[kind][1])
    con.print(f"[green]{copied} file(s) offloaded and checked[/], {skipped} already there → {shoot}")
    if project:
        con.print(f"  AutoEdit project [bold]{project.name}[/] reads its clips from {shoot / '1 Ruw' / 'Video'}")
    con.print("  The card is untouched; format it in the camera once you are happy.")
    return {"copied": copied, "skipped": skipped, "shoot": str(shoot), "project": str(project) if project else None}
