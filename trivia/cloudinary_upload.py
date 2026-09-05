# -*- coding: utf-8 -*-
"""Upload trivia_132 assets to Cloudinary.

Images -> images/zee_trivia/trivia_BATCH/<slug>   (resource_type image)
Audio  -> audio/zee_trivia/trivia_BATCH/<slug>    (resource_type video, as .mp3)

Always signs invalidate=true: version-less delivery URLs otherwise keep serving
a stale edge copy (see the notes in scripts/invalidate_cloudinary.py).
"""
import hashlib, json, mimetypes, os, sys, time, urllib.request, uuid

S = os.path.dirname(os.path.abspath(__file__))
CLOUD = "liars-club"
KEY = "721495889677635"
SECRET = "uRKz0gw-XsGs4VT3CcndOiFZD24"

IMG_FOLDER = "images/zee_trivia/trivia_BATCH"
AUD_FOLDER = "audio/zee_trivia/trivia_BATCH"


def sign(params):
    src = "&".join("%s=%s" % (k, params[k]) for k in sorted(params)) + SECRET
    return hashlib.sha1(src.encode()).hexdigest()


def post(resource_type, path, public_id):
    ts = str(int(time.time()))
    params = {"invalidate": "true", "overwrite": "true",
              "public_id": public_id, "timestamp": ts}
    fields = dict(params)
    fields["signature"] = sign(params)
    fields["api_key"] = KEY

    boundary = uuid.uuid4().hex
    body = b""
    for k, v in fields.items():
        body += ("--%s\r\nContent-Disposition: form-data; name=\"%s\"\r\n\r\n%s\r\n"
                 % (boundary, k, v)).encode()
    fname = os.path.basename(path)
    ctype = mimetypes.guess_type(fname)[0] or "application/octet-stream"
    body += ("--%s\r\nContent-Disposition: form-data; name=\"file\"; filename=\"%s\"\r\n"
             "Content-Type: %s\r\n\r\n" % (boundary, fname, ctype)).encode()
    body += open(path, "rb").read() + b"\r\n"
    body += ("--%s--\r\n" % boundary).encode()

    url = "https://api.cloudinary.com/v1_1/%s/%s/upload" % (CLOUD, resource_type)
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "multipart/form-data; boundary=" + boundary)
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.load(r)


def main():
    what = sys.argv[1] if len(sys.argv) > 1 else "all"
    out = {}
    if os.path.exists(S + "/uploaded.json"):
        out = json.load(open(S + "/uploaded.json"))

    if what in ("all", "images"):
        resolved = json.load(open(S + "/resolved.json"))
        for slug in sorted(resolved, key=lambda k: (k.rsplit("_", 1)[0], int(k.rsplit("_", 1)[1]))):
            r = resolved[slug]
            if not r or not os.path.exists(r["raw"]):
                print("%-10s SKIP (no file)" % slug)
                continue
            pid = "%s/%s" % (IMG_FOLDER, slug)
            try:
                res = post("image", r["raw"], pid)
            except Exception as e:
                print("%-10s UPLOAD FAIL %s" % (slug, e))
                continue
            out[slug] = {"url": res["secure_url"], "public_id": res["public_id"],
                         "w": res.get("width"), "h": res.get("height"),
                         "bytes": res.get("bytes"), "format": res.get("format")}
            print("%-10s %5sx%-5s %8sB  %s" % (slug, res.get("width"), res.get("height"),
                                               res.get("bytes"), res["public_id"]))

    if what in ("all", "audio"):
        adir = S + "/audio_out"
        files = sorted(os.listdir(adir), key=lambda f: (len(f), f)) if os.path.isdir(adir) else []
        for f in files:
            if not f.endswith(".mp3"):
                continue
            slug = f[:-4]
            pid = "%s/%s" % (AUD_FOLDER, slug)
            try:
                res = post("video", adir + "/" + f, pid)
            except Exception as e:
                print("%-12s UPLOAD FAIL %s" % (slug, e))
                continue
            out[slug] = {"url": res["secure_url"], "public_id": res["public_id"],
                         "bytes": res.get("bytes"), "duration": res.get("duration")}
            print("%-12s %5.1fs %8sB  %s" % (slug, res.get("duration") or 0,
                                             res.get("bytes"), res["public_id"]))

    json.dump(out, open(S + "/uploaded.json", "w"), indent=1)
    print("\ntotal uploaded records:", len(out))


if __name__ == "__main__":
    main()
