# Endpoint Module Platform v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move declarative diagnostic module authority and typed execution to Endpoint Platform while retaining the Helpdesk legacy module runtime.

**Architecture:** Endpoint owns immutable module versions, validation, recipes, operations, and WSS-delivered typed commands. Helpdesk owns the browser BFF, authorization, facade operation, and safe ticket evidence through a narrow HTTPS port.

**Tech Stack:** Python, Pydantic v2, FastAPI, aiohttp, SQLAlchemy/Alembic, PostgreSQL, Gateway WSS, JavaScript/TypeScript web UI, pytest.

**Spec:** `docs/segmentation/MODULE_PLATFORM_BOUNDARY.md`; Endpoint companion: `docs/modules/ENDPOINT_MODULE_PLATFORM_DESIGN.md`.

## Global Constraints

- No Python, shell, PowerShell, dynamic import, generic invocation, URL/path, or executable field in recipe v1.
- Network probes must be independently fail-closed on server and agent.
- Browser-to-Endpoint direct calls, shared DB/FK, `DeviceOutbox`, `ToolService`, Helpdesk WebSocket, dual dispatch, and automatic fallback are forbidden for endpoint-native modules.
- Module execution flags default disabled; production deployment and credentials are out of scope.
- Existing Alembic revisions are immutable and every schema change has one head.

---

## Current State — 2026-08-27

- Phase-0 design and legacy migration matrix are present in both repositories;
  the matrix keeps legacy source out of Endpoint recipes.
- Endpoint integration source is at `23dca1e` and the Helpdesk HD2 integration
  source is at `0be9bb97`. Both worktrees are clean before this plan update.
- Endpoint verification passed locally: contracts, operations, gateway, modules,
  architecture, packaging and agent runtime/primitives/windows suites reported
  `928 passed, 8 skipped`; generated contract artifacts, compilation and
  `git diff --check` also passed.
- Helpdesk `python scripts/verify_workspace.py` passed. The typed port, BFF,
  facade/reconciler, safe evidence model and distinct Endpoint Recipe Workbench
  are implemented and documented in `server/docs/CODEMAP.md`.
- The existing real Endpoint Operations cross-repository acceptance passed on a
  DB-compatible staging runner (`2 passed`): it validated the exact provider
  lock, the real Endpoint factory/PostgreSQL/Gateway WSS path, the Helpdesk
  facade and its one-evidence projection. Its Windows runner remains unsuitable
  for fresh Helpdesk migrations over the staging SSH tunnel because it stalls at
  initial schema introspection; no production system was touched.
- ALT staging package `endpoint-agent-3.2.30-alt1` has been signed using a
  test-only RPM identity, verified by RPM and installed on the ALT test agent;
  the service is active. The module-recipe canary remains gated on its dedicated
  acceptance test and staging release alignment.

## Next Steps

1. Add `server/tests/acceptance/test_endpoint_module_platform_v1.py` using the
   real Endpoint factory, PostgreSQL, catalog, recipe engine, Gateway WSS,
   protocol-compatible client and Helpdesk reconciler; it must assert all
   required no-legacy and exactly-once counts.
2. Run that test from a DB-compatible runner that does not use the stalled
   Windows Alembic-over-tunnel path, then record only redacted evidence.
3. Align approved staging releases, execute one ALT and one Windows
   `network.basic.check@1.0.0-canary` run, prove rollback, and keep production
   unchanged.

---

### Task 1: Preserve Phase 0 audit evidence

**Files:**
- Create: `docs/modules/ENDPOINT_MODULE_PLATFORM_DESIGN.md` in Endpoint
- Create: `docs/modules/TYPED_PRIMITIVE_CATALOG.md` in Endpoint
- Create: `docs/segmentation/MODULE_PLATFORM_BOUNDARY.md`
- Create: `docs/segmentation/LEGACY_MODULE_MIGRATION_MATRIX.csv`

- [ ] Verify that every legacy module row has a migration classification and no row carries source code.
- [ ] Verify that the design names the legacy `user_function_body`/ZIP/ToolService path as retained only.
- [ ] Commit the documentation-only audit before runtime work.

### Task 2: Deliver PR-EP1 contracts and target policy

**Files:**
- Create: `endpoint_contracts/network_primitives.py`
- Modify: `endpoint_contracts/commands.py`, `endpoint_contracts/gateway_ws.py`
- Create: `endpoint_server/policy/network_targets.py`
- Test: `tests/contracts/test_network_primitives.py`, `tests/operations/test_network_target_policy.py`

- [ ] Write failing tests for strict target grammar, parameter bounds, result bounds, and raw-output rejection.
- [ ] Add frozen Pydantic parameter/result DTOs plus capability-specific Gateway parameter allowlists.
- [ ] Implement CIDR/suffix policy that rejects empty allowlists, URL, loopback, unspecified, multicast, broadcast, link-local, and unallowlisted public targets.
- [ ] Run `python -m pytest tests/contracts tests/operations -q`.

