import sys, os, glob
sys.path.insert(0, "/Users/ankitbuddhiraju/Documents/claude/Code/scripts/carte_royal_mafia")
from upload_crm import upload

FOLDER = "images/grapheme"
paths = sorted(glob.glob("/tmp/paperback_cards/*.png"))
paths = [p for p in paths if not os.path.basename(p).startswith("_")]
print("uploading", len(paths), "files to", FOLDER)
for i, p in enumerate(paths, 1):
    pid = os.path.splitext(os.path.basename(p))[0]
    url = upload(open(p, "rb").read(), FOLDER, pid, "png")
    print("[%d/%d] %s" % (i, len(paths), pid))
print("done")
