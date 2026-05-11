# Things to Remember — Ludio Game Engine

## 1. JSON Structure, Setup & Flow

- **Architecture:** A game JSON has distinct sections: `gameInitOptions`, `visualSettings`, `beforeLoopActions`, `gameLoop`, `winCondition` (or `playersWinCondition`), and `postGameActions`. If players can become spectators (i.e. leave mid-game) or spectators can become players (i.e. join mid-game), there are also sections for `turnPlayerToSpectatorActions` and `turnSpectatorToPlayerActions`.
- **beforeLoopActions Limitations:** This is a simple list of actions, NOT action groups. You CANNOT use `repeat` or `parallel` modifiers here. Do all deck creations (`createCustomDeck`, `createDeck`) and array initializations here so they execute only once. The only exception is when setup requires `repeat`/`parallel` — in that case, put it in the first `gameLoop` group with `skipCondition: gameLoopIndex > 0`.
- **`createGenericCardWidget` Placement:** Never call `createGenericCardWidget` before the tutorial group, and never before all decks referenced in its `"decks"` field have been created. Since position decks (created with `repeat`) must live in the first `gameLoop` group, `createGenericCardWidget` must also be in the `gameLoop` (with `skipCondition: gameLoopIndex > 0`), placed after all deck-creation groups.
- **`repeat`/`parallel` Must Be Top-Level on Action Groups:** A `repeat` or `parallel` block modifies an action group — it is a top-level key alongside `"name"`, `"actions"`, and `"skipCondition"`. It CANNOT appear nested inside an `actions` array. If you find yourself placing `{"repeat": {...}, "actions": [...]}` inside a list of actions, extract it into its own top-level action group.
- **Variables vs Parameters — Critical Distinction:** Ludio has two distinct concepts that must never be confused:
  - **Parameters** are inputs to selector functions. They always have three fields: `"name"`, `"type"`, and `"value"`. The `"type"` can be `"preset"`, `"cached"`, or `"computed"`, and this is the ONLY place where `{"type": "cached", "value": "varName"}` is valid syntax.
  - **Variables** are values stored in cache (`saveValueInCache`) or structural fields like `qnt`. They have NO `"type"` field — a variable is either a literal (`5`, `"red"`, `[]`) or a computed selector object. Writing `{"type": "cached", "value": "numPlayers"}` as a variable is always wrong.
  - Correct `repeat.qnt`: `"qnt": 3` or `"qnt": {"selector": "getCachedValue", "params": [{"name": "name", "type": "preset", "value": "numPlayers"}]}`.
- **Free Variables from Engine Context:** Ludio injects certain variables automatically — never save them to cache *(enforced by validator)*:
  - `repeatIndex` — 0-based index inside a `repeat` block. The `repeat` block only ever has `"qnt"` — never add `"indexVar"` or similar.
  - `spaIndex` — 0-based index inside a `parallel` block.
  - `gameLoopIndex` — increments each outer `gameLoop` iteration.
  - `loopIndex` — inside a nested `[]` loop.
  - `waitingSpectator` — the joining spectator's player ID, inside `turnSpectatorToPlayerActions`.
