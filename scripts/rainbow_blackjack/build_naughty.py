#!/usr/bin/env python3
"""Add the Naughty variant to Rainbow Blackjack.

Pulls the live production game JSON, layers the variant on top of it, and writes
game_jsons/rainbow_blackjack.json. Run gen_naughty_deck.py first — this assumes
the `naughty` card set already exists in the deck JSON.

The host picks Nice or Naughty at the start of the game (the same createVote
shape Spicy Peppers uses). Everything that differs between the two is resolved
once, right after that vote, into cached variables; the rest of the game reads
those variables instead of hardcoded card names, so Nice keeps behaving exactly
as it does in production.

Naughty is "Flip 7: With a Vengeance": numbers 0-13, negative modifiers, five
action cards (Just One More, Flip 4, Steal, Swap, Discard) and three special
numbers (The Zero, Unlucky 7, Lucky 13).

Usage:
  python3 scripts/rainbow_blackjack/build_naughty.py            # pull from prod
  python3 scripts/rainbow_blackjack/build_naughty.py --local    # patch the file
"""
import copy
import json
import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rb_dsl import (  # noqa: E402
    P, C, X, sel, cache, copy_of, player_deck_of,
    NEW_STRINGS, PICK_DECKS, WIDGET_LOOK, N_ACTIONS,
    variant_vote_actions, restore_main_widget,
    steal_groups, swap_groups, discard_groups, penalty_groups,
)

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
GAME = os.path.join(REPO, "game_jsons", "rainbow_blackjack.json")
PROD = "https://try.ludio.gg/api/setup/7271e197-2822-4fd2-bdbd-1438f5d71d60"


# ── small navigation helpers ────────────────────────────────────────────────
def inner_loop(g):
    """The `[]` sub-loop that runs one simultaneous flip round."""
    return next(x for x in g["gameLoop"] if isinstance(x, list))


def group_index(loop, name):
    for i, g in enumerate(loop):
        if isinstance(g, dict) and g.get("name") == name:
            return i
    raise KeyError("no group named %r" % name)


def svc_entry(action, name):
    for e in action.get("saveValueInCache", []):
        if e.get("name") == name:
            return e
    raise KeyError("no saveValueInCache entry %r" % name)


def svc_insert_after(action, after, entries):
    svc = action["saveValueInCache"]
    i = next(k for k, e in enumerate(svc) if e.get("name") == after)
    svc[i + 1:i + 1] = entries


def action_index(group, key, occurrence=0):
    seen = 0
    for i, a in enumerate(group["actions"]):
        if a.get("key") == key:
            if seen == occurrence:
                return i
            seen += 1
    raise KeyError("no %r action #%d" % (key, occurrence))


# ── the patches ─────────────────────────────────────────────────────────────
def patch_strings(g):
    """Add the Naughty copy and the game-mode vote copy."""
    g["gameInitOptions"]["strings"]["Default"].update(NEW_STRINGS)


def patch_cheatsheet(g):
    """Point at the consolidated sheet that covers both variants.

    gameInitOptions.cheatsheet is static config, so it cannot switch on the
    host's choice — one sheet has to serve both. It shows the shared numbers
    once and then only what differs, which is why it fits.
    """
    g["gameInitOptions"]["cheatsheet"]["image"] = (
        "https://res.cloudinary.com/liars-club/image/upload"
        "/images/rainbow_blackjack/cheatsheet.png")


def patch_before_loop(g):
    """Insert the game-mode vote, then create the decks the variant needs."""
    bla = g["beforeLoopActions"]

    # The vote goes straight after the tutorial vote, so the host answers both
    # questions back to back before any deck exists.
    tutorial_vote = next(i for i, a in enumerate(bla)
                         if a.get("key") == "createMixVote")
    bla[tutorial_vote + 1:tutorial_vote + 1] = variant_vote_actions()

    # The playing deck and its hand-side mirror are now built from whichever
    # set the host chose.
    for a in bla:
        if a.get("key") == "createDeck":
            preset = a["payload"]["preset"]
            if preset.get("set") == "cards":
                del preset["set"]
                a["payload"].setdefault("cached", {})["set"] = "deckSet"

    # Seed the lists that get read by contains() before anything has had a
    # chance to write them, so the first tick can never see a non-array.
    init = next(a for a in bla
                if any(e["name"] == "players" for e in a.get("saveValueInCache", [])))
    init["saveValueInCache"].extend([cache("handNames", []),
                                     cache("mustHit", []),
                                     cache("touched", []),
                                     cache("diff", [])])

    # Somewhere to park the first card of a Swap while the second player's
    # pile is laid out.
    discard_deck = next(i for i, a in enumerate(bla)
                        if a.get("key") == "createCustomDeck"
                        and a["payload"]["preset"].get("name") == "discard")
    bla.insert(discard_deck + 1, {
        "key": "createCustomDeck",
        "payload": {"preset": {"name": "swap_hold"}},
    })


