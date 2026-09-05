#!/usr/bin/env python3
"""Shared pieces for building the Rainbow Blackjack Naughty variant.

Holds the small selector DSL, the naughty card vocabulary, the new
user-facing copy, and the reusable builders that the three card-manipulation
action cards (Steal, Swap, Discard) are assembled from.
"""

# ── selector DSL helpers ────────────────────────────────────────────────────
def P(name, value):
    return {"name": name, "type": "preset", "value": value}


def C(name, value):
    return {"name": name, "type": "cached", "value": value}


def X(name, value):
    return {"name": name, "type": "computed", "value": value}


def sel(selector, *params):
    return {"selector": selector, "params": list(params)}


def cache(name, value):
    return {"name": name, "value": value}


def copy_of(var):
    """A saveValueInCache value that copies an existing cached variable."""
    return sel("getCachedValue", P("name", var))


def lst(*items):
    """createList over already-formed params."""
    return sel("createList", *[
        (it if isinstance(it, dict) and "name" in it else X("arg%d" % (i + 1), it))
        for i, it in enumerate(items)])


def one(value_param):
    return sel("createList", value_param)


def player_deck_of(player_param):
    """The central-widget pile belonging to a player."""
    return sel("selectElement",
               C("list", "playerDecks"),
               X("index", sel("indexOf", C("list", "players"), player_param)))


# ── naughty card vocabulary ─────────────────────────────────────────────────
N_NUMBERS = ["n_%d" % v for v in range(0, 14)]
N_MODIFIERS = ["n_divide_2", "n_minus_2", "n_minus_4",
               "n_minus_6", "n_minus_8", "n_minus_10"]
N_ACTIONS = ["n_just_one_more", "n_flip_four", "n_steal", "n_swap", "n_discard"]
# The modifiers are all penalties in Naughty, and a penalty is handed to
# somebody else the moment it is drawn.
N_PENALTIES = list(N_MODIFIERS)
N_PENALTY_LABELS = {"n_divide_2": "÷2", "n_minus_2": "−2", "n_minus_4": "−4",
                    "n_minus_6": "−6", "n_minus_8": "−8", "n_minus_10": "−10"}
# The two one-off numbers. They are ordinary number cards apart from their rule,
# so they can be stolen, swapped and discarded like any other.
N_SPECIAL_NUMBERS = ["n_7_unlucky", "n_13_lucky"]

NICE_SPECIALS = ["freeze", "second_chance", "flip", "hit", "stay",
                 "plus_2", "plus_4", "plus_6", "plus_8", "plus_10", "times_2"]
NAUGHTY_SPECIALS = N_ACTIONS + ["hit", "stay"] + N_MODIFIERS

# Cards a player can be robbed of / forced to discard: numbers and modifiers.
# The action cards are excluded — they sit in a victim's pile as a marker of
# what was played on them and have no matching card in anyone's hand.
PICK_CARDS = N_NUMBERS + N_SPECIAL_NUMBERS + N_MODIFIERS
PICK_DECKS = ["k_" + n for n in PICK_CARDS]
CARD_TO_PICK_DECK = dict(zip(PICK_CARDS, PICK_DECKS))

# Swap lays both players' piles out at the same time, so it needs a SECOND
# family of single-card decks: the two players can easily hold the same card
# name, and one deck per name cannot hold both. Row 1 of the swap widget is
# built from the `k_` decks, row 2 from these.
PICK_DECKS_B = ["j_" + n for n in PICK_CARDS]
CARD_TO_PICK_DECK_B = dict(zip(PICK_CARDS, PICK_DECKS_B))

# The widget grid is filled row by row, so the shorter of the two rows has to
# be padded out to the full width or the other player's cards wrap up into it.
# Only one row ever needs padding (the width is the larger of the two counts),
# so one family of empties is enough.
SWAP_PAD_DECKS = ["swap_pad_%d" % i for i in range(len(PICK_CARDS))]

# Created in one pass, so they travel as one list.
SWAP_EXTRA_DECKS = PICK_DECKS_B + SWAP_PAD_DECKS

# Swap's widget is always three rows: player A, player B, and an empty one
# below them. Keyed by the width, which is the larger of the two hands.
SWAP_ROW_DIMENSIONS = {str(_n): [_n, 3] for _n in range(1, len(PICK_CARDS) + 1)}

# dimensions[0] * dimensions[1] must be >= the number of decks shown.
PICK_DIMENSIONS = {}
for _n in range(1, len(PICK_CARDS) + 1):
    for _cols, _rows in ((1, 1), (2, 1), (3, 1), (4, 1), (5, 1), (3, 2), (4, 2),
                         (5, 2), (4, 3), (5, 3), (4, 4), (5, 4), (5, 5)):
        if _cols * _rows >= _n:
            PICK_DIMENSIONS[str(_n)] = [_cols, _rows]
            break

WIDGET_LOOK = {"ratio": "0.77", "backgroundImage": "yellow_background"}


