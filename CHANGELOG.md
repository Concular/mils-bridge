# Changelog

Every published release of `ghcr.io/concular/mils-bridge`, newest first. The
format is [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions
follow [semantic versioning](https://semver.org/spec/v2.0.0.html), where a
**major** bump means a peer that upgrades one end and not the other stops
working.

## Unreleased

## 0.2.0 — RELEASE-DATE

Six new sources, a redesigned console with a built-in user guide, and a
PropertyData answer peers can use. Run `docker compose pull && docker compose
up -d`; migrations apply at start-up. Back up the `bridge-data` volume first.

### Added

- **Six more ways to register into MILS:**
  [Amazon S3](docs/s3.md) (a file, or a whole folder as a bulk import),
  [Microsoft 365](docs/microsoft-365.md) (SharePoint and OneDrive for
  Business, each user connecting their own work account),
  [SQL databases](docs/sql.md) (a read-only PostgreSQL query, one element per
  row), [Notion](docs/notion.md) (one element per page of a data source),
  [inbound push](docs/push.md) (other systems POST signed JSON records to a
  channel) and [bulk import](docs/bulk-import.md) (a CSV, JSON or NDJSON file,
  one element per record).
- **Sources that stay in step.** SQL, push and Notion elements are keyed by
  their source record: a changed record rewrites the item's data without a new
  MILS item, and a record that disappears from a full sync is marked missing
  (or archived, if you choose). Scheduled syncs run unless `SOURCE_SYNC=off`.
- **A user guide inside the console** (`/guide`), with screenshots, in all
  five languages.
- **A redesigned console**: grouped navigation (Overview, Elements, Access,
  Network, Browse, then Setup), one register wizard for every source, and a
  paste-an-id jump. Every URL from 0.1.0 still works.
- The [integration pages](docs/mils.md) are now part of the published docs.

### Changed — for peers

- **`PropertyData` answers a structure, always.** `GET
  /rest/MilsItems/{id}/PropertyData` is now `application/json`: the item's id,
  the media type `ItemData` and `BinaryData` each answer with (or `null`), and
  every property type MILS lists for the item's type, with the values this
  node knows. It answers `200` for every item this node holds and `404` only
  for an id it holds nothing for. It was opaque text that answered `404` for
  almost every item. This is the shape Block Materials serves and asked every
  node to serve. Run **Sync registry** once after upgrading (Browse → MILS →
  Nodes, or the `sync:actor-registry` script) so the property list is filled.
- **`ItemData` is served as `application/json`** instead of `text/plain`. The
  bytes are the same, and a 0.1.0 bridge accepts both, so 0.1.0 and 0.2.0
  bridges read each other's items.
- **Peer tokens live at most 24 hours** by default (`ACTOR_JWT_MAX_TTL_SECONDS
  = 86400`, which was unlimited). A token without `iat` is measured from now.
- **A bearer presented to the handshake is verified** under
  `MILS_INTERNAL_AUTH=open` and `actor` too: an invalid token is refused with
  `401` instead of being treated as anonymous. A token whose node claim
  contradicts its `X-MILS-Node-Id` header is refused.

### Security

- The outbound address guard (peers, API Explorer, S3, SQL) understands
  IPv6 forms that hide a private address and re-checks the address at connect
  time, closing DNS rebinding.
- Files from peers are always served as attachments; uploaded files render
  inline only for an allow-list of types, with `nosniff` and a sandbox CSP.
- Under `ACCESS_ENFORCEMENT=enforce`, a read of an unmapped element is decided
  from the defaults instead of allowed.
- Google sign-in binds its callback to the session, and API Explorer refuses
  to keep a stored credential when an API's base URL changes origin.
- Reconfiguring an imported API is for its importer or an administrator, and
  a console edit of an item's data needs an item this node owns.

### Fixed

- Registration can no longer create two MILS items for one source record when
  a request is retried or two users click at once.
- MILS and Concore calls time out after 30 s (`MILS_TIMEOUT_MS`,
  `CONCORE_TIMEOUT_MS`) instead of hanging.
- A setting written from the command line reaches the running server within
  10 s.

### Upgrade notes

- `compose.yaml` now derives `M365_REDIRECT_URI` from `WEB_ORIGIN`, as it
  already did for Google. Take the new file if you use Microsoft 365.
- `.env.example` lists the new switches (`SQL_SOURCES`, `PUSH_INBOUND`,
  `SOURCE_SYNC`, `M365_*`); none is needed to keep running as before.
- If you set `SECRETS_KEY`, the new credentials (S3 keys, SQL passwords, push
  secrets, Notion tokens, Microsoft 365 secrets and tokens) are encrypted too.

## 0.1.0 — 2026-09-22

The first published release. `docker compose up -d` and
<http://localhost:8080>.

### The bridge

- **Register into MILS** from five sources: Concore entities, Google Drive
  files, recorded responses from any OpenAPI document you import, files
  uploaded from your own computer, and typed JSON values. Every registration
  keeps a durable mapping between the source record and the MILS item, so an
  item id always resolves back to where it came from.
- **Answer peer nodes** on `/rest/*` — the BLM contract as
  [`spec/mils-internal.yaml`](spec/mils-internal.yaml) publishes it: item data,
  file bytes, property data, the item list per object, and the object-access
  handshake. Implemented locally from this node's own store, not forwarded.
- **Read from peers** (optional, `PEER_FEDERATION=on`): resolve a peer-owned
  item or object through MILS, ask its owner for access, and read the payload
  once granted. No grant, no request for data — there is no setting that skips
  the handshake.
- **Decide who may read what** ([`docs/access-control.md`](docs/access-control.md)):
  policy, per-node and per-actor defaults, per-element modes and rules, with
  `ACCESS_ENFORCEMENT` deciding how far a decision is acted on. `shadow` by
  default, so you can see what would be refused before refusing it.
- **A console** for all of it: dashboard, registered elements, access, a data
  explorer over MILS/Concore/Drive/imported APIs, integrations, settings, users
  and an audit trail. In English, German, Dutch, Spanish and Norwegian.

### Running it

- One image, `ghcr.io/concular/mils-bridge`, `linux/amd64` and `linux/arm64`,
  running as uid 1000, with SBOM and provenance attestations.
- SQLite plus the registered file bytes on one volume; migrations apply at
  start-up.
- The console is served from the BFF's own origin, so there is no second image,
  no baked API URL and no CORS to configure.

### Known limits

- No `LICENSE` and no `SECURITY.md` yet — see the README's Support section.
- The peer-facing `/rest/*` surface is unauthenticated by default, which is the
  published contract's own posture. `MILS_INTERNAL_AUTH=actor` or `node`
  changes it; [`docs/security.md`](docs/security.md) is explicit about what that
  means for `ACCESS_ENFORCEMENT`.