def patch_pick_decks(g):
    """One single-card deck per stealable card name, for the picking widget."""
    loop = g["gameLoop"]
    at = group_index(loop, "Create player decks") + 1
    loop.insert(at, {
        "name": "Create card-picking decks",
        # These never change, so build them once on the first pass.
        "skipCondition": [sel("greaterThan", C("arg1", "gameLoopIndex"), P("arg2", 0))],
        "repeat": {"qnt": len(PICK_DECKS)},
        "actions": [{
            "key": "createCustomDeck",
            "payload": {
                "preset": {"public": True, "counter": False, "facedown": False},
                "computed": {
                    "name": sel("selectElement", C("list", "pickDeckNames"),
                                C("index", "repeatIndex")),
                },
            },
        }],
    })


def patch_prepare_round(g):
    """Reset the variant's per-round state; drop the old modifier trackers."""
    loop = g["gameLoop"]
    grp = loop[group_index(loop, "Prepare for round")]
    act = next(a for a in grp["actions"]
               if any(e["name"] == "remainingPlayers"
                      for e in a.get("saveValueInCache", [])))
    svc = act["saveValueInCache"]

    # Modifiers are now read straight off the hand at scoring time, because
    # Steal and Swap can move a modifier card to a different player after it
    # was drawn. The draw-time tallies these two held are no longer correct.
    act["saveValueInCache"] = [e for e in svc
                               if e["name"] not in ("playerToMultiplication",
                                                    "playerToAddition")]
    act["saveValueInCache"].extend([
        cache("pendingStop", []),
        cache("mustHit", []),
        cache("touched", []),
        cache("stealQueue", []),
        cache("swapQueue", []),
        cache("discardQueue", []),
        cache("penQueue", []),
        cache("penCards", []),
        cache("penReady", False), cache("penPossible", False),
        cache("penDrop", False),
        cache("flipIdle", True), cache("aliveCount", 0),
        cache("stlReady", False), cache("stlHasCards", False),
        cache("swpaReady", False), cache("swpaHasCards", False),
        cache("swpbReady", False), cache("swpbHasCards", False),
        cache("dscReady", False), cache("dscHasCards", False),
        cache("stlPossible", False), cache("stlDrop", False),
        cache("swpPossible", False), cache("swpaDrop", False),
        cache("dscPossible", False), cache("dscDrop", False),
    ])


def patch_tutorial(g):
    """Point the rules at the chosen variant's copy."""
    loop = g["gameLoop"]
    grp = loop[group_index(loop, "Tutorial")]
    for a in grp["actions"]:
        cached = (a.get("payload") or {}).get("cached") or {}
        if cached.get("text") == "overviewText":
            cached["text"] = "overviewTextV"
        elif cached.get("text") == "modifiersText":
            cached["text"] = "modifiersTextV"
        elif cached.get("text") == "actionsText":
            cached["text"] = "actionsTextV"

    # The three special number cards only exist in Naughty, so they get their
    # own slide rather than being crammed into the actions one.
    after_actions = next(i for i, a in enumerate(grp["actions"])
                         if (a.get("payload") or {}).get("cached", {}).get("text")
                         == "actionsTextV")
    grp["actions"].insert(after_actions + 1, {
        "key": "createNotification",
        "skipCondition": sel("logicalNOT", C("arg", "naughty")),
        "payload": {
            "preset": {"duration": 30},
            "cached": {"header": "naughtySpecialNumbersHeader",
                       "text": "naughtySpecialNumbersText",
                       "to": "learners"},
        },
    })


