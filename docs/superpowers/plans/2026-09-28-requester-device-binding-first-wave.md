# Requester Registration & Device Binding — First Wave Implementation Plan

**Goal:** Execute the supplied First Wave specification across Endpoint and Helpdesk, with Windows staging acceptance.
**Spec:** `C:/Users/admin-2/.codex/attachments/d6a2d1eb-52ee-49dc-8c96-a71177f384e0/pasted-text-1.txt`.
**Execution:** Native, sequential provider then consumer. User supplied the architecture and explicitly requested execution.
**Architecture:** Endpoint authenticates devices and issues/redeems possession challenges. Helpdesk resolves the authenticated RegistryPerson and uses its existing Registry device mapping, binding and ownership review workflow. Account registration remains independent.
**Tech stack:** Existing FastAPI, SQLAlchemy 2/Alembic, PostgreSQL, Pydantic 2, Windows native tray/service, Helpdesk aiohttp/React Query/React Router.

## Baselines and constraints

- Helpdesk starts at bd3090bd72633a83be5e5f83a894ac959306cf74. Preserve the user's unstaged AGENTS.md edit.
- Endpoint remote main on discovery: 0e04ce638193d5758009792c7f4d17f54708991e. Existing clean local staging-origin branch remains recoverable.
- GitNexus helpdesk-platform status: no missing repos, commitsBehind=0, indexStale=false, contractsStale=false on discovery.
- Changes to each repository use its own workspace. No legacy pairing, production deployment, ALT live acceptance, new GUI application or credentials in browser/tray.
- Codes: six ASCII digits, display NNN-NNN, TTL 600 seconds, one active challenge per device/purpose; HMAC using domain-separated existing server pepper; no raw code persistence/logging.
- Authenticated device identity only on create; dedicated service scope on redeem; exact provider commit/OpenAPI digest pinned only after provider stabilization.
- Remote acceptance only on approved staging hosts; stop services and restore fixture/enrollment state afterward.

## Review focus

- Concurrent creation and redemption, including collision retries: DB constraints and PostgreSQL transactions must enforce one active challenge and one winner.
- Anonymous login/profile redirects: retain code only in memory; strip fragment before navigation and do not use durable storage.
- Ambiguous/shared ownership and repeated submissions: reuse conflict queue without replacing ownership or duplicating records.
- Tray security boundary: service owns protected credential; interactive user receives only bounded short-lived challenge over authenticated local IPC.
- Provider verified but Registry commit fails: consumed code cannot be replayed; UI guides safe challenge refresh and never reports an uncommitted binding as success.

## A — Endpoint provider

- [x] Create dedicated branch from accepted remote baseline; inspect device authentication, audit, model/migration and packaged tray source.
- [x] Add `endpoint_contracts/device_binding.py` request/response models; `endpoint_server/db/models/device_binding.py` and migration 0036 (accepted baseline already includes Policy Foundation through 0035). Persist challenge status/digest and serialized rate-limit state.
- [x] Add `endpoint_server/device_binding/service.py` challenge lifecycle using device row locks, unique active indexes, bounded collision retries and domain-separated HMAC. Add route module using existing `_authenticate_device` and `require_service_scope`.
- [x] Test device identity/unauthenticated/arbitrary ID, TTL/revoke/expire/replay, uniform rejection, collisions, scope, bounded projection, no raw persistence/logging and persistent limiter. Verify one concurrent winner with real PostgreSQL.
- [x] Extend existing service-side HTTPS client for challenge creation. Add restricted Windows local IPC and integrate existing runtime/tray, with copy/refresh/open actions and fragment link. Test parsing, redirect denial, expiry, local principal ACL and credential exclusion.
- [ ] Extend canonical OpenAPI and typed artifacts; update canonical docs/CODEMAP. Run Python/unit/API, migrations, contracts, compilation, packaging checks and Windows canary.
- [x] Review complete provider diff, commit atomic changes, publish draft PR A; record SHA, OpenAPI SHA256, migration, package/version.

## B — Helpdesk consumer

- [x] Inspect auth/session capability endpoint, registration tests, RequesterIdentityResolver, RegistryPort/local adapter and current forms policy.
- [x] Remove retired code from `webapp/src/features/auth/register-page.tsx` and API payload; project registration flag through existing safe public/session endpoint, render disabled states on login/register. Keep backend rejection of retired payloads.
- [x] Extend `server/endpoint_adapter/http.py` and `wire.py` with typed redemption; update `integration/endpoint_contract.lock.json` with exact accepted provider SHA/hash and run contract acceptance.
- [x] Add requester binding handler with existing session/CSRF policy; require resolved complete RegistryPerson before redeem. Resolve canonical device mapping; use Registry binding/claim path for free/same-owner/conflicting/shared devices, including bounded audit.
- [x] Add canonical `/app/requester/devices/link` wizard (requester actor, primary job bind computer, secondary help obtaining code/profile). Capture/remove URL fragment immediately; preserve only memory across auth/profile; normalize manual input. Invalidate requester bootstrap/devices/registry after success.
- [x] Update devices empty state/action and Admin Registry owner/requested-owner/source/timeline projections. Correct visible terminology without schema renaming.
- [x] Correct canonical/default form policies to permit no-device tickets; preserve explicit device-required policy. Optional primary-device selector must support explicit no-device, preserving requester identity/routing/SLA/consent.
- [x] Add auth, binding, conflict/idempotency/redaction/cross-user tests, canonical no-device form tests and requester lifecycle regressions. Update canonical documentation.
- [ ] Run Python compilation, no-DB/PostgreSQL/migrations, typecheck/Vitest/Playwright/build, scoped workspace verifier, contract acceptance and exact-SHA canonical CI. Review and publish draft PR B.

