# Helpdesk–Endpoint Integration Hardening v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the Endpoint Operations API v1 consumer/provider boundary reproducible, fail closed on schema and correlation drift, persist only verified device mappings, and prove one safe terminal diagnostic evidence through real API, WSS, and headless-agent paths.

**Architecture:** Endpoint owns the canonical OpenAPI provider and WSS-only execution. Helpdesk owns a strict HTTP consumer adapter, locally authorized facade operation and durable reconciliation. The repositories have no production runtime import path; only the acceptance module receives a provider checkout through `ENDPOINT_PLATFORM_REPO`.

**Tech Stack:** Python, FastAPI, Pydantic, SQLAlchemy/Alembic, PostgreSQL, SQLite only for provider-local test isolation where explicitly stated, pytest, GitHub Actions, real Gateway WSS test agent.

**Spec:** `endpoint_platform/docs/superpowers/specs/2026-08-20-helpdesk-integration-hardening-v1-design.md` at Endpoint branch `codex/helpdesk-integration-hardening-v1`.

## Global Constraints

- Baselines are Endpoint `94da3b61faa2761b093a10e09dd69d54149da9a4` and Helpdesk `de1bf33d68646f8d86051016bf806dacf1d311cb`; do not start from a divergent local Helpdesk checkout.
- Branches/worktrees are Endpoint `codex/helpdesk-integration-hardening-v1` and Helpdesk `codex/endpoint-integration-hardening-v1`.
- Endpoint OpenAPI is canonical. Keep wire DTOs in `server/endpoint_adapter/` separate from `server/domain_ports/endpoint.py` internal DTOs; both reject extras.
- No Helpdesk runtime import of Endpoint and no Endpoint runtime import of Helpdesk. Cross-repository imports are allowed solely in `server/tests/acceptance/test_endpoint_operations_v1_acceptance.py` when `ENDPOINT_PLATFORM_REPO` is explicitly set.
- Preserve legacy Helpdesk agent runtime and existing migrations. Do not implement fallback, dual dispatch, ToolService, Helpdesk WebSocket, or DeviceOutbox delivery for the endpoint capability.
- Do not deploy, run production migrations, mutate credentials/TLS/configuration, restart services, roll out agents, force-push, or rewrite historical migrations. All database work is disposable test-only.
- Use test-driven development: make each listed focused test fail, implement the smallest correct behavior, run its green command, inspect `git diff --check`, and stage only listed task files.
- GitHub acceptance uses the lock's normal public/readable provider repository with ordinary `GITHUB_TOKEN`; do not add a separate secret, source archive, fake server, checkout cache, or absolute author path.

---

### Task 1: Freeze and validate the provider contract

**Files:**

- Endpoint modify: `endpoint_contracts/operations.py`, `endpoint_server/operations/routes.py`, `endpoint_server/main.py`, `contracts/openapi/endpoint-platform-v1.yaml`
- Endpoint create/modify: `contracts/jsonschema/endpoint-device-summary-v1.json`, `contracts/jsonschema/endpoint-device-capabilities-v1.json`, `contracts/jsonschema/endpoint-operation-v1.json`, generated contract artifacts, `tests/contracts/test_endpoint_operations_contract.py`, `tests/operations/test_operation_routes.py`, `tests/gateway/test_endpoint_operation_delivery.py`
- Helpdesk later modify: `integration/endpoint_contract.lock.json`

**Interfaces:** `GET /api/v1/devices/{device_id}`, versioned capabilities, `POST /api/v1/devices/{device_id}/operations`, and `GET /api/v1/operations/{operation_id}` use the OpenAPI-defined envelope. Operation response remains `data.operation` plus `data.result`.

- [ ] **Step 1: Add provider RED tests**

Test a valid `EndpointDeviceSummaryV1`, exact device/capability IDs, the response schema/version, nested operation/result on create and read, and generated-artifact parity. Add a Gateway assertion that its command contains only Endpoint operation data and no Helpdesk ticket, actor, requester, diagnostic-session, correlation, or credential fields.

- [ ] **Step 2: Run provider RED**

```powershell
python -m pytest tests/contracts/test_endpoint_operations_contract.py tests/operations/test_operation_routes.py tests/gateway/test_endpoint_operation_delivery.py -q
```

Expected: missing device read/versioned capability and schema assertions fail before provider implementation.

- [ ] **Step 3: Implement provider contract atomically**

