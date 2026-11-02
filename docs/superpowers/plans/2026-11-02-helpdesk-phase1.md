# Helpdesk first-stage implementation plan

> **For agentic workers:** Use superpowers:subagent-driven-development to execute independently owned tasks; use focused test-first fixes and independent review. Do not commit shared working-tree changes; the coordinator stages atomic commits after review.

**Goal:** Deliver the user's corrected first-stage ticket flow and prove it in Studio, ordinary requester and support paths on staging.

**Architecture:** Reuse existing OIDC/identity, scenario-session, support status and policy services. Automate presentation steps while retaining authoritative server checks and scenario questions/SLA. Configure ordinary published policies through existing reviewed publication paths.

**Tech Stack:** Existing Python/aiohttp/SQLAlchemy and React/router/query/Vitest/Playwright, versions pinned in requirements/package lock. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-11-02-helpdesk-phase1.md`

## Global constraints

- Preserve registration policy, profiles, roles, questions, answer conditions and SLA.
- All Helpdesk AD roles remain password-only; never infer identity ownership.
- Approved staging only; leave staging running; no production/AD/credential changes.
- Later user clarification authorizes a separate staging `admin-2` administrator
  profile and verified AD binding. Preserve existing accounts/roles; owned new
  synthetic requester fixtures do not change the registration flag.
- Preserve ownership/visibility/audit, atomic status changes, versioned scenario sessions.
- Existing checkout and unrelated dirty work are retained.

## Review focus

- Resume/reload/double submit must not create duplicate tickets or navigate to stale sessions.
- Hidden answer branches/backtracking must invalidate stale processing and retain correct questions/SLA.
- Failed closure must roll back the entire resolution/close command and its success effects.
- Admin requester workspace actions must match server authorization without widening ticket ownership.
- Registration and SSO errors must not leak provider strings or replace existing profile/roles.

### Task 1: Automatic Studio submission processing

**Ownership/files:** `webapp/src/features/requester/scenario-session.tsx`, its component tests; focused helper file if needed. No support/auth files.
**Interface:** Keep existing session/preview/submit API payloads. Navigate through existing requester ticket route when the current session returns ticket_created/linked_ticket_id.
- [ ] Add regression tests for automatic preview, blocker/retry, immediate navigation, resumed-created session and stale/double responses.
- [ ] Remove manual preview action, trigger processing when entering submit step without changing questions/SLA; retain server submit validation.
- [ ] Run focused Vitest and report exact commands/results.

### Task 2: Backend resolution and requester action correctness

**Ownership/files:** `server/web_api/support_handlers.py`, `server/web_api/requester_handlers.py`, related DTOs, `server/tickets/{workflow_service,closure_policy,requester_policy,handlers}.py` only as necessary; focused new test files to avoid shared test churn. No auth/registration or frontend files.
**Interface:** Agree a minimal additive support status command `close_after_resolve: bool = false` (or prove an existing equivalent); execute resolved -> closed atomically when requested and policy permits. Expose actual closure/confirmation capability to UI.
- [ ] Map current status/confirmation and requester authorization with GitNexus/source.
- [ ] Write failing tests for resolve+close, rollback/concurrency/ownership/explicit policy denial, requester action projection/command consistency and public result visibility.
- [ ] Implement through canonical workflow, retaining explicit special-policy requirements; ordinary policy changes are owned by Task 5.
- [ ] Run focused no-DB tests; coordinator runs PostgreSQL coverage.

### Task 3: Compact support entry and simple completion UI

**Ownership/files:** `webapp/src/app/navigation.tsx`, relevant router/shell tests; `webapp/src/pages/tickets/components/simple-*`, relevant list/detail orchestration, `webapp/src/features/queues/api.ts`; `webapp/src/pages/requester/{tickets-panels,ticket-chat-page}.tsx` for result/confirmation presentation and corresponding focused tests. No scenario-session/auth files.
**Interface:** Coordinate Task 2's additive status flag and actual confirmation capabilities. Keep advanced center accessible separately and URLs compatible.
- [ ] Add tests proving compact normal entry, visible problem/result, no manual code field, resolve+close ordinary action and confirmation UI consistent with capabilities.
- [ ] Implement small scoped edits; preserve normal question/SLA display and attachment/chat privacy.
- [ ] Run focused Vitest/typecheck and report changed files/remaining browser cases.

### Task 4: Registration and AD profile preservation

**Ownership/files:** `server/auth/oidc.py`, `server/web_api/session_handlers.py`, `server/auth/identity.py` only if a proven defect needs fixing, `webapp/src/features/auth/{login-page,register-page}.tsx` and tests; focused new backend tests. No requester/support status files.
**Interface:** Keep registration policy, profile and role authority. Fixed/whitelisted same-origin SSO failure presentation only; no arbitrary callback/return target or automatic identity binding.
- [ ] Audit registration enabled/disabled, normal user issuance, duplicates/invalid input, next path and profile preservation using focused source/tests.
- [ ] Fix proven issues; retain password-only OIDC for every role. Add usable Russian handling for unknown/unlinked identity and provider failure.
- [ ] Run focused auth/registration tests and record large-test prerequisites without creating/granting accounts silently.

### Task 5: Studio coverage and ordinary policy publication (coordinator)

**Ownership/files:** new `scripts/helpdesk_phase1_*` content/publication helpers and tests, task-specific evidence; relevant catalog/scenario docs. Do not edit worker-owned files.
- [ ] Inventory published scenarios and missing necessary requests; add bounded common missing scenarios through existing Studio definitions/publication APIs.
- [ ] Preserve existing question/SLA routes. Define ordinary closure policy with public result, no required code or requester confirmation; publish through canonical versioned policy boundary.
- [ ] Validate representative branches and policy changes on isolated DB; prepare reviewed, idempotent staging application with private backup/readback, no deletes.

### Task 6: Integration, review, deployment and browser acceptance (coordinator)

- [ ] Review tasks for spec/correctness and resolve interface mismatches; run affected focused checks, PostgreSQL tests, frontend build and workspace verification.
- [ ] Commit only task files in atomic logical commits; build/deploy fixed candidate with canonical staging scripts, verified backup, no production actions.
- [ ] Apply reviewed Studio/policy publication and verify source/runtime SHA, TLS/health.
- [ ] Rerun Other creation through automatic opening, support take/reply/resolve/close and requester result; use ordinary requester role as well as admin.
- [ ] Test Studio questions/conditions/backtracking, validation, SLA and no duplicate submit at desktop/mobile fallback sizes. Inspect console/network failures with redacted evidence.
- [ ] Reconcile every user requirement with evidence; keep goal active for missing checks. Leave staging running and update docs/report/ledger.
