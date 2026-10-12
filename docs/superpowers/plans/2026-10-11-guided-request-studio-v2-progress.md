# Guided Request Studio v2 execution ledger

Plan: [canonical specification and P0–P10](2026-10-11-guided-request-studio-v2.md).
Specification commit: `507ee7154b947391d51148d3a8929b77983eb77e`.
Implementation branch: `codex/guided-request-studio-v2`.
Production deployment/publication and real Endpoint execution are excluded.
Isolated staging scenario publication is authorized for the acceptance pilot.

## Current acceptance state (2026-10-12)

P0–P9 are committed; P10 remains incomplete. Earlier entries below are historical
receipts, not acceptance of subsequent corrections.

- Exact `6a2d9ff6068024879772498e297851c88aa084ab` CI 38173068210 passed all
  18 canonical layers and Endpoint contract acceptance. Downloaded report audit
  confirms 663 frontend unit tests and 106 fixture browser cases passed. Fixture
  results do not accept the installed staging candidate.
- Frozen `08dfa34f` seven-layer backend coverage timed out after 7200 seconds.
  Its incomplete coverage is rejected. Final inspection found no owned checkout
  processes or scoped DB sessions; three owned databases were removed and the
  temporary role is absent.
- Final assertion-level independent audit found AC01 search omitted offering
  request types and Studio profiles. The bounded correction adds machine codes
  and Russian labels for scenarios and legacy offerings before merged pagination.
  RED: seven cases returned zero instead of two matches. GREEN: 113 focused
  tests and scoped workspace verification passed, including malformed profile
  object/list/null regressions. Admin instructions and CODEMAP were synchronized.
  Isolated staging PostgreSQL HTTP/catalog checks: 21 PASS (353.64s), including
  type/profile search for bound scenarios and legacy offerings. Working-copy
  overlay archive digest: `b16de177c183acd8ba083064db34ca57440a016e05d7bd8410470d22ce853e7b`.
  Temporary role removed; no owned databases remained for final cleanup.
- Quality run 38173066095 for `6a2d9ff6` was deliberately cancelled because this
  application correction requires a new exact candidate. Canonical PostgreSQL
  stop and evidence upload succeeded; Sonar analysis was skipped. It is not a
  quality PASS. No threshold, scanner token rights or PR parameters were weakened.
- The existing application binds sessions to authenticated actors inside isolated
  per-instance deployment/database resources. No separate multi-tenant contract
  exists in AuthContext; no independent multi-tenant acceptance is claimed.
- Pending: corrected-candidate exact CI/security/coverage
  and PR Sonar gate, canonical staging installation, actual A–J plus four viewport
  checks, owned pilot cleanup/service stop and the final AC01–20 matrix.

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

### P10 — IN PROGRESS (not accepted)

- P9 committed as `1802ba24c6e9ce2cf280270e11ad1674495788aa`.
- Before actual A–J acceptance, complete the original wizard processing and
  simulation requirements. Reuse existing Helpdesk policy registry selectors
  and `resolve_policy_ref`; no policy engine, SLA implementation or live catalog
  mutation is introduced. Admin-saved scenario bindings are server-validated
  references to published policies, applied through the same trusted internal
  path for readiness, dry-run and actual ticket creation. Empty selection keeps
  existing template/catalog inheritance. Requester commands cannot supply refs.
- GitNexus query completed before P10 source exploration; existing canonical
  source confirms policy_refs already control ticket lifecycle resolution.
- P10 A–J staging browser, exact CI/security/coverage/Sonar and final AC matrix
  remain outstanding. No production deployment or Endpoint dispatch.
- Processing increment implemented: typed eight-kind published policy refs,
  same canonical resolver bridge for save/readiness/simulation/actual creation,
  editor choices and mapped-fact explanation with local advanced disclosures.
  Full result displays normalized facts, traversed branch, priority reason,
  SLA/OLA, approval, notification rules and closure. Notification projection uses
  existing rule helpers, no provider calls or delivery claims.
- RED/GREEN: backend binding tests initially **4 failed**; missing UI component
  was RED, then choice test GREEN. Missing normalized-facts result was RED via
  actual PostgreSQL API. Independent review found inactive legacy SLA and a
  frontend OLA array assumption; both reproduced RED and corrected. Explicit SLA
  no longer inherits a no_sla waiver. Exact OLA object/empty object fixtures now
  cover the frontend boundary. Final review closures have no remaining blockers.
