"""Drop folder: put clips in a new subfolder of paths.drop_folder → rough cut is built automatically.

Every video gets your house style. The subfolder name can carry the category for captions/hashtags:
"fitness - leg day", "travel porto", "fashion fits"… The build starts once the files stop growing.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from rich.console import Console

from . import pipeline
from .analyze import VIDEO_EXT
from .config import DATA

con = Console()
DONE = DATA / "drop_done.json"


def _snapshot(folder: Path) -> dict[str, int]:
    return {str(p): p.stat().st_size for p in folder.rglob("*") if p.is_file() and p.suffix.lower() in VIDEO_EXT}


def watch(cfg, interval: int = 15, settle: int = 30, render: bool = True):
    root = Path(cfg.get("paths.drop_folder"))
    root.mkdir(parents=True, exist_ok=True)
    done = set(json.loads(DONE.read_text())) if DONE.exists() else set()
    seen: dict[str, tuple[dict, float]] = {}
    con.print(f"[bold]Watching[/] {root}  (drop a folder of clips in here; Ctrl+C to stop)")
    while True:
        for sub in sorted(p for p in root.iterdir() if p.is_dir()):
            if str(sub) in done:
                continue
            snap = _snapshot(sub)
            if not snap:
                continue
            prev = seen.get(str(sub))
            if prev is None or prev[0] != snap:
                seen[str(sub)] = (snap, time.time())
                continue
            if time.time() - prev[1] < settle:
                continue
            cat = next((c for c in ("fitness", "travel", "fashion", "lifestyle") if c in sub.name.lower()), None)
            try:
                pipeline.run(cfg, sub, None, variants="A", render=render, category=cat)
            except SystemExit as e:
                con.print(f"[red]{sub.name}: {e}[/]")
            except Exception as e:                       # keep watching other folders
                con.print(f"[red]{sub.name} failed: {e!r}[/]")
            done.add(str(sub))
            DONE.write_text(json.dumps(sorted(done)))
        time.sleep(interval)
