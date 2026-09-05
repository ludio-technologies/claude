#!/usr/bin/env python3
"""Banner + wallpaper for Paperback (book/parchment theme)."""
import os
from PIL import Image, ImageDraw, ImageFont
OUT = "/tmp/paperback_cards"; os.makedirs(OUT, exist_ok=True)
SERIF = "/System/Library/Fonts/Supplemental/Georgia Bold.ttf"
if not os.path.exists(SERIF): SERIF = "/System/Library/Fonts/Supplemental/Times New Roman Bold.ttf"
SANS = "/System/Library/Fonts/Supplemental/Arial.ttf"
INK=(60,42,26); BORDER=(107,74,43); PARCH=(242,228,201)

def font(p,s): return ImageFont.truetype(p,s)
def ctext(d, cx, y, t, f, fill):
    b=f.getbbox(t); d.text((cx-(b[2]-b[0])/2-b[0], y), t, font=f, fill=fill)

# ── banner 1200x420 ──
W,H=1200,420
img=Image.new("RGB",(W,H),PARCH); d=ImageDraw.Draw(img)
d.rectangle([0,0,W,H],outline=BORDER,width=26)
# faint tile letters in the corners as motif
for (x,c) in [(120,"P"),(1010,"K")]:
    tf=font(SERIF,240); ctext(d,x,60,c,tf,(224,208,178))
ctext(d, W//2, 90, "PAPERBACK", font(SERIF,150), INK)
ctext(d, W//2, 270, "spell words · build your deck · out-write the table", font(SANS,44), BORDER)
img.save(f"{OUT}/banner.png")

# ── wallpaper 1600x1000 ──
W,H=1600,1000
img=Image.new("RGB",(W,H),(214,196,162)); d=ImageDraw.Draw(img)
# scattered faint tiles
import random; random.seed(7)
tf=font(SERIF,120)
for _ in range(60):
    x=random.randint(-20,W-80); y=random.randint(-20,H-80)
    c=random.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
    d.text((x,y),c,font=tf,fill=(206,188,154))
# center plate
pw,ph=900,300; x0=(W-pw)//2; y0=(H-ph)//2
d.rounded_rectangle([x0,y0,x0+pw,y0+ph],radius=40,fill=PARCH,outline=BORDER,width=16)
ctext(d,W//2,y0+70,"PAPERBACK",font(SERIF,120),INK)
ctext(d,W//2,y0+210,"a word-building deck game",font(SANS,40),BORDER)
img.save(f"{OUT}/wallpaper.png")
print("banner + wallpaper ->", OUT)
