"""
Applies 4 notification changes to enigma.json:

1. GL-3a/3b (Notify Encryptor): remove codeword labels from text, reduce duration 15→8
2. GL-8a/8b (Botch): reduce duration 6→4, add code image, remove botch count from text
3. GL-9 (Round End): remove "Red's code" and "Blue's code" createNotification actions
4. GL-5a/5b (Reveal Clues): duration 10→1, add isAnnounceOnly:true
"""
import json

with open('game_jsons/enigma.json', 'r') as f:
    data = json.load(f)

gl = data['gameLoop']

# ─── Change 1: GL-3a / GL-3b Notify Encryptor ────────────────────────────────
for idx, team in [(9, 'red'), (22, 'blue')]:
    g = gl[idx]
    notif = g['actions'][0]
    assert notif['key'] == 'createNotification', f"Expected notification at GL[{idx}]"
    preset = notif['payload']['preset']

    # Reduce duration
    preset['duration'] = 8

    # Replace text with simple instruction only (no codeword labels)
    notif['payload']['computed']['text'] = {
        "selector": "formatString",
        "params": [
            {"name": "format", "type": "preset",
             "value": "Give ONE clue per position, in order."}
        ]
    }

    print(f"Change 1: GL[{idx}] {g['name']} — duration→8, text simplified")

# ─── Change 2: GL-8a / GL-8b Botch notifications ─────────────────────────────
# GL-8a: clicker var = redActiveClicker, guessed = rdg1/2/3, image = redCodeImage
# GL-8b: clicker var = blueActiveClicker, guessed = bdg1/2/3, image = blueCodeImage
botch_specs = [
    (35, 'redActiveClicker', 'rdg1',  'rdg2',  'rdg3',  'redCodeImage'),
    (36, 'blueActiveClicker','bdg1',  'bdg2',  'bdg3',  'blueCodeImage'),
]
for idx, clicker_var, g1, g2, g3, img_var in botch_specs:
    g = gl[idx]
    notif = g['actions'][3]   # [0]=emptyAction, [1]=updateScore, [2]=animateBox, [3]=createNotification
    assert notif['key'] == 'createNotification', f"Expected notification at GL[{idx}] actions[3]"

    # Reduce duration
    notif['payload']['preset']['duration'] = 4

    # Add code image
    notif['payload'].setdefault('cached', {})['image'] = img_var

    # Simplify text: remove botch count
    notif['payload']['computed']['text'] = {
        "selector": "formatString",
        "params": [
            {"name": "format", "type": "preset",
             "value": "($1) guessed ($2)—($3)—($4)"},
            {"name": "arg1", "type": "computed", "value": {
                "selector": "getPlayerNameById",
                "params": [{"name": "id", "type": "cached", "value": clicker_var}]
            }},
            {"name": "arg2", "type": "cached", "value": g1},
            {"name": "arg3", "type": "cached", "value": g2},
            {"name": "arg4", "type": "cached", "value": g3},
        ]
    }

    print(f"Change 2: GL[{idx}] {g['name']} — duration→4, image added, botch count removed")

# ─── Change 3: GL-9 remove "Red's code" and "Blue's code" notifications ───────
g39 = gl[39]
assert g39['name'] == 'GL-9 Round End'

# Identify and remove the two code-reveal notifications
# They are createNotification actions whose header contains "code:"
new_actions = []
removed = 0
for a in g39['actions']:
    if a.get('key') == 'createNotification':
        header = a.get('payload', {}).get('computed', {}).get('header', {})
        fmt = ''
        for p in header.get('params', []):
            if p.get('name') == 'format':
                fmt = p.get('value', '')
        if "code:" in fmt or "code: ($" in fmt or "'s code:" in fmt:
            removed += 1
            continue  # drop this notification
    new_actions.append(a)

g39['actions'] = new_actions
print(f"Change 3: GL-9 — removed {removed} code-reveal notification(s)")

# ─── Change 4: GL-5a / GL-5b Reveal Clues — isAnnounceOnly, duration 1 ───────
for idx in [13, 26]:
    g = gl[idx]
    notif = g['actions'][0]
    assert notif['key'] == 'createNotification', f"Expected notification at GL[{idx}]"
    notif['payload']['preset']['duration'] = 1
    notif['payload']['preset']['isAnnounceOnly'] = True
    print(f"Change 4: GL[{idx}] {g['name']} — duration→1, isAnnounceOnly→true")

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