# ── new user-facing copy ────────────────────────────────────────────────────
NEW_STRINGS = {
    "gameModeTitle": "Game Mode",
    "gameModeQuestion": "($1), do you want to play Nice or Naughty?",
    "niceNaughtyTargets": ["Nice", "Naughty"],
    "niceNaughtyOptions": {
        "Nice": {
            "icon": "https://res.cloudinary.com/liars-club/image/upload/icons/angel-svgrepo-com.svg",
            "backgroundColor": "#D3D3D3",
            "boxIconColor": "#D3D3D3",
            "textColor": "black",
            "widgetIconColor": "green",
        },
        "Naughty": {
            "icon": "https://res.cloudinary.com/liars-club/image/upload/icons/devil-svgrepo-com.svg",
            "backgroundColor": "#D3D3D3",
            "boxIconColor": "#D3D3D3",
            "textColor": "black",
            "widgetIconColor": "red",
        },
    },

    "naughtyStopQuestion": "($1), force any active player to draw ONE more card and then stop!",
    "naughtyFlipQuestion": "($1), force any active player to HIT 4 times RIGHT NOW!",

    # A forced draw is a Hit in this reskin, not a Flip. These three override
    # the production copy so the wording matches what the cards now say.
    "forceFlipQuestion": "($1), force any active player to HIT 3 times RIGHT NOW!",
    "actionsText": (
        "These are 3 special action cards: Stop, Hit 3, and Extra Life.<br><br>"
        "If you are dealt a Stop card, you must play it on any player that is still "
        "in the round. They will be forced to stop drawing cards for the rest of the "
        "round. You can only play Stop cards on players with higher scores (unless "
        "you're the highest score). If you are the only remaining player, any Stop "
        "cards you draw have no effect.<br><br>"
        "If you are dealt a Hit 3 card, you must play it on any player that is still "
        "in the round. They are dealt 3 more cards immediately.<br><br>"
        "If you are dealt an Extra Life card, it stays in your hand for the rest of "
        "the round. If you ever bust, the Extra Life saves you - the card that would "
        "have busted you gets discarded along with your Extra Life card and you keep "
        "playing.<br><br>"
        "If you draw a Stop or Hit 3 card while in the middle of a Hit 3 action, "
        "those cards have no effect unless it is the 3rd card you are dealt."),
    "noSpecialActionText": (
        "If you do not choose a player for the Stop/Hit action, a random valid "
        "player will be chosen for you."),

    "stealVictimQuestion": "($1), pick a player to STEAL a card from!",
    "stealCardQuestion": "Pick the card you want to steal.",
    "discardVictimQuestion": "($1), pick a player who has to DISCARD a card!",
    "penaltyVictimQuestion": "($1), you drew the ($2) - pick who has to take it!",
    "zeroLockHeader": "The Zero has you",
    "zeroLockText": (
        "You are holding <b>The Zero</b>, so your Stay card is gone - you have to keep "
        "hitting for the rest of the round.<br><br>"
        "Your score for the round is <b>0</b> unless you get all the way to a Rainbow, "
        "which is now the only thing worth playing for.<br><br>"
        "Get rid of it and you are free again - a Steal or a Discard played on you takes "
        "it away."),
    "discardCardQuestion": "Pick the card they have to throw away.",
    "swapVictimAQuestion": "($1), pick the FIRST player in the swap!",
    "swapCardAQuestion": "Pick a card from the TOP row - the first player's hand.",
    "swapVictimBQuestion": "($1), pick the SECOND player in the swap!",
    "swapCardBQuestion": "Now pick a card from the MIDDLE row - the second player's hand. The two cards trade places.",

    "naughtyOverviewText": (
        "Naughty mode is played with a bigger, meaner deck: the numbers run 0-13, "
        "and there is no Extra Life card to save you.<br><br>"
        "Everything else works the same. Every turn each player chooses Hit or Stop. "
        "Hit and you are dealt another card. Draw a number you already have and you bust, "
        "losing your points for that round.<br><br>"
        "If you are dealt 7 unique number cards, you have made a Rainbow draw. That ends "
        "the round immediately and you get 25 bonus points.<br><br>"
        "Naughty is a shorter game than Nice: the first player to reach 150 points "
        "wins!"),
    "naughtyModifiersText": (
        "In Naughty mode every modifier hurts. The deck contains -2, -4, -6, -8, -10 and "
        "÷2. They do exactly what they say and do not count towards your unique "
        "number cards. The ÷2 is applied first (rounding down), then the minuses "
        "are subtracted.<br><br>"
        "You never keep a penalty you draw. The moment one turns up you pick another "
        "player who is still drawing and it goes in front of them instead. Players who "
        "have busted or already stopped are safe from it. If there is nobody left who "
        "is still drawing, the penalty stays with you."),
    "naughtyActionsText": (
        "There are 5 action cards, and each one is played on another player the moment "
        "you draw it.<br><br>"
        "<b>One More</b> - the player you pick is dealt one more card and is then forced "
        "to stop.<br><br>"
        "<b>Hit 4</b> - the player you pick is dealt 4 more cards immediately.<br><br>"
        "<b>Steal</b> - pick a player, then take any one of their number or modifier "
        "cards for yourself. Careful: if you steal a number you already have, you bust."
        "<br><br>"
        "<b>Swap</b> - pick two players. Both their hands are laid out, one row each, "
        "and you pick one card from each row. The two cards trade places. This can bust "
        "both of them at once.<br><br>"
        "<b>Discard</b> - pick a player, then pick one of their cards to throw away."
        "<br><br>"
        "Every one of these cards can only be pointed at a player who is still drawing. "
        "Once you have stopped - or busted - nobody can steal from you, swap your cards, "
        "make you discard, or hand you a penalty. Stopping keeps you safe.<br><br>"
        "If there is nobody left to play them on they simply do nothing: Steal and "
        "Discard need one other player still drawing, and Swap needs at least three "
        "players still drawing."),
    "naughtySpecialNumbersHeader": "Naughty Mode: Special Numbers",
    "naughtySpecialNumbersText": (
        "<b>The Zero</b> - your score for the round becomes 0 unless you make a Rainbow "
        "draw, and you are forced to keep hitting for the rest of the round.<br><br>"
        "<b>Unlucky 7</b> - there is one of these in the deck. The moment you draw it, "
        "every other number and modifier card in front of you is thrown away. All you "
        "keep is the 7. The other six 7s are ordinary cards.<br><br>"
        "<b>Lucky 13</b> - there is one of these in the deck, and it is the only 13 that "
        "does not clash. You can hold it alongside an ordinary 13 without busting. Two "
        "ordinary 13s still bust you."),
}


