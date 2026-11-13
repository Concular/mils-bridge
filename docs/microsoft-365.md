<!-- Generated from the MILS Bridge source repository (docs/integrations/microsoft-365.md). Edit it there, not here. -->

# Microsoft 365

SharePoint document libraries and OneDrive for Business through Microsoft
Graph (`plans/microsoft-365-integration-plan.md`, phase 1). Each console user
connects their own **work account** (delegated, read-only: `Files.Read.All`,
`Sites.Read.All`); the BFF browses and downloads as that user. A registered
file is copied into the local store like a Drive file (`m365-drive-item`,
keyed `<driveId>/<itemId>`), and its `StoredFileDto` is the ItemData.

**Setup.** Register a Web application in Microsoft Entra with the redirect URI
`<bridge>/api/integration/microsoft-365/oauth/callback`, create a client
secret, and enter client id, secret, tenant (id/domain, or empty for
`organizations`) and redirect URI under Integrations → Microsoft 365 (env
fallback: `M365_CLIENT_ID`, `M365_CLIENT_SECRET`, `M365_TENANT`,
`M365_REDIRECT_URI`). Many tenants need an admin to consent once; the panel
shows the admin-consent link. Users connect from the same panel (auth code
flow with PKCE; refresh tokens rotate and are sealed).

**Routes** (`/api/integration/microsoft-365/*`, console session): connection,
connect, oauth/callback, disconnect; `locations/my-drive`, `locations/shared`,
`sites?search=`, `sites/:siteId/drives`, `drives/:driveId/items`,
`drives/:driveId/items/:itemId`; `POST registrations` (optional
`convertTo: "pdf"` for Office files); `POST drives/:d/items/:i/resync`
(stale when the `cTag` moved).

**Downloads** follow one redirect, `https` only, to a host in
`M365_DOWNLOAD_HOST_SUFFIXES` (default SharePoint/OneDrive hosts) that does not
resolve privately, without the Authorization header.

**CLI:** `register:m365-item -- --user <email> --drive --item --object
--item-type [--pdf]`, `m365:resync -- [--user <email>] [--apply]`.

Test-only env: `M365_GRAPH_BASE`, `M365_LOGIN_BASE`,
`M365_ALLOW_PRIVATE_DOWNLOADS` — they point the integration at a local fake of
Microsoft's sign-in and Graph, which is how phase 1 was run end to end (PKCE,
token rotation, paging, a download redirect that never receives the token,
register, re-sync, disconnect). It has not yet run against a real tenant. Phase 2: the console browser; phase 3:
app-only site connections.
