"""
Applies 2 structural changes to enigma.json:

1. BLA reorder: after encryptors vote → compute teams → layout+highlights → THEN clicker votes

2. GL reorder: implement proper turn sequence
   - Red encryptor gives 3 clues
   - (Skip R1) Blue intercepts (3 clicks) → immediate result + clear highlights
   - Red decodes (3 clicks) → immediate result + clear highlights
   - Blue encryptor gives 3 clues
   - (Skip R1) Red intercepts (3 clicks) → immediate result + clear highlights
   - Blue decodes (3 clicks) → immediate result + clear highlights
   - Scoring groups
   - Round end
"""
import json

with open('game_jsons/enigma.json', 'r') as f:
    data = json.load(f)

bla = data['beforeLoopActions']
gl  = data['gameLoop']

# ─── Change 1: Reorder BLA[12-18] ────────────────────────────────────────────
# Current: [12]=redClickerVote, [13]=blueClickerVote, [14]=teamCompute,
#          [15]=removeHighlights, [16]=highlightRed, [17]=highlightBlue, [18]=changeLayout
# New:     [12]=teamCompute, [13]=removeHighlights, [14]=highlightRed,
#          [15]=highlightBlue, [16]=changeLayout, [17]=redClickerVote, [18]=blueClickerVote

segment = bla[12:19]  # 7 items
red_vote   = segment[0]   # createVote redClicker
blue_vote  = segment[1]   # createVote blueClicker
team_comp  = segment[2]   # emptyAction redTeam/blueTeam
rem_high   = segment[3]   # removeAllHighlights
high_red   = segment[4]   # highlightPlayers red
high_blue  = segment[5]   # highlightPlayers blue
ch_layout  = segment[6]   # changeLayout

bla[12:19] = [team_comp, rem_high, high_red, high_blue, ch_layout, red_vote, blue_vote]
print("Change 1 done: BLA reordered (layout+highlights before clicker votes)")

data['beforeLoopActions'] = bla

# ─── Change 2: Restructure gameLoop ──────────────────────────────────────────
# Extract current groups by their current index

g_tutorial    = gl[0]
g_cr_red_pos  = gl[1]
g_cr_blue_pos = gl[2]
g_cr_red_clu  = gl[3]
g_cr_blue_clu = gl[4]
g_widget      = gl[5]
g_gl1         = gl[6]   # GL-1 Assign Encryptors → MODIFY
g_gl2a        = gl[7]   # GL-2a Pick Red Code Card
g_gl2b        = gl[8]   # GL-2b Pick Blue Code Card
g_gl3a        = gl[9]   # GL-3a Notify Red Encryptor
g_gl3b        = gl[10]  # GL-3b Notify Blue Encryptor → MOVE
g_gl4a1       = gl[11]  # GL-4a Red Clue 1
g_gl4a2       = gl[12]  # GL-4a Red Clue 2
g_gl4a3       = gl[13]  # GL-4a Red Clue 3
g_gl4b1       = gl[14]  # GL-4b Blue Clue 1 → MOVE
g_gl4b2       = gl[15]  # GL-4b Blue Clue 2 → MOVE
g_gl4b3       = gl[16]  # GL-4b Blue Clue 3 → MOVE
g_gl5         = gl[17]  # GL-5 Reveal Clues → SPLIT
g_gl6a1       = gl[18]  # GL-6a Red Decode Click 1
g_gl6a2       = gl[19]  # GL-6a Red Decode Click 2
g_gl6a3       = gl[20]  # GL-6a Red Decode Click 3
g_gl6b1       = gl[21]  # GL-6b Blue Decode Click 1 → MOVE
g_gl6b2       = gl[22]  # GL-6b Blue Decode Click 2 → MOVE
g_gl6b3       = gl[23]  # GL-6b Blue Decode Click 3 → MOVE
g_gl7a1       = gl[24]  # GL-7a Blue Intercepts Red Click 1 → MOVE + skip R1
g_gl7a2       = gl[25]  # GL-7a Blue Intercepts Red Click 2 → MOVE + skip R1
g_gl7a3       = gl[26]  # GL-7a Blue Intercepts Red Click 3 → MOVE + skip R1
g_gl7b1       = gl[27]  # GL-7b Red Intercepts Blue Click 1 → skip R1
g_gl7b2       = gl[28]  # GL-7b Red Intercepts Blue Click 2 → skip R1
g_gl7b3       = gl[29]  # GL-7b Red Intercepts Blue Click 3 → skip R1
# gl[30] = GL-8 Compute Results → REMOVED (computed inline)
g_gl8a        = gl[31]  # GL-8a Red Botch
g_gl8b        = gl[32]  # GL-8b Blue Botch
g_gl8c        = gl[33]  # GL-8c Blue Breaks Red
g_gl8d        = gl[34]  # GL-8d Red Breaks Blue
g_gl9         = gl[35]  # GL-9 Round End

