"""
Applies 4 changes to enigma.json:

1. Simplify getCachedValue wrapping: any param with type="computed" whose value
   is {selector: getCachedValue, params:[{name:"name", ...value:"X"}]}
   is replaced with {name:..., type:"cached", value:"X"}

2. Replace allUsers selector with cached "players":
   Move fields using {selector:"allUsers"} from computed → cached section as "players"

3. Add missing playList.0 field to all notifications that have sounds.list
   (GL-8a, GL-8b, GL-8c, GL-8d result notifications)

4. Fix turnPlayerToSpectatorActions:
   a. Recompute "players" using allPlayers selector (instead of listsSubtract)
   b. Recompute "numPlayers" using listLength(allPlayers)
   c. Append changeLayout action (same as BLA changeLayout)
"""
import json, copy

with open('game_jsons/enigma.json', 'r') as f:
    data = json.load(f)

# ─── Change 1: Simplify getCachedValue in params ──────────────────────────────

def simplify_get_cached_in_params(obj):
    if isinstance(obj, dict):
        if isinstance(obj.get('params'), list):
            params = obj['params']
            for i, p in enumerate(params):
                if not isinstance(p, dict):
                    continue
                if p.get('type') == 'computed':
                    v = p.get('value', {})
                    if (isinstance(v, dict) and v.get('selector') == 'getCachedValue'):
                        inner = v.get('params', [])
                        if len(inner) == 1 and inner[0].get('name') == 'name':
                            cached_var = inner[0].get('value')
                            params[i] = {'name': p['name'], 'type': 'cached', 'value': cached_var}
                            continue
                simplify_get_cached_in_params(p)
        for v in obj.values():
            simplify_get_cached_in_params(v)
    elif isinstance(obj, list):
        for item in obj:
            simplify_get_cached_in_params(item)

simplify_get_cached_in_params(data)
print("Change 1: simplified getCachedValue wrappers in params")

# ─── Change 2: Replace allUsers with cached players ───────────────────────────

def replace_all_users(obj):
    count = 0
    if isinstance(obj, dict):
        key = obj.get('key')
        payload = obj.get('payload')
        if key and isinstance(payload, dict):
            computed = payload.get('computed', {})
            if not isinstance(computed, dict):
                return 0
            fields_to_move = []
            for field, val in computed.items():
                if isinstance(val, dict) and val.get('selector') == 'allUsers':
                    fields_to_move.append(field)
            if fields_to_move:
                cached = payload.setdefault('cached', {})
                for field in fields_to_move:
                    del computed[field]
                    cached[field] = 'players'
                    count += 1
        for v in obj.values():
            count += replace_all_users(v)
    elif isinstance(obj, list):
        for item in obj:
            count += replace_all_users(item)
    return count

count = replace_all_users(data)
print(f"Change 2: replaced {count} allUsers → cached players")

# ─── Change 3: Add playList.0 to notifications with sounds ───────────────────

gl = data['gameLoop']

# GL-8a Red Botch [23], GL-8b Blue Botch [38], GL-8c Blue Breaks Red [18], GL-8d Red Breaks Blue [33]
for idx in [18, 23, 33, 38]:
    g = gl[idx]
    for a in g['actions']:
        if a.get('key') == 'createNotification':
            preset = a.get('payload', {}).get('preset', {})
            if 'sounds.list' in preset:
                cached = a['payload'].setdefault('cached', {})
                cached['playList.0'] = 'players'
                print(f"Change 3: GL[{idx}] {g['name']} — added playList.0 → players")

# ─── Change 4: Fix turnPlayerToSpectatorActions ───────────────────────────────

tptsa = data.get('turnPlayerToSpectatorActions', [])

# 4a/4b: Rewrite players and numPlayers in the emptyAction saveValueInCache
for a in tptsa:
    if a.get('key') == 'emptyAction':
        svc = a.get('saveValueInCache', [])
        for entry in svc:
            if entry['name'] == 'players':
                entry['value'] = {'selector': 'allPlayers'}
                print("Change 4a: turnPlayerToSpectatorActions players → allPlayers")
            elif entry['name'] == 'numPlayers':
                entry['value'] = {
                    'selector': 'listLength',
                    'params': [
                        {'name': 'list', 'type': 'computed', 'value': {'selector': 'allPlayers'}}
                    ]
                }
                print("Change 4b: turnPlayerToSpectatorActions numPlayers → listLength(allPlayers)")

# 4c: Append changeLayout action (copy from BLA changeLayout)
bla = data['beforeLoopActions']
change_layout = None
for a in bla:
    if isinstance(a, dict) and a.get('key') == 'changeLayout':
        change_layout = copy.deepcopy(a)
        break

if change_layout:
    tptsa.append(change_layout)
    print("Change 4c: changeLayout appended to turnPlayerToSpectatorActions")
else:
    print("Change 4c: WARNING — changeLayout not found in BLA")

data['turnPlayerToSpectatorActions'] = tptsa

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
