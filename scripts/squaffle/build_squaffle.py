#!/usr/bin/env python3
"""Build game_jsons/squaffle.json — Squaffle, a Quiddler-inspired turn-based word game.

Design (user-approved, v4 — full overhaul from the old round/go-out model):
  * 2-6 players, fully TURN-BASED (one gameLoop pass = one player's turn). No rounds.
  * On your turn you pick ONE of three actions (createVote): DRAW 1 (stock or discard-top),
    SWAP up to 5 (discard 1-5 → draw the same number back), or PLAY a word (checkIfValid;
    score Σ(letter ranks); then draw back up to 5). Hands generally GROW (draw > spend).
  * Each player's row of 6 word slots secretly has one random 2x (double-score) slot and one
    random 3x (triple-score) slot, labelled "2x"/"3x"; a word landing there scores ×2 / ×3.
    No leftover penalty.
  * Game ENDS the instant a player has played their 7th word → 7 word columns per row.
  * Players CAN become spectators (hand → discard, grid re-indexed) but spectators can NOT
    rejoin. Highest score at game end wins.

Per-player word DISPLAY: each player's played words render in their widget row; tracked in
`wordTextsList` (position-indexed list of word-text lists) so it survives a player leaving —
rebuilt on redraw. Reuses Grapheme's (build_paperback.py) DSL + hoist/strip/norm pipeline.
RE-RUN to rebuild the json (don't hand-edit). Deck: squaffle_cards (set "full").
"""
import json, os, re

OUT = "/Users/ankitbuddhiraju/Documents/claude/Code/game_jsons/squaffle.json"
IMG = "https://res.cloudinary.com/liars-club/image/upload/images/squaffle/"
BG, TXT, BDR = "#e8dcc0", "#3a2c1a", "#7a5a34"
HL_COLOR = "#FFBF00"            # amber deck-highlight for the action the current player chose
WOOD = "https://res.cloudinary.com/liars-club/image/upload/wood_qbegm0.jpg"
DECK = "squaffle_cards"
MAXP = 6
SLOTS = 6                       # word columns per player; game ends when a player fills all 6
WORDS_TO_WIN = 6                # play your 6th word → triggers the final lap
START_HAND = 5                  # starting hand (grows over the game); tunable
DRAW_BACK = 5                   # max cards swapped in one Swap action
REFILL_TO = 5                   # after playing a word, only draw back UP TO this many cards
HAND_CAP = 11                   # you can't draw a new card once your hand holds 11
TESTING = False                 # True strips timed-turn durations for untimed human testing
ALL_WORD_DECKS = [f"word_{p}_{k}" for p in range(MAXP) for k in range(SLOTS)]
SLOT_IDX = list(range(SLOTS))   # [0..SLOTS-1]; per row we pick a random 2x slot + a random 3x slot
# the four action buttons live in the widget top row; player clicks one to choose their action.
# DRAW & PLAY (draw a card, then immediately play a word) is usable only ONCE per game per player.
ACT_DRAW, ACT_SWAP, ACT_PLAY, ACT_DRAWPLAY = "act_draw", "act_swap", "act_play", "act_drawplay"
ACTION_DECKS = [ACT_DRAW, ACT_SWAP, ACT_PLAY, ACT_DRAWPLAY]
TOP_ROW = ["stock", "discard"] + ACTION_DECKS   # widget row 0 (6 cols; SLOTS==6)
DUMMY = {"name": "a", "rank": 0, "size": 0, "label": "A"}   # pad for safe selectElement on empty deck
EMPTY_SEED = [[] for _ in range(MAXP)]      # seed for the per-player word-text/score lists
PADW = [""] * SLOTS                          # pad so slot index 0..SLOTS-1 is always valid
PADSCORE = [0] * SLOTS

# ── DSL helpers (from build_paperback.py) ──────────────────────────────────────
def pc(n, v): return {"name": n, "type": "cached", "value": v}
def pp(n, v): return {"name": n, "type": "preset", "value": v}
def pm(n, v): return {"name": n, "type": "computed", "value": v}
def S(sel, *ps): return {"selector": sel, "params": list(ps)}
def _p(x, argname): return pc(argname, x) if isinstance(x, str) else pm(argname, x)
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
        ps.append({"name": f"arg{i}", "type": a[0], "value": a[1]})
    return S("formatString", *ps)
def C(v): return ("cached", v)
def P(v): return ("preset", v)
def M(v): return ("computed", v)
def getcache(name): return S("getCachedValue", pp("name", name))
def deckcards(name_cached): return S("getDeckCards", pc("deck", name_cached))
def decklen(name_cached): return S("listLength", pm("list", deckcards(name_cached)))
def decklen_lit(name): return S("listLength", pm("list", S("getDeckCards", pp("deck", name))))
def player_at(idx_cached): return S("selectElement", pc("list", "players"), pc("index", idx_cached))
def one(idexpr): return S("createList", _p(idexpr, "arg1"))
def score_delta(ids_expr, delta_expr):
    return act("updateScore", {"computed": {"scores": S("createList", pm("arg1",
        S("createDict", pp("keys", ["list", "delta"]),
          pm("values", S("createList", _p(ids_expr, "arg1"), _p(delta_expr, "arg2"))))))}})
def score_delta_lit(ids_expr, lit):
    return act("updateScore", {"computed": {"scores": S("createList", pm("arg1",
        S("createDict", pp("keys", ["list", "delta"]),
          pm("values", S("createList", _p(ids_expr, "arg1"), pp("arg2", lit))))))}})
def score_set(ids_expr, val):
    return act("updateScore", {"computed": {"scores": S("createList", pm("arg1",
        S("createDict", pp("keys", ["list", "score"]),
          pm("values", S("createList", _p(ids_expr, "arg1"), pp("arg2", val))))))}})

# ── Squaffle-specific helpers ──────────────────────────────────────────────────
def wname_ci(k):  return S("formatString", pp("format", f"word_($1)_{k}"), pc("arg1", "ci"))
def wname_pi(k):  return S("formatString", pp("format", f"word_($1)_{k}"), pc("arg1", "repeatIndex"))
def dcards_node(node): return S("getDeckCards", pm("deck", node))
def dlen_node(node):   return S("listLength", pm("list", dcards_node(node)))
def _fieldsum(cards_list_node, field):
    return S("sumAllElementsList", pm("list", S("append",
        pm("list", S("getObjectFieldList", pm("list", cards_list_node), pp("field", field))),
        pp("element", 0))))
