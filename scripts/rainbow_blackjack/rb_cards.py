#!/usr/bin/env python3
"""What is in each Rainbow Blackjack deck — names, image slugs and labels.

Pure data, no drawing, so the deck builder and the cheatsheet can import it
without needing Pillow. rb_art.py adds the colours and icons on top.
"""

FOLDERS = {
    "nice": "images/rainbow_blackjack/nice",
    "naughty": "images/rainbow_blackjack/naughty",
}

NUMBERS = {"nice": list(range(0, 13)), "naughty": list(range(0, 14))}

# Only Naughty gives a number a rule of its own. The Zero is the only rule that
# applies to every copy of a number — Unlucky 7 and Lucky 13 are single cards
# (see SPECIAL_NUMBERS), so the ordinary 7s and 13s carry no caption.
CAPTIONS = {
    "nice": {},
    "naughty": {0: "THE ZERO"},
}

# One-off numbers: a single copy in the deck that scores like its face value but
# carries a rule and its own artwork. (name, slug, label, value, caption, drawn)
# `drawn` is False for faces that were supplied rather than generated — the
# renderer must not overwrite those.
SPECIAL_NUMBERS = {
    "nice": [],
    "naughty": [
        ("n_7_unlucky", "7_unlucky", "7", 7, "UNLUCKY", False),
        ("n_13_lucky", "13_lucky", "13", 13, "LUCKY", False),
    ],
}

# (card name in the deck JSON, image slug, label drawn on the card)
MODIFIERS = {
    "nice": [
        ("times_2", "times_2", "×2"),
        ("plus_2", "plus_2", "+2"),
        ("plus_4", "plus_4", "+4"),
        ("plus_6", "plus_6", "+6"),
        ("plus_8", "plus_8", "+8"),
        ("plus_10", "plus_10", "+10"),
    ],
    "naughty": [
        ("n_divide_2", "divide_2", "÷2"),
        ("n_minus_2", "minus_2", "−2"),
        ("n_minus_4", "minus_4", "−4"),
        ("n_minus_6", "minus_6", "−6"),
        ("n_minus_8", "minus_8", "−8"),
        ("n_minus_10", "minus_10", "−10"),
    ],
}

MODIFIER_CAPTION = {"nice": "BONUS", "naughty": "PENALTY"}

ACTIONS = {
    "nice": [
        ("freeze", "stop", "STOP"),
        ("flip", "flip", "HIT 3"),
        ("second_chance", "second_chance", "EXTRA LIFE"),
    ],
    "naughty": [
        ("n_just_one_more", "just_one_more", "ONE MORE"),
        ("n_flip_four", "flip_four", "HIT 4"),
        ("n_steal", "steal", "STEAL"),
        ("n_swap", "swap", "SWAP"),
        ("n_discard", "discard", "DISCARD"),
    ],
}