# ── the variant vote and everything derived from it ─────────────────────────
def variant_vote_actions():
    vote = {
        "key": "createVote",
        "payload": {
            "preset": {
                "type": "target_poll",
                # Untimed: only the host votes, and the game should wait for
                # them rather than picking a variant on a countdown.
                "terminationCondition": "get_all_votes",
                "showResultInRealTime": True,
                "showResultDuration": 2,
                "showResult": True,
                "allowRevoting": False,
                "backgroundColor": "#001861",
                "textColor": "white",
                "borderColor": "white",
            },
            "cached": {
                "actors": "host",
                "title": "gameModeTitle",
                "targets": "niceNaughtyTargets",
                "pollVoteTargetsOptions": "niceNaughtyOptions",
            },
            "computed": {
                "question": sel("formatString",
                                C("format", "gameModeQuestion"),
                                X("arg1", sel("getPlayerNameById", C("id", "host.0")))),
            },
        },
        "saveValueInCache": [
            cache("naughty", sel("isTargetGotMajority",
                                 C("voteResult", "lastActionResult"),
                                 C("target", "niceNaughtyTargets.1"))),
        ],
    }

    def pick(nice_value, naughty_value):
        """ifElse on the variant flag, both branches given as literals."""
        return sel("ifElse",
                   C("condition", "naughty"),
                   P("thenValue", naughty_value),
                   P("elseValue", nice_value))

    def pick_str(nice_var, naughty_var):
        """ifElse between two `strings` entries."""
        return sel("ifElse",
                   C("condition", "naughty"),
                   C("thenValue", naughty_var),
                   C("elseValue", nice_var))

    derived = {
        "key": "emptyAction",
        "saveValueInCache": [
            # Which set of the deck JSON to build the playing deck from.
            cache("deckSet", pick("cards", "naughty")),

            # Cards that must not count towards the 7 unique numbers.
            cache("specialCards", pick(NICE_SPECIALS, NAUGHTY_SPECIALS)),

            # Scoring modifiers.
            cache("specialCardToAddition", pick(
                {"plus_2": 2, "plus_4": 4, "plus_6": 6, "plus_8": 8, "plus_10": 10},
                {"n_minus_2": -2, "n_minus_4": -4, "n_minus_6": -6,
                 "n_minus_8": -8, "n_minus_10": -10})),
            cache("additionCards", pick(
                ["plus_2", "plus_4", "plus_6", "plus_8", "plus_10"],
                ["n_minus_2", "n_minus_4", "n_minus_6", "n_minus_8", "n_minus_10"])),
            cache("multiplierCard", pick("times_2", "n_divide_2")),

            # Action cards, as scalars and as one-element lists (moveCards and
            # recallCards both want `cardNames` as a list).
            cache("stopCard", pick("freeze", "n_just_one_more")),
            cache("stopCardList", pick(["freeze"], ["n_just_one_more"])),
            cache("flipCard", pick("flip", "n_flip_four")),
            cache("flipCardList", pick(["flip"], ["n_flip_four"])),
            cache("flipCount", pick(3, 4)),
            cache("stealCard", pick("none", "n_steal")),
            cache("stealCardList", pick(["none"], ["n_steal"])),
            cache("swapCard", pick("none", "n_swap")),
            cache("swapCardList", pick(["none"], ["n_swap"])),
            cache("discardCard", pick("none", "n_discard")),
            cache("discardCardList", pick(["none"], ["n_discard"])),

            # Special numbers. "none" is a name no card ever has, so the Nice
            # deck simply never matches these.
            cache("zeroCard", pick("none", "n_0")),
            # One card each, not every 7 and every 13. The Lucky 13 carries its
            # own name, so holding it alongside an ordinary 13 is not a
            # duplicate and cannot bust — the rule falls out of the deck.
            cache("unluckyCard", pick("none", "n_7_unlucky")),
            cache("unluckyCardList", pick(["none"], ["n_7_unlucky"])),
            cache("luckyCard", pick("none", "n_13_lucky")),

            # Penalties are handed to another player in Naughty. Empty in Nice,
            # where the modifiers are bonuses you keep.
            cache("penaltyCards", pick([], N_PENALTIES)),
            cache("penaltyCardLabels", pick({}, N_PENALTY_LABELS)),
            # An ordinary 7 and the Unlucky 7 are both sevens, so holding the
            # two of them has to bust exactly as two ordinary 7s would. They no
            # longer share a name, so the duplicate check needs telling.
            cache("plainSevenCard", pick("none", "n_7")),

            # Naughty scores faster and hurts more, so it plays to a shorter
            # target. Read by playersWinCondition.gameOverCondition, which is
            # evaluated outside the loop but sees the same cache.
            cache("winTarget", pick(200, 150)),

            # Cards that live in a victim's pile without a matching hand card,
            # so they can never be stolen, swapped or discarded.
            cache("actionMarkers", pick(["freeze", "flip"], N_ACTIONS)),

            # Static tables for the card-picking widget.
            cache("pickCardNames", PICK_CARDS),
            cache("pickDeckNames", PICK_DECKS),
            cache("cardNameToPickDeck", CARD_TO_PICK_DECK),
            cache("cardWidgetDimensions", PICK_DIMENSIONS),
            # Swap shows two hands at once, so it needs its own second family
            # of pick decks, the row padding, and a three-row grid.
            cache("swapExtraDeckNames", SWAP_EXTRA_DECKS),
            cache("cardNameToPickDeckB", CARD_TO_PICK_DECK_B),
            cache("swapPadDecks", SWAP_PAD_DECKS),
            cache("swapRowDimensions", SWAP_ROW_DIMENSIONS),
            cache("hitOnlyCards", ["hit"]),
            cache("hitStayCards", ["hit", "stay"]),

            # The table's wallpaper follows the rule set. It can only be applied
            # once the vote has resolved — until then the neutral `wallpaperImg`
            # from strings is what is on screen, which is why that one stays.
            # A separate name because a strings key must never also be a
            # saveValueInCache target.
            cache("variantWallpaper", pick("nice_wallpaper", "naughty_wallpaper")),

            # Variant copy.
            cache("stopQuestionText", pick_str("forceStopQuestion", "naughtyStopQuestion")),
            cache("flipQuestionText", pick_str("forceFlipQuestion", "naughtyFlipQuestion")),
            cache("overviewTextV", pick_str("overviewText", "naughtyOverviewText")),
            cache("modifiersTextV", pick_str("modifiersText", "naughtyModifiersText")),
            cache("actionsTextV", pick_str("actionsText", "naughtyActionsText")),
        ],
    }
    return [vote, derived]


