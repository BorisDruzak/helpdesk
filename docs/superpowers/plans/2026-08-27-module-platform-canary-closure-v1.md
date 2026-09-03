# Module Platform Canary Closure v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrate the 15 reviewed Endpoint canary fixes into Endpoint `main`, harden the Helpdesk module-operation reconciler, and close one staging-only Module Platform acceptance run with reversible configuration, credential revocation, redacted off-host evidence, and a Helpdesk acceptance record.

**Architecture:** Endpoint remains the authoritative recipe, parent-operation, child-step, credential and Gateway-WSS provider. Helpdesk remains the ticket-facing BFF, local facade `Operation`, `EndpointOperationLink`, reconciliation worker and bounded `DiagnosticEvidence` owner. Only the four registered HTTPS contracts cross repositories; neither side may use Helpdesk `DeviceOutbox`, `ToolService`, legacy WebSocket or a fallback path.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, SQLAlchemy/Alembic, PostgreSQL, Gateway WSS, pytest, systemd staging release scripts.

**Spec:** `docs/segmentation/MODULE_PLATFORM_BOUNDARY.md`; `docs/superpowers/plans/2026-08-26-endpoint-module-platform-v1.md`; Endpoint `docs/modules/ENDPOINT_MODULE_PLATFORM_DESIGN.md`.

## Global Constraints

- Scope is staging only: `osn-admin@192.168.101.118`, `osn-admin@192.168.101.70`, and `test_agent_win@192.168.101.120`. Never touch production `192.168.100.19`.
- Never log, commit, copy into evidence, or display bearer tokens, passwords, cookies, CA private material, or raw agent output.
- Use reviewed release procedures and systemd units; never patch a deployed release in place and never use direct SQL to manufacture acceptance state.
- Keep `network.canary.check@1.0.0` published and execute exactly one new ticket-run in this closure. Repeated reconciliation is read/reconcile only and must produce no additional provider operation or evidence.
- Rollback means restoring the exact pre-run staging feature-flag configuration and removing access to the scoped credential while retaining the newly deployed mainline releases. Credential revocation is permanent and is verified server-side before its private file is removed.
- Evidence backup is a redacted, integrity-hashed bundle copied from staging to the operator workstation outside the staging host; it is not committed to Git.

## Task 1: Establish exact baselines and integration branches

**Files:**
- Inspect: Endpoint `origin/main`, `codex/windows-ping-oem-module-platform`
- Inspect: Helpdesk `master`, `codex/endpoint-module-workbench-hd2-v1`

- [ ] Bootstrap UTF-8 and record clean worktree status for both repositories.
- [x] Fetch remotes; prove the Endpoint range `origin/main..codex/windows-ping-oem-module-platform` has exactly 15 commits and run a conflict-only merge simulation.
- [ ] Create isolated integration branches from current remote mainlines; merge normally without rebasing or force-pushing. Endpoint is complete; Helpdesk integration remains.
- [ ] Record pre-deploy Endpoint/Helpdesk SHA, Alembic head, service status, published-recipe state, and the eight baseline counters.

## Task 2: Harden module reconciliation before staging use

**Files:**
- Modify: `server/app/services/endpoint_module_operation_reconciler.py`
- Modify: `server/tests/test_endpoint_module_operation_reconciler.py`
- Modify: `server/tests/acceptance/test_endpoint_module_platform_v1.py` only if its lifecycle assertion needs the hardened contract.

- [ ] Write failing tests proving each remote call owns one fresh lease, an unexpected transport exception becomes a redacted retryable commit, terminal operations cannot regress, and a repeated reconcile cannot create a second evidence row.
- [x] Implement one-claim-at-a-time reconciliation, bounded retry scheduling, retry attempt accounting, terminal/monotonic commit guards, and secret-free logging. Keep remote calls outside transactions.
- [x] Preserve the existing exact-once remote idempotency key and evidence uniqueness `(ticket_id, source_type, source_id, kind)`.
- [x] Run `python -m pytest server/tests/test_endpoint_module_operation_reconciler.py server/tests/test_endpoint_module_operation_service.py server/tests/test_endpoint_modules_port_contracts.py server/tests/test_endpoint_modules_http_adapter.py -q`.
- [ ] Run the real cross-repository acceptance fixture: `python -m pytest server/tests/acceptance/test_endpoint_module_platform_v1.py -q`. The exact provider lock now passes; the local Windows fixture is blocked by its stale `example.test` DB-tunnel target, so this gate moves to real isolated staging.

## Task 3: Integrate and verify Endpoint main

**Files:**
- Merge: the 15 reviewed commits listed by `git log --reverse origin/main..codex/windows-ping-oem-module-platform`
- Verify changed canary, packaging, agent-runtime, contracts, operations, Gateway and module suites.

- [x] Merge the 15 commits into a branch based on latest Endpoint `origin/main`, resolve only genuine merge conflicts, and preserve both parents when a merge commit is required.
- [x] Run full Endpoint CI locally: `python -m pytest -q`, `python tools/contracts/generate_contract_artifacts.py --check`, `python -m compileall -q endpoint_contracts endpoint_server pc_agent`, and `git diff --check`.
- [x] Push the verified fast-forwardable result to `origin/main`; verify remote SHA and clean worktree. If `origin/main` advances before push, stop and repeat the safe merge with the new tip.

## Task 4: Integrate Helpdesk hardening and verify its release candidate

