#!/usr/bin/env python3
"""Revise Squaffle in place (source of truth = game_jsons/squaffle.json, which
mirrors production; build_squaffle.py is stale and would revert the game).

TWO CHANGES
===========

1. THE DRAW PILE SPLITS IN TWO. `stock` becomes `stock_v` (the 44 vowels: A E I O U)
   and `stock_c` (the other 74: consonants + the CL/ER/IN/QU/TH combo tiles). The
   DRAW A CARD action card therefore splits into DRAW VOWEL (`act_draw_v`) and
   DRAW OTHER (`act_draw_c`), so every player now holds five action cards, not four.
   DRAW & PLAY draws from the OTHER pile.

   The three draws that are NOT an explicit action-card choice — the opening deal of
   5, the SWAP refill, and the refill back up to 5 after playing a word — are split
   PROPORTIONALLY to the deck (44/118 of the cards drawn are vowels, rounded), so a
   hand's vowel supply behaves as it does today and the split only adds agency where
   the player actually chooses.

   The discard stays a single pile. When a stock pile cannot cover the draw, only the
   cards belonging to THAT pile are pulled out of the discard and reshuffled back in,
   via moveCards `cardNames`. Note this fires on "cannot cover the draw" rather than
   the old "is completely empty": each pile is now less than half the size it was, so
   waiting for empty would short-deal players routinely.

2. BONUS SPACES MOVE OFF THE ENDS. The 2x and 3x word slots were drawn from all six
   columns; a 3x in column 6 is close to worthless because you may never reach it.
   They are now drawn from columns 2-5 only.

The deck gains sets and a card, so it is published as a NEW deck (`squaffle_cards_v2`)
rather than an edit of `squaffle_cards` — the deck store is shared between try/ptr and
production's one-pile game still reads the old deck.
"""
import json, os, shutil

CODE = "/Users/ankitbuddhiraju/Documents/claude/Code"
GAME = f"{CODE}/game_jsons/squaffle.json"
# The validator resolves a game's deck as the sibling `<game>_cards.json`, so the
# split deck has to land in squaffle_cards.json. Production's one-pile deck is
# preserved beside it (and is what build_deck reads, so re-running is idempotent).
DECK = f"{CODE}/game_jsons/squaffle_cards.json"
DECK_PROD = f"{CODE}/game_jsons/squaffle_cards_prod.json"
if not os.path.exists(DECK_PROD):
    shutil.copy(DECK, DECK_PROD)
DESCRIBE = f"{CODE}/game_jsons/squaffle_describe.json"
CLOUD = "https://res.cloudinary.com/liars-club/image/upload/images/squaffle"

DECK_NAME = "squaffle_cards_v2"
VOWELS = ["a", "e", "i", "o", "u"]
FULL = json.load(open(DECK_PROD))["sets"]["full"]
OTHERS = [k for k in FULL if k not in VOWELS]
N_VOWEL = sum(v for k, v in FULL.items() if k in VOWELS)   # 44
N_TOTAL = sum(FULL.values())                               # 118
OPEN_V, OPEN_C = 2, 3                # opening hand of 5, 44/118 rounded

# ── selector/payload helpers (same shapes the rest of the repo emits) ─────────
def pc(n, v): return {"name": n, "type": "cached", "value": v}
def pp(n, v): return {"name": n, "type": "preset", "value": v}
def pm(n, v): return {"name": n, "type": "computed", "value": v}
def S(sel, *ps): return {"selector": sel, "params": list(ps)}

def act(key, payload=None, skip=None, save=None):
    a = {"key": key}
    if skip: a["skipCondition"] = list(skip)
    if payload is not None: a["payload"] = payload
    if save is not None: a["saveValueInCache"] = save
    return a

def setc(*pairs, skip=None):
    return act("emptyAction", skip=skip,
               save=[{"name": n, "value": v} for n, v in pairs])

def deck_len(deck, cached=False):
    p = pc("deck", deck) if cached else pp("deck", deck)
    return S("listLength", pm("list", S("getDeckCards", p)))

def eq(a, b):  return S("equals", pc("arg1", a), pp("arg2", b))
def neq(a, b): return S("notEqual", pc("arg1", a), pp("arg2", b))
def NOT(name): return S("logicalNOT", pc("arg", name))

