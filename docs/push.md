<!-- Generated from the MILS Bridge source repository (docs/integrations/push.md). Edit it there, not here. -->

# Inbound push

Other systems — an ERP webhook, an integration platform (n8n, Make, Power
Automate, Zapier), a nightly script — **push** JSON records to an
administrator's **channel**. Each request is signed with the channel's secret.
Each record becomes one MILS element (`push-record`, keyed
`push:<channel slug>/<record key>`), and pushing the same key again **updates**
that element instead of registering a second one — the
keyed record machinery.

Phase 1 (`plans/inbound-push-plan.md`): HMAC channels, intake, delivery status,
the `push:channels` CLI. The console has a status panel only; actor-JWT
channels, archive operations and the public OpenAPI section are phase 3.

## Turning it on

| Variable                     | Default | Meaning                                                                                                                    |
| ---------------------------- | ------- | -------------------------------------------------------------------------------------------------------------------------- |
| `PUSH_INBOUND`               | off     | Only the literal `on` registers the routes. Off: both `/api/integration/push/*` and `/push-channels/*` answer 404          |
| `PUSH_MAX_BODY_BYTES`        | 5 MiB   | Raw-body cap on a delivery                                                                                                 |
| `PUSH_MAX_RECORDS`           | 500     | Records per delivery                                                                                                       |
| `PUSH_TIMESTAMP_TOLERANCE_S` | 300     | Replay window of a signature                                                                                               |
| `PUSH_RATE_PER_MINUTE`       | 120     | Deliveries per channel per minute (token bucket; `0` = off). The global per-IP throttler does not apply to the push routes |
| `PUSH_SECRET_OVERLAP_HOURS`  | 24      | How long the previous secret verifies after a rotation                                                                     |

Every push creates or updates elements with **this node's** MILS credential,
which is why channels are admin-created, confined, rate-limited and off by
default. `INTEGRATION_ACTOR_WRITES` is not involved: a channel is its own
explicit grant.

## A channel

Created with `pnpm --filter @bridge/api push:channels -- --add channel.json`
(or `POST /api/integration/push-channels`, `ADMIN`). The answer carries the
**secret, once**; store it in the sender. `--rotate <slug>` issues a new one
while the old one keeps verifying for `PUSH_SECRET_OVERLAP_HOURS`.

```json
{
  "name": "ERP assets",
  "slug": "erp",
  "fixedObjectId": "{…}",
  "fixedItemTypeId": "{…}",
  "shape": {
    "keyPointer": "/asset/number",
    "namePointer": "/asset/label",
    "payloadPointer": "/data"
  }
}
```

- **The shape** is a set of [JSON pointers](https://www.rfc-editor.org/rfc/rfc6901):
  `keyPointer` (required — a string or a number), `namePointer`,
  `payloadPointer` (default `""`, the whole record, which must be an object).
- **The target** is fixed on the channel (the default and the safest: senders
  name no target), or read from each record with `objectIdPointer` (and
  `itemTypeIdPointer`). Then the channel needs `allowedRootIds` — MILS **root**
  objects — and every record's object is climbed to its root and refused with
  `TARGET_NOT_ALLOWED` when that root is not allowed. A channel can never write
  into an arbitrary object.
- The slug is in the URL and in every element's key, so it is immutable.

## Signing a request

```
POST /api/integration/push/<slug>/records
X-Bridge-Timestamp: <unix seconds>
X-Bridge-Signature: v1=<hex HMAC-SHA256(secret, "<timestamp>.<raw body>")>
Idempotency-Key: <optional, ≤ 128 printable characters>
```

The signature covers the timestamp (a captured request expires after the
window) and the exact body bytes (a leaked header cannot carry another body).
Several `v1=` values separated by commas are accepted, so a sender can sign
with both secrets during a rotation.

```bash
ts=$(date +%s)
sig=$( { printf '%s.' "$ts"; cat body.json; } | openssl dgst -sha256 -hmac "$SECRET" -hex | sed 's/^.*= //')
curl -X POST "$BRIDGE/api/integration/push/erp/records" \
  -H 'Content-Type: application/json' \
  -H "X-Bridge-Timestamp: $ts" -H "X-Bridge-Signature: v1=$sig" \
  --data-binary @body.json
```

```python
import hashlib, hmac, time, requests
body = open("body.json", "rb").read()
ts = str(int(time.time()))
sig = hmac.new(SECRET.encode(), ts.encode() + b"." + body, hashlib.sha256).hexdigest()
requests.post(f"{BRIDGE}/api/integration/push/erp/records", data=body, headers={
    "Content-Type": "application/json", "X-Bridge-Timestamp": ts, "X-Bridge-Signature": f"v1={sig}"})
```

```ts
import { createHmac } from 'node:crypto';
const ts = String(Math.floor(Date.now() / 1000));
const sig = createHmac('sha256', SECRET)
  .update(`${ts}.`)
  .update(body)
  .digest('hex');
```

Sign the bytes you send — not a re-serialisation of them. In an integration
platform, compute the header in a code step over the exact body string.

## The body

One JSON object (one record), `{ "records": [ … ] }`, a bare array, or NDJSON
with `Content-Type: application/x-ndjson`; at most `PUSH_MAX_RECORDS`. A key
repeated within one delivery keeps its **last** record (an event stream sending
the same entity twice — the later state is the truth).

## The answer

| Status | Meaning                                                                                                       |
| ------ | ------------------------------------------------------------------------------------------------------------- |
| `202`  | Accepted; the records register in the background                                                              |
| `200`  | An earlier delivery with the same `Idempotency-Key`, answered again (nothing stored twice)                    |
| `422`  | Nothing in the delivery was usable; `issues` says why, per record                                             |
| `400`  | The body is not an envelope (not JSON, empty, too many records)                                               |
| `401`  | The signature or the timestamp is wrong — uniform; the reason is in the server log and the channel's refusals |
| `404`  | No such channel, or it is disabled, or push is off                                                            |
| `429`  | Over `PUSH_RATE_PER_MINUTE`; see `Retry-After`                                                                |

```json
{
  "deliveryId": "…",
  "status": "RUNNING",
  "accepted": 2,
  "rejected": 1,
  "issues": [
    {
      "index": 2,
      "code": "MISSING_KEY",
      "message": "/asset/number is not in the record."
    }
  ],
  "statusUrl": "/api/integration/push/erp/deliveries/…",
  "repeat": false
}
```

`index` is the record's 1-based position in the delivery. `GET statusUrl`,
signed over `"<timestamp>.GET <path>"`, answers the delivery's counters
(`registeredRows`, `updatedRows`, `unchangedRows`, `failedRows`, …) and its
row issues. A delivery is only visible through its own channel.

## Administering channels

`/api/integration/push-channels/*`, console session (writes need `ADMIN`):
list, get, create, update (name, enabled, or the target + shape together),
`POST :id/rotate`, delete (the elements stay), `GET :id/deliveries`,
`GET :id/refusals`. Writes are audited (`SETTINGS`, field names only).

Refused requests are kept in `PushRefusal` (channel, address, reason; repeats
within a minute collapse; 31 days) — apart from `PeerAuthEvent`, which is about
peer tokens. Accepted and refused pushes are counted as their own request
surface, `push`.
