# Helpdesk Endpoint Integration v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Route `endpoint.context.diagnostic.collect` through the existing
Helpdesk `EndpointPort` to Endpoint Operations API v1, persist a safe local
facade and diagnostic evidence, and prove no legacy agent dispatch occurs.

**Architecture:** A typed fail-closed `EndpointPort` and HTTPS adapter consume
safe Endpoint projections. Helpdesk records local operation/link state in a
short transaction; a reconciler performs idempotent external work and projects
terminal safe results into existing diagnostics. The execution flag selects
either the isolated endpoint path or unchanged legacy behaviour, never both.

**Tech Stack:** Python, Pydantic, aiohttp, SQLAlchemy, Alembic, PostgreSQL,
pytest, React/TypeScript and Playwright browser evidence if workspace UI changes.

## Global Constraints

- Primary repository: `BorisDruzak/helpdesk`; use the actual default branch
  `codex/helpdesk-process-model` as the baseline. Endpoint Platform is
  read-only contract evidence only.
- Create `codex/helpdesk-endpoint-diagnostic-cutover` in a separate worktree
  before implementation. Starting baseline is
  `062703ab291645123e01d3732939c1dfebe43339`; record the actual final branch,
  commit and Alembic head in the execution report.
- Extend `server/domain_ports/endpoint.py`; do not create a parallel port or
  import `endpoint_platform` Python code.
- Default Endpoint state is unavailable and default diagnostic mode is `legacy`.
  In `endpoint` mode never fall back to tools, Helpdesk agent WebSocket or
  DeviceOutbox, and never dual-dispatch.
- Preserve `/ws_ui`, legacy agent runtime/tables/routes and all unrelated
  capabilities. Do not deploy, migrate production, change credentials, or roll
  out agents.
- Use TDD for each implementation task: demonstrate RED, make the minimal
  change, run focused GREEN, inspect the diff, then make the listed atomic
  commit. Do not edit historical Alembic revisions or downgrade.

---

### Task 1: Capture baseline and approve the residual boundary

**Files:**

- Create: `docs/segmentation/HELPDESK_ENDPOINT_RESIDUAL_INVENTORY.md`
- Create: `docs/segmentation/HELPDESK_ENDPOINT_OPERATION_BOUNDARY.md`
- Create: `docs/superpowers/specs/2026-08-17-helpdesk-endpoint-integration-design.md`
- Modify: `PLANS.md`, `docs/ARCHITECTURE_BOUNDARIES.md`, relevant CODEMAP only if implementation moves entrypoints
- Test: `server/tests/test_segmentation_docs.py` only if this project already validates the new documents

**Interfaces:** Produces the non-runtime ownership, route, security, rollback,
and residual-deletion record consumed by every later task.

- [ ] **Step 1: Capture immutable pre-change evidence**

Run:

```powershell
.\scripts\bootstrap_shell_utf8.ps1
git rev-parse HEAD
git status --short
git remote show origin
python scripts/task_intake.py --task "Helpdesk Endpoint diagnostic integration"
python scripts/build_context_pack.py --topic "EndpointPort diagnostics operations cutover"
```

Record the actual default branch, Alembic head, registered HTTP/WS routes,
existing operation statuses, and diagnostic execution targets. Inspect Endpoint
Operations API v1, committed schema/DTO sources, and both repositories with
GitNexus before source-level expansion.

- [ ] **Step 2: Verify the documentation boundary**

```powershell
python scripts/verify_workspace.py
git diff --check
```

Expected: documentation is UTF-8, linked files exist, and no runtime behaviour
or route changes are present.

- [ ] **Step 3: Commit**

```powershell
git add PLANS.md docs/segmentation/HELPDESK_ENDPOINT_RESIDUAL_INVENTORY.md docs/segmentation/HELPDESK_ENDPOINT_OPERATION_BOUNDARY.md docs/superpowers/specs/2026-08-17-helpdesk-endpoint-integration-design.md docs/superpowers/plans/2026-08-17-helpdesk-endpoint-integration.md
git commit -m "docs: define Helpdesk Endpoint integration boundary"
```

### Task 2: Expand the existing EndpointPort contracts

**Files:**

