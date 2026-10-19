"""Files prepared before they go into Resolve: SFX at the right gain, a ducked music bed,
and hook text rendered as transparent PNGs inside the TikTok/Reels safe zones."""
from __future__ import annotations

import hashlib
import textwrap
from pathlib import Path

import numpy as np
import soundfile as sf
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from .analyze import load_audio
from .config import DATA

PREP = DATA / "prep"
PREP.mkdir(exist_ok=True)
SR = 48000

# TikTok/Reels UI covers roughly: top 220 px, bottom 420 px, right 140 px (on 1080×1920)
SAFE = {"top": 260, "bottom": 480, "left": 70, "right": 160}


def sfx_at_gain(path: Path, gain_db: float) -> Path:
    if abs(gain_db) < 0.1:
        return path
    out = PREP / f"{path.stem}_{hashlib.sha1(str(path).encode()).hexdigest()[:6]}_{gain_db:+.0f}dB.wav"
    if not out.exists():
        data, sr = sf.read(path, always_2d=True)
        sf.write(out, data * 10 ** (gain_db / 20), sr)
    return out


def music_bed(music: Path, offset: float, length: float, speech: list[tuple[float, float]],
              duck_db: float = -12, fade_out: float = 1.2, bass_db: float = -4.0, fade_in: float = 0.05) -> Path:
    """Cut the song to the video (stereo), tame the low end, fade out, duck under speech."""
    import subprocess

    from .analyze import FFMPEG
    key = hashlib.sha1(f"{music}{offset}{length}{speech}{duck_db}{bass_db}v2".encode()).hexdigest()[:10]
    out = PREP / f"music_{key}.wav"
    if out.exists():
        return out
    # low shelf around 100 Hz (bass_db < 0 = less bass) + rumble filter below 30 Hz
    af = f"highpass=f=30,bass=g={bass_db}:f=100:w=0.7" if bass_db else "highpass=f=30"
    raw = subprocess.run([FFMPEG, "-v", "error", "-ss", f"{offset:.3f}", "-t", f"{length:.3f}", "-i", str(music),
                          "-af", af, "-ac", "2", "-ar", str(SR), "-f", "f32le", "-"], capture_output=True).stdout
    seg = np.frombuffer(raw, np.float32).reshape(-1, 2).astype(np.float64)
    need = int(length * SR)
    if len(seg) < need:
        seg = np.pad(seg, ((0, need - len(seg)), (0, 0)))
    env = np.ones(len(seg))
    duck = 10 ** (duck_db / 20)
    ramp = int(0.15 * SR)
    for a, b in speech:
        i, j = int(a * SR), int(b * SR)
        env[max(0, i - ramp):j + ramp] = np.minimum(env[max(0, i - ramp):j + ramp], duck)
    env = np.convolve(env, np.ones(ramp) / ramp, mode="same")      # smooth the ducking
    fi = max(1, int(fade_in * SR))
    env[:fi] *= np.linspace(0, 1, fi)
    fo = int(fade_out * SR)
    env[-fo:] *= np.linspace(1, 0, fo) ** 2
    seg *= env[:, None]
    peak = np.abs(seg).max() or 1
    if peak > 0.98:                                                 # never clip after the EQ
        seg *= 0.98 / peak
    sf.write(out, seg.astype(np.float32), SR)
    return out


def _font(size: int, name: str) -> ImageFont.FreeTypeFont:
    candidates = [name, f"{name}-Black", f"{name}-ExtraBold", f"{name}-Bold", "Montserrat-Bold",
                  "arialbd", "segoeuib", "arial"]
    fontdirs = [Path("C:/Windows/Fonts"), Path.home() / "AppData/Local/Microsoft/Windows/Fonts"]
    for c in candidates:
        for d in fontdirs:
            for ext in (".ttf", ".otf"):
                p = d / f"{c}{ext}"
                if p.exists():
                    return ImageFont.truetype(str(p), size)
    return ImageFont.load_default(size)


