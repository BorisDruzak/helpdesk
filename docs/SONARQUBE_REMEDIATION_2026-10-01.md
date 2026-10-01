# SonarQube remediation evidence — 2026-10-01

Scope: [approved plan](superpowers/plans/2026-10-01-sonarqube-evidence-remediation.md),
B1–B6 and D1–D5. Baseline `e9c9bf37dc26af98e9da91b7d424bc4efcee7990`;
working branch `codex/sonarqube-evidence-remediation`. All changes are local.

## Behavior and architecture

- Required numeric zero is accepted; min/max and missing values retain validation.
- Checkbox strings use explicit true/false aliases. Numeric/object/list/unknown
  values are rejected. Visibility preserves typed false/zero/null, legacy boolean
  aliases and case-sensitive select/multi-select values.
- Hidden field errors are removed; errors in visible dependencies remain.
  Schema publication rejects malformed regex, and existing invalid saved regex
  blocks submission with a safe configuration error. Python-only constructs are
  rejected by token-aware checks; escaped literals and character classes survive.
  This checks a shared syntax subset, not full equivalence of the two regex engines.
- Scheduler stop awaits shielded child cleanup and preserves parent cancellation,
  including repeated cancellation and a child cleanup exception.
- Form schema, values and defaults have separate ownership behind the original
  facade. Create has typed input/context, trusted identity checks, field assembly
  and persistence/init stages. Workflow separates pure updates and ordered effects.
- The compatibility detail page now uses a controller, formatting helpers and
  sections. The active application route still renders `TicketListPage` through
  `lazy-pages.tsx`; routing was not changed. Compatibility exports remain available.
- Related FK/delete constants retain SQLAlchemy metadata for all 165 tables;
  UTC generation retains the public `Z` representation. Presence assertions are
  separate so failures identify the mismatching field.

## Regression evidence

Before correction, form regressions reproduced 33 backend failures and 8 frontend
failures. Numeric-zero subset: 8 passed after correction. Cancellation reproduced
2 failures before correction. Independent review reproduced 3 valid-pattern
rejections; mirrored regressions now cover escaped quantifiers/classes. A later
render regression demonstrated that invalid checkbox input must stay editable
and fail validation without crashing the form.

Final results are recorded below. Interim DB run:
121 passed in 2252.43 s across form packs, scheduler, workflow profiles,
closure/approval policies, atomicity/concurrency and side-effect observability.
This interim run predates the last create-stage extraction and is not claimed as
verification of the final source.

Final local checks (after review corrections):

| Check | Result |
|---|---|
| Focused backend unit/contract suite below | 140 passed in 1.88 s |
| `npm --prefix webapp test` | 90 files, 529 tests passed in 48.86 s |
| `npm --prefix webapp run build` | TypeScript and Vite passed |
| Documented Chromium selection | 3 passed in 7.8 s; page/console/HTTP errors absent |
| `python scripts/verify_workspace.py --workspace .` | Verification passed |
| `python scripts/audit_db_cleanup_schema.py --schema-from-models --strict` | All risk/classification counters zero |
| FK target/ondelete metadata compared with pre-change snapshot | Identical for all 165 tables |
| Strict test-inventory audit for the six added/extended backend test files | 6 files, 0 issues |
| AST comparison of create/schema/submission public signatures against baseline | Arguments, defaults, return annotations and async contract unchanged |
| `git diff --check` | Passed under repository Git configuration |

The backend selection was run as:

```powershell
python -m pytest server/tests/test_form_submission_edge_cases_no_db.py server/tests/test_create_identity_context_no_db.py server/tests/test_ticket_create_initialization_no_db.py server/tests/test_workflow_atomicity_no_db.py server/tests/test_public_create_atomicity_no_db.py server/tests/test_scheduler_stop_cancellation_no_db.py server/tests/test_workflow_update_builder_no_db.py server/tests/test_id_generators_no_db.py server/tests/test_requester_create_idempotency_no_db.py server/tests/test_workflow_concurrency_no_db.py server/tests/test_domain_ports.py -q --tb=short
```

Final DB/API selection (through runtime-only `TEST_DATABASE_ADMIN_URL`, isolated
harness, migration-fingerprinted temporary template):

```powershell
python -m pytest server/tests/test_ticket_form_packs.py server/tests/test_requester_device_binding_api.py server/tests/test_requester_create_idempotency.py server/tests/test_public_create_atomicity.py server/tests/test_ticket_create_contracts.py server/tests/test_workflow_atomicity.py server/tests/test_workflow_concurrency.py server/tests/test_workflow_side_effect_observability.py -q --tb=short
python -m pytest server/tests/test_ticket_form_packs.py::test_requester_api_persists_checkbox_and_zero -q --tb=short
python -m pytest server/tests/test_problem_scheduler.py server/tests/test_ticket_context_builder.py::test_create_flow_stores_ticket_context_without_trusting_current_device server/tests/test_ticket_context_builder.py::test_create_flow_stores_on_behalf_affected_target_context server/tests/test_ticket_context_builder.py::test_create_flow_writes_ticket_context_resolved_event -q --tb=short
```

Direct requester API persistence selection: **2 passed in 216.75 s** for both
true and false conditions, numeric zero and verified no-device identity.
Its temporary databases/template/role were removed. The broader final DB/API
selection passed **101 tests in 2074.31 s**; its temporary databases/template/role
were also removed. Combined final DB/API selections: **109 passed**, with no failures.
Final scheduler/context selection: **6 passed in 436.19 s**; temporary
databases/template/role removed. This checks scheduler enable/run/overlap and
persisted requester/on-behalf snapshots and context audit events on the final code.

