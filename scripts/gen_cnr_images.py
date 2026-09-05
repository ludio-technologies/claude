"""Generate all Cops & Robbers (CNR) image aliases.

For each image:
1. Build a Cloudinary transformation URL (text + icon overlays).
2. Fetch the rendered PNG.
3. Upload to Cloudinary's images/cnr/ folder with a clean public_id.

Final output: a JSON map of {alias: {url: stable_url}} ready to drop into
gameInitOptions.images.

Run: python3 gen_cnr_images.py [--limit N]
"""
import argparse
import base64
import hashlib
import json
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

API_KEY    = "721495889677635"
API_SECRET = "uRKz0gw-XsGs4VT3CcndOiFZD24"
CLOUD_NAME = "liars-club"
FOLDER     = "images/cnr"

BASE_URL = f"https://res.cloudinary.com/{CLOUD_NAME}/image/upload"
TRANSPARENT = "transparent_sbx4wv.png"

# --- Color palette ---
COLORS = {
    "red":    "e53935",
    "blue":   "2e5ba8",
    "green":  "2e8b57",
    "black":  "000000",
    "brown":  "8b4513",
    "grey":   "808080",
    "purple": "6a0dad",
    "orange": "ff8c00",
}

ROBBERS = [
    ("red",   "Tomato Tornado"),
    ("blue",  "Blueberry Bandito"),
    ("green", "Pickle Plunderer"),
]

COPS = [
    ("black",  "Officer Inkwell"),
    ("brown",  "Detective Donut"),
    ("grey",   "Officer Overcast"),
    ("purple", "Detective Royal-Pain"),
    ("orange", "Officer Sherbet"),
]

SPECIALS = [
    ("getaway",    "GETAWAY CAR", "Move 2 cells",          "sedan"),
    ("backstreet", "BACKSTREET",  "Teleport within block", "shortcut"),
    ("speedboat",  "SPEEDBOAT",   "Teleport on water",     "yacht"),
]


# --- Helpers ---
def b64(s: str) -> str:
    return base64.b64encode(s.encode()).decode()


def url_encode_text(s: str) -> str:
    return s.replace(" ", "%20").replace(",", "%2C").replace("&", "%26")


# --- URL builders ---
def coord_url(label: str) -> str:
    """400x400 square, dark slate bg, off-white centered label."""
    return (f"{BASE_URL}/w_400,h_400,c_pad,b_rgb:3a3a3a"
            f"/l_text:Arial_180_bold:{label},co_rgb:f5f5dc,g_center"
            f"/{TRANSPARENT}")


def counter_url(n: int, robbers: int) -> str:
    """400x400 circular tile, parchment bg, big number + red dots."""
    parts = [f"{BASE_URL}/w_400,h_400,c_pad,b_rgb:e8dcc4,r_max"]
    parts.append(f"/l_text:Arial_200_bold:{n},co_rgb:2a1810,g_north,y_70")
    if robbers > 0:
        dots = "%E2%80%A2" * robbers
        parts.append(f"/l_text:Arial_90_bold:{dots},co_rgb:b22222,g_south,y_70")
    parts.append(f"/{TRANSPARENT}")
    return "".join(parts)


def robber_url(name: str, color_hex: str) -> str:
    """500x800 wanted poster, parchment with role-color border + name."""
    icon = b64("https://img.icons8.com/ios-filled/300/3A1810/robber.png")
    name_url = url_encode_text(name)
    return (f"{BASE_URL}/w_500,h_800,c_pad,b_rgb:d4b896,bo_25px_solid_rgb:{color_hex}"
            f"/l_fetch:{icon},w_260,g_center,y_-30"
            f"/l_text:Georgia_100_bold:WANTED,co_rgb:3a1810,g_north,y_110"
            f"/l_text:Georgia_42_bold:{name_url},co_rgb:{color_hex},g_south,y_180"
            f"/l_text:Georgia_36_italic:THE%20ROBBER,co_rgb:3a1810,g_south,y_110"
            f"/{TRANSPARENT}")


