#!/usr/bin/env python3
"""Rainbow Blackjack — name the hand on screen, and cut Naughty to 150.

The next patch layer after patch_stayed_and_swap.py (none of these are
idempotent, so each change set is its own script).

**Source is the repo copy, not prod.** patch_stayed_and_swap.py has shipped to
staging but not to production, so prod is a layer behind and pulling from it
would silently drop the new Swap. Pass --prod only once this has all landed
there.

1. **The exploded piles were anonymous.** Steal, Swap and Discard lift a
   player's cards out of their seat and show them in the middle of the table,
   and until now nothing on screen said whose they were — the pick decks are a
   pool shared by every flow and every round. Each one is now labelled with its
   owner's name as it is dealt, inside the explode loop, so Swap's two rows come
   out labelled with the two different players.

2. **Naughty plays to 150.** It scores faster than Nice and the penalties bite,
   so 200 dragged. `playersWinCondition.gameOverCondition` compared against a
   preset 200, which cannot tell the variants apart; it now reads a `winTarget`
   resolved once by the game-mode vote (200 Nice, 150 Naughty), the same way
   every other variant difference is handled. The tutorial's Naughty overview
   says so, and the cheatsheet line is redrawn by gen_cheatsheet.py.

  python3 scripts/rainbow_blackjack/patch_labels_and_target.py
  python3 scripts/rainbow_blackjack/patch_labels_and_target.py --prod
"""
import json
import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rb_dsl import (  # noqa: E402
    C, P, cache, sel, NEW_STRINGS, owner_label_action,
)
from build_naughty import (  # noqa: E402
    inner_loop, group_index, svc_insert_after,
)

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
GAME = os.path.join(REPO, "game_jsons", "rainbow_blackjack.json")
PROD = "https://try.ludio.gg/api/setup/7271e197-2822-4fd2-bdbd-1438f5d71d60"

# group name -> the cache variable holding the player whose pile it lays out.
EXPLODE_GROUPS = {
    "Naughty: steal - lay out their cards": "stlVictim",
    "Naughty: discard - lay out their cards": "dscVictim",
    "Naughty: swap - lay out the first hand": "swpaVictim",
    "Naughty: swap - lay out the second hand": "swpbVictim",
}


def find_action(actions, var):
    return next(a for a in actions
                if any(e["name"] == var for e in a.get("saveValueInCache", [])))


# ── 1. whose cards are these ────────────────────────────────────────────────
def patch_owner_labels(g):
    """Append the label call to each explode loop.

    Appended rather than inserted: the label has to name the deck the card just
    went into, so it runs after the moveCards for that same repeatIndex.
    """
    inner = inner_loop(g)
    done = []
    for name, victim in EXPLODE_GROUPS.items():
        grp = inner[group_index(inner, name)]
        prefix = victim[:-len("Victim")]
        assert not any(a.get("key") == "setDeckLabel" for a in grp["actions"]), name
        grp["actions"].append(owner_label_action(prefix, victim))
        done.append("%s -> %s" % (name.split(" - ")[-1], victim))
    return done


# ── 2. Naughty plays to 150 ─────────────────────────────────────────────────
def patch_win_target(g):
    """Give the two variants their own finish line.

    The vote's derived action is where every other variant difference is
    resolved, so the target joins them there rather than being branched on
    inside the win condition.
    """
    bla = g["beforeLoopActions"]
    svc_insert_after(find_action(bla, "plainSevenCard"), "plainSevenCard", [
        # The same shape as every other `pick()` in that action: ifElse on the
        # `naughty` flag, both branches literal.
        cache("winTarget", sel("ifElse",
                               C("condition", "naughty"),
                               P("thenValue", 150),
                               P("elseValue", 200))),
    ])

    cond = g["playersWinCondition"]["gameOverCondition"]
    arg2 = next(p for p in cond["params"] if p["name"] == "arg2")
    was = arg2["value"]
    assert was == 200 and arg2["type"] == "preset", (arg2["type"], was)
    arg2.update({"type": "cached", "value": "winTarget"})
    return was


def patch_strings(g):
    """The Naughty overview names the target, so the tutorial follows."""
    g["gameInitOptions"]["strings"]["Default"].update(NEW_STRINGS)


# ── entry point ─────────────────────────────────────────────────────────────
def load_game():
    if "--prod" in sys.argv:
        with urllib.request.urlopen(PROD, timeout=90) as r:
            raw = json.load(r).get("raw")
        return json.loads(raw) if isinstance(raw, str) else raw
    return json.load(open(GAME))


def main():
    g = load_game()

    labelled = patch_owner_labels(g)
    was = patch_win_target(g)
    patch_strings(g)

    with open(GAME, "w") as f:
        json.dump(g, f, indent=2)
        f.write("\n")

    print("wrote %s" % GAME)
    print("  piles now labelled with their owner:")
    for line in labelled:
        print("      %s" % line)
    print("  win target: preset %d -> cached winTarget (Nice 200, Naughty 150)" % was)
    print("  size: %.1f KB" % (os.path.getsize(GAME) / 1024.0))


if __name__ == "__main__":
    main()
