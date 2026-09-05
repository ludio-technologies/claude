from PIL import Image, ImageDraw, ImageFont, ImageEnhance, ImageFilter
import sys, os, urllib.request
sys.path.insert(0, "/Users/ankitbuddhiraju/Documents/claude/Code/scripts/carte_royal_mafia")
from upload_crm import upload

FONT = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
# Base image: "1st Miss Charm pageant" — PUBLIC DOMAIN, Wikimedia Commons (a real pageant stage).
SRC_URL = "https://upload.wikimedia.org/wikipedia/commons/d/dd/1st_Miss_Charm_pageant_%282%29.jpg"
os.makedirs("/tmp/pageant_cards", exist_ok=True)
if not os.path.exists("/tmp/miss_charm.jpg"):
    urllib.request.urlretrieve(SRC_URL, "/tmp/miss_charm.jpg")
src = Image.open("/tmp/miss_charm.jpg").convert("RGB")   # 1600x1200 PD pageant stage
W0, H0 = src.size

# ---------- BANNER 1080x1080 (square center crop + title scrim) ----------
side = min(W0, H0)                       # 1200
left = (W0 - side) // 2                   # center crop
banner = src.crop((left, 0, left + side, side)).resize((1080, 1080), Image.LANCZOS)
# bottom scrim for text legibility
scrim = Image.new("RGBA", (1080, 1080), (0, 0, 0, 0))
sd = ImageDraw.Draw(scrim)
for y in range(700, 1080):
    a = int(235 * (y - 700) / 380)
    sd.line([(0, y), (1080, y)], fill=(10, 4, 14, a))
banner = Image.alpha_composite(banner.convert("RGBA"), scrim)
d = ImageDraw.Draw(banner)
tf = ImageFont.truetype(FONT, 150)
tb = d.textbbox((0, 0), "PAGEANT", font=tf); tw = tb[2] - tb[0]
d.text(((1080 - tw) // 2 + 4, 812), "PAGEANT", font=tf, fill=(0, 0, 0, 150))
d.text(((1080 - tw) // 2, 808), "PAGEANT", font=tf, fill=(255, 224, 138))
sf = ImageFont.truetype(FONT, 44)
sub = "Take the stage — dodge the spotlight"
sb = d.textbbox((0, 0), sub, font=sf); sw = sb[2] - sb[0]
d.text(((1080 - sw) // 2, 985), sub, font=sf, fill=(238, 224, 236))
banner.convert("RGB").save("/tmp/pageant_cards/banner.png")

# ---------- WALLPAPER 1600x900 (darkened + vignette, understated) ----------
wp = src.crop((0, 150, 1600, 1050)).resize((1600, 900), Image.LANCZOS)
wp = ImageEnhance.Brightness(wp).enhance(0.5)
wp = ImageEnhance.Color(wp).enhance(0.85)
vig = Image.new("L", (1600, 900), 0)
vd = ImageDraw.Draw(vig)
vd.ellipse((-350, -250, 1950, 1150), fill=255)
vig = vig.filter(ImageFilter.GaussianBlur(180))
dark = Image.new("RGB", (1600, 900), (6, 3, 10))
wp = Image.composite(wp, dark, vig)
wp.save("/tmp/pageant_cards/wallpaper.jpg", quality=88)

# ---------- upload ----------
FOLDER = "images/pageant"
print("BANNER", upload(open("/tmp/pageant_cards/banner.png", "rb").read(), FOLDER, "banner", "png"))
print("WALLPAPER", upload(open("/tmp/pageant_cards/wallpaper.jpg", "rb").read(), FOLDER, "wallpaper", "jpg"))

# preview
prev = Image.new("RGB", (540 + 800 + 30, 540), (30, 30, 30))
prev.paste(Image.open("/tmp/pageant_cards/banner.png").resize((540, 540)), (10, 0))
prev.paste(Image.open("/tmp/pageant_cards/wallpaper.jpg").resize((800, 450)), (560, 45))
prev.save("/tmp/pageant_cards/_realbg_preview.png")
