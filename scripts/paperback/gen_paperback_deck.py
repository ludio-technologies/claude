#!/usr/bin/env python3
"""Generate Grapheme letter-tile card images (square) + paperback_cards.json.

Tiles are COLOR-CODED BY POINT VALUE so letters are easy to tell apart at a glance
(beyond the glyph itself). Each card's single `rank` doubles as its letter VALUE
(score when played) and its PRICE (cost to buy). Multigraph tiles ("TH", "ING") are
one column but spell multiple letters; the engine concatenates the `letter` field for
the dictionary check. Composition is intentionally easy to retune here.
"""
import os, json
from PIL import Image, ImageDraw, ImageFont

OUT = "/tmp/paperback_cards"
os.makedirs(OUT, exist_ok=True)
SERIF = "/System/Library/Fonts/Supplemental/Georgia Bold.ttf"
if not os.path.exists(SERIF):
    SERIF = "/System/Library/Fonts/Supplemental/Times New Roman Bold.ttf"
SANS = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
CLOUD = "https://res.cloudinary.com/liars-club/image/upload/images/grapheme"

S = 500  # square
INK     = (54, 38, 22)
BORDER  = (107, 74, 43)
VALUEBG = (74, 52, 30)

# background tint per point value — light enough that the dark ink stays readable
VALUE_COLORS = {
    1:  (244, 232, 208),   # cream
    2:  (206, 232, 208),   # mint
    3:  (203, 224, 244),   # sky blue
    4:  (224, 212, 240),   # lavender
    5:  (247, 220, 192),   # peach
    6:  (200, 232, 228),   # aqua
    7:  (244, 212, 222),   # rose
    8:  (245, 205, 194),   # coral
    10: (240, 220, 150),   # gold
    11: (236, 200, 128),   # deep gold
}
def fill_for(v): return VALUE_COLORS.get(v, (244, 232, 208))
def darker(c, f=0.82): return tuple(int(x * f) for x in c)

def font(path, sz): return ImageFont.truetype(path, sz)

def fit_font(path, text, max_w, start=300, min_sz=90):
    sz = start
    while sz > min_sz:
        f = font(path, sz)
        b = f.getbbox(text)
        if (b[2]-b[0]) <= max_w:
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
    p = f"{OUT}/{name}.png"; img.save(p); return p

def done_tile():
    img, d = base_tile((214, 234, 210))
    green = (40, 110, 54)
    f = font(SANS, 96)
    b = f.getbbox("DONE")
    d.text(((S-(b[2]-b[0]))/2 - b[0], 130), "DONE", font=f, fill=green)
    d.line([(178, 330), (232, 388), (338, 268)], fill=green, width=28, joint="curve")
    img.save(f"{OUT}/done.png")

def overflow_tile():
    # plain tile; runtime createCard overlays the concatenated overflow letters as its label
    img, d = base_tile((236, 224, 200))
    img.save(f"{OUT}/overflow_bg.png")

# ── letter POINT VALUES (rank = score = price), Scrabble-style (rarer letter = pricier) ───
VAL = {"a":1,"b":3,"c":3,"d":2,"e":1,"f":4,"g":2,"h":4,"i":1,"j":8,"k":5,"l":1,
       "m":3,"n":1,"o":1,"p":3,"q":10,"r":1,"s":1,"t":1,"u":1,"v":4,"w":4,"x":8,
       "y":4,"z":10}
# multigraph tiles (one column, spell 2-3 letters). value ≈ letters × ~2 + premium.
MULTI = {"th":5,"er":4,"in":4,"re":4,"an":4,"st":4,"en":4,"ed":4,"ou":4,"ch":6,"nd":5,"ar":4,
         "ing":10,"ion":6,"ent":6,"ter":6,"est":6,"the":6,"and":6,"ate":6,"qu":5}

# ── market pile COMPOSITION: only 2-3 copies of each unique tile, so a shuffled pile can't
# produce long runs of the same letter. The game REFILLS a pile (re-imports the set + shuffles)
# whenever it empties, so absolute counts stay small; frequency is expressed as 3 (more useful)
# vs 2 (harder to use, e.g. U among the vowels).
# All tiles are UNIQUE (1 copy) except vowels (2 of a/e/i/o, 1 of the harder-to-use u). Piles are
# tiny — they REFILL the instant a purchase empties one — so this maximizes tile variety.
PILES = {
    "vowels":   {"a":1, "e":3, "i":2, "o":2, "u":1},   # extra E, only 1 A (players get a free A each turn)
    "common":   {"t":2, "s":3, "n":1, "r":1, "d":1, "l":1, "h":1},   # extra S(x2), T
    "uncommon": {c: 1 for c in ["c", "m", "g", "w", "f", "y", "p", "b"]},
    "rare":     {c: 1 for c in ["v", "k", "j", "x", "q", "z"]},
    "digraph":  {c: 1 for c in ["th", "er", "in", "re", "st", "an", "en", "ed", "ou", "ch", "nd", "ar"]},
    "big":      {c: 1 for c in ["ing", "the", "and", "ion", "ent", "ter", "est", "ate", "qu"]},
}
STARTER = ["l", "s", "n", "t", "r", "a", "e", "o"]  # unused now (players buy their own start)

