#!/usr/bin/env python3
"""
build_pageant.py — authors game_jsons/pageant.json (Ludio retheme of the card game Parade).

From-scratch tableau/collection engine. Scaffolding idioms: Piranha (turn/deal/draw/next +
min-score win), Carte Royal Mafia (videobox summary card), Pecking Order (slot moving).
Tutorial createMixVote + postGame from emeralds (postGame adapted max->min score).

RE-RUN to rebuild game_jsons/pageant.json (do NOT hand-edit the json).
Inputs: /tmp/piranha.json, scripts/pageant/tutorial_mixvote.json, scripts/pageant/postgame.json.
Design + turn algorithm: memory ludio-pageant.md.

DSL rule: selector PARAMS are (type,value) tuples via c()/p()/cm(); everything else
(save-values, skipConditions, nested selector nodes, computed-field values) is a BARE
selector dict or a literal.
"""
import json, copy, os

REPO = "/Users/ankitbuddhiraju/Documents/claude/Code"
SDIR = os.path.join(REPO, "scripts", "pageant")
COLORS = ["crimson", "amber", "emerald", "sapphire", "violet", "rose"]
MAXP = 6
# Central widget = 3 rows of pageant-line slots (5 wide for ≤5 players, 6 wide for 6) + 1 row
# of per-player collection decks. Create the max (18) pageant slots; use 15 or 18 per count.
MAXPAR = 18
PARADE_ALL = [f"parade_{i}" for i in range(MAXPAR)]
COLL_ALL = [f"collection_{i}" for i in range(MAXP)]   # per-player collected-card decks
HAND_ALL = [f"hand_{i}" for i in range(MAXP)]         # endgame reveal: each player's kept hand
COLS_BY_COUNT = {str(n): (6 if n == 6 else 5) for n in range(2, MAXP + 1)}          # 5 or 6 cols
PARADE_COUNT_BY_COUNT = {str(n): (18 if n == 6 else 15) for n in range(2, MAXP + 1)}  # 3 rows
HL_PLAYED = "#B9F6CA"       # light green — the card just played
HL_SAFE = "#E57373"         # red — the card's "safe window" (last N cards, guaranteed to stay)
HL_COLLECT = "#FFF176"      # yellow — cards about to be swept into a troupe
PAUSE = 2                   # seconds between animation beats
CLOUD = "https://res.cloudinary.com/liars-club/image/upload"
# TESTING=True strips playCards `duration` so human turns are UNTIMED (postHandler won't
# auto-fire), giving time to act + read the console. Set False before final deploy.
TESTING = False

# --- param tuples -----------------------------------------------------------
def c(v):  return ("cached", v)
def p(v):  return ("preset", v)
def cm(v): return ("computed", v)     # v is a BARE selector dict
def prm(name, tv):
    t, v = tv
    return {"name": name, "type": t, "value": v}

# --- selector builders (return BARE dicts) ----------------------------------
def S(selector, **kw):
    node = {"selector": selector}
    if kw:
        node["params"] = [prm(k, v) for k, v in kw.items()]
    return node
def fmt(template, *args):
    kw = {"format": p(template)}
    for i, a in enumerate(args, 1):
        kw["arg%d" % i] = a
    return S("formatString", **kw)
def clist(*tvs):   return S("createList", **{f"arg{i+1}": tv for i, tv in enumerate(tvs)})
def cget(name):    return S("getCachedValue", name=p(name))
def dcards(dtv):   return S("getDeckCards", deck=dtv)
def llen(ltv):     return S("listLength", list=ltv)
def sel(ltv, itv): return S("selectElement", list=ltv, index=itv)
# getCardField: ONLY valid inside a playCards action, on the card ID in the result object.
# getObjectField: for card OBJECTS returned by getDeckCards / fetchHandField (anywhere else).
def cardf(otv, f): return S("getCardField", cardId=otv, field=p(f))
def objf(otv, f):  return S("getObjectField", obj=otv, field=p(f))
def add(a, b):     return S("add", arg1=a, arg2=b)
def inc(a):        return S("inc", arg=a)
def dec(a):        return S("dec", arg=a)
def sub(a, b):     return S("subtract", arg1=a, arg2=b)
def eq(a, b):      return S("equals", arg1=a, arg2=b)
def neq(a, b):     return S("notEqual", arg1=a, arg2=b)
def gt(a, b):      return S("greaterThan", arg1=a, arg2=b)
def gte(a, b):     return S("greaterThanOrEqual", arg1=a, arg2=b)
def lt(a, b):      return S("lessThan", arg1=a, arg2=b)
def lte(a, b):     return S("lessThanOrEqual", arg1=a, arg2=b)
def AND(a, b):     return S("logicalAND", arg1=a, arg2=b)
def OR(a, b):      return S("logicalOR", arg1=a, arg2=b)
def NOT(a):        return S("logicalNOT", arg=a)
def IF(cond, then, els): return S("ifElse", condition=cond, thenValue=then, elseValue=els)
def AND_ALL(nodes):
    n = nodes[-1]
    for x in reversed(nodes[:-1]):
        n = AND(cm(x), cm(n))
    return n

