#!/usr/bin/env python3
"""Push the Rainbow Blackjack deck and game JSON to staging (ptr.ludio.gg).

  python3 scripts/rainbow_blackjack/deploy.py            # dry run: show what would go
  python3 scripts/rainbow_blackjack/deploy.py --push     # actually PATCH staging
"""
import json
import os
import sys
import urllib.request

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
GAME = os.path.join(REPO, "game_jsons", "rainbow_blackjack.json")
CARDS = os.path.join(REPO, "game_jsons", "rainbow_blackjack_cards.json")

HOST = "https://ptr.ludio.gg"
SETUP_ID = "d7aad5d4-5295-400a-b9e7-230d0136acb1"   # Rainbow Blackjack on staging
DECK_NAME = "rainbow_blackjack"


def get(url):
    with urllib.request.urlopen(url, timeout=90) as r:
        return json.load(r)


def patch(url, body):
    req = urllib.request.Request(
        url, data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"}, method="PATCH")
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.status


def main():
    push = "--push" in sys.argv
    game = json.load(open(GAME))
    cards = json.load(open(CARDS))

    deck = get("%s/api/deck/%s" % (HOST, DECK_NAME))
    deck_id = deck["id"]
    current = deck["script"]
    if isinstance(current, str):
        current = json.loads(current)

    print("staging deck  %s (%d card defs, sets: %s)"
          % (deck_id, len(current.get("cards", [])),
             ", ".join(current.get("sets", {}))))
    print("local deck    %d card defs, sets: %s"
          % (len(cards["cards"]), ", ".join(cards["sets"])))
    print("staging setup %s" % SETUP_ID)
    print("local game    %.1f KB" % (os.path.getsize(GAME) / 1024.0))

    if not push:
        print("\ndry run — pass --push to write")
        return

    print("\ndeck  PATCH:", patch("%s/api/deck/%s" % (HOST, deck_id),
                                  {"script": cards}))
    print("setup PATCH:", patch("%s/api/setup/%s" % (HOST, SETUP_ID),
                                {"raw": game}))

    # Read back and confirm what landed.
    back_deck = get("%s/api/deck/%s" % (HOST, DECK_NAME))["script"]
    if isinstance(back_deck, str):
        back_deck = json.loads(back_deck)
    back_raw = get("%s/api/setup/%s" % (HOST, SETUP_ID))["raw"]
    if isinstance(back_raw, str):
        back_raw = json.loads(back_raw)

    print("\nverify:")
    print("  deck sets on staging:", ", ".join(
        "%s=%d" % (k, sum(v.values())) for k, v in back_deck["sets"].items()))
    print("  naughty cards present:",
          sum(1 for c in back_deck["cards"] if c["name"].startswith("n_")))
    print("  game matches local:", back_raw == game)


if __name__ == "__main__":
    main()