- **`isActionLoop` is Free Inside Loops:** Within any loop, Ludio provides `isActionLoop` as `true` automatically. Never initialize it to `true` — only set it to `false` when you want to exit the loop.
- **Action Group Fields:** Only use: `name`, `repeat`, `parallel`, `skipCondition`, `actions`, `checkWinCondition`, `turnPlayersToSpectators`, `turnSpectatorsToPlayers`, `nextGroupNonStop`. *(enforced by validator)* Note: `nextGroupNonStop` is always true by default — omit it unless you need `false`.
- **`setImagesRow` Placement:** Place `setImagesRow` (the transparent image row that makes space for the card hand) in `beforeLoopActions`, after any pre-game votes or notifications that shouldn't show the hand area yet.
- **Score Initialization:** Player scores default to 0 at game start. Never call `updateScore` to initialize scores to 0.
- **`turnPlayersToSpectators` / `turnSpectatorsToPlayers` Flags:** Place these on a dedicated empty action group at the end of the `gameLoop` (e.g. `{"name": "Change players", "turnPlayersToSpectators": true, "turnSpectatorsToPlayers": true, "actions": []}`). This marks the safe point for player↔spectator transitions.
- **Individual Actions Can Have `skipCondition`:** Not just action groups — individual action objects inside an `actions` array can also carry a `skipCondition`. Useful for skipping one notification within a group based on a result computed earlier in that same group.
- **`inc`/`dec` for ±1:** Use `inc(arg)` and `dec(arg)` (single param `"arg"`) instead of `add(x, 1)` / `subtract(x, 1)`.
- **showScore Placement:** `showScore` should be called in `beforeLoopActions` so the score display is visible from the start.
- **When to use `showScore`/`updateScore` vs. other score displays:** For individual card games, use `showScore` + `updateScore` in player cameras. For team games: if there's a central widget, consider deck labels on the board instead — it co-locates the score with the game state (see Enigma, Pitfall). If no widget (e.g. Wavelength), use `showScore`/`updateScore` on player cameras.
- **Dot Notation for List Access:** When a selector param needs a specific element of a cached list by hardcoded index, use `{"name": "argN", "type": "cached", "value": "listName.0"}` instead of `selectElement`. Only use `selectElement` when the index is dynamic.
- **Never Repeat Actions with skipConditions When a Variable Already Holds the Value:** If a cached variable already holds the value you need, pass it directly via `cached` — do not write N copies of the same action each hardcoding one possible value with a `skipCondition` guard.
- **Cache Repeated Computations:** If a selector expression is used more than once, compute it once in `saveValueInCache` and reference the cached variable everywhere else. Order `saveValueInCache` entries so later entries can reference earlier ones.
- **Boolean "Update" Flag Pattern:** When updating both a "highest rank" and "highest player" in the same `saveValueInCache` block, compute a single boolean flag first (e.g. `isHighestTrump`), then use it as the `condition` in both updates. Never re-compute the condition inline in each `ifElse` — the first update changes the value and the second comparison will be against the wrong value.
- **Idiomatic Double Loops:** Nested loops restart at the top unless `isActionLoop` evaluates to false. Wrap the outer loop in `[]` (provides `loopIndex`). Inside, use an `emptyAction` to set `isActionLoop: false` to break. Use `repeat` for the inner loop.

## 2. Payloads & Selectors (Strict Syntax)

- **Payload Types:** Actions take inputs in their payload divided into `preset` (primitives), `cached` (variables), and `computed` (selector functions like `ifElse`, `listLength`, `formatString`, etc.).
- **No "preset" Selector:** There is no selector called `"preset"`.
- **Don't Wrap Already-List Variables in `createList`:** Before using `createList` with a single cached argument, verify the variable is a scalar. If it's already a list, reference it directly via `cached`. To save a literal value to cache, write it directly: `{"name": "myList", "value": [1,2,3]}`. Similarly, static values in a payload belong in `preset`, not `computed` with a fake selector.
- **Strict Param Structure:** Inside a selector, EVERY item in `params` MUST have exactly three keys: `"name"`, `"type"`, and `"value"`. Never use shorthand.
- **Eager Evaluation Trap:** In an `ifElse` selector, Ludio computes BOTH `thenValue` and `elseValue` regardless of the condition — no lazy evaluation. Never use `ifElse` to guard an expression that would be invalid in one branch. Design both branches to be safe unconditionally — use `remainder` or `minValue` to clamp indices rather than relying on a condition to prevent out-of-bounds access.
- **Safe Lookups & Manipulation:**
  - Always use `defaultValue` with `getCachedObjectValue` so the engine doesn't crash if the key doesn't exist.
  - NEVER use `equals` to compare booleans. Use `getCachedValue` to check if true; use `logicalNOT` to check if false.
  - NEVER use `equals` to compare two lists — wrap each in `listToString` first.
  - `getCachedValue` takes exactly one param: `{"name": "name", "type": "preset", "value": "<variableName>"}`. The param name is literally `"name"`.
  - Use `negate` (one `"arg"`) to return the negative of a number, instead of `subtract(0, x)`.
  - In `getCachedObjectValue` and `setCachedObjectValue`, `objectName` is almost always `"type": "preset"` — only `"cached"` if the object name itself is a variable.
  - `logicalAND` accepts unlimited arguments (`arg1`, `arg2`, …). Never nest `logicalAND` inside another — flatten into one call with N args.