## C — Live acceptance and final evidence

- [ ] Approved Windows staging tray → code → browser/login/profile → binding → requester/admin projections.
- [ ] Create tickets with and without device, support/requester messaging and waiting/reply transition, safe consent-controlled diagnostic, resolved → requester-confirmed closed, allowed feedback/reopen.
- [ ] Fixture ownership conflict, invalid/expired/replayed/revoked/throttled/concurrent code cases; inspect only redacted logs/evidence.
- [ ] Restore test state, protected enrollment and stop staging services. Final report explicitly separates automated, real Windows, E2E and CI evidence; no completion claim until the complete chain passes.

## Checkpoint receipts (2026-09-28)

- Provider draft: https://github.com/BorisDruzak/endpoint_platform/pull/37.
  SHA `731f271ad0ba1ba7a134ace45b6bc8771542f688`; migration 0036;
  OpenAPI `e0161970a2f08dcc80fc333676319c2018065743d74f880da160404115b6cdec`.
- MSI 3.2.76 built through the canonical source-bound Windows MSI builder;
  SHA256 `1806841273267058082678ac81c0b63442bc4ac794785d65e3ef2b8a6c233672`.
  This is packaging evidence, not installation or live tray acceptance.
- Frozen provider real PostgreSQL 16 contracts/operations/Gateway/binding/migrations:
  648 passed. Windows suite: 369 passed. GitHub provider CI remains open.
- Helpdesk real PostgreSQL Registry/concurrency/resolver/context: 23 passed.
  Clean-source no-DB export: 893 passed, 1 skipped. Full frontend: 486 passed.
  Playwright requester/binding fixtures: 23 passed at 1366 and 1920 widths.
  Current build, compile, workspace verifier and immutable contract lock passed.
- Ignored legacy pc_agent/dist files in the working copy cause an unrelated
  retired-import guard failure; these user artifacts were preserved. The clean
  Git source export passes the same no-DB suite.
- Provider/consumer reviews found no confirmed blocker after the documented
  corrections. Additional ownership approval and provider-adapter checks remain
  running. Full canonical CI and real Windows acceptance must pass on frozen SHAs.
- Installed staging services, Windows enrollment and real employee ownership
  were not changed. Approved runtime privilege/secret input is still pending.

## Automated gate follow-up (2026-09-28)

- Draft consumer PR: https://github.com/BorisDruzak/helpdesk/pull/38, target
  `codex/helpdesk-process-model`; source before this checkpoint
  `0de166865f002967aabf82c1acd11be25a3432ef`.
- Clean-source no-DB repeat: 895 passed, 1 skipped (800 deselected). Vitest:
  486 passed across 89 files. Complete Playwright fixture suite: 31 passed.
  Fixture results do not establish real Windows acceptance.
- Real PostgreSQL ownership/admin approval: 4 passed. Extended binding API
  covers replay/conflict, explicit no-device and selected bound-device tickets;
  this API plus authorized affected-person context regression: 2 passed.
- Full CI exposed missing capability fixtures, cleanup marker, mapping table
  and fixed table-count expectation. Each was corrected without suppressing
  assertions. Strict model-schema classification and 60 cleanup/harness checks
  pass. GitHub full CI run 36396167011 is pending; contract acceptance has passed
  on earlier consumer candidates, each bound to its exact provider lock.
- Provider candidate `fa6f65ce766a6a4a3c9cd5d82c042f1e1989267e` only adds
  CI bounds/stack diagnostics and test-facade graceful disconnect ordering after
  runtime source 731f271. Bounded run 36395058167 identified a TestClient portal
  shutdown stall in existing WSS identity acceptance. The facade now waits for
  actual ASGI cleanup and asserts persisted closed sessions; production code is
  unchanged. Current contracts: 428 passed; Gateway: 80 passed. Fresh provider
  PR CI 36396495509 and exact-HEAD dispatch 36396880086 remain required. The
  consumer lock now pins fa6f65ce and the unchanged OpenAPI digest; new consumer
  full/contract CI must validate the final source candidate.
- MSI source remains 731f271; package/hash above are unchanged. MSI, sidecar and
  canonical canary/preflight scripts were staged on Windows, not installed.
  Baseline preflight reports the existing 3.2.75 installation with strict TLS;
  it is not 3.2.76 acceptance. Disposable PostgreSQL and the SSH tunnel are stopped.
- Required independent staging deployment and real tray→requester-confirmed
  closure/conflict/restore remain blocked by pending approved Linux privilege
  input. No production or ALT live operations are authorized.
