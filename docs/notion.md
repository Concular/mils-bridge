<!-- Generated from the MILS Bridge source repository (docs/integrations/notion.md). Edit it there, not here. -->

# Notion

An administrator connects a **Notion workspace** through an internal
integration and shares databases with it in Notion. A **synced source** is one
Notion _data source_ (a database's table): each row — a Notion page — becomes
one MILS element (`notion-page`, keyed `notion:<page id>`) whose payload is the
row's properties as plain JSON. A later sync **updates** the elements whose row
changed, leaves the others alone, and marks the rows that disappeared — the
keyed record machinery.

Phase 1 (`plans/notion-integration-plan.md`): connections, browsing what is
shared, synced sources with one fixed target each, the `notion:sources` CLI,
and a status panel. Page content as Markdown, attachments as files, routing
rows to objects by a property and a Notion filter are phase 2; webhooks and
per-user OAuth phase 3.

## Connecting a workspace

1. In Notion, create an **internal integration** (Settings → Connections →
   Develop or manage integrations) with **read content** capability, and copy
   its token (`ntn_…`).
2. Add it here: `pnpm --filter @bridge/api notion:sources -- --add-connection
<name> <token>` (or `POST /api/integration/notion/connections`, `ADMIN`).
   The token is sealed (`SECRETS_KEY`), never returned, and covered by
   `encrypt:secrets`; the answer shows the workspace and bot name.
3. In Notion, **share** each database with the integration (… →
   Connections). That sharing is the boundary: the bridge reads nothing that is
   not shared, and does not try to.

`--search <connection> [text]` lists the data sources the integration can see,
with their ids.

## Syncing a data source

```json
{
  "connectionId": "…",
  "dataSourceId": "1a2b3c4d111122223333444455556666",
  "milsObjectId": "{…}",
  "itemTypeId": "{…}",
  "includeProperties": ["Name", "Code", "material.kind"],
  "scheduleMinutes": 60,
  "onMissing": "archive"
}
```

`--add-source source.json`, then `--preview <source>` (the first 20 rows as
they would be registered) and `--sync <source>`. Every sync is a **full** sync
of the data source: one run of the bulk-import runner (origin `notion`), with
per-row outcomes, retry, cancel and `results.csv`. A scheduled source
(`scheduleMinutes`, 5 minutes to a week) is synced by the scheduler. Pages in
Notion's trash are left out, so they become missing; `onMissing: archive`
archives their elements, `keep` (default) only marks them.

## What a row becomes

| Notion property                                                    | Payload value                                                                                                                      |
| ------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------- |
| `title`, `rich_text`                                               | the plain text                                                                                                                     |
| `number`, `checkbox`, `url`, `email`, `phone_number`               | the value                                                                                                                          |
| `select`, `status`                                                 | the option name                                                                                                                    |
| `multi_select`                                                     | the option names                                                                                                                   |
| `date`                                                             | `{ "start", "end"? }`                                                                                                              |
| `people`                                                           | the names                                                                                                                          |
| `relation`                                                         | `notion:<page id>` of each related page — the related row's own element key                                                        |
| `formula`, `rollup`                                                | their computed value                                                                                                               |
| `unique_id`                                                        | `PREFIX-123`                                                                                                                       |
| `files`                                                            | `[{ "name" }]` — a Notion-hosted URL expires within the hour and is **never** published; an external link is kept as `externalUrl` |
| `created_time`, `last_edited_time`, `created_by`, `last_edited_by` | left out unless listed in `includeProperties` (they change without the content changing)                                           |
| `button`, `verification`, `place`                                  | left out                                                                                                                           |

Property names are the keys, and dotted names nest as in bulk import
(`material.kind` → `{ "material": { "kind": … } }`). `includeProperties`
narrows the payload — **every included property is published** to the MILS
network under this node's access model. The element is named by `nameProperty`,
else the title property. A page's `last_edited_time` is recorded as its version;
whether it changed is decided by the payload's hash, so a property left out of
the payload never causes an update.

## Limits and errors

Every call pins `Notion-Version: 2025-09-03` (the data-source model). Calls of
one connection go one after another at `NOTION_RATE_PER_SECOND` (default 3, the
rate Notion allows); a `429` is waited out once. A data source with more than
`BULK_IMPORT_MAX_ROWS` rows is refused rather than cut.

| Sentence                                         | Fix                                                                      |
| ------------------------------------------------ | ------------------------------------------------------------------------ |
| The integration cannot see this page or database | Share it with the integration in Notion (… → Connections)                |
| Notion refused the token                         | The token is wrong or the integration was removed; update the connection |
| Notion is rate limiting this connection          | Wait; a sync continues more slowly                                       |

## API

`/api/integration/notion/*`, console session (writes and previews `ADMIN`):
`connections` (list, get, create, update, delete — refused while it has
sources —, `:id/test`, `:id/search?q=&type=data_source|page`,
`:id/data-sources/:dataSourceId`), `sources` (list, get, create, update,
delete — the elements stay —, `:id/preview`, `POST :id/runs` = sync now,
`GET :id/runs`). Writes are audited (`SETTINGS`, field names only).

| Variable                    | Default                     | Meaning                         |
| --------------------------- | --------------------------- | ------------------------------- |
| `NOTION_API_BASE`           | `https://api.notion.com/v1` | Only tests point it elsewhere   |
| `NOTION_REQUEST_TIMEOUT_MS` | 15 s                        |                                 |
| `NOTION_RATE_PER_SECOND`    | 3                           | Calls per connection per second |
