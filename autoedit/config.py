"""Loads config.yaml, styles.yaml and .env; one place for all paths."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"          # analysis cache, generated sfx, fusion comps, history
DATA.mkdir(exist_ok=True)

load_dotenv(ROOT / ".env")


@dataclass
class Config:
    raw: dict
    styles: dict

    def __getitem__(self, key):
        return self.raw[key]

    def get(self, dotted: str, default=None):
        node = self.raw
        for part in dotted.split("."):
            if not isinstance(node, dict) or part not in node:
                return default
            node = node[part]
        return node

    def style(self, name: str | None) -> dict:
        name = name or self.raw.get("default_style", "lifestyle")
        if name not in self.styles:
            raise SystemExit(f"Unknown style '{name}'. Options: {', '.join(self.styles)}")
        return {"name": name, **self.styles[name]}


def load(path: str | os.PathLike | None = None) -> Config:
    cfg_path = Path(path) if path else ROOT / "config.yaml"
    with open(cfg_path, encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    with open(ROOT / "styles.yaml", encoding="utf-8") as f:
        styles = yaml.safe_load(f)
    user_styles = DATA / "user_styles.yaml"      # presets you saved yourself
    if user_styles.exists():
        with open(user_styles, encoding="utf-8") as f:
            styles.update(yaml.safe_load(f) or {})
    return Config(raw, styles)


def save_user_style(name: str, style: dict) -> None:
    path = DATA / "user_styles.yaml"
    existing = {}
    if path.exists():
        existing = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    existing[name] = {k: v for k, v in style.items() if k != "name"}
    path.write_text(yaml.safe_dump(existing, sort_keys=False, allow_unicode=True), encoding="utf-8")
