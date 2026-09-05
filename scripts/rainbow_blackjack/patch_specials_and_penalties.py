#!/usr/bin/env python3
"""Rainbow Blackjack — one Unlucky 7, one Lucky 13, and penalties you hand on.

`build_naughty.py` cannot be re-run: it turns a pre-Naughty game into a Naughty
one, and production has been the Naughty one since 2026-08-26. Re-running it
against today's prod duplicates the action-card groups and then dies looking for
a field an earlier pass already moved. So this is the next layer instead — the
same shape (pull live prod, apply named patches, write the repo copy), applied
on top of what build_naughty produced.

Two changes:

  1. Unlucky 7 and Lucky 13 become single cards (`n_7_unlucky`, `n_13_lucky`)
     rather than rules that fired on all seven 7s and all thirteen 13s.
  2. A penalty card is never kept by whoever drew it. They pick another player
     still in the round and it lands in front of them instead.

  python3 scripts/rainbow_blackjack/patch_specials_and_penalties.py
  python3 scripts/rainbow_blackjack/patch_specials_and_penalties.py --local
"""
import json
import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rb_dsl import (  # noqa: E402
    P, C, X, sel, cache, NEW_STRINGS, PICK_DECKS,
    variant_vote_actions, penalty_groups,
)
from build_naughty import (  # noqa: E402
    inner_loop, group_index, svc_entry, svc_insert_after,
)

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
GAME = os.path.join(REPO, "game_jsons", "rainbow_blackjack.json")
PROD = "https://try.ludio.gg/api/setup/7271e197-2822-4fd2-bdbd-1438f5d71d60"


def find_action(actions, var):
    """The action that writes `var` to cache."""
    return next(a for a in actions
                if any(e["name"] == var for e in a.get("saveValueInCache", [])))


# ── 1. copy ─────────────────────────────────────────────────────────────────
def patch_strings(g):
    """Refresh the Naughty copy: the two rule blurbs changed and the penalty
    prompt is new."""
    g["gameInitOptions"]["strings"]["Default"].update(NEW_STRINGS)


# ── 2. what the variant vote resolves into ──────────────────────────────────
def patch_variant_cache(g):
    """Replace the derived-variables action wholesale from rb_dsl.

    Rebuilding rather than editing in place keeps this action the single thing
    rb_dsl is responsible for — the new card names, the penalty tables and the
    two extra pick decks all arrive together and cannot drift apart.
    """
    bla = g["beforeLoopActions"]
    at = next(i for i, a in enumerate(bla)
              if any(e["name"] == "zeroCard" for e in a.get("saveValueInCache", [])))
    fresh = variant_vote_actions()[1]

    before = {e["name"] for e in bla[at]["saveValueInCache"]}
    after = {e["name"] for e in fresh["saveValueInCache"]}
    assert not before - after, "dropped cached variables: %s" % sorted(before - after)
    bla[at] = fresh
    return sorted(after - before)


def patch_pick_deck_count(g):
    """Two more pick decks, because the two new numbers are stealable too."""
    loop = g["gameLoop"]
    grp = loop[group_index(loop, "Create card-picking decks")]
    was = grp["repeat"]["qnt"]
    grp["repeat"]["qnt"] = len(PICK_DECKS)
    return was, len(PICK_DECKS)


# ── 3. the two special numbers ──────────────────────────────────────────────
def patch_bust(g):
    """Swap the Lucky 13 exemption for the Unlucky 7 clash.

    Lucky 13 needs no rule now: it is one card with its own name, so it cannot
    duplicate an ordinary 13 and cannot bust. Two ordinary 13s still share a
    name and still do.

    The Unlucky 7 is the mirror image. It is also its own name, but it is still
    a seven — holding it next to an ordinary 7 has to bust the way two ordinary
    7s would, and the duplicate check can no longer see that on its own.
    """
    inner = inner_loop(g)
    setup = inner[group_index(inner, "Compute players who bust")]["actions"][0]
    still_in = svc_entry(setup, "stillIn")

    # Unwrap the Lucky 13 clause build_naughty wrapped around the original.
    v = still_in["value"]
    assert v["selector"] == "logicalOR", v["selector"]
    lucky = v["params"][1]["value"]
    assert lucky["selector"] == "logicalAND" and "luckyCard" in json.dumps(lucky)
    original = v["params"][0]["value"]

    still_in["value"] = sel(
        "logicalAND",
        X("arg1", original),
        X("arg2", sel("logicalNOT", X("arg", sel(
            "logicalAND",
            X("arg1", sel("contains",
                          C("list", "handNames"), C("element", "plainSevenCard"))),
            X("arg2", sel("contains",
                          C("list", "handNames"), C("element", "unluckyCard"))))))))


