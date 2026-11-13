<!-- Generated from the MILS Bridge source repository (docs/integrations/sql.md). Edit it there, not here. -->

# SQL databases

An **SQL source** is an administrator's read-only query against a database.
Each row of its result becomes one MILS element (`sql-row`), whose payload is
the row as JSON. A sync runs the stored query again: a changed row **updates**
its element, an unchanged one is left alone, and a row that disappeared is
marked missing (and archived, if the source says so). The sync machinery is
the keyed record one; this page covers what is
specific to SQL.

Phase 1 speaks **PostgreSQL** only, and has no console editor yet: sources are
created and synced with the `sql:sources` command or the API
(`plans/sql-query-source-plan.md`).

## Turning it on

| Variable                    | Default                         | Meaning                                                                                                                                     |
| --------------------------- | ------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------- |
| `SQL_SOURCES`               | off                             | Only the literal `on` registers the routes. Off: `/api/integration/sql/*` answers 404 and no database is ever dialled                       |
| `SQL_ALLOW_PRIVATE_TARGETS` | off                             | Allows loopback/private hosts and `tls: disable`. Databases usually live on a private network, so on-premise and desktop deployments set it |
| `SQL_CONNECT_TIMEOUT_MS`    | 10 s                            |                                                                                                                                             |
| `SQL_STATEMENT_TIMEOUT_MS`  | 60 s                            | The server's `statement_timeout` for each run                                                                                               |
| `SQL_MAX_ROWS`              | `BULK_IMPORT_MAX_ROWS` (10 000) | Above it a run is refused, never truncated — a cut-off full sync would mark the rest missing                                                |
| `SOURCE_SYNC`               | on                              | `off` stops scheduled syncs; a sync started by hand still runs                                                                              |

## Read-only, in three layers

1. **The database account — the real boundary.** Give every source its own
   user with `SELECT` on exactly what the query reads:

   ```sql
   CREATE ROLE mils_reader LOGIN PASSWORD '…';
   GRANT USAGE ON SCHEMA public TO mils_reader;
   GRANT SELECT ON materials TO mils_reader;
   ```

   `test` warns when the account is a superuser or holds `INSERT` / `UPDATE` /
   `DELETE` / `TRUNCATE` on any table.

2. **A read-only transaction.** Every statement runs inside `BEGIN READ ONLY`
   with `SET LOCAL statement_timeout`, and is rolled back. A query that writes
   through a function (`SELECT nextval('s')`) fails with "The query tried to
   write" and changes nothing.
3. **A text check** (`checkSelectOnly` in `@bridge/shared`). One statement,
   starting with `SELECT` / `WITH` / `VALUES` / `TABLE`, and no write or lock
   keyword outside strings, quoted identifiers and comments. It catches
   mistakes; it is not the boundary. It is conservative: a column literally
   named `update` must be `"double-quoted"`.

The query is configuration. A run executes the stored text; nothing a request
carries reaches the database. Creating or changing a source, `test` and
`preview` need `ADMIN`; any console user may start the stored sync.

## Where the BFF connects

There is no free-form connection string: the driver config is built from the
validated fields only, so options like `sslmode=disable` cannot ride along. The
host is resolved by the BFF and the connection made **to that address** (the
name kept for TLS), and a private or loopback answer is refused unless
`SQL_ALLOW_PRIVATE_TARGETS` — so a name that resolves public when checked and
private when connecting is not a way around it.

| `tls`               | Meaning                                                                       |
| ------------------- | ----------------------------------------------------------------------------- |
| `require` (default) | Encrypted; the certificate is not verified (the usual managed-database setup) |
| `verify-full`       | Encrypted and verified against the public CAs, or `caCertPem`                 |
| `disable`           | Plain TCP. Only with `SQL_ALLOW_PRIVATE_TARGETS`, on a network you trust      |

## From a row to an element

The source's `mapping` names the columns:

