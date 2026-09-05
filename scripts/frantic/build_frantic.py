#!/usr/bin/env python3
"""Build Frantic (ex-Doodle Dash) game JSON from scratch.

Frantic = a real-time drawing race. Each round one player is the GUESSER; everyone
else draws the SAME secret word simultaneously on private whiteboards for one shared,
per-round-random duration (timer runs out for all). Their captured drawings become
cards (in SUBMISSION order). The guesser is then shown the drawings ONE AT A TIME via
createVote (the raw captured URL as the vote image, public — never contains the word);
the HOST grades Correct/Not-yet on the honor system (once per rotation the host is also
the guesser — fine). Guessing early scores the guesser more (numDrawers - k) and gives
the shown drawing's owner a bonus. After each reveal the just-shown card is dealt into
the guesser's private hand so they can keep referring to earlier drawings. At round end
ALL drawings are shown in a central-widget grid — each drawing in its OWN deck, always
2 rows. Individual scoring, fixed 2 rotations (play-again vote at each rotation
boundary), highest score wins.

Individual game (no teams). Players 4-8. See memory ludio-* notes + Things to remember.
Assets: bespoke CC0 doodle banner + wallpaper at Cloudinary images/frantic/.
No setImagesRow (only the guesser holds cards — the reserved strip would eat the
whiteboard/vote space for everyone).
"""
import json

OUT = '/Users/ankitbuddhiraju/Documents/claude/Code/game_jsons/frantic.json'

# ---------------- DSL helpers ----------------
def pc(n, v):  return {"name": n, "type": "cached", "value": v}
def pp(n, v):  return {"name": n, "type": "preset", "value": v}
def pm(n, v):  return {"name": n, "type": "computed", "value": v}
def S(sel, *ps): return {"selector": sel, "params": list(ps)}
def svc(n, v): return {"name": n, "value": v}
def act(key, payload=None, save=None, ph=None, skip=None):
    # canonical action key order: key, skipCondition, payload, postHandler, saveValueInCache
    a = {"key": key}
    if skip is not None: a["skipCondition"] = skip
    if payload is not None: a["payload"] = payload
    if ph is not None: a["postHandler"] = ph
    if save is not None: a["saveValueInCache"] = save
    return a

# canonical action-group key order
_GRP_ORDER = ["name", "turnPlayersToSpectators", "turnSpectatorsToPlayers",
              "skipCondition", "repeat", "parallel", "checkWinCondition", "actions"]
def grp(name, actions, **kw):
    raw = {"name": name, "actions": actions}
    raw.update(kw)
    return {k: raw[k] for k in _GRP_ORDER if k in raw}

# convenience selectors
def getc(name):  return S("getCachedValue", pp("name", name))
def NOT(v):      return S("logicalNOT", pc("arg", v)) if isinstance(v, str) else S("logicalNOT", pm("arg", v))
def LEN(listvar): return S("listLength", pc("list", listvar))
def objget(obj, key_cached, default=None):
    ps = [pp("objectName", obj), pc("value", key_cached)]
    if default is not None:
        ps.append(pp("defaultValue", default))
    return S("getCachedObjectValue", *ps)

# ============================================================
# Colors / theme
# ============================================================
BG      = "#fdf6e3"   # paper cream
BORDER  = "#333333"
TEXT    = "#333333"
ACCENT  = "#e07b39"   # marker orange
# central-widget board background — the shared wood image (Picky Eaters, Rat in the Kitchen, ...)
WOOD    = "https://res.cloudinary.com/liars-club/image/upload/wood_qbegm0.jpg"
# drawing-themed LottieFiles celebration for a correct guess (Asim Das "Web Design",
# person at a drawing tablet w/ pencils; Lottie Simple License, free) — Optimized Lottie JSON
CELEBRATE_ANIM = "https://lottie.host/0f017a81-c14e-4aaa-945f-9d6be0890808/ArBdeOOodk.json"

DRAW_COLORS = ["red", "green", "blue", "aqua", "black", "orange",
               "brown", "gold", "pink", "purple", "coral"]
DRAW_PALETTE = 6   # colors offered on each whiteboard

# random per-round total drawing time (seconds) — pick one from this list each round.
# Band centered on ~60s (user wanted "more time to draw, 60 seconds") but kept random.
DRAW_TIMES = [50, 55, 60, 65, 70]

# constant upper bound on drawers (= maxPlayers - 1). We create this many display
# decks ONCE so spectators can join without needing new decks mid-game.
MAX_DRAWERS = 7

# central-widget grid dims keyed by number of drawings (= numDrawers, 3..7 typical).
# ALWAYS 2 rows; columns = ceil(numDrawers / 2) so the drawings spread across the board.
GRID_DIMS = {
    "2": [2, 1], "3": [2, 2], "4": [2, 2], "5": [2, 3],
    "6": [2, 3], "7": [2, 4], "8": [2, 4],
}

