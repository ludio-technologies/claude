"""
Applies 4 feedback changes:

1. Add overrideSpellCheck:true to all createInput presets
2. Fix codeword in createInput question: getDeckLabel should use the actual
   position deck (red_{codeDigitN}) not the hardcoded deck (red_N)
3. Rename rank/points/weight → digit1/digit2/digit3 in enigma_cards.json
   and update the corresponding getObjectField calls in the game JSON
4. Add checkWinCondition:true to GL-9 (Round End group)
"""
import json

# ─── Load files ───────────────────────────────────────────────────────────────
with open('game_jsons/enigma.json', 'r') as f:
    data = json.load(f)
with open('game_jsons/enigma_cards.json', 'r') as f:
    cards_data = json.load(f)

gl  = data['gameLoop']

# ─── Change 1: overrideSpellCheck:true on all createInput presets ─────────────
count = 0
for g in gl:
    if not isinstance(g, dict): continue
    for a in g.get('actions', []):
        if a.get('key') == 'createInput':
            a['payload']['preset']['overrideSpellCheck'] = True
            count += 1
print(f"Change 1 done: added overrideSpellCheck to {count} createInput actions")

# ─── Change 2: Fix codeword reference in createInput question ─────────────────
# For each clue N (1..3), arg2 of the question formatString currently uses
# getDeckLabel("red_N") or getDeckLabel("blue_N").
# It should use getDeckLabel(formatString("red/blue_($1)", redCodeDigitN)).
#
# Mapping: GL index → (team_prefix, digit_var)
clue_fixes = {
    11: ("red",  "redCodeDigit1"),
    12: ("red",  "redCodeDigit2"),
    13: ("red",  "redCodeDigit3"),
    14: ("blue", "blueCodeDigit1"),
    15: ("blue", "blueCodeDigit2"),
    16: ("blue", "blueCodeDigit3"),
}

for gi, (prefix, digit_var) in clue_fixes.items():
    g = gl[gi]
    a = g['actions'][0]
    q_params = a['payload']['computed']['question']['params']
    # arg2 is at index 2
    arg2 = q_params[2]
    assert arg2['name'] == 'arg2', f"Expected arg2 at index 2 in GL[{gi}]"
    # Replace the inner getDeckLabel deck param from preset → computed formatString
    arg2['value'] = {
        "selector": "getDeckLabel",
        "params": [
            {
                "name": "deck",
                "type": "computed",
                "value": {
                    "selector": "formatString",
                    "params": [
                        {"name": "format", "type": "preset", "value": f"{prefix}_($1)"},
                        {"name": "arg1",   "type": "cached",  "value": digit_var}
                    ]
                }
            }
        ]
    }
    print(f"  Fixed GL[{gi}] {g['name']}: getDeckLabel now uses {prefix}_(${digit_var})")

print("Change 2 done")

# ─── Change 3: Rename rank/points/weight → digit1/digit2/digit3 ───────────────

# 3a: Update enigma_cards.json
for card in cards_data['cards']:
    card['digit1'] = card.pop('rank')
    card['digit2'] = card.pop('points')
    card['digit3'] = card.pop('weight')

with open('game_jsons/enigma_cards.json', 'w') as f:
    json.dump(cards_data, f, indent=4, ensure_ascii=False)
print("Change 3a done: enigma_cards.json fields renamed (rank→digit1, points→digit2, weight→digit3)")

# 3b: Update getObjectField calls in game JSON
field_map = {"rank": "digit1", "points": "digit2", "weight": "digit3"}

def fix_field_names(obj):
    if isinstance(obj, dict):
        if obj.get('selector') == 'getObjectField':
            for p in obj.get('params', []):
                if p.get('name') == 'field' and p.get('value') in field_map:
                    p['value'] = field_map[p['value']]
        for v in obj.values():
            fix_field_names(v)
    elif isinstance(obj, list):
        for item in obj:
            fix_field_names(item)

fix_field_names(data)
print("Change 3b done: getObjectField calls updated in game JSON")

# ─── Change 4: Add checkWinCondition:true to GL-9 ────────────────────────────
gl9 = gl[35]
assert gl9['name'] == 'GL-9 Round End', f"Expected GL-9 at index 35, got {gl9['name']}"
gl9['checkWinCondition'] = True
print("Change 4 done: checkWinCondition:true added to GL-9 Round End")

# ─── Write game JSON ──────────────────────────────────────────────────────────
with open('game_jsons/enigma.json', 'w') as f:
    json.dump(data, f, indent=4, ensure_ascii=False)
print("\nAll changes written.")

# ─── Validate ─────────────────────────────────────────────────────────────────
import subprocess, sys
result = subprocess.run(
    [sys.executable, 'documentation/validate_game_json.py', 'game_jsons/enigma.json'],
    capture_output=True, text=True
)
print(result.stdout)
if result.stderr:
    print(result.stderr)
