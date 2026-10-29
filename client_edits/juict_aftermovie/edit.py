"""JUICT - Compain AI aftermovie (v12, approved for upload 2026-10-28): the client's original film, kept intact.

- JUICT intro instead of the IT Synergy opening card (0-2.76 s), revealing the original's first shot
- IT Synergy booklet shot (5.74-7.17 s) left out: 48 frames = 4 beats, so the music stays in time
- 3 photo snaps (flash + white print landing on the blurred shot + camera click)
- JUICT outro instead of the IT Synergy end card
- everything else exactly as the original (decision docs/decisions/0010-client-films-stay-intact.md)

The client material is not in the repo. It is read from the project folder:
  source/Aftermovie V2.mp4, branding/juict_logo_white_red.png, photos/photo_1.jpg .. photo_3.jpg
Run:  C:\\Users\\Timon\\.aev\\Scripts\\python.exe edit.py ["<project folder>"] [--out name.mp4]
"""
import argparse
import subprocess
from pathlib import Path

import cv2
import imageio_ffmpeg
import numpy as np

import brand_motion as bm
import brand_motion2 as bm2

PROJECT = Path(r"C:\Users\Timon\Videos\AutoEdit Projects\JUICT - Compain AI aftermovie")
SFX = Path(r"C:\Users\Timon\Documents\Editor Packs\FOUR Editors - Sound Effects\All Sound Effects In One Download")
FF = imageio_ffmpeg.get_ffmpeg_exe()
W, H = 1920, 1080
FPS = 30000 / 1001
SR = 48000

SRC_DUR = 83.02                    # original film length
INTRO_END = 2.76                   # IT Synergy opening card ends here (on the beat)
CUT_AT = 172 / FPS                 # end of the light-flash shot = start of the booklet
GAP = 48 / FPS                     # 4 beats (beat ≈ 0.40 s); resumes at 7.34, the booklet ends at 7.17
OUTRO_SRC = 78.51                  # IT Synergy end card starts here in the original
DUR = SRC_DUR - GAP
SNAPS = [(s0 - GAP, s1 - GAP, name) for s0, s1, name in                       # original times → output times
         [(28.05, 28.44, "photo_2.jpg"), (33.18, 33.97, "photo_1.jpg"), (41.08, 41.87, "photo_3.jpg")]]


def ease(x):
    x = min(max(x, 0.0), 1.0)
    return 1 - (1 - x) ** 3


class Reader:
    """Frame at time t from a video, reading forward where possible."""

    def __init__(self, path):
        self.cap = cv2.VideoCapture(str(path))
        self.fps = self.cap.get(cv2.CAP_PROP_FPS)
        self.idx, self.frame = -1, None

    def at(self, t):
        want = max(0, int(round(t * self.fps)))
        if want < self.idx or want > self.idx + 60:
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, want)
            self.idx = want - 1
        while self.idx < want:
            ok, f = self.cap.read()
            if not ok:
                break
            self.frame, self.idx = f, self.idx + 1
        return None if self.frame is None else self.frame.copy()


