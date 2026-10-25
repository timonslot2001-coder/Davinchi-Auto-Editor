"""Export QA: container/stream checks, black/frozen frames, loudness/true peak, frame count vs EDL."""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

import imageio_ffmpeg

from .edl import EDL

FF = imageio_ffmpeg.get_ffmpeg_exe()


def check(video: Path, edl: EDL | None = None) -> dict:
    info = subprocess.run([FF, "-hide_banner", "-i", str(video)], capture_output=True, text=True, errors="replace").stderr
    v = re.search(r"Video: (\w+).*?(\d{3,5})x(\d{3,5}).*?([\d.]+) fps", info)
    dur = re.search(r"Duration: (\d+):(\d+):([\d.]+)", info)
    r = subprocess.run([FF, "-hide_banner", "-i", str(video), "-vf", "blackdetect=d=0.12:pix_th=0.06,freezedetect=n=0.002:d=0.6",
                        "-af", "ebur128=peak=true", "-f", "null", "-"], capture_output=True, text=True, errors="replace").stderr
    lufs = re.findall(r"I:\s+(-?[\d.]+) LUFS", r)
    peak = re.findall(r"Peak:\s+(-?[\d.]+) dBFS", r)
    res = {"codec": v[1] if v else None, "size": [int(v[2]), int(v[3])] if v else None, "fps": float(v[4]) if v else None,
           "duration": (int(dur[1]) * 3600 + int(dur[2]) * 60 + float(dur[3])) if dur else None,
           "has_audio": "Audio:" in info,
           "black": re.findall(r"black_start:([\d.]+) black_end:([\d.]+)", r),
           "frozen": re.findall(r"freeze_start: ([\d.]+)", r),
           "lufs": float(lufs[-1]) if lufs else None, "true_peak_dbfs": float(peak[-1]) if peak else None}
    problems = []
    if edl:
        if res["size"] != [edl.width, edl.height]:
            problems.append(f"size {res['size']} != {[edl.width, edl.height]}")
        if res["duration"] is not None and abs(res["duration"] - edl.duration) > 0.1:
            problems.append(f"duration {res['duration']:.2f} != {edl.duration:.2f}")
    if res["black"]:
        problems.append(f"black segments {res['black']}")
    if res["frozen"]:
        problems.append(f"frozen at {res['frozen']} (check: may be an intentional held shot)")
    if res["true_peak_dbfs"] is not None and res["true_peak_dbfs"] > -1.0:
        problems.append(f"true peak {res['true_peak_dbfs']} dBFS > -1")
    res["problems"] = problems
    return res
