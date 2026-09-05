#!/usr/bin/env python3
"""Build Braggart game raw JSON by forking Roundabout and surgically transforming it.

Braggart = a from-scratch trick-taker (reimplementation of BON / Boast-or-Nothing).
Suits: brains / speed / strength, values 1-11 + Pass. Rotating suit-strength hierarchy.
Faithful-implicit scoring (0 tricks -> 2pts, exact target -> 1pt). Play-again vote,
highest-score wins (no threshold). 3-5 players. See memory ludio-braggart.
"""
import json, copy, os, re

RB = json.load(open('/tmp/roundabout_raw.json'))
OUT = '/Users/ankitbuddhiraju/Documents/claude/Code/game_jsons/braggart.json'

SUITS = ["brains", "speed", "strength"]
ANIM = json.load(open('/tmp/braggart_animations.json'))
CARDURL = json.load(open('/tmp/braggart_card_urls.json'))

# ---------------- DSL helpers ----------------
def pc(n, v):  return {"name": n, "type": "cached", "value": v}
def pp(n, v):  return {"name": n, "type": "preset", "value": v}
def pm(n, v):  return {"name": n, "type": "computed", "value": v}
def S(sel, *ps): return {"selector": sel, "params": list(ps)}
def svc(n, v): return {"name": n, "value": v}
def act(key, payload=None, save=None, ph=None):
    a = {"key": key}
    if payload is not None: a["payload"] = payload
    if save is not None: a["saveValueInCache"] = save
    if ph is not None: a["postHandler"] = ph
    return a

def replace_deck_name(node, old="roundabout", new="braggart"):
    """Recursively replace any string value EXACTLY == old with new (deck script name)."""
    if isinstance(node, dict):
        return {k: replace_deck_name(v, old, new) for k, v in node.items()}
    if isinstance(node, list):
        return [replace_deck_name(v, old, new) for v in node]
    if node == old:
        return new
    return node

def find_svc_value(step, name):
    """Return the saveValueInCache entry dict with given name (mutate in place)."""
    def walk(n):
        if isinstance(n, dict):
            for s in n.get('saveValueInCache', []) or []:
                if isinstance(s, dict) and s.get('name') == name:
                    return s
            for v in n.values():
                r = walk(v)
                if r is not None: return r
        elif isinstance(n, list):
            for v in n:
                r = walk(v)
                if r is not None: return r
        return None
    return walk(step)

# ============================================================
# 1. gameInitOptions
# ============================================================
gio = {
    "minPlayers": 3,
    "maxPlayers": 5,
    "timePerRound": 6,
    "allowRecorder": True,
    "allowSpectatorBecomePlayer": True,
    "allowPlayerBecomeSpectator": True,
    "roleConfirmation": False,
    "useDefaultRoles": True,
    "teams": {"all": {"id": "all", "name": "All", "color": "#297a4d",
                       "roles": ["player", "1st", "2nd", "3rd", "4th", "5th"]}},
    "roles": [
        {"roleInfo": {"id": "player", "name": "Player",
                       "description": "Boast big or take nothing!",
                       "avatar": "https://res.cloudinary.com/liars-club/image/upload/card_player_ed7jck.webp",
                       "team": "all", "prefix": "a "},
         "isDefaultRole": True, "isRequired": False},
    ] + [{"roleInfo": {"id": o, "name": o, "team": "all"}, "isRequired": False}
         for o in ["1st", "2nd", "3rd", "4th", "5th"]],
    "images": {
        "wallpaper": {"url": "https://res.cloudinary.com/liars-club/image/upload/images/braggart/wallpaper.png"},
        "banner":    {"url": "https://res.cloudinary.com/liars-club/image/upload/images/braggart/banner.png"},
        "cardback":  {"url": "https://res.cloudinary.com/liars-club/image/upload/pirate_cardback_cii39m.png"},
        "transparent": {"url": "https://res.cloudinary.com/liars-club/image/upload/transparent_sbx4wv.png"},
        "winner":    {"url": "https://res.cloudinary.com/liars-club/image/upload/winner_h5eyfr.gif"},
        "card_brains":   {"url": CARDURL["brains_7"]},
        "card_speed":    {"url": CARDURL["speed_4"]},
        "card_strength": {"url": CARDURL["strength_9"]},
        "card_pass":     {"url": CARDURL["pass"]},
    },
    "animations": {
        "winner": "https://assets3.lottiefiles.com/packages/lf20_hgvbg30i.json",
        "brains": ANIM["brains"], "speed": ANIM["speed"], "strength": ANIM["strength"],
    },
    "soundboard": {"default": {
        "reminder": "https://res.cloudinary.com/liars-club/video/upload/audio/reminder.mp4",
        "clap": "https://res.cloudinary.com/liars-club/video/upload/audio/polite_clap.mp3"}},
}

