#!/usr/bin/env python3
"""Rainbow Blackjack — tell players The Zero has locked them, and stop the
penalty prompt appearing when there is nobody to give the card to.

The next patch layer (see patch_variant_wallpaper.py for the chain; none of
these are idempotent, so each change set is its own script).

1. **The Zero was silent.** Holding `n_0` puts you in `mustHit` on every tick,
   which swaps your playable cards from ["hit","stay"] to ["hit"] — your Stay
   card simply stops working for the rest of the round. That is the designed
   rule, but nothing said so, and the card can arrive by Steal or Swap rather
   than by drawing it, so it read as a bug. Now the player is told, once, the
   first time they are found holding it.

2. **The penalty prompt ran with nothing to click.** Whether the hand-off could
   happen was decided from `aliveCount`, worked out earlier in the tick in a
   different group; the pool the prompt actually offers is computed later. When
   they disagreed the vote appeared with an empty target list, the player could
   not click anyone, and the timeout fallback dealt the card to a random player.
   Readiness is now decided by the pool itself, in a group that runs before the
   prompt.

  python3 scripts/rainbow_blackjack/patch_zero_notice_and_penalty_skip.py
  python3 scripts/rainbow_blackjack/patch_zero_notice_and_penalty_skip.py --local
"""
import json
import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rb_dsl import (  # noqa: E402
    P, C, X, sel, cache, NEW_STRINGS, penalty_groups,
)
from build_naughty import (  # noqa: E402
    inner_loop, group_index, svc_entry, svc_insert_after,
)

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
GAME = os.path.join(REPO, "game_jsons", "rainbow_blackjack.json")
PROD = "https://try.ludio.gg/api/setup/7271e197-2822-4fd2-bdbd-1438f5d71d60"


def find_action(actions, var):
    return next(a for a in actions
                if any(e["name"] == var for e in a.get("saveValueInCache", [])))


# ── 1. The Zero explains itself ─────────────────────────────────────────────
def patch_strings(g):
    g["gameInitOptions"]["strings"]["Default"].update(NEW_STRINGS)


def patch_zero_notice(g):
    """Tell a player the first time they are found holding The Zero.

    Appended to the end of the per-player bust walk rather than inserted into
    it: actions 2-5 there are chained on `isPrevActionSkipped`, and putting
    anything between them would break the chain. `hasZero`, `stillIn` and
    `thisPlayer` are all still in cache from the top of the same iteration.

    Keyed on holding the card, not on drawing it, so a Zero arriving by Steal or
    Swap announces itself too. `zeroTold` keeps it to once per player per round;
    a skipped action does not run its saveValueInCache, so the list only grows
    when the notification actually fires.
    """
    inner = inner_loop(g)
    grp = inner[group_index(inner, "Compute players who bust")]
    already_told = sel("contains", C("list", "zeroTold"), C("element", "thisPlayer"))
    grp["actions"].append({
        "key": "createNotification",
        "skipCondition": sel("logicalNOT", X("arg", sel(
            "logicalAND",
            C("arg1", "hasZero"),
            X("arg2", sel("logicalAND",
                          C("arg1", "stillIn"),
                          X("arg2", sel("logicalNOT", X("arg", already_told)))))))),
        "payload": {
            "preset": {"duration": 14},
            "cached": {"header": "zeroLockHeader", "text": "zeroLockText"},
            "computed": {"to": sel("createList", C("arg1", "thisPlayer"))},
        },
        "saveValueInCache": [
            cache("zeroTold", sel("append",
                                  C("list", "zeroTold"),
                                  C("element", "thisPlayer"))),
        ],
    })


# ── 2. the penalty prompt only when there is somebody to point at ───────────
def patch_penalty_groups(g):
    """Swap the two penalty groups for the three-group version."""
    inner = inner_loop(g)
    at = group_index(inner, "Naughty: penalty - work out who can take it") \
        if any(x.get("name") == "Naughty: penalty - work out who can take it"
               for x in inner if isinstance(x, dict)) \
        else group_index(inner, "Naughty: penalty - choose who takes it")
    old = [x for x in inner
           if isinstance(x, dict) and str(x.get("name", "")).startswith("Naughty: penalty")]
    assert len(old) == 2, "expected 2 penalty groups, found %d" % len(old)
    for x in old:
        inner.remove(x)
    fresh = penalty_groups()
    inner[at:at] = fresh
    return [x["name"] for x in fresh]


def patch_penalty_readiness(g):
    """Readiness stops meaning "enough players" and starts meaning "we got a
    look at it"; the pool decides whether the prompt happens.

    `penHasTargets` is cleared every tick alongside the other flows' flags, so a
    tick where the setup group does not run cannot inherit a stale true from an
    earlier penalty and fire the prompt on the wrong player.
    """
    inner = inner_loop(g)
    act = inner[group_index(inner, "Freezers and flippers")]["actions"][0]

    queued = sel("greaterThan",
                 X("arg1", sel("listLength", C("list", "penQueue"))),
                 P("arg2", 0))
    svc_entry(act, "penReady")["value"] = sel(
        "logicalAND", X("arg1", queued), C("arg2", "flipIdle"))
    # Drain whenever we had the chance to act on it: either the card was handed
    # on, or there was no one to hand it to and the drawer keeps it.
    svc_entry(act, "penDrop")["value"] = sel(
        "getCachedValue", P("name", "penReady"))

    act["saveValueInCache"] = [e for e in act["saveValueInCache"]
                               if e["name"] != "penPossible"]
    svc_insert_after(act, "penDrop", [cache("penHasTargets", False)])


def patch_initial_cache(g):
    """Seed zeroTold before anything can read it.

    Ludio's logicalAND does not short-circuit, so the notification's
    `contains(zeroTold, …)` is evaluated on every player on every tick — even
    when hasZero is false. It has to be a list from the very first tick or that
    is a runtime "contains list argument is not array".
    """
    bla = g["beforeLoopActions"]
    act = find_action(bla, "mustHit")
    svc_insert_after(act, "mustHit", [cache("zeroTold", [])])


def patch_round_reset(g):
    """Per-round state for both fixes."""
    loop = g["gameLoop"]
    grp = loop[group_index(loop, "Prepare for round")]
    act = find_action(grp["actions"], "penQueue")
    act["saveValueInCache"] = [e for e in act["saveValueInCache"]
                               if e["name"] != "penPossible"]
    svc_insert_after(act, "penQueue", [
        cache("penHasTargets", False),
        cache("zeroTold", []),
    ])


def load_game():
    if "--local" in sys.argv:
        return json.load(open(GAME))
    with urllib.request.urlopen(PROD, timeout=90) as r:
        raw = json.load(r).get("raw")
    return json.loads(raw) if isinstance(raw, str) else raw


def main():
    g = load_game()

    patch_strings(g)
    patch_initial_cache(g)
    patch_zero_notice(g)
    names = patch_penalty_groups(g)
    patch_penalty_readiness(g)
    patch_round_reset(g)

    with open(GAME, "w") as f:
        json.dump(g, f, indent=2)
        f.write("\n")

    print("wrote %s" % GAME)
    print("  penalty groups now: %s" % "; ".join(names))
    print("  inner-loop groups: %d" % len(inner_loop(g)))
    print("  size: %.1f KB" % (os.path.getsize(GAME) / 1024.0))


if __name__ == "__main__":
    main()
