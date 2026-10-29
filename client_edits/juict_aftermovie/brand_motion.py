"""JUICT brand motion: navy field with slanted line texture, logo that draws itself on, slanted panel wipes.

All shapes follow the italic slant of the JUICT logo so intro, outro and transitions feel like one system.
"""
import math

import cv2
import numpy as np

W, H = 1920, 1080
NAVY = np.array((0x63, 0x42, 0x23), np.float32)         # BGR
NAVY_DEEP = np.array((0x3A, 0x24, 0x12), np.float32)
RED = np.array((0x48, 0x3F, 0xD4), np.float32)
SLANT = math.radians(12)                                  # lean of the logo's vertical strokes
TAN = math.tan(SLANT)

_yy, _xx = np.mgrid[0:H, 0:W].astype(np.float32)
DIAG = _xx + (H - _yy) * TAN                              # coordinate along the slant (0 .. W + H*tan)
DIAG_MAX = W + H * TAN


def ease(x):
    x = min(max(x, 0.0), 1.0)
    return 1 - (1 - x) ** 3


def ease_io(x):
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)


# ---------------------------------------------------------------- background field
def _field():
    # deep navy gradient, lighter towards the upper right, plus a soft vignette
    g = np.clip((_xx / W) * 0.55 + (1 - _yy / H) * 0.45, 0, 1)[..., None]
    base = NAVY_DEEP + (NAVY - NAVY_DEEP) * g
    v = 1 - 0.35 * (((_xx - W / 2) / (W * 0.75)) ** 2 + ((_yy - H / 2) / (H * 0.8)) ** 2)
    return base * np.clip(v, 0.55, 1)[..., None]


FIELD = _field()


def lines(t):
    """Fine slanted lines drifting slowly; every 7th line a touch brighter."""
    period = 46.0
    off = (DIAG - t * 38) % period
    thin = np.clip(1.4 - np.abs(off - period / 2), 0, 1)
    idx = np.floor((DIAG - t * 38) / period) % 7
    a = np.where(idx == 0, 0.10, 0.035) * thin
    return a[..., None]


def field(t):
    f = FIELD + (255 - FIELD) * lines(t)
    return f


# ---------------------------------------------------------------- logo draw-on
class Logo:
    def __init__(self, rgba, width):
        h = int(rgba.shape[0] * width / rgba.shape[1])
        self.img = cv2.resize(rgba, (width, h), interpolation=cv2.INTER_AREA).astype(np.float32)
        self.h, self.w = self.img.shape[:2]
        yy, xx = np.mgrid[0:self.h, 0:self.w].astype(np.float32)
        d = xx + (self.h - yy) * TAN
        self.d = d / d.max()                                  # 0..1 along the slant
        b, g, r = self.img[..., 0], self.img[..., 1], self.img[..., 2]
        self.is_red = ((r - b) > 60)                          # "VOOR IT"

    def draw(self, dst, cx, cy, p_logo, p_tag, alpha=1.0, scale=1.0):
        """p_logo: 0..1 draw-on progress of JUICT (slanted sweep with a red glowing edge); p_tag: VOOR IT."""
        a = self.img[..., 3] / 255.0
        edge = p_logo * 1.12 - 0.06
        reveal = np.clip((edge - self.d) / 0.06 + 1, 0, 1)
        glow = np.clip(1 - np.abs(self.d - edge) / 0.05, 0, 1) * (p_logo < 1)
        rgb = self.img[..., :3].copy()
        rgb = rgb * (1 - glow[..., None]) + RED * glow[..., None]
        a_logo = a * reveal * (~self.is_red)
        tag_shift = int(40 * (1 - p_tag))
        a_tag = a * self.is_red * p_tag
        img = np.dstack([rgb, (a_logo + 0 * a_tag) * 255 * alpha])
        tag = np.dstack([self.img[..., :3], a_tag * 255 * alpha])
        if scale != 1.0:
            img = cv2.resize(img, None, fx=scale, fy=scale)
            tag = cv2.resize(tag, None, fx=scale, fy=scale)
        x, y = int(cx - img.shape[1] / 2), int(cy - img.shape[0] / 2)
        _over(dst, img, x, y)
        _over(dst, tag, x - tag_shift, y)


