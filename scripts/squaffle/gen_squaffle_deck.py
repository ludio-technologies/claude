#!/usr/bin/env python3
"""Generate Squaffle letter-tile card images (square) + squaffle_cards.json.

Squaffle is a Quiddler-style word-building card game. Tiles are COLOR-CODED BY
POINT VALUE (cool/light = cheap common letters, warm/gold = pricey rare letters)
so they read at a glance beyond the glyph. Each card's `rank` is its printed point
value (which doubles as +/- scoring). Combo tiles ("TH", "QU", ...) are one card
but spell two letters; the engine concatenates the `letter` field for the
dictionary check, and `size` (letter count) feeds the longest-word bonus.

This script is the SOURCE OF TRUTH for both the art and game_jsons/squaffle_cards.json.
"""
import os, json
from PIL import Image, ImageDraw, ImageFont

OUT = "/tmp/squaffle_cards"
os.makedirs(OUT, exist_ok=True)
SERIF = "/System/Library/Fonts/Supplemental/Georgia Bold.ttf"
if not os.path.exists(SERIF):
    SERIF = "/System/Library/Fonts/Supplemental/Times New Roman Bold.ttf"
SANS = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
CLOUD = "https://res.cloudinary.com/liars-club/image/upload/images/squaffle"

S = 500  # square
INK    = (54, 38, 22)
BORDER = (107, 74, 43)
VALUEBG = (74, 52, 30)

# background tint per point value — cool/light for cheap letters, warm/gold for rare
VALUE_COLORS = {
    2:  (244, 232, 208),   # cream
    3:  (206, 232, 208),   # mint
    4:  (203, 224, 244),   # sky blue
    5:  (224, 212, 240),   # lavender
    6:  (200, 232, 228),   # aqua
    7:  (244, 212, 222),   # rose
    8:  (245, 205, 194),   # coral
    9:  (247, 220, 192),   # peach
    10: (240, 220, 150),   # gold
    11: (236, 200, 128),   # deep gold
    12: (236, 186, 120),   # amber
    13: (240, 178, 120),   # orange
    14: (235, 168, 112),   # burnt orange
    15: (232, 158, 108),   # ember
}
def fill_for(v): return VALUE_COLORS.get(v, (244, 232, 208))
def darker(c, f=0.82): return tuple(int(x * f) for x in c)

def font(path, sz): return ImageFont.truetype(path, sz)

def fit_font(path, text, max_w, start=300, min_sz=90):
    sz = start
    while sz > min_sz:
        f = font(path, sz)
        b = f.getbbox(text)
        if (b[2] - b[0]) <= max_w:
            return f
        sz -= 6
    return font(path, min_sz)

def base_tile(fill):
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([8, 8, S-8, S-8], radius=44, fill=fill, outline=BORDER, width=12)
    d.rounded_rectangle([30, 30, S-30, S-30], radius=30, outline=darker(fill, 0.85), width=3)
    return img, d

def value_badge(d, value):
    r = 52
    cx, cy = S-84, S-84
    d.ellipse([cx-r, cy-r, cx+r, cy+r], fill=VALUEBG)
    vf = font(SANS, 54 if value < 10 else 46)
    t = str(value)
    b = vf.getbbox(t)
    d.text((cx-(b[2]-b[0])/2, cy-(b[3]-b[1])/2-b[1]), t, font=vf, fill=(255, 255, 255))

def letter_tile(name, label, value):
    img, d = base_tile(fill_for(value))
    f = fit_font(SERIF, label, max_w=330)
    b = f.getbbox(label)
    d.text(((S-(b[2]-b[0]))/2 - b[0], (S-(b[3]-b[1]))/2 - b[1] - 24), label, font=f, fill=INK)
    value_badge(d, value)
    img.save(f"{OUT}/{name}.png")

def done_tile():
    img, d = base_tile((214, 234, 210))
    green = (40, 110, 54)
    f = font(SANS, 96)
    b = f.getbbox("DONE")
    d.text(((S-(b[2]-b[0]))/2 - b[0], 130), "DONE", font=f, fill=green)
    d.line([(178, 330), (232, 388), (338, 268)], fill=green, width=28, joint="curve")
    img.save(f"{OUT}/done.png")

def cardback_tile():
    # a proper face-DOWN card back (warm wood-brown tile, cream "S" + wordmark) so the
    # stock/draw pile reads as a card back rather than a random tile face.
    img, d = base_tile((150, 110, 66))
    cream = (238, 226, 200)
    f = font(SERIF, 340)
    b = f.getbbox("?")   # a QUESTION MARK, not "S" — the draw pile is face-down, letter unknown
    d.text(((S - (b[2] - b[0])) / 2 - b[0], (S - (b[3] - b[1])) / 2 - b[1] - 44), "?", font=f, fill=cream)
    wf = font(SANS, 40)
    t = "SQUAFFLE"; wb = wf.getbbox(t)
    d.text(((S - (wb[2] - wb[0])) / 2, S - 96), t, font=wf, fill=cream)
    img.save(f"{OUT}/cardback.png")