def patch_deal(g):
    """Track the drawing player's pile, and handle Unlucky 7 on the way in."""
    inner = inner_loop(g)
    grp = inner[group_index(inner, "Deal 1 card to each remaining player")]

    svc_insert_after(grp["actions"][0], "thisPlayer", [
        cache("thisDeck", player_deck_of(C("element", "thisPlayer"))),
    ])

    # A penalty is never kept by whoever turned it over. Queue the drawer and
    # the card together — both lists gain an entry or neither does, so they stay
    # index-aligned — and the hand-off flow deals with it. Hung off the deal,
    # which is the first point at which `cardNames` names the drawn card.
    # `penaltyCards` is empty in Nice, where a modifier is a bonus you want.
    dealt = next(a for a in grp["actions"]
                 if any(e["name"] == "justDrewToPlayer"
                        for e in a.get("saveValueInCache", [])))
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

    # The draw-time modifier tallies are gone (see patch_prepare_round).
    grp["actions"] = [
        a for a in grp["actions"]
        if not (a.get("key") == "emptyAction"
                and any(e["name"] in ("playerToMultiplication", "playerToAddition")
                        for e in a.get("saveValueInCache", [])))
    ]

    # Unlucky 7: the moment it lands, everything else in front of the player is
    # thrown away. Easiest correct way to do that is to sweep the whole pile
    # into the discard and then deal one 7 straight back.
    drew_unlucky = sel("notEqual", C("arg1", "cardNames.0"), C("arg2", "unluckyCard"))
    grp["actions"].extend([
        {"key": "moveCards",
         "skipCondition": drew_unlucky,
         "payload": {"preset": {"type": "deck", "to": "discard"},
                     "cached": {"from": "thisDeck"}}},
        # `type: "number"` covers every card in the deck JSON except hit/stay,
        # which the player needs to keep in order to take their turn.
        {"key": "recallCards",
         "skipCondition": sel("isPrevActionSkipped"),
         "payload": {"preset": {"deck": "copies", "type": "number"},
                     "cached": {"targets": "thisPlayer"}}},
        {"key": "moveCards",
         "skipCondition": sel("isPrevActionSkipped"),
         "payload": {"preset": {"type": "deck", "qnt": 1, "from": "discard"},
                     "cached": {"to": "thisDeck", "cardNames": "unluckyCardList"}}},
        {"key": "dealDeck",
         "skipCondition": sel("isPrevActionSkipped"),
         "payload": {"preset": {"deck": "copies", "qnt": 1,
                                "sortBy": "rank", "order": "asc"},
                     "cached": {"targets": "thisPlayer",
                                "cardNames": "unluckyCardList"}}},
    ])


def patch_busted_leave_stopped(g):
    """A player who busts should stop being shown as stopped.

    Only reachable in Naughty, where a Swap can bust somebody who had already
    stayed — without this they stay blue instead of turning red.
    """
    inner = inner_loop(g)
    handle = inner[group_index(inner, "Handle players who bust")]
    svc_insert_after(handle["actions"][0], "allBusted", [
        cache("allStopped", sel("listsSubtract",
                                C("list1", "allStopped"),
                                C("list2", "busted"))),
    ])


