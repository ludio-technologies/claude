"""Generate the Cops & Robbers Ludio game JSON.

Output: ~/LudioCode/game_jsons/cops_and_robbers.json

Run: python3 gen_cnr_game.py
"""
import json
from pathlib import Path

ROOT = Path("/Users/ankitbuddhiraju/LudioCode")
OUTPUT = ROOT / "game_jsons" / "cops_and_robbers.json"
IMAGES_JSON = ROOT / "scripts" / "cnr_images.json"

# =================================================================
# Constants
# =================================================================

COLORS = {
    "red":    "e53935",
    "blue":   "2e5ba8",
    "green":  "2e8b57",
    "black":  "000000",
    "brown":  "8b4513",
    "grey":   "808080",
    "purple": "6a0dad",
    "orange": "ff8c00",
}

# Robber role tuples: (role_id / slug, display_name, color_key, emoji).
ROBBERS = [
    ("red",   "Tomato Tornado 🟥",     "red",   "🟥"),
    ("blue",  "Blueberry Bandito 🟦",  "blue",  "🟦"),
    ("green", "Pickle Plunderer 🟩",   "green", "🟩"),
]

# Cop role tuples: (role_id, display_name, color_key, priority_index)
COPS = [
    ("cop_black",  "Officer Inkwell",      "black",  1),
    ("cop_brown",  "Detective Donut",      "brown",  2),
    ("cop_grey",   "Officer Overcast",     "grey",   3),
    ("cop_purple", "Detective Royal-Pain", "purple", 4),
    ("cop_orange", "Officer Sherbet",      "orange", 5),
]

# Player count -> ((rows, cols), num_robbers, num_cops).
# Grids are landscape: rows are the short dim, cols the long dim.
PLAYER_CONFIG = {
    3: ((6, 9),  1, 2),
    4: ((6, 9),  1, 3),
    5: ((6, 10), 2, 3),
    6: ((6, 10), 2, 4),
    7: ((7, 10), 3, 4),
    8: ((7, 10), 3, 5),
}

# Max bounding box across all shapes — used to size precomputed adjacency
# tables and the universe of cell fake-roles / cell decks.
MAX_COLS = 10   # letters A..J
MAX_ROWS = 7    # rows 1..7

GRID_SHAPES = [(6, 9), (6, 10), (7, 10)]

# Total game length per shape (replaces the old per-robber 15-move timer).
GAME_TURNS = {
    (6, 9):  30,
    (6, 10): 35,
    (7, 10): 40,
}

# Cop deployment rectangle (rows × cols) per shape — centered.
COP_DEPLOY = {
    (6, 9):  (2, 3),
    (6, 10): (2, 4),
    (7, 10): (3, 4),
}

# Every TRAIL_RESET_PERIOD turns: clear visited lists + repaint labels.
TRAIL_RESET_PERIOD = 10

# =================================================================
# Cell coordinate helpers
# =================================================================

def cell(c: int, r: int) -> str:
    """Convert 0-indexed (col, row) -> 'A1' style coordinate."""
    return f"{chr(ord('A')+c)}{r+1}"


def parse(coord: str) -> tuple[int, int]:
    return ord(coord[0]) - ord('A'), int(coord[1:]) - 1


def all_cells(cols: int, rows: int) -> list[str]:
    """Row-major cell list for a (cols × rows) grid (top-left to bottom-right)."""
    return [cell(c, r) for r in range(rows) for c in range(cols)]


def in_bounds(c: int, r: int, cols: int, rows: int) -> bool:
    return 0 <= c < cols and 0 <= r < rows


# =================================================================
# Preset maps
# Each map: central deployment zone, water cells, house blocks
# =================================================================

def _cop_center(rows: int, cols: int) -> list[str]:
    """Centered cop deployment rectangle for this shape."""
    drows, dcols = COP_DEPLOY[(rows, cols)]
    r0 = (rows - drows) // 2
    c0 = (cols - dcols) // 2
    return [cell(c, r) for r in range(r0, r0 + drows) for c in range(c0, c0 + dcols)]


# Each preset map carries:
#   central — cop deployment cells (auto-derived from COP_DEPLOY)
#   water   — 2 sections, each with min dim ≥3
#   houses  — 4 building blocks, each with min dim ≥3
# All terrain features are placed outside the central zone. Houses can sit
# inside stash corners (cells stay reachable), water cannot (water cells are
# excluded from stash eligibility).
PRESET_MAPS = {
    # 6 rows × 9 cols
    (6, 9): {
        "central": _cop_center(6, 9),
        "water": [
            # top edge between corners (1×3)
            "D1", "E1", "F1",
            # bottom-mid L (cols D-F × rows 5-6, bounding box 2×3)
            "D5", "D6", "E6", "F6",
        ],
        "houses": [
            ["A1", "B1", "C1"],   # TL row 1 — 1×3
            ["G1", "H1", "I1"],   # TR row 1 — 1×3
            ["A4", "A5", "A6"],   # left edge bottom — 3×1
            ["I4", "I5", "I6"],   # right edge bottom — 3×1
        ],
    },
    # 6 rows × 10 cols
    (6, 10): {
        "central": _cop_center(6, 10),
        "water": [
            "D1", "E1", "F1", "G1",   # top edge mid — 1×4
            "D6", "E6", "F6", "G6",   # bottom edge mid — 1×4
        ],
        "houses": [
            ["A1", "B1", "C1"],   # TL row 1
            ["H1", "I1", "J1"],   # TR row 1
            ["A4", "A5", "A6"],   # left edge bottom — 3×1
            ["J4", "J5", "J6"],   # right edge bottom — 3×1
        ],
    },
    # 7 rows × 10 cols
    (7, 10): {
        "central": _cop_center(7, 10),
        "water": [
            "D1", "E1", "F1", "G1",   # top edge mid — 1×4
            "D7", "E7", "F7", "G7",   # bottom edge mid — 1×4
        ],
        "houses": [
            ["A1", "B1", "C1"],   # TL row 1
            ["H1", "I1", "J1"],   # TR row 1
            ["A5", "A6", "A7"],   # left edge bottom — 3×1
            ["J5", "J6", "J7"],   # right edge bottom — 3×1
        ],
    },
}


def stash_corners(rows: int, cols: int) -> dict[str, list[str]]:
    """Each stash quadrant is a 2-row × 3-col rectangle hugging a corner."""
    return {
        "TL": [cell(c, r) for r in range(2)         for c in range(3)],
        "TR": [cell(c, r) for r in range(2)         for c in range(cols - 3, cols)],
        "BL": [cell(c, r) for r in range(rows - 2, rows) for c in range(3)],
        "BR": [cell(c, r) for r in range(rows - 2, rows) for c in range(cols - 3, cols)],
    }


def stash_eligibility(rows: int, cols: int) -> dict[str, list[str]]:
    """Per-corner stash candidates — corner rectangle minus water cells."""
    m = PRESET_MAPS[(rows, cols)]
    excluded = set(m["water"])
    return {q: [c for c in cells if c not in excluded]
            for q, cells in stash_corners(rows, cols).items()}


# =================================================================
# Cell adjacency precomputation (for max grid)
# =================================================================

def neighbors_4(coord: str, cols: int, rows: int) -> list[str]:
    c, r = parse(coord)
    out = []
    for dc, dr in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
        nc, nr = c + dc, r + dr
        if in_bounds(nc, nr, cols, rows):
            out.append(cell(nc, nr))
    return out


def neighbors_8(coord: str, cols: int, rows: int) -> list[str]:
    c, r = parse(coord)
    out = []
    for dc in (-1, 0, 1):
        for dr in (-1, 0, 1):
            if dc == 0 and dr == 0:
                continue
            nc, nr = c + dc, r + dr
            if in_bounds(nc, nr, cols, rows):
                out.append(cell(nc, nr))
    return out


def cop_destinations(coord: str, cols: int, rows: int) -> list[str]:
    """Cells reachable in 0-2 orthogonal moves (4-dir), self included."""
    c, r = parse(coord)
    reachable = {coord}
    for dc, dr in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
        nc, nr = c + dc, r + dr
        if in_bounds(nc, nr, cols, rows):
            reachable.add(cell(nc, nr))
    for dc1, dr1 in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
        for dc2, dr2 in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nc, nr = c + dc1 + dc2, r + dr1 + dr2
            if in_bounds(nc, nr, cols, rows):
                reachable.add(cell(nc, nr))
    return sorted(reachable)


def jack_reach_2(coord: str, cols: int, rows: int) -> list[str]:
    """Cells reachable in 0-2 steps of 8-direction movement (Chebyshev <= 2).
    Used by the Robber's Getaway Car special card."""
    c, r = parse(coord)
    reachable = set()
    for dc in (-2, -1, 0, 1, 2):
        for dr in (-2, -1, 0, 1, 2):
            nc, nr = c + dc, r + dr
            if in_bounds(nc, nr, cols, rows):
                reachable.add(cell(nc, nr))
    return sorted(reachable)


def probe_targets(coord: str, cols: int, rows: int) -> list[str]:
    """Cell + 4 ortho neighbors (legal probe/bust targets)."""
    return sorted({coord} | set(neighbors_4(coord, cols, rows)))


# =================================================================
# Helpers for action JSON
# =================================================================

def cached(name): return {"type": "cached", "value": name}
def preset(value): return {"type": "preset", "value": value}
def computed(sel): return {"type": "computed", "value": sel}

def cached_p(name, value):   return {"name": name, "type": "cached", "value": value}
def preset_p(name, value):   return {"name": name, "type": "preset", "value": value}
def computed_p(name, sel):   return {"name": name, "type": "computed", "value": sel}

def sel(selector_name, *params):
    out = {"selector": selector_name}
    if params:
        out["params"] = list(params)
    return out

def empty_action(*items):
    return {"key": "emptyAction", "saveValueInCache": list(items)}

def cache(name, value):
    return {"name": name, "value": value}


# =================================================================
# Build sections
# =================================================================

def build_images() -> dict:
    images = json.loads(IMAGES_JSON.read_text())
    # add the static art
    images["transparent"] = {
        "url": "https://res.cloudinary.com/liars-club/image/upload/transparent_sbx4wv.png"
    }
    images["wallpaper"] = {
        # Dark rainy alley — noir/Cops-&-Robbers vibe (Pexels-licensed image
        # uploaded to our Cloudinary).
        "url": "https://res.cloudinary.com/liars-club/image/upload/images/cnr/wallpaper.jpg"
    }
    images["banner"] = {
        # Composite: handcuffs (cops) + money bag (robbers) on noir bg, with title.
        "url": "https://res.cloudinary.com/liars-club/image/upload/images/cnr/banner.png"
    }
    images["central_bg"] = {
        # Soft yellow paper-ish texture used as the central widget background
        # and the player-hand background.
        "url": "https://res.cloudinary.com/liars-club/image/upload/yellow_background_gxts9c.jpg"
    }
    images["winner"] = {
        "url": "https://res.cloudinary.com/liars-club/image/upload/winner_h5eyfr.gif"
    }
    return images


def build_teams() -> dict:
    return {
        "robbers": {
            "id": "robbers",
            "name": "Robbers",
            "description": "The criminal gang",
            # Dark "rogue" brown — distinct from any individual Robber color
            # (red / blue / green) so videoboxes and chips stay readable.
            "color": "#2a1810",
            "roles": [r[0] for r in ROBBERS],
        },
        "cops": {
            "id": "cops",
            "name": "Cops",
            "description": "The investigators",
            # Cops team — dark navy.
            "color": "#0d1b3d",
            "roles": [c[0] for c in COPS],
        },
        "all": {
            "id": "all",
            "name": "All",
            "description": "All players",
            "color": "#666666",
            "roles": ["player"],
        },
    }


def build_roles() -> list:
    """All roles: 1 generic + 3 robbers + 5 cops + 64 cell fake-roles."""
    roles = []

    # Generic default role
    roles.append({
        "roleInfo": {
            "id": "player",
            "name": "Player",
            "description": "Awaiting role assignment.",
            "avatar": "https://res.cloudinary.com/liars-club/image/upload/card_player_ed7jck.webp",
            "team": "all",
            "prefix": "a ",
        },
        "isDefaultRole": True,
        "isRequired": False,
    })

    # Robber roles
    for slug, name, color_key, _emoji in ROBBERS:
        roles.append({
            "roleInfo": {
                "id": slug,
                "name": name,
                "description": f"You are the {name}! Hit your 4 stashes without getting busted.",
                "avatar": f"https://res.cloudinary.com/liars-club/image/upload/images/cnr/robber_{color_key}.png",
                "team": "robbers",
                "prefix": "the ",
            },
            "isDefaultRole": False,
            "isRequired": False,
        })

    # Cop roles
    for slug, name, color_key, _prio in COPS:
        roles.append({
            "roleInfo": {
                "id": slug,
                "name": name,
                "description": f"You are the {name}! Investigate cells, find clues, and bust the robbers.",
                "avatar": f"https://res.cloudinary.com/liars-club/image/upload/images/cnr/cop_{color_key}.png",
                "team": "cops",
                "prefix": "the ",
            },
            "isDefaultRole": False,
            "isRequired": False,
        })

    # Cell fake roles
    for coord in all_cells(MAX_COLS, MAX_ROWS):
        roles.append({
            "roleInfo": {
                "id": f"cell_{coord}",
                "name": coord,
                "description": f"You are at cell {coord}.",
                "avatar": "https://res.cloudinary.com/liars-club/image/upload/transparent_sbx4wv.png",
                "team": "all",
                "prefix": "at ",
            },
            "isDefaultRole": False,
            "isRequired": False,
        })

    return roles


def build_game_init_options() -> dict:
    return {
        "allowRecorder": False,
        "allowSpectatorBecomePlayer": False,
        "allowPlayerBecomeSpectator": False,
        "roleConfirmation": False,
        "useDefaultRoles": True,
        "minPlayers": 3,
        "maxPlayers": 8,
        "timePerRound": 5,
        "preferredPlayersQnt": [4, 6, 8],
        "teams": build_teams(),
        "roles": build_roles(),
        "rolesPreset": {},
        "images": build_images(),
        "animations": {
            "winner": "https://lottie.host/ae7f6864-0454-4f5b-9d5d-598a8234f4b4/P4YrwOR8gd.json",
        },
        "soundboard": {
            "default": {
                "reminder": "https://res.cloudinary.com/liars-club/video/upload/audio/reminder.mp4",
                "clap":     "https://res.cloudinary.com/liars-club/video/upload/audio/polite_clap.mp3",
                "failure":  "https://res.cloudinary.com/liars-club/video/upload/audio/sad_music.mp3",
                "success":  "https://res.cloudinary.com/liars-club/video/upload/audio/avalon/sounds/success.mp3",
            }
        },
        "notChangeLayoutAfterGame": True,
    }


