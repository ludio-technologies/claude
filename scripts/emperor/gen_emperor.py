#!/usr/bin/env python3
"""Build Emperor — deck, game JSON and rulebook.

  python3 scripts/emperor/gen_emperor.py

Writes game_jsons/emperor_cards.json, emperor.json and
emperor_describe.json. This script is the source of truth: the JSON under
game_jsons/ is generated, so change the rules here and re-run, never by hand.

Card art comes from scripts/emperor/emperor_images.json — run
gen_emperor_images.py first if that file is missing.

WHY A PREHANDLER GAME
---------------------
Emperor's play rule ("same number of cards as the lead, all one rank, lower than
the lead, Jesters wild") cannot be expressed with playCards' minCards/maxCards
alone, and rejecting a bad play after the cards have already left the hand is not
recoverable. preHandler runs BEFORE the cards move and hands the player back an
error, so the rule can live in the action that enforces it.
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
GJ = os.path.join(ROOT, "game_jsons")
IMAGES = json.load(open(os.path.join(HERE, "emperor_images.json")))

TITLES = {
    1: "Emperor", 2: "Archbishop", 3: "Earl Marshal", 4: "Baroness",
    5: "Abbess", 6: "Knight", 7: "Seamstress", 8: "Mason", 9: "Cook",
    10: "Shepherdess", 11: "Stonecutter", 12: "Peasant", 13: "Jester",
}
JESTER_RANK = 13
DECK_NAME = "emperor_cards"
DECK_SIZE = 80          # 78 numbered (rank N appears N times) + 2 Jesters
NO_LEAD_RANK = 14       # sentinel: beats nothing, everything beats it
MIN_PLAYERS, MAX_PLAYERS = 3, 8

BG, BORDER, TEXT = "#2B1B4A", "#C9A227", "white"
WOOD = "https://res.cloudinary.com/liars-club/image/upload/wood_qbegm0.jpg"
TRANSPARENT = "https://res.cloudinary.com/liars-club/image/upload/transparent_sbx4wv.png"
WINNER_GIF = "https://res.cloudinary.com/liars-club/image/upload/winner_h5eyfr.gif"
AVATAR = "https://res.cloudinary.com/liars-club/image/upload/card_player_ed7jck.webp"


# --------------------------------------------------------------------- DSL
class Cached(str):
    """Marks a string as a cache reference rather than a literal."""


def C(name):
    return Cached(name)


def _param(name, value):
    if isinstance(value, Cached):
        return {"name": name, "type": "cached", "value": str(value)}
    if isinstance(value, dict) and "selector" in value:
        return {"name": name, "type": "computed", "value": value}
    return {"name": name, "type": "preset", "value": value}


def S(_selector, **params):
    """A selector. kwargs keep their written order, which is the param order."""
    return {"selector": _selector, "params": [_param(k, v) for k, v in params.items()]}


def _split(payload):
    """Sort a flat {field: value} payload into preset / cached / computed.

    A trailing underscore is stripped, so `from_` reaches the engine as the
    payload field `from` without colliding with the Python keyword.
    """
    preset, cached, computed = {}, {}, {}
    for k, v in payload.items():
        k = k[:-1] if k.endswith("_") else k
        if isinstance(v, Cached):
            cached[k] = str(v)
        elif isinstance(v, dict) and "selector" in v:
            computed[k] = v
        else:
            preset[k] = v
    out = {}
    for name, section in (("preset", preset), ("cached", cached), ("computed", computed)):
        if section:
            out[name] = section
    return out


def A(key, skipCondition=None, postHandler=None, saveValueInCache=None,
      preHandler=None, **payload):
    """An action. Field order matches the repo's canonical ACTION_FIELD_ORDER."""
    act = {"key": key}
    if skipCondition is not None:
        act["skipCondition"] = _norm_skip(skipCondition)
    if payload:
        act["payload"] = _split(payload)
    if preHandler is not None:
        act["preHandler"] = preHandler
    if postHandler is not None:
        act["postHandler"] = postHandler
    if saveValueInCache is not None:
        act["saveValueInCache"] = saveValueInCache
    return act


def G(name, actions, skipCondition=None, repeat=None, parallel=None,
      checkWinCondition=None, **flags):
    g = {"name": name}
    for k in ("turnPlayersToSpectators", "turnSpectatorsToPlayers"):
        if k in flags:
            g[k] = flags[k]
    if skipCondition is not None:
        g["skipCondition"] = _norm_skip(skipCondition)
    if repeat is not None:
        g["repeat"] = repeat
    if parallel is not None:
        g["parallel"] = parallel
    if checkWinCondition is not None:
        g["checkWinCondition"] = checkWinCondition
    g["actions"] = actions
    return g


def save(name, value):
    return {"name": name, "value": value}


def getc(name):
    """Read a cache var where a bare `cached` reference is not accepted.

    Only three places need this: the top-level `value` of a saveValueInCache
    entry, a skipCondition entry, and a repeat/parallel `qnt`. Everywhere else —
    payload fields and selector params — use C(name), which the engine reads
    directly and which does not pay for a wrapper selector.
    """
    return S("getCachedValue", name=name)


def _norm_skip(condition):
    """A skipCondition is a LIST of selector objects — a bare cached reference
    is not one, so a boolean flag has to be read through getCachedValue here.
    Normalising centrally means no call site can forget."""
    entries = condition if isinstance(condition, list) else [condition]
    return [getc(str(e)) if isinstance(e, Cached) else e for e in entries]


