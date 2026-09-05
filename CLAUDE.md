# Ludio trivia — working agreement

This file loads automatically for anyone working in this repo. It exists so a
trivia night can be built by someone who has never seen the game JSON.

## Who does what

**The writer's whole job is the questions.** They talk to Claude, iterate, and
approve. They never touch the game JSON, the build script, or production.

**Claude does everything else** — sourcing images and audio, uploading, building
the setup JSON, validating, and (only when Ankit says so) deploying.

## The one file a writer's work lands in

`trivia/questions_<batch>.json` — plain data, no code. Each question is:

```json
{ "night": "fri", "n": 7, "q": "…", "answer": "…",
  "image": "alien_7",            // asset name, not a link
  "image_negate": true,          // show it colour-inverted
  "answer_image": "inv_7_pair",  // shown while grading, instead of "image"
  "audio": "ms_7", "audio_short": "ms_7_5s" }
```

Rules: 5 rounds, each with exactly 10 questions per night. `n` is the asset
number — **odd = Friday, even = Saturday**. Assets live in the Cloudinary folders
named at the top of the file.

## Build and deploy

```bash
python3 trivia/build_trivia.py                       # build + validate only
python3 trivia/build_trivia.py --deploy both         # -> STAGING (writers: use this)
python3 trivia/build_trivia.py --deploy both --prod  # -> PRODUCTION (Ankit only)
```

**Deploy to staging freely — that is what it is for.** Writers should push to
staging as often as they like and play the game to check their questions.

| | Friday | Saturday |
|---|---|---|
| staging | Friday Night Trivia | Saturday Night Trivia |
| production | Ankit's Friday Trivia | Ankit's Saturday Trivia |

**`--prod` is Ankit's call, every time.** Never run it on your own initiative,
even if the writer says the questions are final. Production nights are live
products with real players.

It builds on top of production (the source of truth for game logic) and the
game-loop patch is idempotent, so it is safe to re-run. A deploy carries over the
target's own night-name copy, so pushing to staging does not overwrite
"Welcome to Friday Night Trivia!" with production's wording.

It prints `differs from what is live` — a clean build of unchanged questions must
say `no`.

**Never hand-edit anything in `game_jsons/`.** It is generated. Edit the question
bank and rebuild.

**Validator parity is the safety check.** Compare against the untouched original,
not against zero: these setups carry 1 pre-existing error and 7 warnings. Same
numbers after your change = no regression. More = you broke something.

## How Ankit wants questions written

**The target: a middling team should get about 7 of 10.** They feel good and come
back; the hardcore players get 9–10. Too easy is also a failure — the round feels
like a waste of time. Aim for ~7/10 on average across the night; individual rounds
may run a little hard or a little easy.

1. **The answer is a name, not a property.** Put the obscure detail in the
   question; make a film, show, sport, country or person the answer. "The Wall is
   made of what?" → "Which series has a wall of ice?" (Game of Thrones).
2. **Facts are free in the question; ask exactly one thing.** Never two.
3. **Avoid numeric answers** — percentages, constants, bare years. If a number is
   unavoidable, state a tolerance ("within 1 degree").
4. **Cut in both directions.** Trivial and unguessable both fail.
5. **Living memory beats archive.** Recent viral moments over historical fact.
6. **Calibrate with scaffolding, not substitution.** Add a hint, keep the
   question. Keep hints **loose** by default — "entertainer", not "rapper";
   "athlete", not "footballer" — and tighten only on the specific questions where
   the stimulus is genuinely hard to read.
7. **A picture must not answer its own question**, and picture rounds want real
   film stills, not cosplay, statues or posters.
8. **Full sentences, as a host would speak them.** Not "In which sport?" but
   "Which sport did she win it in?"
9. **Short answers** — a word or two where possible.
10. **No repeats** from recent nights, and no song whose title gives the answer
    away.

## Asset pipeline — hard-won details

Ignoring these produces *silent* failures: the game still renders, with the wrong
or missing media.

**Cloudinary**
- `e_negate` must be its **own** URL component, and must come **after** the
  resize. Combined with `e_sharpen` only one effect survives and the negate is
  dropped; applied before the resize it 400s on images over ~25MP.
- Verify a transform by **hashing the bytes**, never by checking for HTTP 200 — a
  wrong-but-valid image returns 200 happily.
- Always sign `invalidate=true` on upload, or version-less URLs serve a stale
  edge copy. `trivia/cloudinary_upload.py` does this (set the folder constants).

**Finding pictures**
- Wikimedia only hosts *free* content, so searches return cosplay, statues and
  theme parks. Real film stills are elsewhere:
  - **en.wikipedia non-free article images** — the `pageimages` API omits these;
    use `prop=images` then `imageinfo`.
  - **Fandom wikis** via `https://<wiki>.fandom.com/api.php`. Fandom blocks page
    scraping but not the API. This is where screencaps live.
  - **News pages** expose the lead image as `og:image`. eBay and NYT block
    scraping entirely.
- Non-free images are low-resolution by policy; upscale with
  `w_N,c_scale,e_sharpen:60`.
- **Always look at what you downloaded.** Filenames lie: searches have returned a
  fairground ride for "breakdance", a Japanese idol named Yūki Yoda for "Yoda",
  and Rex for "Little Green Men". Build a contact sheet and check.

**Audio**
- yt-dlp gets 403s from YouTube after a couple of pulls;
  `--extractor-args youtube:player_client=android` works.
- **Record the resolved video title before downloading.** A search once returned
  a comedy skit instead of the Jaws theme and nothing caught it.
- Clip spec: 15s clip + 5s cut, 192 kbps CBR, 44.1 kHz stereo.
- Pick the start as the **earliest** window at full strength, not the loudest —
  plain argmax lands on the closing climax.

**Game JSON**
- `createVote` supports only the **singular `image`** field. It has no `images`.
  (`createInput` and `createNotification` do support `images`, a list of aliases.)
- Question picture = `i`; grading picture = `iA`; resolution is
  `iA → i → placeholder`. To show two pictures at grading, pre-render them into
  one file (see `trivia/make_pairs` approach used for the inverted round).
- Image *aliases* are string literals — reference them in `preset`, never
  `cached`.

## Layout

```
trivia/questions_<batch>.json   the question bank — the writer's file
trivia/assets_<batch>.json      uploaded asset dimensions (drives upscaling)
trivia/build_trivia.py          bank -> game JSON -> validate -> deploy
trivia/cloudinary_upload.py     signed upload with invalidate=true
game_jsons/                     GENERATED. do not hand-edit.
documentation/validate_game_json.py
```

Assets: `images/zee_trivia/trivia_<n>` and `audio/zee_trivia/trivia_<n>`.
Increment `<n>` for each new pair of nights.

## Review surface

Each batch gets a published dashboard artifact — every question with its image
and audio inline — which is how the writer and Ankit review. Comments can be left
per question. Rebuild it whenever the bank changes so it never drifts from what
is live; diff it against production before publishing.
