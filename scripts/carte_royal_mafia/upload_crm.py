import hashlib, json, time, os, glob
import urllib.request, urllib.error

API_KEY    = "721495889677635"
API_SECRET = "uRKz0gw-XsGs4VT3CcndOiFZD24"
CLOUD_NAME = "liars-club"
FOLDER     = "images/carte_royal_mafia"

def upload(image_bytes, folder, public_id, ext="png"):
    ts = str(int(time.time()))
    # signed params, alphabetical
    sig_string = (f"folder={folder}&invalidate=true&overwrite=true"
                  f"&public_id={public_id}&timestamp={ts}{API_SECRET}")
    sig = hashlib.sha1(sig_string.encode()).hexdigest()
    boundary = "----CRMBoundary98765"
    parts = []
    for n, v in [("api_key", API_KEY), ("timestamp", ts), ("folder", folder),
                 ("invalidate", "true"), ("overwrite", "true"),
                 ("public_id", public_id), ("signature", sig)]:
        parts.append(f"--{boundary}\r\n".encode())
        parts.append(f'Content-Disposition: form-data; name="{n}"\r\n\r\n'.encode())
        parts.append(f"{v}\r\n".encode())
    parts.append(f"--{boundary}\r\n".encode())
    parts.append(f'Content-Disposition: form-data; name="file"; filename="{public_id}.{ext}"\r\n'.encode())
    parts.append(f"Content-Type: image/{'jpeg' if ext=='jpg' else 'png'}\r\n\r\n".encode())
    parts.append(image_bytes)
    parts.append(b"\r\n")
    parts.append(f"--{boundary}--\r\n".encode())
    body = b"".join(parts)
    req = urllib.request.Request(
        f"https://api.cloudinary.com/v1_1/{CLOUD_NAME}/image/upload",
        data=body, method="POST")
    req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                res = json.loads(resp.read())
            secure = res.get("secure_url", res.get("url", ""))
            return secure.replace(f"/upload/v{res['version']}/", "/upload/")
        except urllib.error.HTTPError as e:
            if attempt == 2:
                raise
            time.sleep(3)

def main():
    # 1. cards
    cards = sorted(glob.glob("/tmp/crm_cards_new/*.png"))
    print(f"Uploading {len(cards)} cards...")
    for i, p in enumerate(cards, 1):
        pid = os.path.splitext(os.path.basename(p))[0]
        url = upload(open(p, "rb").read(), FOLDER, pid, "png")
        print(f"[{i}/{len(cards)}] {pid} -> {url}")
    # 2. wallpaper (new public_id)
    wp_url = upload(open("/tmp/crm_wallpaper_new.jpg", "rb").read(),
                    FOLDER, "wallpaper_speakeasy", "jpg")
    print("WALLPAPER ->", wp_url)

if __name__ == "__main__":
    main()