def pslot(itv):    return cm(fmt("parade_($1)", itv))          # deck-name selector
def slot_obj(itv): return sel(cm(dcards(pslot(itv))), p(0))    # the one card object in slot i
def slot_len(itv): return llen(cm(dcards(pslot(itv))))
def list_set(name, itv, newval_tv, iP1tv):
    """rebuild parallel list `name` (cached) with element `itv` replaced by newval_tv (a param tuple)."""
    return S("concat",
             list1=cm(S("sublist", list=c(name), start=p(0), end=itv)),
             list2=cm(clist(newval_tv)),
             list3=cm(S("sublist", list=c(name), start=iP1tv, end=c("numPlayers"))))

# --- action / step ----------------------------------------------------------
def save(name, value):
    # Guard the #1 slip: a param tuple c()/p()/cm() passed as a save-VALUE serializes to a
    # literal list like ["cached","zeroPlayers"] (silently wrong, no syntax error). Convert:
    # copying a cached var -> getCachedValue; computed -> the node; preset -> the literal.
    if isinstance(value, tuple) and len(value) == 2 and value[0] in ("cached", "preset", "computed"):
        t, v = value
        value = cget(v) if t == "cached" else v
    return {"name": name, "value": value}
def A(key, preset=None, cached=None, computed=None, save_=None, postHandler=None, skip=None):
    # canonical key order: key, skipCondition, payload, postHandler, saveValueInCache
    act = {"key": key}
    if skip is not None: act["skipCondition"] = skip        # bare selector dict
    payload = {}
    if preset is not None:  payload["preset"] = preset
    if cached is not None:  payload["cached"] = cached
    if computed is not None: payload["computed"] = computed
    if payload: act["payload"] = payload
    if postHandler: act["postHandler"] = postHandler
    if save_ is not None: act["saveValueInCache"] = save_
    return act
def STEP(name, actions, repeat=None, parallel=None, skip=None, checkWin=False):
    s = {"name": name}
    # step-level skipCondition = LIST of selector dicts (skip if ANY is true). Accept one node
    # or an already-built list.
    if skip is not None: s["skipCondition"] = skip if isinstance(skip, list) else [skip]
    if repeat is not None: s["repeat"] = repeat
    if parallel is not None: s["parallel"] = parallel
    if checkWin: s["checkWinCondition"] = True
    s["actions"] = actions
    return s

# ---------------------------------------------------------------------------
# gameInitOptions
# ---------------------------------------------------------------------------
piranha = json.load(open("/tmp/piranha.json"))["raw"]
gio = copy.deepcopy(piranha["gameInitOptions"])
gio["minPlayers"] = 2
gio["maxPlayers"] = 6
gio["preferredPlayersQnt"] = [4, 6]
gio["time"] = 20
gio["teams"] = {"all": {"id": "all", "name": "Contestants",
                        "description": "Producers of the grandest pageant in town.",
                        "color": "#b0356a", "roles": ["player"]}}
gio["roles"] = [{"roleInfo": {"id": "player", "name": "Producer",
                              "description": "Stage a dazzling pageant — but dodge the low scores. \U0001F3AD",
                              "avatar": f"{CLOUD}/card_player_ed7jck.webp",
                              "team": "all", "prefix": "a "},
                 "isDefaultRole": True, "isRequired": False}]
def _card(n): return {"url": f"{CLOUD}/images/pageant/{n}.png"}
gio["images"] = {
    "transparent": {"url": f"{CLOUD}/transparent_sbx4wv.png"},
    "pageant_cardback": _card("crimson_7"),
    "banner": _card("banner"), "wallpaper": {"url": f"{CLOUD}/images/pageant/wallpaper.jpg"},
    "winner": {"url": f"{CLOUD}/winner_h5eyfr.gif"},
    # tutorial: reuse existing CARD images for most slides; one generated composite for the
    # collection rule.
    "tut_welcome": _card("rose_8"), "tut_turn": _card("sapphire_9"),
    "tut_collect": _card("tut_collect"), "tut_troupe": _card("crimson_7"),
    "tut_score": _card("emerald_1"), "tut_finale": _card("amber_10"),
}
gio["animations"] = {}
gio.pop("cheatsheet", None)

# ---- string hoisting: all user-facing copy lives in gameInitOptions.strings.Default and is
#      referenced via cached keys (loaded to cache at game start). ----
STRINGS = {}
def hs(key, val):        # hoist a plain string; return the cache KEY (for cached sections)
    STRINGS[key] = val
    return key
def hfmt(key, template, *args):   # hoisted formatString (format sourced from strings)
    STRINGS[key] = template
    kw = {"format": c(key)}
    for i, a in enumerate(args, 1):
        kw["arg%d" % i] = a
    return S("formatString", **kw)
gio["strings"] = {"Default": STRINGS}
# colored hearts (render in the createCard font, unlike 🟠🟢🟣); 3 rows of 2.
STRINGS["summaryFormat"] = "❤️($1) \U0001F9E1($2)\n\U0001F49A($3) \U0001F499($4)\n\U0001F49C($5) \U0001F497($6)"
def summary_fmt(*args): return S("formatString", format=c("summaryFormat"),
                                 **{f"arg{i+1}": a for i, a in enumerate(args)})