# ============================================================
# reusable: place the 3 indicator cards into hier decks per cached `hierarchy`
# ============================================================
def indicator_name(idx):
    return S("formatString", pp("format", "($1)_indicator"), pc("arg1", f"hierarchy.{idx}"))

def place_indicators():
    HIER = ["hier_strong", "hier_mid", "hier_weak"]
    acts = [act("moveCards", {"preset": {"type": "deck", "to": "indicator_pool"},
                              "cached": {"from": "hierarchyDecks"}})]
    for i, deck in enumerate(HIER):
        acts.append(act("moveCards", {
            "preset": {"type": "deck", "from": "indicator_pool", "to": deck, "qnt": 1},
            "computed": {"cardNames": S("createList", pm("arg1", indicator_name(i)))}}))
    return acts

# ============================================================
# 2. beforeLoopActions
# ============================================================
RB_BLA = RB['beforeLoopActions']

core_vars = act("emptyAction", save=[
    svc("players", S("allPlayers")),
    svc("numPlayers", S("listLength", pc("list", "players"))),
    svc("trickDecks", S("sublist",
        pp("list", ["trick_0", "trick_1", "trick_2", "trick_3", "trick_4"]),
        pp("start", 0), pc("end", "numPlayers"))),
    svc("hierarchyDecks", ["hier_strong", "hier_mid", "hier_weak"]),
    svc("suitsInHand", []),
    svc("leader", S("selectElement", pc("list", "players"), pp("index", 0))),
    svc("roundIndex", 0),
    svc("playAgain", True),
    svc("reset", False),
    svc("dimensions", {"3": [2, 3], "4": [2, 4], "5": [2, 5]}),
    svc("ordinal", {"0": "1st", "1": "2nd", "2": "3rd", "3": "4th", "4": "5th"}),
    svc("targetsByCount", {"3": 3, "4": 2, "5": 1}),
    # top rank in play per player count (deck sets p3/p4/p5 use 1-7/1-9/1-11)
    svc("maxRankByCount", {"3": 7, "4": 9, "5": 11}),
    # secondScore display format per target: "<tricks>🃏/<target>" (($1)=tricks, filled by engine)
    svc("secondScoreFormats", {"1": "($1)🃏/1", "2": "($1)🃏/2", "3": "($1)🃏/3"}),
    svc("recreateDecks", True),
])

host_action = copy.deepcopy(RB_BLA[3])  # host computation (keeps validator host-check happy)

create_main_deck = act("createDeck", {
    "preset": {"name": "braggart"},
    "computed": {"set": S("formatString", pp("format", "p($1)"), pc("arg1", "numPlayers"))}})

create_discard = act("createCustomDeck", {"preset": {"name": "discard", "public": False}})
create_indicator_pool = act("createDeck", {
    "preset": {"name": "braggart", "set": "indicators", "customName": "indicator_pool"}})
create_hier_decks = [act("createCustomDeck", {"preset": {"name": d, "public": True}})
                     for d in ["hier_strong", "hier_mid", "hier_weak"]]
label_hier = [
    act("setDeckLabel", {"preset": {"deck": "hier_strong", "label": "Strongest"}}),
    act("setDeckLabel", {"preset": {"deck": "hier_mid", "label": "Middle"}}),
    act("setDeckLabel", {"preset": {"deck": "hier_weak", "label": "Weakest"}}),
]
create_trick_decks = [act("createCustomDeck", {"preset": {"name": f"trick_{i}", "public": True}})
                      for i in range(5)]