# ── generic helpers used by the three card-manipulation flows ───────────────
def find_group(loop, name):
    for i, g in enumerate(loop):
        if isinstance(g, dict) and g.get("name") == name:
            return i
    raise KeyError(name)


def restore_main_widget():
    return {
        "key": "createGenericCardWidget",
        "payload": {
            "preset": dict(WIDGET_LOOK),
            "computed": {
                "decks": sel("concat",
                             C("list1", "playerDecks"),
                             X("list2", sel("createList", P("arg1", "original")))),
                "dimensions": sel("getObjectField",
                                  C("obj", "centralWidgetDimensions"),
                                  C("field", "numPlayers")),
            },
        },
    }


def not_ready(prefix):
    """skipCondition: run only when this flow has a target holding cards."""
    return [sel("logicalNOT",
                X("arg", sel("logicalAND",
                             C("arg1", prefix + "Ready"),
                             C("arg2", prefix + "HasCards"))))]


def victim_pick_actions(prefix, victim_var, pool_var, question_var, actor_var,
                        deck_dict="cardNameToPickDeck"):
    """Ask `actor_var` to pick a victim, then work out that victim's pickable cards.

    `deck_dict` names the family of single-card decks the victim's pile is
    exploded into. Swap shows two piles side by side and so passes the second
    family for its second player; everything else uses the default.
    """
    return [
        {
            "key": "createCardVote",
            "payload": {
                "preset": {
                    "terminationCondition": "get_all_votes",
                    "duration": 25,
                    "answersQuantity": 1,
                    "allowFewerAnswers": False,
                    "allowSkipping": False,
                    "allowRevoting": True,
                    "showResultInRealTime": True,
                    "sounds.waitForSoundEnd": True,
                    "sounds.list": ["soundboard.reminder"],
                },
                "cached": {
                    "actors": actor_var,
                    "playList.1": actor_var,
                    "targets": pool_var,
                },
                "computed": {
                    "question": sel("formatString",
                                    C("format", question_var),
                                    X("arg1", sel("getPlayerNameById",
                                                  C("id", actor_var + ".0")))),
                },
            },
            "saveValueInCache": [
                cache("voteResult", copy_of("lastActionResult.voteResult")),
                cache(victim_var, sel(
                    "ifElse",
                    X("condition", sel("equals",
                                       X("arg1", sel("listLength", C("list", "voteResult"))),
                                       P("arg2", 0))),
                    X("thenValue", sel("createList",
                                       X("arg1", sel("randomElement", C("list", pool_var))))),
                    C("elseValue", "voteResult"))),
                cache(victim_var + "Deck", player_deck_of(C("element", victim_var + ".0"))),
                # Only numbers and modifiers can be taken — action-card markers
                # in the pile have no counterpart in anybody's hand.
                cache(prefix + "Names", sel(
                    "unique",
                    X("list", sel("listsSubtract",
                                  X("list1", sel("fetchDeckField",
                                                 C("deck", victim_var + "Deck"),
                                                 P("field", "name"))),
                                  C("list2", "actionMarkers"))))),
                cache(prefix + "Decks", sel("listByDictionary",
                                            C("list", prefix + "Names"),
                                            C("dict", deck_dict))),
                cache(prefix + "Count", sel("listLength", C("list", prefix + "Names"))),
                cache(prefix + "HasCards", sel("greaterThan",
                                               C("arg1", prefix + "Count"),
                                               P("arg2", 0))),
            ],
        },
    ]


