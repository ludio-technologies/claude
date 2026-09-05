#!/usr/bin/env python3
"""Generate and upload every Intransitive image asset.

The art is authored here as SVG and uploaded to Cloudinary, which rasterises it
on delivery (we request the .png extension). Authoring the glyphs ourselves
avoids depending on a third-party icon set for the six pieces that the whole
board is read from.

  python3 scripts/gen_intransitive_images.py            # generate + upload all
  python3 scripts/gen_intransitive_images.py --local    # write SVGs only
  python3 scripts/gen_intransitive_images.py --only piece_

Writes scripts/intransitive_images.json — the alias -> url map that drops
straight into gameInitOptions.images.
"""
import argparse
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.request
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_JSON = os.path.join(HERE, "intransitive_images.json")
SVG_DIR = os.path.join(HERE, "intransitive_art")

CLOUD = "liars-club"
KEY = "721495889677635"
SECRET = "uRKz0gw-XsGs4VT3CcndOiFZD24"
FOLDER = "images/intransitive"
AUDIO_FOLDER = "audio/intransitive"
BASE = f"https://res.cloudinary.com/{CLOUD}/image/upload"
AUDIO_BASE = f"https://res.cloudinary.com/{CLOUD}/video/upload"

# Sound effects, fetched from Freesound's public preview CDN so the whole
# pipeline stays re-runnable without a login. CC0 only — public domain, so the
# game carries no attribution obligation.
# One per capturing piece, so the sound tells you what did the taking.
#
# Freesound files are rarely the one-shot you want — sources here variously ran
# four snips in a row, a three-second crumple, and a flat noise bed. So rather
# than trusting any file's layout, every clip is cut to a short window around
# its own loudest onset (see onset_seconds) and then levelled. That turns a
# take of several hits into the single cleanest hit in it.
CLIP_SECONDS = 0.55
PRE_ONSET = 0.06
_SFX = "loudnorm=I=-16:TP=-1.5:LRA=11,afade=t=out:st=0.42:d=0.13"
SOUNDS = [
    {
        "alias": "capture_R",
        "source": "https://cdn.freesound.org/previews/321/321478_5485024-hq.mp3",
        "credit": "Freesound #321478 'Concrete Hit 2' by dslrguide (CC0)",
    },
    {
        "alias": "capture_P",
        "source": "https://cdn.freesound.org/previews/334/334200_4290188-hq.mp3",
        "credit": "Freesound #334200 'Paper Crumple 3' by WasabiWielder (CC0)",
    },
    {
        "alias": "capture_S",
        "source": "https://cdn.freesound.org/previews/800/800081_2520418-hq.mp3",
        "credit": "Freesound #800081 'Scissor Foley Snips and Cuts 8' by CVLTIV8R (CC0)",
    },
    {
        # The quiet click for an ordinary move, in the spirit of lichess.
        "alias": "move",
        "source": "https://cdn.freesound.org/previews/546/546119_9129912-hq.mp3",
        "credit": "Freesound #546119 'Piece Placement' by el_boss (CC0)",
    },
]

# Board palette. Red/Blue per the house convention for two-team games; the
# board itself is the warm paper white of the original.
RED = "#D83232"
BLUE = "#2E5BA8"
RED_DARK = "#A81F1F"
BLUE_DARK = "#1E3E77"
PAPER = "#F4EEE8"
INK = "#2B2B2B"

TEAM = {
    "blue": (BLUE, BLUE_DARK),
    "red": (RED, RED_DARK),
}


# ---------------------------------------------------------------- piece glyphs
# All glyphs are drawn in a 240x240 box, centred on (120,120) and spanning
# roughly 60..180 so they sit comfortably inside the tile's rounded corners.
def _tile(fill, dark):
    """The rounded team-coloured tile every piece sits on."""
    return (
        f'<rect x="10" y="10" width="220" height="220" rx="38" fill="{dark}"/>'
        f'<rect x="10" y="10" width="220" height="216" rx="38" fill="{fill}"/>'
    )


def rock_svg(fill, dark):
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 240 240" width="240" height="240">
{_tile(fill, dark)}
<path d="M56 170 L64 116 L94 80 L136 68 L174 92 L184 134 L170 170 Z"
      fill="#FFFFFF"/>
