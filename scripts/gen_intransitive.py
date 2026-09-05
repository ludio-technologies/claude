#!/usr/bin/env python3
"""Build the Intransitive game setup for Ludio.

Intransitive is rock-paper-scissors as a two-player abstract, played on a 9x9
board (rules video: https://www.youtube.com/watch?v=LO_zcGNJriA, reference
implementation: https://meaf.us/rps2/). Each side has 3 rock, 4 paper and
3 scissors. A turn moves one piece one square in any of the 8 directions.
R takes S, S takes P, P takes R; anything else is simply not a legal square.
Blue starts at a1 and wins by reaching i9; Red starts at i9 and wins by
reaching a1.

  python3 scripts/gen_intransitive.py                  # build + validate
  python3 scripts/gen_intransitive.py --deploy         # ... and PATCH staging
  python3 scripts/gen_intransitive.py --size 7         # a smaller variant

Writes game_jsons/intransitive.json and game_jsons/intransitive_describe.json.
Both are GENERATED — edit this script, never the JSON.
"""
import argparse
import copy
import json
import os
import re
import subprocess
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
IMAGES_JSON = os.path.join(HERE, "intransitive_images.json")

STAGING = "https://ptr.ludio.gg/api/setup/"
PROD = "https://try.ludio.gg/api/setup/"
DECK_API = "https://ptr.ludio.gg/api/deck"

RED = "#D83232"
BLUE = "#2E5BA8"
PAPER_BG = "#F4EEE8"
TURN_HL = "#3FA34D"      # camera border for the side to move — neither team's colour
TRAIL_BLUE = "#BBD0EE"   # the two squares of Blue's last move
TRAIL_RED = "#F5C2C2"

# Time controls the host chooses between: label, seconds per side (0 = untimed),
# and an icon from the shared Cloudinary icons folder.
ICONS = "https://res.cloudinary.com/liars-club/image/upload/icons"
TIME_CONTROLS = [
    ("No clock", 0, "sleep_face"),
    ("5 minutes each", 300, "five"),
    ("10 minutes each", 600, "ten"),
]


# ════════════════════════════════════════════════════════════ board geometry
def files_for(n):
    return "ABCDEFGHI"[:n]


def cells_for(n):
    """Every square name, e.g. A1..I9."""
    return [f"{f}{r}" for r in range(1, n + 1) for f in files_for(n)]


def widget_order(n):
    """Row-major from the TOP row down, so rank 1 (Blue's home) sits at the
    bottom-left exactly as it does in the rules video."""
    return [f"{f}{r}" for r in range(n, 0, -1) for f in files_for(n)]


def neighbours(n):
    """cell -> the squares one king-step away (3, 5 or 8 of them).

    Baked in rather than derived, so the turn loop never does grid arithmetic:
    a piece's moves are found by intersecting this list against the empty
    squares and against the enemy squares it can take.
    """
    fs = files_for(n)
    out = {}
    for i, f in enumerate(fs):
        for j in range(n):
            near = []
            for di in (-1, 0, 1):
                for dj in (-1, 0, 1):
                    if di == 0 and dj == 0:
                        continue
                    a, b = i + di, j + dj
                    if 0 <= a < n and 0 <= b < n:
                        near.append(f"{fs[a]}{b + 1}")
            out[f"{f}{j + 1}"] = near
    return out


# Which enemy bucket each piece can capture: rock takes scissors, paper takes
# rock, scissors takes paper.
PREY = {"R": "S", "P": "R", "S": "P"}


def prey_table():
    """"<team><type>" -> the opposing bucket it captures, e.g. blueR -> redS."""
    other = {"blue": "red", "red": "blue"}
    return {t + k: other[t] + PREY[k] for t in ("blue", "red") for k in "RPS"}


def bucket_keys():
    return [t + k for t in ("blue", "red") for k in "RPS"]


def mirror(cell, n):
    """180-degree rotation: Blue's setup maps onto Red's."""
    fs = files_for(n)
    i = fs.index(cell[0])
    j = int(cell[1:]) - 1
    return f"{fs[n - 1 - j]}{n - i}"


