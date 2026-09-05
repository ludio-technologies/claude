#!/usr/bin/env python3
"""Generate and upload every Great Emperor image asset.

The art is authored here as SVG and uploaded to Cloudinary, which rasterises it
on delivery (we request the .png extension). Same pipeline as Intransitive —
authoring the faces ourselves keeps the 13 ranks on one visual system, which
matters more here than in most decks: the whole game is scanning a hand for
rank order, so rank has to be readable at hand size.

  python3 scripts/emperor/gen_emperor_images.py            # generate + upload
  python3 scripts/emperor/gen_emperor_images.py --local    # write SVGs only
  python3 scripts/emperor/gen_emperor_images.py --only r1,r2

Writes scripts/emperor/emperor_images.json — the alias -> url map that the
game builder reads for gameInitOptions.images and the deck's card art.
"""
import argparse
import colorsys
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_JSON = os.path.join(HERE, "emperor_images.json")
SVG_DIR = os.path.join(HERE, "emperor_art")

CLOUD = "liars-club"
KEY = "721495889677635"
SECRET = "uRKz0gw-XsGs4VT3CcndOiFZD24"
FOLDER = "images/emperor"
BASE = "https://res.cloudinary.com/%s/image/upload" % CLOUD

# ------------------------------------------------------------------- palette
PAPER = "#F6F1E7"      # the card face
INK = "#2B2417"
GOLD = "#C9A227"
CRIMSON = "#9E2B2B"

# The twelve ranks ride one continuous ramp — deep indigo at the Emperor through
# to pale tan at the Peasant. Rank is legible from colour alone before you read
# the numeral, and "darker is better" holds across the whole hand.
#
# The hue wraps FORWARD past 1.0 (violet -> magenta -> crimson -> orange -> tan).
# Interpolating the short way instead runs it through teal and green, which is
# both off-theme and non-monotonic to the eye.
RAMP_FROM = (0.735, 0.55, 0.26)   # HSL, deep royal indigo
RAMP_TO = (1.085, 0.38, 0.60)     # HSL, warm pale tan (0.085 + one full turn)

# Rank -> title. Rank N appears N times in the deck; the Jester is rank 13 and
# there are two of them.
TITLES = {
    1: "Emperor",
    2: "Archbishop",
    3: "Earl Marshal",
    4: "Baroness",
    5: "Abbess",
    6: "Knight",
    7: "Seamstress",
    8: "Mason",
    9: "Cook",
    10: "Shepherdess",
    11: "Stonecutter",
    12: "Peasant",
    13: "Jester",
}
JESTER_RANK = 13


def _hex(r, g, b):
    return "#%02X%02X%02X" % (round(r * 255), round(g * 255), round(b * 255))


def rank_colors(rank):
    """(accent, dark, light) for a rank, interpolated along the ramp.

    The Jester sits off the ramp entirely — it is not a rung on the ladder, it
    is the wild card, so it gets gold rather than a position-implying shade.
    """
    if rank == JESTER_RANK:
        return GOLD, "#8A6D12", "#EBD98A"
    t = (rank - 1) / 11.0
    h = RAMP_FROM[0] + (RAMP_TO[0] - RAMP_FROM[0]) * t
    s = RAMP_FROM[1] + (RAMP_TO[1] - RAMP_FROM[1]) * t
    ll = RAMP_FROM[2] + (RAMP_TO[2] - RAMP_FROM[2]) * t
    accent = _hex(*colorsys.hls_to_rgb(h, ll, s))
    dark = _hex(*colorsys.hls_to_rgb(h, max(0.0, ll - 0.12), s))
    light = _hex(*colorsys.hls_to_rgb(h, min(1.0, ll + 0.32), s * 0.8))
    return accent, dark, light


# ---------------------------------------------------------------- card faces
CARD_W, CARD_H = 500, 700


