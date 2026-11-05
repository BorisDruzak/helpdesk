# Service-name search and missing-service intake — 2026-11-05

User scope: search the actual service catalog, add Электронный бюджет and ЕИС,
and allow «Не знаю» when nothing matches. Staging only, preserve existing
publication/draft/ticket history and earlier requester decision controls.

## Observed causes

Before this change the live public catalog had 31 offerings but search indexed only their entrance
texts when entrances existed. «электронная подпись» therefore found only an ЕСЭД
problem and missed the signature service itself. Электронный бюджет and ЕИС did
not exist. The advertised fallback was retired `other.unknown`, absent from the
current offering list, so the UI could not show its fallback button.

## Changes and checks

Search emits additive service rows for public offering/section names, retaining
entrance ranking and bounds. Selecting a service browses its problems without
starting a remembered scenario. Explicit configured fallback metadata resolves
only to one public executable entrance under a real public parent. The UI offers
«Не знаю / моей услуги нет в списке» with that exact entrance key.

The new guarded publication helper builds two maps from the current published
information-system intake, inheriting routing, SLA and policy refs. Each has
login/signature/system-error entrances; the existing Other `not_found` entrance
becomes fallback. Publication uses canonical audited services, sorted service
locks before source freeze, an admin/actor check and a fresh source fingerprint.

The empty hint advertises «Не знаю» only when the caller exposes that fallback.
Incomplete-profile restrictions remain intact; the restricted admin browser
session cannot access ordinary services or the fallback until profile setup.

## Verification and staging acceptance

- `python -m pytest server/tests/test_service_catalog_search.py server/tests/test_service_catalog_contract_no_db.py scripts/test_helpdesk_catalog_service_search.py -q`: 26 passed; existing Authlib deprecation warning.
- `pnpm --dir webapp test src/features/requester/catalog-search.test.tsx src/features/requester/scenario-entrances.test.tsx src/pages/requester/new-request-page.test.tsx`: 33 passed, including unavailable-fallback regression (observed red before fix).
- `pnpm --dir webapp build`: passed.
- `python scripts/verify_workspace.py`: passed.
- `PC_CLIENT_WEBAPP_E2E_PORT=4189 pnpm --dir webapp test:e2e tests/catalog-service-search.spec.ts --output=../tmp/catalog-service-search-20261105/browser-final`: 3 passed at 1366x768, 1920x1080 and 390x844. Fixture-backed browser checks cover service expansion, remembered-entry isolation, explicit problem selection, EIS results, unknown-service fallback and no ticket submission/overflow/console errors.
- Private-index `git diff --cached --check`: passed. Independent review found lock-order and hidden-parent issues; both fixed with regressions, followup found no actionable findings.

Code commits on private branch `codex/catalog-service-search`:

- `17223df1429592dc3bff7e82b72dc6f6fbdee0f0` — `fix(catalog): search service names and expose current fallback` (18 files: backend search/runtime/tests, guarded publication script/tests, requester search/types/page/entrance behavior/tests, browser spec, catalog/CODEMAP/UX docs and PLANS).
- `f85af9310468780cf87768671043a1e0409684bd` — `fix(catalog): align empty hint with fallback availability` (catalog-search component and test only).

The canonical immutable installer targets isolated staging only. Database schema
remains 155. Verified backups precede code installation and data publication;
latest backup SHA256 is `9b5e6f3988ddb373c096a33a0386bb9a2c2d36173e8f9173373c87a458665a8c`.
Final runtime is `f85af9310468780cf87768671043a1e0409684bd`; all 13 source/test
hashes match committed files. Helpdesk and Endpoint HTTPS health return 200 and
all three staging services are active. Fresh live-browser empty-state verification
passes with no warning/error console entries (`live-profile-guard.jpg`).

Canonical audited publication added 2 maps with 3 entrances each and configured
the existing Other `not_found` entrance. Public offerings increased from 31 to
33; versions 74 to 76 and drafts 54 to 56. Fingerprints of every existing version,
draft and ticket remained unchanged. Repeated apply made no changes or duplicates.
Tickets remain 76; events 18218, artifacts 6, users 160 and people 44 unchanged.

Real staging HTTP search confirms first service results for «электронный бюджет»,
«ЕИС» and «электронная подпись», problem matches for «ЭБ» and «еис закупки», empty
results for an unknown service and the actual executable fallback offering/entry.
The live admin browser confirms profile gating; full ordinary-requester behavior
was tested with browser fixtures and the real public catalog API, rather than
changing an employee's profile or creating a ticket.

GitNexus architecture and source checks keep this change inside Helpdesk; no
Endpoint consumer contract or provider API changed. Additive search `result_kind`
and fallback `entry_point_key` are documented. No dependency or schema migration.
Full CI, fault-injected concurrent publication and production deployment were
not performed. Staging remains active for the requested feature.

Private evidence: `tmp/catalog-service-search-20261105`. The source working copy
contains earlier committed requester-control changes from another branch; freeze
this task on top of `1a341d05dcd8b89b10891d3ad8447e59ec865efe` with a private index
so those installed controls and unrelated shared staging are preserved.