class Film:
    def __init__(self, project: Path):
        self.p = project
        self.after = Reader(project / "source" / "Aftermovie V2.mp4")
        logo = cv2.imread(str(project / "branding" / "juict_logo_white_red.png"), cv2.IMREAD_UNCHANGED)
        self.ghost = bm.Ghost(logo)
        self.letters = bm2.LetterLogo(logo, 760)
        self.prints, self.first_shot, self.outro_base = {}, None, None

    # ------------------------------------------------------------ brand card (intro + outro)
    def _card(self, t, start, exit_k=0.0, label="AI INSPIRATIEDAG"):
        f = bm.field(start + t * 2.6)                               # lines drift faster (parallax)
        self.ghost.draw(f, -t * 2.2, alpha=0.032)                   # ghost logo drifts the other way
        bm.slab(f, t, (t - 0.05) / 0.5)
        bm2.streaks(f, t)
        bm.tech_layer(f, t, t_in=0.0, t_arrive=0.75)
        cx, cy = W / 2, H / 2 + 6
        t_fly = 0.28
        t_land = t_fly + 4 * 0.075 + 0.42                           # last letter lands
        scale = 1.0 + 0.02 * t
        if exit_k > 0:
            scale *= 1 + 0.9 * bm2.ease_in(exit_k)
        layer, flash = self.letters.layer(t, t_fly, cx, cy, scale, alpha=1 - bm2.ease_in(exit_k), tag_t0=t_land - 0.15)
        bm.red_bar(f, (t - t_land + 0.05) / 0.3, int(cy + 168 * scale), int(cx + 60 * scale))
        k = (t - t_land - 0.08) / 0.5
        shine = (bm.ease_io(k) * (bm.DIAG_MAX * 0.55) + W * 0.3) if 0 < k < 1 else None
        bm.bloom_shine(f, layer, shine, bloom=0.32 + 0.35 * flash)
        box = (int(cx - 430 * scale), int(cy - 181 * scale), int(cx + 430 * scale), int(cy + 179 * scale))
        g = max(0.0, 1 - abs(t - t_land - 0.03) / 0.05)
        if g > 0:
            bm.glitch(f, g, (max(box[0], 0), max(box[1], 0), min(box[2], W), min(box[3], H)))
        if exit_k == 0:
            bm.brackets(f, box, (t - t_land) / 0.25)
            bm.mono_label(f, label, box[0] + 4, box[3] + 30, t, t_land + 0.1)
        f = bm2.camera(f, t)
        bm.grain(f, start + t)
        return f

    def brand_card(self, t, start, exit_k=0.0):
        dt = 1 / (FPS * 3)                                          # motion blur: 3 sub-frame samples
        return sum(self._card(t + o, start, exit_k) for o in (-dt, 0.0, dt)) / 3

    def intro_frame(self, t):
        k = (t - (INTRO_END - 0.46)) / 0.46                         # last beat: punch-through + layered reveal
        card = self.brand_card(t, 0.0, exit_k=max(0.0, k))
        if k > 0:
            if self.first_shot is None:
                self.first_shot = self.after.at(2.80).astype(np.float32)
            card = bm.layered_wipe(card, self.first_shot, bm.ease_io(k), "reveal")
        return np.clip(card, 0, 255).astype(np.uint8)

    def outro_frame(self, src_t):
        if self.outro_base is None:
            self.outro_base = self.after.at(78.45).astype(np.float32)
        k = src_t - OUTRO_SRC
        card = self.brand_card(k, OUTRO_SRC)
        if k < 0.5:
            card = bm.layered_wipe(card, self.outro_base, bm.ease_io(k / 0.5), "cover")
        fade = bm.ease((k - 3.85) / 0.6)
        return np.clip(card * (1 - fade), 0, 255).astype(np.uint8)

    # ------------------------------------------------------------ photo snap
    def print_frame(self, name, k, scene):
        """The photo as a white-bordered print that lands on the blurred scene (slight tilt, settles in)."""
        if name not in self.prints:
            im = cv2.imread(str(self.p / "photos" / name))
            h = int(H * 0.74)
            im = cv2.resize(im, (int(im.shape[1] * h / im.shape[0]), h), interpolation=cv2.INTER_AREA)
            b = 16
            card = np.full((h + 2 * b, im.shape[1] + 2 * b, 4), 255, np.uint8)
            card[b:b + h, b:b + im.shape[1], :3] = im
            self.prints[name] = card
        card = self.prints[name]
        bg = cv2.GaussianBlur(scene, (0, 0), 14)
        bg = (bg.astype(np.float32) * 0.6).astype(np.uint8)
        e = ease(k * 1.6)
        s = 1.08 - 0.08 * e
        ang = {"photo_1.jpg": -2.0, "photo_2.jpg": 1.6, "photo_3.jpg": -1.2}.get(name, 1.5) * (1.6 - 0.6 * e)
        ch, cw = card.shape[:2]
        m = cv2.getRotationMatrix2D((cw / 2, ch / 2), ang, s)
        m[0, 2] += W / 2 - cw / 2
        m[1, 2] += H / 2 - ch / 2 + 14 * (1 - e)
        warped = cv2.warpAffine(card, m, (W, H), flags=cv2.INTER_LINEAR, borderValue=(0, 0, 0, 0))
        sh = cv2.GaussianBlur(warped[..., 3].astype(np.float32), (0, 0), 22) / 255 * 0.55
        sh = np.roll(sh, (18, 10), (0, 1))[..., None]
        bg = (bg.astype(np.float32) * (1 - sh)).astype(np.uint8)
        a = warped[..., 3:4].astype(np.float32) / 255
        return (warped[..., :3].astype(np.float32) * a + bg.astype(np.float32) * (1 - a)).astype(np.uint8)

    # ------------------------------------------------------------ timeline
    def frame(self, t):
        if t < INTRO_END:
            return self.intro_frame(t)
        src = t if t < CUT_AT else t + GAP
        if src >= OUTRO_SRC:
            return self.outro_frame(src)
        f = self.after.at(src)
        for s0, s1, name in SNAPS:                                  # flash, print lands, soft exit
            if s0 - 0.001 <= t < s1 + 0.12:
                ph = self.print_frame(name, (t - s0) / (s1 - s0), f)
                a = 1.0 if t < s1 else 1 - (t - s1) / 0.12
                f = (ph.astype(np.float32) * a + f.astype(np.float32) * (1 - a)).astype(np.uint8)
                flash = max(0.0, 1 - (t - s0) / 0.1) * 0.85
                if flash > 0:
                    f = (f.astype(np.float32) * (1 - flash) + 255 * flash).astype(np.uint8)
        return f