Add `EndpointDeviceSummaryV1`, exact device read, versioned capability response, and the canonical OpenAPI/JSON schemas. Keep delivery selected only as `gateway_wss`; do not enrich WSS payloads from caller HTTP metadata. Regenerate every repository-tracked contract artifact.

- [ ] **Step 4: Verify and commit Endpoint provider contract**

```powershell
python -m pytest tests/contracts -q
python -m pytest tests/operations -q
python -m pytest tests/gateway -q
python tools/contracts/generate_contract_artifacts.py
git diff --exit-code -- contracts
git diff --check
git add endpoint_contracts endpoint_server/operations contracts tests/contracts tests/operations tests/gateway tools/contracts
git commit -m "feat(api): publish Helpdesk Operations v1 contract"
```

Expected: test suites pass and generation leaves no diff. Push this Endpoint commit and record its full SHA before changing the Helpdesk lock.

### Task 2: Enforce safe correlation headers at the provider

**Files:**

- Endpoint create: `endpoint_server/http/correlation.py`
- Endpoint modify: `endpoint_server/main.py`, `endpoint_server/operations/routes.py`, OpenAPI route/header definitions and generated artifacts
- Endpoint test: `tests/operations/test_operation_routes.py`, `tests/contracts/test_endpoint_operations_contract.py`, provider error-route tests

**Interfaces:** Valid `X-Correlation-ID` matches `^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$`; it is echoed byte-for-byte only as a response header and never becomes JSON, authorization state, persistent operation data, or an agent command field.

- [ ] **Step 1: Add RED examples**

Cover every canonical route and normal/error response with a valid header; missing behavior according to the route contract; invalid/control/non-ASCII/oversized values yielding safe `422` without reflection; and proof correlation does not affect authorization or persisted operation/WSS command data.

- [ ] **Step 2: Run RED, implement central validation, then run GREEN**

```powershell
python -m pytest tests/operations/test_operation_routes.py tests/contracts/test_endpoint_operations_contract.py tests/gateway/test_endpoint_operation_delivery.py -q
python tools/contracts/generate_contract_artifacts.py
git diff --exit-code -- contracts
```

Use one request/response helper or middleware instead of route-by-route copies. Do not log invalid supplied header values.

- [ ] **Step 3: Commit Endpoint correlation hardening**

```powershell
git add endpoint_server/http endpoint_server/main.py endpoint_server/operations contracts tests/operations tests/contracts tests/gateway tools/contracts
git commit -m "fix(api): validate safe correlation headers"
```

### Task 3: Lock and reproduce the external provider in Helpdesk CI

**Files:**

- Helpdesk modify: `integration/endpoint_contract.lock.json`, `server/tests/acceptance/test_endpoint_operations_v1_acceptance.py`, pytest markers/configuration
- Helpdesk create/modify: `scripts/validate_endpoint_contract_lock.py`, `.github/workflows/endpoint-contract-acceptance.yml`, lock-validator and acceptance bootstrap tests

**Interfaces:** The lock records provider repository, exact provider commit, OpenAPI relative path and SHA-256 digest. `ENDPOINT_PLATFORM_REPO` is the only local injection point; ordinary pytest skips the cross-repository module when absent.

- [ ] **Step 1: Write lock/bootstrap RED tests**

Assert: missing variable cleanly skips; a checkout at a different commit fails; changed OpenAPI bytes fail; an exact checkout succeeds; no fixture uses fixed Windows/author paths; and CI obtains the repo/ref from the lock without a custom secret.

- [ ] **Step 2: Update lock only after Endpoint provider push**

Set `provider_commit` to the just-pushed Endpoint feature commit and save the digest calculated from its committed OpenAPI file. The validator must use `git -C <root> rev-parse HEAD` and hash raw bytes, not a parsed/reformatted YAML representation.

- [ ] **Step 3: Implement CI checkout and verify locally**

```powershell
python scripts/validate_endpoint_contract_lock.py --provider-root $env:ENDPOINT_PLATFORM_REPO
python -m pytest server/tests/acceptance/test_endpoint_operations_v1_acceptance.py -m cross_repo_acceptance -q --tb=short
git diff --check
```

CI uses `actions/checkout` for Helpdesk and a second normal checkout of the lock's public/readable Endpoint repository/ref. It fails explicitly if checkout cannot authenticate; it must not replace provider routes with mocks.

- [ ] **Step 4: Commit Helpdesk reproducibility work**

```powershell
git add integration/endpoint_contract.lock.json scripts/validate_endpoint_contract_lock.py .github/workflows/endpoint-contract-acceptance.yml server/tests/acceptance/test_endpoint_operations_v1_acceptance.py pytest.ini
git commit -m "ci: verify locked Endpoint provider contract"
```