<path d="M136 68 L174 92 L184 134 L170 170 L124 170 L142 118 Z"
      fill="{dark}" opacity="0.28"/>
</svg>"""


def paper_svg(fill, dark):
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 240 240" width="240" height="240">
{_tile(fill, dark)}
<path d="M74 58 H146 L178 90 V182 H74 Z" fill="#FFFFFF"/>
<path d="M146 58 L178 90 H146 Z" fill="{dark}" opacity="0.45"/>
<path d="M96 116 H156 M96 138 H156 M96 160 H134"
      fill="none" stroke="{fill}" stroke-width="10" stroke-linecap="round"/>
</svg>"""


def scissors_svg(fill, dark):
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 240 240" width="240" height="240">
{_tile(fill, dark)}
<g fill="none" stroke="#FFFFFF" stroke-width="16" stroke-linecap="round">
  <path d="M102 146 L160 56"/>
  <path d="M138 146 L80 56"/>
</g>
<g fill="none" stroke="#FFFFFF" stroke-width="12">
  <circle cx="94" cy="166" r="22"/>
  <circle cx="146" cy="166" r="22"/>
</g>
<circle cx="120" cy="126" r="13" fill="#FFFFFF"/>
<circle cx="120" cy="126" r="5" fill="{fill}"/>
</svg>"""


GLYPHS = {"rock": rock_svg, "paper": paper_svg, "scissors": scissors_svg}
CODE = {"rock": "R", "paper": "P", "scissors": "S"}


# ------------------------------------------------------------------ board cells
def cell_svg(fill=PAPER, accent=None):
    """An empty board square: paper white with the board's ink grid line."""
    inner = ""
    if accent:
        inner = (f'<rect x="26" y="26" width="148" height="148" rx="10" '
                 f'fill="{accent}" opacity="0.22"/>'
                 f'<circle cx="100" cy="100" r="26" fill="none" stroke="{accent}" '
                 f'stroke-width="9" opacity="0.85"/>')
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200" width="200" height="200">
<rect x="0" y="0" width="200" height="200" fill="#FFFFFF"/>
{inner}
<rect x="4" y="4" width="192" height="192" fill="none" stroke="{INK}" stroke-width="8"/>
</svg>"""


# ---------------------------------------------------------------- promo artwork
def _mini_board():
    """A small 5x5 board with a blue scissors one step from the red corner."""
    cells = []
    for r in range(5):
        for c in range(5):
            cells.append(f'<rect x="{c * 76}" y="{r * 76}" width="76" height="76" '
                         f'fill="#FFFFFF" stroke="{INK}" stroke-width="5"/>')
    cells.append(f'<rect x="304" y="0" width="76" height="76" fill="{RED}" opacity="0.25"/>')
    cells.append(f'<rect x="0" y="304" width="76" height="76" fill="{BLUE}" opacity="0.25"/>')
    cells.append(f'<circle cx="266" cy="114" r="26" fill="{BLUE}"/>')
    cells.append(f'<circle cx="114" cy="266" r="26" fill="{BLUE}"/>')
    cells.append(f'<circle cx="190" cy="190" r="26" fill="{RED}"/>')
    cells.append(f'<circle cx="342" cy="190" r="26" fill="{RED}"/>')
    return "".join(cells)


def banner_svg():
    """3:2 and centred on purpose.

    The games-list card centre-crops this to roughly 3:2 and drops anything
    outside the middle ~76% horizontally, which clipped the title of the
    earlier wide, left-weighted version to "Intransitiv". Everything that has
    to survive the crop is stacked down the middle.
    """
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 800" width="1200" height="800">
<rect width="1200" height="800" fill="{PAPER}"/>
<text x="600" y="132" text-anchor="middle" font-family="Georgia, serif"
      font-size="100" font-weight="bold" fill="{INK}">Intransitive</text>
<text x="600" y="192" text-anchor="middle" font-family="Georgia, serif"
      font-size="36" fill="{RED}">Rock, paper, scissors as a board game.</text>
<g transform="translate(410,232) scale(1.0)">{_mini_board()}</g>
<text x="600" y="682" text-anchor="middle" font-family="Georgia, serif"
      font-size="32" fill="{INK}" opacity="0.75">Ten pieces. One step a turn.</text>
<text x="600" y="728" text-anchor="middle" font-family="Georgia, serif"
      font-size="32" fill="{INK}" opacity="0.75">Reach your opponent's corner to win.</text>
</svg>"""