- Latest fast scenario regression: **142 passed, 32 DB tests deselected in
  2.35s**; separate focused policy/runtime/readiness **72 passed in 1.30s**.
  Studio frontend **54 passed in 6.38s**; typecheck/build passed with the existing
  common-chunk warning only. Strict new-test inventory: 2 files, zero issues;
  scoped workspace verifier and diff checks passed.
- Owned staging DB regression: selected-route actual creation parity + existing
  Service Catalog preview and legacy Studio APIs **8 passed in 281.15s**.
  Final expanded selected-route/SLA parity **1 passed in 66.02s**, proving chosen
  standalone 240-minute SLA replaces inherited 120-minute legacy SLA in dry-run
  and actual ticket snapshot/deadline. Simulator leaves ticket/operation/approval/
  notification counts unchanged. Test databases and tunnel cleaned by harness.
- Corrected canonical-shape browser run: `PC_CLIENT_WEBAPP_E2E_PORT=4188 pnpm
  --dir webapp test:e2e guided-processing.spec.ts`: **4 passed in 10.4s** at
  1366x768, 1440x900, 1920x1080 and 820x1180; keyboard, draft-only selection,
  full result and overflow/error checks. Screenshots in
  `artifacts/browser_checks/guided-request-studio-v2/p10/`, 1366 inspected.
  This remains fixture UI evidence, not the required actual staging A–J browser.
- Approved staging SSH read-only inspection confirmed dedicated staging root,
  state directory and units. No deployment or service mutation yet. Remaining:
  final field/readiness fidelity audit (finite significant domains are still
  conservative), actual staging A–J plus 30-question UI, canonical CI/security/
  coverage/Sonar, remaining catalog/form/runbook docs and full AC01–AC20 report.

### P10 fidelity increment: inline category creation

Reused category CRUD inside wizard purpose; selected service/parent are initial
values, service is fixed to prevent cross-service placement. Save selects the
new category and preserves local scenario edits. Wizard navigation and scenario
save/copy/archive/leave are guarded while the inline form is open. Chromium's
HTML pattern /v gate also exposed an unescaped hyphen in the existing category
slug validation; category and scenario key patterns now escape it.

- RED: purpose component lacked the inline creation action.
- GREEN: deferred-response component confirms edits made during category save
  survive. Studio component regression: 55 tests passed.
- Typecheck and production build: PASS; existing bundle-size warning unchanged.
- Browser: `PC_CLIENT_WEBAPP_E2E_PORT=4188 pnpm --dir webapp test:e2e
  guided-category-inline.spec.ts` — 4 passed (10.1s), all four required viewports,
  keyboard save, guarded actions, no overflow/console/network/unexpected API.
  Initial stale-dist and selector runs were not counted; actual pattern error
  was fixed before the final successful run.
- Screenshots: ignored `artifacts/browser_checks/guided-request-studio-v2/p10/
  category-inline/`; 1366 screenshot visually inspected.
- Independent bounded review: no blocking findings. Reviewer suggested delayed
  response coverage; that regression passed after adding it.
- Scoped workspace verification and diff check: PASS. No schema/API change.
- Remaining fidelity: inline new offering/profile, real field sections and
  faithful selected-step preview, catalog metadata/collapse, publication result.
- Full P10 still IN PROGRESS: actual isolated staging A–J and canonical CI open.

### P10 fidelity increment: named sections and requester preview

Added optional bounded `group_title` beside existing group key; rejected blank,
ownerless or inconsistent titles within one page. Legacy groups remain valid.
Requester, server simulator UI and selected-step preview share display-only
section rendering. Builder assigns/renames sections by human title, retaining
stable keys. Selected preview now uses existing requester dynamic controls,
disabled, with conditional visibility explicitly delegated to server testing.
A full-branch preview action opens that testing stage.

- RED: group title rejected by DTO; requester lacked section group; preview lacked
  real controls. GREEN: projection, section requester, disabled controls regressions.
- Reviewer found simulator lacked allow_unknown; RED checkbox regression then
  GREEN explicit `{printer:null}` command, sequence invalidation, browser assertion.