def owner_label_action(prefix, victim_var):
    """Put the owner's name under each card of an exploded pile.

    The pick decks are a shared pool reused by every flow and every round, so
    whose cards are on screen is not otherwise obvious — the pile is lifted out
    of its owner's seat and shown in the middle of the table. Set inside the
    explode loop, one deck at a time, so it always matches what was just dealt
    into that deck. Swap relabels both rows this way, each with its own owner.
    """
    return {
        "key": "setDeckLabel",
        "payload": {
            "computed": {
                "deck": sel("selectElement", C("list", prefix + "Decks"),
                            C("index", "repeatIndex")),
                "label": sel("getPlayerNameById", C("id", victim_var + ".0")),
            },
        },
    }


def explode_group(prefix, victim_var, label, skip=None):
    """Deal the victim's pile out into one single-card deck per card name."""
    return {
        "name": label,
        "skipCondition": skip or not_ready(prefix),
        "repeat": {"qnt": sel("listLength", C("list", prefix + "Names"))},
        "actions": [{
            "key": "moveCards",
            "payload": {
                "preset": {"type": "deck"},
                "cached": {"from": victim_var + "Deck"},
                "computed": {
                    "to": sel("selectElement", C("list", prefix + "Decks"),
                              C("index", "repeatIndex")),
                    "cardNames": sel("createList",
                                     X("arg1", sel("selectElement",
                                                   C("list", prefix + "Names"),
                                                   C("index", "repeatIndex")))),
                },
            },
        }, owner_label_action(prefix, victim_var)],
    }


def collapse_group(prefix, victim_var, label, skip=None):
    """Put every pick deck back into the victim's pile."""
    return {
        "name": label,
        "skipCondition": skip or not_ready(prefix),
        "repeat": {"qnt": sel("listLength", C("list", prefix + "Names"))},
        "actions": [{
            "key": "moveCards",
            "payload": {
                "preset": {"type": "deck"},
                "cached": {"to": victim_var + "Deck"},
                "computed": {
                    "from": sel("selectElement", C("list", prefix + "Decks"),
                                C("index", "repeatIndex")),
                },
            },
        }],
    }


def choose_card_actions(prefix, actor_var, question_var):
    """Show the exploded pile and let the actor click one card."""
    return [
        {
            "key": "createGenericCardWidget",
            "payload": {
                "preset": dict(WIDGET_LOOK),
                "cached": {"decks": prefix + "Decks"},
                "computed": {
                    "dimensions": sel("getObjectField",
                                      C("obj", "cardWidgetDimensions"),
                                      C("field", prefix + "Count")),
                },
            },
        },
    ] + [pick_card_action(prefix, actor_var, question_var)]


def pick_card_action(prefix, actor_var, question_var):
    """One click on one of `prefix`'s decks, on whatever widget is already up.

    Split out of `choose_card_actions` because Swap puts both players' hands on
    screen with a single widget and then runs this twice, once per row.
    """
    return (
        {
            "key": "selectCentralWidgetDeck",
            "payload": {
                "preset": {
                    "duration": 25,
                    "sounds.waitForSoundEnd": True,
                    "sounds.list": ["soundboard.reminder"],
                },
                "cached": {
                    "decks": prefix + "Decks",
                    "actors": actor_var,
                    "question": question_var,
                },
                "computed": {
                    "playList.1": copy_of(actor_var),
                    "defaultSelect": sel("randomElement", C("list", prefix + "Decks")),
                },
            },
            "saveValueInCache": [
                cache(prefix + "PickedDeck", sel("getCachedObjectValue",
                                                 P("objectName", "lastActionResult"),
                                                 C("value", actor_var + ".0"))),
                cache(prefix + "PickedName", sel(
                    "getObjectField",
                    X("obj", sel("selectElement",
                                 X("list", sel("getDeckCards",
                                               C("deck", prefix + "PickedDeck"))),
                                 P("index", 0))),
                    P("field", "name"))),
                cache(prefix + "PickedList", sel("createList",
                                                 C("arg1", prefix + "PickedName"))),
            ],
        }
    )


# ── the three card-manipulation flows ───────────────────────────────────────
def pool_of(*exclude_vars):
    """Everyone the action cards are allowed to reach, minus the given players.

    Only players who are still drawing. Busting takes you out, and so does
    stopping: once you have stayed, nobody can steal from you, swap your cards,
    make you discard, or hand you a penalty. `remainingPlayers` is the same set
    but is emptied out during a forced-hit cascade, so this is computed from the
    two exclusion lists instead, which hold their value across the whole round.
    """
    pool = sel("listsSubtract", C("list1", "players"), C("list2", "allBusted"))
    pool = sel("listsSubtract", X("list1", pool), C("list2", "allStopped"))
    for var in exclude_vars:
        pool = sel("listsSubtract", X("list1", pool), C("list2", var))
    return pool


def actor_setup(prefix, queue_var, exclude_actor=True):
    """Take the player at the head of the queue and work out who they may target."""
    entries = [
        cache(prefix + "Actor", sel("createList", C("arg1", queue_var + ".0"))),
        cache(prefix + "ActorDeck", player_deck_of(C("element", prefix + "Actor.0"))),
        cache(prefix + "Pool",
              pool_of(prefix + "Actor") if exclude_actor else pool_of()),
    ]
    return {"key": "emptyAction", "saveValueInCache": entries}


