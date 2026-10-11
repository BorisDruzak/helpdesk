# Guided Request Studio v2 execution ledger

Plan: [canonical specification and P0–P10](2026-10-11-guided-request-studio-v2.md).
Specification commit: `507ee7154b947391d51148d3a8929b77983eb77e`.
Implementation branch: `codex/guided-request-studio-v2`.
Production deployment, live scenario publication and Endpoint execution are excluded.

## P0 dependency matrix (source-verified)

| Boundary | Existing authority | v2 integration / verification |
|---|---|---|
| Catalog identifiers | `HelpdeskService`, `HelpdeskServiceOffering`, `ServiceCatalogRepo` | Keep `service_code`, `offering_full_code`, template and form references. Categories are navigation only. Never duplicate offerings. |
| Requester visibility | `ServiceCatalogRuntimeResolver.resolve_selection`, `_is_visible` | Published public service AND offering for user; category visibility must intersect this. Recheck on session start and mutations. |
| Form validation / snapshots | `resolve_create_form_submission`, registry pack projection, `validate_form_submission` | Reuse canonical normalization before preview/create; hidden stale answers removed. Existing `field_roles` supports lists; Studio's single `processMeaning` needs replacement. |
| Ticket preview | requester ticket preview handler, `form_process_preview`, `service_catalog_preview` | Safe result projection; existing policies remain authoritative. Simulator must not call create or diagnostic dispatch. |
| Ticket creation / idempotence | requester create handler, `RequesterCreateLedger`, migration 144 | Actor-scoped durable key and payload hash; reservation and ticket binding in transaction. Session submission must reuse this boundary, not add a ticket engine. |
| Priority / route / SLA / OLA | existing priority, routing, SLA and OLA services | Scenario roles map validated answers to facts. No client actor/queue/SLA overrides. |
| Approval / closure / notifications | existing effective template policy bundle and create/lifecycle flow | Readiness validates actual policy dependencies; scenario completion cannot change ticket lifecycle. |
| Publication | `RequestStudioPublicationService`, DTO `request_studio.py`, publish token table | Preserve old routes/DTOs. Extend full canonical hash binding, one-use token, atomic version/active pointer and revalidation. |
| Authentication | `AuthContext`, `require_auth`, requester identity resolver | User/session owner from authenticated context; auditor reads only. Current legacy preview can issue a token to auditor, but auditor cannot publish. New draft mutations remain admin-only. |
| Diagnostics | documented support ticket Endpoint facade | No pre-ticket dispatch contract. v2 diagnostic always unavailable with fallback; simulation explicitly labeled. |
| Persistence | SQLAlchemy models, Alembic head 146 | New migration starts after 146. Additive tables/FKs/indexes with PostgreSQL verification. Revision 144 is forward-only: do not rewrite historical migration or assume whole-schema downgrade works. |
| Studio frontend | Studio page, `draft-model.ts`, existing editor/shell/api | Five-step wizard; selected block/field only; local disclosures. No new raw JSON workflow. |
| Requester frontend | `new-request-page`, `dynamic-form`, requester API types | Per-offering opt-in, owner-scoped server session; legacy `/help` and form-only clients retain their contracts. |

GitNexus query/context/impact was used before manual source exploration. Publication
impact identified `request_studio_handlers.py` and `routes.py`; this is not evidence
that dynamic create/policy relationships are absent. The rows above were checked
against source. No group sync, reindex or Endpoint operation was performed.
`list_repos` reports Helpdesk indexed commit
`92a4ba89e7914f380efefa6b91759e79a9cd9267` on the historical process-model branch,
so graph results are baseline hints, not verification of the current specification
commit or local diff. Important relationships were independently checked in source.

## Pre-flight shared interfaces

| Producer → consumer | Required agreement |
|---|---|
| P1 → P2/P3/P6/P8 | Strict schema v1, stable block IDs, typed `current_result`, revision/version identifiers, bounded condition AST. Design JSON is illustrative, not an existing API. |
| P2 → P5/P6/P8 | One server evaluator for preview/runtime; typed branch ordering, explicit fallback, DAG and downstream invalidation. No separate browser evaluator. |
| P3 → P4/P5 | Typed catalog/detail/draft DTO; optimistic revision conflicts; user-friendly pickers use existing offering IDs. |
| P6 → P7 | Pinned session, validated visible answers, authenticated owner, expected block/revision, transaction and idempotency binding. |
| P7 → P8/P10 | Canonical create/preview/policy boundary, legacy compatibility and PostgreSQL receipt. |
| P8 → P10 | Readiness differs from Policy Health; full payload hash, one-use token and immutable publication. |

Ruling: use the canonical checkout with a separate feature branch because root
AGENTS scopes work to this checkout. Preserve all unrelated scanner/Sonar files.
No main merge or push is implied by this decision.

## Evidence and current gate

- Initial local main: `ee0dea2b56d78c5a55347885846c00fd13f9e872`.
- `git fetch origin` recovered the requested specification commit; branch starts
  at that exact commit, without changing local main.