def wallpaper_svg():
    lines = []
    for i in range(0, 1921, 120):
        lines.append(f'<line x1="{i}" y1="0" x2="{i}" y2="1080" stroke="{INK}" '
                     f'stroke-width="2" opacity="0.06"/>')
    for i in range(0, 1081, 120):
        lines.append(f'<line x1="0" y1="{i}" x2="1920" y2="{i}" stroke="{INK}" '
                     f'stroke-width="2" opacity="0.06"/>')
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1920 1080" width="1920" height="1080">
<rect width="1920" height="1080" fill="{PAPER}"/>
{''.join(lines)}
<rect x="1680" y="0" width="240" height="240" fill="{RED}" opacity="0.10"/>
<rect x="0" y="840" width="240" height="240" fill="{BLUE}" opacity="0.10"/>
</svg>"""


def board_bg_svg():
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 1200" width="1200" height="1200">
<rect width="1200" height="1200" fill="{PAPER}"/>
</svg>"""


def winner_svg():
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 800" width="800" height="800">
<rect width="800" height="800" fill="{PAPER}"/>
<g transform="translate(210,150) scale(1.0)">{_mini_board()}</g>
<text x="400" y="640" text-anchor="middle" font-family="Georgia, serif"
      font-size="86" font-weight="bold" fill="{INK}">Corner reached</text>
<text x="400" y="710" text-anchor="middle" font-family="Georgia, serif"
      font-size="44" fill="{RED}">Intransitive</text>
