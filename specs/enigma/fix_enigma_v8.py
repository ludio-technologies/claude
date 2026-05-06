"""
Applies 3 changes to enigma.json:

1. Score → deck labels: remove showScore/updateScore, add setDeckLabel on
   red_clues/blue_clues with "+breaks, -botches" format in GL-1 (init) and GL-9 (update)

2. Delay intercept reveal: move decode clicks before result groups so the
   outcome isn't shown until after the original team has also guessed
   Red phase: intercept1/2/3 → decode1/2/3 → 7a_result → 6a_result
   Blue phase: intercept1/2/3 → decode1/2/3 → 7b_result → 6b_result

3. Breakout rooms: remove from BLA, create in GL-5a/5b after clues revealed,
   destroy at start of result groups (both intercept+decode results for R1 safety)
"""
import json, copy

with open('game_jsons/enigma.json', 'r') as f:
    data = json.load(f)

gl  = data['gameLoop']
bla = data['beforeLoopActions']

# ─── Change 1: Score → deck labels ───────────────────────────────────────────

# 1a: Remove showScore from BLA
bla_new = [a for a in bla if not (isinstance(a, dict) and a.get('key') == 'showScore')]
print(f"Change 1a: removed {len(bla) - len(bla_new)} showScore action(s) from BLA")
data['beforeLoopActions'] = bla_new
bla = bla_new

# 1b: Remove updateScore from GL-8a/8b/8c/8d (indices 35-38)
for idx in [35, 36, 37, 38]:
    g = gl[idx]
    before = len(g['actions'])
    g['actions'] = [a for a in g['actions'] if a.get('key') != 'updateScore']
    print(f"Change 1b: GL[{idx}] {g['name']} — removed {before - len(g['actions'])} updateScore")

# 1c: Remove break-count text from GL-8c/8d notifications (label replaces it)
for idx in [37, 38]:
    g = gl[idx]
    for a in g['actions']:
        if a.get('key') == 'createNotification':
            a['payload']['computed'].pop('text', None)
    print(f"Change 1c: GL[{idx}] {g['name']} — removed break count from notification text")

# 1d: Build setDeckLabel helper
def make_set_deck_label(deck_name, breaks_var, botches_var):
    return {
        "key": "setDeckLabel",
        "payload": {
            "preset": {"deck": deck_name},
            "computed": {
                "label": {
                    "selector": "formatString",
                    "params": [
                        {"name": "format", "type": "preset", "value": "+($1), -($2)"},
                        {"name": "arg1", "type": "cached", "value": breaks_var},
                        {"name": "arg2", "type": "cached", "value": botches_var},
                    ]
                }
            }
        }
    }

label_actions = [
    make_set_deck_label("red_clues",  "redBreaks",  "redBotches"),
    make_set_deck_label("blue_clues", "blueBreaks", "blueBotches"),
]

# 1e: Init labels at start of GL-1 (runs every round, shows current state)
gl[6]['actions'] = copy.deepcopy(label_actions) + gl[6]['actions']
print("Change 1e: setDeckLabel init added at start of GL-1")

# 1f: Update labels at start of GL-9 (after GL-8a-8d have updated counters)
gl[39]['actions'] = copy.deepcopy(label_actions) + gl[39]['actions']
print("Change 1f: setDeckLabel update added at start of GL-9")

# ─── Change 2: Delay intercept result ────────────────────────────────────────
# Red phase: [14,15,16]=intercept, [17]=7a_result, [18,19,20]=decode, [21]=6a_result
# → new:     [14,15,16]=intercept, [17,18,19]=decode, [20]=7a_result, [21]=6a_result
g_7a_result = gl[17]
gl[17], gl[18], gl[19], gl[20] = gl[18], gl[19], gl[20], g_7a_result
print(f"Change 2: Red phase reordered — decode before result, GL[20] is now {gl[20]['name']}")

# Blue phase: [27,28,29]=intercept, [30]=7b_result, [31,32,33]=decode, [34]=6b_result
# → new:      [27,28,29]=intercept, [30,31,32]=decode, [33]=7b_result, [34]=6b_result
g_7b_result = gl[30]
gl[30], gl[31], gl[32], gl[33] = gl[31], gl[32], gl[33], g_7b_result
print(f"Change 2: Blue phase reordered — decode before result, GL[33] is now {gl[33]['name']}")

# ─── Change 3: Breakout rooms timing ─────────────────────────────────────────
# 3a: Remove createTeamsConversationGroups from BLA
bla_new = [a for a in bla if not (isinstance(a, dict) and a.get('key') == 'createTeamsConversationGroups')]
print(f"Change 3a: removed {len(bla) - len(bla_new)} createTeamsConversationGroups from BLA")
data['beforeLoopActions'] = bla_new

create_rooms = {
    "key": "createTeamsConversationGroups",
    "payload": {
        "preset": {
            "video": True,
            "audio": True,
            "private": False,
            "indicator": "\U0001f512",
            "isVideoForAll": False
        }
    }
}
destroy_rooms = {"key": "destroyConversationGroups"}

# 3b: Add createTeamsConversationGroups at end of GL-5a (13) and GL-5b (26)
gl[13]['actions'].append(copy.deepcopy(create_rooms))
gl[26]['actions'].append(copy.deepcopy(create_rooms))
print("Change 3b: createTeamsConversationGroups appended to GL-5a (13) and GL-5b (26)")

# 3c: Add destroyConversationGroups at start of result groups
# GL-7a Result now at [20] (skipCondition R1) — destroys on R2+
# GL-6a Result at [21] (no skip)              — destroys on R1 (2nd call on R2+ is no-op)
# GL-7b Result now at [33] (skipCondition R1) — destroys on R2+
# GL-6b Result at [34] (no skip)              — destroys on R1
for idx, name in [(20, 'GL-7a Result'), (21, 'GL-6a Result'), (33, 'GL-7b Result'), (34, 'GL-6b Result')]:
    gl[idx]['actions'].insert(0, copy.deepcopy(destroy_rooms))
    print(f"Change 3c: destroyConversationGroups prepended to GL[{idx}] {gl[idx]['name']}")

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
