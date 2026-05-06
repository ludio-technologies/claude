"""
Applies 4 changes to enigma.json:

1. Add removeAllHighlightDecks at start of first decode-click group for each
   team (GL[17] = GL-6a Red Decode Click 1, GL[30] = GL-6b Blue Decode Click 1)

2. Remove ALL remaining updateScore and showScore (postGameActions + turnSpectatorToPlayerActions)
   Also remove the emptyAction that computes redFinalScore/blueFinalScore (only used for score)
   Remove scoreRef from turnSpectatorToPlayerActions emptyAction

3. Restructure winCondition to have 3 mutually exclusive keys: "red", "blue", "tie"
   Rewrite postGameActions winner notification: header uses 'winner' cached var,
   text shows breaks/botches without score references

4. Replace all \\n with <br/> in createNotification text formatString format values
"""
import json, re

with open('game_jsons/enigma.json', 'r') as f:
    data = json.load(f)

gl   = data['gameLoop']
bla  = data['beforeLoopActions']
pga  = data['postGameActions']
stpa = data.get('turnSpectatorToPlayerActions', [])

# ─── Change 1: removeAllHighlightDecks before decode clicks ──────────────────
clear = {"key": "removeAllHighlightDecks"}
gl[17]['actions'].insert(0, dict(clear))  # before GL-6a Red Decode Click 1
gl[30]['actions'].insert(0, dict(clear))  # before GL-6b Blue Decode Click 1
print("Change 1: removeAllHighlightDecks added at start of GL[17] and GL[30]")

# ─── Change 2: Remove all updateScore / showScore ────────────────────────────

# 2a: postGameActions — remove emptyAction computing scores + both updateScore
pga_new = []
for a in pga:
    k = a.get('key')
    if k == 'updateScore':
        print(f"Change 2: removed updateScore from postGameActions")
        continue
    if k == 'emptyAction':
        svc = a.get('saveValueInCache', [])
        names = [e['name'] for e in svc]
        if 'redFinalScore' in names or 'blueFinalScore' in names:
            print(f"Change 2: removed emptyAction computing final scores from postGameActions")
            continue
    pga_new.append(a)
data['postGameActions'] = pga_new

# 2b: turnSpectatorToPlayerActions — remove updateScore and showScore
#     Also strip scoreRef from the first emptyAction's saveValueInCache
stpa_new = []
for i, a in enumerate(stpa):
    k = a.get('key')
    if k in ('updateScore', 'showScore'):
        print(f"Change 2: removed {k} from turnSpectatorToPlayerActions")
        continue
    if k == 'emptyAction':
        svc = a.get('saveValueInCache', [])
        cleaned = [e for e in svc if e['name'] != 'scoreRef']
        if len(cleaned) < len(svc):
            a['saveValueInCache'] = cleaned
            print(f"Change 2: removed scoreRef from turnSpectatorToPlayerActions emptyAction")
    stpa_new.append(a)
data['turnSpectatorToPlayerActions'] = stpa_new

# ─── Change 3: Restructure winCondition + rewrite winner notification ─────────

def gte(var, val):
    return {"selector": "greaterThanOrEqual", "params": [
        {"name": "arg1", "type": "cached",  "value": var},
        {"name": "arg2", "type": "preset", "value": val},
    ]}

def lor(*selectors):
    return {"selector": "logicalOR", "params": [
        {"name": f"arg{i+1}", "type": "computed", "value": s}
        for i, s in enumerate(selectors)
    ]}

def land(*selectors):
    return {"selector": "logicalAND", "params": [
        {"name": f"arg{i+1}", "type": "computed", "value": s}
        for i, s in enumerate(selectors)
    ]}

def lnot(selector):
    return {"selector": "logicalNOT", "params": [
        {"name": "arg", "type": "computed", "value": selector}
    ]}

red_wins  = lor(gte("redBreaks", 2), gte("blueBotches", 2))
blue_wins = lor(gte("blueBreaks", 2), gte("redBotches", 2))

data['winCondition'] = {
    "red":  land(red_wins,  lnot(blue_wins)),
    "blue": land(blue_wins, lnot(red_wins)),
    "tie":  land(red_wins,  blue_wins),
}
print("Change 3: winCondition restructured with mutually exclusive red/blue/tie keys")

# Rewrite the winner createNotification in postGameActions
new_notif = {
    "key": "createNotification",
    "payload": {
        "preset": {
            "duration": 12,
            "backgroundColor": "#fee893",
            "borderColor": "black",
            "textColor": "black"
        },
        "computed": {
            "to": {"selector": "allUsers"},
            "header": {
                "selector": "ifElse",
                "params": [
                    {"name": "condition", "type": "computed", "value": {
                        "selector": "equals",
                        "params": [
                            {"name": "arg1", "type": "cached", "value": "winner"},
                            {"name": "arg2", "type": "preset", "value": "red"},
                        ]
                    }},
                    {"name": "thenValue", "type": "preset", "value": "Team Red wins!"},
                    {"name": "elseValue", "type": "computed", "value": {
                        "selector": "ifElse",
                        "params": [
                            {"name": "condition", "type": "computed", "value": {
                                "selector": "equals",
                                "params": [
                                    {"name": "arg1", "type": "cached", "value": "winner"},
                                    {"name": "arg2", "type": "preset", "value": "blue"},
                                ]
                            }},
                            {"name": "thenValue", "type": "preset", "value": "Team Blue wins!"},
                            {"name": "elseValue", "type": "preset", "value": "It's a tie!"},
                        ]
                    }},
                ]
            },
            "text": {
                "selector": "formatString",
                "params": [
                    {"name": "format", "type": "preset",
                     "value": "Red: ($1) breaks, ($2) botches<br/>Blue: ($3) breaks, ($4) botches"},
                    {"name": "arg1", "type": "cached", "value": "redBreaks"},
                    {"name": "arg2", "type": "cached", "value": "redBotches"},
                    {"name": "arg3", "type": "cached", "value": "blueBreaks"},
                    {"name": "arg4", "type": "cached", "value": "blueBotches"},
                ]
            }
        }
    }
}

# Replace the createNotification in postGameActions
pga = data['postGameActions']
replaced = False
for i, a in enumerate(pga):
    if a.get('key') == 'createNotification':
        pga[i] = new_notif
        replaced = True
        print("Change 3: postGameActions winner notification rewritten")
        break
if not replaced:
    pga.append(new_notif)
    print("Change 3: winner notification appended to postGameActions")

# ─── Change 4: Replace \\n with <br/> in all createNotification text ──────────
count = 0

def fix_newlines(obj):
    global count
    if isinstance(obj, dict):
        if obj.get('key') == 'createNotification':
            for section in ['preset', 'computed']:
                s = obj.get('payload', {}).get(section, {})
                if isinstance(s, dict) and 'text' in s:
                    fix_newlines_in_value(s, 'text')
        for v in obj.values():
            fix_newlines(v)
    elif isinstance(obj, list):
        for item in obj:
            fix_newlines(item)

def fix_newlines_in_value(parent, key):
    global count
    v = parent[key]
    if isinstance(v, str) and '\n' in v:
        parent[key] = v.replace('\n', '<br/>')
        count += 1
    elif isinstance(v, dict):
        # It's a selector — recurse into params looking for format strings
        for p in v.get('params', []):
            if p.get('name') == 'format' and isinstance(p.get('value'), str):
                if '\n' in p['value']:
                    p['value'] = p['value'].replace('\n', '<br/>')
                    count += 1

fix_newlines(data)
print(f"Change 4: replaced \\n with <br/> in {count} notification text format(s)")

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