- Modify: `server/domain_ports/endpoint.py`, `server/domain_ports/__init__.py`, `server/domain_ports/unavailable.py`, `server/domain_ports/container.py`, `server/config.py`
- Test: `server/tests/test_endpoint_port_contracts.py`, existing domain-port tests

**Interfaces:** Produces frozen Pydantic opaque refs, safe projections, and
`EndpointPort.availability()`, exact device/capability reads, idempotent create,
exact read, and bounded list methods for only `context.diagnostic.collect`.

- [ ] **Step 1: Write failing contract tests**

Cover immutable/extra-field rejection; 128-character ref bound; strict safe-code
pattern; aware dates; allowed availability outcomes; fixed capability; bounded
projection collections/results; rejected raw fields, arbitrary capability/reason,
malformed processes, and oversized excerpts.

- [ ] **Step 2: Run RED**

```powershell
python -m pytest server/tests/test_endpoint_port_contracts.py -q --noconftest
```

Expected: failure because only `EndpointAvailability` and `availability()`
exist.

- [ ] **Step 3: Add minimal typed contract and configuration**

Use frozen Pydantic models with `ConfigDict(extra="forbid", frozen=True)`.
Keep external values opaque; never normalize, UUID-parse, or case-fold them.
Make `UnavailableEndpointPort` provide every new method as a typed unavailable
outcome. Add validated configuration for Endpoint port mode, HTTPS base origin,
CA path, bearer presence, bounded timeout, and
`ENDPOINT_DIAGNOSTIC_EXECUTION_MODE=legacy|endpoint`. Reject unknown modes.

- [ ] **Step 4: Run GREEN and commit**

```powershell
python -m pytest server/tests/test_endpoint_port_contracts.py server/tests/test_domain_ports.py -q --tb=short
python -m compileall -q server/domain_ports
git add server/domain_ports server/config.py server/tests/test_endpoint_port_contracts.py
git commit -m "feat: expand Helpdesk EndpointPort contracts"
```

### Task 3: Add the external Endpoint HTTP adapter

**Files:**

- Create: `server/endpoint_adapter/__init__.py`, `server/endpoint_adapter/http.py`
- Modify: `server/domain_ports/container.py`, `server/config.py`
- Test: `server/tests/test_endpoint_http_adapter.py`

**Interfaces:** Produces `ExternalEndpointHttpAdapter` composed only when
configuration is complete and exposing safe versioned Endpoint API projections.

- [ ] **Step 1: Write failing transport tests**

Exercise valid availability/device/capability/read/list response, create `201`,
replay `200`, and `401/403/404/409/422/429/5xx/timeout/malformed JSON/extra
fields/correlation mismatch`. Assert redirects/off-origin redirects fail; service
bearer, raw body and result excerpts never enter logs.

- [ ] **Step 2: Run RED**

```powershell
python -m pytest server/tests/test_endpoint_http_adapter.py -q --noconftest
```

- [ ] **Step 3: Implement transport isolation**

Use HTTPS, configured internal CA and bounded aiohttp timeout. Send a service
bearer only in the authorization header; accept only exact expected origins,
methods, schemas and correlation. Map every remote outcome to a typed safe port
result. Do not add Helpdesk HTTP routes, foreign imports, DB access, or logging
of secrets/content.

- [ ] **Step 4: Run GREEN and commit**

```powershell
python -m pytest server/tests/test_endpoint_http_adapter.py server/tests/test_endpoint_port_contracts.py -q --tb=short
git add server/endpoint_adapter server/domain_ports/container.py server/config.py server/tests/test_endpoint_http_adapter.py
git commit -m "feat: add external Endpoint HTTP adapter"
```

### Task 4: Persist verified device and external-operation references

**Files:**

- Create: `server/app/db/migrations/versions/20260817_135_endpoint_operation_links.py`, `server/app/services/endpoint_device_reference_service.py`, `server/app/services/endpoint_operation_bridge.py`
- Modify: `server/app/db/models.py`, ticket creation/enrichment service, `server/app/repos/operations_repo.py`
- Test: `server/tests/test_endpoint_device_reference_service.py`, `server/tests/test_endpoint_operation_bridge.py`, migration contract tests