def build_visual_settings() -> dict:
    return {
        "isCardAnimationsOff": True,
        "increaseHandHeight":  True,
        "cardHandBackgroundImage": "https://res.cloudinary.com/liars-club/image/upload/yellow_background_gxts9c.jpg",
    }


# =================================================================
# beforeLoopActions — large
# =================================================================

def build_before_loop_actions() -> list:
    actions = []

    # ----- 1. changeBackground (wallpaper) -----
    actions.append({
        "key": "changeBackground",
        "payload": {"preset": {"image": "wallpaper"}},
    })

    # ----- 2. Initial cache -----
    actions.append(empty_action(
        cache("players", sel("allPlayers")),
        cache("numPlayers", sel("listLength", computed_p("list", sel("allPlayers")))),
        # Canonical host snippet (uses 'players.0' dotted-path shorthand)
        cache("host", sel("ifElse",
            computed_p("condition", sel("contains",
                cached_p("list", "players"),
                computed_p("element", sel("getHostPlayerId")),
            )),
            computed_p("thenValue", sel("createList",
                computed_p("arg1", sel("getHostPlayerId")),
            )),
            computed_p("elseValue", sel("createList",
                cached_p("arg1", "players.0"),
            )),
        )),
        # Grid shape is rows × cols (landscape: cols is the long dim).
        cache("gridRows", 6),
        cache("gridCols", 9),
        cache("numRobbers", 1),
        cache("maxTurns", 30),
        cache("gameOver", False),
        cache("robbersWin", False),
        cache("tutorial", True),
        cache("learners", []),
        cache("turnNumber", 0),
        # Cells whose label has been publicly revealed by a Cop investigation;
        # cleared every TRAIL_RESET_PERIOD turns.
        cache("investigatedCells", []),
        # ── Per-player STATE keyed by player ID. Canonical source of truth
        # for the refactored stages — populated by repeat blocks iterating
        # activeRobbers / activeCops.
        cache("posByPlayer", {}),
        cache("visitedByPlayer", {}),
        cache("stashesByPlayer", {}),
        cache("stashesRemainingByPlayer", {}),
        cache("stashesHitByPlayer", {}),
        cache("bustedByPlayer", {}),
        cache("oldPosByPlayer", {}),
        # ── Per-player constant LISTS indexed by slot number in
        # activeRobbers/activeCops. The Nth active player gets the Nth
        # color/emoji/role. Adding a slot = one entry in each.
        cache("robberColors",     [f"#{COLORS[c]}" for _slug, _name, c, _emoji in ROBBERS]),
        cache("robberColorNames", [c                for _slug, _name, c, _emoji in ROBBERS]),
        cache("robberEmojis",     [emoji            for _slug, _name, _c, emoji in ROBBERS]),
        cache("robberRoles",      [slug             for slug,  _name, _c, _emoji in ROBBERS]),
        cache("robberNames",      [name             for _slug, name,  _c, _emoji in ROBBERS]),
        cache("copColors",        [f"#{COLORS[c]}" for _slug, _name, c, _prio in COPS]),
        cache("copColorNames",    [c                for _slug, _name, c, _prio in COPS]),
        cache("copRoles",         [slug             for slug,  _name, _c, _prio in COPS]),
        cache("copNames",         [name             for _slug, name,  _c, _prio in COPS]),
        # Per-shape terrain caches — actually overwritten below by exactly one
        # of the shape-gated empty_actions, but pre-init as [] here so the
        # validator's contains-list check stays clean and any selector that
        # reads them before the shape gate fires won't see undefined.
        cache("centralCells", []),
        cache("waterCells", []),
        cache("houseBlocks", []),
        cache("quadrant_TL", []),
        cache("quadrant_TR", []),
        cache("quadrant_BL", []),
        cache("quadrant_BR", []),
        cache("validCells", []),
        cache("gridCells", []),
        # Every coord in the MAX grid — drives the iter-0 repeat block that
        # creates the cell decks and the per-turn label recompute.
        cache("cellNames", all_cells(MAX_COLS, MAX_ROWS)),
    ))

    # ----- 2a. Welcome notification (Roundabout/Enigma/Spectrum pattern). -----
    actions.append({
        "key": "createNotification",
        "payload": {
            "preset": {
                "header": "Welcome to Cops & Robbers!",
                "image": "banner",
                "duration": 8,
                "backgroundColor": "#1c3a5e",
                "borderColor": "white",
                "textColor": "white",
            },
            "cached": {"to": "players"},
            "computed": {
                "text": sel("formatString",
                    preset_p("format", "<b>($1)</b> - in a moment, tell me whether you want Ludio to teach your group how to play Cops & Robbers!"),
                    computed_p("arg1", sel("listToString",
                        computed_p("list", sel("getPlayerNamesByIds",
                            cached_p("ids", "host"),
                        )),
                    )),
                ),
            },
        },
    })

    # ----- 2b. Tutorial mode vote (host picks who needs tutorial) -----
    actions.append({
        "key": "createMixVote",
        "payload": {
            "preset": {
                "title": "Tutorial mode",
                "terminationCondition": "get_all_votes",
                "showResultInRealTime": True,
                "showResultDuration": 2,
                "showResultDelay": 0,
                "point.allowFewerAnswers": True,
                "point.terminationCondition": "get_all_votes",
                "poll.answersQuantity": 1,
                "poll.targets": ["Everybody!", "Nobody!"],
                "oneClick": True,
                "allowRevoting": True,
                "pollVoteTargetsOptions": {
                    "Everybody!": {
                        "icon": "https://res.cloudinary.com/liars-club/image/upload/icons/like.svg",
                        "backgroundColor": "#D3D3D3",
                        "boxIconColor": "#D3D3D3",
                        "textColor": "black",
                        "widgetIconColor": "green"
                    },
                    "Nobody!": {
                        "icon": "https://res.cloudinary.com/liars-club/image/upload/icons/dislike.svg",
                        "backgroundColor": "#D3D3D3",
                        "boxIconColor": "#D3D3D3",
                        "textColor": "black",
                        "widgetIconColor": "red"
                    }
                },
                "poll.terminationCondition": "get_all_votes",
                "backgroundColor": "#1c3a5e",
                "borderColor": "white",
                "textColor": "white",
            },
            "cached": {
                "actors": "host",
                "point.targets": "players",
                "point.answersQuantity": "numPlayers",
            },
            "computed": {
                "question": {
                    "selector": "formatString",
                    "params": [
                        preset_p("format", "($1), who needs the tutorial? Click on the players or select from the middle."),
                        computed_p("arg1", sel("getPlayerNameById",
                            cached_p("id", "host.0"),
                        )),
                    ],
                }
            }
        },
        "saveValueInCache": [
            cache("voteResult", sel("getCachedValue",
                preset_p("name", "lastActionResult.voteResult"),
            )),
            cache("learners", sel("ifElse",
                computed_p("condition", sel("contains",
                    cached_p("list", "players"),
                    cached_p("element", "voteResult.0"),
                )),
                cached_p("thenValue", "voteResult"),
                computed_p("elseValue", sel("ifElse",
                    computed_p("condition", sel("contains",
                        cached_p("list", "voteResult"),
                        preset_p("element", "Everybody!"),
                    )),
                    cached_p("thenValue", "players"),
                    preset_p("elseValue", []),
                )),
            )),
            cache("tutorial", sel("greaterThan",
                computed_p("arg1", sel("listLength",
                    cached_p("list", "learners"),
                )),
                preset_p("arg2", 0),
            )),
        ],
    })

    # ----- 3. Pick (gridRows, gridCols, numRobbers, maxTurns) from numPlayers.
    #   3-4 → 6×9,  1 robber,  30 turns
    #   5-6 → 6×10, 2 robbers, 35 turns
    #   7-8 → 7×10, 3 robbers, 40 turns
    def _by_player_count(small, mid, big):
        return sel("ifElse",
            computed_p("condition", sel("lessThanOrEqual",
                cached_p("arg1", "numPlayers"),
                preset_p("arg2", 4),
            )),
            preset_p("thenValue", small),
            computed_p("elseValue", sel("ifElse",
                computed_p("condition", sel("lessThanOrEqual",
                    cached_p("arg1", "numPlayers"),
                    preset_p("arg2", 6),
                )),
                preset_p("thenValue", mid),
                preset_p("elseValue", big),
            )),
        )

    actions.append(empty_action(
        cache("gridRows",   _by_player_count(6, 6, 7)),
        cache("gridCols",   _by_player_count(9, 10, 10)),
        cache("numRobbers", _by_player_count(1, 2, 3)),
        cache("maxTurns",   _by_player_count(GAME_TURNS[(6, 9)],
                                              GAME_TURNS[(6, 10)],
                                              GAME_TURNS[(7, 10)])),
    ))

    # ----- 4. Initial vertical layout (will be re-set with team split after role assignment) -----
    actions.append({
        "key": "changeLayout",
        "payload": {
            "preset": {
                "type": "HIGHLIGHT",
                "direction": "VERTICAL",
                "percent": 65,
            },
            "cached": {
                "top": "players",
            }
        }
    })

    # NOTE: Cell deck creation is in gameLoop iter 0 (a repeat block over cellNames),
    # because cell decks need labelInspectors=activeRobbers — which doesn't exist
    # until role assignment runs at the end of beforeLoopActions.

    # Precompute adjacency tables for every cell in the MAX grid (10×7).
    # The runtime clips these to the active shape by intersecting with validCells.
    max_cells = all_cells(MAX_COLS, MAX_ROWS)
    eight_neighbors = {c: neighbors_8(c, MAX_COLS, MAX_ROWS) for c in max_cells}
    cop_reach_map   = {c: cop_destinations(c, MAX_COLS, MAX_ROWS) for c in max_cells}
    jack_reach_map  = {c: jack_reach_2(c, MAX_COLS, MAX_ROWS) for c in max_cells}
    probe_map       = {c: probe_targets(c, MAX_COLS, MAX_ROWS) for c in max_cells}
    actions.append(empty_action(
        cache("eightNeighbors", eight_neighbors),
        cache("copReach", cop_reach_map),
        cache("jackReach2", jack_reach_map),
        cache("probeTargets", probe_map),
    ))

    # Per-player videobox decks (used as playCards target for Cop actions)
    actions.append({
        "key": "createVideoboxDecks",
        "payload": {
            "preset": {"cardback": "transparent"},
            "cached": {"players": "players"},
        }
    })

    # Per-robber private hand deck — created via createDeck from cnr_cards.
    # The set used depends on robber count: solo Robber gets 2 of each special
    # (set: specials_solo), multi-Robber gives each Robber 1 of each (set: specials_each).
    for slug, _name, _color, _emoji in ROBBERS:
        idx = ROBBERS.index((slug, _name, _color, _emoji))
        skip_inactive = [sel(
            "lessThanOrEqual",
            cached_p("arg1", "numRobbers"),
            preset_p("arg2", idx),
        )]
        # Solo: 2 of each special movement
        actions.append({
            "key": "createDeck",
            "payload": {
                "preset": {
                    "name": "cnr_cards",
                    "customName": f"hand_{slug}",
                    "set": "specials_solo",
                }
            },
            "skipCondition": [
                skip_inactive[0],
                sel("greaterThan", cached_p("arg1", "numRobbers"), preset_p("arg2", 1)),
            ],
        })
        # Multi-Robber: 1 of each special movement
        actions.append({
            "key": "createDeck",
            "payload": {
                "preset": {
                    "name": "cnr_cards",
                    "customName": f"hand_{slug}",
                    "set": "specials_each",
                }
            },
            "skipCondition": [
                skip_inactive[0],
                sel("equals", cached_p("arg1", "numRobbers"), preset_p("arg2", 1)),
            ],
        })

    # Per-robber used heist kit deck (public discard pile for special cards)
    for slug, _name, _color, _emoji in ROBBERS:
        actions.append({
            "key": "createCustomDeck",
            "payload": {
                "preset": {
                    "name": f"used_kit_{slug}",
                    "public": True,
                    "emptyImage": "transparent",
                }
            }
        })

    # Per-robber Pass card deck: every active Robber gets exactly 1 Pass card.
    for slug, _name, _color, _emoji in ROBBERS:
        idx = ROBBERS.index((slug, _name, _color, _emoji))
        skip_inactive = [sel(
            "lessThanOrEqual",
            cached_p("arg1", "numRobbers"),
            preset_p("arg2", idx),
        )]
        actions.append({
            "key": "createDeck",
            "skipCondition": skip_inactive,
            "payload": {
                "preset": {
                    "name": "cnr_cards",
                    "customName": f"pass_{slug}",
                    "set": "pass_card",
                }
            }
        })

    # Per-cop hand: 2 action cards (Investigate + Bust) via createDeck
    for slug, _name, _color, _prio in COPS:
        idx = COPS.index((slug, _name, _color, _prio))
        skip_inactive = [sel(
            "greaterThanOrEqual",
            computed_p("arg1", sel("add",
                cached_p("arg1", "numRobbers"),
                preset_p("arg2", idx),
            )),
            cached_p("arg2", "numPlayers"),
        )]
        actions.append({
            "key": "createDeck",
            "payload": {
                "preset": {
                    "name": "cnr_cards",
                    "customName": f"cophand_{slug}",
                    "set": "cop_actions",
                }
            },
            "skipCondition": skip_inactive,
        })

    # NOTE: Widget mount, terrain highlighting, and initial counter row paint
    # all moved to gameLoop iter-0 stages (because they depend on cell decks
    # existing, which now happens in iter 0).

    # Preset map data caches (NOT moved — these don't depend on cell decks and
    # are consumed by downstream beforeLoopActions like stash randomization).
    for (rows, cols), m in PRESET_MAPS.items():
        skip = [sel(
            "logicalNOT",
            computed_p("arg", sel("logicalAND",
                computed_p("arg1", sel("equals",
                    cached_p("arg1", "gridRows"),
                    preset_p("arg2", rows),
                )),
                computed_p("arg2", sel("equals",
                    cached_p("arg1", "gridCols"),
                    preset_p("arg2", cols),
                )),
            )),
        )]
        eligibility = stash_eligibility(rows, cols)
        # cell -> list of cells in same house block (empty if cell isn't in a block)
        cell_to_house = {}
        for c in all_cells(cols, rows):
            cell_to_house[c] = []
            for block in m["houses"]:
                if c in block:
                    cell_to_house[c] = list(block)
                    break
        actions.append(empty_action(
            cache("centralCells", m["central"]),
            cache("waterCells", m["water"]),
            cache("houseBlocks", m["houses"]),
            cache("quadrant_TL", eligibility["TL"]),
            cache("quadrant_TR", eligibility["TR"]),
            cache("quadrant_BL", eligibility["BL"]),
            cache("quadrant_BR", eligibility["BR"]),
            cache("validCells", [c for c in all_cells(cols, rows) if c not in m["water"]]),
            # Every coord in the active grid regardless of terrain — used to clip
            # the MAX-grid precomputed adjacency lists.
            cache("gridCells", all_cells(cols, rows)),
            # cell -> list of cells in same house block (for Backstreet card)
            cache("cellToHouseBlock", cell_to_house),
        ))
        actions[-1]["skipCondition"] = skip

    # ----- 9. Host picks volunteers as Robbers (replaces the old shuffle) -----
    # Single target_point vote: host selects exactly numRobbers players from the
    # roster. Result is a list of player IDs we destructure into the Robber slots
    # below; the leftover players become Cops via listsSubtract.
    actions.append({
        "key": "createVote",
        "payload": {
            "preset": {
                "title": "Pick the Robbers",
                "type": "target_point",
                "terminationCondition": "get_all_votes",
                "showResultInRealTime": True,
                "showResultDuration": 2,
                "showResultDelay": 0,
                "allowRevoting": True,
                "allowFewerAnswers": False,
                "oneClick": True,
                "vertical": True,
                "backgroundColor": "#1c3a5e",
                "borderColor": "white",
                "textColor": "white",
            },
            "cached": {
                "actors": "host",
                "targets": "players",
                "answersQuantity": "numRobbers",
            },
            "computed": {
                "question": sel("formatString",
                    preset_p("format", "($1), pick ($2) player(s) to be the Robbers — everyone else will be a Cop."),
                    computed_p("arg1", sel("getPlayerNameById",
                        cached_p("id", "host.0"),
                    )),
                    cached_p("arg2", "numRobbers"),
                ),
            },
        },
        "saveValueInCache": [
            cache("chosenRobbers", sel("getCachedValue",
                preset_p("name", "lastActionResult.voteResult"),
            )),
            cache("chosenCops", sel("listsSubtract",
                cached_p("list1", "players"),
                computed_p("list2", sel("getCachedValue",
                    preset_p("name", "lastActionResult.voteResult"),
                )),
            )),
        ],
    })

    # ──────────────────────────────────────────────────────────────────
    # NOTE: All per-player setup (role assignment, highlighting, layout,
    # showRole, deck creation, stash randomization, card dealing, setup
    # picks) is now in iter-0 stages — see build_iter0_setup_stages().
    # That setup iterates activeRobbers / activeCops via Ludio `repeat`
    # blocks rather than codegen-time Python loops with skipConditions.
    # ──────────────────────────────────────────────────────────────────

    # The shared stash_pool deck (3 copies of every cell) is created HERE
    # since it's a singleton (not per-player); the per-Robber dealing happens
    # in iter-0.
    actions.append({
        "key": "createDeck",
        "payload": {
            "preset": {
                "name": "cnr_cards",
                "customName": "stash_pool",
                "set": "cells_3x",
            }
        }
    })

    return actions