create_videobox = copy.deepcopy(RB_BLA[15])

welcome = act("createNotification", {
    "preset": {"header": "Welcome to Braggart!",
               "text": "A trick-taking game of bold claims. Win the EXACT target number of tricks, or ZERO — anything else scores nothing. Watch the shifting suit strengths and use your Pass cards wisely!",
               "duration": 8, "backgroundColor": "#fee893", "borderColor": "black",
               "image": "banner"},
    "cached": {"to": "players"}})

tutorial_vote = copy.deepcopy(RB_BLA[17])  # createMixVote "Tutorial mode" (Everybody/Nobody)

setimagesrow = copy.deepcopy(RB_BLA[18])
changelayout = copy.deepcopy(RB_BLA[19])
# widen the central widget (35 -> 45%) so a 5-card trick row isn't squished
changelayout["payload"]["preset"]["percent"] = 45
showscore_main = copy.deepcopy(RB_BLA[20])
showscore_tricks = copy.deepcopy(RB_BLA[21])  # secondScore "($1) 🃏"
showhand = copy.deepcopy(RB_BLA[22])

before_loop = ([copy.deepcopy(RB_BLA[0])] +          # changeBackground(wallpaper)
               [core_vars, copy.deepcopy(RB_BLA[2]), host_action,
                create_main_deck, create_discard, create_indicator_pool] +
               create_hier_decks + label_hier + create_trick_decks +
               [create_videobox, welcome, tutorial_vote, setimagesrow,
                changelayout, showscore_main, showscore_tricks, showhand])

# ============================================================
# 3. gameLoop
# ============================================================
RB_GL = RB['gameLoop']
RB_TRICK = RB_GL[9]

# ---- Tutorial (3 slides to learners) ----
def tut_slide(header, text, images=None, image=None):
    pre = {"header": header, "text": text, "duration": 15,
           "backgroundColor": "#fee893", "borderColor": "black"}
    if image: pre["image"] = image
    if images: pre["images"] = images
    return act("createNotification", {"preset": pre, "cached": {"to": "learners"}})

tutorial = copy.deepcopy(RB_GL[1])
tutorial["actions"] = [
    tut_slide("How to Play - Part 1",
        "Braggart is a trick-taking game for 3-5 players with three suits: <b>Brains</b>, <b>Speed</b>, and <b>Strength</b> (1-11).<br/><br/>Each round you get 7 cards. Follow the led suit if you can!",
        images=["card_brains", "card_speed", "card_strength"]),
    tut_slide("How to Play - Part 2",
        "The three suits have a shifting strength order shown in the middle (<b>Strongest / Middle / Weakest</b>). ANY card of a stronger suit beats ANY card of a weaker one; numbers only break ties within a suit.<br/><br/>After each trick, the winning suit drops to Weakest! Play a <b>Pass</b> card to duck a trick — it never wins.",
        image="card_pass"),
    tut_slide("How to Play - Part 3",
        "<b>Go big or go home:</b> score <b>2 pts</b> for winning ZERO tricks, or <b>1 pt</b> for winning EXACTLY the target (3 tricks @3p, 2 @4p, 1 @5p). Anything else = 0.<br/><br/>Vote to keep playing; most points when you stop wins!"),
    act("emptyAction", save=[svc("tutorial", False)]),
]

# ---- Round Start ----
round_start = copy.deepcopy(RB_GL[2])
# deck name + deal count
sd = round_start["actions"][1]  # dealDeck
sd["payload"]["preset"]["qnt"] = 7
# replace the bid-init emptyAction (index 3) with braggart round init
base = ["brains", "speed", "strength"]
rotK = S("remainder", pc("arg1", "roundIndex"), pp("arg2", 3))
hierarchy_val = S("concat",
    pm("list1", S("sublist", pp("list", base), pm("start", rotK), pp("end", 3))),
    pm("list2", S("sublist", pp("list", base), pp("start", 0), pm("end", rotK))))
