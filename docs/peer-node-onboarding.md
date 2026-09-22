<!-- Generated from the MILS Bridge source repository (docs/integrations/peer-node-onboarding.md). Edit it there, not here. -->

# Connecting your MILS node to ours

**Who this is for:** a developer at another MILS node reading item payloads this
node owns.

**What you are calling:** the BLM node-to-node contract
([`../spec/mils-internal.yaml`](../spec/mils-internal.yaml)) as this
bridge serves it, from its own store.

```
https://bridge.example.com/rest
```

> **In a hurry?** [Peer node quickstart](peer-node-quickstart.md) is §4–§7 of this
> page with one consistent set of shell variables, for when onboarding is already
> done and you just want the commands.

That is the network convention — a node's node-to-node API sits at its REST
root — so you can derive it from the `NodeHostName` MILS publishes for us. Our
`/api` prefix does **not** apply to it. (`/rest/api/mils-internal` is retired
and answers `404`.)

> **Check your copy of the spec is current.** Until 2026-09-04 the `bearerAuth`
> description in `mils-internal.yaml` said `aud` names the **sender**. It names
> the **recipient** — one of _our_ names. If you are working from an older copy,
> re-fetch it; stamping your own audience is the single most common cause of a
> `401` on a first connection. §2 is authoritative either way.

---

## 1. Before you start

Onboarding is a MILS change plus a switch on our side — never a key exchange. We
hold no credential of yours; we verify against the certificate MILS publishes
for your actor.

Send us your `ActorCode`, `ActorId` and `NodeId`. We sync them from MILS and an
admin enables **both** the actor and the node — two separate switches, both
default off. **Nothing below works until that is done**, so confirm it with us
first.

Also ask us which `MILS_INTERNAL_AUTH` posture is live, because it decides
whether a token is required at all:

| Posture          | Item reads                           | `POST /MilsObjectAccesses`                                   |
| ---------------- | ------------------------------------ | ------------------------------------------------------------ |
| `open` (default) | No credential                        | Open, but can only ever answer `0` — no node to decide about |
| `actor`          | Token + our per-element rules        | Same                                                         |
| `node`           | Token, and it must resolve to a node | Requires a resolved node; answers a real `1` or `2`          |

Send the token even under `open` — it is ignored, not rejected, so it is free
forward-compatibility.

---

## 2. The token

A bearer RS256 JWT, signed with the private key matching the certificate MILS
publishes for your actor.

| Claim | Value                                                                                                                                                                       |
| ----- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `aud` | **One of _our_ names**: `conc-rest-api` or `conc-mils-api`                                                                                                                  |
| `iss` | Your `ActorTokenIssuer`, byte for byte as MILS publishes it. Usually **not** a URL — most actors in this network publish a bare word; a trailing slash is part of the value |
| `sub` | Your `ActorCode` (matched unbraced, case-insensitively)                                                                                                                     |
| `exp` | Required — a token carrying no `exp` is refused, because it would never expire. Minutes, not days                                                                           |
| `iat` | Recommended, not required (it is what an optional server-side lifetime cap measures against)                                                                                |

Header must be `alg: RS256` — we pin it, so `none` and any HMAC variant are
rejected before the signature is looked at.

Send it as an ordinary bearer credential — nothing else is required:

```
Authorization: Bearer <jwt>
```

A conventional MILS token names no node, and it does not need to: we resolve
which peer is calling from your actor's registered node (§3).

**`aud` names the recipient.** A token for us carries a name of ours; a token
for MILS carries `mils-rest-api`; a token for Blm carries `blm-mils-api`. That
is what stops a token being replayed at a different node. Stamping your own
`<your code>-rest-api` is the mistake to avoid.

Minting, in Node:

```js
import jwt from 'jsonwebtoken';

const token = jwt.sign(
  {
    iss: 'blm', // exactly as MILS publishes it — often a bare word, not a URL
    sub: 'blm', // your ActorCode
    aud: 'conc-mils-api', // OURS, not yours
  },
  privateKeyPem,
  { algorithm: 'RS256', expiresIn: '5m' }, // `exp` is required
);
```

---

## 3. How we validate it — worked through for node `blm`

Assume actor `blm` (BlockMaterials) owns one enabled node here, and sends
`Authorization: Bearer <jwt>` with `sub: "blm"`.

**Step 1 — Decode, trusting nothing.** We decode the payload without verifying
it, purely to pick which registry rows to look at.

**Step 2 — Select the principal** (`actor-registry/node-principal.ts`):

- We read `sub`. `"blm"` is not uuid-shaped, so we try `ActorCode` first:
  exactly one actor row matches → selection step `ACTOR_CODE`.
- Then we infer the node from **our** registry: the enabled nodes owned by
  `blm`. Exactly one → resolved, and that is the normal case. Zero enabled
  nodes, or more than one, is ambiguous — we refuse rather than attribute the
  read to the wrong peer. Tell us if you ever run several nodes off one actor.

