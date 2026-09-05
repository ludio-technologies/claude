#!/usr/bin/env python3
"""Push Emperor's deck and setup to Ludio.

  python3 scripts/emperor/deploy.py --deck-only          # staging deck only
  python3 scripts/emperor/deploy.py --setup <setup-id>   # deck + setup
  python3 scripts/emperor/deploy.py --setup <id> --prod  # production

The deck half is fully scriptable: POST /api/deck creates one outright. The setup
half is NOT — Ludio has no create endpoint for setups, so a new game has to be
made by hitting **Copy** on any existing row at https://ptr.ludio.gg/admin/setups
(admin login; the page is not linked from the Games list). Snapshot GET /api/setup
before and after the click to find the new id, then pass it here with --setup.

Deck ids differ per host and setups have a DIFFERENT id on staging and
production, so never reuse one across hosts.
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
GJ = os.path.join(HERE, "..", "..", "game_jsons")
STAGING = "https://ptr.ludio.gg"
PROD = "https://try.ludio.gg"


def req(url, body=None, method="GET"):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(
        url, data=data, method=method,
        headers={"Content-Type": "application/json"} if data else {})
    with urllib.request.urlopen(r, timeout=120) as resp:
        raw = resp.read()
        return resp.status, (json.loads(raw) if raw else None)


def find_deck(host, script_name):
    """The list endpoint returns no top-level name, so match on script.name.
    GET /api/deck/<id> 500s, which is why this reads out of the list."""
    _, decks = req(host + "/api/deck")
    for d in decks:
        if (d.get("script") or {}).get("name") == script_name:
            return d["id"]
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--setup", help="setup id on the target host")
    ap.add_argument("--deck-only", action="store_true")
    ap.add_argument("--prod", action="store_true")
    args = ap.parse_args()

    host = PROD if args.prod else STAGING
    if args.prod:
        print("*** PRODUCTION (%s) ***" % host)

    cards = json.load(open(os.path.join(GJ, "emperor_cards.json")))
    raw = json.load(open(os.path.join(GJ, "emperor.json")))
    desc = json.load(open(os.path.join(GJ, "emperor_describe.json")))

    deck_id = find_deck(host, cards["name"])
    if deck_id:
        status, _ = req("%s/api/deck/%s" % (host, deck_id), {"script": cards}, "PATCH")
        print("deck PATCH %s -> %s" % (deck_id, status))
    else:
        status, made = req(host + "/api/deck", {"name": cards["name"], "script": cards}, "POST")
        deck_id = (made or {}).get("id")
        print("deck POST -> %s  id=%s" % (status, deck_id))

    # Read the deck back off the LIST (the by-id GET 500s) and prove it landed.
    check = None
    _, decks = req(host + "/api/deck")
    for d in decks:
        if d["id"] == deck_id:
            check = d["script"]
    if not check:
        sys.exit("deck did not read back from %s" % host)
    print("  %d card types, %d cards in 'full', jester=%s"
          % (len(check["cards"]), sum(check["sets"]["full"].values()),
             check["sets"]["full"].get("jester")))

    if args.deck_only:
        return
    if not args.setup:
        sys.exit("no --setup id. Copy a setup at %s/admin/setups first "
                 "(there is no create endpoint), then re-run with its id." % host)

    body = {"name": desc["name"], "banner": desc["banner"],
            "description": desc["description"], "rules": desc["rules"],
            "tags": desc["tags"], "raw": raw, "settings": []}
    status, _ = req("%s/api/setup/%s" % (host, args.setup), body, "PATCH")
    print("setup PATCH %s -> %s" % (args.setup, status))

    _, live = req("%s/api/setup/%s" % (host, args.setup))
    same = json.dumps(live.get("raw"), sort_keys=True) == json.dumps(raw, sort_keys=True)
    print("  name: %s | raw matches: %s" % (live.get("name"), same))
    if not same:
        sys.exit("setup raw did not match what was sent")


if __name__ == "__main__":
    main()
