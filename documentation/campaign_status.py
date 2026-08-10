#!/usr/bin/env python3
"""Refactor Readiness Campaign — live status + next-game picker.

Source of truth is LIVE PRODUCTION (https://try.ludio.gg/api/setup), not any
committed tracker, so the campaign self-corrects every run. Excludes demo
copies (type == "DEMO"). Computes the 3 refactor flags per game and prints the
next incomplete game to work on (alphabetical, skipping any listed in
documentation/campaign_blocked.txt).

Usage:
  python3 documentation/campaign_status.py            # summary + next game
  python3 documentation/campaign_status.py --all      # full per-game table
  python3 documentation/campaign_status.py --json      # machine-readable next game
"""
import json, sys, os, urllib.request

PROD_LIST = "https://try.ludio.gg/api/setup"
BLOCKED_FILE = os.path.join(os.path.dirname(__file__), "campaign_blocked.txt")


def fetch_setups():
    with urllib.request.urlopen(PROD_LIST, timeout=60) as r:
        return json.load(r)


def walk(o):
    if isinstance(o, dict):
        yield o
        for v in o.values():
            yield from walk(v)
    elif isinstance(o, list):
        for v in o:
            yield from walk(v)


def count_key(o, key):
    n = 0
    if isinstance(o, dict):
        if o.get("key") == key:
            n += 1
        for v in o.values():
            n += count_key(v, key)
    elif isinstance(o, list):
        for v in o:
            n += count_key(v, key)
    return n


def analyze(raw):
    gio = raw.get("gameInitOptions", {}) if isinstance(raw, dict) else {}
    strings = gio.get("strings")
    has_strings = isinstance(strings, dict) and len(strings) > 0

    vs = raw.get("visualSettings") if isinstance(raw, dict) else None
    has_vs = isinstance(vs, dict) and any(
        vs.get(k) for k in ("textColor", "borderColor", "backgroundColor")
    )

    has_tut_mv = False
    for node in walk(raw):
        if node.get("key") == "createMixVote" and "tutorial" in json.dumps(
            node.get("payload", {})
        ).lower():
            has_tut_mv = True
            break

    tut_notif = tut_convo = False
    gl = raw.get("gameLoop", []) if isinstance(raw, dict) else []
    for g in gl if isinstance(gl, list) else []:
        if not isinstance(g, dict):
            continue
        gname = str(g.get("name", "")).lower()
        sc = json.dumps(g.get("skipCondition", "")).lower()
        if "tutorial" in gname or "tutorial" in sc:
            if count_key(g.get("actions", []), "createNotification") > 0:
                tut_notif = True
            if count_key(g.get("actions", []), "createConversationGroup") > 0:
                tut_convo = True
    std_tut = has_tut_mv and tut_notif
    if std_tut:
        tut_state = "ok"
    elif has_tut_mv and tut_convo:
        tut_state = "convo-group (convert)"
    elif tut_notif or tut_convo or has_tut_mv:
        tut_state = "partial/legacy"
    else:
        tut_state = "none (build from scratch)"
    return has_strings, has_vs, std_tut, tut_state


def load_blocked():
    if not os.path.exists(BLOCKED_FILE):
        return set()
    out = set()
    with open(BLOCKED_FILE) as f:
        for line in f:
            line = line.split("#", 1)[0].strip()
            if line:
                out.add(line.lower())
    return out


def main():
    setups = fetch_setups()
    blocked = load_blocked()
    games = []
    for x in setups:
        if x.get("type") == "DEMO":
            continue
        hs, hv, st, ts = analyze(x.get("raw", {}))
        games.append({
            "name": x.get("name"),
            "id": x.get("id"),
            "strings": hs, "visualSettings": hv, "tutorial": st,
            "tutorial_state": ts,
            "done": hs and hv and st,
        })
    games.sort(key=lambda g: g["name"].lower())
    remaining = [g for g in games if not g["done"]]

    def is_blocked(g):
        return g["id"].lower() in blocked or g["name"].lower() in blocked

    next_game = next((g for g in remaining if not is_blocked(g)), None)

    if "--json" in sys.argv:
        print(json.dumps(next_game))
        return

    total, comp = len(games), sum(g["done"] for g in games)
    print(f"Campaign status: {comp}/{total} complete, {len(remaining)} remaining "
          f"({sum(is_blocked(g) for g in remaining)} blocked)")
    print(f"  missing strings: {sum(not g['strings'] for g in remaining)} | "
          f"visualSettings: {sum(not g['visualSettings'] for g in remaining)} | "
          f"tutorial: {sum(not g['tutorial'] for g in remaining)}")

    if "--all" in sys.argv:
        Y = lambda b: "Y" if b else "-"
        print()
        for g in games:
            flag = "DONE" if g["done"] else ("BLOCKED" if is_blocked(g) else "")
            print(f"  {Y(g['strings'])}{Y(g['visualSettings'])}{Y(g['tutorial'])}  "
                  f"{g['name']:26} {g['id']}  {g['tutorial_state']:24} {flag}")

    print()
    if next_game:
        need = []
        if not next_game["strings"]: need.append("string-hoisting")
        if not next_game["visualSettings"]: need.append("visualSettings-colors")
        if not next_game["tutorial"]: need.append(f"tutorial [{next_game['tutorial_state']}]")
        print("NEXT GAME:", next_game["name"])
        print("  setup id:", next_game["id"])
        print("  needs:   ", ", ".join(need))
    else:
        print("NEXT GAME: none — every remaining game is blocked, or campaign complete.")


if __name__ == "__main__":
    main()
