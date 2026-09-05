#!/usr/bin/env python3
"""Draw both Rainbow Blackjack decks and upload them to Cloudinary.

Nice and Naughty share one style (see rb_art.py) and one hue wheel, so the
numbers they have in common come out identical. Each deck gets its own folder
under images/rainbow_blackjack/ so the original artwork is left untouched.

  python3 scripts/rainbow_blackjack/gen_card_images.py                 # draw both
  python3 scripts/rainbow_blackjack/gen_card_images.py nice            # one deck
  python3 scripts/rainbow_blackjack/gen_card_images.py --upload        # and push
  python3 scripts/rainbow_blackjack/gen_card_images.py --upload --force

`--force` stamps each PNG with the render time so its bytes differ from what is
already stored. Cloudinary de-duplicates identical bytes — it returns the stored
version without doing any work, and crucially without running the invalidation —
so a re-upload of unchanged art leaves a stale CDN copy in place forever. Use
--force when the edge is serving something old and the pixels have not changed.
"""
import hashlib
import io
import json
import os
import sys
import time
import urllib.request

from PIL import Image, PngImagePlugin

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rb_cards  # noqa: E402
from rb_art import render_deck  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(REPO, "rainbow_blackjack_card_art")

CLOUD_NAME = "liars-club"
API_KEY = "721495889677635"
API_SECRET = "uRKz0gw-XsGs4VT3CcndOiFZD24"


def upload(path, folder, public_id):
    """Overwrite a public_id and purge the CDN copy.

    `invalidate=true` matters as much as `overwrite=true`: we serve these from
    version-less URLs, so without it a re-upload leaves the old picture cached
    at the edge and players keep seeing the card we just replaced. Signed params
    go into sig_src in alphabetical order.
    """
    data = open(path, "rb").read()
    ts = str(int(time.time()))
    sig_src = ("folder=%s&invalidate=true&overwrite=true&public_id=%s&timestamp=%s%s"
               % (folder, public_id, ts, API_SECRET))
    sig = hashlib.sha1(sig_src.encode()).hexdigest()
    boundary = "----RainbowBlackjackCards"
    parts = []
    for n, v in (("api_key", API_KEY), ("timestamp", ts), ("folder", folder),
                 ("invalidate", "true"), ("overwrite", "true"),
                 ("public_id", public_id), ("signature", sig)):
        parts.append(("--%s\r\n" % boundary).encode())
        parts.append(('Content-Disposition: form-data; name="%s"\r\n\r\n' % n).encode())
        parts.append(("%s\r\n" % v).encode())
    parts.append(("--%s\r\n" % boundary).encode())
    parts.append(('Content-Disposition: form-data; name="file"; filename="%s.png"\r\n'
                  % public_id).encode())
    parts.append(b"Content-Type: image/png\r\n\r\n")
    parts.append(data)
    parts.append(b"\r\n")
    parts.append(("--%s--\r\n" % boundary).encode())
    req = urllib.request.Request(
        "https://api.cloudinary.com/v1_1/%s/image/upload" % CLOUD_NAME,
        data=b"".join(parts), method="POST")
    req.add_header("Content-Type", "multipart/form-data; boundary=%s" % boundary)
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.load(r)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    variants = args or list(rb_cards.FOLDERS)
    push = "--upload" in sys.argv
    force = "--force" in sys.argv

    # An invisible tEXt chunk: same pixels, different bytes, so the upload is a
    # real one and the invalidation actually runs.
    stamp = None
    if force:
        stamp = PngImagePlugin.PngInfo()
        stamp.add_text("rendered", time.strftime("%Y-%m-%dT%H:%M:%S"))

    for variant in variants:
        folder = os.path.join(OUT, variant)
        os.makedirs(folder, exist_ok=True)
        made = []
        for slug, im in render_deck(variant):
            path = os.path.join(folder, slug + ".png")
            im.save(path, "PNG", optimize=True, pnginfo=stamp)
            made.append((slug, path))
        size = sum(os.path.getsize(p) for _, p in made)
        print("%-8s %2d cards -> %s (%.1f MB)"
              % (variant, len(made), folder, size / 1e6))

        if push:
            for slug, path in made:
                upload(path, rb_cards.FOLDERS[variant], slug)
            print("         uploaded to %s/" % rb_cards.FOLDERS[variant])

    if not push:
        print("\npass --upload to push them to Cloudinary")


if __name__ == "__main__":
    main()
