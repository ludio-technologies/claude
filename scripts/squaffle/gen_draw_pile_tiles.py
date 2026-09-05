#!/usr/bin/env python3
"""Art for the two-pile draw split: the DRAW A CARD action becomes DRAW VOWEL and
DRAW OTHER, so it needs two tiles instead of one.

Deliberately NEW public_ids (act_draw_v / act_draw_c) rather than an overwrite of
act_draw.png — production still serves that URL to the live one-pile game.

Style is copied from gen_squaffle_deck.py's action_tile() so the new tiles sit next
to SWAP/PLAY/DRAW & PLAY without looking bolted on. Blue stays with the "other"
pile (it is the old draw card's colour); the vowel pile gets teal, the one hue not
already spoken for.
"""
import os, sys
from PIL import Image, ImageDraw, ImageFont

OUT = "/tmp/squaffle_cards_split"
os.makedirs(OUT, exist_ok=True)
SANS = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"

S = 500
BORDER = (107, 74, 43)

def darker(c, f=0.85): return tuple(int(x * f) for x in c)
def font(sz): return ImageFont.truetype(SANS, sz)

def fit_font(text, max_w, start=130, min_sz=54):
    sz = start
    while sz > min_sz:
        f = font(sz)
        b = f.getbbox(text)
        if (b[2] - b[0]) <= max_w:
            return f
        sz -= 6
    return font(min_sz)

def base_tile(fill):
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([8, 8, S-8, S-8], radius=44, fill=fill, outline=BORDER, width=12)
    d.rounded_rectangle([30, 30, S-30, S-30], radius=30, outline=darker(fill), width=3)
    return img, d

def action_tile(name, lines, fill, footnote=None):
    img, d = base_tile(fill)
    cream = (250, 240, 224)
    # two big lines, same geometry as the existing action tiles; the footnote (the
    # letters actually in that pile) sits under them so the split is legible on the
    # card face itself and not only in the tutorial.
    dy = -18 if footnote else 0
    for i, line in enumerate(lines):
        f = fit_font(line, max_w=410)
        d.text((S // 2, S // 2 - 74 + i * 148 + dy), line, font=f, fill=cream, anchor="mm")
    if footnote:
        f = fit_font(footnote, max_w=400, start=52, min_sz=30)
        d.text((S // 2, S - 92), footnote, font=f, fill=darker(cream, 0.92), anchor="mm")
    p = f"{OUT}/{name}.png"
    img.save(p)
    print("wrote", p)
    return p

TILES = [
    ("act_draw_v", ["DRAW", "VOWEL"], (38, 132, 146), "A E I O U"),
    ("act_draw_c", ["DRAW", "OTHER"],  (52, 110, 168), "CONSONANT / COMBO"),
]

def main():
    paths = [action_tile(*t) for t in TILES]
    if "--upload" not in sys.argv:
        print("\n(dry run — pass --upload to push to Cloudinary)")
        return
    sys.path.insert(0, "/Users/ankitbuddhiraju/Documents/claude/Code/scripts/carte_royal_mafia")
    from upload_crm import upload
    for p in paths:
        pid = os.path.splitext(os.path.basename(p))[0]
        url = upload(open(p, "rb").read(), "images/squaffle", pid, "png")
        print(pid, "->", url)

if __name__ == "__main__":
    main()