def _shape_skip(rows: int, cols: int):
    """Skip-condition fragment: skip unless the active shape matches (rows, cols)."""
    return sel("logicalNOT",
        computed_p("arg", sel("logicalAND",
            computed_p("arg1", sel("equals",
                cached_p("arg1", "gridRows"),
                preset_p("arg2", rows),
            )),
            computed_p("arg2", sel("equals",
                cached_p("arg1", "gridCols"),
                preset_p("arg2", cols),
            )),
        )),
    )


def build_iter0_setup_stages() -> list:
    """Iter-0 stages — all game setup runs HERE (not in beforeLoopActions),
    structured as a sequence of single-stage repeat blocks that iterate
    activeRobbers / activeCops. beforeLoopActions stays flat with only the
    one-shot global setup (initial cache, tutorial vote, host vote, etc.).

    Order:
      1. Assign Robber + Cop roles (repeat over chosenRobbers / chosenCops).
      2. Cache activeRobbers / activeCops via getPlayersFromTeam.
      3. Role confirmation.
      4. Highlight Robbers + Cops (repeat over each team, color from list).
      5. Re-layout with teams + showRole.
      6. Create per-Robber decks: hand_<colorName>, pass_<colorName>, used_kit_<colorName>.
      7. Create per-Cop decks: cophand_<colorName>.
      8. Create cell decks (existing).
      9. Mount widget + terrain (existing).
     10. Stash randomization (repeat over activeRobbers, writes to dicts).
     11. Deal stash + hand + pass to Robbers (repeat).
     12. Show Robber hands cooperatively.
     13. Deal Cop hands (repeat).
     14. Setup picks — Robbers + Cops (repeat over each team).
    """
    iter0_skip_only = [sel("greaterThan",
        cached_p("arg1", "gameLoopIndex"),
        preset_p("arg2", 0),
    )]
    stages = []

    def _iter0_stage(name, actions, repeat_over=None, extra_skip=None, check_win=False):
        skip = list(iter0_skip_only)
        if extra_skip is not None:
            skip.append(extra_skip)
        stage = {
            "name": name,
            "skipCondition": skip,
            "actions": actions,
            "nextGroupNonStop": True,
        }
        if repeat_over is not None:
            stage["repeat"] = {"qnt": sel("listLength", cached_p("list", repeat_over))}
        if check_win:
            stage["checkWinCondition"] = True
        return stage

    # 1a. Assign Robber roles. chosenRobbers / robberRoles are parallel lists:
    #     Nth chosen player gets Nth role id.
    stages.append(_iter0_stage("Assign Robber roles", [
        empty_action(
            cache("currentPlayer", sel("selectElement",
                cached_p("list", "chosenRobbers"),
                cached_p("index", "repeatIndex"),
            )),
            cache("currentRole", sel("selectElement",
                cached_p("list", "robberRoles"),
                cached_p("index", "repeatIndex"),
            )),
        ),
        {
            "key": "setRole",
            "payload": {
                "cached": {"roleId": "currentRole", "playerId": "currentPlayer"},
            }
        },
    ], repeat_over="chosenRobbers"))

    # 1b. Assign Cop roles.
    stages.append(_iter0_stage("Assign Cop roles", [
        empty_action(
            cache("currentPlayer", sel("selectElement",
                cached_p("list", "chosenCops"),
                cached_p("index", "repeatIndex"),
            )),
            cache("currentRole", sel("selectElement",
                cached_p("list", "copRoles"),
                cached_p("index", "repeatIndex"),
            )),
        ),
        {
            "key": "setRole",
            "payload": {
                "cached": {"roleId": "currentRole", "playerId": "currentPlayer"},
            }
        },
    ], repeat_over="chosenCops"))

    # 2. Cache activeRobbers / activeCops from team membership.
    stages.append(_iter0_stage("Cache active team lists", [
        empty_action(
            cache("activeRobbers", sel("getPlayersFromTeam",
                preset_p("teamId", "robbers"),
            )),
            cache("activeCops", sel("getPlayersFromTeam",
                preset_p("teamId", "cops"),
            )),
        ),
    ]))

    # 3. Role confirmation — each player sees their role card.
    stages.append(_iter0_stage("Role confirmation", [{"key": "roleConfirmation"}]))

    # 4a. Highlight Robbers — Nth Robber gets Nth color.
    stages.append(_iter0_stage("Highlight Robbers", [
        _set_current_robber(),
        {
            "key": "highlightPlayers",
            "payload": {
                "cached": {"color": "currentColor"},
                "computed": {
                    "listOfPlayers": sel("createList",
                        cached_p("arg1", "currentPlayer"),
                    ),
                },
            }
        },
    ], repeat_over="activeRobbers"))

    # 4b. Highlight Cops.
    stages.append(_iter0_stage("Highlight Cops", [
        _set_current_cop(),
        {
            "key": "highlightPlayers",
            "payload": {
                "cached": {"color": "currentColor"},
                "computed": {
                    "listOfPlayers": sel("createList",
                        cached_p("arg1", "currentPlayer"),
                    ),
                },
            }
        },
    ], repeat_over="activeCops"))

    # 5a. Re-layout with team split (cops on top, robbers on bottom).
    stages.append(_iter0_stage("Re-layout with teams", [{
        "key": "changeLayout",
        "payload": {
            "preset": {
                "type": "HIGHLIGHT",
                "direction": "VERTICAL",
                "percent": 65,
            },
            "cached": {
                "top":    "activeCops",
                "bottom": "activeRobbers",
            }
        }
    }]))

    # 5b. Show all roles to all players (cooperative).
    stages.append(_iter0_stage("Show all roles", [{
        "key": "showRole",
        "payload": {
            "cached": {"from": "players", "to": "players"},
        }
    }]))

    # 6. Create per-Robber decks: hand_<colorName>, pass_<colorName>, used_kit_<colorName>.
    #    Set name on hand_<colorName> depends on numRobbers (specials_solo for
    #    a lone Robber, specials_each for multi-Robber).
    stages.append(_iter0_stage("Create Robber decks", [
        _set_current_robber(),
        # hand_<colorName>
        {
            "key": "createDeck",
            "payload": {
                "preset": {"name": "cnr_cards"},
                "computed": {
                    "customName": sel("formatString",
                        preset_p("format", "hand_($1)"),
                        cached_p("arg1", "currentColorName"),
                    ),
                    "set": sel("ifElse",
                        computed_p("condition", sel("equals",
                            cached_p("arg1", "numRobbers"),
                            preset_p("arg2", 1),
                        )),
                        preset_p("thenValue", "specials_solo"),
                        preset_p("elseValue", "specials_each"),
                    ),
                },
            },
        },
        # pass_<colorName>
        {
            "key": "createDeck",
            "payload": {
                "preset": {"name": "cnr_cards", "set": "pass_card"},
                "computed": {
                    "customName": sel("formatString",
                        preset_p("format", "pass_($1)"),
                        cached_p("arg1", "currentColorName"),
                    ),
                },
            },
        },
        # used_kit_<colorName> — public discard pile, no source script.
        {
            "key": "createCustomDeck",
            "payload": {
                "preset": {"public": True, "emptyImage": "transparent"},
                "computed": {
                    "name": sel("formatString",
                        preset_p("format", "used_kit_($1)"),
                        cached_p("arg1", "currentColorName"),
                    ),
                },
            },
        },
    ], repeat_over="activeRobbers"))

    # 7. Create per-Cop decks: cophand_<colorName>.
    stages.append(_iter0_stage("Create Cop decks", [
        _set_current_cop(),
        {
            "key": "createDeck",
            "payload": {
                "preset": {"name": "cnr_cards", "set": "cop_actions"},
                "computed": {
                    "customName": sel("formatString",
                        preset_p("format", "cophand_($1)"),
                        cached_p("arg1", "currentColorName"),
                    ),
                },
            },
        },
    ], repeat_over="activeCops"))

    # 8. Cell decks — repeat over the 70 max-grid coords; labelInspectors uses
    # the just-populated activeRobbers list.
    stages.append({
        "name": "Create cell decks",
        "skipCondition": iter0_skip_only,
        "repeat": {"qnt": MAX_COLS * MAX_ROWS},
        "actions": [{
            "key": "createCustomDeck",
            "payload": {
                "preset": {
                    "public": True,
                    "inspectDeck": True,
                    "inspectLabel": True,
                },
                "cached": {"labelInspectors": "activeRobbers"},
                "computed": {
                    "name": sel("selectElement",
                        cached_p("list", "cellNames"),
                        cached_p("index", "repeatIndex"),
                    ),
                    "emptyImage": sel("formatString",
                        preset_p("format", "coord_($1)"),
                        computed_p("arg1", sel("selectElement",
                            cached_p("list", "cellNames"),
                            cached_p("index", "repeatIndex"),
                        )),
                    ),
                },
            }
        }],
        "nextGroupNonStop": True,
    })

    # 9a. Mount widget — one stage per grid shape (gated by gridRows/gridCols).
    for (rows, cols) in GRID_SHAPES:
        stages.append({
            "name": f"Mount widget {rows}x{cols}",
            "skipCondition": iter0_skip_only + [_shape_skip(rows, cols)],
            "actions": [{
                "key": "createGenericCardWidget",
                "payload": {
                    "preset": {
                        "ratio": "1",
                        # Ludio reads dimensions as [rows, cols] — row count first.
                        "dimensions": [rows, cols],
                        "decks": all_cells(cols, rows),
                        "cardback": "transparent",
                        "backgroundImage": "central_bg",
                    }
                }
            }],
            "nextGroupNonStop": True,
        })

    # 9b. Terrain — one stage per grid shape.
    HOUSE_COLOR = "#E9D77A"
    WATER_COLOR = "#9CD3EA"
    for (rows, cols), m in PRESET_MAPS.items():
        terrain_actions = []
        if m["water"]:
            terrain_actions.append({
                "key": "highlightDecks",
                "payload": {
                    "preset": {"color": WATER_COLOR, "decks": list(m["water"])}
                }
            })
        all_house_cells = [c for block in m["houses"] for c in block]
        if all_house_cells:
            terrain_actions.append({
                "key": "highlightDecks",
                "payload": {
                    "preset": {"color": HOUSE_COLOR, "decks": all_house_cells}
                }
            })
        stages.append({
            "name": f"Terrain {rows}x{cols}",
            "skipCondition": iter0_skip_only + [_shape_skip(rows, cols)],
            "actions": terrain_actions,
            "nextGroupNonStop": True,
        })

    # 10. Stash randomization — Nth Robber gets 4 random cells (one per corner
    #     quadrant). Writes to stashesByPlayer + initializes the other per-player
    #     dicts (visited/busted/stashesHit).
    stages.append(_iter0_stage("Stash randomization", [
        _set_current_robber(),
        empty_action(cache("currentStashes", sel("createList",
            computed_p("arg1", sel("randomElement", cached_p("list", "quadrant_TL"))),
            computed_p("arg2", sel("randomElement", cached_p("list", "quadrant_TR"))),
            computed_p("arg3", sel("randomElement", cached_p("list", "quadrant_BL"))),
            computed_p("arg4", sel("randomElement", cached_p("list", "quadrant_BR"))),
        ))),
        empty_action(
            cache("stashesByPlayer", sel("setCachedObjectFieldValue",
                preset_p("objectName", "stashesByPlayer"),
                cached_p("fieldName", "currentPlayer"),
                cached_p("value", "currentStashes"),
            )),
            cache("visitedByPlayer", sel("setCachedObjectFieldValue",
                preset_p("objectName", "visitedByPlayer"),
                cached_p("fieldName", "currentPlayer"),
                preset_p("value", []),
            )),
            cache("bustedByPlayer", sel("setCachedObjectFieldValue",
                preset_p("objectName", "bustedByPlayer"),
                cached_p("fieldName", "currentPlayer"),
                preset_p("value", False),
            )),
            cache("stashesHitByPlayer", sel("setCachedObjectFieldValue",
                preset_p("objectName", "stashesHitByPlayer"),
                cached_p("fieldName", "currentPlayer"),
                preset_p("value", 1),
            )),
        ),
    ], repeat_over="activeRobbers"))

    # 11. Deal stash + special movement + pass cards to each active Robber.
    stages.append(_iter0_stage("Deal Robber cards", [
        _set_current_robber(),
        # Deal 4 stash coord cards from the shared stash_pool (cardNames =
        # this Robber's stashesByPlayer entry).
        {
            "key": "dealDeck",
            "payload": {
                "preset": {"deck": "stash_pool", "qnt": 1, "sortBy": "weight"},
                "cached": {"targets": "currentPlayer"},
                "computed": {
                    "cardNames": sel("getCachedObjectValue",
                        preset_p("objectName", "stashesByPlayer"),
                        cached_p("value", "currentPlayer"),
                        preset_p("defaultValue", []),
                    ),
                },
            },
        },
        # Deal Special Movement cards from hand_<colorName>.
        {
            "key": "dealDeck",
            "payload": {
                "preset": {"sortBy": "weight"},
                "cached": {"targets": "currentPlayer"},
                "computed": {
                    "deck": sel("formatString",
                        preset_p("format", "hand_($1)"),
                        cached_p("arg1", "currentColorName"),
                    ),
                },
            },
        },
        # Deal 1 Pass card from pass_<colorName>.
        {
            "key": "dealDeck",
            "payload": {
                "preset": {"qnt": 1, "sortBy": "weight"},
                "cached": {"targets": "currentPlayer"},
                "computed": {
                    "deck": sel("formatString",
                        preset_p("format", "pass_($1)"),
                        cached_p("arg1", "currentColorName"),
                    ),
                },
            },
        },
    ], repeat_over="activeRobbers"))

    # 12. Show Robber hands cooperatively to the Robber team.
    stages.append(_iter0_stage("Show Robber hands", [{
        "key": "showHand",
        "payload": {
            "cached": {"from": "activeRobbers", "to": "activeRobbers"},
        }
    }]))

    # 13. Deal each Cop their action cards (Investigate + Bust) from
    #     cophand_<colorName>.
    stages.append(_iter0_stage("Deal Cop cards", [
        _set_current_cop(),
        {
            "key": "dealDeck",
            "payload": {
                "cached": {"targets": "currentPlayer"},
                "computed": {
                    "deck": sel("formatString",
                        preset_p("format", "cophand_($1)"),
                        cached_p("arg1", "currentColorName"),
                    ),
                },
            },
        },
    ], repeat_over="activeCops"))

    # 14a. Setup picks — Robbers pick starting stash.
    stages.append(_iter0_stage("Setup picks — Robbers", [
        _set_current_robber(),
        empty_action(cache("currentStashes", sel("getCachedObjectValue",
            preset_p("objectName", "stashesByPlayer"),
            cached_p("value", "currentPlayer"),
            preset_p("defaultValue", []),
        ))),
        {
            "key": "selectCentralWidgetDeck",
            "payload": {
                "preset": {
                    "duration": 60,
                    "neededVotes": 1,
                    "terminationCondition": "get_needed_votes",
                },
                "cached": {
                    "actors": "currentPlayer",
                    "decks": "currentStashes",
                },
                "computed": {
                    "question": sel("formatString",
                        preset_p("format", "($1), pick your starting stash (one of your 4)."),
                        cached_p("arg1", "currentRobberName"),
                    ),
                },
            },
            "saveValueInCache": [
                cache("currentPos", sel("selectElement",
                    computed_p("list", sel("getObjectValues",
                        cached_p("obj", "lastActionResult"),
                    )),
                    preset_p("index", 0),
                )),
            ],
        },
        # Update posByPlayer.
        empty_action(cache("posByPlayer", sel("setCachedObjectFieldValue",
            preset_p("objectName", "posByPlayer"),
            cached_p("fieldName", "currentPlayer"),
            cached_p("value", "currentPos"),
        ))),
        # Drop a stash card on the starting cell.
        {
            "key": "createCard",
            "payload": {
                "preset": {
                    "ratio": 1.0,
                    "textColor": "white",
                    "fontHeightPercentage": 25,
                },
                "cached": {
                    "deck": "currentPos",
                    "background": "currentColor",
                    "cardText": "currentEmoji",
                },
                "computed": {
                    "image": sel("formatString",
                        preset_p("format", "stash_($1)"),
                        cached_p("arg1", "currentColorName"),
                    ),
                },
            },
        },
        # Seed visited + stashesRemaining for this Robber.
        empty_action(
            cache("visitedByPlayer", sel("setCachedObjectFieldValue",
                preset_p("objectName", "visitedByPlayer"),
                cached_p("fieldName", "currentPlayer"),
                computed_p("value", sel("createList", cached_p("arg1", "currentPos"))),
            )),
            cache("stashesRemainingByPlayer", sel("setCachedObjectFieldValue",
                preset_p("objectName", "stashesRemainingByPlayer"),
                cached_p("fieldName", "currentPlayer"),
                computed_p("value", sel("listsSubtract",
                    cached_p("list1", "currentStashes"),
                    computed_p("list2", sel("createList", cached_p("arg1", "currentPos"))),
                )),
            )),
        ),
        # ✓-mark the starting stash coord card in this Robber's hand.
        *mark_stash_visited_actions_dict(),
        # Show fake-role badge (cell_<coord>) on this Robber's videobox.
        {
            "key": "showFakeRole",
            "payload": {
                "cached": {"from": "currentPlayer", "to": "activeRobbers"},
                "computed": {
                    "roleId": sel("formatString",
                        preset_p("format", "cell_($1)"),
                        cached_p("arg1", "currentPos"),
                    ),
                }
            }
        },
    ], repeat_over="activeRobbers"))

    # 14b. Setup picks — Cops pick deployment cell.
    stages.append(_iter0_stage("Setup picks — Cops", [
        _set_current_cop(),
        {
            "key": "selectCentralWidgetDeck",
            "payload": {
                "preset": {
                    "duration": 30,
                    "neededVotes": 1,
                    "terminationCondition": "get_needed_votes",
                },
                "cached": {
                    "actors": "currentPlayer",
                    "decks": "centralCells",
                },
                "computed": {
                    "question": sel("formatString",
                        preset_p("format", "($1), pick your starting cell in the central zone."),
                        cached_p("arg1", "currentCopName"),
                    ),
                },
            },
            "saveValueInCache": [
                cache("currentPos", sel("selectElement",
                    computed_p("list", sel("getObjectValues",
                        cached_p("obj", "lastActionResult"),
                    )),
                    preset_p("index", 0),
                )),
            ],
        },
        # Update posByPlayer with chosen cell.
        empty_action(cache("posByPlayer", sel("setCachedObjectFieldValue",
            preset_p("objectName", "posByPlayer"),
            cached_p("fieldName", "currentPlayer"),
            cached_p("value", "currentPos"),
        ))),
        # Drop a cop-figure card on the chosen cell. Card name is
        # cop_<colorName>_figure (same name format used downstream by
        # cop_apply_moves_stage).
        {
            "key": "createCard",
            "payload": {
                "preset": {
                    "ratio": 1.0,
                    "textColor": "white",
                    "fontHeightPercentage": 30,
                },
                "cached": {
                    "deck": "currentPos",
                    "background": "currentColor",
                },
                "computed": {
                    "name": sel("formatString",
                        preset_p("format", "cop_($1)_figure"),
                        cached_p("arg1", "currentColorName"),
                    ),
                    "image": sel("formatString",
                        preset_p("format", "cop_($1)"),
                        cached_p("arg1", "currentColorName"),
                    ),
                    "cardText": sel("substring",
                        computed_p("text", sel("getPlayerNameById",
                            cached_p("id", "currentPlayer"),
                        )),
                        preset_p("start", 0),
                        preset_p("end", 3),
                    ),
                },
            },
        },
    ], repeat_over="activeCops"))

    return stages


