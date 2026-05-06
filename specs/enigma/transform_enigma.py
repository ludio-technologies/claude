"""
Transforms enigma.json:
1. 5-column widget (red_clues/blue_clues decks as column 1 per row)
2. Fix GL-8 equals(list, list) -> equals(listToString, listToString)
3. New player assignment: createVote for encryptors, divide into teams, createVote for clickers, nextPlayer rotation
"""
import json, copy

with open('game_jsons/enigma.json', 'r') as f:
    data = json.load(f)

bla = data['beforeLoopActions']
gl  = data['gameLoop']
pga = data['postGameActions']

# ─── HELPERS ────────────────────────────────────────────────────────────────

def cached(v):      return {"type": "cached",  "value": v}
def preset(v):      return {"type": "preset",  "value": v}
def computed(v):    return {"type": "computed", "value": v}

def getCachedValue(name):
    return {"selector": "getCachedValue", "params": [{"name": "name", "type": "preset", "value": name}]}

def listToString(list_selector):
    return {"selector": "listToString", "params": [{"name": "list", "type": "computed", "value": list_selector}]}

# ─── 1. BEFORE LOOP ACTIONS ──────────────────────────────────────────────────

# 1a. Remove redEncryptorIndex / blueEncryptorIndex from first emptyAction
bla[0]['saveValueInCache'] = [
    x for x in bla[0]['saveValueInCache']
    if x['name'] not in ('redEncryptorIndex', 'blueEncryptorIndex')
]

# Map current bla positions we want to keep
# 0: first emptyAction (modified above)
# 1: changeBackground
# 2: restPlayers emptyAction  -> DISCARD
# 3: setRole(redPlayer, redTeam)  -> DISCARD
# 4: setRole(bluePlayer, blueTeam)  -> DISCARD
# 5: removeAllHighlights
# 6: highlightPlayers(red)
# 7: highlightPlayers(blue)
# 8: changeLayout
# 9: showScore(from: redTeam)
# 10: showScore(from: blueTeam)
# 11: shuffledWords emptyAction
# 12: createDeck
# 13: shuffleDeck
# 14: createVideoboxDecks
# 15: createTeamsConversationGroups
# 16: showRole(from: redTeam)
# 17: showRole(from: blueTeam)
# 18: host emptyAction
# 19: createNotification(welcome)
# 20: createMixVote(tutorial)

NEW_ITEMS = []

# ── createVote: pick encryptors ──────────────────────────────────────────────
vote_encryptors = {
    "key": "createVote",
    "payload": {
        "preset": {
            "type": "target_point",
            "title": "Select encryptors",
            "terminationCondition": "get_all_votes",
            "allowFewerAnswers": True
        },
        "cached": {
            "actors": "host",
            "targets": "players",
            "answersQuantity": "numPlayers"
        }
    },
    "saveValueInCache": [
        {
            "name": "selectedEncryptors",
            "value": getCachedValue("lastActionResult.voteResult")
        }
    ]
}

# ── emptyAction: compute team halves ────────────────────────────────────────
compute_teams = {
    "key": "emptyAction",
    "saveValueInCache": [
        {
            "name": "shuffledEncryptors",
            "value": {"selector": "shuffleList", "params": [{"name": "list", "type": "cached", "value": "selectedEncryptors"}]}
        },
        {
            "name": "numEncryptors",
            "value": {"selector": "listLength", "params": [{"name": "list", "type": "cached", "value": "shuffledEncryptors"}]}
        },
        {
            "name": "halfEncryptors",
            "value": {
                "selector": "integerDivide",
                "params": [
                    {"name": "arg1", "type": "cached", "value": "numEncryptors"},
                    {"name": "arg2", "type": "preset", "value": 2}
                ]
            }
        },
        {
            "name": "redEncryptors",
            "value": {
                "selector": "sublist",
                "params": [
                    {"name": "list",  "type": "cached", "value": "shuffledEncryptors"},
                    {"name": "start", "type": "preset", "value": 0},
                    {"name": "end",   "type": "cached", "value": "halfEncryptors"}
                ]
            }
        },
        {
            "name": "blueEncryptors",
            "value": {
                "selector": "sublist",
                "params": [
                    {"name": "list",  "type": "cached", "value": "shuffledEncryptors"},
                    {"name": "start", "type": "cached", "value": "halfEncryptors"},
                    {"name": "end",   "type": "cached", "value": "numEncryptors"}
                ]
            }
        },
        {
            "name": "nonEncryptors",
            "value": {
                "selector": "listsSubtract",
                "params": [
                    {"name": "list1", "type": "cached", "value": "players"},
                    {"name": "list2", "type": "cached", "value": "selectedEncryptors"}
                ]
            }
        },
        {
            "name": "shuffledNon",
            "value": {"selector": "shuffleList", "params": [{"name": "list", "type": "cached", "value": "nonEncryptors"}]}
        },
        {
            "name": "numNon",
            "value": {"selector": "listLength", "params": [{"name": "list", "type": "cached", "value": "shuffledNon"}]}
        },
        {
            "name": "halfNon",
            "value": {
                "selector": "integerDivide",
                "params": [
                    {"name": "arg1", "type": "cached", "value": "numNon"},
                    {"name": "arg2", "type": "preset", "value": 2}
                ]
            }
        },
        {
            "name": "redNonEncryptors",
            "value": {
                "selector": "sublist",
                "params": [
                    {"name": "list",  "type": "cached", "value": "shuffledNon"},
                    {"name": "start", "type": "preset", "value": 0},
                    {"name": "end",   "type": "cached", "value": "halfNon"}
                ]
            }
        },
        {
            "name": "blueNonEncryptors",
            "value": {
                "selector": "sublist",
                "params": [
                    {"name": "list",  "type": "cached", "value": "shuffledNon"},
                    {"name": "start", "type": "cached", "value": "halfNon"},
                    {"name": "end",   "type": "cached", "value": "numNon"}
                ]
            }
        }
    ]
}