# ══════════════════════════════════════════════════════════════════════════════
# the deck: two new sets, DRAW A CARD replaced by DRAW VOWEL + DRAW OTHER
# ══════════════════════════════════════════════════════════════════════════════
def build_deck():
    deck = json.load(open(DECK_PROD))
    vowels = {k: v for k, v in FULL.items() if k in VOWELS}
    others = {k: v for k, v in FULL.items() if k not in VOWELS}
    assert sum(vowels.values()) == N_VOWEL and sum(others.values()) == N_TOTAL - N_VOWEL

    # act_draw retires; the two replacements take the leftmost hand slots (weight asc)
    # so a player's action cards read DRAW VOWEL, DRAW OTHER, PLAY, SWAP, DRAW & PLAY.
    cards = [c for c in deck["cards"] if c["name"] != "act_draw"]
    def action_card(name, label, weight):
        return {"name": name, "image": f"{CLOUD}/{name}.png", "label": label,
                "type": "action", "rank": 0, "size": 0, "weight": weight,
                "enlargeOnHover": True}
    at = next(i for i, c in enumerate(cards) if c.get("type") == "action")
    cards[at:at] = [action_card("act_draw_v", "Draw Vowel", -5),
                    action_card("act_draw_c", "Draw Other", -4)]

    deck["name"] = DECK_NAME
    deck["cards"] = cards
    deck["sets"] = {"full": FULL, "vowels": vowels, "others": others,
                    "done": deck["sets"]["done"],
                    "actions": {"act_draw_v": 1, "act_draw_c": 1, "act_play": 1,
                                "act_swap": 1, "act_drawplay": 1}}
    return deck

# ══════════════════════════════════════════════════════════════════════════════
# the refill primitive, shared by SWAP and the play-a-word top-up
# ══════════════════════════════════════════════════════════════════════════════
def refill(count_var, tag, gate=()):
    """Deal `count_var` cards to currentPlayer split proportionally across the two
    stock piles, reshuffling the matching half of the discard into a pile that is
    short. `gate` is an extra skip reason OR-ed into every emitted action (a
    skipCondition list skips the action when ANY of its entries is true)."""
    gate = list(gate)
    want_v, want_c = f"{tag}WantV", f"{tag}WantC"
    out = [setc(
        # round(n * 44/118) vowels, the rest off the other pile
        (want_v, S("round", pm("arg", S("divide",
            pm("arg1", S("multiply", pc("arg1", count_var), pp("arg2", N_VOWEL))),
            pp("arg2", N_TOTAL))))),
        (want_c, S("subtract", pc("arg1", count_var), pc("arg2", want_v))),
        skip=gate)]

    for pile, names, want in (("stock_v", VOWELS, want_v),
                              ("stock_c", OTHERS, want_c)):
        suf = pile[-1].upper()
        short, draw = f"{tag}Short{suf}", f"{tag}Draw{suf}"
        out += [
            setc((short, S("lessThan", pm("arg1", deck_len(pile)), pc("arg2", want))),
                 skip=gate),
            act("moveCards",
                payload={"preset": {"type": "deck", "from": "discard", "to": pile,
                                    "cardNames": names}},
                skip=[NOT(short)] + gate),
            act("shuffleDeck", payload={"preset": {"deck": pile}},
                skip=[NOT(short)] + gate),
            setc((draw, S("minValue", pm("list", S("createList",
                 pc("arg1", want), pm("arg2", deck_len(pile)))))), skip=gate),
            act("dealDeck",
                payload={"preset": {"deck": pile, "sortBy": "weight", "order": "asc"},
                         "cached": {"targets": "currentPlayer", "qnt": draw}},
                skip=[S("lessThanOrEqual", pc("arg1", draw), pp("arg2", 0))] + gate),
        ]
    return out

