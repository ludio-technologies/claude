#!/usr/bin/env python3
"""Rainbow Blackjack — stopping keeps you safe, and Swap becomes two clicks.

The next patch layer after patch_zero_notice_and_penalty_skip.py (none of these
are idempotent, so each change set is its own script).

1. **Stopping is protection again.** The five Naughty cards that reach across
   the table — Steal, Swap, Discard, One More, Hit 4 — plus the penalty
   hand-off used to be split on this. One More and Hit 4 have always offered
   only players who are still drawing, because they force a draw and there is
   nothing to force out of somebody who has finished. Steal, Swap, Discard and
   the penalty hand-off deliberately went the other way: `pool_of` was
   `players - allBusted`, so anyone who had stayed was still fair game. That
   read as a bug at the table — you stay, you watch your hand get taken apart,
   and there is nothing you can do about it. All six now agree: the pool is
   `players - allBusted - allStopped`, and the three `*Possible` thresholds
   count that same set (`activeCount`, replacing `aliveCount`) so a card whose
   targets have all stopped is dropped rather than offered with nobody to
   point at.

2. **Swap was four questions and three widget rebuilds.** Pick a player, lay
   their hand out, pick a card, put the hand back, restore the board, pick a
   second player, lay that hand out, pick a card — with the first card parked in
   a holding deck the whole time so the tear-down did not put it straight back.
   Now the two players are named first, then both hands go up together on one
   three-row widget — first player's cards on the top row, second player's on
   the middle row, the bottom row left empty — and the two cards are clicked
   back to back off it. Neither card ever leaves its own single-card deck until
   the trade, so `swap_hold` is no longer needed.

   Showing both hands at once needs a second family of single-card decks
   (`j_n_5` beside `k_n_5`): both players can be holding the same card name, and
   one deck per name cannot hold two of them. It also needs a row of empty pad
   decks, because the grid fills row by row and the shorter hand has to be
   padded out to the full width or the second player's cards wrap up onto the
   end of the first player's row.

  python3 scripts/rainbow_blackjack/patch_stayed_and_swap.py
  python3 scripts/rainbow_blackjack/patch_stayed_and_swap.py --local
"""
import json
import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rb_dsl import (  # noqa: E402
    P, C, X, sel, cache, NEW_STRINGS, SWAP_EXTRA_DECKS, CARD_TO_PICK_DECK_B,
    SWAP_PAD_DECKS, SWAP_ROW_DIMENSIONS, pool_of, swap_groups,
)
from build_naughty import (  # noqa: E402
    inner_loop, group_index, svc_entry, svc_insert_after,
)

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
GAME = os.path.join(REPO, "game_jsons", "rainbow_blackjack.json")
PROD = "https://try.ludio.gg/api/setup/7271e197-2822-4fd2-bdbd-1438f5d71d60"

SWAP_PREFIX = "Naughty: swap - "


def find_action(actions, var):
    return next(a for a in actions
                if any(e["name"] == var for e in a.get("saveValueInCache", [])))


def set_svc(action, name, value):
    """Overwrite one saveValueInCache entry in place, keeping its position."""
    svc_entry(action, name)["value"] = value


# ── 1. stopping keeps you safe ──────────────────────────────────────────────
def patch_pools(g):
    """Rewrite the three target pools that are not rebuilt by the Swap work.

    Each is `pool_of(<the drawer>)` and each already excludes the busted; the
    new `pool_of` adds `allStopped`. Swap's own two pools come back with the
    replacement groups.
    """
    inner = inner_loop(g)
    touched = []
    for group_name, var, actor in (
            ("Naughty: penalty - work out who can take it", "penPool", "penActor"),
            ("Naughty: steal - choose a victim", "stlPool", "stlActor"),
            ("Naughty: discard - choose a victim", "dscPool", "dscActor"),
    ):
        grp = inner[group_index(inner, group_name)]
        set_svc(find_action(grp["actions"], var), var, pool_of(actor))
        touched.append(var)
    return touched


def patch_active_count(g):
    """`aliveCount` counted everyone unbusted; the thresholds need the players
    who are actually still drawing.

    Renamed rather than redefined: the three `*Possible` flags are its only
    readers, and a variable called "alive" that excludes players who are very
    much still in the game would be a trap for the next change.
    """
    inner = inner_loop(g)
    act = inner[group_index(inner, "Freezers and flippers")]["actions"][0]

    entry = svc_entry(act, "aliveCount")
    entry["name"] = "activeCount"
    entry["value"] = sel("listLength", X("list", pool_of()))

    # Steal and Discard need one other player to point at; Swap names two
    # players besides the drawer, so it needs a table of three.
    for flag in ("stlPossible", "swpPossible", "dscPossible"):
        for prm in svc_entry(act, flag)["value"]["params"]:
            if prm.get("value") == "aliveCount":
                prm["value"] = "activeCount"

    # And the round-start seed, so the first tick never reads a missing name.
    loop = g["gameLoop"]
    prep = find_action(loop[group_index(loop, "Prepare for round")]["actions"],
                       "aliveCount")
    svc_entry(prep, "aliveCount")["name"] = "activeCount"