**Files:**
- Merge: the verified Helpdesk module branch into the repository mainline selected by its remote default (`origin/HEAD`)
- Create: `docs/verification/2026-08-27-module-platform-canary-closure-v1.md` after acceptance

- [x] Run `python scripts/verify_workspace.py`, affected reconciler/port/BFF tests, and `git diff --check`.
- [x] Review uncommitted impact with GitNexus plus source-level contract checks; update `server/docs/CODEMAP.md` only if routes, contracts, or ownership changed.
- [ ] Push the verified Helpdesk mainline SHA without rewriting history.

## Task 5: Deploy new mainline releases to isolated staging

**Files:**
- Use reviewed staging release scripts and immutable release directories only.

- [ ] Deploy Endpoint and Helpdesk mainline SHAs to their isolated staging paths on `.118`; run migrations through their release procedures and verify exactly one schema head per service.
- [ ] Verify systemd active state, loopback health checks, TLS/CA connectivity from Helpdesk to Endpoint, and the selected Gateway test device connection. Do not change production or legacy service ownership.
- [ ] Create timestamped, root-readable backups of only the two staging environment files before enabling temporary module flags.

## Task 6: Execute one ticket-run and collect deterministic acceptance evidence

**Files:**
- Create outside Git: redacted run bundle under the operator workstation evidence directory.

- [ ] Provision one fresh root-only Helpdesk module credential through the Endpoint provisioner; add it only to the isolated Helpdesk staging environment and enable `ENDPOINT_MODULE_PORT_MODE=external` plus `ENDPOINT_MODULE_EXECUTION_MODE=endpoint` for the run.
- [ ] Select an existing staging ticket with a verified Endpoint device mapping; capture its status and all eight pre-run counters using read-only application queries.
- [ ] Through the Helpdesk ticket route, submit exactly one `network.canary.check@1.0.0` request with a unique idempotency key. Do not call Endpoint directly to create the acceptance operation.
- [ ] Wait for the single remote parent and its three ordered child steps (`dns.resolve`, `network.ping`, `tcp.connect`) to become terminal through Gateway WSS; reconcile until the local facade is terminal.
- [ ] Prove: one new local `Operation`, one new `EndpointOperationLink`, one remote parent, three child steps, one `DiagnosticEvidence`, unchanged `Ticket.status`, and zero deltas for `DeviceOutbox`, `ToolService`, and legacy WebSocket.
- [ ] Run reconciliation again and prove every recorded count and reference remains unchanged.

## Task 7: Roll back run-only access and close evidence

**Files:**
- Create: `docs/verification/2026-08-27-module-platform-canary-closure-v1.md`
- Modify: `PLANS.md`

- [ ] Restore the exact backed-up Endpoint and Helpdesk staging environment files, restart only their staging services, and verify the module path is fail-closed while both releases remain healthy.
- [ ] Revoke the fresh scoped credential through a root-only audited Endpoint procedure, verify it is inactive without printing its bearer, then remove the root-only token file.
- [ ] Produce a redacted evidence manifest with deployed SHAs, schema heads, ticket/operation opaque identifiers, counts, status comparisons, configuration rollback proof, credential-revocation proof, command outcomes, and SHA-256 digest. Copy it off `.118` to the operator workstation outside Git.
- [ ] Write and commit the final Helpdesk acceptance document with evidence digest and backup location, then push it. Update `PLANS.md` Current State, Verification, and Handoff.

## Required acceptance commands

```powershell
# Endpoint full CI (integrated Endpoint worktree)
python -m pytest -q
python tools/contracts/generate_contract_artifacts.py --check
python -m compileall -q endpoint_contracts endpoint_server pc_agent
git diff --check

# Helpdesk hardening and release checks (integrated Helpdesk worktree)
python -m pytest server/tests/test_endpoint_module_operation_reconciler.py server/tests/test_endpoint_module_operation_service.py server/tests/test_endpoint_modules_port_contracts.py server/tests/test_endpoint_modules_http_adapter.py -q
python -m pytest server/tests/acceptance/test_endpoint_module_platform_v1.py -q
python scripts/verify_workspace.py
git diff --check
```

## Execution record — 2026-08-27

- Endpoint `main` is `59b1e7ecd9a9aceb806ae6d93a2b8f0c563413a2`: merge
  `0080722` contains the 15 requested canary commits and `59b1e7e` removes two
  orphaned tests that imported the intentionally excluded Helpdesk `scripts/`
  tree. Full Endpoint CI passed `1970 passed, 36 skipped`.
- Helpdesk reconciler focused/contract tests passed `30 passed`; workspace
  verifier and diff check passed. The provider lock now pins Endpoint `59b1e7e`
  with unchanged verified OpenAPI digest.
- The local real-provider acceptance fails closed at its Windows database tunnel
  bootstrap (`example.test` cannot resolve). No fallback or mock was used; the
  same acceptance assertions remain required against the isolated staging pair.

## Completion criteria

- Both new mainline SHAs are deployed to staging and healthy; no production host was contacted or changed.
- The run proves exactly the eight stated data-plane invariants and a second reconciliation produces no delta.
- The reconciler hardening is covered by focused tests and the full Helpdesk/Endpoint gates pass.
- Feature configuration is restored, the fresh credential is revoked and removed, redacted evidence is stored off-host with a digest, and the final Helpdesk acceptance document is committed and pushed.
