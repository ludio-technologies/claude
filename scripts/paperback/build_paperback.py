#!/usr/bin/env python3
"""Build paperback.json — a word-building deck game (simplified Paperback).

Design (agreed with product):
  * 2-6 players, simultaneous rounds. Host picks Short (4) / Full (8) rounds (Stoneball).
  * Personal deck per player: draw_<id> + disc_<id>. Start = L S N T R A E O (all value 1).
  * Each round: draw 6, spell ONE valid word with letter cards (engine checkIfValid).
    Word score = sum of played tiles' `rank`; that score is ADDED to your total AND is
    your spending money.
  * SINGLE accumulating score. Buying SPENDS points (strategic). Buy from a 6-pile market
    (one pile per offer, top card visible). Pass-based double-loop: outer [] over buy passes,
    inner repeat over the still-active buyers; each active buyer clicks a market pile to buy
    its top card, or clicks the DONE pile to stop. Capped at 7 buys (7 passes).
  * Central widget: row 0 = market (6 piles + DONE), rows 1..N = each player's spelled word,
    one tile per column. 7 columns; the 8th+ tile stacks into the last column under a
    createCard "overflow" tile. Everything square (ratio 1).
  * No player<->spectator transitions (deck/hand management).
  * Most points after the last round wins; Emeralds play-again + postgame.
"""
import json, copy, os, re

OUT = "/Users/ankitbuddhiraju/Documents/claude/Code/game_jsons/paperback.json"
IMG = "https://res.cloudinary.com/liars-club/image/upload/images/grapheme/"
BG, TXT, BDR = "#f2e4c9", "#3c2a1a", "#6b4a2b"
WOOD = "https://res.cloudinary.com/liars-club/image/upload/wood_qbegm0.jpg"
TOPUP = 6                # each turn, top the hand up to 6 kept letters, then add 1 free A = 7
MAX_BUYS = 7
COLS = 7                 # columns per row in the widget
WORD_COLS = COLS - 1     # first 6 columns show the spelled word; the last (col 6) is the draw deck
MARKET = ["market_vowels", "market_common", "market_uncommon",
          "market_rare", "market_digraph", "market_big"]
MARKET_LABEL = {"market_vowels": "Vowels", "market_common": "Common",
                "market_uncommon": "Uncommon", "market_rare": "Rare",
                "market_digraph": "Digraphs", "market_big": "Big"}

# ── DSL helpers ───────────────────────────────────────────────────────────────
def pc(n, v): return {"name": n, "type": "cached", "value": v}
def pp(n, v): return {"name": n, "type": "preset", "value": v}
def pm(n, v): return {"name": n, "type": "computed", "value": v}
def S(sel, *ps): return {"selector": sel, "params": list(ps)}
def _p(x, argname):  # str -> cached ref (cleaner); selector dict -> computed
    return pc(argname, x) if isinstance(x, str) else pm(argname, x)
def svc(n, v): return {"name": n, "value": v}
def act(key, payload=None, save=None, ph=None, skip=None):
    a = {"key": key}
    if skip is not None: a["skipCondition"] = skip
    if payload is not None: a["payload"] = payload
    if ph is not None: a["postHandler"] = ph
    if save is not None: a["saveValueInCache"] = save
    return a
def grp(name, actions, repeat=None, parallel=None, skip=None, checkwin=None):
    g = {"name": name}
    if parallel is not None: g["parallel"] = parallel
    if repeat is not None: g["repeat"] = repeat
    if skip is not None: g["skipCondition"] = skip
    g["actions"] = actions
    if checkwin: g["checkWinCondition"] = True
    return g

def fmt(template, *args):
    ps = [pp("format", template)]
    for i, a in enumerate(args, 1):
        ps.append({"name": f"arg{i}", **({"type": a[0], "value": a[1]})})
    return S("formatString", *ps)
def C(v): return ("cached", v)
def P(v): return ("preset", v)
def M(v): return ("computed", v)

def getcache(name): return S("getCachedValue", pp("name", name))
def deckcards(name_cached): return S("getDeckCards", pc("deck", name_cached))
def decklen(name_cached): return S("listLength", pm("list", deckcards(name_cached)))
def numPlayers(): return getcache("numPlayers")
def player_at(idx_cached):  # players[idx]
    return S("selectElement", pc("list", "players"), pc("index", idx_cached))
def score_delta(ids_expr, delta_expr):
    return act("updateScore", {"computed": {"scores": S("createList", pm("arg1",
        S("createDict", pp("keys", ["list", "delta"]),
          pm("values", S("createList", _p(ids_expr, "arg1"), _p(delta_expr, "arg2"))))))}})
def score_set(ids_expr, val):
    return act("updateScore", {"computed": {"scores": S("createList", pm("arg1",
        S("createDict", pp("keys", ["list", "score"]),
          pm("values", S("createList", _p(ids_expr, "arg1"), pp("arg2", val))))))}})
def one(idexpr): return S("createList", _p(idexpr, "arg1"))
def name_expr(prefix, idvar="playerId"):
    return S("formatString", pp("format", prefix + "_($1)"), pc("arg1", idvar))

# per-iteration name setup (used inside repeat-over-players groups)
def set_player_names():
    word_list = S("createList", *[pm(f"arg{i+1}",
        S("formatString", pp("format", f"word_($1)_{i}"), pc("arg1", "playerId")))
        for i in range(WORD_COLS)])
    return act("emptyAction", save=[
        svc("playerId", player_at("repeatIndex")),
        svc("drawName", name_expr("draw")),
        svc("discName", name_expr("disc")),
        svc("spellName", name_expr("spell")),
        svc("keepName", name_expr("keep")),
        svc("ovName", name_expr("ov")),
        svc("wordNames", word_list),
    ])

