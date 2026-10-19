"""Animated effects, built live inside each timeline item's Fusion composition.

Chain per item:  MediaIn → [TimeStretcher] → [Transform] → [CameraShake] → [DirectionalBlur]
                 → [Custom (invert)] → [BrightnessContrast (flash)] → MediaOut
Comp time 0 = first frame of the item on the timeline (handles are available before/after).

Never call comp.Render() from scripts: it opens a modal "Render completed" dialog in Resolve.
"""
from __future__ import annotations

import random
import uuid
from pathlib import Path

from .config import DATA

COMP_DIR = DATA / "comps"
COMP_DIR.mkdir(exist_ok=True)


def commit(item, comp_index: int = 1) -> bool:
    """Comps edited through the API are not picked up by Resolve's renderer; a comp that was
    imported from a file is. So: export what we built, import it back (it becomes the active comp)."""
    path = COMP_DIR / f"{uuid.uuid4().hex}.comp"
    if not item.ExportFusionComp(str(path), comp_index):
        return False
    ok = item.ImportFusionComp(str(path)) is not None
    if ok:
        for name in item.GetFusionCompNameList()[:-1]:          # drop the API-built original
            item.DeleteFusionCompByName(name)
    path.unlink(missing_ok=True)
    return ok


def _key(tool, inp: str, keys: dict[int, float]):
    tool.AddModifier(inp, "BezierSpline")
    for f, v in sorted(keys.items()):
        tool.SetInput(inp, v, f)


def _key_point(tool, inp: str, keys: dict[int, tuple[float, float]]):
    tool.AddModifier(inp, "XYPath")
    for f, v in sorted(keys.items()):
        tool.SetInput(inp, {1: v[0], 2: v[1]}, f)


def reset(comp):
    """Remove everything except MediaIn1/MediaOut1 and reconnect them."""
    for t in list(comp.GetToolList(False).values()):
        if t.GetAttrs()["TOOLS_Name"] not in ("MediaIn1", "MediaOut1"):
            t.Delete()
    comp.FindTool("MediaOut1").ConnectInput("Input", comp.FindTool("MediaIn1"))


def grid_panel(item, k: int, fps: float, src_size=(3840, 2160), canvas=(1080, 1920), cols=2, rows=3,
               gutter=8, pop=True) -> bool:
    """Places the clip as tile k of a cols×rows grid, built on a transparent canvas inside Fusion.

    The comp outputs a full-canvas image (transparent outside the tile), so on the Edit page the
    item just sits 1:1 over the tracks below. Edit-page Crop/Tilt clip unpredictably, so not used.
    """
    comp = item.GetFusionCompByIndex(1) or item.AddFusionComp()
    if comp is None:
        return False
    cw, ch = canvas
    pw, ph = cw / cols, ch / rows
    iw, ih = pw - gutter, ph - gutter
    col, row = k % cols, k // cols
    cx, cy = (col + 0.5) / cols, 1 - (row + 0.5) / rows          # Fusion: y=0 is the bottom
    comp.Lock()
    try:
        reset(comp)
        mi, mo = comp.FindTool("MediaIn1"), comp.FindTool("MediaOut1")
        src_w, src_h = map(float, src_size)
        bg = comp.AddTool("Background", -32768, -32768)
        bg.SetInput("UseFrameFormatSettings", 0)
        bg.SetInput("Width", cw)
        bg.SetInput("Height", ch)
        bg.SetInput("TopLeftAlpha", 0.0)
        mg = comp.AddTool("Merge", -32768, -32768)
        mg.ConnectInput("Background", bg)
        mg.ConnectInput("Foreground", mi)
        cover = max(ih / src_h, iw / src_w)                       # fill the tile, crop the rest
        mg.SetInput("Center", {1: cx, 2: cy})
        if pop:
            # neutral snap: tile appears at full size, settles 3% over 2 frames (no grow-from-zero / bounce)
            _key(mg, "Size", {0: cover * 1.03, 2: cover})
        else:
            mg.SetInput("Size", cover)
        mask = comp.AddTool("RectangleMask", -32768, -32768)
        mask.SetInput("Center", {1: cx, 2: cy})
        mask.SetInput("Width", iw / cw)
        mask.SetInput("Height", ih / ch)
        mg.ConnectInput("EffectMask", mask)
        mo.ConnectInput("Input", mg)
    finally:
        comp.Unlock()
    return commit(item)