def mark_touched(*victim_vars):
    """Flag these players for a bust/score re-check on the next tick.

    Needed because Steal, Swap and Discard can change the cards in front of
    somebody who has already stopped and so is no longer being walked.
    """
    value = None
    for var in victim_vars:
        value = sel("concat",
                    C("list1", "touched") if value is None else X("list1", value),
                    C("list2", var))
    return cache("touched", value)


def pop_queue(queue_var):
    return {"key": "emptyAction", "saveValueInCache": [
        cache(queue_var, sel("sublist",
                             C("list", queue_var),
                             P("start", 1),
                             X("end", sel("listLength", C("list", queue_var))))),
    ]}


def not_started(prefix):
    """skipCondition for the wrap-up group, which restores the board and takes
    the drawer off the queue.

    Keyed on `Drop` rather than on the queue being empty. A card that could not
    run because a forced flip was mid-cascade stays queued and gets its go on a
    later tick; one that can never run — too few players left for it to mean
    anything — comes off the queue and does nothing, which is the rule for
    these cards.
    """
    return [sel("logicalNOT", C("arg", prefix + "Drop"))]


def penalty_groups():
    """Hand a just-drawn penalty card to somebody else.

    Much shorter than Steal/Swap/Discard: the card is already known — it is the
    one the player just turned over — so there is no pile to explode and no card
    to choose. Only a player to point at.

    Split across two groups on purpose. A group's skipCondition is evaluated
    before any of its actions run, so the pool has to be worked out in one group
    and the prompt gated on it in the next — the same shape Swap uses for its
    second player. Deciding from a count worked out earlier in the tick is what
    produced a prompt with nothing clickable that then timed out and dealt the
    card to a random player.

    With no one to give it to, the prompt never appears and the drawer keeps the
    card; the queue still drains, because `penDrop` only asks whether we got a
    chance to look at it.
    """
    p = "pen"
    return [
        {
            "name": "Naughty: penalty - work out who can take it",
            "skipCondition": [sel("logicalNOT", C("arg", p + "Ready"))],
            "actions": [
                {"key": "emptyAction", "saveValueInCache": [
                    cache(p + "Actor", sel("createList", C("arg1", "penQueue.0"))),
                    cache(p + "ActorDeck",
                          player_deck_of(C("element", "penQueue.0"))),
                    cache(p + "Pool", pool_of(p + "Actor")),
                    # The card itself, as a scalar and as the one-element list
                    # moveCards/recallCards want.
                    cache(p + "Card", copy_of("penCards.0")),
                    cache(p + "CardList", sel("createList", C("arg1", "penCards.0"))),
                    # The authority on whether the prompt should happen at all.
                    cache(p + "HasTargets", sel(
                        "greaterThan",
                        X("arg1", sel("listLength", C("list", p + "Pool"))),
                        P("arg2", 0))),
                ]},
            ],
        },
        {
            "name": "Naughty: penalty - choose who takes it",
            "skipCondition": [sel("logicalNOT", C("arg", p + "HasTargets"))],
            "actions": [
                {
                    "key": "createCardVote",
                    "payload": {
                        "preset": {
                            "terminationCondition": "get_all_votes",
                            "duration": 25,
                            "answersQuantity": 1,
                            "allowFewerAnswers": False,
                            "allowSkipping": False,
                            "allowRevoting": True,
                            "showResultInRealTime": True,
                            "sounds.waitForSoundEnd": True,
                            "sounds.list": ["soundboard.reminder"],
                        },
                        "cached": {"actors": p + "Actor",
                                   "playList.1": p + "Actor",
                                   "targets": p + "Pool"},
                        # `penCard` is a card name, not a dealt card id, so the
                        # label comes from a static table rather than getCardField.
                        "computed": {"question": sel(
                            "formatString",
                            C("format", "penaltyVictimQuestion"),
                            X("arg1", sel("getPlayerNameById",
                                          C("id", p + "Actor.0"))),
                            X("arg2", sel("getCachedObjectValue",
                                          P("objectName", "penaltyCardLabels"),
                                          C("value", p + "Card"),
                                          P("defaultValue", "penalty"))))},
                    },
                    "saveValueInCache": [
                        cache("voteResult", copy_of("lastActionResult.voteResult")),
                        # Timed out: it still has to land on somebody.
                        cache(p + "Victim", sel(
                            "ifElse",
                            X("condition", sel("equals",
                                               X("arg1", sel("listLength",
                                                             C("list", "voteResult"))),
                                               P("arg2", 0))),
                            X("thenValue", sel("createList",
                                               X("arg1", sel("randomElement",
                                                             C("list", p + "Pool"))))),
                            C("elseValue", "voteResult"))),
                        cache(p + "VictimDeck",
                              player_deck_of(C("element", p + "Victim.0"))),
                    ],
                },
                # Pile side.
                {"key": "moveCards",
                 "payload": {"preset": {"type": "deck", "qnt": 1},
                             "cached": {"from": p + "ActorDeck",
                                        "to": p + "VictimDeck",
                                        "cardNames": p + "CardList"}}},
                # Hand side — bust detection and scoring read the hand, so the
                # card has to change hands there too.
                {"key": "recallCards",
                 "payload": {"preset": {"deck": "copies", "qnt": 1},
                             "cached": {"targets": p + "Actor",
                                        "cardNames": p + "CardList"}}},
                {"key": "dealDeck",
                 "payload": {"preset": {"deck": "copies", "qnt": 1,
                                        "sortBy": "rank", "order": "asc"},
                             "cached": {"targets": p + "Victim",
                                        "cardNames": p + "CardList"}},
                 "saveValueInCache": [mark_touched(p + "Victim", p + "Actor")]},
            ],
        },
        {
            "name": "Naughty: penalty - next in line",
            "skipCondition": not_started(p),
            "actions": [pop_queue("penQueue"), pop_queue("penCards")],
        },
    ]


