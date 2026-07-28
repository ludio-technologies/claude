from PIL import Image, ImageDraw
import os

CARDS = "/tmp/crm_cards_new"
OUT = "/tmp/crm_tut"
os.makedirs(OUT, exist_ok=True)

BG = (20, 28, 56)
BORDER = (212, 175, 55)  # #d4af37 gold accent

SLIDES = {
    "tut1": ["mafia", "warlock"],
    "tut2": ["gold_15", "townsperson_1"],
    "tut3": ["mafia"],
    "tut4": ["warlock"],
    "tut5": ["police_officer"],
    "tut6": ["dagger"],
}

CARD_H = 384
GAP = 46
MARGIN_Y = 44

def build(cards):
    imgs = []
    for n in cards:
        c = Image.open(f"{CARDS}/{n}.png").convert("RGBA")
        w = int(CARD_H * c.width / c.height)
        imgs.append(c.resize((w, CARD_H), Image.LANCZOS))
    total_w = sum(i.width for i in imgs) + GAP * (len(imgs) - 1)
    W = 720
    H = CARD_H + 2 * MARGIN_Y
    canvas = Image.new("RGBA", (W, H), BG + (255,))
    d = ImageDraw.Draw(canvas)
    d.rounded_rectangle([5, 5, W - 6, H - 6], radius=18, outline=BORDER, width=3)
    x = (W - total_w) // 2
    for im in imgs:
        canvas.alpha_composite(im, (x, MARGIN_Y))
        x += im.width + GAP
    return canvas.convert("RGB")

for name, cards in SLIDES.items():
    img = build(cards)
    img.save(f"{OUT}/{name}.png")
    print(f"{name}: {img.size}  cards={cards}")