# ── Modify GL-1: init interception results to false each round ────────────────
gl1_svc = g_gl1['actions'][1]['saveValueInCache']  # [0] is removeAllHighlightDecks
# Prepend initialization entries
interception_init = [
    {"name": "blueInterceptionCorrect", "value": False},
    {"name": "redInterceptionCorrect",  "value": False},
]
g_gl1['actions'][0]['saveValueInCache'] = interception_init + gl1_svc
print("GL-1 modified: interception result variables initialized to false")

# ── Split GL-5 into GL-5a (red) and GL-5b (blue) ─────────────────────────────
gl5_actions = g_gl5['actions']
# actions[0] = red notification, [1] = blue notification, [2] = red_clues card, [3] = blue_clues card
g_gl5a = {
    "name": "GL-5a Reveal Red Clues",
    "actions": [gl5_actions[0], gl5_actions[2]]
}
g_gl5b = {
    "name": "GL-5b Reveal Blue Clues",
    "actions": [gl5_actions[1], gl5_actions[3]]
}
print("GL-5 split into GL-5a and GL-5b")

# ── skipCondition for R1 ──────────────────────────────────────────────────────
def skip_r1():
    return [{"selector": "equals", "params": [
        {"name": "arg1", "type": "cached", "value": "gameLoopIndex"},
        {"name": "arg2", "type": "preset", "value": 0}
    ]}]

for g in [g_gl7a1, g_gl7a2, g_gl7a3, g_gl7b1, g_gl7b2, g_gl7b3]:
    g['skipCondition'] = skip_r1()
print("Skip-R1 condition added to all intercept click groups")

# ── Helper: build result group ────────────────────────────────────────────────
def make_list_to_string_entry(v1, v2, v3):
    return {
        "selector": "listToString",
        "params": [{"name": "list", "type": "computed", "value": {
            "selector": "createList",
            "params": [
                {"name": "arg1", "type": "cached", "value": v1},
                {"name": "arg2", "type": "cached", "value": v2},
                {"name": "arg3", "type": "cached", "value": v3},
            ]
        }}]
    }

def make_result_group(name, result_var, clicked_vars, code_vars, bg_color, team_label, do_skip_r1=False):
    g1, g2, g3 = clicked_vars
    c1, c2, c3 = code_vars
    group = {
        "name": name,
        "actions": [
            {
                "key": "emptyAction",
                "saveValueInCache": [{
                    "name": result_var,
                    "value": {
                        "selector": "equals",
                        "params": [
                            {"name": "arg1", "type": "computed",
                             "value": make_list_to_string_entry(g1, g2, g3)},
                            {"name": "arg2", "type": "computed",
                             "value": make_list_to_string_entry(c1, c2, c3)}
                        ]
                    }
                }]
            },
            {
                "key": "createNotification",
                "payload": {
                    "preset": {
                        "duration": 6,
                        "backgroundColor": bg_color,
                        "borderColor": "white",
                        "textColor": "white"
                    },
                    "computed": {
                        "to": {"selector": "allUsers"},
                        "header": {
                            "selector": "ifElse",
                            "params": [
                                {"name": "condition", "type": "computed", "value": {
                                    "selector": "getCachedValue",
                                    "params": [{"name": "name", "type": "preset", "value": result_var}]
                                }},
                                {"name": "thenValue", "type": "preset", "value": "Correct!"},
                                {"name": "elseValue", "type": "preset", "value": "Incorrect."}
                            ]
                        },
                        "text": {
                            "selector": "formatString",
                            "params": [
                                {"name": "format", "type": "preset",
                                 "value": f"{team_label} clicked ($1)–($2)–($3) — code: ($4)–($5)–($6)"},
                                {"name": "arg1", "type": "cached", "value": g1},
                                {"name": "arg2", "type": "cached", "value": g2},
                                {"name": "arg3", "type": "cached", "value": g3},
                                {"name": "arg4", "type": "cached", "value": c1},
                                {"name": "arg5", "type": "cached", "value": c2},
                                {"name": "arg6", "type": "cached", "value": c3},
                            ]
                        }
                    }
                }
            },
            {"key": "removeAllHighlightDecks"}
        ]
    }
    if do_skip_r1:
        group["skipCondition"] = skip_r1()
    return group