# Blue's opening, straight off the reference implementation:
#   sy = {R:["b4","c3","d2"], P:["b5","c4","d3","e2"], S:["c5","d4","e3"]}
# Three anti-diagonal stripes — rocks nearest the home corner, then paper,
# then scissors. In (file, rank) index terms the stripes sit on i+j = 4, 5, 6
# and take the middle 3, 4 and 3 squares of each diagonal.
def blue_setup(n):
    if n == 9:
        return {"R": ["B4", "C3", "D2"],
                "P": ["B5", "C4", "D3", "E2"],
                "S": ["C5", "D4", "E3"]}
    # Smaller boards: same construction, but the diagonals are shorter so the
    # 3/4/3 split has to be clipped. Only 9x9 is the real game — the smaller
    # sizes are for experimenting and their balance is untested.
    fs = files_for(n)
    out = {}
    for code, d, want in (("R", n - 5, 3), ("P", n - 4, 4), ("S", n - 3, 3)):
        span = [i for i in range(n) if 0 <= d - i < n]
        if not span:
            out[code] = []
            continue
        lo = max(0, (len(span) - want) // 2)
        picked = span[lo:lo + want]
        out[code] = [f"{fs[i]}{d - i + 1}" for i in picked]
    return out


def start_pieces(n):
    """-> list of (cell, team, type, card_name) in placement order.

    Every piece gets its own card name so placement can address one exact card
    rather than "any blue rock" — deterministic, and far easier to debug.
    """
    out = []
    seq = {}
    for code, squares in blue_setup(n).items():
        for sq in squares:
            for team, cell in (("blue", sq), ("red", mirror(sq, n))):
                key = team + code
                seq[key] = seq.get(key, 0) + 1
                out.append((cell, team, code, f"{team}_{code}_{seq[key]}"))
    return out


TYPE_NAME = {"R": "Rock", "P": "Paper", "S": "Scissors"}


def build_cards(n, images):
    """The deck the engine imports. The pieces exist before the game starts;
    setup only moves them onto their squares."""
    cards, freq = [], {}
    for _cell, team, code, card_name in start_pieces(n):
        cards.append({
            "name": card_name,
            "label": f"{team.capitalize()} {TYPE_NAME[code]}",
            "image": images[f"piece_{team}_{code}"]["url"],
            "weight": {"R": 1, "P": 2, "S": 3}[code],
        })
        freq[card_name] = 1
    return {"name": "intransitive_cards", "cards": cards, "sets": {"pieces": freq}}


# ═════════════════════════════════════════════════════════ selector plumbing
def P(name, type_, value):
    return {"name": name, "type": type_, "value": value}


def S(selector, *params):
    return {"selector": selector, "params": list(params)}


def C(value):
    """A computed param value."""
    return ("computed", value)


def cv(name):
    """Read a cached variable as a selector (for saveValueInCache values)."""
    return S("getCachedValue", P("name", "preset", name))


def obj_get(objname, key_param, default=""):
    return S("getCachedObjectValue",
             P("objectName", "preset", objname),
             key_param,
             P("defaultValue", "preset", default))


def obj_set(objname, field_param, value_param):
    return S("setCachedObjectFieldValue",
             P("objectName", "preset", objname),
             field_param,
             value_param)


def eq(a, b):
    return S("equals", a, b)


def neq(a, b):
    return S("notEqual", a, b)


def empty(save=None, skip=None):
    a = {"key": "emptyAction"}
    if skip:
        a["skipCondition"] = skip
    if save:
        a["saveValueInCache"] = save
    return a


def group(name, actions, skip=None, repeat=None, nonstop=None, checkwin=None):
    g = {"name": name}
    if skip is not None:
        g["skipCondition"] = skip
    if repeat is not None:
        g["repeat"] = repeat
    if checkwin:
        g["checkWinCondition"] = True
    g["actions"] = actions
    # nextGroupNonStop defaults to true, so it is only worth writing to turn off.
    if nonstop is False:
        g["nextGroupNonStop"] = False
    return g


# No deck labels anywhere: a 9x9 board is already tight vertically, and a label
# row under every cell costs height the board cannot spare.


# The validator pins the key order of action objects and action groups, so
# normalise once at the end rather than hand-ordering every literal above.
ACTION_ORDER = ["key", "skipCondition", "payload", "postHandler", "saveValueInCache"]
GROUP_ORDER = ["name", "turnPlayersToSpectators", "turnSpectatorsToPlayers",
               "skipCondition", "repeat", "parallel", "checkWinCondition", "actions"]


def canonicalize(o):
    if isinstance(o, list):
        return [canonicalize(x) for x in o]
    if not isinstance(o, dict):
        return o
    o = {k: canonicalize(v) for k, v in o.items()}
    order = ACTION_ORDER if "key" in o else (GROUP_ORDER if "actions" in o else None)
    if order is None:
        return o
    out = {k: o[k] for k in order if k in o}
    out.update({k: v for k, v in o.items() if k not in order})
    return out


def only_first_iteration():
    return [neq(P("arg1", "cached", "gameLoopIndex"), P("arg2", "preset", 0))]


def skip_when_over():
    return [S("getCachedValue", P("name", "preset", "gameOver"))]


def notif(header, text, image=None, duration=7, to="players", bg=PAPER_BG,
          border="#2B2B2B", textcolor="#2B2B2B", images=None):
    preset = {"header": header, "text": text, "duration": duration,
              "backgroundColor": bg, "borderColor": border, "textColor": textcolor}
    if image:
        preset["image"] = image
    if images:
        preset["images"] = images
    return {"key": "createNotification",
            "payload": {"preset": preset, "cached": {"to": to}}}


# ═════════════════════════════════════════════════════ the legal-move scan
def scan_entries():
    """One piece's legal destinations, computed in a single action.

    Every square a piece could step to is either empty or holds an enemy it
    beats, so both halves are a set intersection against lists we already keep:
    `emptyCells`, and the one enemy bucket this piece captures. That means the
    scan costs one iteration per surviving piece rather than one per direction
    — the same shape dodgeball uses for its move computation.

    Squares held by a friendly piece, or by an enemy that beats us, are in
    neither set, so they drop out without needing a rule of their own. That is
    the blockade.
    """
    return [
        {"name": "scanCell", "value": S("selectElement",
                                        P("list", "cached", "myPieces"),
                                        P("index", "cached", "repeatIndex"))},
        {"name": "scanNbrs", "value": obj_get("neighbors",
                                              P("value", "cached", "scanCell"), [])},
        {"name": "scanPrey", "value": obj_get(
            "sets",
            P("value", "computed", obj_get(
                "preyOf",
                P("value", "computed", S("formatString",
                                         P("format", "preset", "($1)($2)"),
                                         P("arg1", "cached", "turnTeam"),
                                         P("arg2", "computed", obj_get(
                                             "ptype",
                                             P("value", "cached", "scanCell"))))))),
            [])},
        {"name": "scanDests", "value": S(
            "concat",
            P("arg1", "computed", S("intersect",
                                    P("list1", "cached", "scanNbrs"),
                                    P("list2", "cached", "emptyCells"))),
            P("arg2", "computed", S("intersect",
                                    P("list1", "cached", "scanNbrs"),
                                    P("list2", "cached", "scanPrey"))))},
        {"name": "destsByCell", "value": obj_set("destsByCell",
                                                 P("fieldName", "cached", "scanCell"),
                                                 P("value", "cached", "scanDests"))},
        {"name": "movable", "value": S(
            "ifElse",
            P("condition", "computed", S("greaterThan",
                                         P("arg1", "computed", S("listLength",
                                                                 P("list", "cached", "scanDests"))),
                                         P("arg2", "preset", 0))),
            P("thenValue", "computed", S("append", P("list", "cached", "movable"),
                                         P("element", "cached", "scanCell"))),
            P("elseValue", "cached", "movable"))},
    ]


def derived_sets():
    """Recompute the lists the scan reads. Cheap, and done once per turn."""
    keys = bucket_keys()
    return [
        {"name": "piecesBlue", "value": S("concat", *[
            P(f"arg{i + 1}", "computed", obj_get("sets", P("value", "preset", k), []))
            for i, k in enumerate(keys[:3])])},
        {"name": "piecesRed", "value": S("concat", *[
            P(f"arg{i + 1}", "computed", obj_get("sets", P("value", "preset", k), []))
            for i, k in enumerate(keys[3:])])},
        {"name": "occupied", "value": S("concat",
                                        P("arg1", "cached", "piecesBlue"),
                                        P("arg2", "cached", "piecesRed"))},
        {"name": "emptyCells", "value": S("listsSubtract",
                                          P("list1", "cached", "cells"),
                                          P("list2", "cached", "occupied"))},
        {"name": "cntBlue", "value": S("listLength", P("list", "cached", "piecesBlue"))},
        {"name": "cntRed", "value": S("listLength", P("list", "cached", "piecesRed"))},
    ]


def bucket_remove(bucket_var, cell_var):
    """Drop a cell from one of the six team/type buckets.

    `bucket_var` names a cached variable holding the bucket key. The read and
    the write name that key with different params — getCachedObjectValue wants
    `value`, setCachedObjectFieldValue wants `fieldName` — so they are built
    separately rather than sharing one param object.
    """
    return obj_set("sets", P("fieldName", "cached", bucket_var),
                   P("value", "computed", S(
                       "listsSubtract",
                       P("list1", "computed", obj_get("sets",
                                                      P("value", "cached", bucket_var), [])),
                       P("list2", "computed", S("createList",
                                                P("arg1", "cached", cell_var))))))


def bucket_add(bucket_var, cell_var):
    return obj_set("sets", P("fieldName", "cached", bucket_var),
                   P("value", "computed", S(
                       "append",
                       P("list", "computed", obj_get("sets",
                                                     P("value", "cached", bucket_var), [])),
                       P("element", "cached", cell_var))))


# ═══════════════════════════════════════════════════════════════ the setup
def build(n, images):
    cells = cells_for(n)
    order = widget_order(n)
    nbrs = neighbours(n)
    pieces = start_pieces(n)
    home_blue = f"A1"
    home_red = f"{files_for(n)[-1]}{n}"
    normal_cells = [c for c in cells if c not in (home_blue, home_red)]

    img = {k: {"url": v["url"]} for k, v in images.items()}

    init = {
        "useDefaultRoles": True,
        "roleConfirmation": False,
        "allowSpectatorBecomePlayer": False,
        "allowPlayerBecomeSpectator": False,
        "notChangeLayoutAfterGame": True,
        "minPlayers": 2,
        "maxPlayers": 2,
        "preferredPlayersQnt": [2],
        "time": 20,
        "teams": {
            "blue": {"id": "blue", "name": "Blue", "description": "Blue starts in the bottom-left corner",
                     "color": BLUE, "roles": ["blue_player"]},
            "red": {"id": "red", "name": "Red", "description": "Red starts in the top-right corner",
                    "color": RED, "roles": ["red_player"]},
            "all": {"id": "all", "name": "All", "description": "All players",
                    "color": "#666666", "roles": ["player"]},
        },
        "roles": [
            {"roleInfo": {"id": "player", "name": "Player",
                          "description": "Rock, paper, scissors as a board game.",
                          "avatar": "https://res.cloudinary.com/liars-club/image/upload/"
                                    "card_player_ed7jck.webp",
                          "team": "all", "prefix": "a "},
             "isDefaultRole": True, "isRequired": False},
            {"roleInfo": {"id": "blue_player", "name": "Blue",
                          "description": "You are Blue. Your corner is A1; reach "
                                         f"{home_red} to win.",
                          "avatar": img["piece_blue_R"]["url"], "team": "blue", "prefix": ""},
             "isDefaultRole": False, "isRequired": False},
            {"roleInfo": {"id": "red_player", "name": "Red",
                          "description": f"You are Red. Your corner is {home_red}; reach "
                                         "A1 to win.",
                          "avatar": img["piece_red_R"]["url"], "team": "red", "prefix": ""},
             "isDefaultRole": False, "isRequired": False},
        ],
        "rolesPreset": {},
        "images": img,
        "animations": {},
        "soundboard": {"default": dict(
            {f"capture_{code}": images[f"capture_{code}"]["url"] for code in "RPS"},
            move=images["move"]["url"])},
    }

    data = {
        "gameInitOptions": init,
        "visualSettings": {"isCardAnimationsOff": True},
        "beforeLoopActions": before_loop(n, cells, nbrs, pieces, home_blue, home_red),
        "gameLoop": game_loop(n, cells, normal_cells, order, home_blue, home_red),
        # Keys are the TEAM IDS verbatim, matching enigma / spectrum /
        # cops_and_robbers. Reaching the corner previously threw "Cannot read
        # properties of undefined (reading 'members')" — a team lookup failing
        # at the moment of victory — and these were "Blue"/"Red" against teams
        # keyed "blue"/"red". The winner is still announced with proper casing
        # by postGameActions, so nothing is lost by matching the ids.
        "winCondition": {
            "blue": S("logicalAND",
                      P("arg1", "cached", "gameOver"),
                      P("arg2", "computed", eq(P("arg1", "cached", "winner"),
                                               P("arg2", "preset", "blue")))),
            "red": S("logicalAND",
                     P("arg1", "cached", "gameOver"),
                     P("arg2", "computed", eq(P("arg1", "cached", "winner"),
                                              P("arg2", "preset", "red")))),
        },
        # winnersInfo is deliberately absent. It is optional telemetry, no other
        # game in the repo uses it, and it is the other thing in the win path
        # that resolves a team — so it stays out until the corner-reach ending
        # is confirmed working without it.
        "postGameActions": [
            {"key": "removeAllHighlights"},
            {"key": "createNotification",
             "payload": {
                 "preset": {"duration": 14, "image": "winner",
                            "backgroundColor": PAPER_BG, "borderColor": "#2B2B2B",
                            "textColor": "#2B2B2B"},
                 "cached": {"to": "players", "text": "postgameMessage"},
                 "computed": {"header": S(
                     "ifElse",
                     P("condition", "computed", eq(P("arg1", "cached", "winner"),
                                                   P("arg2", "preset", "blue"))),
                     P("thenValue", "preset", "Blue wins!"),
                     P("elseValue", "preset", "Red wins!"))}}},
        ],
    }
    return data


# ══════════════════════════════════════════════════════════ beforeLoopActions
def before_loop(n, cells, nbrs, pieces, home_blue, home_red):
    tutorial_vote = json.load(open(os.path.join(HERE, "tutorial_vote.json")))
    tutorial_vote = copy.deepcopy(tutorial_vote)
    tutorial_vote["payload"]["preset"]["backgroundColor"] = PAPER_BG
    tutorial_vote["payload"]["preset"]["borderColor"] = "#2B2B2B"

    acts = [
        {"key": "changeBackground", "payload": {"preset": {"image": "wallpaper"}}},
        # All twenty pieces, imported from the intransitive_cards deck rather
        # than conjured mid-game.
        {"key": "createDeck",
         "payload": {"preset": {"name": "intransitive_cards", "set": "pieces",
                                "customName": "piece_pool"}}},
        # Board tables. These are constants for a given board size, so they are
        # baked in here rather than derived at runtime — Ludio has no grid maths.
        empty(save=[
            {"name": "cells", "value": cells},
            {"name": "neighbors", "value": nbrs},
            {"name": "preyOf", "value": prey_table()},
            {"name": "homeBlue", "value": home_blue},
            {"name": "homeRed", "value": home_red},
            {"name": "startCells", "value": [p[0] for p in pieces]},
            {"name": "startCards", "value": [p[3] for p in pieces]},
            {"name": "typeNames", "value": {"R": "Rock", "P": "Paper", "S": "Scissors"}},
            # Display names. The team ids stay lowercase because they key decks,
            # buckets and lookups; anything a player reads uses these.
            {"name": "teamName", "value": {"blue": "Blue", "red": "Red"}},
            # Glyphs for the move log, which is written in chess notation.
            {"name": "teamEmoji", "value": {"blue": "🔵", "red": "🟥"}},
            {"name": "pieceEmoji", "value": {"R": "🪨", "P": "📄", "S": "✂️"}},
            # One capture sound per capturing piece, so the sound says what did
            # the taking: a stone hit, a paper crumple, a scissor snip.
            {"name": "captureSound", "value": {
                "R": "soundboard.capture_R",
                "P": "soundboard.capture_P",
                "S": "soundboard.capture_S"}},
        ]),
        empty(save=[
            {"name": "players", "value": S("allPlayers")},
            {"name": "numPlayers", "value": S("listLength",
                                              P("list", "computed", S("allPlayers")))},
            {"name": "host", "value": S(
                "ifElse",
                P("condition", "computed", S("contains",
                                             P("list", "cached", "players"),
                                             P("element", "computed", S("getHostPlayerId")))),
                P("thenValue", "computed", S("createList",
                                             P("arg1", "computed", S("getHostPlayerId")))),
                P("elseValue", "computed", S("createList",
                                             P("arg1", "cached", "players.0"))))},
        ]),
        {"key": "createNotification",
         "payload": {
             "preset": {"header": "Welcome to Intransitive!", "image": "banner",
                        "duration": 8, "backgroundColor": PAPER_BG,
                        "borderColor": "#2B2B2B", "textColor": "#2B2B2B"},
             "cached": {"to": "players"},
             "computed": {"text": S(
                 "formatString",
                 P("format", "preset",
                   "<b>($1)</b> - in a moment, tell me whether you want Ludio to "
                   "teach your group how to play Intransitive!"),
                 P("arg1", "computed", S("listToString", P("list", "computed", S(
                     "getPlayerNamesByIds", P("ids", "cached", "host"))))))}}},
        tutorial_vote,
        # Host picks the time control.
        {"key": "createVote",
         "payload": {
             "preset": {
                 "title": "Time control",
                 "type": "target_poll",
                 "targets": [t[0] for t in TIME_CONTROLS],
                 "pollVoteTargetsOptions": {
                     label: {"icon": f"{ICONS}/{icon}.svg",
                             "backgroundColor": "#D3D3D3",
                             "boxIconColor": "#D3D3D3",
                             "textColor": "black",
                             "widgetIconColor": colour}
                     for (label, _secs, icon), colour in
                     zip(TIME_CONTROLS, ("black", BLUE, RED))
                 },
                 "terminationCondition": "get_all_votes",
                 "showResultInRealTime": True,
                 "showResult": True,
                 "showResultDuration": 2,
                 "allowRevoting": False,
                 "duration": 30,
                 "backgroundColor": PAPER_BG,
                 "textColor": "#2B2B2B",
                 "borderColor": "#2B2B2B",
             },
             "cached": {"actors": "host"},
             "computed": {"question": S(
                 "formatString",
                 P("format", "preset",
                   "($1), how long should each side get on the clock?"),
                 P("arg1", "computed", S("getPlayerNameById",
                                         P("id", "cached", "host.0"))))}},
         "saveValueInCache": [
             {"name": "modeChoice", "value": S(
                 "selectElement",
                 P("list", "computed", S("append",
                                         P("list", "cached", "lastActionResult.voteResult"),
                                         P("element", "preset", TIME_CONTROLS[0][0]))),
                 P("index", "preset", 0))},
             {"name": "startClock", "value": S(
                 "getCachedObjectValue",
                 P("objectName", "preset", "clockTable"),
                 P("value", "cached", "modeChoice"),
                 P("defaultValue", "preset", 0))},
         ]},
    ]
    # clockTable has to exist before the vote reads it.
    acts.insert(1, empty(save=[
        {"name": "clockTable", "value": {label: secs for label, secs, _i in TIME_CONTROLS}},
    ]))
    acts.append(empty(save=[
        {"name": "isTimed", "value": S("greaterThan",
                                       P("arg1", "cached", "startClock"),
                                       P("arg2", "preset", 0))},
        {"name": "clockBlue", "value": cv("startClock")},
        {"name": "clockRed", "value": cv("startClock")},
    ]))
    # Seat the two players.
    acts += [
        empty(save=[
            {"name": "seating", "value": S("shuffleList", P("list", "cached", "players"))},
            {"name": "blueId", "value": cv("seating.0")},
            {"name": "redId", "value": cv("seating.1")},
        ]),
        {"key": "setRole", "payload": {"preset": {"roleId": "blue_player"},
                                       "computed": {"playerId": S(
                                           "createList", P("arg1", "cached", "blueId"))}}},
        {"key": "setRole", "payload": {"preset": {"roleId": "red_player"},
                                       "computed": {"playerId": S(
                                           "createList", P("arg1", "cached", "redId"))}}},
        {"key": "showRole", "payload": {"cached": {"from": "players", "to": "players"}}},
        # No standing team colours on the cameras — the border is reserved for
        # showing whose turn it is, in a colour that is neither side's.
        {"key": "removeAllHighlights", "payload": {}},
        {"key": "changeLayout",
         "payload": {"preset": {"type": "HIGHLIGHT", "direction": "VERTICAL", "percent": 62},
                     "computed": {"top": S("createList", P("arg1", "cached", "blueId")),
                                  "bottom": S("createList", P("arg1", "cached", "redId"))}}},
        {"key": "showScore",
         "payload": {"preset": {"order": "highest", "format": "($1) ♟"},
                     "cached": {"from": "players", "to": "players"}}},
        {"key": "showScore",
         "payload": {"preset": {"secondScore": True, "order": "highest",
                                "format": "($1) ⏰"},
                     "cached": {"from": "players", "to": "players"}},
         "skipCondition": [S("logicalNOT", P("arg", "cached", "isTimed"))]},
    ]
    return acts


# ═══════════════════════════════════════════════════════════════ the gameLoop
def game_loop(n, cells, normal_cells, order, home_blue, home_red):
    first = only_first_iteration()
    groups = []

    # ── tutorial ──────────────────────────────────────────────────────────
    groups.append(group("Tutorial", [
        notif("Intransitive (1/5)",
              "Two armies of ten: <b>3 rock, 4 paper, 3 scissors</b>. Blue starts "
              "in the bottom-left corner, Red in the top-right.",
              image="banner", duration=11, to="learners"),
        notif("Moving (2/5)",
              "On your turn you move <b>one piece one square</b> — straight or "
              "diagonally, in any of the eight directions. That is the whole move. "
              "You must move; there is no passing.",
              duration=11, to="learners"),
        notif("Taking (3/5)",
              "Step onto an enemy you beat and you capture it. <b>Rock takes "
              "scissors, scissors takes paper, paper takes rock.</b>",
              images=["piece_blue_R", "piece_red_S"], duration=11, to="learners"),
        notif("Blockades (4/5)",
              "You <b>cannot</b> step onto your own piece — or onto an enemy that "
              "beats you. A rock simply cannot enter a square held by paper, so "
              "pieces genuinely wall each other off.",
              images=["piece_red_P", "piece_blue_R"], duration=12, to="learners"),
        notif("Winning (5/5)",
              f"Get any one of your pieces into <b>your opponent's corner</b> — "
              f"Blue is aiming at {home_red}, Red at {home_blue}. First one there "
              "wins. If you ever have no legal move at all, you lose.",
              image="winner", duration=12, to="learners"),
        empty(save=[{"name": "tutorial", "value": False}]),
    ], skip=[S("logicalNOT", P("arg", "cached", "tutorial"))]))

    # ── board construction (first iteration only) ─────────────────────────
    groups.append(group("Cell list", [
        empty(save=[{"name": "normalCells", "value": normal_cells}]),
    ], skip=first, nonstop=True))

    groups.append(group("Create cells", [
        {"key": "createCustomDeck",
         "payload": {"preset": {"public": True, "counter": False, "facedown": False,
                                "emptyImage": "cell"},
                     "computed": {"name": S("selectElement",
                                            P("list", "cached", "normalCells"),
                                            P("index", "cached", "repeatIndex"))}}},
    ], skip=first, nonstop=True,
        repeat={"qnt": S("listLength", P("list", "cached", "normalCells"))}))

    groups.append(group("Create home corners and captured piles", [
        {"key": "createCustomDeck",
         "payload": {"preset": {"name": home_blue, "public": True, "counter": False,
                                "facedown": False, "emptyImage": "cell_home_blue"}}},
        {"key": "createCustomDeck",
         "payload": {"preset": {"name": home_red, "public": True, "counter": False,
                                "facedown": False, "emptyImage": "cell_home_red"}}},
        {"key": "createCustomDeck",
         "payload": {"preset": {"name": "taken_blue", "public": True, "counter": True}}},
        {"key": "createCustomDeck",
         "payload": {"preset": {"name": "taken_red", "public": True, "counter": True}}},
    ], skip=first, nonstop=True))

    groups.append(group("Mount the board", [
        {"key": "createGenericCardWidget",
         "payload": {"preset": {"ratio": "1", "backgroundImage": "board_bg",
                                "dimensions": [n, n], "decks": order}}},
    ], skip=first, nonstop=True))

    # ── place the pieces ──────────────────────────────────────────────────
    # The opening is known at build time, so the whole starting state is baked
    # rather than assembled by a loop at runtime.
    owner0, ptype0 = {}, {}
    sets0 = {k: [] for k in bucket_keys()}
    for cell, team, kind, _card in start_pieces(n):
        owner0[cell] = team
        ptype0[cell] = kind
        sets0[team + kind].append(cell)

    groups.append(group("Init board state", [
        empty(save=[
            {"name": "owner", "value": owner0},
            {"name": "ptype", "value": ptype0},
            # sets: one cell list per team-and-type. This is the index the turn
            # loop reads, so a piece's moves cost one set intersection.
            {"name": "sets", "value": sets0},
            {"name": "turnTeam", "value": "blue"},
            {"name": "gameOver", "value": False},
            {"name": "winner", "value": ""},
            {"name": "postgameMessage", "value": ""},
            {"name": "moveNumber", "value": 1},
            # The two squares of each side's last move, kept per side so a
            # player's own trail can be cleared without touching the opponent's.
            {"name": "trailBlue", "value": []},
            {"name": "trailRed", "value": []},
        ] + derived_sets()),
    ], skip=first))

    # The twenty pieces already exist, dealt into piece_pool from the imported
    # deck. Setup only walks them to their opening squares.
    groups.append(group("Place pieces", [
        empty(save=[
            {"name": "pCell", "value": S("selectElement",
                                         P("list", "cached", "startCells"),
                                         P("index", "cached", "repeatIndex"))},
            {"name": "pCard", "value": S("selectElement",
                                         P("list", "cached", "startCards"),
                                         P("index", "cached", "repeatIndex"))},
        ]),
        {"key": "moveCards",
         "payload": {"preset": {"type": "deck", "qnt": 1, "from": "piece_pool"},
                     "cached": {"to": "pCell"},
                     "computed": {"cardNames": S("createList",
                                                 P("arg1", "cached", "pCard"))}}},
    ], skip=first,
        repeat={"qnt": S("listLength", P("list", "cached", "startCells"))}))

    groups.append(group("Opening board readout", [
        score_update("blueId", "cntBlue"),
        score_update("redId", "cntRed"),
        clock_score_update(),
        notif("The board is set",
              "Blue moves first. Ten pieces each: 3 rock, 4 paper, 3 scissors. "
              f"Blue is aiming at <b>{home_red}</b>, Red at <b>{home_blue}</b>.",
              image="banner", duration=8),
    ], skip=first, nonstop=True))

    # ── the turn ──────────────────────────────────────────────────────────
    groups += turn_groups(n, home_blue, home_red)

    groups.append(group("Check for a winner", [], skip=None, checkwin=True))
    return groups


def _score_entry(who_var, value_param, second=False):
    keys = ["list", "score"] + (["secondScore"] if second else [])
    values = [P("arg1", "computed", S("createList", P("arg1", "cached", who_var))),
              value_param]
    if second:
        values.append(P("arg3", "preset", True))
    values[1] = dict(value_param, name="arg2")
    return S("createDict",
             P("keys", "preset", keys),
             P("values", "computed", S("createList", *values)))


def score_update(who_var, count_var):
    """Primary score = pieces still on the board."""
    return {"key": "updateScore",
            "payload": {"computed": {"scores": S(
                "createList",
                P("arg1", "computed", _score_entry(who_var,
                                                   P("arg2", "cached", count_var))))}}}


def clock_score_update():
    """Both clocks into the secondScore slot. Skipped when untimed."""
    return {"key": "updateScore",
            "skipCondition": [S("logicalNOT", P("arg", "cached", "isTimed"))],
            "payload": {"computed": {"scores": S(
                "createList",
                P("arg1", "computed", _score_entry("blueId",
                                                   P("arg2", "cached", "clockBlue"),
                                                   second=True)),
                P("arg2", "computed", _score_entry("redId",
                                                   P("arg2", "cached", "clockRed"),
                                                   second=True)))}}}


def turn_groups(n, home_blue, home_red):
    over = skip_when_over()
    g = []

    # Who is on move, and what are they aiming at.
    g.append(group("Whose turn", [
        empty(save=[
            {"name": "isBlueTurn", "value": eq(P("arg1", "cached", "turnTeam"),
                                               P("arg2", "preset", "blue"))},
            {"name": "mover", "value": S("ifElse",
                                         P("condition", "cached", "isBlueTurn"),
                                         P("thenValue", "cached", "blueId"),
                                         P("elseValue", "cached", "redId"))},
            {"name": "waiter", "value": S("ifElse",
                                          P("condition", "cached", "isBlueTurn"),
                                          P("thenValue", "cached", "redId"),
                                          P("elseValue", "cached", "blueId"))},
            {"name": "otherTeam", "value": S("ifElse",
                                             P("condition", "cached", "isBlueTurn"),
                                             P("thenValue", "preset", "red"),
                                             P("elseValue", "preset", "blue"))},
            {"name": "myPieces", "value": S("ifElse",
                                            P("condition", "cached", "isBlueTurn"),
                                            P("thenValue", "cached", "piecesBlue"),
                                            P("elseValue", "cached", "piecesRed"))},
            {"name": "targetCell", "value": S("ifElse",
                                              P("condition", "cached", "isBlueTurn"),
                                              P("thenValue", "cached", "homeRed"),
                                              P("elseValue", "cached", "homeBlue"))},
            {"name": "myClock", "value": S("ifElse",
                                           P("condition", "cached", "isBlueTurn"),
                                           P("thenValue", "cached", "clockBlue"),
                                           P("elseValue", "cached", "clockRed"))},
            {"name": "movers", "value": S("createList", P("arg1", "cached", "mover"))},
            {"name": "moverName", "value": S("getPlayerNameById",
                                             P("id", "cached", "mover"))},
            {"name": "movable", "value": []},
            {"name": "destsByCell", "value": {}},
            {"name": "myTrail", "value": S("ifElse",
                                           P("condition", "cached", "isBlueTurn"),
                                           P("thenValue", "cached", "trailBlue"),
                                           P("elseValue", "cached", "trailRed"))},
        ]),
        # The camera border is the only turn indicator, so it moves every ply.
        {"key": "removeAllHighlights", "payload": {}},
        {"key": "highlightPlayers",
         "payload": {"preset": {"color": TURN_HL},
                     "cached": {"listOfPlayers": "movers"}}},
        # Your own last move stops being highlighted the moment it is your turn
        # again; the opponent's stays up, so you can always see what they did.
        {"key": "removeHighlightDecks",
         "skipCondition": [S("equals",
                             P("arg1", "computed", S("listLength",
                                                     P("list", "cached", "myTrail"))),
                             P("arg2", "preset", 0))],
         "payload": {"cached": {"decks": "myTrail"}}},
    ], skip=over))

    # One iteration per surviving piece — each works out all eight directions at
    # once by intersecting the baked neighbour list against the empty squares
    # and against the enemy bucket it can take.
    g.append(group("Find pieces that can move", [
        empty(save=scan_entries()),
    ], skip=over,
        repeat={"qnt": S("listLength", P("list", "cached", "myPieces"))}))

    # Zero legal moves is a loss, not a stalemate.
    g.append(group("Trapped with no legal move", [
        empty(save=[
            {"name": "gameOver", "value": True},
            {"name": "winner", "value": cv("otherTeam")},
            {"name": "postgameMessage", "value": S(
                "formatString",
                P("format", "preset", "($1) had no legal move left."),
                P("arg1", "computed", obj_get("teamName",
                                              P("value", "cached", "turnTeam"))))},
        ]),
    ], skip=over + [S("greaterThan",
                      P("arg1", "computed", S("listLength", P("list", "cached", "movable"))),
                      P("arg2", "preset", 0))], nonstop=True))

    # ── click 1: which piece ──────────────────────────────────────────────
    for timed in (True, False):
        g.append(group("Pick a piece" + (" (clock)" if timed else " (no clock)"),
                       [pick_action("movable",
                                    "your move — click the piece you want to move.",
                                    timed)],
                       skip=over + [clock_guard(timed)], nonstop=True))

    g.append(group("Read the piece", [
        empty(save=[
            {"name": "pickRaw", "value": S(
                "selectElement",
                P("list", "computed", S("append",
                                        P("list", "computed", S("getObjectValues",
                                                                P("obj", "cached", "lastActionResult"))),
                                        P("element", "preset", ""))),
                P("index", "preset", 0))},
            # A click that never arrived would otherwise leave fromCell empty and
            # send the destination scan looking up neighbours of "". On a clock
            # that case is already a loss (the flag-fall group is next); this
            # keeps every other way of getting nothing from corrupting the board.
            {"name": "fromCell", "value": S(
                "ifElse",
                P("condition", "computed", eq(P("arg1", "cached", "pickRaw"),
                                              P("arg2", "preset", ""))),
                P("thenValue", "computed", S(
                    "selectElement",
                    P("list", "computed", S("append", P("list", "cached", "movable"),
                                            P("element", "preset", ""))),
                    P("index", "preset", 0))),
                P("elseValue", "cached", "pickRaw"))},
        ]),
        empty(save=[{"name": "myClock", "value": S("getRemainingTimer",
                                                   P("timerId", "cached", "lastActionId"))}],
              skip=[S("logicalNOT", P("arg", "cached", "isTimed"))]),
    ], skip=over, nonstop=True))

    # A flag that falls mid-selection ends it there.
    g += flag_fall_groups("after choosing a piece")

    # No second scan: the pass above already stored every piece's destinations.
    g.append(group("Load the destinations", [
        empty(save=[{"name": "dests", "value": obj_get(
            "destsByCell", P("value", "cached", "fromCell"), [])}]),
    ], skip=over))

    # ── click 2: where to ─────────────────────────────────────────────────
    for timed in (True, False):
        g.append(group("Pick a destination" + (" (clock)" if timed else " (no clock)"),
                       [pick_action("dests",
                                    "now click the square to move it to.",
                                    timed)],
                       skip=over + [clock_guard(timed)], nonstop=True))

    g.append(group("Read the destination", [
        empty(save=[
            {"name": "destRaw", "value": S(
                "selectElement",
                P("list", "computed", S("append",
                                        P("list", "computed", S("getObjectValues",
                                                                P("obj", "cached", "lastActionResult"))),
                                        P("element", "preset", ""))),
                P("index", "preset", 0))},
            {"name": "toCell", "value": S(
                "ifElse",
                P("condition", "computed", eq(P("arg1", "cached", "destRaw"),
                                              P("arg2", "preset", ""))),
                P("thenValue", "computed", S(
                    "selectElement",
                    P("list", "computed", S("append", P("list", "cached", "dests"),
                                            P("element", "cached", "fromCell"))),
                    P("index", "preset", 0))),
                P("elseValue", "cached", "destRaw"))},
        ]),
        empty(save=[{"name": "myClock", "value": S("getRemainingTimer",
                                                   P("timerId", "cached", "lastActionId"))}],
              skip=[S("logicalNOT", P("arg", "cached", "isTimed"))]),
    ], skip=over))

    g += flag_fall_groups("choosing a destination")

    # ── apply the move ────────────────────────────────────────────────────
    g.append(group("Resolve the capture", [
        empty(save=[
            {"name": "capturedTeam", "value": obj_get("owner", P("value", "cached", "toCell"))},
            {"name": "capturedType", "value": obj_get("ptype", P("value", "cached", "toCell"))},
            {"name": "isCapture", "value": neq(P("arg1", "computed",
                                                 obj_get("owner", P("value", "cached", "toCell"))),
                                               P("arg2", "preset", ""))},
        ]),
        {"key": "moveCards",
         "payload": {"preset": {"type": "deck", "qnt": 1},
                     "cached": {"from": "toCell"},
                     "computed": {"to": S("formatString",
                                          P("format", "preset", "taken_($1)"),
                                          P("arg1", "cached", "capturedTeam"))}},
         "skipCondition": [S("logicalNOT", P("arg", "cached", "isCapture"))]},
        empty(save=[
            {"name": "capturedBucket", "value": S("formatString",
                                                  P("format", "preset", "($1)($2)"),
                                                  P("arg1", "cached", "capturedTeam"),
                                                  P("arg2", "cached", "capturedType"))},
            {"name": "sets", "value": bucket_remove("capturedBucket", "toCell")},
        ], skip=[S("logicalNOT", P("arg", "cached", "isCapture"))]),
    ], skip=over))

    g.append(group("Move the piece", [
        {"key": "moveCards",
         "payload": {"preset": {"type": "deck", "qnt": 1},
                     "cached": {"from": "fromCell", "to": "toCell"}}},
        empty(save=[
            {"name": "movedType", "value": obj_get("ptype", P("value", "cached", "fromCell"))},
            # An empty string is how a square reads as vacant: every lookup on
            # owner/ptype carries defaultValue "".
            {"name": "owner", "value": obj_set("owner", P("fieldName", "cached", "fromCell"),
                                               P("value", "preset", ""))},
            {"name": "ptype", "value": obj_set("ptype", P("fieldName", "cached", "fromCell"),
                                               P("value", "preset", ""))},
        ]),
        empty(save=[
            {"name": "owner", "value": obj_set("owner", P("fieldName", "cached", "toCell"),
                                               P("value", "cached", "turnTeam"))},
            {"name": "ptype", "value": obj_set("ptype", P("fieldName", "cached", "toCell"),
                                               P("value", "cached", "movedType"))},
            {"name": "movedBucket", "value": S("formatString",
                                               P("format", "preset", "($1)($2)"),
                                               P("arg1", "cached", "turnTeam"),
                                               P("arg2", "cached", "movedType"))},
        ]),
        # The piece leaves one square of its bucket and joins another.
        empty(save=[{"name": "sets", "value": bucket_remove("movedBucket", "fromCell")}]),
        empty(save=[{"name": "sets", "value": bucket_add("movedBucket", "toCell")}]),
        empty(save=[
            {"name": "clockBlue", "value": S("ifElse", P("condition", "cached", "isBlueTurn"),
                                             P("thenValue", "cached", "myClock"),
                                             P("elseValue", "cached", "clockBlue"))},
            {"name": "clockRed", "value": S("ifElse", P("condition", "cached", "isBlueTurn"),
                                            P("thenValue", "cached", "clockRed"),
                                            P("elseValue", "cached", "myClock"))},
        ] + derived_sets()),
        score_update("blueId", "cntBlue"),
        score_update("redId", "cntRed"),
        clock_score_update(),
        # The move log, in chess notation: the move number leads Blue's half and
        # an ellipsis stands in for it on Red's, so a pair of plies reads
        # "1. 🔵✂️ D4 E5" / "… 🟥✂️ F6 F5". Everything goes in the header —
        # isAnnounceOnly files it straight into the history without a popup.
        # The cell decks are already named the way the video labels the board
        # (A1 bottom-left, I9 top-right), so the squares need no translation.
        empty(save=[
            {"name": "movePrefix", "value": S(
                "ifElse",
                P("condition", "cached", "isBlueTurn"),
                P("thenValue", "computed", S("formatString",
                                             P("format", "preset", "($1)."),
                                             P("arg1", "cached", "moveNumber"))),
                P("elseValue", "preset", "…"))},
            {"name": "trailCells", "value": S("createList",
                                              P("arg1", "cached", "fromCell"),
                                              P("arg2", "cached", "toCell"))},
            {"name": "trailColor", "value": S("ifElse",
                                              P("condition", "cached", "isBlueTurn"),
                                              P("thenValue", "preset", TRAIL_BLUE),
                                              P("elseValue", "preset", TRAIL_RED))},
            {"name": "trailBlue", "value": S("ifElse",
                                             P("condition", "cached", "isBlueTurn"),
                                             P("thenValue", "cached", "trailCells"),
                                             P("elseValue", "cached", "trailBlue"))},
            {"name": "trailRed", "value": S("ifElse",
                                            P("condition", "cached", "isBlueTurn"),
                                            P("thenValue", "cached", "trailRed"),
                                            P("elseValue", "cached", "trailCells"))},
        ]),
        # Light wash on the from- and to-squares, in the mover's colour.
        {"key": "highlightDecks",
         "payload": {"cached": {"decks": "trailCells", "color": "trailColor"}}},
        move_log(capture=False),
        # A capture is the same line with the target square marked "x", and it
        # is the action that carries the sound.
        move_log(capture=True),
    ], skip=over))


    # ── did that win it? ──────────────────────────────────────────────────
    g.append(group("Corner reached", [
        empty(save=[
            {"name": "gameOver", "value": True},
            {"name": "winner", "value": cv("turnTeam")},
            {"name": "postgameMessage", "value": S(
                "formatString",
                P("format", "preset", "($1) reached ($2)."),
                P("arg1", "computed", obj_get("teamName",
                                              P("value", "cached", "turnTeam"))),
                P("arg2", "cached", "toCell"))},
        ]),
    ], skip=over + [neq(P("arg1", "cached", "toCell"), P("arg2", "cached", "targetCell"))],
        nonstop=True))

    g.append(group("Next side", [
        empty(save=[
            {"name": "turnTeam", "value": cv("otherTeam")},
            # A move is both halves, so this advances only once Red has replied.
            {"name": "moveNumber", "value": S(
                "ifElse",
                P("condition", "cached", "isBlueTurn"),
                P("thenValue", "cached", "moveNumber"),
                P("elseValue", "computed", S("inc", P("arg", "cached", "moveNumber"))))},
        ]),
    ], skip=over, nonstop=True))

    return g


def move_log(capture):
    """One line of the move log, in chess notation.

    Two variants rather than one action with a computed sound list: only the
    capture line plays audio, and an empty sounds.list on the quiet variant
    would be a sound action with nothing to play.
    """
    fmt = "($1) ($2)($3) ($4) x($5)" if capture else "($1) ($2)($3) ($4) ($5)"
    preset = {"isAnnounceOnly": True}
    payload = {"preset": preset,
               "cached": {"to": "players"},
               "computed": {
                   "header": S("formatString",
                               P("format", "preset", fmt),
                               P("arg1", "cached", "movePrefix"),
                               P("arg2", "computed", obj_get(
                                   "teamEmoji", P("value", "cached", "turnTeam"))),
                               P("arg3", "computed", obj_get(
                                   "pieceEmoji", P("value", "cached", "movedType"))),
                               P("arg4", "cached", "fromCell"),
                               P("arg5", "cached", "toCell"))}}
    guard = S("logicalNOT", P("arg", "cached", "isCapture")) if capture \
        else S("getCachedValue", P("name", "preset", "isCapture"))
    # Every move is audible: a quiet placement click, or the sound of whichever
    # piece did the taking. Neither holds the turn up.
    preset["sounds.waitForSoundEnd"] = False
    payload["cached"]["playList.0"] = "players"
    if capture:
        payload["computed"]["sounds.list"] = S(
            "createList",
            P("arg1", "computed", obj_get("captureSound",
                                          P("value", "cached", "movedType"))))
    else:
        preset["sounds.list"] = ["soundboard.move"]
    return {"key": "createNotification", "skipCondition": [guard], "payload": payload}


def clock_guard(timed):
    """Run the timed variant only when a clock is on, and vice versa."""
    if timed:
        return S("logicalNOT", P("arg", "cached", "isTimed"))
    return S("getCachedValue", P("name", "preset", "isTimed"))


def pick_action(decks_var, question, timed):
    payload = {"cached": {"actors": "movers", "decks": decks_var},
               "computed": {"question": S("formatString",
                                          P("format", "preset", "($1), " + question),
                                          P("arg1", "cached", "moverName"))}}
    if timed:
        # The whole turn is played out of the side's own bank: this action is
        # given whatever is left of it, and what remains afterwards is read
        # back off the timer.
        payload["computed"]["duration"] = S("maxValue",
                                            P("list", "computed", S(
                                                "createList",
                                                P("arg1", "cached", "myClock"),
                                                P("arg2", "preset", 1))))
    return {"key": "selectCentralWidgetDeck", "payload": payload}


def flag_fall_groups(when):
    """A clock that hits zero ends the game immediately."""
    return [group(f"Flag falls {when}", [
        empty(save=[
            {"name": "gameOver", "value": True},
            {"name": "winner", "value": cv("otherTeam")},
            {"name": "postgameMessage", "value": S(
                "formatString",
                P("format", "preset", "($1) ran out of time."),
                P("arg1", "computed", obj_get("teamName",
                                              P("value", "cached", "turnTeam"))))},
        ]),
    ], skip=skip_when_over() + [
        S("logicalNOT", P("arg", "cached", "isTimed")),
    ] + [S("greaterThan", P("arg1", "cached", "myClock"), P("arg2", "preset", 0))],
        nonstop=True)]


# ══════════════════════════════════════════════════════════════ the rulebook
def build_describe(n, home_blue, home_red, banner_url):
    return {
        "name": "Intransitive",
        "demo": False,
        "parallel": False,
        "url": "../setups/ludio-v1-engine-setup/dist_cards/app.output.js",
        "banner": banner_url,
        "description": {
            "summary": "Rock, paper, scissors as a two-player board game. Ten pieces "
                       "each on a 9x9 grid; race your opponent to their home corner.",
            "description_title": "Intransitive Overview",
            "# Players": "2",
            "players": "2",
            "Duration": "20 mins",
        },
        "tags": ["two player", "strategic"],
        "rules": [
            {"name": "Basic Rules", "content": [
                {"title": "The board",
                 "text": f"A {n}x{n} grid. Blue's home corner is {home_blue} (bottom-left), "
                         f"Red's is {home_red} (top-right). Both corners are marked."},
                {"title": "Your army",
                 "text": "Ten pieces each: 3 rock, 4 paper and 3 scissors, arranged in "
                         "three diagonal stripes in front of your corner. Red's setup is "
                         "Blue's rotated 180 degrees."},
                {"title": "The move",
                 "text": "Blue goes first. On your turn you move exactly one piece exactly "
                         "one square, straight or diagonally, in any of the eight "
                         "directions. There is no passing."},
                {"title": "Capturing",
                 "text": "Move onto an enemy piece you beat and it is captured. Rock takes "
                         "scissors, scissors takes paper, paper takes rock."},
                {"title": "Blocking",
                 "text": "You may not move onto your own piece, and you may not move onto "
                         "an enemy piece that beats yours. Those squares are not legal "
                         "moves at all, so pieces wall each other off."},
            ]},
            {"name": "Win Conditions", "content": [
                {"title": "Reaching the corner",
                 "text": f"Get any one of your pieces into your opponent's home corner. "
                         f"Blue wins by reaching {home_red}; Red wins by reaching "
                         f"{home_blue}. The first player to do it wins immediately."},
                {"title": "No stalemate",
                 "text": "If it is your turn and you have no legal move, you lose."},
                {"title": "Running out of time",
                 "text": "In a timed game, a player whose clock reaches zero loses."},
            ]},
            {"name": "Mechanics", "content": [
                {"title": "Making a move",
                 "text": "Your turn takes two clicks on the board. First click one of "
                         "your highlighted pieces — only the ones with a legal move are "
                         "offered. The squares it can reach then light up; click one to "
                         "move there."},
                {"title": "Reading the board",
                 "text": "Each player's remaining rock, paper and scissors counts are "
                         "shown on their own home corner, and their piece count and "
                         "remaining time next to their camera."},
                {"title": "Time control",
                 "text": "Before the board is built, the host picks one of three settings: "
                         "no clock, 5 minutes each, or 10 minutes each."},
                {"title": "How the clock runs",
                 "text": "In a timed game each side has its own bank. Your clock runs while "
                         "you choose a piece and while you choose its destination, and "
                         "stops as soon as you have moved. Run out and you lose."},
            ]},
            {"name": "Advanced Rules", "content": [
                {"title": "Material",
                 "text": "More pieces is better, but it is the least interesting of the "
                         "three advantages."},
                {"title": "Position",
                 "text": "Being closer to your opponent's corner than they are to yours "
                         "cramps them and wins most endgames, so trades tend to favour "
                         "whoever is further advanced."},
                {"title": "Matchup",
                 "text": "The mix matters as much as the count. If you are down to one "
                         "scissors, your opponent can create two threats with two papers "
                         "and your single scissors can only answer one of them. A balanced "
                         "3/4/3 is usually the safest shape."},
                {"title": "Defending a runner",
                 "text": "Against a piece heading for your corner you can defend actively "
                         "(capture it) or passively (park a piece in your own corner so it "
                         "cannot land). Either way you must stay ahead of it in rings: "
                         "count the squares to the corner, and always be one closer than "
                         "the attacker."},
            ]},
        ],
    }


# ══════════════════════════════════════════════════════════════════ plumbing
def validate(path, script="validate_game_json.py"):
    v = os.path.join(REPO, "documentation", script)
    r = subprocess.run([sys.executable, v, path], capture_output=True)
    out = r.stdout.decode() + r.stderr.decode()
    err = warn = 0
    for line in out.splitlines():
        m = re.match(r"[^\d]*(\d+) error", line)
        if m:
            err = int(m.group(1))
        m = re.match(r"[^\d]*(\d+) warning", line)
        if m:
            warn = int(m.group(1))
    return out, err, warn


def api_get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.load(r)


def api_patch(url, body):
    req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"},
                                 method="PATCH")
    with urllib.request.urlopen(req, timeout=300) as r:
        return r.status


