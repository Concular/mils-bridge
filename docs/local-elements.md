<!-- Generated from the MILS Bridge source repository (docs/integrations/local-elements.md). Edit it there, not here. -->

# Local elements — files and JSON values from the console itself

Console users register **a file from their own computer**, or **a JSON value
they type in**, straight into MILS as an Item — in one step, with no upstream
system behind it. The console user is the source. Both end exactly where the
Google Drive and API Explorer registrations end, so nothing downstream tells
them apart: a peer reads a file's descriptor as `ItemData` and its bytes as
`ItemFile` / `BinaryData`, and reads a value as `ItemData` verbatim.

```
File   /local-elements → Register a file → pick file · Object · ItemType [· name] → Upload & register
       → FileStore blob + StoredFile (source 'upload') → POST /Items → ResourceMapping (kind local-file)
       → MilsItemPayload = StoredFileDto descriptor → RegistrationLog

Value  /local-elements → Register a JSON value → type { … } · Object · ItemType [· name] → Register value
       → POST /Items → ResourceMapping (kind json-value) → MilsItemPayload = the value → RegistrationLog
```

This is what closed gaps 1 and 2 of
`multi-source-element-registration-report.md`:
before it, bytes could only enter the node through Google Drive, and a JSON
value needed "create an item, then paste" — which wrote no `ResourceMapping`
row, so the item was invisible to `GET /rest/MilsItems`, to Access → Elements
and to the object-access handshake.

## How it fits together

| Piece                | Where                                                                                      | Notes                                                                                                                                                        |
| -------------------- | ------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Registry entry       | `INTEGRATIONS['local-elements']` in `packages/shared/src/integrations.ts`                  | Role `source`, kinds `local-file` + `json-value`, `browsePath: '/local-elements'`, empty settings slice                                                      |
| Contracts            | `packages/shared/src/local-elements.ts`                                                    | `registerLocalFileSchema` (the multipart text fields), `registerJsonValueSchema`, the two result DTOs, `LOCAL_FILE_FIELD`, `JsonValueSnapshot`               |
| Module               | `apps/api/src/local-elements/`                                                             | Controller + two registration services + `MimeSniffService`; `MulterModule` configured here                                                                  |
| Uploaded file        | `StoredFile` row with `source = 'upload'`                                                  | `sourceFileId` = the upload key; `mimeType` = sniffed from the bytes, `sourceMimeType` = what the browser declared; Drive-only columns stay null             |
| Cross-reference      | `ResourceMapping` with `concoreKind = 'local-file'` / `'json-value'`, `concoreId = <key>`  | `ownerUserId` = the console user who registered it                                                                                                           |
| Item payload (file)  | `MilsItemPayload` = `StoredFileDto`                                                        | The same descriptor a Drive registration writes — `internalContentPath` points at `ItemFile`, and the peer panel's file button recognises it                 |
| Item payload (value) | `MilsItemPayload` = the value, verbatim                                                    | A JSON **object** under `ITEM_PAYLOAD_MAX_BYTES` (64 KiB); arrays and scalars are refused at both ends                                                       |
| Mapping snapshot     | `concoreSnapshot`                                                                          | File: `{ name, mimeType, sourceMimeType, size, sha256, source }`; value: `{ kind: 'json-value', name, payload }` — `displayNameFor` reads both               |
| Provider             | `apps/api/src/integrations/providers/local-elements.provider.ts`                           | Counts + the two caps as facts; `test()` checks the file store directory is writable and never leaves the BFF                                                |
| Console              | `apps/web/src/features/local-elements/`, route `routes/_explorer/local-elements/index.tsx` | Two cards (file, JSON value) over `MilsRegisterTargetPicker`, then the elements registered from this console — the `/mappings` table filtered to this source |

## Endpoints

Both under `/api/integration/local-elements`, guard `session` (`AuthGuard`) —
never the actor JWT. Not in `PUBLIC_INTEGRATION_PREFIXES`, so absent from the
public OpenAPI document; the mappings they create are visible through the
public `/mappings` routes like any other.

| Method | Path    | Body                                                                                            | Answer                                                                         |
| ------ | ------- | ----------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------ |
| POST   | `files` | `multipart/form-data`: `milsObjectId`, `itemTypeId`, optional `name`, and one part named `file` | `LocalFileRegistrationResultDto` — `outcome`, the mapping, the `StoredFileDto` |
| POST   | `json`  | `application/json`: `{ milsObjectId, itemTypeId, name?, payload }`                              | `JsonValueRegistrationResultDto` — `outcome`, the mapping, `payloadBytes`      |

Failure shapes, in the order they can happen:

- **400** — a malformed id, a missing or empty file part, a payload that is not
  an object, or one over `ITEM_PAYLOAD_MAX_BYTES` (checked **before** the MILS
  item exists — the payload is the point).
- **413** — a file over `FILE_STORE_MAX_BYTES`. Multer refuses it while
  streaming; no byte reaches the registration service.
- **502** — MILS refused `POST /Items`. The mapping is `FAILED` with a
  `RegistrationLog` row; for a file the blob and its `StoredFile` row stay
  (harmless, `files:gc`-able), and the same upload again retries the row.

## The upload key — why the same file can be `EXISTS` and also a second element

Every other source has a natural id (a Concore entity, a Drive file, an
exchange) for `@@unique([concoreKind, concoreId])` to key on; that unique is
what turns a double-click into `EXISTS` and a failed attempt into something a
retry picks up. A local element has none, so `local-element-key.ts` derives
one:

```
sha256( <content digest> "\n" <object id> "\n" <item type id> )
```

The **target is part of the key**. Keyed on content alone, one photo could
never be registered under two Objects; keyed on nothing, a double-click would
create two MILS items. So: the same bytes (or the same value, with keys sorted
at every level) to the same Object and ItemType is one element, and to another
Object is a second one. Ids are normalised to the bare lowercase uuid first.

For a file the same key is the `StoredFile.sourceFileId`; the blob itself is
content-addressed by the store and never written twice.

## The mime type

The browser's declared `Content-Type` for a part is whatever the OS mapped the
extension to. The bytes are the truth, so `MimeSniffService` (the `file-type`
package, ESM-only, loaded like the Scalar parsers) reads the magic bytes and
`chooseMimeType()` prefers that; text formats have no signature, so a
well-formed declared type is next, and `application/octet-stream` is last.
That is a **storage** decision, not the safety boundary: whatever is stored is
served with `X-Content-Type-Options: nosniff`, and `text/html`,
`image/svg+xml` and scripts are forced to `Content-Disposition: attachment` by
`send-stored-file.ts` regardless of source.

## What is deliberately not here

- **No re-sync.** The console was the source; the source cannot move on.
  Upload again to replace — under the same target that refreshes the
  descriptor and answers `EXISTS`.
- **No batch.** One element per call. `files: 1` in the multer config; a
  multi-file form is a follow-up (§6 D of the report).
- **No actor-JWT access.** A machine caller has the public `item-payloads`
  surface for JSON and nothing for files, on purpose.
- **No size knowledge in the console.** `FILE_STORE_MAX_BYTES` is env; the
  BFF's 413 is the message. The JSON card does check
  `ITEM_PAYLOAD_MAX_BYTES`, which is code.

## Related

- [`google-drive.md`](google-drive.md) — the file store and the descriptor
  convention this reuses.
  the shared registration shape.
- [`mils-internal-api.md`](mils-internal-api.md) — how a
  peer reads what was registered.
