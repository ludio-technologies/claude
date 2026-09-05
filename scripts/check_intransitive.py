#!/usr/bin/env python3
"""Verify the generated Intransitive setup actually plays by the real rules.

The Ludio validator only checks that the JSON is well-formed. This checks the
game: it pulls the lookup tables the setup bakes in (neighbours, the beats
table, the opening position) and plays thousands of random games with them,
comparing every legal-move set against an independent implementation written
straight from the published rules.

  python3 scripts/check_intransitive.py [--games 400]
"""
import argparse
import json
import os
import random
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)

# The reference implementation's own constants, transcribed from
# https://meaf.us/rps2/ — the independent source of truth for this check.
REF_BLUE_SETUP = {"R": ["b4", "c3", "d2"],
                  "P": ["b5", "c4", "d3", "e2"],
                  "S": ["c5", "d4", "e3"]}
REF_CORNERS = {"blue": "a1", "red": "i9"}
REF_BEATS = {"R": "S", "S": "P", "P": "R"}
FILES = "abcdefghi"


# ───────────────────────────────────────────── independent rules implementation
def ref_mirror(sq):
    b = FILES.index(sq[0])
    u = int(sq[1:]) - 1
    return f"{FILES[8 - u]}{8 - b + 1}"


def ref_start():
    board = {}
    for t, squares in REF_BLUE_SETUP.items():
        for sq in squares:
            board[sq] = ("blue", t)
            board[ref_mirror(sq)] = ("red", t)
    return board


def ref_legal(board, sq):
    """Straight transcription of the reference implementation's move generator."""
    team, kind = board[sq]
    i, j = FILES.index(sq[0]), int(sq[1:]) - 1
    out = []
    for di in (-1, 0, 1):
        for dj in (-1, 0, 1):
            if di == 0 and dj == 0:
                continue
            a, b = i + di, j + dj
            if not (0 <= a < 9 and 0 <= b < 9):
                continue
            t = f"{FILES[a]}{b + 1}"
            occupant = board.get(t)
            if occupant is None:
                out.append(t)
            elif occupant[0] != team and REF_BEATS[kind] == occupant[1]:
                out.append(t)
    return sorted(out)


# ─────────────────────────────────────── the setup's own tables and algorithm
def baked(data):
    """Pull every constant the setup bakes into cache."""
    found = {}
    for action in data["beforeLoopActions"]:
        for e in action.get("saveValueInCache", []) or []:
            if isinstance(e.get("value"), (dict, list, str, int)) and "selector" not in str(e.get("value"))[:20]:
                found.setdefault(e["name"], e["value"])
    return found


def table_legal(sets, empty_cells, cell, team, kind, neighbors, prey_of):
    """The move generator exactly as the game JSON expresses it: intersect the
    baked neighbour list against the empty squares, and against the single
    enemy bucket this piece captures. No per-direction branching."""
    nbrs = neighbors[cell]
    prey = sets[prey_of[team + kind]]
    free = [c for c in nbrs if c in set(empty_cells)]
    takes = [c for c in nbrs if c in set(prey)]
    return sorted(free + takes)


def norm(sq):
    return sq.lower()


def denorm(sq):
    return sq.upper()


