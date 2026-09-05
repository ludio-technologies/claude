#!/usr/bin/env python3
"""One generated tutorial image: the COLLECTION rule. A row of 4 cards — the last is the card
just played (green); of the 3 before it, 2 are collected (yellow, arrow out) — one by color
match (higher number), one by value ≤ the played number — and 1 stays. No text.
(Other tutorial slides just reuse existing card images.) Uploads to images/pageant/tut_collect."""
import os, sys
from PIL import Image, ImageDraw, ImageFilter
sys.path.insert(0, "/Users/ankitbuddhiraju/Documents/claude/Code/scripts/carte_royal_mafia")
from upload_crm import upload

CARDS = "/tmp/pageant_cards"
OUT = "/tmp/pageant_tut"
os.makedirs(OUT, exist_ok=True)

# Rule-accurate: play Emerald 1 (N=1). Safe window = the 1 card just before it (Sapphire 9).
# The two older candidates are swept: Emerald 6 (color match, higher) and Crimson 1 (value ≤ 1).
ROW = [("emerald_6", "collect"), ("crimson_1", "collect"), ("sapphire_9", "stay"), ("emerald_1", "played")]
CH = 300
W = 4 * CH * 5 // 7 + 5 * 40 + 40
H = 480
img = Image.new("RGBA", (W, H), (26, 15, 34, 255))

def glow(color, box, blur=26, grow=16):
    lay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    x0, y0, x1, y1 = box
    ImageDraw.Draw(lay).rounded_rectangle([x0-grow, y0-grow, x1+grow, y1+grow], radius=34, fill=color)
    return lay.filter(ImageFilter.GaussianBlur(blur))

def card(name):
    im = Image.open(f"{CARDS}/{name}.png").convert("RGBA")
    r = CH / im.height
    return im.resize((int(im.width * r), CH), Image.LANCZOS)

x = 40
positions = []
for name, kind in ROW:
    c = card(name)
    y = 70 if kind != "collect" else 40   # lift the collected cards up slightly
    positions.append((name, kind, x, y, c.width))
    x += c.width + 40

# glows behind cards
for name, kind, x, y, w in positions:
    if kind == "collect":
        img.alpha_composite(glow((255, 214, 60, 200), (x, y, x+w, y+CH)))   # yellow
    elif kind == "played":
        img.alpha_composite(glow((90, 230, 130, 210), (x, y, x+w, y+CH)))   # green
# cards on top
for name, kind, x, y, w in positions:
    img.alpha_composite(card(name), (x, y))
    d = ImageDraw.Draw(img)
    if kind == "collect":      # downward arrow = swept into your troupe
        cx = x + w // 2
        ay = y + CH + 24
        d.polygon([(cx-26, ay), (cx+26, ay), (cx, ay+42)], fill=(255, 214, 60))
        d.rectangle([cx-11, ay-40, cx+11, ay], fill=(255, 214, 60))

img.convert("RGB").save(f"{OUT}/tut_collect.png")
print("collect ->", upload(open(f"{OUT}/tut_collect.png", "rb").read(), "images/pageant", "tut_collect", "png"))
img.convert("RGB").resize((W//2, H//2)).save(f"{OUT}/_collect_preview.png")
