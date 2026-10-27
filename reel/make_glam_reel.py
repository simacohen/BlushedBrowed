"""Render the "floating products -> glam reveal" reel for Blushed & Browed.

Same beat structure as the example reel:
  products float around the face, swarm onto it, ghost-dissolve into the glam
  shot, then the frame darkens behind a centred Instagram logo + handle.

    python3 reel/make_glam_reel.py
    python3 reel/make_glam_reel.py --music song.mp3
"""
import argparse
import math
import os
import subprocess

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")
OUT_DIR = os.path.join(HERE, "output")

W, H, FPS = 1080, 1920, 30
SS = 3  # supersampling for the drawn products / logo
HANDLE = "@BLUSHEDBROWED"

# beats (seconds)
POP_END = 0.8
SWARM_START, SWARM_END = 4.0, 5.6
GHOST_START, GHOST_END = 5.5, 6.4
END_START = 8.4
TOTAL = 10.8

ROSE_GOLD = (190, 140, 115)
GOLD = (212, 172, 112)
ESPRESSO = (70, 46, 36)
LIP_PINK = (214, 70, 104)
BROW_BROWN = (110, 66, 44)


def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def ease_out(x):
    x = clamp(x)
    return 1 - (1 - x) ** 3


def ease_in_out(x):
    x = clamp(x)
    return 4 * x ** 3 if x < 0.5 else 1 - (-2 * x + 2) ** 3 / 2


def back_out(x):
    x = clamp(x)
    c = 1.9
    return 1 + (c + 1) * (x - 1) ** 3 + c * (x - 1) ** 2


def font(path, size):
    return ImageFont.truetype(path, size)


HANDLE_FONT = "/usr/share/fonts/opentype/inter/InterDisplay-SemiBold.otf"
LABEL_FONT = "/usr/share/fonts/opentype/inter/Inter-Medium.otf"
SERIF_FONT = "/usr/share/fonts/truetype/crosextra/Caladea-Regular.ttf"


# ---------------------------------------------------------------- product drawing

def shaded(w, h, color, spec=0.55):
    """A cylinder-shaded swatch lit from the upper left."""
    x = np.linspace(-1, 1, w)[None, :]
    diffuse = 0.58 + 0.42 * np.cos(np.clip((x + 0.3) * 1.35, -math.pi / 2, math.pi / 2))
    rim = 0.12 * np.exp(-((x - 0.85) / 0.1) ** 2)
    hi = spec * np.exp(-((x + 0.5) / 0.11) ** 2)
    c = np.array(color, np.float32)[None, None, :]
    rgb = c * (diffuse + rim)[..., None] + 255 * hi[..., None]
    rgb = np.repeat(rgb, h, axis=0)
    a = np.full((h, w, 1), 255, np.float32)
    return Image.fromarray(np.clip(np.concatenate([rgb, a], 2), 0, 255).astype(np.uint8), "RGBA")


def part(canvas, box, color, radius=0, spec=0.55, alpha=255, poly=None):
    s = SS
    x0, y0, x1, y1 = [round(v * s) for v in box]
    swatch = shaded(x1 - x0, y1 - y0, color, spec)
    mask = Image.new("L", swatch.size, 0)
    md = ImageDraw.Draw(mask)
    if poly:
        md.polygon([((px - box[0]) * s, (py - box[1]) * s) for px, py in poly], fill=alpha)
    else:
        md.rounded_rectangle((0, 0, swatch.width - 1, swatch.height - 1), radius * s, fill=alpha)
    canvas.paste(swatch, (x0, y0), mask)


def blank(w, h):
    return Image.new("RGBA", (w * SS, h * SS), (0, 0, 0, 0))