def steal_groups():
    p = "stl"
    return [
        {
            "name": "Naughty: steal - choose a victim",
            "skipCondition": [sel("logicalNOT", C("arg", p + "Ready"))],
            "actions": [actor_setup(p, "stealQueue")] + victim_pick_actions(
                p, p + "Victim", p + "Pool", "stealVictimQuestion", p + "Actor"),
        },
        explode_group(p, p + "Victim", "Naughty: steal - lay out their cards"),
        {
            "name": "Naughty: steal - take a card",
            "skipCondition": not_ready(p),
            "actions": choose_card_actions(p, p + "Actor", "stealCardQuestion") + [
                # Pile: the chosen card moves into the thief's own pile.
                {"key": "moveCards",
                 "payload": {"preset": {"type": "deck", "qnt": 1},
                             "cached": {"from": p + "PickedDeck",
                                        "to": p + "ActorDeck"}}},
                # Hand: the same card has to change hands too, or the pile and
                # the hand - which is what bust detection reads - drift apart.
                {"key": "recallCards",
                 "payload": {"preset": {"deck": "copies", "qnt": 1},
                             "cached": {"targets": p + "Victim",
                                        "cardNames": p + "PickedList"}}},
                {"key": "dealDeck",
                 "payload": {"preset": {"deck": "copies", "qnt": 1,
                                        "sortBy": "rank", "order": "asc"},
                             "cached": {"targets": p + "Actor",
                                        "cardNames": p + "PickedList"}},
                 "saveValueInCache": [mark_touched(p + "Victim", p + "Actor")]},
            ],
        },
        collapse_group(p, p + "Victim", "Naughty: steal - put the rest back"),
        {
            "name": "Naughty: steal - restore the board",
            "skipCondition": not_started("stl"),
            "actions": [restore_main_widget(), pop_queue("stealQueue")],
        },
    ]


def discard_groups():
    p = "dsc"
    return [
        {
            "name": "Naughty: discard - choose a victim",
            "skipCondition": [sel("logicalNOT", C("arg", p + "Ready"))],
            "actions": [actor_setup(p, "discardQueue")] + victim_pick_actions(
                p, p + "Victim", p + "Pool", "discardVictimQuestion", p + "Actor"),
        },
        explode_group(p, p + "Victim", "Naughty: discard - lay out their cards"),
        {
            "name": "Naughty: discard - throw a card away",
            "skipCondition": not_ready(p),
            "actions": choose_card_actions(p, p + "Actor", "discardCardQuestion") + [
                {"key": "moveCards",
                 "payload": {"preset": {"type": "deck", "qnt": 1, "to": "discard"},
                             "cached": {"from": p + "PickedDeck"}}},
                {"key": "recallCards",
                 "payload": {"preset": {"deck": "copies", "qnt": 1},
                             "cached": {"targets": p + "Victim",
                                        "cardNames": p + "PickedList"}},
                 "saveValueInCache": [mark_touched(p + "Victim")]},
            ],
        },
        collapse_group(p, p + "Victim", "Naughty: discard - put the rest back"),
        {
            "name": "Naughty: discard - restore the board",
            "skipCondition": not_started("dsc"),
            "actions": [restore_main_widget(), pop_queue("discardQueue")],
        },
    ]


def swap_not_ready():
    """skipCondition for every group from the layout onwards.

    Both halves have to have landed: two players chosen, and both of them
    holding something that can be taken. All four flags are cleared at the top
    of the tick in "Freezers and flippers", so a stale value from an earlier
    Swap cannot let this run.
    """
    return [sel("logicalNOT", X("arg", sel(
        "logicalAND",
        X("arg1", sel("logicalAND",
                      C("arg1", "swpaReady"), C("arg2", "swpaHasCards"))),
        X("arg2", sel("logicalAND",
                      C("arg1", "swpbReady"), C("arg2", "swpbHasCards"))))))]


def swap_layout_action():
    """Work out the three-row grid both hands are laid out on.

    The grid is filled row by row, so the width is the larger of the two hands
    and the shorter row is padded out with empty decks — without that, the
    second player's first cards wrap up onto the end of the first player's row.
    Only one row can ever need padding, and the third row is left blank: the
    grid is three rows tall but only two rows of decks are handed to it.
    """
    pad_needed = sel("subtract", C("arg1", "swpCols"), C("arg2", "swpaCount"))
    return {"key": "emptyAction", "saveValueInCache": [
        cache("swpCols", sel("maxValue", X("list", sel(
            "createList", C("arg1", "swpaCount"), C("arg2", "swpbCount"))))),
        cache("swpRowPad", sel("sublist",
                               C("list", "swapPadDecks"),
                               P("start", 0),
                               X("end", pad_needed))),
        cache("swpRowDecks", sel(
            "concat",
            X("list1", sel("concat",
                           C("list1", "swpaDecks"),
                           C("list2", "swpRowPad"))),
            C("list2", "swpbDecks"))),
    ]}


