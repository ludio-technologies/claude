#!/usr/bin/env python3
"""BLANK in 4 Words refactor.

Three passes over the prod game JSON (game_jsons/blank_in_four_words.json):
  1. Tutorial   — rip out the old voice-narrated guided-playthrough tutorial and
                  replace it with the standard createMixVote + one "Tutorial"
                  gameLoop group of notifications to `learners`.
  2. strings    — hoist every display string / vote-option list / image alias into
                  gameInitOptions.strings.Default (variant-ready).
  3. visual     — hoist the modal colors into top-level visualSettings.

Run:  python3 scripts/blank_in_four_words/refactor_b4w.py
"""
import copy
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
GAME = os.path.join(REPO, "game_jsons", "blank_in_four_words.json")
RBJ = os.path.join(REPO, "game_jsons", "rainbow_blackjack.json")
SRC = sys.argv[1] if len(sys.argv) > 1 else GAME  # re-run against a pre-refactor snapshot

BG, BORDER = "#fee893", "black"

d = json.load(open(SRC))
rbj = json.load(open(RBJ))

STRINGS = {}


def put(key, value):
    """Register a strings key (idempotent for identical values)."""
    if key in STRINGS:
        assert STRINGS[key] == value, "strings key %r reused with a different value" % key
    else:
        STRINGS[key] = value
    return key


def group(name, occurrence=0):
    hits = [g for g in d["gameLoop"] if isinstance(g, dict) and g.get("name") == name]
    assert len(hits) > occurrence, "no gameLoop group %r #%d" % (name, occurrence)
    return hits[occurrence]


def refs_tutorial(node):
    if isinstance(node, dict):
        if node.get("value") == "tutorial":
            return True
        return any(refs_tutorial(v) for v in node.values())
    if isinstance(node, list):
        return any(refs_tutorial(v) for v in node)
    return False


def hoist_preset(action, field, key):
    """payload.preset[field] -> payload.cached[field] = <strings key>."""
    pre = action["payload"]["preset"]
    assert field in pre, "%s has no preset.%s" % (action.get("key"), field)
    put(key, pre.pop(field))
    action["payload"].setdefault("cached", {})[field] = key
    return action


def hoist_format(fmt_selector, key):
    """formatString's `format` param: preset literal -> cached strings key."""
    assert fmt_selector.get("selector") == "formatString"
    for prm in fmt_selector["params"]:
        if prm.get("name") == "format":
            assert prm["type"] == "preset", "format param already hoisted"
            put(key, prm["value"])
            prm["type"] = "cached"
            prm["value"] = key
            return fmt_selector
    raise AssertionError("no format param found")


def hoist_preset_arg(fmt_selector, arg_name, key):
    for prm in fmt_selector["params"]:
        if prm.get("name") == arg_name:
            assert prm["type"] == "preset"
            put(key, prm["value"])
            prm["type"] = "cached"
            prm["value"] = key
            return
    raise AssertionError("no %s param" % arg_name)


def tidy(node):
    """Reorder payload buckets to preset/cached/computed and drop empty ones."""
    if isinstance(node, dict):
        pl = node.get("payload")
        if isinstance(pl, dict):
            ordered = {}
            for bucket in ("preset", "cached", "computed"):
                if bucket in pl:
                    if pl[bucket]:
                        ordered[bucket] = pl[bucket]
            for k, v in pl.items():
                if k not in ("preset", "cached", "computed"):
                    ordered[k] = v
            if ordered:
                node["payload"] = ordered
            else:
                node.pop("payload")
        for v in node.values():
            tidy(v)
    elif isinstance(node, list):
        for v in node:
            tidy(v)


# ─────────────────────────────────────────────────────────────────────────────
# PASS 0 — pre-existing bugs
# ─────────────────────────────────────────────────────────────────────────────

