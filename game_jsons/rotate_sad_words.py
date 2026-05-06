#!/usr/bin/env python3
"""
rotate_sad_words.py
Weekly word rotation for Sound Act Draw on Ludio staging (ptr.ludio.gg).
Keeps 50% of current words, replaces the other 50% with Claude-generated ones.
Run directly: python3 rotate_sad_words.py
"""

import json
import random
import sys
import urllib.request
import urllib.error

LUDIO_BASE = "https://ptr.ludio.gg/api"
SETUP_ID = "f0b506a0-e4a0-4d00-a0f4-435a071c51f5"
EMAIL = "team@ludio.gg"
PASSWORD = "ClaudeBot"


def http(method, url, body=None, headers=None):
    data = json.dumps(body).encode() if body else None
    hdrs = {"Content-Type": "application/json"}
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def login():
    result = http("POST", f"{LUDIO_BASE}/auth/login",
                  body={"email": EMAIL, "password": PASSWORD})
    return result["accessToken"]


def get_setup(token):
    return http("GET", f"{LUDIO_BASE}/setup/{SETUP_ID}",
                headers={"Authorization": f"Bearer {token}"})


def patch_setup(token, raw):
    return http("PATCH", f"{LUDIO_BASE}/setup/{SETUP_ID}",
                body={"raw": raw},
                headers={"Authorization": f"Bearer {token}"})


def find_words(raw):
    for action in raw.get("beforeLoopActions", []):
        for sv in action.get("saveValueInCache", []):
            if sv.get("name") == "words":
                return sv["value"]
    raise ValueError("words array not found in JSON")


def set_words(raw, new_words):
    for action in raw.get("beforeLoopActions", []):
        for sv in action.get("saveValueInCache", []):
            if sv.get("name") == "words":
                sv["value"] = new_words
                return
    raise ValueError("words array not found in JSON")


def rotate(current_words, new_words):
    """Keep 50% of current, fill with new_words (deduped). Shuffle result."""
    random.shuffle(current_words)
    keep = current_words[:len(current_words) // 2]
    keep_set = set(keep)
    fresh = [w for w in new_words if w not in keep_set]
    target = len(current_words)
    combined = keep + fresh
    if len(combined) > target:
        combined = combined[:target]
    random.shuffle(combined)
    return combined


def main(new_words_json=None):
    """
    new_words_json: path to a JSON file containing a list of new words,
                    or None to read from stdin as JSON array.
    """
    if new_words_json:
        with open(new_words_json) as f:
            new_words = json.load(f)
    else:
        print("Reading new words from stdin (JSON array)...")
        new_words = json.loads(sys.stdin.read())

    print(f"Received {len(new_words)} new words")

    print("Logging in to Ludio API...")
    token = login()

    print("Fetching current setup...")
    setup = get_setup(token)
    raw = setup["raw"]

    current_words = find_words(raw)
    print(f"Current word count: {len(current_words)}")

    rotated = rotate(current_words, new_words)
    print(f"After rotation: {len(rotated)} words "
          f"({len(current_words)//2} kept, {len(rotated)-len(current_words)//2} new)")

    set_words(raw, rotated)

    print("Patching Ludio API...")
    patch_setup(token, raw)
    print("Done! Words rotated successfully on staging.")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