def patch_bust_and_score(g):
    """Lucky 13, The Zero, and scoring read from the hand instead of a tally."""
    inner = inner_loop(g)
    grp = inner[group_index(inner, "Compute players who bust")]
    setup = grp["actions"][0]

    # Read the hand once — five of the values below are derived from it.
    svc_insert_after(setup, "thisDeck", [
        cache("handNames", sel("fetchHandField",
                               C("playerId", "thisPlayer"), P("field", "name"))),
    ])
    svc_entry(setup, "cardsWithoutSpecials")["value"] = sel(
        "listsSubtract", C("list1", "handNames"), C("list2", "specialCards"))

    # Lucky 13 needs no rule of its own any more: it is a single card with its
    # own name, so holding it next to an ordinary 13 is not a duplicate and
    # cannot bust, while two ordinary 13s still share a name and still do.
    #
    # The Unlucky 7 needs the opposite nudge. It is also its own name, but it is
    # still a 7 — holding it alongside an ordinary 7 has to bust exactly as two
    # ordinary 7s would, and the duplicate check can no longer see that.
    still_in = svc_entry(setup, "stillIn")
    still_in["value"] = sel(
        "logicalAND",
        X("arg1", still_in["value"]),
        X("arg2", sel("logicalNOT", X("arg", sel(
            "logicalAND",
            X("arg1", sel("contains",
                          C("list", "handNames"), C("element", "plainSevenCard"))),
            X("arg2", sel("contains",
                          C("list", "handNames"), C("element", "unluckyCard"))))))))

    svc_insert_after(setup, "stillIn", [
        # Modifiers, read off the hand so that a stolen or swapped modifier
        # scores for whoever is holding it now.
        cache("handModifiers", sel(
            "trueSubtract",
            C("list1", "handNames"),
            X("list2", sel("listsSubtract",
                           C("list1", "handNames"),
                           C("list2", "additionCards"))))),
        # The leading 0 keeps the sum well defined when a player holds none.
        cache("handAddition", sel("sumAllElementsList", X("list", sel(
            "concat",
            X("list1", sel("createList", P("arg1", 0))),
            X("list2", sel("listByDictionary",
                           C("list", "handModifiers"),
                           C("dict", "specialCardToAddition"))))))),
        cache("hasMultiplier", sel("contains",
                                   C("list", "handNames"),
                                   C("element", "multiplierCard"))),
        cache("baseScore", sel("getCardsScore", C("hand", "thisPlayer"))),
        # The Zero wipes the round unless the player gets all the way to a
        # Rainbow, and forces them to keep hitting until then.
        cache("hasZero", sel("contains",
                             C("list", "handNames"), C("element", "zeroCard"))),
        cache("hasZeroPenalty", sel(
            "logicalAND",
            C("arg1", "hasZero"),
            X("arg2", sel("logicalNOT", X("arg", sel(
                "equals",
                C("arg1", "numUniqueCardsWithoutSpecials"),
                C("arg2", "rainbow"))))))),
        cache("mustHit", sel("ifElse",
                             C("condition", "hasZero"),
                             X("thenValue", sel("append",
                                                C("list", "mustHit"),
                                                C("element", "thisPlayer"))),
                             C("elseValue", "mustHit"))),
    ])

    # A player can be evaluated twice in one tick — once here, once in the
    # settle pass after a card is moved on them — and the Rainbow bonus is paid
    # per entry in this list, so a duplicate would pay 25 points twice.
    rainbow = svc_entry(setup, "rainbowPlayers")
    rainbow["value"] = sel("unique", X("list", rainbow["value"]))

    # Rebuild the surviving player's score from the hand.
    round_score = sel(
        "add",
        X("arg1", sel("ifElse",
                      C("condition", "hasMultiplier"),
                      X("thenValue", sel("ifElse",
                                         C("condition", "naughty"),
                                         X("thenValue", sel("integerDivide",
                                                            C("arg1", "baseScore"),
                                                            P("arg2", 2))),
                                         X("elseValue", sel("multiply",
                                                            C("arg1", "baseScore"),
                                                            P("arg2", 2))))),
                      C("elseValue", "baseScore"))),
        C("arg2", "handAddition"))

    score_action = grp["actions"][-1]
    assert score_action["key"] == "updateScore"
    score_action["payload"]["computed"]["scores"] = sel(
        "createItemList",
        P("length", 1),
        X("item", sel(
            "createDict",
            P("keys", ["list", "score"]),
            X("values", sel(
                "createList",
                X("arg1", sel("createList", C("arg1", "thisPlayer"))),
                X("arg2", sel(
                    "add",
                    X("arg1", sel("getCachedObjectValue",
                                  P("objectName", "playerToPrevScore"),
                                  C("value", "thisPlayer"))),
                    X("arg2", sel("ifElse",
                                  C("condition", "hasZeroPenalty"),
                                  P("thenValue", 0),
                                  X("elseValue", round_score))))))))))


def patch_promote_pending_stops(g):
    """A Just One More victim stops once their forced card has been dealt."""
    inner = inner_loop(g)
    at = group_index(inner, "Handle players who bust") + 1
    inner.insert(at, {
        "name": "Naughty: stop the players who took one more card",
        "skipCondition": [sel("equals",
                              X("arg1", sel("listLength", C("list", "pendingStop"))),
                              P("arg2", 0))],
        "actions": [{
            "key": "emptyAction",
            "saveValueInCache": [
                # Anyone who busted on the forced card is already out.
                cache("pendingSurvivors", sel("listsSubtract",
                                              C("list1", "pendingStop"),
                                              C("list2", "allBusted"))),
                cache("remainingPlayers", sel("listsSubtract",
                                              C("list1", "remainingPlayers"),
                                              C("list2", "pendingSurvivors"))),
                cache("allStopped", sel("unique", X("list", sel(
                    "concat",
                    C("list1", "allStopped"),
                    C("list2", "pendingSurvivors"))))),
                cache("pendingStop", []),
            ],
        }],
    })


