"""Load and validate the Editing DNA package. Read-only: the engine never edits the DNA."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from . import DNA_DIR

REQUIRED_DOCS = ["README_START_HERE.md", "style_dna.json", "STYLE_DNA.md", "EDITING_PSYCHOLOGY.md",
                 "ASSET_LIBRARY.md", "ACCURACY_AND_GAPS.md"]


class DNAError(RuntimeError):
    pass


@dataclass
class Profile:
    id: str
    approved: bool
    data: dict
    rules: dict
    defaults: dict
    fonts: dict

    # convenience accessors used by the planner -------------------------------------------------
    @property
    def pacing_by_fifth(self) -> list[float]:
        return self.data["pacing"]["shot_len_median_by_fifth_s"]

    @property
    def title_timing(self) -> dict:
        return self.data["devices"]["title_slam"]["timing"]

    @property
    def transition_share(self) -> dict:
        return self.data["transitions"]["share"]

    @property
    def accents_per_second(self) -> float:
        return self.data["attention_budget"]["accents_per_second"]


def load(profile_id: str = "P_CINE_MONTAGE", dna_dir: Path = DNA_DIR, require_approved: bool = True) -> Profile:
    missing = [f for f in REQUIRED_DOCS if not (dna_dir / f).exists()]
    if missing:
        raise DNAError(f"DNA package incomplete, missing: {missing} in {dna_dir}")
    d = json.loads((dna_dir / "style_dna.json").read_text(encoding="utf-8"))
    if d.get("schema") != "editing-dna/1.0":
        raise DNAError(f"unknown DNA schema {d.get('schema')}")
    prof = d["profiles"].get(profile_id)
    if not prof or "pacing" not in prof:
        raise DNAError(f"profile {profile_id} not extracted (status: {prof and prof.get('status')})")
    approved = d["approval"].get(profile_id) == "approved"
    if require_approved and not approved:
        raise DNAError(f"profile {profile_id} is not approved (status: {d['approval'].get(profile_id)})")
    rules = {r["id"]: r for r in d["rules"]}
    for rid in d["priority"]:
        if rid not in rules:
            raise DNAError(f"priority lists unknown rule {rid}")
    fonts = {}
    for f in d["assets"]["fonts"]:
        p = dna_dir / f["file"]
        if not p.exists():
            raise DNAError(f"font file missing: {p}")
        fonts[f["family"].split(" (")[0]] = p
    defaults = d["approval"].get(f"{profile_id}_defaults", {"title_variant": "poster_condensed", "accent": "#E70002"})
    return Profile(profile_id, approved, prof, rules, defaults, fonts)


def summary(p: Profile) -> str:
    t = p.title_timing
    return (f"{p.id} ({'approved' if p.approved else 'NOT approved'}) · pacing by fifth {p.pacing_by_fifth} s · "
            f"title in ~{t['in_s_median']} s hold ~{t['hold_s_median']} s · transitions {p.transition_share} · "
            f"accents {p.accents_per_second}/s · default accent {p.defaults.get('accent')}")
