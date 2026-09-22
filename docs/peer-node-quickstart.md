<!-- Generated from the MILS Bridge source repository (docs/integrations/peer-node-quickstart.md). Edit it there, not here. -->

# Reading our items — quickstart

**Who this is for:** a developer at another MILS node who is already registered
with us and wants the shortest path from a token to a payload.

This is the condensed version of
[Peer node onboarding](peer-node-onboarding.md). It assumes the parts that only
happen once are done: your actor and node are published in MILS, we have enabled
**both** of them here, and you can mint a token addressed to us. If any of that
is not true yet, or a `401` is not obvious, read the full guide — it explains why.

---

## 0. Set these once

Every command below uses these names, unchanged. Paste this block into your
shell first.

```bash
# Us — the node you are reading from. Our /api prefix does NOT apply to /rest.
BASE=https://bridge.example.com

# MILS itself — where you look up who owns an item.
MILS=https://mils.example.org/rest

# Your JWT for US: RS256, aud = conc-rest-api or conc-mils-api,
# iss = your ActorTokenIssuer byte-exact, sub = your ActorCode, short exp.
TOKEN='<your jwt for us>'

# Your JWT for MILS: same key, but aud = mils-rest-api.
MILS_TOKEN='<your jwt for mils>'

# The item you want, as a BARE uuid (no braces — this goes in paths).
ITEM=79e09709-d263-4a93-bc04-bf57074171f7
```

`OBJECT`, `TYPE` and `ACCESS` are filled in from responses as you go.

**Braces:** **bodies** and the **query filters** on `GET /MilsItems` use braced
GUIDs, `{104fa31f-…}`; **path parameters** use the bare uuid. Keep every variable
above bare and add the braces at the two call sites that want them (steps 3 and 5) — a bare GUID in either is a `400`.

**`curl` eats braces.** `{}` is glob syntax, so `curl "…?ObjectId={$OBJECT}"`
silently sends something else and you get a `400` about the pattern. Pass `-g`
(`--globoff`) on any command with braces **in the URL**; a `-d` body is
unaffected. Every example below already does.

---

## 1. Check we know who you are

```bash
curl -sS "$BASE/api/actor-registry/whoami" \
  -H "Authorization: Bearer $TOKEN"
```

Note the `/api` prefix — this is the one call that is not under `/rest`.

```json
{
  "actorCode": "blm",
  "tokenIssuer": "blm",
  "audience": "conc-rest-api, conc-mils-api",
  "node": { "nodeId": "…", "nodeName": "Blm", "ownerActorCode": "blm" }
}
```

- **`200` with a `node` object** — you are wired up. Continue.
- **`200` with `"node": null`** — your token is fine, but your actor owns no
  _enabled_ node here. Ask us to enable it; nothing under `/rest` will work yet.
