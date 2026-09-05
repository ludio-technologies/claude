#!/usr/bin/env python3
"""Turn a trivia question bank into the two Ludio game setups.

  python3 trivia/build_trivia.py                 # build + validate, write files
  python3 trivia/build_trivia.py --deploy fri    # also PATCH that night to prod
  python3 trivia/build_trivia.py --deploy both

Reads  trivia/questions_<batch>.json   (the question bank - the only file a
                                        writer should ever edit)
       trivia/assets_<batch>.json      (uploaded asset dimensions)
Writes game_jsons/ankits_<night>_trivia_<batch>.json

The game loop is patched IDEMPOTENTLY on top of whatever is live, so this can
be run any number of times without stacking edits.
"""
import argparse, copy, json, os, subprocess, sys, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
BATCH = "132"

IMG_BASE = "https://res.cloudinary.com/liars-club/image/upload"
AUD_BASE = "https://res.cloudinary.com/liars-club/video/upload"
PROD = "https://try.ludio.gg/api/setup/"
STAGING = "https://ptr.ludio.gg/api/setup/"

# Copy that names the night. Carried over from whatever setup is being written
# to, so a staging deploy keeps saying "Friday Night Trivia" rather than
# inheriting production's wording.
TITLE_STRINGS = ("welcomeToAnkitS", "ankitSTriviaNight")
PLACEHOLDER = "https://res.cloudinary.com/liars-club/image/upload/questions_gnh6cx.jpg"


# --------------------------------------------------------------- asset URLs
def img_url(bank, assets, slug, negate=False, w=1200):
    """Compose a delivery URL.

    Two Cloudinary rules are load-bearing here:
      * e_negate must be its OWN component - combined with e_sharpen in one
        component only one effect survives and the negate is silently dropped.
      * the resize must come FIRST - the effect has a ~25MP ceiling and the
        largest source portrait is over it, which returns HTTP 400.
    """
    a = assets.get(slug) or {}
    small = a.get("w") and a.get("h") and (a["w"] < 700 or a["h"] < 700)
    comps = ["w_%d,c_scale,e_sharpen:60" % w if small else "w_%d,c_limit" % w]
    if negate:
        comps.append("e_negate")
    return "%s/%s/%s/%s.jpg" % (IMG_BASE, "/".join(comps), bank["images_folder"], slug)


def aud_url(bank, slug):
    return "%s/%s/%s.mp3" % (AUD_BASE, bank["audio_folder"], slug)


# ------------------------------------------------------------- question data
def rounds_for(bank, assets, night):
    """-> (list of 5 question lists, soundboard entries, categoryMapping)."""
    out, sounds, mapping = [], {}, {}
    for rnd in sorted(bank["rounds"], key=lambda r: r["round"]):
        key = "round%dQuestions" % rnd["round"]
        mapping[rnd["category"]] = key
        items = []
        for q in rnd["questions"]:
            if q["night"] != night:
                continue
            item = {"q": q["q"], "answer": q["answer"]}
            if q.get("image"):
                item["i"] = img_url(bank, assets, q["image"],
                                    negate=bool(q.get("image_negate")))
            if q.get("answer_image"):
                item["iA"] = img_url(bank, assets, q["answer_image"])
            if q.get("audio"):
                item["a"] = "soundboard." + q["audio"]
                sounds[q["audio"]] = aud_url(bank, q["audio"])
            if q.get("audio_short"):
                item["a5"] = "soundboard." + q["audio_short"]
                sounds[q["audio_short"]] = aud_url(bank, q["audio_short"])
            items.append(item)
        if len(items) != 10:
            raise SystemExit("round %d (%s) has %d questions for %s, expected 10"
                             % (rnd["round"], rnd["category"], len(items), night))
        out.append((key, items))
    return out, sounds, mapping


# -------------------------------------------------------------- loop patching
def patch_loop(raw):
    """Wire the optional `iA` (answer image) field. Safe to re-run.

    createVote supports only the SINGULAR `image` field - it has no `images`.
    So the grading vote keeps `image` and simply points at a new cache var that
    resolves iA -> i -> placeholder.
    """
    gl = raw["gameLoop"]
    notes = []

    svc = gl[11][0]["actions"][0]["saveValueInCache"]
    if not any(s.get("name") == "currentAnswerImage" for s in svc):
        idx = next(i for i, s in enumerate(svc) if s.get("name") == "currentImage")
        svc.insert(idx + 1, {
            "name": "currentAnswerImage",
            "value": {"selector": "getCachedObjectValue", "params": [
                {"name": "objectName", "type": "preset", "value": "currentItem"},
                {"name": "value", "type": "preset", "value": "iA"},
                {"name": "defaultValue", "type": "cached", "value": "currentImage"},
            ]},
        })
        notes.append("added currentAnswerImage")

    cached = gl[11][1]["actions"][0]["payload"]["cached"]
    cached.pop("images", None)                 # never valid on a createVote
    if cached.get("image") != "currentAnswerImage":
        cached["image"] = "currentAnswerImage"
        notes.append("grading vote -> currentAnswerImage")

    # the question-side votes must keep the plain question image
    for path, act in (("10[0].a2", gl[10][0]["actions"][2]),
                      ("10[0].a7", gl[10][0]["actions"][7]),
                      ("10[2].a0", gl[10][2]["actions"][0])):
        c = act["payload"]["cached"]
        c.pop("images", None)
        if c.get("image") != "currentImage":
            c["image"] = "currentImage"
            notes.append("%s -> currentImage" % path)

    # currentImage must fall back to the placeholder URL, not an alias
    for stage in (gl[10][0]["actions"][0], gl[11][0]["actions"][0]):
        for s in stage["saveValueInCache"]:
            if s.get("name") == "currentImage":
                for p in s["value"]["params"]:
                    if p["name"] == "defaultValue" and p["value"] != PLACEHOLDER:
                        p["value"] = PLACEHOLDER
                        notes.append("currentImage default restored")
    return notes or ["already wired"]