- Scenario server no_db suite: 146 passed, 32 deselected (2.39s).
- Studio plus requester session component suite: 72 passed (7.84s).
- Owned PostgreSQL processing API: 1 passed (67.70s); saved/published section
  metadata reaches the requester while actual queue/SLA/ticket parity remains PASS.
- Typecheck/build: PASS, existing common chunk warning only.
- Browser `guided-sections.spec.ts`: 4 passed (10.9s), 32 questions, exactly one
  selected field editor, keyboard selection/drawer Escape, human section controls,
  full server-simulator stage and explicit unknown null, no overflow/errors/unsafe API.
- Screenshots copied to ignored `artifacts/browser_checks/guided-request-studio-v2/
  p10/sections/`; 1366 screenshot visually inspected. Fixture E2E is not actual staging.
- Independent review found no remaining blocker in this bounded increment.
- No migration/new endpoint/dependency or changes to the legacy form contracts.
- Remaining fidelity: inline new offering/profile, catalog metadata/collapse and
  publication result. Actual staging A–J and canonical CI still open. P10 IN PROGRESS.

Final focused browser regression for the section increment:
`PC_CLIENT_WEBAPP_E2E_PORT=4188 pnpm --dir webapp test:e2e guided-studio.spec.ts
 guided-requester.spec.ts guided-sections.spec.ts guided-category-inline.spec.ts`
— 27 passed (1.1m), including requester self-service/ticket flows and Studio
loading/empty/error/retry. Scoped workspace verification and diff check PASS.

### P10 fidelity increment: catalog metadata and category collapse

- Catalog shows full human service/category ancestry, description, active
  published version number and last scenario/draft modification time. Individual
  category branches are independently collapsible with keyboard-accessible
  buttons; category selection and existing service collapse remain available.
- Server adds nullable `published_version` by joining the active immutable
  pointer, preserving unpublished and legacy form-only entries. No migration,
  new endpoint or dependency; requester execution/publication controls unchanged.
- RED: component test failed on missing human path. Owned PostgreSQL publication
  regression failed with missing `published_version`; GREEN after projection.
- Independent review found stale timestamp on same-actor block-only edits.
  Dedicated owned PostgreSQL regression confirmed RED (scenario remained 2020,
  draft changed to 2026), then GREEN after selecting the maximum timestamp.
  Reviewer rechecked fix and reported no new findings.
- Frontend Studio + catalog page: 63 passed (9.39s); production build/typecheck
  PASS (existing common chunk warning). Scoped workspace and diff check PASS.
- Owned PostgreSQL timestamp + atomic publication/replay/rollback tests:
  2 passed (90.33s). First publication metadata GREEN independently 1 passed
  (62.52s). Harness dropped owned runtime databases and closed its tunnel.
- Browser `guided-studio.spec.ts --grep 'catalog and wizard'`: 4 passed (14.0s),
  1366/1440/1920/tablet820, keyboard collapse, category metadata, visible primary
  action, no horizontal overflow, console/network errors or draft loss. Initial
  tablet check used hidden desktop navigation; corrected to visible catalog
  action and verified unsaved-change cancellation. This is fixture browser
  evidence, not the actual staging A–J pilot.
- Screenshots copied to ignored
  `artifacts/browser_checks/guided-request-studio-v2/p10/catalog/`; 1366 visually
  inspected. Browser fixture stopped after validation.
- Remaining: inline new offering/profile, publication result, readiness coverage
  fidelity audit, actual isolated staging A–J, exact canonical CI/security/coverage/
  Sonar and final P0–P10/AC matrix. P10 remains IN PROGRESS.

### P10 fidelity increment: publication summary, result and requester link

- Publication stage shows title/description, human target offering and all steps
  in collapsible previews using the existing requester controls. Transition
  destinations use human titles; actual branch evaluation stays on the server.
  Successful result prefers the returned immutable version definition, shows
  version, links to the requester flow and retains the existing version history.
- `/app/requester/new?offering=...` selects only a matching offering from the
  authenticated requester catalog. Existing availability and owner-scoped
  scenario runtime remain authoritative. A link does not grant access.
