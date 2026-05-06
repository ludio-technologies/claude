"""
Applies 6 changes to enigma.json:

1. createGenericCardWidget ratio: float 1.6 → string "1.6"
2. showResultDuration:1 on encryptor + clicker createVote actions (BLA[5,17,18])
3. Increase fontHeightPercentage on all createCard actions slightly
4. createGenericCardWidget dimensions: [5,2] → [2,5]
5. Interception result notifications: remove from GL-6a/6b Result (own-team decode);
   update GL-7a/7b Result headers to "[Team] broke/failed to break [Other]'s code!",
   remove text
6. Add trailing period to botch notification text (GL-8a/8b)
"""
import json

with open('game_jsons/enigma.json', 'r') as f:
    data = json.load(f)

gl  = data['gameLoop']
bla = data['beforeLoopActions']

# ─── Change 1: Widget ratio float → string ────────────────────────────────────
for g in gl:
    if not isinstance(g, dict): continue
    for a in g.get('actions', []):
        if a.get('key') == 'createGenericCardWidget':
            a['payload']['preset']['ratio'] = "1.6"
            print("Change 1: createGenericCardWidget ratio set to string '1.6'")

# ─── Change 2: showResultDuration:1 on encryptor/clicker votes ───────────────
vote_indices = [5, 17, 18]
for i in vote_indices:
    a = bla[i]
    assert a.get('key') == 'createVote', f"Expected createVote at BLA[{i}]"
    a['payload']['preset']['showResultDuration'] = 1
    print(f"Change 2: BLA[{i}] '{a['payload']['preset']['title']}' — showResultDuration=1")

# ─── Change 3: Increase fontHeightPercentage on all createCard actions ────────
FONT_INCREASES = {20: 25, 7: 9, 10: 13}
for g in gl:
    if not isinstance(g, dict): continue
    for a in g.get('actions', []):
        if a.get('key') == 'createCard':
            old = a['payload']['preset'].get('fontHeightPercentage')
            if old in FONT_INCREASES:
                a['payload']['preset']['fontHeightPercentage'] = FONT_INCREASES[old]
print(f"Change 3: fontHeightPercentage increased: {FONT_INCREASES}")

# ─── Change 4: Widget dimensions [5,2] → [2,5] ───────────────────────────────
for g in gl:
    if not isinstance(g, dict): continue
    for a in g.get('actions', []):
        if a.get('key') == 'createGenericCardWidget':
            a['payload']['preset']['dimensions'] = [2, 5]
            print("Change 4: createGenericCardWidget dimensions set to [2, 5]")

# ─── Change 5: Fix interception result notifications ─────────────────────────
# GL-6a Result [21] and GL-6b Result [34]: remove createNotification (own-team decode)
for idx in [21, 34]:
    g = gl[idx]
    before = len(g['actions'])
    g['actions'] = [a for a in g['actions'] if a.get('key') != 'createNotification']
    print(f"Change 5: GL[{idx}] {g['name']} — removed {before - len(g['actions'])} createNotification")

# GL-7a Result [20]: Blue intercepts Red — update header, remove text
g20 = gl[20]
for a in g20['actions']:
    if a.get('key') == 'createNotification':
        a['payload']['computed']['header'] = {
            "selector": "ifElse",
            "params": [
                {"name": "condition", "type": "computed", "value": {
                    "selector": "getCachedValue",
                    "params": [{"name": "name", "type": "preset", "value": "blueInterceptionCorrect"}]
                }},
                {"name": "thenValue", "type": "preset", "value": "Blue broke Red's code!"},
                {"name": "elseValue", "type": "preset", "value": "Blue failed to break Red's code!"}
            ]
        }
        a['payload']['computed'].pop('text', None)
        print(f"Change 5: GL[20] {g20['name']} — header updated, text removed")

# GL-7b Result [33]: Red intercepts Blue — update header, remove text
g33 = gl[33]
for a in g33['actions']:
    if a.get('key') == 'createNotification':
        a['payload']['computed']['header'] = {
            "selector": "ifElse",
            "params": [
                {"name": "condition", "type": "computed", "value": {
                    "selector": "getCachedValue",
                    "params": [{"name": "name", "type": "preset", "value": "redInterceptionCorrect"}]
                }},
                {"name": "thenValue", "type": "preset", "value": "Red broke Blue's code!"},
                {"name": "elseValue", "type": "preset", "value": "Red failed to break Blue's code!"}
            ]
        }
        a['payload']['computed'].pop('text', None)
        print(f"Change 5: GL[33] {g33['name']} — header updated, text removed")

# ─── Change 6: Add trailing period to botch notification text ─────────────────
for idx in [35, 36]:
    g = gl[idx]
    for a in g['actions']:
        if a.get('key') == 'createNotification':
            for p in a['payload']['computed']['text']['params']:
                if p.get('name') == 'format':
                    if not p['value'].endswith('.'):
                        p['value'] += '.'
                        print(f"Change 6: GL[{idx}] {g['name']} — added trailing period to text format")

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
