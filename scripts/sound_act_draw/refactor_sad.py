#!/usr/bin/env python3
"""Sound Act Draw! refactor — Refactor Readiness Campaign recipes 1 and 2.

Two passes over the prod game JSON (game_jsons/sound_act_draw.json):
  1. strings — hoist every display string, vote-option list, image alias and
               content bank into gameInitOptions.strings.Default (variant-ready).
  2. visual  — hoist the widget colors into top-level visualSettings.

Recipe 3 (the standard notification tutorial) is deliberately NOT applied: this
game still runs the legacy voiceover conversation-group tutorial.

The script rewrites in place, so it is not idempotent — re-run it against a
pre-refactor snapshot:  python3 scripts/sound_act_draw/refactor_sad.py <snapshot>
"""
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
GAME = os.path.join(REPO, "game_jsons", "sound_act_draw.json")
SRC = sys.argv[1] if len(sys.argv) > 1 else GAME  # re-run against a pre-refactor snapshot

BG, BORDER = "#FFC680", "black"

d = json.load(open(SRC))

STRINGS = {}


def put(key, value):
    """Register a strings key (idempotent for identical values)."""
    if key in STRINGS:
        assert STRINGS[key] == value, "strings key %r reused with a different value" % key
    else:
        STRINGS[key] = value
    return key


def group(name):
    hits = [g for g in d["gameLoop"] if isinstance(g, dict) and g.get("name") == name]
    assert len(hits) == 1, "expected exactly one gameLoop group %r, got %d" % (name, len(hits))
    return hits[0]


def action(container, key, occurrence=0):
    hits = [a for a in container if isinstance(a, dict) and a.get("key") == key]
    assert len(hits) > occurrence, "no %r action #%d" % (key, occurrence)
    return hits[occurrence]


def hoist_preset(act, field, key):
    """payload.preset[field] -> payload.cached[field] = <strings key>."""
    pre = act["payload"]["preset"]
    assert field in pre, "%s has no preset.%s" % (act.get("key"), field)
    put(key, pre.pop(field))
    act["payload"].setdefault("cached", {})[field] = key
    return act


def hoist_param(selector, param_name, key):
    """A selector param's preset literal -> cached strings key."""
    for prm in selector["params"]:
        if prm.get("name") == param_name:
            assert prm["type"] == "preset", "%s param already hoisted" % param_name
            put(key, prm["value"])
            prm["type"] = "cached"
            prm["value"] = key
            return selector
    raise AssertionError("no %s param found" % param_name)


def point_param(selector, param_name, key):
    """A selector param's preset literal -> cached reference to an EXISTING key."""
    for prm in selector["params"]:
        if prm.get("name") == param_name:
            assert prm["type"] == "preset"
            base = key.split(".")[0]
            expected = STRINGS[base]
            if "." in key:
                expected = expected[int(key.split(".")[1])]
            assert prm["value"] == expected, "%r != %r" % (prm["value"], expected)
            prm["type"] = "cached"
            prm["value"] = key
            return selector
    raise AssertionError("no %s param found" % param_name)


def hoist_format(fmt_selector, key):
    assert fmt_selector.get("selector") == "formatString"
    return hoist_param(fmt_selector, "format", key)


def svc(act, name):
    """The saveValueInCache entry called `name`."""
    for entry in act["saveValueInCache"]:
        if entry["name"] == name:
            return entry
    raise AssertionError("no saveValueInCache entry %r" % name)


def bank(entry, key):
    """A literal content bank -> strings key, with the cache var seeded from it."""
    put(key, entry["value"])
    entry["value"] = {"selector": "getCachedValue",
                      "params": [{"name": "name", "type": "preset", "value": key}]}


def tidy(node):
    """Reorder payload buckets to preset/cached/computed and drop empty ones."""
    if isinstance(node, dict):
        pl = node.get("payload")
        if isinstance(pl, dict):
            ordered = {}
            for bucket in ("preset", "cached", "computed"):
                if pl.get(bucket):
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
# PASS 1 — strings
# ─────────────────────────────────────────────────────────────────────────────

bla = d["beforeLoopActions"]

# --- Opening: wallpaper, welcome banner, tutorial vote ----------------------
hoist_preset(bla[0], "image", "wallpaperImg")            # changeBackground

welcome = action(bla, "createNotification")
hoist_preset(welcome, "header", "welcomeHeader")
hoist_preset(welcome, "image", "bannerImg")
hoist_format(welcome["payload"]["computed"]["text"], "tutorialIntroText")

