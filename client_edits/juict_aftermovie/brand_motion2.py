"""JUICT brand motion, v10 additions: kinetic letters, speed streaks, camera move."""
import cv2
import numpy as np

from brand_motion import H, RED, TAN, W, ease, ease_io


def ease_out_back(x, s=1.5):
    x = min(max(x, 0.0), 1.0) - 1
    return 1 + (s + 1) * x ** 3 + s * x ** 2


def ease_in(x):
    x = min(max(x, 0.0), 1.0)
    return x ** 3


class LetterLogo:
    """The logo split into its letters (connected shapes) so each can fly in on its own."""

    def __init__(self, rgba, width):
        sc = width / rgba.shape[1]
        img = cv2.resize(rgba, (width, int(rgba.shape[0] * sc)), interpolation=cv2.INTER_AREA)
        self.h, self.w = img.shape[:2]
        a = img[..., 3] > 10
        red = (img[..., 2].astype(int) - img[..., 0].astype(int)) > 60
        n, lab, st, _ = cv2.connectedComponentsWithStats((a & ~red).astype(np.uint8), 8)
        comps = sorted([i for i in range(1, n) if st[i, 4] > 150 * sc * sc], key=lambda i: st[i, 0])
        groups = []                                  # the "i" is two shapes (stem + bar): merge overlapping x-ranges
        for i in comps:
            x0, x1 = st[i, 0], st[i, 0] + st[i, 2]
            if groups and x0 < groups[-1][1] - 0.15 * (x1 - x0):
                groups[-1][0].append(i)
                groups[-1][1] = max(groups[-1][1], x1)
            else:
                groups.append([[i], x1])
        self.letters = []
        for ids, _ in groups:
            m = np.isin(lab, ids).astype(np.uint8)
            m = cv2.dilate(m, np.ones((3, 3), np.uint8)).astype(bool) & ~red   # keep anti-aliased edges
            spr = img.astype(np.float32).copy()
            spr[..., 3] *= m
            self.letters.append(spr)
        tag = img.astype(np.float32).copy()
        tag[..., 3] *= red
        self.tag = tag

    def layer(self, t, t0, cx, cy, scale=1.0, stagger=0.075, dur=0.42, alpha=1.0, tag_t0=None):
        """RGBA float layer with letters flying in along the slant; returns (layer, landing_flash)."""
        out = np.zeros((H, W, 4), np.float32)
        flash = 0.0
        for k, spr in enumerate(self.letters):
            p = (t - (t0 + k * stagger)) / dur
            if p <= 0:
                continue
            e = ease_out_back(p, 1.2)
            dx = 300 * (1 - e)
            dy = -300 * TAN * (1 - e) - 30 * (1 - e)
            s = scale * (1 + 0.35 * (1 - ease(p)))
            _sprite(out, spr, cx + dx, cy + dy, s, alpha * ease(p * 2.2))
            if p > 0.6:
                flash = max(flash, max(0.0, 1 - abs(p - 1) / 0.35))
        if tag_t0 is not None and t > tag_t0:
            p = (t - tag_t0) / 0.5
            sx = 1 + 0.45 * (1 - ease(p))                    # tracks in from wide to tight
            _sprite(out, self.tag, cx + 120 * (1 - ease(p)), cy, scale, alpha * ease(p * 1.5), sx)
        return out, flash


def _sprite(dst, spr, cx, cy, s, a, sx=1.0):
    """Warp a logo-sized RGBA sprite so its centre lands on (cx, cy), scale s, extra x-stretch sx."""
    h, w = spr.shape[:2]
    m = np.array([[s * sx, 0, cx - s * sx * w / 2], [0, s, cy - s * h / 2]], np.float32)
    warped = cv2.warpAffine(spr, m, (W, H), flags=cv2.INTER_LINEAR, borderValue=(0, 0, 0, 0))
    wa = warped[..., 3:4] / 255.0 * max(a, 0.0)
    dst[..., :3] = warped[..., :3] * wa + dst[..., :3] * (1 - wa)
    dst[..., 3:4] = wa + dst[..., 3:4] * (1 - wa)


_SR = np.random.default_rng(11)
STREAKS = [(float(_SR.uniform(60, H - 60)), float(_SR.uniform(180, 520)), float(_SR.uniform(1800, 3400)),
            float(_SR.uniform(-0.2, 2.4)), bool(_SR.random() < 0.3), int(_SR.integers(1, 3))) for _ in range(16)]


def streaks(dst, t, amount=1.0):
    """Fast thin light streaks shooting across the frame (speed lines)."""
    layer = np.zeros((H, W, 3), np.float32)
    for y, ln, v, t0, red, th in STREAKS:
        for rep in (0.0, 2.9):                               # repeat so a longer card keeps moving
            k = t - t0 - rep
            if k < 0:
                continue
            x1 = -ln + k * v
            if x1 - ln > W + 200:
                continue
            col = RED if red else np.array((255, 255, 255), np.float32)
            cv2.line(layer, (int(x1 - ln), int(y)), (int(x1), int(y)), (col * 0.55).tolist(), th, cv2.LINE_AA)
    dst += cv2.GaussianBlur(layer, (0, 0), 0.8) * amount


def camera(img, t, push=0.07, roll=(-1.0, 0.5)):
    """Continuous camera move: slow push-in and a slight roll."""
    s = 1.04 + push * t
    ang = roll[0] + (roll[1] - roll[0]) * ease_io(t / 3.0)
    m = cv2.getRotationMatrix2D((W / 2, H / 2), ang, s)
    return cv2.warpAffine(img, m, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