def _pips(count, accent, cy):
    """A row of dots saying how many of this rank exist in the deck.

    This is the one piece of information an Emperor player actually has to hold
    in their head — twelve Peasants but only one Emperor — so it belongs on the
    card rather than in the rulebook. Rows of six keep the count countable.
    """
    out = []
    per_row = 6
    rows = [count] if count <= per_row else []
    if not rows:
        full, rest = divmod(count, per_row)
        rows = [per_row] * full + ([rest] if rest else [])
    gap, r, row_gap = 34, 9, 32
    y = cy - (len(rows) - 1) * row_gap / 2.0
    for row in rows:
        x0 = CARD_W / 2.0 - (row - 1) * gap / 2.0
        for i in range(row):
            out.append('<circle cx="%.1f" cy="%.1f" r="%d" fill="%s"/>'
                       % (x0 + i * gap, y, r, accent))
        y += row_gap
    return "".join(out)


def card_svg(rank):
    accent, dark, light = rank_colors(rank)
    title = TITLES[rank]
    count = 2 if rank == JESTER_RANK else rank
    numeral = str(rank)
    caption = ("Wild &#183; 2 in the deck" if rank == JESTER_RANK
               else "%d in the deck" % count)
    # The Jester earns a motley band; every other rank keeps the plain frame so
    # the ramp reads cleanly down the hand. Inset to x 160..340 so it clears the
    # corner numerals rather than sitting on top of them.
    motley = ""
    if rank == JESTER_RANK:
        motley = "".join(
            '<path d="M%d 46 L%d 76 L%d 106 L%d 76 Z" fill="%s" opacity="0.85"/>'
            % (x, x + 24, x, x - 24, CRIMSON if (i % 2 == 0) else accent)
            for i, x in enumerate(range(176, 341, 48)))
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {CARD_W} {CARD_H}" width="{CARD_W}" height="{CARD_H}">
<rect width="{CARD_W}" height="{CARD_H}" rx="36" fill="{dark}"/>
<rect x="8" y="8" width="{CARD_W - 16}" height="{CARD_H - 16}" rx="30" fill="{accent}"/>
<rect x="30" y="30" width="{CARD_W - 60}" height="{CARD_H - 60}" rx="18" fill="{PAPER}"/>
{motley}
<text x="{CARD_W / 2}" y="330" text-anchor="middle" font-family="Georgia, serif"
      font-size="230" font-weight="bold" fill="{accent}">{numeral}</text>
<text x="{CARD_W / 2}" y="408" text-anchor="middle" font-family="Georgia, serif"
      font-size="44" fill="{INK}">{title}</text>
<path d="M140 440 H360" stroke="{light}" stroke-width="4" stroke-linecap="round"/>
{_pips(count, accent, 500)}
<text x="{CARD_W / 2}" y="612" text-anchor="middle" font-family="Georgia, serif"
      font-size="26" fill="{INK}" opacity="0.6">{caption}</text>
<text x="66" y="98" text-anchor="middle" font-family="Georgia, serif"
      font-size="46" font-weight="bold" fill="{accent}">{numeral}</text>
<g transform="rotate(180 {CARD_W - 66} {CARD_H - 98})"><text x="{CARD_W - 66}" y="{CARD_H - 98}"
      text-anchor="middle" font-family="Georgia, serif" font-size="46"
      font-weight="bold" fill="{accent}">{numeral}</text></g>