# The `votes` fallback for a player with no recorded vote is a randomElement
# selector, but it was typed `preset` — so it was never evaluated and the missing
# vote resolved through indexOf() to -1 (i.e. the wrong player got the point).
vote_lookup = group("Get counts")["actions"][0]["saveValueInCache"][1]["value"]
default_prm = next(p for p in vote_lookup["params"][1]["value"]["params"][1]["value"]["params"]
                   if p["name"] == "defaultValue")
assert default_prm["type"] == "preset" and "selector" in default_prm["value"]
default_prm["type"] = "computed"

# The vote-reveal createMessage carried a playList with no sounds.list — no sound
# was ever intended here, so drop the orphaned audience field.
reveal_msg = next(a for a in group("Reveal votes")["actions"] if a.get("key") == "createMessage")
assert reveal_msg["payload"]["cached"].pop("playList.1", None) is not None

# ─────────────────────────────────────────────────────────────────────────────
# PASS 1 — tutorial
# ─────────────────────────────────────────────────────────────────────────────

bla = d["beforeLoopActions"]

# 1a. Move the variable-init emptyAction (players/numPlayers/prompts/...) ahead of
#     the tutorial vote — the standard mixVote needs `players` and `numPlayers`.
init_idx = next(i for i, a in enumerate(bla)
                if a.get("key") == "emptyAction"
                and any(e.get("name") == "numPlayers" for e in a.get("saveValueInCache", [])))
init = bla.pop(init_idx)
bla.insert(1, init)  # after changeBackground, before the host lookup

# 1b. Swap the old Yes/No tutorial createVote for the standard createMixVote.
old_idx = next(i for i, a in enumerate(bla)
               if a.get("key") == "createVote"
               and any(e.get("name") == "tutorial" for e in a.get("saveValueInCache", [])))
mix = copy.deepcopy(next(a for a in rbj["beforeLoopActions"] if a.get("key") == "createMixVote"))
for color in ("backgroundColor", "textColor", "borderColor"):
    mix["payload"]["preset"].pop(color, None)      # inherit from visualSettings
bla[old_idx] = mix

# The mixVote references these strings keys (values copied from the standard).
rbj_strings = rbj["gameInitOptions"]["strings"]["Default"]
for key in ("tutorialModeTitle", "whoNeedsTutorialQuestion",
            "everybodyNobodyTargets", "everybodyNobodyOptions"):
    put(key, copy.deepcopy(rbj_strings[key]))

# 1c. Drop every old tutorial group (they all gate on the `tutorial` flag).
loop = d["gameLoop"]
removed = [g["name"] for g in loop
           if isinstance(g, dict) and g.get("name") != "PLAY AGAIN?"
           and refs_tutorial(g.get("skipCondition"))]
d["gameLoop"] = loop = [g for g in loop
                        if not (isinstance(g, dict) and g.get("name") != "PLAY AGAIN?"
                                and refs_tutorial(g.get("skipCondition")))]
assert set(removed) == {"Tutorial Part 1", "Tutorial Part 2", "Tutorial Part 3",
                        "Tutorial Part 3.5", "Tutorial Part 4", "Tutorial Part 5",
                        "Tutorial Part 7", "End tutorial",
                        "Create cards and move to central decks"}, removed

# 1d. The round-review selectCentralWidgetDeck was gated on "not the tutorial round".
review = group("Delay, Tutorial Part 8")
review["name"] = "Review round"
review["actions"][0].pop("skipCondition", None)

# 1e. Same for the play-again vote's tutorial guard.
play_again = group("PLAY AGAIN?")
play_again["skipCondition"] = [c for c in play_again["skipCondition"]
                               if not refs_tutorial(c)]
assert len(play_again["skipCondition"]) == 1
play_again["skipCondition"] = play_again["skipCondition"][0]

