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