def make_setRole(role_id, player_cached_key):
    return {
        "key": "setRole",
        "payload": {
            "preset": {"roleId": role_id},
            "cached": {"playerId": player_cached_key}
        }
    }

# ── emptyAction: get teams + init encryptors for nextPlayer ──────────────────
init_teams = {
    "key": "emptyAction",
    "saveValueInCache": [
        {
            "name": "redTeam",
            "value": {"selector": "getPlayersFromTeam", "params": [{"name": "teamId", "type": "preset", "value": "red"}]}
        },
        {
            "name": "blueTeam",
            "value": {"selector": "getPlayersFromTeam", "params": [{"name": "teamId", "type": "preset", "value": "blue"}]}
        },
        {
            "name": "redTeamSize",
            "value": {"selector": "listLength", "params": [{"name": "list", "type": "cached", "value": "redTeam"}]}
        },
        {
            "name": "blueTeamSize",
            "value": {"selector": "listLength", "params": [{"name": "list", "type": "cached", "value": "blueTeam"}]}
        },
        {
            "name": "redEncryptorsSize",
            "value": {"selector": "listLength", "params": [{"name": "list", "type": "cached", "value": "redEncryptors"}]}
        },
        {
            "name": "blueEncryptorsSize",
            "value": {"selector": "listLength", "params": [{"name": "list", "type": "cached", "value": "blueEncryptors"}]}
        },
        # Init redEncryptor to LAST element so nextPlayer returns FIRST on round 1
        {
            "name": "redEncryptor",
            "value": {
                "selector": "selectElement",
                "params": [
                    {"name": "list", "type": "cached", "value": "redEncryptors"},
                    {"name": "index", "type": "computed", "value": {
                        "selector": "dec",
                        "params": [{"name": "arg", "type": "cached", "value": "redEncryptorsSize"}]
                    }}
                ]
            }
        },
        {
            "name": "blueEncryptor",
            "value": {
                "selector": "selectElement",
                "params": [
                    {"name": "list", "type": "cached", "value": "blueEncryptors"},
                    {"name": "index", "type": "computed", "value": {
                        "selector": "dec",
                        "params": [{"name": "arg", "type": "cached", "value": "blueEncryptorsSize"}]
                    }}
                ]
            }
        }
    ]
}

def make_vote_clicker(color, team_cached_key):
    clicker_name = f"{color}Clicker"
    return {
        "key": "createVote",
        "payload": {
            "preset": {
                "type": "target_point",
                "title": f"Select {color} team clicker",
                "terminationCondition": "get_all_votes",
                "answersQuantity": 1,
                "allowFewerAnswers": False
            },
            "cached": {
                "actors": "host",
                "targets": team_cached_key
            }
        },
        "saveValueInCache": [
            {
                "name": clicker_name,
                "value": {
                    "selector": "selectElement",
                    "params": [
                        {"name": "list", "type": "computed", "value": getCachedValue("lastActionResult.voteResult")},
                        {"name": "index", "type": "preset", "value": 0}
                    ]
                }
            }
        ]
    }

