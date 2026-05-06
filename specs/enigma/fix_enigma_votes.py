"""
Fixes for enigma.json:
1. Add question + showResultInRealTime to all 3 createVote actions
2. Add safety logic in team computation: ensure at least 2 encryptors
"""
import json

with open('game_jsons/enigma.json', 'r') as f:
    data = json.load(f)

bla = data['beforeLoopActions']

# ─── Helper ──────────────────────────────────────────────────────────────────

def formatString_question(template, host_key="host.0"):
    return {
        "selector": "formatString",
        "params": [
            {"name": "format", "type": "preset", "value": template},
            {
                "name": "arg1",
                "type": "computed",
                "value": {
                    "selector": "getPlayerNameById",
                    "params": [{"name": "id", "type": "cached", "value": host_key}]
                }
            }
        ]
    }

# ─── Fix 1: createVote(encryptors) at beforeLoopActions[5] ───────────────────
ev = bla[5]
assert ev['key'] == 'createVote', f"Expected createVote at [5], got {ev['key']}"
ev['payload']['preset']['showResultInRealTime'] = True
ev['payload']['computed'] = {
    "question": formatString_question(
        "($1), select the players who want to be encryptors this game."
    )
}

# ─── Fix 2: safeEncryptors logic in team computation emptyAction at [6] ──────
tc = bla[6]
assert tc['key'] == 'emptyAction', f"Expected emptyAction at [6], got {tc['key']}"

safety_entries = [
    # Fallback pool: all players shuffled (so extras are random)
    {
        "name": "safeExtraPool",
        "value": {
            "selector": "listsSubtract",
            "params": [
                {"name": "list1", "type": "computed", "value": {
                    "selector": "shuffleList",
                    "params": [{"name": "list", "type": "cached", "value": "players"}]
                }},
                {"name": "list2", "type": "cached", "value": "selectedEncryptors"}
            ]
        }
    },
    {
        "name": "numSelectedRaw",
        "value": {
            "selector": "listLength",
            "params": [{"name": "list", "type": "cached", "value": "selectedEncryptors"}]
        }
    },
    # If < 2 encryptors selected, pad up to 2 from safeExtraPool
    {
        "name": "safeEncryptors",
        "value": {
            "selector": "ifElse",
            "params": [
                {
                    "name": "condition",
                    "type": "computed",
                    "value": {
                        "selector": "greaterThanOrEqual",
                        "params": [
                            {"name": "arg1", "type": "cached", "value": "numSelectedRaw"},
                            {"name": "arg2", "type": "preset", "value": 2}
                        ]
                    }
                },
                {"name": "thenValue", "type": "cached", "value": "selectedEncryptors"},
                {
                    "name": "elseValue",
                    "type": "computed",
                    "value": {
                        "selector": "ifElse",
                        "params": [
                            {
                                "name": "condition",
                                "type": "computed",
                                "value": {
                                    "selector": "equals",
                                    "params": [
                                        {"name": "arg1", "type": "cached", "value": "numSelectedRaw"},
                                        {"name": "arg2", "type": "preset", "value": 1}
                                    ]
                                }
                            },
                            {
                                # 1 selected: append one random extra
                                "name": "thenValue",
                                "type": "computed",
                                "value": {
                                    "selector": "append",
                                    "params": [
                                        {"name": "list", "type": "cached", "value": "selectedEncryptors"},
                                        {"name": "element", "type": "computed", "value": {
                                            "selector": "selectElement",
                                            "params": [
                                                {"name": "list", "type": "cached", "value": "safeExtraPool"},
                                                {"name": "index", "type": "preset", "value": 0}
                                            ]
                                        }}
                                    ]
                                }
                            },
                            {
                                # 0 selected: take first 2 from extra pool
                                "name": "elseValue",
                                "type": "computed",
                                "value": {
                                    "selector": "sublist",
                                    "params": [
                                        {"name": "list", "type": "cached", "value": "safeExtraPool"},
                                        {"name": "start", "type": "preset", "value": 0},
                                        {"name": "end", "type": "preset", "value": 2}
                                    ]
                                }
                            }
                        ]
                    }
                }
            ]
        }
    }
]

# Prepend safety entries; replace selectedEncryptors with safeEncryptors in the rest
existing = tc['saveValueInCache']

# Replace selectedEncryptors references in the original entries with safeEncryptors
def replace_refs(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, str) and v == 'selectedEncryptors':
                obj[k] = 'safeEncryptors'
            else:
                replace_refs(v)
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            if isinstance(item, str) and item == 'selectedEncryptors':
                obj[i] = 'safeEncryptors'
            else:
                replace_refs(item)

# Replace in all existing entries (shuffledEncryptors uses selectedEncryptors, nonEncryptors uses it too)
replace_refs(existing)

tc['saveValueInCache'] = safety_entries + existing

# ─── Fix 3: createVote(redClicker) at beforeLoopActions[20] ─────────────────
rv = bla[20]
assert rv['key'] == 'createVote', f"Expected createVote at [20], got {rv['key']}"
rv['payload']['preset']['showResultInRealTime'] = True
rv['payload']['computed'] = {
    "question": formatString_question(
        "($1), click the Red team player who will be the clicker for the whole game."
    )
}

# ─── Fix 4: createVote(blueClicker) at beforeLoopActions[21] ────────────────
bv = bla[21]
assert bv['key'] == 'createVote', f"Expected createVote at [21], got {bv['key']}"
bv['payload']['preset']['showResultInRealTime'] = True
bv['payload']['computed'] = {
    "question": formatString_question(
        "($1), click the Blue team player who will be the clicker for the whole game."
    )
}

data['beforeLoopActions'] = bla

with open('game_jsons/enigma.json', 'w') as f:
    json.dump(data, f, indent=4, ensure_ascii=False)

print("Fixes applied.")

# Validate
import subprocess, sys
result = subprocess.run(
    [sys.executable, 'documentation/validate_game_json.py', 'game_jsons/enigma.json'],
    capture_output=True, text=True
)
print(result.stdout)
if result.stderr:
    print(result.stderr)
