#!/usr/bin/env python3
"""Swap the five prompt banks in game_jsons/sound_act_draw.json for the ones in
word_banks.py, leaving every other byte of the game definition alone.

Run:  python3 scripts/sound_act_draw/apply_banks.py
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
GAME = os.path.join(REPO, "game_jsons", "sound_act_draw.json")
sys.path.insert(0, HERE)

from word_banks import build  # noqa: E402

banks, problems = build()
assert not problems, "word_banks.py is not clean:\n  " + "\n  ".join(problems)

d = json.load(open(GAME))
strings = d["gameInitOptions"]["strings"]["Default"]

before = {}
for var, key in (("words", "wordsBank"), ("boomerCards", "boomerCardsBank"),
                 ("genXCards", "genXCardsBank"), ("millenialCards", "millenialCardsBank"),
                 ("genZCards", "genZCardsBank")):
    assert key in strings, "%s missing — run refactor_sad.py first" % key
    before[key] = len(strings[key])
    strings[key] = banks[var]

# The banks are the only thing that moves; nothing else in the file is touched.
json.dump(d, open(GAME, "w"), indent=2, ensure_ascii=False)

for key, old in before.items():
    print("%-20s %3d -> %3d" % (key, old, len(strings[key])))
