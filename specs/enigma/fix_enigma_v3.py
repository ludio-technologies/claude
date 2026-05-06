"""
Applies 5 feedback changes to enigma.json:

1. Remove backgroundColor/textColor from all createCustomDeck presets
2. Increase changeLayout VERTICAL percent from 45 → 55
3. Add placeholder number cards (1-4) into position decks at game start
4. No repeated decks for clicker - subtract already-clicked decks from available
5. highlightDecks after each click (light red/blue/green); clear at round start
"""
import json, copy

with open('game_jsons/enigma.json', 'r') as f:
    data = json.load(f)

bla = data['beforeLoopActions']
gl  = data['gameLoop']

# ─── Helper builders ──────────────────────────────────────────────────────────

def make_list_of_4(prefix):
    """Returns a createList selector for ["prefix_1","prefix_2","prefix_3","prefix_4"]."""
    return {
        "selector": "createList",
        "params": [
            {"name": f"arg{i}", "type": "preset", "value": f"{prefix}_{i}"}
            for i in range(1, 5)
        ]
    }

def make_subtract_decks(all_4_prefix, exclude_vars):
    """
    Returns a saveValueInCache entry that computes available decks =
    all 4 decks minus those in exclude_vars (list of cached var names).
    """
    return {
        "selector": "listsSubtract",
        "params": [
            {"name": "list1", "type": "computed", "value": make_list_of_4(all_4_prefix)},
            {"name": "list2", "type": "computed", "value": {
                "selector": "createList",
                "params": [
                    {"name": f"arg{i+1}", "type": "cached", "value": v}
                    for i, v in enumerate(exclude_vars)
                ]
            }}
        ]
    }

def highlight_action(color, deck_var):
    """Returns a highlightDecks action for the given deck (cached var name)."""
    return {
        "key": "highlightDecks",
        "payload": {
            "preset": {"color": color},
            "computed": {
                "decks": {
                    "selector": "createList",
                    "params": [{"name": "arg1", "type": "cached", "value": deck_var}]
                }
            }
        }
    }

HIGHLIGHT_COLORS = ["#FF9999", "#99AAFF", "#99EE99"]  # click1=light-red, click2=light-blue, click3=light-green

# ─── Change 1: Remove backgroundColor/textColor from all createCustomDeck ─────
for gi, g in enumerate(gl):
    if not isinstance(g, dict):
        continue
    for ai, a in enumerate(g.get('actions', [])):
        if a.get('key') == 'createCustomDeck':
            p = a['payload']['preset']
            p.pop('backgroundColor', None)
            p.pop('textColor', None)
print("Change 1 done: removed colors from createCustomDeck presets")

# ─── Change 2: Increase changeLayout percent 45 → 55 ─────────────────────────
layout = bla[18]
assert layout['key'] == 'changeLayout'
layout['payload']['preset']['percent'] = 55
print("Change 2 done: changeLayout percent now 55")

# ─── Change 3: Add placeholder number cards into position decks ───────────────
# GL[1] (Create Red Position Decks, repeat qnt:4): add createCard after createCustomDeck
# GL[2] (Create Blue Position Decks, repeat qnt:4): same

def make_number_card(color_hex, deck_prefix):
    return {
        "key": "createCard",
        "payload": {
            "preset": {
                "background": color_hex,
                "textColor": "white",
                "fontHeightPercentage": 20,
                "facedown": False
            },
            "computed": {
                "deck": {
                    "selector": "formatString",
                    "params": [
                        {"name": "format", "type": "preset", "value": f"{deck_prefix}_($1)"},
                        {"name": "arg1", "type": "computed", "value": {
                            "selector": "add",
                            "params": [
                                {"name": "arg1", "type": "cached", "value": "repeatIndex"},
                                {"name": "arg2", "type": "preset", "value": 1}
                            ]
                        }}
                    ]
                },
                "cardText": {
                    "selector": "formatString",
                    "params": [
                        {"name": "format", "type": "preset", "value": "($1)"},
                        {"name": "arg1", "type": "computed", "value": {
                            "selector": "add",
                            "params": [
                                {"name": "arg1", "type": "cached", "value": "repeatIndex"},
                                {"name": "arg2", "type": "preset", "value": 1}
                            ]
                        }}
                    ]
                }
            }
        }
    }

assert gl[1]['name'] == 'Create Red Position Decks'
gl[1]['actions'].append(make_number_card("#D83232", "red"))

assert gl[2]['name'] == 'Create Blue Position Decks'
gl[2]['actions'].append(make_number_card("#4EC1D0", "blue"))

print("Change 3 done: placeholder number cards added to position deck groups")

# ─── Change 4 + 5: No repeated decks, and highlightDecks ─────────────────────
# We modify 4 sets of 3-click groups:
#   GL[18-20]: GL-6a Red Decode (red decks, redActiveClicker)
#   GL[21-23]: GL-6b Blue Decode (blue decks, blueActiveClicker)
#   GL[24-26]: GL-7a Blue Intercepts Red (red decks, blueActiveClicker)
#   GL[27-29]: GL-7b Red Intercepts Blue (blue decks, redActiveClicker)

