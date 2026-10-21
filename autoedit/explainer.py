"""Explainer mode: step-by-step videos (onboarding, how-to) from a script.yaml in a project.

Each section = one b-roll clip + an animated step card (panel with number + title, the sub-lines appear a
beat later). Intro card over the first shot, a full-frame end card with contact info at the end. Cuts land
on beats of the project's music, a soft whoosh carries every section change, a click when sub-lines pop in.
"""
from __future__ import annotations

from pathlib import Path

import yaml

from . import analyze, projects
from .planner import Plan, Shot


def _find(clips_dir: Path, prefix: str) -> Path:
    for f in sorted(clips_dir.glob("*")):
        if f.name.lower().startswith(prefix.lower()) and f.suffix.lower() in analyze.VIDEO_EXT:
            return f
    raise SystemExit(f"No clip starting with '{prefix}' in {clips_dir}")


def build_plan(cfg, project: Path) -> tuple[Plan, dict, Path | None]:
    spec = yaml.safe_load((project / "script.yaml").read_text(encoding="utf-8"))
    st = spec.get("style", {})
    songs = sorted(f for f in (project / "music").glob("*") if f.suffix.lower() in analyze.AUDIO_EXT)
    music = analyze.analyze_music(songs[0]) if songs else None
    beat = 60 / music.tempo if music and music.tempo else 0.5
    fps = float(cfg.get("camera.fps", 25))

    shots, texts, sfx, t = [], [], [], 0.0
    for i, sec in enumerate(spec["sections"]):
        clip = _find(project / "clips", sec["clip"])
        dur = float(sec.get("seconds", 7))
        if music:                                           # section length = whole beats
            dur = max(beat, round(dur / beat) * beat)
        src_in = 0.4                                        # skip AI warm-up frames
        shots.append(Shot(str(clip), src_in, round(src_in + dur, 3), round(t, 3), role="body"))
        kind = sec.get("kind", "step")
        title = sec["title"]
        if kind == "outro":
            texts.append({"t0": round(t + 0.4, 3), "t1": round(t + dur, 3), "text": title, "kind": "endcard",
                          "color": st.get("text", "#FFFFFF"), "bg": st.get("accent", "#0078D4")})
            sfx.append({"t": round(t + 0.4, 3), "cat": "swell", "gain_db": -14, "why": "endcard"})
        else:
            a = t + (0.5 if kind == "intro" else 0.35)
            texts.append({"t0": round(a, 3), "t1": round(t + dur - 0.25, 3), "text": title, "kind": "panel",
                          "color": st.get("text", "#FFFFFF"), "bg": st.get("accent", "#0078D4")})
            texts.append({"t0": round(a + max(0.6, beat * 2), 3), "t1": round(t + dur - 0.25, 3), "text": title,
                          "kind": "panel_sub", "color": st.get("text", "#FFFFFF"), "bg": st.get("accent", "#0078D4")})
            sfx.append({"t": round(a, 3), "cat": "click", "gain_db": -16, "why": "card"})
            sfx.append({"t": round(a + max(0.6, beat * 2), 3), "cat": "click", "gain_db": -19, "why": "card_sub"})
        if i > 0:
            sfx.append({"t": round(max(0, t - 0.15), 3), "cat": "whoosh", "gain_db": -15, "why": "section"})
        t += dur
    plan = Plan("explainer", fps, round(t, 3), shots, None, sfx, texts, [], (
        {"path": str(songs[0]), "offset": 0.0, "tempo": music.tempo} if music else None), None, "A", "explainer")
    style = {"name": "explainer", "label": "Explainer", "aspect": st.get("aspect", "16:9"),
             "grade_look": st.get("grade_look", "clean_warm")}
    return plan, style, Path(songs[0]) if songs else None


def run(cfg, name: str, render: bool = True, log=print) -> dict:
    from . import export
    from .builder import Builder, render as do_render

    project = projects.find(cfg, name)
    plan, style, _ = build_plan(cfg, project)
    out = project / "exports"
    out.mkdir(exist_ok=True)
    (out / "explainer_plan.json").write_text(plan.to_json(), encoding="utf-8")
    log(f"Explainer · {project.name} · {len(plan.shots)} sections · {plan.length:.1f}s")
    built = Builder(cfg, plan, style, log=log).build()
    res = {"timeline": built["timeline"]}
    if render:
        raw = do_render(built["timeline"], out / "_raw", "explainer", log=log)
        wide = style["aspect"] == "16:9"
        res.update(export.finish(raw, out, "explainer", cfg.get("audio.target_lufs", -14), [],
                                 expect=(1920, 1080) if wide else (1080, 1920)))
    return res