# Shorthands for the selectors this game leans on hardest.
def LEN(v):
    return S("listLength", list=v)


def AT(lst, index):
    return S("selectElement", list=lst, index=index)


def EQ(a, b):
    return S("equals", arg1=a, arg2=b)


def NOT(v):
    return S("logicalNOT", arg=v)


def AND(*args):
    return S("logicalAND", **{"arg%d" % (i + 1): a for i, a in enumerate(args)})


def OR(*args):
    return S("logicalOR", **{"arg%d" % (i + 1): a for i, a in enumerate(args)})


def IF(cond, then, els):
    return S("ifElse", condition=cond, thenValue=then, elseValue=els)


def WITHOUT(lst, element):
    """listsSubtract drops every occurrence of every element in list2."""
    return S("listsSubtract", list1=lst, list2=S("createList", arg1=element))


def fmt(template, *args):
    kw = {"format": template}
    for i, a in enumerate(args):
        kw["arg%d" % (i + 1)] = a
    return S("formatString", **kw)


def names(ids):
    return S("listToString", list=S("getPlayerNamesByIds", ids=ids))


def name_of(pid):
    return S("getPlayerNameById", id=pid)


# ------------------------------------------------------------------- deck
def build_deck():
    cards = []
    for rank in range(1, 13):
        cards.append({
            "name": "r%d" % rank,
            "label": "%d %s" % (rank, TITLES[rank]),
            "rank": rank,
            # weight drives hand sort order, so a hand always reads best-first.
            "weight": rank,
            "image": IMAGES["r%d" % rank]["url"],
            "type": "emperor",
        })
    cards.append({
        "name": "jester",
        "label": "Jester",
        "rank": JESTER_RANK,
        "weight": JESTER_RANK,
        "image": IMAGES["jester"]["url"],
        "type": "emperor",
    })
    counts = {"r%d" % r: r for r in range(1, 13)}
    counts["jester"] = 2
    assert sum(counts.values()) == DECK_SIZE, sum(counts.values())
    return {"name": DECK_NAME, "cards": cards, "sets": {"full": counts}}


# --------------------------------------------------- emeralds reference blocks
# The validator diffs these against emeralds.json, so lift them from the file
# rather than transcribing — a transcription silently rots when emeralds moves.
_EMERALDS = json.load(open(os.path.join(GJ, "emeralds.json")))


def _recolour(obj):
    """Emeralds' block with its per-action colours dropped, everything else verbatim.

    Colour lives in visualSettings for this game and nowhere else, which is how
    the refactored games (Squaffle, Knockout, Braggart) do it. Emeralds predates
    that and paints each notification inline, so its blocks have to be stripped
    rather than recoloured: its welcome notification carries backgroundColor and
    borderColor but no textColor, so rewriting only the keys already present
    repaints the box dark and leaves the text at the inherited near-black.
    The validator strips these three keys from both sides before diffing against
    emeralds, so removing them keeps the reference comparison passing.
    """
    if isinstance(obj, dict):
        return {k: _recolour(v) for k, v in obj.items()
                if k not in ("backgroundColor", "borderColor", "textColor")}
    if isinstance(obj, list):
        return [_recolour(v) for v in obj]
    return obj


def emeralds_action(key, needle=None, where="beforeLoopActions"):
    found = []

    def walk(o):
        if isinstance(o, dict):
            if o.get("key") == key and (needle is None or needle in json.dumps(o)):
                found.append(o)
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    walk(_EMERALDS[where])
    if not found:
        raise SystemExit("emeralds block not found: %s %s" % (key, needle))
    return _recolour(json.loads(json.dumps(found[0])))


def welcome():
    """The pre-tutorial welcome notification.

    Lifted from emeralds for its structure — the validator checks that the text
    is a formatString naming the host — but the header has to name THIS game.
    Taking it verbatim shipped a box reading "Welcome to Emeralds!" over an
    Emperor banner.
    """
    act = emeralds_action("createNotification", needle="Welcome to Emeralds!")
    act["payload"]["preset"]["header"] = "Welcome to Emperor!"
    return act


# ------------------------------------------------------------------ helpers
def hand_ranks(player):
    return S("fetchHandField", playerId=player, field="rank")


def hand_size(player):
    return LEN(S("playerHand", playerId=player))


def input_ranks():
    """Ranks of the cards the player has selected, inside a preHandler."""
    return S("fetchCardsField", cards=C("inputCards"), field="rank")


def effective_rank(ranks):
    """The rank a play counts as. Jesters are wild, so a play is worth its
    lowest card; appending the Jester rank also keeps minValue safe on the
    empty selection a pass produces, which matters because logicalOR evaluates
    every argument eagerly."""
    return S("minValue", list=S("append", list=ranks, element=JESTER_RANK))


def one_rank_only(ranks):
    """True when every non-Jester card in the selection shares a rank."""
    return S("lessThanOrEqual",
             arg1=LEN(WITHOUT(S("unique", list=ranks), JESTER_RANK)),
             arg2=1)


