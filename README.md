# MILS Bridge

The MILS Bridge registers the things your organisation already has — Concore
entities, Google Drive files, responses from any HTTP API you import, files
from your own computer and typed JSON values — as **items in MILS**, keeps the
durable cross-reference between the two, and serves those items back to the
peer nodes that ask for them. It is one container: a server that talks to the
upstream systems for you, and a web console that talks only to that server.

It is for an organisation that runs a MILS node: you decide what gets
registered, which peers may read which elements, and what your node answers
when another node asks.

Full picture: [`docs/what-this-is.md`](docs/what-this-is.md) ·
[`docs/glossary.md`](docs/glossary.md).

## Quickstart

```bash
git clone https://github.com/Concular/mils-bridge && cd mils-bridge
cp .env.example .env         # set MILS_ACTOR_CODE_SELF and MILS_BASE_URL
docker compose up -d         # pulls ghcr.io/concular/mils-bridge
docker compose logs -f bridge
```

Then open <http://localhost:8080>. The first visit lands on `/setup`: the
account you create there is the node's first administrator. After that, go to
**Integrations** and connect MILS — a signing key on the MILS panel is what
lets this node create items.

Two things worth knowing before you start:

- `MILS_ACTOR_CODE_SELF` is **your** MILS ActorCode. Left unset it falls back
  to Concular's, and every token this node signs then claims to be Concular's.
  The bridge logs a warning at boot if you leave it.
- The quickstart publishes port 8080 on loopback only, so nothing is reachable
  from the network yet. Peers can read from this node once it is behind a
  domain — see below.

## Production

```bash
# in .env: BRIDGE_DOMAIN=bridge.example.com
#          WEB_ORIGIN=https://bridge.example.com
#          TRUST_PROXY=1
docker compose --profile tls up -d
```

Caddy terminates TLS for `BRIDGE_DOMAIN`, gets its certificate automatically
and forwards everything to the same container. Delete the `ports:` block from
the `bridge` service once you do this, so plain 8080 is not open beside it.

**`/rest/*` is the path other MILS nodes call**, and it must reach the
container unrewritten. `/api/*`, `/rest/*` and the console are one origin and
one process, so any proxy config is a single upstream — there is no path
routing to get wrong. Details, including an nginx block:
[`docs/deployment.md`](docs/deployment.md).

## Configure

Every setting: [`docs/configuration.md`](docs/configuration.md). Each upstream
value in `.env` is only a seed — what you save on the console's Settings pages
is stored in the database and wins at request time, so most of the file can
stay empty.

Three decisions every deployment makes:

| Decision                    | Where                                                                                                                    |
| --------------------------- | ------------------------------------------------------------------------------------------------------------------------ |
| Who this node is            | `MILS_ACTOR_CODE_SELF`, plus an RS256 signing key on the MILS settings panel                                             |
| Who may read what           | `ACCESS_ENFORCEMENT` (`shadow` → `enforce`) and `MILS_INTERNAL_AUTH` — [`docs/access-control.md`](docs/access-control.md) |
| Whether secrets are at rest | `SECRETS_KEY` — with it set, the stored credentials are encrypted in SQLite                                              |

`ACCESS_ENFORCEMENT` ships as `shadow`: rules are evaluated and recorded, and
nothing is refused. Watch the denial counts on **Access → Statistics** until
they are what you expect, then switch to `enforce`
([`docs/runbooks.md`](docs/runbooks.md)). Note that while
`MILS_INTERNAL_AUTH=open` — the published contract's own posture — enforcement
does not cover the peer-facing item reads.
[`docs/security.md`](docs/security.md) is explicit about which surfaces are
unauthenticated and what closes them.

Connecting another node, or connecting to one:
[`docs/peer-node-quickstart.md`](docs/peer-node-quickstart.md) (copy-pasteable)
and [`docs/peer-node-onboarding.md`](docs/peer-node-onboarding.md) (the whole
handshake). The contract peers implement is
[`spec/mils-internal.yaml`](spec/mils-internal.yaml).

When something does not work:
[`docs/troubleshooting.md`](docs/troubleshooting.md), symptom first.

## Upgrading

```bash
docker compose pull && docker compose up -d
```

Migrations run at start-up. **Back up the `bridge-data` volume first** — it
holds the mapping store and every registered file, and it is the only copy of
the cross-reference between your systems and MILS
([`docs/deployment.md`](docs/deployment.md)).

## Versions

| Tag           | What it promises                                            |
| ------------- | ----------------------------------------------------------- |
| `0.1.0`       | One release, immutable. Pin this on anything you care about |
| `0.1`         | The latest patch of that minor                              |
| `latest`      | The newest release. Fine for a trial, not for a deployment  |
| `sha-abc1234` | One build of one commit — the tag to quote in a bug report  |

Set the one you want as `BRIDGE_VERSION` in `.env`. Releases are announced on
this repository's [Releases](https://github.com/Concular/mils-bridge/releases)
page, with the changelog entry as the body; `CHANGELOG.md` has the same text.

A change to `spec/mils-internal.yaml` that peers must follow bumps the major
version and says so in the release title — a peer that upgrades one end and not
the other stops working.

## Support

Questions and bug reports:
[issues](https://github.com/Concular/mils-bridge/issues). What is supported is
`compose.yaml` as published here, on the current minor release. Please include
the output of `curl -s localhost:8080/api/version` and the image tag you are
running.

If you think you have found a security problem, **do not open an issue** — mail
the Concular team directly and we will come back to you.

No licence has been chosen for this project yet, so: all rights reserved, with
permission to run the published image. A `LICENSE` file will land here when
that decision is made, and the image will carry the matching SPDX label in the
same release.
