#!/usr/bin/env python3
"""Ludio Describe-popup validator.

A new game's Describe popup lives in the staging admin UI (Setups → Describe). The
content is too easy to ship wrong — see the memory trail across recent games. Workflow:

  1. Save the Describe content as a local JSON file at <game>_describe.json next to
     the game JSON. Same shape as the popup itself:

       {
         "name":        "<Game Name>",
         "demo":        false,            // optional, default false
         "parallel":    false,            // optional, default false
         "url":         "../setups/ludio-v1-engine-setup/dist_cards/app.output.js",
         "banner":      "https://res.cloudinary.com/.../banner.png",
         "description": { ... },
         "rules":       [ ... ],
         "tags":        [ ... ]
       }

  2. Run this validator before pasting to staging.

  3. Paste each section into the matching admin UI field.

Rules embedded here come from `documentation/The Describe json.pdf` plus the lessons
in `feedback_describe_popup_no_bold.md` and `feedback_describe_required_fields.md`.

Usage:  python3 validate_describe_json.py path/to/<game>_describe.json
"""
import json, os, re, sys
from typing import Any, List, Tuple

# ─── Allowed values ───────────────────────────────────────────────────────────
URL_CARDS  = "../setups/ludio-v1-engine-setup/dist_cards/app.output.js"
URL_OTHER  = "../setups/ludio-v1-engine-setup/dist/app.output.js"
URLS       = {URL_CARDS, URL_OTHER}

ALLOWED_TAGS = {
    "social deduction", "player elimination", "played in teams", "filler",
    "icebreaker", "creativity", "drawing game", "strategic", "card game",
    "word game", "two player", "memory", "collaborative",
}

# # Players / players: range "3-12", single "2", or lower-bound "1+".
PLAYER_COUNT_RE = re.compile(r"^\s*(\d+(?:-\d+)?|\d+\+)\s*$")
# Duration: "X mins", "X mins/player", "X mins/round" (X = integer).
DURATION_RE = re.compile(r"^\s*\d+\s*mins(?:/player|/round)?\s*$")
# Cloudinary URL must be versionless (no /v<digits>/ segment).
CLOUDINARY_HOST_RE = re.compile(r"^https://res\.cloudinary\.com/")
VERSION_SEGMENT_RE = re.compile(r"/v\d+/")
# Bold tags are forbidden in Description/Rules text.
BOLD_TAG_RE = re.compile(r"</?b\s*>", re.IGNORECASE)


