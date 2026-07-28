"""Regenerate Carte Royal Mafia card images.

Changes vs the original set:
  - Larger fonts across every card (badges, center number, suit label, names, descriptions).
  - Numbered cards: drop the redundant "Value: N" label; just show the N scoring icons.
  - Zero-value numbered cards: a muted suit glyph with a slash (clearly "scores 0").
Everything else (palette + icons) is preserved: icons are the exact glyphs extracted
from the original card images.
"""
import json, os, textwrap
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
CARDS = json.load(open(os.path.join(HERE, '..', '..', 'game_jsons', 'carte_royal_mafia_cards.json')))['cards']
SPR = os.path.join(HERE, "sprites")   # icon glyphs extracted from the original card art
OUT = "/tmp/crm_cards_new"
os.makedirs(OUT, exist_ok=True)

W, H = 400, 600
OUTER_BG = (20, 28, 56)
PANEL_BG = (32, 42, 75)
BORDER   = (60, 74, 122)
PANEL_BORDER = (74, 90, 140)
BADGE_TEXT = (18, 24, 48)
MUTED = (90, 105, 150)   # #5a6996 — the game's "absent/zero" colour

SUIT_COLOR = {"gold": (242, 184, 50), "townsperson": (170, 195, 235)}
SUIT_LABEL = {"gold": "Gold", "townsperson": "Townsperson"}
SUIT_SPRITE = {"gold": "coin", "townsperson": "head"}

# Special-card metadata: role -> (badge text, name, sprite, color, description)
SPECIALS = {
    "dagger": ("0", "Dagger", "dagger", (120, 224, 205),
        "A TRUMP 0. If a Mafia player captures this card, their Townsperson score is halved."),
    "mafia": ("16 | +1", "The Mafia", "mafia", (214, 72, 72),
        "If led: a TRUMP 16. Otherwise: same suit as the previous card played, with rank +1. "
        "If a Townsperson or Warlock captures this card, their Gold score is halved."),
    "warlock": ("16", "The Warlock", "warlock", (178, 120, 214),
        "A 16 of the LEADING suit. Holding this card (without any Mafia card) makes you the "
        "Warlock — you score Gold like a Townsperson but you are on the Mafia team."),
    "police": ("16 | 0", "Police Officer", "lantern", (120, 175, 225),
        "A TRUMP 16 if no Mafia card is played to the same trick. Otherwise, a 0 of the LEADING suit."),
}

FONT = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
def font(sz): return ImageFont.truetype(FONT, sz)

def rounded(draw, box, r, fill=None, outline=None, width=1):
    draw.rounded_rectangle(box, radius=r, fill=fill, outline=outline, width=width)

def text_wh(draw, s, f):
    b = draw.textbbox((0, 0), s, font=f)
    return b[2]-b[0], b[3]-b[1]

def fit_font(draw, s, max_w, start, floor=14):
    sz = start
    while sz > floor:
        f = font(sz)
        if text_wh(draw, s, f)[0] <= max_w:
            return f
        sz -= 2
    return font(floor)

def tint(sprite, color):
    """Return sprite recolored to `color`, keeping its alpha."""
    r, g, b, a = sprite.split()
    solid = Image.new("RGBA", sprite.size, color + (255,))
    solid.putalpha(a)
    return solid

def draw_center_text(draw, cx, y, s, f, fill):
    w, h = text_wh(draw, s, f)
    b = draw.textbbox((0, 0), s, font=f)
    draw.text((cx - w/2 - b[0], y - b[1]), s, font=f, fill=fill)
    return h