- UTF-8 bootstrap and root/server/webapp AGENTS were read.
- Installed dependencies: Pydantic 2.12.5, SQLAlchemy 2.0.51. Context7 confirmed
  discriminated unions and strict/extra-forbid configuration; the installed version
  remains authoritative where documentation is from a newer branch.
- `python -m pytest server/tests/test_request_scenario_contract.py -q --tb=short`:
  **Initial RED: 10 failed, 2 passed**. New typed scenario/session DTO module is absent;
  legacy payload roundtrip and rejection of a silently added scenario passed.
  DTO tests must turn green in P1; HTTP auth tests belong to P6. Do not mark
  this branch release-ready or hide these failures with xfail/skip.
- First existing Studio API baseline attempt: **5 setup errors**, test PostgreSQL
  tunnel settings absent. No application assertions executed.
- Approved staging SSH access verified. Read-only discovery confirmed a separate
  CREATEDB test role. Baseline rerun uses the existing harness with runtime-only
  staging target and SSH key, isolated `pc_support_test_*` database, and an owned
  loopback tunnel. No application database or deployment is changed.
- Independent P0 review identified a potential false-positive in authority
  rejection tests. Corrected with valid baseline input, realistic authority values
  and an explicit `extra_forbidden`/field location assertion. Added anonymous,
  auditor and support rejection tests at the future requester handler boundary.
  Owner/visibility/version/persistence tests remain required in P3/P6/P8; a DTO
  rejection alone is not ownership proof.
- Revised `python -m pytest server/tests/test_request_scenario_contract.py -q --tb=line`:
  **RED: 13 failed, 2 passed** due to absent new DTO/handler modules. No skip/xfail.
- Existing no-DB catalog/idempotency/process preview baseline: **22 passed,
  2 deselected** (explicit `-m no_db`); no PostgreSQL acceptance inferred.
- Existing frontend Studio/dynamic form baseline: **5 files, 74 tests passed**.
- `python scripts/verify_workspace.py --workspace .`: **PASS**. `git diff --check`: **PASS**.
- First PostgreSQL rerun lacked progress output at Alembic; PostgreSQL showed one isolated test
  transaction waiting for the client for over five minutes. Own test process was
  interrupted. No root cause proven yet. Diagnostic rerun uses a separate owned
  loopback tunnel, watchdog=30s and pytest faulthandler=45s (stack observations,
  not forced termination). It advances through migrations; do not describe it
  as a proven permanent hang. Diagnostic rerun completed: **5 passed in 648.60s**,
  migration head **146**. Preview/diff/publication/token rejection/auditor denial and
  public form/catalog projection passed on isolated PostgreSQL.
- Harness dropped the successful run's database and owned tunnel. Used the same
  validated harness cleanup helper for the interrupted run's sole leftover DB,
  restricted to the two owned run PIDs. Both owned local tunnel ports have no
  listener. Existing test role was not created by this task and was not removed.
- Independent review of corrected P0 tests/ledger: no remaining findings. Reviewer
  checked source and claims; it did not independently rerun the test commands.
- `python scripts/audit_test_inventory.py --workspace . --paths server/tests/test_request_scenario_contract.py --strict`:
  **PASS**, one no-DB test file, zero issues.

Commands for the existing baseline:

```powershell
python -m pytest server/tests/test_service_catalog_contract_no_db.py server/tests/test_requester_create_idempotency_no_db.py server/tests/test_form_process_preview.py server/tests/test_service_catalog_preview.py -m no_db -q --tb=short
pnpm --dir webapp test src/features/request-template-studio/draft-model.test.ts src/features/request-template-studio/readiness.test.ts src/features/request-template-studio/studio-model.test.ts src/pages/admin/request-template-studio-page.test.tsx src/features/requester/dynamic-form/dynamic-form.test.tsx
python -m pytest server/tests/test_request_studio_api.py -x -vv -s -o faulthandler_timeout=45
```

PostgreSQL runtime settings are scoped to the approved staging target; no credentials
are recorded here. Frontend toolchain bootstrapped with the existing project script.

## Stage matrix

| Stage | State |
|---|---|
| P0 | PASS: architecture/source matrix, intended RED, existing PostgreSQL/no-DB/frontend baseline, independent review, cleanup |
| P1 | PASS: typed domain/TS contract, additive persistence, PostgreSQL/rollback, independent review; commit below in Git history |
| P2–P10 | Not started; gated by predecessor |

## Acceptance matrix

| Criteria | State / required evidence |
|---|---|
| AC01–AC05 | Pending P4/P5 + browser evidence |
| AC06–AC07 | Pending P1/P2/P6 validated conditions and process roles |
| AC08–AC09 | Pending P2/P6/P9 self-resolution and diagnostic fallback |
| AC10–AC12 | Pending P7 policies, side-effect-free preview, durable single create |
| AC13 | Pending P3/P6/P8 RBAC, owner scope, revision/version tests |
| AC14–AC15 | Pending P8 readiness and publication safety |
| AC16 | Legacy DTO baseline: 2 passed; full API/form/help compatibility pending |
| AC17–AC18 | Pending P10 pilot A–J and required browser sizes/accessibility |
| AC19 | Pending migrations, frontend/backend/E2E and canonical CI/security gates |
| AC20 | Respected so far: no production deployment/publication |