def _fieldsum_c(list_cached, field):   # same, over an already-cached card-object list
    return S("sumAllElementsList", pm("list", S("append",
        pm("list", S("getObjectFieldList", pc("list", list_cached), pp("field", field))),
        pp("element", 0))))
def _len_c(list_cached): return S("listLength", pc("list", list_cached))
def handranksum(pid_cached): return _fieldsum(S("playerHand", pc("playerId", pid_cached)), "rank")
def handlen(pid_cached): return S("listLength", pm("list", S("playerHand", pc("playerId", pid_cached))))
def set_at_i(listname, idx_cached, val_node):   # parallel list, element idx_cached := val_node
    return S("concat",
        pm("list1", S("sublist", pc("list", listname), pp("start", 0), pc("end", idx_cached))),
        pm("list2", S("createList", pm("arg1", val_node))),
        pm("list3", S("sublist", pc("list", listname),
            pm("start", S("inc", pc("arg", idx_cached))), pc("end", "numPlayers"))))
def conn_dur(actor_cached, secs):   # short duration if the sole actor is disconnected (AFK safety)
    if TESTING: return None
    return S("ifElse", pm("condition", S("contains",
        pm("list", S("allConnectedUsers")), pc("element", actor_cached))),
        pp("thenValue", secs), pp("elseValue", 1))
def with_dur(computed, actor_cached, secs):
    d = conn_dur(actor_cached, secs)
    if d is not None: computed["duration"] = d
    return computed

# ══════════════════════════════════════════════════════════════════════════════
# gameInitOptions
# ══════════════════════════════════════════════════════════════════════════════
gio = {
    "minPlayers": 2, "maxPlayers": MAXP, "time": 25,
    "notChangeLayoutAfterGame": True, "allowRecorder": True,
    "allowSpectatorBecomePlayer": False, "allowPlayerBecomeSpectator": True,
    "roleConfirmation": False, "useDefaultRoles": True,
    "teams": {"all": {"id": "all", "name": "All", "color": BDR, "roles": ["player"]}},
    "cheatsheet": {"label": "Cheatsheet", "image": IMG + "cheatsheet.png"},
    "roles": [{"roleInfo": {"id": "player", "name": "Wordsmith",
        "description": "Spell words, empty your hand, out-score the table!",
        "avatar": "https://res.cloudinary.com/liars-club/image/upload/card_player_ed7jck.webp",
        "team": "all", "prefix": "a "}, "isDefaultRole": True, "isRequired": False}],
    "images": {
        "wallpaper": {"url": IMG + "wallpaper.jpg"},
        "banner": {"url": IMG + "banner.png"},
        "cardback": {"url": IMG + "cardback.png"},
        "act_draw_img": {"url": IMG + "act_draw.png"},
        "act_swap_img": {"url": IMG + "act_swap.png"},
        "act_play_img": {"url": IMG + "act_play.png"},
        "act_drawplay_img": {"url": IMG + "act_drawplay.png"},
        "transparent": {"url": "https://res.cloudinary.com/liars-club/image/upload/transparent_sbx4wv.png"},
        "winner": {"url": "https://res.cloudinary.com/liars-club/image/upload/winner_h5eyfr.gif"},
        "tile_q": {"url": IMG + "qu.png"}, "tile_th": {"url": IMG + "th.png"},
        "tile_a": {"url": IMG + "a.png"}, "tile_e": {"url": IMG + "e.png"},
    },
    "animations": {"celebrate": "https://lottie.host/3bac8eee-31d7-4284-8831-b2f7d8d814a6/kOArNSkeDj.json"},
    "soundboard": {"default": {
        "reminder": "https://res.cloudinary.com/liars-club/video/upload/audio/reminder.mp4",
        "clap": "https://res.cloudinary.com/liars-club/video/upload/audio/polite_clap.mp3",
        "success": "https://res.cloudinary.com/liars-club/video/upload/audio/forsee.mp3",
        "discard": "https://res.cloudinary.com/liars-club/video/upload/audio/discard.mp3"}},
}
visualSettings = {"backgroundColor": BG, "textColor": TXT, "borderColor": BDR,
                  "cardHandBackgroundImage": WOOD, "isCardAnimationsOff": True,
                  "reorderHandCards": True}

# ══════════════════════════════════════════════════════════════════════════════
# beforeLoopActions
# ══════════════════════════════════════════════════════════════════════════════
host_action = act("emptyAction", save=[svc("host", S("ifElse",
    pm("condition", S("contains", pc("list", "players"), pm("element", S("getHostPlayerId")))),
    pm("thenValue", S("createList", pm("arg1", S("getHostPlayerId")))),
    pm("elseValue", S("createList", pc("arg1", "players.0")))))])

