"""Form-field checks shared by the web app (app.py) and the Artifact studio (studio.py). No Flask here, so the studio
CLI can import it on its own. Every value that ends up in an `engine ...`/`autoedit ...` argv passes one of these."""
from __future__ import annotations

import re

LOOKS = {"reference_film", "clean_warm", "moody", "daylight", "blue_hour", "vintage"}   # keep in step with engine grade
GRADES = {"auto", "slog3", "rec709", "none"}


def _num(v, lo, hi, cast=float):
    if v in (None, ""):
        return None
    x = cast(v)
    if not lo <= x <= hi:
        raise ValueError(f"{x} outside {lo}-{hi}")
    return str(x)


def _text(v, maxlen=200):
    v = (v or "").strip()
    if len(v) > maxlen or any(c in v for c in "\r\n\0"):
        raise ValueError("text too long or has line breaks")
    return v


def _name(v):
    """Project/shoot name that is a plain folder name: no '..', no path characters, no leading/trailing dot or space."""
    name = _text(v, 80)
    if not name or not re.fullmatch(r"[\w .,'&()\-]+", name) or name[0] in ". " or name[-1] in ". ":
        raise ValueError("use letters, digits, spaces and - _ . , ' & ( ) in the name (not starting/ending with a dot)")
    return name


def grade_args(b, action, pr):
    """--grade is part of the approval (set at plan): render ignores the body and sends the approved mode itself.
    The look lives in cine_montage/grade.json, so render never gets --look; preview takes a non-persisting try-out."""
    a = []
    if action == "render":
        mode = ((pr["cine"].get("approval") or {}).get("grade_mode")) or "auto"
        if mode != "auto" and mode in GRADES:
            a += ["--grade", mode]
    elif b.get("grade") in GRADES:
        a += ["--grade", b["grade"]]
    if action == "preview" and b.get("look") in LOOKS:
        a += ["--look", b["look"]]
    return a
