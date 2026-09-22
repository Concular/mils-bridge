# Changelog

Every published release of `ghcr.io/concular/mils-bridge`, newest first. The
format is [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions
follow [semantic versioning](https://semver.org/spec/v2.0.0.html), where a
**major** bump means a peer that upgrades one end and not the other stops
working.

## Unreleased

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