**Step 3 — Verify against that actor's certificate**
(`actor-registry/actor-token-verifier.service.ts`), in this order:

1. The actor row must carry a `tokenIssuer`, or we refuse rather than let
   `jwt.verify` skip the issuer check.
2. Its `ActorCertificate` is parsed and its SPKI public key extracted.
3. `jwt.verify` with `algorithms: ['RS256']`, `issuer` pinned to the actor's
   `ActorTokenIssuer`, `audience` = `['conc-rest-api', 'conc-mils-api']`, and
   60 s clock tolerance.
4. `exp` must be present — a token with none would never expire, so it is
   refused even though its signature is good. Any lifetime cap
   (`ACTOR_JWT_MAX_TTL_SECONDS`, off by default) is applied here too, measured
   against `iat`.
5. The certificate's own `notAfter`.

**Step 4 — The request proceeds** as node `blm`, and our per-element access
rules are evaluated against that node.

Two consequences worth internalising:

- **The token selects a key; the registry decides which key.** Everything read
  in step 2 is unverified — it only picks which row to look at. Naming an
  identity you do not hold selects _that_ actor's certificate and fails at the
  signature, not at a string comparison. So we can afford to be tolerant about
  how you name yourself without loosening what you have to prove.
- **`blm` must stamp `conc-*`, not `blm-*`.** `blm-mils-api` is what _we_ stamp
  when calling _you_; it is refused inbound.

