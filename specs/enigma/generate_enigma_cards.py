"""
Generates card images for enigma_cards.json, uploads to Cloudinary,
and updates the JSON with image URLs.
"""
import json
import os
import cloudinary
import cloudinary.uploader
from PIL import Image, ImageDraw, ImageFont

# --- Cloudinary config ---
cloudinary.config(
    cloud_name="liars-club",
    api_key="721495889677635",
    api_secret="uRKz0gw-XsGs4VT3CcndOiFZD24",
    secure=True
)

# --- Card design ---
W, H = 900, 1260          # portrait card
BG      = "#0d0d1a"       # dark navy
ACCENT  = "#ffffff"       # white digits
LINE    = "#3a3a6e"       # dim purple separator lines
BORDER  = "#5555aa"       # subtle border

FONT_BOLD  = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
FONT_REG   = "/System/Library/Fonts/Supplemental/Arial.ttf"

OUTPUT_DIR = "output_enigma_cards"
os.makedirs(OUTPUT_DIR, exist_ok=True)

def draw_card(label: str) -> Image.Image:
    """Render a single code card for a label like '2 — 4 — 1'."""
    img  = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)

    # Outer border
    draw.rounded_rectangle([10, 10, W-10, H-10], radius=40, outline=BORDER, width=4)

    # Top decorative bar
    draw.rectangle([40, 40, W-40, 100], fill=LINE)

    # "ENIGMA" label in bar
    try:
        small_font  = ImageFont.truetype(FONT_BOLD, 44)
        digit_font  = ImageFont.truetype(FONT_BOLD, 220)
        sep_font    = ImageFont.truetype(FONT_REG, 120)
        label_font  = ImageFont.truetype(FONT_BOLD, 56)
    except IOError:
        small_font = digit_font = sep_font = label_font = ImageFont.load_default()

    # "ENIGMA" centered in top bar
    bb = draw.textbbox((0,0), "ENIGMA", font=small_font)
    tw = bb[2] - bb[0]
    draw.text(((W - tw)//2, 47), "ENIGMA", fill="#aaaacc", font=small_font)

    # Parse the 3 digits from label e.g. "2 — 4 — 1" → ["2","4","1"]
    parts = [p.strip() for p in label.split("—")]

    # Draw each digit in its own zone, with dim vertical separators
    zone_w = (W - 80) // 3
    zone_y_top = 130
    zone_y_bot = 880

    for i, digit in enumerate(parts):
        x_left  = 40 + i * zone_w
        x_right = x_left + zone_w

        # Dim background for each zone
        zone_color = ["#1a0a0a", "#0a0a1a", "#0a1a1a"][i]
        draw.rectangle([x_left+4, zone_y_top+4, x_right-4, zone_y_bot-4], fill=zone_color)

        # Position number (1/2/3/4) label at top of zone
        pos_text = str(i + 1)
        pbb = draw.textbbox((0,0), pos_text, font=label_font)
        pw  = pbb[2] - pbb[0]
        draw.text((x_left + (zone_w - pw)//2, zone_y_top + 18), pos_text,
                  fill="#555588", font=label_font)

        # Big digit centered in zone
        dbb = draw.textbbox((0,0), digit, font=digit_font)
        dw  = dbb[2] - dbb[0]
        dh  = dbb[3] - dbb[1]
        dx  = x_left + (zone_w - dw) // 2
        dy  = zone_y_top + (zone_y_bot - zone_y_top - dh) // 2
        draw.text((dx, dy), digit, fill=ACCENT, font=digit_font)

    # Vertical separators between zones
    for i in [1, 2]:
        sx = 40 + i * zone_w
        draw.line([(sx, zone_y_top), (sx, zone_y_bot)], fill=LINE, width=3)

    # Bottom section: show full code label
    bottom_top = zone_y_bot + 10
    draw.rectangle([40, bottom_top, W-40, bottom_top + 90], fill=LINE)
    lbb = draw.textbbox((0,0), label, font=label_font)
    lw  = lbb[2] - lbb[0]
    draw.text(((W - lw)//2, bottom_top + 17), label, fill="#ddddff", font=label_font)

    # Bottom decorative bar
    draw.rectangle([40, H-100, W-40, H-40], fill=LINE)
    tag = "SECRET CODE CARD"
    tbb = draw.textbbox((0,0), tag, font=small_font)
    tw  = tbb[2] - tbb[0]
    draw.text(((W - tw)//2, H - 93), tag, fill="#aaaacc", font=small_font)

    return img


def main():
    json_path = "game_jsons/enigma_cards.json"
    with open(json_path, "r") as f:
        deck = json.load(f)

    updated_cards = []
    for card in deck["cards"]:
        name  = card["name"]
        label = card["label"]

        # Generate image
        img      = draw_card(label)
        out_path = os.path.join(OUTPUT_DIR, f"{name}.png")
        img.save(out_path, "PNG")
        print(f"Generated {out_path}")

        # Upload to Cloudinary
        result = cloudinary.uploader.upload(
            out_path,
            public_id=f"enigma/cards/{name}",
            overwrite=True,
            resource_type="image"
        )
        url = result["secure_url"]
        print(f"  → {url}")

        updated_cards.append({**card, "image": url})

    deck["cards"] = updated_cards

    with open(json_path, "w") as f:
        json.dump(deck, f, indent=4, ensure_ascii=False)
    print(f"\nUpdated {json_path} with {len(updated_cards)} image URLs.")


if __name__ == "__main__":
    main()
