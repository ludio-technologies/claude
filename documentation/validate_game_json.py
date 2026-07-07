#!/usr/bin/env python3
"""
Ludio game JSON validator.
Usage:  python3 validate_game_json.py path/to/game.json
        python3 validate_game_json.py path/to/game.json --strict   # also warn on optional-param mismatches
"""

import json, sys, os
from typing import Any, Dict, List, Tuple, Optional

# ─── Selector registry ────────────────────────────────────────────────────────
# Keys per entry:
#   "zero"           → no params expected at all
#   "params"         → required param names (exact match enforced)
#   "optional"       → param names that are valid but not required
#   "variadic"       → any param names are OK (e.g. add, logicalAND, createList)
#   "variadic_extra" → "params" are required; anything else is also allowed (e.g. formatString)
#   "zero_or_optional" → may be called with zero params OR with the listed optional params

SELECTORS: Dict[str, dict] = {
    # ── Math ──────────────────────────────────────────────────────────────────
    "add":                  {"variadic": True},
    "multiply":             {"variadic": True},
    "integerDivide":        {"params": ["arg1", "arg2"]},
    "divide":               {"params": ["arg1", "arg2"]},
    "remainder":            {"params": ["arg1", "arg2"]},
    "subtract":             {"params": ["arg1", "arg2"]},
    "floor":                {"params": ["arg"]},
    "inc":                  {"params": ["arg"]},
    "dec":                  {"params": ["arg"]},
    "abs":                  {"params": ["arg"]},
    "round":                {"params": ["arg"]},
    "negate":               {"params": ["arg"]},

    # ── Logical ───────────────────────────────────────────────────────────────
    "logicalOR":            {"variadic": True},
    "logicalAND":           {"variadic": True},
    "logicalNOT":           {"params": ["arg"]},

    # ── Comparisons ───────────────────────────────────────────────────────────
    "greaterThan":          {"params": ["arg1", "arg2"]},
    "greaterThanOrEqual":   {"params": ["arg1", "arg2"]},
    "lessThan":             {"params": ["arg1", "arg2"]},
    "lessThanOrEqual":      {"params": ["arg1", "arg2"]},
    "equals":               {"params": ["arg1", "arg2"]},
    "notEqual":             {"params": ["arg1", "arg2"]},

    # ── List ──────────────────────────────────────────────────────────────────
    "listLength":           {"params": ["list"]},
    "concat":               {"variadic": True},
    "append":               {"params": ["list", "element"]},
    "intersect":            {"params": ["list1", "list2"]},
    "listsSubtract":        {"params": ["list1", "list2"]},
    "trueSubtract":         {"params": ["list1", "list2"]},
    "contains":             {"params": ["list", "element"]},
    "indexOf":              {"params": ["list", "element"]},
    "shuffleList":          {"params": ["list"]},
    "selectElement":        {"params": ["list", "index"]},
    "removeElement":        {"params": ["list", "index"]},
    "sublist":              {"params": ["list"], "optional": ["start", "end"]},
    "listByDictionary":     {"params": ["list", "dict"]},
    "createList":           {"variadic": True},
    "maxIndex":             {"params": ["list"]},
    "minIndex":             {"params": ["list"]},
    "createItemList":       {"params": ["length", "item"]},
    "unique":               {"params": ["list"]},
    "minValue":             {"params": ["list"]},
    "maxValue":             {"params": ["list"]},
    "sumAllElementsList":   {"params": ["list"]},
    "reverseList":          {"params": ["list"]},

    # ── Random ────────────────────────────────────────────────────────────────
    "randomNumber":         {"params": ["max"], "optional": ["min"]},
    "randomElement":        {"params": ["list"]},
    "randomElementsList":   {"params": ["list", "length"]},

    # ── String ────────────────────────────────────────────────────────────────
    # formatString: "format" is required; arg1, arg2, … can have any names
    "formatString":         {"params": ["format"], "variadic_extra": True},
    "listToString":         {"params": ["list"], "optional": ["readable", "delimiter"]},
    "toLowerCase":          {"params": ["text"]},
    "toUpperCase":          {"params": ["text"]},
    "stringLength":         {"params": ["text"]},
    "substring":            {"params": ["text", "start", "end"]},
    "stringToList":         {"params": ["text"]},
    "stringToInt":          {"params": ["text"]},
    "isRealEnglishWord":    {"params": ["text"]},

    # ── Conditional ───────────────────────────────────────────────────────────
    "ifElse":               {"params": ["condition", "thenValue", "elseValue"]},

    # ── Object ────────────────────────────────────────────────────────────────
    "getObjectField":       {"params": ["obj", "field"], "optional": ["defaultValue"]},
    "getObjectFieldList":   {"params": ["obj", "field"], "optional": ["defaultValue"]},
    "getObjectKeys":        {"params": ["obj"]},
    "getObjectValues":      {"params": ["obj"]},
    "createDict":           {"params": ["keys", "values"]},

    # ── Other ─────────────────────────────────────────────────────────────────
    "polynomial":           {"params": ["value", "coefficients"]},

    # ── Common state ──────────────────────────────────────────────────────────
    "allPlayers":           {"zero": True},
    "allPlayersByOrder":    {"zero": True},
    "allConnectedUsers":    {"zero": True},
    "allSpectators":        {"zero": True},
    "allRobotPlayers":      {"zero": True},
    "getPlayerNameById":    {"params": ["id"]},

    # ── Skip-condition special selectors ──────────────────────────────────────
    "isPrevActionGroupSkipped": {"zero": True},
    "isPrevActionGroupDone":    {"zero": True},
    "isPrevActionSkipped":      {"zero": True},
    "isPrevActionDone":         {"zero": True},

    # ── Votes module ──────────────────────────────────────────────────────────
    "isTargetGotMajority":  {"params": ["voteResult", "target"]},
    "getVotersByAnswer":    {"params": ["voteResult", "answer"]},
    "getPlayerVoice":       {"params": ["voteResult", "playerId"]},

    # ── Teams & Roles ─────────────────────────────────────────────────────────
    "getTeamNameByPlayerId":    {"params": ["playerId"]},
    "getRoleNameByPlayerId":    {"params": ["playerId"]},
    "getPlayersFromTeam":       {"params": ["teamId"]},
    "getRoleName":              {"params": ["roleId"]},
    "getPlayersByRole":         {"params": ["role"]},
    "getPlayerByRole":          {"params": ["role"]},
    "getPlayersRoles":          {"params": ["players"]},
    "getPlayersTeams":          {"params": ["players"]},
    "getCardNames":             {"optional": ["ids"], "zero_or_optional": True},
    "getAllRolesIdsExpandedByFrequency": {"zero": True},
    "getTrueRoles":             {"zero": True},
    "switchTrueRoles":          {"params": ["trueRoles", "from", "to"]},
    "isTrueRoleInGame":         {"params": ["trueRoles", "role"]},
    "getNonEmptyTeamsIds":      {"zero": True},
    "getFewestPlayersTeam":     {"zero": True},
    "getMostPlayersTeam":       {"zero": True},

    # ── Player Score module ───────────────────────────────────────────────────
    "getPlayersByScore":        {"optional": ["min", "max"], "zero_or_optional": True},
    "getPlayerScore":           {"params": ["playerId"]},
    "getPlayersWithMinScore":   {"optional": ["players"], "zero_or_optional": True},
    "getPlayersWithMaxScore":   {"optional": ["players"], "zero_or_optional": True},
    "getMaxCurrentScore":       {"zero": True},
    "getMinCurrentScore":       {"zero": True},

    # ── Dead Player module ────────────────────────────────────────────────────
    "allLivePlayers":           {"zero": True},
    "getAllPlayersExcept":       {"params": ["players"], "optional": ["additionalPlayers"]},

    # ── Cards module ──────────────────────────────────────────────────────────
    "fetchHandField":           {"params": ["playerId", "field"]},
    "getCardField":             {"params": ["cardId", "field"]},
    "fetchDeckField":           {"params": ["deck", "field"]},
    "getCardsIdsByType":        {"params": ["type"]},
    "getPlayerByCardName":      {"params": ["name"]},
    "getTrickWinner":           {"zero": True},
    "getCardsScore":            {"optional": ["deck", "hand"], "zero_or_optional": True},
    "playerHand":               {"params": ["playerId"]},
    "getDeckCards":             {"params": ["deck"]},
    "getDeckLabel":             {"params": ["deck"]},
    "getHandCardsIdsByName":    {"params": ["playerId", "name"]},
    "getFugitivePlayableCards": {"params": ["playerId", "highestCard"], "optional": ["isFirstTurn"]},
    "getNoThanksCardsScore":    {"optional": ["deck", "hand"], "zero_or_optional": True},
    "getLlamaPartyCardsScore":  {"params": ["hand"]},

    # ── Grids module ──────────────────────────────────────────────────────────
    "getCodenamesWinner":       {"zero": True},

    # ── Cache selectors ───────────────────────────────────────────────────────
    "isCachedObjectContainsField":  {"params": ["objectName", "fieldName"]},
    "selectRandomPuzzgridId":       {"zero": True},
    "getCachedValue":               {"params": ["name"]},
    "getCachedObjectValue":         {"params": ["objectName", "value"], "optional": ["defaultValue"]},
    "setCachedObjectFieldValue":    {"params": ["objectName", "fieldName", "value"]},
    "setCachedObjectFieldsValues":  {"params": ["objectName", "fieldsNames", "values"]},
    "incObjectFieldValue":          {"params": ["objectName", "ids"]},
    "decObjectFieldValue":          {"params": ["objectName", "ids"]},
    "getHostPlayerId":              {"zero": True},
    "allHumanPlayers":              {"zero": True},
    "allUsers":                     {"zero": True},
    "getObjectKeysWithPositiveValue": {"params": ["data"]},
    "getPlayerNamesByIds":          {"params": ["ids"]},
    "getRemainingTimer":            {"params": ["timerId"]},
    "nextPlayer":                   {"params": ["playersList", "playerId"]},
    "prevPlayer":                   {"params": ["playersList", "playerId"]},

    # ── Mafia-specific ────────────────────────────────────────────────────────
    "livePlayersFromTeam":          {"params": ["teamId"]},
    "isAllTeamAlive":               {"params": ["teamName"]},
    "isNotRoleInGame":              {"params": ["role"]},
    "isVigilanteSkip":              {"params": ["prevChoice"]},
    "questFailsNumber":             {"params": ["voteResult", "playerId"]},
    "prepareVigilanteChoiceAnnounce":   {"params": ["ids"]},
    "prepareParityCopChoiceAnnounce":   {"params": ["currentChoice"], "optional": ["prevChoice"]},
    "prepareAccuserNotification":       {"params": ["accuser", "nominee"]},
    "prepareDeathVoteQuestion":         {"params": ["player"]},
    "prepareDeathVoteResultAnnounce":   {"params": ["player", "voteId"]},
    "prepareWerewolvesRevealAnnounce":  {"zero": True},
    "prepareSeerChoiceAnnounce":        {"params": ["ids"]},
    "prepareEndGameAnnounce":           {"params": ["ids", "trueRoles"]},
    "isWerewolvesWin":                  {"params": ["ids", "trueRoles"]},
    "isTannerWins":                     {"params": ["ids", "trueRoles"]},
    "isVillagersWins":                  {"params": ["ids", "trueRoles"]},

    # ── Galaxy Brain game-specific ────────────────────────────────────────────
    "getGalaxyBrainThinkerRoundScore":  {"params": ["thinker", "judgeChoices", "thinkersChoices"]},
    "getGalaxyBrainJudgeRoundScore":    {"params": ["judgeChoices", "thinkersChoices"]},
}

# ─── Action registry ─────────────────────────────────────────────────────────
# "required": fields that MUST appear somewhere in preset/cached/computed
# "one_of":   lists of fields where at least one from each list must be present

ACTIONS: Dict[str, dict] = {
    # ── Core ──────────────────────────────────────────────────────────────────
    "emptyAction":              {"required": []},
    "createNotification":       {"required": ["to"], "one_of": [["text", "header"]]},
    "createConfirmation":       {"required": ["actors", "text", "passCriterion"]},
    "highlightPlayers":         {"required": ["listOfPlayers", "color"]},
    "removeHighlight":          {"required": ["id"]},
    "removeAllHighlights":      {"required": []},
    "mutePlayers":              {"required": ["players"]},
    "unmutePlayers":            {"required": ["players"]},
    "restoreMuteStatus":        {"required": []},
    "changeLayout":             {"required": ["type"]},
    "setImagesRow":             {"required": ["images"]},
    "changeImageInRow":         {"required": ["index", "image"]},
    "changeBackground":         {"required": ["image"]},
    "createConversationGroup":  {"required": ["members", "indicator"]},
    "destroyConversationGroup": {"required": ["id"]},
    "destroyConversationGroups":{"required": []},
    "createPuzzgrid":           {"required": ["actors"]},
    "animateBox":               {"required": ["userIds", "animation"]},
    "removeWidget":             {"required": ["id"]},
    "restoreWidget":            {"required": ["id"]},
    "createMessage":            {"required": ["text", "sender"]},
    "createInput":              {"required": ["title", "type", "question", "terminationCondition", "scope", "actors"]},
    # teamsAndRoles module — see Ludio engine docs (1WUwKK6gqSOB_Rl1GNJs84aRtjwbImTVPUuA8L1-S_wA).
    # NOTE: there is NO `hideFakeRole` action. Use `hideRole` to un-show whatever
    # role (real OR fake) was previously shown to `to:` players for `from:` players.
    "showTeam":                 {"required": ["from", "to"]},
    "showRole":                 {"required": ["from", "to"]},
    "showFakeTeam":             {"required": ["from", "to", "teamId"]},
    "showTrueRoles":            {"required": ["from", "trueRoles"]},
    "showFakeRole":             {"required": ["from", "to", "roleId"]},
    "hideRole":                 {"required": ["from", "to"]},
    "showAllPlayersHands":      {"required": []},
    "hideAllPlayersHands":      {"required": []},
    "showPlayersHands":         {"required": ["userIds"]},
    "hidePlayersHands":         {"required": ["userIds"]},
    "hideInvisiblePlayers":     {"required": ["hide"]},
    "createTeamsConversationGroups": {"required": []},
    "muteTeam":                 {"required": ["team"]},
    "setRole":                  {"required": ["roleId", "playerId"]},
    "orderByTeam":              {"required": []},
    "drawArrows":               {"required": ["arrows"]},
    "setGameEndSound":          {"required": ["sound"]},
    "roleConfirmation":         {"required": []},
    "createMissionHistory":     {"required": ["type", "title", "players"]},
    "updateMissionHistory":     {"required": []},
    "createAdvertisement":      {"required": ["header", "text"]},
    "createDrawing":            {"required": ["actors", "question", "terminationCondition"]},
    "startClip":                {"required": ["title"]},
    "endClip":                  {"required": []},
    "takeWidgetScreenshot":     {"required": ["title"]},
    "createOneWordClue":        {"required": ["actor", "duration", "restrictedWords"]},

    # ── Votes module ──────────────────────────────────────────────────────────
    "createVote":       {"required": ["title", "type", "question", "terminationCondition", "actors", "showResultInRealTime"]},
    "createMixVote":    {"required": ["title", "question", "terminationCondition", "actors",
                                      "showResultInRealTime", "point.targets", "poll.targets"]},
    "getTriviaQuestions": {"required": ["qnt"]},

    # ── Score module ──────────────────────────────────────────────────────────
    "showScore":        {"required": ["from", "to"]},
    "updateScore":      {"required": ["scores"]},
    "removeScore":      {"required": []},
    "orderByScore":     {"required": []},

    # ── Dead Player module ────────────────────────────────────────────────────
    "killPlayer":       {"required": ["userId"]},
    "killPlayers":      {"required": ["users"]},
    "makeAllPlayersAlive": {"required": []},
    "createIndividualConversationGroups": {"required": []},

    # ── Cards module ──────────────────────────────────────────────────────────
    "createDeck":               {"required": ["name", "set"]},
    "createPublicDeck":         {"required": ["type"]},
    "createPlayersDecks":       {"required": ["players"]},
    "createCustomDeck":         {"required": ["name"]},  # public:true enforced by _check_custom_deck_public
    "shuffleDeck":              {"required": ["deck"]},
    "dealDeck":                 {"required": ["targets", "deck"]},
    "playCards":                {"required": ["actor", "target", "notification"]},
    "moveCards":                {"required": ["type", "from", "to"]},
    "recallCards":              {"required": ["targets", "deck"]},
    "discard":                  {"required": ["targets", "deck", "cards"]},
    "sortDeck":                 {"required": ["deck", "sortBy"]},
    "showHand":                 {"required": ["from", "to"]},
    "createGenericCardWidget":  {"required": ["dimensions", "decks"]},
    "createVideoboxDecks":      {"required": ["players"]},
    "selectCentralWidgetDeck":  {"required": ["actors"]},
    "flipOverTopCard":          {"required": ["deck"]},
    "createCard":               {"required": ["deck"]},
    "createTextCards":          {"required": ["deck", "cardText"]},
    "setDeckInspectors":        {"required": ["deck", "inspectors"]},
    "setInspectDeck":           {"required": ["deck", "inspectDeck"]},
    "setDeckLabels":            {"required": ["decks", "labels"]},
    "setDeckLabel":             {"required": ["deck", "label"]},
    "highlightDecks":           {"required": ["decks", "color"]},
    "removeHighlightDecks":     {"required": ["decks"]},
    "removeAllHighlightDecks":  {"required": []},
    "takeFivePlaceCards":       {"required": []},
    "noThanksPlaceCards":       {"required": []},
    "setCardsPile":             {"required": ["name"]},
    "setLabelInspectors":       {"required": []},

    # ── Mafia application ─────────────────────────────────────────────────────
    "setDay":   {"required": []},
    "setNight": {"required": []},
}