round_start["actions"][3] = act("emptyAction", save=[
    svc("tricksWon", {}),
    svc("target", S("getCachedObjectValue", pp("objectName", "targetsByCount"),
                    pc("value", "numPlayers"), pp("defaultValue", 2))),
    svc("maxRank", S("getCachedObjectValue", pp("objectName", "maxRankByCount"),
                     pc("value", "numPlayers"), pp("defaultValue", 11))),
    svc("hierarchy", hierarchy_val),
])
# secondScore format "<tricks>🃏/<target>" — re-set every round (target is fresh here,
# so it stays correct even after the player count changes via a spectator swap).
showscore_second_dynamic = act("showScore", {
    "preset": {"secondScore": True, "order": "highest"},
    "cached": {"from": "players", "to": "players"},
    "computed": {"format": S("getCachedObjectValue", pp("objectName", "secondScoreFormats"),
                             pc("value", "target"), pp("defaultValue", "($1)🃏"))}})
# announce the round's target (and that ZERO tricks also scores) in the round notification
rs_notif = next(a for a in round_start["actions"] if a.get("key") == "createNotification")
rs_notif.setdefault("payload", {}).setdefault("computed", {})["text"] = S("formatString",
    pp("format", "Score by winning EXACTLY ($1) tricks — or ZERO. This round each suit runs 1–($2). Anything else = 0 pts!"),
    pc("arg1", "target"), pc("arg2", "maxRank"))
# order: [shuffle, deal, showHands, init] + place indicators + secondScore-format + [notification]
round_start["actions"] = (round_start["actions"][:4] + place_indicators()
                          + [showscore_second_dynamic] + round_start["actions"][4:])

# ---- Setup Widget ----
def widget_decks():
    return S("concat", pc("list1", "trickDecks"), pc("list2", "hierarchyDecks"))
def widget_dims():
    return S("getCachedObjectValue", pp("objectName", "dimensions"),
             pc("value", "numPlayers"), pp("defaultValue", [2, 4]))

setup_widget = copy.deepcopy(RB_GL[5])
w = setup_widget["actions"][0]["payload"]["computed"]
w["decks"] = widget_decks()
w["dimensions"] = widget_dims()

init_trick_leader = copy.deepcopy(RB_GL[8])

# ---- Trick loop ----
# Trick Start
trick_start = act("emptyAction", save=[
    svc("trickPlayers", []), svc("trickSuits", []), svc("trickRanks", []),
    svc("leadSuit", "BLANK"), svc("bestPower", -2),
    svc("winPlayer", "BLANK"), svc("winSuit", "BLANK"),
])
trick_widget = act("createGenericCardWidget", {
    "preset": {"ratio": "0.77", "cardback": "cardback",
               "backgroundImage": "https://res.cloudinary.com/liars-club/image/upload/wood_qbegm0.jpg"},
    "computed": {"decks": widget_decks(), "dimensions": widget_dims()}})
trick_start_step = {"name": "Trick Start", "actions": [trick_start, trick_widget]}

show_order = copy.deepcopy(RB_TRICK[1])
label_decks = copy.deepcopy(RB_TRICK[2])

# Play Card Loop: reuse, override playableSuits (leader can't pass; followers always may pass)
play_loop = copy.deepcopy(RB_TRICK[3])
ps = find_svc_value(play_loop, "playableSuits")
ps["value"] = S("ifElse",
    pm("condition", S("equals", pc("arg1", "leadSuit"), pp("arg2", "BLANK"))),
    pp("thenValue", SUITS),  # leader: real suits only, no pass
    pm("elseValue", S("ifElse",
        pc("condition", "hasLeadSuit"),
        pm("thenValue", S("createList", pc("arg1", "leadSuit"), pp("arg2", "pass"))),
        pp("elseValue", SUITS + ["pass"]))))

# Evaluate Winner (power-score)
suitBase = S("selectElement", pp("list", [200, 100, 0]),
             pm("index", S("maxValue", pm("list", S("createList",
                 pm("arg1", S("indexOf", pc("list", "hierarchy"), pc("element", "evalSuit"))),
                 pp("arg2", 0))))))
power_val = S("ifElse",
    pm("condition", S("equals", pc("arg1", "evalSuit"), pp("arg2", "pass"))),
    pp("thenValue", -1),
    pm("elseValue", S("add", pm("arg1", suitBase), pc("arg2", "evalRank"))))