# ============================================================
# Prompt bank — concrete, DRAWABLE, guessable words/short phrases
# ============================================================
PROMPTS = [
    "a birthday cake", "a lighthouse", "a snowman", "a treasure chest", "a hot air balloon",
    "a robot", "a dragon", "a mermaid", "a pirate ship", "a castle",
    "an octopus", "a rocket ship", "a cactus in a pot", "a slice of pizza", "a hamburger",
    "a cup of coffee", "an ice cream cone", "a rubber duck", "a beach umbrella", "a campfire",
    "a ghost", "a jack-o-lantern", "a Christmas tree", "a spider web", "a rainbow",
    "a unicorn", "a penguin", "an elephant", "a giraffe", "a kangaroo",
    "a hedgehog", "a narwhal", "a sloth hanging from a branch", "a turtle", "a jellyfish",
    "a bumblebee", "a butterfly", "a ladybug", "a snail", "a frog on a lily pad",
    "a windmill", "a hot dog stand", "a ferris wheel", "a roller coaster", "a merry-go-round",
    "a sandcastle", "a fishing boat", "a submarine", "a helicopter", "a hot rod car",
    "a bicycle", "a skateboard", "a pogo stick", "a unicycle", "a tricycle",
    "a wizard hat", "a crown", "a pair of glasses", "a top hat", "a cowboy hat",
    "a scarecrow", "a garden gnome", "a mailbox", "a park bench", "a street lamp",
    "a grandfather clock", "an hourglass", "a compass", "a treasure map", "a magnifying glass",
    "a paintbrush and palette", "a stack of books", "a globe", "a telescope", "a microscope",
    "a volcano erupting", "a desert island", "a waterfall", "a mountain range", "a tornado",
    "a cloud raining", "a lightning bolt", "a crescent moon", "a shooting star", "a sun with sunglasses",
    "a cactus wearing a sombrero", "a cat playing piano", "a dog on a skateboard", "a bear eating honey", "a fox in a scarf",
    "an owl reading a book", "a rabbit magician", "a hamster on a wheel", "a parrot on a perch", "a peacock",
    "a flamingo standing on one leg", "a swan", "a rooster crowing", "a pig in mud", "a cow jumping over the moon",
    "a race car", "a fire truck", "a school bus", "a train engine", "a tractor",
    "an ambulance", "a police car", "a garbage truck", "a monster truck", "a go-kart",
    "a cheeseburger with fries", "a taco", "a donut with sprinkles", "a cupcake", "a lollipop",
    "a candy cane", "a gingerbread man", "a jar of cookies", "a bunch of grapes", "a watermelon slice",
    "a pineapple", "a banana", "a strawberry", "a bunch of bananas", "an apple with a worm",
    "a treasure key", "a padlock", "a light bulb idea", "a battery", "a plug and socket",
    "a wrench and hammer", "a saw", "a screwdriver", "a paint roller", "a ladder",
    "a tent under stars", "a canoe", "a backpack", "a pair of hiking boots", "a compass and map",
    "a snow globe", "a music note", "a guitar", "a drum set", "a trumpet",
    "a saxophone", "a violin", "a piano", "a microphone", "a pair of headphones",
    "a superhero cape", "a magic wand", "a genie lamp", "a crystal ball", "a potion bottle",
    "a haunted house", "a UFO abducting a cow", "an astronaut floating", "a planet with rings", "a comet",
    "a knight in armor", "a wizard casting a spell", "a fairy with wings", "a troll under a bridge", "a giant beanstalk",
    "a treasure-hunting pirate", "a ninja", "a cowboy on a horse", "a firefighter", "a chef with a tall hat",
    "a mailman delivering letters", "a doctor with a stethoscope", "a scientist with a beaker", "a farmer with a pitchfork", "a clown juggling",
    # --- expansion to 300 ---
    "a shark", "a dolphin", "a whale", "a crab", "a lobster",
    "a seahorse", "a starfish", "a koala", "a panda", "a lion",
    "a tiger", "a zebra", "a monkey", "a gorilla", "a camel",
    "a rhino", "a hippo", "a deer", "a moose", "a squirrel",
    "a raccoon", "a skunk", "a bat", "a crow", "a seagull",
    "a toucan", "an ostrich", "a chameleon", "a snake", "a scorpion",
    "an ant", "a grasshopper", "a dragonfly", "a caterpillar", "a goat",
    "a sandwich", "a pretzel", "a bagel", "a croissant", "a stack of pancakes",
    "a waffle", "a fried egg", "a strip of bacon", "a wedge of cheese", "a sushi roll",
    "a bowl of ramen", "a plate of spaghetti", "a bag of popcorn", "a carrot", "an ear of corn",
    "a mushroom", "a chili pepper", "an avocado", "a lemon", "a cherry",
    "a pear", "a coconut", "a slice of pie", "a milkshake", "a soda can",
    "an umbrella", "an anchor", "a kite", "a birthday present", "a camera",
    "a television", "an old telephone", "a laptop", "an alarm clock", "a pair of scissors",
    "a pencil", "a ruler", "a paperclip", "an envelope", "a postage stamp",
    "a wallet", "a broom", "a bucket", "a watering can", "a vase of flowers",
    "a party hat", "a pair of dice", "a playing card", "a magnet", "a horseshoe",
    "a palm tree", "a sunflower", "a rose", "a tulip", "a maple leaf",
    "an acorn", "a pinecone", "a seashell", "an iceberg", "a snowflake",
    "an airplane", "a sailboat", "a kayak", "a scooter", "a motorcycle",
    "a taxi cab", "an army tank", "a wheelbarrow", "a shopping cart", "a rowboat",
    "a soccer ball", "a basketball", "a baseball bat", "a tennis racket", "a bowling pin",
    "a dartboard", "a boxing glove", "a dumbbell", "a jump rope", "a surfboard",
    "a house", "a barn", "an igloo", "a pyramid", "the Eiffel Tower",
    "a king", "an alien", "a mummy", "a witch on a broom", "a scuba diver",
]