# ---------------------------------------------------------------- audio
def load(path):
    raw = subprocess.run([FF, "-v", "error", "-i", str(path), "-ac", "2", "-ar", str(SR), "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).reshape(-1, 2).copy()


def place(dst, clip, t, gain_db=0.0):
    i = int(t * SR)
    n = min(len(clip), len(dst) - i)
    if n > 0:
        dst[i:i + n] += clip[:n] * 10 ** (gain_db / 20)


def sfx(*parts):
    s = load(SFX.joinpath(*parts))
    return s / max(np.abs(s).max(), 1e-6)


def build_audio(project: Path, path: Path):
    mix = load(project / "source" / "Aftermovie V2.mp4")
    a, b, xf = int(CUT_AT * SR), int((CUT_AT + GAP) * SR), int(0.03 * SR)     # equal-power splice, same beat phase
    ramp = np.linspace(0, 1, xf, dtype=np.float32)[:, None]
    splice = mix[a - xf // 2:a + xf - xf // 2] * np.sqrt(1 - ramp) + mix[b - xf // 2:b + xf - xf // 2] * np.sqrt(ramp)
    out = np.concatenate([mix[:a - xf // 2], splice, mix[b + xf - xf // 2:]])
    out = np.pad(out, ((0, max(0, int(DUR * SR) - len(out))), (0, 0)))[:int(DUR * SR)].copy()

    click = sfx("Synths of the Past SFX", "Camera", "Old Camera", "Camera Click.wav")
    for s0, _, _ in SNAPS:
        place(out, click, s0 - 0.015, -15)
    whoosh = sfx("Quantum Motion Sound FX", "Whooshes", "FLOW_WHOOSH_SOFT_Air.wav")
    swipe = sfx("Quantum Motion Sound FX", "Whooshes", "FLOW_WHOOSH_SOFT_Swipe.wav")
    place(out, whoosh, 0.25, -17)                                   # intro: logo draws itself
    place(out, swipe, 2.34, -17)                                    # intro: panel reveals the footage
    place(out, swipe, OUTRO_SRC - 0.06 - GAP, -17)                  # outro: panel sweeps in
    place(out, whoosh, OUTRO_SRC + 0.29 - GAP, -19)                 # outro: logo draws itself

    peak = np.abs(out).max()
    if peak > 0.79:                                                 # ~-2 dBFS headroom (AAC overshoots)
        out *= 0.79 / peak
    out.astype(np.float32).tofile(path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project", nargs="?", default=str(PROJECT))
    ap.add_argument("--out", default="JUICT_aftermovie_v12.mp4")
    args = ap.parse_args()
    project = Path(args.project)
    film = Film(project)
    pcm = project / "analysis" / "_mix.f32"
    pcm.parent.mkdir(exist_ok=True)
    build_audio(project, pcm)
    dst = project / "exports" / args.out
    enc = subprocess.Popen([FF, "-v", "error", "-y",
                            "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H}", "-r", "30000/1001", "-i", "-",
                            "-f", "f32le", "-ar", str(SR), "-ac", "2", "-i", str(pcm),
                            "-c:v", "libx264", "-preset", "medium", "-crf", "16", "-pix_fmt", "yuv420p",
                            "-c:a", "aac", "-b:a", "320k", "-shortest", "-movflags", "+faststart", str(dst)],
                           stdin=subprocess.PIPE)
    total = int(DUR * FPS)
    for i in range(total):
        enc.stdin.write(np.ascontiguousarray(film.frame(i / FPS)).tobytes())
        if i % 300 == 0:
            print(f"{i}/{total}", flush=True)
    enc.stdin.close()
    enc.wait()
    print("done", dst)


if __name__ == "__main__":
    main()
