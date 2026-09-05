#!/usr/bin/env python3
"""Revise game_jsons/squaffle.json in place (source of truth = the live game JSON,
NOT build_squaffle.py, which is stale relative to production).

Two changes:

1. BONUS SPACES GET ART. Each player's row has one 2x and one 3x word slot; the
   only cue was the deck label, and in column 0 the label is prefixed with the
   player's name — a long name pushes "2x"/"3x" out of view. Empty decks can
   render an `emptyImage` in the central widget, so every word slot now gets one:
   the 2x/3x tile art on bonus slots, a transparent pixel everywhere else.

   `emptyImage` is only settable at createCustomDeck time, so the word decks move
   out of beforeLoopActions into a first-pass game-loop group that runs AFTER the
   multipliers are drawn. Multipliers are now drawn per ROW (6 rows, always) and
   are no longer spliced when a player leaves, so a row's art can never drift out
   of sync with its label.

2. EVERY PLAYER HOLDS EVERY ACTION CARD. Action cards used to be dealt to the
   current player from a shared pool and recalled at end of turn, which made the
   game hard to explain (you cannot see your options until it is your turn). Now
   each player is dealt their own copy of the `actions` set at setup, plays one
   into their videobox on their turn, and gets it dealt straight back afterwards —
   except Draw & Play, which is trashed for good (it is once-per-game).

   Consequences handled here: word/swap plays exclude action cards, and every
   "how many cards in hand" check counts LETTER cards only (type != "action").
"""
import json, os, sys

GAME = "/Users/ankitbuddhiraju/Documents/claude/Code/game_jsons/squaffle.json"
DESCRIBE = "/Users/ankitbuddhiraju/Documents/claude/Code/game_jsons/squaffle_describe.json"
CLOUD = "https://res.cloudinary.com/liars-club/image/upload"
BONUS2X = f"{CLOUD}/images/squaffle/bonus2x.png"
BONUS3X = f"{CLOUD}/images/squaffle/bonus3x.png"
BLANK = f"{CLOUD}/transparent_sbx4wv.png"

HAND_LIMIT = 11   # letter cards
ROWS = 6          # maxPlayers, i.e. rows in the word grid

# ── payload/selector helpers (same shapes build_squaffle.py emits) ────────────
def pc(n, v): return {"name": n, "type": "cached", "value": v}
def pp(n, v): return {"name": n, "type": "preset", "value": v}
def pm(n, v): return {"name": n, "type": "computed", "value": v}
def S(sel, *ps): return {"selector": sel, "params": list(ps)}
def act(key, payload=None, skip=None):
    a = {"key": key}
    if payload is not None: a["payload"] = payload
    if skip is not None: a["skipCondition"] = skip
    return a

def fmt(template, *args):
    ps = [pp("format", template)]
    for i, a in enumerate(args, 1):
        ps.append(a if isinstance(a, dict) else pc(f"arg{i}", a))
    return S("formatString", *ps)

def ri(name):   # formatString over repeatIndex
    return S("formatString", pp("format", name), pc("arg1", "repeatIndex"))

def videobox(player_cached="currentPlayer"):
    return S("formatString", pp("format", "videobox_($1)"), pc("arg1", player_cached))

def letters_in_hand(player_cached="currentPlayer"):
    """How many LETTER cards a player holds — action cards live in the hand now."""
    return S("listLength", pm("list", S("listsSubtract",
        pm("list1", S("fetchHandField", pc("playerId", player_cached), pp("field", "type"))),
        pp("list2", ["action"]))))

SKIP_SETUP = [S("greaterThan", pc("arg1", "gameLoopIndex"), pp("arg2", 0))]

g = json.load(open(GAME))
loop = g["gameLoop"]
before = g["beforeLoopActions"]

def group(name):
    for i, grp in enumerate(loop):
        if grp.get("name") == name: return i, grp
    raise KeyError(name)

# ─────────────────────────────────────────────────────────────────────────────
# 1a. Multipliers are drawn per ROW, for all 6 rows, once.
# ─────────────────────────────────────────────────────────────────────────────
_, mult = group("Assign multipliers")
mult["repeat"] = {"qnt": ROWS}

# ... and are never re-indexed when someone leaves, so row art stays truthful.
for a in g["turnPlayerToSpectatorActions"]:
    svc = a.get("saveValueInCache")
    if svc:
        a["saveValueInCache"] = [s for s in svc if s["name"] not in ("mult2List", "mult3List")]

