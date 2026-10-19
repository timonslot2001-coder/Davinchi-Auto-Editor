"""Posting queue + Instagram Reels (Graph API) + TikTok drafts (Content Posting API).

Nothing is posted unless its queue entry has status "approved" — you approve in the dashboard or with
`autoedit approve <id>`. Credentials live in .env (never in code):

  IG_USER_ID=...            # Instagram professional (Creator) account id, linked to a Facebook page
  IG_ACCESS_TOKEN=...       # long-lived token with instagram_content_publish + instagram_manage_insights
  TIKTOK_CLIENT_KEY=...     # from your TikTok developer app (Content Posting API, scope video.upload)
  TIKTOK_CLIENT_SECRET=...
  TIKTOK_REFRESH_TOKEN=...  # from the one-time login (autoedit tiktok-login)
"""
from __future__ import annotations

import json
import os
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

from .config import DATA, ROOT

QUEUE = DATA / "queue.json"
GRAPH = "https://graph.facebook.com/v23.0"
TIKTOK = "https://open.tiktokapis.com/v2"


# ---------------------------------------------------------------- queue

def _load() -> list[dict]:
    return json.loads(QUEUE.read_text(encoding="utf-8")) if QUEUE.exists() else []


def _save(q: list[dict]) -> None:
    QUEUE.write_text(json.dumps(q, indent=1, ensure_ascii=False), encoding="utf-8")


def enqueue(video_9x16: str, cover: str | None, style: str, captions: dict[str, list[dict]],
            when: dict[str, str] | None = None, meta: dict | None = None) -> dict:
    q = _load()
    entry = {"id": uuid.uuid4().hex[:8], "created": datetime.now().isoformat(timespec="seconds"),
             "video": video_9x16, "cover": cover, "style": style,
             "options": captions,                                   # {platform: [3 suggestions]}
             "chosen": {p: 0 for p in captions},                    # index of the chosen suggestion
             "scheduled": when or {}, "status": "pending_approval", "results": {}, "meta": meta or {}}
    q.append(entry)
    _save(q)
    return entry


def get(entry_id: str) -> dict | None:
    return next((e for e in _load() if e["id"] == entry_id), None)


def update(entry_id: str, **changes) -> dict:
    q = _load()
    for e in q:
        if e["id"] == entry_id:
            e.update(changes)
            _save(q)
            return e
    raise KeyError(entry_id)


def entries() -> list[dict]:
    return _load()


def next_slot(cfg, platform: str, after: datetime | None = None) -> str:
    """Next 'best time' slot from config (adjusted over time by performance feedback)."""
    tz = ZoneInfo(cfg.get("posting.timezone", "Europe/Amsterdam"))
    now = after or datetime.now(tz)
    days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    best = None
    for slot in cfg.get(f"posting.best_times.{platform}", []):
        d, hm = slot.split()
        h, m = map(int, hm.split(":"))
        delta = (days.index(d) - now.weekday()) % 7
        t = (now + timedelta(days=delta)).replace(hour=h, minute=m, second=0, microsecond=0)
        if t <= now + timedelta(minutes=20):
            t += timedelta(days=7)
        best = t if best is None or t < best else best
    return (best or now + timedelta(hours=1)).isoformat(timespec="minutes")


# ---------------------------------------------------------------- Instagram

def instagram_post(video: Path, caption: str, cover_offset_ms: int | None = None) -> dict:
    uid, tok = os.environ.get("IG_USER_ID"), os.environ.get("IG_ACCESS_TOKEN")
    if not uid or not tok:
        raise RuntimeError("IG_USER_ID / IG_ACCESS_TOKEN missing in .env (see README → Instagram setup)")
    params = {"media_type": "REELS", "upload_type": "resumable", "caption": caption,
              "share_to_feed": "true", "access_token": tok}
    if cover_offset_ms is not None:
        params["thumb_offset"] = str(cover_offset_ms)
    r = requests.post(f"{GRAPH}/{uid}/media", data=params, timeout=60)
    r.raise_for_status()
    container = r.json()["id"]
    size = video.stat().st_size
    with open(video, "rb") as f:
        up = requests.post(f"https://rupload.facebook.com/ig-api-upload/v23.0/{container}",
                           headers={"Authorization": f"OAuth {tok}", "offset": "0", "file_size": str(size)},
                           data=f, timeout=600)
    up.raise_for_status()
    for _ in range(120):                                  # processing can take a few minutes
        st = requests.get(f"{GRAPH}/{container}", params={"fields": "status_code,status", "access_token": tok},
                          timeout=30).json()
        if st.get("status_code") == "FINISHED":
            break
        if st.get("status_code") == "ERROR":
            raise RuntimeError(f"Instagram processing failed: {st}")
        time.sleep(5)
    pub = requests.post(f"{GRAPH}/{uid}/media_publish", data={"creation_id": container, "access_token": tok},
                        timeout=60)
    pub.raise_for_status()
    media_id = pub.json()["id"]
    link = requests.get(f"{GRAPH}/{media_id}", params={"fields": "permalink", "access_token": tok}, timeout=30).json()
    return {"media_id": media_id, "url": link.get("permalink")}