### Task 4: Strictly translate Endpoint wire envelopes in the consumer adapter

**Files:**

- Helpdesk modify: `server/endpoint_adapter/http.py`, `server/endpoint_adapter/__init__.py`, `server/domain_ports/endpoint.py`, `server/domain_ports/container.py`
- Helpdesk test: `server/tests/test_endpoint_http_adapter.py`, `server/tests/test_endpoint_port_contracts.py`

**Interfaces:** External Pydantic DTOs parse Endpoint envelopes; internal `EndpointPort` DTOs expose safe, bounded projections. Adapter calls use the exact routes/methods in Task 1 and compare response `X-Correlation-ID` to the request.

- [ ] **Step 1: Write consumer RED tests**

Use the current real Endpoint envelope fixtures for device read, capabilities, create `201`, replay `200`, conflict `409`, and operation read. Reject extra envelope/data/operation/result fields, wrong schema/version, response ID mismatch, absent/mismatched correlation, malformed nested result, and terminal `succeeded` with no safe result.

- [ ] **Step 2: Run RED**

```powershell
python -m pytest server/tests/test_endpoint_http_adapter.py server/tests/test_endpoint_port_contracts.py -q --tb=short
```

- [ ] **Step 3: Implement fail-closed mapping**

Keep wire and internal classes distinct. Validate exact known keys before projection, never pass raw response dicts onward, and map only documented safe results. Do not use correlation for authorization or place it in request JSON. Return typed safe remote failures rather than implicit retries/fallback.

- [ ] **Step 4: Run GREEN and commit**

```powershell
python -m pytest server/tests/test_endpoint_http_adapter.py server/tests/test_endpoint_port_contracts.py -q --tb=short
python -m compileall -q server/endpoint_adapter server/domain_ports
git add server/endpoint_adapter server/domain_ports server/tests/test_endpoint_http_adapter.py server/tests/test_endpoint_port_contracts.py
git commit -m "fix(endpoint): enforce strict Operations API projections"
```

### Task 5: Require audited verified device mapping before readiness

**Files:**

- Helpdesk modify: `server/app/services/endpoint_device_reference_service.py`, `server/diagnostics/handlers.py`, `server/routes.py`, relevant request/response DTO module, existing audit integration
- Helpdesk test: `server/tests/test_endpoint_device_reference_service.py`, API/RBAC/readiness/audit tests

**Interfaces:** Admin-only `PUT /api/admin/tickets/{ticket_id}/endpoint-device-mapping` accepts strict `EndpointDeviceMappingRequestV1`: `endpoint_device_ref` 1–128, `replace`, nullable exact expected previous ref, and `reason` 8–256 without control characters. Unknown fields are invalid.

- [ ] **Step 1: Add RED mapping and authorization tests**

Prove readiness calls `EndpointDeviceReferenceService` first; no hostname/IP/MAC matching exists; administrator mapping verifies the exact non-retired provider device then persists a redacted snapshot; anonymous is `401`, non-admin is `403`, retired is `409 ENDPOINT_DEVICE_RETIRED` without storage/audit success. Prove equal replay is idempotent/no meaningless audit and replacement requires `replace=true`, exact expected prior ref and reason.

- [ ] **Step 2: Run RED and implement exact-reference workflow**

```powershell
python -m pytest server/tests/test_endpoint_device_reference_service.py server/tests/test_endpoint_readiness.py server/tests/test_admin_ticket_routes.py -q --tb=short
```

Verify upstream outside the short persistence transaction, lock/re-read the ticket before save, retain only safe snapshot fields, and write existing audit records with previous/new refs, reason, request correlation and result. Never derive a ref from network identity.

- [ ] **Step 3: Run GREEN and commit**

```powershell
python -m pytest server/tests/test_endpoint_device_reference_service.py server/tests/test_endpoint_readiness.py server/tests/test_admin_ticket_routes.py -q --tb=short
git add server/app/services/endpoint_device_reference_service.py server/diagnostics/handlers.py server/routes.py server/tests
git commit -m "fix(endpoint): audit verified device mapping changes"
```

### Task 6: Preserve actor-scoped idempotency and recover each reconciliation claim

**Files:**

