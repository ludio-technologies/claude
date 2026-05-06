import json
import os
import zipfile
import textwrap
from PIL import Image, ImageDraw, ImageFont

# --- Configuration ---
WIDTH = 1700
HEIGHT = 2200
ASSETS_DIR = "assets"       
OUTPUT_DIR = "output_cards" 
JSON_FILE = "deck.json"     
FONT_FILE = "font.ttf"      

def generate_card(card_data):
    name = card_data['name']
    title = card_data.get('title')
    num = card_data['number']
    bg_color = card_data['color']
    icon_filename = card_data['icon']
    description = card_data['text']
    
    filename = f"{name}_{num}.png"
    
    # 1. Create the base canvas
    card = Image.new('RGB', (WIDTH, HEIGHT), color=bg_color)
    draw = ImageDraw.Draw(card)

    # 2. Handle the PNG Icon
    if icon_filename:
        icon_path = os.path.join(ASSETS_DIR, icon_filename)
        if os.path.exists(icon_path):
            icon = Image.open(icon_path).convert("RGBA")
            
            # Resize icon to fit nicely
            icon.thumbnail((800, 800))
            
            # Calculate centered coordinates
            x = (WIDTH - icon.width) // 2
            y = (HEIGHT - icon.height) // 2 - 250
            
            card.paste(icon, (x, y), icon)
        else:
            print(f"Warning: Could not find {icon_path}")

    # 3. Setup Fonts
    try:
        num_font = ImageFont.truetype(FONT_FILE, 350)
        title_font = ImageFont.truetype(FONT_FILE, 220) # <--- Distinctly larger title
        text_font = ImageFont.truetype(FONT_FILE, 120)  # <--- Smaller description text
    except IOError:
        print(f"\n[!] ERROR: Could not find '{FONT_FILE}'.")
        print("Falling back to the tiny default font...\n")
        num_font = ImageFont.load_default()
        title_font = ImageFont.load_default()
        text_font = ImageFont.load_default()

    # 4. Draw the Number (Top Left)
    draw.text((150, 150), str(num), fill="black", font=num_font)

    # 5. Draw Title and Description
    # Start positioning text below the image icon
    text_y = HEIGHT - 750 

    # Draw the Title first (if it exists)
    if title:
        title_bbox = draw.textbbox((0, 0), title, font=title_font)
        title_width = title_bbox[2] - title_bbox[0]
        title_x = (WIDTH - title_width) // 2
        
        # Solid black text, no shadow
        draw.text((title_x, text_y), title, fill="black", font=title_font)
        
        # Move the Y coordinate down so the description text renders below the title
        text_y += title_bbox[3] - title_bbox[1] + 60 
    else:
        # If there is no title, push the description text down a bit so it's vertically balanced
        text_y += 100

    # Draw the Description Text
    # Wrap text cleanly based on the new 120 font size
    wrapped_text = textwrap.wrap(description, width=25) 
    
    for line in wrapped_text:
        line_bbox = draw.textbbox((0, 0), line, font=text_font)
        line_width = line_bbox[2] - line_bbox[0]
        text_x = (WIDTH - line_width) // 2
        
        # Solid black text, no shadow
        draw.text((text_x, text_y), line, fill="black", font=text_font)
        
        text_y += line_bbox[3] - line_bbox[1] + 30 

    # 6. Save the file
    card.save(os.path.join(OUTPUT_DIR, filename))
    return filename

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    with open(JSON_FILE, 'r') as f:
        data = json.load(f)

    generated_files = []

    for card in data.get('cards', []):
        saved_filename = generate_card(card)
        generated_files.append(saved_filename)
        print(f"Generated {saved_filename}")

    zip_filename = f"{data['deck_name']}.zip"
    with zipfile.ZipFile(zip_filename, 'w') as zipf:
        for file in generated_files:
            file_path = os.path.join(OUTPUT_DIR, file)
            zipf.write(file_path, arcname=file)
            
    print(f"\nSuccess! Generated {len(generated_files)} cards and saved to {zip_filename}")

if __name__ == "__main__":
    main()