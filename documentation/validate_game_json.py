#!/usr/bin/env python3
"""
Ludio game JSON validator.
Usage:  python3 validate_game_json.py path/to/game.json
        python3 validate_game_json.py path/to/game.json --strict   # also warn on optional-param mismatches
"""

import json, sys
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
    "sublist":              {"params": ["list", "start", "end"]},
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
    "showPlayersHands":         {"required": ["userids"]},
    "hidePlayersHands":         {"required": ["userids"]},
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

# ─── Validator ────────────────────────────────────────────────────────────────

class Validator:
    def __init__(self, data: Any):
        self.data = data
        self.errors: List[Tuple[str, str]] = []

    def err(self, path: str, msg: str):
        self.errors.append((path, msg))

    def run(self) -> List[Tuple[str, str]]:
        self._walk(self.data, "")
        return self.errors

    def _walk(self, obj: Any, path: str):
        if isinstance(obj, dict):
            if "selector" in obj and isinstance(obj["selector"], str):
                self._check_selector(obj, path)
            if "key" in obj and isinstance(obj["key"], str):
                self._check_action(obj, path)
                self._check_structural(obj, path)
            if "name" in obj and "actions" in obj and "key" not in obj:
                self._check_action_group(obj, path)
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
            if "type" not in p:
                self.err(pp, "Param missing 'type' field")
            elif p["type"] not in VALID_PARAM_TYPES:
                self.err(pp, f"Param type '{p['type']}' is invalid — must be preset, cached, or computed")
            if "value" not in p:
                self.err(pp, "Param missing 'value' field")
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

        # One-of constraints
        for group in spec.get("one_of", []):
            if not any(f in fields for f in group):
                self.err(path, f"Action '{key}' requires at least one of {group} in payload")

    def _check_action_group(self, obj: dict, path: str):
        allowed = {"name", "repeat", "parallel", "skipCondition", "actions", "checkWinCondition",
                   "turnPlayersToSpectators", "turnSpectatorsToPlayers"}
        for k in obj.keys():
            if k not in allowed:
                self.err(path, f"Action group '{obj['name']}' has unexpected field '{k}' (allowed: {sorted(allowed)})")

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

    errors = Validator(data).run()

    if not errors:
        print(f"✓ No errors found in {path}")
        sys.exit(0)

    print(f"✗ {len(errors)} error(s) in {path}\n")
    # Group by path prefix for readability
    for loc, msg in sorted(errors):
        print(f"  [{loc}]\n    {msg}\n")
    sys.exit(1)


if __name__ == "__main__":
    main()