def second_best(ranks):
    """The rank of a player's SECOND-best card.

    listsSubtract drops every copy of the best rank, so the length tells us
    whether the player held one of them or several: if exactly one went, the
    next-best is the min of what is left; if several went, the second-best is
    the best rank again. Written this way the answer is right whether
    listsSubtract removes one occurrence or all of them.
    """
    best = S("minValue", list=ranks)
    rest = WITHOUT(ranks, best)
    return IF(EQ(LEN(rest), S("dec", arg=LEN(ranks))),
              S("minValue", list=S("append", list=rest, element=JESTER_RANK)),
              best)


def timed(player, seconds):
    """Full duration for a connected actor, 1s for a disconnected one."""
    return IF(S("contains", list=S("allConnectedUsers"), element=player), seconds, 1)


# The bottom seat, and whether the table is big enough to seat a Little Emperor
# and Little Serf. At three players it is just Emperor, Merchant, Serf.
LAST_SEAT = S("dec", arg=C("numPlayers"))
BIG_TABLE = S("greaterThanOrEqual", arg1=C("numPlayers"), arg2=4)


def rank_role_groups(name, skipCondition=None):
    """Show every player their rank at the table as a fake role.

    The role is derived from the player's index in `order`, so it is built once
    into a list parallel to `players` and then simply read per parallel slot —
    computing the index inside the showFakeRole would repeat the same lookup
    four times over in one action.
    """
    # Resolve the seat once into `seatIdx`, then branch on the cached value —
    # inlining the lookup would repeat it in all four ifElse arms.
    seat = C("seatIdx")
    role_for_seat = IF(
        EQ(seat, 0), "great_emperor",
        IF(EQ(seat, LAST_SEAT), "great_serf",
           IF(AND(BIG_TABLE, EQ(seat, 1)), "little_emperor",
              IF(AND(BIG_TABLE, EQ(seat, S("dec", arg=LAST_SEAT))), "little_serf",
                 "merchant"))))
    return [
        G(name + " (reset)", skipCondition=skipCondition, actions=[
            A("emptyAction", saveValueInCache=[save("rankRoles", [])]),
        ]),
        G(name + " (work out)", skipCondition=skipCondition,
          repeat={"qnt": getc("numPlayers")}, actions=[
            A("emptyAction", saveValueInCache=[
                save("seatIdx", S("indexOf", list=C("order"),
                                  element=AT(C("players"), C("repeatIndex")))),
                save("rankRoles", S("append", list=C("rankRoles"), element=role_for_seat)),
            ]),
        ]),
        G(name, skipCondition=skipCondition,
          parallel={"type": "smart", "qnt": getc("numPlayers")}, actions=[
            A("showFakeRole",
              to=C("players"),
              from_=S("createList", arg1=AT(C("players"), C("spaIndex"))),
              roleId=AT(C("rankRoles"), C("spaIndex"))),
        ]),
    ]


# ------------------------------------------------------------ tax exchange
def tax_group(payer_var, payee_var, qnt, deck, label, skipCondition=None):
    """The Serf hands their best cards up; the Emperor sends any back.

    Cards cannot move hand-to-hand directly, so both halves go through a deck —
    the same route Hearts uses for its pass.
    """
    ordinal = "two best cards" if qnt == 2 else "best card"
    pre = {
        "error": "You must hand over your %s — the %s in your hand."
                 % (ordinal, "two lowest numbers" if qnt == 2 else "lowest number"),
        "success": AND(
            EQ(LEN(C("inputCards")), qnt),
            EQ(S("minValue", list=S("append", list=input_ranks(), element=JESTER_RANK)),
               S("minValue", list=hand_ranks(C(payer_var)))),
            EQ(S("maxValue", list=S("append", list=input_ranks(), element=1)),
               second_best(hand_ranks(C(payer_var))) if qnt == 2
               else S("minValue", list=hand_ranks(C(payer_var)))),
        ),
    }
    return [
        G("Tax: %s pays" % label, skipCondition=skipCondition, actions=[
            A("playCards",
              target=deck, minCards=qnt, maxCards=qnt, playable="availableCards",
              label="You handed over the $(cards)",
              **{"sounds.list": ["soundboard.reminder"], "sounds.waitForSoundEnd": False,
                 "playList.0": S("createList", arg1=C(payer_var))},
              actor=C(payer_var),
              duration=timed(C(payer_var), 40),
              notification=fmt(
                  "Taxes! Hand your %s to ($1)." % ordinal, name_of(C(payee_var))),
              preHandler=pre,
              postHandler="playOneRandomCard"),
        ]),
        G("Tax: %s receives" % label, skipCondition=skipCondition, actions=[
            A("dealDeck", deck=deck, qnt=qnt, sortBy="weight", order="asc",
              targets=S("createList", arg1=C(payee_var))),
        ]),
        G("Tax: %s returns" % label, skipCondition=skipCondition, actions=[
            A("playCards",
              target=deck + "_back", minCards=qnt, maxCards=qnt,
              playable="availableCards",
              label="You sent back the $(cards)",
              **{"sounds.list": ["soundboard.reminder"], "sounds.waitForSoundEnd": False,
                 "playList.0": S("createList", arg1=C(payee_var))},
              actor=C(payee_var),
              duration=timed(C(payee_var), 40),
              notification=fmt("Send any %s back down to ($1).",
                               name_of(C(payer_var))) if qnt == 2 else
              fmt("Send any card back down to ($1).", name_of(C(payer_var))),
              postHandler="playOneRandomCard"),
        ]),
        G("Tax: %s collects" % label, skipCondition=skipCondition, actions=[
            A("dealDeck", deck=deck + "_back", qnt=qnt, sortBy="weight", order="asc",
              targets=S("createList", arg1=C(payer_var))),
        ]),
    ]


