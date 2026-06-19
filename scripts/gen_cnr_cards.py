"""Generate the Cops & Robbers cards JSON (cnr_cards) with 5 action cards + cell cards.

Cell cards cover the MAX grid (10 cols × 7 rows = 70 cells) so the largest
configuration (7×10) has every stash coord available.
"""
import json
from pathlib import Path

OUT = Path("/Users/ankitbuddhiraju/LudioCode/game_jsons/cops_and_robbers_cards.json")
BASE = "https://res.cloudinary.com/liars-club/image/upload/images/cnr"

MAX_COLS = 10   # letters A..J
MAX_ROWS = 7    # rows 1..7


def cell(c: int, r: int) -> str:
    return f"{chr(ord('A')+c)}{r+1}"


def main():
    # Weight ranges sort the Robber's hand left-to-right after dealDeck(sortBy="weight"):
    #   PASS (0)   < stash coord cards (100) < specials (200) < ✓-stash done (300+)
    # The intent: keep PASS far away from the Specials so users don't misclick.
    cards = [
        {"name": "pass",        "image": f"{BASE}/special_pass.png",        "label": "Pass",        "enlargeOnHover": True, "weight": 0},
        {"name": "getaway",     "image": f"{BASE}/special_getaway.png",     "label": "Getaway Car", "enlargeOnHover": True, "weight": 200},
        {"name": "backstreet",  "image": f"{BASE}/special_backstreet.png",  "label": "Backstreet",  "enlargeOnHover": True, "weight": 201},
        {"name": "speedboat",   "image": f"{BASE}/special_speedboat.png",   "label": "Speedboat",   "enlargeOnHover": True, "weight": 202},
        {"name": "investigate", "image": f"{BASE}/action_investigate.png",  "label": "Investigate", "enlargeOnHover": True, "weight": 10},
        {"name": "bust",        "image": f"{BASE}/action_bust.png",         "label": "Bust",        "enlargeOnHover": True, "weight": 11},
    ]

    cell_cards = []
    for c in range(MAX_COLS):
        for r in range(MAX_ROWS):
            coord = cell(c, r)
            cell_cards.append({
                "name": coord,
                "image": f"{BASE}/coord_{coord}.png",
                "label": coord,
                "enlargeOnHover": True,
                "weight": 100,
            })

    cards.extend(cell_cards)

    sets = {
        "specials_solo":  {"getaway": 2, "backstreet": 2, "speedboat": 2},
        "specials_each":  {"getaway": 1, "backstreet": 1, "speedboat": 1},
        # 3 Pass cards in the set — dealDeck qnt=1 hands 1 to each Robber.
        "pass_card":      {"pass": 3},
        "cop_actions":    {"investigate": 1, "bust": 1},
        # 3 copies of every cell so up to 3 Robbers can each draw the same coord
        "cells_3x":       {c["name"]: 3 for c in cell_cards},
    }

    doc = {
        "name": "cnr_cards",
        "cards": cards,
        "sets": sets,
    }

    OUT.write_text(json.dumps(doc, indent=2) + "\n")
    print(f"Wrote {OUT} — {len(cards)} cards, {len(sets)} sets ({sum(sets['cells_3x'].values())} cell copies in cells_3x)")


if __name__ == "__main__":
    main()
