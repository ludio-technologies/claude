#!/usr/bin/env python3
"""Build the one cheatsheet that covers both Rainbow Blackjack variants.

The cards say what they do — every one carries its own name or a BONUS /
PENALTY / UNLUCKY caption — so this is an index, not a rulebook. Three bands:
what both decks share, then what each version adds. The two decks have the same
numbers apart from the 13, which is why it fits on one landscape page.

  python3 scripts/rainbow_blackjack/gen_cheatsheet.py            # draw
  python3 scripts/rainbow_blackjack/gen_cheatsheet.py --upload   # and push
"""
import os
import sys

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rb_art  # noqa: E402
import rb_cards  # noqa: E402
from gen_card_images import upload  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ART = os.path.join(REPO, "rainbow_blackjack_card_art")
OUT = os.path.join(ART, "cheatsheet.png")

FOLDER = "images/rainbow_blackjack"
PUBLIC_ID = "cheatsheet"

# A row of 13 cards is what sets the card size, and three such rows are short
# relative to that width — so the page is a wide landscape rather than 16:9.
# Sized to sit snug: any taller and the bands float in empty gutters.
W, H = 2400, 1200
MARGIN = 64
CARD_GAP = 14
LABEL_H = 52
MAX_BAND_GAP = 80

BG = (22, 20, 27)
TEXT = (226, 224, 234)
DIM = (150, 148, 162)

BODY = "/System/Library/Fonts/Supplemental/Arial.ttf"


def disp(size):
    return ImageFont.truetype(rb_art.DISPLAY, size, index=rb_art.DISPLAY_IDX)


def body(size):
    return ImageFont.truetype(BODY, size)


def load(variant, slug):
    return Image.open(os.path.join(ART, variant, slug + ".png"))


def bands():
    """(label, colour, [(variant, slug), ...]) for each row of the sheet."""
    nice, naughty = "nice", "naughty"
    shared = [(nice, str(v)) for v in rb_cards.NUMBERS["nice"]]

    nice_only = ([(nice, s) for _n, s, _l in rb_cards.MODIFIERS[nice]]
                 + [(nice, s) for _n, s, _l in rb_cards.ACTIONS[nice]])

    # The 13 leads the Naughty row: it is the one number the other deck lacks.
    # The two one-off numbers follow it — since the ordinary 7s and 13s stopped
    # carrying captions, these two faces are the only place those rules are
    # written down.
    naughty_only = ([(naughty, "13")]
                    + [(naughty, s)
                       for _n, s, _l, _v, _c, _d in rb_cards.SPECIAL_NUMBERS[naughty]]
                    + [(naughty, s) for _n, s, _l in rb_cards.MODIFIERS[naughty]]
                    + [(naughty, s) for _n, s, _l in rb_cards.ACTIONS[naughty]])

    return [
        ("IN BOTH VERSIONS", TEXT, shared),
        ("NICE ONLY", rb_art.GREEN, nice_only),
        ("NAUGHTY ONLY", rb_art.RED, naughty_only),
    ]


def main():
    rows = bands()
    usable = W - 2 * MARGIN

    # One card size across the whole sheet, set by the row that needs the most
    # room. Uniform sizing is what makes the three bands read as one page.
    cw = min((usable - (len(cards) - 1) * CARD_GAP) // len(cards)
             for _l, _c, cards in rows)
    ch = int(round(cw * rb_art.H / float(rb_art.W)))

    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)

    d.text((MARGIN, 44), "RAINBOW BLACKJACK", font=disp(62), fill=TEXT)
    # The two variants no longer share a finish line, and this one line has to
    # serve both — the sheet is static config and cannot switch on the host's
    # choice, same as everything else on it.
    d.text((MARGIN + 2, 126),
           "Collect different numbers — draw one twice and you bust. "
           "7 different numbers is a Rainbow: +25, and the round ends. "
           "First to 200 wins — 150 in Naughty.",
           font=body(28), fill=DIM)

    # Spread what is left over between the bands rather than letting it pool at
    # the bottom, but cap it so they do not drift apart.
    top = 200
    content = len(rows) * (LABEL_H + ch)
    gap = min((H - top - MARGIN - content) // max(len(rows) - 1, 1), MAX_BAND_GAP)

    y = top
    for label, colour, cards in rows:
        d.text((MARGIN, y), label, font=disp(40), fill=colour)
        # Every row starts at the margin, under its own label — a short row
        # reads as a short list, not as a centred one that lost its heading.
        for i, (variant, slug) in enumerate(cards):
            im.paste(load(variant, slug).resize((cw, ch), Image.LANCZOS),
                     (MARGIN + i * (cw + CARD_GAP), y + LABEL_H))
        y += LABEL_H + ch + gap

    im.save(OUT, "PNG", optimize=True)
    print("wrote %s (%dx%d, ratio %.2f, %.1f MB)"
          % (OUT, W, H, W / float(H), os.path.getsize(OUT) / 1e6))
    print("  card size %dx%d across %d bands" % (cw, ch, len(rows)))

    if "--upload" in sys.argv:
        print("uploaded ->", upload(OUT, FOLDER, PUBLIC_ID)["secure_url"])


if __name__ == "__main__":
    main()
