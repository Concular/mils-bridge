<!-- Generated from the MILS Bridge source repository (docs/integrations/ifc.md). Edit it there, not here. -->

# IFC models

A BIM model exported as an **IFC file** can be uploaded to this node. The BFF
parses it once, indexes every element (its class, name, type, storey,
property sets, quantities, materials and classification) and builds a compact
3D file for the viewer. The elements you select are then **published** to MILS,
one item each, with the element's data as the item's `ItemData`.

Each element is a keyed record of kind
`ifc-element`, keyed `ifc:<model slug>/<GlobalId>`. The **model** is the
namespace, not the file. When the next revision of the same model is
uploaded and published:

- an element whose data changed is **updated** in place (no new MILS item);
- an unchanged element is left alone;
- an element published under another Object or item type is **refused**,
  because an item is never moved.

The integration delivers:

- upload, processing and the element index (the `/api/integration/ifc/*` API);
- stored selections, a publish **preview** (what would be created, updated,
  left unchanged or refused) and the publish itself;
- the revision diff (added, removed and changed elements, by GlobalId);
- the `ifc:import` and `ifc:publish` CLIs;
- the Integrations card and its connection test;
- the console (below): the models list, the upload page and the workspace.

It does **not** deliver:

- `.ifczip` uploads (unzip first), and IDS `partOf` / `dataType` checks
  (below).

## How a file is processed

1. **Upload.** `POST /api/integration/ifc/revisions` (multipart, part `file`,
   plus `newModelName` or `modelId`). The first 64 KiB are checked before
   anything is stored. A file that is not STEP, or whose schema is not
   IFC2X3, IFC4 or IFC4X3, is refused with `415` and a sentence. The bytes go
   into the file store (`FILE_STORE_DIR`), and the revision is queued: `202`.
