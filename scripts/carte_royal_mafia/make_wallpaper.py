from PIL import Image, ImageEnhance
import math

src = Image.open("/tmp/cand_speakeasy.jpg").convert("RGB")
W0, H0 = src.size
TARGET = 5376/3118  # match original wallpaper aspect ~1.724

# center-crop to target aspect
if W0/H0 > TARGET:
    nw = int(H0*TARGET); x0 = (W0-nw)//2
    src = src.crop((x0, 0, x0+nw, H0))
else:
    nh = int(W0/TARGET); y0 = (H0-nh)//2
    src = src.crop((0, y0, W0, y0+nh))

# upscale a bit for a crisper board bg
W, H = 2400, int(2400/TARGET)
im = src.resize((W, H), Image.LANCZOS)

# tone: darken + navy tint (multiply toward #1a2342) + vignette
im = ImageEnhance.Brightness(im).enhance(0.62)
im = ImageEnhance.Contrast(im).enhance(1.05)

TINT = (26, 35, 66)  # #1a2342
px = im.load()
cx, cy = W/2, H/2
maxd = math.hypot(cx, cy)
for y in range(H):
    for x in range(W):
        r, g, b = px[x, y]
        # navy multiply blend (30%)
        r = int(r*0.72 + TINT[0]*0.28)
        g = int(g*0.72 + TINT[1]*0.28)
        b = int(b*0.72 + TINT[2]*0.28)
        # vignette
        d = math.hypot(x-cx, y-cy)/maxd
        v = 1.0 - 0.45*(d**2)
        px[x, y] = (int(r*v), int(g*v), int(b*v))

im.save("/tmp/crm_wallpaper_new.jpg", quality=88)
print("saved", im.size)
