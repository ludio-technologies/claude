# Refactor Readiness Campaign

**Goal:** get every non-demo production game to ✅ on all three code-hygiene refactors so we're ready to add variants at any time. Pure hygiene — no user-facing impact until variants are added.

The three refactors:
1. **String hoisting** — copy strings live in `raw.gameInitOptions.strings.Default` (a non-empty dict).
2. **visualSettings colors** — `raw.visualSettings` carries `backgroundColor` / `textColor` / `borderColor` so widget colors cascade instead of being hard-coded per action.
3. **Standard tutorial** — a `createMixVote` "who needs the tutorial?" vote (Roundabout/Emeralds pattern) + **one** gameLoop action group that teaches all learners via `createNotification` actions.

This runs as an **unattended cloud routine every 2 hours**, doing **ONE game per run** to stay within token budget.

---

## Per-run algorithm (do exactly one game)

1. **Pick the next game.** Run `python3 documentation/campaign_status.py` — it reads **live production** (the source of truth), computes the 3 flags for every non-demo game, skips games listed in `documentation/campaign_blocked.txt`, and prints `NEXT GAME` with its setup id and which refactors it needs. Work on exactly that game. If it prints "none", the campaign is complete (or all remaining are blocked) — stop and report. (The Work Queue table lower in this file is a human-readable snapshot only; the script is authoritative.)