# Build the new beforeLoopActions:
new_bla = [
    bla[0],   # init vars (modified)
    bla[1],   # changeBackground
    bla[18],  # host emptyAction
    bla[19],  # welcome notification
    bla[20],  # createMixVote tutorial
    vote_encryptors,
    compute_teams,
    make_setRole("redPlayer",  "redEncryptors"),
    make_setRole("bluePlayer", "blueEncryptors"),
    make_setRole("redPlayer",  "redNonEncryptors"),
    make_setRole("bluePlayer", "blueNonEncryptors"),
    init_teams,
    bla[5],   # removeAllHighlights
    bla[6],   # highlightPlayers(red)
    bla[7],   # highlightPlayers(blue)
    bla[8],   # changeLayout
    bla[9],   # showScore(from redTeam)
    bla[10],  # showScore(from blueTeam)
    bla[16],  # showRole(from redTeam)
    bla[17],  # showRole(from blueTeam)
    make_vote_clicker("red",  "redTeam"),
    make_vote_clicker("blue", "blueTeam"),
    bla[11],  # shuffledWords emptyAction
    bla[12],  # createDeck
    bla[13],  # shuffleDeck
    bla[14],  # createVideoboxDecks
    bla[15],  # createTeamsConversationGroups
]

data['beforeLoopActions'] = new_bla

# ─── 2. GAME LOOP ────────────────────────────────────────────────────────────

skip_if_not_first_round = [
    {
        "selector": "greaterThan",
        "params": [
            {"name": "arg1", "type": "cached", "value": "gameLoopIndex"},
            {"name": "arg2", "type": "preset", "value": 0}
        ]
    }
]

# 2a. Add red_clues and blue_clues deck creation groups (after Create Blue Position Decks)
create_red_clues_deck_group = {
    "name": "Create Red Clues Deck",
    "skipCondition": skip_if_not_first_round,
    "actions": [
        {
            "key": "createCustomDeck",
            "payload": {
                "preset": {
                    "name": "red_clues",
                    "public": True,
                    "facedown": False,
                    "cardback": "transparent",
                    "counter": False,
                    "backgroundColor": "#D83232",
                    "textColor": "white"
                }
            }
        }
    ]
}

create_blue_clues_deck_group = {
    "name": "Create Blue Clues Deck",
    "skipCondition": skip_if_not_first_round,
    "actions": [
        {
            "key": "createCustomDeck",
            "payload": {
                "preset": {
                    "name": "blue_clues",
                    "public": True,
                    "facedown": False,
                    "cardback": "transparent",
                    "counter": False,
                    "backgroundColor": "#4EC1D0",
                    "textColor": "white"
                }
            }
        }
    ]
}

# 2b. Update GL-0c Create Widget (currently gl[3])
gl_0c = gl[3]
assert gl_0c['name'] == 'GL-0c Create Widget', f"Expected GL-0c, got: {gl_0c['name']}"
widget_action = gl_0c['actions'][0]
assert widget_action['key'] == 'createGenericCardWidget'
widget_action['payload']['preset']['dimensions'] = [2, 5]
widget_action['payload']['preset']['decks'] = [
    "red_clues", "red_1", "red_2", "red_3", "red_4",
    "blue_clues", "blue_1", "blue_2", "blue_3", "blue_4"
]

# 2c. Update GL-1 Assign Encryptors (currently gl[4])
gl_1 = gl[4]
assert gl_1['name'] == 'GL-1 Assign Encryptors', f"Expected GL-1, got: {gl_1['name']}"
# Replace the emptyAction's saveValueInCache
first_action = gl_1['actions'][0]
assert first_action['key'] == 'emptyAction'
first_action['saveValueInCache'] = [
    {
        "name": "redEncryptor",
        "value": {
            "selector": "nextPlayer",
            "params": [
                {"name": "playersList", "type": "cached", "value": "redEncryptors"},
                {"name": "playerId",    "type": "cached", "value": "redEncryptor"}
            ]
        }
    },
    {
        "name": "blueEncryptor",
        "value": {
            "selector": "nextPlayer",
            "params": [
                {"name": "playersList", "type": "cached", "value": "blueEncryptors"},
                {"name": "playerId",    "type": "cached", "value": "blueEncryptor"}
            ]
        }
    },
    {
        "name": "redActiveClicker",
        "value": getCachedValue("redClicker")
    },
    {
        "name": "blueActiveClicker",
        "value": getCachedValue("blueClicker")
    }
]

# 2d. Build new gameLoop with clue deck groups inserted after Create Blue Position Decks (gl[2])
new_gl = (
    gl[:3]                           # Tutorial, Create Red/Blue Position Decks
    + [create_red_clues_deck_group,
       create_blue_clues_deck_group]
    + gl[3:]                         # GL-0c onwards (already modified above)
)

# 2e. Fix GL-5 createCard actions (now at index 15+2=17 in new_gl)
# Find GL-5 by name
gl5_idx = next(i for i, g in enumerate(new_gl) if g['name'].startswith('GL-5'))
gl5 = new_gl[gl5_idx]
# Keep first 2 actions (notifications), replace createCard actions with 2 summary cards
gl5_notifications = [a for a in gl5['actions'] if a['key'] == 'createNotification']

