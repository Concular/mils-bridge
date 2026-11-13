<!-- Generated from the MILS Bridge source repository (docs/integrations/bulk-import.md). Edit it there, not here. -->

# Bulk import

Register many elements at once from one **CSV**, **JSON** or **NDJSON** file.
Each record becomes one MILS Item, and the record itself becomes that item's
`ItemData` payload. Design and later phases are in
`bulk-import-plan.md`.

A bulk import is a loop over the [Local elements](local-elements.md) JSON value
registration, not a new kind of element. Every row is a `json-value` mapping,
so `GET /rest/MilsItems`, Access → Elements, the object handshake, `ItemData`
and `PropertyData` treat an imported element exactly like a typed one.

An import can also be made from an **S3 prefix** instead of a file
(`POST /bulk-imports/s3`, format `s3`). Its rows are the objects under the
prefix, and the runner registers each one as an `s3-object` element through
`S3RegistrationService.register()` rather than as a JSON value. See
[Amazon S3](s3.md). The S3 bucket browser starts these imports and shows
their progress. It is the only console UI for bulk imports so far.

**Status (phase 1):** the BFF API and the `import:bulk` CLI. The API needs a
console session. The console UI (phase 2) and access for other systems with
the actor JWT (phase 3) are not built yet.

## How it works

1. **Upload and validate.** `POST /api/integration/bulk-imports` parses the
   file, applies the default target, types the values and checks every row.
   It writes nothing to MILS. It makes one read per **distinct** target
   (`GET /Objects/{id}`, `GET /ItemTypes/{id}`), so a wrong default fails the
   preview instead of every row. It also counts how many rows already exist,
   using only `ResourceMapping`. The import is then `READY`, or `INVALID` when
   the file is unreadable or no row is valid.
2. **Start.** `POST …/:id/start`, or `start=true` on the upload. The runner
   in the BFF process registers the `PENDING` rows, a few at a time
   (`BULK_IMPORT_CONCURRENCY`).
3. **Follow.** `GET …/:id` returns the counters. `GET …/:id/rows?status=FAILED`
   returns the rows. `GET …/:id/results.csv` returns every row with its
   outcome, MILS item id and error, ready to hand back to the source system.
4. **Retry or cancel.** `…/:id/retry` re-queues the `FAILED` rows and carries
   on with any left `PENDING`. `…/:id/cancel` stops between rows. Rows already
   registered stay registered.