# ───────────────────────────────────────────────────────────────────── checks
def structural(data, fails):
    init = data["gameInitOptions"]
    images = set(init["images"])

    widget = None
    created = set()
    for g in data["gameLoop"]:
        for a in g.get("actions", []):
            if a.get("key") == "createGenericCardWidget":
                widget = a["payload"]["preset"]
            if a.get("key") == "createCustomDeck":
                nm = (a["payload"].get("preset") or {}).get("name")
                if nm:
                    created.add(nm)

    if widget is None:
        fails.append("no createGenericCardWidget in the gameLoop")
        return
    decks = widget["decks"]
    if widget["dimensions"] != [9, 9]:
        fails.append(f"widget dimensions {widget['dimensions']} != [9, 9]")
    if len(decks) != 81 or len(set(decks)) != 81:
        fails.append(f"widget lists {len(decks)} decks ({len(set(decks))} unique), expected 81")

    # Cells created in a repeat come from the normalCells list, not a literal name.
    normal = None
    for g in data["gameLoop"]:
        for a in g.get("actions", []):
            for e in a.get("saveValueInCache", []) or []:
                if e.get("name") == "normalCells":
                    normal = e["value"]
    if normal is None:
        fails.append("normalCells list not found")
    else:
        made = set(normal) | created
        missing = [d for d in decks if d not in made]
        if missing:
            fails.append(f"widget references {len(missing)} decks that are never created: {missing[:5]}")

    # Top-left of the rendered grid must be A9 and bottom-right I1, so that
    # Blue's home corner sits bottom-left as it does in the rules video.
    if decks[0] != "A9" or decks[8] != "I9" or decks[-9] != "A1" or decks[-1] != "I1":
        fails.append(f"widget order wrong: first row {decks[:9]}, last row {decks[-9:]}")

    # Every image alias the setup mentions must exist.
    used = set()

    def walk(o):
        if isinstance(o, dict):
            for k, v in o.items():
                if k in ("image", "emptyImage", "backgroundImage") and isinstance(v, str):
                    used.add(v)
                if k == "images" and isinstance(v, list):
                    used.update(x for x in v if isinstance(x, str))
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    walk(data["gameLoop"])
    walk(data["beforeLoopActions"])
    walk(data.get("postGameActions", []))
    for alias in sorted(used - images):
        if not alias.startswith("http"):
            fails.append(f"image alias {alias!r} is used but not defined in gameInitOptions.images")

    if init["minPlayers"] != 2 or init["maxPlayers"] != 2:
        fails.append("this is a strictly two-player game; min/maxPlayers must both be 2")


def tables(data, fails):
    b = baked(data)
    for key in ("neighbors", "preyOf", "startCells", "startCards",
                "homeBlue", "homeRed"):
        if key not in b:
            fails.append(f"baked table {key!r} missing from beforeLoopActions")
            return None

    nbrs, prey_of = b["neighbors"], b["preyOf"]

    if len(nbrs) != 81:
        fails.append(f"neighbors has {len(nbrs)} cells, expected 81")
    for cell, lst in nbrs.items():
        expect = sorted(denorm(x) for x in ref_legal({norm(cell): ("blue", "R")}, norm(cell)))
        if sorted(lst) != expect:
            fails.append(f"neighbors[{cell}] = {sorted(lst)}, expected {expect}")
            break

    # preyOf must encode exactly the three winning pairings, and always point at
    # the opposing colour.
    want_prey = {t + k: ("red" if t == "blue" else "blue") + REF_BEATS[k]
                 for t in ("blue", "red") for k in "RPS"}
    if prey_of != want_prey:
        fails.append(f"preyOf is {prey_of}, expected {want_prey}")

    # Opening position must match the reference implementation exactly.
    init = initial_state(data, fails)
    if len(init) == 3:
        got = {c: (init["owner"][c], init["ptype"][c]) for c in init["owner"]}
        want = {denorm(sq): v for sq, v in ref_start().items()}
        if got != want:
            only_got = {k: v for k, v in got.items() if want.get(k) != v}
            only_want = {k: v for k, v in want.items() if got.get(k) != v}
            fails.append(f"opening position differs. unexpected={only_got} missing={only_want}")
        # sets must be the same board expressed the other way round.
        from_sets = {c: (k[:-1], k[-1]) for k, v in init["sets"].items() for c in v}
        if from_sets != got:
            fails.append("the six team/type buckets disagree with owner/ptype at setup")

    if b["homeBlue"] != denorm(REF_CORNERS["blue"]) or b["homeRed"] != denorm(REF_CORNERS["red"]):
        fails.append(f"corners are {b['homeBlue']}/{b['homeRed']}, "
                     f"expected {denorm(REF_CORNERS['blue'])}/{denorm(REF_CORNERS['red'])}")
    return b