VALID_PARAM_TYPES = {"preset", "cached", "computed"}

# Selectors whose result is a list (used by the cache-type pre-pass and the
# list-expecting-field check).
_LIST_RETURNING_SELECTORS = {
    "createList", "append", "listsSubtract", "intersect", "shuffleList",
    "getDeckCards", "allPlayers", "getPlayersFromTeam", "getPlayerNamesByIds",
    "sublist", "concat", "randomElementsList", "getObjectValues", "getObjectKeys",
    "createDict",
}

# Selectors whose result is a single scalar value (string/number/boolean/card).
_SCALAR_RETURNING_SELECTORS = {
    "selectElement", "getCardField", "getObjectField", "getHostPlayerId",
    "getPlayerNameById", "listLength", "minValue", "maxValue", "abs",
    "add", "subtract", "multiply", "integerDivide", "inc", "dec",
    "randomNumber", "randomElement", "indexOf", "formatString",
    "equals", "notEquals", "lessThan", "lessThanOrEqual", "greaterThan",
    "greaterThanOrEqual", "logicalAND", "logicalOR", "logicalNOT", "contains",
}

# Ludio variables always available in cache without explicit saveValueInCache
BUILTIN_CACHE_VARS = {
    "gameLoopIndex",     # current game-loop iteration index (0-based)
    "lastActionResult",  # result object from the previous action (.voteResult, .selectedDecks, etc.)
    "repeatIndex",       # current index inside a repeat{} block
    "spaIndex",          # current index inside a parallel{} block (smart type)
    "loopIndex",         # current index inside a square-brackets [] sub-loop in gameLoop
    "oldPlayer",          # injected in turnPlayerToSpectatorActions (the departing player)
    "waitingSpectator",   # injected in turnSpectatorToPlayerActions (the arriving spectator)
                          # games often immediately rename it: saveValueInCache [{name:"newPlayer",...}]
    "lastActionId",       # ID of the last action executed (engine-provided)
    # NOTE: "winner" is NOT a global built-in. It is set by the win-condition mechanism
    # (the winning key name from winCondition, or the winners list from playersWinCondition)
    # and is only accessible inside postGameActions. It is handled specially in _check_cached_ref.
}

# Keys excluded when comparing actions against the emeralds.json reference template
COSMETIC_KEYS = {"backgroundColor", "borderColor", "textColor"}

# Free engine variables that must never appear as the target name of saveValueInCache.
# isActionLoop is excluded: setting it to false to break a loop IS a valid use.
FREE_VARS_NO_SAVE = {
    "repeatIndex", "spaIndex", "gameLoopIndex", "loopIndex",
    "oldPlayer", "waitingSpectator", "lastActionResult", "lastActionId",
}

# Canonical key ordering for action groups, actions, and the payload sub-object.
# Any keys not listed are ignored by the order check — only the relative ordering
# of LISTED keys is enforced (so 'nextGroupNonStop' on a group, for example, is
# allowed anywhere). Many older games predate this convention and will warn; we
# only fix these as we touch the files.
GROUP_FIELD_ORDER = [
    "name", "turnPlayersToSpectators", "turnSpectatorsToPlayers",
    "skipCondition", "repeat", "parallel", "checkWinCondition", "actions",
]
ACTION_FIELD_ORDER = ["key", "skipCondition", "payload", "postHandler", "saveValueInCache"]
PAYLOAD_SECTION_ORDER = ["preset", "cached", "computed"]

# Canonical value for any saveValueInCache entry named "host".
# The logic: if getHostPlayerId() is in the active players list, use them;
# otherwise fall back to players[0] (handles host-is-spectator edge case).
HOST_CACHE_VALUE = {
    "selector": "ifElse",
    "params": [
        {
            "name": "condition",
            "type": "computed",
            "value": {
                "selector": "contains",
                "params": [
                    {"name": "list",    "type": "cached",   "value": "players"},
                    {"name": "element", "type": "computed", "value": {"selector": "getHostPlayerId"}}
                ]
            }
        },
        {
            "name": "thenValue",
            "type": "computed",
            "value": {
                "selector": "createList",
                "params": [
                    {"name": "arg1", "type": "computed", "value": {"selector": "getHostPlayerId"}}
                ]
            }
        },
        {
            "name": "elseValue",
            "type": "computed",
            "value": {
                "selector": "createList",
                "params": [
                    {
                        "name": "arg1",
                        "type": "cached",
                        "value": "players.0"
                    }
                ]
            }
        }
    ]
}

# emeralds.json is used as the reference template for standard patterns
_EMERALDS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'game_jsons', 'emeralds.json')


# ─── Validator ────────────────────────────────────────────────────────────────