## Browser evidence and limits

Real Chromium fixture checks cover requester checkbox/required/zero submission
and reopening the created ticket, plus compatibility detail at 1366×768 and
1920×1080. They check draft retention after refetch, the initial viewport status
action, horizontal overflow, page errors and unexpected failed HTTP responses.
Screenshots are disposable Playwright outputs in `webapp/test-results/`.
Actual pack/ticket persistence is checked separately through PostgreSQL API tests;
the browser fixture does not establish live staging UI or deployed behavior.

Playwright starts the documented Python fixture server and builds the compatibility
bundle automatically in ignored `webapp/.e2e-compat/`. Run from `webapp`:

```powershell
npm run build
npm run test:e2e -- tests/detail-compatibility.spec.ts tests/requester-workspace.spec.ts -g "compatibility ticket detail|saved checkbox"
```

The Windows Python fixture can log `ConnectionResetError`/WinError 10054 on browser
connection teardown. The assertions distinguish this server transport warning
from browser page/HTTP errors; it is not evidence of clean server logs.

## Database boundary

DB acceptance uses the isolated PostgreSQL harness on approved staging
`192.168.101.118`, a temporary CREATEDB role, and a loopback-only parent-owned SSH
tunnel. Credentials remain in runtime/environment or protected local secret storage.
The harness uses dedicated `pc_support_test_*` databases. No shared application DB,
production resource, application service, deployment or persistent schema migration
is used. Temporary databases, template and role are removed at completion.

## Audit and review limits

GitNexus query/context provided the committed architecture and caller boundaries;
source/tests verified the local uncommitted changes. The reported index revision
was `92a4ba89e7914f380efefa6b91759e79a9cd9267`, older than the local baseline. No
manual group sync/reindex was performed. Context7 checked asyncio cancellation,
React hook state and Vite fixture-build configuration against the pinned versions
or their closest documented version.

Independent source review found regex compatibility, missing fresh-checkout fixture
build integration, incomplete create decomposition and CODEMAP drift. Corrections
and follow-up verification are recorded in this evidence. Contextual Sonar findings
in the plan were reviewed and retained with their stated rationale.

Sonar baseline remains the existing analysis: no scanner run, rule/issue mutation,
suppression or new complexity/quality-gate claim. Full CI, deployment and production
acceptance were outside this local remediation scope.

## Completion and changed surfaces

All implementation checkboxes in the plan are complete. Following acceptance,
the user selected local integration with `main`. Implementation is captured by
the six scoped commits below on `codex/sonarqube-evidence-remediation`; a final
documentation commit records the evidence. No push, PR, deployment or Sonar
analysis is part of this integration.

Changed surfaces: form facade/defaults/schema/values and mirrored requester
validation; typed create/context/field/persistence helpers; workflow builders and
effect stages; scheduler cancellation; DB constants/UTC/presence assertions;
compatibility ticket-detail controller/formatting/workspace/sections and browser
fixture startup; regression tests, CODEMAP, testing rules, plan and PLANS.

Pre-commit source/test/CODEMAP snapshot: 48 files; aggregate SHA256
`855703da854cdc622cd72539f3339475e9f73937a1073f6288e19e4c5d1d6650`.
Two redundant EOF blank lines were removed after the original snapshot; form
regressions passed again (72 tests), with no behavior change. This is a raw
working-copy provenance digest, not a commit or release artifact; Git normalizes
line endings independently.

Execution rulings, in order: the explicit user implementation request superseded
the original audit-only stage; the mandated checkout was preserved with a local
branch instead of an outside worktree. If either interpretation were wrong, the
cost would be reversing the local diff or moving it into an isolated checkout.
No deferred minor review findings remain. Unreviewed Sonar issues remain outside
the source-verified groups in this plan.

## Local integration commits

| Commit | Message |
|---|---|
| `e8e6b0de999720f0076cbe14869548b3a302e73a` | `fix(forms): validate checkbox conditions and numeric zero` |
| `c5f0dab43d83cbc3932da497568d1472f9d1a440` | `fix(scheduler): preserve parent cancellation during shutdown` |
| `86dd602106b659e3aa066a2c8b174a5b714e3245` | `refactor(tickets): separate typed creation stages` |
| `17d9e7e30ba5ddecf75210d1ff5b67b984b3d437` | `refactor(tickets): separate workflow updates and effects` |
| `9e7cf5c231489ebeb59e777932f9fbcdb71eb4d2` | `refactor(webapp): split compatibility ticket detail controller` |
| `054ed6a45ff9b150355d4072ed4626b60db5d6e8` | `refactor(server): preserve schema and UTC helper contracts` |

Before these commits, source bytes were compared against the reviewed snapshot,
the complete diff and every staged file set were checked, and task-owned paths
were staged explicitly. The fresh pre-commit gate passed 140 backend tests,
529 frontend tests and TypeScript/Vite build; metadata and strict cleanup audit
also passed. Each commit's exact file list and final main SHA are captured in the
local integration receipt at
`artifacts/diagnostics/sonarqube-evidence-remediation-2026-10-01/integration.md`.
Scanner inputs and local validation caches are excluded from the commits.

`git fetch origin` confirmed the local `main` and `origin/main` both remained at
the approved baseline. Integration uses fast-forward only, preserving the exact
verified implementation tree; final backend/frontend/browser/workspace checks
run again on `main`. Previously completed DB/API results remain valid because
integration changes no implementation blobs.