# ---------------------------------------------------------------- the game
def build_game():
    before = [
        A("changeBackground", image="wallpaper"),
        A("emptyAction", saveValueInCache=[
            save("players", S("allPlayers")),
            save("numPlayers", LEN(S("allPlayers"))),
            save("host", HOST_VALUE),
        ]),
        welcome(),
        emeralds_action("createMixVote"),
        # 'name' names the staging deck script; 'customName' is the handle every
        # other action refers to it by.
        A("createDeck", name=DECK_NAME, customName="emperor", set="full",
          label="draw", counter=True),
        A("shuffleDeck", deck="emperor"),
        # Where a play lands, the lead it becomes, and everything already beaten.
        # createCustomDeck, not createDeck: these are built from scratch.
        # createDeck IMPORTS a deck from the store and its `name` has to be that
        # deck's script name, which is why only `emperor` above uses it.
        A("createCustomDeck", name="play_area", public=False),
        A("createCustomDeck", name="lead", public=True, label="the lead", counter=True),
        A("createCustomDeck", name="pile", public=True, label="spent", counter=True),
    ]
    # The tax exchange stays private: at the table the Peon hands cards over
    # face to face, and the rest of the room does not get to see what moved.
    for deck in ("tax_high", "tax_high_back", "tax_low", "tax_low_back"):
        before.append(A("createCustomDeck", name=deck, public=False))
    before += [
        A("emptyAction", saveValueInCache=[
            # Seating for round one is random; after that it is the finishing order.
            save("order", S("shuffleList", list=C("players"))),
            save("finished", []),
            # Seeded unconditionally: the trick loop feeds `active` to contains(),
            # which errors on a var that has never been written.
            save("active", []),
            save("inTrick", []),
            save("rankRoles", []),
            save("playAgain", True),
            save("reset", False),
            save("currentMinScore", 0),
        ]),
        A("changeLayout", type="HIGHLIGHT", direction="VERTICAL", percent=35),
        # increaseHandHeight makes hand cards taller, so the strip below the
        # board needs 230 or the hand overlaps the table when it opens.
        A("setImagesRow", maxHeight=230, images=["transparent"]),
        A("showAllPlayersHands"),
        A("showScore", order="highest", from_=C("players"), to=C("players")),
    ]

    loop = []

    # ---- tutorial -------------------------------------------------------
    loop.append(G("Tutorial", skipCondition=[NOT(C("tutorial"))], actions=[
        A("createNotification",
          header="Emperor", image="banner", duration=11,
          to=C("learners"),
          text="Everyone is dealt a rank at the table, from the <b>Great "
               "Emperor</b> at the top to the <b>Great Serf</b> at the bottom. "
               "Your goal every round is simple: <b>get rid of your whole hand "
               "first</b>.<br/><br/>Low numbers are powerful. The single 1 is the "
               "Emperor; there are twelve 12s and they are Peasants."),
        A("createNotification",
          header="Playing cards", duration=13,
          to=C("learners"),
          text="The leader plays any number of cards <b>of the same rank</b> — "
               "one 7, or three 9s. Everyone after must play the <b>same number "
               "of cards</b> at a <b>lower rank</b>, or pass.<br/><br/>So three 9s "
               "can be beaten by three 4s, but never by two 4s.<br/><br/>Once "
               "everyone else passes, the trick is over and whoever played last "
               "leads the next one."),
        A("createNotification",
          header="Jesters and taxes", duration=13,
          to=C("learners"),
          text="The two <b>Jesters</b> are wild — play them alongside real cards "
               "to pad out a set. On their own they are the worst rank in the "
               "game.<br/><br/>Before each round the Serfs hand their <b>best</b> "
               "cards up to the Emperors, who send <b>any</b> cards back down. "
               "Unless someone holding both Jesters calls a <b>Revolution</b> — "
               "then nobody pays.<br/><br/>Go out first and you rule next round. "
               "Go out last and you serve."),
        A("emptyAction", saveValueInCache=[save("tutorial", False)]),
    ]))

    # ---- one-time table setup ------------------------------------------
    loop.append(G("Build the table", skipCondition=[S("greaterThan", arg1=C("gameLoopIndex"), arg2=0)],
                  actions=[
        A("createGenericCardWidget",
          cardback="cardback", backgroundImage=WOOD,
          decks=["lead", "pile"], dimensions=[1, 2]),
    ]))

    # ---- new round ------------------------------------------------------
    loop.append(G("New round", [
        A("recallCards", deck="emperor", targets=C("players")),
        # Sweep every deck back, tax decks included: a timed-out tax leaves cards
        # stranded there, and anything not swept is gone from the deck for good.
        A("moveCards", type="deck", to="emperor",
          from_=["lead", "pile", "play_area",
                 "tax_high", "tax_high_back", "tax_low", "tax_low_back"]),
        A("shuffleDeck", deck="emperor"),
        A("emptyAction", saveValueInCache=[
            save("finished", []),
            save("revolutionary", ""),
            save("revolutionCalled", False),
        ]),
    ]))

    # ---- deal -----------------------------------------------------------
    # Eighty cards rarely divide evenly. Everyone gets the floor; the remainder
    # goes to the BOTTOM of the table, so the extra cards land on the players
    # the taxes are about to punish rather than on the Emperor.
    extras = S("remainder", arg1=DECK_SIZE, arg2=C("numPlayers"))
    loop.append(G("Deal", [
        A("dealDeck", deck="emperor", sortBy="weight", order="asc",
          targets=C("players"),
          qnt=S("integerDivide", arg1=DECK_SIZE, arg2=C("numPlayers"))),
        A("dealDeck", deck="emperor", qnt=1, sortBy="weight", order="asc",
          skipCondition=[EQ(extras, 0)],
          targets=S("sublist", list=C("order"),
                    start=S("subtract", arg1=C("numPlayers"), arg2=extras),
                    end=C("numPlayers"))),
    ]))

    # ---- announce the pecking order -------------------------------------
    loop += rank_role_groups("Announce ranks")

    # ---- revolution ------------------------------------------------------
    jesters_of = lambda p: LEN(S("getHandCardsIdsByName", playerId=p, name="jester"))
    loop.append(G("Look for a Revolution",
                  repeat={"qnt": getc("numPlayers")},
                  actions=[
        A("emptyAction", saveValueInCache=[
            save("revolutionary",
                 IF(EQ(jesters_of(AT(C("order"), C("repeatIndex"))), 2),
                    AT(C("order"), C("repeatIndex")),
                    C("revolutionary"))),
        ]),
    ]))
    loop.append(G("Offer the Revolution",
                  skipCondition=[EQ(C("revolutionary"), "")],
                  actions=[
        A("removeWidget", id="GenericCardWidget"),
        A("createVote",
          title="REVOLUTION?", type="target_poll",
          question="You hold both Jesters. Call a Revolution and cancel this "
                   "round's taxes?",
          terminationCondition="get_all_votes", showResultInRealTime=True,
          showResultDuration=1, showResultDelay=0, oneClick=True,
          targets=["Call Revolution", "Keep quiet"],
          duration=timed(C("revolutionary"), 25),
          actors=S("createList", arg1=C("revolutionary")),
          saveValueInCache=[
              save("revolutionCalled",
                   S("isTargetGotMajority", voteResult=C("lastActionResult"),
                     target="Call Revolution")),
          ]),
        A("restoreWidget", id="GenericCardWidget"),
    ]))
    # A Revolution from the very bottom of the table turns it upside down.
    great_rev = AND(C("revolutionCalled"),
                    EQ(C("revolutionary"), AT(C("order"), LAST_SEAT)))
    loop.append(G("Greater Revolution", skipCondition=[NOT(great_rev)], actions=[
        A("createNotification",
          header="GREATER REVOLUTION!", image="banner", duration=8,
          to=C("players"),
          text=fmt("<b>($1)</b> was the Great Serf and held both Jesters. The "
                   "whole table turns over — the Serf is now the Great Emperor, "
                   "and the Emperor is the Serf.", names(S("createList", arg1=C("revolutionary"))))),
        A("emptyAction", saveValueInCache=[
            save("order", S("reverseList", list=C("order"))),
        ]),
    ]))
    loop.append(G("Revolution", actions=[
        A("createNotification",
          header="Revolution!", duration=7,
          to=C("players"),
          text=fmt("<b>($1)</b> revealed both Jesters. No taxes are paid this round.",
                   names(S("createList", arg1=C("revolutionary"))))),
    ], skipCondition=[OR(NOT(C("revolutionCalled")), great_rev)]))
    # Re-announce, because a Greater Revolution just changed everyone's rank.
    loop += rank_role_groups("Re-announce ranks", skipCondition=NOT(great_rev))

    # ---- taxation --------------------------------------------------------
    loop.append(G("Name the taxpayers",
                  skipCondition=[C("revolutionCalled")],
                  actions=[
        A("emptyAction", saveValueInCache=[
            save("greatEmperor", C("order.0")),
            save("greatSerf", AT(C("order"), LAST_SEAT)),
            save("littleEmperor", C("order.1")),
            save("littleSerf", AT(C("order"), S("dec", arg=LAST_SEAT))),
        ]),
    ]))
    loop += tax_group("greatSerf", "greatEmperor", 2, "tax_high", "Great Serf",
                      skipCondition=C("revolutionCalled"))
    # The lesser pair only exists from four players up.
    loop += tax_group("littleSerf", "littleEmperor", 1, "tax_low", "Little Serf",
                      skipCondition=OR(C("revolutionCalled"), NOT(BIG_TABLE)))

    # Seed the round's turn state HERE, not back in "New round" — a Greater
    # Revolution reverses `order` in between, and these all derive from it.
    # Seeding earlier would leave the old Great Emperor leading and send the
    # turn order round the table backwards.
    loop.append(G("Seat the table", [
        A("emptyAction", saveValueInCache=[
            save("active", getc("order")),
            save("inTrick", getc("order")),
            save("leadRank", NO_LEAD_RANK),
            save("leadCount", 0),
            save("current", C("order.0")),
            save("lastPlayer", C("order.0")),
            save("outHeir", C("order.0")),
        ]),
    ]))
    loop.append(G("Take your seats", [
        A("createNotification",
          header="Play!", duration=6,
          to=C("players"),
          text=fmt("<b>($1)</b> is the Great Emperor and leads. Shed your whole "
                   "hand first to rule the next round.",
                   names(S("createList", arg1=C("order.0"))))),
    ]))

    # ---- the trick loop --------------------------------------------------
    loop.append(build_trick_loop())

    # ---- round end -------------------------------------------------------
    loop.append(G("Round over", [
        A("emptyAction", saveValueInCache=[
            # Whoever is left holding cards finishes last.
            save("finished", S("concat", list1=C("finished"), element=C("active"))),
        ]),
        A("emptyAction", saveValueInCache=[
            save("order", getc("finished")),
        ]),
    ]))
    loop.append(G("Award points",
                  repeat={"qnt": getc("numPlayers")},
                  actions=[
        # Taking the crown pays DOUBLE the field; everyone below keeps the plain
        # ladder (2nd scores numPlayers-1, down to 1 for last). A linear ladder
        # made winning a round worth exactly one point more than coming second,
        # which is not worth playing for.
        A("updateScore", scores=S("createList", arg1=S(
            "createDict",
            keys=["list", "delta"],
            values=S("createList",
                     arg1=S("createList", arg1=AT(C("finished"), C("repeatIndex"))),
                     arg2=IF(EQ(C("repeatIndex"), 0),
                             S("multiply", arg1=C("numPlayers"), arg2=2),
                             S("subtract", arg1=C("numPlayers"),
                               arg2=C("repeatIndex"))))))),
    ]))
    loop.append(G("The new order", [
        A("createNotification",
          header="The new pecking order", duration=9,
          to=C("players"),
          text=fmt("<b>($1)</b> went out first and is the next Great Emperor. "
                   "<b>($2)</b> went out last and serves as Great Serf.",
                   names(S("createList", arg1=C("order.0"))),
                   names(S("createList", arg1=AT(C("order"), LAST_SEAT))))),
        A("emptyAction", saveValueInCache=[
            save("currentMinScore", S("getMinCurrentScore")),
        ]),
    ]))

    # ---- play again ------------------------------------------------------
    play_again = emeralds_action("createVote", needle="PLAY AGAIN?", where="gameLoop")
    loop.append(G("Another round?", [
        A("removeWidget", id="GenericCardWidget"),
        play_again,
        A("restoreWidget", id="GenericCardWidget"),
    ]))
    reset = _EMERALDS["gameLoop"][12]
    loop.append(G("Reset scores", _recolour(json.loads(json.dumps(reset["actions"]))),
                  skipCondition=[NOT(C("reset"))]))
    loop.append(G("End round", [A("emptyAction")], checkWinCondition=True))
    loop.append(G("Change players", [A("emptyAction")]))

    game = {
        "gameInitOptions": build_init(),
        "visualSettings": {
            # The palette lives HERE and nowhere else. These are the base for
            # every relevant action; an action may override any of them, but a
            # PARTIAL override — a dark backgroundColor with no matching
            # textColor — is how you end up with black text on deep purple.
            # Keeping all colour at this level makes that impossible.
            "backgroundColor": BG,
            "textColor": TEXT,
            "borderColor": BORDER,
            "increaseHandHeight": True,
            "isCardAnimationsOff": True,
            "reorderHandCards": True,
            "cardHandBackgroundImage": WOOD,
        },
        "beforeLoopActions": before,
        "gameLoop": loop,
        "postGameActions": _recolour(json.loads(json.dumps(_EMERALDS["postGameActions"]))),
        "playersWinCondition": {
            "winners": S("getPlayerNamesByIds", ids=S("getPlayersWithMaxScore")),
            "gameOverCondition": NOT(C("playAgain")),
        },
        "winnersInfo": {"userIds": S("getPlayersWithMaxScore")},
    }
    return game