# ══════════════════════════════════════════════════════════════════════════════
# gameInitOptions
# ══════════════════════════════════════════════════════════════════════════════
gio = {
    "minPlayers": 2, "maxPlayers": 6, "timePerRound": 6,
    "notChangeLayoutAfterGame": True,   # keep the board layout after the game ends (like Knockout)
    "allowRecorder": True,
    "allowSpectatorBecomePlayer": False, "allowPlayerBecomeSpectator": False,
    "roleConfirmation": False, "useDefaultRoles": True,
    "teams": {"all": {"id": "all", "name": "All", "color": "#6b4a2b", "roles": ["player"]}},
    "cheatsheet": {"label": "Cheatsheet", "image": IMG + "cheatsheet.png"},
    "roles": [{"roleInfo": {"id": "player", "name": "Author",
        "description": "Spell words, build your deck, out-write the table!",
        "avatar": "https://res.cloudinary.com/liars-club/image/upload/card_player_ed7jck.webp",
        "team": "all", "prefix": "an "}, "isDefaultRole": True, "isRequired": False}],
    "images": {
        "wallpaper": {"url": IMG + "wallpaper.png"},
        "banner": {"url": IMG + "banner.png"},
        "done": {"url": IMG + "done.png"},
        "overflow_bg": {"url": IMG + "overflow_bg.png"},
        "cardback": {"url": IMG + "overflow_bg.png"},
        "transparent": {"url": "https://res.cloudinary.com/liars-club/image/upload/transparent_sbx4wv.png"},
        "winner": {"url": "https://res.cloudinary.com/liars-club/image/upload/winner_h5eyfr.gif"},
        # a few sample tiles shown in the tutorial for flavor
        "tile_a": {"url": IMG + "a.png"}, "tile_e": {"url": IMG + "e.png"},
        "tile_st": {"url": IMG + "st.png"}, "tile_th": {"url": IMG + "th.png"},
        "tile_ing": {"url": IMG + "ing.png"}, "tile_q": {"url": IMG + "q.png"},
    },
    "animations": {"winner": "https://lottie.host/ae7f6864-0454-4f5b-9d5d-598a8234f4b4/P4YrwOR8gd.json",
                   "genius": "https://lottie.host/95889080-c5b7-422d-b11e-f1442f8870d1/WYEWcOsyPf.json"},
    "soundboard": {"default": {
        "reminder": "https://res.cloudinary.com/liars-club/video/upload/audio/reminder.mp4",
        "clap": "https://res.cloudinary.com/liars-club/video/upload/audio/polite_clap.mp3"}},
}

visualSettings = {"backgroundColor": BG, "textColor": TXT, "borderColor": BDR,
                  "cardHandBackgroundImage": WOOD,
                  "isCardAnimationsOff": True,   # no per-moveCards animation (esp. during buying)
                  "reorderHandCards": True}      # let players rearrange tiles in their hand

# ══════════════════════════════════════════════════════════════════════════════
# beforeLoopActions
# ══════════════════════════════════════════════════════════════════════════════
host_action = act("emptyAction", save=[svc("host", S("ifElse",
    pm("condition", S("contains", pc("list", "players"), pm("element", S("getHostPlayerId")))),
    pm("thenValue", S("createList", pm("arg1", S("getHostPlayerId")))),
    pm("elseValue", S("createList", pc("arg1", "players.0")))))])

welcome = act("createNotification", {
    "preset": {"header": "Welcome to Grapheme!", "image": "banner", "duration": 8,
               "backgroundColor": BG, "borderColor": BDR, "textColor": TXT},
    "cached": {"to": "players"},
    "computed": {"text": fmt(
        "<b>($1)</b> - in a moment, tell me whether you want Ludio to teach your group how to play Grapheme!",
        M(S("listToString", pm("list", S("getPlayerNamesByIds", pc("ids", "host"))))))}})

tutorial_vote = act("createMixVote", {
    "preset": {"title": "Tutorial mode", "terminationCondition": "get_all_votes",
        "showResultInRealTime": True, "showResultDuration": 2, "showResultDelay": 0,
        "point.allowFewerAnswers": True, "point.terminationCondition": "get_all_votes",
        "poll.answersQuantity": 1, "poll.targets": ["Everybody!", "Nobody!"],
        "oneClick": True, "allowRevoting": True,
        "pollVoteTargetsOptions": {
            "Everybody!": {"icon": "https://res.cloudinary.com/liars-club/image/upload/icons/like.svg",
                "backgroundColor": "#D3D3D3", "boxIconColor": "#D3D3D3", "textColor": "black", "widgetIconColor": "green"},
            "Nobody!": {"icon": "https://res.cloudinary.com/liars-club/image/upload/icons/dislike.svg",
                "backgroundColor": "#D3D3D3", "boxIconColor": "#D3D3D3", "textColor": "black", "widgetIconColor": "red"}},
        "poll.terminationCondition": "get_all_votes",
        "backgroundColor": BG, "borderColor": BDR, "textColor": TXT},
    "cached": {"actors": "host", "point.targets": "players", "point.answersQuantity": "numPlayers"},
    "computed": {"question": fmt("($1), who needs the tutorial? Click on the players or select from the middle.",
        M(S("getPlayerNameById", pc("id", "host.0"))))}},
    save=[
        svc("voteResult", getcache("lastActionResult.voteResult")),
        svc("learners", S("ifElse",
            pm("condition", S("contains", pc("list", "players"), pc("element", "voteResult.0"))),
            pc("thenValue", "voteResult"),
            pm("elseValue", S("ifElse",
                pm("condition", S("contains", pc("list", "voteResult"), pp("element", "Everybody!"))),
                pc("thenValue", "players"), pp("elseValue", []))))),
        svc("tutorial", S("greaterThan",
            pm("arg1", S("listLength", pc("list", "learners"))), pp("arg2", 0))),
    ])

# game-length vote (Stoneball pattern): Short (4) / Full (8)
# (No game-length vote — the game runs open-endedly and asks "play again?" every 4 rounds.)

# Market: a raw createDeck pile is FACEDOWN and renders as an empty widget cell. So mirror
# an_apple_a_day: build a hidden facedown pool (createDeck+set), then moveCards ALL of it into a
# public createCustomDeck display shown FACE-UP in the widget (top tile = current offer; buying
# the top reveals the next). Same for the DONE tile (a real 1-card 'done' set).
market_creates = []
for m in MARKET:                       # m = "market_vowels", ...
    pool = m + "_pool"
    market_creates += [
        act("createDeck", {"preset": {"name": "grapheme_cards", "set": m, "customName": pool}}),
        act("shuffleDeck", {"preset": {"deck": pool}}),
        act("createCustomDeck", {"preset": {"name": m, "public": True, "counter": True}}),
        act("moveCards", {"preset": {"type": "deck", "from": pool, "to": m}}),
        act("shuffleDeck", {"preset": {"deck": m}}),   # shuffle the display so letters aren't clustered
        act("setDeckLabel", {"preset": {"deck": m, "label": MARKET_LABEL[m]}}),
    ]
done_creates = [
    act("createDeck", {"preset": {"name": "grapheme_cards", "set": "done", "customName": "done_pool"}}),
    act("createCustomDeck", {"preset": {"name": "done", "public": True}}),
    act("moveCards", {"preset": {"type": "deck", "from": "done_pool", "to": "done"}}),
    act("setDeckLabel", {"preset": {"deck": "done", "label": "Done"}}),
    act("createCustomDeck", {"preset": {"name": "trash", "public": False}}),
]