# =================================================================
# gameLoop, winCondition — stubs for v1
# =================================================================









# =================================================================
# Per-turn label recompute selectors
# Each cell's label is "($1)($2)" — ($1) shows the current occupier
# ("[emoji] |" or ●) and ($2) shows the visited-this-window emojis.
# Investigated cells drop ($1) and show only ($2).
# Used in the recompute stage (over cellNames via repeatIndex) where
# `currentCell` is the per-iteration coord.
# =================================================================

def _robber_active_cond(i: int):
    return sel("greaterThan",
        cached_p("arg1", "numRobbers"),
        preset_p("arg2", i),
    )


def _player_at_slot(i: int):
    """Selector returning activeRobbers[i] — the player ID at robber slot i.
    Use this everywhere a label selector needs to address the Nth active Robber
    instead of touching slug-keyed cache vars."""
    return sel("selectElement",
        cached_p("list", "activeRobbers"),
        preset_p("index", i),
    )


def _emoji_at_slot(i: int):
    """Selector returning robberEmojis[i] — the color emoji assigned to robber
    slot i (these are stored as a cached list at the start of the game)."""
    return sel("selectElement",
        cached_p("list", "robberEmojis"),
        preset_p("index", i),
    )


def _per_robber_emoji_concat(predicate_factory):
    """Build a formatString selector that concatenates the slot-i robber's emoji
    when `predicate_factory(i)` evaluates to true, else ''. Iterates the max
    robber-slot count (len(ROBBERS)); each slot is gated by an active-check on
    numRobbers, so inactive slots contribute nothing."""
    args = []
    for i in range(len(ROBBERS)):
        args.append(computed_p(f"arg{i+1}", sel("ifElse",
            computed_p("condition", sel("logicalAND",
                computed_p("arg1", _robber_active_cond(i)),
                computed_p("arg2", predicate_factory(i)),
            )),
            computed_p("thenValue", _emoji_at_slot(i)),
            preset_p("elseValue", ""),
        )))
    return sel("formatString",
        preset_p("format", "($1)($2)($3)"),
        *args,
    )


def label_stash_selector():
    """Selector for ($1) on private cells: 'ST.<emojis>' if currentCell is in
    any active Robber's stash list (looked up via stashesByPlayer dict), else ''."""
    emojis = _per_robber_emoji_concat(
        lambda i: sel("contains",
            computed_p("list", sel("getCachedObjectValue",
                preset_p("objectName", "stashesByPlayer"),
                computed_p("value", _player_at_slot(i)),
                preset_p("defaultValue", []),
            )),
            cached_p("element", "currentCell"),
        )
    )
    return sel("ifElse",
        computed_p("condition", sel("equals",
            computed_p("arg1", emojis),
            preset_p("arg2", ""),
        )),
        preset_p("thenValue", ""),
        computed_p("elseValue", sel("formatString",
            preset_p("format", "ST.($1)"),
            computed_p("arg1", emojis),
        )),
    )


def label_here_selector():
    """Selector for ($2) on private cells: '|<emojis>' for every active Robber
    whose current pos (via posByPlayer dict) equals currentCell."""
    emojis = _per_robber_emoji_concat(
        lambda i: sel("equals",
            computed_p("arg1", sel("getCachedObjectValue",
                preset_p("objectName", "posByPlayer"),
                computed_p("value", _player_at_slot(i)),
                preset_p("defaultValue", ""),
            )),
            cached_p("arg2", "currentCell"),
        )
    )
    return sel("ifElse",
        computed_p("condition", sel("equals",
            computed_p("arg1", emojis),
            preset_p("arg2", ""),
        )),
        preset_p("thenValue", ""),
        computed_p("elseValue", sel("formatString",
            preset_p("format", "|($1)"),
            computed_p("arg1", emojis),
        )),
    )


def label_history_selector():
    """Selector for the investigated-cell label: concatenated emojis of every
    active Robber whose visited list (via visitedByPlayer dict) contains
    currentCell."""
    return _per_robber_emoji_concat(
        lambda i: sel("contains",
            computed_p("list", sel("getCachedObjectValue",
                preset_p("objectName", "visitedByPlayer"),
                computed_p("value", _player_at_slot(i)),
                preset_p("defaultValue", []),
            )),
            cached_p("element", "currentCell"),
        )
    )


def label_combined_selector():
    """Cell label per the new spec:
      • Private (not in investigatedCells) → '($1)($2)' where
            ($1) = 'ST.<emojis>'   if a stash, else ''
            ($2) = '|<emojis>'     if any Robber is here, else ''
        Visible only to activeRobbers (labelInspectors).
      • Investigated → emojis of Robbers whose visited_<slug> contains
        currentCell (history). Visible to everyone."""
    return sel("ifElse",
        computed_p("condition", sel("contains",
            cached_p("list", "investigatedCells"),
            cached_p("element", "currentCell"),
        )),
        computed_p("thenValue", label_history_selector()),
        computed_p("elseValue", sel("formatString",
            preset_p("format", "($1)($2)"),
            computed_p("arg1", label_stash_selector()),
            computed_p("arg2", label_here_selector()),
        )),
    )


def recompute_labels_stage(name: str = "Recompute labels"):
    """Stage: repeat over every cell in cellNames; for each cell that's part
    of the active grid, call setDeckLabel with the recomputed value."""
    in_grid = sel("contains",
        cached_p("list", "gridCells"),
        cached_p("element", "currentCell"),
    )
    return {
        "name": name,
        "skipCondition": [sel("getCachedValue", preset_p("name", "gameOver"))],
        "repeat": {"qnt": MAX_COLS * MAX_ROWS},
        "actions": [
            empty_action(cache("currentCell", sel("selectElement",
                cached_p("list", "cellNames"),
                cached_p("index", "repeatIndex"),
            ))),
            {
                "key": "setDeckLabel",
                "skipCondition": [sel("logicalNOT", computed_p("arg", in_grid))],
                "payload": {
                    "cached": {"deck": "currentCell"},
                    "computed": {"label": label_combined_selector()},
                },
            },
        ],
        "nextGroupNonStop": True,
    }