# ── build cards + images ─────────────────────────────────────────────────────
cards = []
alpha_idx = {c: i for i, c in enumerate("abcdefghijklmnopqrstuvwxyz")}
def add_card(name, letter, value, weight):
    label = letter.upper()
    letter_tile(name, label, value)
    cards.append({"name": name, "image": f"{CLOUD}/{name}.png", "label": label,
                  "letter": letter, "rank": value, "type": "tile", "weight": weight})

for c, v in VAL.items():
    add_card(c, c, v, alpha_idx[c])
for i, (mg, v) in enumerate(MULTI.items()):
    add_card(mg, mg, v, 100 + i)

done_tile(); overflow_tile()
# DONE is a real card with its own image (shown in the widget, clicked to finish buying)
cards.append({"name": "done", "image": f"{CLOUD}/done.png", "label": "Done", "type": "ui", "rank": 0, "weight": 999})

sets = {"start": {c: 1 for c in STARTER}, "done": {"done": 1},
        "free_a": {"a": 12}}   # pool of free A's — one loaned to each player every turn, collected back
for pile, comp in PILES.items():
    sets[f"market_{pile}"] = comp

deck = {"name": "grapheme_cards", "cards": cards, "sets": sets}
OUTJSON = "/Users/ankitbuddhiraju/Documents/claude/Code/game_jsons/grapheme_cards.json"
json.dump(deck, open(OUTJSON, "w"), indent=1)

# ── cheatsheet: how many of each tile is in the game, grouped by its market pile ──────────
PILE_LABELS = [("vowels", "Vowels"), ("common", "Common"), ("uncommon", "Uncommon"),
               ("rare", "Rare"), ("digraph", "Digraphs"), ("big", "Big multigrams")]
TS = 92
label_w = 390          # leaves a gap between the longest label ("Big multigrams") and the tiles
row_h = TS + 46
RANK = {**VAL, **MULTI}   # for sorting each row low → high point value
maxtiles = max(len(PILES[k]) for k, _ in PILE_LABELS)
CW = label_w + maxtiles * (TS + 18) + 40
CH = 170 + len(PILE_LABELS) * row_h + 30
cs = Image.new("RGB", (CW, CH), (247, 240, 224))
dd = ImageDraw.Draw(cs)
dd.text((32, 34), "GRAPHEME — Tile Guide", font=font(SERIF, 64), fill=INK)
dd.text((34, 112), "How many of each tile are in each market pile. You're also loaned 1 free A every turn.",
        font=font(SANS, 26), fill=BORDER)
lf, cf = font(SERIF, 36), font(SANS, 26)
y = 172
for key, label in PILE_LABELS:
    dd.text((32, y + TS // 2 - 20), label, font=lf, fill=INK)
    x = label_w
    for name, cnt in sorted(PILES[key].items(), key=lambda kv: RANK[kv[0]]):
        t = Image.open(f"{OUT}/{name}.png").convert("RGBA").resize((TS, TS))
        cs.paste(t, (x, y), t)
        ct = f"x{cnt}"; b = cf.getbbox(ct)
        dd.text((x + TS // 2 - (b[2] - b[0]) // 2, y + TS + 8), ct, font=cf, fill=BORDER)
        x += TS + 18
    y += row_h
cs.save(f"{OUT}/cheatsheet.png")
print("cheatsheet ->", f"{OUT}/cheatsheet.png")

# contact sheet
tiles = sorted([f for f in os.listdir(OUT) if f.endswith(".png") and not f.startswith("_")])
cols = 9; rows = (len(tiles)+cols-1)//cols; tw = 120
sheet = Image.new("RGB", (cols*tw, rows*tw), (250,250,250))
for i, fn in enumerate(tiles):
    im = Image.open(f"{OUT}/{fn}").convert("RGBA").resize((tw-6, tw-6))
    bg = Image.new("RGBA",(tw-6,tw-6),(255,255,255,255)); bg.alpha_composite(im)
    sheet.paste(bg.convert("RGB"), ((i%cols)*tw+3, (i//cols)*tw+3))
sheet.save(f"{OUT}/_contact.png")
print(f"{len(cards)} cards -> {OUTJSON}")
print("sets:", list(sets.keys()))
print("contact:", f"{OUT}/_contact.png")