| Field                                    | Meaning                                                                                                                                                               |
| ---------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `keyColumns`                             | 1–4 columns joined with `/` into the record key. Must be unique and never NULL. **Cannot change once the source has elements**                                        |
| `objectIdColumn` / `defaultObjectId`     | Exactly one: the MILS Object per row, or one for all                                                                                                                  |
| `itemTypeIdColumn` / `defaultItemTypeId` | Exactly one, likewise                                                                                                                                                 |
| `nameColumn`                             | Optional display name                                                                                                                                                 |
| `payloadColumns`                         | Optional; default every column not used above. **Every payload column is published** to the MILS network under this node's access model — select the columns you mean |
| `nestDottedColumns`                      | Default on: a column `material.kind` becomes `{ "material": { "kind": … } }`                                                                                          |
| `numericAsNumber`                        | Default off: `int8` / `numeric` stay strings, because JSON numbers lose precision. On: numbers when they round-trip exactly, strings otherwise                        |

Values: timestamps become ISO 8601 from the text the server sent (never
through the BFF's time zone); dates stay `YYYY-MM-DD`; `json` / `jsonb` and
arrays are converted deeply; **binary (`bytea`) columns are always left out**,
NULL or not, and `preview` says so.

Each element's key is `sql:<slug>/<record key>`. The slug is the source's
stable namespace — it is fixed at creation, and a new source under the same
slug re-adopts the elements.

## Syncing

Every sync is a **full** sync: the query's whole result is one run of the
bulk import runner (origin `sql`), so a run has per-row outcomes, retry with
backoff, cancel and `results.csv`. One run per source at a time. A source with
`scheduleMinutes` (5 minutes to a week) is synced by the scheduler; the next
sync is counted from when the last one was claimed. `onMissing: archive`
archives the elements whose row is gone; `keep` (default) only marks them.

## API

`/api/integration/sql/*`, console session only (`:id` is the id or the slug):

| Route                            | Role    | Does                                                          |
| -------------------------------- | ------- | ------------------------------------------------------------- |
| `GET sources`, `GET sources/:id` | any     | List / detail; the password is never returned (`hasPassword`) |
| `POST sources`                   | `ADMIN` | Create (`createSqlSourceSchema`)                              |
| `PATCH sources/:id`              | `ADMIN` | Update; omit `password` to keep it, `''` to remove it         |
| `DELETE sources/:id`             | `ADMIN` | Delete; the elements stay registered                          |
| `POST sources/:id/test`          | `ADMIN` | Connect, server version, TLS, write warning                   |
| `POST sources/:id/preview`       | `ADMIN` | The first 20 rows, converted, with column roles and issues    |
| `POST sources/:id/runs`          | any     | Sync now                                                      |
| `GET sources/:id/runs`           | any     | The source's last 50 runs                                     |

Source writes are audited (`SETTINGS`, field names only).

## CLI

```bash
pnpm --filter @bridge/api sql:sources -- --add source.json
pnpm --filter @bridge/api sql:sources -- --test erp-materials
pnpm --filter @bridge/api sql:sources -- --preview erp-materials
pnpm --filter @bridge/api sql:sources -- --sync erp-materials
pnpm --filter @bridge/api sql:sources -- --list
```

`source.json` is the `POST sources` body. The command needs `SQL_SOURCES=on`
like the routes, and `--sync` runs in its own process. See the
[runbook](runbooks.md).

## Errors

| Sentence                                                   | Fix                                                                      |
| ---------------------------------------------------------- | ------------------------------------------------------------------------ |
| wrong user or password, or pg_hba does not allow this host | Check the credentials and `pg_hba.conf`                                  |
| The query tried to write                                   | Remove the write; sources only read                                      |
| … ran longer than the statement timeout                    | Narrow the query, add an index, or raise `SQL_STATEMENT_TIMEOUT_MS`      |
| … is a private or loopback address                         | Set `SQL_ALLOW_PRIVATE_TARGETS=1` if the database is on your own network |
| The server's TLS certificate is not trusted                | Paste its CA as `caCertPem`, or use `tls: require`                       |
| returned more than N rows                                  | Narrow the query or raise `SQL_MAX_ROWS`                                 |
| The key columns cannot change once the source has elements | Create a new source with a new slug                                      |