**Interfaces:** Produces nullable ticket `endpoint_device_ref`/immutable snapshot
and an `EndpointOperationLink` with unique local operation key, unique opaque
external reference once bound, deterministic idempotency key, lease/retry and
evidence metadata.

- [ ] **Step 1: Write failing persistence tests**

Prove exact existing ref is used; only server verification persists a matching
ref/snapshot; not-found/unavailable/mismatch persist nothing; browser input
cannot set the ref; ticket creation works while Endpoint is down. Prove facade
operation/link/session/step are one local transaction, idempotent retry returns
the same local operation, conflicts reject, and no remote HTTP/outbox/WebSocket
call occurs in the transaction.

- [ ] **Step 2: Run RED**

```powershell
python -m pytest server/tests/test_endpoint_device_reference_service.py server/tests/test_endpoint_operation_bridge.py -q --tb=short
```

- [ ] **Step 3: Implement additive persistence**

Use one forward-only revision after actual head 134. Add nullable ticket fields,
index `endpoint_device_ref`, and `endpoint_operation_links`; no Endpoint FK
and no legacy-table deletion. Build immutable JSON only from an exact Endpoint
projection. Generate stable idempotency from canonical Helpdesk request identity,
not browser data; retain the no-remote-inside-transaction rule.

- [ ] **Step 4: Run GREEN and commit**

```powershell
python -m pytest server/tests/test_endpoint_device_reference_service.py server/tests/test_endpoint_operation_bridge.py server/tests/test_migration_schema_contract.py -q --tb=short
git add server/app/db/models.py server/app/db/migrations/versions server/app/services/endpoint_device_reference_service.py server/app/services/endpoint_operation_bridge.py server/app/repos/operations_repo.py server/tests/test_endpoint_device_reference_service.py server/tests/test_endpoint_operation_bridge.py server/tests/test_migration_schema_contract.py
git commit -m "feat: persist Endpoint device and operation references"
```

### Task 5: Reconcile Endpoint operations into Helpdesk diagnostics

**Files:**

- Create: `server/app/services/endpoint_operation_reconciler.py`
- Modify: `server/app/services/operation_service.py`, `server/app/repos/operations_repo.py`, `server/diagnostics/evidence.py`, `server/diagnostics/sessions.py`, server runtime composition
- Test: `server/tests/test_endpoint_operation_reconciler.py`

**Interfaces:** Consumes unbound/active links and projects Endpoint status to
existing `Operation`, `DiagnosticStep`, `DiagnosticSession`, and exactly-once
`DiagnosticEvidence`.

- [ ] **Step 1: Write failing reconciliation tests**

Cover create-pending to remote create; `201` and replay `200`; crash between
remote create and local bind; lease exclusion; retry/backoff; terminal
auth/contract failure; full status map; terminal immutability; no duplicate
evidence/UI publication; ticket status unchanged; bounded redaction/persistence
of success fields.

- [ ] **Step 2: Run RED**

```powershell
python -m pytest server/tests/test_endpoint_operation_reconciler.py -q --tb=short
```

- [ ] **Step 3: Implement safe asynchronous reconciliation**

Acquire/renew a link lease in short DB transactions, invoke Endpoint outside
them, bind stable external refs, and optimistically project only legal
transitions. Retry only typed retryable transport outcomes with bounded backoff;
auth/contract errors become terminal. Redact again before any evidence/API
projection. Create evidence once by the external source pair, then publish only
after commit.

- [ ] **Step 4: Run GREEN and commit**

```powershell
python -m pytest server/tests/test_endpoint_operation_reconciler.py server/tests/test_diagnostic_layer.py server/tests/test_operation_service.py -q --tb=short
git add server/app/services/endpoint_operation_reconciler.py server/app/services/operation_service.py server/app/repos/operations_repo.py server/diagnostics/evidence.py server/diagnostics/sessions.py server/server.py server/tests/test_endpoint_operation_reconciler.py
git commit -m "feat: reconcile Endpoint operations into Helpdesk diagnostics"
```

### Task 6: Route the Endpoint diagnostic capability through EndpointPort

**Files:**