# ============================================================
# strings (Default) — centralized text, refactor-ready
# ============================================================
strings_default = {
    "bannerImg": "banner",
    "wallpaperImg": "wallpaper",
    # welcome + tutorial vote
    "welcomeToFrantic": "Welcome to Frantic!",
    "inAMomentTell": "<b>($1)</b> - in a moment, tell me whether you want Ludio to teach your group how to play Frantic!",
    "tutorialModeTitle": "Tutorial mode",
    "whoNeedsTutorialQuestion": "($1), who needs the tutorial? Click on the players or select from the middle.",
    "everybodyNobodyTargets": ["Everybody!", "Nobody!"],
    "everybodyNobodyOptions": {
        "Everybody!": {"icon": "https://res.cloudinary.com/liars-club/image/upload/icons/like.svg",
                        "backgroundColor": "#D3D3D3", "boxIconColor": "#D3D3D3", "textColor": "black", "widgetIconColor": "green"},
        "Nobody!": {"icon": "https://res.cloudinary.com/liars-club/image/upload/icons/dislike.svg",
                     "backgroundColor": "#D3D3D3", "boxIconColor": "#D3D3D3", "textColor": "black", "widgetIconColor": "red"},
    },
    # tutorial slides
    "tut1Header": "One guesser, everyone else draws",
    "tut1Text": "Each round, one player is the <b>guesser</b>. Everyone else secretly gets the <b>same word</b> and races to draw it on their own whiteboard before the timer runs out.",
    "tut2Header": "Drawings are revealed one at a time",
    "tut2Text": "The guesser is shown the drawings <b>one by one</b> and says out loud what they think the word is. Each drawing that pops up is a fresh clue!",
    "tut3Header": "Guess early for more points",
    "tut3Text": "The sooner the guesser gets it, the more points they score - and the player whose drawing cracked it earns a bonus. So draw clearly and fast!",
    "tut4Header": "The host grades",
    "tut4Text": "As drawings appear and the guesser shouts out answers, the <b>host</b> taps <b>Correct!</b> the moment they get it (honor system). At the end, everyone sees all the drawings side by side.",
    # round flow
    "youAreGuesser": "You're the guesser this round! Everyone else is drawing the same secret word. Watch the drawings and shout out your guess!",
    # NOTE: drawThis is used in a createDrawing prompt -> NO <b> tags allowed here.
    "drawThis": "Draw: ($1)",
    "drawThisHeader": "Get drawing!",
    "gotYourDrawingHeader": "Got your drawing!",
    "gotYourDrawing": "Nice! Sit tight while everyone else finishes drawing.",
    "sitTightGuesser": "Others are drawing... get ready to guess!",
    "reviewSelect": "Everyone's drawings for \"($1)\"! ($2), click any drawing to continue.",
    "judgeHeader": "Did the guesser get it?",
    "judgeQuestion": "Has ($1) correctly guessed what this drawing is yet?",
    "judgeTargets": ["Correct!", "Not yet"],
    "judgeOptions": {
        "Correct!": {"icon": "https://res.cloudinary.com/liars-club/image/upload/icons/like.svg",
                      "backgroundColor": "#D3D3D3", "boxIconColor": "#D3D3D3", "textColor": "black", "widgetIconColor": "green"},
        "Not yet": {"icon": "https://res.cloudinary.com/liars-club/image/upload/icons/dislike.svg",
                     "backgroundColor": "#D3D3D3", "boxIconColor": "#D3D3D3", "textColor": "black", "widgetIconColor": "red"},
    },
    "finalBoardHeader": "Last chance!",
    "finalJudgeQuestion": "Has ($1) correctly guessed what any of these drawings are yet?",
    "revealWordHeader": "The word was...",
    "revealWordText": "The word was: <b>($1)</b>!",
    "guesserGotItHeader": "Nice guess!",
    "guesserGotItText": "($1) guessed <b>($2)</b>!",
    "nobodyGotItHeader": "Nobody got it!",
    "nobodyGotItText": "The word was <b>($1)</b>. Better luck next round!",
    "reviewHeader": "Round ($1) drawings",
    "reviewText": "Take a look at everyone's drawing for \"($1)\"!",
    # play again
    "playAgainTitle": "PLAY AGAIN?",
    "playAgainQuestion": "Would you like to play another round?",
    "playAgainTargets": ["Reset scores", "Keep scores", "I'M SO DONE"],
    "playAgainOptions": {
        "Keep scores": {"icon": "https://res.cloudinary.com/liars-club/image/upload/icons/like.svg",
                         "backgroundColor": "#D3D3D3", "boxIconColor": "#D3D3D3", "textColor": "black", "widgetIconColor": "green"},
        "Reset scores": {"icon": "https://res.cloudinary.com/liars-club/image/upload/icons/like.svg",
                          "backgroundColor": "#D3D3D3", "boxIconColor": "#D3D3D3", "textColor": "black", "widgetIconColor": "blue"},
        "I'M SO DONE": {"icon": "https://res.cloudinary.com/liars-club/image/upload/icons/dislike.svg",
                         "backgroundColor": "#D3D3D3", "boxIconColor": "#D3D3D3", "textColor": "black", "widgetIconColor": "red"},
    },
    "prompts": PROMPTS,
}

# ============================================================
# 1. gameInitOptions
# ============================================================
gio = {
    "minPlayers": 4,
    "maxPlayers": 8,
    "timePerRound": 8,
    "preferredPlayersQnt": [5, 6, 7],
    "allowSpectatorBecomePlayer": True,
    "allowPlayerBecomeSpectator": True,
    "roleConfirmation": False,
    "useDefaultRoles": True,
    "notChangeLayoutAfterGame": True,
    "teams": {"all": {"id": "all", "name": "All", "color": ACCENT,
                       "roles": ["player"]}},
    "roles": [
        {"roleInfo": {"id": "player", "name": "Player",
                       "description": "Draw fast, guess faster!",
                       "avatar": "https://res.cloudinary.com/liars-club/image/upload/card_player_ed7jck.webp",
                       "team": "all", "prefix": "a "},
         "isDefaultRole": True, "isRequired": False},
    ],
    "images": {
        # bespoke doodle art (CC0 sources, processed) uploaded to Cloudinary images/frantic
        "banner": {"url": "https://res.cloudinary.com/liars-club/image/upload/images/frantic/banner.png"},
        "wallpaper": {"url": "https://res.cloudinary.com/liars-club/image/upload/images/frantic/wallpaper.png"},
        "transparent": {"url": "https://res.cloudinary.com/liars-club/image/upload/transparent_sbx4wv.png"},
        "winner": {"url": "https://res.cloudinary.com/liars-club/image/upload/winner_h5eyfr.gif"},
    },
    "soundboard": {"default": {
        "reminder": "https://res.cloudinary.com/liars-club/video/upload/audio/reminder.mp4",
        "success": "https://res.cloudinary.com/liars-club/video/upload/audio/avalon/sounds/success.mp3",
        "music_1": "https://res.cloudinary.com/liars-club/video/upload/audio/soft_indie.mp3",
        "clap": "https://res.cloudinary.com/liars-club/video/upload/audio/polite_clap.mp3",
    }},
    "animations": {
        "winner": "https://lottie.host/3cba778c-312b-410c-8240-c9fdc0c4f5ef/Iu7CfEX2Va.json",
        # drawing-themed celebration for a correct guess (sourced from LottieFiles below)
        "celebrate": CELEBRATE_ANIM,
    },
    "strings": {"Default": strings_default},
}