def cards_deck(data, b, fails):
    """The pieces must come from the imported deck, not be conjured mid-game."""
    path = os.path.join(REPO, "game_jsons", "intransitive_cards.json")
    if not os.path.exists(path):
        fails.append("intransitive_cards.json is missing — the pieces have no deck")
        return
    cards = json.load(open(path))

    for g in data["gameLoop"]:
        for a in g.get("actions", []):
            if a.get("key") == "createCard":
                fails.append("createCard in the gameLoop: pieces should be moved from "
                             "the imported deck, not created on the fly")

    made = {c["name"] for c in cards["cards"]}
    placed = set(b["startCards"])
    if placed - made:
        fails.append(f"placement names cards the deck does not define: "
                     f"{sorted(placed - made)[:5]}")
    if made - placed:
        fails.append(f"deck defines cards nothing places: {sorted(made - placed)[:5]}")
    if len(b["startCards"]) != len(placed):
        fails.append("a card name is placed twice")

    freq = cards.get("sets", {}).get("pieces", {})
    if sorted(freq) != sorted(made) or set(freq.values()) != {1}:
        fails.append("sets.pieces must list every card exactly once")

    # Each side: 3 rock, 4 paper, 3 scissors, and the right art on each.
    for team in ("blue", "red"):
        for code, want_n in (("R", 3), ("P", 4), ("S", 3)):
            n = sum(1 for c in cards["cards"] if c["name"].startswith(f"{team}_{code}_"))
            if n != want_n:
                fails.append(f"{team} has {n} {code} cards, expected {want_n}")
    for c in cards["cards"]:
        team, code, _i = c["name"].split("_")
        if f"piece_{team}_{code}" not in c["image"]:
            fails.append(f"card {c['name']} uses the wrong art: {c['image']}")

    # And no deck labels anywhere — they cost vertical space the board needs.
    for g in data["gameLoop"]:
        for a in g.get("actions", []):
            if a.get("key") in ("setDeckLabel", "setDeckLabels"):
                fails.append(f"{a['key']} in the gameLoop: deck labels eat board height")


