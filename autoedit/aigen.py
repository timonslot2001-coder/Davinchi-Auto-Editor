"""AI shots via Muapi.ai (text/image → video) straight into a project — with a price check first.

  autoedit generate "drone shot over Utrecht at golden hour" --project smoke --seconds 5
  autoedit generate "..." --project smoke --model veo3-fast --role hero_wide --yes

Flow: look the model up in Muapi's public catalog → ask Muapi what it will cost (free, no key needed)
→ check the project's AI budget → ask you to confirm → generate (needs MUAPI_KEY in .env) → poll →
download into <project>/clips/AI_<name>.mp4 and tag it, so the editor uses it like any other shot.
AI clips are graded with the film look only (they're Rec.709 already, not S-Log3).

Costs money per generation (pay-as-you-go credits on muapi.ai). Nothing is generated without a
confirmation, and never above the project's budget (project.yaml: ai_budget_usd, default $5).
"""
from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime
from pathlib import Path

import requests

API = "https://api.muapi.ai/api/v1"

# Short names → catalog model names. Prices are Muapi's catalog base prices (USD) as of 2026-10-21;
# the exact price is always asked from Muapi before generating.
PRESETS = {
    # prices: live estimate for 5 s at 1080p, 2026-10-21
    "seedance":       {"name": "seedance-pro-t2v", "note": "good quality, 1080p, 5-10 s (~$0.62)"},
    "seedance-fast":  {"name": "seedance-pro-t2v-fast", "note": "cheap drafts, 1080p (~$0.30)"},
    "pixverse":       {"name": "pixverse-v5-t2v", "note": "1080p, 5-8 s (~$0.60)"},
    "kling":          {"name": "kling-v2.5-turbo-pro-t2v", "note": "strong motion, 5/10 s (~$0.45)"},
    "veo3-fast":      {"name": "veo3-fast-text-to-video", "note": "Google Veo 3 Fast, 8 s (~$0.60)"},
    "veo3":           {"name": "veo3-text-to-video", "note": "Google Veo 3 quality, 8 s (~$2.50)"},
}
DEFAULT_MODEL = "kling"                                # best price/quality for B-roll


class AIGenError(RuntimeError):
    pass


def _key() -> str:
    k = os.environ.get("MUAPI_KEY")
    if not k:
        raise AIGenError("MUAPI_KEY missing in .env — make an account on muapi.ai, add credit, "
                         "create an API key (Dashboard → API Keys) and put MUAPI_KEY=... in .env")
    return k


def model_info(model: str) -> dict:
    """Catalog entry for a preset or catalog name (public endpoint, no key needed)."""
    name = PRESETS.get(model, {}).get("name", model)
    r = requests.get(f"{API}/models/{name}", timeout=30)
    if r.ok:
        return r.json()
    # names drift: fall back to searching the text-to-video catalog by name / endpoint
    cat = requests.get(f"{API}/models", params={"category": "Text to Video"}, timeout=60)
    cat.raise_for_status()
    items = cat.json() if isinstance(cat.json(), list) else cat.json().get("models", [])
    for m in items:
        if name in (m.get("name"), m.get("endpoint"), m.get("endpoint_url")):
            return m
    raise AIGenError(f"Model '{model}' not found in Muapi's catalog")


def build_body(info: dict, prompt: str, seconds: int, aspect: str, image_url: str | None = None) -> dict:
    fields = set(info.get("input_fields") or (info.get("input_schema") or {}).get("properties", {}).keys() or [])
    body = {"prompt": prompt}
    if not fields or "aspect_ratio" in fields:
        body["aspect_ratio"] = aspect
    if "duration" in fields:
        body["duration"] = seconds
    if "resolution" in fields:
        body["resolution"] = "1080p"
    if "camera_fixed" in fields:
        body["camera_fixed"] = False
    if image_url:
        body["image_url"] = image_url
    return body


def estimate(info: dict, body: dict) -> float:
    """Exact price from Muapi (public endpoint, free)."""
    r = requests.post(f"{API}/models/{info['name']}/estimate-cost", json=body, timeout=30)
    if r.ok and "cost" in r.json():
        return float(r.json()["cost"])
    return float(info.get("cost") or 0)


# ---------------------------------------------------------------- budget ledger (per project)

def _ledger(project: Path) -> dict:
    f = project / "ai_spend.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {"spent_usd": 0.0, "items": []}