No new routes exist yet. Migration 147 and domain/storage CODEMAP entries are
implemented in P1; PostgreSQL storage acceptance has passed. Browser and canonical CI signoff
are pending, not replaced by source review or unit tests.

## P1 evidence (PASS)

- P0 commit: `ef5b1db21e0693b8d5edacd8997f127704b7fbf6`
  (`test(studio): record P0 baseline and scenario contract gaps`).
- Extended DTO contract tests: RED **35 failed, 2 passed, 3 deselected** before
  implementation; GREEN **37 passed, 3 deselected** with
  `python -m pytest server/tests/test_request_scenario_contract.py -k "not requester_session_read" -q --tb=short`.
  Three requester handler tests remain intentionally RED until P6; no release
  readiness claim or skip/xfail is added.
- Metadata registration test: RED **1 failed, 4 deselected** before models;
  GREEN **1 passed, 4 deselected** after registration. Additional DB constraints
  and bounded 147 → 146 → 147 rollback tests have been added.
- `pnpm --dir webapp exec tsc --noEmit`: **PASS**.
- `python scripts/audit_test_inventory.py --workspace . --paths server/tests/test_request_scenario_contract.py server/tests/test_request_scenario_persistence.py --strict`: **PASS**, zero issues.
- Initial PostgreSQL migration/persistence: **5 passed in 627.87s**, fresh migration
  through 147. Expanded persistence (9) and actual migrated cleanup schema (1):
  **10 passed in 792.70s**. Uses the existing scoped harness
  and approved staging target, with a retained test template for later stage
  tests. The task-owned template must be cleaned at final acceptance.
- Existing catalog audit schema supports scenario/category object types without
  a schema change; atomic application audit writes are required in P3/P8.
- Final DTO/metadata selection after separating no-DB and persistence files:
  **38 passed, 3 deselected**. Inventory now owns persistence in the canonical
  DB/API catch-all suite and contract tests in the no-DB suite.
- Independent P1 review found reset omitted sessions. Regression RED:
  **1 failed, 2 deselected**; added sessions to `EXPLICIT_CLEAR_TABLES`, reset
  regression suite GREEN: **3 passed**. Configuration remains preserved.
- Model-based cleanup schema audit: **PASS**, all nine risk counters zero.
  Cleanup profile audit: **PASS**, 269 files, zero missing profiles.
  Scoped workspace verification and diff whitespace check: **PASS**.
- Independent review also identified nullable condition-source wire drift.
  Frontend `satisfies ScenarioCondition` regression reproduced **TS2322 RED**;
  aligned TS `field?: null` with standard Pydantic JSON projection. Backend
  roundtrip/contract + reset selection: **42 passed, 3 deselected**; frontend
  typecheck **PASS**, wire regression **1 passed**.
- Concurrency test no longer introduces artificial row locks or treats a
  deadlock/timeout as validation success; only SQLSTATE 23514 is accepted.
  Wrong scenario/offering version uses retired state to avoid masking a missing
  FK with the active-version unique index; all three composite FK cases require
  SQLSTATE 23503. Separate rerun of these corrected tests:
  **2 passed in 65.28s**. This receipt supersedes their original expanded-run
  variants for the relevant concurrency/FK acceptance claims.
- Actual 147 → 146 → 147 rollback retained the synthetic legacy service row and
  removed/recreated exactly the five additive tables. Fresh migration reached
  147; actual schema/model/cleanup classification audit passed.
- Owned run databases and tunnels were dropped/closed on test exit; templates
  are intentionally retained until final stage cleanup. No staging application
  database, service, production runtime or Endpoint operation was changed.
- Independent final P1 review: no remaining blocking findings after correcting
  all four reported issues. Reviewer inspected source/claims; it did not rerun
  PostgreSQL or frontend tests itself. P2 graph/runtime, P3 audit APIs, P6 auth,
  P8 publication, browser/CI/security gates remain mandatory and unverified.

P1 changed files: `server/web_api/dto/request_scenario.py`,
`server/app/db/request_scenario_models.py`, `server/app/db/models.py`, migration
`20261011_147_guided_request_scenarios.py`, server contract/persistence tests,
`server/tests/conftest.py`, `scripts/reset_test_data.py` and its regression test,
`quality/db_table_classification.toml`, frontend `scenario-contract.ts` and its
wire test, `server/docs/GUIDED_REQUEST_SCENARIOS.md`, `server/docs/CODEMAP.md`,
`PLANS.md` and this ledger. No HTTP route or running application was added.

## P2 evidence (PASS)

- P1 commit: `651b6e54f649961919df02b759a7be2ce88c9659`
  (`feat(studio): add versioned scenario domain and persistence`).
- Runtime safety initial RED: **32 failed** (missing modules), then GREEN
  **32 passed**. Covers invalid graphs, strict values, visible/hidden required
  fields, Back cleanup, revision conflicts, explicit self-service completion,
  unavailable diagnostics and 60 seeded DAG executions.
- Additional RED/GREEN regressions: 1200-field dependency chain (recursion),
  overlapping multi-select branches, oversized integers (OverflowError), finite
  floats normalized into unsafe integers (**2 failed**), and resolution coverage
  depending on an absent answer (**1 failed**, independent review finding).
  Iterative traversal, conservative overlap/coverage and bounded numeric guards
  correct these cases.