def _trail_reset_skip():
    """Trail reset stages all share this gate: turnNumber > 0 AND turnNumber % N == 0,
    plus the usual gameOver short-circuit."""
    return [sel("logicalOR",
        computed_p("arg1", sel("getCachedValue", preset_p("name", "gameOver"))),
        computed_p("arg2", sel("logicalNOT",
            computed_p("arg", sel("logicalAND",
                computed_p("arg1", sel("greaterThan",
                    cached_p("arg1", "turnNumber"),
                    preset_p("arg2", 0),
                )),
                computed_p("arg2", sel("equals",
                    computed_p("arg1", sel("remainder",
                        cached_p("arg1", "turnNumber"),
                        preset_p("arg2", TRAIL_RESET_PERIOD),
                    )),
                    preset_p("arg2", 0),
                )),
            )),
        )),
    )]


def trail_reset_state_stage():
    """Stage 1 of the trail reset: clear visited + investigatedCells, fire the
    notification. The per-cell inspector reset lives in a sibling stage so the
    repeat block can iterate cellNames."""
    return {
        "name": "Trail reset (every 10 turns)",
        "skipCondition": _trail_reset_skip(),
        "actions": [
            empty_action(
                # Wipe every player's footprints by resetting the whole dict.
                cache("visitedByPlayer", {}),
                cache("investigatedCells", []),
            ),
            {
                "key": "createNotification",
                "payload": {
                    "preset": {
                        "header": "Trail wiped",
                        "text": "10 turns elapsed — every Robber's footprints have cleared. Cops, start your search again.",
                        "duration": 6,
                        "backgroundColor": "#1c3a5e",
                        "borderColor": "white",
                        "textColor": "white",
                    },
                    "cached": {"to": "players"},
                }
            },
        ],
        "nextGroupNonStop": True,
    }


def trail_reset_inspectors_stage():
    """Stage 2 of the trail reset: repeat over every cellNames coord, and for
    cells inside the active grid restore labelInspectors=activeRobbers (so the
    previously-investigated cells become Robber-only again)."""
    in_grid = sel("contains",
        cached_p("list", "gridCells"),
        cached_p("element", "currentCell"),
    )
    return {
        "name": "Trail reset — restore inspectors",
        "skipCondition": _trail_reset_skip(),
        "repeat": {"qnt": MAX_COLS * MAX_ROWS},
        "actions": [
            empty_action(cache("currentCell", sel("selectElement",
                cached_p("list", "cellNames"),
                cached_p("index", "repeatIndex"),
            ))),
            {
                "key": "setLabelInspectors",
                "skipCondition": [sel("logicalNOT", computed_p("arg", in_grid))],
                "payload": {
                    "cached": {
                        "deck": "currentCell",
                        "labelInspectors": "activeRobbers",
                    },
                },
            },
        ],
        "nextGroupNonStop": True,
    }





# =================================================================
# Parallel-turn helpers (replace the original sequential per-Robber /
# per-Cop stages above). Each parallel block runs qnt iterations in
# parallel; spaIndex is bound to the current iteration. Per-player
# results are merged into shared cache dicts (playerToMoveChoice,
# playerToNextPos, playerToCopNextPos, playerToCopAction, playerToCopTarget)
# via setCachedObjectFieldValue, so downstream sequential stages can
# look up "what did THIS slug's player do?" by their player ID.
# =================================================================


def _spa_player(team_var: str):
    """Selector evaluating to the current parallel-iteration's player ID
    (the spaIndex-th entry of the given team list)."""
    return sel("selectElement",
        cached_p("list", team_var),
        cached_p("index", "spaIndex"),
    )


def _gameOver_skip():
    return [sel("getCachedValue", preset_p("name", "gameOver"))]


# =================================================================
# Per-iteration helpers for the refactored repeat-block stages.
# Inside a repeat block iterating active players, the FIRST action in
# the actions list should be one of these — they cache currentPlayer
# plus the matching color / emoji / name / colorName values from the
# parallel constant lists (robberColors, robberEmojis, etc.).
# =================================================================


def _set_current_robber():
    """First action of a repeat over activeRobbers — caches the per-iteration
    Robber's player ID and all the slot-indexed constants needed for downstream
    actions (color hex, color name for image lookups, emoji, display name)."""
    return empty_action(
        cache("currentPlayer", sel("selectElement",
            cached_p("list", "activeRobbers"),
            cached_p("index", "repeatIndex"),
        )),
        cache("currentColor", sel("selectElement",
            cached_p("list", "robberColors"),
            cached_p("index", "repeatIndex"),
        )),
        cache("currentColorName", sel("selectElement",
            cached_p("list", "robberColorNames"),
            cached_p("index", "repeatIndex"),
        )),
        cache("currentEmoji", sel("selectElement",
            cached_p("list", "robberEmojis"),
            cached_p("index", "repeatIndex"),
        )),
        cache("currentRobberName", sel("selectElement",
            cached_p("list", "robberNames"),
            cached_p("index", "repeatIndex"),
        )),
    )


def _set_current_cop():
    """First action of a repeat over activeCops — caches per-iteration Cop's
    player ID + slot-indexed constants (color hex, color name, display name)."""
    return empty_action(
        cache("currentPlayer", sel("selectElement",
            cached_p("list", "activeCops"),
            cached_p("index", "repeatIndex"),
        )),
        cache("currentColor", sel("selectElement",
            cached_p("list", "copColors"),
            cached_p("index", "repeatIndex"),
        )),
        cache("currentColorName", sel("selectElement",
            cached_p("list", "copColorNames"),
            cached_p("index", "repeatIndex"),
        )),
        cache("currentCopName", sel("selectElement",
            cached_p("list", "copNames"),
            cached_p("index", "repeatIndex"),
        )),
    )


def mark_stash_visited_actions_dict():
    """Dict-version of mark_stash_visited_actions. Reads per-iteration cache
    vars currentPlayer / currentColorName / currentPos to:
      1. Recall the coord card from this Robber's hand back into hand_<colorName>.
      2. Create a ✓-overlay card in hand_<colorName> using the original card's image.
      3. Deal the new ✓ card back to the Robber.
      4. Move the original card from hand_<colorName> back to stash_pool.

    Hand-deck name is computed via formatString('hand_($1)', currentColorName)."""
    hand_deck = sel("formatString",
        preset_p("format", "hand_($1)"),
        cached_p("arg1", "currentColorName"),
    )
    done_name = sel("formatString",
        preset_p("format", "($1)_done"),
        cached_p("arg1", "currentPos"),
    )
    return [
        {
            "key": "recallCards",
            "payload": {
                "cached": {"targets": "currentPlayer"},
                "computed": {
                    "deck": hand_deck,
                    "cardNames": sel("createList", cached_p("arg1", "currentPos")),
                },
            },
        },
        {
            "key": "createCard",
            "payload": {
                "preset": {
                    "cardText": "✓",
                    "textColor": "#1a8a3a",
                    "fontHeightPercentage": 50,
                    "enlargeOnHover": True,
                    "weight": 300,
                },
                "computed": {
                    "deck": hand_deck,
                    "name": done_name,
                    "cardImage": sel("getObjectField",
                        computed_p("obj", sel("selectElement",
                            computed_p("list", sel("getDeckCards",
                                computed_p("deck", hand_deck),
                            )),
                            preset_p("index", 0),
                        )),
                        preset_p("field", "image"),
                    ),
                },
            },
        },
        {
            "key": "dealDeck",
            "payload": {
                "preset": {"sortBy": "weight"},
                "cached": {"targets": "currentPlayer"},
                "computed": {
                    "deck": hand_deck,
                    "cardNames": sel("createList",
                        computed_p("arg1", done_name),
                    ),
                },
            },
        },
        {
            "key": "moveCards",
            "payload": {
                "preset": {
                    "type": "deck",
                    "to": "stash_pool",
                },
                "computed": {
                    "from": hand_deck,
                    "cardNames": sel("createList", cached_p("arg1", "currentPos")),
                },
            },
        },
    ]


# ----- Robber turn ------------------------------------------------


def robber_turn_init_stage():
    """Clear the per-turn parallel-results dicts before the card-pick block."""
    return {
        "name": "Init robber turn",
        "skipCondition": _gameOver_skip(),
        "actions": [
            empty_action(
                cache("playerToMoveChoice", {}),
                cache("playerToNextPos", {}),
            )
        ]
    }


def robber_pick_card_parallel_stage():
    """All active Robbers play their movement card (or Pass) simultaneously.
    Each iteration writes the chosen card name into playerToMoveChoice keyed
    by the acting Robber's player ID."""
    actor = _spa_player("activeRobbers")
    return {
        "name": "Robbers pick movement card",
        "skipCondition": _gameOver_skip(),
        "parallel": {
            "type": "smart",
            "qnt": sel("listLength", cached_p("list", "activeRobbers")),
        },
        "actions": [
            {
                "key": "playCards",
                "payload": {
                    "preset": {
                        "qnt": 1,
                        "duration": 30,
                        "oneClick": True,
                        "playable": "availableCards",
                        "playableInclude.cards": ["pass", "getaway", "backstreet", "speedboat"],
                        "sounds.list": ["soundboard.reminder"],
                        "sounds.waitForSoundEnd": False,
                    },
                    "computed": {
                        "actor": actor,
                        "target": sel("formatString",
                            preset_p("format", "videobox_($1)"),
                            computed_p("arg1", actor),
                        ),
                        "playList.0": sel("createList", computed_p("arg1", actor)),
                        "notification": sel("formatString",
                            preset_p("format", "Play Pass (then move normally) or play a Special card."),
                        ),
                    }
                },
                "postHandler": {
                    "handler": "playOneCardByName",
                    "params": [{"name": "name", "type": "preset", "value": "pass"}],
                },
                "saveValueInCache": [
                    # Inline the getCardField → setCachedObjectFieldValue chain so
                    # there's no shared scratch cache var (e.g. playedCardName) that
                    # parallel iterations could clobber. Each iteration's value
                    # selector now reads exclusively from its own lastActionResult.
                    {
                        "name": "playerToMoveChoice",
                        "value": sel("setCachedObjectFieldValue",
                            preset_p("objectName", "playerToMoveChoice"),
                            computed_p("fieldName", actor),
                            computed_p("value", sel("getCardField",
                                computed_p("cardId", sel("selectElement",
                                    computed_p("list", sel("getCachedValue",
                                        preset_p("name", "lastActionResult.cards"),
                                    )),
                                    preset_p("index", 0),
                                )),
                                preset_p("field", "name"),
                            )),
                        ),
                    },
                ],
            },
            # Hide this Robber's hand strip now that they've committed (mirrors
            # the Cop flow: cards close right after playCards, before the cell
            # pick UI shows up).
            {
                "key": "hidePlayersHands",
                "payload": {
                    "computed": {
                        "userIds": sel("createList", computed_p("arg1", actor)),
                    }
                }
            },
        ]
    }


def robber_process_cards_stage():
    """Single stage iterating all active Robbers. For each: pull played card
    name out of playerToMoveChoice (default 'pass'), then deal Pass back to
    hand OR move Special card to used_kit. Snapshots oldPosByPlayer for the
    fake-role transition in the upcoming apply-moves stage."""
    is_pass = sel("equals",
        cached_p("arg1", "currentChoice"),
        preset_p("arg2", "pass"),
    )
    not_pass = sel("logicalNOT", computed_p("arg", is_pass))
    videobox = sel("formatString",
        preset_p("format", "videobox_($1)"),
        cached_p("arg1", "currentPlayer"),
    )
    used_kit = sel("formatString",
        preset_p("format", "used_kit_($1)"),
        cached_p("arg1", "currentColorName"),
    )
    return {
        "name": "Process Robber cards",
        "skipCondition": _gameOver_skip(),
        "repeat": {"qnt": sel("listLength", cached_p("list", "activeRobbers"))},
        "actions": [
            _set_current_robber(),
            empty_action(cache("currentChoice", sel("getCachedObjectValue",
                preset_p("objectName", "playerToMoveChoice"),
                cached_p("value", "currentPlayer"),
                preset_p("defaultValue", "pass"),
            ))),
            # Pass → deal the videobox card back to this Robber's hand.
            {
                "key": "dealDeck",
                "skipCondition": [not_pass],
                "payload": {
                    "preset": {"sortBy": "weight"},
                    "cached": {"targets": "currentPlayer"},
                    "computed": {"deck": videobox},
                }
            },
            # Special → move the played card from videobox to used_kit.
            {
                "key": "moveCards",
                "skipCondition": [is_pass],
                "payload": {
                    "preset": {"type": "deck"},
                    "computed": {
                        "from": videobox,
                        "to": used_kit,
                    },
                }
            },
            # Snapshot old position into oldPosByPlayer for the fake-role
            # transition during apply-moves.
            empty_action(cache("oldPosByPlayer", sel("setCachedObjectFieldValue",
                preset_p("objectName", "oldPosByPlayer"),
                cached_p("fieldName", "currentPlayer"),
                computed_p("value", sel("getCachedObjectValue",
                    preset_p("objectName", "posByPlayer"),
                    cached_p("value", "currentPlayer"),
                    preset_p("defaultValue", ""),
                )),
            ))),
        ]
    }


def robber_compute_destination_decks_stage():
    """Zero robberToDestDecks + robberToCurrentPos before the per-robber fill
    stage. (Stage allows only one repeat block.)"""
    return {
        "name": "Precompute robber destination decks",
        "skipCondition": _gameOver_skip(),
        "actions": [
            empty_action(
                cache("robberToDestDecks", {}),
                cache("robberToCurrentPos", {}),
            ),
        ],
        "nextGroupNonStop": True,
    }


