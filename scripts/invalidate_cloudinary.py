#!/usr/bin/env python3
"""Purge the CDN copy of assets that are already on Cloudinary.

Re-uploading is not enough on its own. Cloudinary de-duplicates: upload bytes
identical to the stored version and it returns the existing version without
doing any work — including without running the invalidation. So an asset whose
edge copy went stale *before* we started sending `invalidate=true` stays stale
no matter how many times it is re-uploaded.

The `explicit` endpoint is the way out. It re-processes an asset that is already
stored, and honours `invalidate=true`, so it purges the edge without needing new
bytes.

  python3 scripts/invalidate_cloudinary.py images/foo/bar images/foo/baz
  python3 scripts/invalidate_cloudinary.py --rainbow-blackjack
"""
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.request

CLOUD_NAME = "liars-club"
API_KEY = "721495889677635"
API_SECRET = "uRKz0gw-XsGs4VT3CcndOiFZD24"


def explicit(public_id):
    """Re-process a stored asset and purge its CDN copy."""
    ts = str(int(time.time()))
    # Signed params, alphabetical.
    sig_src = ("invalidate=true&public_id=%s&timestamp=%s&type=upload%s"
               % (public_id, ts, API_SECRET))
    sig = hashlib.sha1(sig_src.encode()).hexdigest()
    fields = [("api_key", API_KEY), ("timestamp", ts), ("public_id", public_id),
              ("type", "upload"), ("invalidate", "true"), ("signature", sig)]
    body = urllib.parse.urlencode(fields).encode()
    req = urllib.request.Request(
        "https://api.cloudinary.com/v1_1/%s/image/explicit" % CLOUD_NAME,
        data=body, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.load(r)


def rainbow_blackjack_ids():
    here = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, os.path.join(here, "rainbow_blackjack"))
    import rb_cards
    repo = os.path.dirname(here)
    art = os.path.join(repo, "rainbow_blackjack_card_art")
    ids = []
    for variant, folder in rb_cards.FOLDERS.items():
        for f in sorted(os.listdir(os.path.join(art, variant))):
            if f.endswith(".png"):
                ids.append("%s/%s" % (folder, os.path.splitext(f)[0]))
    ids.append("images/rainbow_blackjack/cheatsheet")
    return ids


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    ids = rainbow_blackjack_ids() if "--rainbow-blackjack" in sys.argv else args
    if not ids:
        print(__doc__)
        return
    print("invalidating %d assets" % len(ids))
    failed = []
    for pid in ids:
        try:
            res = explicit(pid)
            print("  ok   %-52s v%s" % (pid, res.get("version")))
        except urllib.error.HTTPError as e:
            print("  FAIL %-52s %s %s" % (pid, e.code, e.read()[:120]))
            failed.append(pid)
    if failed:
        sys.exit("failed: %s" % failed)


if __name__ == "__main__":
    import urllib.parse  # noqa: E402  (used by explicit())
    main()