class DescribeValidator:
    def __init__(self, data: Any, source_path: str = ""):
        self.data = data
        self.path = source_path
        self.errors:   List[Tuple[str, str]] = []
        self.warnings: List[Tuple[str, str]] = []

    def err(self, where: str, msg: str):
        self.errors.append((where, msg))

    def warn(self, where: str, msg: str):
        self.warnings.append((where, msg))

    # ── entry point ───────────────────────────────────────────────────────────
    def run(self):
        if not isinstance(self.data, dict):
            self.err("(root)", "Describe file must be a JSON object.")
            return self.errors, self.warnings
        self._check_name()
        self._check_url()
        self._check_banner()
        self._check_description()
        self._check_player_count_matches_game_json()
        self._check_rules()
        self._check_tags()
        self._check_optional_flags()
        return self.errors, self.warnings

    # ── individual field checks ───────────────────────────────────────────────
    def _check_name(self):
        name = self.data.get("name")
        if not isinstance(name, str) or not name.strip():
            self.err("name", "Required: a non-empty string game name.")
            return
        if name != name.strip():
            self.warn("name", f"Trailing/leading whitespace in name: {name!r}.")
        if name.startswith('"') or name.endswith('"'):
            self.warn("name", f"Name appears to be quoted ({name!r}). The admin UI stores raw text; quotes will render literally.")

    def _check_url(self):
        url = self.data.get("url")
        if not isinstance(url, str) or not url:
            self.err("url", f"Required: one of {sorted(URLS)}. Empty/missing.")
            return
        if url not in URLS:
            self.err("url",
                     f"URL must be exactly one of:\n"
                     f"  • {URL_CARDS}  (card games)\n"
                     f"  • {URL_OTHER}  (everything else)\n"
                     f"Got: {url!r}")
            return
        # Smart hint: if there is a sibling <stem>_cards.json or the game JSON uses
        # any card-deck actions, the game is a card game and must use dist_cards.
        is_card_game = self._infer_card_game()
        if is_card_game is True and url == URL_OTHER:
            self.err("url",
                     "Sibling cards JSON / card-deck actions detected — this is a card game. "
                     f"Use {URL_CARDS} instead.")
        elif is_card_game is False and url == URL_CARDS:
            self.warn("url",
                      "No card-deck actions detected, but URL is the card-games build. "
                      "Verify this is intentional (the dist_cards build is heavier).")

    def _check_banner(self):
        banner = self.data.get("banner")
        if not isinstance(banner, str) or not banner.strip():
            self.err("banner", "Required: a Cloudinary URL.")
            return
        if not CLOUDINARY_HOST_RE.match(banner):
            self.warn("banner", f"Banner is not a Cloudinary URL: {banner!r}. "
                                "Banners are expected to live in our Cloudinary cloud.")
        if VERSION_SEGMENT_RE.search(banner):
            self.err("banner",
                     f"Strip the /v<digits>/ segment from the URL so Cloudinary serves the latest "
                     f"replacement automatically. Got: {banner!r}")

    def _check_description(self):
        desc = self.data.get("description")
        if not isinstance(desc, dict):
            self.err("description", "Required: a JSON object with summary, description_title, "
                                    "# Players, players, Duration.")
            return
        required = ["summary", "description_title", "# Players", "players", "Duration"]
        for k in required:
            if k not in desc:
                self.err(f"description.{k}", "Required field missing.")
        # summary
        summary = desc.get("summary")
        if isinstance(summary, str):
            if not summary.strip():
                self.err("description.summary", "Empty string. Write a 1-2 sentence pitch.")
            elif len(summary) > 300:
                self.warn("description.summary",
                          f"{len(summary)} chars is long for a 1-2 sentence summary; consider trimming.")
            if BOLD_TAG_RE.search(summary):
                self.err("description.summary",
                         "Contains <b>/</b> tag. The Describe popup renders tags as literal text — "
                         "use plain text, quotes, or UPPERCASE for emphasis.")
        # description_title
        title = desc.get("description_title")
        if isinstance(title, str):
            if not title.endswith(" Overview"):
                self.err("description.description_title",
                         f"Must end with ' Overview' per the doc (e.g. '<Game Name> Overview'). Got: {title!r}.")
            else:
                game_name = self.data.get("name")
                if isinstance(game_name, str):
                    expected = f"{game_name} Overview"
                    if title != expected:
                        self.warn("description.description_title",
                                  f"Title is {title!r}, but name is {game_name!r}. "
                                  f"Convention is exactly '<name> Overview' (would be {expected!r}).")
        # # Players + players
        p_hash = desc.get("# Players")
        p_lower = desc.get("players")
        if isinstance(p_hash, str) and not PLAYER_COUNT_RE.match(p_hash):
            self.err("description.# Players",
                     f"Format must be a range like '3-12', a single number '2', or a lower-bound '1+'. Got: {p_hash!r}.")
        if isinstance(p_lower, str) and not PLAYER_COUNT_RE.match(p_lower):
            self.err("description.players",
                     f"Format must be a range, single number, or lower-bound. Got: {p_lower!r}.")
        if isinstance(p_hash, str) and isinstance(p_lower, str) and p_hash.strip() != p_lower.strip():
            self.err("description.players",
                     f"'players' ({p_lower!r}) must equal '# Players' ({p_hash!r}). The website renders both.")
        # Duration
        dur = desc.get("Duration")
        if isinstance(dur, str) and not DURATION_RE.match(dur):
            self.err("description.Duration",
                     f"Format must be 'X mins', 'X mins/player', or 'X mins/round' (X is an integer). Got: {dur!r}.")

    def _check_rules(self):
        # The Ludio Describe popup only accepts these section names — anything else
        # renders without proper styling or is silently dropped.
        ALLOWED_SECTION_NAMES = {
            "Basic Rules", "Day Voting", "Win Conditions", "Mechanics", "Advanced Rules",
        }

        rules = self.data.get("rules")
        if rules is None:
            self.err("rules", "Required: a JSON array of rule sections (Basic Rules at minimum).")
            return
        if not isinstance(rules, list) or not rules:
            self.err("rules", "Must be a non-empty list of rule sections.")
            return
        names_seen = set()
        for i, section in enumerate(rules):
            spath = f"rules[{i}]"
            if not isinstance(section, dict):
                self.err(spath, f"Each rule section must be an object; got {type(section).__name__}.")
                continue
            name = section.get("name")
            if not isinstance(name, str) or not name.strip():
                self.err(f"{spath}.name", "Section name is required (e.g. 'Basic Rules').")
            else:
                if name not in ALLOWED_SECTION_NAMES:
                    self.err(f"{spath}.name",
                             f"Section name {name!r} is not allowed. The Describe popup "
                             f"only accepts these section names: {sorted(ALLOWED_SECTION_NAMES)}. "
                             "Restructure your rules into one of these buckets.")
                if name in names_seen:
                    self.warn(f"{spath}.name", f"Duplicate section name {name!r}.")
                names_seen.add(name)
            content = section.get("content")
            if not isinstance(content, list) or not content:
                self.err(f"{spath}.content", "Each section needs a non-empty 'content' list of {title, text} items.")
                continue
            for j, item in enumerate(content):
                cpath = f"{spath}.content[{j}]"
                if not isinstance(item, dict):
                    self.err(cpath, f"Content item must be an object; got {type(item).__name__}.")
                    continue
                t = item.get("title")
                if not isinstance(t, str) or not t.strip():
                    self.err(f"{cpath}.title", "Required: non-empty section title.")
                txt = item.get("text")
                if not isinstance(txt, str) or not txt.strip():
                    self.err(f"{cpath}.text", "Required: non-empty section body text.")
                    continue
                if BOLD_TAG_RE.search(txt):
                    self.err(f"{cpath}.text",
                             "Contains <b>/</b> tag. The Describe popup renders HTML tags as literal text — "
                             "strip every <b> and </b>. The only HTML that works here is <br> / <br/> for line breaks.")
        # First section should be Basic Rules per the doc.
        if rules and isinstance(rules[0], dict) and rules[0].get("name") != "Basic Rules":
            self.warn("rules[0].name",
                      f"First section is {rules[0].get('name')!r}; convention is 'Basic Rules' first.")

    def _check_tags(self):
        tags = self.data.get("tags")
        if tags is None:
            self.err("tags", "Required: 2-4 tags from the canonical list.")
            return
        if not isinstance(tags, list):
            self.err("tags", f"Must be a list of strings; got {type(tags).__name__}.")
            return
        if not (2 <= len(tags) <= 4):
            self.err("tags", f"Use 2-4 tags. Got {len(tags)}.")
        for i, t in enumerate(tags):
            if not isinstance(t, str):
                self.err(f"tags[{i}]", f"Tag must be a string; got {type(t).__name__}.")
                continue
            if t not in ALLOWED_TAGS:
                self.err(f"tags[{i}]",
                         f"Tag {t!r} is not in the canonical list. Allowed: {sorted(ALLOWED_TAGS)}.")

    def _check_player_count_matches_game_json(self):
        """Cross-file check: the Describe's "# Players" string must agree with the sibling
        game JSON's `gameInitOptions.minPlayers` / `maxPlayers`. Mismatched player counts
        show wrong info on the website (Describe) versus the matchmaking rules (game JSON).
        """
        if not self.path:
            return
        # Resolve the sibling game JSON path the same way the card-game inference does.
        if self.path.endswith("_describe.json"):
            game_path = self.path[: -len("_describe.json")] + ".json"
        elif self.path.endswith(".json"):
            game_path = self.path[:-5] + ".json"
        else:
            return
        if not os.path.exists(game_path):
            return
        try:
            with open(game_path) as f:
                game = json.load(f)
        except (json.JSONDecodeError, OSError):
            return
        opts = game.get("gameInitOptions") or {}
        gmin = opts.get("minPlayers")
        gmax = opts.get("maxPlayers")
        if not (isinstance(gmin, int) and isinstance(gmax, int)):
            return  # Can't compare; let the game-JSON validator catch missing fields.

        desc = self.data.get("description") or {}
        hash_str = desc.get("# Players")
        if not isinstance(hash_str, str):
            return  # Already errored upstream as missing/wrong type.
        m = PLAYER_COUNT_RE.match(hash_str)
        if not m:
            return  # Already errored upstream for bad format.

        token = m.group(1)
        if "-" in token:
            lo, hi = (int(x) for x in token.split("-", 1))
        elif token.endswith("+"):
            lo, hi = int(token[:-1]), None
        else:
            lo = hi = int(token)

        if lo != gmin or (hi is not None and hi != gmax):
            describe_range = token
            game_range = (f"{gmin}-{gmax}" if gmin != gmax else f"{gmin}")
            self.err("description.# Players",
                     f"'# Players' = {describe_range!r} but the game JSON declares "
                     f"minPlayers={gmin}, maxPlayers={gmax} (which would read as {game_range!r}). "
                     f"The Describe popup and the game JSON must agree — the website renders one, "
                     f"matchmaking enforces the other.")
        elif hi is None and gmax > gmin:
            # Lower-bound notation but the game JSON has a real upper bound.
            self.warn("description.# Players",
                      f"'# Players' uses lower-bound notation ('{token}'), but the game JSON sets "
                      f"maxPlayers={gmax}. Consider '{gmin}-{gmax}' so the website shows the real ceiling.")

    def _check_optional_flags(self):
        for k in ("demo", "parallel"):
            v = self.data.get(k)
            if v is not None and not isinstance(v, bool):
                self.err(k, f"Optional field {k!r} must be a boolean if present; got {type(v).__name__}.")
        sheet = self.data.get("googleSheetId") or self.data.get("google_sheet_id") or self.data.get("Google Sheet ID")
        if isinstance(sheet, str) and sheet.strip():
            self.warn("googleSheetId", "Google Sheet ID is deprecated per the doc — leave blank.")

    # ── helpers ───────────────────────────────────────────────────────────────
    def _infer_card_game(self) -> "bool | None":
        """Return True/False if we can tell, else None (unknown)."""
        if not self.path:
            return None
        # Drop _describe.json suffix to get the game stem.
        path = self.path
        if path.endswith("_describe.json"):
            stem = path[: -len("_describe.json")]
        elif path.endswith(".json"):
            stem = path[:-5]
        else:
            return None
        cards_path = f"{stem}_cards.json"
        if os.path.exists(cards_path):
            return True
        game_path = f"{stem}.json"
        if not os.path.exists(game_path):
            return None
        try:
            with open(game_path) as f:
                game = json.load(f)
        except (json.JSONDecodeError, OSError):
            return None
        s = json.dumps(game)
        card_action_markers = ('"createDeck"', '"createCustomDeck"', '"createCard"',
                               '"dealDeck"', '"playCards"', '"moveCards"')
        return any(m in s for m in card_action_markers)


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 validate_describe_json.py path/to/<game>_describe.json")
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

    v = DescribeValidator(data, source_path=os.path.abspath(path))
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