# ── 4. penalties change hands ───────────────────────────────────────────────
def patch_queue_penalties(g):
    """Queue the drawer and the card the moment a penalty is turned over.

    Hung off the deal, the first point at which `cardNames` names the drawn
    card. Both lists gain an entry or neither does, so they stay index-aligned;
    `penaltyCards` is empty in Nice, where a modifier is a bonus you want.
    """
    inner = inner_loop(g)
    grp = inner[group_index(inner, "Deal 1 card to each remaining player")]
    dealt = find_action(grp["actions"], "justDrewToPlayer")
    svc_insert_after(dealt, "justDrewToPlayer", [
        cache("drewPenalty", sel("contains",
                                 C("list", "penaltyCards"),
                                 C("element", "cardNames.0"))),
        cache("penQueue", sel("ifElse",
                              C("condition", "drewPenalty"),
                              X("thenValue", sel("append",
                                                 C("list", "penQueue"),
                                                 C("element", "thisPlayer"))),
                              C("elseValue", "penQueue"))),
        cache("penCards", sel("ifElse",
                              C("condition", "drewPenalty"),
                              X("thenValue", sel("append",
                                                 C("list", "penCards"),
                                                 C("element", "cardNames.0"))),
                              C("elseValue", "penCards"))),
    ])


def patch_prepare_round(g):
    """Clear the penalty queue between rounds, like the other queues."""
    loop = g["gameLoop"]
    grp = loop[group_index(loop, "Prepare for round")]
    act = find_action(grp["actions"], "stealQueue")
    svc_insert_after(act, "stealQueue", [
        cache("penQueue", []),
        cache("penCards", []),
        cache("penReady", False),
        cache("penPossible", False),
        cache("penDrop", False),
    ])


def patch_collect_drawers(g):
    """Work out each tick whether the penalty hand-off can run."""
    inner = inner_loop(g)
    act = inner[group_index(inner, "Freezers and flippers")]["actions"][0]

    svc_insert_after(act, "stlPossible", [
        # Handing a penalty on asks exactly what Steal asks — is there one other
        # unbusted player to point at — so it reads that answer rather than
        # inlining the same comparison a third time. With nobody else left the
        # queue still drains and the drawer keeps the card.
        cache("penPossible", sel("getCachedValue", P("name", "stlPossible"))),
        cache("penReady", sel(
            "logicalAND",
            X("arg1", sel("logicalAND",
                          X("arg1", sel("greaterThan",
                                        X("arg1", sel("listLength",
                                                      C("list", "penQueue"))),
                                        P("arg2", 0))),
                          C("arg2", "penPossible"))),
            C("arg2", "flipIdle"))),
        cache("penDrop", sel(
            "logicalAND",
            X("arg1", sel("greaterThan",
                          X("arg1", sel("listLength", C("list", "penQueue"))),
                          P("arg2", 0))),
            X("arg2", sel("logicalOR",
                          C("arg1", "penReady"),
                          X("arg2", sel("logicalNOT", C("arg", "penPossible"))))))),
    ])


def patch_insert_penalty_groups(g):
    """Run the hand-off ahead of the card-moving cards, so who holds what is
    settled before Steal and Swap start reaching across the table."""
    inner = inner_loop(g)
    at = group_index(inner, "Naughty: steal - choose a victim")
    inner[at:at] = penalty_groups()


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

    patch_strings(g)
    added = patch_variant_cache(g)
    was, now = patch_pick_deck_count(g)
    patch_bust(g)
    patch_queue_penalties(g)
    patch_prepare_round(g)
    patch_collect_drawers(g)
    patch_insert_penalty_groups(g)

    with open(GAME, "w") as f:
        json.dump(g, f, indent=2)
        f.write("\n")

    print("wrote %s" % GAME)
    print("  new cached variables: %s" % ", ".join(added))
    print("  card-picking decks: %d -> %d" % (was, now))
    print("  inner-loop groups: %d -> %d" % (before_groups, len(inner_loop(g))))
    print("  size: %.1f KB" % (os.path.getsize(GAME) / 1024.0))


if __name__ == "__main__":
    main()
