"""Builds a Plan into DaVinci Resolve: timeline, grade, effects, grid, SFX, music, text, captions, render.

Your originals are never touched: everything happens in a project called "AutoEdit",
each build gets its own timeline (= a version you can always go back to).
"""
from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path

from rich.console import Console

from . import fx
from .media_prep import music_bed, sfx_at_gain, text_clip, text_png
from .planner import Plan
from .resolve_api import connect
from .sfx import Library

con = Console()
PROJECT = "AutoEdit"
SCALE_FIT, SCALE_FILL = 2, 3
COMPOSITE = {"normal": 0, "add": 1, "screen": 5, "overlay": 6, "softlight": 8, "lighten": 10}
LOOK_NODES = ["BlueHour", "Daylight", "Evening", "Night", "Outdoors", "Overcast", "Vintage"]
W, H = 1080, 1920
# video tracks
V_MAIN, V_GRID0, V_OVERLAY, V_TEXT = 1, 2, 8, 9
# audio tracks
A_CLIP, A_SFX, A_SFX2, A_MUSIC = 1, 2, 3, 4


class Builder:
    def __init__(self, cfg, plan: Plan, style: dict, log=con.print):
        self.cfg, self.plan, self.style, self.log = cfg, plan, style, log
        self.fps = plan.fps
        self.resolve = connect()
        self.pm = self.resolve.GetProjectManager()
        self.lib = Library(cfg.get("paths.sfx_folders", []))

    # ---------------------------------------------------------------- helpers
    def f(self, seconds: float) -> int:
        return int(round(seconds * self.fps))

    def _project(self):
        cur = self.pm.GetCurrentProject()
        if cur and cur.GetName() == PROJECT:
            p = cur
        else:
            p = self.pm.LoadProject(PROJECT) or self.pm.CreateProject(PROJECT)
        if not p:
            raise SystemExit("Can't open/create the 'AutoEdit' project in Resolve (is a dialog open?).")
        for k, v in {"timelineResolutionWidth": str(W), "timelineResolutionHeight": str(H),
                     "timelineFrameRate": str(int(self.fps)), "timelinePlaybackFrameRate": str(int(self.fps))}.items():
            p.SetSetting(k, v)
        # playback performance: play from proxies when they exist, cache Fusion/grade output in the background
        p.SetSetting("perfProxyMediaMode", "1")
        p.SetSetting("perfRenderCacheMode", "smart")
        p.SetSetting("perfAutoRenderCacheFuEffect", "1")
        p.RefreshLUTList()
        return p

    def _import(self, paths: list[Path], folder) -> dict[str, object]:
        mp = self.project.GetMediaPool()
        mp.SetCurrentFolder(folder)
        existing = {c.GetClipProperty("File Path").lower(): c for c in folder.GetClipList() or []}
        todo = [str(p) for p in paths if str(p).lower() not in existing]
        if todo:
            for c in mp.ImportMedia(todo) or []:
                existing[c.GetClipProperty("File Path").lower()] = c
        return {str(p): existing.get(str(p).lower()) for p in paths}

    def _subfolder(self, parent, name):
        for f in parent.GetSubFolderList() or []:
            if f.GetName() == name:
                return f
        return self.project.GetMediaPool().AddSubFolder(parent, name)

    def _append(self, mpi, src_in: int, src_out: int, track: int, rec: int, media_type: int):
        items = self.project.GetMediaPool().AppendToTimeline([{
            "mediaPoolItem": mpi, "startFrame": src_in, "endFrame": src_out,
            "trackIndex": track, "recordFrame": rec, "mediaType": media_type}])
        return items[0] if items else None

    # ---------------------------------------------------------------- grading
    def _grade(self, items: list):
        g = self.cfg.get("grading", {}) or {}
        if not g.get("enabled", True) or not items:
            return
        if g.get("mode", "lut") == "lut":
            # one baked LUT (Sony S-Log3 → Rec.709 + film look) on a clean node: renders exactly as tested
            from . import grade
            look = self.style.get("grade_look") or g.get("grade_look", "reference_film")
            lut = grade.build_lut(look, g.get("strength", 1.0), g.get("exposure", -1.75))
            self.project.RefreshLUTList()
            rel = grade.relative(lut)
            ok = 0
            for it in items:
                graph = it.GetNodeGraph()
                graph.ResetAllGrades()
                ok += bool(graph.SetLUT(1, rel))
                it.SetColorOutputCache(self.resolve.CACHE_ENABLED)
            self.log(f"Grade [bold]{look}[/] (exposure {g.get('exposure', -1.75)} stops) on {ok}/{len(items)} clips")
            return
        drx = self._powergrade_drx()
        if not drx:
            self.log("[yellow]No PowerGrade found, skipping grade[/]")
            return
        look = self.style.get("look") or g.get("look")
        first = items[0]
        graph = first.GetNodeGraph()
        if not graph.ApplyGradeFromDRX(str(drx), 0):
            self.log("[red]Applying PowerGrade failed[/]")
            return
        graph = first.GetNodeGraph()
        if look:
            labels = {graph.GetNodeLabel(i): i for i in range(1, graph.GetNumNodes() + 1)}
            lut = graph.GetLUT(labels[look]) if look in labels else None
            # the 7 looks sit in a parallel mixer: give every branch the same LUT → look at 100%
            if lut:
                for name in LOOK_NODES:
                    if name in labels:
                        graph.SetLUT(labels[name], lut)
        # Denoise (node 1) is temporal noise reduction: by far the heaviest node, kills playback.
        # Clean Sony footage rarely needs it → off unless grading.denoise: true
        if not g.get("denoise", False):
            labels = {graph.GetNodeLabel(i): i for i in range(1, graph.GetNumNodes() + 1)}
            if "Denoise" in labels:
                graph.SetNodeEnabled(labels["Denoise"], False)
        if len(items) > 1:
            first.CopyGrades(items[1:])
        for it in items:                                   # background-cache the graded result
            it.SetColorOutputCache(self.resolve.CACHE_ENABLED)
        self.log(f"PowerGrade [bold]{drx.name}[/] applied to {len(items)} clips, look: {look}")

    def _powergrade_drx(self) -> Path | None:
        """Prefer your own PowerGrade from the Gallery (with the CST set to S-Log3); else the .drx file."""
        label = self.cfg.get("grading.gallery_label")
        if label:
            gal = self.project.GetGallery()
            for album in gal.GetGalleryPowerGradeAlbums() or []:
                for still in album.GetStills() or []:
                    if label.lower() in (album.GetLabel(still) or "").lower():
                        out = Path(self.cfg.get("paths.output_folder")) / "_powergrade"
                        out.mkdir(parents=True, exist_ok=True)
                        album.ExportStills([still], str(out), "pg", "drx")
                        files = sorted(out.glob("pg*.drx"), key=lambda p: p.stat().st_mtime)
                        if files:
                            return files[-1]
        f = self.cfg.get("grading.drx_file")
        return Path(f) if f and Path(f).exists() else None

    # ---------------------------------------------------------------- build
    def build(self) -> dict:
        t0 = time.time()
        plan, cfg = self.plan, self.cfg
        self.project = self._project()
        mp = self.project.GetMediaPool()
        root = mp.GetRootFolder()
        stamp = datetime.now().strftime("%m%d-%H%M%S")
        name = f"{plan.style}_{plan.variant}_{stamp}"
        bins = self._subfolder(root, "AutoEdit")
        b_footage, b_sfx, b_gfx, b_tl = (self._subfolder(bins, n) for n in ("Footage", "SFX & Music", "Graphics", "Timelines"))

        clips = sorted(({s.clip for s in plan.shots} | {p["clip"] for p in (plan.grid.panels if plan.grid else [])}) - {""})
        mpi = self._import([Path(c) for c in clips], b_footage)
        missing = [c for c, v in mpi.items() if v is None]
        if missing:
            raise SystemExit(f"Import failed for: {missing}")
        if cfg.get("performance.proxies", True):
            from .proxy import ensure_proxies
            folder = Path(cfg.get("paths.output_folder")) / "_proxies"
            prox = ensure_proxies([Path(c) for c in clips], folder, log=self.log)
            linked = sum(bool(mpi[c].LinkProxyMedia(str(prox[c]))) for c in clips)
            self.log(f"Playback proxies linked: {linked}/{len(clips)}")

        mp.SetCurrentFolder(b_tl)
        tl = mp.CreateEmptyTimeline(name)
        self.project.SetCurrentTimeline(tl)
        # per-timeline resolution (9:16 for TikTok/Reels, 16:9 for the cinematic preset)
        self.W, self.H = (1920, 1080) if self.style.get("aspect") == "16:9" else (W, H)
        tl.SetSetting("useCustomSettings", "1")
        tl.SetSetting("timelineResolutionWidth", str(self.W))
        tl.SetSetting("timelineResolutionHeight", str(self.H))
        self.resolve.OpenPage("edit")
        for _ in range(V_TEXT - tl.GetTrackCount("video")):
            tl.AddTrack("video")
        for _ in range(A_MUSIC - tl.GetTrackCount("audio")):
            tl.AddTrack("audio", "stereo")
        start = tl.GetStartFrame()
        keep_audio = plan.mode == "talking" or plan.music is None

        # ---- V1 main shots (frame-exact: each shot ends where the next begins)
        main_items, speech = [], []
        bounds = [self.f(s.rec_in) for s in plan.shots] + [self.f(plan.length)]
        for i, s in enumerate(plan.shots):
            nxt = bounds[i + 1]
            if plan.grid and bounds[i] < self.f(plan.grid.rec_in) < nxt:
                nxt = self.f(plan.grid.rec_in)
            dur = max(1, nxt - bounds[i])
            if not s.clip:                                   # dip to black: leave the gap empty
                continue
            a = self.f(s.src_in)
            item = self._append(mpi[s.clip], a, a + dur, V_MAIN, start + bounds[i], 1)
            if not item:
                self.log(f"[red]Could not place shot {i} ({Path(s.clip).name})[/]")
                continue
            if keep_audio:
                self._append(mpi[s.clip], a, a + dur, A_CLIP, start + bounds[i], 2)
                speech.append((s.rec_in, s.rec_in + dur / self.fps))
            item.SetProperty("Scaling", SCALE_FILL)
            main_items.append((s, item))
        self.log(f"{len(main_items)} shots placed on V1")

        # ---- grid section: 6 panels on V2–V7, each pops in with a sound
        grid_items = []
        if plan.grid:
            g = plan.grid
            end = start + self.f(g.rec_in + g.dur)
            for k, panel in enumerate(g.panels):
                rec = start + self.f(g.rec_in + k * g.interval)
                a = self.f(panel["src_in"])
                item = self._append(mpi[panel["clip"]], a, a + (end - rec), V_GRID0 + k, rec, 1)
                if item:
                    item.SetProperty("Scaling", SCALE_FIT)       # the comp outputs a full 1080×1920 canvas
                    res = (mpi[panel["clip"]].GetClipProperty("Resolution") or "3840x2160").lower().split("x")
                    grid_items.append((item, k, (int(res[0]), int(res[1]))))
            self.log(f"6-panel grid at {g.rec_in:.1f}s")

        # ---- per-shot: stabilize, smart reframe, effects
        stab_n = fx_n = 0
        for i, (s, item) in enumerate(main_items):
            if s.stabilize and item.Stabilize():
                stab_n += 1
            if cfg.get("format.smart_reframe") and s.role == "hook":
                item.SmartReframe()
            fx_n += len(fx.apply(item, [e for e in s.effects if e != "bw"], self.fps, s.speed_ramp, seed=i,
                                  intensity=cfg.get("effects.intensity", 1.0)))
        for item, k, src in grid_items:
            fx.grid_panel(item, k, self.fps, src_size=src, canvas=(self.W, self.H))
        grid_items = [it for it, _, _ in grid_items]
        for it in [it for _, it in main_items] + grid_items:
            if it.GetFusionCompCount():
                it.SetFusionOutputCache(self.resolve.CACHE_ENABLED)
        self.log(f"Stabilized {stab_n} shots, {fx_n} effects built")

        # ---- grade everything (main + grid panels)
        self._grade([it for _, it in main_items] + grid_items)
        for s, it in main_items:
            if "bw" in s.effects:                      # black & white accent (ref B)
                it.SetCDL({"NodeIndex": "1", "Slope": "1 1 1", "Offset": "0 0 0", "Power": "1 1 1", "Saturation": "0"})

        # ---- overlay (film frames / light leaks) over the whole edit
        ov = plan.overlay
        if ov:
            files = [p for d in cfg.get("paths.overlay_folders", []) for p in Path(d).glob("*.mov")]
            if files:
                pick = files[hash(plan.variant) % len(files)]
                o = self._import([pick], b_gfx)[str(pick)]
                item = self._append(o, 0, self.f(plan.length), V_OVERLAY, start, 1)
                if item:
                    item.SetProperty("Scaling", SCALE_FILL)
                    item.SetProperty("CompositeMode", COMPOSITE.get(ov.get("blend", "screen"), 5))
                    item.SetProperty("Opacity", float(ov.get("opacity", 30)))

        # ---- hook text (PNG in safe zone, pops in)
        for ti, t in enumerate(plan.texts):
            track = V_TEXT + ti                              # every text on its own track (they overlap in time)
            while tl.GetTrackCount("video") < track:
                tl.AddTrack("video")
            png = text_png(t["text"], t["kind"], cfg.get("branding.font", "Montserrat"),
                           cfg.get("branding.primary_color", "#FFFFFF"), cfg.get("branding.accent_color", "#FFD400"),
                           w=self.W, h=self.H, scale=self.style.get("title_size", 0.03) if t["kind"] == "minimal" else 0.03)
            n = self.f(t["t1"] - t["t0"])
            clip = text_clip(png, n / self.fps, self.fps, fade=0.2 if t["kind"] == "minimal" else 0.0)
            m = self._import([clip], b_gfx)[str(clip)]
            item = self._append(m, 0, n, track, start + self.f(t["t0"]), 1)
            if item and t["kind"] != "minimal":                # minimal titles sit still, like the reference
                fx.apply(item, [], self.fps, pop_in=True)

        # ---- SFX (alternating two tracks so overlapping sounds never collide)
        sfx_files, lane_end = [], {A_SFX: -1, A_SFX2: -1}
        base_gain = cfg.get("audio.sfx_volume_db", -6)
        for ev in plan.sfx:
            src = self.lib.pick(ev["cat"])
            if not src:
                continue
            sfx_files.append((ev, sfx_at_gain(src, base_gain + ev.get("gain_db", 0))))
        sfx_mpi = self._import(sorted({p for _, p in sfx_files}), b_sfx)
        import soundfile as sf
        for ev, p in sfx_files:
            n = max(1, int(sf.info(p).duration * self.fps))
            rec = start + self.f(ev["t"])
            if ev["cat"] in ("riser", "swell") and "why" not in ev:   # director already leads these itself          # risers end ON the moment instead of starting there
                rec = max(start, rec - n + self.f(0.05))
            lane = A_SFX if lane_end[A_SFX] <= rec else A_SFX2
            if self._append(sfx_mpi[str(p)], 0, n, lane, rec, 2):
                lane_end[lane] = rec + n

        # ---- music bed (cut, faded, ducked under speech)
        if plan.music:
            bed = music_bed(Path(plan.music["path"]), plan.music["offset"], plan.length, speech if plan.mode == "talking" else [],
                            cfg.get("audio.music_duck_db", -12), bass_db=cfg.get("audio.music_bass_db", -4))
            m = self._import([bed], b_sfx)[str(bed)]
            self._append(m, 0, self.f(plan.length), A_MUSIC, start, 2)

        # ---- voice: isolation + auto captions
        if keep_audio and plan.mode == "talking":
            if cfg.get("audio.voice_isolation"):
                tl.SetVoiceIsolationState(A_CLIP, {"isEnabled": True, "amount": 70})
            if cfg.get("captions.enabled"):
                self._captions(tl)

        # ---- markers so you can see every decision on the timeline
        colors = {"cut": "Blue", "punch_zoom": "Red", "smooth_zoom": "Pink", "whip": "Cyan"}
        for mk in plan.markers:
            tl.AddMarker(self.f(mk["t"]), colors.get(mk["name"].split("+")[0], "Yellow"), mk["name"], mk["note"], 1)
        if plan.grid:
            tl.AddMarker(self.f(plan.grid.rec_in), "Green", "6-panel grid", "", 1)

        self.project.SetCurrentTimeline(tl)
        self.pm.SaveProject()
        self.log(f"[green]Timeline '{name}' built in {time.time() - t0:.0f}s[/]")
        return {"timeline": name, "project": PROJECT, "length": plan.length}

    def _captions(self, tl):
        r = self.resolve
        lang = {"dutch": r.AUTO_CAPTION_DUTCH, "english": r.AUTO_CAPTION_ENGLISH}.get(
            self.cfg.get("captions.language", "auto"), r.AUTO_CAPTION_AUTO)
        ok = tl.CreateSubtitlesFromAudio({
            r.SUBTITLE_LANGUAGE: lang,
            r.SUBTITLE_CAPTION_PRESET: r.AUTO_CAPTION_SUBTITLE_DEFAULT,
            r.SUBTITLE_CHARS_PER_LINE: int(self.cfg.get("captions.chars_per_line", 18)),
            r.SUBTITLE_LINE_BREAK: r.AUTO_CAPTION_LINE_SINGLE,
        })
        self.log("Captions generated" if ok else "[yellow]Auto captions failed[/]")