</svg>"""


def cardback_svg():
    accent, dark, _ = rank_colors(1)
    lattice = "".join(
        '<path d="M%d %d L%d %d L%d %d L%d %d Z" fill="%s" opacity="0.30"/>'
        % (x, y, x + 34, y + 44, x, y + 88, x - 34, y + 44, GOLD)
        for y in range(-40, CARD_H, 88) for x in range(34, CARD_W, 68))
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {CARD_W} {CARD_H}" width="{CARD_W}" height="{CARD_H}">
<rect width="{CARD_W}" height="{CARD_H}" rx="36" fill="{dark}"/>
<rect x="8" y="8" width="{CARD_W - 16}" height="{CARD_H - 16}" rx="30" fill="{accent}"/>
<clipPath id="c"><rect x="30" y="30" width="{CARD_W - 60}" height="{CARD_H - 60}" rx="18"/></clipPath>
<g clip-path="url(#c)"><rect x="30" y="30" width="{CARD_W - 60}" height="{CARD_H - 60}" fill="{dark}"/>{lattice}</g>
<circle cx="{CARD_W / 2}" cy="{CARD_H / 2}" r="92" fill="{accent}" stroke="{GOLD}" stroke-width="6"/>
<text x="{CARD_W / 2}" y="{CARD_H / 2 + 26}" text-anchor="middle" font-family="Georgia, serif"
      font-size="96" font-weight="bold" fill="{GOLD}">E</text>
</svg>"""


def banner_svg():
    fan = []
    for i, rank in enumerate((1, 4, 7, 10, 12)):
        accent, dark, _ = rank_colors(rank)
        # Spacing must exceed the scaled card width (500 * 0.44 = 220) or each
        # card clips the numeral of the one before it.
        x, rot = 250 + i * 175, -22 + i * 11
        fan.append(
            f'<g transform="translate({x},430) rotate({rot}) scale(0.44)">'
            f'<rect x="-250" y="-350" width="500" height="700" rx="36" fill="{dark}"/>'
            f'<rect x="-242" y="-342" width="484" height="684" rx="30" fill="{accent}"/>'
            f'<rect x="-220" y="-320" width="440" height="640" rx="18" fill="{PAPER}"/>'
            f'<text x="0" y="60" text-anchor="middle" font-family="Georgia, serif"'
            f' font-size="230" font-weight="bold" fill="{accent}">{rank}</text></g>')
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 800" width="1200" height="800">
<rect width="1200" height="800" fill="#2B1B4A"/>
<text x="600" y="150" text-anchor="middle" font-family="Georgia, serif"
      font-size="94" font-weight="bold" fill="{GOLD}">Emperor</text>
<text x="600" y="212" text-anchor="middle" font-family="Georgia, serif"
      font-size="36" fill="{PAPER}">A game of rank, ruin and revolution.</text>
{"".join(fan)}
<text x="600" y="706" text-anchor="middle" font-family="Georgia, serif"
      font-size="32" fill="{PAPER}" opacity="0.8">Shed your hand first and rule the table.</text>
<text x="600" y="752" text-anchor="middle" font-family="Georgia, serif"
      font-size="32" fill="{PAPER}" opacity="0.8">Finish last and serve it.</text>
</svg>"""


def wallpaper_svg():
    lattice = "".join(
        '<path d="M%d %d L%d %d L%d %d L%d %d Z" fill="%s" opacity="0.10"/>'
        % (x, y, x + 60, y + 78, x, y + 156, x - 60, y + 78, GOLD)
        for y in range(-80, 1000, 156) for x in range(60, 1600, 120))
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1600 1000" width="1600" height="1000">
<rect width="1600" height="1000" fill="#241640"/>
{lattice}
</svg>"""


def build_specs():
    specs = [("r%d" % r, card_svg(r)) for r in range(1, 13)]
    specs.append(("jester", card_svg(JESTER_RANK)))
    specs.append(("cardback", cardback_svg()))
    specs.append(("banner", banner_svg()))
    specs.append(("wallpaper", wallpaper_svg()))
    return specs


# -------------------------------------------------------------------- upload
def sign(params):
    src = "&".join("%s=%s" % (k, params[k]) for k in sorted(params)) + SECRET
    return hashlib.sha1(src.encode()).hexdigest()


