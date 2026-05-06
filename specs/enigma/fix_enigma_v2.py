"""
Applies 5 changes to enigma.json:

1. BLA[5] encryptors vote: add oneClick, limit answersQuantity to N-2, add dark colors
2. Clicker votes: move to right after encryptors init, target non-encryptors, add oneClick + team colors
3. redTeam/blueTeam: remove from BLA[11], add new emptyAction after clicker votes
4. (same as #1 and #2 - colors applied there)
5. GL-9: insert 6 createCard actions (clue history) after code-reveal notifications
"""
import json

with open('game_jsons/enigma.json', 'r') as f:
    data = json.load(f)

bla = data['beforeLoopActions']
gl  = data['gameLoop']

# ─── Helpers ──────────────────────────────────────────────────────────────────

def cached(value):
    return {"type": "cached", "value": value}

def preset(value):
    return {"type": "preset", "value": value}

def computed(selector, **kwargs):
    return {"type": "computed", "value": {"selector": selector, "params": [
        {"name": k, **v} for k, v in kwargs.items()
    ]}}

def format_question(template):
    return {
        "selector": "formatString",
        "params": [
            {"name": "format", "type": "preset", "value": template},
            {"name": "arg1", "type": "computed", "value": {
                "selector": "getPlayerNameById",
                "params": [{"name": "id", "type": "cached", "value": "host.0"}]
            }}
        ]
    }

# ─── Change 1: BLA[5] encryptors createVote ──────────────────────────────────
ev = bla[5]
assert ev['key'] == 'createVote', f"Expected createVote at BLA[5], got {ev['key']}"

# Add oneClick
ev['payload']['preset']['oneClick'] = True

# Add colors (dark game theme)
ev['payload']['preset']['backgroundColor'] = "#1a1a2e"
ev['payload']['preset']['borderColor']     = "#D83232"
ev['payload']['preset']['textColor']       = "white"

# Change answersQuantity from cached numPlayers to dec(dec(numPlayers))
# Remove the cached answersQuantity
ev['payload']['cached'].pop('answersQuantity', None)
# Add computed answersQuantity = dec(dec(numPlayers))
ev['payload']['computed']['answersQuantity'] = {
    "selector": "dec",
    "params": [
        {
            "name": "arg",
            "type": "computed",
            "value": {
                "selector": "dec",
                "params": [
                    {"name": "arg", "type": "cached", "value": "numPlayers"}
                ]
            }
        }
    ]
}

# ─── Change 3 (part A): BLA[11] – remove redTeam/blueTeam/redTeamSize/blueTeamSize ──
em = bla[11]
assert em['key'] == 'emptyAction', f"Expected emptyAction at BLA[11], got {em['key']}"
to_remove = {'redTeam', 'blueTeam', 'redTeamSize', 'blueTeamSize'}
em['saveValueInCache'] = [e for e in em['saveValueInCache'] if e['name'] not in to_remove]

# ─── Remove BLA[20] and BLA[21] (old clicker votes) and BLA[12-19] (display) ─
# We'll rebuild the section between BLA[11] and BLA[22].
# Current: [12]=removeAllHighlights ... [19]=showRole blue, [20]=createVote red, [21]=createVote blue
# New:     [12]=createVote red, [13]=createVote blue, [14]=new team emptyAction,
#          [15..22]=the display actions, [23..27]=unchanged deck creation

old_vote_red  = bla[20]
old_vote_blue = bla[21]
display_block = bla[12:20]   # removeAllHighlights .. showRole blue (8 items)
deck_block    = bla[22:]     # shuffledWords, createDeck, shuffleDeck, createVideoboxDecks, createTeamsConversationGroups

# Build modified clicker votes
def make_clicker_vote(color, team_label, target_var, bg, text_q):
    return {
        "key": "createVote",
        "payload": {
            "preset": {
                "type": "target_point",
                "title": f"Select {team_label} team clicker",
                "terminationCondition": "get_all_votes",
                "answersQuantity": 1,
                "allowFewerAnswers": False,
                "showResultInRealTime": True,
                "oneClick": True,
                "backgroundColor": bg,
                "borderColor": "white",
                "textColor": "white"
            },
            "cached": {
                "actors": "host",
                "targets": target_var
            },
            "computed": {
                "question": {
                    "selector": "formatString",
                    "params": [
                        {"name": "format", "type": "preset", "value": text_q},
                        {"name": "arg1", "type": "computed", "value": {
                            "selector": "getPlayerNameById",
                            "params": [{"name": "id", "type": "cached", "value": "host.0"}]
                        }}
                    ]
                }
            }
        },
        "saveValueInCache": [
            {
                "name": f"{color}Clicker",
                "value": {
                    "selector": "selectElement",
                    "params": [
                        {"name": "list", "type": "computed", "value": {
                            "selector": "getCachedValue",
                            "params": [{"name": "name", "type": "preset",
                                        "value": "lastActionResult.voteResult"}]
                        }},
                        {"name": "index", "type": "preset", "value": 0}
                    ]
                }
            }
        ]
    }