- **`401`** — every refusal looks identical on purpose. Check `aud` is one of
  **our** names (not yours, not MILS's), `iss` matches byte for byte, and the
  token carries an `exp`. If it still fails, send us your `ActorCode` and the
  approximate timestamp — we can see the real reason, you cannot.
- **`audience` differs from what you stamped** — stamp what that field says.

---

## 2. Ask MILS who owns the item

```bash
curl -sS "$MILS/Items/$ITEM" \
  -H "Authorization: Bearer $MILS_TOKEN"
```

Three fields matter: `ItemOwnerNodeId` (is it us?), `ObjectId` and `ItemTypeId`.
Permission is asked for the **Object**, the payload is read for the **Item**, and
the two of them together are what `GET /MilsItems` filters on in step 5. No two
of the three are ever the same value.

```bash
# Strip the braces MILS puts around them — we want bare uuids.
OBJECT=da928a7b-5b61-4ffe-8be3-75eff0ef7a70
TYPE=b54fd06d-5c9f-441a-b132-0bc779c62de2
```

---

## 3. Ask us for access to the object

```bash
curl -sS -X POST "$BASE/rest/MilsObjectAccesses" \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d "{\"ObjectId\":\"{$OBJECT}\"}"
```

Braces here, because it is a body.

```json
201 → { "ObjectId": "{74ef754b-01eb-438c-91f3-52a3637339e0}" }
```

> The `201` returns the id of the access **record**, not the object you asked
> about. Both fields are called `ObjectId`; the values are different things.
> Keep this one.

```bash
ACCESS=74ef754b-01eb-438c-91f3-52a3637339e0
```

One grant covers every item of that object we own — so you do this once per
object, not once per item. Capped at 10 requests/minute in every posture.

---

## 4. Poll the state

```bash
curl -sS "$BASE/rest/MilsObjectAccesses/$ACCESS" \
  -H "Authorization: Bearer $TOKEN"
```

```json
200 → { "ObjectAccessState": 1, "ObjectId": "{74ef754b-…}" }
```

| State   | Meaning                       |
| ------- | ----------------------------- |
| `1`     | Granted — go to step 5        |
| `2`     | Denied — talk to our operator |
| `0`     | Pending                       |
| _other_ | **Treat as pending**          |

Poll `$ACCESS` rather than POSTing again. Never read anything but `1` as consent
— being wrong should cost you a read that does not happen. A `404` on an old
`$ACCESS` means the record was pruned (31 days): ask again from step 3.

---

## 5. List what else is under that object

One grant covers the whole object, so this is usually the next thing you want:
which of its items do we actually hold?

Both filters are **required** by the contract, and both are braced. Both came
out of the same `GET /Items/$ITEM` body in step 2:

```bash
curl -sS -g "$BASE/rest/MilsItems?ObjectId={$OBJECT}&ItemTypeId={$TYPE}" \
  -H "Authorization: Bearer $TOKEN"
```

```json
200 → {
  "AvailableRowCount": 2,
  "MilsItems": [
    {
      "ItemDescription": "Ground floor slab",
      "ItemId": "{79e09709-d263-4a93-bc04-bf57074171f7}",
      "ObjectId": "{da928a7b-5b61-4ffe-8be3-75eff0ef7a70}"
    },
    {
      "ItemDescription": "as-built-plan.pdf",
      "ItemId": "{104fa31f-55ea-4e76-baf3-8dd9386e6b90}",
      "ObjectId": "{da928a7b-5b61-4ffe-8be3-75eff0ef7a70}"
    }
  ]
}
```

Optional: `FilterText` (substring, case-insensitive), `SkipRowCount`,
`MaxRowCount` (default `50`, max `200`; `201` is a `400`).

```bash
curl -sS -g "$BASE/rest/MilsItems?ObjectId={$OBJECT}&ItemTypeId={$TYPE}&MaxRowCount=1&SkipRowCount=1" \
  -H "Authorization: Bearer $TOKEN"
```

Four things worth knowing before you build on it:

- **`AvailableRowCount` is the total after filtering, before paging.** Page with
  `SkipRowCount` until you have that many rows; a skip past the end returns an
  empty array and the true count, not `0`.
- **`ItemDescription` is our local name for the element, not a MILS field.** The
  MILS contract publishes no description for an Item, so there is nothing to
  round-trip — this is the label our operators see. Display it; do not key on it.
- **An empty list is not an error, and not always "we hold nothing".** An
  unknown object, an unknown item type, and an item we registered before we
  started storing its `ItemTypeId` all look identical from out here:
  `{"AvailableRowCount":0,"MilsItems":[]}`. If you know we hold something and the
  list disagrees, ask us — that last case is ours to fix, and `ItemData` on the
  id you already have still works meanwhile.
- **The list can be shorter than the object.** Our per-element rules apply to it,
  the same ones that can `403` a single read (below). What you see listed is what
  you may read.

Same posture as everything else here: with `MILS_INTERNAL_AUTH=node` this is a
`401` without your token.

---

## 6. Read the payload

Paths take the bare uuid, so `$ITEM` goes in as-is.

```bash
# The stored payload, verbatim, as text/plain
curl -sS "$BASE/rest/MilsItems/$ITEM/ItemData" \
  -H "Authorization: Bearer $TOKEN"

# The file bytes, with stored Content-Type, ETag and Content-Disposition
curl -sS -D - -o item.bin "$BASE/rest/MilsItems/$ITEM/ItemFile" \
  -H "Authorization: Bearer $TOKEN"

# The same bytes, base64 as text/plain (the BLM contract's own operation)
curl -sS "$BASE/rest/MilsItems/$ITEM/BinaryData" \
  -H "Authorization: Bearer $TOKEN" | base64 -d > item.bin

# The item's property data, verbatim, as text/plain
curl -sS "$BASE/rest/MilsItems/$ITEM/PropertyData" \
  -H "Authorization: Bearer $TOKEN"
```

For a registered file, `ItemData` is a JSON descriptor (name, mime, size,
sha256) pointing at `ItemFile`. Prefer `ItemFile` over `BinaryData` for anything
large — base64 costs a third more bytes and cannot be streamed usefully.

`PropertyData` is **opaque text**, not JSON — the BLM contract types it as a
plain string and we serve exactly what our operator stored:

```
200 text/plain →
NetFloorArea=124.5
FireRating=EI60
```

What belongs in it is values against the property schema MILS publishes for this
item's `ItemTypeId` (`GET /PropertyTypes?ItemTypeId=…`, from MILS — we do not
serve that operation), but we do not validate it against that schema, so parse
defensively. It is set by hand, never derived from a registration: most items
have a payload and no property data, and answer `404`.

- `403` — a grant is a **gate, not a bypass**: our per-element rules still apply
  to each read, so a granted object can refuse one of its items. Handle it.
- `404` — nothing stored for that item.
- `410` — the record exists but our copy of the blob is gone. Tell us; it needs
  a re-sync on our side.

Rate limit: 300 requests / 60 s per IP **per endpoint** — the budget is not
shared across routes.

---

## Checklist

- [ ] `whoami` returns `200` with a non-null `node`
- [ ] `$TOKEN` is addressed to **us**, `$MILS_TOKEN` to MILS — two different `aud`
- [ ] `$OBJECT` and `$TYPE` from `GET /Items/$ITEM`, braced in the POST body and the list query
- [ ] `$ACCESS` kept and polled; `0` and anything unrecognised are pending
- [ ] `curl -g` wherever braces are in the URL
- [ ] Paging driven by `AvailableRowCount`, not by a short page
- [ ] Per-item `403` handled even after a grant, including on a listed item