def _over(dst, rgba, x, y):
    h, w = rgba.shape[:2]
    x0, y0, x1, y1 = max(x, 0), max(y, 0), min(x + w, W), min(y + h, H)
    if x1 <= x0 or y1 <= y0:
        return
    src = rgba[y0 - y:y1 - y, x0 - x:x1 - x]
    a = src[..., 3:4] / 255.0
    dst[y0:y1, x0:x1] = src[..., :3] * a + dst[y0:y1, x0:x1] * (1 - a)


# ---------------------------------------------------------------- slanted panel wipe
def panel_mask(p, reverse=False):
    """Mask (1 = panel) of a slanted panel that sweeps across the frame; p 0..1.
    reverse=False: panel enters from the left and covers; True: panel leaves to the right."""
    edge = p * (DIAG_MAX + 80) - 40
    if not reverse:
        m = np.clip((edge - DIAG) / 3 + 0.5, 0, 1)
    else:
        m = np.clip((DIAG - edge) / 3 + 0.5, 0, 1)
    band = np.clip(1 - np.abs(DIAG - edge) / 7, 0, 1) * (0 < p < 1)
    return m[..., None], band[..., None]


def wipe(under, over_img, p, reverse=False):
    """over_img covers `under` with a slanted panel edge in JUICT red."""
    m, band = panel_mask(p, reverse)
    out = under * (1 - m) + over_img * m
    return out * (1 - band) + RED * band


# ---------------------------------------------------------------- tech layer (subtle)
def _traces(seed=7, logo_box=(580, 400, 1340, 690)):
    """PCB-like traces from the frame edges towards the logo: horizontal runs + slanted legs, end in a node."""
    rng = np.random.default_rng(seed)
    x0, y0, x1, y1 = logo_box
    out = []
    for side in ("L", "R") * 4:
        y = float(rng.uniform(140, H - 140))
        if y0 - 30 < y < y1 + 30:
            y += 220 * (1 if y > H / 2 else -1)
        if side == "L":
            pts = [(-10, y), (rng.uniform(140, 380), y)]
            ty = rng.uniform(y0 + 30, y1 - 30)
            dx = (y - ty) * TAN
            pts.append((pts[-1][0] + abs(y - ty) * TAN + 30, ty))
            pts.append((x0 - rng.uniform(30, 90), ty))
        else:
            pts = [(W + 10, y), (W - rng.uniform(140, 380), y)]
            ty = rng.uniform(y0 + 30, y1 - 30)
            pts.append((pts[-1][0] - abs(y - ty) * TAN - 30, ty))
            pts.append((x1 + rng.uniform(30, 90), ty))
        dense = []
        for (ax, ay), (bx, by) in zip(pts, pts[1:]):
            n = max(int(math.hypot(bx - ax, by - ay) / 3), 1)
            dense += [(ax + (bx - ax) * i / n, ay + (by - ay) * i / n) for i in range(n)]
        dense.append(pts[-1])
        out.append((np.array(pts, np.float32), np.array(dense, np.float32), float(rng.uniform(0.0, 0.35))))
    return out


TRACES = _traces()


def tech_layer(dst, t, t_in=0.1, t_arrive=1.1, fade_out=None):
    """Faint traces + data pulses that travel to the logo and arrive around t_arrive."""
    fade = 1.0 if fade_out is None else max(0.0, 1 - (t - fade_out) / 0.4)
    layer = np.zeros((H, W, 3), np.float32)
    show = ease((t - t_in) / 0.5) * fade
    if show <= 0:
        return
    for pts, dense, delay in TRACES:
        cv2.polylines(layer, [pts.astype(np.int32)], False, (255, 255, 255), 1, cv2.LINE_AA)
        end = tuple(int(v) for v in pts[-1])
        cv2.circle(layer, end, 4, (255, 255, 255), 1, cv2.LINE_AA)
    layer *= 0.10 * show
    pulses = np.zeros((H, W, 3), np.float32)
    for pts, dense, delay in TRACES:
        k = (t - t_in - delay) / max(t_arrive - t_in - delay, 0.2)       # 0..1 along the trace
        if not 0 < k < 1.15:
            continue
        head = int(min(k, 1.0) * (len(dense) - 1))
        tail = max(head - 45, 0)
        for i in range(tail, head):
            a = (i - tail) / max(head - tail, 1)
            col = RED * a + np.array((255, 255, 255), np.float32) * (1 - a) * 0.6
            p0, p1 = dense[i], dense[i + 1]
            cv2.line(pulses, (int(p0[0]), int(p0[1])), (int(p1[0]), int(p1[1])), (col * a).tolist(), 2, cv2.LINE_AA)
        if k >= 1.0:                                                     # node lights up on arrival
            glow = max(0.0, 1 - (k - 1.0) / 0.15)
            cv2.circle(pulses, tuple(int(v) for v in pts[-1]), 5, (RED * glow).tolist(), -1, cv2.LINE_AA)
    pulses = cv2.GaussianBlur(pulses, (0, 0), 1.2) * 1.6 + pulses
    dst += (layer + pulses * fade)
    np.clip(dst, 0, 255, out=dst)