def _save_ledger(project: Path, led: dict) -> None:
    (project / "ai_spend.json").write_text(json.dumps(led, indent=1), encoding="utf-8")


# ---------------------------------------------------------------- generate

def generate(project: Path, prompt: str, model: str = DEFAULT_MODEL, seconds: int = 5, aspect: str = "16:9",
             role: str = "establish", budget_usd: float = 5.0, yes: bool = False, image: str | None = None,
             log=print, ask=input) -> Path:
    info = model_info(model)
    endpoint = (info.get("endpoint_url") or info.get("endpoint") or info["name"]).strip("/")
    image_url = None
    if image:
        image_url = image if image.startswith("http") else upload(Path(image))
    body = build_body(info, prompt, seconds, aspect, image_url)
    cost = estimate(info, body)
    led = _ledger(project)
    left = budget_usd - led["spent_usd"]
    log(f"AI shot · model {info['name']} · {body.get('duration', '?')} s · {aspect}")
    log(f"  price: ${cost:.2f}   project budget left: ${left:.2f} of ${budget_usd:.2f}")
    if cost > left:
        raise AIGenError(f"Over budget: this costs ${cost:.2f}, only ${left:.2f} left for this project "
                         f"(raise ai_budget_usd in project.yaml if you want)")
    if not yes:
        if ask(f"  Generate for ${cost:.2f}? [y/N] ").strip().lower() not in ("y", "yes", "j", "ja"):
            raise AIGenError("Cancelled — nothing was charged.")

    key = _key()
    r = requests.post(f"{API}/{endpoint}", json=body, timeout=60,
                      headers={"x-api-key": key, "Content-Type": "application/json"})
    if not r.ok:
        raise AIGenError(f"Muapi refused the request ({r.status_code}): {r.text[:300]}")
    rid = r.json().get("request_id")
    log(f"  submitted ({rid}), waiting for the result…")
    res = {}
    for _ in range(360):                                   # up to ~30 min (video models can queue)
        res = requests.get(f"{API}/predictions/{rid}/result", headers={"x-api-key": key}, timeout=30).json()
        st = res.get("status")
        if st == "completed":
            break
        if st in ("failed", "cancelled"):
            raise AIGenError(f"Generation {st} (failed generations are not charged): {res.get('error', '')}")
        time.sleep(5)
    else:
        raise AIGenError(f"Still not done after 30 min — check request {rid} on muapi.ai")
    url = (res.get("outputs") or [None])[0]
    if not url:
        raise AIGenError(f"No output in the result: {res}")
    charged = float((res.get("cost") or {}).get("amount_usd", cost))

    slug = re.sub(r"[^a-z0-9]+", "-", prompt.lower()).strip("-")[:40] or "shot"
    out = project / "clips" / f"AI_{slug}_{datetime.now():%H%M%S}.mp4"
    with requests.get(url, stream=True, timeout=300) as dl:
        dl.raise_for_status()
        with open(out, "wb") as f:
            for chunk in dl.iter_content(1 << 20):
                f.write(chunk)

    led["spent_usd"] = round(led["spent_usd"] + charged, 4)
    led["items"].append({"file": out.name, "prompt": prompt, "model": info["name"], "usd": charged,
                         "request_id": rid, "at": datetime.now().isoformat(timespec="seconds")})
    _save_ledger(project, led)
    tag(project, out.name, role, prompt)
    log(f"  ✓ saved {out.name} (${charged:.2f}; project total ${led['spent_usd']:.2f})")
    return out


def upload(path: Path) -> str:
    key = _key()
    with open(path, "rb") as f:
        r = requests.post(f"{API}/upload_file", headers={"x-api-key": key}, files={"file": f}, timeout=300)
    r.raise_for_status()
    j = r.json()
    return j.get("url") or j.get("file_url") or next(iter(j.values()))


def tag(project: Path, clip_name: str, role: str, desc: str) -> None:
    f = project / "tags.json"
    tags = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
    tags[clip_name] = {"role": role, "desc": f"AI: {desc}", "ai": True, "best": [1.0, 3.0]}
    f.write_text(json.dumps(tags, indent=1, ensure_ascii=False), encoding="utf-8")


def balance() -> float:
    r = requests.get(f"{API}/account/balance", headers={"x-api-key": _key()}, timeout=30)
    r.raise_for_status()
    return float(r.json().get("balance", 0))