def find_setup(base, name):
    for s in api_get(base):
        if s.get("name") == name:
            return s
    return None


def api_post(url, body):
    req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"},
                                 method="POST")
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.load(r)


def deploy_deck(cards):
    """Upsert the card deck on staging.

    The list endpoint returns only id/createdAt/updatedAt/script, so decks are
    matched on script.name. GET on a single deck 500s, hence the readback is
    done off the list.
    """
    decks = api_get(DECK_API)
    existing = next((d for d in decks
                     if ((d.get("script") or {}) or {}).get("name") == cards["name"]), None)
    if existing:
        api_patch(f"{DECK_API}/{existing['id']}", {"script": cards})
        did, verb = existing["id"], "updated"
    else:
        made = api_post(DECK_API, {"name": cards["name"], "script": cards})
        did, verb = made["id"], "created"

    back = next((d for d in api_get(DECK_API) if d["id"] == did), None)
    script = (back or {}).get("script") or {}
    ok = json.dumps(script, sort_keys=True) == json.dumps(cards, sort_keys=True)
    return f"{verb} {did} ({len(cards['cards'])} cards), readback matches: {ok}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--size", type=int, default=9, help="board size (9 is the real game)")
    ap.add_argument("--deploy", action="store_true", help="PATCH the staging setup")
    ap.add_argument("--meta", action="store_true",
                    help="also push name/banner/description/tags/rules, not just raw")
    ap.add_argument("--setup-id", default=None,
                    help="target this staging setup id instead of matching on name. "
                         "Needed the first time, when the fresh copy is still called "
                         "something like 'Discrete Dodgeball (1)'.")
    ap.add_argument("--setup-name", default="Intransitive")
    args = ap.parse_args()

    n = args.size
    images = json.load(open(IMAGES_JSON))
    data = canonicalize(build(n, images))

    stem = "intransitive" if n == 9 else f"intransitive_{n}x{n}"
    path = os.path.join(REPO, "game_jsons", f"{stem}.json")
    json.dump(data, open(path, "w"), indent=1)

    home_red = f"{files_for(n)[-1]}{n}"
    desc = build_describe(n, "A1", home_red, images["banner"]["url"])
    dpath = os.path.join(REPO, "game_jsons", f"{stem}_describe.json")
    json.dump(desc, open(dpath, "w"), indent=1)

    cards = build_cards(n, images)
    cpath = os.path.join(REPO, "game_jsons", f"{stem}_cards.json")
    json.dump(cards, open(cpath, "w"), indent=1)

    out, errs, warns = validate(path)
    print(out)
    dout, derrs, dwarns = validate(dpath, "validate_describe_json.py")
    print(dout)
    cout, cerrs, cwarns = validate(cpath)
    print(cout)
    print(f"=== {path}: {errs} errors, {warns} warnings")
    print(f"=== {dpath}: {derrs} errors, {dwarns} warnings")
    print(f"=== {cpath}: {cerrs} errors, {cwarns} warnings")
    errs += cerrs

    if args.deploy:
        if errs or derrs:
            print("refusing to deploy with validator errors", file=sys.stderr)
            sys.exit(1)
        setup_id = args.setup_id
        if setup_id is None:
            setup = find_setup(STAGING, args.setup_name)
            if setup is None:
                print(f"No staging setup named {args.setup_name!r}. The API has no "
                      f"create endpoint — duplicate one in the admin panel "
                      f"(/admin/setups, the Copy button) and pass its id as "
                      f"--setup-id the first time.", file=sys.stderr)
                sys.exit(1)
            setup_id = setup["id"]

        # The deck has to exist before the setup that imports it. Unlike
        # setups, /api/deck does support POST, so this upserts on its own.
        deck_status = deploy_deck(cards)
        print(f"deck {cards['name']}: {deck_status}")

        body = {"raw": data}
        if args.meta:
            # Lobby-facing metadata: name, banner, blurb, tags, rulebook popup.
            body["name"] = desc["name"]
            body.update({k: desc[k] for k in
                         ("banner", "description", "tags", "rules", "url")})
        status = api_patch(STAGING + setup_id, body)
        back = api_get(STAGING + setup_id)["raw"]
        same = json.dumps(back, sort_keys=True) == json.dumps(data, sort_keys=True)
        print(f"deployed to staging: HTTP {status}, readback matches: {same}")


if __name__ == "__main__":
    main()
