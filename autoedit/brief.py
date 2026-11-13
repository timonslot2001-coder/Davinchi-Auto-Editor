"""The brief: what Timon chooses before an edit is cut. Song, rhythm, length and his own PowerGrade come first
(brainstorm 2026-11-06: "ritme en muziek moet een keuzemogelijkheid zijn voordat je begint te knippen"); the editor
never picks a song or a look for him. Stored per project under `edit:` in project.yaml, so a second edit is one click.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, fields, replace

LENGTHS = {"kort": 10.0, "normaal": 20.0, "lang": 30.0}       # seconds
RHYTHMS = ("beat", "rustig")
KINDS = ("auto", "montage", "praat")
ASPECTS = ("9:16", "16:9")
NO_MUSIC = "none"


@dataclass
class Brief:
    song: str | None = None              # file name or part of it; "none" = no music
    song_start: float | None = None      # seconds into the song; None = the editor picks the part around the drop
    rhythm: str = "rustig"               # beat = cut on the beat / rustig = about a bar per shot
    length: str = "normaal"
    grade: str | None = None             # the name of one of his PowerGrades, or "basis"
    kind: str = "auto"                   # auto / montage / praat
    aspect: str = "9:16"

    @property
    def seconds(self) -> float:
        return LENGTHS[self.length]


def from_project(settings: dict) -> Brief:
    """The brief stored in project.yaml (`edit:`); unknown keys are ignored."""
    raw = dict((settings or {}).get("edit") or {})
    known = {f.name for f in fields(Brief)}
    kw = {k: v for k, v in raw.items() if k in known and v is not None}
    start = kw.pop("song_start", None)
    if start not in (None, "auto"):
        try:
            kw["song_start"] = float(start)
        except (TypeError, ValueError):
            pass
    return Brief(**{k: (str(v) if k != "song_start" else v) for k, v in kw.items()})


def merge(base: Brief, **overrides) -> Brief:
    """`base` with the given choices on top; a None override keeps what was there."""
    return replace(base, **{k: v for k, v in overrides.items() if v is not None})


def to_project(b: Brief) -> dict:
    d = asdict(b)
    d["song_start"] = "auto" if b.song_start is None else b.song_start
    return d


def _choices(items: list[str]) -> str:
    return ", ".join(items) if items else "(nog geen)"


def problems(b: Brief, songs: list[str], grades: list[str]) -> list[str]:
    """Why this brief cannot be cut yet, in plain Dutch; an empty list means ready."""
    out = []
    if not b.song:
        out.append(f"Kies een liedje. Je hebt: {_choices(songs)}. Zonder muziek: none.")
    elif b.song != NO_MUSIC and not any(b.song.lower() in s.lower() for s in songs):
        out.append(f"Het liedje '{b.song}' staat niet in je muziekmap. Je hebt: {_choices(songs)}.")
    if not b.grade:
        out.append(f"Kies een kleur (PowerGrade). Je hebt: {_choices(grades)}.")
    elif not any(b.grade.lower() == g.lower() or b.grade.lower() in g.lower() for g in grades):
        out.append(f"De kleur '{b.grade}' is er niet. Je hebt: {_choices(grades)}.")
    if b.rhythm not in RHYTHMS:
        out.append(f"Ritme '{b.rhythm}' bestaat niet. Kies: {_choices(list(RHYTHMS))}.")
    if b.length not in LENGTHS:
        out.append(f"Lengte '{b.length}' bestaat niet. Kies: {_choices(list(LENGTHS))}.")
    if b.kind not in KINDS:
        out.append(f"Soort '{b.kind}' bestaat niet. Kies: {_choices(list(KINDS))}.")
    if b.aspect not in ASPECTS:
        out.append(f"Formaat '{b.aspect}' bestaat niet. Kies: {_choices(list(ASPECTS))}.")
    if b.song_start is not None and b.song_start < 0:
        out.append("Het startpunt in het liedje kan niet onder 0 seconden liggen.")
    return out