before_init = act("emptyAction", save=[
    svc("players", S("allPlayers")),
    svc("numPlayers", S("listLength", pc("list", "players"))),
    svc("roundIndex", 0),
    svc("refillN", 0),   # monotonic id for mid-round market-refill pool decks
    svc("playAgain", True),
    svc("reset", False),
    svc("marketPiles", MARKET),
    svc("clickableDecks", MARKET + ["done"]),
    svc("widgetDecks", MARKET + ["done"]),
])

# hidden pool of free A's — one is loaned into each player's hand every round, collected back
a_pool_create = [act("createDeck", {"preset": {"name": "grapheme_cards", "set": "free_a",
                                               "customName": "a_pool"}})]

beforeLoopActions = (
    [act("changeBackground", {"preset": {"image": "wallpaper"}}), before_init, host_action]
    + market_creates + done_creates + a_pool_create
    + [welcome, tutorial_vote,
       act("changeLayout", {"preset": {"type": "HIGHLIGHT", "direction": "VERTICAL", "percent": 45}}),
       act("setImagesRow", {"preset": {"maxHeight": 140, "images": ["transparent"]}}),
       act("showAllPlayersHands"),
       act("showScore", {"preset": {"order": "highest"}, "cached": {"from": "players", "to": "players"}})]
)

# ══════════════════════════════════════════════════════════════════════════════
# gameLoop
# ══════════════════════════════════════════════════════════════════════════════
SKIP_SETUP = [S("greaterThan", pc("arg1", "gameLoopIndex"), pp("arg2", 0))]
SKIP_ROUND0 = [S("equals", pc("arg1", "gameLoopIndex"), pp("arg2", 0))]   # skip on the round-0 shop

# ── G0a: per-player deck creation ─────────────────────────────────────────────
create_player_decks = grp("Create player decks",
    repeat={"qnt": getcache("numPlayers")}, skip=SKIP_SETUP, actions=[
        set_player_names(),
        # draw pile — starts empty (players buy their own start). Shown FACE-DOWN in the last
        # column of the player's row, inspectable ONLY by its owner so they can plan ahead.
        act("createCustomDeck", {"preset": {"public": True, "facedown": True,
              "inspectDeck": True, "counter": True}, "computed": {"name": getcache("drawName")}}),
        act("setDeckInspectors", {"computed": {"deck": one("drawName"), "inspectors": one("playerId")}}),
        act("createCustomDeck", {"preset": {"public": True}, "computed": {"name": getcache("discName")}}),
        act("createCustomDeck", {"preset": {"public": False}, "computed": {"name": getcache("spellName")}}),
        act("createCustomDeck", {"preset": {"public": False}, "computed": {"name": getcache("keepName")}}),
    ] + [act("createCustomDeck", {"preset": {"public": True},
              "computed": {"name": getcache(f"wordNames.{i}")}}) for i in range(WORD_COLS)]
    + [act("emptyAction", save=[svc("widgetDecks",   # row = 6 word cols + the draw deck (col 7)
            S("concat", pc("list1", "widgetDecks"),
              pm("list2", S("append", pc("list", "wordNames"), pc("element", "drawName")))))]),
       act("setDeckLabel", {"computed": {"deck": getcache("wordNames.0"),
            "label": S("getPlayerNameById", pc("id", "playerId"))}}),
       act("setDeckLabel", {"preset": {"label": "Draw"}, "computed": {"deck": getcache("drawName")}})])

# ── G0b: build the central widget ─────────────────────────────────────────────
create_widget = grp("Build widget", skip=SKIP_SETUP, actions=[
    act("createGenericCardWidget", {
        "preset": {"ratio": "1", "cardback": "cardback", "backgroundImage": WOOD},
        "cached": {"decks": "widgetDecks"},
        "computed": {"dimensions": S("createList",
            pm("arg1", S("inc", pc("arg", "numPlayers"))), pp("arg2", COLS))}}),
    # everyone starts with 10 points to spend on their initial tiles (round-0 shop)
    score_set("players", 10)])

# ── G1: tutorial ──────────────────────────────────────────────────────────────
def tut_slide(header, text, images=None):
    pre = {"header": header, "text": text, "duration": 15,
           "backgroundColor": BG, "borderColor": BDR, "textColor": TXT}
    if images:
        pre["images"] = images
    return act("createNotification", {"preset": pre, "cached": {"to": "learners"}})

tutorial = grp("Tutorial", skip=[S("logicalNOT", pc("arg", "tutorial"))], actions=[
    tut_slide("How to Play — Part 1",
        "Grapheme is a word-building deck game. Each turn your hand is 6 tiles plus a free A (7 to work with). Spell ONE real word and I'll check it's real! Afterward you may KEEP up to 2 leftover tiles for next turn — the rest go to your discard (your draw pile reshuffles from it when it runs out). So you can plan a little, but you can't hoard a whole word. Some tiles carry two or three letters (like TH or ING). Tap <b>Cheatsheet</b> anytime to see how many of each tile exist.",
        images=["tile_a", "tile_th", "tile_ing", "tile_q"]),
    tut_slide("How to Play — Part 2",
        "Your score is also your MONEY. You start by spending 10 points to buy your OWN opening tiles! After each round, spend points at the market (top of the board) for stronger tiles — and peek at your face-down draw pile (your last column) to plan ahead. Click the green <b>DONE</b> pile when you're finished shopping.",
        images=["tile_st", "tile_e", "tile_ing"]),
    tut_slide("How to Play — Part 3",
        "Each tile's number is BOTH its point value and its price, and playing a word of 6 or more tiles earns a +5 bonus (you get a free A every turn to help!). The game ends when someone reaches <b>40 points</b> — or whenever your group votes to stop sooner. Most points wins (ties share it). Good luck, authors!"),
    act("emptyAction", save=[svc("tutorial", False)]),
])

# ── G2: round start (announce + refill hands) ─────────────────────────────────
round_announce = grp("Round start", actions=[
    # round-0 = the initial shop: everyone spends their 10 starting points on tiles
    act("createNotification", {"preset": {"header": "Buy your starting tiles!",
        "text": "You have 10 points — spend them at the market to build your opening deck. The words you can spell depend on the tiles you pick!",
        "duration": 8, "backgroundColor": BG, "borderColor": BDR, "textColor": TXT, "image": "banner"},
        "cached": {"to": "players"}}, skip=[S("notEqual", pc("arg1", "gameLoopIndex"), pp("arg2", 0))]),
    act("createNotification", {"preset": {"duration": 3, "isAnnounceOnly": True,
        "backgroundColor": BG, "borderColor": BDR, "textColor": TXT, "image": "banner"},
        "cached": {"to": "players"},
        "computed": {"header": fmt("Round ($1)!", M(S("inc", pc("arg", "roundIndex"))))}},
        skip=SKIP_ROUND0)])