def cop_url(name: str, color_hex: str) -> str:
    """500x800 police bulletin, parchment with role-color border + name."""
    icon = b64(f"https://img.icons8.com/ios-filled/300/{color_hex}/police-badge.png")
    name_url = url_encode_text(name)
    return (f"{BASE_URL}/w_500,h_800,c_pad,b_rgb:e8e0d0,bo_25px_solid_rgb:{color_hex}"
            f"/l_fetch:{icon},w_260,g_center,y_-30"
            f"/l_text:Georgia_85_bold:POLICE,co_rgb:{color_hex},g_north,y_70"
            f"/l_text:Georgia_45_bold:BULLETIN,co_rgb:{color_hex},g_north,y_175"
            f"/l_text:Georgia_42_bold:{name_url},co_rgb:{color_hex},g_south,y_180"
            f"/l_text:Georgia_36_italic:DETECTIVE,co_rgb:{color_hex},g_south,y_110"
            f"/{TRANSPARENT}")


def investigate_url() -> str:
    icon = b64("https://img.icons8.com/ios-filled/300/FFFFFF/search.png")
    return (f"{BASE_URL}/w_500,h_800,c_pad,b_rgb:1c3a5e"
            f"/l_fetch:{icon},w_280,g_center,y_-120"
            f"/l_text:Arial_62_bold:INVESTIGATE,co_white,g_center,y_180"
            f"/l_text:Arial_36:Question%20witnesses,co_rgb:c8d4e8,g_south,y_90"
            f"/{TRANSPARENT}")


def bust_url() -> str:
    icon = b64("https://img.icons8.com/ios-filled/300/FFFFFF/handcuffs.png")
    return (f"{BASE_URL}/w_500,h_800,c_pad,b_rgb:7a0a0a"
            f"/l_fetch:{icon},w_280,g_center,y_-120"
            f"/l_text:Arial_90_bold:BUST,co_white,g_center,y_180"
            f"/l_text:Arial_36:Arrest%20suspect,co_rgb:e8d4d4,g_south,y_90"
            f"/{TRANSPARENT}")


def stash_url(name: str, color_hex: str) -> str:
    icon = b64("https://img.icons8.com/ios-filled/200/FFFFFF/money-bag.png")
    name_url = url_encode_text(name)
    return (f"{BASE_URL}/w_400,h_400,c_pad,b_rgb:{color_hex}"
            f"/l_fetch:{icon},w_180,g_center,y_-20"
            f"/l_text:Arial_55_bold:STASH,co_white,g_north,y_30"
            f"/l_text:Arial_30:{name_url},co_rgb:f5e8c4,g_south,y_30"
            f"/{TRANSPARENT}")


def special_url(name: str, tagline: str, icon_name: str) -> str:
    icon = b64(f"https://img.icons8.com/ios-filled/300/f5d76e/{icon_name}.png")
    name_url = url_encode_text(name)
    tagline_url = url_encode_text(tagline)
    return (f"{BASE_URL}/w_500,h_800,c_pad,b_rgb:2a1810"
            f"/l_fetch:{icon},w_290,g_center,y_-120"
            f"/l_text:Arial_60_bold:{name_url},co_rgb:f5d76e,g_center,y_180"
            f"/l_text:Arial_36:{tagline_url},co_white,g_south,y_90"
            f"/{TRANSPARENT}")


# --- Build the full list of (alias, dynamic_url) ---
# Cell coords cover the MAX grid for any player count: 10 cols (A..J) × 7 rows.
MAX_COLS_LETTERS = "ABCDEFGHIJ"
MAX_ROWS = 7


def build_specs():
    specs = []

    # 1. Coord cells: A1..J7 (70)
    for col_letter in MAX_COLS_LETTERS:
        for row in range(1, MAX_ROWS + 1):
            label = f"{col_letter}{row}"
            specs.append((f"coord_{label}", coord_url(label)))

    # 2. Counter circles: 1..15 turns x 0..3 robbers (60)
    for n in range(1, 16):
        for r in range(0, 4):
            specs.append((f"counter_{n}_R{r}", counter_url(n, r)))

    # 3. Robber wanted posters (3)
    for slug, name in ROBBERS:
        specs.append((f"robber_{slug}", robber_url(name, COLORS[slug])))

    # 4. Cop bulletins (5)
    for slug, name in COPS:
        specs.append((f"cop_{slug}", cop_url(name, COLORS[slug])))

    # 5. Action cards (2)
    specs.append(("action_investigate", investigate_url()))
    specs.append(("action_bust", bust_url()))

    # 6. Stash cards (3)
    for slug, name in ROBBERS:
        specs.append((f"stash_{slug}", stash_url(name, COLORS[slug])))

    # 7. Special movement cards (3)
    for slug, name, tagline, icon in SPECIALS:
        specs.append((f"special_{slug}", special_url(name, tagline, icon)))

    return specs