WOOD_BG = f"{CLOUD}/wood_qbegm0.jpg"   # same felt/wood the central widget uses (Emeralds' bg)
DARK_BG, DARK_BORDER = "#2a1330", "#b0356a"   # consistent dark scheme (white text) for all popups
visualSettings = {"cardHandBackgroundImage": WOOD_BG, "increaseHandHeight": True,
                  "isCardAnimationsOff": True,   # moveCards is instant (our highlights do the pacing)
                  "backgroundColor": DARK_BG, "textColor": "white", "borderColor": DARK_BORDER}

# ---------------------------------------------------------------------------
# beforeLoopActions
# ---------------------------------------------------------------------------
mixvote = json.load(open(os.path.join(SDIR, "tutorial_mixvote.json")))
mixvote["payload"]["preset"]["backgroundColor"] = DARK_BG   # dark scheme so white text is legible
mixvote["payload"]["preset"]["borderColor"] = DARK_BORDER
# hoist the tutorial-vote display copy (title + question format) into strings.Default
_q = mixvote["payload"]["computed"]["question"]["params"][0]
_q["type"], _q["value"] = "cached", hs("tutorialQuestion", _q["value"])
mixvote["payload"]["cached"]["title"] = hs("tutorialTitle", mixvote["payload"]["preset"].pop("title"))
before = []
before.append(A("emptyAction", save_=[
    save("players", S("allPlayers")),
    save("numPlayers", llen(cm(S("allPlayers")))),
]))
before.append(A("emptyAction", save_=[
    save("host", IF(cm(S("contains", list=c("players"), element=cm(S("getHostPlayerId")))),
                    cm(clist(cm(S("getHostPlayerId")))),
                    cm(clist(c("players.0")))))
]))
# welcome banner notification (standard first-thing, shown to everyone)
before.append(A("createNotification",
    preset={"image": "banner", "duration": 8, "backgroundColor": DARK_BG, "borderColor": DARK_BORDER},
    cached={"to": "players",
            "header": hs("welcomeHeader", "Welcome to Pageant!"),
            "text": hs("welcomeText", "Send contestants onto the stage — but sweep up as few as you can. The lowest score wins!")}))
before.append(mixvote)
before.append(A("createDeck", preset={"name": "pageant_cards", "customName": "draw_pile", "set": "full"}))
before.append(A("shuffleDeck", preset={"deck": "draw_pile"}))
for i in range(MAXPAR):
    before.append(A("createCustomDeck",
                    preset={"public": True, "enlargeOnHover": True, "name": f"parade_{i}"}))
before.append(A("createCustomDeck", preset={"public": True, "name": "discard"}))
before.append(A("createVideoboxDecks", preset={"cardback": "pageant_cardback"}, cached={"players": "players"}))
before.append(A("emptyAction", save_=[
    save("paradeLen", 0), save("finalLap", False), save("gameOver", False),
    save("finalTurnsLeft", 0), save("halfWarned", False), save("lowWarned", False),
    save("currentPlayer", cget("players.0")),
    save("zeroPlayers", S("sublist", list=p([0] * 12), start=p(0), end=c("numPlayers"))),
    save("colsByCount", COLS_BY_COUNT),
    save("paradeCountByCount", PARADE_COUNT_BY_COUNT),
    save("maxSlots", S("getCachedObjectValue", objectName=p("paradeCountByCount"), value=c("numPlayers"))),
]))
for col in COLORS:
    before.append(A("emptyAction", save_=[save(f"cnt_{col}", c("zeroPlayers")),
                                          save(f"sum_{col}", c("zeroPlayers"))]))

# ---------------------------------------------------------------------------
# gameLoop
# ---------------------------------------------------------------------------
gl = []
first_only = gt(c("gameLoopIndex"), p(0))
skip_turn  = AND(c("finalLap"), cm(lte(c("finalTurnsLeft"), p(0))))
final_now  = NOT(cm(AND(c("finalLap"), cm(lte(c("finalTurnsLeft"), p(0))))))

# updateScore helper: set the SAME single score for the players in `who` (a list selector).
# (score is ONE number applied to all players in `list` — NOT a parallel list.)
def set_score(who_node, score_tv):
    return A("updateScore", computed={"scores": clist(cm(S("createDict",
        keys=p(["list", "score"]), values=cm(clist(cm(who_node), score_tv)))))})

# ---- create per-player collection decks (inspectable, labeled) — first pass only ----
gl.append(STEP("Collection Decks", [
    A("createCustomDeck", preset={"public": True, "inspectDeck": True, "enlargeOnHover": True},
      computed={"name": fmt("collection_($1)", c("repeatIndex")),
                "label": S("getPlayerNameById", id=cm(sel(c("players"), c("repeatIndex"))))}),
    # per-player "hand" deck, revealed only in the endgame walkthrough
    A("createCustomDeck", preset={"public": True, "inspectDeck": True, "enlargeOnHover": True},
      computed={"name": fmt("hand_($1)", c("repeatIndex")),
                "label": hfmt("handLabel", "($1)'s Hand", cm(S("getPlayerNameById", id=cm(sel(c("players"), c("repeatIndex"))))))}),
], repeat={"qnt": cget("numPlayers")}, skip=first_only))