- `python -m pytest server/tests/test_request_scenario_runtime.py
  server/tests/test_request_scenario_contract.py scripts/tests/test_reset_test_data_script.py
  -q -k 'not requester_session_read'`: **80 passed, 3 deselected**. Three original
  HTTP owner/auth checks remain RED until P6 without skip/xfail.
- `python -m pytest server/tests/test_form_process_preview.py
  server/tests/test_form_business_validation.py -m no_db -q`: **18 passed**.
- `pnpm --dir webapp exec tsc --noEmit`: **PASS**;
  `pnpm --dir webapp test src/features/request-template-studio`: **21 passed,
  5 files**. Transition priority mirrors the TS wire contract.
- Runtime inventory: **1 file, zero issues**, canonical no-DB suite. Workspace
  verifier initially required docs updates; its final rerun follows CODEMAP/domain
  documentation updates. No migration or browser surface changed in P2.
- Independent review reproduced coverage failure, reviewed corrections and found
  no remaining blockers; it ran diff whitespace validation, not the full suite.
- Changed: three pure `tickets/request_scenario_*` modules, runtime test,
  DTO/TS transition priority, domain docs, CODEMAP, PLANS and ledger. No HTTP
  route, actual ticket/Endpoint operation, deployment or publication.

## P3 evidence (PASS)

- P2 commit: `8733dccb0409e1b0a58ddaf2d09be42a7485514a`
  (`feat(studio): validate and execute deterministic scenario graphs`).
- Initial PostgreSQL HTTP RED: **12 failed in 312.61s**; absent routes returned
  404 for CRUD, RBAC and catalog operations. Six auditor mutation probes initially
  used separate cases; the final suite batches the same six probes in one test
  to avoid repeated full cleanup/app setup without reducing coverage.
- First implementation run: **3 failed, 11 passed in 411.11s**. Category UPDATE,
  draft UPDATE and the concurrent-save test returned 500. Independent review
  confirmed SQLAlchemy 2.0.51 `onupdate=func.now()` expires updated_at after UPDATE
  with eager_defaults=auto; synchronous audit/JSON projection then performs
  implicit IO. Explicit awaited refresh now resolves both scenario/draft and
  category timestamps before projection. Corrected PostgreSQL rerun passed.
- Independent review also found string query offset/limit rejected by strict
  DTO parsing. Fast handler-boundary regression RED **1 failed, 9 passed**;
  `model_validate_strings` fixes HTTP query conversion while retaining bounds.
  Admin boundary suite before final filter regression: **11 passed**, including unknown/bounded query
  inputs, strict revisions, streamed/chunked valid body and 1 MiB rejection.
- Error-filter regression RED **1 failed, 11 deselected**: a published scenario's
  invalid new draft was excluded. Filter now includes all non-archived drafts with
  issues, preserving published status. Final combined boundary suite:
  **92 passed, 3 deselected** (admin boundary 12);
  requester HTTP auth remains P6 RED. Test inventory **2 files, zero issues**.
- Cleanup classification audit: all nine risk counters zero; profiles audit:
  **272 files, zero missing profiles**. Scoped workspace and diff checks pass.
- `python -m pytest server/tests/test_request_scenario_admin_api.py
  server/tests/test_request_studio_api.py -q -x --tb=short`: **14 passed in 418.56s**
  (9 new API acceptance tests + 5 existing Studio regression tests). Covers actual
  category updates/tree conflicts/audit, copy/move/reload, auth/RBAC, query bounds,
  immutable binding/authority rejection, simulator no draft mutation, optimistic
  edits, exactly one concurrent-save winner and rollback on audit failure.
- Independent final source review: no remaining concrete blockers, including
  the filter correction. Reviewer did not rerun PostgreSQL; the command above is
  the runtime receipt. Own per-run database/tunnel closed on successful exit;
  retained task templates remain for subsequent stages and final cleanup.
- New API/docs impact: admin/auditor read and pure simulation, admin-only
  category/scenario mutations, immutable catalog binding, draft revision and
  same-transaction catalog audit. Existing Studio endpoints remain unchanged.
  No publication/enablement/requester route, migration, running deployment or
  Endpoint dispatch is added. Version history is read-only until P8 publication.
- Changed files: scenario repo, admin handlers/DTO, routes, two admin test files,
  CODEMAP, GUIDED_REQUEST_SCENARIOS, SERVICE_CATALOG, REQUEST_FORM_BUILDER,
  PLANS and this ledger. Browser/typecheck are not repeated for this pure backend
  stage; P2 frontend receipts remain applicable. Browser/CI gates still pending.

## P4 — catalog-first React wizard evidence (PASS)

- P3 commit: `84dc6be2a6a4ec370868cad386296c5df84d3c45`
  (`feat(studio): add audited scenario catalog and draft APIs`).
- Initial catalog/component RED: **4 failed** against the former page (9.29s),
  which lacked the default catalog/primary create/CAS wizard/readonly flow.
  Category-before-pagination RED: **1 failed** (unsupported filter); legacy
  offering inventory RED: **1 failed** (total zero). Deep-link compatibility RED:
  **1 failed** (no offering-purpose editor). These regressions now pass.
