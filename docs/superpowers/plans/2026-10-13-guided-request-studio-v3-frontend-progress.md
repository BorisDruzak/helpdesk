# Studio v3 frontend integration progress

Implemented in the functional working tree; no commit, push, deployment, real ticket, or real scenario/policy publication was performed.

## Integrated behavior

- Studio navigation now has Catalog, Scenario Map, and Approvals. Simulation, publication and versions use contextual panels while the map stays mounted. Issue links open the relevant transition or policy inspector.
- Administrative catalog includes directly openable scenario-map cards, description, draft/publication state, active version, updated date and optional server-projected published entrance count. Existing Service/Offering and form access remain available.
- Approval editor uses the existing Helpdesk model registry and publish-policy API. It supports any_one, all and sequential modes and requester_manager, service_owner, queue_lead and explicit active support/admin accounts from the existing admin registry. Publishing requires explicit confirmation. Editing an existing scheme preserves unfamiliar config, nested source options and original scope.
- Saved drafts autosave after 1200ms debounce. The initial draft is saved explicitly. Save success advances the known server revision while preserving newer local edits; stale responses/errors from a departed editor are ignored. Conflicts retain local work and stop autosave until an explicit server reload or manual save succeeds. Editing remains possible while saving.
- Requester offerings consume published catalog_items, searchable by title, description and synonyms. Choosing an entrance sends only offering_full_code and entry_point_key; no target/version authority is supplied by the browser. Selection and opaque session IDs are cached by user, offering and entrance; server session pins the actual version/context. Ordinary forms and legacy single-entrance scenarios remain supported.

## Verification executed

- RED: selected-entrance session regression initially resumed the default cached session and failed because no POST body was sent. GREEN after entrance-key isolation.
- npm test --prefix webapp -- src/features/request-template-studio src/features/requester/scenario-session.test.tsx src/features/requester/scenario-entrances.test.tsx src/pages/admin/request-template-studio-page.test.tsx src/pages/admin/request-template-studio-catalog.test.tsx: 29 files, 124 tests PASS.
- Added debounce/latest-edit regression afterward; npm test --prefix webapp -- src/features/request-template-studio/use-scenario-editor.test.tsx: 3 tests PASS.
- npm run build --prefix webapp: PASS after final product changes, TypeScript and Vite production build.
- Browser fixtures on port 4183 using compiled production dist, at 1366x768 and 1920x1080: category creation, trusted processing selection, diagnostic simulation boundary, 32-question editor/sections, simulation input/focus, auditor access, offering creation, publication issue links, explicit publication, catalog/unsaved guard, map keyboard editing + persisted geometry, independent template and explicit approval-policy confirmation PASS.
- Main desktop browser run: 25 of 26 passed; publication1920 found a clipped confirmation button. Sticky confirmation footer plus root's available-height map CSS fix resolved it; targeted publication1920 and approval1366/1920 retry: 3 PASS.
- Requester selected-entrance search, POST contract and pinned-session resume PASS at both requested desktop sizes. Legacy escape-ticket1366 also PASS.
- git diff --check: PASS after stripping extra EOF blank lines.

## Limits

- Explicit approvers now use canonical active admin/support account logins, selected by human-readable names through the existing admin registry. Group approvers remain unavailable: the backend produces literal group:<id> while the actual decision handler requires an exact authenticated actor ID and has no membership expansion. Existing group configuration is preserved; no second approval runtime is introduced.
- Approval late-response regression reproduced graph overwrite and mutation after unmount; latest-definition and mounted/scenario-generation guards resolve both. Four focused approval regressions and TypeScript check passed.
- Browser evidence is synthetic fixture acceptance; production and staging installed acceptance are not claimed. Backend/database evidence and final whole-project baseline checks are owned by the root task.

## Parent final checks

Full baseline711 frontend tests passed; later source-specific129 passed including
multiline synonym and deferred approval publication regressions. Dynamic React Flow
handles refresh through useUpdateNodeInternals; browser pointer regressions at
1366/1920 cover movement, immediate new edge rendering, target reconnect, dropped
block insertion retaining conditions, explicit entrance deletion and compound
Undo/Redo. Full fixture suite118 passed. Map uses full available page width and
measures viewport height for the graph/inspector; final targeted layout checks
verify the canvas stays inside both desktop viewports. Production TypeScript/Vite
build passed. Fixture server emits known Windows Proactor connection-reset teardown
messages separately from product console/network assertions.
