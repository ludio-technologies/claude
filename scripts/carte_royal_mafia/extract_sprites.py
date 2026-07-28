from PIL import Image
import os

OLD = "/tmp/crm_cards_old"
OUT = "/tmp/crm_sprites"
os.makedirs(OUT, exist_ok=True)

OUTER_BG = (20, 28, 56)
PANEL_BG = (32, 42, 75)

def dist(c, bg):
    return ((c[0]-bg[0])**2 + (c[1]-bg[1])**2 + (c[2]-bg[2])**2) ** 0.5

def extract(src, box, bg, thresh, recolor=None, name=""):
    """Crop box from src, alpha = clamp(dist_from_bg/thresh). Auto-bbox to content."""
    im = Image.open(f"{OLD}/{src}.png").convert("RGB")
    region = im.crop(box)
    w, h = region.size
    out = Image.new("RGBA", (w, h), (0,0,0,0))
    px = region.load()
    op = out.load()
    minx, miny, maxx, maxy = w, h, 0, 0
    for y in range(h):
        for x in range(w):
            c = px[x, y]
            d = dist(c, bg)
            a = max(0.0, min(1.0, d / thresh))
            if a > 0.05:
                minx, miny = min(minx, x), min(miny, y)
                maxx, maxy = max(maxx, x), max(maxy, y)
            if recolor is not None:
                op[x, y] = (recolor[0], recolor[1], recolor[2], int(a*255))
            else:
                op[x, y] = (c[0], c[1], c[2], int(a*255))
    if maxx < minx:
        print(f"{name}: EMPTY")
        return
    cropped = out.crop((minx, miny, maxx+1, maxy+1))
    cropped.save(f"{OUT}/{name}.png")
    print(f"{name}: sprite {cropped.size} from {src}{box}")

# Coin (gold) -- gold_4 has a single coin in the bottom panel, keep RGB
extract("gold_4", (140, 430, 260, 560), PANEL_BG, 60, name="coin")
# Head (townsperson) -- townsperson_4 single head in panel; recolor flat to #aac3eb
extract("townsperson_4", (140, 420, 260, 570), PANEL_BG, 45, recolor=(170,195,235), name="head")
# Specials: big center icons on outer bg. Recolor to their flat silhouette color.
extract("dagger", (60, 90, 360, 360), OUTER_BG, 55, recolor=(120,224,205), name="dagger")
extract("mafia", (70, 110, 340, 330), OUTER_BG, 55, recolor=(214,72,72), name="mafia")
extract("warlock", (70, 120, 340, 340), OUTER_BG, 55, recolor=(178,120,214), name="warlock")
extract("police_officer", (110, 100, 300, 330), OUTER_BG, 55, recolor=(120,175,225), name="lantern")