- `pnpm --dir webapp test src/pages/admin/request-template-studio-page.test.tsx
  src/pages/admin/request-template-studio-catalog.test.tsx
  src/features/request-template-studio`: **39 passed, 8 files**. Existing pure
  legacy feature contracts remain tested. The former 9 page tests for the global
  modes/giant policy workbench were replaced by the approved catalog/wizard
  interaction checks rather than skipped/xfail. Publication UI is the P8 gate.
- `python -m pytest server/tests/test_request_scenario_admin_contract.py
  server/tests/test_request_scenario_contract.py server/tests/test_request_scenario_runtime.py
  scripts/tests/test_reset_test_data_script.py -q -k 'not requester_session_read'`:
  **94 passed, 3 deselected**. Original requester/auth RED remains P6 work.
- Isolated PostgreSQL command: `python -m pytest
  server/tests/test_request_scenario_admin_api.py -k
  'scenario_draft_cas_simulation_archive_and_version_reads or catalog_read_auth_and_not_found'
  -q -x --tb=short`: **2 passed, 7 deselected in 79.81s**. Actual HTTP checks
  cover legacy offering before scenario creation, no duplicate afterward,
  category filter with limit=1, auth/query bounds, reload/CAS, simulation and
  archive. P3's other backend/legacy API receipts remain unchanged. Per-run DB
  and tunnel closed; retained task templates still await final cleanup.
- `pnpm --dir webapp build`: **PASS**, including TypeScript. Existing common
  bundle >500 KiB warning remains; no new dependency or threshold change.
- Real browser command: `PC_CLIENT_WEBAPP_E2E_PORT=4188 pnpm --dir webapp
  test:e2e guided-studio.spec.ts`: **3 passed in 12.1s**. 1366×768 and 1920×1080
  catalog/wizard, inline settings, current step only, primary visibility after
  scroll, no horizontal document overflow and cancelled sidebar navigation.
  Separate loading/empty/error/retry browser case intentionally returns catalog
  500, verifies recovery and permits only those expected failures. Normal flows
  have no console/page errors or failed network requests. Browser MCP returned
  Transport closed; the documented project Playwright/fixture server was used.
  Screenshots were inspected under `webapp/test-results/guided-studio-*`.
  A retained local copy is in the ignored
  `artifacts/browser_checks/guided-request-studio-v2/p4/` directory, outside
  Playwright's replaceable test-results output. Owned browser/DB test ports have
  zero remaining listeners after validation.
  These are fixture UI receipts; actual staging pilot A–J remains P10.
- Review corrected four concrete findings: legacy forms missing from catalog;
  unsaved changes lost on router/unload; incomplete page mistaken for an absent
  offering scenario; cancelled pending open left loading stuck. Final independent
  read-only review found no remaining blockers in those corrections. Regression
  tests retain local edits and ignore stale async responses. The wizard key stays
  stable while editing its technical key; steps require a saved valid binding.
- Visual inspection also found CSS sticky trapped by the shell overflow boundary.
  The small action-bar portal keeps save available outside that boundary, with
  browser verification. Context7 checked TanStack Query v5 cache mutation and
  React 19 portal context/cleanup; pinned repository versions remain authoritative.
- GitNexus query/impact used the committed baseline. Exact page-symbol impact
  returned zero indexed dependents; source inspection still verified its lazy
  route and Forms/Service Catalog/Policy Health deep links, preserving their
  context. No cross-repository API contract or Endpoint behavior changed.
- Test inventory: **2 files, zero issues**. Scoped workspace verifier and
  `git diff --check`: **PASS** after docs updates. No schema/migration change.
  Changed surface: page/tests, scenario API/catalog/purpose/category/wizard,
  editor/context/dirty/action-bar components, Playwright spec, catalog query/repo
  and admin tests, CODEMAP/domain/admin guide/PLANS/ledger. No deployment or live
  publication. P5 block editing, P6/P7 requester/ticket flow and P8 publication
  are next gates, with P9/P10 still required for the full goal.

## P5 PASS — block workbench

- Wizard step 2 now has an explorer, one selected block editor and optional
  selected-step preview. Palette insertion focuses the new title; drag/drop and
  keyboard buttons reorder without rewriting explicit transitions. Copy generates
  fresh block/field/fact identifiers and remaps copied local conditions. Removal
  displays incoming routes/entry and requires reassignment; externally referenced
  answers block deletion. Undo/redo keeps at most 100 local snapshots.
- Form pages support single/group/section layouts and one selected question
  editor. Local disclosures contain typed conditions, compatible multiple roles,
  validation, aliases, facts and dependency uses. Source/target pickers use titles;
  field sources are limited to current/upstream pages. Option labels and stable
  values are separate. File type is unavailable; diagnostics cannot execute.