- Offering-link drafts use separate keys from normal drafts. Same-router
  intent/offering changes remount content to restore the correct draft before
  persistence; normal drafts and both offering drafts survive navigation.
- RED: requester direct-link test failed to select the offering; publication
  result test failed on absent requester link. GREEN after implementation.
- Independent review found same-router draft overwrite risk. Regression RED
  reproduced the retained old category; keyed-content fix GREEN restores normal,
  printer and laptop answers individually. Reviewer closed the finding and found
  no further issues; immutable-result preference has a component assertion.
- Studio + requester page + catalog page: 82 passed (9.87s). Build/typecheck PASS
  (existing common chunk warning); scoped workspace and diff check PASS.
- Browser `guided-studio.spec.ts guided-requester.spec.ts --grep
  'publication confirmation|guided requester'`: 12 passed (27.9s), all four
  viewports. Publication confirmation/result/expanded instruction, deep-linked
  ticket flow, normal self-service, reload/resume, no horizontal overflow or
  console/network errors. This is fixture browser evidence, not live A–J.
- Screenshots copied to ignored
  `artifacts/browser_checks/guided-request-studio-v2/p10/publication-result/`;
  1366 visually inspected. Browser fixture stopped after validation.
- No backend/schema/policy/dependency change. Remaining: inline new offering/
  profile, readiness coverage fidelity, actual staging A–J and canonical CI/
  security/coverage/Sonar/final acceptance matrix. P10 remains IN PROGRESS.

### P10 fidelity increment: atomic new-offering publication backend

- Strict saved `publish_offering` defaults false. Explicit intent permits only
  a public draft offering under a published public parent, using the existing
  Service Catalog validator and canonical processing preview. Requester JSON
  cannot enable candidate authority. Preview remains non-mutating and includes
  offering promotion in the source-bound confirmation diff.
- Promotion, immutable scenario version with published offering snapshot, active
  pointer, token consumption and both audits share one transaction. A catalog
  source lock is acquired in write-compatible mode before revalidation to avoid
  concurrent SHARE-lock upgrade deadlock; promotion serializes catalog writes
  for the duration of this transaction. Existing published offerings stay intact.
- RED: strict-contract test lacked the field; HTTP promotion tests rejected the
  new definition. Canonical readiness then exposed a missing request type in the
  test fixture; the fixture was corrected without relaxing catalog validation.
- Final owned PostgreSQL command: `python -m pytest
  server/tests/test_request_scenario_offering_publication_api.py
  server/tests/test_request_scenario_publication_api.py::test_atomic_publish_replay_actor_scope_and_rollback_as_new_version
  -q --tb=short`: 4 passed (206.93s). Covers atomic success, audit-failure rollback,
  no-intent rejection, private offering, unpublished parent, invalid catalog,
  replay rejection and existing publication/rollback behavior.
- Scenario no-DB regression: 152 passed, 1 skipped, 1956 deselected (2.48s).
  Catalog mocks were aligned with the previously added active-version projection
  in separate test-only commit `3abb7521ae212368f10d89d0477f8987f5ba7077`.
  Wire contract component: 1 passed (2.35s). Independent review found no blocking
  source issues; requested negative HTTP boundaries are now covered.
- Additive saved JSON field; no migration, new endpoint, dependency or second
  policy engine. Remaining: inline creation UI, readiness fidelity audit, actual
  isolated staging A–J, exact full CI/security/coverage/Sonar and final acceptance
  matrix. P10 remains IN PROGRESS.

### P10 fidelity increment: inline new offering and human profile

- Purpose step now creates a public draft under a published/public parent via
  existing catalog `save-draft`; code is generated once per form. Only active
  published templates are selectable. Canonical ticket type follows the template;
  human installation profile maps to existing `service_request` and is retained
  in offering metadata. No parallel profile/policy processing engine is added.
- New offering is selected locally and catalog refreshed; explicit saved
  publication intent enables the already verified atomic backend. Existing
  offerings are not edited. Latest definition ref preserves edits made during
  the request. Wizard/page actions use the existing inline dirty/open guards;
  loading/error/empty states block submit, retry retains input, cancel confirms
  dirty discard. Publication diff has human labels for new offering promotion.