# ─────────────────────────────────────────────────────────────────────────────
# 1b. Word decks move to a game-loop group so emptyImage can encode the bonus.
# ─────────────────────────────────────────────────────────────────────────────
before[:] = [a for a in before
             if not (a.get("key") == "createCustomDeck"
                     and str(a["payload"]["preset"].get("name", "")).startswith("word_"))]

def word_deck(col):
    def is_mult(which):
        return S("equals",
                 pm("arg1", S("selectElement", pc("list", which), pc("index", "repeatIndex"))),
                 pp("arg2", col))
    empty_image = S("ifElse",
        pm("condition", is_mult("mult2List")),
        pp("thenValue", BONUS2X),
        pm("elseValue", S("ifElse",
            pm("condition", is_mult("mult3List")),
            pp("thenValue", BONUS3X),
            pp("elseValue", BLANK))))
    return act("createCustomDeck", {
        "preset": {"public": True, "enlargeOnHover": True},
        "computed": {"name": ri(f"word_($1)_{col}"), "emptyImage": empty_image}})

word_decks_group = {
    "name": "Create word decks",
    "skipCondition": SKIP_SETUP,
    "repeat": {"qnt": ROWS},
    "actions": [word_deck(c) for c in range(6)],
}

# ─────────────────────────────────────────────────────────────────────────────
# 2a. Each player gets their own copy of the action set, dealt at setup.
# ─────────────────────────────────────────────────────────────────────────────
before[:] = [a for a in before
             if not (a.get("key") == "createDeck"
                     and a["payload"]["preset"].get("customName") == "act_pool")
             and not (a.get("key") == "createCustomDeck"
                      and a["payload"]["preset"].get("name") == "act_deal")]

deal_actions_group = {
    "name": "Deal action cards",
    "skipCondition": SKIP_SETUP,
    "repeat": {"qnt": S("getCachedValue", pp("name", "numPlayers"))},
    "actions": [
        act("createDeck", {"preset": {"name": "squaffle_cards", "set": "actions"},
                           "computed": {"customName": ri("act_p_($1)")}}),
        act("dealDeck", {"preset": {"sortBy": "weight", "order": "asc"},
                         "computed": {"deck": ri("act_p_($1)"),
                                      "targets": S("selectElement", pc("list", "players"),
                                                   pc("index", "repeatIndex"))}}),
    ],
}

i_mult, _ = group("Assign multipliers")
loop[i_mult + 1:i_mult + 1] = [word_decks_group, deal_actions_group]

# ─────────────────────────────────────────────────────────────────────────────
# 2b. Turn: play an action card straight out of your own hand.
# ─────────────────────────────────────────────────────────────────────────────
_, choose = group("Choose action")
choose["actions"] = [a for a in choose["actions"]
                     if a["key"] not in ("moveCards", "dealDeck", "recallCards")]

for svc in choose["actions"][0]["saveValueInCache"]:
    if svc["name"] == "canDraw":                 # hand limit counts letters only
        svc["value"] = S("lessThan", pm("arg1", letters_in_hand()), pp("arg2", HAND_LIMIT))
counts = choose["actions"][2]["saveValueInCache"]
choose["actions"][2]["saveValueInCache"] = [s for s in counts if s["name"] != "myActionCount"]

# Letter plays must not be able to consume the action cards sitting in the hand.
for gname in ("Swap cards", "Play a word"):
    _, grp = group(gname)
    for a in grp["actions"]:
        if a["key"] == "playCards":
            a["payload"].setdefault("cached", {})["playableExclude.cards"] = "allActionCards"

# Refilling to 5 after a word is about letters, not the action cards in hand.
_, playword = group("Play a word")
for a in playword["actions"]:
    for svc in a.get("saveValueInCache", []) or []:
        if svc["name"] == "drawN":
            svc["value"] = S("minValue", pm("list", S("createList",
                pm("arg1", S("maxValue", pm("list", S("createList",
                    pp("arg1", 0),
                    pm("arg2", S("subtract", pp("arg1", 5), pm("arg2", letters_in_hand()))))))),
                pm("arg2", S("listLength", pm("list", S("getDeckCards", pp("deck", "stock"))))))))