eval_winner = {"name": "Evaluate Winner",
    "repeat": {"qnt": S("getCachedValue", pp("name", "numPlayers"))},
    "actions": [act("emptyAction", save=[
        svc("evalPlayer", S("selectElement", pc("list", "trickPlayers"), pc("index", "repeatIndex"))),
        svc("evalSuit", S("selectElement", pc("list", "trickSuits"), pc("index", "repeatIndex"))),
        svc("evalRank", S("selectElement", pc("list", "trickRanks"), pc("index", "repeatIndex"))),
        svc("power", power_val),
        svc("isBetter", S("greaterThan", pc("arg1", "power"), pc("arg2", "bestPower"))),
        svc("bestPower", S("ifElse", pc("condition", "isBetter"),
                           pc("thenValue", "power"), pc("elseValue", "bestPower"))),
        svc("winPlayer", S("ifElse", pc("condition", "isBetter"),
                           pc("thenValue", "evalPlayer"), pc("elseValue", "winPlayer"))),
        svc("winSuit", S("ifElse", pc("condition", "isBetter"),
                         pc("thenValue", "evalSuit"), pc("elseValue", "winSuit"))),
    ])]}

# End Trick
tricks_of_winner = S("getCachedObjectValue", pp("objectName", "tricksWon"),
                     pc("value", "currentWinner"), pp("defaultValue", 0))
end_trick_actions = [
    act("emptyAction", save=[
        svc("currentWinner", S("getCachedValue", pp("name", "winPlayer"))),
        svc("winnerSuit", S("getCachedValue", pp("name", "winSuit"))),
        svc("tricksWon", S("incObjectFieldValue", pp("objectName", "tricksWon"),
                           pm("ids", S("createList", pc("arg1", "currentWinner"))))),
    ]),
    # secondScore = tricks won so far (live display)
    act("updateScore", {"computed": {"scores": S("createList", pm("arg1",
        S("createDict", pp("keys", ["list", "score", "secondScore"]),
          pm("values", S("createList",
              pm("arg1", S("createList", pc("arg1", "currentWinner"))),
              pm("arg2", tricks_of_winner),
              pp("arg3", True))))))}}),
    act("emptyAction", {"preset": {"sounds.list": ["soundboard.clap"], "sounds.waitForSoundEnd": False},
                        "cached": {"playList.0": "players"}}),
    act("animateBox", {"cached": {"animation": "winnerSuit"},
                       "computed": {"userIds": S("createList", pc("arg1", "currentWinner"))}}),
    act("createNotification", {
        "preset": {"duration": 3, "isAnnounceOnly": True, "backgroundColor": "#fee893", "borderColor": "black"},
        "cached": {"to": "players"},
        "computed": {"header": S("formatString", pp("format", "($1) wins the trick!"),
            pm("arg1", S("getPlayerNameById", pc("id", "currentWinner"))))}}),
    # collect the played cards to discard
    act("moveCards", {"preset": {"type": "deck", "to": "discard"},
                      "computed": {"from": S("getCachedValue", pp("name", "trickDecks"))}}),
    # rotate hierarchy: winning suit -> weakest (end)
    act("emptyAction", save=[svc("hierarchy", S("append",
        pm("list", S("listsSubtract", pc("list1", "hierarchy"),
            pm("list2", S("createList", pc("arg1", "winnerSuit"))))),
        pc("element", "winnerSuit")))]),
] + place_indicators() + [
    act("emptyAction", save=[
        svc("trickLeader", S("getCachedValue", pp("name", "currentWinner"))),
        svc("isActionLoop", S("greaterThan",
            pm("arg1", S("listLength", pm("list", S("playerHand", pc("playerId", "players.0"))))),
            pp("arg2", 0))),
    ]),
]
end_trick = {"name": "End Trick", "actions": end_trick_actions}

trick_loop = [trick_start_step, show_order, label_decks, play_loop, eval_winner, end_trick]