# 1f. The standard "Tutorial" group: notifications to `learners`, then tutorial=false.
#     Copy is drawn from the game's prod rulebook (setup.rules).
CARDS = [
    ("tutOverviewHeader", "How BLANK in 4 Words works",
     "Every round there's a new prompt. Everyone writes a <b>4-word answer</b> to it.<br/><br/>"
     "All the answers then appear anonymously in the middle, and everyone votes for the one "
     "they like best. The answer with the most votes wins the round.", 22, None),
    ("tutConstraintHeader", "The constraint",
     "Before you write, you get <b>3 words of your own</b>: a 1-point word, a 2-point word and "
     "a 3-point word — roughly how hard each one is to squeeze in.<br/><br/>"
     "You must <b>commit to one of them</b> and use it in your answer.", 24, "three_words"),
    ("tutScoringHeader", "Scoring",
     "If your answer wins the round, you score the point value of the word you committed to.<br/><br/>"
     "So the 3-point word pays the most — if you can make it sound natural.", 18, None),
    ("tutVotingHeader", "Voting",
     "When the answers go up in the middle, click the one you like best. "
     "You can't vote for your own — your deck is left out of the choice.", 16, None),
    ("tutAfkHeader", "If you go quiet",
     "No answer typed in time? A default answer gets submitted for you.<br/><br/>"
     "No favorite picked in time? One of the answers is chosen for you at random.", 16, None),
]
tutorial_actions = []
for key_base, header, text, duration, image in CARDS:
    text_key = key_base.replace("Header", "Text")
    payload = {"preset": {"duration": duration},
               "cached": {"header": put(key_base, header),
                          "text": put(text_key, text),
                          "to": "learners"}}
    if image:
        payload["cached"]["image"] = put(key_base.replace("Header", "Img"), image)
    tutorial_actions.append({"key": "createNotification", "payload": payload})
tutorial_actions.append({"key": "emptyAction",
                         "saveValueInCache": [{"name": "tutorial", "value": False}]})

d["gameLoop"].insert(0, {
    "name": "Tutorial",
    "skipCondition": [
        {"selector": "greaterThan", "params": [
            {"name": "arg1", "type": "cached", "value": "gameLoopIndex"},
            {"name": "arg2", "type": "preset", "value": 0}]},
        {"selector": "logicalNOT", "params": [
            {"name": "arg", "type": "cached", "value": "tutorial"}]},
    ],
    "actions": tutorial_actions,
})

# ─────────────────────────────────────────────────────────────────────────────
# PASS 2 — strings
# ─────────────────────────────────────────────────────────────────────────────

# Images: wallpaper + banner aliases.
hoist_preset(bla[0], "image", "wallpaperImg")            # changeBackground
welcome = next(a for a in bla if a.get("key") == "createNotification")
hoist_preset(welcome, "header", "welcomeHeader")
hoist_preset(welcome, "image", "bannerImg")
hoist_format(welcome["payload"]["computed"]["text"], "tutorialIntroText")
# `to: allPlayers()` -> cached players (spectators get notifications regardless).
welcome["payload"]["computed"].pop("to")
welcome["payload"].setdefault("cached", {})["to"] = "players"

# Prompt bank: gameplay consumes `prompts` (listsSubtract each round), so keep a
# pristine strings bank and seed the working variable from it.
prompts_entry = next(e for e in init["saveValueInCache"] if e["name"] == "prompts")
put("promptsBank", prompts_entry["value"])
prompts_entry["value"] = {"selector": "getCachedValue",
                          "params": [{"name": "name", "type": "preset", "value": "promptsBank"}]}

# Round copy.
constraint = group("Players see constraint")["actions"][0]
hoist_preset(constraint, "text", "constraintText")
hoist_format(constraint["payload"]["computed"]["header"], "promptFmt")

word_vote, word_wait = group("Players choose word")["actions"][:2]
hoist_preset(word_vote, "title", "commitToScoreTitle")
hoist_format(word_vote["payload"]["computed"]["question"], "chooseWordQuestion")
hoist_preset(word_wait, "header", "sitTightHeader")
hoist_format(word_wait["payload"]["computed"]["text"], "gotYourWordText")