new_vote_red  = make_clicker_vote("red",  "Red",  "redNonEncryptors",  "#D83232",
    "($1), click the Red team player (non-encryptor) who will be the clicker for the whole game.")
new_vote_blue = make_clicker_vote("blue", "Blue", "blueNonEncryptors", "#4EC1D0",
    "($1), click the Blue team player (non-encryptor) who will be the clicker for the whole game.")

# ─── Change 3 (part B): new emptyAction to compute redTeam/blueTeam ──────────
def make_team_entry(name, team_id):
    return {
        "name": name,
        "value": {
            "selector": "getPlayersFromTeam",
            "params": [{"name": "teamId", "type": "preset", "value": team_id}]
        }
    }

def make_length_entry(name, list_var):
    return {
        "name": name,
        "value": {
            "selector": "listLength",
            "params": [{"name": "list", "type": "cached", "value": list_var}]
        }
    }

team_compute_action = {
    "key": "emptyAction",
    "saveValueInCache": [
        make_team_entry("redTeam",  "red"),
        make_team_entry("blueTeam", "blue"),
        make_length_entry("redTeamSize",  "redTeam"),
        make_length_entry("blueTeamSize", "blueTeam"),
    ]
}

# ─── Reassemble BLA ───────────────────────────────────────────────────────────
new_bla = (
    bla[:12]           # [0..11]: unchanged (except [5] and [11] modified in-place above)
    + [new_vote_red,   # [12] clicker vote red
       new_vote_blue,  # [13] clicker vote blue
       team_compute_action]  # [14] redTeam/blueTeam
    + display_block    # [15..22] removeAllHighlights .. showRole blue
    + deck_block       # [23..27] shuffledWords ... createTeamsConversationGroups
)

data['beforeLoopActions'] = new_bla
print(f"BLA length: {len(new_bla)} items (was 27, now {len(new_bla)})")

# ─── Change 5: GL-9 – add 6 clue history createCard actions ──────────────────
gl9 = gl[35]
assert gl9['name'] == 'GL-9 Round End', f"Expected GL-9 at index 35, got {gl9['name']}"

def make_clue_card(bg_color, clue_var, code_digit_var, deck_prefix):
    return {
        "key": "createCard",
        "payload": {
            "preset": {
                "background": bg_color,
                "textColor": "white",
                "fontHeightPercentage": 10,
                "facedown": False
            },
            "cached": {
                "cardText": clue_var
            },
            "computed": {
                "deck": {
                    "selector": "formatString",
                    "params": [
                        {"name": "format", "type": "preset", "value": f"{deck_prefix}_($1)"},
                        {"name": "arg1", "type": "cached", "value": code_digit_var}
                    ]
                }
            }
        }
    }

clue_cards = [
    make_clue_card("#D83232", "redClue1",  "redCodeDigit1",  "red"),
    make_clue_card("#D83232", "redClue2",  "redCodeDigit2",  "red"),
    make_clue_card("#D83232", "redClue3",  "redCodeDigit3",  "red"),
    make_clue_card("#4EC1D0", "blueClue1", "blueCodeDigit1", "blue"),
    make_clue_card("#4EC1D0", "blueClue2", "blueCodeDigit2", "blue"),
    make_clue_card("#4EC1D0", "blueClue3", "blueCodeDigit3", "blue"),
]

# Find the position of the "Round X begins" notification (last item in GL-9 actions)
# and insert clue cards just before it.
# Current GL-9 actions:
#   0: setRole redPlayer → redEncryptor
#   1: setRole bluePlayer → blueEncryptor
#   2: setRole redPlayer → redActiveClicker
#   3: setRole bluePlayer → blueActiveClicker
#   4: emptyAction (roundNumber, isActionLoop)
#   5: createNotification Red's code
#   6: createNotification Blue's code
#   7: createNotification "Round X begins" (skipCondition)
# Insert clue cards at position 7 (before "Round X begins").
actions = gl9['actions']
insert_pos = 7
assert len(actions) == 8, f"Expected 8 actions in GL-9, got {len(actions)}"
assert actions[6]['key'] == 'createNotification', "Expected Blue code notification at GL-9[6]"
assert actions[7]['key'] == 'createNotification', "Expected Round-begins notification at GL-9[7]"

gl9['actions'] = actions[:insert_pos] + clue_cards + actions[insert_pos:]
print(f"GL-9 actions: {len(gl9['actions'])} (was 8, now {len(gl9['actions'])})")

# ─── Write output ─────────────────────────────────────────────────────────────
with open('game_jsons/enigma.json', 'w') as f:
    json.dump(data, f, indent=4, ensure_ascii=False)

print("Changes applied.")

# ─── Validate ─────────────────────────────────────────────────────────────────
import subprocess, sys
result = subprocess.run(
    [sys.executable, 'documentation/validate_game_json.py', 'game_jsons/enigma.json'],
    capture_output=True, text=True
)
print(result.stdout)
if result.stderr:
    print(result.stderr)