# ---- Round Scoring (braggart) ----
round_scoring = copy.deepcopy(RB_GL[10])
this_player = S("selectElement", pc("list", "players"), pc("index", "repeatIndex"))
score_delta = S("ifElse",
    pm("condition", S("equals", pc("arg1", "tricks"), pp("arg2", 0))),
    pp("thenValue", 2),
    pm("elseValue", S("ifElse",
        pm("condition", S("equals", pc("arg1", "tricks"), pc("arg2", "target"))),
        pp("thenValue", 1), pp("elseValue", 0))))
round_scoring["actions"][0] = act("emptyAction", save=[
    svc("scoringPlayer", this_player),
    svc("tricks", S("getCachedObjectValue", pp("objectName", "tricksWon"),
                    pm("value", this_player), pp("defaultValue", 0))),
    svc("scoreDelta", score_delta),
])
# keep updateScore #1 (delta) and #2 (secondScore=tricks) as-is; fix the notification text
notif = round_scoring["actions"][3]
notif["payload"]["computed"]["text"] = S("formatString",
    pp("format", "($1): ($2) tricks (aim 0 or ($3)) → ($4) pts"),
    pm("arg1", S("getPlayerNameById", pc("id", "scoringPlayer"))),
    pc("arg2", "tricks"), pc("arg3", "target"), pc("arg4", "scoreDelta"))

play_again = copy.deepcopy(RB_GL[11])
reset_scores = copy.deepcopy(RB_GL[12])

# ---- End Round ----
end_round = replace_deck_name(copy.deepcopy(RB_GL[13]))

# ---- Spectator <-> player support ----
TRICK_DECK_NAMES = ["trick_0", "trick_1", "trick_2", "trick_3", "trick_4"]
def roster_svc():
    """Recompute the live roster + trick-deck list (all 5 trick decks, sublist to count)."""
    return [
        svc("players", S("allPlayers")),
        svc("numPlayers", S("listLength", pc("list", "players"))),
        svc("trickDecks", S("sublist", pp("list", TRICK_DECK_NAMES), pp("start", 0), pc("end", "numPlayers"))),
    ]

# Change Players: runs every round — rotates the leader AND (via the group flags)
# triggers the turn*Actions when someone joins/leaves. FIXED vs Roundabout: trick
# deck list now spans trick_0..trick_4 (Roundabout only had 4) so 5-player round 2+
# keeps all five trick decks; dropped the unused summaryDecks recompute.
change_players = {
    "name": "Change Players",
    "turnSpectatorsToPlayers": True,
    "turnPlayersToSpectators": True,
    "actions": [act("emptyAction", save=roster_svc() + [
        svc("leader", S("nextPlayer", pc("playersList", "players"), pc("playerId", "leader"))),
    ])],
}

# spectator -> player: recompute roster, make them a player, seat them at the current
# minimum score (currentMinScore is cached in End Round — do NOT call getMinCurrentScore
# here, it returns the newcomer's own 0), refresh score displays + hand decks, rebuild
# the deck for the new player count. Next Round Start deals them in.
spec_to_player = [
    act("emptyAction", save=[svc("newPlayer", S("getCachedValue", pp("name", "waitingSpectator")))]
                            + roster_svc() + [svc("recreateDecks", True)]),
    act("setRole", {"preset": {"roleId": "player"}, "cached": {"playerId": "newPlayer"}}),
    act("updateScore", {"computed": {"scores": S("createList", pm("arg1",
        S("createDict", pp("keys", ["list", "score"]),
          pm("values", S("createList",
              pm("arg1", S("createList", pc("arg1", "newPlayer"))),
              pc("arg2", "currentMinScore"))))))}}),
    act("showScore", {"preset": {"order": "highest"}, "cached": {"from": "players", "to": "players"}}),
    copy.deepcopy(showscore_second_dynamic),
    act("createVideoboxDecks", {"preset": {"cardback": "cardback"}, "cached": {"players": "players"}}),
    copy.deepcopy(create_main_deck),
]

# player -> spectator: recall the leaver's cards, recompute roster, rebuild the deck.
player_to_spec = [
    act("recallCards", {"preset": {"deck": "braggart"}, "cached": {"targets": "oldPlayer"}}),
    act("emptyAction", save=roster_svc() + [svc("recreateDecks", True)]),
    copy.deepcopy(create_main_deck),
]