# Build the 4 result groups
g_gl7a_result = make_result_group(
    "GL-7a Result",
    "blueInterceptionCorrect",
    ("big1", "big2", "big3"),
    ("redCodeDigit1", "redCodeDigit2", "redCodeDigit3"),
    "#4EC1D0", "Blue", do_skip_r1=True
)
g_gl6a_result = make_result_group(
    "GL-6a Result",
    "redDecodeCorrect",
    ("rdg1", "rdg2", "rdg3"),
    ("redCodeDigit1", "redCodeDigit2", "redCodeDigit3"),
    "#D83232", "Red", do_skip_r1=False
)
g_gl7b_result = make_result_group(
    "GL-7b Result",
    "redInterceptionCorrect",
    ("rig1", "rig2", "rig3"),
    ("blueCodeDigit1", "blueCodeDigit2", "blueCodeDigit3"),
    "#D83232", "Red", do_skip_r1=True
)
g_gl6b_result = make_result_group(
    "GL-6b Result",
    "blueDecodeCorrect",
    ("bdg1", "bdg2", "bdg3"),
    ("blueCodeDigit1", "blueCodeDigit2", "blueCodeDigit3"),
    "#4EC1D0", "Blue", do_skip_r1=False
)
print("4 result groups created")

# ── Reassemble gameLoop ───────────────────────────────────────────────────────
new_gl = [
    g_tutorial,        # [0]
    g_cr_red_pos,      # [1]
    g_cr_blue_pos,     # [2]
    g_cr_red_clu,      # [3]
    g_cr_blue_clu,     # [4]
    g_widget,          # [5]
    g_gl1,             # [6] GL-1 Assign Encryptors (modified)

    # ── Red Phase ──────────────────────────────────────────────────────────
    g_gl2a,            # [7]  GL-2a Pick Red Code Card
    g_gl2b,            # [8]  GL-2b Pick Blue Code Card
    g_gl3a,            # [9]  GL-3a Notify Red Encryptor
    g_gl4a1,           # [10] GL-4a Red Clue 1
    g_gl4a2,           # [11] GL-4a Red Clue 2
    g_gl4a3,           # [12] GL-4a Red Clue 3
    g_gl5a,            # [13] GL-5a Reveal Red Clues

    g_gl7a1,           # [14] GL-7a Blue Intercepts Red Click 1 (skip R1)
    g_gl7a2,           # [15] GL-7a Blue Intercepts Red Click 2 (skip R1)
    g_gl7a3,           # [16] GL-7a Blue Intercepts Red Click 3 (skip R1)
    g_gl7a_result,     # [17] GL-7a Result                       (skip R1)

    g_gl6a1,           # [18] GL-6a Red Decode Click 1
    g_gl6a2,           # [19] GL-6a Red Decode Click 2
    g_gl6a3,           # [20] GL-6a Red Decode Click 3
    g_gl6a_result,     # [21] GL-6a Result

    # ── Blue Phase ──────────────────────────────────────────────────────────
    g_gl3b,            # [22] GL-3b Notify Blue Encryptor
    g_gl4b1,           # [23] GL-4b Blue Clue 1
    g_gl4b2,           # [24] GL-4b Blue Clue 2
    g_gl4b3,           # [25] GL-4b Blue Clue 3
    g_gl5b,            # [26] GL-5b Reveal Blue Clues

    g_gl7b1,           # [27] GL-7b Red Intercepts Blue Click 1 (skip R1)
    g_gl7b2,           # [28] GL-7b Red Intercepts Blue Click 2 (skip R1)
    g_gl7b3,           # [29] GL-7b Red Intercepts Blue Click 3 (skip R1)
    g_gl7b_result,     # [30] GL-7b Result                       (skip R1)

    g_gl6b1,           # [31] GL-6b Blue Decode Click 1
    g_gl6b2,           # [32] GL-6b Blue Decode Click 2
    g_gl6b3,           # [33] GL-6b Blue Decode Click 3
    g_gl6b_result,     # [34] GL-6b Result

    # ── Scoring + End ───────────────────────────────────────────────────────
    g_gl8a,            # [35] GL-8a Red Botch
    g_gl8b,            # [36] GL-8b Blue Botch
    g_gl8c,            # [37] GL-8c Blue Breaks Red
    g_gl8d,            # [38] GL-8d Red Breaks Blue
    g_gl9,             # [39] GL-9 Round End
]

data['gameLoop'] = new_gl
print(f"gameLoop reassembled: {len(new_gl)} groups (was {len(gl)})")

# ─── Write output ─────────────────────────────────────────────────────────────
with open('game_jsons/enigma.json', 'w') as f:
    json.dump(data, f, indent=4, ensure_ascii=False)
print("Changes written.")

# ─── Validate ─────────────────────────────────────────────────────────────────
import subprocess, sys
result = subprocess.run(
    [sys.executable, 'documentation/validate_game_json.py', 'game_jsons/enigma.json'],
    capture_output=True, text=True
)
print(result.stdout)
if result.stderr:
    print(result.stderr)