# ---- one-time setup ----
setup = [
    A("changeBackground", preset={"image": "wallpaper"}),
    A("changeLayout", preset={"type": "HIGHLIGHT", "direction": "VERTICAL", "percent": 50}),
    A("setImagesRow", preset={"maxHeight": 230, "images": ["transparent"]}),
    A("createGenericCardWidget",
      preset={"ratio": "0.77", "cardback": "pageant_cardback", "backgroundImage": WOOD_BG},
      computed={"decks": S("concat",
                    list1=cm(S("sublist", list=p(PARADE_ALL), start=p(0),
                              end=cm(S("getCachedObjectValue", objectName=p("paradeCountByCount"),
                                       value=c("numPlayers"))))),
                    list2=cm(S("sublist", list=p(COLL_ALL), start=p(0), end=c("numPlayers")))),
                # dims = [rows=4, cols] — 3 pageant-line rows + 1 collection row
                "dimensions": clist(p(4), cm(S("getCachedObjectValue", objectName=p("colsByCount"),
                                               value=c("numPlayers"))))}),
    A("dealDeck", preset={"deck": "draw_pile", "qnt": 5, "sortBy": "weight", "order": "asc"},
      cached={"targets": "players"}),
    A("showAllPlayersHands"),
    A("showScore", cached={"from": "players", "to": "players"}),  # scores start at 0 by default
]
for i in range(6):
    # move the TOP card of draw_pile into slot i (qnt:1, no cardNames — deck cards are UUIDs)
    setup.append(A("moveCards", preset={"type": "deck", "from": "draw_pile", "to": f"parade_{i}", "qnt": 1}))
setup.append(A("emptyAction", save_=[
    save("paradeLen", 6),
    save("drawStart", llen(cm(dcards(p("draw_pile"))))),   # draw pile size after the deal
]))
gl.append(STEP("Setup", setup, skip=first_only))

# ---- tutorial (shown once, only to players who opted in via the mixVote) ----
# (image, header, text). Images are existing CARD art except the collection composite (tut_collect).
TUT = [
    ("tut_welcome", "Welcome to Pageant",
     "You're producing a beauty pageant of numbered contestants in 6 sash colors. Sweep up as FEW as possible — the lowest score wins!"),
    ("tut_turn", "Taking Your Turn",
     "On your turn, play one contestant to the END of the stage lineup, then draw back up to 5 cards."),
    ("tut_collect", "Who Gets Collected",
     "Your card's number N shields the last N contestants. Anyone earlier in the line who shares your color OR has a number ≤ N joins your troupe — and that's bad!"),
    ("tut_troupe", "Your Troupe",
     "Collected contestants pile into your troupe deck, which everyone can inspect. You can also see a summary of which colors you've collected in your video box."),
    ("tut_score", "Scoring",
     "Add up the numbers in your troupe — the LOWEST total wins. But for each color, whoever holds the most flips those cards to just 1 point each."),
    ("tut_finale", "The Finale",
     "The show ends when someone collects all 6 colors, or the draw pile empties. Everyone takes one last turn, discards 2 cards, then scores. Good luck!"),
]
tut_actions = [
    A("createNotification",
      preset={"image": img, "duration": 15, "backgroundColor": DARK_BG, "borderColor": DARK_BORDER},
      cached={"to": "learners",
              "header": hs(f"tutHeader{i+1}", f"({i+1}/6) {hdr}"),
              "text": hs(f"tutText{i+1}", txt)})
    for i, (img, hdr, txt) in enumerate(TUT)
]
tut_actions.append(A("emptyAction", save_=[save("tutorial", False)]))   # required: last group flips it off
gl.append(STEP("Tutorial", tut_actions,
               skip=[gt(c("gameLoopIndex"), p(0)), NOT(c("tutorial"))]))

# ---- turn init ----
gl.append(STEP("Turn Init", [
    A("emptyAction", save_=[
        save("ci", S("indexOf", list=c("players"), element=c("currentPlayer"))),
        save("ciP1", inc(cm(S("indexOf", list=c("players"), element=c("currentPlayer"))))),
    ]),
    A("highlightPlayers", preset={"color": "#f2c94c"},
      computed={"listOfPlayers": clist(c("currentPlayer"))},
      save_=[save("highlightId", cget("lastActionId"))]),
], skip=skip_turn))

# ---- overflow guard: if the stage is FULL, discard the oldest contestant and slide everyone
#      back one slot so the played card always has a free slot (stage never breaks). ----
skip_overflow = OR(cm(skip_turn), cm(lt(c("paradeLen"), c("maxSlots"))))
gl.append(STEP("Overflow Discard",
    [A("moveCards", preset={"type": "deck", "from": "parade_0", "to": "discard"})],
    skip=skip_overflow))
gl.append(STEP("Overflow Shift", [
    A("moveCards", preset={"type": "deck"},
      computed={"from": fmt("parade_($1)", cm(inc(c("repeatIndex")))),
                "to": fmt("parade_($1)", c("repeatIndex"))}),
], repeat={"qnt": dec(c("maxSlots"))}, skip=skip_overflow))
gl.append(STEP("Overflow Len",
    [A("emptyAction", save_=[save("paradeLen", dec(c("maxSlots")))])],
    skip=skip_overflow))