def finish(img):
    return img.resize((img.width // SS, img.height // SS), Image.LANCZOS)


def lipstick():
    c = blank(70, 230)
    part(c, (0, 110, 70, 230), ROSE_GOLD, 6)
    part(c, (8, 58, 62, 104), GOLD, 4)
    part(c, (12, 0, 58, 64), (200, 80, 108), poly=[(12, 64), (12, 26), (58, 2), (58, 64)])
    part(c, (0, 100, 70, 116), (38, 28, 28), 3, spec=0.25)
    return finish(c)


def pigment_bottle(liquid, label):
    c = blank(92, 236)
    part(c, (0, 96, 92, 236), liquid, 20, spec=0.7)
    part(c, (4, 100, 30, 230), (255, 255, 255), 14, spec=0, alpha=40)  # glass sheen
    part(c, (8, 52, 84, 100), (236, 222, 226), 10, spec=0.5)
    part(c, (24, 0, 68, 58), (244, 234, 238), poly=[(26, 58), (40, 4), (52, 4), (66, 58)])
    d = ImageDraw.Draw(c)
    d.rounded_rectangle((8 * SS, 146 * SS, 84 * SS, 196 * SS), 4 * SS, fill=(248, 244, 240, 255))
    d.text((46 * SS, 164 * SS), label, font=font(LABEL_FONT, 15 * SS), fill=(50, 40, 40, 255), anchor="mm")
    d.text((46 * SS, 182 * SS), "PIGMENT", font=font(LABEL_FONT, 9 * SS), fill=(120, 100, 100, 255), anchor="mm")
    return finish(c)


def pmu_pen():
    c = blank(56, 340)
    d = ImageDraw.Draw(c)
    d.line((28 * SS, 0, 28 * SS, 14 * SS), fill=(70, 70, 75, 255), width=2 * SS)
    part(c, (17, 10, 39, 74), (226, 222, 228), 6, spec=0.8, alpha=230)
    part(c, (6, 66, 50, 146), (52, 42, 42), 10, spec=0.3)
    part(c, (0, 140, 56, 340), ROSE_GOLD, 24)
    part(c, (0, 140, 56, 152), GOLD, 4)
    return finish(c)


def spoolie():
    c = blank(44, 270)
    part(c, (15, 104, 29, 270), ESPRESSO, 7)
    part(c, (13, 84, 31, 108), GOLD, 3)
    d = ImageDraw.Draw(c)
    for y in range(4, 86, 3):
        r = 18 * math.sin(math.pi * clamp((y + 6) / 96)) ** 0.6
        d.line(((22 - r) * SS, y * SS, (22 + r) * SS, (y + 4) * SS), fill=(30, 26, 26, 255), width=SS + 1)
    return finish(c)


def brow_pencil():
    c = blank(36, 310)
    part(c, (0, 62, 36, 310), (98, 64, 46), 4)
    part(c, (0, 280, 36, 310), GOLD, 4)
    part(c, (0, 8, 36, 64), (226, 192, 152), poly=[(0, 64), (36, 64), (18, 8)])
    part(c, (11, 0, 25, 30), (62, 40, 30), poly=[(11, 30), (25, 30), (18, 0)])
    return finish(c)


def tweezers():
    c = blank(64, 270)
    part(c, (2, 0, 30, 270), ROSE_GOLD, poly=[(24, 0), (32, 0), (14, 270), (4, 270)])
    part(c, (32, 0, 62, 270), ROSE_GOLD, poly=[(32, 0), (40, 0), (60, 270), (50, 270)])
    part(c, (20, 0, 44, 40), GOLD, 6)
    return finish(c)


def compact():
    n = 180 * SS
    yy, xx = np.mgrid[0:n, 0:n].astype(np.float32)
    cx = cy = n / 2
    r = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2) / (n / 2)
    light = np.clip(1.0 - 0.35 * ((xx - cx * 0.6) ** 2 + (yy - cy * 0.6) ** 2) ** 0.5 / n, 0.5, 1.2)
    rgb = np.where((r < 0.8)[..., None], np.array([226, 142, 152], np.float32), np.array(GOLD, np.float32))
    rgb = rgb * light[..., None]
    ring = np.exp(-((r - 0.8) / 0.03) ** 2) * 60
    rgb = rgb + ring[..., None]
    a = (np.clip((1 - r) * n / 4, 0, 1) * 255)[..., None]
    img = Image.fromarray(np.clip(np.concatenate([rgb, a], 2), 0, 255).astype(np.uint8), "RGBA")
    d = ImageDraw.Draw(img)
    d.text((n / 2, n / 2 + 4 * SS), "B", font=font(SERIF_FONT, 82 * SS), fill=(200, 112, 124, 255), anchor="mm")
    return finish(img)


def with_shadow(img, blur=10, off=(8, 14), opacity=0.45):
    pad = blur * 3
    out = Image.new("RGBA", (img.width + pad * 2, img.height + pad * 2), (0, 0, 0, 0))
    sh = Image.new("RGBA", img.size, (20, 10, 5, 255))
    sh.putalpha(img.getchannel("A").point(lambda v: int(v * opacity)))
    out.alpha_composite(sh, (pad + off[0], pad + off[1]))
    out = out.filter(ImageFilter.GaussianBlur(blur))
    out.alpha_composite(img, (pad, pad))
    return out


# ---------------------------------------------------------------- instagram logo

def ig_gradient(n):
    yy, xx = np.mgrid[0:n, 0:n].astype(np.float32) / n
    t = np.clip((xx * 0.55 + (1 - yy) * 0.75) / 1.3, 0, 1)
    stops = np.array([[254, 218, 117], [250, 126, 30], [214, 41, 118], [150, 47, 191], [79, 91, 213]], np.float32)
    pos = np.linspace(0, 1, len(stops))
    rgb = np.stack([np.interp(t, pos, stops[:, k]) for k in range(3)], -1)
    return Image.fromarray(rgb.astype(np.uint8), "RGB")


def ig_glyph(size):
    n = size * SS
    mask = Image.new("L", (n, n), 0)
    d = ImageDraw.Draw(mask)
    w = round(n * 0.085)
    d.rounded_rectangle((w / 2, w / 2, n - w / 2, n - w / 2), n * 0.28, outline=255, width=w)
    r = n * 0.215
    d.ellipse((n / 2 - r, n / 2 - r, n / 2 + r, n / 2 + r), outline=255, width=w)
    rd = n * 0.06
    d.ellipse((n * 0.745 - rd, n * 0.255 - rd, n * 0.745 + rd, n * 0.255 + rd), fill=255)
    return mask.resize((size, size), Image.LANCZOS), ig_gradient(size)


# ---------------------------------------------------------------- scene

class GlamReel:
    def __init__(self):
        self.portrait = Image.open(os.path.join(ASSETS, "portrait.jpg")).convert("RGB")
        glam = ImageEnhance.Color(self.portrait).enhance(1.10)
        glam = ImageEnhance.Brightness(glam).enhance(1.03)
        glow = glam.filter(ImageFilter.GaussianBlur(18))
        self.glam = Image.blend(glam, Image.composite(glow, glam, glow.convert("L")), 0.22)

        # (image, home x, home y, home angle, swarm x, swarm y, swarm angle)
        items = [
            (pigment_bottle(LIP_PINK, "LIP"), 205, 520, -16, 470, 820, -30),
            (lipstick(), 820, 760, 14, 600, 740, 40),
            (spoolie(), 880, 520, 28, 640, 880, -20),
            (compact(), 905, 1090, 0, 560, 900, 0),
            (tweezers(), 140, 860, -12, 450, 950, 25),
            (pigment_bottle(BROW_BROWN, "BROW"), 175, 1200, 10, 520, 1010, 15),
            (brow_pencil(), 860, 1360, 32, 620, 1040, -45),
            (pmu_pen(), 470, 1450, -24, 540, 980, 60),
        ]
        self.items = [(with_shadow(img), *rest) for img, *rest in items]

        self.glyph_small, self.grad_small = ig_glyph(46)
        self.glyph_big, self.grad_big = ig_glyph(170)
        self.handle_small = ImageFont.truetype(HANDLE_FONT, 25)
        self.handle_big = ImageFont.truetype(HANDLE_FONT, 50)

    @staticmethod
    def cover(img, zoom, focus):
        s = max(W / img.width, H / img.height) * zoom
        rw, rh = round(img.width * s), round(img.height * s)
        x = clamp(focus[0] * rw - W / 2, 0, rw - W)
        y = clamp(focus[1] * rh - H / 2, 0, rh - H)
        box = (x / s, y / s, (x + W) / s, (y + H) / s)
        return img.resize((W, H), Image.BICUBIC, box=box)

    def before(self, t):
        zoom = 1.0 + 0.05 * clamp(t / GHOST_END)
        img = self.cover(self.portrait, zoom, (0.5, 0.5)).convert("RGBA")
        swarm = ease_in_out((t - SWARM_START) / (SWARM_END - SWARM_START))
        for k, (it, hx, hy, ha, sx, sy, sa) in enumerate(self.items):
            pop = back_out((t - 0.08 * k) / 0.5)
            if pop <= 0:
                continue
            ph = k * 1.7
            fx = hx + 14 * math.sin(t * 1.3 + ph)
            fy = hy + 18 * math.sin(t * 1.7 + ph * 1.3)
            fa = ha + 5 * math.sin(t * 1.1 + ph)
            x = fx + (sx - fx) * swarm
            y = fy + (sy - fy) * swarm
            a = fa + (sa - fa) * swarm
            scale = pop * (1 - 0.15 * swarm)
            if scale <= 0.02:
                continue
            im = it.resize((max(1, round(it.width * scale)), max(1, round(it.height * scale))), Image.BICUBIC)
            im = im.rotate(-a, Image.BICUBIC, expand=True)
            img.alpha_composite(im, (round(x - im.width / 2), round(y - im.height / 2)))
        return img.convert("RGB")

    def after(self, t):
        p = clamp((t - GHOST_START) / (TOTAL - GHOST_START))
        return self.cover(self.glam, 1.42 - 0.10 * ease_out(p), (0.5, 0.40))

    def corner_badge(self, img, alpha):
        if alpha <= 0:
            return img
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        white = Image.new("RGBA", self.glyph_small.size, (255, 255, 255, 255))
        white.putalpha(self.glyph_small.point(lambda v: int(v * alpha)))
        layer.alpha_composite(white, (930 - 23, 437))
        ImageDraw.Draw(layer).text((930, 515), HANDLE, font=self.handle_small,
                                   fill=(255, 255, 255, int(235 * alpha)), anchor="mm")
        out = img.convert("RGBA")
        out.alpha_composite(layer)
        return out.convert("RGB")

    def end_card(self, img, t):
        p = ease_out((t - END_START) / 0.45)
        if p <= 0:
            return img
        img = Image.blend(img, Image.new("RGB", (W, H), (12, 10, 10)), 0.66 * p)
        # logo goes white -> instagram gradient -> white, like the example
        g = math.sin(math.pi * clamp((t - END_START - 0.3) / 1.8))
        n = self.glyph_big.width
        logo = Image.blend(Image.new("RGB", (n, n), (255, 255, 255)), self.grad_big, g).convert("RGBA")
        logo.putalpha(self.glyph_big.point(lambda v: int(v * p)))
        s = 0.88 + 0.12 * p
        logo = logo.resize((round(n * s), round(n * s)), Image.LANCZOS)
        out = img.convert("RGBA")
        out.alpha_composite(logo, (round(W / 2 - logo.width / 2), round(900 - logo.height / 2)))
        ImageDraw.Draw(out).text((W / 2, 1065), HANDLE, font=self.handle_big,
                                 fill=(255, 255, 255, int(255 * p)), anchor="mm")
        return out.convert("RGB")

    def frame(self, t):
        if t < GHOST_START:
            img = self.before(t)
        elif t < GHOST_END:
            # double-exposure dissolve, products still swarming
            img = Image.blend(self.before(t), self.after(t), ease_in_out((t - GHOST_START) / (GHOST_END - GHOST_START)))
        else:
            img = self.after(t)
        badge = clamp((t - 0.6) / 0.4) * (1 - clamp((t - END_START) / 0.3))
        img = self.corner_badge(img, badge)
        return self.end_card(img, t)


def render(out_path, music=None):
    reel = GlamReel()
    n_frames = round(TOTAL * FPS)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    cmd = ["ffmpeg", "-y", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-"]
    if music:
        cmd += ["-i", music]
    else:
        cmd += ["-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100"]
    afilter = f"afade=t=out:st={TOTAL - 1.0:.2f}:d=1.0" if music else "anull"
    cmd += ["-map", "0:v", "-map", "1:a", "-af", afilter, "-t", f"{TOTAL:.3f}",
            "-c:v", "libx264", "-preset", "slow", "-crf", "18", "-pix_fmt", "yuv420p",
            "-profile:v", "high", "-c:a", "aac", "-b:a", "192k",
            "-movflags", "+faststart", out_path]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for i in range(n_frames):
        t = i / FPS
        img = reel.frame(t)
        if i == round(2.5 * FPS):
            img.save(os.path.splitext(out_path)[0] + "_cover.jpg", quality=92)
        proc.stdin.write(img.tobytes())
    proc.stdin.close()
    if proc.wait() != 0:
        raise SystemExit("ffmpeg failed")
    print(f"wrote {out_path} ({TOTAL:.1f}s, {n_frames} frames)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--music", help="optional audio track to lay under the reel")
    ap.add_argument("--out", default=os.path.join(OUT_DIR, "blushedbrowed_glam_reel.mp4"))
    args = ap.parse_args()
    render(args.out, args.music)
