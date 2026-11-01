"""Grade choice per project: look + strength + exposure, stored in <project>/cine_montage/grade.json.

The grade is part of the approval (gate B): `approve` records key(grade) and `render` refuses when the grade changed
afterwards. Kept free of numpy so the CLI can parse arguments without loading the grade code (autoedit/grade.py).
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path

# the film looks of autoedit/grade.py LOOKS, without "none" (tests/grade_gate_test.py keeps them in sync)
LOOKS: tuple[str, ...] = ("reference_film", "clean_warm", "moody", "daylight", "blue_hour", "vintage")
STRENGTH = (0.0, 1.0)
EXPOSURE = (-3.0, 0.5)                                           # stops, only applied to log clips


@dataclass(frozen=True)
class Grade:
    look: str = "reference_film"
    strength: float = 1.0
    exposure: float = -1.75


def validate(g: Grade) -> None:
    if g.look not in LOOKS:
        raise ValueError(f"onbekende look '{g.look}': kies uit {', '.join(LOOKS)}")
    if not STRENGTH[0] <= g.strength <= STRENGTH[1]:
        raise ValueError(f"sterkte {g.strength} valt buiten {STRENGTH[0]}..{STRENGTH[1]}")
    if not EXPOSURE[0] <= g.exposure <= EXPOSURE[1]:
        raise ValueError(f"belichting {g.exposure} valt buiten {EXPOSURE[0]}..{EXPOSURE[1]} stops")


def load(work: Path) -> Grade:
    f = Path(work) / "grade.json"
    if not f.exists():
        return Grade()
    d = json.loads(f.read_text(encoding="utf-8"))
    return Grade(str(d.get("look", Grade.look)), float(d.get("strength", Grade.strength)),
                 float(d.get("exposure", Grade.exposure)))


def save(work: Path, g: Grade) -> None:
    validate(g)
    (Path(work) / "grade.json").write_text(json.dumps(asdict(g), indent=1), encoding="utf-8")


def key(g: Grade) -> str:
    return hashlib.sha1(json.dumps([g.look, round(g.strength, 3), round(g.exposure, 3)]).encode()).hexdigest()[:12]