# ---- play a card into parade_(paradeLen) ----
gl.append(STEP("Play Card", [
    A("playCards", postHandler="playOneRandomCard",
      preset={"minCards": 1, "maxCards": 1, "oneClick": True, "playable": "availableCards",
              "sounds.list": ["soundboard.reminder"], "sounds.waitForSoundEnd": False},
      cached={"actor": "currentPlayer"},
      computed={k: v for k, v in {
          "playList.1": clist(c("currentPlayer")),   # play the reminder to the active player
          "target": fmt("parade_($1)", c("paradeLen")),
          "duration": None if TESTING else IF(
              cm(S("contains", list=cm(S("allConnectedUsers")), element=c("currentPlayer"))), p(45), p(1)),
          "notification": hfmt("playPrompt", "($1), send a contestant onto the stage!",
                               cm(S("getPlayerNameById", id=c("currentPlayer")))),
      }.items() if v is not None},
      save_=[
          save("preLen", cget("paradeLen")),
          save("playedCard", cget("lastActionResult.cards.0")),
          save("playedColor", cardf(c("lastActionResult.cards.0"), "color")),
          save("N", cardf(c("lastActionResult.cards.0"), "value")),
      ]),
    A("emptyAction", save_=[
        save("paradeLen", inc(c("paradeLen"))),
    ]),
], skip=skip_turn))

# ---- removal pass ----
def tally_updates(collect_tv, color_tv, val_tv, idx_tv, iP1tv):
    ups = []
    for col in COLORS:
        match = AND(collect_tv, cm(eq(color_tv, p(col))))
        ups.append(save(f"cnt_{col}", list_set(f"cnt_{col}", idx_tv,
                        cm(add(cm(sel(c(f"cnt_{col}"), idx_tv)), cm(IF(cm(match), p(1), p(0))))), iP1tv)))
    for col in COLORS:
        match = AND(collect_tv, cm(eq(color_tv, p(col))))
        ups.append(save(f"sum_{col}", list_set(f"sum_{col}", idx_tv,
                        cm(add(cm(sel(c(f"sum_{col}"), idx_tv)), cm(IF(cm(match), val_tv, p(0))))), iP1tv)))
    return ups

# Removal is animated so players can follow it: (1) MARK each slot as collected/unaffected,
# building two deck-name lists; (2) highlight the unaffected decks light-red + pause; (3) loop
# the collected decks — highlight each yellow, pause, then sweep it into the player's troupe;
# (4) clear highlights. Then compaction repacks the parade.
gl.append(STEP("Removal Init",
    [A("emptyAction", save_=[save("collectedDecks", []), save("safeDecks", [])])],
    skip=skip_turn))

gl.append(STEP("Removal Mark", [
    A("emptyAction", save_=[
        save("slotName", fmt("parade_($1)", c("repeatIndex"))),
        save("isPlayed", eq(c("repeatIndex"), c("preLen"))),   # the card just played (tail slot)
        save("cardI", slot_obj(c("repeatIndex"))),
        save("colorI", objf(c("cardI"), "color")),
        save("valI", objf(c("cardI"), "value")),
        save("isCand", lt(c("repeatIndex"), cm(sub(c("preLen"), c("N"))))),
        save("collectI", AND(c("isCand"),
                             cm(OR(cm(eq(c("colorI"), c("playedColor"))),
                                   cm(lte(c("valI"), c("N"))))))),
    ]),
    A("emptyAction", save_=[
        save("collectedDecks", IF(c("collectI"),
                cm(S("concat", list1=c("collectedDecks"), list2=cm(clist(c("slotName"))))),
                c("collectedDecks"))),
        # safe window = the last N cards before the played card (NOT a candidate, NOT the
        # played card) — these are GUARANTEED to stay, so they get the red highlight.
        save("safeDecks", IF(cm(AND(cm(NOT(c("isCand"))), cm(NOT(c("isPlayed"))))),
                cm(S("concat", list1=c("safeDecks"), list2=cm(clist(c("slotName"))))),
                c("safeDecks"))),
    ]),
], repeat={"qnt": inc(c("preLen"))}, skip=skip_turn))

# highlight the just-played card green, pause 1s; then its safe window red, pause; then collect
gl.append(STEP("Highlight Played", [
    A("highlightDecks", preset={"color": HL_PLAYED},
      computed={"decks": clist(cm(fmt("parade_($1)", c("preLen"))))}),
    A("emptyAction", preset={"delay": 1}),
], skip=skip_turn))

gl.append(STEP("Highlight Safe Window", [
    A("highlightDecks", preset={"color": HL_SAFE}, cached={"decks": "safeDecks"}),
    A("emptyAction", preset={"delay": PAUSE}),
], skip=skip_turn))

gl.append(STEP("Collect Loop", [
    A("emptyAction", save_=[save("thisDeck", sel(c("collectedDecks"), c("repeatIndex")))]),
    A("highlightDecks", preset={"color": HL_COLLECT}, computed={"decks": clist(c("thisDeck"))}),
    # bite SFX (piranha's) the moment the deck turns yellow
    A("emptyAction", preset={"sounds.list": ["soundboard.bite"], "sounds.waitForSoundEnd": False},
      cached={"playList.1": "players"}),
    A("emptyAction", preset={"delay": PAUSE}),
    A("emptyAction", save_=[
        save("cCard", cm(sel(cm(dcards(c("thisDeck"))), p(0)))),
    ]),
    A("emptyAction", save_=[
        save("cColor", objf(c("cCard"), "color")),
        save("cVal", objf(c("cCard"), "value")),
    ]),
    A("emptyAction", save_=tally_updates(p(True), c("cColor"), c("cVal"), c("ci"), c("ciP1"))),
    A("moveCards", preset={"type": "deck"},
      cached={"from": "thisDeck"}, computed={"to": fmt("collection_($1)", c("ci"))}),
    A("emptyAction", preset={"delay": 1}),   # 1s beat after the card lands in the troupe
], repeat={"qnt": llen(c("collectedDecks"))}, skip=skip_turn))