- Model/component suites first failed on missing implementation modules (RED),
  then passed. Final command `pnpm --dir webapp test
  src/pages/admin/request-template-studio-page.test.tsx
  src/pages/admin/request-template-studio-catalog.test.tsx
  src/features/request-template-studio`: **59 passed in 12 files**. Covers safe
  graph operations, multiple roles, selected-only editors, focus, undo/redo,
  readonly controls, exact result/operator domains, separator typing and numeric
  wire safety, plus all P4 catalog/CAS/conflict/navigation regressions.
- Fast server regression command from P4: **94 passed, 3 deselected in 1.16s**.
  The three requester-session auth RED tests remain the explicit P6 gate;
  no skip/xfail was added. P5 changes no backend route, schema or DB operation;
  PostgreSQL P3/P4 receipts carry forward without an artificial repeated DB run.
- `pnpm --dir webapp build`: **PASS**, TypeScript and production bundle. Existing
  common chunk >500 KiB warning remains; no dependency/threshold change.
- Independent read-only review found and corrected two blockers: separator loss
  during ordinary membership/alias typing and incompatible operators/results.
  Incremental typing retains raw separators while emitting parsed canonical
  values; enum/boolean membership uses typed checkboxes. Exact block result domains
  and numeric/multiselect operator restrictions preserve invalid saved conditions
  with an explicit warning. Final source review has no remaining blockers.
- Visual inspection caught overlapping breakpoint rules that moved wide preview
  below the editor. Non-overlapping media rules and browser geometry assertions
  now require the third column right of the editor at the same Y. Partial header
  overlap also obscured Save; a genuine failing regression was fixed with full
  anchor visibility observation. Browser checks require the complete primary
  action inside the viewport and below the shell header.
- Final browser command `PC_CLIENT_WEBAPP_E2E_PORT=4188 pnpm --dir webapp
  test:e2e guided-studio.spec.ts`: **7 passed in 22.7s**, including builder
  at 1366×768, 1440×900, 1920×1080 and 820×1180. Checks include ordinary alias
  typing, enum membership, keyboard move, correct preview columns/drawer,
  full Save visibility, save/reload persistence and no horizontal overflow.
  Normal flows have zero console/page/network errors; the separate retry case
  permits only its intentional catalog 500. Screenshots are retained in the
  ignored `artifacts/browser_checks/guided-request-studio-v2/p5/` directory.
  These are fixture API/UI checks, not actual staging acceptance (P10).
- Test inventory: **2 existing server files, zero issues**. Scoped workspace
  verification and `git diff --check` passed. GitNexus query preceded narrow
  source inspection; no external contract/Endpoint behavior changed. No live
  publication or deployment. P6 requester sessions, P7 real ticket/policy binding,
  P8 readiness/publication and P9 compatibility/import remain required.

## P6 PASS — requester sessions

- Added owner-only strict commands, 24-hour TTL, locked revision checks,
  immutable version pinning, safe current-step/review projection and last-command
  replay. Start resumes the same active owner/version. Retired versions remain
  pinned; expired/revoked sessions cannot execute. Canonical runtime handles Back
  pruning and unavailable diagnostics; no ticket or Endpoint side effects.
- Genuine RED: three missing requester auth handler tests; six missing session
  DTO/projection cases; missing runtime preview; missing review answer projection;
  missing public offering flag; UI missing module, late owner response and null
  restoration. Each received implementation and focused GREEN evidence.
- Final fast backend command: `python -m pytest
  server/tests/test_request_scenario_session_contract.py
  server/tests/test_request_scenario_admin_contract.py
  server/tests/test_request_scenario_contract.py
  server/tests/test_request_scenario_runtime.py
  scripts/tests/test_reset_test_data_script.py -q`: **106 passed in 1.21s**.
  The original three requester-auth RED tests now pass without deselection.
- Final frontend command: `pnpm --dir webapp test
  src/features/requester/scenario-session.test.tsx
  src/pages/requester/new-request-page.test.tsx`: **24 passed in 3.66s**,
  including all 16 legacy requester page tests. Covers owner response races,
  explicit unknown, preview ordering, stale-handle recovery, instruction consent,
  typed commands and human review labels. `pnpm --dir webapp build`: **PASS**
  (TypeScript/Vite; existing common chunk >500 KiB warning remains).
- PostgreSQL sessions plus existing catalog fallback: **5 passed in 161.14s**.
  Final session suite after picker/audit/display additions:
  `python -m pytest server/tests/test_request_scenario_session_api.py -q`:
  **3 passed in 105.50s**. A fixture initially omitted required device protocol
  metadata; corrected fixture then passed. New forced audit failure/rollback case
  in `-k owner_resume`: **1 passed, 2 deselected in 47.68s**. Checks owner 404,
  start resume, concurrent identical replay, changed stale 409, invalid required,
  Back, retired version pinning, TTL, same-page preview without save, instruction
  acknowledgment, unavailable diagnostic, self-service finish replay, owned
  device/department choices, forged ID rejection, safe display and audit rollback.
- Browser first exposed restoration before catalog arrival; restore now waits
  for catalog loading. Final `PC_CLIENT_WEBAPP_E2E_PORT=4188 pnpm --dir webapp
  test:e2e guided-requester.spec.ts`: **4 passed in 11.4s**,
  including reload/resume, instruction acknowledgment, resolution/self-service,
  focus, full primary action visibility, no overflow or normal console/network
  errors. These are fixture checks, not P10 staging acceptance.