# ─────────────────────────────────────────────────────────────────────────────
# 2c. End of turn: the played card goes back to its owner (Draw & Play is spent).
# ─────────────────────────────────────────────────────────────────────────────
_, turn_end = group("Turn end")
assert turn_end["actions"][0]["key"] == "moveCards", "expected the videobox recall first"
is_drawplay = S("equals", pc("arg1", "choice"), pp("arg2", "act_drawplay"))
turn_end["actions"][0:1] = [
    act("moveCards",
        {"preset": {"type": "deck", "to": "trash"},
         "cached": {"cardNames": "allActionCards"},
         "computed": {"from": videobox()}},
        skip=[S("notEqual", pc("arg1", "choice"), pp("arg2", "act_drawplay"))]),
    act("dealDeck",
        {"cached": {"targets": "currentPlayer"},
         "computed": {"deck": videobox()}},
        skip=[is_drawplay,
              S("equals", pm("arg1", S("listLength", pm("list", S("getDeckCards", pm("deck", videobox()))))),
                pp("arg2", 0))]),
]

# ─────────────────────────────────────────────────────────────────────────────
# A leaving player's action cards are trashed, not dumped into the discard pile
# (they would come back around as if they were letters).
# ─────────────────────────────────────────────────────────────────────────────
spec = g["turnPlayerToSpectatorActions"]
assert spec[0]["key"] == "recallCards"
spec.insert(0, act("recallCards", {"preset": {"deck": "trash", "type": "action"},
                                   "cached": {"targets": "oldPlayer"}}))

# ─────────────────────────────────────────────────────────────────────────────
# Text: the tutorial and the rules describe the old deal-them-each-turn flow.
# ─────────────────────────────────────────────────────────────────────────────
strings = g["gameInitOptions"]["strings"]["Default"]
strings["squaffleIsATurn"] = (
    "Squaffle is a turn-based word game. You hold all four action cards in your hand "
    "the whole game — on your turn, play one of them to take your turn: DRAW a card, "
    "SWAP up to 5 cards (discard some, draw the same number back), PLAY a word, or — "
    "ONCE per game — DRAW & PLAY (draw a card, then immediately play a word; that card "
    "is then spent for good). Every draw comes off the top of the draw pile — you can't "
    "take cards from the discard, though the discard is reshuffled back in if the draw "
    "pile runs out. Your hand can hold at most 11 letter cards.")
strings["lookAtYourSix"] = (
    "Look at your six word slots: one is a 2x space and another is a 3x space — marked "
    "with a gold 2x tile and a red 3x tile. They're placed randomly for each row, and "
    "everyone can see every player's bonus spaces. Your words fill your row left to "
    "right, so plan which word lands where: a word placed on your 2x space scores "
    "DOUBLE, and on your 3x space it scores TRIPLE!")

TURN_RULE = ("On your turn you play ONE of the four action cards in your hand: DRAW one card "
             "from the face-down draw pile, SWAP up to 5 cards (discard some and draw the same "
             "number back), PLAY a word, or - once per game - DRAW & PLAY (draw a card, then "
             "immediately play a word). Everyone holds the same four action cards all game, so "
             "you can always see your options; the card you play comes back to your hand at the "
             "end of your turn, except DRAW & PLAY, which is spent for good. Your hand can hold "
             "at most 11 letter cards, so you cannot draw once it is full.")

def patch_rules(rules):
    for section in rules:
        for item in section.get("content", []):
            if item.get("title") == "Your turn":
                item["text"] = TURN_RULE
    return rules

desc = json.load(open(DESCRIBE))
patch_rules(desc["rules"])
json.dump(desc, open(DESCRIBE, "w"), indent=1)

# ── canonical key order (same as build_squaffle.py, keeps the validator quiet) ─
ACTION_ORDER = ["key", "skipCondition", "payload", "postHandler", "saveValueInCache"]
GROUP_ORDER = ["name", "turnPlayersToSpectators", "turnSpectatorsToPlayers",
               "skipCondition", "repeat", "parallel", "checkWinCondition", "actions"]
def norm(node):
    if isinstance(node, list):
        return [norm(x) for x in node]
    if isinstance(node, dict):
        node = {k: norm(v) for k, v in node.items()}
        if "key" in node: order = ACTION_ORDER
        elif "actions" in node or "repeat" in node or "parallel" in node: order = GROUP_ORDER
        elif node and set(node.keys()) <= {"preset", "cached", "computed"}: order = ["preset", "cached", "computed"]
        else: order = None
        if order is None: return node
        return {**{k: node[k] for k in order if k in node},
                **{k: v for k, v in node.items() if k not in order}}
    return node
for sect in ["beforeLoopActions", "gameLoop", "postGameActions", "turnPlayerToSpectatorActions"]:
    g[sect] = norm(g[sect])

json.dump(g, open(GAME, "w"), indent=1)
print("wrote", GAME, "| gameLoop groups:", len(loop), "| beforeLoopActions:", len(before))
