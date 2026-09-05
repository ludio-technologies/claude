#!/usr/bin/env python3
"""The card face style shared by both Rainbow Blackjack decks.

A card is a near-black field inside a thick band of an accent colour, with one
big mark in that same colour and an optional caption strip beneath it. The
colour is doing real work: spotting a duplicate across the table is the whole
game, so every card has to be identifiable at thumbnail size.

Numbers use one hue wheel divided into 13, so a 5 is the same green in both
decks and only the 13 is unique to Naughty. Accents carry meaning rather than
decoration — Nice modifiers are green because they add, Naughty modifiers are
red because they take away.
"""
import colorsys
import os
import sys

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rb_cards  # noqa: E402

# Matches the deck the game shipped with, and the widget's 0.77 ratio.
W, H = 1700, 2200
SS = 2                      # supersample, then downsample for clean diagonals

# Phosphate Solid: heavy enough to hold up at pick-widget size, condensed enough
# that "13" fits at the same size as "1" (so every numeral shares a cap height),
# and with far more personality than a plain grotesque. Covers ÷ and − properly,
# which most display faces do not.
DISPLAY = "/System/Library/Fonts/Supplemental/Phosphate.ttc"
DISPLAY_IDX = 1

INK = (14, 12, 18)          # the near-black card field
RED = (255, 59, 48)         # takes points away
GREEN = (54, 214, 122)      # gives points
VIOLET = (176, 128, 255)    # the forced-draw pair, Hit 3 and Hit 4
AMBER = (255, 176, 32)
ROSE = (255, 111, 168)
CYAN = (64, 200, 255)
MAGENTA = (240, 84, 200)
JADE = (64, 220, 120)

# Every card puts its main mark's ink centre on this line, so numbers do not
# appear to drift as you scan a row of them.
MARK_Y = 1040
CAPTION_Y = 1900

CAPTION_WORDS = ["PENALTY", "BONUS", "THE ZERO", "UNLUCKY", "LUCKY"]
ALPHA = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def lift(rgb, floor=0.42):
    """Blend towards white until the colour is bright enough to read on black.

    A fully saturated blue carries about a fifth of the perceived luminance of a
    fully saturated yellow, so the raw hue wheel puts 9 and 10 almost into the
    card's background. Lifting by luminance keeps every number equally findable
    without touching its hue.
    """
    r, g, b = [c / 255.0 for c in rgb]
    lum = 0.2126 * r + 0.7152 * g + 0.0722 * b
    if lum >= floor:
        return rgb
    t = (floor - lum) / (1.0 - lum)
    return tuple(int(round(255 * (c + (1.0 - c) * t))) for c in (r, g, b))


def number_hue(value):
    """0 keeps the original deck's white; 1-13 walk one 13-step wheel."""
    if value == 0:
        return (255, 255, 255)
    r, g, b = colorsys.hsv_to_rgb(((value - 1) / 13.0) % 1.0, 1.0, 1.0)
    return lift((int(r * 255), int(g * 255), int(b * 255)))


# ── type ────────────────────────────────────────────────────────────────────
def font(size):
    return ImageFont.truetype(DISPLAY, size, index=DISPLAY_IDX)


def family_font(labels, max_w, max_h, start=4200):
    """Largest size at which *every* label in the family fits.

    One size for the whole family is the point: it is what gives 1 and 13 the
    same cap height, instead of each number being shrunk to taste.
    """
    size = start
    while size > 20:
        f = font(size)
        if all((f.getbbox(s)[2] - f.getbbox(s)[0]) <= max_w
               and (f.getbbox(s)[3] - f.getbbox(s)[1]) <= max_h for s in labels):
            return f
        size -= 10
    return font(20)


def ink_centre(d, f, ref="0123456789"):
    """Vertical centre of the font's ink for a reference string.

    Centring each label on its own ink box would let a flat-topped 1 and a
    round-topped 0 land at different heights. Measuring one reference and
    reusing it puts every label on the same baseline.
    """
    b = d.textbbox((0, 0), ref, font=f, anchor="lt")
    return (b[1] + b[3]) / 2.0


def text_at(d, cx, cy, s, f, fill, ref_cy):
    """Draw `s` centred horizontally on cx, sitting on the family baseline."""
    b = d.textbbox((0, 0), s, font=f, anchor="lt")
    d.text((cx - (b[0] + b[2]) / 2.0, cy - ref_cy), s, font=f, fill=fill, anchor="lt")