def upload(svg_bytes, public_id):
    """Signed upload. invalidate=true or the version-less URL serves a stale copy."""
    ts = str(int(time.time()))
    params = {"folder": FOLDER, "invalidate": "true", "overwrite": "true",
              "public_id": public_id, "timestamp": ts}
    fields = dict(params)
    fields["signature"] = sign(params)
    fields["api_key"] = KEY

    boundary = uuid.uuid4().hex
    body = b""
    for k, v in fields.items():
        body += ('--%s\r\nContent-Disposition: form-data; name="%s"\r\n\r\n%s\r\n'
                 % (boundary, k, v)).encode()
    body += ('--%s\r\nContent-Disposition: form-data; name="file"; filename="%s.svg"\r\n'
             "Content-Type: image/svg+xml\r\n\r\n" % (boundary, public_id)).encode()
    body += svg_bytes + b"\r\n"
    body += ("--%s--\r\n" % boundary).encode()

    req = urllib.request.Request(
        "https://api.cloudinary.com/v1_1/%s/image/upload" % CLOUD,
        data=body, method="POST")
    req.add_header("Content-Type", "multipart/form-data; boundary=" + boundary)
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.load(r)


def explicit(public_id):
    """Re-derive a stored asset and purge its edge copy.

    Uploading with invalidate=true is not enough on its own: the .png we deliver
    is a DERIVED asset, and its cached derivation survives the upload. A query
    string does not get you past it either — Cloudinary ignores unknown params,
    so `?v=123` returns the same stale bytes and a verification built on it
    silently passes. The explicit endpoint re-processes the asset and honours
    invalidate, which is what actually replaces the delivered image.
    """
    ts = str(int(time.time()))
    params = {"invalidate": "true", "public_id": "%s/%s" % (FOLDER, public_id),
              "type": "upload", "timestamp": ts}
    body = dict(params)
    body["signature"] = sign(params)
    body["api_key"] = KEY
    data = urllib.parse.urlencode(body).encode()
    req = urllib.request.Request(
        "https://api.cloudinary.com/v1_1/%s/image/explicit" % CLOUD,
        data=data, method="POST")
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.load(r)


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--local", action="store_true", help="write SVGs, skip upload")
    ap.add_argument("--only", default="", help="comma-separated alias prefixes")
    args = ap.parse_args()

    os.makedirs(SVG_DIR, exist_ok=True)
    specs = build_specs()
    if args.only:
        pref = tuple(p.strip() for p in args.only.split(",") if p.strip())
        specs = [s for s in specs if s[0].startswith(pref)]

    for alias, svg in specs:
        open(os.path.join(SVG_DIR, alias + ".svg"), "w").write(svg)
    print("wrote %d SVGs to %s" % (len(specs), SVG_DIR))
    if args.local:
        return

    out = {}
    if os.path.exists(OUT_JSON):
        out = json.load(open(OUT_JSON))

    failures = []
    for i, (alias, svg) in enumerate(specs, 1):
        try:
            upload(svg.encode(), alias)
            # Serve as .png so the engine never has to deal with SVG itself, and
            # strip the version so a re-upload is picked up (invalidate handles
            # the edge copy).
            url = "%s/%s/%s.png" % (BASE, FOLDER, alias)
            # Purge the derived .png before hashing it, or a re-run records the
            # sha of the PREVIOUS render and the check silently passes on art
            # that is no longer there.
            explicit(alias)
            png = fetch(url)
            out[alias] = {"url": url, "sha1": hashlib.sha1(png).hexdigest()[:12],
                          "bytes": len(png)}
            print("[%2d/%d] %-10s ok  %7dB png  sha %s"
                  % (i, len(specs), alias, len(png), out[alias]["sha1"]))
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "ignore")[:200] if e.fp else str(e)
            print("[%2d/%d] %-10s HTTP %s: %s" % (i, len(specs), alias, e.code, detail),
                  file=sys.stderr)
            failures.append(alias)
        except Exception as e:
            print("[%2d/%d] %-10s %s: %s" % (i, len(specs), alias, type(e).__name__, e),
                  file=sys.stderr)
            failures.append(alias)

    json.dump(out, open(OUT_JSON, "w"), indent=1)
    print("\nwrote %d aliases to %s" % (len(out), OUT_JSON))
    if failures:
        print("FAILED: %s" % ", ".join(failures), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