def action_tile(name, lines, fill):
    # a clickable action button tile (two lines, centered, auto-fit width) for the widget top row
    img, d = base_tile(fill)
    cream = (250, 240, 224)
    for i, line in enumerate(lines):
        f = fit_font(SANS, line, max_w=410, start=130, min_sz=62)
        cy = S // 2 - 74 + i * 148
        d.text((S // 2, cy), line, font=f, fill=cream, anchor="mm")
    img.save(f"{OUT}/{name}.png")

# ── Squaffle (Quiddler) letter POINT VALUES (rank = printed value) ─────────────
VAL = {"a":2,"b":8,"c":8,"d":5,"e":2,"f":6,"g":6,"h":7,"i":2,"j":13,"k":8,"l":3,
       "m":5,"n":5,"o":2,"p":6,"q":15,"r":5,"s":3,"t":3,"u":4,"v":11,"w":10,"x":12,
       "y":4,"z":14}
# combo tiles (one card, two letters)
COMBO = {"cl":10, "er":7, "in":7, "qu":9, "th":9}
# full-deck composition (118 cards total)
COUNTS = {"a":10,"b":2,"c":2,"d":4,"e":12,"f":2,"g":4,"h":2,"i":8,"j":2,"k":2,"l":4,
          "m":2,"n":6,"o":8,"p":2,"q":2,"r":6,"s":4,"t":6,"u":6,"v":2,"w":2,"x":2,
          "y":4,"z":2,"cl":2,"er":2,"in":2,"qu":2,"th":2}

# ── build cards + images ──────────────────────────────────────────────────────
cards = []
alpha_idx = {c: i for i, c in enumerate("abcdefghijklmnopqrstuvwxyz")}

def add_card(name, letter, value, size, weight):
    label = letter.upper()
    letter_tile(name, label, value)
    cards.append({"name": name, "image": f"{CLOUD}/{name}.png", "label": label,
                  "letter": letter, "rank": value, "size": size, "type": "tile",
                  "weight": weight, "enlargeOnHover": True})

for c, v in VAL.items():
    add_card(c, c, v, 1, alpha_idx[c])
for i, (mg, v) in enumerate(COMBO.items()):
    add_card(mg, mg, v, 2, 100 + i)

done_tile()
cardback_tile()
action_tile("act_draw", ["DRAW", "A CARD"], (52, 110, 168))    # blue
action_tile("act_swap", ["SWAP", "CARDS"], (204, 120, 46))     # orange
action_tile("act_play", ["PLAY", "A WORD"], (54, 128, 66))     # green
action_tile("act_drawplay", ["DRAW &", "PLAY"], (128, 84, 170))  # purple (once per game)
cards.append({"name": "done", "image": f"{CLOUD}/done.png", "label": "Done",
              "type": "ui", "rank": 0, "size": 0, "weight": 999, "enlargeOnHover": True})

sets = {"full": dict(COUNTS), "done": {"done": 1}}
deck = {"name": "squaffle_cards", "cards": cards, "sets": sets}
OUTJSON = "/Users/ankitbuddhiraju/Documents/claude/Code/game_jsons/squaffle_cards.json"
json.dump(deck, open(OUTJSON, "w"), indent=1)

# ── cheatsheet: how many of each tile + its value, grouped by rarity ──────────
GROUPS = [
    ("Vowels", ["a", "e", "i", "o", "u"]),
    ("Common", ["l", "n", "r", "s", "t", "d", "g", "m"]),
    ("Pricey", ["b", "c", "f", "h", "k", "p", "y"]),
    ("Rare",   ["j", "q", "v", "w", "x", "z"]),
    ("Combos", ["cl", "er", "in", "qu", "th"]),
]
RANK = {**VAL, **COMBO}
TS = 92
label_w = 300
row_h = TS + 52
maxtiles = max(len(g) for _, g in GROUPS)
CW = label_w + maxtiles * (TS + 20) + 40
CH = 175 + len(GROUPS) * row_h + 30
cs = Image.new("RGB", (CW, CH), (247, 240, 224))
dd = ImageDraw.Draw(cs)
dd.text((32, 34), "SQUAFFLE — Tile Guide", font=font(SERIF, 64), fill=INK)
dd.text((34, 112), "Point value is on each tile (corner). Count = how many are in the 118-card deck.",
        font=font(SANS, 26), fill=BORDER)
lf, cf = font(SERIF, 38), font(SANS, 26)
y = 178
for label, group in GROUPS:
    dd.text((32, y + TS // 2 - 22), label, font=lf, fill=INK)
    x = label_w
    for name in sorted(group, key=lambda n: RANK[n]):
        t = Image.open(f"{OUT}/{name}.png").convert("RGBA").resize((TS, TS))
        cs.paste(t, (x, y), t)
        ct = f"x{COUNTS[name]}"
        b = cf.getbbox(ct)
        dd.text((x + TS // 2 - (b[2] - b[0]) // 2, y + TS + 8), ct, font=cf, fill=BORDER)
        x += TS + 20
    y += row_h
cs.save(f"{OUT}/cheatsheet.png")

# contact sheet for quick review
tiles = sorted([f for f in os.listdir(OUT) if f.endswith(".png") and not f.startswith("_") and f != "cheatsheet.png"])
cols = 8; rows = (len(tiles) + cols - 1) // cols; tw = 120
sheet = Image.new("RGB", (cols * tw, rows * tw), (250, 250, 250))
for i, fn in enumerate(tiles):
    im = Image.open(f"{OUT}/{fn}").convert("RGBA").resize((tw - 6, tw - 6))
    bg = Image.new("RGBA", (tw - 6, tw - 6), (255, 255, 255, 255)); bg.alpha_composite(im)
    sheet.paste(bg.convert("RGB"), ((i % cols) * tw + 3, (i // cols) * tw + 3))
sheet.save(f"{OUT}/_contact.png")

print(f"{len(cards)} cards -> {OUTJSON}")
print("deck size:", sum(COUNTS.values()))
print("cheatsheet ->", f"{OUT}/cheatsheet.png")
print("contact ->", f"{OUT}/_contact.png")