# ============================================================
# 2. beforeLoopActions
# ============================================================
before = [
    act("changeBackground", {"cached": {"image": "wallpaperImg"}}),
    act("emptyAction", save=[
        svc("round", 1),
        svc("currentMinScore", 0),
        svc("playAgain", True),
        svc("players", S("allPlayers")),
        svc("numPlayers", LEN("players")),
        # numDrawers is constant all game (one guesser, rest draw) — needed by
        # "Create draw decks" which runs before "Pick guesser" recomputes it.
        svc("numDrawers", S("dec", pc("arg", "numPlayers"))),
        # guesser pointer starts at LAST player so first nextPlayer -> players[0]
        svc("currentGuesser", S("selectElement", pc("list", "players"),
                                pm("index", S("dec", pm("arg", LEN("players")))))),
        svc("unusedPrompts", S("shuffleList", pc("list", "prompts"))),
        svc("gridDims", GRID_DIMS),
        svc("drawTimes", DRAW_TIMES),
        svc("solved", False),
        svc("reset", False),
        svc("winner", ""),
        # names of the per-drawing display decks (built once in "Create draw decks")
        svc("drawDecks", []),
    ]),
    act("showScore", {"preset": {"order": "highest"}, "cached": {"from": "players", "to": "players"}}),
    # host
    act("emptyAction", save=[
        svc("host", S("ifElse",
            pm("condition", S("contains", pm("list", S("allPlayers")), pm("element", S("getHostPlayerId")))),
            pm("thenValue", S("createList", pm("arg1", S("getHostPlayerId")))),
            pm("elseValue", S("createList", pm("arg1", S("selectElement", pm("list", S("allPlayers")), pp("index", 0)))))))
    ]),
    # welcome
    act("createNotification", {
        "preset": {"duration": 8},
        "cached": {"header": "welcomeToFrantic", "image": "bannerImg"},
        "computed": {
            "to": S("allPlayers"),
            "text": S("formatString", pc("format", "inAMomentTell"),
                      pm("arg1", S("listToString", pm("list", S("getPlayerNamesByIds", pc("ids", "host"))))))
        }
    }),
    # standard tutorial createMixVote (verbatim structure from enigma/CC)
    act("createMixVote", {
        "preset": {
            "terminationCondition": "get_all_votes", "showResultInRealTime": True,
            "showResultDuration": 2, "showResultDelay": 0, "point.allowFewerAnswers": True,
            "point.terminationCondition": "get_all_votes", "poll.answersQuantity": 1,
            "oneClick": True, "allowRevoting": True, "poll.terminationCondition": "get_all_votes",
        },
        "cached": {
            "actors": "host", "point.targets": "players", "point.answersQuantity": "numPlayers",
            "title": "tutorialModeTitle", "poll.targets": "everybodyNobodyTargets",
            "pollVoteTargetsOptions": "everybodyNobodyOptions",
        },
        "computed": {
            "question": S("formatString", pc("format", "whoNeedsTutorialQuestion"),
                          pm("arg1", S("getPlayerNameById", pc("id", "host.0"))))
        }
    }, save=[
        svc("voteResult", getc("lastActionResult.voteResult")),
        svc("learners", S("ifElse",
            pm("condition", S("contains", pc("list", "players"), pc("element", "voteResult.0"))),
            pc("thenValue", "voteResult"),
            pm("elseValue", S("ifElse",
                pm("condition", S("contains", pc("list", "voteResult"), pc("element", "everybodyNobodyTargets.0"))),
                pc("thenValue", "players"),
                pp("elseValue", []))))),
        svc("tutorial", S("greaterThan", pm("arg1", LEN("learners")), pp("arg2", 0))),
    ]),
    # decks — per-drawing display decks are created in the gameLoop ("Create draw decks").
    # hand_pile feeds the guesser's private reference hand during the reveal.
    act("createCustomDeck", {"preset": {"public": True, "name": "trash"}}),
    act("createCustomDeck", {"preset": {"public": True, "name": "hand_pile", "facedown": False}}),
    act("showAllPlayersHands"),
]

# ============================================================
# 3. gameLoop
# ============================================================
loop = []

# --- Tutorial ---
loop.append(grp("Tutorial",
    skipCondition=[NOT("tutorial")],
    actions=[
        act("createNotification", {"preset": {"duration": 14, "image": "banner"},
             "cached": {"to": "learners", "header": "tut1Header", "text": "tut1Text"}}),
        act("createNotification", {"preset": {"duration": 14, "image": "banner"},
             "cached": {"to": "learners", "header": "tut2Header", "text": "tut2Text"}}),
        act("createNotification", {"preset": {"duration": 14, "image": "banner"},
             "cached": {"to": "learners", "header": "tut3Header", "text": "tut3Text"}}),
        act("createNotification", {"preset": {"duration": 14, "image": "banner"},
             "cached": {"to": "learners", "header": "tut4Header", "text": "tut4Text"}}),
        act("emptyAction", save=[svc("tutorial", False)]),
    ]))