game_loop = [tutorial, round_start, setup_widget, init_trick_leader, trick_loop,
             round_scoring, play_again, reset_scores, end_round, change_players]

# ============================================================
# 4. assemble raw
# ============================================================
raw = {
    "gameInitOptions": gio,
    "visualSettings": copy.deepcopy(RB.get("visualSettings", {})),
    "beforeLoopActions": before_loop,
    "gameLoop": game_loop,
    "playersWinCondition": copy.deepcopy(RB["playersWinCondition"]),
    "postGameActions": copy.deepcopy(RB["postGameActions"]),
    "turnPlayerToSpectatorActions": player_to_spec,
    "turnSpectatorToPlayerActions": spec_to_player,
}

# final safety pass: any leftover deck-name literal "roundabout" -> "braggart"
raw = replace_deck_name(raw)

# ============================================================
# 4b. strings + visualSettings refactor (hoist display copy -> gameInitOptions.strings.Default)
# ============================================================
def collect_svc_names(node, out):
    if isinstance(node, dict):
        for s in node.get('saveValueInCache', []) or []:
            if isinstance(s, dict) and 'name' in s:
                out.add(s['name'])
        for v in node.values():
            collect_svc_names(v, out)
    elif isinstance(node, list):
        for v in node:
            collect_svc_names(v, out)

SVC_NAMES = set()
for sect in ['beforeLoopActions', 'gameLoop', 'postGameActions',
             'turnPlayerToSpectatorActions', 'turnSpectatorToPlayerActions']:
    collect_svc_names(raw[sect], SVC_NAMES)

STR = {}          # key -> value
VAL2KEY = {}      # json(value) -> key

def slug(s):
    t = re.sub(r'<[^>]+>', ' ', s)
    t = re.sub(r'\(\$\d+\)', ' ', t)
    words = re.findall(r'[A-Za-z0-9]+', t)[:4]
    if not words:
        return 'str'
    return words[0].lower() + ''.join(w.capitalize() for w in words[1:])

def hoist(value, base=None):
    vk = json.dumps(value, sort_keys=True)
    if vk in VAL2KEY:
        return VAL2KEY[vk]
    base = base or (slug(value) if isinstance(value, str) else 'val')
    k, i = base, 2
    while k in STR or k in SVC_NAMES:
        k = f"{base}{i}"; i += 1
    STR[k] = value
    VAL2KEY[vk] = k
    return k

COPY_FIELDS = ['header', 'text', 'title', 'subtitle', 'message', 'placeholder', 'label', 'question']
IMG_ALIAS_KEY = {'banner': 'bannerImg', 'wallpaper': 'wallpaperImg'}

def is_identifier_template(fmt):
    stripped = re.sub(r'\(\$\d+\)', '', fmt)
    return (' ' not in fmt) and bool(re.fullmatch(r'[A-Za-z0-9_]*', stripped))

def hoist_action(a):
    """Hoist display strings inside a single action dict (payload preset/cached)."""
    pl = a.get('payload')
    if not isinstance(pl, dict):
        return
    pre = pl.get('preset', {})
    cached = pl.setdefault('cached', {})
    # copy fields
    for f in COPY_FIELDS:
        if f in pre and isinstance(pre[f], str):
            cached[f] = hoist(pre.pop(f))
    # single image alias
    if 'image' in pre and pre['image'] in IMG_ALIAS_KEY:
        alias = pre.pop('image')
        cached['image'] = hoist(alias, IMG_ALIAS_KEY[alias])
    # tutorial mixVote poll targets + options
    if 'poll.targets' in pre and isinstance(pre['poll.targets'], list):
        cached['poll.targets'] = hoist(pre.pop('poll.targets'), 'everybodyNobodyTargets')
    if 'pollVoteTargetsOptions' in pre and isinstance(pre['pollVoteTargetsOptions'], dict):
        cached['pollVoteTargetsOptions'] = hoist(pre.pop('pollVoteTargetsOptions'), 'everybodyNobodyOptions')
    if not cached:
        pl.pop('cached', None)