# ---------------------------------------------------------------- render

def render(timeline_name: str, out_dir: Path, name: str, log=con.print) -> Path:
    """Render the timeline to a high-quality 1080×1920 MP4 (post-processing happens in export.py)."""
    resolve = connect()
    p = resolve.GetProjectManager().LoadProject(PROJECT) or resolve.GetProjectManager().GetCurrentProject()
    tl = next(p.GetTimelineByIndex(i) for i in range(1, p.GetTimelineCount() + 1)
              if p.GetTimelineByIndex(i).GetName() == timeline_name)
    p.SetCurrentTimeline(tl)
    resolve.OpenPage("deliver")
    codecs = p.GetRenderCodecs("mp4") or {}
    codec = next((v for k, v in codecs.items() if "265" in k or "HEVC" in k.upper()), None) or \
        next((v for k, v in codecs.items() if "264" in k), "H264")
    p.SetCurrentRenderFormatAndCodec("mp4", codec)
    out_dir.mkdir(parents=True, exist_ok=True)
    # render only up to the last video frame: SFX tails must not add black at the end (breaks the loop)
    v_end = max((it.GetEnd() for t in range(1, tl.GetTrackCount("video") + 1)
                 for it in (tl.GetItemListInTrack("video", t) or [])), default=tl.GetEndFrame())
    p.SetRenderSettings({
        "SelectAllFrames": False, "MarkIn": tl.GetStartFrame(), "MarkOut": v_end - 1,
        "TargetDir": str(out_dir), "CustomName": name,
        "FormatWidth": int(tl.GetSetting("timelineResolutionWidth") or W),
        "FormatHeight": int(tl.GetSetting("timelineResolutionHeight") or H), "FrameRate": float(tl.GetSetting("timelineFrameRate") or 25),
        "VideoQuality": 25000, "AudioCodec": "aac", "AudioSampleRate": 48000, "ExportVideo": True, "ExportAudio": True,
        "ExportSubtitle": True, "SubtitleFormat": "BurnIn",
    })
    job = p.AddRenderJob()
    p.StartRendering([job], isInteractiveMode=False)
    while p.IsRenderingInProgress():
        st = p.GetRenderJobStatus(job)
        log(f"  rendering… {st.get('CompletionPercentage', 0)}%", end="\r")
        time.sleep(2)
    st = p.GetRenderJobStatus(job)
    if st.get("JobStatus") != "Complete":
        raise SystemExit(f"Render failed: {st}")
    out = next(iter(sorted(out_dir.glob(f"{name}*.mp4"), key=lambda q: q.stat().st_mtime, reverse=True)), None)
    log(f"\n[green]Rendered[/] {out}")
    return out


