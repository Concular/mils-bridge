<!-- Generated from the MILS Bridge source repository (docs/integrations/sum4re.md). Edit it there, not here. -->

# SUM4Re passports

[SUM4Re](https://sum4re.eu/) ("Creating material banks from digital urban
mining") publishes **digital passports** for building materials, components
and buildings. Two kinds of passport exist, and both are W3C Verifiable
Credentials:

- **UNTP Digital Product Passports** at three levels: `model` (a component
  type), `item` (a component) and `batch` (a material).
- **Digital Building Logbooks**.

VTT hosts the passports on a static site. Its index, `id-map.json`, maps each
passport UUID to a JSON file.

An administrator adds a **passport source**: the site, plus the issuer key(s)
to trust. Each passport the index lists becomes one MILS element. Its kind is
`sum4re-passport` and its key is `sum4re:<slug>/<uuid>`. Its `ItemData` is the
signed credential verbatim, so a MILS peer reading it gets the passport itself
and can verify it independently. A later sync behaves like any
keyed record source:

- it **updates** a passport that was re-issued (the payload hash changed);
- it leaves an unchanged passport alone;
- it marks the passports the index no longer lists as missing.

The integration delivers:

- sources with pinned keys;
- signature verification, with its verdict stored per passport;
- routing each passport to a MILS Object by the building it names;
- the relations between passports, shown on each element and, when an
  operator names an ItemLink type, written to MILS as ItemLinks;
- console views: the sources and their passports on the integration page
  (with "Sync now" and "Link in MILS"), a **Digital passport** card on each
  element, and passport URLs in the find box;
- the `sum4re:sources` CLI.

It does **not** deliver:

- a console editor for sources (still the CLI or the API);
- passports above 1 MiB (the 5 MB Svalbard logbook), deferred because most of
  its size is a nested proof;
- issuing passports from this node, and the EU DPP registry export (phases
  3–4, waiting on answers from VTT).

## Trust: pinned keys

A passport carries `proof = { verificationMethod, jws }`, where `jws` is a
compact ES256 JWS whose payload is the credential. The bridge **never** takes
the verification key from the network during a sync, and never from the
document. The key comes from the source's pinned set:

1. `pnpm --filter @bridge/api sum4re:sources -- --issuer https://…/issuer.json`
   prints each key the issuer publishes, with its RFC 7638 **thumbprint**.
2. Confirm the thumbprint with the issuer out of band. Then put
   `{ "verificationMethod": "…#key-1", "jwkThumbprint": "…" }` in the
   source's `pinnedKeys`.
3. On create or update, the bridge reads the issuer document **once**. It
   stores the public key only if its thumbprint matches, and refuses anything
   but a P-256 key.

`--test <source>` re-reads the issuer document and warns when a pinned key is
no longer published, which usually means a rotation. Passports are still
checked against the pinned key until the pin is changed.

## What each passport checks out as

| Status              | Meaning                                                                                                                                    |
| ------------------- | ------------------------------------------------------------------------------------------------------------------------------------------ |
| `VERIFIED`          | Signed by a pinned key, and the signed content **is** the document (compared as canonical JSON, top-level `proof` removed from both sides) |
| `UNSIGNED`          | No `proof`                                                                                                                                 |
| `UNTRUSTED_KEY`     | Signed by a key this source does not pin                                                                                                   |
| `INVALID_SIGNATURE` | Not ES256, or the signature does not verify with the pinned key                                                                            |
| `PAYLOAD_MISMATCH`  | The signature is good, but over content that differs from the document. The message names the first differing path                         |
| `MALFORMED`         | Not a passport, or the proof is not a compact JWS                                                                                          |

The content comparison is the check VTT's own viewer leaves out. That viewer
shows a document edited after signing as verified; the bridge does not.

A logbook signed with its previous `proof` still inside (VTT's DBLs are) is
`VERIFIED` with `nestedProof: true`.

The verdict is kept in `Sum4RePassport`, **beside** the element and never
inside its payload. Read it with:

- `--passports <source>`;
- `GET /api/integration/sum4re/sources/:id/passports`;
- `GET /api/integration/sum4re/passports?key=sum4re:<slug>/<uuid>`.

## Where a passport goes in MILS

Registration needs an Object and an ItemType.

- **ItemType**: `itemTypes` maps `dpp-model`, `dpp-batch`, `dpp-item` and
  `dbl` each to a braced ItemTypeId. A kind left unset is not registered
  (`ITEM_TYPE_UNMAPPED`).
- **Object**: `buildingTargets` maps each logbook's credential id
  (`https://…/id/<uuid>`) to a braced ObjectId.
  - A logbook goes under its own entry.
  - A product passport goes under the mapped building it names in
    `relatedBuildings`.
  - A reused component names both its donor and its target building. In that
    case `buildingPreference` decides; with no preference, the first mapped
    building in the passport's own order wins.
  - With no mapped building, the row is `TARGET_UNRESOLVED`. The bridge never
    guesses a target.

Once a passport is registered it is never moved (`TARGET_CHANGED`).

```json
{
  "slug": "vtt-nl-pilot",
  "name": "SUM4Re NL pilot (VTT)",
  "baseUrl": "https://sum4re-701a59.extgit-pages.vtt.fi",
  "pinnedKeys": [
    {
      "verificationMethod": "https://sum4re-701a59.extgit-pages.vtt.fi/issuer.json#key-1",
      "jwkThumbprint": "<from --issuer, confirmed with VTT>"
    }
  ],
  "requireSignature": false,
  "itemTypes": {
    "dpp-model": "{…}",
    "dpp-batch": "{…}",
    "dpp-item": "{…}",
    "dbl": "{…}"
  },
  "buildingTargets": {
    "https://sum4re-701a59.extgit-pages.vtt.fi/id/00000000-0000-0000-0000-000000000001": "{…}"
  },
  "buildingPreference": [
    "https://sum4re-701a59.extgit-pages.vtt.fi/id/00000000-0000-0000-0000-000000000001"
  ],
  "scheduleMinutes": null,
  "onMissing": "keep"
}
```

Run `--add source.json`, then `--preview <source>`. The preview fetches and
checks up to 200 passports and writes nothing. Then run `--sync <source>`.

`requireSignature: true` registers only `VERIFIED` passports. Any other
passport fails with `PASSPORT_UNVERIFIED`. With it `false` (the default),
every readable passport is registered and the verdict sits beside it.

## Syncing

Every sync is a **full** sync: one run of the bulk-import runner, origin
`sum4re`. It gives per-row outcomes, retry, cancel and `results.csv`.

A passport that could not be downloaded or registered this time is still a row
(`PASSPORT_UNREADABLE`, `PASSPORT_MALFORMED`, …). So it counts as **seen**,
and one bad download never marks its element missing.

A scheduled source (`scheduleMinutes`, 15 minutes to a week) is started by the
`SourceSyncScheduler`.

## Fetching (the posture)

`Sum4ReClient` is the only caller of a passport site. Every request is
**site root + a site-relative path**. An index entry that is absolute, holds
`..`, `//`, a query, a fragment or an encoded slash is refused and never
followed.

The client applies:

- https only;
- no private hosts, also enforced at the socket's own DNS lookup;
- no redirects;
- `SUM4RE_REQUEST_TIMEOUT_MS` (15 s) per request;
- `SUM4RE_DOC_MAX_BYTES` (1 MiB) counted on the stream;
- `SUM4RE_CONCURRENCY` (4) documents at a time;
- JSON only.

`SUM4RE_ALLOW_PRIVATE_TARGETS` lifts the host rules (and allows http), for a
local mirror or tests.

`/id/<uuid>` on VTT's site is a client-side resolver that answers HTML, so
the bridge reads `id-map.json` instead.

## Relations and MILS ItemLinks

Passports name each other:

- a building logbook names its component types;
- a component type names its components;
- a material names the component types made of it;
- every product passport names its buildings.

Each passport's check keeps the credential ids it names (`Sum4RePassport.links`).
From those, the bridge computes edges between the source's passports, in the
direction the documents name them. A passport that is `MALFORMED` takes no
part, because its credential id cannot be trusted. VTT's `SSB.json` carries
Svalbard's id.

**On the element page** the **Digital passport** card lists both directions:

- what this passport names;
- what names it.

Each related passport links to its element when this node registered one.
A reference to a passport the source does not publish is shown and never
followed.

**In MILS** relations become ItemLinks only on request, with
`sum4re:sources -- --link <source>`, the console's "Link in MILS" (`ADMIN`) or
`POST sources/:id/links`. They also need an `itemLinkType` on the source. The
MILS contract publishes no enumeration of `ItemLinkType` values, so there is
no default: set the value agreed for the network with
`--update <source> patch.json` (`{ "itemLinkType": … }`). Until then, linking
answers `409`.

Each pair is recorded in `Sum4ReLink`:

- a linked pair is never written twice;
- a pair whose other end is not registered yet waits for the next link;
- a failure is kept on the pair and retried.

A logbook and a component type that name each other become two ItemLinks,
one per direction, as the documents state both.

## Finding a passport

Paste a passport URL (`https://…/id/<uuid>`) into the console's find box to
open the element registered for it. The BFF looks it up among the passports
it has checked (`GET passports?credential=`); nothing is fetched from the
site.

## Routes

`/api/integration/sum4re/*` takes a console session only and is absent from
`PUBLIC_INTEGRATION_PREFIXES`.

Any user may:

- read stored sources and checks;
- start the stored sync.

`ADMIN` is required for:

- `issuer`, `test` and `preview`, because they make this node call a site;
- `links`, because it writes to MILS;
- every source write.

| Route                                                    |                                                                            |
| -------------------------------------------------------- | -------------------------------------------------------------------------- |
| `GET issuer?url=`                                        | The keys an issuer document publishes, with thumbprints                    |
| `GET passports?key=` / `?credential=`                    | One passport's check, its element and its relations                        |
| `POST sources/:id/links`                                 | Write the source's relations to MILS as ItemLinks                          |
| `GET / POST sources`, `GET / PATCH / DELETE sources/:id` | Sources (id or slug). A deleted source keeps its elements, checks and runs |
| `POST sources/:id/test`, `POST sources/:id/preview`      | Test / preview                                                             |
| `GET sources/:id/passports`                              | Every passport's last check                                                |
| `POST / GET sources/:id/runs`                            | Sync now / the source's runs                                               |