2. **Processing**, in a **child process** per revision (never in the server
   process), at most `IFC_MAX_PROCESSING` at a time:
   - _reading_ and _indexing_ with [web-ifc](https://github.com/ThatOpen/engine_web-ifc)
     (MPL-2.0), one pass per IFC relationship type;
   - _geometry_ with That Open's [Fragments](https://github.com/ThatOpen/engine_fragment)
     importer (MIT). A geometry failure does **not** fail the revision: it
     is READY without a 3D view, and the reason is in its warnings.
3. **READY** (or **FAILED** with a code and a sentence). The importer's own
   complaints about bad entities are kept as the revision's **warnings**.

A revision interrupted by a shutdown is resumed by the next server start
(only the HTTP server resumes, never a CLI).

### What is indexed

Every `IfcElement` **except** feature elements (openings, projections) and
virtual elements, which are geometry helpers. For each element:

| Field                                                                 | From                                                                                                                                |
| --------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------- |
| `class`, `predefinedType`, `name`, `description`, `tag`, `objectType` | the element itself                                                                                                                  |
| `type`                                                                | `IfcRelDefinesByType` (the type's class and name)                                                                                   |
| `properties`                                                          | `IfcRelDefinesByProperties` property sets, then the type's sets **under** them (an instance value wins)                             |
| `quantities`                                                          | quantity sets. Lengths, areas and volumes are converted to **SI** (m, m², m³) from the project's units                              |
| `materials`                                                           | `IfcRelAssociatesMaterial`: layer sets flattened with thicknesses (in metres), constituent sets with fractions, profile sets, lists |
| `classification`                                                      | `IfcRelAssociatesClassification`: system, code, name                                                                                |
| `spatial`                                                             | site, building, storey and space names. A part (a curtain wall's panel) sits where its whole sits                                   |
| `partOf`                                                              | the GlobalId of the element it is part of                                                                                           |

Property **values** are kept as the file has them; only quantities and layer
thicknesses are unit-converted. The payload carries **no** revision-specific
ids (no STEP line numbers, no file hash): otherwise every new export would
rewrite every item.

Property sets are the exporter's, not a standard: Revit exports carry
localised sets (`Andere`, `Bemaßungen`, …) beside `Pset_WallCommon`, some
tools export no quantities or types, and only some carry classification. The
element list's property filter takes any `<set>.<property>` key the model has
(`GET …/property-keys` lists them).

## Publishing

1. **Select**: `POST …/revisions/:id/selections` with explicit GlobalIds, a
   **filter** (classes, storeys, text, publish state, property predicates) or
   a **diff** against another revision (`{ diff: { against, changes:
   ['added' | 'changed'], published? } }`). An unnamed selection is stored for
   `IFC_SELECTION_RETENTION_DAYS`, because one of thousands of ids cannot
   travel in a URL; a named one is kept.
2. **Preview**: `POST …/publish/preview` with the selection, the target
   Object and an **item type per IFC class**. It answers how many elements
   would be created, updated, left unchanged, retried, kept archived or
   refused, with samples and one real payload. It writes nothing.
3. **Publish**: `POST …/publish`. One keyed-record run (origin `ifc`, never a
   full sync, so nothing is marked missing) that is followed like any bulk
   import (`/api/integration/bulk-imports/:id`). One publish per model at a
   time; at most `BULK_IMPORT_MAX_ROWS` elements per publish. The target
   Object and the class → item type mapping are remembered on the model.

The item's name comes from the element's `Name` by default (`nameFrom`:
`Name`, `Tag` or `Name+Tag`; an element without a name is named
`<class> <tag>`).

### Storeys as MILS Objects (opt-in)

With `mirror` on the publish (`{ levels: 'storeys' | 'buildings-storeys',
storeyTypeId, buildingTypeId? }`, the **Create an object per storey** box on
the Target step), the publish first creates one MILS Object per storey the
selection touches, under the target (and, for `buildings-storeys`, one per
building with its storeys under it), then writes each element under its
storey's Object. Elements in no storey go under the target.

- **Once per model and target.** Each created Object is recorded in
  `IfcSpatialObject` (`modelId`, `targetObjectId`, the spatial element's
  GlobalId, which is stable across revisions). A later publish under the same
  target reuses it; the preview says how many it would create and how many it
  reuses. A claim row is written before `POST /Objects`, so two publishes
  cannot create one storey twice (the second answers `409`); a failed
  `POST /Objects` releases its claim and fails the publish before any element
  is written.
- **Names.** The storey's or building's own name; siblings sharing one are
  numbered in tree order (`OG (1)`, `OG (2)`), counted over the whole model
  so the name does not depend on the selection.
- **Types.** The console offers first the types `ObjectTypeLinks` allows
  under the parent and pre-selects one named like the level; like the "New
  object" dialog, the links order the choice and never veto it.
- **Never moved.** An element already published under the target itself is
  refused (`TARGET_CHANGED`), as for any other target change.
- Who may do this: any console user, as for "New object". Deleting the model
  deletes the `IfcSpatialObject` rows, never the MILS Objects. The choice is
  remembered on the model (`IfcModel.mirror`).

### MILS properties

**Model settings › MILS properties** maps, per MILS item type the model's
classes publish as, each property type MILS lists for it
(`GET /PropertyTypes?ItemTypeId=`) to an element field (name, tag, storey,
materials, classification, …), a property or a quantity
(`IfcModel.propertyMap`, `IfcPropertyMap` in `@bridge/shared`). Only the
property names the classes of that item type carry are offered.

At publish time the values are written into the payload as
`milsProperties: { <code>: <scalar> }` (a list is joined with `; `, a missing
value leaves the property out). `PropertyData` reads `milsProperties` after
an operator's override and before the stored file and the payload's own
top-level keys, so the node answers those values for the item. The property
types themselves come from the `PropertyTypeRegistration` cache, which
`sync:actor-registry` fills: a property type added in MILS after the last
sync is valued only once the sync has run.

A changed map changes the payload of every element of that item type, so the
next publish **updates** them; it does not paint the published elements as
changed in the 3D view, because the publish state compares the element's own
hash (stored as the keyed record's `sourceVersion`), not the payload's.

## Console

- **Browse › IFC models** (`/ifc`) lists the models with their latest
  revision, its live processing stage, and how many elements are published.
  **Register element** has an _IFC model_ card that leads to the upload.
- **Upload** (`/ifc/new`). The browser reads the first 64 KiB with the same
  `sniffIfcHeader` the BFF uses and refuses a non-IFC file, an unsupported
  schema, a zip or an oversized file before sending anything. A file whose
  `IfcProject` GlobalId matches a model is offered as its next revision. The
  upload shows its progress, then the processing stages, and the workspace
  opens by itself when the revision is ready.
- **Workspace** (`/ifc/$modelId?rev=&focus=&view=`): the tree (spatial,
  classes, types; tri-state boxes; an ARIA tree), the 3D view (click,
  Ctrl-click, Shift-drag box — window left → right, crossing right → left —,
  double-click for the whole type; fit, isolate, hide, show all, x-ray,
  section, storey plan; spaces and openings hidden; published elements
  tinted green, changed ones orange), the table (server-paged, filters,
  property columns, "select all matching"), the inspector (one element's
  data, a property value selects every element with it; or a summary), and
  the tray with undo/redo and **Publish…**. Keys: Esc, Ctrl+Z /
  Ctrl+Shift+Z, Ctrl+A, F, I, H, Shift+H, S. Without WebGL, with
  `IFC_FRAGMENTS=off` or when the geometry failed, the workspace is
  table-only and says why.
- **Publish…** stores the selection, then: the target Object (or "same as
  last time"), an item type per class (remembered per model), the preview,
  and the run followed to its end with its results CSV.
- An element page of an `ifc-element` has **Open in model**, which opens the
  workspace with that element selected (`?focus=<GlobalId>`).

## Revisions: compare, update, archive

**Compare revisions** on the model page opens `/ifc/$modelId/compare`: how
many elements were added, removed, changed or left unchanged between two
revisions (by GlobalId and payload hash), the newer revision in 3D with the
added elements green and the changed ones orange, the rows, and for one
element the property-level diff (`FireRating: REI 60 → REI 90`). From there:

- **Update the N published elements that changed**: a publish of exactly the
  published elements whose MILS data is not the newer revision's, straight to
  the review step. Elements already published from the newer revision are not
  counted.
- **Archive the N published elements that were removed**: every published
  element of the model whose GlobalId the revision no longer has is archived
  through the Elements page's own archive (audited, reactivatable there). A
  publish never does this by itself.
- **Select the N added**: opens the workspace on the newer revision with
  them selected.

When fewer than 10 % of the elements kept their GlobalId (both revisions with
20 elements or more), the page says the exporter most likely regenerates
GlobalIds and does not offer the update: such a revision cannot update the
last one's items.

## Saved selections

**Save selection** in the bottom bar names the current selection. A named
selection never expires, is listed per model (**N saved selections**), and
loads on any revision: by GlobalId, so the elements still in that revision
are selected. Removing a saved selection is its author's or an `ADMIN`'s.

**Model settings** on the model page edits the model's name and its item type
per IFC class, so a publish starts from them.

## Opening a Concore IFC file

`/ifc/new` has two sources: **From this computer** and **From Concore**. The
second lists Concore's IFC files (`GET /ifc/` through the proxy); choosing one
and **Open in IFC models** sends `POST revisions/from-concore`
`{ concoreIfcFileId, modelId | newModelName }`. The BFF reads the entry
(`GET /ifc/{id}`) for its `file_url` and downloads it **server-side**: https
only, no credentials in the URL, the host must not be a private name and must
resolve publicly at connect time (the `publicOnlyLookup` agents), at most two
redirects, the upload size cap on the stream and `FILE_STORE_DOWNLOAD_TIMEOUT_MS`
as the deadline. Then exactly the upload path; the revision's header keeps the
Concore id, and the workspace says "opened from Concore" with a link back. A
Concore IFC file's own page (Browse › Concore › IFC files) has **Open in IFC
models**. An entry without a `file_url` cannot be opened, and says so.
`IFC_ALLOW_PRIVATE_DOWNLOADS` relaxes https and the address checks (tests,
desktop).

The download itself is `IfcService.createRevisionFromStream` (stream → the
store's `tmp/` under `IFC_MAX_BYTES` → the upload path), which the third
source shares.

## Opening a GENIA model

`/ifc/new` › **From GENIA** (and Browse › IFC models › GENIA, `/genia`) opens a
model held by a GENIA server — see genia.md. The revision's header
keeps `genia: { connectionId, connectionName, projectId, modelId, updatedAt }`
and the workspace says "opened from GENIA" with a link back to the project.

## IFCZIP

Every way in accepts a zipped IFC (`.ifczip`): `createRevision` sees the ZIP
signature and unzips the one `.ifc` inside first (`ifc/ifc-zip.ts`) — exactly
one `.ifc` entry (macOS/Windows noise ignored), stored or deflated, not
encrypted, no ZIP64; the unzipped bytes counted on the stream against
`IFC_MAX_BYTES`, and a declared expansion above 200× refused. The revision is
named after the entry and its header keeps `unzippedFrom`. A refusal is a
`415` (`413` for size) with the reason.

## The `.ifc` as a file item

**Publish the IFC file** on the model page publishes the revision's `.ifc` as
one MILS item through the Local elements file flow (stored, served by
`ItemFile` / `BinaryData`, a `local-file` mapping; the same bytes to the same
object and item type are one element), then writes one **item link** from
every published element of the revision to it (`POST /ItemLinks`, source =
the element, target = the file). The `ItemLinkType` is asked for, because the
contract publishes no enumeration: empty publishes the file without links.
`IfcFileLink` records each pair, so a second call adds only the missing links
(elements published since). The choice is remembered on the model
(`IfcModel.fileItem`).

## IDS checks

**Check against IDS** on the model page checks every element of the revision
against an IDS file (buildingSMART Information Delivery Specification, 0.9 and
1.0) and answers per specification: how many elements it applies to, how many
pass, why the others fail (the first 20, requirement by requirement), and
buttons that select the failing or the passing elements in the workspace. The
checker is native (`ifc/ifc-ids.ts`, no Python sidecar) and reads the index:

- facets `entity` (name, predefined type), `attribute` (Name, Description,
  Tag, ObjectType, GlobalId, PredefinedType), `property` (property sets and
  quantity sets alike), `classification` (system, code) and `material`;
- values as `simpleValue` or `xs:restriction` (enumeration, pattern, numeric
  bounds, lengths): strings exactly, numbers numerically, booleans
  case-insensitively;
- requirement cardinality (`required` / `optional` / `prohibited`, or 0.9's
  `minOccurs` / `maxOccurs`) and the specification's own occurrence;
- **not** `partOf` (the index keeps no assembly relations) and **not**
  `dataType` (it keeps values, not IFC measure types) — a specification that
  uses them says so;
- a specification written for another IFC version is checked anyway, with a
  warning.

IDS files sit on a node-wide shelf (`IfcIdsFile`): any console user adds one
(a file that does not parse as IDS is refused with the reason; the same file
twice is one row), its uploader or an `ADMIN` removes it. The check writes
nothing. SUM4Re's `IDS-Concular.ids.xml`, `IDS-Cirdax.ids.xml` and
`IDS-TS1090-201.ids.xml` all parse.

## Type objects

**Publish types** publishes type objects (`IfcWallType`, `IfcDoorType`, …)
instead of occurrences: one MILS item per type, keyed by the type's GlobalId
under the same `ifc:<slug>/` scheme, whose payload (`IfcTypePayload`,
`kind: 'type'`) holds the type's own property sets, materials and
classification and `instances: { count, classes }`. The dialog lists the
revision's types (most used first) with their publish state; the publish is
the usual dialog with a `types` selection (item type per type class, preview,
property map), never mirrored into storeys. Elements keep their own payloads:
the element → type link is the `IfcElement.typeGlobalId` column, not a payload
field, so indexing types changed no element's hash.

A revision processed before types were indexed (`typeCount` null) offers
**Process again** (`POST revisions/:id/reprocess`, the uploader or an
`ADMIN`): the same bytes are read again, so element payloads, hashes and every
publish state come out as before.

## API

All routes are under `/api/integration/ifc`, need a console session, and are
absent from the public integration surface. Renaming or deleting a model is
its uploader's or an `ADMIN`'s.

| Route                                  | What it does                                                                                |
| -------------------------------------- | ------------------------------------------------------------------------------------------- |
| `GET models` (`?projectGlobalId=`)     | models, newest first, with the latest revision and the published count                      |
| `GET` / `PATCH` / `DELETE models/:id`  | one model; rename, set the remembered item types or the property map; delete (published elements stay) |
| `GET models/:id/revisions`             | its revisions                                                                               |
| `POST revisions`                       | upload (multipart); `202`                                                                   |
| `GET revisions/:id`                    | status, stage, progress, header, counts, warnings                                           |
| `GET revisions/:id/fragments`          | the viewer's geometry; the ETag is its sha256                                               |
| `GET revisions/:id/tree`               | the spatial tree, classes with predefined types, types                                      |
| `GET limits`                           | the upload size, element and publish limits, and whether geometry is built                  |
| `GET revisions/:id/elements`           | paged rows; `filter` is a JSON-encoded filter, `sort` is `class`, `name`, `storey` or `tag`, `props` a JSON array of up to 8 property keys whose values come back per row |
| `GET revisions/:id/index`              | every element in columns (GlobalId, express id, class, storey, type, name, geometry, publish state) for the workspace |
| `GET revisions/:id/element-ids`        | every GlobalId matching `filter` ("select all matching")                                    |
| `GET revisions/:id/elements/:globalId` | one element with its full payload and its mapping                                           |
| `GET revisions/:id/published-state`    | `{ GlobalId → published / changed / archived }`                                             |
| `GET revisions/:id/property-keys`      | every `<set>.<property>` present, most common first; `?classes=` only those classes'        |
| `GET revisions/:id/diff?against=:id`   | added, removed and changed elements between two revisions                                   |
| `POST revisions/:id/selections`        | store a selection                                                                           |
| `POST revisions/:id/publish/preview`   | what a publish would do, and with `mirror` the Objects it would create                      |
| `POST revisions/:id/publish`           | start the publish; `202` with the run                                                       |
| `POST revisions/from-concore`          | open a Concore IFC file as a model or revision; `202`                                       |
| `POST revisions/:id/file`              | publish the `.ifc` as one file item and link the published elements to it                   |
| `GET` / `POST` / `DELETE ids-files`    | the IDS shelf (`POST` is multipart, part `file`)                                            |
| `POST revisions/:id/ids-check`         | `{ idsFileId }`: every element against an IDS file, per specification                       |
| `GET revisions/:id/types`              | the revision's type objects with publish state                                              |
| `POST revisions/:id/reprocess`         | read the file again (uploader or `ADMIN`); `202`                                            |
| `GET revisions/:id/elements/:globalId/compare?against=:id` | one element in two revisions, property by property                     |
| `POST revisions/:id/archive-removed`   | archive the model's published elements this revision no longer has                          |
| `GET models/:id/selections`            | the model's saved selections                                                                |
| `PATCH selections/:id`                 | `{ name }` keeps a selection, `{ name: null }` lets it expire                               |
| `DELETE selections/:id`                | delete a selection (its author or an `ADMIN`)                                               |
| `GET selections/:id/ids?revision=:id`  | a stored selection evaluated on a revision of its model                                     |

## CLI

```bash
pnpm --filter @bridge/api ifc:import model.ifc --new-model "Facade A"
pnpm --filter @bridge/api ifc:import model-rev2.ifc --model facade-a
pnpm --filter @bridge/api ifc:publish --model facade-a --object <id> --item-type <id> --class IfcWall,IfcDoor --dry-run
pnpm --filter @bridge/api ifc:publish --model facade-a --object <id> --item-type IfcWall=<id> --item-type IfcDoor=<id>
```

Both run in their own process: `ifc:import` processes the file before it
exits, `ifc:publish` runs the publish to the end. Neither needs the server.

## Configuration

| Variable                       | Default                | Meaning                                                                  |
| ------------------------------ | ---------------------- | ------------------------------------------------------------------------ |
| `IFC_MAX_BYTES`                | `FILE_STORE_MAX_BYTES` | the largest file accepted, refused on the stream                         |
| `IFC_MAX_ELEMENTS`             | 200 000                | a model above it fails (`TOO_MANY_ELEMENTS`) rather than being truncated |
| `IFC_MAX_PROCESSING`           | 1                      | revisions processed at once                                              |
| `IFC_PROCESS_MEMORY_MB`        | 2048                   | the child is killed above this RSS (`OUT_OF_MEMORY`)                     |
| `IFC_PROCESS_TIMEOUT_MS`       | 15 min                 | wall clock per revision (`TIMEOUT`)                                      |
| `IFC_FRAGMENTS`                | on                     | `off` skips the 3D geometry on small hosts                               |
| `IFC_SELECTION_RETENTION_DAYS` | 7                      | how long a stored selection lives                                        |
| `IFC_ALLOW_PRIVATE_DOWNLOADS`  | off                    | a Concore `file_url` may be plain http or resolve privately (tests)      |

**Sizing.** Measured on eight real models:
peak memory is about 6× the file size while indexing and about 8× while
building geometry. An 80 MB model is indexed in about 5 s and its geometry
built in about 13 s on Node 22. The desktop app (Electron 33, Node 20)
builds geometry about 3× slower.

## Security

- The file is untrusted input to a C++/WASM parser. It is parsed in a child
  process with no database handle and a minimal environment (no secrets),
  watched by an RSS limit, a stall limit and a timeout. A crash fails the
  revision, not the server.
- Memory is bounded by watching the child's RSS, **not** by V8 heap flags
  alone: web-ifc's WASM memory is outside V8's heap.
- Nothing on `/rest/*` exposes the model, its index or its geometry. A peer
  reads only the published elements' `ItemData`, under the normal access
  rules.
- The `.ifc` and `.frag` blobs are kept in the file store as long as a
  revision references them (`files:gc` knows them).
- A Concore `file_url` is a URL another system handed us: it is fetched only
  over https, to a host that is not a private name and does not resolve to a
  private address, with the size cap and a deadline.
- An IDS file is parsed as data (`fast-xml-parser`); a document with a
  DOCTYPE or entity declaration is refused before parsing, so nothing is
  expanded or fetched. Its patterns run as anchored JavaScript regexes over
  short property values.