# ── card chrome ─────────────────────────────────────────────────────────────
def blank():
    im = Image.new("RGB", (W * SS, H * SS), INK)
    return im, ImageDraw.Draw(im)


def frame(d, colour, band=86, radius=54):
    b, r = band * SS, radius * SS
    d.rounded_rectangle([0, 0, W * SS - 1, H * SS - 1], radius=r, fill=colour)
    d.rounded_rectangle([b, b, W * SS - 1 - b, H * SS - 1 - b],
                        radius=max(r - b // 2, 8), fill=INK)


def caption(d, text, colour):
    f = family_font(CAPTION_WORDS, 1200 * SS, 130 * SS, start=400)
    text_at(d, W * SS // 2, CAPTION_Y * SS, " ".join(text), f, colour,
            ink_centre(d, f, ALPHA))


def downsample(im):
    return im.resize((W, H), Image.LANCZOS)


# ── icons ───────────────────────────────────────────────────────────────────
def icon_hit(n):
    """n cards in a row, the last one turned face up."""
    def draw(d, cx, cy, c):
        s = SS
        span = 260 * s
        start = -(n - 1) / 2.0
        for i in range(n):
            dx = (start + i) * span
            top = cy - 300 * s + abs(i - (n - 1) / 2.0) * 46 * s
            box = [cx + dx - 118 * s, top, cx + dx + 118 * s, top + 580 * s]
            if i == n - 1:
                d.rounded_rectangle(box, radius=30 * s, fill=c)
            else:
                d.rounded_rectangle(box, radius=30 * s, outline=c, width=32 * s)
    return draw


def icon_one_more(d, cx, cy, c):
    """One card dropping onto a pile."""
    s = SS
    d.rounded_rectangle([cx - 340 * s, cy + 120 * s, cx + 340 * s, cy + 400 * s],
                        radius=40 * s, fill=c)
    d.line([cx, cy - 400 * s, cx, cy - 90 * s], fill=c, width=60 * s)
    d.polygon([(cx - 200 * s, cy - 120 * s), (cx + 200 * s, cy - 120 * s),
               (cx, cy + 60 * s)], fill=c)


def icon_stop(d, cx, cy, c):
    """An octagon with a bar through it."""
    s = SS
    import math
    r = 380 * s
    pts = [(cx + r * math.cos(math.radians(a + 22.5)),
            cy + r * math.sin(math.radians(a + 22.5))) for a in range(0, 360, 45)]
    d.polygon(pts, outline=c, width=40 * s)
    d.line([cx - 210 * s, cy, cx + 210 * s, cy], fill=c, width=64 * s)


def icon_heart(d, cx, cy, c):
    """A heart, for the card that saves you once."""
    s = SS
    r = 190 * s
    d.ellipse([cx - 2 * r, cy - 250 * s, cx, cy - 250 * s + 2 * r], fill=c)
    d.ellipse([cx, cy - 250 * s, cx + 2 * r, cy - 250 * s + 2 * r], fill=c)
    d.polygon([(cx - 2 * r + 6 * s, cy - 250 * s + r),
               (cx + 2 * r - 6 * s, cy - 250 * s + r),
               (cx, cy + 330 * s)], fill=c)


def icon_steal(d, cx, cy, c):
    """A card leaving one pile for another."""
    s = SS
    d.rounded_rectangle([cx - 560 * s, cy - 260 * s, cx - 250 * s, cy + 260 * s],
                        radius=34 * s, outline=c, width=32 * s)
    d.rounded_rectangle([cx + 250 * s, cy - 260 * s, cx + 560 * s, cy + 260 * s],
                        radius=34 * s, fill=c)
    d.line([cx - 180 * s, cy, cx + 110 * s, cy], fill=c, width=46 * s)
    d.polygon([(cx + 60 * s, cy - 130 * s), (cx + 60 * s, cy + 130 * s),
               (cx + 215 * s, cy)], fill=c)


def icon_swap(d, cx, cy, c):
    """Two arrows trading places."""
    s = SS
    for sign in (-1, 1):
        y = cy + sign * 190 * s
        x0, x1 = cx - 430 * s, cx + 430 * s
        d.line([x0, y, x1, y], fill=c, width=46 * s)
        head = 150 * s
        if sign < 0:
            d.polygon([(x1 - head, y - head), (x1 - head, y + head),
                       (x1 + 40 * s, y)], fill=c)
        else:
            d.polygon([(x0 + head, y - head), (x0 + head, y + head),
                       (x0 - 40 * s, y)], fill=c)


def icon_discard(d, cx, cy, c):
    """A card struck out."""
    s = SS
    d.rounded_rectangle([cx - 300 * s, cy - 380 * s, cx + 300 * s, cy + 380 * s],
                        radius=40 * s, outline=c, width=34 * s)
    for a, b in (((-170, -250), (170, 250)), ((170, -250), (-170, 250))):
        d.line([cx + a[0] * s, cy + a[1] * s, cx + b[0] * s, cy + b[1] * s],
               fill=c, width=52 * s)


# ── how the deck contents map onto colour and icon ──────────────────────────
MODIFIER_ACCENT = {"nice": GREEN, "naughty": RED}

ACTION_STYLE = {
    "freeze": (RED, icon_stop),
    "flip": (VIOLET, icon_hit(3)),
    "second_chance": (ROSE, icon_heart),
    "n_just_one_more": (AMBER, icon_one_more),
    # Deliberately the same violet as Hit 3: they are the same action.
    "n_flip_four": (VIOLET, icon_hit(4)),
    "n_steal": (JADE, icon_steal),
    "n_swap": (CYAN, icon_swap),
    "n_discard": (MAGENTA, icon_discard),
}

ACTION_ACCENT = {k: v[0] for k, v in ACTION_STYLE.items()}

# Sized once across BOTH decks so a 5 is the same size in either one.
ALL_NUMBER_LABELS = [str(v) for v in range(0, 14)]
ALL_MODIFIER_LABELS = [m[2] for v in rb_cards.MODIFIERS.values() for m in v]
ALL_ACTION_LABELS = [a[2] for v in rb_cards.ACTIONS.values() for a in v]


# ── the three card families ─────────────────────────────────────────────────
def draw_number(value, captions):
    colour = number_hue(value)
    im, d = blank()
    frame(d, colour)
    f = family_font(ALL_NUMBER_LABELS, 1150 * SS, 1010 * SS)
    text_at(d, W * SS // 2, MARK_Y * SS, str(value), f, colour, ink_centre(d, f))
    if value in captions:
        caption(d, captions[value], colour)
    return downsample(im)


def draw_modifier(label, accent, cap):
    im, d = blank()
    frame(d, accent)
    f = family_font(ALL_MODIFIER_LABELS, 1260 * SS, 1010 * SS)
    text_at(d, W * SS // 2, MARK_Y * SS, label, f, accent,
            ink_centre(d, f, "".join(ALL_MODIFIER_LABELS)))
    caption(d, cap, accent)
    return downsample(im)


def draw_action(label, accent, icon):
    im, d = blank()
    frame(d, accent)
    icon(d, W * SS // 2, 940 * SS, accent)
    f = family_font(ALL_ACTION_LABELS, 1240 * SS, 260 * SS, start=800)
    text_at(d, W * SS // 2, 1720 * SS, label, f, accent, ink_centre(d, f, ALPHA))
    return downsample(im)


# Renderers for one-off number faces. Both the Unlucky 7 and the Lucky 13 are
# supplied artwork (`drawn=False` in rb_cards), so nothing lives here — the hook
# stays for the next one-off that we do draw ourselves.
SPECIAL_ART = {}


def render_deck(variant):
    """Yield (slug, PIL image) for every card face in a deck."""
    captions = rb_cards.CAPTIONS[variant]
    for v in rb_cards.NUMBERS[variant]:
        yield str(v), draw_number(v, captions)
    # One-off numbers, but only the ones we draw ourselves — a supplied face
    # would be overwritten by whatever we rendered here.
    for _name, slug, _label, _value, _cap, drawn in rb_cards.SPECIAL_NUMBERS[variant]:
        if drawn:
            yield slug, SPECIAL_ART[slug]()
    for _name, slug, label in rb_cards.MODIFIERS[variant]:
        yield slug, draw_modifier(label, MODIFIER_ACCENT[variant],
                                  rb_cards.MODIFIER_CAPTION[variant])
    for name, slug, label in rb_cards.ACTIONS[variant]:
        accent, icon = ACTION_STYLE[name]
        yield slug, draw_action(label, accent, icon)