- RED missing inline creation action; GREEN component verifies draft payload,
  unpublished/private filtering, software-install mapping, generated code,
  explicit intent, no immediate publication and latest title preservation.
  Error/retry/empty registry regression also passes. Studio: 61 passed (10.49s).
- Independent review's missing software-install profile finding closed with
  compatible mapping and regression; no further confirmed issues.
- Build/typecheck PASS (existing common chunk warning). Browser
  `pnpm --dir webapp test:e2e tests/guided-studio.spec.ts --grep 'inline offering'`:
  4 passed (9.7s), 1366/1440/1920/820. Keyboard create, save/leave/step guards,
  canonical draft selection/save, no overflow/console/network errors. Initial
  stale-dist run stopped and rebuilt; a locator failure was corrected to the
  combobox's accessible role. Final screenshots visually checked at 1366.
- This is fixture browser evidence. Actual staging A–J, readiness fidelity audit,
  full exact CI/security/coverage/Sonar and final acceptance matrix remain open.
  P10 remains IN PROGRESS.

### P10 fidelity increment: provable readiness domains and omitted answers

- Multi-select now covers all subsets for graph predicates and ordered subsets
  for policy inputs. Order is preserved by the canonical form normalizer and can
  affect existing string-comparison policy rules; no unordered-policy assumption
  is made. Materialization remains bounded by the existing 512-variant gate.
- Graph-only number predicates partition the valid wire-safe range at literals
  and validation boundaries, with representatives for open intervals. Graph-only
  text/textarea equality/membership/presence predicates cover literals and a
  distinct valid nonempty representative. Ordinary numeric/text representative
  values obey configured bounds; URLs use valid syntax. Arbitrary unbounded
  numeric/text policy domains remain fail-closed, not claimed exhaustive.
- Independent review found explicit unknown versus omitted optional input was
  conflated, allowing an omitted-only fallback to escape readiness. Regression
  RED reproduced that missing terminal. Distinct internal omission sentinel
  removes the key before canonical runtime evaluation; text/number/select/radio
  regressions cover null, known and absent destinations. Reviewer closed P1.
  Checkbox absence remains canonical false; multi-select scalar comparison is
  rejected by the existing graph validator. Neither contract is weakened.
- Initial RED: 4 domain/constraint failures; ordered-policy subset RED; omission
  RED. Final owned PostgreSQL publication regression: 4 passed (242.87s), including
  atomic offering success/audit rollback, negative catalog boundaries and existing
  source-bound publication/replay/rollback. No runtime/schema/frontend changes.
  Scenario no-DB regression: 161 passed, 1 skipped, 1956 deselected (2.49s).
  Scoped workspace and diff check PASS after documentation update.
- SSH staging key and protected local DPAPI sudo credential verified successfully;
  service remains inactive on its previous release. No secret output, production
  changes, or deployment occurred during this increment. Actual staging A–J,
  canonical exact-SHA full CI/security/coverage/Sonar and final matrix remain open.

### P10 installed staging and unknown-answer handling

- Candidate `8fd099ee9bfdbd917bc6a59d17d4cf2df0ba8b9a` installed through the
  canonical release script on isolated staging. Release identity matches; schema
  revision is 147. Pre-migration revision 146 backup passed archive-list validation:
  11746448 bytes, SHA256
  `e6a6e6c6ffd70abb9395c1c7c3f8ef361b7962019bf9265f3cf9e423699ebcf0`.
  This is backup verification, not restore-drill acceptance.
- Four synthetic pilot accounts created through the canonical user repository;
  passwords are held in a local DPAPI profile. Strict HTTPS API login and Studio
  catalog return 200 using the approved Windows CA in the Node test process.
  Installed catalog browser checks at 1366x768, 1440x900 and 1920x1080 have no
  horizontal overflow. Evidence: ignored `artifacts/browser_checks/
  guided-request-studio-v2/p10/staging/*-installed-catalog.png`.
- Exact-SHA canonical CI run 38155806187 attempt 1 failed one simulator unknown
  test (648 others passed); Endpoint contract job passed. Original local full
  frontend suite passed 649/649. One unchanged-SHA diagnostic rerun is in progress.
  The original CI root cause remains unproven; no gate has been weakened.
