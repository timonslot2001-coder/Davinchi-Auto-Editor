"""Free AI shots on your own GPU via ComfyUI (Wan 2.2 5B) — no credits.

  autoedit generate "drone shot over Utrecht at golden hour" --project smoke --model local-wan
  autoedit generate "..." --project smoke --model local-wan-draft      # faster, lower res (test prompts)

Needs Comfy Desktop running (it serves an API on localhost; Desktop uses port 8000, plain ComfyUI 8188)
and the Wan 2.2 5B files in its models folders (or in "AI Models" linked via extra_model_paths.yaml):
  diffusion_models/wan2.2_ti2v_5B_fp16.safetensors
  text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors
  vae/wan2.2_vae.safetensors
The workflow mirrors ComfyUI's "Wan 2.2 5B Video Generation" template (24 fps, uni_pc, shift 8).
"""
from __future__ import annotations

import json
import random
import re
import time
import uuid
from datetime import datetime
from pathlib import Path

import requests

from .aigen import AIGenError, tag

PORTS = (8000, 8188)
# width x height for 16:9 (swapped for 9:16), steps
LOCAL_PRESETS = {
    "local-wan":       {"size": (1280, 704), "steps": 20, "note": "Wan 2.2 5B, 720p, free (your GPU)"},
    "local-wan-draft": {"size": (832, 480), "steps": 14, "note": "Wan 2.2 5B, 480p draft, free + fast"},
}
NEGATIVE = ("blurry, low quality, jpeg artifacts, distorted, deformed, extra limbs, watermark, text, subtitles, "
            "static, frozen frame, overexposed, oversaturated")


def server(url: str | None = None) -> str:
    cands = [url] if url else [f"http://127.0.0.1:{p}" for p in PORTS]
    for u in cands:
        try:
            if requests.get(f"{u}/system_stats", timeout=3).ok:
                return u
        except requests.RequestException:
            pass
    raise AIGenError("ComfyUI is not running — start Comfy Desktop first (it must be open while generating)")


def workflow(prompt: str, seconds: int, aspect: str, preset: dict, seed: int, prefix: str,
             image_name: str | None = None) -> dict:
    w, h = preset["size"]
    if aspect == "9:16":
        w, h = h, w
    elif aspect == "1:1":
        w = h
    length = int(seconds * 24) // 4 * 4 + 1                 # Wan wants 4n+1 frames
    g = {
        "1": {"class_type": "UNETLoader", "inputs": {"unet_name": "wan2.2_ti2v_5B_fp16.safetensors",
                                                    "weight_dtype": "default"}},
        "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": "umt5_xxl_fp8_e4m3fn_scaled.safetensors",
                                                    "type": "wan", "device": "default"}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": "wan2.2_vae.safetensors"}},
        "4": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["2", 0]}},
        "5": {"class_type": "CLIPTextEncode", "inputs": {"text": NEGATIVE, "clip": ["2", 0]}},
        "6": {"class_type": "ModelSamplingSD3", "inputs": {"shift": 8.0, "model": ["1", 0]}},
        "7": {"class_type": "Wan22ImageToVideoLatent", "inputs": {"width": w, "height": h, "length": length,
                                                                  "batch_size": 1, "vae": ["3", 0]}},
        "8": {"class_type": "KSampler", "inputs": {"seed": seed, "steps": preset["steps"], "cfg": 5.0,
                                                   "sampler_name": "uni_pc", "scheduler": "simple", "denoise": 1.0,
                                                   "model": ["6", 0], "positive": ["4", 0], "negative": ["5", 0],
                                                   "latent_image": ["7", 0]}},
        "9": {"class_type": "VAEDecode", "inputs": {"samples": ["8", 0], "vae": ["3", 0]}},
        "10": {"class_type": "CreateVideo", "inputs": {"images": ["9", 0], "fps": 24.0}},
        "11": {"class_type": "SaveVideo", "inputs": {"video": ["10", 0], "filename_prefix": prefix,
                                                     "format": "mp4", "codec": "h264"}},
    }
    if image_name:                                          # image-to-video: first frame = your still
        g["12"] = {"class_type": "LoadImage", "inputs": {"image": image_name}}
        g["7"]["inputs"]["start_image"] = ["12", 0]
    return g


def _upload(base: str, path: Path) -> str:
    with open(path, "rb") as f:
        r = requests.post(f"{base}/upload/image", files={"image": (path.name, f)}, data={"overwrite": "true"},
                          timeout=120)
    r.raise_for_status()
    return r.json()["name"]


def generate(project: Path, prompt: str, model: str = "local-wan", seconds: int = 5, aspect: str = "16:9",
             role: str = "establish", image: str | None = None, url: str | None = None, seed: int | None = None,
             log=print) -> Path:
    preset = LOCAL_PRESETS[model]
    base = server(url)
    seed = seed if seed is not None else random.randint(1, 2**31)
    image_name = _upload(base, Path(image)) if image else None
    prefix = f"autoedit/{uuid.uuid4().hex[:8]}"
    g = workflow(prompt, seconds, aspect, preset, seed, prefix, image_name)
    log(f"AI shot · {model} (local, free) · {seconds} s · {aspect} · {preset['size'][0]}x{preset['size'][1]}"
        f" · seed {seed}")
    r = requests.post(f"{base}/prompt", json={"prompt": g, "client_id": "autoedit"}, timeout=60)
    if not r.ok:
        raise AIGenError(f"ComfyUI refused the workflow ({r.status_code}): {r.text[:500]}")
    pid = r.json()["prompt_id"]
    t0 = time.time()
    hist = {}
    while time.time() - t0 < 3600:
        hist = requests.get(f"{base}/history/{pid}", timeout=30).json().get(pid) or {}
        st = hist.get("status", {})
        if st.get("completed") or st.get("status_str") == "error":
            break
        time.sleep(3)
    else:
        raise AIGenError("Still not done after 60 min — check the ComfyUI window")
    if hist.get("status", {}).get("status_str") == "error":
        msgs = [m for m in hist["status"].get("messages", []) if m[0] == "execution_error"]
        raise AIGenError(f"ComfyUI error: {json.dumps(msgs)[:600]}")
    files = [f for out in hist.get("outputs", {}).values() for v in out.values() if isinstance(v, list)
             for f in v if isinstance(f, dict) and "filename" in f]
    if not files:
        raise AIGenError(f"No video in ComfyUI's output: {json.dumps(hist.get('outputs'))[:400]}")
    f0 = files[0]
    slug = re.sub(r"[^a-z0-9]+", "-", prompt.lower()).strip("-")[:40] or "shot"
    out = project / "clips" / f"AI_{slug}_{datetime.now():%H%M%S}.mp4"
    out.parent.mkdir(exist_ok=True)
    with requests.get(f"{base}/view", params={"filename": f0["filename"], "subfolder": f0.get("subfolder", ""),
                                              "type": f0.get("type", "output")}, stream=True, timeout=300) as dl:
        dl.raise_for_status()
        with open(out, "wb") as fh:
            for chunk in dl.iter_content(1 << 20):
                fh.write(chunk)
    tag(project, out.name, role, prompt)
    log(f"  ✓ saved {out.name} in {time.time() - t0:.0f} s ($0.00 — local)")
    return out