skip_reshuffle = [S("logicalNOT", pm("arg",   # skip the reshuffle when the draw pile CAN cover the top-up
    S("greaterThan", pc("arg1", "drawCount"), pm("arg2", decklen("drawName")))))]
refill = grp("Deal hands", skip=SKIP_ROUND0, repeat={"qnt": getcache("numPlayers")}, actions=[
    set_player_names(),
    # KEEP unplayed tiles in hand; only draw enough to top UP to 5 (5 − current hand size)
    act("emptyAction", save=[svc("drawCount", S("maxValue", pm("list", S("createList",
        pp("arg1", 0),
        pm("arg2", S("subtract", pp("arg1", TOPUP),
            pm("arg2", S("listLength", pm("list", S("playerHand", pc("playerId", "playerId"))))))))))) ]),
    # reshuffle discard into draw only if the draw pile can't cover the top-up
    act("moveCards", {"preset": {"type": "deck"},
        "computed": {"from": getcache("discName"), "to": getcache("drawName")}}, skip=skip_reshuffle),
    act("shuffleDeck", {"computed": {"deck": getcache("drawName")}}, skip=skip_reshuffle),
    act("dealDeck", {"preset": {"sortBy": "weight", "order": "asc"},
        "cached": {"targets": "playerId"},
        "computed": {"deck": getcache("drawName"),
            "qnt": S("minValue", pm("list", S("createList",
                pc("arg1", "drawCount"), pm("arg2", decklen("drawName")))))}},
        skip=[S("logicalOR", pm("arg1", S("equals", pc("arg1", "drawCount"), pp("arg2", 0))),
              pm("arg2", S("equals", pm("arg1", decklen("drawName")), pp("arg2", 0))))]),
    # loan 1 free A on top (dealDeck errors on an empty deck, so guard the pool)
    act("dealDeck", {"preset": {"deck": "a_pool", "qnt": 1, "sortBy": "weight", "order": "asc"},
        "cached": {"targets": "playerId"}},
        skip=[S("equals", pm("arg1", S("listLength", pm("list",
            S("getDeckCards", pp("deck", "a_pool"))))), pp("arg2", 0))]),
])

# ── G3: spell (parallel, all players at once) ─────────────────────────────────
spell = grp("Spell a word", skip=SKIP_ROUND0,
    parallel={"type": "smart", "qnt": getcache("numPlayers")}, actions=[
    act("playCards", {"preset": {"minCards": 1, "maxCards": 12, "checkIfValid": True,
        "overrideSpellCheck": True, "playable": "availableCards", "duration": 100,
        "sounds.list": ["soundboard.reminder"], "sounds.waitForSoundEnd": False},
        "computed": {
            "actor": player_at("spaIndex"),
            "playList.0": one(player_at("spaIndex")),
            "target": S("formatString", pp("format", "spell_($1)"), pm("arg1", player_at("spaIndex"))),
            "notification": fmt("($1), spell a word from your hand!",
                M(S("getPlayerNameById", pm("id", player_at("spaIndex")))))}})])

# ── Keep phase: each player carries up to 2 LEFTOVER tiles to next turn; the rest discard.
# The loaned A is reclaimed BEFORE this (see End-of-turn group), so it's never offered here.
# Skip a player who has nothing left in hand to keep.
keep = grp("Keep tiles", skip=SKIP_ROUND0,
    parallel={"type": "smart", "qnt": getcache("numPlayers")}, actions=[
    act("playCards", {"preset": {"minCards": 0, "maxCards": 2, "playable": "availableCards",
        "duration": 30, "sounds.list": ["soundboard.reminder"], "sounds.waitForSoundEnd": False},
        "computed": {
            "actor": player_at("spaIndex"),
            "playList.0": one(player_at("spaIndex")),
            "target": S("formatString", pp("format", "keep_($1)"), pm("arg1", player_at("spaIndex"))),
            "notification": fmt("($1), keep up to 2 tiles for next turn (or none)!",
                M(S("getPlayerNameById", pm("id", player_at("spaIndex")))))}},
        skip=[S("equals", pm("arg1", S("listLength", pm("list",
            S("playerHand", pm("playerId", player_at("spaIndex")))))), pp("arg2", 0))])])

# ── G4: score + reveal (sequential per player) ────────────────────────────────
DUMMIES = [{"name": "a", "rank": 999999, "letter": "a"} for _ in range(COLS + 1)]
def spellCards(): return deckcards("spellName")
def ith_name(i):  # name of i-th played card, padded so index is always valid
    return S("getObjectField", pm("obj", S("selectElement",
        pm("list", S("concat", pc("list1", "spellCards"), pp("list2", DUMMIES))),
        pp("index", i))), pp("field", "name"))

score_actions = [
    set_player_names(),
    act("emptyAction", save=[
        svc("spellCards", spellCards()),
        svc("wordLen", S("listLength", pc("list", "spellCards"))),
        # append 0 so an EMPTY word (player timed out / played nothing) sums to 0 instead of
        # crashing sumAllElementsList on an empty list
        svc("wordScore", S("sumAllElementsList", pm("list", S("append",
            pm("list", S("getObjectFieldList", pc("list", "spellCards"), pp("field", "rank"))),
            pp("element", 0))))),
        # +5 bonus for a long word: at least 6 tiles played (they get a free A each turn)
        svc("usedEnough", S("greaterThan", pc("arg1", "wordLen"), pp("arg2", 5))),
        svc("gain", S("ifElse", pc("condition", "usedEnough"),
            pm("thenValue", S("add", pc("arg1", "wordScore"), pp("arg2", 5))),
            pc("elseValue", "wordScore"))),
    ]),
    score_delta(one("playerId"), "gain"),
]
# place the first 5 tiles individually into columns 0..4
for i in range(WORD_COLS - 1):
    score_actions.append(act("moveCards", {"preset": {"type": "deck", "qnt": 1},
        "computed": {"from": getcache("spellName"), "to": getcache(f"wordNames.{i}"),
                     "cardNames": S("createList", pm("arg1", ith_name(i)))}},
        skip=[S("logicalNOT", pm("arg", S("greaterThan", pc("arg1", "wordLen"), pp("arg2", i))))]))
# column 5 (6th deck): the 6th tile shown individually when the word is EXACTLY 6 tiles
score_actions.append(act("moveCards", {"preset": {"type": "deck", "qnt": 1},
    "computed": {"from": getcache("spellName"), "to": getcache(f"wordNames.{WORD_COLS-1}"),
                 "cardNames": S("createList", pm("arg1", ith_name(WORD_COLS - 1)))}},
    skip=[S("notEqual", pc("arg1", "wordLen"), pp("arg2", WORD_COLS))]))
