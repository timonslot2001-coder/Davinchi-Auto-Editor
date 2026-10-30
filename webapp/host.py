"""Where the work happens. LocalHost runs commands and reads files on this Windows PC. RemoteHost does the same through
the worker (`python -m webapp worker`), which is how the Docker container reaches Resolve, the GPU and the footage.

Only the editor's own commands can run (ALLOWED), one job at a time, in a queue: renders and Resolve builds are heavy."""
from __future__ import annotations

import os
import queue as _queue
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path

from . import query

REPO = query.REPO
LOG_DIR = REPO / "data" / "webapp_jobs"

# first argument -> allowed subcommands. Interactive or always-on commands (tiktok-login, watch, dashboard) are left out.
ALLOWED = {
    "engine": {"validate", "plan", "check", "approve", "preview", "render", "qa"},
    "autoedit": {"project", "run", "analyze", "import", "new", "projects", "queue", "approve", "post", "post-due",
                 "stats", "report", "ideas", "generate", "ai-models", "ai-balance", "sfx", "optimize", "explainer",
                 "repurpose"},
}
WRITABLE = {"project.yaml", "comments.json"}                     # plus audio files into the music folder


def check_args(args: list[str]) -> None:
    if not args or args[0] not in ALLOWED or len(args) < 2 or args[1] not in ALLOWED[args[0]]:
        raise PermissionError(f"command not allowed: {' '.join(args[:2])}")
    if any(not isinstance(a, str) for a in args):
        raise PermissionError("arguments must be text")


def check_path(path: str, write: bool = False) -> Path:
    p = Path(path).resolve()
    roots = [Path(r).resolve() for r in query.roots().values()]
    inside = any(p == r or r in p.parents for r in roots)
    if not inside:                                               # project clips can be a junction to another drive
        proj_root = Path(query.roots()["projects"]).resolve()
        inside = any((d / "clips").resolve() in p.parents for d in proj_root.iterdir() if (d / "clips").exists())
    if not inside:
        raise PermissionError("path outside the AutoEdit folders")
    if write and not (p.name in WRITABLE or (p.parent == Path(query.roots()["music"]).resolve()
                                             and p.suffix.lower() in query.AUDIO_EXT)):
        raise PermissionError("this file can not be written from the web app")
    return p


class LocalHost:
    mode = "local"

    def __init__(self):
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        self.jobs: dict[str, dict] = {}
        self.procs: dict[str, subprocess.Popen] = {}
        self.todo: _queue.Queue = _queue.Queue()
        threading.Thread(target=self._loop, daemon=True).start()

    # ------------------------------------------------------------ jobs
    def run(self, args: list[str], label: str = "", project: str | None = None) -> dict:
        check_args(args)
        jid = time.strftime("%m%d-%H%M%S-") + uuid.uuid4().hex[:4]
        job = {"id": jid, "args": args, "label": label or " ".join(args[:2]), "project": project, "status": "queued",
               "created": time.time(), "started": None, "ended": None, "returncode": None, "log": []}
        self.jobs[jid] = job
        self.todo.put(jid)
        return self._public(job)

    def _loop(self):
        while True:
            jid = self.todo.get()
            job = self.jobs[jid]
            if job["status"] == "cancelled":
                continue
            mod, cwd = job["args"][0], (query.ENGINE_DIR if job["args"][0] == "engine" else REPO)
            env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUNBUFFERED": "1", "NO_COLOR": "1",
                   "TERM": "dumb", "COLUMNS": "140"}
            job.update(status="running", started=time.time())
            logf = (LOG_DIR / f"{jid}.log").open("w", encoding="utf-8")
            try:
                proc = subprocess.Popen([sys.executable, "-m", mod, *job["args"][1:]], cwd=cwd, env=env, text=True,
                                        encoding="utf-8", errors="replace", stdout=subprocess.PIPE,
                                        stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                self.procs[jid] = proc
                for line in proc.stdout:
                    line = line.rstrip()
                    job["log"].append(line)
                    logf.write(line + "\n")
                    if len(job["log"]) > 3000:
                        del job["log"][:500]
                proc.wait()
                job["returncode"] = proc.returncode
                if job["status"] != "cancelled":
                    job["status"] = "done" if proc.returncode == 0 else "failed"
            except Exception as e:
                job["log"].append(f"could not start: {e}")
                job["status"] = "failed"
            finally:
                logf.close()
                job["ended"] = time.time()
                self.procs.pop(jid, None)

    def _public(self, job: dict, since: int | None = None) -> dict:
        out = {k: v for k, v in job.items() if k != "log"}
        if since is not None:
            out["log"], out["log_len"] = job["log"][since:], len(job["log"])
        return out

    def list_jobs(self) -> list[dict]:
        return [self._public(j) for j in sorted(self.jobs.values(), key=lambda j: -j["created"])][:100]

    def job(self, jid: str, since: int = 0) -> dict:
        if jid not in self.jobs:
            raise KeyError(jid)
        return self._public(self.jobs[jid], since)

    def cancel(self, jid: str) -> dict:
        job = self.jobs[jid]
        if job["status"] in ("queued", "running"):
            job["status"] = "cancelled"
            if jid in self.procs:
                self.procs[jid].terminate()
        return self._public(job)

    # ------------------------------------------------------------ data and files
    def call(self, name: str, params: dict | None = None):
        if name not in query.CALLS:
            raise KeyError(name)
        return query.CALLS[name](**(params or {}))

    def file_path(self, path: str) -> Path:
        p = check_path(path)
        if not p.is_file():
            raise FileNotFoundError(path)
        return p

    def write_file(self, path: str, data: bytes) -> dict:
        p = check_path(path, write=True)
        p.write_bytes(data)
        return {"saved": str(p)}


class RemoteHost:
    """Same interface as LocalHost, over HTTP to the worker on Windows."""
    mode = "docker"

    def __init__(self, url: str, token: str):
        import requests
        self.url, self.s = url.rstrip("/"), requests.Session()
        self.s.headers["X-Token"] = token

    def _req(self, method: str, path: str, **kw):
        r = self.s.request(method, self.url + path, timeout=kw.pop("timeout", 30), **kw)
        if r.status_code >= 400:
            raise RuntimeError(r.json().get("error", r.text) if "json" in r.headers.get("content-type", "") else r.text)
        return r.json()

    def run(self, args, label="", project=None):
        return self._req("POST", "/jobs", json={"args": args, "label": label, "project": project})

    def list_jobs(self):
        return self._req("GET", "/jobs")

    def job(self, jid, since=0):
        return self._req("GET", f"/jobs/{jid}", params={"since": since})

    def cancel(self, jid):
        return self._req("POST", f"/jobs/{jid}/cancel")

    def call(self, name, params=None):
        return self._req("POST", f"/call/{name}", json=params or {}, timeout=60)

    def stream_file(self, path: str, headers: dict):
        return self.s.get(self.url + "/file", params={"path": path}, headers=headers, stream=True, timeout=60)

    def write_file(self, path, data):
        return self._req("PUT", "/file", params={"path": path}, data=data, timeout=300)