# --- Vertical layout (once, after the tutorial): gives the central grid vertical
#     space and seats the guesser's reference hand below the board. Persists. ---
loop.append(grp("Vertical layout",
    skipCondition=[S("greaterThan", pc("arg1", "gameLoopIndex"), pp("arg2", 0))],
    actions=[
        act("changeLayout", {"preset": {"type": "HIGHLIGHT", "direction": "VERTICAL", "percent": 50}}),
    ]))

# --- Create the per-drawing display decks ONCE (numDrawers is constant = numPlayers-1).
#     Each drawing lives in its own deck so the end-of-round grid can show them all
#     spread out (one card per cell). Also record the deck names in `drawDecks`. ---
loop.append(grp("Create draw decks",
    skipCondition=[S("greaterThan", pc("arg1", "gameLoopIndex"), pp("arg2", 0))],
    repeat={"qnt": MAX_DRAWERS},
    actions=[
        act("createCustomDeck", {"preset": {"public": True, "enlargeOnHover": True, "facedown": False},
             "computed": {"name": S("formatString", pp("format", "draw_($1)"), pc("arg1", "repeatIndex"))}}),
        act("emptyAction", save=[
            svc("drawDecks", S("append", pc("list", "drawDecks"),
                pm("element", S("formatString", pp("format", "draw_($1)"), pc("arg1", "repeatIndex"))))),
        ]),
    ]))

# --- Pick guesser + prompt + setup ---
loop.append(grp("Pick guesser", actions=[
    act("emptyAction", save=[
        svc("players", S("allPlayers")),
        svc("numPlayers", LEN("players")),
        svc("solved", False),
        # default 'reset' every round: Play again only fires at rotation boundaries
        # (and `round` is already incremented by then), so without this the
        # "Reset scores" group hits logicalNOT(undefined) on non-boundary rounds.
        svc("reset", False),
        svc("drawingMap", {}),
        # reveal order is built by SUBMISSION order — each drawer appends themselves
        # when their createDrawing completes (see The Dash group).
        svc("revealOrder", []),
    ]),
    # advance guesser
    act("emptyAction", save=[
        svc("currentGuesser", S("nextPlayer", pc("playersList", "players"), pc("playerId", "currentGuesser"))),
    ]),
    act("emptyAction", save=[
        svc("drawers", S("listsSubtract", pc("list1", "players"),
                         pm("list2", S("createList", pc("arg1", "currentGuesser"))))),
    ]),
    act("emptyAction", save=[
        svc("numDrawers", LEN("drawers")),
        # per-round random total draw time
        svc("drawSeconds", S("selectElement",
                             pm("list", S("randomElementsList", pc("list", "drawTimes"), pp("length", 1))),
                             pp("index", 0))),
        # refill prompt bag if empty
        svc("unusedPrompts", S("ifElse",
            pm("condition", S("greaterThan", pm("arg1", LEN("unusedPrompts")), pp("arg2", 0))),
            pc("thenValue", "unusedPrompts"),
            pm("elseValue", S("shuffleList", pc("list", "prompts"))))),
    ]),
    # pull the secret word
    act("emptyAction", save=[
        svc("currentPrompt", getc("unusedPrompts.0")),
        svc("unusedPrompts", S("sublist", pc("list", "unusedPrompts"), pp("start", 1), pm("end", LEN("unusedPrompts")))),
    ]),
    # tell the guesser to sit tight
    act("createNotification", {"preset": {"duration": 6, "image": "banner"},
         "cached": {"header": "sitTightGuesser", "text": "youAreGuesser"},
         "computed": {"to": S("createList", pc("arg1", "currentGuesser"))}}),
    # show the secret word to drawers only
    act("createNotification", {"preset": {"duration": 6},
         "cached": {"to": "drawers", "header": "drawThisHeader"},
         "computed": {
             "text": S("formatString", pc("format", "drawThis"), pc("arg1", "currentPrompt")),
         }}),
    # spotlight the guesser with a RED border from the very start of the turn (before drawing)
    act("highlightPlayers", {"preset": {"color": "#D83232"},
         "computed": {"listOfPlayers": S("createList", pc("arg1", "currentGuesser"))}}),
]))

# --- The Dash: parallel private whiteboards, same duration for all ---
loop.append(grp("The Dash",
    parallel={"type": "smart", "qnt": getc("numDrawers")},
    actions=[
        act("createDrawing", {
            "preset": {"terminationCondition": "get_all", "capture": True, "vertical": True,
                       "private": True, "sounds.waitForSoundEnd": False,
                       "sounds.list": ["soundboard.reminder"]},
            "cached": {"duration": "drawSeconds"},
            "computed": {
                "colors": S("randomElementsList", pp("list", DRAW_COLORS), pp("length", DRAW_PALETTE)),
                "actors": S("createList", pm("arg1", S("selectElement", pc("list", "drawers"), pc("index", "spaIndex")))),
                "playList.1": S("createList", pm("arg1", S("selectElement", pc("list", "drawers"), pc("index", "spaIndex")))),
                "question": S("formatString", pc("format", "drawThis"), pc("arg1", "currentPrompt")),
            }
        }, save=[
            # per-field write into shared drawingMap keyed by this drawer (engine-safe, CC pattern)
            svc("drawingMap", S("setCachedObjectFieldValue",
                pp("objectName", "drawingMap"),
                pm("fieldName", S("selectElement", pc("list", "drawers"), pc("index", "spaIndex"))),
                pc("value", "lastActionResult.url"))),
            # append this drawer as they FINISH -> revealOrder = submission order
            svc("revealOrder", S("append", pc("list", "revealOrder"),
                pm("element", S("selectElement", pc("list", "drawers"), pc("index", "spaIndex"))))),
        ]),
        # confirmation: show the drawer their captured drawing while others finish (CC pattern)
        act("createNotification", {
            "preset": {"duration": 6},
            "cached": {"header": "gotYourDrawingHeader", "text": "gotYourDrawing"},
            "computed": {
                "to": S("createList", pm("arg1", S("selectElement", pc("list", "drawers"), pc("index", "spaIndex")))),
                "image": S("getCachedObjectValue",
                    pp("objectName", "drawingMap"),
                    pm("value", S("selectElement", pc("list", "drawers"), pc("index", "spaIndex"))),
                    pp("defaultValue", "transparent")),
            }
        }),
    ]))