def patch_3click_group(gi_1, gi_2, gi_3, deck_prefix, clicker_var, saved_var_prefix):
    """
    Patches a 3-click selectCentralWidgetDeck sequence for no-repeats and highlights.

    gi_1, gi_2, gi_3: gameLoop indices of click 1, 2, 3
    deck_prefix: "red" or "blue"
    clicker_var: e.g. "redActiveClicker"
    saved_var_prefix: e.g. "rd" → rdClickedDeck1, rdClickedDeck2, rdAvailableDecks2, rdAvailableDecks3
    """
    v1 = f"{saved_var_prefix}ClickedDeck1"
    v2 = f"{saved_var_prefix}ClickedDeck2"
    avail2 = f"{saved_var_prefix}AvailableDecks2"
    avail3 = f"{saved_var_prefix}AvailableDecks3"

    # ── Click 1 ──────────────────────────────────────────────────────────────
    g1 = gl[gi_1]
    svc1 = g1['actions'][0]['saveValueInCache']
    # Rename existing clickedDeck save → v1
    for e in svc1:
        if e['name'] == 'clickedDeck':
            e['name'] = v1
    # The digit var currently references 'clickedDeck'; update it to v1
    for e in svc1:
        raw = json.dumps(e)
        if '"clickedDeck"' in raw:
            # replace the cached value reference
            def fix_ref(obj):
                if isinstance(obj, dict):
                    for k, v in obj.items():
                        if isinstance(v, str) and v == 'clickedDeck':
                            obj[k] = v1
                        else:
                            fix_ref(v)
                elif isinstance(obj, list):
                    for item in obj:
                        fix_ref(item)
            fix_ref(e)
    # Append: compute available decks for click 2
    svc1.append({"name": avail2, "value": make_subtract_decks(deck_prefix, [v1])})
    # Append highlight action after the selectCentralWidgetDeck
    g1['actions'].append(highlight_action(HIGHLIGHT_COLORS[0], v1))

    # ── Click 2 ──────────────────────────────────────────────────────────────
    g2 = gl[gi_2]
    a2 = g2['actions'][0]
    # Move decks from preset to cached
    a2['payload']['preset'].pop('decks', None)
    a2['payload'].setdefault('cached', {})['decks'] = avail2
    svc2 = a2['saveValueInCache']
    # Rename clickedDeck → v2
    for e in svc2:
        if e['name'] == 'clickedDeck':
            e['name'] = v2
    def fix_ref2(obj):
        if isinstance(obj, dict):
            for k, v in obj.items():
                if isinstance(v, str) and v == 'clickedDeck':
                    obj[k] = v2
                else:
                    fix_ref2(v)
        elif isinstance(obj, list):
            for item in obj:
                fix_ref2(item)
    fix_ref2(svc2)
    # Append: compute available decks for click 3
    svc2.append({"name": avail3, "value": make_subtract_decks(deck_prefix, [v1, v2])})
    # Append highlight action
    g2['actions'].append(highlight_action(HIGHLIGHT_COLORS[1], v2))

    # ── Click 3 ──────────────────────────────────────────────────────────────
    g3 = gl[gi_3]
    a3 = g3['actions'][0]
    # Move decks from preset to cached
    a3['payload']['preset'].pop('decks', None)
    a3['payload'].setdefault('cached', {})['decks'] = avail3
    svc3 = a3['saveValueInCache']
    # Rename clickedDeck → v3 (we don't need a separate name, but rename for clarity)
    v3 = f"{saved_var_prefix}ClickedDeck3"
    for e in svc3:
        if e['name'] == 'clickedDeck':
            e['name'] = v3
    def fix_ref3(obj):
        if isinstance(obj, dict):
            for k, v in obj.items():
                if isinstance(v, str) and v == 'clickedDeck':
                    obj[k] = v3
                else:
                    fix_ref3(v)
        elif isinstance(obj, list):
            for item in obj:
                fix_ref3(item)
    fix_ref3(svc3)
    # Append highlight action
    g3['actions'].append(highlight_action(HIGHLIGHT_COLORS[2], v3))

    print(f"  Patched GL[{gi_1}-{gi_3}] ({g1['name']} ... {g3['name']})")

print("Change 4+5: patching click groups...")
patch_3click_group(18, 19, 20, "red",  "redActiveClicker", "rd")
patch_3click_group(21, 22, 23, "blue", "blueActiveClicker", "bd")
patch_3click_group(24, 25, 26, "red",  "blueActiveClicker", "big")
patch_3click_group(27, 28, 29, "blue", "redActiveClicker",  "rig")

# ─── Change 5 (cont): Add removeAllHighlightDecks at start of GL-1 each round ─
clear_action = {"key": "removeAllHighlightDecks"}
gl[6]['actions'].insert(0, clear_action)
print("Change 5 done: removeAllHighlightDecks added to GL-1 start")

# ─── Write output ─────────────────────────────────────────────────────────────
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