welcome = act("createNotification", {
    "preset": {"header": "Welcome to Squaffle!", "image": "banner", "duration": 8,
               "backgroundColor": BG, "borderColor": BDR, "textColor": TXT},
    "cached": {"to": "players"},
    "computed": {"text": fmt(
        "<b>($1)</b> - in a moment, tell me whether you want Ludio to teach your group how to play Squaffle!",
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

before_init = act("emptyAction", save=[
    svc("players", S("allPlayers")),
    svc("numPlayers", S("listLength", pc("list", "players"))),
    svc("gameOver", False), svc("winner", ""), svc("one", 1), svc("didWord", False),
    svc("redraw", True),
    svc("finalLap", False), svc("finalTurnsLeft", 0),   # end-game: once someone hits 6 words
    svc("drawPlayUsers", []),   # player ids who've spent their once-per-game DRAW & PLAY
    # per-player parallel lists (index = player position): the word TEXTS and the word SCORES each
    # player has played. Length = words played; hitting WORDS_TO_WIN triggers the final lap.
    svc("wordTextsList", S("sublist", pp("list", EMPTY_SEED), pp("start", 0), pc("end", "numPlayers"))),
    svc("wordScoresList", S("sublist", pp("list", EMPTY_SEED), pp("start", 0), pc("end", "numPlayers"))),
    # per-player random score-multiplier slot indices: mult2List[i] = which of that player's 6 word
    # slots doubles (2x), mult3List[i] = which triples (3x). Filled once in "Assign multipliers".
    svc("mult2List", []), svc("mult3List", []),
    svc("currentPlayer", getcache("players.0")),
    svc("allWordDecks", ALL_WORD_DECKS),
    svc("actionDecks", ACTION_DECKS),
    svc("topRow", TOP_ROW),
])

# deck creation (unrolled — beforeLoopActions can't repeat). stock = facedown draw pile filled
# from the full set. Widget decks (stock/discard/action buttons/word slots) get enlargeOnHover.
deck_creates = [
    act("createDeck", {"preset": {"name": DECK, "set": "full", "customName": "full_pool"}}),
    act("createCustomDeck", {"preset": {"name": "stock", "public": True, "facedown": True, "counter": True, "enlargeOnHover": True}}),
    act("moveCards", {"preset": {"type": "deck", "from": "full_pool", "to": "stock"}}),
    act("shuffleDeck", {"preset": {"deck": "stock"}}),
    act("createCustomDeck", {"preset": {"name": "discard", "public": True, "counter": True, "inspectDeck": True, "enlargeOnHover": True}}),
    act("createCustomDeck", {"preset": {"name": "draw_tmp", "public": False}}),      # 1-card draw-from-discard buffer
    act("createCustomDeck", {"preset": {"name": "trash", "public": False}}),         # cleared display cards
]
for a in ACTION_DECKS:   # the three clickable action buttons
    deck_creates.append(act("createCustomDeck", {"preset": {"name": a, "public": True, "enlargeOnHover": True}}))
for pi in range(MAXP):   # per-player hidden scratch deck where a played word's tiles land
    deck_creates.append(act("createCustomDeck", {"preset": {"name": f"spell_{pi}", "public": False}}))
for wd in ALL_WORD_DECKS:
    deck_creates.append(act("createCustomDeck", {"preset": {"name": wd, "public": True, "enlargeOnHover": True}}))

beforeLoopActions = (
    [act("changeBackground", {"preset": {"image": "wallpaper"}}), before_init, host_action]
    + deck_creates
    + [welcome, tutorial_vote,
       # deal the starting hand + flip one upcard onto the discard
       act("dealDeck", {"preset": {"deck": "stock", "qnt": START_HAND}, "cached": {"targets": "players"}}),
       act("moveCards", {"preset": {"type": "deck", "from": "stock", "to": "discard", "qnt": 1}}),
       act("showAllPlayersHands"),
       act("showScore", {"preset": {"order": "highest"}, "cached": {"from": "players", "to": "players"}})]
)

# ══════════════════════════════════════════════════════════════════════════════
# gameLoop  (one pass = one round)
# ══════════════════════════════════════════════════════════════════════════════
SKIP_SETUP = [S("greaterThan", pc("arg1", "gameLoopIndex"), pp("arg2", 0))]

# ── Tutorial (once, opt-in) ────────────────────────────────────────────────────
def tut_slide(header, text, images=None):
    pre = {"header": header, "text": text, "duration": 16,
           "backgroundColor": BG, "borderColor": BDR, "textColor": TXT}
    if images: pre["images"] = images
    return act("createNotification", {"preset": pre, "cached": {"to": "learners"}})
tutorial = grp("Tutorial", skip=[S("logicalNOT", pc("arg", "tutorial"))], actions=[
    tut_slide("How to Play — Part 1",
        "Squaffle is a turn-based word game. On your turn, click one of the action tiles in the middle: DRAW a card (from the stock or top of the discard), SWAP up to 5 cards (discard some, draw the same number back), PLAY a word, or — ONCE per game — DRAW & PLAY (draw a card, then immediately play a word). Your hand can hold at most 11 cards.",
        images=["tile_a", "tile_th", "tile_q", "tile_e"]),
    tut_slide("How to Play — Part 2",
        "PLAY A WORD: spell a real word from your hand — I check every one! You score the value of its letters (and if that drops you below 5 cards, you refill back up to 5). Each word lands in your row, labelled with its score, so you can see how everyone is doing."),
    tut_slide("Bonus Spaces",
        "Look at your six word slots: one is a 2x space and another is a 3x space — marked \"2x\" and \"3x\". They're placed randomly for each player, and everyone can see every player's bonus spaces. Your words fill your row left to right, so plan which word lands where: a word placed on your 2x space scores DOUBLE, and on your 3x space it scores TRIPLE!",
        images=["tile_q", "tile_th"]),
    tut_slide("Winning",
        "When someone plays their 6th word (filling their six columns), the end is triggered: every OTHER player gets ONE final turn in which they must play a word. Then whoever has the most points wins — so a last-second flurry can still steal it. Good luck!"),
    act("emptyAction", save=[svc("tutorial", False)]),
])

# ── Setup (idx 0 only): constant deck labels + the 3 persistent action-button cards ─────────────
setup = grp("Setup", skip=SKIP_SETUP, actions=[
    act("setDeckLabel", {"preset": {"deck": "stock", "label": "Draw"}}),
    act("setDeckLabel", {"preset": {"deck": "discard", "label": "Discard"}}),
    act("createCard", {"preset": {"ratio": 1, "cardImage": IMG + "act_draw.png", "deck": ACT_DRAW, "name": "btn_draw"}}),
    act("createCard", {"preset": {"ratio": 1, "cardImage": IMG + "act_swap.png", "deck": ACT_SWAP, "name": "btn_swap"}}),
    act("createCard", {"preset": {"ratio": 1, "cardImage": IMG + "act_play.png", "deck": ACT_PLAY, "name": "btn_play"}}),
    act("createCard", {"preset": {"ratio": 1, "cardImage": IMG + "act_drawplay.png", "deck": ACT_DRAWPLAY, "name": "btn_drawplay"}}),
])
# ── Build widget (whenever `redraw` is set: game start OR after a player joins/leaves): lay out
#    the board for the CURRENT player count. Word rows = one per current player. ──
REDRAW_SKIP = [S("logicalNOT", pc("arg", "redraw"))]
build_widget = grp("Build widget", skip=REDRAW_SKIP, actions=[
    act("changeLayout", {"preset": {"type": "HIGHLIGHT", "direction": "VERTICAL", "percent": 45}}),
    act("setImagesRow", {"preset": {"maxHeight": 140, "images": ["transparent"]}}),
    act("createGenericCardWidget", {
        "preset": {"ratio": "1", "cardback": "cardback", "backgroundImage": WOOD},
        "computed": {
            "decks": S("concat", pc("list1", "topRow"),
                pm("list2", S("sublist", pc("list", "allWordDecks"), pp("start", 0),
                    pm("end", S("multiply", pc("arg1", "numPlayers"), pp("arg2", SLOTS)))))),
            "dimensions": S("createList", pm("arg1", S("inc", pc("arg", "numPlayers"))), pp("arg2", SLOTS))}}),
])
redraw_done = grp("Redraw done", skip=REDRAW_SKIP, actions=[act("emptyAction", save=[svc("redraw", False)])])

# ── Assign multipliers (idx 0 only): for EACH player row, pick 2 distinct random word-slot indices —
#    one becomes that row's 2x (double-score) slot, the other its 3x (triple-score) slot. Built once
#    per player into the parallel lists mult2List / mult3List (trimmed on a player leaving). ──
assign_mult = grp("Assign multipliers", skip=SKIP_SETUP, repeat={"qnt": getcache("numPlayers")}, actions=[
    act("emptyAction", save=[svc("multPick",
        S("randomElementsList", pp("list", SLOT_IDX), pp("length", 2)))]),
    act("emptyAction", save=[
        svc("mult2List", S("append", pc("list", "mult2List"), pc("element", "multPick.0"))),
        svc("mult3List", S("append", pc("list", "mult3List"), pc("element", "multPick.1"))),
    ]),
])

# ── Render words: rebuild every player's word row from wordTextsList/wordScoresList (runs on redraw
#    = game start or a player leaving). Each slot's LABEL shows that word's score (slot 0 also shows
#    the player's name, e.g. "Ankit 10"); empty slots show just the name (slot 0) or nothing. ──
def _slot_label(k):
    # slot 0 always carries the player's name. A 2x/3x slot shows "2x"/"3x" while empty; once a word
    # lands there it shows that word's score with the multiplier in parens, e.g. "20 (2x)". Normal
    # slots just show the word's score once played.
    has = f"has{k}"   # cached bool "this slot already has a word" (computed once per player below)
    is2 = S("equals", pp("arg1", k), pc("arg2", "myMult2"))
    is3 = S("equals", pp("arg1", k), pc("arg2", "myMult3"))
    sc = C(f"paddedScores.{k}")
    def mult(tag):
        if k == 0:
            return S("ifElse", pc("condition", has),
                pm("thenValue", fmt(f"($1) ($2) ({tag})", C("pName"), sc)),
                pm("elseValue", fmt(f"($1) {tag}", C("pName"))))
        return S("ifElse", pc("condition", has),
            pm("thenValue", fmt(f"($1) ({tag})", sc)), pp("elseValue", tag))
    if k == 0:
        normal = S("ifElse", pc("condition", has),
            pm("thenValue", fmt("($1) ($2)", C("pName"), sc)), pc("elseValue", "pName"))
    else:
        normal = S("ifElse", pc("condition", has),
            pm("thenValue", fmt("($1)", sc)), pp("elseValue", ""))
    return S("ifElse", pm("condition", is2), pm("thenValue", mult("2x")),
        pm("elseValue", S("ifElse", pm("condition", is3), pm("thenValue", mult("3x")),
            pm("elseValue", normal))))
_render_slots = []
for k in range(SLOTS):
    _slot = S("formatString", pp("format", f"word_($1)_{k}"), pc("arg1", "repeatIndex"))
    _render_slots.append(act("moveCards", payload={"preset": {"type": "deck", "to": "trash"},
        "computed": {"from": _slot}}))
    _render_slots.append(act("createCard", skip=[S("lessThanOrEqual", pc("arg1", "myCount"), pp("arg2", k))],
        payload={"preset": {"ratio": 1, "background": BDR, "textColor": "white", "fontHeightPercentage": 18},
            "cached": {"cardText": f"paddedWords.{k}"},
            "computed": {"deck": _slot,
                "name": S("formatString", pp("format", f"rw_($1)_{k}"), pc("arg1", "repeatIndex"))}}))
    _render_slots.append(act("setDeckLabel", {"computed": {"deck": _slot, "label": _slot_label(k)}}))
render_words = grp("Render words", skip=REDRAW_SKIP, repeat={"qnt": getcache("numPlayers")}, actions=[
    act("emptyAction", save=[
        svc("myWords", S("selectElement", pc("list", "wordTextsList"), pc("index", "repeatIndex"))),
        svc("myScores", S("selectElement", pc("list", "wordScoresList"), pc("index", "repeatIndex"))),
        svc("myMult2", S("selectElement", pc("list", "mult2List"), pc("index", "repeatIndex"))),
        svc("myMult3", S("selectElement", pc("list", "mult3List"), pc("index", "repeatIndex"))),
        svc("pName", S("getPlayerNameById", pm("id", player_at("repeatIndex")))),
    ]),
    act("emptyAction", save=[
        svc("myCount", S("listLength", pc("list", "myWords"))),
        svc("paddedWords", S("concat", pc("list1", "myWords"), pp("list2", PADW))),
        svc("paddedScores", S("concat", pc("list1", "myScores"), pp("list2", PADSCORE))),
    ]),
    # per-slot "already has a word" flags, referenced by each slot's label (avoids re-inlining)
    act("emptyAction", save=[svc(f"has{k}",
        S("greaterThan", pc("arg1", "myCount"), pp("arg2", k))) for k in range(SLOTS)]),
] + _render_slots)

# ══════════════════════════════════════════════════════════════════════════════════════════════
# TURN (one gameLoop pass = one player's turn). currentPlayer picks ONE of three actions:
#   Draw 1 · Swap up to 5 · Play a word (+draw back up to 5). Game ends when someone plays word #7.
# ══════════════════════════════════════════════════════════════════════════════════════════════
NOT_FROM = [S("logicalNOT", pc("arg", "fromDiscard"))]
SPELL_CI = S("formatString", pp("format", "spell_($1)"), pc("arg1", "ci"))
# reshuffle the discard back into an empty stock (used before every stock draw)
reshuffle_acts = [
    act("emptyAction", save=[svc("stockEmpty", S("equals", pm("arg1", decklen_lit("stock")), pp("arg2", 0)))]),
    act("moveCards", skip=[S("logicalNOT", pc("arg", "stockEmpty"))],
        payload={"preset": {"type": "deck", "from": "discard", "to": "stock"}}),
    act("shuffleDeck", skip=[S("logicalNOT", pc("arg", "stockEmpty"))], payload={"preset": {"deck": "stock"}}),
]

turn_start = grp("Turn start", actions=[
    # if the current pointer left (became a spectator), hand the turn to the first seated player
    act("emptyAction", save=[svc("currentPlayer", S("ifElse",
        pm("condition", S("contains", pc("list", "players"), pc("element", "currentPlayer"))),
        pc("thenValue", "currentPlayer"), pc("elseValue", "players.0")))]),
    act("emptyAction", save=[
        svc("ci", S("indexOf", pc("list", "players"), pc("element", "currentPlayer"))),
        svc("didWord", False),
        # capture the final-lap flag AT TURN START; on the final lap this player MUST play a word
        svc("wasFinalLap", getcache("finalLap")),
        svc("forcePlay", getcache("finalLap")),
    ]),
    act("highlightPlayers", {"preset": {"color": "red"}, "computed": {"listOfPlayers": one("currentPlayer")}},
        save=[svc("highlightId", getcache("lastActionId"))]),
    act("emptyAction", {"preset": {"sounds.list": ["soundboard.reminder"], "sounds.waitForSoundEnd": False},
        "computed": {"playList.0": one("currentPlayer")}}),
])

# ── Final lap: the player has no choice — their action is forced to PLAY A WORD. ──
force_play = grp("Force play", skip=[S("logicalNOT", pc("arg", "forcePlay"))], actions=[
    act("emptyAction", save=[svc("choice", ACT_PLAY)]),
    act("createNotification", {"preset": {"duration": 4, "backgroundColor": BG, "borderColor": BDR, "textColor": TXT},
        "cached": {"to": "players"},
        "computed": {"header": fmt("($1), it's your last turn — you must play a word!",
            M(S("getPlayerNameById", pc("id", "currentPlayer"))))}}),
])
# ── Choose action (normal turns only): the player clicks one of the action tiles in the top row.
#    `choice` becomes the clicked deck name. DRAW is offered ONLY when the hand isn't full. ──
action_vote = grp("Choose action", skip=[getcache("forcePlay")], actions=[
    act("emptyAction", save=[
        svc("canDraw", S("lessThan", pm("arg1", handlen("currentPlayer")), pp("arg2", HAND_CAP))),
        svc("dpUnused", S("logicalNOT", pm("arg",
            S("contains", pc("list", "drawPlayUsers"), pc("element", "currentPlayer"))))),
    ]),
    # clickable decks: SWAP + PLAY always; DRAW when hand<11; DRAW&PLAY when hand<11 AND still unused
    act("emptyAction", save=[
        svc("canDP", S("logicalAND", pc("arg1", "canDraw"), pc("arg2", "dpUnused"))),
        svc("baseDecks", S("ifElse", pc("condition", "canDraw"),
            pm("thenValue", S("concat", pp("list1", [ACT_DRAW]), pp("list2", [ACT_SWAP, ACT_PLAY]))),
            pp("elseValue", [ACT_SWAP, ACT_PLAY]))),
        svc("defSel", S("ifElse", pc("condition", "canDraw"),
            pp("thenValue", ACT_DRAW), pp("elseValue", ACT_SWAP))),
    ]),
    act("emptyAction", save=[svc("myActionDecks", S("ifElse", pc("condition", "canDP"),
        pm("thenValue", S("append", pc("list", "baseDecks"), pp("element", ACT_DRAWPLAY))),
        pc("elseValue", "baseDecks")))]),
    act("selectCentralWidgetDeck", {
        "preset": {"sounds.list": ["soundboard.reminder"], "sounds.waitForSoundEnd": False},
        "cached": {"decks": "myActionDecks", "defaultSelect": "defSel"},
        "computed": with_dur({"actors": one("currentPlayer"), "playList.0": one("currentPlayer"),
            "question": fmt("($1), click DRAW, SWAP or PLAY to take your turn.",
                M(S("getPlayerNameById", pc("id", "currentPlayer"))))}, "currentPlayer", 30)},
        save=[svc("choice", S("getCachedObjectValue", pp("objectName", "lastActionResult"),
            pc("value", "currentPlayer"), pp("defaultValue", ACT_SWAP)))]),
    # a readable verb phrase for the chosen action, for the history-log line below
    act("emptyAction", save=[svc("actionLabel",
        S("ifElse", pm("condition", S("equals", pc("arg1", "choice"), pp("arg2", ACT_DRAW))),
          pp("thenValue", "draw a card"),
          pm("elseValue", S("ifElse", pm("condition", S("equals", pc("arg1", "choice"), pp("arg2", ACT_SWAP))),
            pp("thenValue", "swap cards"),
            pm("elseValue", S("ifElse", pm("condition", S("equals", pc("arg1", "choice"), pp("arg2", ACT_PLAY))),
              pp("thenValue", "play a word"),
              pp("elseValue", "draw a card and play a word")))))))]),
    # highlight the action tile they picked (cleared in Turn end); log the choice in the history
    act("highlightDecks", {"preset": {"color": HL_COLOR},
        "computed": {"decks": S("createList", pc("arg1", "choice"))}}),
    act("createNotification", {"preset": {"duration": 1, "isAnnounceOnly": True}, "cached": {"to": "players"},
        "computed": {"header": fmt("($1) chose to ($2).",
            M(S("getPlayerNameById", pc("id", "currentPlayer"))), C("actionLabel"))}}),
])

# discard's visible top card, safely (top = last element of getDeckCards on a faceup deck)
_disc_top_name = S("getObjectField", pm("obj", S("selectElement",
    pm("list", S("append", pc("list", "discCards"), pp("element", DUMMY))),
    pm("index", S("maxValue", pm("list", S("createList", pp("arg1", 0),
        pm("arg2", S("dec", pm("arg", S("listLength", pc("list", "discCards"))))))))))), pp("field", "name"))

# ── Draw 1: stock or the discard's top card. Runs for DRAW and for the DRAW & PLAY combo. ──
SKIP_NOT_DRAWSTEP = [S("logicalAND",
    pm("arg1", S("notEqual", pc("arg1", "choice"), pp("arg2", ACT_DRAW))),
    pm("arg2", S("notEqual", pc("arg1", "choice"), pp("arg2", ACT_DRAWPLAY))))]
act_draw = grp("Draw one", skip=SKIP_NOT_DRAWSTEP,
    actions=reshuffle_acts + [
    act("emptyAction", save=[
        svc("drawable", S("ifElse",
            pm("condition", S("greaterThan", pm("arg1", decklen_lit("discard")), pp("arg2", 0))),
            pp("thenValue", ["stock", "discard"]), pp("elseValue", ["stock"]))),
        svc("discCards", S("getDeckCards", pp("deck", "discard"))),
    ]),
    act("emptyAction", save=[svc("discTopName", _disc_top_name)]),
    act("selectCentralWidgetDeck", {
        "preset": {"defaultSelect": "stock", "sounds.list": ["soundboard.reminder"], "sounds.waitForSoundEnd": False},
        "cached": {"decks": "drawable"},
        "computed": with_dur({"actors": one("currentPlayer"), "playList.0": one("currentPlayer"),
            "question": fmt("($1), draw from the stock or the discard.",
                M(S("getPlayerNameById", pc("id", "currentPlayer"))))}, "currentPlayer", 30)},
        save=[svc("drawFrom", S("getCachedObjectValue", pp("objectName", "lastActionResult"),
            pc("value", "currentPlayer"), pp("defaultValue", "stock")))]),
    act("emptyAction", save=[svc("fromDiscard", S("equals", pc("arg1", "drawFrom"), pp("arg2", "discard")))]),
    act("moveCards", skip=NOT_FROM, payload={"preset": {"type": "deck", "from": "discard", "to": "draw_tmp", "qnt": 1},
        "computed": {"cardNames": S("createList", pc("arg1", "discTopName"))}}),
    act("dealDeck", skip=NOT_FROM, payload={"preset": {"deck": "draw_tmp"}, "cached": {"targets": "currentPlayer", "qnt": "one"}}),
    act("dealDeck", skip=[getcache("fromDiscard")], payload={"preset": {"deck": "stock"}, "cached": {"targets": "currentPlayer", "qnt": "one"}}),
])

# ── Swap up to 5: discard 1-5 cards, then draw the same number back off the stock ──
act_swap = grp("Swap cards", skip=[S("notEqual", pc("arg1", "choice"), pp("arg2", ACT_SWAP))], actions=[
    act("playCards", ph="playOneRandomCard", payload={
        "preset": {"minCards": 1, "maxCards": DRAW_BACK, "playable": "availableCards", "target": "discard",
                   "sounds.list": ["soundboard.discard"], "sounds.waitForSoundEnd": False},
        "computed": with_dur({"actor": getcache("currentPlayer"), "playList.0": one("currentPlayer"),
            "notification": fmt("($1), discard up to 5 cards to swap.",
                M(S("getPlayerNameById", pc("id", "currentPlayer"))))}, "currentPlayer", 40)}),
    act("emptyAction", save=[svc("swapCount", S("listLength", pc("list", "lastActionResult.cards")))]),
] + reshuffle_acts + [
    act("emptyAction", save=[svc("swapDraw", S("minValue", pm("list",
        S("createList", pc("arg1", "swapCount"), pm("arg2", decklen_lit("stock"))))))]),
    act("dealDeck", skip=[S("equals", pc("arg1", "swapDraw"), pp("arg2", 0))],
        payload={"preset": {"deck": "stock"}, "cached": {"targets": "currentPlayer", "qnt": "swapDraw"}}),
])

# ── Play a word: spell a real word (letter score × this slot's multiplier, then displayed), draw back up to 5 ──
NO_WORD = [S("logicalNOT", pc("arg", "didWord"))]
NOT_MULT = [S("logicalNOT", pc("arg", "hitMult"))]   # skip unless the word landed on a 2x/3x slot
SKIP_NOT_PLAYSTEP = [S("logicalAND",
    pm("arg1", S("notEqual", pc("arg1", "choice"), pp("arg2", ACT_PLAY))),
    pm("arg2", S("notEqual", pc("arg1", "choice"), pp("arg2", ACT_DRAWPLAY))))]
act_play = grp("Play a word", skip=SKIP_NOT_PLAYSTEP, actions=[
    act("emptyAction", save=[svc("didWord", False)]),
    act("playCards", payload={
        "preset": {"minCards": 1, "maxCards": 12, "checkIfValid": True, "overrideSpellCheck": True,
            "playable": "availableCards", "sounds.list": ["soundboard.reminder"], "sounds.waitForSoundEnd": False},
        "computed": with_dur({"actor": getcache("currentPlayer"), "playList.0": one("currentPlayer"),
            "target": SPELL_CI,
            "notification": fmt("($1), spell a word from your hand!",
                M(S("getPlayerNameById", pc("id", "currentPlayer"))))}, "currentPlayer", 60)}),
    act("emptyAction", save=[
        svc("laid", S("listLength", pc("list", "lastActionResult.cards"))),
        svc("didWord", S("greaterThan", pm("arg1", S("listLength", pc("list", "lastActionResult.cards"))), pp("arg2", 0))),
    ]),
    act("emptyAction", skip=NO_WORD, save=[
        svc("spellCards", dcards_node(SPELL_CI)),
        svc("wordScore", _fieldsum_c("spellCards", "rank")),
        svc("wordText", S("listToString",
            pm("list", S("getObjectFieldList", pc("list", "spellCards"), pp("field", "label"))), pp("delimiter", ""))),
        svc("myWords", S("selectElement", pc("list", "wordTextsList"), pc("index", "ci"))),
        svc("myScores", S("selectElement", pc("list", "wordScoresList"), pc("index", "ci"))),
        svc("myMult2", S("selectElement", pc("list", "mult2List"), pc("index", "ci"))),
        svc("myMult3", S("selectElement", pc("list", "mult3List"), pc("index", "ci"))),
    ]),
    act("emptyAction", skip=NO_WORD, save=[
        svc("oldCount", S("listLength", pc("list", "myWords"))),
        svc("slotName", S("formatString", pp("format", "word_($1)_($2)"), pc("arg1", "ci"),
            pm("arg2", S("listLength", pc("list", "myWords"))))),
    ]),
    # this word's slot multiplier: 2x if it lands on the row's 2x slot, 3x on the 3x slot, else 1x
    act("emptyAction", skip=NO_WORD, save=[
        svc("wordMult", S("ifElse", pm("condition", S("equals", pc("arg1", "oldCount"), pc("arg2", "myMult2"))),
            pp("thenValue", 2),
            pm("elseValue", S("ifElse", pm("condition", S("equals", pc("arg1", "oldCount"), pc("arg2", "myMult3"))),
                pp("thenValue", 3), pp("elseValue", 1))))),
    ]),
    act("emptyAction", skip=NO_WORD, save=[
        svc("finalScore", S("multiply", pc("arg1", "wordScore"), pc("arg2", "wordMult"))),
        svc("hitMult", S("greaterThan", pc("arg1", "wordMult"), pp("arg2", 1))),
    ]),
    {**score_delta(one("currentPlayer"), "finalScore"), "skipCondition": NO_WORD},
    # multiplier hit: WxN in the title, player + earned points in the text, and animate that player
    act("createNotification", skip=NOT_MULT, payload={
        "preset": {"duration": 5, "backgroundColor": BG, "borderColor": BDR, "textColor": TXT}, "cached": {"to": "players"},
        "computed": {"header": fmt("($1) landed on a ($2)x space!", C("wordText"), C("wordMult")),
            "text": fmt("($1) scores ($2) points!", M(S("getPlayerNameById", pc("id", "currentPlayer"))), C("finalScore"))}}),
    act("animateBox", skip=NOT_MULT,
        payload={"preset": {"animation": "celebrate"}, "computed": {"userIds": one("currentPlayer")}}),
    act("emptyAction", skip=NOT_MULT, payload={"preset": {"sounds.list": ["soundboard.success"],
        "sounds.waitForSoundEnd": False}, "cached": {"playList.0": "players"}}),
    act("emptyAction", skip=NO_WORD, save=[
        svc("wordTextsList", set_at_i("wordTextsList", "ci", S("append", pc("list", "myWords"), pc("element", "wordText")))),
        svc("wordScoresList", set_at_i("wordScoresList", "ci", S("append", pc("list", "myScores"), pc("element", "wordScore")))),
    ]),
    # played tiles go to the DISCARD pile (recycled: reshuffled into the stock when it runs out)
    act("moveCards", skip=NO_WORD, payload={"preset": {"type": "deck", "to": "discard"}, "computed": {"from": SPELL_CI}}),
    act("createCard", skip=NO_WORD, payload={
        "preset": {"ratio": 1, "background": BDR, "textColor": "white", "fontHeightPercentage": 18},
        "computed": {"deck": getcache("slotName"), "cardText": getcache("wordText"),
            "name": S("formatString", pp("format", "wc_($1)_($2)"), pc("arg1", "ci"), pc("arg2", "oldCount"))}}),
    # label the slot with the word's score; a 2x/3x slot appends "(2x)"/"(3x)". slot 0 also prefixes
    # the player's name (e.g. "Ankit 20", "Ankit 20 (2x)", "20", or "20 (2x)").
    act("setDeckLabel", skip=NO_WORD, payload={"computed": {"deck": getcache("slotName"),
        "label": S("ifElse", pm("condition", S("equals", pc("arg1", "oldCount"), pp("arg2", 0))),
            pm("thenValue", S("ifElse", pc("condition", "hitMult"),
                pm("thenValue", fmt("($1) ($2) (($3)x)", M(S("getPlayerNameById", pc("id", "currentPlayer"))), C("wordScore"), C("wordMult"))),
                pm("elseValue", fmt("($1) ($2)", M(S("getPlayerNameById", pc("id", "currentPlayer"))), C("wordScore"))))),
            pm("elseValue", S("ifElse", pc("condition", "hitMult"),
                pm("thenValue", fmt("($1) (($2)x)", C("wordScore"), C("wordMult"))),
                pm("elseValue", fmt("($1)", C("wordScore"))))))}}),
] + reshuffle_acts + [
    # draw back ONLY up to REFILL_TO (5): if the hand is already >= 5 after playing, draw nothing;
    # otherwise top up to 5 (never more), capped by the stock size.
    act("emptyAction", save=[svc("drawN", S("minValue", pm("list", S("createList",
        pm("arg1", S("maxValue", pm("list", S("createList", pp("arg1", 0),
            pm("arg2", S("subtract", pp("arg1", REFILL_TO), pm("arg2", handlen("currentPlayer")))))))),
        pm("arg2", decklen_lit("stock"))))))]),
    act("dealDeck", skip=[S("logicalNOT", pc("arg", "didWord")), S("lessThanOrEqual", pc("arg1", "drawN"), pp("arg2", 0))],
        payload={"preset": {"deck": "stock"}, "cached": {"targets": "currentPlayer", "qnt": "drawN"}}),
    # keep the hand open after refilling (in case they emptied it) — item 2
    act("showAllPlayersHands", skip=NO_WORD),
])

# ── Mark the once-per-game DRAW & PLAY as spent (the moment it's chosen, even if no word lands) ──
mark_dp = grp("Spend draw-play", skip=[S("notEqual", pc("arg1", "choice"), pp("arg2", ACT_DRAWPLAY))],
    actions=[act("emptyAction", save=[svc("drawPlayUsers",
        S("append", pc("list", "drawPlayUsers"), pc("element", "currentPlayer")))])])

# ── Turn end: turns always pass to the next player (NO chaining). When a player first reaches 6
#    words, start the FINAL LAP — every other player gets exactly one forced word-turn, then over. ──
turn_end = grp("Turn end", actions=[
    act("removeHighlight", {"cached": {"id": "highlightId"}}),
    act("removeAllHighlightDecks"),
    act("emptyAction", save=[
        svc("myCount", S("listLength", pm("list", S("selectElement", pc("list", "wordTextsList"), pc("index", "ci"))))),
        svc("reached5", S("logicalAND", pm("arg1", S("logicalNOT", pc("arg", "wasFinalLap"))),
            pm("arg2", S("greaterThanOrEqual",
                pm("arg1", S("listLength", pm("list", S("selectElement", pc("list", "wordTextsList"), pc("index", "ci"))))),
                pp("arg2", WORDS_TO_WIN)))))]),
    # start the final lap on the turn someone first hits 5 words (N-1 forced turns for everyone else)
    act("emptyAction", save=[
        svc("finalLap", S("logicalOR", pc("arg1", "finalLap"), pc("arg2", "reached5"))),
        svc("finalTurnsLeft", S("ifElse", pc("condition", "reached5"),
            pm("thenValue", S("dec", pc("arg", "numPlayers"))),
            pm("elseValue", S("ifElse", pc("condition", "wasFinalLap"),
                pm("thenValue", S("dec", pc("arg", "finalTurnsLeft"))), pc("elseValue", "finalTurnsLeft"))))),
    ]),
    act("createNotification", skip=[S("logicalNOT", pc("arg", "reached5"))],
        payload={"preset": {"duration": 5, "image": "banner", "backgroundColor": BG, "borderColor": BDR, "textColor": TXT},
        "cached": {"to": "players"},
        "computed": {"header": fmt("($1) reached 5 words!", M(S("getPlayerNameById", pc("id", "currentPlayer")))),
            "text": fmt("Everyone else gets one last turn — and must play a word.")}}),
    act("emptyAction", save=[
        svc("gameOver", S("logicalOR", pc("arg1", "gameOver"),
            pm("arg2", S("logicalAND", pc("arg1", "finalLap"),
                pm("arg2", S("lessThanOrEqual", pc("arg1", "finalTurnsLeft"), pp("arg2", 0))))))),
        svc("winner", S("listToString", pm("list",
            S("getPlayerNamesByIds", pm("ids", S("getPlayersWithMaxScore")))))),
    ]),
    act("emptyAction", save=[svc("currentPlayer", S("ifElse", pc("condition", "gameOver"),
        pc("thenValue", "currentPlayer"),
        pm("elseValue", S("nextPlayer", pc("playersList", "players"), pc("playerId", "currentPlayer")))))]),
    act("showScore", {"preset": {"order": "highest"}, "cached": {"from": "players", "to": "players"}}),
])

# safe transition point (between turns): the engine applies queued player->spectator swaps here.
change_players = grp("Change players", actions=[act("removeAllHighlights")])
change_players["turnPlayersToSpectators"] = True
check_win = grp("Check game over", checkwin=True, actions=[act("emptyAction")])

game_loop = [tutorial, setup, assign_mult, build_widget, render_words, redraw_done,
             turn_start, force_play, action_vote, act_draw, act_swap, act_play, mark_dp, turn_end,
             change_players, check_win]

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
    "gameOverCondition": getcache("gameOver"),
    "winners": S("getPlayerNamesByIds", pm("ids", S("getPlayersWithMaxScore"))),
}

# ══════════════════════════════════════════════════════════════════════════════
# player → spectator transition (applied at the "Change players" group between turns). Spectators
# can NOT become players (allowSpectatorBecomePlayer=False), so there is no reverse section.
# On leaving: discard the leaver's whole hand into the discard pile, drop their entry from the
# per-player wordTextsList (so remaining rows stay aligned), refresh players/numPlayers, redraw.
# `oldPlayer` is the engine-provided free var for the departing player.
# ══════════════════════════════════════════════════════════════════════════════
turnPlayerToSpectatorActions = [
    act("recallCards", {"cached": {"targets": "oldPlayer"}, "preset": {"deck": "discard"}}),
    act("emptyAction", save=[svc("oldIdx", S("indexOf", pc("list", "players"), pc("element", "oldPlayer")))]),
    # drop the leaver's slot from BOTH per-player lists using the OLD numPlayers (before recount)
    act("emptyAction", save=[
        svc("wordTextsList", S("concat",
            pm("list1", S("sublist", pc("list", "wordTextsList"), pp("start", 0), pc("end", "oldIdx"))),
            pm("list2", S("sublist", pc("list", "wordTextsList"),
                pm("start", S("inc", pc("arg", "oldIdx"))), pc("end", "numPlayers"))))),
        svc("wordScoresList", S("concat",
            pm("list1", S("sublist", pc("list", "wordScoresList"), pp("start", 0), pc("end", "oldIdx"))),
            pm("list2", S("sublist", pc("list", "wordScoresList"),
                pm("start", S("inc", pc("arg", "oldIdx"))), pc("end", "numPlayers"))))),
        svc("mult2List", S("concat",
            pm("list1", S("sublist", pc("list", "mult2List"), pp("start", 0), pc("end", "oldIdx"))),
            pm("list2", S("sublist", pc("list", "mult2List"),
                pm("start", S("inc", pc("arg", "oldIdx"))), pc("end", "numPlayers"))))),
        svc("mult3List", S("concat",
            pm("list1", S("sublist", pc("list", "mult3List"), pp("start", 0), pc("end", "oldIdx"))),
            pm("list2", S("sublist", pc("list", "mult3List"),
                pm("start", S("inc", pc("arg", "oldIdx"))), pc("end", "numPlayers"))))),
    ]),
    act("emptyAction", save=[
        svc("players", S("allPlayers")),
        svc("numPlayers", S("listLength", pm("list", S("allPlayers")))),
        svc("redraw", True),
    ]),
    act("changeLayout", {"preset": {"type": "HIGHLIGHT", "direction": "VERTICAL", "percent": 45}}),
]

raw = {
    "gameInitOptions": gio, "visualSettings": visualSettings,
    "beforeLoopActions": beforeLoopActions, "gameLoop": game_loop,
    "turnPlayerToSpectatorActions": turnPlayerToSpectatorActions,
    "playersWinCondition": playersWinCondition, "postGameActions": postGameActions,
}

# ══════════════════════════════════════════════════════════════════════════════
# string-hoist + color-strip + key-order pipeline (verbatim from build_paperback.py)
# ══════════════════════════════════════════════════════════════════════════════
SVC_NAMES = set()
def _collect_svc(node):
    if isinstance(node, dict):
        for s in node.get("saveValueInCache", []) or []:
            if isinstance(s, dict) and "name" in s: SVC_NAMES.add(s["name"])
        for v in node.values(): _collect_svc(v)
    elif isinstance(node, list):
        for v in node: _collect_svc(v)
for _sect in ["beforeLoopActions", "gameLoop", "postGameActions", "turnPlayerToSpectatorActions"]:
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
def _is_identifier_template(f):
    return (" " not in f) and bool(re.fullmatch(r"[A-Za-z0-9_]*", re.sub(r"\(\$\d+\)", "", f)))
def hoist_action(a):
    pl = a.get("payload")
    if not isinstance(pl, dict): return
    pre = pl.get("preset", {}); cached = pl.setdefault("cached", {})
    for f in COPY_FIELDS:
        if f in pre and isinstance(pre[f], str): cached[f] = hoist(pre.pop(f))
    if pre.get("image") in IMG_ALIAS_KEY:
        alias = pre.pop("image"); cached["image"] = hoist(alias, IMG_ALIAS_KEY[alias])
    if isinstance(pre.get("poll.targets"), list):
        cached["poll.targets"] = hoist(pre.pop("poll.targets"), "everybodyNobodyTargets")
    if isinstance(pre.get("pollVoteTargetsOptions"), dict):
        cached["pollVoteTargetsOptions"] = hoist(pre.pop("pollVoteTargetsOptions"), "everybodyNobodyOptions")
    if isinstance(pre.get("targets"), list):
        cached["targets"] = hoist(pre.pop("targets"), "lengthTargets")
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
for _sect in ["beforeLoopActions", "gameLoop", "postGameActions", "turnPlayerToSpectatorActions"]:
    walk_hoist(raw[_sect])
def fix_vote_literal(node):
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
for _sect in ["beforeLoopActions", "gameLoop", "postGameActions", "turnPlayerToSpectatorActions"]:
    strip_colors(raw[_sect])
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
    raw[sect] = norm(raw[sect])

os.makedirs(os.path.dirname(OUT), exist_ok=True)
json.dump(raw, open(OUT, "w"), indent=1)
print("wrote", OUT, "| gameLoop items:", len(game_loop), "| strings:", len(STR))
