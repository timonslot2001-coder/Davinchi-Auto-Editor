"""Cine-montage editing engine: applies the approved Editing DNA (EDITING_DNA_PACKAGE/style_dna.json) to new footage.

Pipeline:  inventory (media.py) -> plan/EDL (planner.py) -> storyboard (storyboard.py) -> [user approval]
           -> render (render.py, graphics.py) -> QA (qa.py).   CLI: python -m engine <command>  (see cli.py)
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent            # VIDEO_EDITING_SYSTEM/
REPO = ROOT.parent
DNA_DIR = REPO / "EDITING_DNA_PACKAGE"
