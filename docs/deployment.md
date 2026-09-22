# Deployment

One image, `ghcr.io/concular/mils-bridge`, containing both halves of the
bridge: the BFF and the console it serves from its own origin. There is no
database container — the mapping store is SQLite on a volume — and no second
image to keep in step.

| Concern     | Value                                                            |
| ----------- | ---------------------------------------------------------------- |
| Port        | `8080` — `/api/*`, `/rest/*` and the console, all on one origin  |
| Runs as     | uid 1000 (`node`), not root                                      |
| State       | `/data`: `mapping.db` plus `files/`, the registered file bytes   |
| Healthcheck | `GET /api/health/live` every 30 s, built into the image          |
| Start-up    | applies pending database migrations, then serves                 |
| Platforms   | `linux/amd64`, `linux/arm64`                                     |

## Two shapes

**Loopback** (the quickstart): `docker compose up -d` publishes `8080` on
`127.0.0.1` only. Nothing is reachable from the network, so peer nodes cannot
read from this bridge — fine for evaluating it, registering elements and
looking around the console.

**Behind TLS** (`docker compose --profile tls up -d`): Caddy terminates HTTPS
for `BRIDGE_DOMAIN`, gets its certificate automatically, and forwards
everything to the same container. Set `WEB_ORIGIN=https://<your domain>` and
`TRUST_PROXY=1`, and delete the `ports:` block from the `bridge` service so
port 8080 is not also open in the clear beside it.

Any other reverse proxy works the same way; there is only one upstream.

### The peer path the proxy must forward

`/rest/*` is the path other MILS nodes call on this bridge — the node's REST
root, the convention the network addresses each node by. It is the one surface
that is not under `/api`, and it must reach the container **unrewritten**: a
proxy that strips or renames the prefix leaves peers with a 404 and no way to
tell that from "this node has nothing".

The `tls` profile forwards the whole host, so there is nothing to configure.
If you are writing your own proxy config, one upstream for `/` is the right
answer — not a rule per prefix:

```caddyfile
bridge.example.com {
	reverse_proxy bridge:8080
}
```

```nginx
location / {
	proxy_pass http://bridge:8080;
	proxy_set_header Host $host;
	proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
	proxy_set_header X-Forwarded-Proto $scheme;
}
```

With any of these, set `TRUST_PROXY=1` — otherwise every request arrives with
the proxy's address and the per-client rate limit becomes a global one.

## The volume is the node

`bridge-data` holds the mapping store and every registered file. Losing it
loses the cross-reference between your source systems and the MILS items you
created from them — the items stay in MILS, but nothing here can resolve them
any more. Back it up before every upgrade:

```bash
docker compose stop bridge
docker run --rm -v mils-bridge_bridge-data:/data -v "$PWD":/backup alpine \
  tar czf /backup/bridge-data-$(date +%F).tgz -C /data .
docker compose start bridge
```

A **named** volume, as in `compose.yaml`, takes the image's ownership when it
is created. A **bind** mount does not: if you replace it with `./data:/data`,
run `mkdir -p data && sudo chown -R 1000:1000 data` first, or the container
cannot write its own database.

## Upgrading

```bash
docker compose pull
docker compose up -d
docker compose logs -f bridge
```

Migrations run at start-up, so an upgrade needs no manual step. Roll back by
setting `BRIDGE_VERSION` to the previous release and running the same two
commands — but note that a downgrade across a migration is not supported:
restore the volume backup instead.

Pin `BRIDGE_VERSION` on anything you care about. `latest` moves.

## Health and logs

```bash
docker compose ps                     # STATUS says (healthy) once it is up
curl -fsS localhost:8080/api/health/live
curl -fsS localhost:8080/api/version  # which release is actually running
docker compose logs -f bridge
```

`LOG_LEVEL=debug` adds the peer plumbing's redacted request and response
headers, which is what to turn on before reporting a federation problem. The
bearer token never appears in a log line at any level.

## Running the operational scripts

Every script in [`runbooks.md`](runbooks.md) runs inside the container. The
image's working directory is already the BFF's, so drop the `--filter` the
runbook shows and keep the rest, `--` for flags included:

```bash
docker compose exec bridge pnpm peer:self-check
docker compose exec bridge pnpm reconcile -- --apply
docker compose exec bridge pnpm files:verify
```

They need no network access to start and nothing installed on the host: the
pnpm release is cached in the image.