### Task 3: Deliver PR-EP1 agent primitives and projection

**Files:**
- Create: `pc_agent/primitives/network/`
- Modify: `pc_agent/runtime/command_executor.py`, `endpoint_server/operations/capabilities.py`, `endpoint_server/operations/service.py`
- Test: `pc_agent/tests/primitives/`, `pc_agent/tests/runtime/`, `tests/gateway/`

- [ ] Write failing tests for unknown capability, policy mismatch, oversized result, and raw stdout/stderr exclusion.
- [ ] Replace context-only dispatch with an explicit built-in capability registry; register only fixed handlers.
- [ ] Project capabilities only for compatible agent/platform, enabled primitive, and configured target policy.
- [ ] Run the PR-EP1 test and contract-artifact commands from the approved task specification.

### Task 4: Deliver PR-EP2 module contracts and persistence

**Files:**
- Create: `endpoint_contracts/modules.py`, `endpoint_server/modules/{repository,service,validation,compatibility,projections,audit}.py`
- Create: forward-only Endpoint Alembic migration(s)
- Test: `tests/modules/test_module_lifecycle.py`, `tests/modules/test_recipe_validation.py`

- [ ] Write lifecycle, immutable-version, idempotency, and lab-gate tests before the models/services.
- [ ] Persist ModuleDefinition, ModuleVersion, ValidationRun, and LiveTest with explicit permitted transitions.
- [ ] Add scopes `modules.read/write/validate/publish` and narrow service-client credentials.
- [ ] Run `python -m pytest tests/modules tests/architecture -q` and check exactly one Alembic head.

### Task 5: Deliver PR-EP2 recipe engine and parent/step operations

**Files:**
- Create: `endpoint_server/modules/recipe_engine.py`, `endpoint_server/modules/routes.py`
- Modify: Endpoint operations/gateway models and services
- Test: `tests/modules/test_recipe_engine.py`, `tests/operations/test_module_operations.py`, `tests/gateway/test_module_delivery.py`

- [ ] Write negative tests for code/shell/URL/path/expression/loop/branch/output-chain and more-than-eight-step recipes.
- [ ] Expand a validated recipe into one parent and sequential child commands with exactly-once terminal step handling.
- [ ] Add module API routes and safe aggregate projections without command internals.
- [ ] Run the approved Endpoint module, operations, gateway, architecture, packaging, and compile checks.

### Task 6: Deliver PR-HD1 typed port and BFF facade

**Files:**
- Create: `server/domain_ports/endpoint_modules.py`, `server/endpoint_adapter/modules_wire.py`, `server/endpoint_adapter/modules_http.py`
- Modify: port container/config, endpoint operation link model/repository/reconciler, routes, RBAC/audit
- Test: `server/tests/test_endpoint_module_port.py`, `server/tests/test_endpoint_module_http_adapter.py`, `server/tests/test_endpoint_module_execution.py`, `server/tests/test_endpoint_operation_reconciler.py`

- [ ] Write failing port DTO, unavailable-mode, authorization, idempotency, and no-legacy-dispatch tests.
- [ ] Implement the fixed HTTPS methods and admin/support BFF routes without a generic proxy.
- [ ] Extend the existing facade/link/reconciler lifecycle and emit one safe evidence item only.
- [ ] Run the specified Helpdesk verifier and focused pytest suite.

### Task 7: Deliver PR-HD2 Workbench recipe editor

**Files:**
- Modify: `server/admin_modules_workbench.js`, `server/admin_modules_workbench.html`, Workbench handlers/services
- Modify: `webapp/src/features/modules/**`
- Test: Workbench API and webapp tests

- [ ] Write tests that distinguish Legacy Python Module from Endpoint Recipe and suppress `user_function_body` for recipes.
- [ ] Add primitive/binding editor, templates, lifecycle/compatibility displays, and admin/support authorization behavior.
- [ ] Use BFF routes only; do not expose Endpoint credentials or direct requests.
- [ ] Run `pnpm --dir webapp test` and `pnpm --dir webapp build`.

### Task 8: Deliver cross-repository acceptance and staging evidence

**Files:**
- Create: `server/tests/acceptance/test_endpoint_module_platform_v1.py`
- Modify: contract lock and acceptance documentation

- [ ] Test Helpdesk adapter through real Endpoint app/PostgreSQL/catalog/recipe engine/Gateway WSS/protocol client/reconciler.
- [ ] Assert exact replay, three ordered child commands, one evidence, unchanged ticket status, and zero legacy transports.
- [ ] Run isolated ALT and Windows staging canaries for `network.basic.check@1.0.0-canary`, then execute documented rollback.
- [ ] Record only redacted counts and outcomes; leave production unchanged.