def presentation(data, fails):
    """The board-presentation rules: no deck highlighting anywhere, team colours
    off the cameras, Blue on the left, and every prompt naming the player."""
    everywhere = [data["beforeLoopActions"], data["gameLoop"],
                  data.get("postGameActions", [])]

    def actions():
        for section in everywhere:
            for item in section:
                if isinstance(item, dict) and "actions" in item:
                    for a in item["actions"]:
                        yield a
                elif isinstance(item, dict):
                    yield item

    # Deck highlighting exists for exactly one thing: the two squares of the
    # last move. Never for showing movable pieces or legal destinations.
    for a in actions():
        if a.get("key") == "removeAllHighlightDecks":
            fails.append("removeAllHighlightDecks would wipe the opponent's move "
                         "trail; clear only the mover's own squares")
        if a.get("key") == "highlightDecks":
            decks = json.dumps((a.get("payload") or {}).get("cached", {}).get("decks"))
            if "trailCells" not in decks:
                fails.append(f"highlightDecks on {decks} — only the move trail "
                             f"may be highlighted")
        if a.get("key") == "removeHighlightDecks":
            decks = json.dumps((a.get("payload") or {}).get("cached", {}).get("decks"))
            if "myTrail" not in decks:
                fails.append(f"removeHighlightDecks on {decks} — only the mover's "
                             f"own trail may be cleared")
        if a.get("key") == "highlightPlayers":
            colour = ((a.get("payload") or {}).get("preset") or {}).get("color")
            if colour and colour.upper() in ("#D83232", "#2E5BA8"):
                fails.append(f"highlightPlayers uses a team colour ({colour}); the "
                             f"camera border is the turn indicator only")
        if a.get("key") == "selectCentralWidgetDeck":
            payload = a.get("payload") or {}
            q = (payload.get("computed") or {}).get("question")
            flat = json.dumps(q)
            if not q or "moverName" not in flat:
                fails.append("a selectCentralWidgetDeck prompt does not name the player")

    for a in actions():
        if a.get("key") == "changeLayout":
            comp = (a.get("payload") or {}).get("computed") or {}
            if "blueId" not in json.dumps(comp.get("top")):
                fails.append("changeLayout must put Blue on top (the left-hand side)")

    # The move log: chess notation, entirely in the header, in two variants —
    # a quiet one and a capture one that marks the target square and plays.
    logs = [a for a in actions()
            if a.get("key") == "createNotification"
            and ((a.get("payload") or {}).get("preset") or {}).get("isAnnounceOnly")]
    if len(logs) != 2:
        fails.append(f"expected 2 move-log variants (quiet + capture), found {len(logs)}")
    formats = []
    for a in logs:
        comp = a["payload"].get("computed") or {}
        if "text" in comp or "text" in (a["payload"].get("preset") or {}):
            fails.append("the move log must carry everything in the header, not text")
        head = json.dumps(comp.get("header"))
        for need in ("movePrefix", "teamEmoji", "pieceEmoji", "fromCell", "toCell"):
            if need not in head:
                fails.append(f"move log header is missing {need}")
        formats.append(comp["header"]["params"][0]["value"])
        if not a.get("skipCondition"):
            fails.append("each move-log variant needs an isCapture guard")
    if sorted(formats) != sorted(["($1) ($2)($3) ($4) ($5)",
                                  "($1) ($2)($3) ($4) x($5)"]):
        fails.append(f"move-log formats are {formats}; the capture line must "
                     f"prefix the target square with x")

    if data["visualSettings"].get("isCardAnimationsOff") is not True:
        fails.append("visualSettings.isCardAnimationsOff must be true")

    # A capture sound per capturing piece, chosen through the captureSound table.
    board = (data["gameInitOptions"].get("soundboard") or {}).get("default") or {}
    table = None
    for a in data["beforeLoopActions"]:
        for e in a.get("saveValueInCache", []) or []:
            if e.get("name") == "captureSound":
                table = e["value"]
    if not table:
        fails.append("no captureSound table")
    else:
        if sorted(table) != ["P", "R", "S"]:
            fails.append(f"captureSound must cover R/P/S, got {sorted(table)}")
        for kind, alias in table.items():
            if not alias.startswith("soundboard."):
                fails.append(f"captureSound[{kind}] {alias!r} lacks the soundboard. prefix")
            elif alias.split(".", 1)[1] not in board:
                fails.append(f"captureSound[{kind}] {alias!r} is not on the soundboard")
        if len(set(board.values())) != len(board):
            fails.append("two capture sounds point at the same file")

    heard = set()
    for a in actions():
        payload = a.get("payload") or {}
        preset, comp = payload.get("preset") or {}, payload.get("computed") or {}
        if "sounds.list" not in preset and "sounds.list" not in comp:
            continue
        if "sounds.list" in comp:
            if "captureSound" not in json.dumps(comp["sounds.list"]):
                fails.append("the capture sound must be chosen by capturing piece")
            heard.add("capture")
        else:
            for s in preset["sounds.list"]:
                if not s.startswith("soundboard."):
                    fails.append(f"sound {s!r} lacks the soundboard. prefix")
                elif s.split(".", 1)[1] not in board:
                    fails.append(f"sound {s!r} is not on the soundboard")
                heard.add(s.split(".", 1)[1])
        if not any(k.startswith("playList.") for k in (payload.get("cached") or {})):
            fails.append(f"{a['key']} plays a sound with no playList audience")
        if preset.get("sounds.waitForSoundEnd") is not False:
            fails.append("sounds must not block the turn "
                         "(sounds.waitForSoundEnd: false)")
    # Every move is audible: a quiet one clicks, a capture plays its piece.
    for need in ("move", "capture"):
        if need not in heard:
            fails.append(f"no {need} sound is played on a move")

    # Team ids stay lowercase because they key decks, buckets and lookups —
    # but nothing a player reads should say "blue" or "red" in lower case.
    visible = {"text", "header", "question", "title", "label", "summary"}
    internal = {"($1)($2)", "taken_($1)", "piece_($1)_($2)", "($1)_($2)_($3)"}

    def scan(o, path=""):
        if isinstance(o, dict):
            for k, v in o.items():
                if k in visible and isinstance(v, str) and v not in internal \
                        and re.search(r"\b(blue|red)\b", v):
                    fails.append(f"lowercase team name in {path}.{k}: {v[:70]!r}")
                if k == "format" and isinstance(v, str) and v not in internal \
                        and re.search(r"\b(blue|red)\b", v):
                    fails.append(f"lowercase team name in a format string: {v[:70]!r}")
                scan(v, f"{path}.{k}")
        elif isinstance(o, list):
            for i, v in enumerate(o):
                scan(v, f"{path}[{i}]")

    scan(data)

    if "winnersInfo" in data:
        fails.append("winnersInfo is back — it is the other team lookup in the win "
                     "path and is unproven; only reinstate it once a corner-reach "
                     "win is confirmed working")
    teams = set(data["gameInitOptions"]["teams"])
    for key in data.get("winCondition", {}):
        if key not in teams:
            fails.append(f"winCondition key {key!r} is not a team id {sorted(teams)} — "
                         f"a mismatch here crashed the win with \"undefined "
                         f"(reading 'members')\"")

    # Score labels are emoji, not words. (Scoped to showScore formats — the
    # createDeck set is also called "pieces" and is not a label.)
    for a in actions():
        if a.get("key") != "showScore":
            continue
        fmt = ((a.get("payload") or {}).get("preset") or {}).get("format", "")
        if any(ch.isalpha() for ch in fmt):
            fails.append(f"showScore format {fmt!r} spells out a word; use an emoji")