def patch_collect_drawers(g):
    """Collect this tick's action-card drawers, including the three new ones."""
    inner = inner_loop(g)
    grp = inner[group_index(inner, "Freezers and flippers")]
    act = grp["actions"][0]

    # The existing freeze/flip lookups are keyed by a hardcoded card name.
    for entry in act["saveValueInCache"]:
        v = entry.get("value")
        if isinstance(v, dict) and v.get("selector") == "getCachedObjectValue":
            for prm in v["params"]:
                if prm.get("name") == "value" and prm.get("value") == "freeze":
                    prm.update({"type": "cached", "value": "stopCard"})
                elif prm.get("name") == "value" and prm.get("value") == "flip":
                    prm.update({"type": "cached", "value": "flipCard"})

    def drawers_of(card_var):
        """Who drew this card this tick — nobody while a forced flip runs."""
        return sel("ifElse",
                   C("condition", "flipActive"),
                   P("thenValue", []),
                   X("elseValue", sel("getCachedObjectValue",
                                      P("objectName", "justDrewToPlayer"),
                                      C("value", card_var),
                                      P("defaultValue", []))))

    # Steal, Swap and Discard each need a run of prompts, so they queue up and
    # one is served per tick. Two players drawing the same action card on the
    # same tick is rare; the second one resolves on the following tick rather
    # than being dropped.

    def queue(name, card_var):
        return cache(name, sel("concat",
                               C("list1", name),
                               X("list2", drawers_of(card_var))))

    def non_empty(queue_var):
        return sel("greaterThan",
                   X("arg1", sel("listLength", C("list", queue_var))),
                   P("arg2", 0))

    def possible(name, minimum):
        """Are there enough players still holding cards for this to mean anything?

        Busted players are out: their pile scores nothing and cannot be taken
        from. Stopped players still count — reaching across at somebody who
        thought they were safe is the point of these cards.
        """
        return cache(name, sel("greaterThanOrEqual",
                               C("arg1", "aliveCount"), P("arg2", minimum)))

    def ready(name, queue_var, possible_var):
        """Runnable right now: something queued, enough targets, no flip mid-run."""
        return cache(name, sel(
            "logicalAND",
            X("arg1", sel("logicalAND",
                          X("arg1", non_empty(queue_var)),
                          C("arg2", possible_var))),
            C("arg2", "flipIdle")))

    def drop(name, queue_var, ready_var, possible_var):
        """Time to take this card off the queue.

        Either it just resolved, or it never can — the table has shrunk below
        what the card needs, and that only ever gets worse within a round. A
        forced flip is the one case we wait out rather than discard.
        """
        return cache(name, sel(
            "logicalAND",
            X("arg1", non_empty(queue_var)),
            X("arg2", sel("logicalOR",
                          C("arg1", ready_var),
                          X("arg2", sel("logicalNOT", C("arg", possible_var)))))))

    act["saveValueInCache"].extend([
        queue("stealQueue", "stealCard"),
        queue("swapQueue", "swapCard"),
        queue("discardQueue", "discardCard"),
        cache("flipIdle", sel("logicalNOT", C("arg", "flipActive"))),
        cache("aliveCount", sel("listLength", X("list", sel(
            "listsSubtract", C("list1", "players"), C("list2", "allBusted"))))),
        # Steal and Discard need one other player to point at. Swap names two
        # players besides being played, so it needs a table of three.
        possible("stlPossible", 2),
        possible("swpPossible", 3),
        possible("dscPossible", 2),
        # A penalty needs one other unbusted player to land on. With nobody
        # else left the drawer keeps it, which is the rule.
        possible("penPossible", 2),
        ready("penReady", "penQueue", "penPossible"),
        drop("penDrop", "penQueue", "penReady", "penPossible"),
        ready("stlReady", "stealQueue", "stlPossible"),
        ready("swpaReady", "swapQueue", "swpPossible"),
        ready("dscReady", "discardQueue", "dscPossible"),
        drop("stlDrop", "stealQueue", "stlReady", "stlPossible"),
        drop("swpaDrop", "swapQueue", "swpaReady", "swpPossible"),
        drop("dscDrop", "discardQueue", "dscReady", "dscPossible"),
        # Cleared here so a flow that does not run cannot be fooled by the
        # values another flow left behind.
        cache("stlHasCards", False),
        cache("swpaHasCards", False),
        cache("swpbHasCards", False),
        cache("swpbReady", False),
        cache("dscHasCards", False),
    ])