- Create: `server/diagnostics/providers/endpoint_platform.py`
- Modify: `server/diagnostics/capability_models.py`, `server/diagnostics/capability_registry.py`, `server/diagnostics/execution_router.py`, `server/diagnostics/readiness.py`, `server/diagnostics/handlers.py`, `server/diagnostics/providers/__init__.py`
- Test: `server/tests/test_endpoint_diagnostic_provider.py`

**Interfaces:** Produces the single external Helpdesk capability and returns
asynchronous `202` local facade information when `endpoint_operation` is chosen.

- [ ] **Step 1: Write failing provider/readiness tests**

Assert the capability appears only in endpoint mode with provider/type
`endpoint_platform`, risk low, no side effects/consent, external source, and an
empty object parameter schema. Assert empty browser params only; configured,
unavailable, mapping-missing and disabled-by-policy readiness; local queued
response; endpoint safe result evidence; and unchanged old diagnostics.

- [ ] **Step 2: Run RED**

```powershell
python -m pytest server/tests/test_endpoint_diagnostic_provider.py -q --tb=short
```

- [ ] **Step 3: Implement the isolated provider and router branch**

Add `endpoint_operation` to target vocabulary with execution kind `operation`.
Map the Helpdesk ID only to external `context.diagnostic.collect`; do not alias
`diag.logs.collect`. Have the provider authorize/resolve locally and use the
bridge, returning `202` without terminal waiting. It must not call ToolService,
agent online checks, websocket protocol, DeviceOutbox, or `pc_agent`.

- [ ] **Step 4: Run GREEN and commit**

```powershell
python -m pytest server/tests/test_endpoint_diagnostic_provider.py server/tests/test_diagnostic_layer.py server/tests/test_diagnostic_capabilities.py -q --tb=short
git add server/diagnostics/providers/endpoint_platform.py server/diagnostics/providers/__init__.py server/diagnostics/capability_models.py server/diagnostics/capability_registry.py server/diagnostics/execution_router.py server/diagnostics/readiness.py server/diagnostics/handlers.py server/tests/test_endpoint_diagnostic_provider.py
git commit -m "feat: route Endpoint diagnostic capability through EndpointPort"
```

### Task 7: Enforce cutover guards and regression boundaries

**Files:**

- Create: `server/tests/test_endpoint_diagnostic_cutover_guards.py`
- Modify: import-boundary check/script only if an existing guard framework is extended
- Test: all six Endpoint test modules from Tasks 2–6

**Interfaces:** Produces AST/runtime proof that the new Endpoint path cannot
depend on the retained legacy agent dispatch stack.

- [ ] **Step 1: Write failing guards**

Forbid imports from `websocket.protocol`, `websocket.agent_handler`,
`state_manager`, `device_outbox_repo`, `tools.service`, `pc_agent`, agent
auth/token modules and Remote Assist runtime in `server/endpoint_adapter/**`,
`server/app/services/endpoint_*`, and the Endpoint provider. In endpoint mode,
patch ToolService, websocket enqueue/send and DeviceOutbox enqueue to raise; the
capability must still create its local facade. Verify legacy mode retains current
behaviour and `/ws_ui` remains registered.

- [ ] **Step 2: Run RED, add exact guards, then run GREEN**

```powershell
python -m pytest server/tests/test_endpoint_diagnostic_cutover_guards.py -q --tb=short
python -m pytest server/tests/test_endpoint_port_contracts.py server/tests/test_endpoint_http_adapter.py server/tests/test_endpoint_device_reference_service.py server/tests/test_endpoint_operation_bridge.py server/tests/test_endpoint_operation_reconciler.py server/tests/test_endpoint_diagnostic_provider.py server/tests/test_endpoint_diagnostic_cutover_guards.py -q --tb=short
```

Scope guards only to new Endpoint paths, not the entire legacy repository.
Endpoint flag errors must be explicit and fail closed; automatic mode, silent
fallback, duplicate dispatch, and duplicate session/operation/evidence are
forbidden.

- [ ] **Step 3: Commit**

```powershell
git add server/tests/test_endpoint_diagnostic_cutover_guards.py scripts/check_domain_import_boundaries.py
git commit -m "test: guard Endpoint diagnostics from legacy agent dispatch"
```