# --- Build cards from captured URLs, in reveal (submission) order (weight = order).
#     Two cards per drawing: one into its display deck draw_<k> (stays put, shown in
#     the end grid), one into hand_pile (dealt to the guesser during the reveal). ---
loop.append(grp("Build cards",
    repeat={"qnt": getc("numDrawers")},
    actions=[
        act("emptyAction", save=[
            svc("bDrawer", S("selectElement", pc("list", "revealOrder"), pc("index", "repeatIndex"))),
            svc("bDeck", S("formatString", pp("format", "draw_($1)"), pc("arg1", "repeatIndex"))),
        ]),
        act("emptyAction", save=[
            svc("bImage", objget("drawingMap", "bDrawer", default="transparent")),
            svc("bName", S("getPlayerNameById", pc("id", "bDrawer"))),
        ]),
        # display card -> its own deck
        act("createCard", {
            "preset": {"background": "white", "ratio": 0.77},
            "cached": {"cardImage": "bImage", "weight": "repeatIndex", "deck": "bDeck", "type": "bName"},
        }),
        # hand-reference card -> shared hand_pile
        act("createCard", {
            "preset": {"deck": "hand_pile", "background": "white", "ratio": 0.77},
            "cached": {"cardImage": "bImage", "weight": "repeatIndex", "type": "bName"},
        }),
        # label the display deck with the drawer's name (shown in the end grid)
        act("setDeckLabel", {"cached": {"deck": "bDeck", "label": "bName"}}),
    ]))

# --- Start guessing: open all hands so the guesser can see past drawings without
#     having to tap their hand open. (Guesser is already highlighted from turn start.) ---
loop.append(grp("Start guessing", actions=[
    act("showAllPlayersHands"),
]))

# --- Reveal & guess loop ([] loop; loopIndex = which reveal) ---
reveal_loop = [
    grp("Reveal setup", actions=[
        act("emptyAction", save=[
            svc("rDrawer", S("selectElement", pc("list", "revealOrder"), pc("index", "loopIndex"))),
        ]),
        act("emptyAction", save=[
            svc("rImage", objget("drawingMap", "rDrawer", default="transparent")),
        ]),
        # spotlight the guesser + the CURRENT drawing's author on top, everyone else below
        act("changeLayout", {
            "preset": {"type": "HIGHLIGHT", "direction": "VERTICAL", "percent": 50},
            "computed": {
                "top": S("createList", pc("arg1", "currentGuesser"), pc("arg2", "rDrawer")),
                "bottom": S("listsSubtract", pc("list1", "players"),
                    pm("list2", S("createList", pc("arg1", "currentGuesser"), pc("arg2", "rDrawer")))),
            }
        }),
    ]),
    grp("Judge vote", actions=[
        act("createVote", {
            "preset": {"type": "target_poll", "terminationCondition": "get_all_votes",
                       "showResultInRealTime": True, "showResultDuration": 1, "showResultDelay": 0,
                       "oneClick": True, "allowRevoting": True, "vertical": True,
                       "sounds.list": ["soundboard.reminder"]},
            "cached": {"image": "rImage", "title": "judgeHeader",
                       "targets": "judgeTargets", "pollVoteTargetsOptions": "judgeOptions",
                       "actors": "host", "playList.1": "host"},
            "computed": {
                # the HOST grades (once per rotation the host is also the guesser — fine).
                # conditional duration: disconnected host -> 1s
                "duration": S("ifElse",
                    pm("condition", S("contains", pm("list", S("allConnectedUsers")), pc("element", "host.0"))),
                    pp("thenValue", 25), pp("elseValue", 1)),
                # NB: the vote prompt is PUBLIC — never include the secret word here.
                "question": S("formatString", pc("format", "judgeQuestion"),
                              pm("arg1", S("getPlayerNameById", pc("id", "currentGuesser")))),
            }
        }, save=[
            svc("solved", S("isTargetGotMajority",
                            pc("voteResult", "lastActionResult"), pc("target", "judgeTargets.0"))),
        ]),
    ]),
    grp("Score correct", skipCondition=[NOT("solved")], actions=[
        # guesser scores (numDrawers - loopIndex); drawer bonus +2
        act("updateScore", {"computed": {"scores": S("createItemList",
            pp("length", 1),
            pm("item", S("createDict",
                pp("keys", ["list", "delta"]),
                pm("values", S("createList",
                    pm("arg1", S("createList", pc("arg1", "currentGuesser"))),
                    pm("arg2", S("subtract", pc("arg1", "numDrawers"), pc("arg2", "loopIndex"))))))))}}),
        act("updateScore", {"computed": {"scores": S("createItemList",
            pp("length", 1),
            pm("item", S("createDict",
                pp("keys", ["list", "delta"]),
                pm("values", S("createList",
                    pm("arg1", S("createList", pc("arg1", "rDrawer"))),
                    pp("arg2", 2))))))}}),
        # celebrate the guesser + the drawer whose picture cracked it
        act("emptyAction", {"preset": {"sounds.list": ["soundboard.success"]},
             "cached": {"playList.0": "players"}}),
        act("animateBox", {"preset": {"animation": "celebrate"},
             "computed": {"userIds": S("createList", pc("arg1", "currentGuesser"), pc("arg2", "rDrawer"))}}),
    ]),
    # deal the just-shown card into the guesser's hand (reference for next reveal)
    grp("Give card to guesser", actions=[
        act("dealDeck", {"preset": {"deck": "hand_pile", "qnt": 1, "sortBy": "weight", "order": "asc"},
             "computed": {"targets": S("createList", pc("arg1", "currentGuesser"))}}),
    ]),
    # loop control: stop when solved OR this was the last drawing
    grp("Loop control", actions=[
        act("emptyAction",
            skip=[S("logicalAND",
                pm("arg1", NOT("solved")),
                pm("arg2", S("lessThan", pc("arg1", "loopIndex"), pm("arg2", S("dec", pc("arg", "numDrawers"))))))],
            save=[svc("isActionLoop", False)]),
    ]),
]
loop.append(reveal_loop)