# ---------------------------------------------------------------- TikTok

def _tiktok_token() -> str:
    key, secret = os.environ.get("TIKTOK_CLIENT_KEY"), os.environ.get("TIKTOK_CLIENT_SECRET")
    refresh = os.environ.get("TIKTOK_REFRESH_TOKEN")
    if not (key and secret and refresh):
        raise RuntimeError("TikTok credentials missing in .env (see README → TikTok setup)")
    r = requests.post(f"{TIKTOK}/oauth/token/", timeout=30, data={
        "client_key": key, "client_secret": secret, "grant_type": "refresh_token", "refresh_token": refresh})
    r.raise_for_status()
    j = r.json()
    if j.get("refresh_token") and j["refresh_token"] != refresh:      # TikTok rotates refresh tokens
        _set_env("TIKTOK_REFRESH_TOKEN", j["refresh_token"])
    return j["access_token"]


def _set_env(key: str, value: str) -> None:
    env = ROOT / ".env"
    lines = env.read_text(encoding="utf-8").splitlines() if env.exists() else []
    lines = [ln for ln in lines if not ln.startswith(f"{key}=")] + [f"{key}={value}"]
    env.write_text("\n".join(lines) + "\n", encoding="utf-8")
    os.environ[key] = value


def tiktok_draft(video: Path) -> dict:
    """Uploads to your TikTok inbox: you get a notification, add the caption/sound and press Post."""
    tok = _tiktok_token()
    size = video.stat().st_size
    chunk = size if size < 64 * 1024 * 1024 else 10 * 1024 * 1024
    count = max(1, size // chunk)
    r = requests.post(f"{TIKTOK}/post/publish/inbox/video/init/", timeout=30,
                      headers={"Authorization": f"Bearer {tok}", "Content-Type": "application/json; charset=UTF-8"},
                      json={"source_info": {"source": "FILE_UPLOAD", "video_size": size,
                                            "chunk_size": chunk, "total_chunk_count": count}})
    r.raise_for_status()
    data = r.json()["data"]
    with open(video, "rb") as f:
        for i in range(count):
            start = i * chunk
            end = size - 1 if i == count - 1 else start + chunk - 1
            f.seek(start)
            body = f.read(end - start + 1)
            put = requests.put(data["upload_url"], data=body, timeout=600, headers={
                "Content-Type": "video/mp4", "Content-Length": str(len(body)),
                "Content-Range": f"bytes {start}-{end}/{size}"})
            put.raise_for_status()
    status = {}
    for _ in range(60):
        status = requests.post(f"{TIKTOK}/post/publish/status/fetch/", timeout=30,
                               headers={"Authorization": f"Bearer {tok}", "Content-Type": "application/json"},
                               json={"publish_id": data["publish_id"]}).json().get("data", {})
        if status.get("status") in ("SEND_TO_USER_INBOX", "PUBLISH_COMPLETE", "FAILED"):
            break
        time.sleep(5)
    if status.get("status") == "FAILED":
        raise RuntimeError(f"TikTok upload failed: {status}")
    return {"publish_id": data["publish_id"], "status": status.get("status")}


# ---------------------------------------------------------------- run

def post_entry(entry_id: str, platforms: list[str] | None = None, force_now: bool = False) -> dict:
    e = get(entry_id)
    if not e:
        raise KeyError(entry_id)
    if e["status"] not in ("approved", "partially_posted"):
        raise PermissionError(f"Entry {entry_id} is '{e['status']}', not approved — nothing posted.")
    results = dict(e.get("results", {}))
    now = datetime.now().astimezone()
    for p in platforms or list(e["options"]):
        if p in results and results[p].get("ok"):
            continue
        when = e["scheduled"].get(p)
        when_dt = datetime.fromisoformat(when) if when else None
        if when_dt and when_dt.tzinfo is None:                   # from the dashboard date picker: local time
            when_dt = when_dt.astimezone()
        if when_dt and not force_now and when_dt > now:
            continue
        opt = e["options"][p][e["chosen"].get(p, 0)]
        try:
            if p == "instagram":
                results[p] = {"ok": True, **instagram_post(Path(e["video"]), opt["full"])}
            elif p == "tiktok":
                results[p] = {"ok": True, **tiktok_draft(Path(e["video"])), "caption_to_paste": opt["full"]}
            results[p]["posted_at"] = now.isoformat(timespec="seconds")
            results[p]["hashtags"] = opt["hashtags"]
        except Exception as ex:                                     # keep going for the other platform
            results[p] = {"ok": False, "error": str(ex)}
    done = all(results.get(p, {}).get("ok") for p in e["options"])
    return update(entry_id, results=results, status="posted" if done else "partially_posted")


def post_due() -> list[dict]:
    """Called every ~15 min by Windows Task Scheduler: posts approved entries whose time has come."""
    return [post_entry(e["id"]) for e in _load() if e["status"] in ("approved", "partially_posted")]