def glitch(img, strength, box):
    """Tiny RGB split + one sliced offset inside box (x0, y0, x1, y1)."""
    if strength <= 0:
        return img
    x0, y0, x1, y1 = box
    roi = img[y0:y1, x0:x1].copy()
    s = int(round(5 * strength))
    out = roi.copy()
    out[:, s:, 2] = roi[:, :-s or None, 2] if s else roi[:, :, 2]
    out[:, :-s or None, 0] = roi[:, s:, 0] if s else roi[:, :, 0]
    h = roi.shape[0]
    a, b = int(h * 0.42), int(h * 0.55)
    out[a:b] = np.roll(out[a:b], int(14 * strength), axis=1)
    img[y0:y1, x0:x1] = out
    return img


def brackets(dst, box, p, arm=34, color=(255, 255, 255), alpha=0.75):
    """HUD corner brackets that snap in around box; p 0..1."""
    if p <= 0:
        return
    x0, y0, x1, y1 = box
    grow = 1.18 - 0.18 * ease(p)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    hw, hh = (x1 - x0) / 2 * grow, (y1 - y0) / 2 * grow
    layer = np.zeros_like(dst)
    for sx in (-1, 1):
        for sy in (-1, 1):
            px, py = int(cx + sx * hw), int(cy + sy * hh)
            cv2.line(layer, (px, py), (px - sx * arm, py), color, 2, cv2.LINE_AA)
            cv2.line(layer, (px, py), (px, py - sy * arm), color, 2, cv2.LINE_AA)
    a = alpha * ease(p)
    np.copyto(dst, dst * (1 - (layer > 0) * a) + layer * a)


_MONO = None


def mono_label(dst, text, x, y, t, start, cps=22, alpha=0.8):
    """Typewriter label in a mono font with a blinking block cursor."""
    global _MONO
    from PIL import Image, ImageDraw, ImageFont
    if _MONO is None:
        _MONO = ImageFont.truetype(r"C:\Windows\Fonts\consola.ttf", 25)
    if t < start:
        return
    n = min(len(text), int((t - start) * cps))
    shown = " ".join(text[:n])                                  # letter-spaced
    cursor = (int((t - start) * 3.2) % 2 == 0) or n < len(text)
    img = Image.new("L", (900, 40), 0)
    d = ImageDraw.Draw(img)
    d.text((0, 6), shown, font=_MONO, fill=255)
    if cursor:
        w = d.textlength(shown + (" " if shown else ""), font=_MONO)
        d.rectangle((w, 10, w + 11, 32), fill=255)
    m = np.array(img, np.float32)[..., None] / 255 * alpha
    h, w = m.shape[:2]
    roi = dst[y:y + h, x:x + w]
    roi[:] = roi * (1 - m) + 255 * m