def swap_groups():
    """Pick two players, then pick one card from each of two rows on screen.

    The older flow asked four questions in sequence — player, card, player,
    card — and had to lay out, tear down and relay the central widget between
    them, parking the first card in a holding deck along the way. This one asks
    for the two players first, then puts both hands up at once, one row each,
    and takes the two clicks back to back off the same widget. Nothing has to
    be parked: both cards are still sitting in their own single-card decks when
    the trade happens.

    The two rows have to come from different deck families (`k_` and `j_`) —
    both players can be holding an n_5, and one deck per card name cannot hold
    two of them.
    """
    a, b = "swpa", "swpb"
    skip = swap_not_ready()
    return [
        {
            "name": "Naughty: swap - choose the first player",
            "skipCondition": [sel("logicalNOT", C("arg", a + "Ready"))],
            # The swapper is allowed to pick themselves as one of the two.
            "actions": [actor_setup(a, "swapQueue", exclude_actor=False)]
            + victim_pick_actions(a, a + "Victim", a + "Pool",
                                  "swapVictimAQuestion", a + "Actor"),
        },
        {
            "name": "Naughty: swap - work out who is left to swap with",
            "skipCondition": not_ready(a),
            "actions": [
                {"key": "emptyAction", "saveValueInCache": [
                    cache(b + "Actor", copy_of(a + "Actor")),
                    cache(b + "ActorDeck", copy_of(a + "ActorDeck")),
                    cache(b + "Pool", pool_of(a + "Victim")),
                    cache(b + "Ready", sel("greaterThan",
                                           X("arg1", sel("listLength",
                                                         C("list", b + "Pool"))),
                                           P("arg2", 0))),
                ]},
            ],
        },
        {
            # Kept separate from the group above so the vote is never put to a
            # player when the pool it draws its options from is empty.
            "name": "Naughty: swap - choose the second player",
            "skipCondition": [sel("logicalNOT", C("arg", b + "Ready"))],
            "actions": victim_pick_actions(b, b + "Victim", b + "Pool",
                                           "swapVictimBQuestion", b + "Actor",
                                           deck_dict="cardNameToPickDeckB"),
        },
        {
            "name": "Naughty: swap - work out the layout",
            "skipCondition": skip,
            "actions": [swap_layout_action()],
        },
        explode_group(a, a + "Victim", "Naughty: swap - lay out the first hand",
                      skip=skip),
        explode_group(b, b + "Victim", "Naughty: swap - lay out the second hand",
                      skip=skip),
        {
            "name": "Naughty: swap - trade the cards",
            "skipCondition": skip,
            "actions": [
                # One widget, three rows: first player, second player, empty.
                {
                    "key": "createGenericCardWidget",
                    "payload": {
                        "preset": dict(WIDGET_LOOK),
                        "cached": {"decks": "swpRowDecks"},
                        "computed": {
                            "dimensions": sel("getObjectField",
                                              C("obj", "swapRowDimensions"),
                                              C("field", "swpCols")),
                        },
                    },
                },
                # Two clicks off that one widget. Each `decks` list is the row
                # it is allowed to come from, so the top row is live for the
                # first question and the middle row for the second.
                pick_card_action(a, a + "Actor", "swapCardAQuestion"),
                pick_card_action(b, b + "Actor", "swapCardBQuestion"),
                # Piles: each card goes into the other player's pile. Both are
                # still in their own single-card decks, so neither needs
                # parking anywhere first.
                {"key": "moveCards",
                 "payload": {"preset": {"type": "deck", "qnt": 1},
                             "cached": {"from": a + "PickedDeck",
                                        "to": b + "VictimDeck"}}},
                {"key": "moveCards",
                 "payload": {"preset": {"type": "deck", "qnt": 1},
                             "cached": {"from": b + "PickedDeck",
                                        "to": a + "VictimDeck"}}},
                # Hands: recall both before dealing either, so nobody
                # momentarily holds two copies of the same card.
                {"key": "recallCards",
                 "payload": {"preset": {"deck": "copies", "qnt": 1},
                             "cached": {"targets": a + "Victim",
                                        "cardNames": a + "PickedList"}}},
                {"key": "recallCards",
                 "payload": {"preset": {"deck": "copies", "qnt": 1},
                             "cached": {"targets": b + "Victim",
                                        "cardNames": b + "PickedList"}}},
                {"key": "dealDeck",
                 "payload": {"preset": {"deck": "copies", "qnt": 1,
                                        "sortBy": "rank", "order": "asc"},
                             "cached": {"targets": b + "Victim",
                                        "cardNames": a + "PickedList"}}},
                {"key": "dealDeck",
                 "payload": {"preset": {"deck": "copies", "qnt": 1,
                                        "sortBy": "rank", "order": "asc"},
                             "cached": {"targets": a + "Victim",
                                        "cardNames": b + "PickedList"}},
                 "saveValueInCache": [mark_touched(a + "Victim", b + "Victim")]},
            ],
        },
        collapse_group(a, a + "Victim",
                       "Naughty: swap - put the first hand back", skip=skip),
        collapse_group(b, b + "Victim",
                       "Naughty: swap - put the second hand back", skip=skip),
        {
            "name": "Naughty: swap - restore the board",
            "skipCondition": not_started("swpa"),
            "actions": [restore_main_widget(), pop_queue("swapQueue")],
        },
    ]
