#!/usr/bin/env python3
"""Source famous-painting images from Wikimedia Commons (all public domain),
download a high-res render, then (after we pick crop boxes) crop to a detail
and upload to Cloudinary for Ankit's Trivia "Masterpiece details" round.

Reuses aerial_trivia's Commons + Cloudinary helpers.

  search  -> download a ~2000px render of each painting (top candidates) into
             ./painting_candidates/<slug>/<n>.jpg for review.
"""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import aerial_trivia as A  # noqa: E402

FOLDER = "images/zee_trivia/paintings"
HERE = Path(__file__).parent
CAND = HERE / "painting_candidates"

# slug -> (answer, Commons search query)
PAINTINGS = {
    "starry":  ("The Starry Night (Van Gogh)",            "Van Gogh Starry Night"),
    "mona":    ("Mona Lisa (da Vinci)",                   "Mona Lisa Leonardo"),
    "adam":    ("The Creation of Adam (Michelangelo)",    "Creation of Adam Michelangelo Sistine"),
    "scream":  ("The Scream (Munch)",                     "The Scream Munch 1893"),
    "pearl":   ("Girl with a Pearl Earring (Vermeer)",    "Girl with a Pearl Earring Vermeer"),
    "wave":    ("The Great Wave off Kanagawa (Hokusai)",  "Great Wave off Kanagawa Hokusai"),
    "venus":   ("The Birth of Venus (Botticelli)",        "Birth of Venus Botticelli"),
    "supper":  ("The Last Supper (da Vinci)",             "Last Supper Leonardo da Vinci"),
    "kiss":    ("The Kiss (Klimt)",                       "The Kiss Gustav Klimt"),
    "lilies":  ("Water Lilies (Monet)",                   "Water Lilies Monet Nympheas"),
}

RENDER_W = 2000


def cmd_search(args):
    CAND.mkdir(exist_ok=True)
    manifest = {}
    for slug, (answer, query) in PAINTINGS.items():
        d = CAND / slug
        d.mkdir(exist_ok=True)
        titles = A.search_files(query, n=args.candidates)
        entries = []
        for i, title in enumerate(titles):
            info = A.imageinfo(title, width=RENDER_W)
            if not info or "image" not in info.get("mime", ""):
                continue
            render = info.get("thumburl") or info.get("url")
            fp = d / f"{i}.jpg"
            if not (fp.exists() and fp.stat().st_size > 1000):
                try:
                    fp.write_bytes(A.fetch(render))
                    time.sleep(1.0)
                except Exception as e:
                    print(f"  ! {slug} #{i}: {e}")
                    continue
            entries.append({
                "idx": i, "title": title, "render": render,
                "full": info.get("url"),
                "w": info.get("width"), "h": info.get("height"),
                "file": str(fp),
            })
            print(f"  {slug} #{i}: {title}  (orig {info.get('width')}x{info.get('height')})")
        manifest[slug] = {"answer": answer, "query": query, "candidates": entries}
    (CAND / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print(f"\nWrote {CAND/'manifest.json'}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("search"); s.add_argument("--candidates", type=int, default=3)
    args = ap.parse_args()
    {"search": cmd_search}[args.cmd](args)