# ══════════════════════════════════════════════════════════════════════════════
def main():
    g = json.load(open(GAME))
    bl, gl, gi = g["beforeLoopActions"], g["gameLoop"], g["gameInitOptions"]

    def find(section, pred):
        hits = [i for i, a in enumerate(section) if pred(a)]
        assert len(hits) == 1, hits
        return hits[0]

    # ── images: the old single DRAW tile gives way to the two new ones ────────
    imgs, rebuilt = gi["images"], {}
    imgs.pop("act_draw_img")
    for k, v in imgs.items():
        if k == "act_swap_img":
            rebuilt["act_draw_v_img"] = {"url": f"{CLOUD}/act_draw_v.png"}
            rebuilt["act_draw_c_img"] = {"url": f"{CLOUD}/act_draw_c.png"}
        rebuilt[k] = v
    gi["images"] = rebuilt

    # ── strings ───────────────────────────────────────────────────────────────
    st = gi["strings"]["Default"]
    st["squaffleIsATurn"] = (
        "Squaffle is a turn-based word game. You hold all five action cards in your "
        "hand the whole game — on your turn, play one of them to take your turn: "
        "DRAW VOWEL, DRAW OTHER, SWAP up to 5 cards (discard some, draw the same "
        "number back), PLAY a word, or — ONCE per game — DRAW & PLAY (draw "
        "one card, then immediately play a word; that card is then spent for good). "
        "There are TWO face-down piles: one of vowels (A E I O U) and one of everything "
        "else (consonants and the two-letter combo tiles) — DRAW VOWEL and DRAW "
        "OTHER take the top card of the pile you name, and DRAW & PLAY takes from the "
        "OTHER pile. You can't take cards from the discard, though a pile that runs "
        "short is topped up from it. Your hand can hold at most 11 letter cards.")
    st["playAWordSpell"] = (
        "PLAY A WORD: spell a real word from your hand — I check every one! You "
        "score the value of its letters (and if that drops you below 5 cards, you "
        "refill back up to 5, split across both piles). Each word lands in your row, "
        "labelled with its score, so you can see how everyone is doing.")
    st["lookAtYourSix"] = (
        "Look at your six word slots: one is a 2x space and another is a 3x space "
        "— marked with a gold 2x tile and a red 3x tile. They always land in the "
        "middle four slots, never on the two ends, and everyone can see every player's "
        "bonus spaces. Your words fill your row left to right, so plan which word lands "
        "where: a word placed on your 2x space scores DOUBLE, and on your 3x space it "
        "scores TRIPLE!")
    st["drawVowelPile"] = "VOWELS"
    st["drawOtherPile"] = "OTHER"

    # ── beforeLoopActions ─────────────────────────────────────────────────────
    cache = bl[1]["saveValueInCache"]
    next(e for e in cache if e["name"] == "allActionCards")["value"] = [
        "act_draw_v", "act_draw_c", "act_swap", "act_play", "act_drawplay"]
    # sane defaults so the Draw group never reads an unset pile after a forced play
    cache.append({"name": "drawPile", "value": "stock_c"})
    cache.append({"name": "drawPileNames", "value": OTHERS})

    # createDeck full_pool  ->  two pools
    i = find(bl, lambda a: a["key"] == "createDeck")
    bl[i:i+1] = [
        act("createDeck", {"preset": {"name": DECK_NAME, "set": "vowels",
                                      "customName": "vowel_pool"}}),
        act("createDeck", {"preset": {"name": DECK_NAME, "set": "others",
                                      "customName": "other_pool"}}),
    ]
    gl[3]["actions"][0]["payload"]["preset"]["name"] = DECK_NAME   # per-player actions

    # createCustomDeck stock -> stock_v + stock_c (same flags, plus a label each)
    i = find(bl, lambda a: a["key"] == "createCustomDeck"
             and a["payload"]["preset"].get("name") == "stock")
    flags = {k: v for k, v in bl[i]["payload"]["preset"].items() if k != "name"}
    bl[i:i+1] = [
        act("createCustomDeck", {"preset": dict(name="stock_v", **flags)}),
        act("createCustomDeck", {"preset": dict(name="stock_c", **flags)}),
        act("setDeckLabel", {"preset": {"deck": "stock_v"},
                             "cached": {"label": "drawVowelPile"}}),
        act("setDeckLabel", {"preset": {"deck": "stock_c"},
                             "cached": {"label": "drawOtherPile"}}),
    ]
    # pool -> pile, then shuffle each
    i = find(bl, lambda a: a["key"] == "moveCards"
             and a["payload"]["preset"].get("to") == "stock")
    bl[i:i+1] = [
        act("moveCards", {"preset": {"type": "deck", "from": "vowel_pool",
                                     "to": "stock_v"}}),
        act("moveCards", {"preset": {"type": "deck", "from": "other_pool",
                                     "to": "stock_c"}}),
    ]
    i = find(bl, lambda a: a["key"] == "shuffleDeck"
             and a["payload"]["preset"].get("deck") == "stock")
    bl[i:i+1] = [act("shuffleDeck", {"preset": {"deck": "stock_v"}}),
                 act("shuffleDeck", {"preset": {"deck": "stock_c"}})]

    # opening hand: 5 cards as 2 vowels + 3 others
    i = find(bl, lambda a: a["key"] == "dealDeck"
             and a["payload"]["preset"].get("deck") == "stock")
    targets = dict(bl[i]["payload"]["cached"])
    bl[i:i+1] = [
        act("dealDeck", {"preset": {"deck": "stock_v", "qnt": OPEN_V,
                                    "sortBy": "weight", "order": "asc"},
                         "cached": targets}),
        act("dealDeck", {"preset": {"deck": "stock_c", "qnt": OPEN_C,
                                    "sortBy": "weight", "order": "asc"},
                         "cached": dict(targets)}),
    ]
    # the seeded face-up discard card comes off the other pile
    i = find(bl, lambda a: a["key"] == "moveCards"
             and a["payload"]["preset"].get("from") == "stock")
    bl[i]["payload"]["preset"]["from"] = "stock_c"

    # ── gameLoop[1]: bonus spaces confined to the middle four columns ─────────
    pick = gl[1]["actions"][0]["saveValueInCache"][0]["value"]
    assert pick["selector"] == "randomElementsList"
    assert pick["params"][0]["value"] == [0, 1, 2, 3, 4, 5]
    pick["params"][0]["value"] = [1, 2, 3, 4]

    # ── gameLoop[9] Choose action ────────────────────────────────────────────
    ch = gl[9]["actions"]
    my = next(e for e in ch[1]["saveValueInCache"] if e["name"] == "myActionCards")
    my["value"] = S("ifElse", pc("condition", "canDraw"),
                    pp("thenValue", ["act_draw_v", "act_draw_c", "act_swap", "act_play"]),
                    pp("elseValue", ["act_swap", "act_play"]))
    # spoken label for the "X chose to Y" banner
    ch[4]["saveValueInCache"][0]["value"] = S("ifElse",
        pm("condition", eq("choice", "act_draw_v")),
        pp("thenValue", "draw a vowel"),
        pm("elseValue", S("ifElse",
            pm("condition", eq("choice", "act_draw_c")),
            pp("thenValue", "draw a non-vowel"),
            pm("elseValue", S("ifElse",
                pm("condition", eq("choice", "act_swap")),
                pp("thenValue", "swap cards"),
                pm("elseValue", S("ifElse",
                    pm("condition", eq("choice", "act_play")),
                    pp("thenValue", "play a word"),
                    pp("elseValue", "draw a card and play a word"))))))))
    # resolve which pile this turn's draw comes from (DRAW & PLAY -> the other pile)
    ch.append(setc(
        ("drawPile", S("ifElse", pm("condition", eq("choice", "act_draw_v")),
                       pp("thenValue", "stock_v"), pp("elseValue", "stock_c"))),
        ("drawPileNames", S("ifElse", pm("condition", eq("choice", "act_draw_v")),
                            pp("thenValue", VOWELS), pp("elseValue", OTHERS)))))

    # ── gameLoop[10] Draw one: one card off whichever pile was chosen ─────────
    d1 = gl[10]
    d1["skipCondition"] = [S("logicalAND",
        pm("arg1", S("logicalAND", pm("arg1", neq("choice", "act_draw_v")),
                                   pm("arg2", neq("choice", "act_draw_c")))),
        pm("arg2", neq("choice", "act_drawplay")))]
    d1["actions"] = [
        setc(("stockEmpty", S("equals", pm("arg1", deck_len("drawPile", cached=True)),
                              pp("arg2", 0)))),
        act("moveCards",
            payload={"preset": {"type": "deck", "from": "discard"},
                     "cached": {"to": "drawPile", "cardNames": "drawPileNames"}},
            skip=[NOT("stockEmpty")]),
        act("shuffleDeck", payload={"cached": {"deck": "drawPile"}},
            skip=[NOT("stockEmpty")]),
        act("dealDeck",
            payload={"preset": {"sortBy": "weight", "order": "asc"},
                     "cached": {"deck": "drawPile", "targets": "currentPlayer",
                                "qnt": "one"}}),
    ]

    # ── gameLoop[11] Swap: draw the replacements proportionally ──────────────
    sw = gl[11]["actions"]
    assert sw[0]["key"] == "playCards"
    assert sw[1]["saveValueInCache"][0]["name"] == "swapCount"
    gl[11]["actions"] = sw[:2] + refill("swapCount", "swap")

    # ── gameLoop[12] Play a word: refill back up to 5, proportionally ────────
    pw = gl[12]["actions"]
    i = find(pw, lambda a: any(e["name"] == "drawN"
                               for e in a.get("saveValueInCache", [])))
    # the old block is [stockEmpty probe, moveCards, shuffleDeck, drawN, dealDeck]
    old = pw[i-3:i+2]
    assert [a["key"] for a in old] == ["emptyAction", "moveCards", "shuffleDeck",
                                       "emptyAction", "dealDeck"], [a["key"] for a in old]
    # `drawN` was min(deficit, stock); the pile clamp now lives inside refill(), so
    # keep only the deficit half.
    old_drawn = pw[i]["saveValueInCache"][0]["value"]          # minValue([deficit, stock])
    assert old_drawn["selector"] == "minValue"
    deficit = old_drawn["params"][0]["value"]["params"][0]["value"]
    assert deficit["selector"] == "maxValue", deficit["selector"]
    did_word = [NOT("didWord")]
    gl[12]["actions"] = (
        pw[:i-3]
        + [setc(("drawN", deficit), skip=did_word)]
        + refill("drawN", "word", gate=did_word)
        + pw[i+2:])

    # ── canonical key order, so the validator stays quiet ────────────────────
    ACTION_ORDER = ["key", "skipCondition", "payload", "postHandler", "saveValueInCache"]
    GROUP_ORDER = ["name", "turnPlayersToSpectators", "turnSpectatorsToPlayers",
                   "skipCondition", "repeat", "parallel", "checkWinCondition", "actions"]
    def norm(node):
        if isinstance(node, list):
            return [norm(x) for x in node]
        if isinstance(node, dict):
            node = {k: norm(v) for k, v in node.items()}
            if "key" in node: order = ACTION_ORDER
            elif "actions" in node or "repeat" in node or "parallel" in node:
                order = GROUP_ORDER
            elif node and set(node.keys()) <= {"preset", "cached", "computed"}:
                order = ["preset", "cached", "computed"]
            else: order = None
            if order is None: return node
            return {**{k: node[k] for k in order if k in node},
                    **{k: v for k, v in node.items() if k not in order}}
        return node
    for sect in ["beforeLoopActions", "gameLoop", "postGameActions",
                 "turnPlayerToSpectatorActions"]:
        g[sect] = norm(g[sect])

    json.dump(build_deck(), open(DECK, "w"), indent=1)
    open(GAME, "w").write(json.dumps(g, indent=1))
    print("wrote", DECK)
    print("wrote", GAME)
    update_rules()