def patch_just_one_more(g):
    """Freeze becomes "draw one more card, then stop" in Naughty."""
    inner = inner_loop(g)
    grp = inner[group_index(inner, "Handle freeze")]

    vote = grp["actions"][action_index(grp, "createCardVote")]
    vote["payload"]["computed"]["question"]["params"][0] = C("format", "stopQuestionText")

    # In Naughty the victim is not stopped yet: they are made to hit once, and
    # "Naughty: stop the players who took one more card" retires them after the
    # next deal. In Nice they stop immediately, exactly as before.
    stopped = svc_entry(vote, "stopped")
    stopped["value"] = sel("ifElse",
                           C("condition", "naughty"),
                           C("thenValue", "stopped"),
                           X("elseValue", stopped["value"]))
    svc_insert_after(vote, "stopped", [
        cache("pendingStop", sel("ifElse",
                                 C("condition", "naughty"),
                                 X("thenValue", sel("concat",
                                                    C("list1", "pendingStop"),
                                                    C("list2", "frozen"))),
                                 C("elseValue", "pendingStop"))),
        cache("mustHit", sel("ifElse",
                             C("condition", "naughty"),
                             X("thenValue", sel("concat",
                                                C("list1", "mustHit"),
                                                C("list2", "frozen"))),
                             C("elseValue", "mustHit"))),
    ])

    for a in grp["actions"]:
        preset = (a.get("payload") or {}).get("preset") or {}
        if preset.get("cardNames") == ["freeze"]:
            del preset["cardNames"]
            a["payload"].setdefault("cached", {})["cardNames"] = "stopCardList"


def patch_flip_four(g):
    """Force Flip deals four cards instead of three in Naughty."""
    inner = inner_loop(g)
    grp = inner[group_index(inner, "Handle flip")]

    svc_entry(grp["actions"][0], "flipsLeft")["value"] = copy_of("flipCount")

    vote = grp["actions"][action_index(grp, "createCardVote")]
    vote["payload"]["computed"]["question"]["params"][0] = C("format", "flipQuestionText")

    for a in grp["actions"]:
        preset = (a.get("payload") or {}).get("preset") or {}
        if preset.get("cardNames") == ["flip"]:
            del preset["cardNames"]
            a["payload"].setdefault("cached", {})["cardNames"] = "flipCardList"

    # The follow-up group fires on the first card of the run, so it has to
    # compare against the variant's flip length rather than a literal 3.
    follow = inner[group_index(inner, "Update variables for flip, change layout for flip")]
    follow["skipCondition"] = [sel("notEqual",
                                   C("arg1", "flipsLeft"),
                                   C("arg2", "flipCount"))]


def patch_hit_or_stay(g):
    """Players holding The Zero, or a Just One More, cannot choose to stop."""
    inner = inner_loop(g)
    grp = inner[group_index(inner, "Hit or stay")]
    play = grp["actions"][action_index(grp, "playCards")]

    del play["payload"]["preset"]["playableInclude.cards"]
    play["payload"]["computed"]["playableInclude.cards"] = sel(
        "ifElse",
        X("condition", sel("contains",
                           C("list", "mustHit"),
                           X("element", sel("selectElement",
                                            C("list", "remainingPlayers"),
                                            C("index", "spaIndex"))))),
        C("thenValue", "hitOnlyCards"),
        C("elseValue", "hitStayCards"))


def patch_carry_must_hit(g):
    """Carry the forced-hit list across the tick boundary."""
    inner = inner_loop(g)
    grp = inner[group_index(inner, "Initialize variables")]
    # Rebuilt from scratch every tick: whoever still owes a forced card, plus
    # (added in the bust group) whoever is holding The Zero.
    grp["actions"][0]["saveValueInCache"].append(
        cache("mustHit", copy_of("pendingStop")))