def build_trick_loop():
    """The climbing loop: one player acts per pass around the table.

    Everything the loop needs is carried in four lists — `active` (still holding
    cards), `inTrick` (still contesting this trick), `finished` (gone out, in
    order) and `order` (the seating). They are all derived from `order` by
    subtraction, so they keep seat order, which is what makes `nextPlayer` on
    them mean the right thing.
    """
    ranks_played = S("fetchDeckField", deck="play_area", field="rank")
    # "Am I starting a fresh trick?" gates the card count, the prompt and the
    # preHandler, so it is resolved once per turn into a flag.
    leading = C("isLeading")

    turn = A(
        "playCards",
        target="play_area",
        playable="availableCards",
        label="You played the $(cards)",
        **{"sounds.list": ["soundboard.reminder"], "sounds.waitForSoundEnd": False,
           "playList.0": S("createList", arg1=C("current"))},
        actor=C("current"),
        duration=timed(C("current"), 45),
        # Leading means playing at least one card; facing a lead means matching
        # its size exactly, or passing with an empty selection.
        minCards=IF(leading, 1, 0),
        maxCards=IF(leading, hand_size(C("current")), C("leadCount")),
        notification=IF(
            leading,
            "You lead. Play any number of cards of a single rank.",
            fmt("Play ($1) cards below rank ($2), or pass.",
                C("leadCount"), C("leadRank"))),
        preHandler={
            "error": "Play the same number of cards as the lead, all of one rank "
                     "(Jesters are wild), and lower than the lead — or select "
                     "nothing to pass.",
            "success": OR(
                # A pass. Only legal once somebody has led.
                AND(EQ(LEN(C("inputCards")), 0),
                    S("greaterThan", arg1=C("leadCount"), arg2=0)),
                AND(
                    # A real play is at least one card. Without this an empty
                    # selection satisfies every other clause when leading (no
                    # count to match, no rank to beat) and reads as a legal
                    # lead of nothing.
                    S("greaterThan", arg1=LEN(C("inputCards")), arg2=0),
                    OR(leading, EQ(LEN(C("inputCards")), C("leadCount"))),
                    one_rank_only(input_ranks()),
                    S("lessThan", arg1=effective_rank(input_ranks()),
                      arg2=C("leadRank")),
                ),
            ),
        },
        saveValueInCache=[
            # Read the play off the deck it landed in — the same way super_dark
            # detects an empty play — rather than trusting lastActionResult.
            save("numPlayed", LEN(S("getDeckCards", deck="play_area"))),
            # Entries resolve in order, so everything below reads the count once.
            save("wasPass", EQ(C("numPlayed"), 0)),
            save("newLeadRank", S("minValue", list=S(
                "append", list=ranks_played, element=NO_LEAD_RANK))),
            save("newLeadCount", getc("numPlayed")),
            # Who acts next, resolved while `current` is still in both lists.
            save("nxt", S("nextPlayer", playersList=C("inTrick"), playerId=C("current"))),
            save("outHeir", S("nextPlayer", playersList=C("active"), playerId=C("current"))),
        ],
    )

    went_out = EQ(hand_size(C("current")), 0)
    trick_over = S("lessThanOrEqual", arg1=LEN(C("inTrick")), arg2=1)

    return [
        G("Turn prep", [
            A("emptyAction", saveValueInCache=[
                save("isLeading", EQ(C("leadCount"), 0)),
            ]),
        ]),
        G("Your turn", [turn]),
        G("A play stands", skipCondition=[C("wasPass")], actions=[
            A("moveCards", type="deck", from_="lead", to="pile"),
            A("moveCards", type="deck", from_="play_area", to="lead"),
            A("emptyAction", saveValueInCache=[
                save("leadRank", getc("newLeadRank")),
                save("leadCount", getc("newLeadCount")),
                save("lastPlayer", getc("current")),
            ]),
        ]),
        G("A pass", skipCondition=[NOT(C("wasPass"))], actions=[
            A("emptyAction", saveValueInCache=[
                save("inTrick", WITHOUT(C("inTrick"), C("current"))),
            ]),
        ]),
        G("Out of cards", skipCondition=[NOT(went_out)], actions=[
            A("createNotification",
              header="Out!", duration=5,
                  to=C("players"),
              text=fmt("<b>($1)</b> has played their last card.",
                       names(S("createList", arg1=C("current"))))),
            A("emptyAction", saveValueInCache=[
                save("finished", S("append", list=C("finished"), element=C("current"))),
                save("active", WITHOUT(C("active"), C("current"))),
                save("inTrick", WITHOUT(C("inTrick"), C("current"))),
            ]),
        ]),
        G("Trick over", skipCondition=[NOT(trick_over)], actions=[
            A("moveCards", type="deck", from_="lead", to="pile"),
            A("emptyAction", saveValueInCache=[
                save("leadRank", NO_LEAD_RANK),
                save("leadCount", 0),
                save("inTrick", getc("active")),
                # The winner leads again; if they just went out, the seat below
                # them inherits it.
                save("current", IF(S("contains", list=C("active"), element=C("lastPlayer")),
                                   C("lastPlayer"), C("outHeir"))),
            ]),
        ]),
        G("Next player", skipCondition=[trick_over], actions=[
            A("emptyAction", saveValueInCache=[save("current", getc("nxt"))]),
        ]),
        # The break goes LAST, and as an expression rather than a bare false —
        # the same shape Hearts uses. Testing at the top of the pass instead
        # would let one phantom turn run after the round is already decided,
        # because the remaining groups in that pass still execute.
        G("Round finished?", [
            A("emptyAction", saveValueInCache=[
                save("isActionLoop", S("greaterThan", arg1=LEN(C("active")), arg2=1)),
            ]),
        ]),
    ]