# column 5: createCard summary of the 6th tile onward ONLY when the word runs past 6 tiles (i.e. 7)
# (the real overflow tiles stay in the spell deck and go to discard at cleanup)
score_actions.append(act("createCard", {
    "preset": {"ratio": 1, "background": BG, "cardImage": IMG + "overflow_bg.png"},
    "computed": {"deck": getcache(f"wordNames.{WORD_COLS-1}"), "name": getcache("ovName"),
        "label": S("listToString", pm("list", S("getObjectFieldList",
            pm("list", S("sublist", pc("list", "spellCards"),
                pp("start", WORD_COLS - 1), pc("end", "wordLen"))),
            pp("field", "letter"))))}},
    skip=[S("logicalNOT", pm("arg", S("greaterThan", pc("arg1", "wordLen"), pp("arg2", WORD_COLS))))]))
# celebratory sound once
score_actions.append(act("emptyAction", {"preset": {"sounds.list": ["soundboard.clap"],
    "sounds.waitForSoundEnd": False}, "cached": {"playList.0": "players"}}))
# long-word bonus flourish (6+ tiles played)
score_actions.append(act("animateBox", {"preset": {"animation": "genius"},
    "computed": {"userIds": one("playerId")}},
    skip=[S("logicalNOT", pc("arg", "usedEnough"))]))
score_actions.append(act("createNotification", {
    "preset": {"isAnnounceOnly": True, "backgroundColor": BG, "borderColor": BDR, "textColor": TXT},
    "cached": {"to": "players"},
    "computed": {"header": fmt("($1) played a 6+ tile word — +5 bonus!",
        M(S("getPlayerNameById", pc("id", "playerId"))))}},
    skip=[S("logicalNOT", pc("arg", "usedEnough"))]))
score = grp("Score words", skip=SKIP_ROUND0, repeat={"qnt": getcache("numPlayers")}, actions=score_actions)
# 10s pause so players can appreciate the words on the board before the next phase
review_delay = grp("Review words", skip=SKIP_ROUND0, actions=[act("emptyAction", {"preset": {"delay": 10}})])

# ── G5: buy phase (pass-based double loop) ────────────────────────────────────
buy_intro = grp("Shopping intro", actions=[
    act("emptyAction", save=[svc("passCount", 0),
        svc("remaining", getcache("players")), svc("orderedBuyers", [])])])

# buy TURN ORDER = lowest current score first: repeatedly pull getPlayersWithMinScore(remaining)
# (a tied group may return >1 at once) and append to orderedBuyers until nobody's left.
buy_order = grp("Buy order (lowest score first)", repeat={"qnt": getcache("numPlayers")}, actions=[
    act("emptyAction",
        skip=[S("equals", pm("arg1", S("listLength", pc("list", "remaining"))), pp("arg2", 0))],
        save=[
            svc("minGroup", S("getPlayersWithMinScore", pc("players", "remaining"))),
            svc("orderedBuyers", S("concat", pc("list1", "orderedBuyers"), pc("list2", "minGroup"))),
            svc("remaining", S("listsSubtract", pc("list1", "remaining"), pc("list2", "minGroup"))),
        ])])
start_buying = grp("Start buying", actions=[act("emptyAction", save=[
    svc("activeBuyers", getcache("orderedBuyers"))])])

# inner pass group (runs inside the [] loop)
buyer = "buyer"  # cache key
# QUIRK: for a FACE-UP Ludio deck the VISIBLE top card is the LAST element of getDeckCards
# (index N-1), NOT index 0. Pad with DUMMIES + clamp the index so an empty/DONE deck can't crash.
def top_obj(deck_param):
    cards = S("getDeckCards", deck_param)
    return S("selectElement",
        pm("list", S("concat", pm("list1", cards), pp("list2", DUMMIES))),
        pm("index", S("maxValue", pm("list", S("createList",
            pp("arg1", 0),
            pm("arg2", S("dec", pm("arg", S("listLength", pm("list", cards))))))))))
def top_rank(deck_param): return S("getObjectField", pm("obj", top_obj(deck_param)), pp("field", "rank"))
skip_done = [S("getCachedValue", pp("name", "isDone"))]

# per-buyer clickable list: a market pile only if its TOP tile is affordable, PLUS "done" —
# except on the round-0 initial shop, where DONE is withheld so players must spend all 10 points
# (they only fall through to auto-done once nothing is affordable, i.e. they're broke).
affordable_svc = [svc("affordableDecks", S("ifElse",
    pm("condition", S("equals", pc("arg1", "gameLoopIndex"), pp("arg2", 0))),
    pp("thenValue", []), pp("elseValue", ["done"])))]
for m in MARKET:
    affordable_svc.append(svc("affordableDecks", S("ifElse",
        pm("condition", S("greaterThan",
            pm("arg1", S("inc", pc("arg", "budget"))), pm("arg2", top_rank(pp("deck", m))))),
        pm("thenValue", S("append", pc("list", "affordableDecks"), pp("element", m))),
        pc("elseValue", "affordableDecks"))))

