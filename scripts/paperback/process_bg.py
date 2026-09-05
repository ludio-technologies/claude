from PIL import Image, ImageEnhance
Image.MAX_IMAGE_PIXELS = None
OUT = "/tmp/paperback_cards"

def center_crop(im, ar):  # ar = w/h target
    w, h = im.size
    if w / h > ar:
        nw = int(h * ar); x = (w - nw) // 2; box = (x, 0, x + nw, h)
    else:
        nh = int(w / ar); y = (h - nh) // 2; box = (0, y, w, y + nh)
    return im.crop(box)

# WALLPAPER — weldon letterpress (CC0), 16:9, slightly darkened for UI contrast
wp = Image.open("/tmp/src_weldon.jpg").convert("RGB")
wp = center_crop(wp, 16/9).resize((1600, 900), Image.LANCZOS)
wp = ImageEnhance.Brightness(wp).enhance(0.82)
wp.save(f"{OUT}/wallpaper.png")

# BANNER — caratteri type case (CC BY-SA 4.0), square, gently brightened
bn = Image.open("/tmp/src_caratteri.jpg").convert("RGB")
bn = center_crop(bn, 1.0).resize((1080, 1080), Image.LANCZOS)
bn = ImageEnhance.Brightness(bn).enhance(1.08)
bn = ImageEnhance.Contrast(bn).enhance(1.05)
bn.save(f"{OUT}/banner.png")

for n in ["wallpaper", "banner"]:
    im = Image.open(f"{OUT}/{n}.png")
    im.resize((300, int(300 * im.size[1] / im.size[0]))).save(f"{OUT}/_prev_{n}.jpg")
print("done", wp.size, bn.size)
