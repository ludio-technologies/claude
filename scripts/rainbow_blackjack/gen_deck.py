#!/usr/bin/env python3
"""Rebuild game_jsons/rainbow_blackjack_cards.json for both variants.

Points, ranks and the Nice set's composition are exactly what production has —
this only repoints the artwork at the new per-variant folders, renames the
forced-draw cards to Hit 3 / Hit 4, and adds the Naughty cards and set.

The original card images are left in place on Cloudinary; the redrawn Nice deck
lives in images/rainbow_blackjack/nice/ alongside the Naughty one.

Usage:  python3 scripts/rainbow_blackjack/gen_deck.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rb_cards  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CARDS = os.path.join(REPO, "game_jsons", "rainbow_blackjack_cards.json")

BASE = "https://res.cloudinary.com/liars-club/image/upload/%s/%s.png"

# The two cards whose name no longer matches what the reskin calls the action:
# a forced draw is a Hit here, not a Flip.
RELABEL = {"flip": "Hit 3", "n_flip_four": "Hit 4"}

# Naughty ranks: everything that is not a number sorts ahead of the numbers,
# matching how the Nice deck lays a hand out.
NAUGHTY_RANKS = {
    "n_divide_2": -1, "n_minus_2": -2, "n_minus_4": -3, "n_minus_6": -4,
    "n_minus_8": -5, "n_minus_10": -6, "n_just_one_more": -7,
    "n_flip_four": -8, "n_steal": -9, "n_swap": -10, "n_discard": -11,
}

# Every naughty card is type "number" for the same reason the Nice modifiers
# are: round cleanup recalls hands with `type: "number"`, which has to sweep up
# everything except the hit/stay cards.
CARD_TYPE = "number"


def image_for(variant, slug):
    return BASE % (rb_cards.FOLDERS[variant], slug)


def naughty_cards():
    out = []
    specials = (rb_cards.MODIFIERS["naughty"] + rb_cards.ACTIONS["naughty"])
    for name, slug, label in specials:
        out.append({"name": name, "image": image_for("naughty", slug),
                    "label": RELABEL.get(name, label), "points": 0,
                    "rank": NAUGHTY_RANKS[name], "type": CARD_TYPE})
    for v in rb_cards.NUMBERS["naughty"]:
        out.append({"name": "n_%d" % v, "image": image_for("naughty", str(v)),
                    "label": str(v), "points": v, "rank": v, "type": CARD_TYPE})
    # Unlucky 7 and Lucky 13: one copy each, scoring like the number they show
    # but carrying their own name so the rules can single them out — and so the
    # Lucky 13 does not collide with an ordinary 13 in a hand.
    for name, slug, label, value, _cap, _drawn in rb_cards.SPECIAL_NUMBERS["naughty"]:
        out.append({"name": name, "image": image_for("naughty", slug),
                    "label": label, "points": value, "rank": value,
                    "type": CARD_TYPE})
    return out


def naughty_set():
    """108 cards: the Vengeance composition.

    0 appears once; 1..13 appear as many times as their face value (91 cards);
    one of each of the six modifiers; two of each of the five action cards.

    The Unlucky 7 and the Lucky 13 come out of their number's own allowance —
    seven 7s is still seven cards, six plain plus the one that bites — so the
    deck stays at 108 and the odds of drawing a 7 or a 13 are unchanged.
    """
    s = {"n_0": 1}
    for v in range(1, 14):
        s["n_%d" % v] = v
    for name, _slug, _label in rb_cards.MODIFIERS["naughty"]:
        s[name] = 1
    for name, _slug, _label in rb_cards.ACTIONS["naughty"]:
        s[name] = 2
    for name, _slug, _label, value, _cap, _drawn in rb_cards.SPECIAL_NUMBERS["naughty"]:
        s["n_%d" % value] -= 1
        s[name] = 1
    return s


def repoint_nice(cards):
    """Send the Nice deck's faces at their redrawn versions."""
    by_name = {c["name"]: c for c in cards}
    moved = 0
    for v in rb_cards.NUMBERS["nice"]:
        by_name[str(v)]["image"] = image_for("nice", str(v))
        moved += 1
    for name, slug, _label in (rb_cards.MODIFIERS["nice"]
                               + rb_cards.ACTIONS["nice"]):
        by_name[name]["image"] = image_for("nice", slug)
        if name in RELABEL:
            by_name[name]["label"] = RELABEL[name]
        moved += 1
    # hit/stay belong to both variants and keep the original artwork.
    return moved


def main():
    deck = json.load(open(CARDS))

    deck["cards"] = [c for c in deck["cards"] if not c["name"].startswith("n_")]
    moved = repoint_nice(deck["cards"])
    deck["cards"].extend(naughty_cards())
    deck["sets"]["naughty"] = naughty_set()

    with open(CARDS, "w") as f:
        json.dump(deck, f, indent=2)
        f.write("\n")

    print("wrote %s" % CARDS)
    print("  repointed %d Nice faces at %s/" % (moved, rb_cards.FOLDERS["nice"]))
    print("  card definitions: %d" % len(deck["cards"]))
    print("  sets: %s" % ", ".join("%s=%d" % (k, sum(v.values()))
                                   for k, v in deck["sets"].items()))
    for name, label in RELABEL.items():
        got = next(c["label"] for c in deck["cards"] if c["name"] == name)
        assert got == label, "%s label is %r" % (name, got)
        print("  %s labelled %r" % (name, got))
    assert sum(deck["sets"]["naughty"].values()) == 108
    untouched = [c["name"] for c in deck["cards"]
                 if "/rainbow_blackjack/" in c["image"]
                 and "/nice/" not in c["image"] and "/naughty/" not in c["image"]]
    print("  still on the original artwork: %s" % ", ".join(untouched))


if __name__ == "__main__":
    main()
