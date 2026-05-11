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
    "showTeam":                 {"required": []},
    "showRole":                 {"required": []},
    "showFakeTeam":             {"required": []},
    "showTrueRoles":            {"required": []},
    "showFakeRole":             {"required": []},
    "showAllPlayersHands":      {"required": []},
    "hideAllPlayersHands":      {"required": []},
    "showPlayersHands":         {"required": ["userIds"]},
    "hidePlayersHands":         {"required": ["userIds"]},
    "hideInvisiblePlayers":     {"required": ["hide"]},
    "createTeamsConversationGroups": {"required": []},
    "muteTeam":                 {"required": []},
    "setRole":                  {"required": ["roleId", "playerId"]},
    "orderByTeam":              {"required": []},
    "hideRole":                 {"required": []},
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
    "createCustomDeck":         {"required": ["name"]},
    "shuffleDeck":              {"required": ["deck"]},
    "dealDeck":                 {"required": ["targets", "deck"]},
    "playCards":                {"required": ["actor", "target"]},
    "moveCards":                {"required": ["type", "from", "to"]},
    "recallCards":              {"required": ["targets", "deck"]},
    "discard":                  {"required": ["targets", "deck", "cards"]},
    "sortDeck":                 {"required": ["deck", "sortBy"]},
    "showHand":                 {"required": ["from", "to"]},
    "createGenericCardWidget":  {"required": ["dimensions", "decks", "cardback"]},
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

# Ludio variables always available in cache without explicit saveValueInCache
BUILTIN_CACHE_VARS = {
    "gameLoopIndex",     # current game-loop iteration index (0-based)
    "lastActionResult",  # result object from the previous action (.voteResult, .selectedDecks, etc.)
    "repeatIndex",       # current index inside a repeat{} block
    "spaIndex",          # current index inside a parallel{} block
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
                        "type": "computed",
                        "value": {
                            "selector": "selectElement",
                            "params": [
                                {"name": "list",  "type": "cached", "value": "players"},
                                {"name": "index", "type": "preset", "value": 0}
                            ]
                        }
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
        # Pre-pass: collect every variable name ever written to cache so we can
        # validate cached references in the main walk.
        self.cache_vars = self._collect_cache_names(self.data) | BUILTIN_CACHE_VARS
        self._walk(self.data, "")
        self._check_toplevel_patterns()
        return self.errors, self.warnings

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
        self._check_tutorial_pattern()
        self._check_tutorial_group()
        self._check_end_of_round_vote()
        self._check_post_game_notification()
        self._check_host_snippet()

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
                payload_ok = (self._strip_cosmetic(tutorial_vote.get("payload")) ==
                              self._strip_cosmetic(ref.get("payload")))
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

        # The header must be a formatString using 'winner' as arg1 and an ifElse for "wins"/"share the win"
        header = (actual.get("payload", {}).get("computed", {}) or {}).get("header")
        ok = False
        if isinstance(header, dict) and header.get("selector") == "formatString":
            params_by_name = {p.get("name"): p for p in header.get("params", []) if isinstance(p, dict)}
            arg1 = params_by_name.get("arg1", {})
            arg2 = params_by_name.get("arg2", {})
            arg1_ok = arg1.get("type") == "cached" and arg1.get("value") == "winner"
            arg2_val = arg2.get("value") if isinstance(arg2, dict) else None
            arg2_ok = isinstance(arg2_val, dict) and arg2_val.get("selector") == "ifElse"
            ok = arg1_ok and arg2_ok

        if not ok:
            self.err(actual_path,
                     "postGameActions winner notification header must be a formatString that uses "
                     "'winner' as arg1 and an ifElse (for 'wins' vs 'share the win') as arg2. "
                     "Copy it verbatim from emeralds.json to ensure ties are handled correctly.")

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
                        # Warn: type="computed" wrapping getCachedValue is verbose — use type="cached" directly
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

        if key not in ACTIONS:
            self.err(path, f"Unknown action key '{key}'")
            return

        spec = ACTIONS[key]
        fields = self._payload_fields(payload)

        # postHandler must not live inside payload
        if isinstance(payload, dict):
            for section in ("preset", "cached", "computed"):
                if section in payload and isinstance(payload[section], dict):
                    if "postHandler" in payload[section]:
                        self.err(path, f"'postHandler' found inside payload.{section} — it must be a top-level field on the action object")

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

    def _check_action_group(self, obj: dict, path: str):
        allowed = {"name", "repeat", "parallel", "skipCondition", "actions", "checkWinCondition",
                   "turnPlayersToSpectators", "turnSpectatorsToPlayers", "nextGroupNonStop"}
        for k in obj.keys():
            if k not in allowed:
                self.err(path, f"Action group '{obj['name']}' has unexpected field '{k}' (allowed: {sorted(allowed)})")

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
        if "parallel" in obj:
            p = obj["parallel"]
            if not isinstance(p, dict):
                self.err(path, "parallel block must be an object")
            else:
                allowed_parallel = {"type", "qnt"}
                extra = [k for k in p if k not in allowed_parallel]
                if extra:
                    self.err(path, f"parallel block has unexpected fields {extra} — only 'type' and 'qnt' are allowed. "
                             "'spaIndex' is provided for free inside the group and must not be declared.")
                if "qnt" in p:
                    q = p["qnt"]
                    if isinstance(q, dict) and "type" in q and "selector" not in q:
                        self.err(path, f"parallel.qnt uses parameter syntax {{\"type\": \"{q.get('type')}\", ...}} "
                                 "which is invalid here — qnt must be a literal integer or a computed selector object "
                                 "{{\"selector\": ..., \"params\": [...]}}")

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

    errors, warnings = Validator(data).run()

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