# ---------------------------------------------------------------- playback optimisation

def optimize_project(cfg, log=con.print) -> dict:
    """Fixes playback of timelines that already exist: proxies, render cache, Denoise off."""
    from .proxy import ensure_proxies

    resolve = connect()
    pm = resolve.GetProjectManager()
    p = pm.LoadProject(PROJECT) or pm.GetCurrentProject()
    p.SetSetting("perfProxyMediaMode", "1")
    p.SetSetting("perfRenderCacheMode", "smart")
    p.SetSetting("perfAutoRenderCacheFuEffect", "1")

    def walk(folder):
        yield from folder.GetClipList() or []
        for sub in folder.GetSubFolderList() or []:
            yield from walk(sub)

    heavy = [c for c in walk(p.GetMediaPool().GetRootFolder())
             if c.GetClipProperty("Type") in ("Video", "Video + Audio")
             and "4:2:2" in (c.GetClipProperty("Video Codec") or "")]
    srcs = [Path(c.GetClipProperty("File Path")) for c in heavy]
    prox = ensure_proxies(srcs, Path(cfg.get("paths.output_folder")) / "_proxies", log=log)
    linked = sum(bool(c.LinkProxyMedia(str(prox[str(s)]))) for c, s in zip(heavy, srcs))

    denoise_off = cached = 0
    for i in range(1, p.GetTimelineCount() + 1):
        tl = p.GetTimelineByIndex(i)
        for t in range(1, tl.GetTrackCount("video") + 1):
            for it in tl.GetItemListInTrack("video", t) or []:
                g = it.GetNodeGraph()
                if g and not cfg.get("grading.denoise", False):
                    for n in range(1, g.GetNumNodes() + 1):
                        if g.GetNodeLabel(n) == "Denoise":
                            denoise_off += bool(g.SetNodeEnabled(n, False))
                if g and g.GetNumNodes() > 1:
                    cached += bool(it.SetColorOutputCache(resolve.CACHE_ENABLED))
                if it.GetFusionCompCount():
                    it.SetFusionOutputCache(resolve.CACHE_ENABLED)
    pm.SaveProject()
    res = {"proxies_linked": f"{linked}/{len(heavy)}", "denoise_disabled": denoise_off, "clips_cached": cached,
           "proxy_mode": p.GetSetting("perfProxyMediaMode"), "render_cache": p.GetSetting("perfRenderCacheMode")}
    log(res)
    return res