- Independent review corrections: owner lifecycle cancellation,
  explicit-null preservation, stale-handle restart, supported picker sources and
  server identifier validation, preview ordering and human summary labels. Final
  bounded read-only review has no blockers. Owner-authorized review API retains
  typed `value` alongside `display_value`; UI displays the human label only.
- Inventory audit: two new files, zero issues. Scoped workspace and diff checks
  pass. Seven requester routes are documented in CODEMAP/admin guide. Responses
  use no-store. Ports 4188/55438 have no remaining listener; temporary test DBs
  were dropped by the harness. Screenshots are preserved under ignored
  `artifacts/browser_checks/guided-request-studio-v2/p6/`. No live publication,
  deployment, ticket creation or Endpoint execution. P7–P10 remain required.

## P7 PASS — canonical ticket submission

- Revalidated visited visible answers become trusted mapped facts/roles and a
  human support snapshot. Existing requester preview/create helpers retain
  canonical profile/device/form, priority/routing/SLA/OLA/approval/closure gates.
  Session lock, ticket initialization, requester create ledger and redacted audit
  share one transaction. Repeated/concurrent submit returns one linked ticket.
- Genuine RED covered missing trusted submission/DTO, numeric confirmation
  coercion, missing selected-device context and missing UI preview/submit.
  Each passed after its implementation. Initial PostgreSQL failures were test
  fixture defects: catalog snapshot shape, invalid standard continuity enum and
  inline approval configuration instead of a published policy reference. They
  were corrected without weakening the canonical processing services.
- Final fast backend run across submission/session/admin/graph/runtime and
  requester create/identity/atomicity/form regressions: **217 passed in 1.92s**.
  Frontend `pnpm --dir webapp test src/features/requester/scenario-session.test.tsx
  src/pages/requester/new-request-page.test.tsx`: **28 passed in 4.31s**.
  `pnpm --dir webapp build`: **PASS**; existing common chunk warning remains.
- `python -m pytest server/tests/test_request_scenario_submit_api.py -q`:
  **3 passed in 148.71s**. Actual mapped facts select P2 and a conditional queue,
  initialize SLA/OLA deadlines, require approval and retain the closure policy.
  Forced audit failure rolls back ticket, ledger and session; retry succeeds.
- Final PostgreSQL regression: concurrent submit/snapshot/owner/device case,
  requester catalog form create/preview, no-device create/preview, actor-scoped
  HTTP replay, initialization rollback/retry, old form payload, standalone
  registry public creation and default catalog fallback:
  **9 passed in 291.08s**. No skips or expected failures added.
- After rebuilding the served bundle, `PC_CLIENT_WEBAPP_E2E_PORT=4188 pnpm
  --dir webapp test:e2e guided-requester.spec.ts`: **8 passed in 21.0s**.
  Both self-service and ticket flows pass at 1366, 1440, 1920 and 820 widths,
  including preview, confirmation, created-ticket link, reload/resume, full
  primary action visibility, no body overflow and no normal console/network
  errors. These fixture checks do not replace P10 actual staging acceptance.
- Bounded independent review has no blockers. Two new test files have zero
  inventory issues. CODEMAP/admin guide document both routes and transaction
  ownership. Screenshots retained under ignored
  `artifacts/browser_checks/guided-request-studio-v2/p7/` (1366 inspected).
  No listeners remain on 4188/55438; owned temporary databases are harness-cleaned.
  Publication readiness/source pinning remain P8; no deployment, live offering
  publication or Endpoint execution. P8–P10 remain required.

### P8 — PASS

- Added distinct graph/processing readiness, bounded canonical variant execution,
  nested diff, actor/scope/source-bound one-use confirmation, atomic immutable
  version publication and rollback into a new draft revision. API simulation
  now supports current-page conditional projection and actual policy dry-run.
- Shared confirmation helpers preserve the legacy publication API. Source
  binding includes canonical form packs, templates, policies, catalog, taxonomy,
  queues, SLA/OLA targets and business calendars. Publication locks those static
  source tables in SHARE mode until commit; preview and simulation do not.
  The conservative global source hash may require a new preview after unrelated
  administrative edits. Neither operation dispatches Endpoint diagnostics.
- Independent review identified optional instruction outcomes, priority
  importance/modifier references and omitted calendar content/locking. Genuine
  RED tests reproduced all three; pure and PostgreSQL fixes now pass. The
  calendar reproduction originally published after a timezone change (expected
  409); the corrected source binding rejects it. Used tokens now enter full
  isolated test cleanup; the legacy global token count assertion is unchanged.
- Readiness fails closed above 512 finite variants or for unbounded facts that
  influence branching/processing. This is an explicit current limitation, not
  proof that all supported field combinations are publishable.
- A focused review of the shared dry-run extension found normalized ticket
  type/taxonomy and empty-answer parity defects. Genuine RED covered differing
  raw/canonical type, while the regression also preserves an empty normalized
  map despite raw hidden facts. Canonical overlay return values are retained.
  These fixes preserve the legacy no-keyword simulator. No review blockers
  remain. Optional acknowledgment is available in both admin and requester UI.