def apply(item, effects: list[str], fps: float, speed_ramp: float | None = None,
          pop_in: bool = False, seed: int = 0, intensity: float = 1.0, src_fps: float | None = None,
          extra: dict | None = None) -> list[str]:
    """Builds the effect chain on a timeline item. Returns the effects that were applied.

    intensity scales how strong every effect is (config effects.intensity): 1 = bold, 0.3 = subtle.
    """
    k = max(0.05, float(intensity))
    effects = list(effects)
    if not effects and speed_ramp is None and not pop_in:
        return []
    rng = random.Random(seed)
    comp = item.GetFusionCompByIndex(1) or item.AddFusionComp()
    if comp is None:
        return []
    n = int(item.GetDuration())                 # frames
    last = max(1, n - 1)
    comp.Lock()
    try:
        mi, mo = comp.FindTool("MediaIn1"), comp.FindTool("MediaOut1")
        node, done = mi, []

        def chain(tid):
            nonlocal node
            t = comp.AddTool(tid, -32768, -32768)
            t.ConnectInput("Image1" if tid == "Custom" else "Input", node)    # Custom has Image1/Image2
            node = t
            return t

        if speed_ramp is not None and src_fps and src_fps >= 1.9 * fps:
            # real slow motion: play the high-frame-rate source at timeline/source speed (50p in 25p → 50 %),
            # so every output frame is a real camera frame — no invented/blended frames (they stutter)
            factor = fps / src_fps
            a = max(1, int((speed_ramp - 0.3) * fps))
            slow = int(0.8 * fps)
            if a + slow < last:
                ts = chain("TimeStretcher")
                src_end = a + slow * factor
                _key(ts, "SourceTime", {0: 0, a: a, a + slow: src_end, last: src_end + (last - a - slow)})
                ts.SetInput("InterpolateBetweenFrames", 0)
                done.append("speed_ramp")

        size: dict[int, float] = {}
        center: dict[int, tuple[float, float]] = {}
        extra = extra or {}
        if pop_in:
            size.update({0: 1.03, 2: 1.0})                # neutral snap-in, no bounce
        if "step_zoom" in effects:
            # zoom toward a detail in 3 hard steps on the beat (ref: Buenos Aires 'Subte' sign)
            b = max(3, int(round(extra.get("beat", 0.5) * fps)))
            keys, z = {0: 1.0}, 1.0
            for k in range(1, 4):
                f = k * b
                if f >= last:
                    break
                keys[f - 1] = z
                z = 1 + 0.08 * k * max(k / 3, 0.6) * (0.6 + intensity)
                keys[f] = z
            keys[last] = z
            size.update(keys)
            done.append("step_zoom")
        if "punch_zoom" in effects:
            size.update({0: 1.0, 2: 1 + 0.22 * k, last: 1 + 0.16 * k})
            done.append("punch_zoom")
        elif "smooth_zoom" in effects:
            size.update({0: 1.0, last: 1 + 0.12 * k})
            done.append("smooth_zoom")
        if "whip" in effects:
            d = rng.choice([-1, 1])
            wf = 3 if k < 0.6 else 4
            center.update({0: (0.5 + 0.35 * k * d, 0.5), wf: (0.5, 0.5)})
            size.setdefault(0, 1.0)
            size[0] = max(size[0], 1 + 0.1 * k)
        if "glitch" in effects:
            for f in range(0, min(6, last)):
                center[f] = (0.5 + rng.uniform(-0.03, 0.03) * k, 0.5 + rng.uniform(-0.02, 0.02) * k)
            center[min(6, last)] = (0.5, 0.5)
        if "shake" in effects:
            size = {f: max(v, 1 + 0.06 * k) for f, v in size.items()} or {0: 1 + 0.06 * k}
        if size or center:
            tr = chain("Transform")
            if len(size) > 1:
                _key(tr, "Size", size)
            elif size:
                tr.SetInput("Size", next(iter(size.values())))
            if center:
                _key_point(tr, "Center", center)
            tr.SetInput("Edges", 2)                 # mirror edges: no black borders during whips/shakes

        if "shake" in effects:
            cs = chain("CameraShake")
            ke = min(8 if k >= 0.6 else 5, last)
            _key(cs, "XDeviation", {0: 0.06 * k, ke: 0.0})
            _key(cs, "YDeviation", {0: 0.06 * k, ke: 0.0})
            done.append("shake")

        if "whip" in effects:
            db = chain("DirectionalBlur")
            _key(db, "Length", {0: 0.25 * k, (3 if k < 0.6 else 4): 0.0})
            done.append("whip")

        if "invert_flash" in effects or "glitch" in effects:
            inv = chain("Custom")
            for ch, src in (("Red", "r1"), ("Green", "g1"), ("Blue", "b1")):
                inv.SetInput(f"{ch}Expression", f"1-{src}")
            if "invert_flash" in effects:
                inv_len = 1 if k < 0.6 else 2                          # subtle: a single-frame invert
                _key(inv, "Blend", {0: 1.0, inv_len: 1.0, inv_len + 1: 0.0})   # inverts in, outverts out
                done.append("invert_flash")
            else:
                gl = min(5 if k >= 0.6 else 3, last)
                _key(inv, "Blend", {f: float(f % 2 == 0) for f in range(0, gl)} | {gl: 0.0})
                done.append("glitch")

        if "frame_in_frame" in effects:
            # the shot as a 'photo' on a paper-coloured backdrop (refs A/B), snaps in like the grid tiles
            paper = comp.AddTool("Background", -32768, -32768)
            mpi = item.GetMediaPoolItem()
            res = ((mpi.GetClipProperty("Resolution") if mpi else "") or "3840x2160").lower().split("x")
            paper.SetInput("UseFrameFormatSettings", 0)          # same size as the clip, else the 'photo' shrinks
            paper.SetInput("Width", int(res[0]))
            paper.SetInput("Height", int(res[1]))
            paper.SetInput("TopLeftRed", 0.95)
            paper.SetInput("TopLeftGreen", 0.94)
            paper.SetInput("TopLeftBlue", 0.91)
            pip = comp.AddTool("Merge", -32768, -32768)
            pip.ConnectInput("Background", paper)
            pip.ConnectInput("Foreground", node)
            _key(pip, "Size", {0: 0.66, 2: 0.62})
            node = pip
            done.append("frame_in_frame")

        if "light_leak" in effects:
            # orange film burn sweeping across the first ~10 frames (screen blend), like the reference
            bg = comp.AddTool("Background", -32768, -32768)
            bg.SetInput("TopLeftRed", 1.0)
            bg.SetInput("TopLeftGreen", 0.42)
            bg.SetInput("TopLeftBlue", 0.12)
            mk = comp.AddTool("RectangleMask", -32768, -32768)
            mk.SetInput("Width", 0.55)
            mk.SetInput("Height", 1.6)
            mk.SetInput("SoftEdge", 0.18)
            _key_point(mk, "Center", {0: (0.05, 0.5), 10: (0.75, 0.5), 14: (1.1, 0.5)})
            bg.ConnectInput("EffectMask", mk)
            lk = comp.AddTool("Merge", -32768, -32768)
            lk.ConnectInput("Background", node)
            lk.ConnectInput("Foreground", bg)
            lk.SetInput("ApplyMode", "Screen")
            _key(lk, "Blend", {0: 0.0, 2: 0.9, 9: 0.75, 14: 0.0})
            node = lk
            done.append("light_leak")

        if "color_wipe" in effects:
            # solid colour block sweeping across the cut (refs: Buenos Aires red block, NYC red bars)
            col = extra.get("wipe_color", (0.84, 0.15, 0.12))
            blk = comp.AddTool("Background", -32768, -32768)
            for ch, v in zip(("Red", "Green", "Blue"), col):
                blk.SetInput(f"TopLeft{ch}", v)
            wm = comp.AddTool("RectangleMask", -32768, -32768)
            wm.SetInput("Width", 0.7)
            wm.SetInput("Height", 1.4)
            _key_point(wm, "Center", {0: (0.45, 0.5), 4: (1.4, 0.5)})
            blk.ConnectInput("EffectMask", wm)
            cw = comp.AddTool("Merge", -32768, -32768)
            cw.ConnectInput("Background", node)
            cw.ConnectInput("Foreground", blk)
            node = cw
            done.append("color_wipe")

        if "bw_flash" in effects:
            # 2-3 frames of black & white on a hit (refs: Oran, Huaraz)
            bwf = chain("Custom")
            for ch in ("Red", "Green", "Blue"):
                bwf.SetInput(f"{ch}Expression", "r1*0.299+g1*0.587+b1*0.114")
            _key(bwf, "Blend", {0: 1.0, 2: 1.0, 3: 0.0})
            done.append("bw_flash")

        if "white_flash" in effects:
            bc = chain("BrightnessContrast")
            _key(bc, "Gain", {0: 1 + 2.5 * k, (3 if k < 0.6 else 4): 1.0})
            done.append("white_flash")

        mo.ConnectInput("Input", node)
    finally:
        comp.Unlock()
    if done or pop_in:
        commit(item)
    return done