HOST_VALUE = IF(S("contains", list=C("players"), element=S("getHostPlayerId")),
                S("createList", arg1=S("getHostPlayerId")),
                S("createList", arg1=C("players.0")))


def build_init():
    rank_roles = [
        ("great_emperor", "Great Emperor"),
        ("little_emperor", "Little Emperor"),
        ("merchant", "Merchant"),
        ("little_serf", "Little Serf"),
        ("great_serf", "Great Serf"),
    ]
    roles = [{
        "roleInfo": {
            "id": "player", "name": "Player",
            "description": "Born to a rank, and out to improve it.",
            "avatar": AVATAR, "team": "all", "prefix": "a ",
        },
        "isDefaultRole": True, "isRequired": False,
    }]
    roles += [{"roleInfo": {"id": rid, "name": nm, "team": "all"},
               "isRequired": False} for rid, nm in rank_roles]
    return {
        "allowRecorder": True,
        "allowSpectatorBecomePlayer": False,
        "allowPlayerBecomeSpectator": False,
        "roleConfirmation": False,
        "useDefaultRoles": True,
        "minPlayers": MIN_PLAYERS,
        "maxPlayers": MAX_PLAYERS,
        "time": 40,
        "teams": {
            "all": {
                "id": "all", "name": "All",
                "description": "One table, twelve ranks and a very short ladder.",
                "color": "#2B1B4A",
                "roles": ["player"] + [r for r, _ in rank_roles],
            },
        },
        "roles": roles,
        "rolesPreset": {},
        "images": {
            "transparent": {"url": TRANSPARENT},
            "cardback": {"url": IMAGES["cardback"]["url"]},
            "wallpaper": {"url": IMAGES["wallpaper"]["url"]},
            "banner": {"url": IMAGES["banner"]["url"]},
            "winner": {"url": WINNER_GIF},
        },
        "animations": {},
        "soundboard": {
            "default": {
                "reminder": "https://res.cloudinary.com/liars-club/video/upload/"
                            "v1673934850/audio/other/swap.mp3",
            },
        },
    }


