#!/usr/bin/env python3
"""Re-upload the supplied card faces so their CDN copies are invalidated.

The Unlucky 7 and the Lucky 13 are artwork we were given, not artwork we draw,
so `gen_card_images.py` skips them (`drawn=False` in rb_cards) and they never
get the invalidating re-upload the rendered cards get.

Each file is pulled back from Cloudinary through a cache-busting query first, so
what goes up is exactly what is live now — this purges the edge cache without
risking a stale local copy overwriting a newer face.

  python3 scripts/rainbow_blackjack/reupload_supplied.py
"""
import os
import sys
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rb_cards  # noqa: E402
from gen_card_images import upload  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ART = os.path.join(REPO, "rainbow_blackjack_card_art")
BASE = "https://res.cloudinary.com/liars-club/image/upload/%s/%s.png"


def main():
    for variant, folder in rb_cards.FOLDERS.items():
        for _name, slug, _label, _v, _cap, drawn in rb_cards.SPECIAL_NUMBERS[variant]:
            if drawn:
                continue
            url = (BASE % (folder, slug)) + "?cb=%d" % time.time()
            with urllib.request.urlopen(url, timeout=90) as r:
                data = r.read()
            path = os.path.join(ART, variant, slug + ".png")
            with open(path, "wb") as f:
                f.write(data)
            print("  %-10s %d bytes -> %s"
                  % (slug, len(data), upload(path, folder, slug)["secure_url"]))


if __name__ == "__main__":
    main()