# ── 2. the two-row swap ─────────────────────────────────────────────────────
def patch_swap_statics(g):
    """The second deck family, the row padding and the three-row grid."""
    bla = g["beforeLoopActions"]
    act = find_action(bla, "cardNameToPickDeck")
    svc_insert_after(act, "cardWidgetDimensions", [
        cache("swapExtraDeckNames", SWAP_EXTRA_DECKS),
        cache("cardNameToPickDeckB", CARD_TO_PICK_DECK_B),
        cache("swapPadDecks", SWAP_PAD_DECKS),
        cache("swapRowDimensions", SWAP_ROW_DIMENSIONS),
    ])
    return ["swapExtraDeckNames", "cardNameToPickDeckB",
            "swapPadDecks", "swapRowDimensions"]


def patch_swap_decks(g):
    """Build them once on the first pass, alongside the existing pick decks."""
    loop = g["gameLoop"]
    at = group_index(loop, "Create card-picking decks") + 1
    loop.insert(at, {
        "name": "Create swap-layout decks",
        "skipCondition": [sel("greaterThan", C("arg1", "gameLoopIndex"),
                              P("arg2", 0))],
        "repeat": {"qnt": len(SWAP_EXTRA_DECKS)},
        "actions": [{
            "key": "createCustomDeck",
            "payload": {
                "preset": {"public": True, "counter": False, "facedown": False},
                "computed": {
                    "name": sel("selectElement", C("list", "swapExtraDeckNames"),
                                C("index", "repeatIndex")),
                },
            },
        }],
    })
    return len(SWAP_EXTRA_DECKS)


def patch_swap_groups(g):
    """Swap out the whole run of `Naughty: swap - ...` groups for the new flow.

    Replaced as a block rather than edited in place: the old flow's shape — lay
    out, pick, put back, restore, and only then start on the second player — is
    exactly what is going away.
    """
    inner = inner_loop(g)
    old = [i for i, grp in enumerate(inner)
           if isinstance(grp, dict) and grp.get("name", "").startswith(SWAP_PREFIX)]
    assert old and old == list(range(old[0], old[-1] + 1)), \
        "the swap groups are not one contiguous run: %s" % old
    was = [inner[i]["name"] for i in old]
    inner[old[0]:old[-1] + 1] = swap_groups()
    return was, [g["name"] for g in swap_groups()]


def patch_round_cleanup(g):
    """Retire `swap_hold` and sweep the new decks instead.

    `swap_hold` parked the first card between the two widget rebuilds; there is
    nothing to park any more, so the deck goes and so does the round-cleanup
    sweep that emptied it — which would otherwise be a "deck not found" the
    first time a round ended. Its slot in cleanup goes to the second pick-deck
    family, for the same reason the first family is already swept: a round that
    ends mid-Swap must not leave a card stranded in a single-card deck.
    """
    changed = []

    bla = g["beforeLoopActions"]
    for i, a in enumerate(bla):
        if (a.get("key") == "createCustomDeck"
                and a["payload"]["preset"].get("name") == "swap_hold"):
            del bla[i]
            changed.append("swap_hold deck dropped")
            break

    loop = g["gameLoop"]
    grp = loop[group_index(loop, "Clean up cards, advance round")]
    at = next(i for i, a in enumerate(grp["actions"])
              if a.get("key") == "moveCards"
              and a["payload"].get("preset", {}).get("from") == "swap_hold")
    grp["actions"][at] = {
        "key": "moveCards",
        "payload": {"preset": {"type": "deck", "to": "discard"},
                    "cached": {"from": "swapExtraDeckNames"}},
    }
    changed.append("cleanup now sweeps swapExtraDeckNames")
    return changed


def patch_strings(g):
    """Refreshed Swap wording, and the rules copy that promised the opposite."""
    g["gameInitOptions"]["strings"]["Default"].update(NEW_STRINGS)


# ── entry point ─────────────────────────────────────────────────────────────
def load_game():
    if "--local" in sys.argv:
        return json.load(open(GAME))
    with urllib.request.urlopen(PROD, timeout=90) as r:
        raw = json.load(r).get("raw")
    return json.loads(raw) if isinstance(raw, str) else raw


def main():
    g = load_game()
    before_groups = len(inner_loop(g))

    pools = patch_pools(g)
    patch_active_count(g)
    added = patch_swap_statics(g)
    decks = patch_swap_decks(g)
    was, now = patch_swap_groups(g)
    cleanup = patch_round_cleanup(g)
    patch_strings(g)

    with open(GAME, "w") as f:
        json.dump(g, f, indent=2)
        f.write("\n")

    print("wrote %s" % GAME)
    print("  pools now exclude stopped players: %s" % ", ".join(pools))
    print("  aliveCount -> activeCount")
    print("  new cached variables: %s" % ", ".join(added))
    print("  new custom decks: %d" % decks)
    print("  round cleanup: %s" % "; ".join(cleanup))
    print("  swap groups: %d -> %d" % (len(was), len(now)))
    for name in now:
        print("      %s" % name)
    print("  inner-loop groups: %d -> %d" % (before_groups, len(inner_loop(g))))
    print("  size: %.1f KB" % (os.path.getsize(GAME) / 1024.0))


if __name__ == "__main__":
    main()