gl.append(STEP("Clear Highlights", [A("removeAllHighlightDecks")], skip=skip_turn))

# ---- compaction ----
gl.append(STEP("Compact Init", [A("emptyAction", save_=[save("w", 0)])], skip=skip_turn))
gl.append(STEP("Compact", [
    A("emptyAction", save_=[
        save("filledI", gt(cm(slot_len(c("repeatIndex"))), p(0))),
        save("needMove", AND(cm(gt(cm(slot_len(c("repeatIndex"))), p(0))),
                             cm(neq(c("repeatIndex"), c("w"))))),
    ]),
    A("moveCards", preset={"type": "deck"},
      computed={"from": fmt("parade_($1)", c("repeatIndex")), "to": fmt("parade_($1)", c("w"))},
      skip=NOT(c("needMove"))),
    A("emptyAction", save_=[save("w", IF(c("filledI"), cm(inc(c("w"))), c("w")))]),
], repeat={"qnt": inc(c("preLen"))}, skip=skip_turn))
gl.append(STEP("Set Parade Len", [A("emptyAction", save_=[save("paradeLen", cget("w"))])], skip=skip_turn))

# ---- summary card + running score (sum of collected card ranks; majority-flip applied only
#      at the very end, so this is a live "raw total" the player understands) ----
_run_total = sel(c(f"sum_{COLORS[0]}"), c("ci"))
for _col in COLORS[1:]:
    _run_total = add(cm(_run_total), cm(sel(c(f"sum_{_col}"), c("ci"))))
gl.append(STEP("Summary", [
    A("emptyAction", save_=[
        save("summaryText", summary_fmt(*[cm(sel(c(f"cnt_{col}"), c("ci"))) for col in COLORS])),
        save("myVideobox", fmt("videobox_($1)", c("currentPlayer"))),
        save("runTotal", _run_total),
    ]),
    A("moveCards", preset={"type": "deck", "to": "discard"}, cached={"from": "myVideobox"}),
    A("createCard", preset={"fontHeightPercentage": 13, "ratio": 0.77, "textColor": "white",
                            "background": "#3a1c44"},
      cached={"deck": "myVideobox"}, computed={"cardText": cget("summaryText")}),
    set_score(S("createList", arg1=c("currentPlayer")), c("runTotal")),
    A("showScore", cached={"from": "players", "to": "players"}),
], skip=skip_turn))

hs("endgameText", "Everyone gets one last turn on stage — then each producer discards 2 contestants.")

# ---- endgame check A: current player holds all 6 colors ----
gl.append(STEP("Endgame Check A", [
    A("emptyAction", save_=[
        save("allSix", AND_ALL([gte(cm(sel(c(f"cnt_{col}"), c("ci"))), p(1)) for col in COLORS])),
        save("triggerA", AND(cm(NOT(c("finalLap"))), c("allSix"))),
    ]),
    A("createNotification", skip=NOT(c("triggerA")),
      preset={"backgroundColor": DARK_BG, "borderColor": DARK_BORDER},
      cached={"to": "players", "text": "endgameText"},
      computed={"header": hfmt("collectedAllHeader", "($1) has collected every sash!",
                               cm(S("getPlayerNameById", id=c("currentPlayer"))))}),
    A("emptyAction", save_=[
        save("finalTurnsLeft", IF(c("triggerA"), c("numPlayers"), c("finalTurnsLeft"))),
        save("finalLap", OR(c("finalLap"), c("allSix"))),
    ]),
], skip=skip_turn))

# ---- draw one (unless final lap) — re-sorts the hand by weight ----
gl.append(STEP("Draw", [
    A("dealDeck", preset={"deck": "draw_pile", "qnt": 1, "sortBy": "weight", "order": "asc"},
      computed={"targets": clist(c("currentPlayer"))}),
], skip=cget("finalLap")))

# ---- draw-pile "running low" notifications (each fires once) ----
gl.append(STEP("Draw Warnings", [
    A("emptyAction", save_=[
        save("drawSize", llen(cm(dcards(p("draw_pile"))))),
        save("halfMark", S("integerDivide", arg1=c("drawStart"), arg2=p(2))),
        save("halfFire", AND(cm(NOT(c("halfWarned"))), cm(lte(c("drawSize"), c("halfMark"))))),
        save("lowFire", AND(cm(NOT(c("lowWarned"))), cm(lte(c("drawSize"), p(7))))),
    ]),
    A("createNotification", skip=NOT(c("halfFire")),
      preset={"backgroundColor": DARK_BG, "borderColor": DARK_BORDER},
      cached={"to": "players",
              "header": hs("drawHalfHeader", "Half the deck is gone!"),
              "text": hs("drawHalfText", "The draw pile is running low — the show won't last forever.")}),
    A("createNotification", skip=NOT(c("lowFire")),
      preset={"backgroundColor": DARK_BG, "borderColor": DARK_BORDER},
      cached={"to": "players",
              "header": hs("drawLowHeader", "Only 7 contestants left backstage!"),
              "text": hs("drawLowText", "When the draw pile empties, the final round begins.")}),
    A("emptyAction", save_=[
        save("halfWarned", OR(c("halfWarned"), cm(lte(c("drawSize"), c("halfMark"))))),
        save("lowWarned", OR(c("lowWarned"), cm(lte(c("drawSize"), p(7))))),
    ]),
], skip=cget("finalLap")))