- Helpdesk create: forward-only migration `server/app/db/migrations/versions/*_137_*caller_idempotency*.py`
- Helpdesk modify: operation/link models and repositories, `server/app/services/endpoint_operation_reconciler.py`, reconciler runner, UI publication boundary
- Helpdesk test: `server/tests/test_endpoint_operation_reconciler.py`, operation repository/idempotency/migration tests, diagnostic evidence tests

**Interfaces:** Migration 137 is additive and actor-scopes caller idempotency. Store gains a compare-and-set failure method equivalent to:

```python
async def record_unexpected_failure(
    *, claim: EndpointReconcileClaim, error_code: str, next_attempt_at: datetime
) -> bool: ...
```

It locks link/operation, verifies the lease token and non-terminal state, records only `endpoint_reconcile_unexpected`, increments bounded attempts, clears lease and schedules bounded retry. `False` means stale and causes no mutation.

- [ ] **Step 1: Add RED idempotency and lifecycle tests**

Test same actor plus canonical caller request gives one facade operation; a semantic mismatch conflicts; another actor does not inherit the caller key. Test one-claim-at-a-time (or renewal/recheck immediately before remote call), stale lease no-op, isolated unexpected exception, safe failure persistence, retry ceiling, lease release, continued runner, safe log event, no duplicate evidence/remote create, and post-commit UI publication failure leaving committed state untouched.

- [ ] **Step 2: Run RED**

```powershell
python -m pytest server/tests/test_endpoint_operation_reconciler.py server/tests/test_endpoint_operation_repository.py server/tests/test_endpoint_operation_migration.py server/tests/test_diagnostic_evidence.py -q --tb=short
```

- [ ] **Step 3: Implement bounded claim recovery**

Replace every relevant `except Exception: pass` with per-claim safe handling. Log `endpoint_reconcile_claim_failed` only with operation ID, attempt number, retry time, worker/lease-safe identifier and exception class/fingerprint—never body, header, token, ticket data or exception text. Runner-level errors log safely, wait bounded time and continue. UI publication is explicitly post-commit and never changes durable operation/link state.

- [ ] **Step 4: Migration and GREEN verification**

```powershell
python -m pytest server/tests/test_endpoint_operation_reconciler.py server/tests/test_endpoint_operation_repository.py server/tests/test_endpoint_operation_migration.py server/tests/test_diagnostic_evidence.py -q --tb=short
python -m compileall -q server
git diff --check
```

Perform disposable PostgreSQL upgrade-from-prior-head and clean-chain rehearsal; do not run Alembic on production. Commit migration separately from service tests if the repository's migration convention requires it.

- [ ] **Step 5: Commit**

```powershell
git add server/app/db/migrations/versions server/app/db server/app/repos server/app/services/endpoint_operation_reconciler.py server/tests
git commit -m "fix(endpoint): recover reconciler claims safely"
```

### Task 7: Prove cross-repository vertical acceptance and legacy-dispatch absence

**Files:**

- Helpdesk modify: `server/tests/acceptance/test_endpoint_operations_v1_acceptance.py`
- Helpdesk create/modify: focused import-boundary test such as `server/tests/test_endpoint_diagnostic_cutover_guards.py`, CI workflow if needed
- Endpoint test support only: existing real app/gateway fixtures; no mocked provider routes

**Interfaces:** Starts actual `endpoint_server.main.create_app()`, uses real Helpdesk adapter and service credentials, temporary provider backend and temporary Helpdesk PostgreSQL with full migration chain, Gateway WSS and headless agent.

- [ ] **Step 1: Add RED acceptance cases**

Prove device read, capability read, create `201`, exact replay `200`, conflict `409`, read operation, correlation echo and all strict negative adapter cases. Then create Helpdesk facade operation and drive it to a safe terminal result with exactly one `DiagnosticEvidence`. Patch Helpdesk ToolService/WebSocket/DeviceOutbox to raise and assert no call; inspect WSS command fields to ensure no Helpdesk identifiers/correlation/credentials crossed the boundary.

- [ ] **Step 2: Execute local true-provider acceptance**

```powershell
$env:ENDPOINT_PLATFORM_REPO = 'C:\Users\admin-2\Documents\endpoint\.worktrees\codex-helpdesk-integration-hardening-v1'
python scripts/validate_endpoint_contract_lock.py --provider-root $env:ENDPOINT_PLATFORM_REPO
python -m pytest server/tests/acceptance/test_endpoint_operations_v1_acceptance.py -m cross_repo_acceptance -q --tb=short
Remove-Item Env:ENDPOINT_PLATFORM_REPO
python -m pytest server/tests/acceptance/test_endpoint_operations_v1_acceptance.py -q --tb=short
```