def robber_fill_destination_decks_stage():
    """Per-robber repeat: based on playerToMoveChoice[currentPlayer] and
    posByPlayer[currentPlayer], compute the destination decks for this Robber
    and write to robberToDestDecks[currentPlayer]."""
    robber_pos = sel("getCachedObjectValue",
        preset_p("objectName", "posByPlayer"),
        cached_p("value", "currentPlayer"),
        preset_p("defaultValue", ""),
    )
    choice = sel("getCachedObjectValue",
        preset_p("objectName", "playerToMoveChoice"),
        cached_p("value", "currentPlayer"),
        preset_p("defaultValue", "pass"),
    )
    eight = sel("getCachedObjectValue",
        preset_p("objectName", "eightNeighbors"),
        computed_p("value", robber_pos),
        preset_p("defaultValue", []),
    )
    on_water = sel("contains",
        cached_p("list", "waterCells"),
        computed_p("element", robber_pos),
    )
    normal_decks = sel("ifElse",
        computed_p("condition", on_water),
        computed_p("thenValue", sel("intersect",
            computed_p("list1", eight),
            cached_p("list2", "gridCells"),
        )),
        computed_p("elseValue", sel("intersect",
            computed_p("list1", eight),
            cached_p("list2", "validCells"),
        )),
    )
    getaway_decks = sel("intersect",
        computed_p("list1", sel("getCachedObjectValue",
            preset_p("objectName", "jackReach2"),
            computed_p("value", robber_pos),
            preset_p("defaultValue", []),
        )),
        cached_p("list2", "validCells"),
    )
    backstreet_decks = sel("append",
        computed_p("list", sel("intersect",
            computed_p("list1", sel("getCachedObjectValue",
                preset_p("objectName", "cellToHouseBlock"),
                computed_p("value", robber_pos),
                preset_p("defaultValue", []),
            )),
            cached_p("list2", "validCells"),
        )),
        computed_p("element", robber_pos),
    )
    adjacent_water = sel("intersect",
        computed_p("list1", eight),
        cached_p("list2", "waterCells"),
    )
    speedboat_decks = sel("ifElse",
        computed_p("condition", sel("greaterThan",
            computed_p("arg1", sel("listLength",
                computed_p("list", adjacent_water),
            )),
            preset_p("arg2", 0),
        )),
        computed_p("thenValue", adjacent_water),
        computed_p("elseValue", normal_decks),
    )

    decks_by_choice = sel("ifElse",
        computed_p("condition", sel("equals",
            computed_p("arg1", choice),
            preset_p("arg2", "getaway"),
        )),
        computed_p("thenValue", getaway_decks),
        computed_p("elseValue", sel("ifElse",
            computed_p("condition", sel("equals",
                computed_p("arg1", choice),
                preset_p("arg2", "backstreet"),
            )),
            computed_p("thenValue", backstreet_decks),
            computed_p("elseValue", sel("ifElse",
                computed_p("condition", sel("equals",
                    computed_p("arg1", choice),
                    preset_p("arg2", "speedboat"),
                )),
                computed_p("thenValue", speedboat_decks),
                computed_p("elseValue", normal_decks),
            )),
        )),
    )

    return {
        "name": "Fill robber destination decks",
        "skipCondition": _gameOver_skip(),
        "repeat": {"qnt": sel("listLength", cached_p("list", "activeRobbers"))},
        "actions": [
            _set_current_robber(),
            empty_action(
                cache("robberToDestDecks", sel("setCachedObjectFieldValue",
                    preset_p("objectName", "robberToDestDecks"),
                    cached_p("fieldName", "currentPlayer"),
                    computed_p("value", decks_by_choice),
                )),
                cache("robberToCurrentPos", sel("setCachedObjectFieldValue",
                    preset_p("objectName", "robberToCurrentPos"),
                    cached_p("fieldName", "currentPlayer"),
                    computed_p("value", robber_pos),
                )),
            ),
        ],
    }


def robber_pick_destination_parallel_stage():
    """Parallel: each active Robber picks a destination cell. The decks list
    AND the defaultSelect both come from precomputed dicts keyed by player ID
    (see robber_compute_destination_decks_stage). Writes the chosen cell into
    playerToNextPos[robber_id]."""
    actor = _spa_player("activeRobbers")
    return {
        "name": "Robbers move to destination",
        "skipCondition": _gameOver_skip(),
        "parallel": {
            "type": "smart",
            "qnt": sel("listLength", cached_p("list", "activeRobbers")),
        },
        "actions": [
            {
                "key": "selectCentralWidgetDeck",
                "payload": {
                    "preset": {
                        # IMPORTANT: do NOT set terminationCondition/neededVotes
                        # on a parallel selectCentralWidgetDeck — Ludio bug ends
                        # the whole parallel block when any single iteration
                        # completes. Just let duration time out per-iteration.
                        "duration": 60,
                        "sounds.list": ["soundboard.reminder"],
                        "sounds.waitForSoundEnd": False,
                    },
                    "computed": {
                        "actors": sel("createList", computed_p("arg1", actor)),
                        "decks": sel("getCachedObjectValue",
                            preset_p("objectName", "robberToDestDecks"),
                            computed_p("value", actor),
                            preset_p("defaultValue", []),
                        ),
                        "playList.0": sel("createList", computed_p("arg1", actor)),
                        "defaultSelect": sel("getCachedObjectValue",
                            preset_p("objectName", "robberToCurrentPos"),
                            computed_p("value", actor),
                            preset_p("defaultValue", ""),
                        ),
                        "question": sel("formatString",
                            preset_p("format", "Pick your destination cell."),
                        ),
                    }
                },
                "saveValueInCache": [
                    # No shared scratch — inline the lastActionResult lookup so
                    # parallel iterations can't clobber each other's values.
                    {
                        "name": "playerToNextPos",
                        "value": sel("setCachedObjectFieldValue",
                            preset_p("objectName", "playerToNextPos"),
                            computed_p("fieldName", actor),
                            computed_p("value", sel("selectElement",
                                computed_p("list", sel("getObjectValues",
                                    cached_p("obj", "lastActionResult"),
                                )),
                                preset_p("index", 0),
                            )),
                        ),
                    },
                ],
            }
        ]
    }


def robber_apply_moves_stage():
    """Single stage iterating all active Robbers. For each: pull destination
    from playerToNextPos, update posByPlayer / visitedByPlayer, slide fake-role
    badge, detect stash hit (and bump stashesHitByPlayer + lift robbersWin /
    gameOver if 4th stash), drop a stash card, notify the Robber team.

    Stage carries checkWinCondition: True — engine evaluates winCondition
    after the repeat finishes. If any Robber placed their 4th stash this turn,
    game ends immediately (before Cops act)."""
    not_hit = sel("logicalNOT", cached_p("arg", "currentHitStash"))
    skip_unless_hit = [not_hit]
    return {
        "name": "Apply Robber moves",
        "skipCondition": _gameOver_skip(),
        "checkWinCondition": True,
        "repeat": {"qnt": sel("listLength", cached_p("list", "activeRobbers"))},
        "actions": [
            _set_current_robber(),
            # currentPos = playerToNextPos[currentPlayer], default = previous pos.
            empty_action(cache("currentPos", sel("getCachedObjectValue",
                preset_p("objectName", "playerToNextPos"),
                cached_p("value", "currentPlayer"),
                computed_p("defaultValue", sel("getCachedObjectValue",
                    preset_p("objectName", "posByPlayer"),
                    cached_p("value", "currentPlayer"),
                    preset_p("defaultValue", ""),
                )),
            ))),
            # Update posByPlayer.
            empty_action(cache("posByPlayer", sel("setCachedObjectFieldValue",
                preset_p("objectName", "posByPlayer"),
                cached_p("fieldName", "currentPlayer"),
                cached_p("value", "currentPos"),
            ))),
            # Append currentPos to visitedByPlayer[currentPlayer].
            empty_action(cache("visitedByPlayer", sel("setCachedObjectFieldValue",
                preset_p("objectName", "visitedByPlayer"),
                cached_p("fieldName", "currentPlayer"),
                computed_p("value", sel("append",
                    computed_p("list", sel("getCachedObjectValue",
                        preset_p("objectName", "visitedByPlayer"),
                        cached_p("value", "currentPlayer"),
                        preset_p("defaultValue", []),
                    )),
                    cached_p("element", "currentPos"),
                )),
            ))),
            # Slide the fake-role badge.
            {
                "key": "hideRole",
                "payload": {
                    "cached": {"from": "currentPlayer", "to": "activeRobbers"},
                },
            },
            {
                "key": "showFakeRole",
                "payload": {
                    "cached": {"from": "currentPlayer", "to": "activeRobbers"},
                    "computed": {
                        "roleId": sel("formatString",
                            preset_p("format", "cell_($1)"),
                            cached_p("arg1", "currentPos"),
                        ),
                    },
                },
            },
            # Stash-hit detection.
            empty_action(cache("currentHitStash", sel("contains",
                computed_p("list", sel("getCachedObjectValue",
                    preset_p("objectName", "stashesRemainingByPlayer"),
                    cached_p("value", "currentPlayer"),
                    preset_p("defaultValue", []),
                )),
                cached_p("element", "currentPos"),
            ))),
            # Drop the stash card on the cell if hit. Background + image
            # picked from currentColor / currentColorName (per-iteration).
            {
                "key": "createCard",
                "skipCondition": skip_unless_hit,
                "payload": {
                    "preset": {
                        "ratio": "1",
                        "textColor": "white",
                        "fontHeightPercentage": 25,
                    },
                    "cached": {
                        "deck": "currentPos",
                        "background": "currentColor",
                        "cardText": "currentEmoji",
                    },
                    "computed": {
                        "image": sel("formatString",
                            preset_p("format", "stash_($1)"),
                            cached_p("arg1", "currentColorName"),
                        ),
                    },
                },
            },
            # ✓-mark the stash coord card in the Robber's hand.
            *[
                {**a, "skipCondition": skip_unless_hit}
                for a in mark_stash_visited_actions_dict()
            ],
            # Update stashesHitByPlayer + stashesRemainingByPlayer if hit.
            {
                **empty_action(
                    cache("stashesHitByPlayer", sel("setCachedObjectFieldValue",
                        preset_p("objectName", "stashesHitByPlayer"),
                        cached_p("fieldName", "currentPlayer"),
                        computed_p("value", sel("inc",
                            computed_p("arg", sel("getCachedObjectValue",
                                preset_p("objectName", "stashesHitByPlayer"),
                                cached_p("value", "currentPlayer"),
                                preset_p("defaultValue", 1),
                            )),
                        )),
                    )),
                    cache("stashesRemainingByPlayer", sel("setCachedObjectFieldValue",
                        preset_p("objectName", "stashesRemainingByPlayer"),
                        cached_p("fieldName", "currentPlayer"),
                        computed_p("value", sel("listsSubtract",
                            computed_p("list1", sel("getCachedObjectValue",
                                preset_p("objectName", "stashesRemainingByPlayer"),
                                cached_p("value", "currentPlayer"),
                                preset_p("defaultValue", []),
                            )),
                            computed_p("list2", sel("createList",
                                cached_p("arg1", "currentPos"),
                            )),
                        )),
                    )),
                ),
                "skipCondition": skip_unless_hit,
            },
            # Lift robbersWin / gameOver if this Robber's count now ≥ 4.
            empty_action(cache("currentHitCount", sel("getCachedObjectValue",
                preset_p("objectName", "stashesHitByPlayer"),
                cached_p("value", "currentPlayer"),
                preset_p("defaultValue", 1),
            ))),
            empty_action(
                cache("robbersWin", sel("logicalOR",
                    cached_p("arg1", "robbersWin"),
                    computed_p("arg2", sel("greaterThanOrEqual",
                        cached_p("arg1", "currentHitCount"),
                        preset_p("arg2", 4),
                    )),
                )),
                cache("gameOver", sel("logicalOR",
                    cached_p("arg1", "gameOver"),
                    computed_p("arg2", sel("greaterThanOrEqual",
                        cached_p("arg1", "currentHitCount"),
                        preset_p("arg2", 4),
                    )),
                )),
            ),
            # Confirm to Robber team only.
            {
                "key": "createNotification",
                "payload": {
                    "preset": {
                        "duration": 4,
                        "borderColor": "white",
                        "textColor": "white",
                    },
                    "cached": {
                        "to": "activeRobbers",
                        "backgroundColor": "currentColor",
                        "header": "currentRobberName",
                    },
                    "computed": {
                        "text": sel("formatString",
                            preset_p("format", "Moved to ($1). Turn ($2)/($3)."),
                            cached_p("arg1", "currentPos"),
                            cached_p("arg2", "turnNumber"),
                            cached_p("arg3", "maxTurns"),
                        )
                    }
                }
            },
        ]
    }


# ----- Cop turn ---------------------------------------------------


def cop_turn_init_stage():
    """Clear per-turn parallel-results dicts for the Cop phase."""
    return {
        "name": "Init cop turn",
        "skipCondition": _gameOver_skip(),
        "actions": [
            empty_action(
                cache("playerToCopNextPos", {}),
                cache("playerToCopAction", {}),
                cache("playerToCopTarget", {}),
            )
        ]
    }


def cop_compute_move_decks_stage():
    """Precompute each active Cop's move-pick reach via a repeat block. Writes
        copToMoveDecks[cop_id]    = intersect(copReach[posByPlayer[cop_id]], validCells)
        copToCurrentPos[cop_id]   = posByPlayer[cop_id]
    No Python loop / no per-slug skipConditions — the repeat iterates exactly
    the active cops via activeCops[repeatIndex]."""
    cop_pos = sel("getCachedObjectValue",
        preset_p("objectName", "posByPlayer"),
        cached_p("value", "currentPlayer"),
        preset_p("defaultValue", ""),
    )
    return {
        "name": "Precompute cop move decks",
        "skipCondition": _gameOver_skip(),
        "actions": [
            # Stage opens by zeroing the dicts (runs once before the inner repeat).
            empty_action(
                cache("copToMoveDecks", {}),
                cache("copToCurrentPos", {}),
            ),
            # ... but stages only support one `repeat` block. The inner per-cop
            # work has to live in a SEPARATE stage. We split into two: this
            # stage clears the dicts, the next stage fills them.
        ],
        "nextGroupNonStop": True,
    }


def cop_fill_move_decks_stage():
    """Sibling of cop_compute_move_decks_stage — the repeat block that fills
    copToMoveDecks + copToCurrentPos per active Cop."""
    cop_pos = sel("getCachedObjectValue",
        preset_p("objectName", "posByPlayer"),
        cached_p("value", "currentPlayer"),
        preset_p("defaultValue", ""),
    )
    return {
        "name": "Fill cop move decks",
        "skipCondition": _gameOver_skip(),
        "repeat": {"qnt": sel("listLength", cached_p("list", "activeCops"))},
        "actions": [
            _set_current_cop(),
            empty_action(
                cache("copToMoveDecks", sel("setCachedObjectFieldValue",
                    preset_p("objectName", "copToMoveDecks"),
                    cached_p("fieldName", "currentPlayer"),
                    computed_p("value", sel("intersect",
                        computed_p("list1", sel("getCachedObjectValue",
                            preset_p("objectName", "copReach"),
                            computed_p("value", cop_pos),
                            preset_p("defaultValue", []),
                        )),
                        cached_p("list2", "validCells"),
                    )),
                )),
                cache("copToCurrentPos", sel("setCachedObjectFieldValue",
                    preset_p("objectName", "copToCurrentPos"),
                    cached_p("fieldName", "currentPlayer"),
                    computed_p("value", cop_pos),
                )),
            ),
        ],
    }


