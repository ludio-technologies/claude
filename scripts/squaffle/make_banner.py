#!/usr/bin/env python3
"""Squaffle banner (square 1080) + wallpaper (1600x900). Composes the actual letter
tiles spelling SQUAFFLE on a warm parchment/wood field. Run with /usr/bin/python3
(system Pillow). Regen tiles first via gen_squaffle_deck.py."""
import os
from PIL import Image, ImageDraw, ImageFont, ImageFilter

TILES = "/tmp/squaffle_cards"
OUT = "/tmp/squaffle_art"
os.makedirs(OUT, exist_ok=True)
SERIF = "/System/Library/Fonts/Supplemental/Georgia Bold.ttf"
SANS = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
PARCH = (232, 220, 192)
INK = (58, 44, 26)
BORDER = (122, 90, 52)

def font(p, s): return ImageFont.truetype(p, s)

def parchment(w, h):
    img = Image.new("RGB", (w, h), PARCH)
    d = ImageDraw.Draw(img)
    # faint vignette
    for i in range(60):
        a = int(40 * (i / 60))
        d.rectangle([i, i, w - i, h - i], outline=(122 - 30, 90 - 20, 52 - 10, a))
    return img.filter(ImageFilter.GaussianBlur(0.5))

def tile_row(letters, tile_px, gap):
    ims = [Image.open(f"{TILES}/{n}.png").convert("RGBA").resize((tile_px, tile_px)) for n in letters]
    w = len(ims) * tile_px + (len(ims) - 1) * gap
    strip = Image.new("RGBA", (w, tile_px), (0, 0, 0, 0))
    x = 0
    for im in ims:
        strip.alpha_composite(im, (x, 0))
        x += tile_px + gap
    return strip

# ── Banner (square 1080) — two rows SQUA / FFLE + title ──
W = 1080
banner = parchment(W, W).convert("RGBA")
d = ImageDraw.Draw(banner)
tp, gap = 210, 16
r1 = tile_row(list("squa"), tp, gap)
r2 = tile_row(list("ffle"), tp, gap)
banner.alpha_composite(r1, ((W - r1.width) // 2, 200))
banner.alpha_composite(r2, ((W - r2.width) // 2, 200 + tp + gap))
tf = font(SANS, 60)
tag = "Spell. Score. Go out."
b = tf.getbbox(tag)
d.text(((W - (b[2] - b[0])) // 2, 760), tag, font=tf, fill=BORDER)
banner.convert("RGB").save(f"{OUT}/banner.png")

# ── Wallpaper (1600x900) — understated parchment, faint oversized tiles ──
WW, WH = 1600, 900
wall = parchment(WW, WH).convert("RGBA")
faint = tile_row(list("squaffle"), 150, 20)
faint = faint.resize((int(faint.width * 1.1), int(faint.height * 1.1)))
ov = Image.new("RGBA", wall.size, (0, 0, 0, 0))
ov.alpha_composite(faint, ((WW - faint.width) // 2, (WH - faint.height) // 2))
ov.putalpha(ov.getchannel("A").point(lambda a: int(a * 0.10)))
wall.alpha_composite(ov)
wall.convert("RGB").save(f"{OUT}/wallpaper.jpg", quality=88)

print("banner ->", f"{OUT}/banner.png")
print("wallpaper ->", f"{OUT}/wallpaper.jpg")