# --- End guessing: drop the guesser spotlight ---
loop.append(grp("End guessing", actions=[act("removeAllHighlights")]))

# --- End of round: show all drawings (one per deck, 2-row grid), final judge, reveal ---
loop.append(grp("Show all drawings", actions=[
    # only the decks that actually got a drawing this round (numDrawers of the MAX_DRAWERS)
    act("emptyAction", save=[
        svc("shownDecks", S("sublist", pc("list", "drawDecks"), pp("start", 0), pc("end", "numDrawers"))),
    ]),
    # neutral vertical layout so all cameras sit around the board
    act("changeLayout", {"preset": {"type": "HIGHLIGHT", "direction": "VERTICAL", "percent": 50}}),
    act("createGenericCardWidget", {
        "preset": {"ratio": "0.77", "backgroundImage": WOOD},
        "cached": {"decks": "shownDecks"},
        "computed": {
            "dimensions": objget("gridDims", "numDrawers", default=[2, 4]),
        }
    }),
]))
# final all-at-once guess judged by the host (neutral) — only if not yet solved
loop.append(grp("Final guess", skipCondition=[getc("solved")], actions=[
    act("createVote", {
        "preset": {"type": "target_poll", "terminationCondition": "get_all_votes",
                   "showResultInRealTime": True, "showResultDuration": 1, "showResultDelay": 0,
                   "oneClick": True, "allowRevoting": True, "vertical": True},
        "cached": {"actors": "host", "title": "finalBoardHeader",
                   "targets": "judgeTargets", "pollVoteTargetsOptions": "judgeOptions"},
        "computed": {
            "duration": S("ifElse",
                pm("condition", S("contains", pm("list", S("allConnectedUsers")), pc("element", "host.0"))),
                pp("thenValue", 25), pp("elseValue", 1)),
            "question": S("formatString", pc("format", "finalJudgeQuestion"),
                          pm("arg1", S("getPlayerNameById", pc("id", "currentGuesser")))),
        }
    }, save=[
        svc("solved", S("isTargetGotMajority", pc("voteResult", "lastActionResult"), pc("target", "judgeTargets.0"))),
    ]),
    # award 1 point to guesser if they finally got it
    act("updateScore",
        skip=[NOT("solved")],
        payload={"computed": {"scores": S("createItemList",
            pp("length", 1),
            pm("item", S("createDict",
                pp("keys", ["list", "delta"]),
                pm("values", S("createList",
                    pm("arg1", S("createList", pc("arg1", "currentGuesser"))),
                    pp("arg2", 1))))))}}),
]))
# reveal the word + who scored
loop.append(grp("Reveal word", actions=[
    act("createNotification", {
        "preset": {"duration": 7, "image": "banner"},
        "cached": {"to": "players"},
        "computed": {
            "to": S("allPlayers"),
            "header": S("ifElse", pc("condition", "solved"),
                       pc("thenValue", "guesserGotItHeader"), pc("elseValue", "nobodyGotItHeader")),
            "text": S("ifElse", pc("condition", "solved"),
                pm("thenValue", S("formatString", pc("format", "guesserGotItText"),
                                  pm("arg1", S("getPlayerNameById", pc("id", "currentGuesser"))),
                                  pc("arg2", "currentPrompt"))),
                pm("elseValue", S("formatString", pc("format", "nobodyGotItText"), pc("arg1", "currentPrompt")))),
        }
    }),
]))
# review: untimed — the host studies the grid and clicks any drawing to advance
loop.append(grp("Review", actions=[
    act("selectCentralWidgetDeck", {
        "cached": {"actors": "host", "decks": "shownDecks"},
        "computed": {
            "question": S("formatString", pc("format", "reviewSelect"),
                          pc("arg1", "currentPrompt"),
                          pm("arg2", S("getPlayerNameById", pc("id", "host.0")))),
            "defaultSelect": S("randomElement", pc("list", "shownDecks")),
        }
    }),
]))
# clear the widget + decks for next round; set winner var; cache currentMinScore for
# any spectator who joins next round (getMinCurrentScore inside the transition would
# count the joiner's default 0 — see Emeralds).
loop.append(grp("Clean up", actions=[
    act("removeWidget", {"preset": {"id": "GenericCardWidget"}}),
    # guesser's reference hand -> trash; leftover undealt hand cards -> trash
    act("recallCards", {"preset": {"deck": "trash"}, "cached": {"targets": "currentGuesser"}}),
    act("moveCards", {"preset": {"from": "hand_pile", "type": "deck", "to": "trash"}}),
    act("emptyAction", save=[
        svc("round", S("inc", pc("arg", "round"))),
        svc("currentMinScore", S("getMinCurrentScore")),
        svc("winner", S("listToString", pm("list", S("getPlayerNamesByIds",
            pm("ids", S("getPlayersWithMaxScore")))))),
    ]),
]))
# empty each per-drawing display deck -> trash (they're reused next round)
loop.append(grp("Clear draw decks",
    repeat={"qnt": getc("numDrawers")},
    actions=[
        act("moveCards", {"preset": {"type": "deck", "to": "trash"},
             "computed": {"from": S("formatString", pp("format", "draw_($1)"), pc("arg1", "repeatIndex"))}}),
    ]))