- **Strings in Computed:** Formatted strings (e.g. `"videobox_($1)"`) MUST go in `computed`, never `cached`.
- **Any Payload Field Can Be Computed:** For binary outcomes, use a single action with `ifElse` on `sounds.list`, `image`, `header`, `text`, etc. rather than two separate conditional actions.
- **Prefer `type: "cached"` Over `getCachedValue` in Params:** Always use `{"name": "...", "type": "cached", "value": "varName"}` — never wrap in `getCachedValue` inside `type: "computed"`. `getCachedValue` is valid only as a top-level `computed` field or in `skipCondition`.
- **Use `players` Not `allUsers` for Audience Fields:** Spectators automatically receive all notifications, so `allUsers` is redundant. Use `players` in `cached` for `to` (notifications), `labelInspectors` (`setLabelInspectors`), and `playList.0` (sounds). *(enforced by validator for `createNotification` and `setLabelInspectors`)*

## 3. Cards & Actions

- **Never Create Player-Count Aliases:** Do not create variables like `players4` padding `players` to a fixed length. Always use `players` directly with a `repeat qnt: numPlayers` block.
- **One Cards JSON Per Game:** All card types for a game live in a single cards JSON. Only split into a separate file for genuinely reusable cross-game cards (e.g. a shared `bids_cards.json`).
- **Deck Labels Go on `createCustomDeck`, Not on `createCard`:** The `label` field on `createCustomDeck` labels the deck. Fields in a `createCard` payload are card attributes. Create labeled decks in the first `gameLoop` group (with `skipCondition: gameLoopIndex > 0`) using `repeat` + `getPlayerNameById`, since player names are unavailable in `beforeLoopActions`.
- **dealDeck Rules & Safety:** `dealDeck` is the ONLY action to move cards to a player's hand. Always specify `qnt`. Always sort by `weight asc`. Always check the deck has cards before dealing; use `minValue` to avoid over-drawing.
- **Other Card Movements:** `moveCards (type: "deck")` — deck-to-deck only. `moveCards (type: "hand")` — hand-to-hand only. `recallCards` — hand to deck. `recallCards.targets` accepts a single player ID or a list — pass all players at once rather than looping one at a time.
- **playCards Rules:** Omit `oneClick: true` if playing more than 1 card. Always include `"playable": "availableCards"` in preset. `postHandler` is always a top-level field on the action object (not inside payload) — use `"playOneRandomCard"`.
- **postHandlers Placement & Usage:** `postHandler` is always top-level on the action object. For `selectCentralWidgetDeck`, omit if the "nothing clicked" case is handled in `saveValueInCache`. Use postHandlers only on timed actions.
- **createGenericCardWidget Must Precede playCards and selectCentralWidgetDeck:** Call `createGenericCardWidget` in a setup group before any `playCards` or `selectCentralWidgetDeck` — even if those come in a bidding phase that precedes the trick loop.
- **Avoid Dealing Cards to Hands When Possible:** If you only need card data (not physical card-holding), use `getDeckCards` + `selectElement` + `getObjectField` to read card fields directly — no `dealDeck` or `setImagesRow` needed. Show the card to a player via a private `createNotification` with `cached: {image: "cardImageVar"}`.

## 4. Voting, Targeting UX, & Interactions

- **`lastActionResult` for Vote Actions:** `createVote` and `createMixVote` produce a result dict: `voteResult` (winning answers list), `voices`, `answersCount`, `answersVoters`. **Safe extraction:** `selectElement(append(lastActionResult.voteResult, <fallback>), 0)` — always append a fallback because an empty `voteResult` (nobody voted) would crash on index 0. **With a postHandler:** `lastActionResult` IS the list directly, so use `selectElement(append(lastActionResult, <fallback>), 0)`.
- **createVote Required Fields:** `title`, `type`, `question`, `terminationCondition`, `actors`, `showResultInRealTime` — all six are mandatory. Use `oneClick: true` to avoid a second confirmation click. *(enforced by validator)*
- **Lists for Actors/Targets:** `actors` and `to` must be lists. Use `createList` to wrap a single player ID.
- **Targeting via Decks:** Prefer `selectCentralWidgetDeck` over `createVote` when players can click their target's public discard deck — this avoids the central-widget squish limitation and is better UX when per-player decks are already visible in the widget.
- **`createVote` + Central Widget UI Conflict:** Running `createVote` while the central widget is displayed squishes the UI. The `removeWidget`/`restoreWidget` workaround hides the cards during voting — prefer `selectCentralWidgetDeck` for player-targeting votes that happen while the widget is visible. Expected to be resolved in Ludio soon.
- **Input Parallelism:** `createInput` is natively parallel — `actors: "players"` gives everyone their own input box simultaneously. Do not wrap in a parallel action group.
- **`createInput` `scope` and `private`:** `scope` is `"player"` or `"team"`. Always set `"private": true` to hide from non-actors. `title` must be a preset string — never a computed `formatString`.
- **Avoid Redundant Pre-Round Notifications:** Don't add a `createNotification` before each `selectCentralWidgetDeck` after the tutorial. Players know the flow — repeated pop-ups are noise.
- **PostHandlers:** Use `postHandlers` (`randomSelectForOneAnswerTargetVote`, `playOneRandomCard`) strictly on timed actions to prevent AFK stalling. Never on untimed actions.
- **Conditional Duration for Disconnected Players:** Any timed action with exactly one actor should compute `duration` as `ifElse(contains(allConnectedUsers, <actor>), <normal_secs>, 1)`. Move `duration` from `preset` to `computed`. Copy the pattern from Emeralds.