# --- Cloudinary upload ---
def upload_to_cloudinary(image_bytes: bytes, folder: str, public_id: str) -> dict:
    ts = str(int(time.time()))
    # invalidate=true purges the CDN copy. We serve version-less URLs, so an
    # overwrite without it leaves the old picture cached at the edge.
    sig_string = (f"folder={folder}&invalidate=true&overwrite=true"
                  f"&public_id={public_id}&timestamp={ts}{API_SECRET}")
    sig = hashlib.sha1(sig_string.encode()).hexdigest()
    boundary = "----CloudinaryBoundary12345"
    parts = []
    for n, v in [
        ("api_key", API_KEY),
        ("timestamp", ts),
        ("folder", folder),
        ("invalidate", "true"),
        ("overwrite", "true"),
        ("public_id", public_id),
        ("signature", sig),
    ]:
        parts.append(f"--{boundary}\r\n".encode())
        parts.append(f'Content-Disposition: form-data; name="{n}"\r\n\r\n'.encode())
        parts.append(f"{v}\r\n".encode())
    parts.append(f"--{boundary}\r\n".encode())
    parts.append(f'Content-Disposition: form-data; name="file"; filename="{public_id}.png"\r\n'.encode())
    parts.append(b"Content-Type: image/png\r\n\r\n")
    parts.append(image_bytes)
    parts.append(b"\r\n")
    parts.append(f"--{boundary}--\r\n".encode())
    body = b"".join(parts)
    req = urllib.request.Request(
        f"https://api.cloudinary.com/v1_1/{CLOUD_NAME}/image/upload",
        data=body,
        method="POST",
    )
    req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read())


def fetch_url(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read()


# --- Main ---
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0,
                    help="Process only the first N specs (0 = all)")
    ap.add_argument("--out", type=str,
                    default=str(Path(__file__).parent / "cnr_images.json"),
                    help="Path to write the alias→URL JSON")
    ap.add_argument("--force", action="store_true",
                    help="Re-upload aliases that already exist in the output JSON")
    ap.add_argument("--only", type=str, default="",
                    help="Comma-separated prefixes to filter specs (e.g. 'coord_I,coord_J')")
    args = ap.parse_args()

    out_path = Path(args.out)
    existing = {}
    if out_path.exists():
        try:
            existing = json.loads(out_path.read_text())
        except Exception:
            existing = {}

    specs = build_specs()
    if args.only:
        prefixes = tuple(p.strip() for p in args.only.split(",") if p.strip())
        specs = [s for s in specs if s[0].startswith(prefixes)]
    if not args.force:
        specs = [s for s in specs if s[0] not in existing]
    if args.limit:
        specs = specs[: args.limit]
    total = len(specs)
    print(f"Generating + uploading {total} images (existing: {len(existing)})...")

    out = dict(existing)
    failures = []
    for i, (alias, dyn_url) in enumerate(specs, 1):
        try:
            img_bytes = fetch_url(dyn_url)
            res = upload_to_cloudinary(img_bytes, FOLDER, alias)
            secure = res.get("secure_url", res.get("url", ""))
            stripped = secure.replace(f"/upload/v{res['version']}/", "/upload/")
            out[alias] = {"url": stripped}
            print(f"[{i}/{total}] {alias} -> OK ({len(img_bytes)} bytes)")
        except urllib.error.HTTPError as e:
            err = e.read().decode("utf-8", errors="ignore")[:200] if e.fp else str(e)
            print(f"[{i}/{total}] {alias} -> HTTP {e.code}: {err}", file=sys.stderr)
            failures.append((alias, dyn_url, str(e)))
        except Exception as e:
            print(f"[{i}/{total}] {alias} -> ERROR {type(e).__name__}: {e}", file=sys.stderr)
            failures.append((alias, dyn_url, str(e)))

    out_path.write_text(json.dumps(out, indent=2) + "\n")
    print(f"\nWrote {len(out)} aliases to {out_path}")
    if failures:
        print(f"FAILURES: {len(failures)}", file=sys.stderr)
        for alias, _, err in failures[:10]:
            print(f"  {alias}: {err}", file=sys.stderr)


if __name__ == "__main__":
    main()