def patch_odds(g):
    """A second 13 is not a bust, so it should not count against the odds."""
    inner = inner_loop(g)
    grp = inner[group_index(inner, "Update odds")]
    scores = grp["actions"][0]["payload"]["computed"]["scores"]

    def find_subtract(node):
        """The listsSubtract that produces the player's own number cards."""
        if isinstance(node, dict):
            if (node.get("selector") == "listsSubtract"
                    and any(p.get("name") == "list2" and p.get("value") == "specialCards"
                            for p in node.get("params", []))):
                return node
            for v in node.values():
                found = find_subtract(v)
                if found:
                    return found
        elif isinstance(node, list):
            for v in node:
                found = find_subtract(v)
                if found:
                    return found
        return None

    dangerous = find_subtract(scores)
    inner_copy = dict(dangerous)
    dangerous.clear()
    dangerous.update(sel("listsSubtract",
                         X("list1", inner_copy),
                         X("list2", sel("createList", C("arg1", "luckyCard")))))


def patch_settle_moved_cards(g):
    """Re-run bust and scoring on everyone a card was moved on, same tick.

    A Steal moves points from one player to another, a Discard destroys some,
    and a Swap can do both at once — and any of those can hand somebody a
    number they already hold. None of that is picked up by the bust group,
    which ran earlier in the tick and only walks the players still taking
    turns. Waiting for the next tick is not good enough either: if the round
    ends on this one, the scores that get saved are the ones from before the
    card moved.

    The per-player maths is deep-copied out of the bust group rather than
    written out again, so the two can never drift apart.
    """
    inner = inner_loop(g)
    bust = inner[group_index(inner, "Compute players who bust")]

    evaluate = copy.deepcopy(bust["actions"][0])
    svc_entry(evaluate, "thisPlayer")["value"] = sel(
        "selectElement", C("list", "settleList"), C("index", "repeatIndex"))
    # Forced-hit tracking belongs to the deal, not to a card changing hands.
    evaluate["saveValueInCache"] = [e for e in evaluate["saveValueInCache"]
                                    if e["name"] != "mustHit"]

    highlight_bust = copy.deepcopy(bust["actions"][action_index(bust, "highlightDecks")])
    score_busted = copy.deepcopy(bust["actions"][-2])
    score_survivor = copy.deepcopy(bust["actions"][-1])
    assert score_busted["key"] == "updateScore" and score_survivor["key"] == "updateScore"

    bookkeeping = {
        "key": "emptyAction",
        "skipCondition": sel("getCachedValue", P("name", "stillIn")),
        "saveValueInCache": [
            cache("settleOne", sel("createList", C("arg1", "thisPlayer"))),
            cache("settleBusted", sel("append",
                                      C("list", "settleBusted"),
                                      C("element", "thisPlayer"))),
            cache("allBusted", sel("unique", X("list", sel(
                "concat", C("list1", "allBusted"), C("list2", "settleOne"))))),
            cache("remainingPlayers", sel("listsSubtract",
                                          C("list1", "remainingPlayers"),
                                          C("list2", "settleOne"))),
            cache("allStopped", sel("listsSubtract",
                                    C("list1", "allStopped"),
                                    C("list2", "settleOne"))),
        ],
    }

    nothing_moved = [sel("equals",
                         X("arg1", sel("listLength", C("list", "touched"))),
                         P("arg2", 0))]

    groups = [
        {
            "name": "Naughty: work out whose cards moved",
            "skipCondition": nothing_moved,
            "actions": [{
                "key": "emptyAction",
                "saveValueInCache": [
                    cache("settleBusted", []),
                    # A Steal touches two players; a Swap that the swapper is
                    # part of can name the same player twice.
                    cache("settleList", sel("unique", C("list", "touched"))),
                ],
            }],
        },
        {
            "name": "Naughty: rescore them",
            "skipCondition": nothing_moved,
            "repeat": {"qnt": sel("listLength", C("list", "settleList"))},
            "actions": [evaluate, highlight_bust, bookkeeping,
                        score_busted, score_survivor],
        },
    ]

    # Deck labels carry each player's score, so they have to be redrawn too.
    # Rebuilt key by key to keep the canonical action-group field order.
    src = inner[group_index(inner, "Relabel")]
    groups.append({
        "name": "Naughty: redraw the scores on the piles",
        "skipCondition": nothing_moved,
        "repeat": copy.deepcopy(src["repeat"]),
        "actions": copy.deepcopy(src["actions"]),
    })

    groups.append({
        "name": "Naughty: show who it cost",
        "skipCondition": nothing_moved,
        "actions": [
            {"key": "emptyAction",
             "skipCondition": sel("equals",
                                  X("arg1", sel("listLength", C("list", "settleBusted"))),
                                  P("arg2", 0)),
             "payload": {"preset": {"sounds.waitForSoundEnd": False,
                                    "sounds.list": ["soundboard.elimination"]},
                         "cached": {"playList.1": "players"}}},
            {"key": "animateBox",
             "skipCondition": sel("isPrevActionSkipped"),
             "payload": {"preset": {"animation": "dead"},
                         "cached": {"userIds": "settleBusted"}}},
            {"key": "removeAllHighlights"},
            {"key": "highlightPlayers",
             "payload": {"preset": {"color": "red"},
                         "cached": {"listOfPlayers": "allBusted"}}},
            {"key": "highlightPlayers",
             "payload": {"preset": {"color": "blue"},
                         "cached": {"listOfPlayers": "allStopped"}}},
            {"key": "highlightPlayers",
             "payload": {"preset": {"color": "green"},
                         "cached": {"listOfPlayers": "remainingPlayers"}}},
            {"key": "emptyAction", "saveValueInCache": [cache("touched", [])]},
        ],
    })

    at = group_index(inner, "Naughty: discard - restore the board") + 1
    inner[at:at] = groups


