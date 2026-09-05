import os, json, urllib.request
from PIL import Image, ImageDraw, ImageFont

W, H = 500, 750
FONT = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
ICONS = "/tmp/pageant_icons"
OUT = "/tmp/pageant_cards"
os.makedirs(ICONS, exist_ok=True)
os.makedirs(OUT, exist_ok=True)

def font(sz): return ImageFont.truetype(FONT, sz)

# color -> (LABEL, openmoji hex, dark, mid, lightbg)  ; one performer per color
COLORS = {
    # (LABEL, openmoji-hex, dark, mid, lightbg). STRONG/saturated backgrounds (not pale) so the
    # 6 hues are clearly distinct — esp. crimson (salmon-RED, low blue) vs rose (PINK, high blue)
    # vs violet (LAVENDER). Big number is drawn in `dark`, still readable on the fill.
    "crimson":  ("CRIMSON",  "1F483", (150, 18, 30),   (222, 50, 60),   (247, 138, 138)),
    "amber":    ("AMBER",    "1F939", (140, 82, 6),    (236, 150, 22),  (250, 194, 108)),
    "emerald":  ("EMERALD",  "1F938", (22, 108, 54),   (50, 168, 88),   (148, 212, 150)),
    "sapphire": ("SAPPHIRE", "1F57A", (20, 88, 172),   (56, 138, 226),  (150, 192, 246)),
    "violet":   ("VIOLET",   "1F9D9", (96, 48, 160),   (150, 100, 206), (200, 164, 242)),
    "rose":     ("ROSE",     "1F478", (188, 40, 112),  (238, 108, 168), (250, 172, 208)),
}
RAW = "https://raw.githubusercontent.com/hfg-gmuend/openmoji/master/color/618x618/{}.png"

def get_icon(hexcode):
    p = f"{ICONS}/{hexcode}.png"
    if not os.path.exists(p):
        urllib.request.urlretrieve(RAW.format(hexcode), p)
    im = Image.open(p).convert("RGBA")
    bbox = im.getbbox()
    return im.crop(bbox) if bbox else im

def fit(icon, box):
    w, h = icon.size
    s = min(box / w, box / h)
    return icon.resize((max(1, int(w*s)), max(1, int(h*s))))

def base_card(dark, mid, lightbg):
    img = Image.new("RGBA", (W, H), (255, 255, 255, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([6, 6, W-6, H-6], radius=38, fill=lightbg, outline=dark, width=10)
    d.rounded_rectangle([26, 26, W-26, H-26], radius=26, outline=mid, width=3)
    return img, d

def banner(img, d, text, dark):
    lf = font(46)
    tb = d.textbbox((0, 0), text, font=lf); tw = tb[2]-tb[0]
    d.rounded_rectangle([(W-tw)//2-26, H-150, (W+tw)//2+26, H-150+70], radius=20, fill=dark)
    d.text(((W-tw)//2, H-150+10), text, font=lf, fill=(255, 255, 255))

def number_card(color, rank):
    label, hexc, dark, mid, lightbg = COLORS[color]
    img, d = base_card(dark, mid, lightbg)
    d.text((W//2, 70), str(rank), font=font(150), fill=dark, anchor="mt")
    icon = fit(get_icon(hexc), 300)
    img.alpha_composite(icon, ((W-icon.width)//2, 300 + (300-icon.height)//2))
    banner(img, d, label, dark)
    p = f"{OUT}/{color}_{rank}.png"; img.save(p); return p

CLOUD = "https://res.cloudinary.com/liars-club/image/upload/images/pageant"
cards, full_set = [], {}
for color in COLORS:
    label = COLORS[color][0].title()
    ci = list(COLORS).index(color)
    for v in range(0, 11):
        number_card(color, v)
        name = f"{color}_{v}"
        cards.append({
            "name": name,
            "image": f"{CLOUD}/{name}.png",
            "label": f"{label} {v}",
            "type": color,
            "color": color,
            "value": v,
            "weight": ci * 11 + v,   # sort hand by color then value (dealDeck sortBy:weight)
        })
        full_set[name] = 1

deck = {"name": "pageant_cards", "cards": cards, "sets": {"full": full_set}}
json.dump(deck, open("/Users/ankitbuddhiraju/Documents/claude/Code/game_jsons/pageant_cards.json", "w"), indent=1)
print(f"generated {len(cards)} cards; deck json -> game_jsons/pageant_cards.json")

# full contact sheet: 6 rows (colors) x 11 cols (values 0-10)
rows, cols = 6, 11; tw, th = 130, 195
sheet = Image.new("RGB", (cols*tw, rows*th), (245,245,245))
for r, color in enumerate(COLORS):
    for v in range(0, 11):
        c = Image.open(f"{OUT}/{color}_{v}.png").convert("RGBA").resize((tw-8, th-8))
        bg = Image.new("RGBA",(tw-8,th-8),(255,255,255,255)); bg.alpha_composite(c)
        sheet.paste(bg.convert("RGB"), (v*tw+4, r*th+4))
sheet.save(f"{OUT}/_deck_all.png")
print("contact:", f"{OUT}/_deck_all.png")
