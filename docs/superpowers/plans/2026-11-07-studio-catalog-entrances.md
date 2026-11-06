# Catalog entrance blocks implementation plan

> Execute inline with superpowers:executing-plans; request a fresh read-only review before release.

Goal: explicit «Вход из каталога» in the library, always connected from «Начало», opening a chosen scenario step; multiple named entrances, preserved legacy services.

Approved design: follow the user's explicit rename/library/start-only request using existing entry_points serialization. A library action opens a small creation form bound to Start; no floating runtime block or entry with a missing target is persisted. Creating an entrance is one undoable edit; cards still move/resize independently. Existing entries stay unchanged unless edited. No schema version bump, database migration, new dependency, or production access. Alternative new runtime kind rejected because entrance selection precedes runtime execution and existing compatible entry_points already implement it.

Actor: admin. Job: create catalog entry to a selected starting step. Archetype: existing map Studio/workbench, library and inline entrance editor. Missing blocks/disabled maps/64-entry limit get explicit states. Source is fixed Start, target excludes policy attachments. Multiple entrances to the same target may have independent names; original main entrance is retained. Ordinary route sources can never target entrance cards, including reconnect operations.

Files: scenario-map-model/canvas/link-card/workbench; new scenario-catalog-entrance component; existing entry inspector; focused model/component/canvas tests; new fixture browser test; UNIFIED_SERVICE_SCENARIOS/CODEMAP and release report. Reuse existing Start connector and local card geometry.

- [ ] Capture source/DB baseline and verified backup; account for dirty checkout via alternate index.
- [ ] Add failing tests for explicit entrance creation, source/target guards, unchanged main/block graph/schema, independent entries, old maps, read-only/empty/limit state.
- [ ] Add library and Start action creation UI; consistent Russian rename; reject graph links into catalog cards in connect/reconnect paths.
- [ ] Focused tests, frozen build/workspace and 1366/1920 browser checks including legacy; fresh strict review and fixes.
- [ ] Freeze task-only commit over installed67ef61b0; canonical staging deploy with source guard; live browser on own test draft, preserve original tabs, archive own test data; compare all original hashes/versions and report.
