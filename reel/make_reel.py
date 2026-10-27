"""Render a 1080x1920 Instagram Reel for Blushed & Browed.

Frames are drawn with Pillow and piped straight into ffmpeg.

    python3 reel/make_reel.py            # writes reel/output/blushedbrowed_reel.mp4
    python3 reel/make_reel.py --music song.mp3
"""
import argparse
import os
import subprocess

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")
OUT_DIR = os.path.join(HERE, "output")

W, H, FPS = 1080, 1920, 30
XFADE = 0.4  # seconds of crossfade between scenes

CREAM = (244, 237, 230)
ESPRESSO = (59, 42, 34)
ROSE = (190, 120, 116)
WHITE = (255, 255, 255)

FONT_DIR_SERIF = "/usr/share/fonts/truetype/crosextra"
FONT_DIR_SANS = "/usr/share/fonts/opentype/inter"


def font(name, size):
    path = os.path.join(FONT_DIR_SERIF if name.startswith("Caladea") else FONT_DIR_SANS, name)
    return ImageFont.truetype(path, size)


SERIF = lambda s: font("Caladea-Regular.ttf", s)
SERIF_IT = lambda s: font("Caladea-Italic.ttf", s)
SANS = lambda s: font("Inter-Light.otf", s)
SANS_MED = lambda s: font("Inter-Medium.otf", s)


# ---------------------------------------------------------------- easing / helpers

def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def ease_out(x):
    x = clamp(x)
    return 1 - (1 - x) ** 3


def fade(t, start, dur=0.5):
    return ease_out((t - start) / dur)


