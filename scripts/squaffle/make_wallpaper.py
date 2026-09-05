#!/usr/bin/env python3
"""Wallpaper from an online photo (Unsplash, free for commercial use / no attribution):
scrabble letter tiles on a wooden surface. Darkened + warm scrim so board cards/text stay
readable. 1600x900, uploaded over images/squaffle/wallpaper.jpg (same public_id → live at once).
Run with /usr/bin/python3."""
import sys, urllib.request
from PIL import Image, ImageEnhance
sys.path.insert(0, "/Users/ankitbuddhiraju/Documents/claude/Code/scripts/carte_royal_mafia")
from upload_crm import upload

SRC = ("https://images.unsplash.com/photo-1646380783208-5bfac3c1d02d"
       "?fm=jpg&q=80&w=2400&fit=crop")
OUT = "/tmp/squaffle_art/wallpaper.jpg"
req = urllib.request.Request(SRC, headers={"User-Agent": "Mozilla/5.0"})
data = urllib.request.urlopen(req, timeout=120).read()
open("/tmp/squaffle_src.jpg", "wb").write(data)

im = Image.open("/tmp/squaffle_src.jpg").convert("RGB")
# center-crop to 16:9 then resize to 1600x900
W, H = 1600, 900
tw, th = im.size
scale = max(W / tw, H / th)
im = im.resize((int(tw * scale), int(th * scale)))
tw, th = im.size
im = im.crop(((tw - W) // 2, (th - H) // 2, (tw - W) // 2 + W, (th - H) // 2 + H))
# darken + slightly desaturate so it recedes behind the play area
im = ImageEnhance.Brightness(im).enhance(0.55)
im = ImageEnhance.Color(im).enhance(0.75)
# warm parchment scrim
scrim = Image.new("RGB", (W, H), (60, 44, 26))
im = Image.blend(im, scrim, 0.30)
im.save(OUT, quality=88)

url = upload(open(OUT, "rb").read(), "images/squaffle", "wallpaper", "jpg")
print("wallpaper ->", url)