def walk_hoist(node):
    if isinstance(node, dict):
        # formatString templates
        if node.get('selector') == 'formatString':
            for p in node.get('params', []):
                if p.get('name') == 'format' and p.get('type') == 'preset' \
                        and isinstance(p.get('value'), str) and not is_identifier_template(p['value']):
                    p['type'] = 'cached'; p['value'] = hoist(p['value'])
                # hoist literal display-text string args (with a space)
                elif p.get('name', '').startswith('arg') and p.get('type') == 'preset' \
                        and isinstance(p.get('value'), str) and ' ' in p['value']:
                    p['type'] = 'cached'; p['value'] = hoist(p['value'])
        if node.get('key'):
            hoist_action(node)
        for v in node.values():
            walk_hoist(v)
    elif isinstance(node, list):
        for v in node:
            walk_hoist(v)

for sect in ['beforeLoopActions', 'gameLoop', 'postGameActions']:
    walk_hoist(raw[sect])

# vote-result comparison literal: learners svc compares voteResult contains "Everybody!"
def fix_vote_literal(node):
    if isinstance(node, dict):
        if node.get('selector') == 'contains':
            for p in node.get('params', []):
                if p.get('type') == 'preset' and p.get('value') == 'Everybody!':
                    p['type'] = 'cached'; p['value'] = 'everybodyNobodyTargets.0'
        for v in node.values():
            fix_vote_literal(v)
    elif isinstance(node, list):
        for v in node:
            fix_vote_literal(v)
fix_vote_literal(raw['beforeLoopActions'])

raw['gameInitOptions']['strings'] = {'Default': STR}

# visualSettings: hoist the shared modal colours; strip them from cascade actions.
# increaseHandHeight = bigger hand cards; cardHandBackgroundImage = SAME wood texture
# as the central widget's backgroundImage (see trick_widget/setup_widget).
WOOD_BG = "https://res.cloudinary.com/liars-club/image/upload/wood_qbegm0.jpg"
raw['visualSettings'] = {"backgroundColor": "#fee893", "textColor": "black", "borderColor": "black",
                         "increaseHandHeight": True, "cardHandBackgroundImage": WOOD_BG}
CASCADE = {'createNotification', 'createVote', 'createMixVote', 'createInput', 'createConfirmation'}
def strip_colors(node):
    if isinstance(node, dict):
        if node.get('key') in CASCADE:
            pre = (node.get('payload', {}) or {}).get('preset', {})
            for c, val in [('backgroundColor', '#fee893'), ('textColor', 'black'), ('borderColor', 'black')]:
                if pre.get(c) == val:
                    pre.pop(c)
        for v in node.values():
            strip_colors(v)
    elif isinstance(node, list):
        for v in node:
            strip_colors(v)
for sect in ['beforeLoopActions', 'gameLoop', 'postGameActions']:
    strip_colors(raw[sect])

# normalize action/group key ordering to the validator's canonical order (cosmetic)
ACTION_ORDER = ['key', 'skipCondition', 'payload', 'postHandler', 'saveValueInCache']
GROUP_ORDER = ['name', 'turnPlayersToSpectators', 'turnSpectatorsToPlayers',
               'skipCondition', 'repeat', 'parallel', 'checkWinCondition', 'actions']
def norm(node):
    if isinstance(node, list):
        return [norm(x) for x in node]
    if isinstance(node, dict):
        node = {k: norm(v) for k, v in node.items()}
        order = ACTION_ORDER if 'key' in node else (
                GROUP_ORDER if ('actions' in node or 'repeat' in node or 'parallel' in node) else None)
        if order is None:
            return node
        return {**{k: node[k] for k in order if k in node},
                **{k: v for k, v in node.items() if k not in order}}
    return node
for sect in ['beforeLoopActions', 'gameLoop', 'postGameActions',
             'turnPlayerToSpectatorActions', 'turnSpectatorToPlayerActions']:
    raw[sect] = norm(raw[sect])

os.makedirs(os.path.dirname(OUT), exist_ok=True)
json.dump(raw, open(OUT, "w"), indent=1)
print("wrote", OUT)
print("gameLoop steps:", [ (s.get('name') if isinstance(s, dict) else 'TRICK_LOOP_LIST') for s in game_loop])
print("beforeLoop len:", len(before_loop))