- Final fast backend command across readiness/submission/admin contract/graph/
  runtime/Policy Health: **122 passed in 1.33s**. Studio and requester frontend
  tests: **61 passed in 6.26s**. `pnpm --dir webapp build`: **PASS**, with the
  existing shared-chunk warning. Scoped workspace verification and strict test
  inventory for all three new backend files: **PASS**, zero inventory issues.
- PostgreSQL publication/calendar plus complete legacy Studio and requester
  catalog/Policy Health catalog regressions: **14 passed in 458.51s**. After the
  final parity fixes, simulation-vs-actual-create with offering type override,
  actual P2/SLA120 no-write preview and calendar binding: **3 passed in 119.42s**.
  Actor mismatch, invalid/reused/expired tokens, changed sources/revisions,
  concurrent publish, audit rollback and rollback-as-new-version are covered.
- Final `PC_CLIENT_WEBAPP_E2E_PORT=4188 pnpm --dir webapp test:e2e
  guided-studio.spec.ts`: **11 passed in 28.3s** across four sizes, including
  keyboard publication and history restore into a new draft. Screenshots are
  retained in ignored `artifacts/browser_checks/guided-request-studio-v2/p8/`,
  1366 inspected. This is fixture browser evidence, not P10 actual signoff.
- Full-task follow-through still requires policy selection inside the processing
  step, complete simulated-result presentation and actual A–J staging acceptance.
  These remain explicit P10 acceptance gaps; P8 only accepts its publication
  contract. P9/P10 remain required. No production deployment or live publication.

### P9 — PASS (local/staging test gate)

- P8 committed as `b0e508508d7825734e47d71d9599731f73c5818f`
  (`feat(studio): publish validated scenario versions atomically`, 30 files).
- GitNexus query was used before P9 source exploration. The committed index
  points to the existing ticket-scoped diagnostic support boundary; no missing
  path is interpreted as permission for pre-ticket execution.
- Genuine RED: four missing runtime simulated outcome cases and the missing
  admin simulator DTO. Implemented caller-only diagnostic failure outcomes:
  unavailable/denied/timeout/capability_absent. Admin repo passes the validated
  map to the canonical side-effect-free evaluator. Simulated results explicitly
  carry simulated=true/operation_created=false and configured consent metadata.
  Requester answer DTO rejects diagnostic outcome/consent/success injection.
- The capability allowlist already exists in graph validation. An initial P9
  test incorrectly expected that rejection in the DTO; moving the test to the
  actual pre-runtime graph boundary preserves the existing regression contract.
  No capability or safety check was relaxed. File fields remain DTO-rejected.
- `python -m pytest server/tests/test_request_scenario_diagnostic_boundary.py
  server/tests/test_request_scenario_runtime.py
  server/tests/test_request_scenario_admin_contract.py -q`: **58 passed in 0.99s**.
- Readiness now traverses all four failure statuses, including explicit diagnostic
  outcome branches. Requester defaults remain unchanged. Imported malformed file
  fields carry the explicit attachments_unsupported publication blocker; safe
  pre-ticket upload is intentionally unavailable under the P9 allowed boundary.
- Frontend inspector displays configured consent, required fallback and execution
  boundary. Simulator lets the administrator choose a typed failure outcome and
  marks results as simulation/no operation. Changing the outcome resets the run.
- Independent review found blank names for new outcomes in the branch-condition
  editor. Genuine regression RED then shared label lookup fixes scalar and
  membership choices. No safety controls or legacy tests were relaxed.
- Latest fast backend command (boundary/runtime/admin_contract/readiness):
  **78 passed in 1.31s**. Studio vitest: **51 passed in 7.17s**. Owned staging
  PostgreSQL API test: **1 passed in 46.71s**, checking four outcomes, requester
  403, invalid success/unknown/non-diagnostic ID 400, file draft 400 and no ticket,
  event, approval, operation or session writes. Final expanded count regression:
  **1 passed in 46.65s**, also proving no TicketNotification, ConsentDecision or
  UserConsentRequest records. Both runs used owned isolated staging databases
  and runtime SSH profile; no credentials or database URLs were printed.
- `PC_CLIENT_WEBAPP_E2E_PORT=4188 pnpm --dir webapp test:e2e
  guided-diagnostics.spec.ts`: **4 passed in 12.9s** at 1366x768, 1440x900,
  1920x1080 and tablet 820x1180. Keyboard start/focus, outcome reset, no overflow,
  no console/network errors or unexpected API dispatch. The initial browser
  fixture used an incorrect step label; corrected to the existing «Тестирование».
  Fixture evidence does not replace P10 actual staging acceptance. Screenshots
  copied to `artifacts/browser_checks/guided-request-studio-v2/p9/`; 1366 inspected.
- Strict inventory for both new backend tests: **2 files, 0 issues**. Scoped
  workspace verification and diff checks passed. Final `pnpm --dir webapp build`
  passed (existing common-chunk size warning only). Independent P9 review and
  bounded finding closure found no remaining blockers. No migration/new route.
  No production changes or pre-ticket Endpoint execution. P10 remains required,
  including the full processing-selection/simulator gaps recorded under P8.