class Validator:
    _emeralds_cache: Optional[dict] = None  # shared singleton across instances

    def __init__(self, data: Any):
        self.data = data
        self.errors:   List[Tuple[str, str]] = []
        self.warnings: List[Tuple[str, str]] = []
        self.cache_vars: set = set()

    def err(self, path: str, msg: str):
        self.errors.append((path, msg))

    def warn(self, path: str, msg: str):
        self.warnings.append((path, msg))

    def run(self) -> tuple:
        # If this looks like a cards JSON (script.name + cards array, no game loop),
        # run the cards-JSON checks instead of the game-JSON walk.
        if self._is_cards_json():
            self._check_cards_json()
            return self.errors, self.warnings

        # Pre-pass: collect every variable name ever written to cache so we can
        # validate cached references in the main walk.
        self.cache_vars = self._collect_cache_names(self.data) | BUILTIN_CACHE_VARS
        # Also treat names the engine loads into cache from gameInitOptions
        # BEFORE the game loop runs as valid cached references: configVariables
        # (host config step) and strings variants (the chosen variant's variables
        # are written to cache at game start). These never appear in a
        # saveValueInCache entry but are legitimate cached references.
        init_names, init_types = self._collect_gameinit_cache_names()
        self.cache_vars |= init_names
        # Pre-pass: classify each cache name as 'list' / 'scalar' / 'unknown'
        # by inspecting the right-hand side of each saveValueInCache entry.
        self.cache_types: dict = {}
        self._collect_cache_types(self.data, self.cache_types)
        for name, shape in init_types.items():
            if name in self.cache_types and self.cache_types[name] != shape:
                self.cache_types[name] = "unknown"
            else:
                self.cache_types.setdefault(name, shape)
        self._walk(self.data, "")
        self._check_toplevel_patterns()
        return self.errors, self.warnings

    def _is_cards_json(self) -> bool:
        """A cards JSON has top-level 'name' (string) + 'cards' (list) and lacks game-level
        fields like 'gameInitOptions' or 'gameLoop'."""
        if not isinstance(self.data, dict):
            return False
        if "gameInitOptions" in self.data or "gameLoop" in self.data:
            return False
        return (isinstance(self.data.get("name"), str)
                and isinstance(self.data.get("cards"), list))

    def _check_cards_json(self):
        """Validate a cards JSON (the script you POST to /api/deck).

        Required:
          - 'name': string (matches the createDeck.name in the sibling game JSON)
          - 'cards': list of objects, each with name + label + image
          - Each card 'label' is a single-line string (no '\\n' — multi-line labels render
            with the literal escape sequence visible)
          - 'sets' (if present): each value MUST be a dict mapping card_name → positive int
            frequency, NOT a list. The Ludio engine reads sets as freq dicts; passing a
            list of names creates a deck with zero copies of each card.
        """
        d = self.data

        # Required top-level fields.
        if not isinstance(d.get("name"), str) or not d["name"]:
            self.err("name", "Cards JSON requires a non-empty top-level 'name' string "
                             "(this is the script.name the engine matches against createDeck.name).")
        cards = d.get("cards")
        if not isinstance(cards, list) or not cards:
            self.err("cards", "Cards JSON requires a non-empty top-level 'cards' list.")
            return

        # Per-card checks.
        seen_names = set()
        REQUIRED_FIELDS = ("name", "label", "image")
        for i, card in enumerate(cards):
            cpath = f"cards[{i}]"
            if not isinstance(card, dict):
                self.err(cpath, f"Each card must be an object; got {type(card).__name__}.")
                continue
            for f in REQUIRED_FIELDS:
                v = card.get(f)
                if not isinstance(v, str) or not v:
                    self.err(f"{cpath}.{f}",
                             f"Missing/empty required card field {f!r}. Every card needs "
                             f"a non-empty 'name', 'label', and 'image'.")
            label = card.get("label")
            if isinstance(label, str) and "\n" in label:
                self.err(f"{cpath}.label",
                         f"Card label contains a newline ({label!r}). Labels render as a "
                         f"single line in the card widget; embed multi-line content via "
                         f"HTML <br> tags in the card image or via the action that displays "
                         f"the card, not via '\\n' in the label.")
            name = card.get("name")
            if isinstance(name, str):
                if name in seen_names:
                    self.err(f"{cpath}.name",
                             f"Duplicate card name {name!r}. Each card 'name' must be unique "
                             f"within the cards array; the engine uses 'name' as the card ID.")
                seen_names.add(name)

        # Sets format check.
        sets = d.get("sets")
        if sets is not None:
            if not isinstance(sets, dict):
                self.err("sets", "Top-level 'sets' must be a dict mapping set name → frequency dict.")
            else:
                for set_name, set_val in sets.items():
                    spath = f"sets.{set_name}"
                    if isinstance(set_val, list):
                        self.err(spath,
                                 "Set value is a LIST of card names — this is the most common "
                                 "cards-JSON bug. Sets must be DICTS mapping card_name → integer "
                                 "frequency (e.g. {\"red_1\": 1, \"red_2\": 1}). The engine reads "
                                 "the frequency to decide how many copies of each card to put into "
                                 "the deck; a list silently produces zero copies. See "
                                 "roundabout_cards.json for the canonical shape.")
                        continue
                    if not isinstance(set_val, dict):
                        self.err(spath,
                                 f"Set value must be a dict (card_name → int frequency); got "
                                 f"{type(set_val).__name__}.")
                        continue
                    for card_name, freq in set_val.items():
                        if not isinstance(card_name, str):
                            self.err(spath, f"Set key {card_name!r} must be a string (card name).")
                        elif card_name not in seen_names:
                            self.err(spath, f"Set references unknown card {card_name!r}.")
                        if not isinstance(freq, int) or freq < 1:
                            self.err(f"{spath}.{card_name}",
                                     f"Frequency must be a positive integer; got {freq!r}.")

    # ── Emeralds reference helpers ────────────────────────────────────────────

    @classmethod
    def _get_emeralds(cls) -> Optional[dict]:
        """Load emeralds.json once and cache it. Returns None if unavailable."""
        if cls._emeralds_cache is not None:
            return cls._emeralds_cache if cls._emeralds_cache else None
        try:
            with open(_EMERALDS_PATH) as f:
                cls._emeralds_cache = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            cls._emeralds_cache = {}  # empty dict sentinel — avoids retrying
        return cls._emeralds_cache if cls._emeralds_cache else None

    @staticmethod
    def _strip_cosmetic(obj: Any) -> Any:
        """Remove COSMETIC_KEYS deeply so color differences don't affect comparisons."""
        if isinstance(obj, dict):
            return {k: Validator._strip_cosmetic(v) for k, v in obj.items() if k not in COSMETIC_KEYS}
        if isinstance(obj, list):
            return [Validator._strip_cosmetic(i) for i in obj]
        return obj

    @staticmethod
    def _strip_tutorial_hoistable(payload: Any) -> Any:
        """Normalize a tutorial createMixVote payload for reference comparison.

        On top of stripping cosmetic colors, this neutralizes the two pieces of
        user-facing copy that games are now allowed to hoist into
        gameInitOptions.strings (see the strings/variants feature): the widget
        `title` and the `question` formatString's `format` template. Whether a
        game keeps them inline (preset/computed literals) or references a cached
        strings var, both forms reduce to the same skeleton here — so the
        MECHANICS of the tutorial vote are still compared verbatim against
        emeralds while the copy is free to be themed per variant."""
        p = Validator._strip_cosmetic(payload)
        if not isinstance(p, dict):
            return p
        # 1. Drop `title` wherever it lives (preset when inline, cached when hoisted).
        for sect in ("preset", "cached", "computed"):
            if isinstance(p.get(sect), dict):
                p[sect].pop("title", None)
        # 2. Blank the question formatString's `format` param (its value AND type,
        #    since hoisting flips it from preset literal to cached reference).
        question = (p.get("computed") or {}).get("question")
        if isinstance(question, dict) and question.get("selector") == "formatString":
            for prm in question.get("params", []):
                if isinstance(prm, dict) and prm.get("name") == "format":
                    prm["type"] = "<hoistable>"
                    prm["value"] = "<hoistable>"
        return p

    @staticmethod
    def _refs_vote_result(obj: Any) -> bool:
        """Return True if obj contains any string starting with 'lastActionResult.voteResult'."""
        if isinstance(obj, str):
            return obj.startswith("lastActionResult.voteResult")
        if isinstance(obj, dict):
            return any(Validator._refs_vote_result(v) for v in obj.values())
        if isinstance(obj, list):
            return any(Validator._refs_vote_result(v) for v in obj)
        return False

    @staticmethod
    def _comparable_action(action: dict) -> dict:
        """Extract only payload + saveValueInCache for reference comparisons.
        Top-level fields like skipCondition can legitimately vary per game."""
        return {k: action[k] for k in ("payload", "saveValueInCache") if k in action}

    @staticmethod
    def _find_tutorial_vote_in(data: dict) -> Optional[dict]:
        """Find the tutorial createMixVote (saves learners + tutorial) in beforeLoopActions."""
        for action in data.get("beforeLoopActions", []):
            if not isinstance(action, dict) or action.get("key") != "createMixVote":
                continue
            svc_names = {e.get("name") for e in action.get("saveValueInCache", []) if isinstance(e, dict)}
            if "learners" in svc_names and "tutorial" in svc_names:
                return action
        return None

    @staticmethod
    def _find_end_of_round_vote_in(data: dict) -> Optional[dict]:
        """Find the end-of-round createVote (saves playAgain) anywhere in gameLoop."""
        def search(loop):
            for item in loop:
                if isinstance(item, dict):
                    for action in item.get("actions", []):
                        if not isinstance(action, dict) or action.get("key") != "createVote":
                            continue
                        svc_names = {e.get("name") for e in action.get("saveValueInCache", []) if isinstance(e, dict)}
                        if "playAgain" in svc_names:
                            return action
                elif isinstance(item, list):
                    result = search(item)
                    if result:
                        return result
            return None
        return search(data.get("gameLoop", []))

    @staticmethod
    def _skip_refs_tutorial(sc: Any) -> bool:
        """Return True if a skipCondition value references the 'tutorial' cache variable."""
        if isinstance(sc, str):
            return "tutorial" in sc
        if isinstance(sc, dict):
            v = sc.get("value")
            if isinstance(v, str) and v == "tutorial":
                return True
            return any(Validator._skip_refs_tutorial(x) for x in sc.values())
        if isinstance(sc, list):
            return any(Validator._skip_refs_tutorial(x) for x in sc)
        return False

    # ── Top-level structural pattern checks ──────────────────────────────────

    def _check_toplevel_patterns(self):
        self._check_timing_fields()
        self._check_roles()
        self._check_create_deck_pattern()
        self._check_card_game_setup()
        self._check_show_all_hands_decision()
        self._check_custom_deck_public()
        self._check_tutorial_pattern()
        self._check_tutorial_group()
        self._check_end_of_round_vote()
        self._check_post_game_notification()
        self._check_host_snippet()
        self._check_host_display()
        self._check_widget_visibility()
        self._check_increase_hand_height_pair()
        self._check_card_movement_targets()
        self._check_select_element_shorthand()
        self._check_get_card_field_scope()
        self._check_html_in_action_text()
        self._check_repeated_subexpressions()
        self._check_videobox_decks_initialized()
        self._check_check_win_condition()
        self._check_win_condition_defined()
        self._check_post_game_actions_required()
        self._check_winners_returns_names()
        self._check_save_value_in_cache_shape()
        self._check_no_nested_groups_in_repeat_parallel()
        self._check_cardback_resolves()
        self._check_move_cards_payload()
        self._check_asset_urls_resolve()
        self._check_spectator_transitions()
        self._check_contains_list_initialized()

    def _check_contains_list_initialized(self):
        """A cache var used as the `list` arg of a `contains(...)` selector must
        have at least one write that's GUARANTEED to run before the contains()
        evaluates. If every write is inside a skipCondition'd action, some
        runtime paths leave the var undefined, and the contains() will fail
        with 'contains list argument is not array'. Ludio's logicalAND does
        NOT short-circuit, so guarding the contains with a per-slot is-active
        check does NOT prevent evaluation.

        Heuristic: search beforeLoopActions for any action with no skipCondition
        that writes the var. If none exists, warn.

        The CnR per-turn label recompute hit this on 2026-05-20 — stashes_blue
        / stashes_green were only written inside skipCondition'd per-slot
        actions for inactive Robber slots, so in a 4-player game (numRobbers=1)
        they were undefined when label_stash_selector evaluated
        contains(stashes_blue, currentCell) every turn.
        """
        # 1. Every cache var read as `contains.list` (root only — drop any
        #    dotted-path or [i] suffix).
        contains_list_reads: dict = {}  # name → first-seen path

        def find_contains(node, path=""):
            if isinstance(node, dict):
                if node.get("selector") == "contains":
                    params = {p.get("name"): p for p in node.get("params", []) if isinstance(p, dict)}
                    lst = params.get("list") or {}
                    if lst.get("type") == "cached" and isinstance(lst.get("value"), str):
                        root = lst["value"].split(".")[0].split("[")[0]
                        contains_list_reads.setdefault(root, path or "(root)")
                for k, v in node.items():
                    find_contains(v, f"{path}.{k}" if path else k)
            elif isinstance(node, list):
                for i, v in enumerate(node):
                    find_contains(v, f"{path}[{i}]")
        find_contains(self.data)

        # 2. Every cache var written in beforeLoopActions by an action with
        #    NO skipCondition (i.e., guaranteed to run regardless of player
        #    count / role assignment).
        unconditional_writes: set = set()
        before = self.data.get("beforeLoopActions")
        if not isinstance(before, list):
            return
        for action in before:
            if not isinstance(action, dict):
                continue
            if action.get("skipCondition"):
                continue
            svc = action.get("saveValueInCache")
            if not isinstance(svc, list):
                continue
            for entry in svc:
                if isinstance(entry, dict) and isinstance(entry.get("name"), str):
                    unconditional_writes.add(entry["name"].split(".")[0])

        # 3. Warn for vars read by contains() that have no guaranteed write.
        for name, first_path in sorted(contains_list_reads.items()):
            if name in unconditional_writes:
                continue
            if name in BUILTIN_CACHE_VARS:
                continue
            if name not in self.cache_vars:
                continue  # unknown ref — flagged elsewhere
            self.warn(first_path,
                      f"cache var {name!r} is used as the list arg of a contains() "
                      f"selector but every write to it in beforeLoopActions is "
                      f"guarded by a skipCondition. If any path evaluates contains() "
                      f"before that conditional write fires, you'll hit runtime "
                      f"\"contains list argument is not array\". Add "
                      f"cache({name!r}, []) to your initial-cache block (or another "
                      f"unconditional action) so the var is always at least an "
                      f"empty list. (Ludio's logicalAND does not short-circuit, so "
                      f"guarding the contains with a per-slot 'is-active' check does "
                      f"NOT prevent it from firing for inactive slots.)")

    def _check_check_win_condition(self):
        """At least one gameLoop action group must carry 'checkWinCondition': true,
        otherwise the engine never evaluates winCondition and the game never ends.

        The flag is set at the stage (action-group) level, not on an individual
        action. Common patterns: an empty trailing stage with just
        {"actions": [], "checkWinCondition": true} (handshake.json, contour.json),
        or attaching the flag to the final stage that bumps the round counter
        (enigma.json). Both work — the engine checks the condition after the
        stage completes.
        """
        loop = self.data.get("gameLoop")
        if not isinstance(loop, list) or not loop:
            return
        has_check = any(isinstance(s, dict) and s.get("checkWinCondition") is True
                        for s in loop)
        if not has_check:
            self.err("gameLoop",
                     "No action group has 'checkWinCondition': true — the engine "
                     "never evaluates winCondition, so the game can never end. Add "
                     "a stage (typically the trailing win-check stage) with "
                     "\"checkWinCondition\": true at the stage level (alongside "
                     "'name'/'actions', NOT inside an action). See handshake.json "
                     "or enigma.json for the canonical pattern.")

    def _check_win_condition_defined(self):
        """Every game must define one of `winCondition` or `playersWinCondition` at
        the top level. Without one of these, the `checkWinCondition: true` flag on
        an action group has nothing to evaluate, so the engine never ends the game.
        Symptom in the wild: 'cannot convert undefined or null to object' thrown
        right after the play-again vote, because the engine tries to iterate the
        winners dict that was never populated.

        - `winCondition`: dict mapping team/role names to boolean selectors. Use
           this for team-based games (Mafia, Avalon, Codenames).
        - `playersWinCondition`: a selector that returns the winning player IDs.
           Use this for individual-score games (Hearts, Roundabout, Willpower).
           Canonical value: `{"selector": "getPlayersWithMaxScore"}` so the
           highest-score player(s) win when the host ends the game.
        """
        if not isinstance(self.data, dict):
            return
        if "gameInitOptions" not in self.data and "gameLoop" not in self.data:
            return  # Not a game JSON; skip (e.g. cards-only JSON).
        if "winCondition" in self.data or "playersWinCondition" in self.data:
            return
        self.err("(top-level)",
                 "Missing winCondition / playersWinCondition. Every game JSON must "
                 "define exactly one — without it, the engine has no condition to "
                 "evaluate when an action group's `checkWinCondition: true` fires "
                 "(symptom: 'cannot convert undefined or null to object' after the "
                 "play-again vote). Use `winCondition` (dict: team → selector) for "
                 "team-based games or `playersWinCondition` (selector returning the "
                 "winning player IDs) for individual-score games. Default for the "
                 "latter: {\"selector\": \"getPlayersWithMaxScore\"}.")

    def _check_asset_urls_resolve(self):
        """HEAD-check every asset URL in gameInitOptions.{images,animations,
        soundboard} to make sure it actually serves a real file.

        Catches the silent killers: typos in URLs, doubled path prefixes (e.g.
        accidentally concatenating `/image/upload` + `/video/upload/...`),
        forgotten uploads, expired/private files. These rarely show up before
        a playtest because the engine just plays nothing on a 404 and moves on.

        Asset shapes:
          - gameInitOptions.images.<key>.url  → string URL
          - gameInitOptions.animations.<key>  → string URL (lottie .json/.lottie)
          - gameInitOptions.soundboard.<channel>.<sound>  → string URL

        HTTP non-2xx is an error (real bug). Network failure / timeout is a
        warning (transient, don't block validation in offline envs).

        Set env var `LUDIO_VALIDATOR_SKIP_NETWORK=1` to skip this check entirely
        (CI/airgapped environments).
        """
        import os
        if os.environ.get("LUDIO_VALIDATOR_SKIP_NETWORK"):
            return

        init = self.data.get("gameInitOptions")
        if not isinstance(init, dict):
            return

        urls = []  # list of (url, validator_path)

        images = init.get("images") or {}
        if isinstance(images, dict):
            for k, v in images.items():
                if isinstance(v, dict) and isinstance(v.get("url"), str) and v["url"].startswith("http"):
                    urls.append((v["url"], f"gameInitOptions.images.{k}.url"))

        anims = init.get("animations") or {}
        if isinstance(anims, dict):
            for k, v in anims.items():
                if isinstance(v, str) and v.startswith("http"):
                    urls.append((v, f"gameInitOptions.animations.{k}"))

        sb = init.get("soundboard") or {}
        if isinstance(sb, dict):
            for channel, sounds in sb.items():
                if not isinstance(sounds, dict):
                    continue
                for sname, surl in sounds.items():
                    if isinstance(surl, str) and surl.startswith("http"):
                        urls.append((surl, f"gameInitOptions.soundboard.{channel}.{sname}"))

        if not urls:
            return

        import urllib.request
        import urllib.error
        from concurrent.futures import ThreadPoolExecutor, as_completed

        def probe(url):
            # HEAD first; some CDNs reject HEAD — fall back to GET-with-Range.
            for method, headers in [("HEAD", {}), ("GET", {"Range": "bytes=0-0"})]:
                try:
                    req = urllib.request.Request(url, method=method, headers={
                        **headers,
                        "User-Agent": "Mozilla/5.0 (validate_game_json)",
                    })
                    with urllib.request.urlopen(req, timeout=8) as resp:
                        return ("ok", resp.status)
                except urllib.error.HTTPError as e:
                    if e.code == 405 and method == "HEAD":
                        continue  # try GET-Range
                    return ("http_err", e.code)
                except Exception as e:
                    return ("net_err", str(e)[:80])
            return ("net_err", "exhausted methods")

        with ThreadPoolExecutor(max_workers=8) as pool:
            futures = {pool.submit(probe, u): (u, p) for u, p in urls}
            for fut in as_completed(futures):
                url, path = futures[fut]
                kind, info = fut.result()
                if kind == "ok":
                    continue
                if kind == "http_err":
                    self.err(path,
                             f"Asset URL returned HTTP {info}: {url!r}. The engine "
                             "will silently fail to load this asset at runtime. "
                             "Common causes: typo, doubled path prefix (e.g. "
                             "`image/upload/video/upload/...`), file was never "
                             "uploaded, or the public_id/folder doesn't match.")
                else:  # net_err
                    self.warn(path,
                              f"Could not verify asset URL {url!r}: {info}. "
                              "Network may be offline; set LUDIO_VALIDATOR_SKIP_"
                              "NETWORK=1 to skip these checks.")

    def _check_move_cards_payload(self):
        """Validate moveCards payload fields against the documented spec:
          - `type` is REQUIRED and must be exactly "hand" or "deck" (no "card",
            "cards", or anything else — moveCards moves things BETWEEN containers,
            it doesn't have a "single-card" type)
          - To target specific cards by name, use `cardNames` (a list of strings,
            or a computed list selector) — NOT `cards`. The `cards` field is a
            common hallucination; the engine silently ignores it and moves the
            entire deck, which is rarely what you wanted.
        Both fields can appear in either `preset` or `computed` sections."""
        VALID_TYPES = {"hand", "deck"}

        def walk(item, path):
            if isinstance(item, dict):
                if item.get("key") == "moveCards":
                    payload = item.get("payload") or {}
                    preset = payload.get("preset") or {}
                    cached = payload.get("cached") or {}
                    computed = payload.get("computed") or {}
                    pp = f"{path}.payload"

                    # `type` is required and constrained
                    t = preset.get("type") if isinstance(preset, dict) else None
                    if t is None:
                        # Could in theory be cached/computed, but docs+examples only ever use preset
                        if "type" not in cached and "type" not in computed:
                            self.err(pp, "moveCards is missing required field `type`. "
                                         "It must be 'hand' (hand→hand) or 'deck' (deck→deck).")
                    elif t not in VALID_TYPES:
                        self.err(f"{pp}.preset.type",
                                 f"moveCards `type` must be 'hand' or 'deck', got {t!r}. "
                                 "There is no 'card' type — to move specific cards by name "
                                 "use type='deck' (or 'hand') and put the names in `cardNames`.")

                    # `cards` is a hallucinated field — the engine ignores it silently
                    for section_name, section in (("preset", preset), ("cached", cached), ("computed", computed)):
                        if isinstance(section, dict) and "cards" in section:
                            self.err(f"{pp}.{section_name}.cards",
                                     "moveCards has no `cards` field — the engine silently "
                                     "ignores it and ends up moving the entire source deck. "
                                     "To target specific cards by name, rename this field to "
                                     "`cardNames` (a list of strings, or a computed list selector).")
                for k, v in item.items():
                    walk(v, f"{path}.{k}" if path else k)
            elif isinstance(item, list):
                for i, x in enumerate(item):
                    walk(x, f"{path}[{i}]")

        walk(self.data, "")

    def _check_cardback_resolves(self):
        """Every preset.cardback reference (createGenericCardWidget, createVideoboxDecks,
        etc.) must resolve to a real image — either a full http(s) URL or an alias key
        defined in gameInitOptions.images. A bare key like 'cardback' is valid only when
        gameInitOptions.images.cardback exists with a `url`. Aliases pointing at the
        transparent placeholder don't count as a cardback (the engine shows nothing
        and may throw)."""
        init = self.data.get("gameInitOptions") or {}
        images = init.get("images") or {}
        TRANSPARENT_TAIL = "transparent_sbx4wv.png"

        def is_url(s):
            return isinstance(s, str) and (s.startswith("http://") or s.startswith("https://"))

        def walk(obj, path):
            if isinstance(obj, dict):
                preset = obj.get("payload", {}).get("preset") if isinstance(obj.get("payload"), dict) else None
                if isinstance(preset, dict) and "cardback" in preset:
                    cb = preset["cardback"]
                    cb_path = f"{path}.payload.preset.cardback"
                    if not isinstance(cb, str) or not cb:
                        self.err(cb_path,
                                 f"`cardback` must be a non-empty URL or an image alias key, "
                                 f"got {cb!r}.")
                    elif is_url(cb):
                        if cb.endswith(TRANSPARENT_TAIL):
                            self.err(cb_path,
                                     "`cardback` points at the transparent placeholder. "
                                     "Use a real card-back image (e.g. the standard "
                                     "pirate_cardback_cii39m.png that Hearts/Euchre use, "
                                     "or upload a themed one).")
                    else:
                        alias = images.get(cb)
                        if not isinstance(alias, dict) or not alias.get("url"):
                            self.err(cb_path,
                                     f"`cardback: {cb!r}` is not a URL and no matching "
                                     f"alias exists in gameInitOptions.images. Add "
                                     f'`\"{cb}\": {{\"url\": \"<real card-back image URL>\"}}` '
                                     f"under gameInitOptions.images, or pass a full URL "
                                     f"directly.")
                        elif isinstance(alias.get("url"), str) and alias["url"].endswith(TRANSPARENT_TAIL):
                            self.err(cb_path,
                                     f"`cardback: {cb!r}` resolves via the alias to the "
                                     "transparent placeholder. The engine needs a real "
                                     "face-down image here — use the standard "
                                     "pirate_cardback_cii39m.png or upload a themed one.")
                for k, v in obj.items():
                    walk(v, f"{path}.{k}")
            elif isinstance(obj, list):
                for i, x in enumerate(obj):
                    walk(x, f"{path}[{i}]")

        walk(self.data, "")

    def _check_no_nested_groups_in_repeat_parallel(self):
        """A group carrying a `repeat` or `parallel` directive can ONLY contain plain
        actions in its `actions` list — not nested action groups. The engine doesn't
        recurse into sub-groups when iterating a repeat/parallel block; nested groups
        either silently no-op or trip mismatched-state crashes (e.g. an inner playCards
        sees stale outer-loop variables).

        For nested looping use a `[]` square-bracket loop at the gameLoop level —
        inside it you can place full action groups freely, and you control iteration by
        saving `isActionLoop: true/false` to cache (see willpower.json's trick loop,
        roundabout.json's trick body). A square-bracket loop also auto-populates a
        `loopIndex` cache var counting completed iterations.

        A "nested group" here is any dict with `name` plus `actions`/`repeat`/`parallel`.
        Plain actions have `key` (emptyAction, playCards, setRole, etc.)."""
        def is_action_group(item):
            return (
                isinstance(item, dict)
                and "name" in item
                and ("actions" in item or "repeat" in item or "parallel" in item)
            )

        def walk(item, path):
            if isinstance(item, dict):
                has_iter = "repeat" in item or "parallel" in item
                if has_iter:
                    actions = item.get("actions", [])
                    if isinstance(actions, list):
                        for i, a in enumerate(actions):
                            if is_action_group(a):
                                directive = "repeat" if "repeat" in item else "parallel"
                                self.err(
                                    f"{path}.actions[{i}]",
                                    f"Action group '{a.get('name')}' is nested inside a "
                                    f"`{directive}` group's `actions` list — the engine "
                                    f"does NOT iterate sub-groups inside a repeat/parallel "
                                    f"block. For nested looping, use a [] square-bracket "
                                    f"loop at the gameLoop level. Inside a square-bracket "
                                    f"loop you can place full action groups; set "
                                    f"`isActionLoop: false` via saveValueInCache to break "
                                    f"out (and use the auto-populated `loopIndex` cache "
                                    f"var if you need an iteration counter). See "
                                    f"willpower.json's trick loop for the pattern."
                                )
                for k, v in item.items():
                    walk(v, f"{path}.{k}")
            elif isinstance(item, list):
                for i, x in enumerate(item):
                    walk(x, f"{path}[{i}]")

        walk(self.data.get("gameLoop", []), "gameLoop")

    def _check_save_value_in_cache_shape(self):
        """A saveValueInCache entry's `value` is either the literal value, or a
        selector object (a dict with a `selector` key). It is NOT a typed param
        wrapper like `{type: "preset", value: V}` / `{type: "cached", value: "X"}`
        / `{type: "computed", value: <selector>}` — those wrappers belong inside
        SELECTOR PARAMS, not in saveValueInCache values. Mistake symptom: the
        engine treats the wrapper object as a literal cached value, so any
        downstream selector that expects a list/scalar gets `[object Object]`
        and crashes (e.g. 'concat argument is not list, list2: [object Object]')."""
        TYPED_KEYS = {"preset", "cached", "computed"}

        def looks_typed_wrapper(v):
            return (
                isinstance(v, dict)
                and set(v.keys()) == {"type", "value"}
                and v.get("type") in TYPED_KEYS
            )

        def walk(obj, path):
            if isinstance(obj, dict):
                svc = obj.get("saveValueInCache")
                if isinstance(svc, list):
                    for i, entry in enumerate(svc):
                        if not isinstance(entry, dict):
                            continue
                        v = entry.get("value")
                        entry_path = f"{path}.saveValueInCache[{i}]"
                        if looks_typed_wrapper(v):
                            t = v["type"]
                            inner = v["value"]
                            if t == "preset":
                                suggestion = f"value={inner!r:.80}"
                            elif t == "cached":
                                suggestion = (
                                    f'value={{"selector": "getCachedValue", '
                                    f'"params": [{{"name": "name", "type": "preset", '
                                    f'"value": "{inner}"}}]}}'
                                )
                            else:  # computed
                                suggestion = "value=<the selector object directly>"
                            self.err(
                                entry_path,
                                f"saveValueInCache value is a typed param wrapper "
                                f"({{type: {t!r}, value: ...}}). saveValueInCache values "
                                f"must be either the literal value itself or a selector "
                                f"object — never a typed wrapper. Use "
                                f"{suggestion} instead. (Typed wrappers belong inside "
                                f"selector params, not as saveValueInCache values.)"
                            )
                for k, vv in obj.items():
                    if k == "saveValueInCache":
                        continue  # handled above
                    walk(vv, f"{path}.{k}" if path else k)
            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    walk(item, f"{path}[{i}]")

        walk(self.data, "")

    def _check_post_game_actions_required(self):
        """Every game with a defined win condition must also define `postGameActions`
        with at least one action — the engine has no built-in "you won" UI, so without
        postGameActions the players see nothing when the game ends. Canonical content:
        hideAllPlayersHands → setImagesRow (shrink) → createNotification announcing
        the winner → endClip. Copy from emeralds.json / coalition.json / roundabout.json."""
        if not isinstance(self.data, dict):
            return
        if "gameInitOptions" not in self.data and "gameLoop" not in self.data:
            return  # Not a game JSON; skip.
        has_win = "winCondition" in self.data or "playersWinCondition" in self.data
        if not has_win:
            return  # _check_win_condition_defined already errored on this.
        pga = self.data.get("postGameActions")
        if not isinstance(pga, list) or len(pga) == 0:
            self.err("(top-level)",
                     "Missing or empty `postGameActions`. Every game with a win condition "
                     "must define a non-empty postGameActions list — the engine fires it "
                     "after `playersWinCondition.gameOverCondition` flips true. Without it, "
                     "players see no end-game UI when the host votes to end. Canonical "
                     "content: hideAllPlayersHands → setImagesRow (maxHeight=10, transparent) "
                     "→ createNotification announcing the winner (header uses cached 'winner' "
                     "+ ifElse for wins/share) → endClip. Copy verbatim from emeralds.json, "
                     "coalition.json, or roundabout.json.")

    def _check_winners_returns_names(self):
        """For `playersWinCondition`, the `winners` selector must return a list of
        player NAMES (strings), not raw IDs — postGameActions notifications display
        `cached.winner` as text in `formatString`. The canonical pattern wraps the
        ID-returning selector (e.g. getPlayersWithMaxScore) in getPlayerNamesByIds.
        Without the wrap, the engine pipes raw UUIDs into the winner notification."""
        if not isinstance(self.data, dict):
            return
        pwc = self.data.get("playersWinCondition")
        if not isinstance(pwc, dict):
            return
        winners = pwc.get("winners")
        if not isinstance(winners, dict):
            self.err("playersWinCondition.winners",
                     "playersWinCondition.winners must be a selector object. Use "
                     "getPlayerNamesByIds wrapping getPlayersWithMaxScore (canonical: copy from "
                     "emeralds.json / roundabout.json / coalition.json).")
            return
        if winners.get("selector") != "getPlayerNamesByIds":
            self.err("playersWinCondition.winners",
                     "playersWinCondition.winners must use selector `getPlayerNamesByIds` "
                     "wrapping the ID-returning selector (e.g. getPlayersWithMaxScore). "
                     "Raw IDs break the postGameActions winner notification — `cached.winner` "
                     "is rendered as text via formatString. Canonical form (see emeralds.json):\n"
                     "  {\"selector\": \"getPlayerNamesByIds\", \"params\": [{\"name\": \"ids\", "
                     "\"type\": \"computed\", \"value\": {\"selector\": \"getPlayersWithMaxScore\"}}]}")

    def _check_spectator_transitions(self):
        """If `allowPlayerBecomeSpectator` is enabled, the game must:
          1. Define `turnPlayerToSpectatorActions` at the top level (the action
             block the engine fires when a player drops to spectator), AND
          2. Carry `turnPlayersToSpectators: true` on at least one gameLoop action
             group — this is the trigger that lets the engine actually fire that
             block. Without the group-level flag the transition section is dead
             code: the player UI shows a leave option, but the engine never runs
             the recall/refresh actions and downstream state goes stale.

        Symmetric check for `allowSpectatorBecomePlayer` ↔
        `turnSpectatorToPlayerActions` + `turnSpectatorsToPlayers: true`.

        Pair this with [[feedback_spectator_to_player_checklist]] (memory) for the
        per-game implementation detail.
        """
        init = self.data.get("gameInitOptions")
        if not isinstance(init, dict):
            return
        loop = self.data.get("gameLoop")
        loop_groups = loop if isinstance(loop, list) else []

        def _has_group_flag(flag_name: str) -> bool:
            """True if at least one top-level action group in gameLoop carries
            `flag_name: true` (groups inside trick-loop arrays count too)."""
            def walk(item) -> bool:
                if isinstance(item, dict):
                    if item.get(flag_name) is True:
                        return True
                    # Group can also be nested inside a list-of-groups (action-loop pattern).
                if isinstance(item, list):
                    return any(walk(x) for x in item)
                return False
            return any(walk(g) for g in loop_groups)

        for direction, allow_field, actions_field, flag_field in (
            ("player → spectator", "allowPlayerBecomeSpectator",
             "turnPlayerToSpectatorActions", "turnPlayersToSpectators"),
            ("spectator → player", "allowSpectatorBecomePlayer",
             "turnSpectatorToPlayerActions", "turnSpectatorsToPlayers"),
        ):
            if init.get(allow_field) is not True:
                continue
            block = self.data.get(actions_field)
            if not isinstance(block, list) or not block:
                self.err(f"gameInitOptions.{allow_field}",
                         f"`{allow_field}: true` requires a top-level "
                         f"`{actions_field}` list of actions — the engine fires that "
                         f"block on every {direction} transition. Without it, the "
                         f"transition leaves state inconsistent (hands not recalled, "
                         f"player lists stale, etc.).")
            if not _has_group_flag(flag_field):
                self.err(f"gameInitOptions.{allow_field}",
                         f"`{allow_field}: true` and `{actions_field}` are defined, "
                         f"but no gameLoop action group has `{flag_field}: true` — "
                         f"so the engine never actually runs the transition block. "
                         f"Add `\"{flag_field}\": true` (at the group level, NOT "
                         f"inside an action) to the dedicated 'Change Players' "
                         f"group at the end of gameLoop. See Roundabout for the "
                         f"canonical placement (empty trailing group, with "
                         f"`changeLayout` at the tail of the actions list).")

    def _check_select_element_shorthand(self):
        """Flag `selectElement(list=cached:X, index=preset:N)` — Ludio supports a
        cache-path shorthand `cached: "X.N"` that's equivalent and one selector lighter.

        Only fires when BOTH the list is a cached reference (so the dotted path can
        resolve) AND the index is a preset integer (so the path is statically known).
        Mixed cases (list computed, index cached) stay as full selectors.
        """
        def walk(node, path=""):
            if isinstance(node, dict):
                if node.get("selector") == "selectElement":
                    params = {p.get("name"): p for p in node.get("params", []) if isinstance(p, dict)}
                    lst = params.get("list") or {}
                    idx = params.get("index") or {}
                    if (lst.get("type") == "cached" and isinstance(lst.get("value"), str)
                        and idx.get("type") == "preset" and isinstance(idx.get("value"), int)):
                        self.warn(path or "(root)",
                                  f"selectElement(list=cached:{lst['value']!r}, index=preset:{idx['value']}) "
                                  f"can be rewritten as cached:{lst['value']}.{idx['value']!s} "
                                  f"— Ludio reads the dotted path from the cached value. "
                                  f"Saves one selector and reads cleaner.")
                for k, v in node.items():
                    walk(v, f"{path}.{k}" if path else k)
            elif isinstance(node, list):
                for i, v in enumerate(node):
                    walk(v, f"{path}[{i}]")

        walk(self.data, "")

    def _check_get_card_field_scope(self):
        """getCardField only works on a cardId, and cardIds only exist as the result
        of a playCards action. So getCardField is only valid inside the
        saveValueInCache list of a playCards action — anywhere else it fails at
        runtime. To read a field on a known card object (e.g. the result of
        selectElement(getDeckCards(...))), use getObjectField instead.
        """
        def walk(node, path, in_legal_scope):
            if isinstance(node, dict):
                if not in_legal_scope and node.get("key") == "playCards":
                    # Only this action's saveValueInCache is a legal scope.
                    for k, v in node.items():
                        child_path = f"{path}.{k}" if path else k
                        walk(v, child_path, k == "saveValueInCache")
                    return
                if not in_legal_scope and node.get("selector") == "getCardField":
                    self.err(path or "(root)",
                             "getCardField only works on a cardId, which only exists "
                             "as the result of a playCards action — so it must appear "
                             "inside that playCards action's saveValueInCache. For a "
                             "known card object (e.g. selectElement(getDeckCards(...))), "
                             "use getObjectField on the card object instead.")
                for k, v in node.items():
                    walk(v, f"{path}.{k}" if path else k, in_legal_scope)
            elif isinstance(node, list):
                for i, v in enumerate(node):
                    walk(v, f"{path}[{i}]", in_legal_scope)

        walk(self.data, "", False)

    # Tags the engine renders as formatting *only* inside createNotification.text.
    # Everywhere else (any other action, and any other field of createNotification)
    # they render as literal text — so we flag them as a warning.
    _HTML_FORMAT_RE = __import__("re").compile(r"<\s*/?\s*(b|br|i)\s*/?\s*>", flags=__import__("re").IGNORECASE)

    def _check_html_in_action_text(self):
        """Only createNotification.text supports text-formatting tags (<br/>, <b>,
        <i>). Every other action — and every other field of createNotification —
        renders these tags as literal characters. Warn on any HTML tag found in
        a string anywhere under a non-allowed payload field. Walks formatString
        format params too, so e.g. formatString("Round <br/> 1") buried inside
        payload.computed.question still gets caught."""
        def find_html(value, path):
            """Yield (path, string) for every preset-flavored string under `value`
            that contains a flagged HTML tag. Descends through nested dicts/lists
            and through selector params with type 'preset' or 'computed' (cached
            params are cache-key strings, not display text)."""
            results = []
            if isinstance(value, str):
                if self._HTML_FORMAT_RE.search(value):
                    results.append((path, value))
            elif isinstance(value, dict):
                if isinstance(value.get("selector"), str):
                    for p in value.get("params", []):
                        if not isinstance(p, dict):
                            continue
                        if p.get("type") in ("preset", "computed"):
                            pname = p.get("name", "?")
                            results.extend(find_html(p.get("value"), f"{path}.{pname}"))
                else:
                    for k, v in value.items():
                        results.extend(find_html(v, f"{path}.{k}"))
            elif isinstance(value, list):
                for i, item in enumerate(value):
                    results.extend(find_html(item, f"{path}[{i}]"))
            return results

        def walk(node, path=""):
            if isinstance(node, dict):
                key = node.get("key")
                if isinstance(key, str):
                    payload = node.get("payload") or {}
                    if isinstance(payload, dict):
                        for section in ("preset", "computed"):
                            sec = payload.get(section)
                            if not isinstance(sec, dict):
                                continue
                            for field, value in sec.items():
                                # The single allowed home for HTML formatting in the
                                # entire action catalog: createNotification.text.
                                if key == "createNotification" and field == "text":
                                    continue
                                hits = find_html(value, f"{path}.payload.{section}.{field}")
                                for hit_path, hit_str in hits:
                                    self.warn(hit_path,
                                              f"'{key}' contains an HTML formatting tag "
                                              f"in {hit_str!r}. Only createNotification.text "
                                              "renders <br/>, <b>, and <i> as formatting — "
                                              "every other action and every other field "
                                              "shows these tags as literal text. Strip the "
                                              "tags (use ' — ' separators for inline lists) "
                                              "or move the prose into a createNotification.text.")
                for k, v in node.items():
                    walk(v, f"{path}.{k}" if path else k)
            elif isinstance(node, list):
                for i, v in enumerate(node):
                    walk(v, f"{path}[{i}]")

        walk(self.data, "")

    # Cached variable names that strongly imply a PLAYER ID (the hand owner), not a deck name.
    # When one of these appears in a `from`/`to`/`deck` field of a card-movement action, the
    # author probably meant to use dealDeck (deck→hand) or recallCards (hand→deck) instead of
    # moveCards (deck↔deck or hand↔hand only).
    SUSPECT_PLAYER_CACHE_NAMES = {
        "clueWriter", "cluegiver", "currentBard", "currentBidder", "currentPlayer",
        "newPlayer", "winner", "bard", "currentRepresentative", "judge", "thinker",
        "host", "currentWinner", "spectator", "waitingSpectator", "actor", "clicker",
        "currentLeader", "leader",
    }

    def _check_card_movement_targets(self):
        """Catch the deck/hand confusion in card-movement actions.

        Engine semantics (from documentation/Players <-> Spectators.pdf):
          • A *hand* is a player's cards (rendered as the bottom-of-screen strip).
          • A *deck* is a pile of cards, typically rendered in the central widget.
          • dealDeck:     deck → hand(s)
          • moveCards:    deck → deck    OR   hand → hand   (NEVER deck → hand or hand → deck)
          • recallCards:  hand(s) → deck
          • createPlayersDecks: creates one DECK per player, named after the player ID
            (so cached player IDs CAN legitimately appear as deck names downstream)

        Two patterns we flag:
          (A) `moveCards`/`createCard` `from`/`to`/`deck` is a PRESET string that doesn't
              match any deck created in this game JSON. The engine throws "deck not found"
              at runtime. Error.
          (B) `moveCards` `from`/`to` is a CACHED reference whose cache-variable name
              implies a player ID (e.g. `clueWriter`). Almost certainly a deck-vs-hand
              mix-up. Warn (we can't be 100% sure without runtime evaluation, but it's
              the right thing 99% of the time).

        Same checks apply to `dealDeck.deck`, `recallCards.deck`, `createCard.deck`.
        Skip (B) when `createPlayersDecks` is anywhere in the document — that action
        legitimately creates decks whose names match cached player IDs.
        """
        decks = self._collect_known_deck_names()
        if not decks:
            return  # No decks created — likely not a card game.

        has_players_decks_action = self._has_action_anywhere("createPlayersDecks")

        def check_deck_field(action, field, path):
            payload = action.get("payload") or {}
            preset = payload.get("preset") or {}
            cached = payload.get("cached") or {}
            # PRESET path: deck name as a literal string.
            if field in preset:
                val = preset[field]
                if isinstance(val, str) and val and val not in decks and not has_players_decks_action:
                    self.err(f"{path}.payload.preset.{field}",
                             f"References unknown deck {val!r}. The engine will throw "
                             f"\"deck not found\" at runtime. Known decks in this game: "
                             f"{sorted(decks)}.")
            # CACHED path: cache-variable name that strongly implies a player ID.
            if field in cached:
                val = cached[field]
                if isinstance(val, str):
                    head = val.split(".")[0]
                    if head in Validator.SUSPECT_PLAYER_CACHE_NAMES:
                        self.warn(f"{path}.payload.cached.{field}",
                                  f"Cached reference {val!r} looks like a player ID, but "
                                  f"this field expects a deck name. moveCards is deck↔deck "
                                  f"or hand↔hand only. To move cards from a deck into a "
                                  f"player's hand use dealDeck; from a player's hand into "
                                  f"a deck use recallCards. (Suppress this warning by "
                                  f"renaming the cache variable to something deck-shaped.)")

        def walk(node, path):
            if isinstance(node, dict):
                key = node.get("key")
                if key in ("moveCards", "createCard"):
                    for f in ("from", "to", "deck"):
                        check_deck_field(node, f, path)
                elif key == "dealDeck":
                    check_deck_field(node, "deck", path)
                elif key == "recallCards":
                    check_deck_field(node, "deck", path)
                for k, v in node.items():
                    walk(v, f"{path}.{k}" if path else k)
            elif isinstance(node, list):
                for i, v in enumerate(node):
                    walk(v, f"{path}[{i}]")

        walk(self.data, "")

    def _collect_known_deck_names(self) -> set:
        """Collect every locally-known deck name from createDeck/createCustomDeck calls.

        For `createDeck`, the LOCAL name is `customName` if provided, otherwise `name`
        (the staging script name). For `createCustomDeck`, the local name is `name`.
        """
        decks: set = set()

        def walk(node):
            if isinstance(node, dict):
                key = node.get("key")
                if key == "createDeck":
                    preset = (node.get("payload") or {}).get("preset") or {}
                    local = preset.get("customName") or preset.get("name")
                    if isinstance(local, str):
                        decks.add(local)
                elif key == "createCustomDeck":
                    preset = (node.get("payload") or {}).get("preset") or {}
                    name = preset.get("name")
                    if isinstance(name, str):
                        decks.add(name)
                for v in node.values():
                    walk(v)
            elif isinstance(node, list):
                for v in node:
                    walk(v)

        walk(self.data)
        return decks

    def _has_action_anywhere(self, key: str) -> bool:
        found = [False]

        def walk(node):
            if found[0]:
                return
            if isinstance(node, dict):
                if node.get("key") == key:
                    found[0] = True
                    return
                for v in node.values():
                    walk(v)
            elif isinstance(node, list):
                for v in node:
                    walk(v)

        walk(self.data)
        return found[0]

    # Threshold: a central widget grid with strictly more than this many rows
    # is considered "vertical space at a premium" — image rows would squeeze the
    # board too far. ≤ this many rows ⇒ vertical space is fine, an image row
    # belongs at the bottom to host player hands.
    PREMIUM_ROW_THRESHOLD = 3

    @staticmethod
    def _image_row_is_trivial(images_field) -> bool:
        """An image row is 'trivial' (i.e. just a hand-strip spacer) when it shows
        nothing but the canonical 'transparent' placeholder. Anything else
        (real images, computed selectors, etc.) is treated as game-relevant
        content the designer cares about."""
        if isinstance(images_field, list):
            return all(isinstance(x, str) and x == "transparent" for x in images_field)
        return False

    def _check_increase_hand_height_pair(self):
        """Image-row decision (per the cards × vertical-space flowchart):

        Factors:
          (a) Is there a setImagesRow with non-trivial content? (real images vs.
              transparent-only spacer.)
          (b) Do players receive cards they can play? (any dealDeck action.)
          (c) Is vertical space at a premium? (central widget grid has more than
              PREMIUM_ROW_THRESHOLD rows.)

        Rules:
          • Players don't get cards → image row only matters if it's used for
            something game-relevant; transparent spacers should be removed.
          • Players get cards + premium vertical space → omit the image row
            (transparent spacer wastes space; just let hands cover the grid).
          • Players get cards + non-premium vertical space → include a
            setImagesRow tall enough for the hand. Use maxHeight=230 when
            visualSettings.increaseHandHeight is true, otherwise ~140.
        """
        if not isinstance(self.data, dict):
            return
        vs = self.data.get("visualSettings") or {}
        increased = isinstance(vs, dict) and vs.get("increaseHandHeight") is True

        # Walk the JSON once collecting widget row counts, dealDeck presence, and
        # all setImagesRow actions with enough context to classify them.
        max_rows = 0
        has_deal = False
        rows_collected = []        # list of (preset.maxHeight, preset.images)
        def walk(node):
            nonlocal max_rows, has_deal
            if isinstance(node, dict):
                key = node.get("key")
                if key == "createGenericCardWidget":
                    preset = (node.get("payload") or {}).get("preset") or {}
                    dims = preset.get("dimensions")
                    # Ludio reads dimensions as [rows, cols] — first element is rows.
                    if isinstance(dims, list) and dims and isinstance(dims[0], int):
                        max_rows = max(max_rows, dims[0])
                elif key == "dealDeck":
                    has_deal = True
                elif key == "setImagesRow":
                    preset = (node.get("payload") or {}).get("preset") or {}
                    rows_collected.append((preset.get("maxHeight"), preset.get("images")))
                for v in node.values():
                    walk(v)
            elif isinstance(node, list):
                for v in node:
                    walk(v)
        walk(self.data)

        premium = max_rows > self.PREMIUM_ROW_THRESHOLD
        trivial_rows = [r for r in rows_collected if self._image_row_is_trivial(r[1])]
        real_rows    = [r for r in rows_collected if not self._image_row_is_trivial(r[1])]
        # "Tall enough for the hand": 140 for default hand, 230 when increaseHandHeight=true.
        target_height = 230 if increased else 140
        any_tall_enough = any(isinstance(h, (int, float)) and h >= target_height
                              for (h, _img) in real_rows)

        if not has_deal:
            # Players don't get cards → only complain about transparent spacers
            # that aren't doing anything. Real image rows are intentional.
            if trivial_rows:
                self.warn("setImagesRow",
                          "Found a setImagesRow with images=['transparent'] but the game never "
                          "calls dealDeck — players don't receive cards, so there's nothing for "
                          "the image-row backdrop to host. Remove this stage and let the central "
                          "widget reclaim the vertical space.")
            return

        # has_deal == True from here on.
        if premium:
            # Vertical space is at a premium → omit the image row entirely.
            if trivial_rows:
                self.warn("setImagesRow",
                          f"Central widget has {max_rows} rows (> {self.PREMIUM_ROW_THRESHOLD}) "
                          "— vertical space is at a premium, so the image row should be omitted. "
                          "The transparent setImagesRow is squeezing the board for no game-relevant "
                          "benefit; player hands covering the grid when open is the accepted "
                          "trade-off. Remove the setImagesRow stage and the increaseHandHeight "
                          "visualSetting if you don't need it. (Real, in-game image rows are fine "
                          "to keep — only transparent spacers are flagged here.)")
        else:
            # Not at a premium → expect a properly-sized image row.
            if not any_tall_enough:
                hint_about_flag = (
                    " (increaseHandHeight=true means hand cards are taller and need maxHeight=230)"
                    if increased else
                    " (default hand height — maxHeight ~140 is enough)"
                )
                self.warn("setImagesRow",
                          f"Central widget has only {max_rows} rows so vertical space is NOT at "
                          f"a premium — players' hands need a dedicated image-row strip below the "
                          f"board. Add a setImagesRow with maxHeight={target_height}{hint_about_flag}. "
                          "Without it the hand cards will overlap the central widget when open.")

    def _check_host_display(self):
        """The 'host' cached var is a list of player IDs (used as 'actors' for createVote etc.).
        When the host is shown in a notification or other string context, it must be converted
        to player names via getPlayerNamesByIds first — otherwise players see raw user IDs.

        We catch the common bug: listToString called with list = cached:host (no name
        conversion in between)."""
        def walk(node, path=""):
            if isinstance(node, dict):
                if node.get("selector") == "listToString":
                    for p in node.get("params", []):
                        if not (isinstance(p, dict) and p.get("name") == "list"):
                            continue
                        if p.get("type") == "cached" and p.get("value") == "host":
                            self.err(path,
                                     "listToString is being called on cached:host directly — "
                                     "this displays raw player IDs in the message. Wrap host in "
                                     "getPlayerNamesByIds first: "
                                     "listToString(getPlayerNamesByIds(cached:host)). "
                                     "See emeralds.json's welcome notification for the canonical pattern.")
                for k, v in node.items():
                    walk(v, f"{path}.{k}" if path else k)
            elif isinstance(node, list):
                for i, v in enumerate(node):
                    walk(v, f"{path}[{i}]")
        walk(self.data, "")

    # Standard avatar for the default "player" role across all card-style games.
    STANDARD_PLAYER_AVATAR = "https://res.cloudinary.com/liars-club/image/upload/card_player_ed7jck.webp"

    def _check_custom_deck_public(self):
        """A createCustomDeck must have preset.public = true IF the deck is ever used as
        one of the selectable decks of a selectCentralWidgetDeck action — that's the case
        where the player has to click the deck. Being a target of a playCards action does
        NOT require public:true (the cards just land there; the player doesn't click it).

        We can only resolve static deck names. For computed deck names (formatString),
        we extract the literal prefix (everything before the first `(`) and match createCustomDeck
        names by prefix. Cached references (e.g. cached.decks = "selectableDecks") cannot be
        traced — those decks slip past this check, so set public:true defensively when you
        reference a deck via a cache var.
        """
        # Step 1: collect static deck names + prefix patterns that must be public.
        required_static = set()
        required_prefixes = set()

        def extract_prefix_from_formatstring(value):
            """If `value` is a {selector: formatString, params: [{name:'format', type:'preset', value:'foo_($1)'}, ...]},
            return the literal prefix 'foo_'. Otherwise None."""
            if not (isinstance(value, dict) and value.get("selector") == "formatString"):
                return None
            for p in value.get("params", []):
                if isinstance(p, dict) and p.get("name") == "format" and p.get("type") == "preset":
                    fmt = p.get("value")
                    if isinstance(fmt, str) and "(" in fmt:
                        prefix = fmt.split("(", 1)[0]
                        if prefix:
                            return prefix
            return None

        def collect_target(node):
            if isinstance(node, dict):
                if node.get("key") == "selectCentralWidgetDeck":
                    payload = node.get("payload", {}) or {}
                    preset_decks = (payload.get("preset", {}) or {}).get("decks")
                    computed_decks = (payload.get("computed", {}) or {}).get("decks")
                    if isinstance(preset_decks, list):
                        for d in preset_decks:
                            if isinstance(d, str):
                                required_static.add(d)
                    if computed_decks:
                        pfx = extract_prefix_from_formatstring(computed_decks)
                        if pfx:
                            required_prefixes.add(pfx)
                for v in node.values():
                    collect_target(v)
            elif isinstance(node, list):
                for v in node:
                    collect_target(v)

        collect_target(self.data)

        # Step 2: walk createCustomDeck and require public:true for matches.
        def name_matches(name):
            if not isinstance(name, str):
                return False
            if name in required_static:
                return True
            return any(name.startswith(p) for p in required_prefixes)

        def check(obj, path):
            if isinstance(obj, dict):
                if obj.get("key") == "createCustomDeck":
                    payload = obj.get("payload", {}) or {}
                    preset = payload.get("preset", {}) or {}
                    computed = payload.get("computed", {}) or {}
                    if preset.get("public") is not True:
                        # Resolve the deck's name. Static name in preset.name; or computed.name
                        # which we try to resolve to a prefix via formatString.
                        name = preset.get("name")
                        is_required = False
                        if isinstance(name, str):
                            is_required = name_matches(name)
                        else:
                            # computed.name → derive prefix and check overlap with required_prefixes
                            pfx = extract_prefix_from_formatstring(computed.get("name"))
                            if pfx and any(pfx.startswith(rp) or rp.startswith(pfx) for rp in required_prefixes):
                                is_required = True
                            # Also: if there's a static-match required_static name matching the deck's
                            # static suffix we can't easily check — skip.
                        if is_required:
                            self.err(path,
                                     f"createCustomDeck for {name!r} must have preset.public = true "
                                     "— this deck is one of the selectCentralWidgetDeck decks, "
                                     "so players need to be able to click it. Without public:true "
                                     "the deck won't render as clickable.")
                for k, v in obj.items():
                    check(v, f"{path}.{k}" if path else k)
            elif isinstance(obj, list):
                for i, v in enumerate(obj):
                    check(v, f"{path}[{i}]")

        check(self.data, "")

    def _check_card_game_setup(self):
        """If the game deals cards to players (any dealDeck action exists), the central
        widget must get vertical space via changeLayout(direction='VERTICAL') so the
        hand strip sits below the board. (The showAllPlayersHands decision is a separate
        UX choice handled by _check_show_all_hands_decision; setImagesRow handling lives
        in _check_increase_hand_height_pair.)
        """
        has_deal = {"v": False}
        layout_ok = {"v": False}

        def scan(node):
            if isinstance(node, dict):
                key = node.get("key")
                if key == "dealDeck":
                    has_deal["v"] = True
                elif key == "changeLayout":
                    preset = (node.get("payload") or {}).get("preset", {}) or {}
                    if preset.get("direction") == "VERTICAL":
                        layout_ok["v"] = True
                for v in node.values():
                    scan(v)
            elif isinstance(node, list):
                for v in node:
                    scan(v)
        scan(self.data)

        if not has_deal["v"]:
            return  # Not a card-dealing game; nothing to check.

        if not layout_ok["v"]:
            self.warn("gameLoop / beforeLoopActions",
                      "Card-dealing game is missing a 'changeLayout' action with "
                      "direction='VERTICAL'. Without it the central widget doesn't get "
                      "vertical space and player hands don't sit below the board. Copy "
                      "from hearts.json (changeLayout HIGHLIGHT/VERTICAL/35-50% after "
                      "dealDeck).")

    def _check_show_all_hands_decision(self):
        """showAllPlayersHands forces every player's hand UI open by default. It is NOT
        a "let players see their cards" requirement — players can always tap their
        own hand strip to open it. It's also unrelated to showHand, which takes
        from/to and lets `to` see `from`'s cards by hovering over them (a hidden-info
        reveal mechanism, not a UI default).

        The decision mirrors the cards × vertical-space-premium flowchart:
          - Non-premium central widget (≤ PREMIUM_ROW_THRESHOLD rows) + dealDeck →
            USE showAllPlayersHands. Trick-taking / standard card UX wants hands
            visible by default; without it players have to tap every round.
          - Premium central widget (> PREMIUM_ROW_THRESHOLD rows) + dealDeck →
            AVOID showAllPlayersHands. Forcing all hands open squeezes the board;
            let players tap to open, or use showPlayersHands for the active player only.

        Carveout: games that intentionally hide hands from opposing teams
        (e.g. Cops & Robbers, where Robbers' stash hands stay secret) skip
        showAllPlayersHands deliberately and will not match either side of the
        rule — suppress the warning manually in that case.
        """
        has_deal = False
        has_show_all = False
        show_all_path = None
        max_rows = 0

        def walk(node, path):
            nonlocal has_deal, has_show_all, show_all_path, max_rows
            if isinstance(node, dict):
                key = node.get("key")
                if key == "dealDeck":
                    has_deal = True
                elif key == "showAllPlayersHands":
                    if not has_show_all:
                        show_all_path = path
                    has_show_all = True
                elif key == "createGenericCardWidget":
                    preset = (node.get("payload") or {}).get("preset") or {}
                    dims = preset.get("dimensions")
                    if isinstance(dims, list) and dims and isinstance(dims[0], int):
                        max_rows = max(max_rows, dims[0])
                for k, v in node.items():
                    walk(v, f"{path}.{k}" if path else k)
            elif isinstance(node, list):
                for i, v in enumerate(node):
                    walk(v, f"{path}[{i}]")

        walk(self.data, "")

        if not has_deal:
            return  # Not a card-dealing game; nothing to check.

        premium = max_rows > self.PREMIUM_ROW_THRESHOLD

        if premium and has_show_all:
            self.warn(show_all_path or "showAllPlayersHands",
                      f"showAllPlayersHands fires but central widget has {max_rows} rows "
                      f"(> {self.PREMIUM_ROW_THRESHOLD}) — vertical space is at a premium, "
                      "so forcing every player's hand open will squeeze the board. Remove "
                      "this action; players can tap their hand UI to open it themselves, "
                      "or use showPlayersHands(userIds=...) to open only the active "
                      "player's hand when it's their turn.")
        elif not premium and not has_show_all:
            self.warn("gameLoop / beforeLoopActions",
                      f"Card-dealing game with {max_rows or 0} central widget row(s) "
                      f"(<= {self.PREMIUM_ROW_THRESHOLD}) has no showAllPlayersHands. "
                      "Vertical space is NOT at a premium here, so the UX default is "
                      "all hands visible — without showAllPlayersHands players have to "
                      "tap to open their hand every round. Add showAllPlayersHands after "
                      "dealDeck. (Suppress only if the game intentionally hides hands "
                      "from opposing teams — e.g. Cops & Robbers, where Robbers' stash "
                      "hands stay secret.)")

    def _check_roles(self):
        """gameInitOptions must declare a 'roles' list with at least one entry that has
        roleInfo.id and roleInfo.name. Teams can reference role ids in their 'roles' field."""
        init = self.data.get("gameInitOptions")
        if not isinstance(init, dict):
            return
        roles = init.get("roles")
        if not isinstance(roles, list) or not roles:
            self.err("gameInitOptions",
                     "Missing 'roles' list — every game needs at least one role under "
                     "gameInitOptions.roles. Each entry should be "
                     "{\"roleInfo\": {\"id\": ..., \"name\": ..., \"team\": ...}, \"isDefaultRole\": true/false, \"isRequired\": true/false}. "
                     "Copy the pattern from roundabout.json or enigma.json.")
            return
        for i, r in enumerate(roles):
            if not isinstance(r, dict):
                self.err(f"gameInitOptions.roles[{i}]", "Role must be an object.")
                continue
            info = r.get("roleInfo")
            if not isinstance(info, dict):
                self.err(f"gameInitOptions.roles[{i}]", "Role missing required 'roleInfo' object.")
                continue
            for f in ("id", "name"):
                if f not in info:
                    self.err(f"gameInitOptions.roles[{i}].roleInfo", f"missing required field '{f}'.")
            # The standard 'player' role across all card-style games uses the canonical avatar.
            if info.get("id") == "player":
                avatar = info.get("avatar")
                if avatar != self.STANDARD_PLAYER_AVATAR:
                    self.err(f"gameInitOptions.roles[{i}].roleInfo",
                             f"The default 'player' role must use the standard avatar "
                             f"({self.STANDARD_PLAYER_AVATAR}). Got: {avatar!r}. "
                             "Every game with a 'player' role should reuse this image so "
                             "the look stays consistent across the catalog.")

        # useDefaultRoles ↔ isDefaultRole consistency: when useDefaultRoles is true the engine
        # automatically assigns the role flagged isDefaultRole=true to every player at game
        # start. When it's false/missing, the game must instead define role presets and
        # NO role should carry isDefaultRole=true — otherwise the flag is silently ignored
        # while the rest of the JSON assumes a default exists.
        use_default = init.get("useDefaultRoles") is True
        default_roles = [
            i for i, r in enumerate(roles)
            if isinstance(r, dict) and r.get("isDefaultRole") is True
        ]
        if use_default and len(default_roles) == 0:
            self.err("gameInitOptions",
                     "`useDefaultRoles: true` but no role has `isDefaultRole: true`. With "
                     "useDefaultRoles enabled, exactly one role must be flagged as the default — "
                     "the engine assigns it to every player at game start. Either set "
                     "`isDefaultRole: true` on the canonical player role, or remove "
                     "`useDefaultRoles: true` and define role presets instead.")
        if use_default and len(default_roles) > 1:
            ids = [roles[i].get("roleInfo", {}).get("id") for i in default_roles]
            self.err("gameInitOptions",
                     f"`useDefaultRoles: true` but {len(default_roles)} roles are flagged "
                     f"`isDefaultRole: true` ({ids}). Exactly one default role is allowed — "
                     "the engine only assigns one role at game start.")
        if not use_default and len(default_roles) > 0:
            ids = [roles[i].get("roleInfo", {}).get("id") for i in default_roles]
            self.err("gameInitOptions",
                     f"Role(s) {ids} have `isDefaultRole: true` but `useDefaultRoles` is not "
                     "true. The default-role flag is only meaningful when `useDefaultRoles: true` "
                     "is set on gameInitOptions. Either flip useDefaultRoles to true (the engine "
                     "will then auto-assign the flagged role at game start) or drop the "
                     "isDefaultRole flag and define role presets instead.")

    def _check_create_deck_pattern(self):
        """createDeck.name must refer to a real staging deck (the script.name of a cards JSON
        uploaded via /api/deck), NOT the local name you want to give the imported deck. To
        rename it locally, use 'customName'. The most common mistake: passing the SET name
        as 'name' — that only works when the staging deck happens to be named the same as
        the set, which is rare.

        Heuristic check: if a sibling <game>_cards.json file exists in the same directory,
        verify each createDeck.name matches the script.name of that cards file. (If you have
        multiple cards files or use shared decks like classic_cards, the check is silently
        skipped because we don't know which deck is the intended source.)
        """
        if not getattr(self, "_source_path", None):
            return
        import os
        game_path = self._source_path
        if not game_path.endswith(".json"):
            return
        cards_path = game_path[:-5] + "_cards.json"
        if not os.path.exists(cards_path):
            return
        try:
            with open(cards_path) as f:
                cards_doc = json.load(f)
        except (json.JSONDecodeError, OSError):
            return
        expected_name = cards_doc.get("name")
        if not isinstance(expected_name, str):
            return

        def walk(node, path):
            if isinstance(node, dict):
                if node.get("key") == "createDeck":
                    preset = (node.get("payload") or {}).get("preset") or {}
                    name = preset.get("name")
                    cached = (node.get("payload") or {}).get("cached") or {}
                    if isinstance(name, str) and name != expected_name and name not in (cached.get("name"), ):
                        self.err(path,
                                 f"createDeck.name = {name!r} does not match the script.name "
                                 f"({expected_name!r}) of the sibling {os.path.basename(cards_path)}. "
                                 f"The 'name' field must reference the staging deck's name. "
                                 f"To rename the imported deck locally, use 'customName' (and put "
                                 f"the actual deck name in 'name').")
                for k, v in node.items():
                    walk(v, f"{path}.{k}" if path else k)
            elif isinstance(node, list):
                for i, v in enumerate(node):
                    walk(v, f"{path}[{i}]")

        walk(self.data, "")

    def _find_entries_named(self, obj: Any, target_name: str, path: str = "") -> list:
        """Recursively find all saveValueInCache entries with the given name."""
        results = []
        if isinstance(obj, dict):
            svc = obj.get("saveValueInCache")
            if isinstance(svc, list):
                for i, entry in enumerate(svc):
                    if isinstance(entry, dict) and entry.get("name") == target_name:
                        results.append((f"{path}.saveValueInCache[{i}]" if path else f"saveValueInCache[{i}]", entry))
            for k, v in obj.items():
                results.extend(self._find_entries_named(v, target_name, f"{path}.{k}" if path else k))
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                results.extend(self._find_entries_named(v, target_name, f"{path}[{i}]"))
        return results

    def _check_host_snippet(self):
        """Every saveValueInCache entry named 'host' must use the canonical getHostPlayerId snippet."""
        for path, entry in self._find_entries_named(self.data, "host"):
            if entry.get("value") != HOST_CACHE_VALUE:
                self.err(path,
                         "Cache variable 'host' must use the canonical snippet: "
                         "ifElse(contains(players, getHostPlayerId()), "
                         "createList(getHostPlayerId()), createList(players[0])). "
                         "Copy it verbatim from Things to remember.md.")

    def _check_widget_visibility(self):
        """
        Walk actions in document/execution order and track the central card widget's
        visibility state. Error if playCards or selectCentralWidgetDeck fires when the
        widget has never been created or is currently hidden (removeWidget without restoreWidget).
        Also warn if createVote/createInput fires while the central widget is visible —
        votes and inputs almost always need the widget hidden first so the prompt UI
        isn't competing with the central card area; hide → vote/input → restore.
        """
        state = {"visible": None}  # None=never created, False=hidden, True=visible

        def visit(action, path):
            key = action.get("key") if isinstance(action, dict) else None
            if key == "createGenericCardWidget":
                state["visible"] = True
            elif key == "removeWidget" and state["visible"] is True:
                state["visible"] = False
            elif key == "restoreWidget":
                state["visible"] = True
            elif key in ("playCards", "selectCentralWidgetDeck"):
                if state["visible"] is None:
                    self.err(path, f"'{key}' fires but createGenericCardWidget was never called before "
                             "this point. Create the central widget before using playCards or selectCentralWidgetDeck.")
                elif not state["visible"]:
                    self.err(path, f"'{key}' fires but the central widget is currently hidden — "
                             "removeWidget was called without a subsequent restoreWidget. "
                             "Call restoreWidget before this action.")
            elif key in ("createVote", "createInput") and state["visible"] is True:
                self.warn(path, f"'{key}' fires while the central card widget is visible. "
                          "Vote/input prompts usually want the widget hidden first so the "
                          "prompt UI isn't competing with the central card area. Pattern: "
                          "removeWidget → createVote/createInput → restoreWidget. "
                          "(Ignore if this game genuinely wants both visible together.)")

        def visit_flat(actions, base_path):
            if not isinstance(actions, list):
                return
            for i, item in enumerate(actions):
                if isinstance(item, dict):
                    visit(item, f"{base_path}[{i}]")

        def visit_groups(groups, base_path):
            if not isinstance(groups, list):
                return
            for i, group in enumerate(groups):
                gp = f"{base_path}[{i}]"
                if isinstance(group, dict):
                    visit_flat(group.get("actions", []), f"{gp}.actions")
                elif isinstance(group, list):
                    visit_groups(group, gp)

        visit_flat(self.data.get("beforeLoopActions", []), "beforeLoopActions")
        visit_groups(self.data.get("gameLoop", []), "gameLoop")
        visit_flat(self.data.get("postGameActions", []), "postGameActions")

    def _check_timing_fields(self):
        init = self.data.get("gameInitOptions")
        if not isinstance(init, dict):
            return
        found = [f for f in ("time", "timePerPlayer", "timePerRound") if f in init]
        if len(found) == 0:
            self.err("gameInitOptions",
                     "Missing timing field — must have exactly one of: time, timePerPlayer, timePerRound")
        elif len(found) > 1:
            self.err("gameInitOptions",
                     f"Multiple timing fields found {found} — must have exactly one of: "
                     "time, timePerPlayer, timePerRound")

    def _check_tutorial_pattern(self):
        """Check the beforeLoopActions tutorial createMixVote (and setImagesRow placement)."""
        bla = self.data.get("beforeLoopActions", [])
        if not isinstance(bla, list):
            return

        tutorial_idx = None
        tutorial_vote = None
        for i, action in enumerate(bla):
            if not isinstance(action, dict) or action.get("key") != "createMixVote":
                continue
            svc_names = {e.get("name") for e in action.get("saveValueInCache", []) if isinstance(e, dict)}
            if "learners" in svc_names and "tutorial" in svc_names:
                tutorial_idx, tutorial_vote = i, action
                break

        if tutorial_vote is None:
            self.err("beforeLoopActions",
                     "No tutorial createMixVote found — every game must include a tutorial vote "
                     "that saves 'learners' and 'tutorial' to cache. Copy it verbatim from emeralds.json.")
            return

        # Check 1: matches emeralds reference (excluding cosmetic colors).
        # Only compares payload (must match exactly) and the first N saveValueInCache entries
        # (must match the emeralds base entries in order; extra game-specific entries are allowed).
        ref_data = self._get_emeralds()
        if ref_data:
            ref = self._find_tutorial_vote_in(ref_data)
            if ref is not None:
                payload_ok = (self._strip_tutorial_hoistable(tutorial_vote.get("payload")) ==
                              self._strip_tutorial_hoistable(ref.get("payload")))
                ref_svc = ref.get("saveValueInCache", [])
                actual_svc = tutorial_vote.get("saveValueInCache", [])
                svc_ok = actual_svc[:len(ref_svc)] == ref_svc
                if not payload_ok or not svc_ok:
                    self.err(f"beforeLoopActions[{tutorial_idx}]",
                             "Tutorial createMixVote does not match the emeralds.json reference "
                             "(excluding backgroundColor, borderColor, textColor). "
                             "Copy it verbatim from emeralds.json and only change cosmetic colors.")

        # Check 2: any setImagesRow in beforeLoopActions must appear AFTER the tutorial vote
        for j, action in enumerate(bla):
            if isinstance(action, dict) and action.get("key") == "setImagesRow" and j < tutorial_idx:
                self.err(f"beforeLoopActions[{j}]",
                         f"setImagesRow at index {j} appears before the tutorial createMixVote "
                         f"(index {tutorial_idx}). Move setImagesRow to after the tutorial vote "
                         "so the card-hand area is only visible once actual gameplay begins.")

    def _check_tutorial_group(self):
        """At least one tutorial gameLoop group must set tutorial: false somewhere in its actions."""
        game_loop = self.data.get("gameLoop", [])
        if not isinstance(game_loop, list):
            return

        tutorial_groups = [g for g in game_loop
                           if isinstance(g, dict) and self._skip_refs_tutorial(g.get("skipCondition"))]
        if not tutorial_groups:
            return  # No tutorial groups found; _check_tutorial_pattern already warned

        def sets_tutorial_false(action):
            svc = action.get("saveValueInCache", []) if isinstance(action, dict) else []
            return any(isinstance(e, dict) and e.get("name") == "tutorial" and e.get("value") is False
                       for e in svc)

        # Only enforce the tutorial: false reset for notification-based tutorials.
        # Games that use createConversationGroup for tutorial narration have a different
        # lifecycle (conversation groups run per-round intentionally).
        uses_notifications = any(
            isinstance(a, dict) and a.get("key") == "createNotification"
            for g in tutorial_groups for a in g.get("actions", [])
        )
        if not uses_notifications:
            return  # Conversation-group or other tutorial mechanism; skip

        any_resets = any(
            any(sets_tutorial_false(a) for a in g.get("actions", []))
            for g in tutorial_groups
        )
        if not any_resets:
            i = game_loop.index(tutorial_groups[-1])
            self.err(f"gameLoop[{i}]",
                     "No action in any tutorial group sets tutorial: false in saveValueInCache. "
                     "The last tutorial group must include an emptyAction with "
                     "{\"name\": \"tutorial\", \"value\": false} to prevent the tutorial "
                     "from replaying every round.")

    def _check_end_of_round_vote(self):
        """End-of-round play-again vote must use the standard emeralds targets and saveValueInCache.
        Only enforced when the vote already uses the emeralds pattern (saves 'reset' as well as 'playAgain')."""
        actual = self._find_end_of_round_vote_in(self.data)
        if actual is None:
            return  # Not a rounds-based game; skip

        # Only apply checks if the game claims to follow the emeralds pattern
        # (saves both playAgain and reset — games with different mechanisms are exempt)
        svc_names = {e.get("name") for e in actual.get("saveValueInCache", []) if isinstance(e, dict)}
        if "reset" not in svc_names:
            return  # Different play-again mechanism; skip

        # Per-game exception: Interference deliberately renames the two non-quit targets
        # to "Reset scores, shuffle teams" / "Keep scores, keep teams" because choosing
        # to keep scores also keeps teams (no reshuffle that round). The renamed targets
        # propagate into the saveValueInCache 'reset' lookup string, so both checks
        # below would fire — skip them for this game only.
        source_basename = os.path.basename(self._source_path) if getattr(self, "_source_path", None) else ""
        if source_basename == "interference.json":
            return

        # Check 1: targets must be exactly the three standard options
        targets = (actual.get("payload", {}).get("preset", {}) or {}).get("targets")
        expected_targets = ["Reset scores", "Keep scores", "I'M SO DONE"]
        if targets != expected_targets:
            self.err("gameLoop (end-of-round host vote)",
                     f"End-of-round vote 'targets' must be exactly {expected_targets}. "
                     f"Got: {targets}. Copy the vote verbatim from emeralds.json.")

        # Check 2: saveValueInCache logic must match emeralds exactly
        ref_data = self._get_emeralds()
        if ref_data:
            ref = self._find_end_of_round_vote_in(ref_data)
            if ref is not None:
                actual_svc = actual.get("saveValueInCache")
                ref_svc = ref.get("saveValueInCache")
                if actual_svc != ref_svc:
                    self.err("gameLoop (end-of-round host vote)",
                             "End-of-round vote saveValueInCache (playAgain/reset logic) does not match "
                             "the emeralds.json reference. Copy it verbatim from emeralds.json.")

    def _check_post_game_notification(self):
        """For individual games, the postGameActions winner notification must use the standard structure."""
        if "winCondition" in self.data:
            return  # Team game — allow variety in the winner announcement
        if "playersWinCondition" not in self.data:
            return
        actual, actual_path = None, None
        for i, action in enumerate(self.data.get("postGameActions", [])):
            if isinstance(action, dict) and action.get("key") == "createNotification":
                actual, actual_path = action, f"postGameActions[{i}]"
                break
        if actual is None:
            return

        # The header must handle ties. Two acceptable patterns:
        #   (A) Player-name pattern (Emeralds): formatString using cached 'winner' as arg1
        #       and an ifElse for 'wins'/'share the win' as arg2.
        #   (B) Team / custom pattern: header is an ifElse selector at the top level (so the
        #       branches inherently choose between two winners and a tie message).
        header = (actual.get("payload", {}).get("computed", {}) or {}).get("header")
        ok = False
        if isinstance(header, dict):
            sel = header.get("selector")
            if sel == "formatString":
                params_by_name = {p.get("name"): p for p in header.get("params", []) if isinstance(p, dict)}
                arg1 = params_by_name.get("arg1", {})
                arg2 = params_by_name.get("arg2", {})
                arg1_ok = arg1.get("type") == "cached" and arg1.get("value") == "winner"
                arg2_val = arg2.get("value") if isinstance(arg2, dict) else None
                arg2_ok = isinstance(arg2_val, dict) and arg2_val.get("selector") == "ifElse"
                ok = arg1_ok and arg2_ok
            elif sel == "ifElse":
                # Team-style winner text built from an ifElse on team scores. Trust that the
                # author handled ties in the elseValue (which should itself be an ifElse or
                # a literal tie string).
                ok = True

        if not ok:
            self.err(actual_path,
                     "postGameActions winner notification header must handle ties. Two acceptable "
                     "patterns: (A) Emeralds-style — formatString using cached 'winner' as arg1 "
                     "and an ifElse for 'wins'/'share the win' as arg2. (B) Team-style — a top-level "
                     "ifElse selector whose branches choose between team-win strings and a tie message.")

    # ── Helpers for the type-consistency checks ───────────────────────────────

    @staticmethod
    def _is_preset_value(v: Any) -> bool:
        """True if v is a valid preset value: scalar, or a list/dict built from scalars.
        A dict that contains a 'selector' key is a computed/selector object, not a preset."""
        if isinstance(v, (str, int, float, bool)) or v is None:
            return True
        if isinstance(v, dict):
            if "selector" in v:
                return False  # this is a selector/computed object
            return all(Validator._is_preset_value(val) for val in v.values())
        if isinstance(v, list):
            return all(Validator._is_preset_value(item) for item in v)
        return False

    def _collect_gameinit_cache_names(self) -> tuple:
        """Names the engine writes into cache from gameInitOptions before the game
        loop runs, so they are valid cached references without a saveValueInCache:
          - configVariables[].name  → host-config values (scalars)
          - strings[<variant>][<var>] → the chosen variant's strings (Android
            strings.xml-style). At game start the host picks a variant and every
            variable in strings[variant] is written to cache under its var name.
        Returns (names:set, types:dict[name -> 'list'|'scalar'|'unknown'])."""
        names: set = set()
        types: dict = {}
        if not isinstance(self.data, dict):
            return names, types
        gio = self.data.get("gameInitOptions")
        if not isinstance(gio, dict):
            return names, types
        cfg = gio.get("configVariables")
        if isinstance(cfg, list):
            for entry in cfg:
                if isinstance(entry, dict) and isinstance(entry.get("name"), str):
                    root = entry["name"].split(".")[0]
                    names.add(root)
                    types[root] = "scalar"
        strings = gio.get("strings")
        if isinstance(strings, dict):
            for variant, mapping in strings.items():
                if not isinstance(mapping, dict):
                    continue
                for vname, val in mapping.items():
                    if not isinstance(vname, str):
                        continue
                    root = vname.split(".")[0]
                    names.add(root)
                    shape = "list" if isinstance(val, list) else (
                        "scalar" if isinstance(val, (str, int, float, bool)) else "unknown")
                    if root in types and types[root] != shape:
                        types[root] = "unknown"
                    else:
                        types.setdefault(root, shape)
        return names, types

    def _collect_cache_names(self, obj: Any) -> set:
        """Walk the whole document and collect every name saved via saveValueInCache."""
        names: set = set()
        if isinstance(obj, dict):
            svc = obj.get("saveValueInCache")
            if isinstance(svc, list):
                for entry in svc:
                    if isinstance(entry, dict) and isinstance(entry.get("name"), str):
                        # Store the root name (e.g. "players" from "players.0")
                        names.add(entry["name"].split(".")[0])
            for v in obj.values():
                names.update(self._collect_cache_names(v))
        elif isinstance(obj, list):
            for item in obj:
                names.update(self._collect_cache_names(item))
        return names

    def _classify_cache_value(self, value: Any) -> str:
        """Return 'list', 'scalar', or 'unknown' for a saveValueInCache value."""
        if isinstance(value, list):
            return "list"
        if isinstance(value, dict):
            sel_name = value.get("selector")
            if sel_name in _LIST_RETURNING_SELECTORS:
                return "list"
            if sel_name in _SCALAR_RETURNING_SELECTORS:
                return "scalar"
            return "unknown"
        return "scalar"  # string/number/bool literal

    def _collect_cache_types(self, obj: Any, out: dict):
        """Pre-pass: build a {cache_name: 'list'|'scalar'|'unknown'} map from every
        saveValueInCache entry. If the same name gets assigned different shapes,
        the result is 'unknown'."""
        if isinstance(obj, dict):
            svc = obj.get("saveValueInCache")
            if isinstance(svc, list):
                for entry in svc:
                    if isinstance(entry, dict) and isinstance(entry.get("name"), str):
                        root = entry["name"].split(".")[0]
                        shape = self._classify_cache_value(entry.get("value"))
                        if root in out and out[root] != shape:
                            out[root] = "unknown"
                        else:
                            out[root] = shape
            for v in obj.values():
                self._collect_cache_types(v, out)
        elif isinstance(obj, list):
            for item in obj:
                self._collect_cache_types(item, out)

    def _check_cached_ref(self, ref: str, path: str):
        """Verify that the root variable of a cache reference was actually saved to cache."""
        root = ref.split(".")[0].split("[")[0]
        if root in self.cache_vars:
            return
        # 'winner' is set by winCondition / playersWinCondition and is only valid in postGameActions
        if root == "winner" and path.startswith("postGameActions"):
            return
        self.err(path, f"Cached reference '{ref}' uses root variable '{root}' which was never "
                       f"saved to cache and is not a built-in Ludio variable. "
                       f"Check for a typo or a missing saveValueInCache entry.")

    def _walk(self, obj: Any, path: str):
        if isinstance(obj, dict):
            if "selector" in obj and isinstance(obj["selector"], str):
                self._check_selector(obj, path)
            if "key" in obj and isinstance(obj["key"], str):
                self._check_action(obj, path)
                self._check_structural(obj, path)
            if "name" in obj and "actions" in obj and "key" not in obj:
                self._check_action_group(obj, path)
            if "skipCondition" in obj:
                self._check_skip_condition_shape(obj["skipCondition"], f"{path}.skipCondition")

            # Free vars must never be saved to cache under their own name
            svc = obj.get("saveValueInCache")
            if isinstance(svc, list):
                for i, entry in enumerate(svc):
                    if isinstance(entry, dict):
                        name = entry.get("name")
                        if name in FREE_VARS_NO_SAVE:
                            self.err(f"{path}.saveValueInCache[{i}]",
                                     f"'{name}' is a free engine variable — it is provided automatically "
                                     f"by Ludio and must never be saved to cache. "
                                     f"Remove this saveValueInCache entry.")
                        # The 'value' field on a saveValueInCache entry must be either a
                        # literal (string/number/bool/list/dict-without-selector) or a
                        # selector object {"selector": ..., "params": [...]}. A param-shape
                        # dict ({"name": ..., "type": ..., "value": ...}) is meant for
                        # selector params and silently breaks at runtime when used as a
                        # cache value.
                        if "value" in entry and isinstance(entry["value"], dict):
                            v = entry["value"]
                            looks_like_param = ("type" in v and v.get("type") in VALID_PARAM_TYPES
                                                and "selector" not in v
                                                and "value" in v
                                                and "name" in v)
                            if looks_like_param:
                                self.err(f"{path}.saveValueInCache[{i}]",
                                         f"'value' for cache variable '{name}' looks like a param dict "
                                         f"(type={v.get('type')!r}, value={v.get('value')!r}). "
                                         "saveValueInCache values must be either a literal "
                                         "(string/number/bool/list) or a selector object "
                                         '{"selector": ..., "params": [...]}. To copy from another '
                                         "cached variable, wrap with getCachedValue: "
                                         '{"selector": "getCachedValue", '
                                         '"params": [{"name": "name", "type": "preset", "value": "<src>"}]}.')

            for k, v in obj.items():
                self._walk(v, f"{path}.{k}" if path else k)
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                self._walk(v, f"{path}[{i}]")

    def _param_names(self, params: list, path: str) -> List[str]:
        names = []
        for i, p in enumerate(params):
            pp = f"{path}.params[{i}]"
            if not isinstance(p, dict):
                self.err(pp, "Param must be a JSON object"); continue
            if "name" not in p:
                self.err(pp, "Param missing 'name' field"); continue

            ptype = p.get("type")
            pval  = p.get("value")
            pname = p["name"]

            if "type" not in p:
                self.err(pp, "Param missing 'type' field")
            elif ptype not in VALID_PARAM_TYPES:
                self.err(pp, f"Param type '{ptype}' is invalid — must be preset, cached, or computed")

            if "value" not in p:
                self.err(pp, "Param missing 'value' field")

            # ── Type-value consistency ────────────────────────────────────────
            if ptype in VALID_PARAM_TYPES and "value" in p:
                if ptype == "preset":
                    if not self._is_preset_value(pval):
                        self.err(pp, f"Param '{pname}' has type='preset' but value is not a preset value "
                                     f"(got {repr(pval)[:80]}). Preset values are strings, numbers, booleans, "
                                     f"lists, or dicts — not selector objects. "
                                     f"Did you mean type='computed'?")
                elif ptype == "cached":
                    if not isinstance(pval, str):
                        self.err(pp, f"Param '{pname}' has type='cached' but value is not a string "
                                     f"(got {repr(pval)[:80]}). Cached values must be cache-key strings "
                                     f"like 'players' or 'host.0'. "
                                     f"Did you mean type='computed' (selector) or type='preset' (literal)?")
                    else:
                        self._check_cached_ref(pval, pp)
                elif ptype == "computed":
                    if not (isinstance(pval, dict) and "selector" in pval):
                        self.err(pp, f"Param '{pname}' has type='computed' but value is not a selector object "
                                     f"(got {repr(pval)[:80]}). Computed values must be "
                                     f'{{\"selector\": \"...\", \"params\": [...]}}. '
                                     f"Did you mean type='preset' (literal) or type='cached' (cache key)?")
                    elif isinstance(pval, dict) and pval.get("selector") == "getCachedValue":
                        # Warn: type="computed" wrapping getCachedValue is verbose — use type="cached" directly.
                        inner_params = pval.get("params", [])
                        if (len(inner_params) == 1
                                and isinstance(inner_params[0], dict)
                                and inner_params[0].get("name") == "name"
                                and inner_params[0].get("type") == "preset"
                                and isinstance(inner_params[0].get("value"), str)):
                            cached_name = inner_params[0]["value"]
                            self.warn(pp, f"Param '{pname}' uses verbose getCachedValue wrapper — "
                                          f"replace with type='cached', value='{cached_name}'.")

            names.append(p["name"])
        return names

    def _check_selector(self, obj: dict, path: str):
        sel = obj["selector"]
        params = obj.get("params", [])

        if sel not in SELECTORS:
            self.err(path, f"Unknown selector '{sel}'")
            return

        spec = SELECTORS[sel]
        names = self._param_names(params, path)

        # Warn: add/subtract by a preset literal 1 → use inc/dec instead
        if sel in ("add", "subtract"):
            preset_vals = [p.get("value") for p in params if isinstance(p, dict) and p.get("type") == "preset"]
            if 1 in preset_vals:
                replacement = "inc" if sel == "add" else "dec"
                self.warn(path, f"'{sel}' with a preset value of 1 — use '{replacement}(arg)' instead.")

        # Error: equals/notEquals with a boolean preset argument. Ludio's
        # equals/notEquals only compare numbers and strings — comparing a
        # boolean cache var against true/false is a no-op at runtime. Use
        # getCachedValue (or wrap with logicalNOT for "is false") directly.
        if sel in ("equals", "notEquals"):
            for p in params:
                if isinstance(p, dict) and p.get("type") == "preset" and isinstance(p.get("value"), bool):
                    self.err(path, f"Selector '{sel}' has a boolean preset argument "
                                   f"(value={p['value']}). equals/notEquals only work on numbers "
                                   f"and strings. To check if a cached boolean is true, use it "
                                   f"directly via getCachedValue (or via type='cached'); to "
                                   f"check if it is false, wrap with logicalNOT.")
                    break

        if spec.get("variadic"):
            return  # Any names are fine

        if spec.get("zero"):
            if names:
                self.err(path, f"Selector '{sel}' takes no params but got: {names}")
            return

        required = spec.get("params", [])
        optional = spec.get("optional", [])
        variadic_extra = spec.get("variadic_extra", False)
        zero_or_optional = spec.get("zero_or_optional", False)

        # Check all required params present
        for req in required:
            if req not in names:
                self.err(path, f"Selector '{sel}' missing required param '{req}' (got: {names})")

        # Check no unexpected params (unless variadic_extra allows extras after required)
        if not variadic_extra and not zero_or_optional:
            allowed = set(required) | set(optional)
            for n in names:
                if n not in allowed:
                    self.err(path, f"Selector '{sel}' has unexpected param '{n}' (allowed: {sorted(allowed)})")
        elif variadic_extra:
            # Only the required ones are enforced; extras are fine
            pass

    def _payload_fields(self, payload: Any) -> set:
        fields = set()
        if isinstance(payload, dict):
            for section in ("preset", "cached", "computed"):
                if section in payload and isinstance(payload[section], dict):
                    fields.update(payload[section].keys())
        return fields

    def _check_action(self, obj: dict, path: str):
        key = obj["key"]
        payload = obj.get("payload", {})

        # Canonical field ordering on the action itself and on its payload.
        self._check_field_order(obj, ACTION_FIELD_ORDER, path, "action")
        if isinstance(payload, dict):
            self._check_field_order(payload, PAYLOAD_SECTION_ORDER, f"{path}.payload", "payload")

        if key not in ACTIONS:
            self.err(path, f"Unknown action key '{key}'")
            return

        spec = ACTIONS[key]
        fields = self._payload_fields(payload)

        # hidePlayersHands.userIds expects a LIST of player IDs. Common bug: pass
        # a single-player cache var (e.g. "robber_crook_player") which resolves to
        # a string scalar. The action silently no-ops in that case.
        if key == "hidePlayersHands" and isinstance(payload, dict):
            preset_s = payload.get("preset") if isinstance(payload.get("preset"), dict) else {}
            cached_s = payload.get("cached") if isinstance(payload.get("cached"), dict) else {}
            computed_s = payload.get("computed") if isinstance(payload.get("computed"), dict) else {}

            if preset_s and "userIds" in preset_s and not isinstance(preset_s["userIds"], list):
                self.err(path, "hidePlayersHands.preset.userIds must be a list of player IDs.")

            if cached_s and isinstance(cached_s.get("userIds"), str):
                src = cached_s["userIds"].split(".")[0]
                shape = self.cache_types.get(src)
                if shape == "scalar":
                    self.err(path,
                             f"hidePlayersHands.cached.userIds = '{cached_s['userIds']}' "
                             f"points to a SCALAR cache value, but userIds must be a LIST "
                             f"of player IDs. Wrap with createList in 'computed', or use a "
                             f"plural cache variable (e.g. 'activeRobbers', 'players').")

            if computed_s and isinstance(computed_s.get("userIds"), dict):
                cv = computed_s["userIds"]
                csel = cv.get("selector")
                if csel and csel not in _LIST_RETURNING_SELECTORS and csel not in ("ifElse", "getCachedValue"):
                    self.err(path,
                             f"hidePlayersHands.computed.userIds uses selector '{csel}' which "
                             f"returns a scalar. userIds must be a LIST of player IDs.")

        # playCards.playable must be the literal string "availableCards" or
        # "allAvailable" — not a list of card names. To restrict which cards
        # are playable, use playableInclude.cards / playableExclude.cards
        # alongside playable: "availableCards".
        if key == "playCards" and isinstance(payload, dict):
            preset_s = payload.get("preset") if isinstance(payload.get("preset"), dict) else {}
            playable_val = preset_s.get("playable") if preset_s else None
            if playable_val is not None and playable_val not in ("availableCards", "allAvailable"):
                self.err(path,
                         f"playCards 'playable' must be the literal string "
                         f"'availableCards' or 'allAvailable' (got {playable_val!r}). "
                         "To limit which cards can be played, use 'availableCards' plus "
                         "'playableInclude.cards' (whitelist) or 'playableExclude.cards' "
                         "(blacklist) — both are lists of card names. See roundabout.json "
                         "for the canonical pattern.")

        # postHandler must not live inside payload
        if isinstance(payload, dict):
            for section in ("preset", "cached", "computed"):
                if section in payload and isinstance(payload[section], dict):
                    if "postHandler" in payload[section]:
                        self.err(path, f"'postHandler' found inside payload.{section} — it must be a top-level field on the action object")

        # updateScore: secondScore must be a field INSIDE the score dict (alongside
        # list / score / delta), NOT in payload.preset. The action accepts a
        # `scores` array of dicts shaped like
        # {list:[...], score:N, secondScore:true} or {list:[...], delta:N, secondScore:true}.
        # Putting `secondScore: true` in preset silently no-ops — the primary
        # score updates instead of the secondScore. See emeralds.json / topaz_25.json
        # for the canonical pattern (keys: ["list","score","secondScore"]).
        if key == "updateScore" and isinstance(payload, dict):
            preset_s = payload.get("preset") if isinstance(payload.get("preset"), dict) else {}
            if preset_s and "secondScore" in preset_s:
                self.err(path,
                         "updateScore has 'secondScore' in payload.preset — this is silently "
                         "ignored. Move it INTO the score dict alongside 'list' and "
                         "'score'/'delta': add 'secondScore' to the createDict 'keys' array "
                         "and 'true' to the matching 'values' array. See emeralds.json / "
                         "topaz_25.json.")

        # Required fields
        for req in spec.get("required", []):
            if req not in fields:
                self.err(path, f"Action '{key}' missing required payload field '{req}' (present: {sorted(fields)})")

        # Extract payload sections for per-action checks
        preset_s   = payload.get("preset",   {}) if isinstance(payload, dict) else {}
        cached_s   = payload.get("cached",   {}) if isinstance(payload, dict) else {}
        computed_s = payload.get("computed", {}) if isinstance(payload, dict) else {}

        # sounds.list entries must not be bare names — they need a namespace prefix (e.g. soundboard.X, voices.X)
        sounds_list = (preset_s or {}).get("sounds.list")
        if not isinstance(sounds_list, list):
            sounds_list = (computed_s or {}).get("sounds.list")  # may also appear in computed via ifElse
        if isinstance(sounds_list, list):
            for entry in sounds_list:
                if isinstance(entry, str) and entry and "." not in entry:
                    self.err(path, f"sounds.list entry '{entry}' has no namespace prefix — use 'soundboard.{entry}' (or 'voices.{entry}' etc.)")

        # Sound requires sounds.list + playList.X together. sounds.waitForSoundEnd is optional (defaults to false).
        has_sl = "sounds.list" in (preset_s or {}) or "sounds.list" in (computed_s or {})
        has_sw = "sounds.waitForSoundEnd" in (preset_s or {})
        # playList.X may be in cached (static list) or computed (dynamic list)
        has_pl = (any(k.startswith("playList.") for k in (cached_s or {})) or
                  any(k.startswith("playList.") for k in (computed_s or {})))
        if has_sl or has_sw or has_pl:
            if not has_sl:
                self.err(path, "Sound incomplete: 'sounds.list' missing — "
                         "both sounds.list (preset or computed) and playList.X (cached or computed) "
                         "must be present for sound to reach players.")
            if not has_pl:
                self.err(path, "Sound incomplete: no 'playList.X' key in payload.cached or computed — "
                         "both sounds.list and playList.X must be present for sound to reach players.")

        # allUsers must not be used as the 'to' target in createNotification or setLabelInspectors
        if key in ("createNotification", "setLabelInspectors"):
            to_val = (computed_s or {}).get("to")
            if isinstance(to_val, dict) and to_val.get("selector") == "allUsers":
                self.err(path, f"'{key}' uses '{{\"selector\": \"allUsers\"}}' for the 'to' field. "
                         "Spectators receive notifications automatically — use "
                         "cached: {{\"to\": \"players\"}} instead.")

        # createVote/createMixVote postHandler checks
        post_handler = obj.get("postHandler")
        if key in ("createVote", "createMixVote") and post_handler:
            svc = obj.get("saveValueInCache", [])
            if isinstance(svc, list):
                for i, entry in enumerate(svc):
                    if isinstance(entry, dict) and self._refs_vote_result(entry.get("value")):
                        self.err(f"{path}.saveValueInCache[{i}]",
                                 f"'{key}' has postHandler '{post_handler}', so lastActionResult IS the "
                                 "list of winners directly — there is no .voteResult field. "
                                 "Use 'lastActionResult' (not 'lastActionResult.voteResult') when reading results.")
            if post_handler == "randomSelectNeededVoters":
                all_fields = self._payload_fields(payload)
                if "neededVoters" not in all_fields:
                    self.err(path, f"'{key}' uses postHandler 'randomSelectNeededVoters' but 'neededVoters' "
                             "is missing from the payload. Add it (e.g. preset: {{\"neededVoters\": N}}) "
                             "to specify how many random targets to select.")

        # createGenericCardWidget: dimensions[0] * dimensions[1] must be >= len(decks)
        if key == "createGenericCardWidget":
            dims_preset   = (preset_s   or {}).get("dimensions")
            dims_computed = (computed_s or {}).get("dimensions")
            decks_preset  = (preset_s   or {}).get("decks")
            decks_computed = (computed_s or {}).get("decks")
            # Only check when decks is a static list — if decks is computed it's assumed to scale correctly
            if isinstance(decks_preset, list) and decks_computed is None:
                if (isinstance(dims_preset, list) and len(dims_preset) == 2
                        and all(isinstance(d, (int, float)) for d in dims_preset)):
                    # Both static: capacity must be >= deck count
                    capacity = int(dims_preset[0]) * int(dims_preset[1])
                    if capacity < len(decks_preset):
                        self.err(path,
                                 f"createGenericCardWidget dimensions {dims_preset} only fit {capacity} deck(s) "
                                 f"but 'decks' has {len(decks_preset)} entries — "
                                 f"increase dimensions so rows × columns >= {len(decks_preset)}.")
                elif dims_computed is not None:
                    # dimensions is dynamic but decks is a fixed-length list — they won't scale together
                    self.err(path,
                             f"createGenericCardWidget 'dimensions' is computed dynamically but 'decks' is a "
                             f"static list of {len(decks_preset)} entries. The grid capacity will vary with "
                             f"player count but the deck list won't — use a computed sublist for 'decks' "
                             f"(e.g. sublist(allDecks, 0, rows * columns)) to match the actual grid size.")

        # One-of constraints
        for group in spec.get("one_of", []):
            if not any(f in fields for f in group):
                self.err(path, f"Action '{key}' requires at least one of {group} in payload")

        # Payload section type consistency
        self._check_payload_types(payload, path)

    def _check_payload_types(self, payload: Any, path: str):
        """Check that values in preset/cached/computed payload sections have appropriate types."""
        if not isinstance(payload, dict):
            return

        preset   = payload.get("preset",   {})
        cached   = payload.get("cached",   {})
        computed = payload.get("computed", {})

        if isinstance(preset, dict):
            for field, value in preset.items():
                if not self._is_preset_value(value):
                    self.err(path, f"payload.preset['{field}'] = {repr(value)[:80]} is not a preset value. "
                                   f"Preset values are strings, numbers, booleans, lists, or dicts — "
                                   f"not selector objects. Did you mean to put this in 'computed'?")

        if isinstance(cached, dict):
            for field, value in cached.items():
                if not isinstance(value, str):
                    self.err(path, f"payload.cached['{field}'] = {repr(value)[:80]} is not a string. "
                                   f"Cached section values must be cache-key strings like 'players' or 'host.0'. "
                                   f"Did you mean to put this in 'computed' (selector) or 'preset' (literal)?")
                else:
                    self._check_cached_ref(value, f"{path}.payload.cached['{field}']")

        if isinstance(computed, dict):
            for field, value in computed.items():
                if not (isinstance(value, dict) and "selector" in value):
                    self.err(path, f"payload.computed['{field}'] = {repr(value)[:80]} is not a selector object. "
                                   f"Computed section values must be selector objects "
                                   f'{{\"selector\": \"...\", \"params\": [...]}}. '
                                   f"Did you mean to put this in 'preset' (literal) or 'cached' (cache key)?")

    def _check_field_order(self, d: Any, canonical: List[str], path: str, label: str):
        """Warn if keys of `d` that appear in `canonical` aren't in canonical order.
        Keys NOT in `canonical` are ignored — only the relative ordering of listed
        keys is enforced. JSON load and Python dict preserve insertion order, so
        d.keys() reflects the on-disk ordering."""
        if not isinstance(d, dict):
            return
        pos = {f: i for i, f in enumerate(canonical)}
        last_idx = -1
        last_key = None
        for k in d.keys():
            if k not in pos:
                continue
            idx = pos[k]
            if idx < last_idx:
                self.warn(path,
                          f"{label} field '{k}' appears after '{last_key}' but the "
                          f"canonical order is {canonical}. Reorder this {label}'s keys.")
                return
            last_idx = idx
            last_key = k

    def _check_action_group(self, obj: dict, path: str):
        allowed = {"name", "repeat", "parallel", "skipCondition", "actions", "checkWinCondition",
                   "turnPlayersToSpectators", "turnSpectatorsToPlayers", "nextGroupNonStop"}
        for k in obj.keys():
            if k not in allowed:
                self.err(path, f"Action group '{obj['name']}' has unexpected field '{k}' (allowed: {sorted(allowed)})")

        self._check_field_order(obj, GROUP_FIELD_ORDER, path, "action group")

        # Validate repeat block structure
        if "repeat" in obj:
            r = obj["repeat"]
            if not isinstance(r, dict):
                self.err(path, "repeat block must be an object")
            else:
                extra = [k for k in r if k != "qnt"]
                if extra:
                    self.err(path, f"repeat block has unexpected fields {extra} — only 'qnt' is allowed. "
                             "'repeatIndex' is provided for free inside the group and must not be declared.")
                if "qnt" in r:
                    q = r["qnt"]
                    if isinstance(q, dict) and "type" in q and "selector" not in q:
                        self.err(path, f"repeat.qnt uses parameter syntax {{\"type\": \"{q.get('type')}\", ...}} "
                                 "which is invalid here — qnt must be a literal integer or a computed selector object "
                                 "{{\"selector\": ..., \"params\": [...]}}")

        # Validate parallel block structure
        # Three parallel types:
        #   smart       — runs N copies of the same group; requires 'qnt'. spaIndex tracks copy index.
        #   independent — runs several different groups in parallel (declared as separate top-level
        #                 groups, each with parallel.type='independent'). Last group in the series
        #                 must carry isLast: true.
        #   dependent   — like independent, but supports cross-group termination via 'conditions'.
        #                 Last group must carry isLast: true.
        if "parallel" in obj:
            p = obj["parallel"]
            if not isinstance(p, dict):
                self.err(path, "parallel block must be an object")
            else:
                ptype = p.get("type")
                if ptype == "smart":
                    allowed_parallel = {"type", "qnt"}
                elif ptype == "independent":
                    allowed_parallel = {"type", "isLast"}
                elif ptype == "dependent":
                    allowed_parallel = {"type", "conditions", "isLast"}
                else:
                    allowed_parallel = {"type", "qnt", "isLast", "conditions"}  # fall back to permissive
                    if ptype is not None:
                        self.err(path, f"parallel.type '{ptype}' is invalid — must be 'smart', 'independent', or 'dependent'.")
                extra = [k for k in p if k not in allowed_parallel]
                if extra:
                    self.err(path, f"parallel block (type={ptype!r}) has unexpected fields {extra} — "
                             f"allowed fields for this type: {sorted(allowed_parallel)}. "
                             "Note: 'spaIndex' is provided for free inside smart parallel groups and must not be declared.")
                if ptype == "smart" and "qnt" not in p:
                    self.err(path, "parallel type='smart' is missing required 'qnt' field — "
                             "smart parallel runs N copies of the same group and needs the count.")
                if "qnt" in p:
                    q = p["qnt"]
                    if isinstance(q, dict) and "type" in q and "selector" not in q:
                        self.err(path, f"parallel.qnt uses parameter syntax {{\"type\": \"{q.get('type')}\", ...}} "
                                 "which is invalid here — qnt must be a literal integer or a computed selector object "
                                 "{{\"selector\": ..., \"params\": [...]}}")

    # Threshold for the repeated-subexpression check. Subtrees smaller than this
    # canonical-JSON length are not worth hoisting (they're usually one-line
    # selectors like `allPlayers()` or `cached:foo` references already).
    REPEATED_SUBEXPR_MIN_SIZE = 80
    # Minimum number of identical occurrences before we warn. 2 is too noisy
    # (every pair of similar args trips it); 3 reliably indicates a real
    # readability problem worth fixing.
    REPEATED_SUBEXPR_MIN_COUNT = 3

    def _check_repeated_subexpressions(self):
        """Warn when the same selector subtree appears ≥3 times inside a single
        action (across both payload and saveValueInCache values). The smell is a
        giant ifElse / formatString / dict whose branches all start with the
        same getCachedObjectValue / getCachedValue / selectElement lookup — that
        block should be hoisted to a `saveValueInCache` temp BEFORE the action
        and referenced via `type='cached'` inside the expression.

        Example: C&R's `robberToDestDecks` action recomputed
        `getCachedObjectValue(posByPlayer, currentPlayer)` 15 times inside a
        single ifElse. That subtree was just `currentPos` (which already
        existed as a cache var); inlining it 15× added ~3KB and obscured the
        actual logic.

        Implementation: canonicalize every selector subtree to sorted-key JSON,
        count occurrences per action, warn on the worst offender per action
        (one warning per action keeps the output focused on the next fix).
        """
        def collect(node, out):
            if isinstance(node, dict):
                if isinstance(node.get("selector"), str):
                    out.append(node)
                for v in node.values():
                    collect(v, out)
            elif isinstance(node, list):
                for v in node:
                    collect(v, out)

        def describe(subtree):
            sel = subtree.get("selector", "?")
            parts = []
            for p in subtree.get("params", []):
                if not isinstance(p, dict):
                    continue
                n = p.get("name", "?")
                t = p.get("type")
                v = p.get("value")
                if t == "preset":
                    vs = repr(v)
                    if len(vs) > 24:
                        vs = vs[:21] + "..."
                    parts.append(f"{n}={vs}")
                elif t == "cached":
                    parts.append(f"{n}=cached:{v}")
                elif t == "computed":
                    inner = v.get("selector", "?") if isinstance(v, dict) else "?"
                    parts.append(f"{n}={inner}(...)")
            return f"{sel}({', '.join(parts)})"

        def walk(node, path=""):
            if isinstance(node, dict):
                if isinstance(node.get("key"), str):
                    subtrees = []
                    payload = node.get("payload")
                    if payload is not None:
                        collect(payload, subtrees)
                    svc = node.get("saveValueInCache")
                    if isinstance(svc, list):
                        for entry in svc:
                            if isinstance(entry, dict) and "value" in entry:
                                collect(entry["value"], subtrees)

                    groups: dict = {}
                    for s in subtrees:
                        canon = json.dumps(s, sort_keys=True, separators=(",", ":"))
                        groups.setdefault(canon, []).append(s)

                    worst = None
                    for canon, instances in groups.items():
                        count = len(instances)
                        if count < self.REPEATED_SUBEXPR_MIN_COUNT:
                            continue
                        if len(canon) < self.REPEATED_SUBEXPR_MIN_SIZE:
                            continue
                        weight = count * len(canon)
                        if worst is None or weight > worst[0]:
                            worst = (weight, count, len(canon), instances[0])
                    if worst is not None:
                        _, count, size, sample = worst
                        self.warn(path,
                                  f"action '{node.get('key')}' inlines the same selector subtree "
                                  f"{count}× ({size}-char canonical form): {describe(sample)}. "
                                  "Hoist it to a saveValueInCache temp in an emptyAction BEFORE "
                                  "this action and reference via type='cached' — the action will "
                                  "shrink dramatically and read like the underlying logic. See "
                                  "feedback_cache_repeated_subexpressions.md for the pattern.")
                for k, v in node.items():
                    walk(v, f"{path}.{k}" if path else k)
            elif isinstance(node, list):
                for i, v in enumerate(node):
                    walk(v, f"{path}[{i}]")

        walk(self.data, "")

    def _check_videobox_decks_initialized(self):
        """If anything in gameLoop references 'videobox' (as a card movement target
        or deck name), beforeLoopActions must have called createVideoboxDecks. Without
        that init the per-player videobox decks don't exist and playCards/moveCards
        targeting them silently fail at runtime."""
        if not isinstance(self.data, dict):
            return

        before = self.data.get("beforeLoopActions") or []
        loop   = self.data.get("gameLoop") or []

        def has_create_videobox(actions):
            for a in actions:
                if isinstance(a, dict) and a.get("key") == "createVideoboxDecks":
                    return True
                # Search nested action lists too (groups, repeats, parallel)
                for child in (a.get("actions"),) if isinstance(a, dict) else ():
                    if isinstance(child, list) and has_create_videobox(child):
                        return True
            return False

        def mentions_videobox(node):
            if isinstance(node, str):
                return "videobox" in node
            if isinstance(node, dict):
                return any(mentions_videobox(v) for v in node.values())
            if isinstance(node, list):
                return any(mentions_videobox(v) for v in node)
            return False

        if not mentions_videobox(loop):
            return

        if not has_create_videobox(before):
            self.err("beforeLoopActions",
                     "gameLoop references 'videobox' (likely as a playCards target or "
                     "card movement to/from videobox_<player>), but beforeLoopActions "
                     "does not call createVideoboxDecks. Without this initialization "
                     "the per-player videobox decks don't exist and the action will "
                     "silently fail at runtime. Add createVideoboxDecks early in "
                     "beforeLoopActions — copy the pattern from roundabout.json.")


    def _check_skip_condition_shape(self, sc: Any, path: str):
        """skipCondition is either a single selector object or a list of them.
        A common mistake is to pass a raw param dict ({"name": ..., "type": "cached", "value": ...})
        which silently passes most validation but blows up at runtime with
        'invalid selector undefined' because no 'selector' key is present.
        """
        if isinstance(sc, dict):
            entries = [(sc, path)]
        elif isinstance(sc, list):
            entries = [(entry, f"{path}[{i}]") for i, entry in enumerate(sc)]
        else:
            self.err(path, f"skipCondition must be a selector object or list of them (got {type(sc).__name__})")
            return
        for entry, ep in entries:
            if not isinstance(entry, dict):
                self.err(ep, f"skipCondition entry must be a selector object (got {type(entry).__name__})")
                continue
            if "selector" not in entry:
                if "type" in entry and "value" in entry:
                    self.err(ep,
                             f"skipCondition entry is a param dict "
                             f"(type={entry.get('type')!r}, value={entry.get('value')!r}) "
                             "but skipCondition needs a selector object {\"selector\": ..., \"params\": [...]}. "
                             "Wrap the value in a selector like equals(cached_var, true) or logicalNOT(arg). "
                             "Otherwise Ludio errors at runtime with 'invalid selector undefined'.")
                else:
                    self.err(ep, "skipCondition entry is missing the 'selector' key — "
                             "each entry must be a selector object {\"selector\": ..., \"params\": [...]}.")

    def _check_structural(self, obj: dict, path: str):
        # repeat/parallel must not appear directly on an action object (one with a 'key')
        if "key" in obj:
            for bad in ("repeat", "parallel"):
                if bad in obj:
                    self.err(path, f"'{bad}' found on action object with key='{obj['key']}' — repeat/parallel belong on action groups (objects with 'name'+'actions'), not on individual actions")

        # Check that items inside an 'actions' array are not action-group objects
        # (i.e. objects with 'repeat'/'parallel' but no 'key' — those should be top-level groups)
        if "actions" in obj and isinstance(obj["actions"], list):
            for i, item in enumerate(obj["actions"]):
                if isinstance(item, dict) and not item.get("key") and ("repeat" in item or "parallel" in item):
                    self.err(f"{path}.actions[{i}]",
                             "Action group with repeat/parallel found inside an 'actions' array — "
                             "it must be extracted to the top-level gameLoop list")


# ─── Entry point ─────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 validate_game_json.py path/to/game.json")
        sys.exit(1)

    path = sys.argv[1]
    try:
        with open(path) as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"JSON parse error: {e}")
        sys.exit(1)
    except FileNotFoundError:
        print(f"File not found: {path}")
        sys.exit(1)

    v = Validator(data)
    v._source_path = os.path.abspath(path)
    errors, warnings = v.run()

    if not errors and not warnings:
        print(f"✓ No errors found in {path}")
        sys.exit(0)

    if errors:
        print(f"✗ {len(errors)} error(s) in {path}\n")
        for loc, msg in sorted(errors):
            print(f"  [{loc}]\n    {msg}\n")

    if warnings:
        print(f"⚠ {len(warnings)} warning(s) in {path}\n")
        for loc, msg in sorted(warnings):
            print(f"  [{loc}]\n    {msg}\n")

    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