skip_mustskip = [S("getCachedValue", pp("name", "mustSkip"))]
skip_norefill = [S("logicalNOT", pc("arg", "needRefill"))]
inner_actions = [
    act("emptyAction", save=[
        svc("buyer", S("selectElement", pc("list", "activeBuyers"), pc("index", "repeatIndex"))),
        svc("budget", S("getPlayerScore", pc("playerId", "buyer"))),
    ]),
    act("emptyAction", save=affordable_svc),
    act("emptyAction", save=[
        # default so a broke buyer (no affordable MARKET) is auto-marked DONE without clicking
        svc("clicked", "done"),
        svc("mustSkip", S("equals",
            pm("arg1", S("listLength", pm("list", S("listsSubtract",
                pc("list1", "affordableDecks"), pp("list2", ["done"]))))),
            pp("arg2", 0))),
    ]),
    # red border on whose turn it is (removed at end of their turn)
    act("highlightPlayers", {"preset": {"color": "red"},
        "computed": {"listOfPlayers": one("buyer")}}, skip=skip_mustskip),
    act("selectCentralWidgetDeck", {
        "preset": {"duration": 30,
                   "sounds.list": ["soundboard.reminder"], "sounds.waitForSoundEnd": False},
        "cached": {"decks": "affordableDecks"},
        "computed": {"actors": one("buyer"), "playList.0": one("buyer"),
            # timeout picks DONE normally, but on the round-0 forced shop it auto-buys a tile
            "defaultSelect": S("ifElse",
                pm("condition", S("equals", pc("arg1", "gameLoopIndex"), pp("arg2", 0))),
                pc("thenValue", "affordableDecks.0"), pp("elseValue", "done")),
            "question": fmt("($1), click a tile to buy it into your deck, or click DONE.",
                M(S("getPlayerNameById", pc("id", "buyer"))))}},
        save=[svc("clicked", S("getCachedObjectValue", pp("objectName", "lastActionResult"),
            pc("value", "buyer"), pp("defaultValue", "done")))],
        skip=skip_mustskip),
    act("emptyAction", save=[
        svc("isDone", S("equals", pc("arg1", "clicked"), pp("arg2", "done"))),
        svc("topCard", top_obj(pc("deck", "clicked"))),          # cache the clicked deck's top tile OBJECT
        svc("topName", S("getObjectField", pc("obj", "topCard"), pp("field", "name"))),
        svc("price", S("getObjectField", pc("obj", "topCard"), pp("field", "rank"))),
    ]),
    # deduct the TOP tile's price, then deal that exact top tile onto the buyer's DRAW pile
    # (so it comes into their hand within a round or two, unlike going to discard)
    {**score_delta(one("buyer"), S("negate", pc("arg", "price"))), "skipCondition": skip_done},
    act("moveCards", {"preset": {"type": "deck", "qnt": 1},
        "cached": {"from": "clicked"},
        "computed": {"to": name_expr("draw", "buyer"),
            "cardNames": S("createList", pc("arg1", "topName"))}},
        skip=skip_done),
    # if that purchase just EMPTIED the pile, refill it immediately (re-import the set + shuffle)
    act("emptyAction", save=[svc("needRefill", S("logicalAND",
        pm("arg1", S("logicalNOT", pc("arg", "isDone"))),
        pm("arg2", S("equals",
            pm("arg1", S("listLength", pm("list", S("getDeckCards", pc("deck", "clicked"))))),
            pp("arg2", 0)))))]),
    act("createDeck", {"preset": {"name": "grapheme_cards"}, "cached": {"set": "clicked"},
        "computed": {"customName": S("formatString", pp("format", "rf_($1)"), pc("arg1", "refillN"))}},
        skip=skip_norefill),
    act("moveCards", {"preset": {"type": "deck"}, "cached": {"to": "clicked"},
        "computed": {"from": S("formatString", pp("format", "rf_($1)"), pc("arg1", "refillN"))}},
        skip=skip_norefill),
    act("shuffleDeck", {"cached": {"deck": "clicked"}}, skip=skip_norefill),
    act("emptyAction", save=[svc("refillN", S("inc", pc("arg", "refillN")))], skip=skip_norefill),
    # announce the purchase straight to history (no popup everyone has to dismiss)
    act("createNotification", {
        "preset": {"isAnnounceOnly": True, "backgroundColor": BG, "borderColor": BDR, "textColor": TXT},
        "cached": {"to": "players"},
        "computed": {"header": fmt("($1) bought ($2)",
            M(S("getPlayerNameById", pc("id", "buyer"))),
            M(S("getObjectField", pc("obj", "topCard"), pp("field", "label"))))}},
        skip=skip_done),
    act("removeAllHighlights"),
    # stay active next pass only if they actually bought (didn't click DONE)
    act("emptyAction", save=[svc("stillActive", S("ifElse",
        pm("condition", S("logicalNOT", pc("arg", "isDone"))),
        pm("thenValue", S("append", pc("list", "stillActive"), pc("element", "buyer"))),
        pc("elseValue", "stillActive")))]),
]
inner_pass = grp("Buy pass — each active buyer", repeat={"qnt": S("listLength", pc("list", "activeBuyers"))},
                 actions=inner_actions)
pass_advance = grp("Advance pass", actions=[act("emptyAction", save=[
    svc("activeBuyers", getcache("stillActive")),
    svc("passCount", S("inc", pc("arg", "passCount"))),
    # keep going while buyers remain AND (it's the round-0 forced shop OR under the 7-buy cap)
    svc("isActionLoop", S("logicalAND",
        pm("arg1", S("greaterThan", pm("arg1", S("listLength", pc("list", "activeBuyers"))), pp("arg2", 0))),
        pm("arg2", S("logicalOR",
            pm("arg1", S("equals", pc("arg1", "gameLoopIndex"), pp("arg2", 0))),
            pm("arg2", S("greaterThan", pp("arg1", MAX_BUYS), pc("arg2", "passCount")))))))])])
reset_pass = grp("Reset pass", actions=[act("emptyAction", save=[svc("stillActive", [])])])
buy_loop = [reset_pass, inner_pass, pass_advance]   # [] loop body

# ── G5.5: end of turn — clear the played word off the board and RECLAIM THE LOANED A *before*
# the Keep phase, so the free A is never offered as a keepable tile and the Keep prompt can
# simply skip a player whose hand is then empty. The A is fungible: if it is still in the hand
# (unplayed) recall it from there; if it was played it now sits in the discard, so pull it there.
ROUND0 = S("equals", pc("arg1", "gameLoopIndex"), pp("arg2", 0))
HAS_A_IN_HAND = S("contains",
    pm("list", S("getObjectFieldList",
        pm("list", S("playerHand", pc("playerId", "playerId"))), pp("field", "name"))),
    pp("element", "a"))
end_turn_actions = [set_player_names(),
    # remove any overflow summary card to trash, then the played word tiles → discard
    act("moveCards", {"preset": {"type": "deck", "to": "trash"},
        "computed": {"from": getcache(f"wordNames.{WORD_COLS-1}"),
            "cardNames": S("createList", pc("arg1", "ovName"))}}),
    act("moveCards", {"preset": {"type": "deck"},
        "computed": {"from": getcache("spellName"), "to": getcache("discName")}}),
]
for i in range(WORD_COLS):
    end_turn_actions.append(act("moveCards", {"preset": {"type": "deck"},
        "computed": {"from": getcache(f"wordNames.{i}"), "to": getcache("discName")}}))
end_turn_actions += [
    # A unplayed → recall it straight out of the hand back to the pool
    act("recallCards", {"preset": {"deck": "a_pool", "cardNames": ["a"], "qnt": 1},
        "cached": {"targets": "playerId"}},
        skip=[S("logicalOR", pm("arg1", ROUND0),
            pm("arg2", S("logicalNOT", pm("arg", HAS_A_IN_HAND))))]),
    # A played (now in discard) → pull it from the discard back to the pool
    act("moveCards", {"preset": {"type": "deck", "to": "a_pool", "cardNames": ["a"], "qnt": 1},
        "computed": {"from": getcache("discName")}},
        skip=[S("logicalOR", pm("arg1", ROUND0), pm("arg2", HAS_A_IN_HAND))]),
]
end_turn = grp("End of turn", repeat={"qnt": getcache("numPlayers")}, actions=end_turn_actions)