red_summary_card = {
    "key": "createCard",
    "payload": {
        "preset": {
            "deck": "red_clues",
            "background": "#D83232",
            "textColor": "white",
            "fontHeightPercentage": 7,
            "facedown": False
        },
        "computed": {
            "cardText": {
                "selector": "formatString",
                "params": [
                    {"name": "format", "type": "preset", "value": "1. ($1)\n2. ($2)\n3. ($3)"},
                    {"name": "arg1",   "type": "cached", "value": "redClue1"},
                    {"name": "arg2",   "type": "cached", "value": "redClue2"},
                    {"name": "arg3",   "type": "cached", "value": "redClue3"}
                ]
            }
        }
    }
}

blue_summary_card = {
    "key": "createCard",
    "payload": {
        "preset": {
            "deck": "blue_clues",
            "background": "#4EC1D0",
            "textColor": "white",
            "fontHeightPercentage": 7,
            "facedown": False
        },
        "computed": {
            "cardText": {
                "selector": "formatString",
                "params": [
                    {"name": "format", "type": "preset", "value": "1. ($1)\n2. ($2)\n3. ($3)"},
                    {"name": "arg1",   "type": "cached", "value": "blueClue1"},
                    {"name": "arg2",   "type": "cached", "value": "blueClue2"},
                    {"name": "arg3",   "type": "cached", "value": "blueClue3"}
                ]
            }
        }
    }
}

gl5['actions'] = gl5_notifications + [red_summary_card, blue_summary_card]
gl5['name'] = 'GL-5 Reveal Clues'

# 2f. Fix GL-8 equals(list, list) bug
gl8_idx = next(i for i, g in enumerate(new_gl) if g['name'] == 'GL-8 Compute Results')
gl8 = new_gl[gl8_idx]
gl8_action = gl8['actions'][0]
assert gl8_action['key'] == 'emptyAction'

def fix_equals_in_cache_entry(entry):
    """Wrap both sides of an equals(createList, createList) in listToString."""
    v = entry['value']
    if v.get('selector') != 'equals':
        return entry
    params = v['params']
    # both arg1 and arg2 should be createList selectors
    new_params = []
    for p in params:
        if p['type'] == 'computed' and isinstance(p['value'], dict) and p['value'].get('selector') == 'createList':
            new_params.append({
                "name": p['name'],
                "type": "computed",
                "value": {
                    "selector": "listToString",
                    "params": [
                        {"name": "list", "type": "computed", "value": p['value']}
                    ]
                }
            })
        else:
            new_params.append(p)
    entry['value']['params'] = new_params
    return entry

gl8_action['saveValueInCache'] = [
    fix_equals_in_cache_entry(e) for e in gl8_action['saveValueInCache']
]

# 2g. Update GL-9: remove redEncryptorIndex and blueEncryptorIndex increments
gl9_idx = next(i for i, g in enumerate(new_gl) if g['name'] == 'GL-9 Round End')
gl9 = new_gl[gl9_idx]
# Find the emptyAction inside GL-9
for action in gl9['actions']:
    if action['key'] == 'emptyAction' and 'saveValueInCache' in action:
        action['saveValueInCache'] = [
            x for x in action['saveValueInCache']
            if x['name'] not in ('redEncryptorIndex', 'blueEncryptorIndex')
        ]

data['gameLoop'] = new_gl

# ─── 3. POST GAME ACTIONS ────────────────────────────────────────────────────

def make_setLabelInspectors(deck_name):
    return {
        "key": "setLabelInspectors",
        "payload": {
            "preset": {"deck": deck_name},
            "computed": {
                "labelInspectors": {"selector": "allUsers"}
            }
        }
    }

# Find where the existing setLabelInspectors for red_1 is and insert red_clues/blue_clues before
# Insert at the beginning of the setLabelInspectors block
first_sli_idx = next(i for i, a in enumerate(pga) if a.get('key') == 'setLabelInspectors')
pga.insert(first_sli_idx, make_setLabelInspectors("red_clues"))
# blue_clues should go right after red_clues (before red_1)
pga.insert(first_sli_idx + 1, make_setLabelInspectors("blue_clues"))

data['postGameActions'] = pga

# ─── WRITE ───────────────────────────────────────────────────────────────────
with open('game_jsons/enigma.json', 'w') as f:
    json.dump(data, f, indent=4, ensure_ascii=False)

print("Done. Summary:")
print(f"  beforeLoopActions: {len(data['beforeLoopActions'])} items")
print(f"  gameLoop: {len(data['gameLoop'])} groups")
print(f"  postGameActions: {len(data['postGameActions'])} items")

# Validate JSON can be re-read
with open('game_jsons/enigma.json', 'r') as f:
    check = json.load(f)
print("  JSON validates OK")

# Print gameLoop names for verification
print("\nGame loop groups:")
for i, g in enumerate(check['gameLoop']):
    print(f"  [{i}] {g['name']}")