## 5. Standard Game Patterns

- **The Tutorial Sequence (required for every game):** Every game must include a tutorial:
  1. **`beforeLoopActions`:** Show a welcome `createNotification` (see pattern below), find the host, then trigger a `createMixVote` asking which players want the tutorial. **Always copy the `createMixVote` verbatim from `enigma.json`** — only change `backgroundColor`, `textColor`, and `borderColor`. The `saveValueInCache` populates `learners` and `tutorial` (boolean). *(validator checks the createMixVote structure)*
  2. **First `gameLoop` group ("Tutorial"):** `skipCondition: [logicalNOT(tutorial)]`. A few `createNotification` actions sent to `cached.to: "learners"`. **The last action must be an `emptyAction` with `saveValueInCache: [{name: "tutorial", value: false}]`** so the tutorial only plays once.
- **Welcome Notification Pattern:** The `createNotification` immediately before the tutorial `createMixVote` must use `computed.text` with `formatString` referencing the host name — never hardcode `"text"`. Duration is always 8. Template:
  ```json
  {
    "key": "createNotification",
    "payload": {
      "preset": {
        "header": "Welcome to [Game Name]!",
        "image": "banner",
        "duration": 8,
        "backgroundColor": "<game bg color>",
        "borderColor": "<game border color>",
        "textColor": "white"
      },
      "cached": {"to": "players"},
      "computed": {
        "text": {
          "selector": "formatString",
          "params": [
            {"name": "format", "type": "preset", "value": "<b>($1)</b> - in a moment, tell me whether you want Ludio to teach your group how to play [Game Name]!"},
            {"name": "arg1", "type": "computed", "value": {
              "selector": "listToString",
              "params": [{"name": "list", "type": "computed", "value": {
                "selector": "getPlayerNamesByIds",
                "params": [{"name": "ids", "type": "cached", "value": "host"}]
              }}]
            }}
          ]
        }
      }
    }
  }
  ```
- **End of Round & Play Again:** **Always copy the end-of-round host vote verbatim from `emeralds.json`** — only change `backgroundColor`, `textColor`, and `borderColor`. *(validator checks the play-again vote structure and targets)*
  - Trigger the vote every N rounds via `gameLoopIndex % X == Y`. Save result to `playAgain`; tie `gameOverCondition` to `logicalNOT -> playAgain`.
  - Insert an untimed "Review Round" `selectCentralWidgetDeck` before the vote so players can see the field.
  - End the loop with an empty group containing `"checkWinCondition": true`. No need to manually skip actions if `playAgain` is false — the engine terminates naturally.
- **Win Conditions & Winner Announcements:**
  - Team-based → `winCondition` (dict mapping team names to boolean selectors). Individual → `playersWinCondition`.
  - **Always copy the `postGameActions` notification verbatim from Emeralds** (only change `backgroundColor` and `borderColor`). It uses the `winner` cache variable with `ifElse` to produce `"($1) wins!"` vs `"($1) share the win!"`. *(validator checks this structure)*