Common refusals, all of which produce the identical `401` below: `aud` is your
own name (or MILS's, or absent); `iss` differs by a trailing slash; the token
carries no `exp`; your `ActorCode` is not unique across the network (we refuse
both rather than guess); the actor or node is not enabled here; the certificate
expired; your actor owns several enabled nodes and the token names none.

---

## 4. Verify your setup

```bash
BASE=https://bridge.example.com
TOKEN=<your jwt>

curl -sS "$BASE/api/actor-registry/whoami" \
  -H "Authorization: Bearer $TOKEN"
```

Note the `/api` prefix — this one is not under `/rest`.

```json
{
  "actorId": "…",
  "actorCode": "blm",
  "actorName": "BlockMaterials",
  "contactEmail": "…",
  "tokenIssuer": "blm",
  "actorState": 0,
  "audience": "conc-rest-api, conc-mils-api",
  "node": {
    "nodeId": "…",
    "nodeName": "Blm",
    "ownerActorId": "…",
    "ownerActorCode": "blm"
  }
}
```

- **`200` with a `node` object** — fully wired, proceed.
- **`200` with `"node": null`** — your credential is good, but we could not
  resolve which node you are: your actor owns no _enabled_ node here. Ask us to
  enable it. Under `node` posture this state gives `200` here and `401` at
  `/rest/*`, which is exactly the signal.
- **`audience` differs from what you stamped** — stamp what this field says.

---

## 5. The read flow

**Permission is asked for an Object; a payload is read for an Item under it.**
Two different ids, never interchangeable. One grant covers every item of that
object we own.

### 5.1 Ask MILS who owns the item

```bash
curl -sS "$MILS/Items/104fa31f-55ea-4e76-baf3-8dd9386e6b90" \
  -H "Authorization: Bearer $MILS_TOKEN"
```

Take `ItemOwnerNodeId` (is it us?) and `ObjectId` (what you ask permission for).

### 5.2 Ask us for the object

```bash
curl -sS -X POST "$BASE/rest/MilsObjectAccesses" \
  -H 'Content-Type: application/json' \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"ObjectId":"{30699f06-146b-499a-a167-2937787f6225}"}'
```

```json
201 → { "ObjectId": "{74ef754b-01eb-438c-91f3-52a3637339e0}" }
```

> **The `201` returns the id of the access _record_ — not the ObjectId you asked
> about.** Both fields are named `ObjectId`; the values are different things.
> This is the contract's naming, not ours. Keep the returned id: it is what you
> poll, and re-checking it beats filing a second request on our server.

### 5.3 Poll the state

```bash
curl -sS "$BASE/rest/MilsObjectAccesses/74ef754b-01eb-438c-91f3-52a3637339e0"
```

```json
200 → { "ObjectAccessState": 1, "ObjectId": "{74ef754b-…}" }
```

| State | Meaning                                                             |
| ----- | ------------------------------------------------------------------- |
| `1`   | Granted                                                             |
| `2`   | Denied                                                              |
| `0`   | **Pending** — recorded, nothing granted. What an anonymous ask gets |
| other | **Treat as pending**                                                |

The contract enumerates nothing, so these are our convention. Treat `0` and
anything unrecognised as pending, never as consent — being wrong should cost you
a read that does not happen. Poll this rather than re-POSTing.

We grant when you may read **at least one** element we hold under the object. An
object we hold nothing for falls through to our default policy, which is
fail-closed. If you get a `2`, the conversation is with our operator, not the
API.

### 5.4 Read the payload

Path parameters take the **bare uuid**.

```bash
ITEM=104fa31f-55ea-4e76-baf3-8dd9386e6b90

# The stored payload, verbatim, as text/plain
curl -sS "$BASE/rest/MilsItems/$ITEM/ItemData" \
  -H "Authorization: Bearer $TOKEN"

# The file bytes, with stored Content-Type, ETag and Content-Disposition
curl -sS -D - -o item.bin "$BASE/rest/MilsItems/$ITEM/ItemFile" \
  -H "Authorization: Bearer $TOKEN"

# The same bytes, base64 as text/plain (the BLM contract's own operation)
curl -sS "$BASE/rest/MilsItems/$ITEM/BinaryData" \
  -H "Authorization: Bearer $TOKEN" | base64 -d > item.bin
```

For a registered file, `ItemData` is a JSON descriptor (name, mime, size,
sha256) pointing at `ItemFile`. Prefer `ItemFile` over `BinaryData` for anything
large — base64 costs a third more bytes and cannot be streamed usefully.

`404` = nothing stored for that item. `410` = the record exists but our local
copy of the blob is gone; tell us, it needs a re-sync on our side.

**A grant is a gate, not a bypass.** Our per-element rules still apply to each
read, so a granted object can still answer `403` on one of its items. Handle
that.

Two more operations round out the surface, both served since 2026-09-08:

- **`GET /MilsItems?ObjectId={…}&ItemTypeId={…}`** — which items we hold under
  one object, of one type. Both filters are required and braced, the reply is
  `{ AvailableRowCount, MilsItems: [{ ItemId, ObjectId, ItemDescription }] }`,
  and `ItemDescription` is our own label for the element, not a MILS field —
  the contract publishes no description for an Item. Our per-element rules
  narrow the list the same way they can `403` a single read, so what is listed
  is what you may read. Note `curl` treats `{}` as glob syntax: pass `-g`.
- **`GET /MilsItems/{ItemId}/PropertyData`** — the item's property data as
  opaque `text/plain`, `404` when none is stored (which is the common case: it
  is set by hand, never derived from a registration).

The [quickstart](peer-node-quickstart.md) §5–§6 has both as runnable commands.

---

## 6. Rules that bite

**GUID braces.** Bodies (both directions) use braced GUIDs, `{6cb8eb2f-…-2c19}`;
path parameters use the bare uuid. We tolerate braces in a path, but bodies are
validated strictly — a bare GUID in a POST body is a `400`.

**Every rejected token gets the same `401`**, whatever went wrong with it:

```json
{
  "message": "Invalid actor token.",
  "error": "Unauthorized",
  "statusCode": 401
}
```

Deliberately uniform, so nobody can probe which actors exist here. (Sending
**no** credential at all is the one other shape: same status, but
`"Authentication required."` — so that one distinction is safe to branch on,
and nothing else is.)

The real reason **is** recorded on our side with your request — route, IP, the
token's digest and decoded claims, how far the resolution ladder got. **The
fastest route through a `401` is to ask us**; send the approximate timestamp and
your `ActorCode`. If you cannot get any token accepted, send us the token
itself (it is a bearer credential, so treat it as one) and we will run it
through our inspector, which reports the ladder step it reached, `aud` / `iss` /
`sub` **expected beside actual**, and whether the signature verified against the
certificate MILS publishes for you — which is what separates "my minting is
wrong" from "my registration is wrong". We cannot do the reverse and hand you a
working token: we hold no key of yours, and the tokens we can mint are addressed
to _you_ and signed as _us_.

**Rate limits.** 300 requests / 60 s per IP **per endpoint** — the budget is not
shared across routes, so exhausting one read does not stop another;
`POST /MilsObjectAccesses` is capped at 10/minute in every posture, and a
request we refuse for a malformed body still counts against that. Access records
are pruned after 31 days, so a `404` on an old access id means "ask again", not
"denied".

---

## 7. Checklist

- [ ] Actor and node published in MILS, `NodeOwnerActorId` pointing at the actor
- [ ] Confirmed with us that **both** `enabled` switches are on
- [ ] Confirmed which `MILS_INTERNAL_AUTH` posture is live
- [ ] Token: RS256, `aud` = `conc-rest-api` or `conc-mils-api`, `iss` byte-exact,
      `sub` = your `ActorCode`, short `exp`
- [ ] `whoami` returns `200` with a non-null `node`
- [ ] Handshake before every payload read; `0` and unknown states are pending
- [ ] Braced GUIDs in bodies, bare in paths
- [ ] Per-item `403` handled
