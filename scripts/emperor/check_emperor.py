#!/usr/bin/env python3
"""Evaluate Emperor's preHandlers against known-good rulings.

  python3 scripts/emperor/check_emperor.py

The play rule lives inside a selector tree in the generated game JSON, where it
cannot be exercised without a live table. So this reads the tree straight out of
game_jsons/emperor.json, interprets it over the handful of selectors it
uses, and asserts the ruling for every case that matters — legal climbs, the
count rule, Jesters as wild, passing, and the two taxes.

It reads the SHIPPED JSON, not the builder's Python, so a refactor that changes
what the game actually enforces gets caught.

`listsSubtract` is the one selector whose multiset semantics I could not confirm
from the engine docs, so every case runs TWICE — once assuming it drops one
occurrence, once assuming it drops all — and both must agree. Any rule that
depends on which is right fails here rather than at a table.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
GAME = os.path.join(HERE, "..", "..", "game_jsons", "emperor.json")
JESTER = 13
NO_LEAD = 14


class Ctx:
    def __init__(self, cache, hands=None, subtract_all=True):
        self.cache = cache
        self.hands = hands or {}
        self.subtract_all = subtract_all


def get(ctx, path):
    """Resolve a cached reference, honouring dotted paths like 'order.0'."""
    cur = ctx.cache
    for i, part in enumerate(path.split(".")):
        if isinstance(cur, list):
            cur = cur[int(part)]
        else:
            cur = cur[part]
    return cur


def arg(ctx, p):
    t = p["type"]
    if t == "preset":
        return p["value"]
    if t == "cached":
        return get(ctx, p["value"])
    return ev(ctx, p["value"])


def ev(ctx, node):
    sel = node["selector"]
    p = {x["name"]: x for x in node.get("params", [])}
    v = lambda n: arg(ctx, p[n])

    if sel == "getCachedValue":
        return get(ctx, p["name"]["value"])
    if sel == "logicalAND":
        return all(v(k) for k in p)
    if sel == "logicalOR":
        return any(v(k) for k in p)
    if sel == "logicalNOT":
        return not v("arg")
    if sel == "equals":
        return v("arg1") == v("arg2")
    if sel == "notEqual":
        return v("arg1") != v("arg2")
    if sel == "lessThan":
        return v("arg1") < v("arg2")
    if sel == "lessThanOrEqual":
        return v("arg1") <= v("arg2")
    if sel == "greaterThan":
        return v("arg1") > v("arg2")
    if sel == "greaterThanOrEqual":
        return v("arg1") >= v("arg2")
    if sel == "listLength":
        return len(v("list"))
    if sel == "minValue":
        return min(v("list"))
    if sel == "maxValue":
        return max(v("list"))
    if sel == "unique":
        seen, out = set(), []
        for x in v("list"):
            if x not in seen:
                seen.add(x)
                out.append(x)
        return out
    if sel == "append":
        return list(v("list")) + [v("element")]
    if sel == "createList":
        return [v(k) for k in p]
    if sel == "listsSubtract":
        l1, l2 = list(v("list1")), list(v("list2"))
        if ctx.subtract_all:
            return [x for x in l1 if x not in l2]
        out = list(l1)
        for x in l2:
            if x in out:
                out.remove(x)
        return out
    if sel == "dec":
        return v("arg") - 1
    if sel == "inc":
        return v("arg") + 1
    if sel == "subtract":
        return v("arg1") - v("arg2")
    if sel == "multiply":
        return v("arg1") * v("arg2")
    if sel == "selectElement":
        return v("list")[v("index")]
    if sel == "createDict":
        return dict(zip(v("keys"), v("values")))
    if sel == "ifElse":
        return v("thenValue") if v("condition") else v("elseValue")
    if sel == "fetchCardsField":
        return [c[p["field"]["value"]] for c in v("cards")]
    if sel == "fetchHandField":
        return [c[p["field"]["value"]] for c in ctx.hands[v("playerId")]]
    raise AssertionError("check_emperor cannot evaluate selector %r" % sel)


# ------------------------------------------------------------------ locate
def find_actions(data, key):
    out = []

    def walk(o):
        if isinstance(o, dict):
            if o.get("key") == key and "preHandler" in o:
                out.append(o)
            for x in o.values():
                walk(x)
        elif isinstance(o, list):
            for x in o:
                walk(x)

    walk(data)
    return out


def cards(*ranks):
    return [{"rank": r} for r in ranks]


def main():
    data = json.load(open(GAME))
    plays = find_actions(data, "playCards")
    turn = next(a for a in plays
                if a["payload"]["preset"].get("target") == "play_area")
    tax2 = next(a for a in plays
                if a["payload"]["preset"].get("target") == "tax_high")
    tax1 = next(a for a in plays
                if a["payload"]["preset"].get("target") == "tax_low")

    failures = []

    def check(label, tree, cache, expect, hands=None):
        for subtract_all in (True, False):
            ctx = Ctx(dict(cache), hands, subtract_all)
            try:
                got = bool(ev(ctx, tree))
            except Exception as e:
                failures.append("%s [listsSubtract-all=%s] raised %s: %s"
                                % (label, subtract_all, type(e).__name__, e))
                continue
            if got != expect:
                failures.append("%s [listsSubtract-all=%s] expected %s got %s"
                                % (label, subtract_all, expect, got))

    # ---- leading a fresh trick (leadCount 0, leadRank 14) ---------------
    lead = {"isLeading": True, "leadCount": 0, "leadRank": NO_LEAD}
    T = turn["preHandler"]["success"]
    check("lead one 7", T, dict(lead, inputCards=cards(7)), True)
    check("lead three 9s", T, dict(lead, inputCards=cards(9, 9, 9)), True)
    check("lead twelve 12s", T, dict(lead, inputCards=cards(*([12] * 12))), True)
    check("lead mixed ranks 4+7", T, dict(lead, inputCards=cards(4, 7)), False)
    check("lead two Jesters alone", T, dict(lead, inputCards=cards(13, 13)), True)
    check("lead 5,5 + Jester", T, dict(lead, inputCards=cards(5, 5, 13)), True)
    check("cannot pass when leading", T, dict(lead, inputCards=[]), False)

    # ---- following a lead of three 9s -----------------------------------
    face = {"isLeading": False, "leadCount": 3, "leadRank": 9}
    check("three 4s beat three 9s", T, dict(face, inputCards=cards(4, 4, 4)), True)
    check("two 4s do not (wrong count)", T, dict(face, inputCards=cards(4, 4)), False)
    check("four 4s do not (wrong count)", T, dict(face, inputCards=cards(4, 4, 4, 4)), False)
    check("three 10s do not (too high)", T, dict(face, inputCards=cards(10, 10, 10)), False)
    check("three 9s do not (equal rank)", T, dict(face, inputCards=cards(9, 9, 9)), False)
    check("two 4s + Jester beat three 9s", T, dict(face, inputCards=cards(4, 4, 13)), True)
    check("4 + two Jesters beat three 9s", T, dict(face, inputCards=cards(4, 13, 13)), True)
    check("three Jesters impossible but harmless", T,
          dict(face, inputCards=cards(13, 13, 13)), False)
    check("mixed 4,5,6 rejected", T, dict(face, inputCards=cards(4, 5, 6)), False)
    check("pass is legal", T, dict(face, inputCards=[]), True)

    # A lead of a single Jester pair is rank 13, so anything real beats it.
    jface = {"isLeading": False, "leadCount": 2, "leadRank": JESTER}
    check("two 12s beat two Jesters", T, dict(jface, inputCards=cards(12, 12)), True)
    check("two Jesters cannot beat two Jesters", T,
          dict(jface, inputCards=cards(13, 13)), False)

    # ---- the two-card tax: must be the payer's two lowest ---------------
    T2 = tax2["preHandler"]["success"]
    hand = {"P": cards(3, 7, 9, 12, 12)}
    base = {"greatSerf": "P"}
    check("tax pays 3 and 7", T2, dict(base, inputCards=cards(3, 7)), True, hand)
    check("tax pays 3 and 9 (holding back)", T2, dict(base, inputCards=cards(3, 9)), False, hand)
    check("tax pays 7 and 9 (keeps the 3)", T2, dict(base, inputCards=cards(7, 9)), False, hand)
    check("tax pays one card only", T2, dict(base, inputCards=cards(3)), False, hand)
    # The duplicate-best case is the one the second_best formula exists for.
    dup = {"P": cards(3, 3, 8, 12)}
    check("duplicate best: pays 3 and 3", T2, dict(base, inputCards=cards(3, 3)), True, dup)
    check("duplicate best: pays 3 and 8", T2, dict(base, inputCards=cards(3, 8)), False, dup)
    # A hand whose two best are a real card and a Jester.
    jest = {"P": cards(6, 13, 13)}
    check("Jester is a payable second-best", T2,
          dict(base, inputCards=cards(6, 13)), True, jest)

    # ---- the one-card tax ------------------------------------------------
    T1 = tax1["preHandler"]["success"]
    lo = {"littleSerf": "Q"}
    hq = {"Q": cards(5, 8, 11)}
    check("lesser tax pays the 5", T1, dict(lo, inputCards=cards(5)), True, hq)
    check("lesser tax pays the 8", T1, dict(lo, inputCards=cards(8)), False, hq)
    check("lesser tax pays two cards", T1, dict(lo, inputCards=cards(5, 8)), False, hq)

    # ---- scoring: the crown pays double the table ------------------------
    # Read the delta straight out of the Award points action and run it for
    # every finishing position, so the payout curve is pinned rather than
    # trusted. Expected at six players: 12 for the crown, then 5,4,3,2,1.
    award = None

    def find_award(o):
        nonlocal award
        if isinstance(o, dict):
            if o.get("key") == "updateScore" and "delta" in json.dumps(o):
                award = award or o
            for x in o.values():
                find_award(x)
        elif isinstance(o, list):
            for x in o:
                find_award(x)

    find_award(data)
    entry = award["payload"]["computed"]["scores"]
    seats = ["p%d" % i for i in range(6)]
    got = []
    for i in range(6):
        ctx = Ctx({"numPlayers": 6, "repeatIndex": i, "finished": seats})
        got.append(ev(ctx, entry)[0]["delta"])
    want = [12, 5, 4, 3, 2, 1]
    if got != want:
        failures.append("scoring at 6 players: expected %s got %s" % (want, got))

    if failures:
        print("FAILED %d ruling(s):" % len(failures))
        for f in failures:
            print("  -", f)
        sys.exit(1)
    print("all preHandler rulings correct "
          "(both listsSubtract semantics, %d cases)" % 26)
    print("scoring curve at 6 players: %s" % want)


if __name__ == "__main__":
    main()