- Review identified reading mutable checkbox DOM state inside deferred functional
  updates in both simulator and requester. Capture the checked value synchronously.
  Tests cover checked null and unchecked omission; request assertions are outside
  mocked fetch so simulator error handling cannot swallow them. Review found no
  blocking issues. Focused frontend: 21 passed; full frontend: 650 passed.
- Actual printer A-J, exact final-candidate CI/security/coverage/Sonar, restore
  acceptance and final AC matrix remain open. No production changes or real
  Endpoint operations occurred.

### P10 canonical cleanup expectation and owned pilot draft

- Commit `470127130f2d2446bea8faf577ebc77881da0b71`, exact CI run 38157172667:
  all 650 frontend tests and Endpoint contract acceptance passed. Server no-DB
  layer failed only the stale full-cleanup expectation (1270 others passed,
  1 skipped). Local RED reproduces expected 171 versus actual 173 tables.
  Update the exact count/prefix for Studio sessions and publication tokens;
  preserve existing cleanup entries and assertions. Focused harness GREEN: 42 passed.
  Full server no-DB regression GREEN: 1271 passed, 1 skipped, 846 deselected (45.95s).
- Original SHA diagnostic CI attempt 2 passed all 649 frontend tests before
  concurrency cancellation by the newer dispatch. Original simulator failure is
  intermittent; synchronous checkbox snapshots are reviewed hardening, not a
  proven RCA claim. No flaky registry, retries, coverage or security gates changed.
- Installed staging browser created only owned pilot offering/category/scenario
  drafts. Seven blocks and canonical printer questions configured through the
  wizard, without JSON/expert editors. Pilot retains required room/impact/
  continuity plus optional model/number. Existing printer template/form unchanged.
- First readiness preview blocked excessive combinations; removing optional
  importance/critical/public questions from the owned pilot keeps canonical
  defaults and permits 192 outcome checks. Current preview: HTTP 200, Health=ok,
  can_publish=false, closure_missing/visibility_missing/category_unavailable.
  The staging registry has no published closure or visibility choices. Prepare
  isolated scoped policies through the existing registry before publication;
  do not bypass readiness or mutate the existing printer processing template.
- No scenario published and no pilot ticket created. Staging service stopped
  through the canonical lifecycle command; inactive confirmed. Synthetic accounts
  and owned draft receipt retained for continuation. Full P10 remains in progress.

- P10 instruction escape fidelity correction: explicit `request_ticket` equality
  to review, selected-transition permission shared by server advance/projection,
  typed DTO/TS result, human builder option and requester/simulator buttons.
  No acknowledged result is fabricated; fallback/neq/exists or higher-priority
  branches cannot authorize escape. Readiness enumerates it; required initial
  facts remain enforced. RED 8, GREEN 8; focused backend 107 PASS; full no-DB
  1279 PASS/1 skipped; frontend focused 25 PASS; build/typecheck PASS; browser
  fixture 12 PASS (four viewports, normal and escape flow). Independent review
  found no blocking issue. Full frontend regression: 111 files / 654 tests PASS.
- c7 exact CI attempt 2 passed the prior database teardown but failed raw-SQL
  concurrent category reparent: expected 23514, received 40P01. The trigger's
  row-before-advisory lock ordering can deadlock opposing UPDATEs; Admin API
  obtains the service lock first. The original teardown timeout RCA remains
  unproven. CI remains red, and latest candidate is not installed or published.
- Raw-SQL race assertion corrected without weakening the tree invariant: accept
  only 23514/40P01 for the losing transaction, require exactly one commit, both
  rows and the exact winning edge/root; retry the losing edge after commit and
  require 23514. Production API concurrency assertions remain unchanged.
  Independent review: no blockers. Canonical harness-owned PostgreSQL suite:
  9 persistence tests PASS (773.26s), including additive 147→146→147 rollback
  retaining the legacy sentinel. Temporary role absent and owned DBs removed.
  Staging synthetic requester profile is now complete via browser form, with
  zero devices and canonical owned department/location records. No pilot
  publication or tickets yet; staging service stopped. Full P10 remains open.
