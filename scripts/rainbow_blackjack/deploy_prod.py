#!/usr/bin/env python3
"""Push the Rainbow Blackjack deck and game JSON to PRODUCTION (try.ludio.gg).

deploy.py points at staging. This is the same thing aimed at prod, and it reads
back what landed rather than trusting the PATCH status.

  python3 scripts/rainbow_blackjack/deploy_prod.py            # dry run
  python3 scripts/rainbow_blackjack/deploy_prod.py --push     # actually write
"""
import json
import os
import sys
import urllib.request

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
GAME = os.path.join(REPO, "game_jsons", "rainbow_blackjack.json")
CARDS = os.path.join(REPO, "game_jsons", "rainbow_blackjack_cards.json")

HOST = "https://try.ludio.gg"
SETUP_ID = "7271e197-2822-4fd2-bdbd-1438f5d71d60"
DECK_NAME = "rainbow_blackjack"


def get(url):
    with urllib.request.urlopen(url, timeout=90) as r:
        return json.load(r)


def patch(url, body):
    req = urllib.request.Request(
        url, data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"}, method="PATCH")
    with urllib.request.urlopen(req, timeout=180) as r:
        return r.status


def norm(o):
    return json.dumps(o, sort_keys=True)


def main():
    push = "--push" in sys.argv
    game = json.load(open(GAME))
    cards = json.load(open(CARDS))

    deck = get("%s/api/deck/%s" % (HOST, DECK_NAME))
    live = deck["script"]
    if isinstance(live, str):
        live = json.loads(live)

    print("prod deck  %s" % deck["id"])
    print("  live  %d card defs, naughty=%d"
          % (len(live["cards"]), sum(live["sets"]["naughty"].values())))
    print("  local %d card defs, naughty=%d"
          % (len(cards["cards"]), sum(cards["sets"]["naughty"].values())))
    print("prod setup %s" % SETUP_ID)
    print("  local game %.1f KB" % (os.path.getsize(GAME) / 1024.0))

    if not push:
        print("\ndry run — pass --push to write")
        return

    # Deck first: the game names cards and a set that have to exist already.
    print("\ndeck  PATCH:", patch("%s/api/deck/%s" % (HOST, deck["id"]),
                                  {"script": cards}))
    print("setup PATCH:", patch("%s/api/setup/%s" % (HOST, SETUP_ID),
                                {"raw": game}))

    back_deck = get("%s/api/deck/%s" % (HOST, DECK_NAME))["script"]
    if isinstance(back_deck, str):
        back_deck = json.loads(back_deck)
    back_raw = get("%s/api/setup/%s" % (HOST, SETUP_ID))["raw"]
    if isinstance(back_raw, str):
        back_raw = json.loads(back_raw)

    ok_deck = norm(back_deck) == norm(cards)
    ok_game = norm(back_raw) == norm(game)
    print("\nverify: deck %s, setup %s"
          % ("round-trips" if ok_deck else "MISMATCH",
             "round-trips" if ok_game else "MISMATCH"))
    if not (ok_deck and ok_game):
        sys.exit(1)


if __name__ == "__main__":
    main()