- **2-Team Guessing Games — Standard Setup Pattern:** (Enigma, Pitfall, Wavelength, etc.) All run in `beforeLoopActions`:
  1. Host picks cluegivers via `createVote` (type `target_point`, `allowFewerAnswers: true`, `answersQuantity: numPlayers-2`, `targets: players`).
  2. Pad to safe minimum if <2 are picked (1 selected → `append` one more; 0 → `sublist` 2 from pool).
  3. Split cluegivers: `shuffleList` → `integerDivide(numCluegivers, 2)` → `sublist` to Red / Blue.
  4. Split non-cluegivers: `listsSubtract(players, safeCluegivers)` → `shuffleList` → `integerDivide` → `sublist` to Red / Blue.
  5. Four `setRole` calls — redCluegiver, blueCluegiver, redPlayer, bluePlayer (each accepts a list).
  6. Derive team lists with `getPlayersFromTeam`. Initialize cluegiver pointers to the **last** element so `nextPlayer` returns the **first** on round 1.
  7. `removeAllHighlights` → `highlightPlayers` Red (#D83232) → Blue (#4EC1D0) → `changeLayout` (HIGHLIGHT, VERTICAL, Red=top, Blue=bottom).
  - **Always Red and Blue** for two-team games (Red left/top, Blue right/bottom) — builds familiarity across the library.
  - **Cluegiver rotation:** Advance only the active team's pointer each round via `nextPlayer`. Both `ifElse` branches evaluate (eager evaluation), but only one pointer is written — safe since `nextPlayer` has no side effects.
- **Role-Based Team Formation with Fixed Clickers (Enigma variant):** After the main team split, two additional `createVote` actions (type `target_point`, `answersQuantity: 1`) let the host pick one fixed clicker per team. Enigma-specific; most 2-team games don't need this.
- **Round Winner Feedback (Fast-Paced Games):** Prefer sound effects + `animateBox` over `createNotification`/`highlightPlayers` for round-winner feedback. Use `emptyAction` with `sounds.list`/`playList.0` for broadcast sound, then `animateBox` on scoring winners' camera boxes. Reserve `createNotification` for slower games where the extra clarity is worth the time.
- **Spectator Management:** In `turnSpectatorToPlayerActions` and `turnPlayerToSpectatorActions`, recompute `players` and `numPlayers` using `allPlayers` (not arithmetic). Grant late joiners `currentMinScore` to avoid starting at 0. Place `"turnSpectatorsToPlayers": true` / `"turnPlayersToSpectators": true` on a dedicated empty "Change players" group at end of `gameLoop`. Always end both transition sections with `changeLayout`.
- **`orderByTeam` vs `changeLayout`:** Use `changeLayout` (HIGHLIGHT, VERTICAL) for explicit left/right team control. Use `orderByTeam` only in standard grid view (not vertical layout) to group teammates next to each other.

## 6. UI, Visuals & Audio Quirks

- **Newlines in createNotification text:** Use `<br/>` for line breaks. `\n` does nothing.
- **Image Aliases Are Presets:** Aliases like `"banner"`, `"winner"`, `"wallpaper"` defined in `gameInitOptions.images` are string literals. Always reference in `preset`, never `cached`.
- **Default Player Role Avatar:** `https://res.cloudinary.com/liars-club/image/upload/card_player_ed7jck.webp` — use unless the spec provides a different one.
- **No Emojis in createCard Text:** `createCard` doesn't support emojis. Use plain text.
- **`ratio` Field on Cards and Widget:** `createCard.ratio` is a **float** (e.g. `1.6`); `createGenericCardWidget.ratio` is a **string** (e.g. `"1.6"`). In practice, `ratio` tends to distort layout — omit unless explicitly required.
- **Summary-Card Column Pattern:** For text summaries alongside clickable position decks, add a non-clickable "summary" deck per team as the first column (e.g. `red_clues`, `blue_clues`). Update `createGenericCardWidget` dimensions and prepend summary deck names. Use `counter: false` on summary decks. Do NOT include them in `selectCentralWidgetDeck`.
- **UI Grids:** `dimensions` is `[rows, columns]`. For trick-taking: `[2, numPlayers]`. The easy mistake is reversing to `[numPlayers, 2]`. Set `facedown: true` and label with the player name.
- **setImagesRow and Card Hand Space:** Use with a transparent image only when players hold a hand that opens from the bottom. Heights: `maxHeight: 140` normal; `maxHeight: 230` with `"increaseHandHeight": true`. Use `10` (not `0`) to visually clear the hand area at end of game.
- **Hand Visuals:** For very few cards, set `"increaseHandHeight": true` in `visualSettings` and `"maxHeight": 230` in the `setImagesRow` action.
- **Audio Arrays:** Every action playing a sound needs both: `sounds.list` (soundboard aliases array, in `preset` or `computed`) and `playList.X` (player ID list, in `cached` — e.g. `"playList.0": "players"`). `sounds.waitForSoundEnd` is optional — when omitted it defaults to `false`, meaning the action continues without waiting for the sound to finish. *(sounds.list + playList.X pairing enforced by validator)*
- **`sounds.list` entries must use the `soundboard.` prefix** — e.g. `["soundboard.success"]`, not `["success"]`. *(enforced by validator)*
- **drawArrows:** `computed` payload is a dict where keys are origin player IDs and values are lists of target player IDs.
- **gameInitOptions Timing Fields:** Use exactly one of `time`, `timePerPlayer`, or `timePerRound` (integers, in minutes). *(enforced by validator)*
- **Always Use Spec Assets:** Use wallpaper, banner, and animation URLs verbatim from the spec in `gameInitOptions.images` and `gameInitOptions.animations`.

## 7. Trick-Taking Games

- **Ordinal Roles for Trick Order:** Use fake ordinal roles ("1st", "2nd", "3rd", "4th") to show each player their trick position. Cache an `ordinal` dict (`{"0": "1st", "1": "2nd", ...}`) in `beforeLoopActions`. At trick start, run a `parallel` "Show Order" group calling `showFakeRole` per player. Compute each player's ordinal as `getCachedObjectValue(ordinal, remainder(numPlayers + spaIndex - indexOf(players, trickLeader), numPlayers))`. Copy the pattern from Emeralds.
- **Standard Wood Background:** `"cardBackgroundImage"` in `visualSettings` and `createGenericCardWidget`'s `"backgroundImage"` both → `https://res.cloudinary.com/liars-club/image/upload/wood_qbegm0.jpg`. Used in essentially all trick-taking games.
- **Spectator→Player: Rebuild Player-Specific Content:** `turnSpectatorToPlayerActions` must rebuild any player-specific labeled decks. Compute the new player's index with `indexOf(players, newPlayer)`, re-label their slot, clear old cards, and create fresh content for that slot.
- **Card Play Location:** Cards go to the central widget unless the widget is needed for something else — then use player videoboxes.
- **Bidding UX:** Give each player a `createVote` to declare their bid, then put bid cards in their videobox to track progress. Some games warrant a different approach depending on whether bids are discrete values, ranges, or sequential.
- **`updateScore` Payload Structure:** `scores` is an array of entry objects: `list` (player IDs), one of `score` (set) or `delta` (add), and optionally `secondScore: true` (boolean flag). Never set `secondScore` to an integer. Never initialize scores to 0 — they default to 0.
- **Reset secondScore Every Round Unconditionally:** Put the secondScore `updateScore` (score: 0, secondScore: true) in the unconditional End Round group, not the conditional Reset Scores group.
- **`nextPlayer` Selector:** Params: `playersList` (type `cached`) and `playerId` (type `cached`). Returns the next player ID in the list, wrapping around. Do not use `players` or `current` as the param names.
- **Player-Count-Dependent Card Sets:** Name sets by integer count (`"3"`, `"4"`, etc.). Pass `numPlayers` as `set` via `cached` — Ludio converts to string for lookup, eliminating any `ifElse` branching.
- **`flipOverTopCard`:** Required payload: `deck` (string). Optional: `delay` (seconds). Use `parallel: {qnt: N}` to flip N decks simultaneously. The correct way to animate a face-down deck reveal.

## 8. Drawing (Whiteboard Widget)

- **`createDrawing`:** Launches a collaborative whiteboard. Required: `actors`, `question`, `terminationCondition` (`"get_all"`). Key optional: `duration`, `capture` (saves result URL to `lastActionResult.url`), `private`, `vertical`, `colors` (palette list). Supports the sound triplet fields. For multiple simultaneous teams, wrap in `"parallel": {"type": "smart", "qnt": numTeams}` and use `spaIndex` to select the team. Display captured URL via `createNotification` with `preset.image`.
- **`startClip`:** Marks start of a highlight recording. Required: `title` (usually formatted with round number). No result saved to cache.
- **MonsDRAWcity is implementable** using `createDrawing` for the drawing phase and Cloudinary for prompt images. The main challenge is uploading the prompt images to Cloudinary.