def patch_round_cleanup(g):
    """Sweep the variant's working decks into the discard at round end."""
    loop = g["gameLoop"]
    grp = loop[group_index(loop, "Clean up cards, advance round")]
    at = next(i for i, a in enumerate(grp["actions"])
              if a.get("key") == "moveCards"
              and (a["payload"].get("cached") or {}).get("from") == "playerDecks")
    grp["actions"][at + 1:at + 1] = [
        {"key": "moveCards",
         "payload": {"preset": {"type": "deck", "from": "swap_hold",
                                "to": "discard"}}},
        {"key": "moveCards",
         "payload": {"preset": {"type": "deck", "to": "discard"},
                     "cached": {"from": "pickDeckNames"}}},
    ]


def patch_action_cards(g):
    """Drop the penalty hand-off, Steal, Swap and Discard in after the stop
    cards resolve.

    The penalty goes first: it is the shortest prompt and it decides who is
    holding what before the card-moving cards start reaching across the table.
    """
    inner = inner_loop(g)
    at = group_index(inner, "Handle stopped players from freezing") + 1
    inner[at:at] = (penalty_groups() + steal_groups() + swap_groups()
                    + discard_groups())


# ── entry point ─────────────────────────────────────────────────────────────
def load_game():
    if "--local" in sys.argv:
        return json.load(open(GAME))
    with urllib.request.urlopen(PROD, timeout=90) as r:
        raw = json.load(r).get("raw")
    return json.loads(raw) if isinstance(raw, str) else raw


def main():
    g = load_game()

    patch_strings(g)
    patch_cheatsheet(g)
    patch_before_loop(g)
    patch_pick_decks(g)
    patch_prepare_round(g)
    patch_tutorial(g)
    patch_carry_must_hit(g)
    patch_deal(g)
    patch_bust_and_score(g)
    patch_busted_leave_stopped(g)
    patch_promote_pending_stops(g)
    patch_collect_drawers(g)
    patch_just_one_more(g)
    patch_round_cleanup(g)
    patch_action_cards(g)
    patch_settle_moved_cards(g)
    patch_flip_four(g)
    patch_hit_or_stay(g)
    patch_odds(g)

    with open(GAME, "w") as f:
        json.dump(g, f, indent=2)
        f.write("\n")

    inner = inner_loop(g)
    print("wrote %s" % GAME)
    print("  gameLoop groups: %d, inner-loop groups: %d"
          % (len(g["gameLoop"]), len(inner)))
    print("  size: %.1f KB" % (os.path.getsize(GAME) / 1024.0))


if __name__ == "__main__":
    main()