# ---------------------------------------------------------------------- build
def get(url):
    with urllib.request.urlopen(url, timeout=180) as r:
        return json.load(r)


def build(bank, assets, night):
    setup = bank["setups"][night]
    live = get(PROD + setup["id"])
    raw = copy.deepcopy(live["raw"])

    rounds, sounds, mapping = rounds_for(bank, assets, night)
    d = raw["gameInitOptions"]["strings"]["Default"]
    for key, items in rounds:
        d[key] = items
    d["categoryMapping"] = mapping

    sb = raw["gameInitOptions"]["soundboard"]["default"]
    for k in [k for k in list(sb) if k.startswith(("tv_", "ms_"))]:
        del sb[k]
    sb.update(sounds)

    notes = patch_loop(raw)
    return raw, notes, setup


def validate(path):
    """-> (raw output, n_errors, n_warnings) parsed from the summary lines."""
    import re
    v = os.path.join(REPO, "documentation", "validate_game_json.py")
    r = subprocess.run([sys.executable, v, path], capture_output=True)
    out = r.stdout.decode()
    err = warn = 0
    for line in out.splitlines():
        m = re.match(r"✗ (\d+) error", line)
        if m:
            err = int(m.group(1))
        m = re.match(r"⚠ (\d+) warning", line)
        if m:
            warn = int(m.group(1))
    return out, err, warn


def patch(url, body):
    req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"},
                                 method="PATCH")
    with urllib.request.urlopen(req, timeout=300) as r:
        return r.status


def deploy(raw, base, setup_id):
    """Write `raw` to a setup, keeping that setup's own night-name copy."""
    url = base + setup_id
    current = get(url)["raw"]
    payload = copy.deepcopy(raw)
    src = current["gameInitOptions"]["strings"]["Default"]
    dst = payload["gameInitOptions"]["strings"]["Default"]
    for k in TITLE_STRINGS:
        if k in src:
            dst[k] = src[k]
    status = patch(url, {"raw": payload})
    back = get(url)["raw"]
    same = json.dumps(back, sort_keys=True) == json.dumps(payload, sort_keys=True)
    return status, same


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--deploy", choices=["fri", "sat", "both"], default=None,
                    help="Deploy that night. Goes to STAGING unless --prod.")
    ap.add_argument("--prod", action="store_true",
                    help="Deploy to PRODUCTION instead of staging. "
                         "Ankit only - never run this without his go-ahead.")
    ap.add_argument("--batch", default=BATCH)
    args = ap.parse_args()

    bank = json.load(open("%s/questions_%s.json" % (HERE, args.batch)))
    assets = json.load(open("%s/assets_%s.json" % (HERE, args.batch)))

    for night in ("fri", "sat"):
        raw, notes, setup = build(bank, assets, night)
        path = "%s/game_jsons/ankits_%s_trivia_%s.json" % (
            REPO, {"fri": "friday", "sat": "saturday"}[night], args.batch)
        json.dump(raw, open(path, "w"), indent=1)

        _out, errs, warns = validate(path)
        d = raw["gameInitOptions"]["strings"]["Default"]
        n_ia = sum(1 for r in range(1, 9)
                   for q in d.get("round%dQuestions" % r, []) if "iA" in q)
        live_raw = get(PROD + setup["id"])["raw"]
        drift = json.dumps(live_raw, sort_keys=True) != json.dumps(raw, sort_keys=True)
        print("=== %s  (%s)" % (setup["name"], night))
        print("    loop: %s" % "; ".join(notes))
        print("    categories: %s" % list(d["categoryMapping"]))
        print("    answer-images (iA): %d | validator: %d error(s), %d warning(s)"
              % (n_ia, errs, warns))
        print("    differs from what is live: %s" % ("YES" if drift else "no"))
        print("    wrote %s" % os.path.relpath(path, REPO))

        if args.deploy in (night, "both"):
            if args.prod:
                status, same = deploy(raw, PROD, setup["id"])
                where = "PRODUCTION  %s" % setup["name"]
            else:
                status, same = deploy(raw, STAGING, setup["staging_id"])
                where = "staging     %s" % setup["staging_name"]
            print("    DEPLOYED -> %s | HTTP %s | verified: %s" % (where, status, same))
        else:
            print("    not deployed (--deploy %s for staging, add --prod for live)"
                  % night)


if __name__ == "__main__":
    main()
