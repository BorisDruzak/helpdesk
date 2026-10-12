# Guided Request Studio v3 — backend progress

## Implemented contracts

- `ScenarioDraftDefinition` / `ScenarioDefinition`: additive `entry_points` (maximum 64) with `key`, `title`, `description`, `category_id`, `synonyms` (maximum 20), `visibility` (`public|internal|restricted`), `enabled`, `target_block_id`, and bounded string `reported_symptom`. Defaults preserve historical definitions. `editor_layout.positions` stores at most 257 finite bounded `{x,y}` points keyed by existing blocks or `system_start`.
- Requester `SessionStart` and admin `SimulationInput` accept optional `entry_point_key`; omission preserves `entry_block_id`. Clients cannot pass a target block, graph version, facts or policy authority.
- Existing requester offerings project published public entrances as `catalog_items`: `{key,entry_point_key,title,description,category_id,synonyms,scenario_key,version_id,target_block_id}`. Disabled, hidden and unavailable-category entrances are omitted; ordinary forms and legacy guided offerings retain their fallback behavior.
- Session start authorizes the scenario, canonical Service/Offering and selected entrance/category. Owner/version/entrance identifies resumable sessions. Existing JSONB `results._entry_point` pins the server-resolved entrance snapshot, preserved through back navigation. Session responses expose `entry_point`; submission snapshots expose separate `reported_context`. These strings never populate answers, policy facts or verified diagnostics.
- Publication uses the same immutable version definition/hash for graph, entrances and geometry. Every configured entrance, including disabled/hidden ones, participates in graph reachability, positive-resolution protection and canonical readiness/processing validation. Aggregate terminal outcomes retain the existing 512 limit. Outcomes identify `entry_point_key`; incompatible processing reports the entrance path.
- Entrance categories must belong to the selected service. Public enabled entrances require public published category ancestry. Current category visibility is rechecked on loading pinned sessions; graph/entrance content remains pinned when later versions publish.

## Storage

Actual Alembic head verified with `python -m alembic heads` from `server`: **148**. Existing version-definition and session-results JSONB support the additive fields; no migration, historical version rewrite or additional runtime executor is required.

## Verification executed

- Initial new regression RED: `python -m pytest server/tests/test_request_scenario_entries.py -q --tb=short` — six expected missing-contract failures, one bound rejection passed, after correcting the test import.
- Focused evaluator/readiness/submission GREEN: 90 passed; expanded contract/session/catalog selection: 153 passed.
- Latest backend pure surface: `python -m pytest server/tests -k 'request_scenario or request_studio_unified_catalog' -m no_db -q --tb=short` — **205 passed, 1 skipped, 2029 deselected**.
- New pure regressions cover bounded DTOs, legacy defaults, selected starts, every-entrance positive resolution, disabled-entrance readiness, aggregate limits, catalog ACL omission, pinned context on back, symptom/fact separation and publication blocking for required canonical data bypass.
- `git diff --check` — passed.
- `python scripts/verify_workspace.py --workspace .` — failed only the documentation drift gate, pending the parent agent's tracked integration documentation/CODEMAP changes.
- `python -m pytest server/tests/test_request_scenario_entries.py server/tests/test_request_scenario_entries_api.py -q --tb=short` — nine pure checks passed at that stage; isolated API setup could not start the default placeholder SSH test-database tunnel. PostgreSQL acceptance remains unverified in this environment.

## Outstanding integration evidence

Run the new isolated `server/tests/test_request_scenario_entries_api.py` using the approved test database harness. It covers actual catalog/start ACL, per-entrance resume, replacement-version pinning and canonical required-field publication rejection. Run existing scenario session/publication/submission API suites with that harness. No shared or production database has been used, no production services changed, and no actual scenario has been published.

SQLAlchemy 2.0 PostgreSQL JSONB tuple-path `.astext` filtering was checked against matching Context7 documentation before implementing the bounded entrance-resume query. Existing Pydantic 2.12 bounded strict models are reused without dependency changes.

## Parent integration verification

Category archive guards now cover entrance-bound drafts, current versions and usable
pinned sessions, while archived maps release the navigation category. Pure RED/GREEN
regression and API rejection/success lifecycle tests pass. Safe partial admin
simulation retains all reachable edges and strict validation with limited_scope
disclosure; publication and sessions still validate the complete definition.
Latest focused backend:208 passed/1 skipped. Full server no_db:1375 passed/1 skipped
(before the two additional partial simulation regressions).

Isolated Linux current-server-overlay PostgreSQL run:36 passed with fresh migration
to head148; tested entrances API, admin API, session API, publication API, submit
API and unified catalog. Source archive digest
38f934dce69290228de35593c6a781aec51a6d32046ad5e12d574cd709f24fdc.
Temporary role absent and owned databases removed by the harness. An initial new
fixture attempted forbidden immutable-version mutation; it was corrected to insert
replacement snapshots. Failed/interrupted attempts remain separate historical
evidence. No installed service or production mutation occurred.