# ---- endgame check B: draw pile empty ----
gl.append(STEP("Endgame Check B", [
    A("emptyAction", save_=[
        save("drawEmpty", eq(cm(llen(cm(dcards(p("draw_pile"))))), p(0))),
        save("triggerB", AND(cm(NOT(c("finalLap"))), cm(eq(cm(llen(cm(dcards(p("draw_pile"))))), p(0))))),
    ]),
    A("createNotification", skip=NOT(c("triggerB")),
      preset={"backgroundColor": DARK_BG, "borderColor": DARK_BORDER},
      cached={"to": "players", "text": "endgameText",
              "header": hs("drawOutHeader", "The draw pile has run out!")}),
    A("emptyAction", save_=[
        save("finalTurnsLeft", IF(c("triggerB"), c("numPlayers"), c("finalTurnsLeft"))),
        save("finalLap", OR(c("finalLap"), c("drawEmpty"))),
    ]),
], skip=cget("finalLap")))

# ---- next player + countdown ----
gl.append(STEP("Next Player", [
    A("removeHighlight", cached={"id": "highlightId"}),
    A("emptyAction", save_=[
        save("finalTurnsLeft", IF(c("finalLap"), cm(dec(c("finalTurnsLeft"))), c("finalTurnsLeft"))),
        save("currentPlayer", S("nextPlayer", playersList=c("players"), playerId=c("currentPlayer"))),
    ]),
], skip=skip_turn))

# ---- FINAL PHASE ----
gl.append(STEP("Final Discard", [
    A("playCards", postHandler="playOneRandomCard",
      preset={"minCards": 2, "maxCards": 2, "playable": "availableCards", "target": "discard",
              **({} if TESTING else {"duration": 25})},
      computed={"actor": sel(c("players"), c("spaIndex")),
                "notification": hfmt("finalBow", "Final bow! Discard 2 contestants — the rest join your troupe.")}),
], parallel={"type": "smart", "qnt": cget("numPlayers")}, skip=final_now))

# ---- endgame walkthrough: reveal each kept hand in a 2nd row, fold it into the counts,
#      recompute summaries, then announce the color leaders BEFORE the winner. ----

# (a) move each player's remaining hand into their (labeled) hand_i deck
gl.append(STEP("Reveal Hands", [
    A("recallCards", computed={"targets": clist(cm(sel(c("players"), c("repeatIndex")))),
                               "deck": fmt("hand_($1)", c("repeatIndex"))}),
], repeat={"qnt": cget("numPlayers")}, skip=final_now))

# (b) redraw the central widget: row 1 = troupes, row 2 = each player's revealed hand
gl.append(STEP("Reveal Widget", [
    A("createGenericCardWidget",
      preset={"ratio": "0.77", "cardback": "pageant_cardback", "backgroundImage": WOOD_BG},
      computed={"decks": S("concat",
                    list1=cm(S("sublist", list=p(COLL_ALL), start=p(0), end=c("numPlayers"))),
                    list2=cm(S("sublist", list=p(HAND_ALL), start=p(0), end=c("numPlayers")))),
                "dimensions": clist(p(2), c("numPlayers"))}),
    A("emptyAction", preset={"delay": PAUSE}),
], skip=final_now))

# (c) fold the kept (hand) cards into cnt_/sum_ — read from the hand_i DECK (reliable objects)
keep = [A("emptyAction", save_=[
    save("kpP1", inc(c("repeatIndex"))),
    save("khand", dcards(cm(fmt("hand_($1)", c("repeatIndex"))))),
    save("khandLen", llen(cm(dcards(cm(fmt("hand_($1)", c("repeatIndex"))))))),
])]
for k in range(5):
    # ifElse evaluates BOTH branches, so clamp the index to a valid card + skip empty hands.
    keep.append(A("emptyAction", save_=[
        save("kExists", gt(c("khandLen"), p(k))),
        save("kIdx", IF(c("kExists"), p(k), p(0))),
        save("kCard", sel(c("khand"), c("kIdx"))),
    ]))
    keep.append(A("emptyAction", skip=eq(c("khandLen"), p(0)), save_=[
        save("kColor", objf(c("kCard"), "color")),
        save("kVal", objf(c("kCard"), "value")),
    ]))
    keep.append(A("emptyAction", skip=eq(c("khandLen"), p(0)),
                 save_=tally_updates(c("kExists"), c("kColor"), c("kVal"),
                                     c("repeatIndex"), c("kpP1"))))
gl.append(STEP("Fold In Hands", keep, repeat={"qnt": cget("numPlayers")}, skip=final_now))