# ---------------------------------------------------------------- v9: stronger look
_RNG = np.random.default_rng(3)
_GRAIN = [(_RNG.standard_normal((H // 2, W // 2)).astype(np.float32)) for _ in range(6)]


def grain(dst, t, amount=3.5):
    g = cv2.resize(_GRAIN[int(t * 24) % len(_GRAIN)], (W, H), interpolation=cv2.INTER_LINEAR)
    dst += g[..., None] * amount


class Ghost:
    """Huge, faint outline of the logo drifting behind everything (parallax depth)."""
    def __init__(self, rgba, width=3000):
        h = int(rgba.shape[0] * width / rgba.shape[1])
        a = cv2.resize(rgba[..., 3], (width, h), interpolation=cv2.INTER_AREA).astype(np.float32) / 255
        self.a = a

    def draw(self, dst, t, alpha=0.05):
        h, w = self.a.shape
        x = int(-w * 0.18 - 30 * t)
        y = int(H / 2 - h / 2 + 40)
        x0, y0, x1, y1 = max(x, 0), max(y, 0), min(x + w, W), min(y + h, H)
        m = self.a[y0 - y:y1 - y, x0 - x:x1 - x][..., None] * alpha
        dst[y0:y1, x0:x1] = dst[y0:y1, x0:x1] * (1 - m) + 255 * m


def slab(dst, t, p):
    """A lighter slanted slab behind the logo (gives the logo a stage), slides in with p."""
    if p <= 0:
        return
    cx = W / 2 + 160 * (1 - ease(p))
    d0 = cx - 520 + (H / 2) * TAN
    d1 = cx + 520 + (H / 2) * TAN
    inside = np.clip((DIAG - d0) / 2, 0, 1) * np.clip((d1 - DIAG) / 2, 0, 1)
    band_y = np.clip(1 - np.abs(_yy - H / 2) / (H * 0.5), 0, 1) ** 0.6
    m = (inside * band_y * 0.10 * ease(p))[..., None]
    dst += (np.array((0x9A, 0x6E, 0x45), np.float32) - dst) * m


def red_bar(dst, p, y, x_end, length=520, thick=7):
    """Thin slanted JUICT-red bar shooting in from the left under the logo."""
    if p <= 0:
        return
    l = length * ease(p)
    x1 = x_end
    x0 = x1 - l
    pts = np.array([(x0, y + thick), (x1, y + thick), (x1 + thick * TAN * 2, y - thick), (x0 + thick * TAN * 2, y - thick)], np.int32)
    layer = np.zeros_like(dst)
    cv2.fillPoly(layer, [pts], RED.tolist(), cv2.LINE_AA)
    m = (layer.sum(axis=2, keepdims=True) > 0).astype(np.float32)
    dst[:] = dst * (1 - m) + layer * m


def logo_layer(logo, p_logo, p_tag, scale, cx, cy):
    """Full-frame RGBA (float) of the logo with draw-on, so it can be bloomed and shined."""
    canvas = np.zeros((H, W, 4), np.float32)
    rgb = np.zeros((H, W, 3), np.float32)
    logo.draw(rgb, cx, cy, p_logo, p_tag, 1.0, scale)
    mask = np.zeros((H, W, 3), np.float32) + 0
    white = np.full((H, W, 3), 255.0, np.float32)
    logo.draw(mask, cx, cy, p_logo, p_tag, 1.0, scale)                 # same draw on black -> luminance as alpha
    a = np.clip(mask.max(axis=2) / 255.0, 0, 1)
    canvas[..., :3] = rgb
    canvas[..., 3] = a
    return canvas


def bloom_shine(dst, layer, shine_pos=None, bloom=0.55):
    a = layer[..., 3:4]
    rgb = layer[..., :3]
    glow = cv2.GaussianBlur(rgb * a, (0, 0), 14) * bloom + cv2.GaussianBlur(rgb * a, (0, 0), 40) * bloom * 0.6
    dst += glow
    if shine_pos is not None:
        band = np.exp(-((DIAG - shine_pos) / 55.0) ** 2)[..., None]
        rgb = rgb + (255 - rgb) * band * 0.9
    dst[:] = dst * (1 - a) + rgb * a


def layered_wipe(card, footage, p, mode="reveal", red_w=110, gap=40):
    """Staggered slanted panels: card -> red band -> footage.
    reveal: card leaves to the right exposing footage; cover: card enters from the left over footage."""
    span = DIAG_MAX + red_w + gap + 80
    lead = p * span - 40
    trail = lead - red_w
    if mode == "reveal":
        m_card = np.clip((DIAG - lead) / 2 + 0.5, 0, 1)[..., None]          # card right of lead
        m_red = np.clip((DIAG - trail) / 2 + 0.5, 0, 1)[..., None] * (1 - m_card)
    else:
        m_card = np.clip((trail - DIAG) / 2 + 0.5, 0, 1)[..., None]         # card left of trail
        m_red = np.clip((lead - DIAG) / 2 + 0.5, 0, 1)[..., None] * (1 - m_card)
    m_foot = 1 - m_card - m_red
    return card * m_card + RED * m_red + footage * m_foot