2. **Pull prod + back up (git = the rollback net).**
   - `curl -s https://try.ludio.gg/api/setup/{SETUP_ID} -o /tmp/setup.json` — the game definition is in the `.raw` field; the rulebook you'll turn into the tutorial is in the setup's `.rules` (the Describe "Rules" field).
   - Extract `.raw` to `game_jsons/<slug>.json` and **git commit it as the pre-change backup**: `Backup: <Game> pre-refactor prod snapshot`. This snapshot is the rollback path (we do NOT create a staging BACKUP setup — that needs auth a headless run doesn't have).

3. **Apply only the refactors this game is missing** (see recipes below). A game may need 1, 2, or all 3.

4. **Validate — hard gate.** `python3 documentation/validate_game_json.py game_jsons/<slug>.json` must report **0 errors**. Warnings about field order are OK. If errors remain after a reasonable effort, **do not push**: add a line to `documentation/campaign_blocked.txt` — `<setup-id>  # <Game>: <short reason>` — so future runs skip it, commit + push the WIP, and stop (leave it for a human). Never push a game that doesn't validate.

5. **Push to prod (open PATCH, no auth).**
   - Body file `/tmp/body.json` = `{"raw": <the def object>}`.
   - `curl -X PATCH -H 'Content-Type: application/json' --data-binary @/tmp/body.json https://try.ludio.gg/api/setup/{SETUP_ID}`
   - **Verify:** re-`GET` the setup and confirm `.raw` round-trips to the local file. If it doesn't match, treat as failure — add it to `campaign_blocked.txt` (`push mismatch`) and stop.

6. **Commit + push (persistence).** The cloud checkout is ephemeral, so commits must reach GitHub or the backup is lost and the next run has no memory of blocked games. Stage the backup snapshot, the refactored `game_jsons/<slug>.json`, and any `campaign_blocked.txt` change, commit `Readiness: <Game> — <which refactors applied>`, and **`git push origin main`**. Progress itself is re-derived from live prod next run (no table to hand-edit), so the push is only for the backup snapshot + blocked list.

**Guardrails:** one game per run; push to prod only on 0 validator errors + verified round-trip; the status script never selects an already-complete game; if a game is unusually risky/complex, add it to `campaign_blocked.txt` (`needs human`) and stop rather than forcing it.

---

## Recipe 1 — String hoisting

Hoist every preset copy field (`title` / `header` / `text` / `question` / `label`, plus any `formatString` `format` value containing a space) out of the action payloads into `raw.gameInitOptions.strings.Default`, replacing the inline literal with a `cached` reference to an auto-generated key; dedupe identical strings to one key. Variant themes later live as sibling dicts (`strings.<Variant>`), but for this campaign we only create/populate `Default`. Scan the WHOLE raw for leftover literals — the **tutorial mixVote's `learners` svc** is the classic missed spot (e.g. `contains(voteResult, "Everybody!")` should reference a hoisted `everybodyNobodyTargets` key). See `documentation/Things to remember.md` for the strings/variants engine syntax.

## Recipe 2 — visualSettings colors

Put the game's palette in `raw.visualSettings` as `backgroundColor` / `textColor` / `borderColor` (whichever apply) and **remove the per-widget color overrides** in individual actions so they inherit the cascade. Card games also want `increaseHandHeight:true` + `cardHandBackgroundImage` (same wood bg as the central widget) — but the ✅ signal for this refactor is specifically the presence of populated color fields in `raw.visualSettings`.

## Recipe 3 — Standard tutorial (notification style, Roundabout template)

Build content **from the setup's Describe `rules` field** (turn each rulebook section into notification cards — do not invent rules or use `summary`). Use images only where they aid a rule, and **reuse existing assets only**: prefer `gameInitOptions.images`, else pull a card image from the deck (`GET /api/deck/{name}`) into the game's images. **Rip out any legacy tutorial** first: voiceover/guided-playthrough tutorials, `createConversationGroup` tutorials, and interspersed-throughout-the-game tutorials (e.g. Piranha-style) — all replaced by the single standard group.

1. **Tutorial vote = `createMixVote`** (copy from a standardized game — Roundabout/Rainbow Blackjack/Gaslight): host-targeted, `poll.targets` `["Everybody!","Nobody!"]`, question "($1), who needs the tutorial? …". Its `saveValueInCache` must be exactly, in order: `voteResult`, `learners` (ifElse: players contains voteResult.0 → voteResult; elif contains "Everybody!" → players; else []), `tutorial` (`greaterThan listLength(learners), 0`). The validator REQUIRES a createMixVote saving both `learners` and `tutorial`.
2. **One gameLoop "Tutorial" group**, `skipCondition` = list (OR/skip-if-any) of `greaterThan(gameLoopIndex,0)` + `logicalNOT(cached tutorial)`. Actions = a series of `createNotification`, each with `payload.cached.to:"learners"`, `preset.duration:~15`, header/text from the rules. **Last action flips the flag off:** `{"key":"emptyAction","saveValueInCache":[{"name":"tutorial","value":false}]}` — the validator errors ("No action in any tutorial group sets tutorial: false") without it.
3. **Prune** orphaned `strings.Default` keys and dead `images` left behind by the removed tutorial. Check the spectator-typo cascade (`turnPlayerToSpectators` → plural `turnPlayersToSpectators`) while you're in there.

If the game is already string-hoisted, keep the tutorial consistent: hoist the mixVote title/question + all notification header/text into `strings.Default`, and omit mixVote/notification bg+border colors so they inherit visualSettings.

---

## Work Queue (needs work — pick top-down)

<!-- QUEUE-START -->
| Game | Setup ID | Strings | visualSettings | Tutorial | Tutorial state | Status |
|------|----------|:---:|:---:|:---:|---|---|
| A Night in Oz | `af2d47bb-b880-4701-b592-847e84d31c31` | ❌ | ❌ | ❌ | none (build from scratch) |  |
| An Apple a Day | `1ed9689b-6f22-4b3f-9764-18eabab52389` | ❌ | ❌ | ❌ | convo-group (convert) |  |
| Anger Management | `59e56902-7a42-4a35-868b-b7601828e8e0` | ❌ | ❌ | ✅ |  |  |
| Ankit's Trivia Night | `684879a4-12cd-42f7-b4cd-875dc49900d3` | ✅ | ✅ | ❌ | none (build from scratch) |  |
| Bingo | `bd13c882-7045-44df-97c3-af63e1e1b558` | ❌ | ❌ | ❌ | none (build from scratch) |  |
| BLANK in 4 Words | `84e57207-d5ea-4252-8938-33d5f5eeb3e2` | ❌ | ❌ | ❌ | partial/legacy |  |
| BS | `1efdab37-3840-4153-8d3f-432ad93062b7` | ❌ | ❌ | ✅ |  |  |
| Buffalo | `d4b10981-243d-468e-bece-cb1ca00a4203` | ❌ | ❌ | ✅ |  |  |
| Bull Run | `35e5cf85-b926-4363-80a9-a5835783d1d3` | ❌ | ❌ | ❌ | none (build from scratch) |  |
| Bunmi's Trivia Night | `3eb78bb6-00e9-4f31-abf2-4815b5b683ce` | ❌ | ❌ | ❌ | none (build from scratch) |  |
| Caption Contraption | `07f75460-352d-4c75-8d1e-0665d4563ff6` | ❌ | ❌ | ❌ | partial/legacy |  |
| Categorical | `9ce8c527-ea4a-4891-afc3-4742645559a5` | ✅ | ✅ | ❌ | none (build from scratch) |  |
| Chasm | `119b6516-352e-4930-bc79-3ee02c371203` | ❌ | ❌ | ❌ | convo-group (convert) |  |
| Clash on Baker Street | `af978a61-e4fd-424a-a973-61cf723a1f18` | ❌ | ❌ | ❌ | partial/legacy |  |
| Classic Mafia | `6adbb968-5a73-4a36-bd0d-09aab71e869d` | ❌ | ❌ | ❌ | partial/legacy |  |
| Climb the Ladder | `7458129f-b6d0-474e-a569-252f2075f7cc` | ❌ | ❌ | ❌ | partial/legacy |  |
| Clowns Applaud Insanity | `4efb99a2-a44e-4d7e-bdc6-395f8fa4df55` | ❌ | ❌ | ❌ | convo-group (convert) |  |
| Coalition | `f2d26bc3-0e01-4333-a9a6-a28d9980119b` | ❌ | ❌ | ❌ | convo-group (convert) |  |
| Coffee Up | `a5eafa62-435b-4f0d-a336-9f3b8a2ce9a0` | ❌ | ❌ | ❌ | partial/legacy |  |
| Concealment | `8a4d40b0-c44c-4b92-8963-e5f4cf109f74` | ❌ | ❌ | ❌ | convo-group (convert) |  |
| Contour | `72853e0a-459e-4e45-9952-b52e56851d75` | ❌ | ❌ | ✅ |  |  |
| Cops and Robbers | `3a8cfe13-df7c-4df9-be9e-a1595bbe33c2` | ❌ | ❌ | ✅ |  |  |
| Court in Chaos | `d5123281-2639-43c6-9c02-aa907eeed825` | ❌ | ❌ | ❌ | partial/legacy |  |
| Deal or Death | `eec01d9a-eb11-439a-9e97-edc6e890ba0b` | ❌ | ❌ | ❌ | partial/legacy |  |
| Dodgeball | `eac22a79-c22d-4ff6-976c-9685205ed531` | ❌ | ❌ | ❌ | partial/legacy |  |
| Dodgeball League | `93856c07-41c7-4721-b547-0f4ae8b7a796` | ❌ | ❌ | ❌ | partial/legacy |  |
| Duplicate | `0add62a4-90f1-4877-87c4-03d241332ebd` | ❌ | ❌ | ❌ | partial/legacy |  |
| Eclipse | `e40c679c-47fc-4d58-8bf9-af5b01a6e2d5` | ❌ | ❌ | ❌ | partial/legacy |  |
| Emeralds | `46685842-3c2c-41ee-82d2-1e9523c02ff4` | ❌ | ❌ | ❌ | convo-group (convert) |  |
| Enigma | `f8a79531-fd0e-48cc-bdd4-142d8f1934fc` | ❌ | ❌ | ✅ |  |  |
| Evil Santa | `048db11c-532a-4e56-bb3f-1b13526b5665` | ❌ | ❌ | ❌ | partial/legacy |  |
| Fugitive | `70111b49-1314-44be-bfe5-a569de9a6ee5` | ❌ | ❌ | ❌ | partial/legacy |  |
| Galactic Shogun | `ba1cd08a-d480-4821-b66b-89eba2fca7c0` | ❌ | ❌ | ❌ | partial/legacy |  |
| Galaxy Brain | `c17eb4b6-d86c-4271-ab71-c6fdad425fa2` | ❌ | ❌ | ❌ | partial/legacy |  |
| Greater Fool | `f93452c6-1dcc-4deb-9c15-602a72f13814` | ❌ | ❌ | ❌ | partial/legacy |  |
| Groupthink | `322836c8-0b7d-4bdd-a736-63b66f90c8aa` | ✅ | ✅ | ❌ | partial/legacy |  |
| Handshake | `38a21371-9cc1-41ad-813c-afe55ba60eb7` | ❌ | ❌ | ✅ |  |  |
| Hearts | `0238ee1b-d735-4b65-86a9-fe89efb0c8aa` | ❌ | ❌ | ✅ |  |  |
| Hungarian Mafia | `1fd63ed6-8bc8-4a0b-93f6-2699f9a4f288` | ❌ | ❌ | ❌ | partial/legacy |  |
| Interference | `92145d58-7564-4d1b-af90-5ab35e9ab2bb` | ❌ | ❌ | ✅ |  |  |
| Is it a Word? | `ad027a72-12d8-40d8-8178-d150a3a2c80b` | ❌ | ❌ | ❌ | partial/legacy |  |
| Jackpot Genius | `c1845fd8-8031-4660-a960-79f88c304cae` | ❌ | ❌ | ❌ | none (build from scratch) |  |
| Kubrat's Trivia Morning | `7c91bb61-be10-4a63-8296-e9d4f314245e` | ❌ | ❌ | ❌ | none (build from scratch) |  |
| Kubrat's Trivia Night | `24dedf1c-043e-4299-bd66-df48fb61229d` | ❌ | ❌ | ❌ | none (build from scratch) |  |
| Mad Match Up | `c9c0627b-40b3-4c45-a051-da2924a13262` | ❌ | ❌ | ❌ | none (build from scratch) |  |
| Mafia Shootout | `081f9018-b929-41e1-b5e9-ff5161ff5cd0` | ✅ | ✅ | ❌ | partial/legacy |  |
| Markup | `69e46b97-9ba5-4ae9-8a22-581c1f1d09b7` | ❌ | ❌ | ❌ | partial/legacy |  |
| Nexus | `307b1d21-4f78-489e-a381-183dcfde80e0` | ❌ | ❌ | ❌ | partial/legacy |  |
| Nothing but Net | `0e9b302c-3b0f-43c3-9e37-fdc38346dc39` | ❌ | ✅ | ✅ |  |  |
| One More Step | `ef718f48-6566-4d0e-8417-2ea439b089e4` | ❌ | ❌ | ✅ |  |  |
| Open Trivia Night! | `6bb48d67-2686-40a8-9a6a-fbeb795d2965` | ❌ | ❌ | ❌ | none (build from scratch) |  |
| Paper Tiger | `69713679-a6ad-4310-b3eb-c38d50d91d34` | ❌ | ❌ | ✅ |  |  |
| Parrot Party | `ca72a128-5834-41bb-9696-631e1e536897` | ❌ | ❌ | ❌ | partial/legacy |  |
| Passengers | `986cfd04-5508-4170-8b23-d8b47eab6241` | ❌ | ❌ | ❌ | partial/legacy |  |
| Pecking Order | `60abb3bb-f304-4cb9-9108-0222d26b16f2` | ❌ | ❌ | ❌ | partial/legacy |  |
| Phantom Ink | `5b7b76e9-7128-486a-879d-88dda390deb8` | ❌ | ❌ | ❌ | partial/legacy |  |
| Phantom Ink League | `20aa0ba1-3ed1-4d65-80c8-de51d00e530c` | ❌ | ❌ | ❌ | none (build from scratch) |  |
| Picky Eaters | `ecddbf8e-0a06-4455-9083-0209de2e9687` | ❌ | ❌ | ❌ | partial/legacy |  |
| Piranha Puzzle | `256f3f84-69b6-41ec-bdc8-54409c305455` | ❌ | ❌ | ❌ | none (build from scratch) |  |
| Pitfall | `02bfdd55-6939-4571-b896-716743729ae8` | ✅ | ✅ | ❌ | convo-group (convert) |  |
| Pitfall League | `f8f9d787-5fc2-46a0-8200-72dcb489a650` | ❌ | ❌ | ❌ | none (build from scratch) |  |
| Portmanteau | `efbb938e-2811-47fa-9ea6-61029971c310` | ❌ | ❌ | ❌ | partial/legacy |  |
| Quantum Pitfall | `f8343b35-57f8-4405-8318-8dd982f0e1f1` | ❌ | ❌ | ❌ | convo-group (convert) |  |
| Rat in the Kitchen | `5eec9f77-48c1-42ac-9942-4897352753e7` | ❌ | ❌ | ✅ |  |  |
| ROLF | `129a21c5-4a21-419f-86cf-6fba7e15ae60` | ❌ | ❌ | ❌ | partial/legacy |  |
| Roundabout | `98aad33d-2aa6-4d00-b9b6-42c6049be86f` | ❌ | ❌ | ✅ |  |  |
| Royal Mafia | `f30b5814-801b-4b32-b61d-5fbfe4fa831c` | ❌ | ❌ | ❌ | partial/legacy |  |
| Runner Up | `4472f857-ec7c-4750-aedb-bc121b690911` | ❌ | ❌ | ✅ |  |  |
| Scorekeeping | `97aac84c-5c05-4928-8ce4-8dedcd1cb93b` | ❌ | ❌ | ❌ | none (build from scratch) |  |
| Sketchophone | `04288e64-9fea-4358-95e5-6b41d4f99f95` | ❌ | ❌ | ❌ | none (build from scratch) |  |
| Snekophone | `ef073af3-4f71-4261-906e-97a52779e9d7` | ❌ | ❌ | ❌ | none (build from scratch) |  |
| Sound Act Draw! | `00c1558e-a5e7-4c72-9414-d66759a3831e` | ❌ | ❌ | ❌ | convo-group (convert) |  |
| Spades | `c6255f69-81cd-4dde-b9b3-219d75e28aef` | ❌ | ❌ | ❌ | partial/legacy |  |
| Spectrum | `26305ae2-8cdc-4887-9a19-6e9ee9711e46` | ❌ | ❌ | ✅ |  |  |
| Speedfall | `9f403a06-0931-435a-a964-10659998f971` | ✅ | ✅ | ❌ | convo-group (convert) |  |
| Spicy Peppers | `ba8bda42-1b8b-4ea2-8fa6-c22d074b970b` | ❌ | ❌ | ❌ | partial/legacy |  |
| Stockings | `9d0d7102-7fde-44b9-aee0-ea217710df66` | ❌ | ❌ | ❌ | convo-group (convert) |  |
| Super Dark | `5bab62a1-f786-4290-ba7f-dd235c6c4a40` | ❌ | ❌ | ❌ | partial/legacy |  |
| Team Trivia | `0b85c977-76c8-439a-91df-126839ab79cf` | ❌ | ❌ | ❌ | partial/legacy |  |
| The Score | `627dc108-bfc3-4bc0-8465-94243df73b1b` | ❌ | ❌ | ❌ | partial/legacy |  |
| Topaz 25 | `de7b8cb3-2fce-47f1-b527-836b7d4bf19a` | ❌ | ❌ | ❌ | partial/legacy |  |
| Tug | `2b3afd76-1556-4121-a5a0-670103153040` | ❌ | ❌ | ❌ | partial/legacy |  |
| Venn | `5d91589e-55ee-4d72-999e-395c9fa03265` | ❌ | ❌ | ✅ |  |  |
| Which Craft? | `6c7284ca-7c5a-4331-9ce0-8808a5b0ed44` | ❌ | ❌ | ❌ | partial/legacy |  |
| Who Goes There? | `701def20-c131-409e-b7fd-3e931fa0a1e3` | ❌ | ❌ | ❌ | convo-group (convert) |  |
| Wisecrack | `d25e0a53-c9ed-440d-a580-9d6058dfa0d8` | ✅ | ✅ | ❌ | convo-group (convert) |  |
| Yo Ho Ho | `160f283b-f9f7-454f-8f90-d86064ff3775` | ❌ | ❌ | ❌ | partial/legacy |  |
| Zee's Trivia Night! | `1d0e9f44-6365-4d90-85b1-c7d59eb76284` | ❌ | ❌ | ❌ | none (build from scratch) |  |

<!-- QUEUE-END -->

## Completed (21/109) — do not touch

| Game | Setup ID | Strings | visualSettings | Tutorial |
|------|----------|:---:|:---:|:---:|
| Braggart | `ecc6e86f-ba05-4836-b55f-2d70481a1db9` | ✅ | ✅ | ✅ |
| Carte Royal Mafia | `7fb49045-d56f-4fcd-ae15-0374d2bb5940` | ✅ | ✅ | ✅ |
| Contrarian | `b55ef6c4-2075-4c67-9436-1ad1de971e4f` | ✅ | ✅ | ✅ |
| Euchre | `4b4bf5cb-ba05-4d5d-b38f-62d5bd09b79c` | ✅ | ✅ | ✅ |
| Fishbowl | `717ce188-bc46-4f63-89f1-2a5f8d0a052a` | ✅ | ✅ | ✅ |
| Fishbowl League | `ad7bb19f-c5d5-4744-903e-6a3cbf7becf4` | ✅ | ✅ | ✅ |
| Gaslight | `1ed2a7c1-f28c-447a-bad1-bb32c3f62476` | ✅ | ✅ | ✅ |
| Grunt! | `9afb0923-1bc6-40a9-9239-25d0c8b8443f` | ✅ | ✅ | ✅ |
| Knockout | `3f7e7246-e1b3-4bab-9db8-61a42bbd525d` | ✅ | ✅ | ✅ |
| Lexicon | `bcb1e0d6-8d28-4b18-b649-9de0f28a6a03` | ✅ | ✅ | ✅ |
| Not My Problem | `1dbe3dbb-6a7e-4963-9f85-cb13bdc964e6` | ✅ | ✅ | ✅ |
| Pageant | `02ebff5a-3922-4900-8de1-3545b9ee8475` | ✅ | ✅ | ✅ |
| Piranha | `607ebd0e-9659-4a28-9d87-543a8bb0d319` | ✅ | ✅ | ✅ |
| Rainbow Blackjack | `7271e197-2822-4fd2-bdbd-1438f5d71d60` | ✅ | ✅ | ✅ |
| Rhyme Time | `86d9ef9c-b4a6-4de6-85ca-d645186b374e` | ✅ | ✅ | ✅ |
| Shark! | `99ee7dc0-ea36-4d93-a709-91e018f8fa29` | ✅ | ✅ | ✅ |
| Spy Noir | `631ebf04-a55b-4395-9e68-73ca33cbae97` | ✅ | ✅ | ✅ |
| Spycraft | `ef197857-36d9-4c95-97dd-954d35377e31` | ✅ | ✅ | ✅ |
| Squarefall | `b92cd2da-d4cb-404b-a9c4-31789340a9a9` | ✅ | ✅ | ✅ |
| Stoneball | `0f108737-444a-41d2-a6b5-31b0c6e16c58` | ✅ | ✅ | ✅ |
| Willpower | `27975cc2-aff5-4a03-92f8-c094ce7bcefd` | ✅ | ✅ | ✅ |
