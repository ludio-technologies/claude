import json, urllib.request

DECK_ID = "3f3cfcdc-c2ce-490f-b242-c0af94ad5763"
SETUP_ID = "face690b-958d-4fdc-8019-c3905106e1de"
G = "/Users/ankitbuddhiraju/Documents/claude/Code/game_jsons/"

def patch(url, body):
    req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"}, method="PATCH")
    with urllib.request.urlopen(req, timeout=90) as r:
        return r.status

def get(url):
    with urllib.request.urlopen(url, timeout=60) as r:
        return json.loads(r.read())

cards = json.load(open(G + "grapheme_cards.json"))
print("deck PATCH:", patch("https://ptr.ludio.gg/api/deck/" + DECK_ID, {"script": cards}))
gd = get("https://ptr.ludio.gg/api/deck/grapheme_cards")  # GET by script name
sc = gd["script"]
print("  deck cards:", len(sc["cards"]), "| has done:", any(c["name"] == "done" for c in sc["cards"]),
      "| e img folder:", next(c["image"] for c in sc["cards"] if c["name"] == "e").split("/")[-2])

raw = json.load(open(G + "paperback.json"))
desc = json.load(open(G + "paperback_describe.json"))
body = {"name": "Grapheme", "banner": desc["banner"], "description": desc["description"],
        "rules": desc["rules"], "tags": desc["tags"], "raw": raw, "settings": []}
print("setup PATCH:", patch("https://ptr.ludio.gg/api/setup/" + SETUP_ID, body))
gs = get("https://ptr.ludio.gg/api/setup/" + SETUP_ID)
print("  name:", gs.get("name"), "| raw matches:",
      json.dumps(gs.get("raw"), sort_keys=True) == json.dumps(raw, sort_keys=True),
      "| banner folder:", gs.get("banner").split("/")[-2])
