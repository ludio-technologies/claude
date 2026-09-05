#!/usr/bin/env python3
"""Push the split-draw-pile Squaffle to STAGING (ptr.ludio.gg).

The deck is published as `squaffle_cards_v2`, a NEW deck — the deck store is shared
with try.ludio.gg and production's one-pile game still reads `squaffle_cards`. Nothing
here touches production.

    python3 deploy_staging.py            # dry run: report what would change
    python3 deploy_staging.py --push     # create/update the deck, then PATCH the setup
"""
import json, sys, urllib.request

HOST = "https://ptr.ludio.gg"
SETUP_ID = "1037e0f8-94a9-4780-8921-54dbdf7164d9"        # Squaffle on staging
G = "/Users/ankitbuddhiraju/Documents/claude/Code/game_jsons/"
DECK_NAME = "squaffle_cards_v2"

def req(url, body=None, method="GET"):
    r = urllib.request.Request(
        url, data=json.dumps(body).encode() if body is not None else None,
        headers={"Content-Type": "application/json"}, method=method)
    with urllib.request.urlopen(r, timeout=90) as resp:
        raw = resp.read()
        return resp.status, (json.loads(raw) if raw else None)

def find_deck(name):
    _, decks = req(f"{HOST}/api/deck")
    hits = [d for d in decks if (d.get("script") or {}).get("name") == name]
    assert len(hits) < 2, f"{len(hits)} decks named {name}"
    return hits[0] if hits else None

def main():
    push = "--push" in sys.argv
    cards = json.load(open(G + "squaffle_cards.json"))
    raw = json.load(open(G + "squaffle.json"))
    desc = json.load(open(G + "squaffle_describe.json"))
    assert cards["name"] == DECK_NAME, cards["name"]

    _, setup = req(f"{HOST}/api/setup/{SETUP_ID}")
    print(f"staging setup: {setup['name']!r} ({SETUP_ID})")
    print("  raw already current:",
          json.dumps(setup.get("raw"), sort_keys=True) == json.dumps(raw, sort_keys=True))

    existing = find_deck(DECK_NAME)
    print(f"deck {DECK_NAME}:", "exists " + existing["id"] if existing else "does not exist yet")
    if not push:
        print("\n(dry run — pass --push to deploy)")
        return

    # 1. the deck first: the setup's createDeck resolves it by name at game start
    if existing:
        st, _ = req(f"{HOST}/api/deck/{existing['id']}", {"script": cards}, "PATCH")
        print("deck PATCH:", st)
    else:
        st, _ = req(f"{HOST}/api/deck", {"name": DECK_NAME, "script": cards}, "POST")
        print("deck POST:", st)

    # 2. the setup. `rules` rides along because both changes are player-visible; the
    # rest of the setup body (name, banner, tags, settings) is deliberately left alone.
    st, _ = req(f"{HOST}/api/setup/{SETUP_ID}", {"raw": raw, "rules": desc["rules"]}, "PATCH")
    print("setup PATCH:", st)

    # 3. read back and prove it landed
    live_deck = find_deck(DECK_NAME)
    _, live = req(f"{HOST}/api/setup/{SETUP_ID}")
    print("\nverify")
    print("  deck id:            ", live_deck["id"])
    print("  deck matches local: ",
          json.dumps(live_deck["script"], sort_keys=True) == json.dumps(cards, sort_keys=True))
    print("  raw matches local:  ",
          json.dumps(live.get("raw"), sort_keys=True) == json.dumps(raw, sort_keys=True))
    print("  rules match local:  ",
          json.dumps(live.get("rules"), sort_keys=True) == json.dumps(desc["rules"], sort_keys=True))
    print("  setup name:         ", live.get("name"))

if __name__ == "__main__":
    main()