</svg>"""


# ------------------------------------------------------------------- the specs
def build_specs():
    specs = []
    for team, (fill, dark) in TEAM.items():
        for glyph, fn in GLYPHS.items():
            specs.append((f"piece_{team}_{CODE[glyph]}", fn(fill, dark)))
    specs.append(("cell", cell_svg()))
    specs.append(("cell_home_blue", cell_svg(accent=BLUE)))
    specs.append(("cell_home_red", cell_svg(accent=RED)))
    specs.append(("banner", banner_svg()))
    specs.append(("wallpaper", wallpaper_svg()))
    specs.append(("board_bg", board_bg_svg()))
    specs.append(("winner", winner_svg()))
    return specs


# -------------------------------------------------------------------- upload
def sign(params):
    src = "&".join("%s=%s" % (k, params[k]) for k in sorted(params)) + SECRET
    return hashlib.sha1(src.encode()).hexdigest()


def upload(svg_bytes, public_id, folder=FOLDER, resource_type="image",
           filename=None, content_type="image/svg+xml"):
    """Signed upload. invalidate=true or the version-less URL serves a stale copy."""
    ts = str(int(time.time()))
    params = {"folder": folder, "invalidate": "true", "overwrite": "true",
              "public_id": public_id, "timestamp": ts}
    fields = dict(params)
    fields["signature"] = sign(params)
    fields["api_key"] = KEY

    boundary = uuid.uuid4().hex
    body = b""
    for k, v in fields.items():
        body += ('--%s\r\nContent-Disposition: form-data; name="%s"\r\n\r\n%s\r\n'
                 % (boundary, k, v)).encode()
    body += ('--%s\r\nContent-Disposition: form-data; name="file"; filename="%s"\r\n'
             "Content-Type: %s\r\n\r\n"
             % (boundary, filename or (public_id + ".svg"), content_type)).encode()
    body += svg_bytes + b"\r\n"
    body += ("--%s--\r\n" % boundary).encode()

    req = urllib.request.Request(
        "https://api.cloudinary.com/v1_1/%s/%s/upload" % (CLOUD, resource_type),
        data=body, method="POST")
    req.add_header("Content-Type", "multipart/form-data; boundary=" + boundary)
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.load(r)


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def onset_seconds(path):
    """Where the loudest moment of a clip starts.

    Decodes to 8 kHz mono and takes the peak of a 20 ms sliding RMS. Used to
    centre the cut on the actual hit rather than on wherever the file begins.
    """
    import array
    import subprocess
    rate, win = 8000, 160
    pcm = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", path, "-ac", "1", "-ar", str(rate),
         "-f", "s16le", "-"], capture_output=True, check=True).stdout
    samples = array.array("h")
    samples.frombytes(pcm[: len(pcm) - (len(pcm) % 2)])
    if not samples:
        return 0.0
    best, best_i = -1.0, 0
    for i in range(0, max(1, len(samples) - win), win):
        chunk = samples[i:i + win]
        energy = sum(s * s for s in chunk) / len(chunk)
        if energy > best:
            best, best_i = energy, i
    return best_i / rate


def build_sounds(out):
    """Fetch, trim and upload each sound effect. Needs ffmpeg on PATH."""
    import subprocess
    os.makedirs(SVG_DIR, exist_ok=True)
    for spec in SOUNDS:
        alias = spec["alias"]
        raw = os.path.join(SVG_DIR, alias + "_raw")
        clip = os.path.join(SVG_DIR, alias + ".mp3")
        open(raw, "wb").write(fetch(spec["source"]))
        start = max(0.0, onset_seconds(raw) - PRE_ONSET)
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{start:.3f}", "-i", raw,
             "-af", _SFX, "-t", str(CLIP_SECONDS),
             "-ar", "44100", "-ac", "2", "-b:a", "192k", "-codec:a", "libmp3lame",
             clip], check=True)
        data = open(clip, "rb").read()
        upload(data, alias, folder=AUDIO_FOLDER, resource_type="video",
               filename=alias + ".mp3", content_type="audio/mpeg")
        url = f"{AUDIO_BASE}/{AUDIO_FOLDER}/{alias}.mp3"
        # The edge can still be serving the previous upload for a moment, so
        # poll until it matches what we just sent rather than reporting the
        # stale bytes as if they were the new ones.
        want = hashlib.sha1(data).hexdigest()
        for attempt in range(6):
            back = fetch(url)
            if hashlib.sha1(back).hexdigest() == want:
                break
            time.sleep(2)
        else:
            print("  WARNING: %s still stale at the edge after upload" % alias,
                  file=sys.stderr)
        out[alias] = {"url": url, "credit": spec["credit"],
                      "bytes": len(data), "sha1": want[:12],
                      "verified": hashlib.sha1(back).hexdigest() == want}
        print("sound %-10s ok  %6dB  sha %s  served=%s  (%s)"
              % (alias, len(data), want[:12], out[alias]["verified"], spec["credit"]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--local", action="store_true", help="write SVGs, skip upload")
    ap.add_argument("--only", default="", help="comma-separated alias prefixes")
    ap.add_argument("--sounds", action="store_true",
                    help="also (re)build and upload the sound effects")
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
            res = upload(svg.encode(), alias)
            # Serve as .png so the engine never has to deal with SVG itself, and
            # strip the version so a re-upload is picked up (invalidate handles
            # the edge copy).
            url = "%s/%s/%s.png" % (BASE, FOLDER, alias)
            png = fetch(url)
            out[alias] = {"url": url, "sha1": hashlib.sha1(png).hexdigest()[:12],
                          "bytes": len(png)}
            print("[%2d/%d] %-18s ok  %6dB png  sha %s"
                  % (i, len(specs), alias, len(png), out[alias]["sha1"]))
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "ignore")[:200] if e.fp else str(e)
            print("[%2d/%d] %-18s HTTP %s: %s" % (i, len(specs), alias, e.code, detail),
                  file=sys.stderr)
            failures.append(alias)
        except Exception as e:
            print("[%2d/%d] %-18s %s: %s" % (i, len(specs), alias, type(e).__name__, e),
                  file=sys.stderr)
            failures.append(alias)

    if args.sounds:
        build_sounds(out)

    json.dump(out, open(OUT_JSON, "w"), indent=1)
    print("\nwrote %d aliases to %s" % (len(out), OUT_JSON))
    if failures:
        print("FAILURES: %s" % ", ".join(failures), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
