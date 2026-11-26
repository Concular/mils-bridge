<!-- Generated from the MILS Bridge source repository (docs/integrations/embed.md). Edit it there, not here. -->

# Partner embed

A partner frames one URL in an `<iframe>` and gets a read-only page showing
what the network knows about one or more elements: name, item type, object
path, properties, linked items, file, digital passport and raw data. The URL names the elements, in the partner's
**own ids**. A short-lived token minted by the partner's backend says which
partner is asking. The partner signs it with a secret this node issued, or with
its own key pair.

The three phases are built:

- **Elements:** this node's own elements and, under grants this node already
  holds, peers' items.
- **Views:** single, list and compare.
- **Sections:** linked items and the passport, with navigation inside the
  frame.
- **Administration:** the alias table, the CLI, and the console page under
  **Integrations › Partner embed**.
- **Frame:** the partner's accent colour, and live `token` / `show` messages.
- **Credentials:** an HS256 secret this node issues, or the partner's own
  ES256 key pair.
- **Traffic:** 7-day views per partner, and an embed card on the Overview.
- **Simple link:** a long-lived link key in a plain iframe URL, for partners
  on a trusted network that will not sign tokens (below).

Every item of the plan is built.

## The simple link

For a partner inside a trusted network, signing a token per view is often more
than it will build. The **simple link** is the alternative: one plain URL per
element, pasted into an `<iframe>` once.

```
https://bridge.example.com/api/embed/v1/frame?k=ek_<43 chars>&ref=item:5d0e4c1a-…
```

The page answers at two paths: `/api/embed/v1/frame` and `/embed/v1/elements`.
Links this node hands out (the simple link, test links, the CLI) use
`/api/embed/v1/frame`, because it sits under the `api` prefix. A reverse proxy
that forwards only `/api/*` to the BFF, like the two-service stack's Caddy,
sends everything else to the console. There, `/embed/v1/elements` would open
the console's sign-in page instead of the frame. The page's asset URLs are
relative, so one build serves both paths.

- `k` is the partner's **link key**, `ek_` + 32 random bytes (base64url). It
  never expires and opens the `view` scope only — never `aliases:write`.
- A view opened with it may be framed by **any** site (`frame-ancestors *`),
  so the partner needs no origins. `postMessage` goes to `*`, and `show`
  messages are taken from whichever page frames it.
- Everything else still applies: the partner's `allowedRootIds` (empty = sees
  nothing), its bound actor, `enabled`, the rate limit, the metrics and the
  refusal log. `ref`, `lang`, `theme`, `view` and `sections` work as with a
  token. `k` stays in the frame's address (a token is removed), so a reload of
  the frame still works.
- An administrator creates, shows, rotates (**New key**: the old key stops at
  once, no overlap) or turns it off in **Integrations › Partner embed ›
  Simple link**, or with `embed:partners -- --link <slug> [ref]`,
  `--link-rotate <slug>`, `--link-off <slug>`. The key is stored sealed
  (`linkKey`) and looked up by its SHA-256 (`linkKeyHash`); the console shows
  it again to `ADMIN`s.

The trade-off is deliberate: whoever holds the URL sees what the partner may
see, for as long as the key lives. Use it where the network around the URL is
trusted; use tokens where it is not. A partner may have both.

## Switching it off

The embed is **on by default**. To remove it from a node:

```bash
EMBED=off
```

With `EMBED=off` (the literal), the page, the partner's reads and the admin
routes answer **404**. Nothing is framed until an administrator creates a
partner, so leaving it on exposes no data by itself. The page is a separate Vite build that the BFF
serves itself:

```bash
pnpm --filter @bridge/web build:embed     # → apps/web/dist-embed (also part of `build`)
```