def wrap_pixels(draw, s, f, max_w):
    words = s.split()
    lines, cur = [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if text_wh(draw, trial, f)[0] <= max_w:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines

def fit_desc(draw, desc, panel_w, panel_h):
    for sz in range(31, 16, -1):
        f = font(sz)
        lines = wrap_pixels(draw, desc, f, panel_w)
        lh = text_wh(draw, "Ag", f)[1] + 8
        if len(lines) * lh <= panel_h:
            return f, lines, lh
    f = font(17)
    return f, wrap_pixels(draw, desc, f, panel_w), text_wh(draw, "Ag", f)[1] + 8

def badge(img, draw, cx, cy, txt, color):
    f = fit_font(draw, txt, 96, 40)
    tw, th = text_wh(draw, txt, f)
    bw, bh = max(tw + 34, 60), 58
    box = [cx - bw/2, cy - bh/2, cx + bw/2, cy + bh/2]
    rounded(draw, box, 12, fill=color)
    b = draw.textbbox((0, 0), txt, font=f)
    draw.text((cx - tw/2 - b[0], cy - th/2 - b[1]), txt, font=f, fill=BADGE_TEXT)
    return bh

def base_card():
    img = Image.new("RGBA", (W, H), OUTER_BG + (255,))
    d = ImageDraw.Draw(img)
    rounded(d, [6, 6, W-7, H-7], 22, outline=BORDER, width=3)
    return img, d

def render_numbered(card):
    suit = card["suit"]; rank = card["rank"]; val = card["icons"]
    color = SUIT_COLOR[suit]
    img, d = base_card()
    # corner badges + mini suit icon
    spr = Image.open(f"{SPR}/{SUIT_SPRITE[suit]}.png").convert("RGBA")
    mini = spr.resize((34, int(34*spr.height/spr.width)))
    for cx in (66, W-66):
        badge(img, d, cx, 52, str(rank), color)
        img.alpha_composite(mini, (cx - mini.width//2, 86))
    # big center number
    fnum = font(215)
    draw_center_text(d, W/2, 150, str(rank), fnum, color)
    # suit label
    draw_center_text(d, W/2, 356, SUIT_LABEL[suit], font(46), color)
    # bottom value panel
    panel = [30, 410, W-30, H-32]
    rounded(d, panel, 18, fill=PANEL_BG, outline=PANEL_BORDER, width=2)
    pcx, pcy = W/2, (410 + H-32)/2
    if val > 0:
        icon = spr.resize((66, int(66*spr.height/spr.width)))
        gap = 12
        total = val*icon.width + (val-1)*gap
        x0 = pcx - total/2
        for i in range(val):
            img.alpha_composite(icon, (int(x0 + i*(icon.width+gap)), int(pcy - icon.height/2)))
    else:
        # zero-value symbol: greyed suit glyph inside a "no / prohibition" ring+slash
        ICON = (120, 136, 178)
        RING = (150, 165, 205)
        glyph = tint(spr, ICON).resize((70, int(70*spr.height/spr.width)))
        img.alpha_composite(glyph, (int(pcx - glyph.width/2), int(pcy - glyph.height/2)))
        r = 56
        d.ellipse([pcx-r, pcy-r, pcx+r, pcy+r], outline=RING + (255,), width=8)
        off = r/(2**0.5)
        d.line([(pcx-off, pcy+off), (pcx+off, pcy-off)], fill=RING + (255,), width=10)
    return img

def render_special(card):
    badge_txt, name, sprite, color, desc = SPECIALS[card["role"]]
    img, d = base_card()
    for cx in (72, W-72):
        badge(img, d, cx, 52, badge_txt, color)
    # big center icon
    spr = Image.open(f"{SPR}/{sprite}.png").convert("RGBA")
    maxw, maxh = 190, 190
    sc = min(maxw/spr.width, maxh/spr.height)
    spr2 = tint(spr, color).resize((int(spr.width*sc), int(spr.height*sc)))
    img.alpha_composite(spr2, (int(W/2 - spr2.width/2), int(210 - spr2.height/2)))
    # name
    draw_center_text(d, W/2, 322, name, font(46), color)
    # description panel
    panel = [26, 392, W-26, H-30]
    rounded(d, panel, 18, fill=PANEL_BG, outline=PANEL_BORDER, width=2)
    pw = (panel[2]-panel[0]) - 34
    ph = (panel[3]-panel[1]) - 26
    fdesc, lines, lh = fit_desc(d, desc, pw, ph)
    ty = (panel[1] + panel[3])/2 - (len(lines)*lh)/2
    for ln in lines:
        draw_center_text(d, W/2, ty, ln, fdesc, (235, 240, 250))
        ty += lh
    return img

def main():
    for card in CARDS:
        if card["suit"] == "special":
            img = render_special(card)
        else:
            img = render_numbered(card)
        img.convert("RGB").save(f"{OUT}/{card['name']}.png")
    print(f"rendered {len(CARDS)} cards to {OUT}")

if __name__ == "__main__":
    main()