# (d) recompute every player's summary card (now incl. hand cards)
gl.append(STEP("Recompute Summaries", [
    A("emptyAction", save_=[
        save("sVbox", fmt("videobox_($1)", cm(sel(c("players"), c("repeatIndex"))))),
        save("sText", summary_fmt(*[cm(sel(c(f"cnt_{col}"), c("repeatIndex"))) for col in COLORS])),
    ]),
    A("moveCards", preset={"type": "deck", "to": "discard"}, cached={"from": "sVbox"}),
    A("createCard", preset={"fontHeightPercentage": 13, "ratio": 0.77, "textColor": "white",
                            "background": "#3a1c44"},
      cached={"deck": "sVbox"}, computed={"cardText": cget("sText")}),
], repeat={"qnt": cget("numPlayers")}, skip=final_now))

# (e) announce who leads each color (that majority flips to 1 pt each), then pause
_hearts = ["❤️", "\U0001F9E1", "\U0001F49A", "\U0001F499", "\U0001F49C", "\U0001F497"]
# one color per <br/> line
_maj_fmt = "<br/>".join("%s %s: ($%d)" % (_hearts[i], col.title(), i + 1) for i, col in enumerate(COLORS))
gl.append(STEP("Announce Leaders", [
    A("emptyAction", save_=[
        save(f"lead_{col}", S("getPlayerNameById", id=cm(sel(c("players"),
              cm(S("indexOf", list=c(f"cnt_{col}"), element=cm(S("maxValue", list=c(f"cnt_{col}")))))))))
        for col in COLORS
    ]),
    A("createNotification",
      preset={"backgroundColor": DARK_BG, "borderColor": DARK_BORDER},
      cached={"to": "players",
              "header": hs("leadersHeader", "Color leaders — the most of each flips to 1 pt each!")},
      computed={"text": hfmt("leadersFmt", _maj_fmt, *[c(f"lead_{col}") for col in COLORS])}),
    A("emptyAction", preset={"delay": PAUSE}),
], skip=final_now))

# ---- final scoring: per player, majority colors flip to count (1/card), else face-value sum;
#      set that player's score directly (one updateScore per player) ----
score = [A("emptyAction", save_=[
    save("is2p", eq(c("numPlayers"), p(2))),
    # other-player index for the 2p majority rule; clamp to 0 for >2 players so the
    # (unused) 2p branch of ifElse never does selectElement(list, -1).
    save("oIdx", IF(c("is2p"), cm(sub(p(1), c("repeatIndex"))), p(0))),
])]
contribs = []
for col in COLORS:
    cntP = cm(sel(c(f"cnt_{col}"), c("repeatIndex")))
    sumP = cm(sel(c(f"sum_{col}"), c("repeatIndex")))
    maxC = cm(S("maxValue", list=c(f"cnt_{col}")))
    maj_multi = cm(AND(cm(eq(cntP, maxC)), cm(gt(maxC, p(0)))))
    maj_2p = cm(gte(cntP, cm(add(cm(sel(c(f"cnt_{col}"), c("oIdx"))), p(2)))))
    isMaj = cm(IF(c("is2p"), maj_2p, maj_multi))
    contribs.append(IF(isMaj, cntP, sumP))
acc = contribs[0]
for x in contribs[1:]:
    acc = add(cm(acc), cm(x))
score.append(A("emptyAction", save_=[save("totalP", acc)]))
score.append(set_score(S("createList", arg1=cm(sel(c("players"), c("repeatIndex")))), c("totalP")))
gl.append(STEP("Score Players", score, repeat={"qnt": cget("numPlayers")}, skip=final_now))

gl.append(STEP("Finalize", [
    A("showScore", cached={"from": "players", "to": "players"}),
    A("emptyAction", save_=[
        save("winner", S("getPlayerNamesByIds", ids=cm(S("getPlayersWithMinScore")))),
        save("gameOver", True),
    ]),
], skip=final_now))

# ---- trailing win-check stage (always runs; ends game once gameOver=true) ----
gl.append(STEP("Win Check", [A("emptyAction")], checkWin=True))

# ---------------------------------------------------------------------------
postgame = json.loads(json.dumps(json.load(open(os.path.join(SDIR, "postgame.json"))))
                      .replace("getPlayersWithMaxScore", "getPlayersWithMinScore")
                      .replace("#e6ffe6", DARK_BG).replace('"borderColor": "black"',
                                                            '"borderColor": "%s"' % DARK_BORDER))
# hoist the postGame winner-banner copy (format + "wins"/"share the win")
_ph = postgame[2]["payload"]["computed"]["header"]["params"]
_ph[0]["type"], _ph[0]["value"] = "cached", hs("winFormat", _ph[0]["value"])
for _prm in _ph[2]["value"]["params"]:
    if _prm["name"] == "thenValue": _prm["type"], _prm["value"] = "cached", hs("winsWord", _prm["value"])
    if _prm["name"] == "elseValue": _prm["type"], _prm["value"] = "cached", hs("shareWord", _prm["value"])

raw = {
    "gameInitOptions": gio,
    "visualSettings": visualSettings,
    "beforeLoopActions": before,
    "gameLoop": gl,
    "winCondition": {},
    "playersWinCondition": {
        "gameOverCondition": cget("gameOver"),
        "winners": S("getPlayerNamesByIds", ids=cm(S("getPlayersWithMinScore"))),
    },
    "postGameActions": postgame,
}
out = os.path.join(REPO, "game_jsons", "pageant.json")
json.dump(raw, open(out, "w"), indent=1)
print("wrote", out, "| beforeLoopActions:", len(before), "| gameLoop steps:", len(gl))