# ── G6: cleanup — the ≤2 KEPT tiles are already in keep_<id>; discard the rest of the hand,
# then deal the kept tiles back so they carry to next turn (skip the deal if nothing was kept).
cleanup_actions = [set_player_names(),
    act("recallCards", {"cached": {"targets": "playerId"}, "computed": {"deck": getcache("discName")}}),
    act("dealDeck", {"preset": {"qnt": 2, "sortBy": "weight", "order": "asc"},
        "cached": {"targets": "playerId"}, "computed": {"deck": getcache("keepName")}},
        skip=[S("logicalOR", pm("arg1", ROUND0),
            pm("arg2", S("equals", pm("arg1", decklen("keepName")), pp("arg2", 0))))]),
]
cleanup = grp("Cleanup", repeat={"qnt": getcache("numPlayers")}, actions=cleanup_actions)

# (Market piles refill the instant a purchase empties one — see the buy loop above.)

# ── G7: increment round ───────────────────────────────────────────────────────
inc_round = grp("Next round", skip=SKIP_ROUND0, actions=[act("emptyAction", save=[
    svc("roundIndex", S("inc", pc("arg", "roundIndex")))])])

# ── G8: end-of-set play-again vote (Emeralds) — every 4 played rounds (never on round-0 shop) ──
end_of_set = grp("Play again?",
    # skip the vote on the round-0 shop, on non-4th rounds, OR when someone has already hit 40
    # (the game is ending anyway — no point asking to keep playing)
    skip=[S("logicalOR",
        pm("arg1", S("equals", pc("arg1", "gameLoopIndex"), pp("arg2", 0))),
        pm("arg2", S("notEqual",
            pm("arg1", S("remainder", pc("arg1", "roundIndex"), pp("arg2", 4))), pp("arg2", 0))),
        pm("arg3", S("greaterThan", pm("arg1", S("getMaxCurrentScore")), pp("arg2", 39))))],
    actions=[
        act("removeWidget", {"preset": {"id": "GenericCardWidget"}}),
        act("createVote", {"preset": {"title": "PLAY AGAIN?", "type": "target_poll",
            "terminationCondition": "get_majority", "showResultInRealTime": True,
            "showResultDuration": 1, "showResultDelay": 0,
            "targets": ["Reset scores", "Keep scores", "I'M SO DONE"],
            "pollVoteTargetsOptions": {
                "Keep scores": {"icon": "https://res.cloudinary.com/liars-club/image/upload/icons/like.svg",
                    "backgroundColor": "#D3D3D3", "boxIconColor": "#D3D3D3", "textColor": "black", "widgetIconColor": "green"},
                "Reset scores": {"icon": "https://res.cloudinary.com/liars-club/image/upload/icons/like.svg",
                    "backgroundColor": "#D3D3D3", "boxIconColor": "#D3D3D3", "textColor": "black", "widgetIconColor": "blue"},
                "I'M SO DONE": {"icon": "https://res.cloudinary.com/liars-club/image/upload/icons/dislike.svg",
                    "backgroundColor": "#D3D3D3", "boxIconColor": "#D3D3D3", "textColor": "black", "widgetIconColor": "red"}},
            "duration": 120, "question": "Would you like to keep playing?",
            "allowRevoting": True, "backgroundColor": BG, "borderColor": BDR},
            "cached": {"actors": "host"}},
            save=[
                svc("playAgain", S("logicalNOT", pm("arg", S("isTargetGotMajority",
                    pc("voteResult", "lastActionResult"), pp("target", "I'M SO DONE"))))),
                svc("reset", S("isTargetGotMajority",
                    pc("voteResult", "lastActionResult"), pp("target", "Reset scores"))),
            ]),
        act("restoreWidget", {"preset": {"id": "GenericCardWidget"}}),
        # reset scores if requested (rounds keep counting either way)
        score_set("players", 0),  # skipped below unless reset
    ])
# make the score reset conditional on `reset` (the score_set action)
for _a in end_of_set["actions"]:
    if _a.get("key") == "updateScore":
        _a["skipCondition"] = [S("logicalNOT", pc("arg", "reset"))]

# compute the winner name(s) EVERY round before the win check, so it's fresh whether the game
# ends by the play-again vote OR by someone crossing 40 points
check_win = grp("Check game over", checkwin=True, actions=[
    act("emptyAction", save=[svc("winner", S("listToString", pm("list",
        S("getPlayerNamesByIds", pm("ids", S("getPlayersWithMaxScore"))))))])])

# NOTE: the "Play again?" vote fires right after scoring (before buying) so a group that stops
# ends the game at their PEAK score — scores drop as they buy for next round. If they continue,
# buy → cleanup run; if the game ends, checkWinCondition halts before buying.
# Round 0 = the initial shop (deal/spell/score/etc. skip; buy runs so players spend their 10).
# Every round: refill any empty market pile → deal → spell → score → 10s review → play-again → buy.
game_loop = [create_player_decks, create_widget, tutorial, round_announce, refill,
             spell, score, review_delay, inc_round, end_of_set, check_win,
             buy_intro, buy_order, start_buying, buy_loop, end_turn, keep, cleanup]

# ══════════════════════════════════════════════════════════════════════════════
# postGameActions + winCondition (Emeralds)
# ══════════════════════════════════════════════════════════════════════════════
postGameActions = [
    {"key": "hideAllPlayersHands"},
    act("setImagesRow", {"preset": {"maxHeight": 10, "images": ["transparent"]}}),
    act("createNotification", {"preset": {"image": "winner", "backgroundColor": BG, "borderColor": BDR},
        "cached": {"to": "players"},
        "computed": {"header": fmt("($1) ($2)!", C("winner"),
            M(S("ifElse", pm("condition", S("equals",
                pm("arg1", S("listLength", pm("list", S("getPlayersWithMaxScore")))), pp("arg2", 1))),
                pp("thenValue", "wins"), pp("elseValue", "share the win"))))}}),
]
playersWinCondition = {
    # game ends when the group votes to stop OR anyone reaches 40 points
    "gameOverCondition": S("logicalOR",
        pm("arg1", S("logicalNOT", pc("arg", "playAgain"))),
        pm("arg2", S("greaterThan", pm("arg1", S("getMaxCurrentScore")), pp("arg2", 39)))),
    "winners": S("getPlayerNamesByIds", pm("ids", S("getPlayersWithMaxScore"))),
}

