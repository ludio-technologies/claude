import sys, os, glob
sys.path.insert(0, "/Users/ankitbuddhiraju/Documents/claude/Code/scripts/carte_royal_mafia")
from upload_crm import upload

FOLDER = "images/pageant"
paths = sorted(glob.glob("/tmp/pageant_cards/*.png"))
paths = [p for p in paths if not os.path.basename(p).startswith("_")]
for i, p in enumerate(paths, 1):
    pid = os.path.splitext(os.path.basename(p))[0]
    url = upload(open(p, "rb").read(), FOLDER, pid, "png")
    print(f"[{i}/{len(paths)}] {url}")