def cop_move_parallel_stage():
    """Parallel: each active Cop picks a move destination. Decks come from the
    precomputed copToMoveDecks dict (see cop_compute_move_decks_stage)."""
    actor = _spa_player("activeCops")
    return {
        "name": "Cops move",
        "skipCondition": _gameOver_skip(),
        "parallel": {
            "type": "smart",
            "qnt": sel("listLength", cached_p("list", "activeCops")),
        },
        "actions": [
            {
                "key": "selectCentralWidgetDeck",
                "payload": {
                    "preset": {
                        # IMPORTANT: do NOT set terminationCondition/neededVotes
                        # on parallel actions — Ludio bug terminates the whole
                        # parallel block on any single iteration's vote.
                        "duration": 30,
                        "sounds.list": ["soundboard.reminder"],
                        "sounds.waitForSoundEnd": False,
                    },
                    "computed": {
                        "actors": sel("createList", computed_p("arg1", actor)),
                        "decks": sel("getCachedObjectValue",
                            preset_p("objectName", "copToMoveDecks"),
                            computed_p("value", actor),
                            preset_p("defaultValue", []),
                        ),
                        "playList.0": sel("createList", computed_p("arg1", actor)),
                        "defaultSelect": sel("getCachedObjectValue",
                            preset_p("objectName", "copToCurrentPos"),
                            computed_p("value", actor),
                            preset_p("defaultValue", ""),
                        ),
                        "question": sel("formatString",
                            preset_p("format", "Pick a cell to move to (up to 2 steps)."),
                        ),
                    }
                },
                "saveValueInCache": [
                    # Inline (no shared scratch) so parallel iterations don't
                    # cross-contaminate destinations.
                    {
                        "name": "playerToCopNextPos",
                        "value": sel("setCachedObjectFieldValue",
                            preset_p("objectName", "playerToCopNextPos"),
                            computed_p("fieldName", actor),
                            computed_p("value", sel("selectElement",
                                computed_p("list", sel("getObjectValues",
                                    cached_p("obj", "lastActionResult"),
                                )),
                                preset_p("index", 0),
                            )),
                        ),
                    },
                ],
            }
        ]
    }


def cop_apply_moves_stage():
    """Single stage that iterates all active Cops via a repeat block. For each
    cop: pull their new pos from playerToCopNextPos, move their figure card
    from current pos → new pos, update posByPlayer. Card name is computed via
    formatString('cop_($1)_figure', currentColorName)."""
    return {
        "name": "Apply Cop moves",
        "skipCondition": _gameOver_skip(),
        "repeat": {"qnt": sel("listLength", cached_p("list", "activeCops"))},
        "actions": [
            _set_current_cop(),
            # currentOldPos = posByPlayer[currentPlayer]
            empty_action(cache("currentOldPos", sel("getCachedObjectValue",
                preset_p("objectName", "posByPlayer"),
                cached_p("value", "currentPlayer"),
                preset_p("defaultValue", ""),
            ))),
            # currentNewPos = playerToCopNextPos[currentPlayer], default = old pos.
            empty_action(cache("currentNewPos", sel("getCachedObjectValue",
                preset_p("objectName", "playerToCopNextPos"),
                cached_p("value", "currentPlayer"),
                cached_p("defaultValue", "currentOldPos"),
            ))),
            # Move the figure card. cardNames filter is the iteration-specific
            # figure name (cop_<colorName>_figure).
            {
                "key": "moveCards",
                "payload": {
                    "preset": {"type": "deck"},
                    "cached": {
                        "from": "currentOldPos",
                        "to": "currentNewPos",
                    },
                    "computed": {
                        "cardNames": sel("createList",
                            computed_p("arg1", sel("formatString",
                                preset_p("format", "cop_($1)_figure"),
                                cached_p("arg1", "currentColorName"),
                            )),
                        ),
                    },
                },
            },
            # Update posByPlayer dict with the new pos.
            empty_action(cache("posByPlayer", sel("setCachedObjectFieldValue",
                preset_p("objectName", "posByPlayer"),
                cached_p("fieldName", "currentPlayer"),
                cached_p("value", "currentNewPos"),
            ))),
        ]
    }


def cop_compute_probe_targets_stage():
    """Zero copToProbeTargets + copToCurrentPos before the per-cop fill stage
    runs. Split into two stages because a Ludio stage supports only ONE repeat
    block."""
    return {
        "name": "Precompute cop probe targets",
        "skipCondition": _gameOver_skip(),
        "actions": [
            empty_action(
                cache("copToProbeTargets", {}),
                cache("copToCurrentPos", {}),
            ),
        ],
        "nextGroupNonStop": True,
    }


def cop_fill_probe_targets_stage():
    """Per-cop repeat: copToProbeTargets[cop_id] = intersect(probeTargets[pos], gridCells)."""
    cop_pos = sel("getCachedObjectValue",
        preset_p("objectName", "posByPlayer"),
        cached_p("value", "currentPlayer"),
        preset_p("defaultValue", ""),
    )
    return {
        "name": "Fill cop probe targets",
        "skipCondition": _gameOver_skip(),
        "repeat": {"qnt": sel("listLength", cached_p("list", "activeCops"))},
        "actions": [
            _set_current_cop(),
            empty_action(
                cache("copToProbeTargets", sel("setCachedObjectFieldValue",
                    preset_p("objectName", "copToProbeTargets"),
                    cached_p("fieldName", "currentPlayer"),
                    computed_p("value", sel("intersect",
                        computed_p("list1", sel("getCachedObjectValue",
                            preset_p("objectName", "probeTargets"),
                            computed_p("value", cop_pos),
                            preset_p("defaultValue", []),
                        )),
                        cached_p("list2", "gridCells"),
                    )),
                )),
                cache("copToCurrentPos", sel("setCachedObjectFieldValue",
                    preset_p("objectName", "copToCurrentPos"),
                    cached_p("fieldName", "currentPlayer"),
                    computed_p("value", cop_pos),
                )),
            ),
        ],
    }


def cop_pick_action_parallel_stage():
    """All active Cops play Investigate or Bust AND pick their target cell
    simultaneously. Decks come from precomputed copToProbeTargets (see
    cop_compute_probe_targets_stage). Action choice goes into
    playerToCopAction; target cell goes into playerToCopTarget."""
    actor = _spa_player("activeCops")
    return {
        "name": "Cops pick action",
        "skipCondition": _gameOver_skip(),
        "parallel": {
            "type": "smart",
            "qnt": sel("listLength", cached_p("list", "activeCops")),
        },
        "actions": [
            # 1. Play Investigate or Bust.
            {
                "key": "playCards",
                "payload": {
                    "preset": {
                        "qnt": 1,
                        "duration": 30,
                        "oneClick": True,
                        "sounds.list": ["soundboard.reminder"],
                        "sounds.waitForSoundEnd": False,
                    },
                    "computed": {
                        "actor": actor,
                        "target": sel("formatString",
                            preset_p("format", "videobox_($1)"),
                            computed_p("arg1", actor),
                        ),
                        "playList.0": sel("createList", computed_p("arg1", actor)),
                        "notification": sel("formatString",
                            preset_p("format", "Play Investigate or Bust."),
                        ),
                    }
                },
                "postHandler": "playOneRandomCard",
                "saveValueInCache": [
                    # Inline so the per-iteration getCardField result goes
                    # straight into playerToCopAction without a shared scratch.
                    {
                        "name": "playerToCopAction",
                        "value": sel("setCachedObjectFieldValue",
                            preset_p("objectName", "playerToCopAction"),
                            computed_p("fieldName", actor),
                            computed_p("value", sel("getCardField",
                                computed_p("cardId", sel("selectElement",
                                    computed_p("list", sel("getCachedValue",
                                        preset_p("name", "lastActionResult.cards"),
                                    )),
                                    preset_p("index", 0),
                                )),
                                preset_p("field", "name"),
                            )),
                        ),
                    },
                ],
            },
            # 2. Hide hand strip before the cell-pick UI shows.
            {
                "key": "hidePlayersHands",
                "payload": {
                    "computed": {
                        "userIds": sel("createList", computed_p("arg1", actor)),
                    }
                }
            },
            # 3. Pick the target cell (probe targets = pos + 4-neighbors).
            {
                "key": "selectCentralWidgetDeck",
                "payload": {
                    "preset": {
                        # IMPORTANT: do NOT set terminationCondition/neededVotes
                        # on parallel actions — Ludio bug terminates the whole
                        # parallel block on any single iteration's vote.
                        "duration": 30,
                        "sounds.list": ["soundboard.reminder"],
                        "sounds.waitForSoundEnd": False,
                    },
                    "computed": {
                        "actors": sel("createList", computed_p("arg1", actor)),
                        "decks": sel("getCachedObjectValue",
                            preset_p("objectName", "copToProbeTargets"),
                            computed_p("value", actor),
                            preset_p("defaultValue", []),
                        ),
                        "playList.0": sel("createList", computed_p("arg1", actor)),
                        "defaultSelect": sel("getCachedObjectValue",
                            preset_p("objectName", "copToCurrentPos"),
                            computed_p("value", actor),
                            preset_p("defaultValue", ""),
                        ),
                        "question": sel("formatString",
                            preset_p("format", "Pick a target cell."),
                        ),
                    }
                },
                "saveValueInCache": [
                    # Inline so each iteration's target cell goes straight into
                    # playerToCopTarget — no shared scratch for parallel races.
                    {
                        "name": "playerToCopTarget",
                        "value": sel("setCachedObjectFieldValue",
                            preset_p("objectName", "playerToCopTarget"),
                            computed_p("fieldName", actor),
                            computed_p("value", sel("selectElement",
                                computed_p("list", sel("getObjectValues",
                                    cached_p("obj", "lastActionResult"),
                                )),
                                preset_p("index", 0),
                            )),
                        ),
                    },
                ],
            },
            # 4. Deal the action card back into the Cop's hand for next turn.
            {
                "key": "dealDeck",
                "payload": {
                    "computed": {
                        "deck": sel("formatString",
                            preset_p("format", "videobox_($1)"),
                            computed_p("arg1", actor),
                        ),
                        "targets": actor,
                    }
                }
            },
        ]
    }






def _cop_hits_emojis_for_currentTarget():
    """formatString that concatenates each active Robber's emoji when their
    visitedByPlayer dict-entry contains the cell stored in 'currentTarget'.
    Used inside the cop investigate repeat block."""
    args = []
    for i in range(len(ROBBERS)):
        args.append(computed_p(f"arg{i+1}", sel("ifElse",
            computed_p("condition", sel("logicalAND",
                computed_p("arg1", _robber_active_cond(i)),
                computed_p("arg2", sel("contains",
                    computed_p("list", sel("getCachedObjectValue",
                        preset_p("objectName", "visitedByPlayer"),
                        computed_p("value", _player_at_slot(i)),
                        preset_p("defaultValue", []),
                    )),
                    cached_p("element", "currentTarget"),
                )),
            )),
            computed_p("thenValue", _emoji_at_slot(i)),
            preset_p("elseValue", ""),
        )))
    return sel("formatString",
        preset_p("format", "($1)($2)($3)"),
        *args,
    )


def cop_investigate_all_stage():
    """Single stage that iterates all active Cops via a repeat block. For each
    cop whose action was Investigate: reveal the target cell's label to all
    players, append target to investigatedCells. (Cops whose action was Bust
    have every per-iteration action gated by the action-check, so they
    pass through this stage as a no-op.)"""
    is_investigate = sel("equals",
        cached_p("arg1", "currentAction"),
        preset_p("arg2", "investigate"),
    )
    skip_unless_investigate = [sel("logicalNOT", computed_p("arg", is_investigate))]
    return {
        "name": "Investigate (all cops)",
        "skipCondition": _gameOver_skip(),
        "repeat": {"qnt": sel("listLength", cached_p("list", "activeCops"))},
        "actions": [
            _set_current_cop(),
            empty_action(
                cache("currentAction", sel("getCachedObjectValue",
                    preset_p("objectName", "playerToCopAction"),
                    cached_p("value", "currentPlayer"),
                    preset_p("defaultValue", ""),
                )),
                cache("currentTarget", sel("getCachedObjectValue",
                    preset_p("objectName", "playerToCopTarget"),
                    cached_p("value", "currentPlayer"),
                    preset_p("defaultValue", ""),
                )),
            ),
            empty_action(cache("currentHits", _cop_hits_emojis_for_currentTarget())),
            # Make the target cell's label visible to everyone.
            {
                "key": "setLabelInspectors",
                "skipCondition": skip_unless_investigate,
                "payload": {
                    "cached": {
                        "deck": "currentTarget",
                        "labelInspectors": "players",
                    },
                },
            },
            {
                "key": "setDeckLabel",
                "skipCondition": skip_unless_investigate,
                "payload": {
                    "cached": {
                        "deck": "currentTarget",
                        "label": "currentHits",
                    },
                },
            },
            # Append target to investigatedCells (dedup'd).
            {
                **empty_action(
                    cache("investigatedCells", sel("ifElse",
                        computed_p("condition", sel("contains",
                            cached_p("list", "investigatedCells"),
                            cached_p("element", "currentTarget"),
                        )),
                        cached_p("thenValue", "investigatedCells"),
                        computed_p("elseValue", sel("append",
                            cached_p("list", "investigatedCells"),
                            cached_p("element", "currentTarget"),
                        )),
                    )),
                ),
                "skipCondition": skip_unless_investigate,
            },
        ]
    }


