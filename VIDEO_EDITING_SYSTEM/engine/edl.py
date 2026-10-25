"""Edit decision list: the single deterministic description of an edit. JSON round-trip, validation."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class Event:
    id: str
    out_in: float                      # output timeline seconds
    out_out: float
    source: str                        # clip path (or "" for generated)
    src_in: float
    src_out: float
    transition_in: str = "T_HARD"      # T_HARD | T_FLASH | T_WHIP
    treatment: list = field(default_factory=list)   # e.g. ["D_CARD_WHITE"], ["D_BW"]
    rule: list = field(default_factory=list)        # DNA rule ids
    why: str = ""
    confidence: str = "medium"
    params: dict = field(default_factory=dict)


@dataclass
class Overlay:
    id: str
    component: str                     # title_slam | side_labels | hud_labels
    out_in: float
    out_out: float
    params: dict
    rule: list = field(default_factory=list)
    why: str = ""


@dataclass
class EDL:
    project: str
    profile: str
    width: int
    height: int
    fps: float
    duration: float
    accent: str
    music: str | None
    music_offset: float
    events: list
    overlays: list
    notes: list = field(default_factory=list)
    open_questions: list = field(default_factory=list)

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=1, ensure_ascii=False)

    def save(self, path: Path) -> None:
        path.write_text(self.to_json(), encoding="utf-8")

    @staticmethod
    def load(path: Path) -> "EDL":
        d = json.loads(path.read_text(encoding="utf-8"))
        d["events"] = [Event(**e) for e in d["events"]]
        d["overlays"] = [Overlay(**o) for o in d["overlays"]]
        return EDL(**d)

    def validate(self) -> list[str]:
        errs, t = [], 0.0
        for e in self.events:
            if abs(e.out_in - t) > 1e-3:
                errs.append(f"{e.id}: gap/overlap at {t:.3f} vs {e.out_in:.3f}")
            if e.out_out - e.out_in < 1 / self.fps - 1e-6:
                errs.append(f"{e.id}: shorter than one frame")
            if e.source and (e.src_out - e.src_in) + 1e-3 < (e.out_out - e.out_in):
                errs.append(f"{e.id}: source shorter than output slot")
            if e.source and not Path(e.source).exists():
                errs.append(f"{e.id}: source missing {e.source}")
            t = e.out_out
        if abs(t - self.duration) > 1e-3:
            errs.append(f"events end at {t:.3f}, duration {self.duration:.3f}")
        titles = [o for o in self.overlays if o.component == "title_slam"]
        if len(titles) > 1:
            errs.append("RULE_TITLE: more than one title")
        for o in self.overlays:                       # attention budget: no flash/whip on a title frame
            for e in self.events:
                if e.transition_in != "T_HARD" and o.out_in - 1e-3 <= e.out_in <= o.out_out + 1e-3 and o.component == "title_slam":
                    errs.append(f"budget: {e.transition_in} at {e.out_in:.2f} inside title {o.id}")
        return errs