- P10 J gap found during acceptance preparation: readiness text did not lead
  to the faulty block or processing control. Publication now provides human
  correction actions using server issue paths/codes. A broken target selects
  its source block, opens local transitions and focuses the first missing
  target; routing/SLA/closure focus their policy after registry loading.
  General errors focus the relevant stage. Navigation does not mutate the
  draft or bypass server publication checks. RED 4; focused GREEN 8 and Studio
  regression 67 PASS; build/typecheck and scoped workspace PASS. Browser
  fixture keyboard navigation PASS at 1366/1440/1920/820, including a broken
  second transition and all three processing controls. Independent review
  identified first-edge focus, now corrected to the first missing target.
  Actual installed J remains required. Previous candidate baeba8b0 full CI
  38161969186 PASS; final correction SHA needs its own exact CI.
- P10 J routing availability: independent source review confirmed that a
  missing/inactive queue could pass readiness solely through a nonempty rule
  ID. Publication now checks active IDs in its locked source snapshot. Scenario
  safe preview refreshes/share-locks the current queue; submit repeats preview
  and refuses unavailable routing. Legacy preview behavior is preserved.
  RED 4; focused GREEN 39 and full backend no-DB 1285/1 skipped PASS.
  Isolated PostgreSQL preview/submit regression and positive publication test:
  3 PASS (634.88s), temporary role absent with no residual test DBs.
  Prior candidate c6beea6e CI 38163730441 PASS; this server fix
  requires a fresh exact-SHA gate. Canonical coverage was stopped before source
  changes; it is partial, not a PASS. Cleanup helper name collision was repaired
  and both residual owned test DBs and the temporary role were removed.
- Independent review found a remaining policy-change race between preview and
  actual create. A post-create check would be too late for external playbooks.
  Canonical scenario creation now checks and share-locks its actual routed queue
  immediately after routing, before SLA/OLA/approval/playbooks. A trusted internal
  flag defaults off for legacy creation; the typed failure rolls back as 409
  PROCESSING_UNAVAILABLE. Boundary RED 2/GREEN 14; frozen Linux PostgreSQL
  interleaved test RED (85.40s, submit returned 200 instead of 409), GREEN
  1 PASS (75.88s) with actual inactive route, no playbook call, full DB rollback
  and unchanged active session. Full backend no-DB 1287/1 skipped PASS;
  scoped workspace/diff check PASS, independent review has no blockers.
  Broader scenario submit/publication and legacy canonical-create PostgreSQL:
  9 PASS (274.81s), including concurrency, audit rollback/retry, mapped
  priority/routing/SLA/OLA/approval and legacy no-device creation. Temporary role
  absent, no residual owned DBs. Focused readiness/runtime/initialization:
  54 PASS. The committed correction still needs its own exact CI and installed
  staging acceptance; no overall P10 PASS is claimed.
  Linux validation uses a dedicated archive/venv, protected fresh scoped role,
  loopback PostgreSQL and no staging application environment. Two initial harness
  preflight failures (UID path access and isolated HOME) were corrected; no
  application data was changed, and every created test role was removed.
  Windows duplicate race run was stopped with its owned process tree and cleanup
  removed the temporary role and one owned test DB. It is not a PASS receipt.

- P10 installed simulation exposed a focus defect: leaving an automatically
  focused heading triggered an empty preview and disabled the answer before
  typing. Control-only blur fixes this. Independent review also found that
  input blur before a direct Continue click swallowed the action; transitions
  to buttons inside the fieldset now skip preview and submit current answers.
  Unit RED/GREEN and native direct-click RED reproduced both paths. Final
  focused checks: 32 PASS; build/typecheck and scoped workspace PASS. Browser
  fixture Tab/direct-click and auditor route: 12 PASS at 1366/1440/1920/820.
  New installed candidate acceptance remains required; prior H is not a PASS.

- P10 installed auditor testing found the global workspace gate blocking the
  documented Studio read/simulation contract. Auditor now receives only the
  Studio route fallback; admin/support workspace grants remain unchanged.
  Simulation has a separate disabled state; editing/publication stay admin-only.
  Router RED 4/GREEN 4 and auditor simulation RED/GREEN; combined 32 PASS,
  build/typecheck, scoped workspace and 12 viewport browser cases PASS.
  Independent review reports no remaining blockers. Full frontend coverage,
  exact candidate CI and installed G/H are still pending.