mix = action(bla, "createMixVote")
hoist_preset(mix, "title", "tutorialModeTitle")
hoist_preset(mix, "poll.targets", "everybodyNobodyTargets")
hoist_preset(mix, "pollVoteTargetsOptions", "everybodyNobodyOptions")
hoist_format(mix["payload"]["computed"]["question"], "whoNeedsTutorialQuestion")
# The learners branch compares against the "Everybody!" option literal.
point_param(svc(mix, "learners")["value"]["params"][2]["value"]["params"][0]["value"],
            "element", "everybodyNobodyTargets.0")

# --- Content banks ----------------------------------------------------------
setup = bla[1]
put("generationLabels", svc(setup, "generationToLabel")["value"])
svc(setup, "generationToLabel")["value"] = {
    "selector": "getCachedValue",
    "params": [{"name": "name", "type": "preset", "value": "generationLabels"}]}
for var, key in (("boomerCards", "boomerCardsBank"), ("genXCards", "genXCardsBank"),
                 ("millenialCards", "millenialCardsBank"), ("genZCards", "genZCardsBank"),
                 ("words", "wordsBank")):
    bank(svc(setup, var), key)

# --- Decks ------------------------------------------------------------------
playing_deck, discard = [a for a in bla if a.get("key") == "createCustomDeck"]
hoist_preset(playing_deck, "label", "playingDeckLabel")
hoist_preset(discard, "label", "discardLabel")
hoist_preset(discard, "cardback", "cardbackImg")

# --- Clip title -------------------------------------------------------------
hoist_format(group("Start clip")["actions"][0]["payload"]["computed"]["title"], "clipTitle")

# --- Edition vote -----------------------------------------------------------
edition_vote, edition_notif = group("Max points")["actions"]
hoist_preset(edition_vote, "title", "editionTitle")
hoist_preset(edition_vote, "targets", "editionTargets")
hoist_preset(edition_vote, "pollVoteTargetsOptions", "editionOptions")
hoist_format(edition_vote["payload"]["computed"]["question"], "whichEditionQuestion")
point_param(svc(edition_vote, "edition")["value"]["params"][0]["value"],
            "element", "editionTargets.0")            # "Standard" fallback
point_param(svc(edition_vote, "skyEdition")["value"], "target", "editionTargets.2")
point_param(svc(edition_vote, "generationsEdition")["value"], "target", "editionTargets.1")

hoist_preset(edition_notif, "image", "bannerImg")
hoist_format(edition_notif["payload"]["computed"]["header"], "editionChosenHeader")
edition_text = edition_notif["payload"]["computed"]["text"]["params"][1]["value"]
hoist_param(edition_text, "thenValue", "generationsEditionText")
sky_or_standard = next(p for p in edition_text["params"] if p["name"] == "elseValue")["value"]
hoist_param(sky_or_standard, "thenValue", "skyEditionText")
hoist_param(sky_or_standard, "elseValue", "standardEditionText")

# --- The turn: card draw, prompt, clue --------------------------------------
turn = group("Highlight current player, give them 1 travel card")["actions"]

appearances = svc(turn[6], "optionAppearances")["value"]
hoist_param(appearances, "values", "answerOptionAppearances")

turn_notif = turn[7]
hoist_format(turn_notif["payload"]["computed"]["header"], "yourTurnHeader")
gen_text = turn_notif["payload"]["computed"]["text"]["params"][1]["value"]
hoist_format(gen_text, "generationCardText")

announce = turn[8]
hoist_format(announce["payload"]["computed"]["header"], "generationCardText")

card_input = action(turn, "createInput")
hoist_preset(card_input, "title", "submitInputTitle")
hoist_format(card_input["payload"]["computed"]["question"], "fillInTheBlankQuestion")
hoist_param(svc(card_input, "choice")["value"]["params"][0]["value"],
            "defaultValue", "didNotSubmitText")

show_card = action(turn, "createVote")
hoist_preset(show_card, "title", "showCardTitle")
hoist_format(show_card["payload"]["computed"]["question"], "pickOneQuestion")

clue_notif = turn[13]
hoist_preset(clue_notif, "text", "getReadyClueText")

# --- Drawing board ----------------------------------------------------------
drawing = group("Sound Act Draw")["actions"][0]
hoist_format(drawing["payload"]["computed"]["question"]["params"][2]["value"],
             "whiteboardQuestion")

