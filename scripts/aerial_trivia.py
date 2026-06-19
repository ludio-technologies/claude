#!/usr/bin/env python3
"""Source aerial landmark photos from Wikimedia Commons, verify locally, then
upload chosen ones to Cloudinary for Ankit's Trivia "aerial shots" round.

Pipeline:
  1. search   -> query Commons File namespace, download top candidate thumbs
                 into ./aerial_candidates/<slug>/<n>.jpg for visual review.
  2. upload   -> given a chosen file per landmark, push to Cloudinary and emit
                 an alias->url JSON ready to drop into round1Questions.
"""
import argparse
import hashlib
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

# --- Cloudinary creds (same account the trivia images already live on) ---
API_KEY    = "721495889677635"
API_SECRET = "uRKz0gw-XsGs4VT3CcndOiFZD24"
CLOUD_NAME = "liars-club"
FOLDER     = "images/zee_trivia/aerial"

HERE = Path(__file__).parent
CAND_DIR = HERE / "aerial_candidates"

# landmark slug -> (display answer, Commons search query)
LANDMARKS = {
    "eiffel":     ("Eiffel Tower",            "aerial Eiffel Tower Paris"),
    "colosseum":  ("Colosseum",               "aerial Colosseum Rome"),
    "giza":       ("Pyramids of Giza",        "aerial Giza pyramids"),
    "opera":      ("Sydney Opera House",      "aerial Sydney Opera House"),
    "taj":        ("Taj Mahal",               "aerial Taj Mahal"),
    "pentagon":   ("The Pentagon",            "aerial The Pentagon Washington"),
    "arc":        ("Arc de Triomphe",         "aerial Arc de Triomphe Paris"),
    "stpeters":   ("St. Peter's Square",      "aerial Saint Peter's Square Vatican"),
    "stonehenge": ("Stonehenge",              "aerial Stonehenge"),
    "forbidden":  ("Forbidden City (Beijing)","aerial Forbidden City Beijing"),
}

UA = {"User-Agent": "ludio-trivia/1.0 (ankit@ludio.gg)"}


def api_get(params: dict) -> dict:
    url = "https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read())


def search_files(query: str, n: int = 6) -> list:
    """Return up to n File: titles matching query in the File namespace."""
    data = api_get({
        "action": "query", "format": "json", "list": "search",
        "srsearch": query, "srnamespace": 6, "srlimit": n,
    })
    return [hit["title"] for hit in data.get("query", {}).get("search", [])]


def imageinfo(title: str, width: int = 900) -> "dict | None":
    data = api_get({
        "action": "query", "format": "json", "prop": "imageinfo",
        "titles": title, "iiprop": "url|mime|size",
        "iiurlwidth": width,
    })
    pages = data.get("query", {}).get("pages", {})
    for p in pages.values():
        info = p.get("imageinfo")
        if info:
            return info[0]
    return None


def fetch(url: str) -> bytes:
    delay = 2.0
    for attempt in range(6):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=90) as resp:
                return resp.read()
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < 5:
                time.sleep(delay)
                delay *= 2
                continue
            raise


def cmd_search(args):
    CAND_DIR.mkdir(exist_ok=True)
    manifest = {}
    for slug, (answer, query) in LANDMARKS.items():
        d = CAND_DIR / slug
        d.mkdir(exist_ok=True)
        titles = search_files(query, n=args.candidates)
        entries = []
        for i, title in enumerate(titles):
            info = imageinfo(title, width=900)
            if not info or "image" not in info.get("mime", ""):
                continue
            thumb = info.get("thumburl") or info.get("url")
            ext = ".jpg"
            fp = d / f"{i}{ext}"
            if not (fp.exists() and fp.stat().st_size > 1000):
                try:
                    data = fetch(thumb)
                except Exception as e:
                    print(f"  ! {slug} #{i} fetch fail: {e}")
                    continue
                fp.write_bytes(data)
                time.sleep(1.0)
            entries.append({
                "idx": i, "title": title,
                "full": info.get("url"), "thumb": thumb,
                "w": info.get("width"), "h": info.get("height"),
                "file": str(fp),
            })
            print(f"  {slug} #{i}: {title}  ({info.get('width')}x{info.get('height')})")
        manifest[slug] = {"answer": answer, "query": query, "candidates": entries}
    (CAND_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print(f"\nWrote {CAND_DIR/'manifest.json'} with candidates for {len(manifest)} landmarks.")


def upload_to_cloudinary(image_bytes: bytes, folder: str, public_id: str) -> dict:
    ts = str(int(time.time()))
    sig_string = f"folder={folder}&overwrite=true&public_id={public_id}&timestamp={ts}{API_SECRET}"
    sig = hashlib.sha1(sig_string.encode()).hexdigest()
    boundary = "----CloudinaryBoundary12345"
    parts = []
    for n, v in [
        ("api_key", API_KEY), ("timestamp", ts), ("folder", folder),
        ("overwrite", "true"), ("public_id", public_id), ("signature", sig),
    ]:
        parts.append(f"--{boundary}\r\n".encode())
        parts.append(f'Content-Disposition: form-data; name="{n}"\r\n\r\n'.encode())
        parts.append(f"{v}\r\n".encode())
    parts.append(f"--{boundary}\r\n".encode())
    parts.append(f'Content-Disposition: form-data; name="file"; filename="{public_id}.jpg"\r\n'.encode())
    parts.append(b"Content-Type: image/jpeg\r\n\r\n")
    parts.append(image_bytes)
    parts.append(b"\r\n")
    parts.append(f"--{boundary}--\r\n".encode())
    body = b"".join(parts)
    req = urllib.request.Request(
        f"https://api.cloudinary.com/v1_1/{CLOUD_NAME}/image/upload",
        data=body, method="POST")
    req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read())


def cmd_upload(args):
    """choices: JSON file mapping slug -> candidate idx to upload."""
    manifest = json.loads((CAND_DIR / "manifest.json").read_text())
    choices = json.loads(Path(args.choices).read_text())
    out = {}
    for slug, idx in choices.items():
        entry = manifest[slug]
        cand = next(c for c in entry["candidates"] if c["idx"] == idx)
        # upload a generous-width render for quality
        info_url = cand["full"]
        img = fetch(info_url)
        res = upload_to_cloudinary(img, FOLDER, slug)
        url = res["secure_url"]
        out[slug] = {"answer": entry["answer"], "url": url}
        print(f"  uploaded {slug}: {url}")
    (CAND_DIR / "uploaded.json").write_text(json.dumps(out, indent=2))
    print(f"\nWrote {CAND_DIR/'uploaded.json'}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("search"); s.add_argument("--candidates", type=int, default=5)
    u = sub.add_parser("upload"); u.add_argument("--choices", required=True)
    args = ap.parse_args()
    {"search": cmd_search, "upload": cmd_upload}[args.cmd](args)