def paper_texture():
    rng = np.random.default_rng(7)
    noise = rng.normal(0, 1, (H // 4, W // 4)).astype(np.float32)
    noise = np.array(Image.fromarray(noise).resize((W, H), Image.BICUBIC))
    base = np.array(CREAM, np.float32)[None, None, :] + noise[..., None] * 3.0
    # soft vignette
    yy, xx = np.mgrid[0:H, 0:W]
    d = np.sqrt(((xx - W / 2) / W) ** 2 + ((yy - H / 2) / H) ** 2)
    base *= (1 - 0.10 * d ** 2)[..., None]
    return Image.fromarray(np.clip(base, 0, 255).astype(np.uint8))


def cover(img, w, h, zoom=1.0, focus=(0.5, 0.5)):
    """Scale img to cover (w, h) with extra zoom, cropping around focus."""
    s = max(w / img.width, h / img.height) * zoom
    rw, rh = round(img.width * s), round(img.height * s)
    big = img.resize((rw, rh), Image.LANCZOS)
    x = clamp(focus[0] * rw - w / 2, 0, rw - w)
    y = clamp(focus[1] * rh - h / 2, 0, rh - h)
    return big.crop((int(x), int(y), int(x) + w, int(y) + h))


def text_layer(draw_fn):
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw_fn(ImageDraw.Draw(layer))
    return layer


def draw_text(d, xy, text, fnt, fill, alpha=1.0, anchor="mm", tracking=0):
    color = fill + (int(255 * clamp(alpha)),)
    if tracking == 0:
        d.text(xy, text, font=fnt, fill=color, anchor=anchor)
        return
    # manual letter spacing, centred on xy
    widths = [d.textlength(c, font=fnt) for c in text]
    total = sum(widths) + tracking * (len(text) - 1)
    x = xy[0] - total / 2
    for c, w in zip(text, widths):
        d.text((x, xy[1]), c, font=fnt, fill=color, anchor="lm")
        x += w + tracking


def overlay(base, layer, alpha=1.0, dy=0):
    if alpha <= 0:
        return base
    if alpha < 1:
        a = layer.getchannel("A").point(lambda v: int(v * alpha))
        layer = layer.copy()
        layer.putalpha(a)
    out = base.convert("RGBA")
    out.alpha_composite(layer, (0, int(dy)))
    return out.convert("RGB")


def with_shadow(card, radius=28, offset=(0, 22), opacity=0.35):
    pad = radius * 3
    sh = Image.new("RGBA", (card.width + pad * 2, card.height + pad * 2), (0, 0, 0, 0))
    mask = Image.new("L", sh.size, 0)
    mask.paste(int(255 * opacity), (pad + offset[0], pad + offset[1],
                                     pad + offset[0] + card.width, pad + offset[1] + card.height))
    mask = mask.filter(ImageFilter.GaussianBlur(radius))
    sh.paste((40, 25, 20, 255), mask=mask)
    sh.putalpha(mask)
    sh.alpha_composite(card.convert("RGBA"), (pad, pad))
    return sh


# ---------------------------------------------------------------- assets

def load_assets():
    portrait = Image.open(os.path.join(ASSETS, "portrait.jpg")).convert("RGB")
    shot = Image.open(os.path.join(ASSETS, "profile_screenshot.png")).convert("RGB")
    # The three pinned posts on the profile grid (screenshot is 1320x2868).
    tiles = {"brows": 0, "intro": 442, "lips": 883}
    cards = {}
    for name, x0 in tiles.items():
        tile = shot.crop((x0, 2036, x0 + 437, 2620))
        if name == "intro":
            box = (60, 78, 386, 584)   # polaroid + "Hi I'm Sima" note, below the pin icon
        else:
            box = (36, 80, 408, 520)   # polaroid card, below the pin icon
        card = tile.crop(box)
        card = card.resize((card.width * 2, card.height * 2), Image.LANCZOS)
        card = card.filter(ImageFilter.UnsharpMask(radius=2, percent=80, threshold=2))
        cards[name] = card
    return portrait, cards


# ---------------------------------------------------------------- scenes

class Hook:
    """Full-bleed portrait with a slow push-in and the hook line."""
    dur = 3.6

    def __init__(self, portrait, bg):
        self.portrait = portrait
        box_w, box_h = 900, 330
        card = Image.new("RGBA", (box_w, box_h), (0, 0, 0, 0))
        ImageDraw.Draw(card).rounded_rectangle((0, 0, box_w - 1, box_h - 1), 40,
                                               fill=CREAM + (240,))
        cd = ImageDraw.Draw(card)
        draw_text(cd, (box_w / 2, 85), "Unpopular opinion…", SERIF_IT(62), ROSE)
        draw_text(cd, (box_w / 2, 175), "your brows shouldn't", SERIF(72), ESPRESSO)
        draw_text(cd, (box_w / 2, 255), "look tattooed.", SERIF(72), ESPRESSO)
        self.card = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        self.card.alpha_composite(with_shadow(card, 24, (0, 14), 0.25),
                                  ((W - box_w) // 2 - 72, 1330 - 72))

    def frame(self, t):
        zoom = 1.0 + 0.07 * (t / self.dur)
        img = cover(self.portrait, W, H, zoom, focus=(0.5, 0.42))
        a = fade(t, 0.35, 0.6)
        return overlay(img, self.card, a, dy=40 * (1 - a))


class Polaroid:
    """A pinned post floating on cream paper with a headline."""
    dur = 3.2

    def __init__(self, bg, card, kicker, title, sub, rot=(-7, -3), width=820, card_y=400):
        self.bg = bg
        s = width / card.width
        self.card = with_shadow(card.resize((width, round(card.height * s)), Image.LANCZOS))
        self.rot = rot
        self.card_y = card_y
        ch = self.card.height
        text_y = card_y + ch - 120

        def draw(d):
            draw_text(d, (W / 2, text_y + 20), kicker, SANS_MED(30), ROSE, tracking=10)
            draw_text(d, (W / 2, text_y + 105), title, SERIF(96), ESPRESSO)
            draw_text(d, (W / 2, text_y + 200), sub, SERIF_IT(60), ESPRESSO)
        self.text = text_layer(draw)

    def frame(self, t):
        p = ease_out(t / 0.9)
        angle = self.rot[0] + (self.rot[1] - self.rot[0]) * p
        scale = 0.92 + 0.08 * p + 0.02 * (t / self.dur)
        c = self.card.resize((round(self.card.width * scale), round(self.card.height * scale)),
                             Image.BICUBIC).rotate(angle, Image.BICUBIC, expand=True)
        img = self.bg.copy().convert("RGBA")
        y = self.card_y - 90 + (1 - p) * 160 - (c.height - self.card.height) / 2
        img.alpha_composite(c, (int((W - c.width) / 2), int(y)))
        img = img.convert("RGB")
        a = fade(t, 0.45, 0.5)
        return overlay(img, self.text, a, dy=30 * (1 - a))


class EndCard:
    dur = 4.4

    def __init__(self, portrait, bg):
        self.bg = bg
        d = 520
        face = cover(portrait, d, d, 2.4, focus=(0.5, 0.40)).convert("RGBA")
        mask = Image.new("L", (d * 4, d * 4), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, d * 4 - 1, d * 4 - 1), fill=255)
        face.putalpha(mask.resize((d, d), Image.LANCZOS))
        ring = Image.new("RGBA", (d + 24, d + 24), (0, 0, 0, 0))
        ImageDraw.Draw(ring).ellipse((0, 0, d + 23, d + 23), outline=ROSE + (255,), width=4)
        ring.alpha_composite(face, (12, 12))
        self.face = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        self.face.alpha_composite(with_shadow(ring, 26, (0, 16), 0.25),
                                  ((W - ring.width) // 2 - 78, 230 - 78))

        def title(dd):
            draw_text(dd, (W / 2, 960), "Blushed.", SERIF(150), ESPRESSO)
            draw_text(dd, (W / 2, 1110), "Browed.", SERIF(150), ESPRESSO)
        self.title = text_layer(title)

        def byline(dd):
            dd.line((200, 1240, 400, 1240), fill=ESPRESSO + (160,), width=2)
            dd.line((680, 1240, 880, 1240), fill=ESPRESSO + (160,), width=2)
            draw_text(dd, (W / 2, 1240), "BY SIMA", SANS_MED(34), ESPRESSO, tracking=10)
            draw_text(dd, (W / 2, 1320), "SOFT. NATURAL. TIMELESS.", SANS(30), ESPRESSO, tracking=8)
        self.byline = text_layer(byline)

        def cta(dd):
            draw_text(dd, (W / 2, 1480), "Brows & lips that heal clean", SERIF_IT(58), ROSE)
            dd.rounded_rectangle((170, 1570, 910, 1690), 60, fill=ESPRESSO + (255,))
            draw_text(dd, (W / 2, 1630), "BOOK · LINK IN BIO", SANS_MED(40), CREAM, tracking=6)
            draw_text(dd, (W / 2, 1760), "@blushedbrowed  ·  Los Angeles", SANS(34), ESPRESSO)
        self.cta = text_layer(cta)

    def frame(self, t):
        img = self.bg.copy()
        a = fade(t, 0.1, 0.7)
        img = overlay(img, self.face, a, dy=30 * (1 - a))
        a = fade(t, 0.5, 0.6)
        img = overlay(img, self.title, a, dy=40 * (1 - a))
        img = overlay(img, self.byline, fade(t, 1.0, 0.6))
        a = fade(t, 1.5, 0.6)
        return overlay(img, self.cta, a, dy=30 * (1 - a))


# ---------------------------------------------------------------- render

def build_scenes():
    portrait, cards = load_assets()
    bg = paper_texture()
    return [
        Hook(portrait, bg),
        Polaroid(bg, cards["brows"], "PMU BROWS", "Ombré Brows", "& brow lamination", rot=(-8, -3)),
        Polaroid(bg, cards["lips"], "PMU LIPS", "Lip Blush", "that heals clean", rot=(7, 3)),
        Polaroid(bg, cards["intro"], "HI, I'M SIMA", "TV host → LA", "brow & lip artist",
                 rot=(-5, -2), width=640, card_y=330),
        EndCard(portrait, bg),
    ]


def timeline(scenes):
    starts, t = [], 0.0
    for s in scenes:
        starts.append(t)
        t += s.dur - XFADE
    return starts, t + XFADE


def render(out_path, music=None):
    scenes = build_scenes()
    starts, total = timeline(scenes)
    n_frames = round(total * FPS)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    cmd = ["ffmpeg", "-y", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-"]
    if music:
        cmd += ["-i", music]
    else:
        cmd += ["-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100"]
    afilter = f"afade=t=out:st={total - 1.2:.2f}:d=1.2" if music else "anull"
    cmd += ["-map", "0:v", "-map", "1:a", "-af", afilter, "-t", f"{total:.3f}",
            "-c:v", "libx264", "-preset", "slow", "-crf", "18", "-pix_fmt", "yuv420p",
            "-profile:v", "high", "-c:a", "aac", "-b:a", "192k",
            "-movflags", "+faststart", out_path]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)

    cover_frame = None
    for i in range(n_frames):
        t = i / FPS
        active = [k for k, s in enumerate(starts) if s <= t < s + scenes[k].dur]
        k = active[-1]
        img = scenes[k].frame(t - starts[k])
        if len(active) > 1:  # crossfade from the previous scene
            j = active[0]
            prev = scenes[j].frame(t - starts[j])
            img = Image.blend(prev, img, ease_out((t - starts[k]) / XFADE))
        if abs(t - 1.5) < 1 / FPS / 2:
            cover_frame = img
        proc.stdin.write(img.tobytes())
    proc.stdin.close()
    if proc.wait() != 0:
        raise SystemExit("ffmpeg failed")
    if cover_frame is not None:
        cover_frame.save(os.path.splitext(out_path)[0] + "_cover.jpg", quality=92)
    print(f"wrote {out_path} ({total:.1f}s, {n_frames} frames)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--music", help="optional audio track to lay under the reel")
    ap.add_argument("--out", default=os.path.join(OUT_DIR, "blushedbrowed_reel.mp4"))
    args = ap.parse_args()
    render(args.out, args.music)