def text_png(text: str, kind: str = "hook", font: str = "Montserrat", color: str = "#FFFFFF",
             accent: str = "#FFD400", w: int = 1080, h: int = 1920, scale: float = 0.03) -> Path:
    key = hashlib.sha1(f"{text}{kind}{font}{color}{accent}{w}{h}{scale}".encode()).hexdigest()[:10]
    out = PREP / f"text_{key}.png"
    if out.exists():
        return out
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    if kind == "corner":
        # tiny labels in the top corners, e.g. "VLOG_01" left and "SHANGHAI" right (ref A)
        left, _, right = text.partition("|")
        size = max(14, int(min(w, h) * 0.022))
        fpath = next((d / f"{n}.ttf" for n in ("Montserrat-Medium", "segoeui", "arial")
                      for d in (Path("C:/Windows/Fonts"), Path.home() / "AppData/Local/Microsoft/Windows/Fonts")
                      if (d / f"{n}.ttf").exists()), None)
        f = ImageFont.truetype(str(fpath), size) if fpath else ImageFont.load_default(size)
        m = int(min(w, h) * 0.05)
        top = SAFE["top"] if h > w else m
        d = ImageDraw.Draw(img)
        sp = lambda s: " ".join(s.upper())
        d.text((m, top), "—" + sp(left), font=f, fill=color)
        if right:
            d.text((w - m - f.getlength(sp(right) + "—"), top), sp(right) + "—", font=f, fill=color)
        img.save(out)
        return out
    if kind == "minimal":
        # small, widely letter-spaced title centred in frame (cinematic reference style)
        spaced = "   ".join(" ".join(word) for word in text.upper().split())
        size = max(18, int(min(w, h) * scale))          # scale = title height as a share of the short side
        f = None
        for name in ("Montserrat-Regular", "segoeui", "arial"):
            for d in (Path("C:/Windows/Fonts"), Path.home() / "AppData/Local/Microsoft/Windows/Fonts"):
                if (d / f"{name}.ttf").exists():
                    f = ImageFont.truetype(str(d / f"{name}.ttf"), size)
                    break
            if f:
                break
        f = f or ImageFont.load_default(size)
        x = (w - f.getlength(spaced)) / 2
        y = h / 2 - size / 2
        shadow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        ImageDraw.Draw(shadow).text((x, y + 2), spaced, font=f, fill=(0, 0, 0, 140))
        ImageDraw.Draw(img).text((x, y), spaced, font=f, fill=color)
        Image.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(4)), img).save(out)
        return out
    usable = w - SAFE["left"] - SAFE["right"]
    size = 92 if kind == "hook" else 64
    f = _font(size, font)
    lines = textwrap.wrap(text.upper() if kind == "hook" else text, width=16)
    while lines and max(f.getlength(line) for line in lines) > usable and size > 40:
        size -= 4
        f = _font(size, font)
    line_h = int(size * 1.15)
    y0 = SAFE["top"] + 120 if kind == "hook" else h - SAFE["bottom"] - line_h * len(lines)
    shadow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    sd, d = ImageDraw.Draw(shadow), ImageDraw.Draw(img)
    for i, line in enumerate(lines):
        x = SAFE["left"] + (usable - f.getlength(line)) / 2
        y = y0 + i * line_h
        sd.text((x + 4, y + 6), line, font=f, fill=(0, 0, 0, 200))
        fill = accent if (kind == "hook" and i == 0 and len(lines) > 1) else color
        d.text((x, y), line, font=f, fill=fill, stroke_width=max(2, size // 22), stroke_fill=(0, 0, 0, 255))
    shadow = shadow.filter(ImageFilter.GaussianBlur(8))
    Image.alpha_composite(shadow, img).save(out)
    return out


def text_clip(png: Path, seconds: float, fps: float = 25, fade: float = 0.25) -> Path:
    """Turn a title PNG into a ProRes 4444 clip (with alpha) of an exact length. Resolve gives stills a
    fixed default duration and ignores the requested end frame, so titles are placed as clips instead."""
    import subprocess

    from .analyze import FFMPEG
    out = PREP / f"{png.stem}_{seconds:.2f}s.mov"
    if out.exists():
        return out
    fd = min(fade, seconds / 3)
    vf = f"format=rgba,fade=t=in:st=0:d={fd}:alpha=1,fade=t=out:st={max(0, seconds - fd):.3f}:d={fd}:alpha=1"
    subprocess.run([FFMPEG, "-y", "-v", "error", "-loop", "1", "-framerate", str(fps), "-t", f"{seconds:.3f}",
                    "-i", str(png), "-vf", vf, "-c:v", "prores_ks", "-profile:v", "4444",
                    "-pix_fmt", "yuva444p10le", str(out)], check=True)
    return out