def cop_bust_all_stage():
    """Single stage that iterates all active Cops. For each cop whose action
    was Bust: for each active Robber, mark bustedByPlayer[robberId] = true if
    the bust target matches that robber's pos. Robbers iterated via a Python
    list-comprehension (slot count known at codegen — max 3); each per-slot
    action gated by both 'this cop busted' and 'this robber slot is active'."""
    is_bust = sel("equals",
        cached_p("arg1", "currentAction"),
        preset_p("arg2", "bust"),
    )
    not_bust = sel("logicalNOT", computed_p("arg", is_bust))
    return {
        "name": "Bust (all cops)",
        "skipCondition": _gameOver_skip(),
        "repeat": {"qnt": sel("listLength", cached_p("list", "activeCops"))},
        "actions": [
            _set_current_cop(),
            empty_action(
                cache("currentAction", sel("getCachedObjectValue",
                    preset_p("objectName", "playerToCopAction"),
                    cached_p("value", "currentPlayer"),
                    preset_p("defaultValue", ""),
                )),
                cache("currentTarget", sel("getCachedObjectValue",
                    preset_p("objectName", "playerToCopTarget"),
                    cached_p("value", "currentPlayer"),
                    preset_p("defaultValue", ""),
                )),
            ),
            # Per-Robber bust check: bustedByPlayer[robberAtSlot(i)] |= (target == pos)
            *[{
                "key": "emptyAction",
                "skipCondition": [
                    sel("logicalOR",
                        computed_p("arg1", not_bust),
                        computed_p("arg2", sel("lessThanOrEqual",
                            cached_p("arg1", "numRobbers"),
                            preset_p("arg2", r_idx),
                        )),
                    )
                ],
                "saveValueInCache": [
                    cache("bustedByPlayer", sel("setCachedObjectFieldValue",
                        preset_p("objectName", "bustedByPlayer"),
                        computed_p("fieldName", _player_at_slot(r_idx)),
                        computed_p("value", sel("logicalOR",
                            computed_p("arg1", sel("getCachedObjectValue",
                                preset_p("objectName", "bustedByPlayer"),
                                computed_p("value", _player_at_slot(r_idx)),
                                preset_p("defaultValue", False),
                            )),
                            computed_p("arg2", sel("equals",
                                cached_p("arg1", "currentTarget"),
                                computed_p("arg2", sel("getCachedObjectValue",
                                    preset_p("objectName", "posByPlayer"),
                                    computed_p("value", _player_at_slot(r_idx)),
                                    preset_p("defaultValue", ""),
                                )),
                            )),
                        )),
                    )),
                ],
            } for r_idx in range(len(ROBBERS))],
        ]
    }


def _any_robber_has_4_stashes_selector():
    """OR-chain: did any active Robber accumulate ≥4 stash hits? Reads from the
    stashesHitByPlayer dict keyed by activeRobbers[i]. Static iteration over
    the max-slot count (len(ROBBERS)), gated per-slot by numRobbers > i."""
    # Build a nested logicalOR over the slots.
    branches = []
    for i in range(len(ROBBERS)):
        branches.append(sel("logicalAND",
            computed_p("arg1", _robber_active_cond(i)),
            computed_p("arg2", sel("greaterThanOrEqual",
                computed_p("arg1", sel("getCachedObjectValue",
                    preset_p("objectName", "stashesHitByPlayer"),
                    computed_p("value", _player_at_slot(i)),
                    preset_p("defaultValue", 1),
                )),
                preset_p("arg2", 4),
            )),
        ))
    # Fold into nested logicalOR.
    result = branches[-1]
    for b in reversed(branches[:-1]):
        result = sel("logicalOR",
            computed_p("arg1", b),
            computed_p("arg2", result),
        )
    return result


def _all_active_robbers_busted_selector():
    """AND-chain: are all active Robbers busted? Reads bustedByPlayer dict.
    For inactive slots the AND-term is short-circuited via 'numRobbers ≤ i' →
    that slot's contribution is true (vacuously)."""
    branches = []
    for i in range(len(ROBBERS)):
        branches.append(sel("logicalOR",
            computed_p("arg1", sel("lessThanOrEqual",
                cached_p("arg1", "numRobbers"),
                preset_p("arg2", i),
            )),
            computed_p("arg2", sel("getCachedObjectValue",
                preset_p("objectName", "bustedByPlayer"),
                computed_p("value", _player_at_slot(i)),
                preset_p("defaultValue", False),
            )),
        ))
    result = branches[-1]
    for b in reversed(branches[:-1]):
        result = sel("logicalAND",
            computed_p("arg1", b),
            computed_p("arg2", result),
        )
    return result


def win_check_stage():
    """Stage: check if game has ended (any active Robber finished all 4 stashes
    OR all active Robbers busted OR turn limit reached). Marked
    checkWinCondition:true so the engine evaluates winCondition right after."""
    return {
        "name": "Win check",
        "checkWinCondition": True,
        "actions": [
            empty_action(
                cache("robbersWin", _any_robber_has_4_stashes_selector()),
                cache("allBusted",  _all_active_robbers_busted_selector()),
            ),
            empty_action(
                cache("turnLimitReached", sel("greaterThanOrEqual",
                    cached_p("arg1", "turnNumber"),
                    cached_p("arg2", "maxTurns"),
                )),
            ),
            empty_action(
                cache("gameOver", sel("logicalOR",
                    cached_p("arg1", "robbersWin"),
                    computed_p("arg2", sel("logicalOR",
                        cached_p("arg1", "allBusted"),
                        cached_p("arg2", "turnLimitReached"),
                    )),
                )),
            ),
        ]
    }


def build_game_loop() -> list:
    """Game loop — Tutorial, then per-turn structure.

    Sequential within each phase (per-Robber, per-Cop with skipConditions on
    inactive slots). Parallel parallelization can be added later.
    """
    # Iter-0 board setup + setup picks (cell decks via repeat, widget mount,
    # terrain, setup picks). All gated by gameLoopIndex==0.
    stages = build_iter0_setup_stages()

    # ----- Tutorial stage (conditional on `tutorial` cache flag) -----
    tutorial_notifs = [
        ("Cops & Robbers (1/6)",
         "A team of <b>Robbers</b> is hiding loot at 4 stash spots across the city. The <b>Cops</b> are racing to catch them before the turn timer runs out."),
        ("Setup (2/6)",
         "Each Robber gets 4 stash cells (one per corner of the board). Each picks one as their <b>starting cell</b> (revealed). The other 3 are secret. Cops deploy together in the central rectangle."),
        ("Robber's Turn (3/6)",
         "Each turn, a Robber moves to <b>1 adjacent cell</b> (any of 8 directions) — or plays a <b>Special Movement</b> card (Getaway Car / Backstreet / Speedboat) for a longer move."),
        ("Cop's Turn (4/6)",
         "Each Cop moves up to <b>2 cells</b> (up/down/left/right), then plays either <b>Investigate</b> (probe an adjacent cell for clues) or <b>Bust</b> (try to arrest a Robber)."),
        ("Clues (5/6)",
         "Robbers see live trails on the board — each cell label shows who has visited recently. When a Cop <b>Investigates</b>, that cell's trail is revealed publicly. <b>Every 10 turns the trails wipe.</b>"),
        ("Winning (6/6)",
         "<b>Robbers win</b> if ANY Robber places all 4 stash cards. <b>Cops win</b> if every Robber is busted, or if the turn limit (30 / 35 / 40 turns) runs out."),
    ]
    tutorial_actions = []
    for header, text in tutorial_notifs:
        tutorial_actions.append({
            "key": "createNotification",
            "payload": {
                "preset": {
                    "header": header,
                    "text": text,
                    "duration": 14,
                    "backgroundColor": "#1c3a5e",
                    "borderColor": "white",
                    "textColor": "white",
                },
                "cached": {"to": "learners"},
            }
        })
    tutorial_actions.append(empty_action(cache("tutorial", False)))

    stages.append({
        "name": "Tutorial",
        "skipCondition": [sel("logicalNOT", cached_p("arg", "tutorial"))],
        "actions": tutorial_actions,
    })

    # ----- Increment turnNumber silently. -----
    stages.append({
        "name": "Bump turn counter",
        "skipCondition": [sel("getCachedValue", preset_p("name", "gameOver"))],
        "actions": [
            empty_action(
                cache("turnNumber", sel("inc", cached_p("arg", "turnNumber"))),
            ),
        ]
    })

    # ----- Robber breakout room — open only when multiple Robbers are in play
    # so they can voice-coordinate their moves. Closed after the last Robber's
    # turn so the table re-joins for the Cop phase. -----
    multi_robber_skip = sel("lessThan",
        cached_p("arg1", "numRobbers"),
        preset_p("arg2", 2),
    )
    stages.append({
        "name": "Robbers' breakout room",
        "skipCondition": [
            multi_robber_skip,
            sel("getCachedValue", preset_p("name", "gameOver")),
        ],
        "actions": [{
            "key": "createTeamsConversationGroups",
            "payload": {
                "preset": {
                    "video": True,
                    "audio": True,
                    "private": False,
                    "indicator": "🔒",
                    "isVideoForAll": False,
                }
            }
        }],
    })

    # ----- Robber turn (parallelized) -----
    # 1. Clear per-turn parallel-results dicts.
    stages.append(robber_turn_init_stage())
    # 2. All active Robbers pick their movement card (or Pass) in parallel.
    stages.append(robber_pick_card_parallel_stage())
    # 3. Single stage iterates active Robbers and processes each card.
    stages.append(robber_process_cards_stage())
    # 4a. Precompute each active Robber's destination-pick decks into
    #     robberToDestDecks. Two stages — zero, then fill via repeat.
    stages.append(robber_compute_destination_decks_stage())
    stages.append(robber_fill_destination_decks_stage())
    # 4b. All active Robbers pick their destination cell in parallel.
    stages.append(robber_pick_destination_parallel_stage())
    # 5. Single stage iterates active Robbers and applies the move (update
    #    pos/visited via dicts, slide fake-role, detect stash hit, bump
    #    robbersWin/gameOver if 4th stash). Stage carries checkWinCondition:
    #    True so the engine ends the game right after this stage if any
    #    Robber placed their 4th stash this turn.
    stages.append(robber_apply_moves_stage())

    # ----- Close the Robber breakout room before the Cops act. -----
    stages.append({
        "name": "Close Robbers' breakout",
        "skipCondition": [multi_robber_skip],
        "actions": [{"key": "destroyConversationGroups"}],
    })

    # ----- Cop turn (parallelized) -----
    # 1. Clear per-turn parallel-results dicts.
    stages.append(cop_turn_init_stage())
    # 2a. Precompute each active Cop's move-pick reach into copToMoveDecks.
    #     Split into two stages because a Ludio stage allows only one repeat
    #     block (one to zero the dict, the next to fill it via repeat).
    stages.append(cop_compute_move_decks_stage())
    stages.append(cop_fill_move_decks_stage())
    # 2b. All active Cops pick their move destination in parallel.
    stages.append(cop_move_parallel_stage())
    # 3. Single repeat-block stage moves every active Cop's figure card from
    #    its old pos to the new pos (one stage iterates activeCops; no Python
    #    loop / no per-slug skipConditions).
    stages.append(cop_apply_moves_stage())
    # 4a. Precompute each active Cop's probe targets (after the move updated
    #     posByPlayer) into copToProbeTargets. Two stages — zero then fill.
    stages.append(cop_compute_probe_targets_stage())
    stages.append(cop_fill_probe_targets_stage())
    # 4b. All active Cops play Investigate/Bust AND pick a target cell in parallel.
    stages.append(cop_pick_action_parallel_stage())
    # 5. Investigations: single repeat-block stage iterates all active Cops;
    #    each iteration's actions are gated by currentAction == "investigate".
    stages.append(cop_investigate_all_stage())
    # 6. Busts: same pattern, gated by currentAction == "bust".
    stages.append(cop_bust_all_stage())

    # ----- Trail reset (fires only at turn 10, 20, 30 — clears caches +
    # notification, then a second stage restores activeRobbers on every cell's
    # labelInspectors. Both gated by the same turn-mod check). -----
    stages.append(trail_reset_state_stage())
    stages.append(trail_reset_inspectors_stage())

    # ----- Recompute every cell's label from current pos + visited state.
    # Runs every turn, so cleared trails paint cleanly after the reset stages. -----
    stages.append(recompute_labels_stage())

    # ----- Win check -----
    stages.append(win_check_stage())

    return stages


def build_win_condition() -> dict:
    return {
        "robbers": sel(
            "logicalAND",
            cached_p("arg1", "gameOver"),
            cached_p("arg2", "robbersWin"),
        ),
        "cops": sel(
            "logicalAND",
            cached_p("arg1", "gameOver"),
            computed_p("arg2", sel("logicalNOT", cached_p("arg", "robbersWin"))),
        ),
    }


# =================================================================
# Main
# =================================================================

def reorder_skip_conditions(obj):
    """Walk the JSON tree and ensure skipCondition sits right after name/key in any dict that has it."""
    if isinstance(obj, dict):
        if "skipCondition" in obj:
            out = {}
            for first in ("name", "key"):
                if first in obj:
                    out[first] = obj[first]
                    break
            out["skipCondition"] = reorder_skip_conditions(obj["skipCondition"])
            for k, v in obj.items():
                if k not in ("name", "key", "skipCondition"):
                    out[k] = reorder_skip_conditions(v)
            return out
        return {k: reorder_skip_conditions(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [reorder_skip_conditions(item) for item in obj]
    return obj


def build_post_game_actions() -> list:
    """Runs once the game ends — announces who won."""
    return [
        {
            "key": "createNotification",
            "payload": {
                "preset": {
                    "duration": 12,
                    "image": "winner",
                    "backgroundColor": "#1c3a5e",
                    "borderColor": "white",
                    "textColor": "white",
                },
                "cached": {"to": "players"},
                "computed": {
                    "header": sel("ifElse",
                        cached_p("condition", "robbersWin"),
                        preset_p("thenValue", "Robbers win!"),
                        preset_p("elseValue", "Cops win!"),
                    ),
                    "text": sel("ifElse",
                        cached_p("condition", "robbersWin"),
                        preset_p("thenValue", "A robber completed all 4 stashes. The heist is done."),
                        preset_p("elseValue", "Either every robber was busted or the turn timer ran out before the heist completed."),
                    ),
                }
            }
        }
    ]


def main():
    game = {
        "gameInitOptions": build_game_init_options(),
        "visualSettings": build_visual_settings(),
        "beforeLoopActions": build_before_loop_actions(),
        "gameLoop": build_game_loop(),
        "winCondition": build_win_condition(),
        "postGameActions": build_post_game_actions(),
    }
    game = reorder_skip_conditions(game)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(game, indent=4) + "\n")
    size = OUTPUT.stat().st_size
    print(f"Wrote {OUTPUT} ({size:,} bytes)")


if __name__ == "__main__":
    main()
