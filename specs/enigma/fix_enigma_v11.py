"""
Applies 3 changes to enigma.json:

1. Fix turn order: intercept result notification now shown BEFORE own-team decode
   (reverts the fix_enigma_v8 reordering that put decode before 7a/7b Result)
   Red phase:  intercept1/2/3 → 7a_result → decode1/2/3 → 6a_result
   Blue phase: intercept1/2/3 → 7b_result → decode1/2/3 → 6b_result

2. Remove "ratio" field from all createCard and createGenericCardWidget preset payloads

3. Remove the extraneous "isActionLoop" field from GL-9 action group
"""
import json, copy

with open('game_jsons/enigma.json', 'r') as f:
    data = json.load(f)

gl = data['gameLoop']

# ─── Change 1: Fix turn order ─────────────────────────────────────────────────
# Current red phase:  [14,15,16]=intercept, [17,18,19]=decode, [20]=7a_result, [21]=6a_result
# Desired red phase:  [14,15,16]=intercept, [17]=7a_result, [18,19,20]=decode, [21]=6a_result

g_7a = gl[20]
gl[17], gl[18], gl[19], gl[20] = g_7a, gl[17], gl[18], gl[19]
assert gl[17]['name'] == 'GL-7a Result', f"Unexpected: {gl[17]['name']}"
assert gl[20]['name'] == 'GL-6a Red Decode Click 3', f"Unexpected: {gl[20]['name']}"
print(f"Change 1: Red phase reordered — GL[17]={gl[17]['name']}, GL[18]={gl[18]['name']}")

# Current blue phase: [27,28,29]=intercept, [30,31,32]=decode, [33]=7b_result, [34]=6b_result
# Desired blue phase: [27,28,29]=intercept, [30]=7b_result, [31,32,33]=decode, [34]=6b_result

g_7b = gl[33]
gl[30], gl[31], gl[32], gl[33] = g_7b, gl[30], gl[31], gl[32]
assert gl[30]['name'] == 'GL-7b Result', f"Unexpected: {gl[30]['name']}"
assert gl[33]['name'] == 'GL-6b Blue Decode Click 3', f"Unexpected: {gl[33]['name']}"
print(f"Change 1: Blue phase reordered — GL[30]={gl[30]['name']}, GL[31]={gl[31]['name']}")

# ─── Change 2: Remove ratio from createCard and createGenericCardWidget ───────
count_card = 0
count_widget = 0

for g in gl:
    if not isinstance(g, dict):
        continue
    for a in g.get('actions', []):
        key = a.get('key')
        if key == 'createCard':
            preset = a.get('payload', {}).get('preset', {})
            if 'ratio' in preset:
                del preset['ratio']
                count_card += 1
        elif key == 'createGenericCardWidget':
            preset = a.get('payload', {}).get('preset', {})
            if 'ratio' in preset:
                del preset['ratio']
                count_widget += 1

print(f"Change 2: removed ratio from {count_card} createCard and {count_widget} createGenericCardWidget actions")

# ─── Change 3: Remove isActionLoop from GL-9 action group ─────────────────────
removed = 0
for i, g in enumerate(gl):
    if isinstance(g, dict) and 'isActionLoop' in g:
        del g['isActionLoop']
        removed += 1
        print(f"Change 3: removed isActionLoop from GL[{i}] {g['name']}")

if removed == 0:
    print("Change 3: isActionLoop not found (already removed?)")

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