- Exact 08dfa34f CI 38167094031 completed successfully: all 18 merge-gate
  steps and Endpoint contracts PASS. That revision was installed through the
  canonical staging release script with identity verified and schema 147.
  Actual UI/database A/B/C/E/F/I/J PASS, including duplicate submission with
  exactly one ticket and immutable V1 sessions after publishing V2.
  D priority comparison remains pending matching H simulation facts; G exposed
  the auditor route defect, and H exposed the focus defect above. Neither is
  accepted. Owned data remains four tickets, zero approvals/notifications/device
  operations; global operation/link counts unchanged. Staging service stopped.
  These receipts apply to 08dfa34f only and do not accept the new fixes.

- AC05 visual review of the 32-question page found navigation height 1532px,
  pushing its single field editor below all question rows. Navigation now has
  a bounded height with native vertical scrolling. Browser RED confirmed1532px;
  GREEN 4 at 1366/1440/1920/820 verifies bounded height, overflowing content,
  keyboard selection of question32 and one editor. Editor unit5, build/typecheck,
  scoped workspace and independent review PASS. Admin guidance updated.
- Candidate3b86fdc6 full frontend coverage executed112 files/663 tests PASS
  (299.87s): line66.90%, branch57.36%; baseline line67.78% preserved.
  Studio/browser33 and requester/32-question browser16 PASS before the bounded
  list correction. Canonical Semgrep1.178.0:17 legacy findings outside changed
  task files, zero task-file findings, zero secrets/errors. Exact CI38170784757
  initially failed one unchanged FormsBuilder required-field unit; same-SHA
  focused retry and local full frontend PASS, one CI rerun pending. No CI or
  installed acceptance is inferred from local results. The list correction
  requires its own exact candidate gate. Backend coverage continues on frozen08
  with byte-identical server/shared/scripts trees; candidate Sonar remains open.

- Candidate b9e71f81 full frontend coverage:112 files/663 tests PASS;
  line66.90%, branch57.36%. Full Studio/sections/requester browser:49 PASS at
  four viewports, with persistent screenshots. Semgrep1.178.0:17 unchanged
  findings outside task paths, zero task findings/secrets/errors. Exact CI
  38171834372 PASS: downloaded exact-SHA summary has all18 steps green and
  full merge gate satisfied; Endpoint contract suite PASS. The preceding
  3b86fdc6 failed-job rerun was cancelled by the newer dispatch, not accepted.
  Frozen08 seven-layer coverage is still running; no coverage completion claim.
- Sonar main gate is OK with zero new violations, but PR41 analysis is absent.
  A separate manual candidate job now shares the existing scanner pipeline
  through YAML aliases. Original main job, trigger, permissions and concurrency
  are exactly equivalent after YAML expansion. Candidate admits only the exact
  same-repository open draft PR41 head/base before checkout and immediately
  before analysis; all three PR parameters are fixed, with no main fallback.
  Admission checks RED15 (missing candidate)/GREEN15; scoped workspace PASS;
  independent security review found no blockers. Actual GitHub acceptance,
  supported Sonar edition and exact candidate gate remain unverified. An
  unsupported PR-analysis response must block, without widening token rights.
  This workflow change requires a new exact-SHA CI and staging acceptance.

- User explicitly deferred Sonar on 2026-10-12. Exact eacd57c5 full CI18 PASS;
  seven backend coverage layers PASS, Semgrep zero task findings/secrets/errors.
  Sonar Community Build rejected PR analysis; Quality Gate remains NOT_COMPUTED.
  A separate human admission allowed only isolated staging, with no production
  permission or fabricated quality receipt. Canonical installation verified eacd.
  Actual A/B/C UI/database PASS; D820 failed primary Continue visibility on a
  long question page. Staging was stopped; D and full P10 are not accepted.
- Long requester pages now separate disabled action and question fieldsets and
  keep step actions sticky. New-request shell horizontal clip avoids the scroll
  ancestor introduced by overflow-x-hidden, for canonical and trailing-slash URLs.
  Longform browser RED reproduced ratio0; fresh build/typecheck and browser12
  at1366/1440/1920/820 PASS, unit18 PASS, scoped workspace PASS. Review found
  and closed the trailing-slash case; no remaining diff findings. New exact CI,
  frontend/security evidence and actual installed A-J/V remain required.