Expected: full acceptance passes with exact lock; the final normal pytest command reports the acceptance test skipped, not imported/failed. Record provider backend type separately from Helpdesk PostgreSQL chain—if provider PostgreSQL is required by a later provider architecture change, add a dedicated provider test gate rather than disguising SQLite coverage.

- [ ] **Step 3: Run broader focused suites and commit**

```powershell
python scripts/verify_workspace.py
python -m pytest server/tests/test_endpoint_http_adapter.py server/tests/test_endpoint_device_reference_service.py server/tests/test_endpoint_operation_reconciler.py server/tests/test_endpoint_diagnostic_cutover_guards.py -q --tb=short
python -m compileall -q server scripts
git diff --check
git add server/tests/acceptance server/tests/test_endpoint_diagnostic_cutover_guards.py .github/workflows
git commit -m "test(endpoint): harden cross-repository operation acceptance"
```

### Task 8: Update documentation, final locks, PRs and evidence

**Files:**

- Endpoint modify: `docs/segmentation/HELPDESK_ENDPOINT_OPERATIONS_CONTRACT_V1.md`, `docs/segmentation/ENDPOINT_HELPDESK_BOUNDARY.md`, `PLANS.md`, `docs/superpowers/specs/2026-08-20-helpdesk-integration-hardening-v1-design.md`
- Helpdesk modify: `docs/segmentation/HELPDESK_ENDPOINT_OPERATION_BOUNDARY.md`, `server/docs/CODEMAP.md`, `PLANS.md`, `integration/endpoint_contract.lock.json`, this plan

- [ ] **Step 1: Record exact operational contract and results**

Document provider checkout/lock validation, route/schema/correlation rules, admin mapping, migration 137, actor-scoped idempotency, reconciler failure/lease behavior, local/CI acceptance commands, and no-legacy-dispatch proof. State clearly that no production system is changed under this plan.

- [ ] **Step 2: Provider-first integration sequence**

Push Endpoint branch without force; create draft provider PR to `main`; pass provider CI; merge it. Replace Helpdesk lock's feature SHA with the actual Endpoint merge SHA and recomputed OpenAPI digest; rerun Helpdesk local and GitHub cross-repo acceptance. Push Helpdesk branch without force and create draft PR to `codex/helpdesk-process-model`.

- [ ] **Step 3: Final verification and commit(s)**

```powershell
# Endpoint
python -m pytest tests/contracts tests/operations tests/gateway -q
python -m compileall -q endpoint_contracts endpoint_server pc_agent
git diff --check

# Helpdesk
python scripts/verify_workspace.py
python -m pytest server/tests/test_endpoint_http_adapter.py server/tests/test_endpoint_device_reference_service.py server/tests/test_endpoint_operation_reconciler.py -q --tb=short
python -m pytest server/tests/acceptance/test_endpoint_operations_v1_acceptance.py -m cross_repo_acceptance -q --tb=short
git diff --check
```

Use only atomic Conventional Commits, inspect staged diff/status before each, and report full SHA, message, files and executed result. The final report lists starting/ending SHAs, branch/PR URLs, schemas/routes, lock SHA/digest, mapping/idempotency/lease semantics, exact test output, remaining risks, and confirmation of zero production actions.

## Stop Conditions

Stop implementation and report evidence rather than weakening a boundary if any of these occurs:

1. The provider repository cannot be checked out by normal GitHub Actions credentials; do not introduce a secret, fake server, source copy, or cache fallback.
2. OpenAPI/schema/artifact behavior disagrees with implemented provider routes.
3. A consumer projection requires an undocumented remote field or cannot prove correlation/ID equality.
4. A mapping needs hostname/IP/MAC inference, a retired device, or audit bypass.
5. A reconciler fix would erase committed data, reissue a remote create, retain a stale lease, or end the runner.
6. Any endpoint capability path reaches ToolService, Helpdesk WebSocket, DeviceOutbox, or legacy agent dispatch.
7. A step would require production migration, deploy, credential/configuration change, restart, rollout, history rewrite, or force push.

## Plan Self-Review

The tasks cover provider contract/correlation, immutable lock and CI checkout, strict adapter projections, verified mapping/readiness, migration-137 actor idempotency, claimed reconciliation and UI failure isolation, true cross-repo acceptance, documentation and provider-first merge sequencing. The deliberately excluded production and legacy paths remain excluded. Each task has concrete files, interfaces, RED/GREEN checks, and an atomic commit boundary.