# --- Play again (every full rotation: when (round-1) % numPlayers == 0) ---
loop.append(grp("Play again",
    skipCondition=[NOT(S("equals",
        pm("arg1", S("remainder", pm("arg1", S("dec", pc("arg", "round"))), pc("arg2", "numPlayers"))),
        pp("arg2", 0)))],
    actions=[
        act("createVote", {
            "preset": {
                "title": "PLAY AGAIN?", "type": "target_poll", "terminationCondition": "get_majority",
                "showResultInRealTime": True, "showResultDuration": 1, "showResultDelay": 0,
                "targets": ["Reset scores", "Keep scores", "I'M SO DONE"],
                "pollVoteTargetsOptions": strings_default["playAgainOptions"],
                "duration": 120, "question": "Would you like to play another round?",
                "allowRevoting": True, "backgroundColor": BG, "borderColor": BORDER, "textColor": TEXT,
            },
            "cached": {"actors": "host"},
        }, save=[
            svc("playAgain", S("logicalNOT", pm("arg", S("isTargetGotMajority",
                pc("voteResult", "lastActionResult"), pp("target", "I'M SO DONE"))))),
            svc("reset", S("isTargetGotMajority",
                pc("voteResult", "lastActionResult"), pp("target", "Reset scores"))),
        ]),
    ]))
# reset scores if requested
loop.append(grp("Reset scores", skipCondition=[NOT("reset")], actions=[
    act("updateScore", {"computed": {"scores": S("createItemList",
        pp("length", 1),
        pm("item", S("createDict",
            pp("keys", ["list", "score"]),
            pm("values", S("createList",
                pc("arg1", "players"),
                pp("arg2", 0))))))}}),
]))
# safe point for player <-> spectator transitions (end of round)
loop.append(grp("Change players", turnPlayersToSpectators=True, turnSpectatorsToPlayers=True, actions=[]))
# win check
loop.append(grp("Check win", checkWinCondition=True, actions=[]))

# ============================================================
# 3b. spectator <-> player transitions
# ============================================================
turn_player_to_spectator = [
    act("emptyAction", save=[
        svc("players", S("allPlayers")),
        svc("numPlayers", LEN("players")),
        svc("numDrawers", S("dec", pc("arg", "numPlayers"))),
    ]),
    act("changeLayout", {"preset": {"type": "HIGHLIGHT", "direction": "VERTICAL", "percent": 50}}),
]
turn_spectator_to_player = [
    act("emptyAction", save=[
        svc("newPlayer", getc("waitingSpectator")),
        svc("players", S("allPlayers")),
        svc("numPlayers", LEN("players")),
        svc("numDrawers", S("dec", pc("arg", "numPlayers"))),
    ]),
    act("setRole", {"preset": {"roleId": "player"}, "cached": {"playerId": "newPlayer"}}),
    # start the late joiner at the current lowest score (not 0)
    act("updateScore", {"computed": {"scores": S("createItemList",
        pp("length", 1),
        pm("item", S("createDict",
            pp("keys", ["list", "score"]),
            pm("values", S("createList",
                pm("arg1", S("createList", pc("arg1", "newPlayer"))),
                pc("arg2", "currentMinScore"))))))}}),
    act("showScore", {"preset": {"order": "highest"}, "cached": {"from": "players", "to": "players"}}),
    act("changeLayout", {"preset": {"type": "HIGHLIGHT", "direction": "VERTICAL", "percent": 50}}),
]

# ============================================================
# 4. playersWinCondition + postGameActions (emeralds verbatim)
# ============================================================
players_win = {
    "gameOverCondition": S("logicalNOT", pc("arg", "playAgain")),
    "winners": S("getPlayerNamesByIds", pm("ids", S("getPlayersWithMaxScore"))),
}

post = [
    {"key": "hideAllPlayersHands"},
    {"key": "createNotification", "payload": {
        "preset": {"image": "winner", "backgroundColor": BG, "borderColor": BORDER},
        "cached": {"to": "players"},
        "computed": {"header": S("formatString", pp("format", "($1) ($2)!"),
            pc("arg1", "winner"),
            pm("arg2", S("ifElse",
                pm("condition", S("equals",
                    pm("arg1", S("listLength", pm("list", S("getPlayersWithMaxScore")))),
                    pp("arg2", 1))),
                pp("thenValue", "wins"), pp("elseValue", "share the win"))))}}},
]

# ============================================================
# assemble
# ============================================================
game = {
    "gameInitOptions": gio,
    "visualSettings": {"backgroundColor": BG, "borderColor": BORDER, "textColor": TEXT,
                        "increaseHandHeight": True},
    "turnPlayerToSpectatorActions": turn_player_to_spectator,
    "turnSpectatorToPlayerActions": turn_spectator_to_player,
    "beforeLoopActions": before,
    "gameLoop": loop,
    "playersWinCondition": players_win,
    "postGameActions": post,
}

with open(OUT, "w") as f:
    json.dump(game, f, indent=2, ensure_ascii=False)
print("wrote", OUT)
print("prompts:", len(PROMPTS), "| gameLoop groups:", len(loop))