# --------------------------------------------------------------- rulebook
def build_describe():
    return {
        "name": "Emperor",
        "demo": False,
        "parallel": False,
        "url": "../setups/ludio-v1-engine-setup/dist_cards/app.output.js",
        "banner": IMAGES["banner"]["url"],
        "description": {
            "summary": "A card game of rank and revolution. Shed your hand first "
                       "to rule the table next round - finish last and pay taxes "
                       "to the people who beat you.",
            "description_title": "Emperor Overview",
            "# Players": "3-8",
            "players": "3-8",
            "Duration": "40 mins",
        },
        "rules": [
            {
                "name": "Basic Rules",
                "icon": "icon.png",
                "content": [
                    {"title": "Overview",
                     "text": "Everyone holds a rank at the table, from the Great "
                             "Emperor at the top down to the Great Serf at the "
                             "bottom. Each round you race to get rid of your whole "
                             "hand. Go out first and you are the Great Emperor "
                             "next round; go out last and you are the Great Serf, "
                             "who pays for the privilege."},
                    {"title": "The deck",
                     "text": "Eighty cards. There is one 1 (the Emperor), two 2s, "
                             "three 3s, and so on down to twelve 12s (the Peasants), "
                             "plus two Jesters. Low numbers are strong. Every card "
                             "tells you how many of it exist, so you always know "
                             "what you are up against."},
                    {"title": "Playing a trick",
                     "text": "The leader plays any number of cards of a single rank "
                             "- one 7, or three 9s. Each player after must play the "
                             "same NUMBER of cards at a LOWER rank, or pass. Three "
                             "9s can be beaten by three 4s, but never by two 4s. "
                             "Passing puts you out of that trick only. When everyone "
                             "else has passed, the trick ends and whoever played "
                             "last leads the next one."},
                    {"title": "Jesters",
                     "text": "The two Jesters are wild. Play them alongside real "
                             "cards to make up the numbers - two 5s and a Jester "
                             "count as three 5s. Played on their own they are rank "
                             "13, the worst in the game, which makes them a fine way "
                             "to dump a lead nobody wants."},
                    {"title": "Taxes",
                     "text": "Before each round the Great Serf hands their two "
                             "best cards to the Great Emperor, who sends any two "
                             "cards back. The Little Serf and Little Emperor do the "
                             "same with one card. You cannot hold back your best - "
                             "the tax takes exactly your lowest numbers."},
                    {"title": "Scoring",
                     "text": "Taking the crown is worth double the table: go out "
                             "first and you score twice the number of players. "
                             "Everyone below that scores on a plain ladder - one "
                             "less than the player count for second, down to a "
                             "single point for finishing last. So at six players "
                             "the round pays 12 for first and 5 for second. The "
                             "highest total when the table stops playing wins."},
                ],
            },
            {
                "name": "Advanced Rules",
                "icon": "icon.png",
                "content": [
                    {"title": "Revolution",
                     "text": "If you are dealt both Jesters you may call a "
                             "Revolution before taxes are paid, and nobody pays "
                             "anything that round. It is optional, and it is not "
                             "always in your interest - if you are already the "
                             "Great Emperor, the taxes were about to go your way."},
                    {"title": "Greater Revolution",
                     "text": "If the player holding both Jesters is the Greater "
                             "Serf, calling a Revolution turns the whole table "
                             "upside down: the seating order reverses, so the "
                             "Great Serf becomes the Great Emperor and the "
                             "Emperor drops to the bottom. No taxes are paid."},
                    {"title": "Uneven hands",
                     "text": "Eighty cards rarely divide evenly. The spare cards go "
                             "to the bottom of the table, so the players about to be "
                             "taxed get a little more to work with."},
                    {"title": "Three players",
                     "text": "At a table of three there is no Little Emperor or "
                             "Little Serf - just the Great Emperor, a Merchant and "
                             "the Great Serf, with the single two-card tax between "
                             "top and bottom."},
                ],
            },
        ],
        "tags": ["card game", "strategic", "player elimination"],
    }


def main():
    deck = build_deck()
    game = build_game()
    describe = build_describe()
    for fname, obj in (("emperor_cards.json", deck),
                       ("emperor.json", game),
                       ("emperor_describe.json", describe)):
        path = os.path.join(GJ, fname)
        with open(path, "w") as f:
            json.dump(obj, f, indent=1)
            f.write("\n")
        print("wrote %-32s %7d bytes" % (fname, os.path.getsize(path)))


if __name__ == "__main__":
    main()
