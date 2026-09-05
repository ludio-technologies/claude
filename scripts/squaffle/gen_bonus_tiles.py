#!/usr/bin/env python3
"""Generate the 2x / 3x bonus-space placeholder tiles for Squaffle's word grid.

Each player's row has one 2x and one 3x slot. Until a word is played there the
slot deck is empty, and an empty deck can show an `emptyImage` in the central
card widget — so these two tiles ARE the bonus markers. They exist because the
deck LABEL (which also carries the multiplier) is prefixed with the player's
name in column 0, and a long name pushes the "2x"/"3x" out of view.

Art matches gen_squaffle_deck.py's tiles: 500px square, rounded rect, wood
border, so an empty bonus slot reads as a tile rather than a hole in the board.

Writes /tmp/squaffle_cards/bonus2x.png + bonus3x.png and uploads both to
Cloudinary (images/squaffle/...), printing the URLs used by squaffle.json.
"""
import os, sys
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, "/Users/ankitbuddhiraju/Documents/claude/Code/scripts/carte_royal_mafia")

OUT = "/tmp/squaffle_cards"
os.makedirs(OUT, exist_ok=True)
SANS = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
FOLDER = "images/squaffle"

S = 500
INK    = (54, 38, 22)
BORDER = (107, 74, 43)
CREAM  = (250, 240, 224)


def font(sz):
    return ImageFont.truetype(SANS, sz)


def darker(c, f=0.82):
    return tuple(int(x * f) for x in c)


def bonus_tile(name, big, fill, ink):
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([8, 8, S - 8, S - 8], radius=44, fill=fill, outline=BORDER, width=12)
    d.rounded_rectangle([30, 30, S - 30, S - 30], radius=30, outline=darker(fill, 0.85), width=3)
    d.text((S // 2, S // 2 - 40), big, font=font(230), fill=ink, anchor="mm")
    d.text((S // 2, S - 132), "WORD", font=font(58), fill=ink, anchor="mm")
    d.text((S // 2, S - 74), "SCORE", font=font(58), fill=ink, anchor="mm")
    p = f"{OUT}/{name}.png"
    img.save(p)
    return p


def main():
    paths = [
        bonus_tile("bonus2x", "2x", (226, 178, 88), INK),      # gold
        bonus_tile("bonus3x", "3x", (176, 66, 58), CREAM),     # brick red
    ]
    if "--no-upload" in sys.argv:
        print("wrote", *paths)
        return
    from upload_crm import upload
    for p in paths:
        pid = os.path.splitext(os.path.basename(p))[0]
        url = upload(open(p, "rb").read(), FOLDER, pid, "png")
        print(pid, "->", url)


if __name__ == "__main__":
    main()