# ══════════════════════════════════════════════════════════════════════════════
def update_rules():
    """Rules text shown in the lobby (the setup's `rules`, mirrored in the describe
    json). Both changes are player-visible, so both belong here."""
    d = json.load(open(DESCRIBE))
    # addressed by index, not title: this file's section titles have drifted from
    # production's (and are the better copy — production's rules text still describes
    # the pre-action-card-in-hand game).
    by = {s["name"]: s["content"] for s in d["rules"]}
    by["Basic Rules"][1]["text"] = (
        "On your turn you play ONE of the five action cards in your hand: DRAW VOWEL "
        "(take the top card of the vowel pile), DRAW OTHER (take the top card of the "
        "consonant-and-combo pile), SWAP up to 5 cards (discard some and draw the same "
        "number back), PLAY a word, or - once per game - DRAW & PLAY (draw from the "
        "OTHER pile, then immediately play a word). Everyone holds the same five action "
        "cards all game, so you can always see your options; the card you play comes "
        "back to your hand at the end of your turn, except DRAW & PLAY, which is spent "
        "for good. Your hand can hold at most 11 letter cards, so you cannot draw once "
        "it is full.")
    by["Basic Rules"][2]["text"] = (
        "Spell a real word from your hand and I check it against the dictionary, so no "
        "gibberish! You score the value of the letters you used. If playing the word "
        "drops your hand below 5 cards, you refill back up to 5, split across the two "
        "piles in the same proportion as the deck (otherwise you draw nothing). Each "
        "word lands in your row of the board, labelled with its score.")
    by["Advanced Rules"][0]["text"] = (
        "Every player's row of six word slots has one 2x space and one 3x space, marked "
        "\"2x\" and \"3x\". Both always fall in the middle four slots, never on the first "
        "or last, so every bonus is reachable; within those four they are randomly "
        "placed for each player, and everyone can see every player's bonus spaces. Your "
        "words fill your row left to right, so plan ahead: a word placed on your 2x "
        "space scores double, and a word on your 3x space scores triple.")
    by["Mechanics"][0]["text"] = (
        "You start with 5 cards - 2 vowels and 3 others - and your hand generally grows "
        "as you take DRAW turns. There are two draw piles: vowels (A E I O U) and "
        "everything else (consonants plus the CL, ER, IN, QU and TH combo tiles). If a "
        "pile cannot cover a draw, that pile's cards are pulled out of the discard and "
        "reshuffled back into it, so you can always keep drawing.")
    by["Mechanics"][1]["text"] = (
        "Each step is timed. If you run out of time it defaults sensibly - playing one "
        "of the action cards still available to you, or simply ending your turn - so "
        "the game keeps moving.")
    json.dump(d, open(DESCRIBE, "w"), indent=1)
    print("wrote", DESCRIBE)

if __name__ == "__main__":
    main()
