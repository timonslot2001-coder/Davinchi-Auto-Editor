"""Photos of a shoot, developed with LightCraft (open-source raw developer, a Lightroom-like editor; lightcraft-cli,
headless). Same idea as the video grade: you see one of your photos finished in a few looks and tap one; every chosen
photo is then developed in that look (auto settings first, then the look) into '<shoot>/2 Bewerkt/Foto/'. When a photo
has a RAW twin (DSC01234.ARW next to DSC01234.JPG) the RAW is developed. The originals are never changed.

config.yaml `lightcraft:` = path to lightcraft-cli.exe (default: the portable copy in ~/.autoedit/lightcraft)."""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path

from . import library, offload
from .library import con

LOOKS = {"auto": ("Automatisch", None), "cinematic": ("Cinematic", "lc.cinematic"),
         "warm_film": ("Warme film", "lc.warm-film"), "crisp": ("Fris landschap", "lc.crisp-landscape"),
         "moody": ("Moody", "lc.moody"), "bw": ("Zwart-wit", "lc.bw-high-contrast")}
RAW = {".arw", ".dng", ".cr3", ".nef", ".raf"}
SHOWN = library.PHOTO_SHOWN | RAW
OUT_DIR = "2 Bewerkt/Foto"
CACHE = library.CACHE.parent / "photo_looks"


def cli(cfg) -> Path:
    p = Path(cfg.get("lightcraft") or "")
    if not p.is_file():
        found = sorted((Path.home() / ".autoedit" / "lightcraft").glob("*/*/lightcraft-cli.exe"))
        p = found[-1] if found else p
    if not p.is_file():
        raise SystemExit("LightCraft is not installed: put the portable zip in ~/.autoedit/lightcraft "
                         "(github.com/storytold/lightcraft releases) or set `lightcraft:` in config.yaml")
    return p


def photos(cfg, rel: str) -> dict:
    """The photos of one shoot, one entry per picture: the JPG (shown) with its RAW twin, or a RAW on its own."""
    shoot = library.resolve_shoot(cfg, rel)
    by_stem: dict[str, dict] = {}
    for f in sorted(shoot.rglob("*")):
        if f.suffix.lower() not in SHOWN or {"2 Bewerkt", "3 Klaar om te posten"} & set(f.relative_to(shoot).parts):
            continue
        e = by_stem.setdefault(str(f.with_suffix("")).lower(), {"name": f.stem})
        e["raw" if f.suffix.lower() in RAW else "path"] = str(f)
    out = [{"name": e["name"], "path": e.get("path") or e["raw"], "raw": e.get("raw")} for e in by_stem.values()]
    done = shoot / OUT_DIR
    return {"rel": rel, "path": str(shoot), "out": str(done), "photos": out,
            "done": sorted(p.name for p in done.glob("*.jpg")) if done.exists() else []}


def _entry(cfg, ref: str) -> dict:
    parts = re.split(r"[\\/]", str(ref).strip())
    if len(parts) != 3:
        raise ValueError(f"not a photo: {ref!r} (expected '<Soort>/<datum naam>/<photo>')")
    hit = next((p for p in photos(cfg, "/".join(parts[:2]))["photos"] if p["name"] == Path(parts[2]).stem), None)
    if hit is None:
        raise FileNotFoundError(f"{parts[2]} is not a photo in {parts[0]}/{parts[1]}")
    return hit


def resolve_photo(cfg, ref: str) -> Path:
    """'<Soort>/<datum naam>/<photo name>' -> the file to develop (the RAW twin when there is one)."""
    hit = _entry(cfg, ref)
    return Path(hit["raw"] or hit["path"])


def _develop(cfg, src: Path, look: str, out: Path, long_edge: int = 0, quality: int = 92) -> None:
    if look not in LOOKS:
        raise ValueError(f"look: one of {list(LOOKS)}")
    preset = LOOKS[look][1]
    cmd = [str(cli(cfg)), "run", "--import", str(src), "develop.auto"]
    if preset:
        cmd += ["preset.apply", f"id={preset}"]
    cmd += ["app.export", f"path={out}", f"longEdge={long_edge}", f"quality={quality}", "conflict=overwrite"]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600)
    fails = [j for j in (json.loads(l) for l in r.stdout.splitlines() if l.startswith("{")) if not j.get("ok")]
    if r.returncode or fails or not out.exists():
        raise RuntimeError(f"LightCraft could not develop {src.name}: {fails or r.stderr.strip()[-300:]}")


def thumb(cfg, ref: str) -> str:
    """A 320 px picture of any photo, RAW included (LightCraft develops it), cached."""
    src = Path(_entry(cfg, ref)["path"])                          # the JPG twin when there is one: instant
    if src.suffix.lower() not in RAW:
        return library.thumb(cfg, str(src))
    out = CACHE / f"t_{hashlib.sha1(f'{src}|{src.stat().st_mtime}'.encode()).hexdigest()[:16]}.jpg"
    if not out.exists():
        CACHE.mkdir(parents=True, exist_ok=True)
        _develop(cfg, src, "auto", out, long_edge=320, quality=80)
    return str(out)


def looks(cfg, ref: str) -> list[dict]:
    """One photo finished in every look (640 px, cached), in LOOKS order: [{"id", "name", "path"}]."""
    src = resolve_photo(cfg, ref)
    key = hashlib.sha1(f"{src}|{src.stat().st_mtime}".encode()).hexdigest()[:16]
    res = []
    for look, (name, _) in LOOKS.items():
        out = CACHE / f"{key}_{look}.jpg"
        if not out.exists():
            CACHE.mkdir(parents=True, exist_ok=True)
            _develop(cfg, src, look, out, long_edge=640, quality=85)
        res.append({"id": look, "name": name, "path": str(out)})
    return res


def export(cfg, refs: list[str], look: str) -> list[str]:
    """Develop every chosen photo in `look`, full size, into '<shoot>/2 Bewerkt/Foto/<name>_<look>.jpg'."""
    if look not in LOOKS:
        raise SystemExit(f"look: one of {', '.join(LOOKS)}")
    if not refs:
        raise SystemExit("pick at least one photo")
    try:
        srcs = [(r, resolve_photo(cfg, r)) for r in refs]
    except (ValueError, FileNotFoundError) as e:
        raise SystemExit(str(e))
    written = []
    for i, (ref, src) in enumerate(srcs, 1):
        shoot = library.resolve_shoot(cfg, "/".join(re.split(r"[\\/]", ref)[:2]))
        out = shoot / OUT_DIR / f"{src.stem}_{look}.jpg"
        out.parent.mkdir(parents=True, exist_ok=True)
        _develop(cfg, src, look, out)
        written.append(str(out))
        con.print(f"  [{i}/{len(srcs)}] {src.name} -> {out.relative_to(offload.library(cfg))}")
    con.print(f"[green]{len(written)} foto('s) in de look {LOOKS[look][0]}[/] -> {OUT_DIR} in de shoot-map")
    return written
