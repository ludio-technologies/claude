#!/usr/bin/env python3
"""Rainbow Blackjack — give each rule set its own table wallpaper.

The next patch layer on top of `patch_specials_and_penalties.py` (which is
itself the layer above `build_naughty.py`; none of them are idempotent, so each
change set gets its own script that pulls live prod and applies named patches).

The background can only follow the variant once the host has answered the
Nice/Naughty vote, so:

  * `beforeLoopActions[0]` keeps showing the neutral `wallpaperImg` through the
    tutorial and both votes — otherwise there would be no background at all
    until the vote resolved.
  * a second `changeBackground` fires immediately after the vote's derived
    variables land, switching to `nice_wallpaper` or `naughty_wallpaper`.
  * the Rainbow celebration swaps to `rainbow_gif` and back; its restore is
    repointed at the variant wallpaper so the board does not revert to the
    neutral one mid-game.

  python3 scripts/rainbow_blackjack/patch_variant_wallpaper.py
  python3 scripts/rainbow_blackjack/patch_variant_wallpaper.py --local
"""
import json
import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rb_dsl import variant_vote_actions  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
GAME = os.path.join(REPO, "game_jsons", "rainbow_blackjack.json")
PROD = "https://try.ludio.gg/api/setup/7271e197-2822-4fd2-bdbd-1438f5d71d60"

BASE = "https://res.cloudinary.com/liars-club/image/upload/images/rainbow_blackjack"
WALLPAPERS = {"nice_wallpaper": BASE + "/nice_wallpaper.png",
              "naughty_wallpaper": BASE + "/naughty_wallpaper.png"}
VAR = "variantWallpaper"


def patch_images(g):
    """Register the two new wallpapers as image aliases."""
    images = g["gameInitOptions"]["images"]
    for alias, url in WALLPAPERS.items():
        images[alias] = {"url": url}


def patch_variant_cache(g):
    """Rebuild the derived-variables action so it also resolves the wallpaper."""
    bla = g["beforeLoopActions"]
    at = next(i for i, a in enumerate(bla)
              if any(e["name"] == "zeroCard" for e in a.get("saveValueInCache", [])))
    fresh = variant_vote_actions()[1]

    before = {e["name"] for e in bla[at]["saveValueInCache"]}
    after = {e["name"] for e in fresh["saveValueInCache"]}
    assert not before - after, "dropped cached variables: %s" % sorted(before - after)
    assert VAR in after, "%s missing from rb_dsl's derived block" % VAR
    bla[at] = fresh
    return at, sorted(after - before)


def patch_apply_wallpaper(g, after_index):
    """Switch the board to the chosen variant's wallpaper, once it is known."""
    g["beforeLoopActions"].insert(after_index + 1, {
        "key": "changeBackground",
        "payload": {"cached": {"image": VAR}},
    })


def patch_rainbow_restore(g):
    """The Rainbow celebration must put the variant wallpaper back, not the
    neutral one it was showing before the vote."""
    grp = next(x for x in g["gameLoop"]
               if isinstance(x, dict) and x.get("name") == "Handle rainbow player")
    restores = [a for a in grp["actions"]
                if a.get("key") == "changeBackground"
                and (a.get("payload") or {}).get("cached", {}).get("image")
                == "wallpaperImg"]
    assert len(restores) == 1, "expected one wallpaper restore, found %d" % len(restores)
    restores[0]["payload"]["cached"]["image"] = VAR
    return grp["name"]


def load_game():
    if "--local" in sys.argv:
        return json.load(open(GAME))
    with urllib.request.urlopen(PROD, timeout=90) as r:
        raw = json.load(r).get("raw")
    return json.loads(raw) if isinstance(raw, str) else raw


def main():
    g = load_game()

    patch_images(g)
    at, added = patch_variant_cache(g)
    patch_apply_wallpaper(g, at)
    grp = patch_rainbow_restore(g)

    with open(GAME, "w") as f:
        json.dump(g, f, indent=2)
        f.write("\n")

    print("wrote %s" % GAME)
    print("  image aliases added: %s" % ", ".join(sorted(WALLPAPERS)))
    print("  new cached variables: %s" % ", ".join(added))
    print("  changeBackground inserted at beforeLoopActions[%d]" % (at + 1))
    print("  %r restore repointed at %s" % (grp, VAR))
    print("  size: %.1f KB" % (os.path.getsize(GAME) / 1024.0))


if __name__ == "__main__":
    main()