def initial_state(data, fails):
    """The baked owner/ptype/sets the setup starts from, out of the gameLoop."""
    got = {}
    for g in data["gameLoop"]:
        for a in g.get("actions", []):
            for e in a.get("saveValueInCache", []) or []:
                if e.get("name") in ("owner", "ptype", "sets") and isinstance(e["value"], dict) \
                        and "selector" not in e["value"]:
                    got.setdefault(e["name"], e["value"])
    for k in ("owner", "ptype", "sets"):
        if k not in got:
            fails.append(f"baked initial {k!r} not found in the gameLoop")
    return got


def playouts(b, init, games, fails, seed=7):
    """Play random games the way the setup does — maintaining the six buckets
    and the empty-square list across every move — and check each resulting move
    set against the independent implementation. This is what proves the bucket
    bookkeeping stays in step with the board."""
    rng = random.Random(seed)
    nbrs, prey_of = b["neighbors"], b["preyOf"]
    all_cells = b["cells"]
    targets = {"blue": b["homeRed"], "red": b["homeBlue"]}
    outcomes = {"corner": 0, "trapped": 0, "capped": 0}
    total_plies = 0

    for _ in range(games):
        owner = dict(init["owner"])
        ptype = dict(init["ptype"])
        sets = {k: list(v) for k, v in init["sets"].items()}
        ref = {norm(c): (owner[c], ptype[c]) for c in owner}
        team = "blue"

        for _ply in range(400):
            total_plies += 1
            occupied = [c for v in sets.values() for c in v]
            empty_cells = [c for c in all_cells if c not in set(occupied)]

            # The buckets must still describe the same board the move log does.
            if sorted(occupied) != sorted(owner):
                fails.append(f"buckets drifted from the board: {sorted(occupied)[:6]} "
                             f"vs {sorted(owner)[:6]}")
                return outcomes, total_plies

            mine = [c for k, v in sets.items() if k.startswith(team) for c in v]
            moves = {}
            for c in mine:
                dests = table_legal(sets, empty_cells, c, team, ptype[c], nbrs, prey_of)
                ref_dests = sorted(denorm(x) for x in ref_legal(ref, norm(c)))
                if dests != ref_dests:
                    fails.append(f"move mismatch for {team} {ptype[c]} on {c}: "
                                 f"setup says {dests}, rules say {ref_dests}")
                    return outcomes, total_plies
                if dests:
                    moves[c] = dests
            if not moves:
                outcomes["trapped"] += 1
                break
            frm = rng.choice(sorted(moves))
            to = rng.choice(moves[frm])

            # Apply exactly as the setup does: capture empties one bucket, then
            # the mover leaves one square of its own bucket and joins another.
            if to in owner:
                sets[owner[to] + ptype[to]].remove(to)
                del owner[to], ptype[to]
            moved = ptype[frm]
            sets[team + moved].remove(frm)
            sets[team + moved].append(to)
            owner[to], ptype[to] = team, moved
            del owner[frm], ptype[frm]
            ref[norm(to)] = ref[norm(frm)]
            del ref[norm(frm)]

            if to == targets[team]:
                outcomes["corner"] += 1
                break
            team = "red" if team == "blue" else "blue"
        else:
            outcomes["capped"] += 1
    return outcomes, total_plies


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, default=400)
    args = ap.parse_args()

    path = os.path.join(REPO, "game_jsons", "intransitive.json")
    data = json.load(open(path))
    fails = []

    structural(data, fails)
    presentation(data, fails)
    b = tables(data, fails)
    init = initial_state(data, fails)
    if b is not None:
        cards_deck(data, b, fails)
    if b is not None and len(init) == 3:
        outcomes, plies = playouts(b, init, args.games, fails)
        print(f"played {args.games} random games, {plies} plies")
        print(f"  won by reaching a corner : {outcomes['corner']}")
        print(f"  won by trapping          : {outcomes['trapped']}")
        print(f"  hit the 400-ply cap      : {outcomes['capped']}")

    if fails:
        print(f"\n✗ {len(fails)} problem(s):", file=sys.stderr)
        for f in fails:
            print("   -", f, file=sys.stderr)
        sys.exit(1)
    print("\n✓ tables, opening position and move generation all match the published rules")


if __name__ == "__main__":
    main()