### Task 8: Present safe Endpoint diagnostic state, only if the workspace changes

**Files:**

- Modify: relevant `server/web_api/dto/support.py`, support handler/projection and `webapp/src/features/diagnostics/**` or current support workspace files
- Test: relevant server support DTO/API tests and webapp diagnostics tests

**Interfaces:** Consumes only safe local operation/source projections and renders
the approved labels/messages; it never consumes Endpoint secrets or raw data.

- [ ] **Step 1: Write RED DTO/UI tests**

Test source `Endpoint Platform`, state labels, unavailable/mapping-missing and
offline queued copy, permission-gated opaque ref, and absence of bearer/base
URL/CA/raw command/raw response/credentials/WSS/internal errors.

- [ ] **Step 2: Implement minimal presentation and verify**

```powershell
python -m pytest server/tests/test_web_support_api.py -q --tb=short
python scripts/bootstrap_web_toolchain.py
pnpm --dir webapp test
pnpm --dir webapp build
```

Reuse the existing diagnostics/support workspace; do not redesign it. Run the
project browser workflow against the changed workspace and retain screenshot,
console, and network evidence.

- [ ] **Step 3: Commit only when UI source changed**

```powershell
git add server/web_api webapp/src server/tests
git commit -m "webapp: present Endpoint diagnostic operation state"
```

### Task 9: Complete documentation, migration rehearsal, and acceptance record

**Files:**

- Modify: `PLANS.md`, `docs/ARCHITECTURE_BOUNDARIES.md`, relevant `server/docs/CODEMAP.md`, `docs/segmentation/HELPDESK_ENDPOINT_OPERATION_BOUNDARY.md`
- Create: acceptance evidence/report under the repository's established documentation location
- Test: workspace verifier, migration tests, docs drift check

**Interfaces:** Produces auditable acceptance evidence: migration revision,
contract/API routes, config, capability IDs, status mapping, idempotency/device
reference/evidence strategies, no-legacy-dispatch proof, residual risk, and
rollback procedure.

- [ ] **Step 1: Rehearse additive migration**

Verify actual `alembic heads`, upgrade from previous head, clean database
upgrade, and representative clone rehearsal. Confirm nullable ticket columns,
no unnecessary table rewrite, link uniqueness/indexes, no production run, and
application-release rollback rather than downgrade.

- [ ] **Step 2: Run affected verification**

```powershell
python scripts/verify_workspace.py
python -m compileall -q server
git diff --check
```

Run the focused Endpoint suite plus diagnostics, operations, tickets,
support/requester API, `/ws_ui`, RegistryPort and migration regressions
required by `docs/TESTING_RULES.md`. Record executed results and every skipped
check; never claim a skipped DB/browser/stand check is green.

- [ ] **Step 3: Record rollback and commit**

Document: stop new diagnostics; let or record active external operations; switch
to legacy; normal verified deploy; verify no new links; reconcile existing links
read-only to terminal; never send legacy replacements. List all legacy
components still retained from the residual inventory.

```powershell
git add PLANS.md docs/ARCHITECTURE_BOUNDARIES.md docs/segmentation server/docs/CODEMAP.md
git commit -m "docs: record Helpdesk Endpoint integration acceptance"
```

## Plan self-review

- Scope coverage: contract, secure adapter, verified device mapping, additive
  persistence, asynchronous idempotent reconciliation, provider/router,
  fail-closed flag, no-legacy guards, optional UI, migration and acceptance are
  each represented by an independently verifiable task.
- Explicitly excluded: generic agent cutover, module/recipe/update/consent/
  Remote Assist migration, Registry/Knowledge changes, production action and
  legacy deletions.
- Endpoint route/DTO details and actual Alembic revision must be confirmed
  against the read-only contract and current branch immediately before the
  corresponding task; this plan does not fabricate them.

## Execution handoff

Start in a separate worktree and execute Tasks 2–7 sequentially because they
share port contracts, persistence and lifecycle semantics. UI work can begin
only after the safe support projection stabilizes. Before a pull request, run
the project code-review and documentation-drift workflows; create a draft PR
only after all required local checks are evidenced.
