"""Type what you want: a local model (LM Studio on this PC, free, no tokens) turns the sentence into one of the
website's own buttons with its options. It never runs anything itself; the page starts the usual job. Rendering is not
one of its buttons: "Ja, renderen" stays your own press (decision 0015).

config.yaml `local_llm:` {model, url, lms, ttl_s} overrides the defaults below. The model is loaded on the first
question and unloaded by LM Studio after `ttl_s` idle, so the GPU is free again for ComfyUI and Resolve."""
from __future__ import annotations

import json
import subprocess
import urllib.request
from pathlib import Path

DEFAULTS = {"model": "openai/gpt-oss-20b", "url": "http://127.0.0.1:1234",
            "lms": str(Path.home() / "AppData/Local/Programs/LM Studio/resources/app/.webpack/lms.exe"), "ttl_s": 600}
FEEDBACK = ("korter", "langer", "ander_voorstel", "ander_nummer")
LOOKS = ("reference_film", "clean_warm", "moody", "daylight", "blue_hour", "vintage")


def settings(cfg: dict | None) -> dict:
    return {**DEFAULTS, **((cfg or {}).get("local_llm") or {})}


def _get(url: str, timeout: float = 3) -> dict:
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.load(r)


def ensure(s: dict) -> None:
    """LM Studio server up and the model loaded (with an idle TTL)."""
    try:
        models = _get(s["url"] + "/api/v1/models")["models"]
    except OSError:
        if not Path(s["lms"]).exists():
            raise RuntimeError("LM Studio is not installed on this PC (local_llm.lms in config.yaml)")
        subprocess.run([s["lms"], "server", "start"], capture_output=True, timeout=60)
        models = _get(s["url"] + "/api/v1/models")["models"]
    m = next((m for m in models if m["key"] == s["model"]), None)
    if m is None:
        raise RuntimeError(f"model {s['model']} is not downloaded in LM Studio")
    if not m.get("loaded_instances"):
        subprocess.run([s["lms"], "load", s["model"], "--ttl", str(int(s["ttl_s"])), "-y"], capture_output=True,
                       timeout=180)


def tools(songs: list[str], clips: list[str]) -> list[dict]:
    def fn(name, desc, props, required=()):
        return {"type": "function", "function": {"name": name, "description": desc, "parameters": {
            "type": "object", "properties": props, "required": list(required)}}}
    return [
        fn("plan", "Make a new proposal (plan) for this video. Use this when the user names a specific song, a title "
           "text or a length in seconds (also combined, e.g. 'longer with title X').",
           {"song": {"type": "string", "enum": songs}, "title": {"type": "string"},
            "length": {"type": "number", "description": "seconds, 8-30"}}),
        fn("feedback", "Change the current proposal without naming specifics: korter = shorter, langer = longer, "
           "ander_voorstel = same song but other shots, ander_nummer = another song (the user asks for a different "
           "song/nummer/muziek without naming it).",
           {"kind": {"type": "string", "enum": list(FEEDBACK)}}, ["kind"]),
        fn("remove_clip", "Leave one clip out and make a new proposal.", {"clip": {"type": "string", "enum": clips}},
           ["clip"]),
        fn("look", "Change the colour look. reference_film = film (house style), clean_warm = warm and bright, moody, "
           "daylight, blue_hour, vintage.", {"look": {"type": "string", "enum": list(LOOKS)}}, ["look"]),
    ]


SYSTEM = ("You operate the AutoEdit video editor for the project '{name}'. Pick exactly one tool for the user's "
          "request (Dutch or English). Rendering, posting or approving is not yours: then reply in Dutch that the "
          "user presses 'Ja, renderen' or 'Plannen' (not you). If nothing fits, reply in one short Dutch sentence. "
          "Current song: {song}. Songs: {songs}. Clips: {clips}.")


def _clean(call: dict, songs: list[str], clips: list[str]) -> dict | None:
    """The model's tool call as a website action, with every value checked against what exists."""
    name = call.get("name")
    try:
        a = json.loads(call.get("arguments") or "{}")
    except json.JSONDecodeError:
        return None
    if name == "plan":
        out = {"action": "plan"}
        if a.get("song") in songs:
            out["song"] = a["song"]
        if isinstance(a.get("title"), str) and a["title"].strip():
            out["title"] = a["title"].strip()[:40]
        if isinstance(a.get("length"), (int, float)) and 8 <= a["length"] <= 30:
            out["length"] = a["length"]
        return out
    if name == "feedback" and a.get("kind") in FEEDBACK:
        return {"action": "feedback", "kind": a["kind"]}
    if name == "remove_clip" and a.get("clip") in clips:
        return {"action": "feedback", "kind": "eruit", "clip": a["clip"]}
    if name == "look" and a.get("look") in LOOKS:
        return {"action": "look", "look": a["look"]}
    return None


def ask(project: dict, text: str, songs: list[str], cfg: dict | None = None, post=None) -> dict:
    """{'action': {...} | None, 'reply': str}. `post` (tests) replaces the HTTP call to the model."""
    text = (text or "").strip()[:500]
    if not text:
        raise ValueError("type what you want")
    s = settings(cfg)
    clips = [c["name"] for c in project.get("clips") or []]
    body = {"model": s["model"], "temperature": 0, "max_tokens": 400, "tools": tools(songs, clips),
            "messages": [{"role": "system", "content": SYSTEM.format(
                name=project["name"], song=(project.get("settings") or {}).get("song") or "none",
                songs=", ".join(songs) or "none", clips=", ".join(clips) or "none")},
                {"role": "user", "content": text}]}
    if post is None:
        ensure(s)

        def post(b):
            req = urllib.request.Request(s["url"] + "/v1/chat/completions", json.dumps(b).encode(),
                                         {"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.load(r)
    m = post(body)["choices"][0]["message"]
    for c in m.get("tool_calls") or []:
        act = _clean(c.get("function") or {}, songs, clips)
        if act:
            return {"action": act, "reply": ""}
    return {"action": None, "reply": (m.get("content") or "").strip()[:400] or "Dat snap ik niet, probeer het anders."}
