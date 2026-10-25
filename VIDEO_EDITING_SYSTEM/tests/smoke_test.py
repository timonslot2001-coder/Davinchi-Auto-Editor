"""SYNTHETIC smoke test of the whole chain (not a user video, not reference evidence):
generated test clips + generated beat track -> plan -> storyboard -> test-approval -> render -> QA.
Run:  C:\\Users\\Timon\\.aev\\Scripts\\python.exe tests\\smoke_test.py"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from engine import cli, graphics, media  # noqa: E402

FF = media.FF
PROJ = ROOT / "tests" / "_synthetic_project"


def make_project():
    if PROJ.exists():
        shutil.rmtree(PROJ)
    (PROJ / "clips").mkdir(parents=True)
    (PROJ / "music").mkdir()
    srcs = ["testsrc2=size=1920x1080:rate=25", "mandelbrot=size=1920x1080:rate=25", "smptehdbars=size=1920x1080:rate=25",
            "life=size=1920x1080:rate=25:mold=10:ratio=0.2", "cellauto=size=1920x1080:rate=25:rule=110", "rgbtestsrc=size=1920x1080:rate=25",
            "testsrc=size=1920x1080:rate=25", "yuvtestsrc=size=1920x1080:rate=25", "mandelbrot=size=1920x1080:rate=25:start_scale=0.5",
            "cellauto=size=1920x1080:rate=25:rule=30"]
    for i, s in enumerate(srcs):
        vf = "drawtext=text='SYNTHETIC TEST %d':fontcolor=white:fontsize=72:x=(w-tw)/2+40*sin(t*3):y=h-160:box=1:boxcolor=black@0.5" % i
        subprocess.run([FF, "-v", "error", "-y", "-f", "lavfi", "-i", s, "-t", "6", "-vf", vf, "-c:v", "libx264", "-preset",
                        "ultrafast", "-pix_fmt", "yuv420p", str(PROJ / "clips" / f"synthetic_{i}.mp4")], check=True)
    # 120 bpm click + bass as a 'song'
    subprocess.run([FF, "-v", "error", "-y", "-f", "lavfi", "-i",
                    "aevalsrc='0.6*sin(2*PI*55*t)*exp(-8*mod(t,0.5))+0.3*sin(2*PI*1800*t)*exp(-60*mod(t,0.5))':s=48000:d=24",
                    "-ac", "2", str(PROJ / "music" / "synthetic_beat.wav")], check=True)


def main():
    results = {}
    make_project()
    results["validate"] = "ok" if cli.main(["validate"]) is None else "fail"
    gfx = graphics.title_png("SYNTHETIC", "#E70002", "poster_condensed", (960, 540), PROJ / "gfx")
    results["title_capture_rgba"] = bool(gfx.shape[2] == 4 and gfx[..., 3].max() == 255 and gfx[..., 3].min() == 0)
    cli.main(["plan", str(PROJ), "--title", "Synthetic", "--length", "12", "--grade", "none"])
    edl = json.loads((PROJ / "cine_montage" / "edl.json").read_text())
    results["events"] = len(edl["events"])
    results["transitions"] = {k: sum(e["transition_in"] == k for e in edl["events"]) for k in ("T_HARD", "T_FLASH", "T_WHIP")}
    try:                                              # gate must refuse before approval
        cli.main(["render", str(PROJ), "--grade", "none"])
        results["gate_refuses_unapproved"] = False
    except SystemExit as e:
        results["gate_refuses_unapproved"] = "REFUSED" in str(e)
    cli.main(["approve", str(PROJ), "--by", "smoke_test", "--note", "SYNTHETIC test approval, not a user approval"])
    cli.main(["render", str(PROJ), "--grade", "none"])
    q = json.loads((PROJ / "cine_montage" / "qa.json").read_text())["qa"]
    results["qa"] = {k: q[k] for k in ("size", "fps", "duration", "has_audio", "lufs", "true_peak_dbfs", "problems")}
    title = next(o for o in edl["overlays"] if o["component"] == "title_slam")
    results["title_in_s"] = title["out_in"]
    ok = (0.3 <= title["out_in"] <= 1.3 and results["title_capture_rgba"] and results["gate_refuses_unapproved"] and q["size"] == [1920, 1080]
          and abs(q["duration"] - edl["duration"]) < 0.1 and q["has_audio"])
    results["PASS"] = bool(ok)
    (ROOT / "tests" / "smoke_result.json").write_text(json.dumps(results, indent=1), encoding="utf-8")
    print(json.dumps(results, indent=1))


if __name__ == "__main__":
    main()
