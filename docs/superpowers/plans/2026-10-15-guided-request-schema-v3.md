# Guided Request Studio schema v3 Implementation Plan

> **For agentic workers:** Use superpowers:subagent-driven-development or superpowers:executing-plans task by task. User explicitly authorizes subagents and execution without additional approvals; use one final risk review, without repeated formal audits.

**Goal:** Author, import, test and execute map-owned SLA/routing and composite rules through canonical Helpdesk services, with catalog-wide problem search.

**Architecture:** Extend the versioned scenario DTO and trusted submission context. Adapt map choices into existing routing/SLA/approval services after policy overlays; the graph evaluator and priority policy remain authoritative.

**Tech Stack:** Python/Pydantic 2.12, SQLAlchemy/PostgreSQL/Alembic, PyYAML 6, React 19.2/TypeScript/React Flow 12, Vitest/Playwright.

**Spec:** `docs/superpowers/specs/2026-10-15-guided-request-schema-v3-design.md`

## Global Constraints

- One feature branch from e5080f58df21415b87987b0d10817696c40aa3c2; adapt to later origin changes before PR.
- Preserve v1/v2, pinned sessions, RBAC, confirmation, audit and canonical policy engines.
- No new dependencies, production deploy, real-service publication or changes to active SLA/queues.
- No authority in requester answers; server revalidates selected route and profile.
- Preserve unrelated untracked workspace files and user-owned browser state.

## Review Focus

- Inherited legacy SLA IDs or registry overlays must not override map-owned deadlines or queue.
- Unknown/skipped fields and overlapping rules must follow explicit safe fallback/order.
- Disabled queue or malformed business calendar must block readiness/create clearly.
- Public search must not disclose hidden/unpublished services or erase negation.
- Import/copy/save must preserve v3 and confirmation rather than silently downgrade or publish.

### Task 1: Versioned contract and interchange — root

**Files:** DTO `server/web_api/dto/request_scenario.py`, DB model/migration150,
`server/app/repos/request_scenario_repo.py`, frontend `scenario-contract.ts`,
`server/tests/test_request_scenario_v3_contract.py`, unified/API compatibility tests.

**Interfaces:** `ScenarioProcessing` dictionaries, defaults and last-matching mode;
`ScenarioBranchProcessing.route/sla_profile/approval_required`; schema versions1/2/3.

- [x] Add RED contract/roundtrip/schema constraint tests and observe unsupported-v3 failures.
- [x] Implement strict bounded DTO/type/storage support, preserve automatic binding version.
- [x] Verify JSON/YAML semantic roundtrip and historical contracts; add complete example.

### Task 2: Trusted processing/runtime — v3_runtime worker

**Files:** scenario submission/processing/validation/readiness/publication,
service catalog preview, requester create, canonical policy overlay as necessary;
new focused server tests.

**Interfaces:** trusted snapshot selection and provenance shared by preview/create;
canonical standalone SLA targets/calendar and routing fallback; server trace for UI.

- [x] Reproduce unsupported map processing with focused tests.
- [x] Derive selected edge assignments from revalidated retained history; explicit defaults/last replacement.
- [x] Adapt queue/SLA/approval through existing services and preserve through overlays.
- [x] Validate every configured reference and retain source-lock/confirmation checks.
- [x] Verify default/override, unknown/overlap, priority independence, calendars, active queue and approval parity.

### Task 3: Map authoring and explanation — v3_studio worker

**Files:** existing Studio components/models/tests and admin Studio creation page.

**Interfaces:** task1 contract; task2 authoritative processing trace; existing queue/calendar registry APIs.

- [x] Add RED component/model regressions for map settings, branch results and multiple-question groups.
- [x] Implement contextual Russian map settings, branch pickers/order, missing-answer warnings and groups/negation.
- [x] Preserve v1/v2, default new maps to v3, display server trace and compare two runs.
- [x] Verify focused Vitest tests and TypeScript/build; preserve route highlight and local employee preview.

### Task 4: Public catalog search — catalog_search worker

**Files:** `tickets/service_catalog_search.py`, catalog handlers, requester catalog search/new-request page and tests.

**Interfaces:** current authorized catalog with additive `q` and search results selecting offering/entry.

- [x] Add RED ranking/normalization/visibility tests.
- [x] Implement deterministic bounded search after visibility filtering, retaining negations.
- [x] Implement requester suggestions/direct entry/results and empty/error fallback.
- [x] Verify Russian word forms/typo/layout, exact-match precedence and hidden data exclusion.

### Task 5: Integration, docs and publication — root with validation agents

**Files:** PLANS.md, canonical guides/CODEMAP, new v3 example and integration/browser tests.

- [x] Run disposable PostgreSQL scenario A/B/D and public search/API checks; no live service publication.
- [x] Run focused backend/frontend checks, build and `python scripts/verify_workspace.py --workspace .`.
- [x] Inspect complete diff and run one independent review; fix material findings and scoped regression checks.
- [x] Commit task-related files only with Conventional Commits; verify status and origin/main compatibility.
- [ ] Install verified exact candidate to approved isolated staging via project release procedure; browser-check 1366/1920 and console/network, stop services started for validation.
- [x] Push the feature branch and create/attach draft PR43; report remaining live gates explicitly.
- [ ] Resolve the final CI legacy-submit regression and pass the updated mandatory gate. Keep unavailable-approver preview blocking scoped to trusted v3 processing; preserve v1/v2 and existing API regressions.