raw = {
    "gameInitOptions": gio, "visualSettings": visualSettings,
    "beforeLoopActions": beforeLoopActions, "gameLoop": game_loop,
    "playersWinCondition": playersWinCondition, "postGameActions": postGameActions,
}

# ══════════════════════════════════════════════════════════════════════════════
# strings refactor (hoist display copy → gameInitOptions.strings.Default) +
# visualSettings refactor (strip modal colors that cascade from visualSettings)
# ══════════════════════════════════════════════════════════════════════════════
SVC_NAMES = set()
def _collect_svc(node):
    if isinstance(node, dict):
        for s in node.get("saveValueInCache", []) or []:
            if isinstance(s, dict) and "name" in s: SVC_NAMES.add(s["name"])
        for v in node.values(): _collect_svc(v)
    elif isinstance(node, list):
        for v in node: _collect_svc(v)
for _sect in ["beforeLoopActions", "gameLoop", "postGameActions"]:
    _collect_svc(raw[_sect])

STR, VAL2KEY = {}, {}
def _slug(s):
    t = re.sub(r"<[^>]+>", " ", s); t = re.sub(r"\(\$\d+\)", " ", t)
    words = re.findall(r"[A-Za-z0-9]+", t)[:4]
    return (words[0].lower() + "".join(w.capitalize() for w in words[1:])) if words else "str"
def hoist(value, base=None):
    vk = json.dumps(value, sort_keys=True)
    if vk in VAL2KEY: return VAL2KEY[vk]
    base = base or (_slug(value) if isinstance(value, str) else "val")
    k, i = base, 2
    while k in STR or k in SVC_NAMES: k = f"{base}{i}"; i += 1
    STR[k] = value; VAL2KEY[vk] = k; return k

COPY_FIELDS = ["header", "text", "title", "subtitle", "message", "placeholder", "label", "question"]
IMG_ALIAS_KEY = {"banner": "bannerImg", "wallpaper": "wallpaperImg"}
def _is_identifier_template(fmt):   # e.g. "draw_($1)" / "word_($1)_0" — a deck name, NOT display copy
    return (" " not in fmt) and bool(re.fullmatch(r"[A-Za-z0-9_]*", re.sub(r"\(\$\d+\)", "", fmt)))
def hoist_action(a):
    pl = a.get("payload")
    if not isinstance(pl, dict): return
    pre = pl.get("preset", {}); cached = pl.setdefault("cached", {})
    for f in COPY_FIELDS:
        if f in pre and isinstance(pre[f], str): cached[f] = hoist(pre.pop(f))
    if pre.get("image") in IMG_ALIAS_KEY:
        alias = pre.pop("image")
        cached["image"] = hoist(alias, IMG_ALIAS_KEY[alias])
    if isinstance(pre.get("poll.targets"), list):
        cached["poll.targets"] = hoist(pre.pop("poll.targets"), "everybodyNobodyTargets")
    if isinstance(pre.get("pollVoteTargetsOptions"), dict):
        cached["pollVoteTargetsOptions"] = hoist(pre.pop("pollVoteTargetsOptions"), "everybodyNobodyOptions")
    if not cached: pl.pop("cached", None)
def walk_hoist(node):
    if isinstance(node, dict):
        if node.get("selector") == "formatString":
            for p in node.get("params", []):
                if p.get("name") == "format" and p.get("type") == "preset" \
                        and isinstance(p.get("value"), str) and not _is_identifier_template(p["value"]):
                    p["type"] = "cached"; p["value"] = hoist(p["value"])
                elif p.get("name", "").startswith("arg") and p.get("type") == "preset" \
                        and isinstance(p.get("value"), str) and " " in p["value"]:
                    p["type"] = "cached"; p["value"] = hoist(p["value"])
        if node.get("key"): hoist_action(node)
        for v in node.values(): walk_hoist(v)
    elif isinstance(node, list):
        for v in node: walk_hoist(v)
for _sect in ["beforeLoopActions", "gameLoop", "postGameActions"]:
    walk_hoist(raw[_sect])

def fix_vote_literal(node):   # tutorial mixVote learners svc compares voteResult contains "Everybody!"
    if isinstance(node, dict):
        if node.get("selector") == "contains":
            for p in node.get("params", []):
                if p.get("type") == "preset" and p.get("value") == "Everybody!":
                    p["type"] = "cached"; p["value"] = "everybodyNobodyTargets.0"
        for v in node.values(): fix_vote_literal(v)
    elif isinstance(node, list):
        for v in node: fix_vote_literal(v)
fix_vote_literal(raw["beforeLoopActions"])

raw["gameInitOptions"]["strings"] = {"Default": STR}

# strip the shared modal colours from cascade actions (they inherit from visualSettings)
CASCADE = {"createNotification", "createVote", "createMixVote", "createInput", "createConfirmation"}
def strip_colors(node):
    if isinstance(node, dict):
        if node.get("key") in CASCADE:
            pre = (node.get("payload", {}) or {}).get("preset", {})
            for c, val in [("backgroundColor", BG), ("textColor", TXT), ("borderColor", BDR)]:
                if pre.get(c) == val: pre.pop(c)
        for v in node.values(): strip_colors(v)
    elif isinstance(node, list):
        for v in node: strip_colors(v)
for _sect in ["beforeLoopActions", "gameLoop", "postGameActions"]:
    strip_colors(raw[_sect])

# normalize action/group key ordering to the validator's canonical order
ACTION_ORDER = ["key", "skipCondition", "payload", "postHandler", "saveValueInCache"]
GROUP_ORDER = ["name", "turnPlayersToSpectators", "turnSpectatorsToPlayers",
               "skipCondition", "repeat", "parallel", "checkWinCondition", "actions"]
def norm(node):
    if isinstance(node, list):
        return [norm(x) for x in node]
    if isinstance(node, dict):
        node = {k: norm(v) for k, v in node.items()}
        if "key" in node:
            order = ACTION_ORDER
        elif "actions" in node or "repeat" in node or "parallel" in node:
            order = GROUP_ORDER
        elif node and set(node.keys()) <= {"preset", "cached", "computed"}:   # a payload
            order = ["preset", "cached", "computed"]
        else:
            order = None
        if order is None:
            return node
        return {**{k: node[k] for k in order if k in node},
                **{k: v for k, v in node.items() if k not in order}}
    return node
for sect in ["beforeLoopActions", "gameLoop", "postGameActions"]:
    raw[sect] = norm(raw[sect])

os.makedirs(os.path.dirname(OUT), exist_ok=True)
json.dump(raw, open(OUT, "w"), indent=1)
print("wrote", OUT)