The BFF reads `embed.html` and `assets/` from `EMBED_DIST` (default
`../web/dist-embed`, relative to the API's working directory). Without the
bundle the page answers `503`, and the integration's _Test connection_ says so.

Both images build the bundle and set `EMBED_DIST`:

- **The published image** (the root `Dockerfile`, BFF and console in one
  container). The page answers at `/embed/v1/*` and `/api/embed/v1/frame`; the
  console's static fallback leaves both alone.
- **The two-service compose stack** (`apps/api/Dockerfile`, behind Caddy).
  The bundle is built in its own stage, so the API image carries no web build
  dependencies. Caddy forwards only `/api/*` and `/rest/*` to the BFF, so here
  only `/api/embed/v1/frame` reaches the page. `/embed/*` gets the console's
  sign-in page, unless `handle /embed/*` is added to the edge.

The desktop app does not ship it.

## In the console

**Integrations › Partner embed** has the integration's status:

- enabled, partners, aliases;
- views and refused tokens over the last 7 days (a **view** is one successful
  `GET /api/embed/v1/elements`; the page, its assets and file downloads are not
  views);
- whether peer items are possible.

_Test connection_ checks that the page is built and that every enabled partner
could be served:

- its secret unseals, or its public key reads;
- it has an origin and a scope;
- if it may see peer items, federation is on.

Below that is the partner table: each partner's credential (the secret's last
four characters, or the start of its key's thumbprint), its aliases, its views
over the last 7 days and its last view. Any signed-in user can read it and the
aliases. ADMINs can:

- **add / edit** a partner (the slug is fixed once created). _Signing_ picks
  the credential: a secret this node issues, shown **once** after saving, or
  the partner's own key pair, whose public key is pasted as a JWK or PEM (see
  [Partner keys](#partner-keys-es256));
- **rotate** the secret: the new one is shown once, and the old one keeps
  verifying for `EMBED_SECRET_OVERLAP_HOURS`. A partner with its own key has no
  _Rotate_: paste its new key in _Edit_ instead;
- open the **aliases**: search, page, download as CSV, delete one, or upload a
  CSV (`externalId,itemId`, a header row optional, quotes honoured). The upload
  is checked in the browser first and shows what would load, which rows cannot
  be read, and how many ids repeat (the last row wins);
- make a **test link**: a 10-minute link signed with the partner's own secret,
  to open the view exactly as the partner's frame would. It is audited. A
  partner that signs with its own key has none: this node holds no private key;
- read the **refusals**: why tokens naming this partner were refused.

## Adding a partner from a shell

```bash
cat > acme.json <<'EOF'
{
  "slug": "acme-fm",
  "name": "Acme FM",
  "allowedOrigins": ["https://app.acme.example"],
  "allowedRootIds": ["{9a1b2c3d-…}"],
  "actorId": null,
  "pushChannelSlug": null
}
EOF
pnpm --filter @bridge/api embed:partners -- --add acme.json     # prints the secret once
```

| Field             | Meaning                                                                                                                                                                                  |
| ----------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `slug`            | The token's `iss`. Immutable.                                                                                                                                                            |
| `allowedOrigins`  | Who may frame the page (`frame-ancestors`). `https` only, unless `EMBED_ALLOW_HTTP_ORIGINS` is on.                                                                                       |
| `allowedRootIds`  | MILS **root** objects. An element is in scope when its `milsRootObjectId` is one of them. **Empty means nothing.** Run `backfill:mils-root-objects` for elements without a root.         |
| `actorId`         | Optional. A registered MILS actor whose Access rules (`resolveAccess`) also apply to the partner. Always enforced, whatever `ACCESS_ENFORCEMENT` says.                                   |
| `pushChannelSlug` | Optional. A push channel whose record keys are the partner's ids: `ext:<key>` resolves to `push:<slug>/<key>` with no alias row.                                                         |
| `peerReads`       | `never` (default) or `granted`: whether the partner may see items **other nodes** own. Leave it `never` until those owners have agreed to their data being shown to the partner's users. |
| `publicKey`       | Optional. The partner's P-256 public key, a JWK or an SPKI PEM. With it the partner signs ES256 and **no secret is issued**; without it, a secret is.                                    |

`--rotate <slug>` issues a new secret and keeps the old credential valid for
`EMBED_SECRET_OVERLAP_HOURS` (on a partner with a key, this switches it to a
secret). `--check-key <file>` prints the JWK this node would store and its
thumbprint. `--update <slug> patch.json` (a `publicKey` in it replaces the
credential), `--remove <slug>` and `--list` work as their names say.

## The token

Signed by the partner's **backend**: HS256 with the secret this node issued,
or ES256 with the partner's own private key. Neither may ever appear in the
partner's frontend code. A partner has one credential, so one algorithm: a
token naming any other `alg` (`none`, `RS256`, `ES384`, HS256 against a key, …)
is refused before a key is touched.

| Claim        | Rule                                                                                              |
| ------------ | ------------------------------------------------------------------------------------------------- |
| `iss`        | The partner's slug                                                                                |
| `aud`        | `<this node's actor code>-embed`, e.g. `conc-embed`                                               |
| `iat`, `exp` | Both required; `exp − iat` ≤ `EMBED_TOKEN_MAX_TTL_SECONDS` (900); 60 s skew                       |
| `scope`      | `view` (default) or `aliases:write`. A view token cannot write aliases, and the reverse holds too |

```js
const token = jwt.sign({ aud: 'conc-embed' }, secret, {
  algorithm: 'HS256',
  issuer: 'acme-fm',
  expiresIn: '10m',
});
```

A refused token gets one uniform answer: `401 "This view could not be opened."`
The reason goes to the log and to the `EmbedRefusal` table. The one exception
is expiry (`code: "TOKEN_EXPIRED"`), so the page can tell its parent.

`--token <slug> [ref …] [--ttl s] [--base url]` prints a test link signed with
the partner's own secret. For a partner with its own key, add
`--key private.pem` (a test key pair: this node never stores a private key).

## Partner keys (ES256)

Instead of a shared secret, a partner can keep its own key pair and register
only the public half. Nothing secret ever leaves the partner, and nothing on
this node can sign as the partner.

```bash
openssl ecparam -name prime256v1 -genkey -noout -out acme-private.pem
openssl ec -in acme-private.pem -pubout -out acme-public.pem
```

The administrator pastes `acme-public.pem` (or the same key as a JWK) into the
partner form, or puts it in `partner.json` as `publicKey`. The BFF reads it,
refuses a private key and anything but EC P-256, stores only the public JWK
(`kty`, `crv`, `x`, `y`) and shows its **RFC 7638 thumbprint**, the way a
SUM4Re source pins an issuer key. Ask the partner to confirm the thumbprint
matches before saving: it is the only check that the key came from them.
`POST /api/integration/embed-partners/public-key` (ADMIN) answers the same
reading without saving, which is what _Check key_ calls.

```js
const token = jwt.sign({ aud: 'conc-embed' }, privateKeyPem, {
  algorithm: 'ES256',
  issuer: 'acme-fm',
  expiresIn: '10m',
});
```

Pasting a new key in _Edit_ replaces the credential, and the old one (a secret
or the previous key) keeps verifying for `EMBED_SECRET_OVERLAP_HOURS`, so the
partner can switch without a gap. _Rotate_ goes back to a secret the same way.

## The URL

```
https://bridge.example.com/embed/v1/elements?t=<token>&ref=ext:DOOR-000214&ref=ext:WIN-000871&lang=de
```

| Parameter  | Values                                                                                                                                                                                              |
| ---------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `ref`      | `ext:<their id>`, `src:<kind>:<id>`, `item:<uuid>`, `object:<uuid>`. Repeat it, or separate refs with commas. At most `EMBED_MAX_REFS`. `object:` expands to at most `EMBED_OBJECT_MAX_ITEMS` items |
| `lang`     | `en de nl es nb` (default: the browser's)                                                                                                                                                           |
| `theme`    | `auto light dark`                                                                                                                                                                                   |
| `view`     | `auto single list table`. `table` compares properties side by side, and falls back to `list` unless at least two elements of one item type are shown                                                |
| `sections` | Any of `details properties links files passport payload`. Defaults to every section with content                                                                                                    |

Each ref answers `SHOWN`, `NOT_IN_MILS` (an `ext:` id with no alias),
`NOT_AVAILABLE` (unknown, out of scope, blocked, or another node's item; the
partner cannot tell these apart) or `INVALID`.

## Items other nodes own

With `PEER_FEDERATION=on` and the partner's `peerReads: granted`, a ref to an
item another node owns (`item:` or an `ext:` alias) is read from its owner,
live. Three checks run before the owner is contacted at all:

1. the partner allows peer reads;
2. the item's root object (from MILS) is in the partner's `allowedRootIds`;
3. this node **already holds** a grant from the owner for the item's object,
   as recorded in `PeerAccessRequest`.

The embed never asks a peer for access. That stays an operator's act, in
Network. The reads are the owner's `PropertyData` and `ItemData` (its
`ItemFile` for a download), each recorded as a `PeerExchange` with
`triggeredBy = embed:<partner>`. Answers are cached per item for
`EMBED_PEER_CACHE_SECONDS`, and concurrent views share one read, so a busy
partner page costs the owner one round per window. The view names the owner
and when the data was read.

A peer item the partner may not see reads `NOT_AVAILABLE`, like anything else.
If the owner does not answer, the ref reads `OWNER_UNREACHABLE` and the rest of
the view is unaffected.

## Sections

An element shows its sections in a fixed order — **Details** (item type,
source, holder, location, registered/updated, MILS item id), **Properties**,
**Linked items**, **Files**, **Digital passport**, **Raw data** — with a
sticky row of jump links when there are three or more. The order and the
filtering come from one registry, `ELEMENT_SECTIONS` in
`apps/web/src/embed/embed-sections.tsx`: a new section is an entry there, its
id in `EMBED_SECTIONS` (`@bridge/shared`) and its title under `section.<id>`
in the `embed` catalogs.

## Linked items and the passport

**Linked items** are the item's active MILS ItemLinks in both directions, the
same read the console's item page makes. A linked item the partner may open
can be **expanded in place** (its own sections, read on demand with the same
credential) or **opened** as the frame's element; inside an expanded item,
links only open. **Digital passport** appears on a
`sum4re-passport` element and shows the signature check, issuer, validity and
the passports it names.

The other end of a link or relation is named only if the partner could open
it. In that case it is a button that opens the element in the frame and posts
`navigate`; _Back_ returns. Any other end shows no name, only its owner node
when it belongs to a peer. At most 50 links per element.

## Aliases

The partner's backend maps its ids to MILS item ids with an `aliases:write`
token:

```bash
curl -X PUT https://bridge.example.com/api/embed/v1/aliases \
  -H "Authorization: Bearer $ALIAS_TOKEN" -H 'content-type: application/json' \
  -d '{"aliases":[{"externalId":"DOOR-000214","itemId":"5d0e4c1a-…"}]}'
# → {"created":1,"updated":0,"unchanged":0,"deleted":0}
```

`DELETE` takes `{"externalIds":[…]}`. At most `EMBED_ALIAS_BATCH_MAX` per call.
The operator can load a CSV file instead:
`embed:partners -- --aliases <slug> aliases.csv` (`externalId,itemId`).

## postMessage

The page posts `{ type, v: 1, … }` to the partner's allowed origins only:

| Type                         | Payload                                                  |
| ---------------------------- | -------------------------------------------------------- |
| `bridge:embed:ready`         | `{ shown, notInMils, notAvailable }`                     |
| `bridge:embed:resize`        | `{ height }`                                             |
| `bridge:embed:navigate`      | `{ ref }`: the user opened a linked element in the frame |
| `bridge:embed:token-expired` | —                                                        |

The partner page may post two messages back, to `iframe.contentWindow` and
for the embed's origin. The frame accepts them only from `window.parent` and
only from one of the partner's origins:

| Type                 | Payload                                                                                                                  |
| -------------------- | ------------------------------------------------------------------------------------------------------------------------ |
| `bridge:embed:token` | `{ token }`: a fresh token. Send it after `token-expired`, or before expiry, so a long-open page never reloads the frame |
| `bridge:embed:show`  | `{ refs }`: show other elements without reloading (at most 25)                                                           |

The partner's **accent colour** (set in the console) becomes the frame's action
colour.

The partner sizes the frame from `resize`:

```js
addEventListener('message', (e) => {
  if (e.origin !== 'https://bridge.example.com') return;
  if (e.data?.type === 'bridge:embed:resize')
    frame.style.height = `${e.data.height}px`;
});
```

## Routes

| Route                                  | Gate                                                                                                                                                                                                                      |
| -------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `GET /embed/v1/elements`               | The page. Outside the `api` prefix. `frame-ancestors` lists the token's partner's origins (`'none'` when no partner can be read from the token), with no `X-Frame-Options`, `Referrer-Policy: no-referrer` and `no-store` |
| `GET /embed/v1/assets/:file`           | The page's hashed assets                                                                                                                                                                                                  |
| `GET /api/embed/v1/elements?ref=…`     | Bearer `view` token or link key. `EmbedElementsDto` (`tokenExpiresAt` is null for a link key)                                                                                                                            |
| `GET /api/embed/v1/files/:itemId`      | Bearer `view` token. The page fetches the file and saves a blob, so the token is never put in a link                                                                                                                      |
| `PUT` / `DELETE /api/embed/v1/aliases` | Bearer `aliases:write` token                                                                                                                                                                                              |
| `/api/integration/embed-partners/*`    | Console session; writes, `PUT`/`DELETE :id/aliases`, `POST :id/test-link`, `GET`/`POST`/`DELETE :id/link` (the simple link) and `POST public-key` need `ADMIN`. Reads: `:id/aliases` (paged, `?q=`), `:id/aliases.csv`, `:id/refusals`                                      |

Per partner, `EMBED_RATE_PER_MINUTE` reads (300) are allowed after the token is
verified, on top of the global per-IP throttle. Every request is counted on the
`embed` metrics surface; one that passed the token guard also carries
`principalType = partner` and the partner's id (`RequestMetric.partnerId`),
which is what the per-partner views and the Overview card count. A refused
token records no partner: its reason is in `EmbedRefusal`.

## Env

`EMBED` (on; only `off` disables it), `EMBED_DIST`, `EMBED_TOKEN_MAX_TTL_SECONDS` (900),
`EMBED_MAX_REFS` (25), `EMBED_OBJECT_MAX_ITEMS` (100), `EMBED_ALIAS_BATCH_MAX`
(1000), `EMBED_PEER_CACHE_SECONDS` (300, the object-path and item-type cache
for now), `EMBED_RATE_PER_MINUTE` (300; 0 = off), `EMBED_SECRET_OVERLAP_HOURS`
(24), `EMBED_ALLOW_HTTP_ORIGINS` (off; desktop and tests).

## On the Overview

With the embed on (unless `EMBED=off`), or any embed traffic in the last 7 days, the Overview shows a
**Partner embed** card: views per day, enabled partners, refused tokens and the
five partners with the most views (`DashboardOverviewDto.embed`, from
`dashboard/collectors/embed.collector.ts`).