answer_input, answer_wait = group("Player submit answer")["actions"][:2]
hoist_preset(answer_input, "title", "submitAnswerTitle")
hoist_preset(answer_wait, "header", "sitTightHeader")
hoist_format(answer_wait["payload"]["computed"]["text"], "gotYourAnswerText")

favorite = group("Everyone selects their favorite")["actions"][0]
hoist_format(favorite["payload"]["computed"]["question"], "pickFavoriteQuestion")

hoist_preset(review["actions"][0], "question", "reviewRoundQuestion")

# The stand-in answer used when a player never submits one.
answer_card = group("Create cards and move to central decks")["actions"][2]
fallback = answer_card["payload"]["computed"]["cardText"]["params"][0]["value"]["params"][1]
put("defaultAnswerText", fallback["value"])
fallback["type"], fallback["value"] = "cached", "defaultAnswerText"

# Play-again vote: title/question/options + the result-comparison literal.
pa_vote = play_again["actions"][0]
hoist_preset(pa_vote, "title", "playAgainTitle")
hoist_preset(pa_vote, "question", "playAgainQuestion")
hoist_preset(pa_vote, "binaryAnswerAliases", "playAgainTargets")
hoist_preset(pa_vote, "pollVoteTargetsOptions", "playAgainOptions")
target_prm = next(p for p in pa_vote["saveValueInCache"][0]["value"]["params"]
                  if p["name"] == "target")
assert target_prm["value"] == STRINGS["playAgainTargets"][0]
target_prm["type"], target_prm["value"] = "cached", "playAgainTargets.0"

# Winner announcement.
win_notif = d["postGameActions"][0]
win_header = win_notif["payload"]["computed"]["header"]
hoist_format(win_header, "winnerHeaderFmt")
arg2 = next(p for p in win_header["params"] if p["name"] == "arg2")["value"]
for branch, key in (("thenValue", "winsText"), ("elseValue", "shareWinText")):
    prm = next(p for p in arg2["params"] if p["name"] == branch)
    put(key, prm["value"])
    prm["type"], prm["value"] = "cached", key

# ─────────────────────────────────────────────────────────────────────────────
# PASS 3 — visualSettings colors
# ─────────────────────────────────────────────────────────────────────────────

CASCADE = {"createNotification", "createVote", "createMixVote", "createConfirmation", "createInput"}


def strip_colors(node):
    if isinstance(node, dict):
        if node.get("key") in CASCADE:
            pre = (node.get("payload") or {}).get("preset") or {}
            if pre.get("backgroundColor") == BG:
                pre.pop("backgroundColor")
            if pre.get("borderColor") == BORDER:
                pre.pop("borderColor")
        for v in node.values():
            strip_colors(v)
    elif isinstance(node, list):
        for v in node:
            strip_colors(v)


for section in ("beforeLoopActions", "gameLoop", "turnSpectatorToPlayerActions", "postGameActions"):
    strip_colors(d[section])

# ─────────────────────────────────────────────────────────────────────────────
# Assemble: strings into gameInitOptions, visualSettings after it.
# ─────────────────────────────────────────────────────────────────────────────

d["gameInitOptions"]["strings"] = {"Default": STRINGS}

# Prune voice clips left orphaned by the removed narration.
blob = json.dumps({k: v for k, v in d.items() if k != "gameInitOptions"})
voices = d["gameInitOptions"].get("voices", {}).get("default", {})
orphans = [alias for alias in list(voices) if ('voices.' + alias) not in blob]
for alias in orphans:
    voices.pop(alias)

tidy(d)

out = {"gameInitOptions": d["gameInitOptions"],
       "visualSettings": {"backgroundColor": BG, "borderColor": BORDER}}
for k, v in d.items():
    if k != "gameInitOptions":
        out[k] = v

json.dump(out, open(GAME, "w"), indent=2, ensure_ascii=False)

print("removed tutorial groups:", sorted(set(removed)))
print("orphaned voice clips pruned:", orphans)
print("strings keys (%d):" % len(STRINGS), ", ".join(sorted(STRINGS)))