Re-importing the same file is safe. A row's key is `sha256(canonical payload +
object + item type)`, the same key as a typed JSON value. A row that is
already registered answers `EXISTS`, and a row that failed earlier is retried
on its existing mapping. Two identical rows in one file are registered once:
the later one is `SKIPPED` with `DUPLICATE_ROW`.

## File formats

### CSV

- UTF-8 (a BOM is fine). Anything else is refused with `FILE_ENCODING`.
- A header row is required. The delimiter is detected from it (`,`, `;` or
  tab), or set with `delimiter` (`comma`, `semicolon`, `tab` also work).
- **Empty cells are omitted** from the payload.
- Column types, set per column with `columnTypes`; the default is `auto`:

  | Type      | Turns into                                                                                                      |
  | --------- | --------------------------------------------------------------------------------------------------------------- |
  | `auto`    | `true`/`false` → boolean; a plain decimal with no leading zero → number; everything else stays text (`007` too) |
  | `string`  | The text verbatim                                                                                               |
  | `number`  | A number; leading zeros and a decimal comma (`12,5`) are accepted                                               |
  | `boolean` | `true`/`false`, `yes`/`no`, `1`/`0`                                                                             |
  | `json`    | The cell parsed as JSON, which is how a CSV carries nested values                                               |

- `nestDottedHeaders=true` turns `address.city` into `{ "address": { "city": … } }`.
  It is off by default, because property codes may contain dots.

### JSON and NDJSON

- **Bare array**: `[{ "code": "W-01", "mass": 12.5 }, …]`. Every element must
  be an object.
- **Envelope**: `{ "defaults": { "milsObjectId", "itemTypeId" }, "rows": [{ "payload": {…}, "name", "milsObjectId", "itemTypeId", "skip" }] }`.
  No payload key is interpreted, not even one starting with `@`. Defaults sent
  with the request outrank the envelope's.
- **NDJSON** (`.ndjson`, `.jsonl`): one bare object per line. Rows are
  numbered by line, and a bad line fails only that row.

### Reserved columns and keys

These apply to CSV and to bare JSON. They steer a row and never enter its
payload. Any other column or key starting with `@` is refused, so a typo
cannot silently become payload.

| Column          | Meaning                                               |
| --------------- | ----------------------------------------------------- |
| `@milsObjectId` | The row's MILS Object (braced or bare GUID)           |
| `@itemTypeId`   | The row's ItemType                                    |
| `@name`         | The element's display name (as in the element tables) |
| `@skip`         | Any truthy value skips the row                        |

## API

All routes are under `/api/integration/bulk-imports`. They need a **console
session**, and the import is not part of the public OpenAPI document yet.
Contracts are in `packages/shared/src/bulk-import.ts`.

| Route                  | Purpose                                                                                                                                                                    |
| ---------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `POST /`               | Multipart (`file` plus option fields), **or** the raw file with `Content-Type: text/csv` / `application/json` / `application/x-ndjson` and the options in the query string |
| `POST /s3`             | JSON `{ connectionId, prefix, recursive, milsObjectId, itemTypeId, start }`: one row per object under an S3 prefix ([Amazon S3](s3.md))                                    |
| `GET /`                | List: `status`, `mine`, `page`, `pageSize`                                                                                                                                 |
| `GET /:id`             | Counters, options, file errors and the first 50 row issues                                                                                                                 |
| `GET /:id/rows`        | Paged rows: `status`, `page`, `pageSize`                                                                                                                                   |
| `GET /:id/results.csv` | Every row's outcome                                                                                                                                                        |
| `POST /:id/start`      | `READY` → `QUEUED`                                                                                                                                                         |
| `POST /:id/cancel`     | `RUNNING` → `CANCELLING`, or `READY`/`QUEUED` → `CANCELLED`                                                                                                                |
| `POST /:id/retry`      | `COMPLETED_WITH_ERRORS`/`CANCELLED` → `QUEUED`                                                                                                                             |
| `DELETE /:id`          | Deletes the import record only, never a mapping. Refused while it runs                                                                                                     |

Options are `format`, `milsObjectId`, `itemTypeId`, `delimiter`, `columnTypes`
(an object, JSON text, or `col=number,other=json`), `nestDottedHeaders`,
`fileName` and `start`. A refused action answers `409` with a sentence.
Changing another user's import needs `ADMIN`.

```bash
curl -b cookies.txt -H 'Content-Type: text/csv' --data-binary @walls.csv \
  'http://localhost:8080/api/integration/bulk-imports?milsObjectId=%7B…%7D&itemTypeId=%7B…%7D&columnTypes=mass%3Dnumber&start=true'
```

## Runner

The runner is in-process (`bulk-import/bulk-import.runner.ts`), with no
scheduler and no broker.

- **Claiming.** It claims an import with a compare-and-set `QUEUED → RUNNING`,
  so no import is ever run twice.
- **Transient failures.** No answer, `408`, `429` or `5xx` back off (1 s,
  doubling, at most 60 s) and retry the same row, up to 5 attempts.
- **Refusals.** Any other status fails the row.
- **Aborting.** After 50 consecutive failed rows the run stops and leaves the
  rest `PENDING`.
- **Restarts.** Only the HTTP server resumes imports at boot (`main.ts`), so a
  CLI script never takes over the server's work. On shutdown, a running import
  goes back to `QUEUED`.
- **Audit.** Create, start, cancel, retry and delete are audited
  (`kind: 'BULK_IMPORT'`, shown in the activity feed). Each row still writes
  its own `RegistrationLog`.
- **Keyed records.** The same runner runs sync runs of keyed record sources
  (`origin` other than `file`): each row is upserted by its source key instead
  of registered by its content, and can end `UPDATED`, `UNCHANGED` or
  `REACTIVATED`. See Keyed records.

## Limits

| Variable                     | Default | Meaning                                                  |
| ---------------------------- | ------- | -------------------------------------------------------- |
| `BULK_IMPORT_MAX_BYTES`      | 20 MiB  | Largest file, for multipart and raw bodies alike         |
| `BULK_IMPORT_MAX_ROWS`       | 10,000  | Rows per import. Above it the file is refused, never cut |
| `BULK_IMPORT_CONCURRENCY`    | 4       | Rows in flight per running import                        |
| `BULK_IMPORT_MAX_RUNNING`    | 2       | Imports running at once; the rest wait                   |
| `BULK_IMPORT_RETENTION_DAYS` | 31      | Finished imports are pruned lazily; mappings never are   |

Each row's payload must also fit `ITEM_PAYLOAD_MAX_BYTES`. That is checked at
validation, never at run time.

## CLI

```bash
pnpm --filter @bridge/api import:bulk walls.csv --object '{…}' --item-type '{…}' --types mass=number
pnpm --filter @bridge/api import:bulk walls.csv --object '{…}' --item-type '{…}' --dry-run
```

Without `--dry-run` or `--no-start`, the import runs in the script's own
process and prints progress. See the [runbook](runbooks.md).