# --- Marking the winners ----------------------------------------------------
mark = group("Mark winners")["actions"]
mark_vote = mark[0]
hoist_preset(mark_vote, "title", "markWinnerTitle")
hoist_preset(mark_vote, "poll.targets", "nobodyGotItTargets")
hoist_preset(mark_vote, "pollVoteTargetsOptions", "nobodyGotItOptions")
hoist_format(mark_vote["payload"]["computed"]["question"], "whoGuessedFirstQuestion")
point_param(svc(mark_vote, "success")["value"]["params"][1]["value"]["params"][0]["value"],
            "element", "nobodyGotItTargets.0")
hoist_preset(mark[6], "text", "wasThePhraseText")

# --- Conversation card ------------------------------------------------------
convo = group("Conversation card")["actions"]
hoist_preset(action(convo, "createGenericCardWidget"), "cardback", "conversationCardbackImg")
hoist_format(action(convo, "selectCentralWidgetDeck")["payload"]["computed"]["question"],
             "conversationCardQuestion")

# --- Play again -------------------------------------------------------------
pa_vote = group("PLAY AGAIN?")["actions"][0]
hoist_preset(pa_vote, "title", "playAgainTitle")
hoist_preset(pa_vote, "question", "playAgainQuestion")
hoist_preset(pa_vote, "binaryAnswerAliases", "playAgainTargets")
hoist_preset(pa_vote, "pollVoteTargetsOptions", "playAgainOptions")
point_param(svc(pa_vote, "playAgain")["value"], "target", "playAgainTargets.0")

# --- Winner announcement ----------------------------------------------------
win_notif = d["postGameActions"][0]
hoist_preset(win_notif, "image", "winnerImg")
win_header = win_notif["payload"]["computed"]["header"]
hoist_format(win_header, "winnerHeaderFmt")
outcome = next(p for p in win_header["params"] if p["name"] == "arg2")["value"]
hoist_param(outcome, "thenValue", "winsText")
hoist_param(outcome, "elseValue", "shareWinText")

# ─────────────────────────────────────────────────────────────────────────────
# PASS 2 — visualSettings colors
# ─────────────────────────────────────────────────────────────────────────────

CASCADE = {"createNotification", "createVote", "createMixVote", "createConfirmation",
           "createInput", "createDrawing"}
stripped = 0


def strip_colors(node):
    global stripped
    if isinstance(node, dict):
        if node.get("key") in CASCADE:
            pre = (node.get("payload") or {}).get("preset") or {}
            if pre.get("backgroundColor") == BG:
                pre.pop("backgroundColor")
                stripped += 1
            if pre.get("borderColor") == BORDER:
                pre.pop("borderColor")
        for v in node.values():
            strip_colors(v)
    elif isinstance(node, list):
        for v in node:
            strip_colors(v)


for section in ("beforeLoopActions", "gameLoop", "turnPlayerToSpectatorActions",
                "turnSpectatorToPlayerActions", "postGameActions"):
    strip_colors(d[section])

def surviving_widget_colors(node, found=None):
    """Any CASCADE widget still carrying the game palette in its own preset."""
    found = [] if found is None else found
    if isinstance(node, dict):
        if node.get("key") in CASCADE:
            pre = (node.get("payload") or {}).get("preset") or {}
            if pre.get("backgroundColor") or pre.get("borderColor"):
                found.append(node["key"])
        for v in node.values():
            surviving_widget_colors(v, found)
    elif isinstance(node, list):
        for v in node:
            surviving_widget_colors(v, found)
    return found


survivors = surviving_widget_colors(
    [d[s] for s in ("beforeLoopActions", "gameLoop", "turnPlayerToSpectatorActions",
                    "turnSpectatorToPlayerActions", "postGameActions")])
assert not survivors, "widget colors survived the strip: %s" % survivors

# ─────────────────────────────────────────────────────────────────────────────
# Assemble: strings into gameInitOptions, colors into visualSettings.
# ─────────────────────────────────────────────────────────────────────────────

d["gameInitOptions"]["strings"] = {"Default": STRINGS}

vs = {"backgroundColor": BG, "borderColor": BORDER}
vs.update(d.get("visualSettings") or {})
d["visualSettings"] = vs

tidy(d)

json.dump(d, open(GAME, "w"), indent=2, ensure_ascii=False)

print("colors stripped from %d widgets" % stripped)
print("visualSettings:", json.dumps(d["visualSettings"]))
print("strings keys (%d):" % len(STRINGS), ", ".join(sorted(STRINGS)))
