"""
Applies 3 changes to enigma.json:

1. Widget layout: dimensions [2,5] → [5,2]; add ratio:1.6 to all createCard
   and createGenericCardWidget presets (landscape cards)

2. Action group field order: name → repeat/parallel → skipCondition → actions
   → checkWinCondition (reorder all action groups in gameLoop)

3. Reduce changeLayout vertical percent: 55 → 50
"""
import json

with open('game_jsons/enigma.json', 'r') as f:
    data = json.load(f)

gl  = data['gameLoop']
bla = data['beforeLoopActions']

# ─── Change 1: dimensions + ratio ─────────────────────────────────────────────

count_card = 0
count_widget = 0

for g in gl:
    if not isinstance(g, dict):
        continue
    for a in g.get('actions', []):
        key = a.get('key')
        if key == 'createCard':
            a['payload']['preset']['ratio'] = 1.6
            count_card += 1
        elif key == 'createGenericCardWidget':
            preset = a['payload']['preset']
            preset['dimensions'] = [5, 2]
            preset['ratio'] = 1.6
            count_widget += 1

print(f"Change 1: ratio:1.6 added to {count_card} createCard and {count_widget} createGenericCardWidget")

# ─── Change 2: Reorder action group fields ────────────────────────────────────
# Desired order: name, repeat/parallel, skipCondition, actions, checkWinCondition

FIELD_ORDER = ['name', 'repeat', 'parallel', 'skipCondition', 'actions', 'checkWinCondition']

def reorder_group(g):
    if not isinstance(g, dict) or 'actions' not in g:
        return g
    ordered = {}
    for k in FIELD_ORDER:
        if k in g:
            ordered[k] = g[k]
    # Any unexpected extra keys go at end
    for k, v in g.items():
        if k not in ordered:
            ordered[k] = v
    return ordered

new_gl = []
reordered = 0
for g in gl:
    if isinstance(g, list):
        # nested loop (bracket group) — reorder items inside too
        new_gl.append([reorder_group(item) for item in g])
    else:
        new_g = reorder_group(g)
        if list(new_g.keys()) != list(g.keys()):
            reordered += 1
        new_gl.append(new_g)

data['gameLoop'] = new_gl
print(f"Change 2: {reordered} action groups had field order corrected")

# ─── Change 3: Reduce changeLayout percent 55 → 50 ───────────────────────────
for a in bla:
    if isinstance(a, dict) and a.get('key') == 'changeLayout':
        old = a['payload']['preset']['percent']
        a['payload']['preset']['percent'] = 50
        print(f"Change 3: changeLayout percent {old} → 50")

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
