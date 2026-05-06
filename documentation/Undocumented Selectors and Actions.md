# Undocumented Actions

The selectors and most actions used in Ludio games are covered in the official documentation PDFs (Basic Selectors.pdf, Advanced Selectors.pdf, Actions.pdf, Card Actions.pdf, Vote Actions.pdf, Score Actions.pdf, Dead Player Actions.pdf).

The following action is confirmed to appear in game JSONs but is absent from all documentation PDFs:

---

### `setLabelInspectors`

Controls which players can see/inspect deck labels. Appears in card-game setups alongside `setDeckInspectors`.

```json
{
  "key": "setLabelInspectors",
  "payload": {}
}
```

No required fields confirmed from game JSONs; full payload schema unknown.

---

## Notes on discrepancies between docs and usage

### `formatString` param convention
The PDF documents `formatString` as taking `{ format, args }` where `args` is a string array. In practice, game JSONs pass individual named params (`arg1`, `arg2`, etc.) rather than a single `args` list. The named-param style is what the validator and all existing games use.

### `createVideoboxDecks` key casing
The Card Actions PDF uses the heading `createVideoBoxDecks` (capital B) but documents the actual key as `createVideoboxDecks` (lowercase b). Use `createVideoboxDecks` in game JSONs.

### `getAllPlayers`
`getAllPlayers` appeared in `caption_contraption.json` as an apparent alias for `allPlayers`. It is not in any documentation PDF and is a bug — it has been replaced with `allPlayers`.
