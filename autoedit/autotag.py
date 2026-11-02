"""Shot tags without typing: a rough role per clip from one frame, for the story order of an AutoEdit build.

  face filling the frame -> close · a face -> subject · no face, bright open top -> establish · else detail

Only clips without a tag get one (marked "auto": true); tags you or Claude wrote in tags.json always win.
OpenCV's YuNet face detector on a 320 px frame at 40 % of the clip: cheap and local, and wrong now and then. It needs
the model file data/models/face_detection_yunet.onnx (OpenCV model zoo); without it nothing is tagged."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import numpy as np

from .analyze import VIDEO_EXT
from .config import DATA

W = 320
MODEL = DATA / "models" / "face_detection_yunet.onnx"


def _frame(path: Path) -> np.ndarray | None:
    import imageio_ffmpeg
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    probe = subprocess.run([ff, "-hide_banner", "-i", str(path)], capture_output=True, text=True, errors="ignore").stderr
    import re
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", probe)
    t = (int(m[1]) * 3600 + int(m[2]) * 60 + float(m[3])) * 0.4 if m else 0
    raw = subprocess.run([ff, "-v", "error", "-ss", f"{t:.2f}", "-i", str(path), "-frames:v", "1", "-vf",
                          f"scale={W}:-2", "-f", "rawvideo", "-pix_fmt", "bgr24", "-"], capture_output=True).stdout
    if not raw or len(raw) % (W * 3):
        return None
    return np.frombuffer(raw, np.uint8).reshape(-1, W, 3)


def role(img: np.ndarray) -> str:
    import cv2
    h, w = img.shape[:2]
    det = cv2.FaceDetectorYN.create(str(MODEL), "", (w, h), 0.7)
    _, faces = det.detect(img)
    if faces is not None and len(faces):
        biggest = max(float(f[2] * f[3]) for f in faces) / (w * h)
        return "close" if biggest > 0.06 else "subject"
    gray = img.mean(axis=2)
    top, bottom = gray[: h // 3].astype(float), gray[2 * h // 3:].astype(float)
    open_top = top.mean() > bottom.mean() + 15 and top.std() < 40           # sky / open space above
    return "establish" if open_top else "detail"


def tag_missing(project: Path) -> int:
    """Give every clip without a tag in <project>/tags.json an automatic one. Returns how many were added."""
    if not MODEL.exists():
        return 0
    f = project / "tags.json"
    tags = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
    added = 0
    for clip in sorted((project / "clips").glob("*")) if (project / "clips").exists() else []:
        if clip.suffix.lower() not in VIDEO_EXT or clip.name in tags:
            continue
        g = _frame(clip)
        if g is None:
            continue
        tags[clip.name] = {"role": role(g), "desc": "auto", "auto": True}
        added += 1
    if added:
        tags.setdefault("_note", "Shot tags per clip. role: detail / establish / subject / close / action / rest / "
                                 "hero_wide. Entries with auto: true were guessed from one frame; edit them freely.")
        f.write_text(json.dumps(tags, indent=1, ensure_ascii=False), encoding="utf-8")
    return added
