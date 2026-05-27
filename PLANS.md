# pc_client Product / Infra Plan

This file is intentionally compact. Detailed phase logs live in git history and the referenced CI/release artifacts; this document keeps the current product state, accepted checkpoints, active work, verification evidence and rollback notes.

## Release Workflow Guardrail

- Full CI is reserved for a frozen release candidate SHA. During implementation and live staging, use targeted tests, `verify_workspace`, relevant build/typecheck and explicit `--gate quick`.
- After green full CI, do not commit before full-gate release. Any new commit is a new candidate and requires a new full CI artifact.
- Before full-gate release, run `python scripts/release_candidate_preflight.py`; it verifies `summary.commit == HEAD`, green status, webapp bundle artifact and dirty workspace state.

## Status History

| Phase | Status | Essence | Key Evidence |
|---|---|---|---|
| P0 / P0.1 Ticket hardening | accepted / baseline | Canonical ticket statuses, public queue privacy, workflow side-effect observability, requester-safe timeline, policy health. | Last recorded P0 suite: 78 targeted passed; full server non-manual 863 passed; webapp build/typecheck and `verify_workspace` passed. |
| P1 / P1.1 Service Catalog | accepted / release-candidate | First-class helpdesk services/offerings, requester/agent-safe catalog, policy inheritance, publication/preview and reporting fields. | P1.1 full CI green with `--server-pytest-timeout 5400`; remote release and browser signoff completed. |
| P2 / P2.1 Knowledge Platform | accepted / release-candidate | Knowledge spaces/items/versions/search/suggestions/feedback/graph, ACL hardening, safe deflection and ticket KB compatibility. | CI artifact `artifacts/ci/08863b071b7a8740ead083d32ae2d6f3405d111f/summary.json`; remote/browser signoff completed. |
| P2.2 / P2.2.1 Knowledge Operations | accepted / release-candidate | Content packs, templates/lint, review tasks, quality/gap/search analytics, rollout policies and pack-binding repair. | CI artifact `artifacts/ci/356b473d231a52d7f77b0690c94e6e93c11dce47/summary.json`; remote/browser signoff completed. |
| P2.2.2 Suggestion Policy Enforcement | accepted / release-candidate | Requester help, agent wizard and `KnowledgeSuggestionService` enforce rollout min/max/no-suggestions/API-unavailable/known-error rules without blocking urgent bypass. Reserved UX flags remain future follow-up. | Commit `bbc7a6f` pushed/deployed; focused policy tests and webapp build/tsc passed. |
| P2.3 Test Harness / CI Layering | accepted / release-candidate | Root pytest collection stabilized, `pc_agent` imports qualified, isolated per-layer DB harness, domain CI layers and `run_ci_suite.py` summary artifacts. | Full CI artifact `artifacts/ci/cd21c1abbf02ce73d3b987555a01361430c321fc/summary.json`; no browser signoff required because product UI did not change. |
| P3 Experience & Quality Loop | accepted / release-candidate | Structured CSAT, reopen reasons, QA review queue, improvement actions, aggregate service/offering quality analytics and requester/support/admin UI. | Commits `71f2326`, `f826e33`; CI artifact `artifacts/ci/f826e3384e07ad0a21ac841434c8a89dccf4a1e1/summary.json`; remote/browser signoff completed. |
| P3.1 Quality Production Hardening | accepted / compact release-candidate | Latest-feedback DB invariant, concurrency coverage, daily/weekly quality snapshot scheduler, effective policy preview and P3 smoke regression. | Focused P3.1 tests, webapp build, `verify_workspace`, context index rebuild and smoke regression passed. |
| P4 Problem Management / RCA | accepted / release-candidate | First-class problems, candidates, ticket links, RCA, known-error/workaround Knowledge links, affected objects, analytics and `/app/admin/problems`. | Commit `2618616`; CI artifact `artifacts/ci/2618616bc2e0045ed4cdcdf39aeed7c195b8149e/summary.json`; remote/browser signoff completed. |
| P4.1 Problem Production Hardening | accepted / release-candidate | Scheduled scanner, run records, broader detection signals, dedup/merge/cooldown, problem SLO/aging and operational dashboard. | Commits `f2ad8db`, `f83f95d`, `d7f3836`; final CI artifact `artifacts/ci/f83f95d794fcd17028bb87d659902af4d26efe0f/summary.json`; remote/browser signoff completed and server stopped. |
| P5 Change Enablement | accepted / release-candidate | First-class changes, standard/normal/emergency lifecycle, risk/impact, approvals, windows/calendar, implementation/rollback plans, tasks, PIR, problem/action linkage and `/app/admin/changes`. | Commits `1abd32c`, `82a33a1`; CI artifact `artifacts/ci/82a33a1ecfcaf308ffe2cd3c53cdb0beb33ab1e7/summary.json`; remote/browser signoff completed. |
| P5 Change Enablement Hardening | accepted / compact release-candidate | Operator docs, standard preapproval catalog, recurring blackout/maintenance windows, overlap detection, emergency retrospective rules, hardened metrics and remote demo cleanup. | Commit `b904791`; focused P5 backend/webapp tests, webapp build, `verify_workspace`, quick deploy, remote smoke and browser signoff passed; remote demo records archived/canceled and server stopped. |

## Current Invariants

- Work only in `C:\Users\admin-2\CodexProjects\pc_client`; the SMB share and Linux checkout are mirrors.
- Do not weaken P0-P5 contracts, canonical ticket statuses, Service Catalog fields, Knowledge visibility, Quality privacy, Problem lifecycle or Change governance.
- Protocol V3 is unchanged unless explicitly required; current P5 scope does not require it.
- Requester/public surfaces must not expose internal QA, RCA, change risk notes, infrastructure details, rollback steps, queue ids, raw policy JSON or requester PII in analytics.
- Full DB/API gates use isolated test databases through the P2.3 harness; shared `pc_support_test` is debug-only and not a full gate.
- Product UI changes require webapp build plus remote/browser signoff at `https://192.168.100.17:9443/admin` before release acceptance.

## Active Work: Pilot Hardening / Mini-prod Readiness

Status: in progress on branch `codex/helpdesk-process-model`.

Goal:

- Close the immediate pilot-readiness gaps without requiring public `/help` or `/ticket` cutover in this pass; requester creation through the PC agent remains the accepted mini-prod path.

Scope:

- Move `InventoryRefreshRuntime` lifecycle out of housekeeping so only one scheduler starts and cleanup stops that single runtime.
- Add explicit `APP_ENV=dev|test|pilot|prod` security profile handling; keep `PILOT_STAND_MODE` as a compatibility strict-mode trigger.
- Make pilot/prod fail closed for default UI passwords, HTTPS/WSS/session-cookie policy, query-token auth, dev fallback and DB initialization failure.
- Remove committed local env/config files from git tracking while leaving local files available for the test stand.
- Align server dependency declarations and webapp CI gates, including Vitest and Playwright fixture checks in the canonical CI suite.
- Add a controlled DB cleanup plan/script for test data later in this block; backup automation is explicitly out of scope for now.

Non-goals:

- No `/help` or `/ticket` requester cutover in this pass.
- No backup/restore automation in this pass.
- No full release gate unless explicitly requested after a frozen candidate.

Verification target:

- Focused server tests for scheduler lifecycle, security config and DB fail-closed startup.
- Focused CI-script tests or dry-run evidence for added webapp CI layers.
- `python scripts/verify_workspace.py`, relevant pytest, `pnpm --dir webapp run test`, `pnpm --dir webapp run test:e2e`, `git diff --check`.

## Active Work: Registry Management Center P1/P2

Status: in progress / P1 feature layer implemented; P2 reliability smoke now focuses on end-to-end workflow invariants, preview-protected dangerous operations and safe registry import.

Goal:

- Turn `/app/admin/registry` from the completed P0 operations center into a fuller CMDB/Identity/Binding operations tool without rewriting the P0 page or weakening registration/account-session security.

Scope:

- Functional Locations and Departments tabs with CRUD, archive, merge, counts and registry events.
- Registration/account-session/ticket visibility policy editor backed by persisted safe config with default fallbacks.
- People merge/dedup workflow that moves identities, bindings, sessions, claims, tickets and derived asset assignments without deleting duplicates.
- Bulk operations for common registry administration: assign locations/departments and revoke account sessions with per-item results.
- CSV export for devices, people, bindings, sessions, locations, departments and quality issues.
- Safe CSV import for people, locations, departments and device inventory mapping through parse -> validate -> preview -> apply with row-level errors, duplicate detection, rollback-safe apply and audit events.
- More actionable quality remediation with persisted ignore/snooze/resolve state and richer timeline/detail drawer data.
- Unified Registry Timeline in the drawer for device/person/binding/session/claim: admin, registration and account events must show actor, time, reason, changes and affected entity ids.
- Operator docs and live smoke checklist for Registry Management Center.
- Repeatable A-F live workflow smoke for people/identities, bind, shared/responsible, transfer owner, people merge and locations/departments with API actions plus DB invariant checks.
- Read-only preview/dry-run contracts for dangerous operations before apply: transfer owner, people merge, location merge, department merge, bulk operations and registry import.

Non-goals:

- No AD/LDAP integration in this pass beyond safe placeholders/hooks.
- No raw lifecycle mutation for binding revoke/transfer/session invalidation; existing `RegistrationService` and `AccountSessionService` remain authoritative.
- No changes to machine-token or account-session architecture.
- No direct binding import in this pass; binding lifecycle remains service-backed and must not be imported without a dedicated preview/approval model.

Verification target:

- Focused Registry DB/API tests for previews, locations, departments, policies, merge, bulk actions, import/export where implemented, plus existing P0 registry/account-session/ticket access tests.
- Timeline regression: `python -m pytest server/tests/test_registry_timeline_admin.py -q`.
- `pnpm --dir webapp test -- registry`, `pnpm --dir webapp run build`, agent account-session smoke tests, `python -m compileall -q server pc_agent`, `python scripts/verify_workspace.py`, `git diff --check`.
- Linux DB validation for DB-backed pytest if the Windows harness stalls, then quick remote release, `python scripts/registry_workflow_smoke.py --base-url https://192.168.100.17:9443 --insecure-tls`, and browser smoke at `https://192.168.100.17:9443/app/admin/registry`.

Stage 5 bulk polish:

- Bulk apply responses now include `bulk_operation_id`, `summary.selected/success/failed` and normalized per-selected-object `items`, while keeping legacy `results` for compatibility.
- Devices, People and Account Sessions tabs expose checkbox selection and a shared bulk result panel with failed-row review, copy errors and CSV result export.

Stage 6 cautious policy editor:

- Registry policy responses now include defaults, effective values, changed-from-defaults, validation ranges, dangerous-setting warnings, `requires_restart` metadata, dry-run preview and reset-to-defaults.
- Enabling `registration.auto_approve_first_binding` shows the explicit test-stand warning before save, and policy patch/reset require a reason and write `policy_changed` audit events.

Stage 7 operation invariants:

- Add focused DB-backed invariants for primary binding uniqueness, transfer/revoke derived state, shared/responsible non-ownership changes, merge dangling-reference cleanup, policy audit and bulk partial-success semantics.

Stage 8 P2 safety hardening:

- Registry import apply now requires the exact `preview_id` returned by import preview, reruns validation before mutation, writes `registry_import_applied` with an operation id and returns per-row apply `items`.
- Data-quality issues now carry stable `issue_key` values. Admin ignore/snooze/resolve actions persist in `registry_quality_issue_overrides`, hide active overrides from the generated issue list and write `quality_issue_*` audit events.

Stage 9 P2 operation consistency:

- Extend the same preview -> apply -> audit -> result-report contract from import to transfer owner, people/location/department merge and bulk actions while preserving existing response fields for UI compatibility.
- Add regression tests that preview endpoints exist for every dangerous operation and that apply responses include `operation_id`, `status`, `summary`, `items` and `events`.
- Keep quality remediation action-first: issues fixed by the underlying operation must disappear from the generated active quality list without requiring a manual override.
- Add import result CSV export in the dialog so large imports can review all rows or failed rows after apply.
- Strengthen timeline coverage around ownership transfer so an admin can see actor, reason, before/after changes and related binding/session/device ids.

## Active Work: Device Account Session Hardening

Status: in progress.

Goal:

- Harden server-issued requester account sessions for the PC agent as the requester identity boundary: ticket create/list/detail/message/read access must require a valid account session, registration-pending gets a deterministic server-issued session, logout/revoke is server-side, and support/admin surfaces show session ownership and other-account warnings.
- Final staging hardening adds artifact-download and handshake leakage guards, explicit ticket visibility policy, support warning rendering, admin account-event visibility, and a live smoke checklist in `server/docs/REGISTRATION_ACCOUNT_SESSIONS.md`.

Follow-up TODO:

- Add an account-session TTL/cleanup scheduler for expired/revoked sessions and old `device_account_events`.
- Add a separate registered owner transfer flow: transfer request claim, admin approval, revoke old binding/sessions and activate the new binding.

Verification target:

- Focused server tests for `AccountSessionService`, registration API, ticket account access and ticket registration enrichment.
- Focused agent tests for account-session manager/gate/client helpers and chat-panel account propagation.
- `python -m compileall server pc_agent`, webapp build/typecheck, `python scripts/verify_workspace.py`, `git diff --check`.

## Active Work: Auth / Registration Security Patch

Status: in progress.

Goal:

- Close critical fail-open and token disclosure paths in user registration, UI auth, legacy UI auth and agent authorization without breaking Protocol V3 or the cookie-based `/api/web/session/login` flow.

Scope:

- Make legacy/public agent token issue admin-only and audited; keep compatibility route but require authenticated admin.
- Protect manual connection request polling with `request_id` plus one-time high-entropy `poll_secret`, without storing raw poll secrets in the database.
- Harden production defaults, role validation, UI config fallback, password policy, token revocation scoping and explicit agent token replacement/limits.
- Reject agent-forged registration confirmation, add safer account-session validation transport and gate legacy localStorage login behind an explicit flag.
- Update focused server and pc_agent tests plus auth/navigation docs touched by these contracts.

Verification target:

- Focused red/green tests for auth security, connection request security, admin users, registration API and pc_agent connection flow.
- `python -m pytest server/tests`, `python -m pytest pc_agent/tests`, `python scripts/verify_workspace.py`, and applicable lint/build checks if available in this workspace.

## Active Work: Admin Ticket Purge

Status: implementation complete / targeted API tests passed; workspace verification pending.

Goal:

- Add an admin-only hard purge path for test/noise tickets that first previews affected rows and blockers, then deletes ticket-owned data without leaving non-FK orphan rows.

Scope:

- Backend service for purge preview/apply over ticket ids.
- Typed/admin web endpoints for preview and confirmed purge.
- Cleanup of known non-FK ticket references: ticket events/archive, operations, remote assist rows, artifacts metadata/files, agent runtime/observer rows and observer projections, before relying on existing FK cascades for ticket-owned tables.
- Safety blockers for active operations and active Remote Assist sessions.
- Docs/CODEMAP sync and focused DB/API tests.

Non-goals:

- No requester/support access to hard delete.
- No automatic scheduled purge.
- No schema migration unless tests reveal a required FK/constraint change.

Verification target:

- Focused pytest for preview counts, admin-only authorization, blockers and successful purge of FK + non-FK tables: `python -m pytest server/tests/test_ticket_purge_api.py -q` -> 4 passed.
- `python scripts/verify_workspace.py`.
- Broader server tests only if touched shared behavior requires it.

## Active Work: Webapp Workspace Navigation IA

Status: local verification passed / commit and remote browser signoff pending.

Goal:

- Restructure the new React webapp navigation from a flat mixed Support/Admin list into `workspace -> domain group -> local tabs`, while preserving routes, permissions, workspace access gates, ticket workspace shell behavior and public requester/help flows.

Scope:

- React webapp navigation source of truth, AppShell, AppSidebar, AppTopbar workspace switching, workspace access helpers, `/app/admin` landing page and route-level domain tabs.
- Route semantics: `/app/support` remains the Support Work Center, `/app/admin` becomes the Admin Center instead of redirecting to inventory, and existing `/app/tickets`, `/app/admin/*`, `/app/help`, `/app/ticket*` routes remain intact.
- Docs/navigation sync only where route semantics or source-of-truth navigation references change.

Decisions:

- Treat this as a React webapp UI boundary change, not a backend/API change. Do not add fake metrics or backend contracts.
- Keep `/app/tickets` isolated from the global AppShell exactly as the current ticket workspace behavior requires.
- Use permission-filtered navigation helpers as the single source for sidebar groups, workspace labels/search placeholder, active matching, domain tabs, admin/support landing cards and workspace switch fallbacks.
- Store last support/admin workspace paths in localStorage only for safe workspace-owned `/app/*` paths, with SSR/test guards and fallback to workspace home when access or permission no longer allows a stored route.

Verification target:

- Focused Vitest: navigation helpers, sidebar workspace/domain behavior, router/admin center and workspace switch history.
- Full webapp `pnpm test`, `pnpm build`, `python scripts/verify_workspace.py`, and if available `pnpm run check:remote:webapp`.
- Browser MCP check at `https://192.168.100.17:9443/admin` for Support/Admin sidebar separation, Admin Center cards, domain tabs and workspace switch context restore.
- Full CI/full gate remains an explicit final release checkpoint and must not be run without user request.

Verification so far:

- RED targeted tests failed before implementation for missing navigation helpers, admin center route and grouped sidebar behavior.
- Focused `pnpm --dir webapp test -- src/app/navigation.test.ts src/components/shell/app-sidebar.test.tsx src/app/router.test.tsx` passed: 3 files / 17 tests.
- Full `pnpm --dir webapp test` passed: 59 files / 283 tests.
- `python scripts/bootstrap_web_toolchain.py`, `pnpm --dir webapp build`, `python -m pytest scripts/test_navigation_catalog.py scripts/test_task_intake.py -q`, `python scripts/build_context_index.py --force`, `python scripts/verify_workspace.py` and `git diff --check` passed.
- Remote quick release, `pnpm --dir webapp run check:remote:webapp` and MCP browser signoff remain pending until after local commit/push.

## Active Work: P0 Tech Panel v2 — Pilot Readiness & Runtime Health

Status: in progress / first production-safe read-only cut.

Goal:

- Turn `/app/admin/tech` into a production-like stand Tech Panel that answers pilot readiness, blockers, degradation, security/auth/session/TLS, PostgreSQL/migrations/backup/restore, agents, operations/outbox/watchdogs, logs and release smoke.

Scope:

- Add typed read-only `GET /api/web/admin/tech/snapshot` while keeping legacy tech endpoints.
- Build readiness gates from config, PostgreSQL health, auth/session policy, connection policy, scheduler/runtime state and marker files for release/smoke/backup/restore.
- Redesign the React page into a Russian Tech Panel workspace with Overview, Security, Runtime, Database, Agents, Operations, Logs/Signals and Release/Smoke tabs.
- Keep the first cut read-only: refresh and navigation links only; no restart/revoke/approve/retry/cancel/SQL/env editing actions.
- Update docs/navigation catalog and targeted backend/frontend tests.

Known gaps for this cut:

- Backup, restore drill, release and business smoke are marker-file based and may be `unknown` until scripts write the configured JSON artifacts.
- HTTPS/WSS and session-cookie gates are config/introspection based; no proxy-origin guessing from the request.
- Alembic current/head remains `unknown` unless a safe marker/status source is available.
- No dangerous control-plane or token-management actions are added to the browser UI.

## Active Work: Tech Panel v2.1 - Pilot Diagnostic Locator & Evidence Markers

Status: follow-up implementation in progress / focused scripts and frontend checks green.

Goal:

- Make `/app/admin/tech` useful during pilot testing by adding read-only quick localization for tickets/devices/operations/traces/logs, marker writers for release/business smoke/restore evidence, query-token telemetry, baseline device lists and inventory scheduler duplicate-task status.

Scope:

- Add `GET /api/web/admin/tech/locate?q=...` for support/admin/auditor with safe links only.
- Extend Tech snapshot with query-token attempt count, below-baseline devices, baseline metadata and inventory scheduler details.
- Add safe marker-writing scripts/helpers for release status, business smoke status, backup status and restore drill evidence.
- Update Tech Panel UI with the locator panel, baseline list, query-token attempts and scheduler duplicate status.
- Keep browser surface read-only: no restart/stop, raw SQL, env edit, token revocation, approval, retry/cancel, remote assist launch or consent bypass.

Known gaps:

- Business smoke can now create a test ticket and enqueue `inventory.collect` only when explicitly requested by CLI flags; a real agent handshake still requires a safe device/test agent.
- Mixed-content/WSS checks are available through the optional Playwright-backed `--browser-check`; headless runtime availability remains an environment prerequisite.
- GitHub branch protection / required status checks must still be enforced in GitHub settings; local repo scripts and docs can describe the gate, but cannot enable protected-branch policy by themselves.

Implemented:

- Quick Locator endpoint/UI for ticket code/id, device id, hostname, operation id, Observer trace id and bounded problem-log matches.
- Quick Locator now accepts non-UUID trace ids of length >= 8 and returns grouped root-cause diagnosis from ticket/device/operation/outbox/approval/Observer signals.
- Read-only operation detail route `/app/admin/operations/:operationId` consumes existing `GET /api/operations/{operation_id}` and exposes only safe context links.
- Release marker helper in `scripts/release_server_to_remote.py` writes Alembic current/head after remote migration when available and writes `/var/chat_bot/pc_client/...` marker paths directly on the remote host; standalone `scripts/business_smoke.py`, safe `scripts/write_restore_drill_marker.py` and `scripts/write_backup_status_marker.py` write readiness evidence markers.
- Remote `smoke server` and release smoke gates now support HTTPS pilot stands through `REMOTE_SMOKE_BASE_URL` / `REMOTE_SMOKE_INSECURE_TLS` or explicit `--base-url` / `--insecure-tls` flags, avoiding false failures after `REQUIRE_HTTPS=true`.
- `scripts/business_smoke.py` supports optional HTTPS cookie check, self-signed stand TLS via `--insecure-tls` / `BUSINESS_SMOKE_INSECURE_TLS`, Playwright mixed-content/WSS check, explicit test ticket creation, support workspace read, explicit `inventory.collect` smoke and operation result polling.
- Runtime/release/migration/browser signoff helpers now accept stand profile env (`PC_CLIENT_REMOTE`, `PC_CLIENT_REMOTE_ROOT`, `PC_CLIENT_REMOTE_SERVER_PYTHON`, `PC_CLIENT_SSH_KEY`, `PC_CLIENT_BROWSER_BASE_URL`) and no longer force the old HTTP browser signoff default.
- Query-token attempt counter in auth middleware with bounded process-local storage and no token values.
- Tech snapshot additions for query-token attempts, below-baseline device lists/baseline metadata and inventory scheduler duplicate-task details.
- Agent baseline now counts only real post-handshake devices with numeric agent versions; pending provisioning stubs and non-numeric canaries stay out of below-version counts and should be handled as cleanup/provisioning data quality.
- Runtime inventory scheduler `status_snapshot()` now includes active task count, duplicate detection, last tick and last error.

## Active Work: Operator Command Center

Status: accepted / release-candidate.

Goal:

- Make `/app/support` a Russian localized Operator Command Center action board that shows what requires operator attention now, while preserving the guided `/app/tickets` queue/workbench and existing ticket routes.

Scope:

- Backend typed endpoint `GET /api/web/support/command-center` derived from existing support queue/workspace signals without fake counters or per-ticket full workspace fanout.
- P1/P2 hardening adds explicit batched `ticket_approvals`, `diagnostic_sessions` and `diagnostic_evidence` sources, plus server-side command-center search.
- Frontend API layer, prioritization helper, lazy support page and navigation update.
- UI controls include scope, queue, search and per-section item limit; search is sent to the typed endpoint and counts are based on the filtered candidate set.
- Docs/navigation updates for the new route, API and section keys.
- Live browser verification on the remote stand with a newly created ticket visible in the Command Center.

Decisions:

- Keep `/app/tickets` and `/app/tickets/:ticketId` as the guided ticket workspace.
- Use compact support queue rows, chat counters, SLA/OLA fields, batched approval/operation/device/diagnostics/passport fields when available, and deterministic recent-ticket grouping for similar spikes.
- Return all command-center sections with real count `0` when a source signal is unavailable; do not synthesize fake activity.
- Prefer links into `/app/tickets/:ticketId`; section actions may fall back to `/app/tickets` when smart-view query support is not guaranteed.

Verification target:

- Backend command-center contract/aggregation tests plus relevant support queue tests.
- Frontend command-center page/prioritization/navigation tests, then webapp build.
- `python -m compileall -q server`, `git diff --check`, `python scripts/verify_workspace.py`.
- Quick remote deploy/release and Browser MCP smoke at `https://192.168.100.17:9443/admin` for `/app/support`, `/app/tickets` and live ticket creation/display.
- Full CI/full gate remains the final publication checkpoint for a release cut; do not reuse a green artifact from a different commit.

Known constraints:

- Local Windows DB-backed `server/tests/test_operator_command_center.py` is slow but now completes on the local harness; keep full CI/full gate as the authoritative release publication checkpoint.

Current P1/P2 hardening checklist:

- Add requester-role regression coverage for `/api/web/support/command-center`; intended model is support-only, so requester tokens must receive 403.
- Mark requester messages as read when a support operator opens the real ticket workspace, using the existing ticket read endpoint rather than hover/preview behavior.
- Make `/app/tickets?smart_view=...` and `/app/tickets?search=...` open the queue view with visible filters; Command Center aliases are mapped to supported queue smart views.
- Change similar-spike links from generic `/app/tickets` to a filtered search context so operators see the group samples first.
- Add command-center performance logging and data-quality fallbacks for historical mojibake/junk titles without modifying stored data blindly.
- Live acceptance evidence: requester-role API returns 403, remote branch is `codex/inventory-v4-registration-presence`, product HEAD `ca8818eb` opened `/app/support` and `/app/tickets`, `/app/tickets?smart_view=unassigned|sla_risk` applied visible queue filters, similar-spike search opened filtered ticket context, live ticket `T-000578` entered `unread_user_messages`, opening `/app/tickets/930461f7-9f88-43c6-9ac5-e5676643a9cd` triggered `POST /api/web/support/tickets/{ticket_id}/read`, and after refresh it disappeared from unread while staying in `operator_action`, `new_unassigned` and `sla_risk`.

## Active Work: P1 Device Operations

Status: implemented / production-oriented cut pending release signoff.

Goal:

- Add a single Russian localized device/agent operations workspace where an admin or support engineer can inspect inventory, binding, agent version/update, modules, outbox, recent operations, Observer traces, provisioning/auth and Remote Assist availability for one device without replacing the existing expert screens.

Implemented:

- Backend typed read endpoint `GET /api/web/admin/device-operations/{device_id}` with query fallback, DTOs and `DeviceOperationsService` aggregation over existing devices, inventory, modules, outbox, operations, Observer, connection request/token audit and Remote Assist data.
- React route `/app/admin/device-operations/:deviceId` plus query fallback `/app/admin/device-operations?device_id=...`, typed frontend client and page with overview, inventory, agent/update, modules, outbox/operations, Observer, Remote Assist and provisioning/auth tabs.
- Deep links from Inventory, Device Card and the ticket device/offline banner to Device Operations while keeping the old Inventory, Device Card, Agent Updates, Modules, Observer and ticket routes intact.

Read-only / known gaps:

- Direct module rollout, operation retry/cancel, provisioning approve/reject and Remote Assist request buttons are intentionally not implemented in Device Operations until safe action-specific permission/consent flows are exposed for this workspace.
- Agent Updates and Observer row-level links into Device Operations are left as follow-up where device_id is available in those tables without a risky refactor.

Verification target:

- `server/tests/test_device_operations.py`, relevant support/inventory regressions, `python -m compileall -q server`.
- `pnpm --dir webapp test -- device-operations`, focused inventory/tickets tests and `pnpm --dir webapp build`.
- `python scripts/verify_workspace.py`, `git diff --check`, quick remote/browser smoke at `https://192.168.100.17:9443/admin` before release acceptance.

## Active Work: P1 Approval/Consent Center

Status: accepted / release-candidate.

Goal:

- Add a unified support/admin read workspace for approvals, user consent, risky action consent, closure approval blockers and policy override work without replacing source-domain workflows.

Implemented:

- Backend typed endpoint `GET /api/web/support/approvals` with DTOs and `ApprovalConsentCenterService`.
- React route `/app/support/approvals`, navigation item `Согласования`, typed frontend client and Russian read-only page with scope/status/kind/risk filters, KPI strip, sections and item cards.
- Real read sources for `ticket_approvals`, `change_approvals`, `operations.status=waiting_consent`, `remote_access_sessions` pending consent and closure-like ticket approvals.
- Command Center pending approval/consent actions now deep-link to Approval/Consent Center.
- Ticket workspace context shows a compact `Согласования и согласия` block when ticket approvals or waiting-consent operations exist.

Read-only / known gaps:

- Mutating approve/reject/delegate/cancel/resend actions are not wired in this cut; source-domain typed endpoints remain the safe action surfaces.
- Policy override items return zero because no first-class pending policy override source is exposed yet.
- Change, Remote Assist and operation rows link to context, but the center does not bypass consent or expose raw operation/Remote Assist secrets.

Verification:

- Backend: `server/tests/test_approval_consent_center.py`, command-center and device-operations regressions, `python -m compileall -q server`.
- Frontend: `pnpm --dir webapp test -- approval-consent`, `pnpm --dir webapp test -- command-center`, `pnpm --dir webapp build`.
- Workspace: `python scripts/verify_workspace.py`, `git diff --check`.
- Live stand acceptance on `0dabb033`: `/api/web/support/approvals` returned 200 for admin/support, 403 for requester, 401 for unauth/invalid bearer; live/seed sources produced ticket, change, risky tool, remote assist and closure approval/consent items; policy override stayed at zero by design; secret scan found no Remote Assist or operation raw secret fields in the payload.
- Browser smoke: `/app/support/approvals`, `/app/support` pending approval/consent links and `/app/tickets/a1111111-1111-4111-8111-111111111111` compact `Согласования и согласия` block passed with no console errors.

## Active Work: P0 Web UI Workbench and Studio Hardening

Status: accepted / production-oriented cut in progress.

Goal:

- Remove visible clipping/overflow from `/app/tickets`, make the ticket workspace task-guided, replace primary raw code/JSON inputs with pickers/guided forms, add a minimal Request Template Studio workflow, and localize the target admin/support screens in Russian while preserving existing endpoints and DTOs.

Scope:

- React webapp only by default: `/app/tickets`, `/app/admin/changes`, `/app/admin/forms`, `/app/admin/service-catalog`, `/app/admin/policy-health`, `/app/admin/device`, navigation and shared admin helpers.
- Backend changes only if existing web API data is insufficient for typed pickers. Prefer existing Service Catalog dashboard, Helpdesk Model registry and Policy Health endpoints.
- Preserve raw/expert JSON modes as collapsed or explicitly expert-only surfaces.
- Do not add fake catalog, policy, device, ticket or problem data.

Decisions:

- Treat the user's P0.0-P0.3 acceptance criteria as the approved design specification for this pass.
- First stabilize visible ticket workspace defects and tool availability grouping.
- Use shared TS helpers for catalog/policy/template option mapping and guided simulation payload construction.
- Implement Request Template Studio as a new admin route composed from existing Service Catalog, Forms Builder registry and Policy Health data; deep links should carry service/offering/template query params where possible.
- Russian UI labels are required for target screens, while technical ids remain visible only as metadata or expert fields.

Verification target:

- `pnpm --dir webapp test` focused component/API tests for picker mapping, guided simulation payloads and tool availability grouping.
- `pnpm --dir webapp build` because `package.json` has no separate `typecheck` or `lint` scripts.
- `python scripts/verify_workspace.py`.
- Focused server tests only if server DTO/routes change.
- Browser MCP smoke at `https://192.168.100.17:9443/admin` for `/app/tickets`, `/app/admin/changes`, `/app/admin/forms`, `/app/admin/service-catalog`, `/app/admin/policy-health` and `/app/admin/device`.

Handoff notes:

- If the whole P0 scope cannot land in one pass, do not leave `/app/tickets` with clipping or duplicated offline reasons. P0.0 and P0.3 take priority over broad visual polish.
- Current production cut fixes Request Template Studio simulation to send catalog context as top-level `service_code` / `offering_code` / `offering_full_code` and adds selected-ticket compact device/agent/inventory context in `/app/tickets` without adding inventory fanout to queue rows.
- 2026-05-20 Studio unification cut promotes `/app/admin/request-template-studio` to the primary request-template setup workflow: service/offering/template selectors, binding summary, embedded form preview, policy binding cards with Policy Health issues, guided simulation with human-readable result cards, publication gates and context-preserving links to Forms Builder, Service Catalog and Policy Health. Forms Builder, Service Catalog and Policy Health remain expert/deep surfaces and now show a Studio banner.
- 2026-05-20 P1 Studio deep-link hardening closed: Service Catalog restores `service`/`offering` query context from Studio links, warns on unknown or mismatched context, shows `template` as a context hint, and Policy Health expert simulation now sends query-derived catalog context as top-level `service_code` / `offering_code` / `offering_full_code` with the same body shown in Expert JSON.
- Read-only gaps: policy/template binding edits and publish-from-Studio are not implemented because no safe typed update/publish contract is exposed for Studio. Use Forms Builder / Service Catalog / expert policy editor for those writes until backend/domain service support is added.
- Verification for this cut: focused webapp tests for Studio payload/API and `TicketDeviceAgentPanel`, `pnpm --dir webapp build`, `server/tests/test_support_inventory_context.py`, and Python compile checks. A DB-backed support workspace route test hung on local Windows and is left for Linux/CI or remote DB verification.

## Latest Accepted Work: P5 Change Enablement

Status: accepted / release-candidate.

Goal: add first-class Change Enablement so P4 permanent-fix outputs can move through controlled change request, risk/impact, approval/CAB-lite, maintenance window, implementation plan, rollback plan, tasks, PIR and closure. P5 is not automatic execution and does not replace tickets, problems or continuous improvement actions.

### Discovery

- Existing change support is legacy linkage only: `ticket_change_links` stores external `change_ref` / `change_system` for ticket history. There is no first-class `changes` domain model, approval workflow, change calendar, rollback plan, PIR or typed `/api/web/changes*` API.
- P4 stores `permanent_fix_summary`, problem affected objects and problem activity events. It currently creates `create_change_candidate` / permanent-fix improvement actions as placeholders; P5 should attach first-class changes to those outputs.
- P3 continuous improvement actions already support `create_change_candidate`; P5 may add nullable `change_id` linkage but must not replace the action lifecycle.
- Service Catalog dimensions (`service_code`, `offering_code`, `request_type`, `reporting_category`) are the reporting boundary for P5. Registry services/assets may be linked as affected objects when present, without creating a heavy CMDB.
- Approval patterns exist for tickets, but P5 needs auditable `change_approvals` tied to change lifecycle, not free-form comments.
- Webapp route pattern exists for admin workspaces: `/app/admin/problems`, `/app/admin/quality`; P5 will add `/app/admin/changes`.

### Design Decisions

- Change is a separate first-class domain entity, not a ticket type and not a problem subtype.
- Change sources: manual, problem, improvement action, quality review, service catalog, security and API.
- Change types: `standard`, `normal`, `emergency`.
- Lifecycle: `draft -> submitted -> assessing -> awaiting_approval -> approved -> scheduled -> implementation_in_progress -> implemented -> pir_required -> closed`, with terminal `rejected`, `canceled`, `failed`, `rolled_back`.
- Normal/emergency changes require a rollback plan before approval; emergency changes also require justification.
- Standard changes can be preapproved only by policy; no automatic approval without policy.
- No scheduled automatic execution. P5 tracks authorization, timing, tasks and results only.
- Requester/public users have no P5 internal change API. Any requester-safe communication remains future scope or existing Knowledge/ticket surfaces.

### Data Model Plan

- Migration `092_change_enablement` after `091_problem_management_production_hardening`.
- New tables: `changes`, `change_risk_assessments`, `change_plans`, `change_approvals`, `change_windows`, `change_affected_objects`, `change_tasks`, `change_pir_records`, `change_activity_events`, `change_policies`.
- Add nullable `change_id` to `continuous_improvement_actions` if needed for source/action linkage.
- Safe indexes: status/type, problem/action linkage, service/offering, planned window, approval status, task status, window time range and affected object.
- No destructive changes to tickets, problems, quality or knowledge tables.

### API / UI Plan

- Server package: `server/change/*` with contracts, serializers, service, risk, approval, calendar, tasks, PIR and analytics.
- Web API: `/api/web/changes*`, `/api/web/change-windows*`, `/api/web/change-calendar`, `/api/web/change-policies*` and `/api/web/changes/metrics/*`.
- Webapp: `/app/admin/changes` workspace with list, create wizard, risk/impact, plan/rollback, approval, calendar, tasks, PIR, affected objects, timeline and problem-to-change action.
- Problem integration: create change from problem permanent fix, copy service/offering and affected objects, record problem activity, show linked changes in problem detail.

### Implementation Snapshot

- Added migration `092_change_enablement` and SQLAlchemy models for `changes`, risk assessments, plans, approvals, windows, affected objects, tasks, PIR records, policies and activity events.
- Added `server/change/*`, `server/app/repos/change_repo.py`, and `server/web_api/change_handlers.py`.
- Added `/api/web/changes*`, `/api/web/change-windows`, `/api/web/change-policies`, create-from-problem and create-from-improvement-action routes.
- Added `/app/admin/changes`, sidebar navigation and a Problem workspace "Create change" action.
- Added `server/docs/CHANGE_ENABLEMENT.md` and updated DATABASE, SECURITY, CODEMAP, QUICK_LOOKUP, ARCHITECTURE_BOUNDARIES, PROBLEM, QUALITY, KNOWLEDGE and Service Catalog docs.

### Tests

- `server/tests/test_change_contract_no_db.py`
- `server/tests/test_change_repo.py`
- `server/tests/test_change_service.py`
- `server/tests/test_change_lifecycle.py`
- `server/tests/test_change_risk_assessment.py`
- `server/tests/test_change_approval_service.py`
- `server/tests/test_change_calendar.py`
- `server/tests/test_change_tasks.py`
- `server/tests/test_change_pir.py`
- `server/tests/test_change_problem_integration.py`
- `server/tests/test_change_service_catalog_integration.py`
- `server/tests/test_change_knowledge_quality_integration.py`
- `server/tests/test_change_api.py`
- `server/tests/test_change_privacy.py`
- `server/tests/test_change_analytics.py`
- `server/tests/test_change_policies.py`

Webapp tests:

- change API client;
- change workspace list/create/risk/approval/calendar/tasks/PIR;
- problem-to-change button/link.

### Verification

- Initial TDD red: `python -m pytest server/tests/test_change_contract_no_db.py -q --tb=short` failed with `ModuleNotFoundError: No module named 'change'`.
- `python -m pytest server/tests/test_change_contract_no_db.py ... server/tests/test_change_policies.py -q --tb=short` -> 22 passed on `codex/helpdesk-process-model`.
- `pnpm --dir webapp test -- src/features/changes/api.test.ts src/features/changes/change-workspace.test.tsx src/features/problems/problem-workspace.test.tsx` -> 4 passed.
- Problem/Quality focused regression passed: `test_problem_api.py`, `test_problem_service.py`, `test_problem_candidate_service.py`, `test_problem_slo_policy.py`, `test_problem_scheduler.py`, `test_quality_api.py`, `test_quality_workflow_integration.py`, `test_quality_smoke_regression.py`.
- Static/local checks passed: `python -m compileall -q server pc_agent scripts`, `git diff --check`, `python scripts/verify_workspace.py`, `python scripts/build_context_index.py --force`, `pnpm --dir webapp build`.
- Full canonical CI passed on commit `82a33a1ecfcaf308ffe2cd3c53cdb0beb33ab1e7`: `python scripts/run_ci_suite.py --server-pytest-timeout 7200 --pc-agent-pytest-timeout 3600 --idle-timeout 0`.
- Full CI artifact: `artifacts/ci/82a33a1ecfcaf308ffe2cd3c53cdb0beb33ab1e7/summary.json`.
- Full CI layer counts: `server_pytest_no_db` 323 passed; `server_pytest_db_knowledge` 90 passed; `server_pytest_db_tickets` 275 passed; `server_pytest_db_observer_diagnostics` 74 passed; `server_pytest_db_agent_runtime` 84 passed; `server_pytest_db_web_api` 195 passed; `server_pytest_agent_ws` 30 passed; `pc_agent_pytest` 315 passed.
- Remote release signoff passed on `82a33a1`: full-gated deploy, Alembic head, webapp bundle upload and `/api/health` smoke succeeded.
- Browser signoff passed at `https://192.168.100.17:9443/app/admin/changes`: created `CHG-000002`, approved risk/plan/request, scheduled, added/completed task, started implementation, implemented, completed PIR and closed with no console errors and all P5 network calls returning 200.
- Problem-to-change browser signoff passed: `/app/admin/problems` `Create change` created `CHG-000003 Permanent fix: P4 smoke RCA problem`, visible in `/app/admin/changes`.

### Rollback Notes

- Disable/hide change creation UI and keep `changes` read-only if P5 must be paused.
- Alembic downgrade `092` removes P5 change tables/links only; P0-P4 tables and workflows remain intact.
- No ticket workflow rollback is required because P5 does not change canonical ticket statuses or automatic ticket transitions.

### Remaining Risks

- P5 does not implement external calendar integrations, automatic execution, or full P5+ release orchestration; those are intentionally outside Change Enablement.
- P5 hardening archived/canceled demo records on the remote stand; no live demo change remains open.

## Latest Accepted Work: P5 Change Enablement Hardening

Status: accepted / compact release-candidate.

Scope:

- Expand `CHANGE_ENABLEMENT.md` with lifecycle matrix, examples and operator guide.
- Clarify standard change catalog by storing catalog examples under `change_policies.metadata.standard_catalog`; explicit `standard_preapproved=true` makes approvals skipped/non-required, not globally automatic.
- Harden calendar behavior with simple recurring RRULE support for blackout/maintenance windows and same-service/offering overlap detection for active planned changes.
- Track emergency retrospective overdue count through effective `max_emergency_retro_hours`.
- Harden change metrics: failure rate, rollback rate, lead time, implementation duration, PIR completion and emergency retrospective overdue.
- Mark or clean remote demo records from the previous P5 browser smoke.

Verification so far:

- RED: new focused tests failed for recurring blackout, same-service overlap, standard preapproval satisfaction and missing metrics keys.
- GREEN: `python -m pytest server/tests/test_change_calendar.py server/tests/test_change_policies.py server/tests/test_change_analytics.py -q --tb=short` -> 7 passed.
- P5 focused backend: `python -m pytest server/tests/test_change_contract_no_db.py server/tests/test_change_repo.py server/tests/test_change_service.py server/tests/test_change_lifecycle.py server/tests/test_change_risk_assessment.py server/tests/test_change_approval_service.py server/tests/test_change_calendar.py server/tests/test_change_tasks.py server/tests/test_change_pir.py server/tests/test_change_problem_integration.py server/tests/test_change_service_catalog_integration.py server/tests/test_change_knowledge_quality_integration.py server/tests/test_change_api.py server/tests/test_change_privacy.py server/tests/test_change_analytics.py server/tests/test_change_policies.py -q --tb=short` -> 26 passed.
- Webapp focused: `pnpm --dir webapp test -- src/features/changes/api.test.ts src/features/changes/change-workspace.test.tsx src/features/problems/problem-workspace.test.tsx` -> 3 files / 4 tests passed.
- Static/docs/build: `python -m compileall -q server pc_agent scripts`, `git diff --check`, `python scripts/build_context_index.py --force`, `python scripts/docs_inventory.py --check-links`, `python scripts/verify_workspace.py`, and `pnpm --dir webapp build` passed.
- Deploy/browser: quick release to remote stand passed on commit `b9047915494a6ddb58a05a34f443e66e86be7a6a`; `/api/health` smoke passed; `/app/admin/changes` showed failure/rollback/lead-time/emergency-retro metrics and archived demo rows with no console errors and all change API calls returning 200.
- Remote demo cleanup: `CHG-000001` and `CHG-000003` moved from `draft` to `canceled`; `CHG-000002` stayed `closed`; all three were renamed with `[demo archived]` and metadata `remote_demo_record=true`.
- Full canonical CI was not rerun for this compact hardening follow-up; the latest full P5 artifact remains `artifacts/ci/82a33a1ecfcaf308ffe2cd3c53cdb0beb33ab1e7/summary.json`.
- Remote server was stopped after smoke (`active=inactive`, `sub=dead`).

Remaining risks:

- External calendar integrations and rich RRULE support remain outside P5; current recurrence support intentionally covers simple daily/weekly maintenance and blackout windows.
- P5 still does not execute changes automatically; it governs approvals, timing, tasks, rollback and PIR only.

## Active Work: Tool Output Presentation Schema v1

Status: accepted / release-candidate.

Goal:

- Add a top-level `presentation_schema` contract next to `params_schema`, `output_schema` and `output_contract` so agent tool/module results can render as readable declarative UI blocks instead of raw JSON.

Scope:

- Agent registry: accept, preserve and expose `presentation_schema` without changing ToolResponse or Protocol V3.
- Built-in agent tools: add a real `system.collect` presentation schema and preserve `device_card` metadata for future inventory cards.
- Agent Recipe Runner: add primitive presentation schemas and a composite recipe schema without changing read-only execution semantics.
- Server diagnostics/capabilities: pass `presentation_schema` through descriptors, persisted recipe descriptors and primitive catalog responses without DB migrations.
- Webapp: add safe typed presentation schema helpers and `ModuleResultRenderer` / `CompositeRecipeRenderer`; integrate minimally into Capability detail and Diagnostic Center result preview while keeping raw JSON fallback.
- Docs/navigation: update module docs, CODEMAP and quick lookup/navigation catalog as required.

TDD checkpoints:

- RED agent registry tests for decorator extraction, flat tool spec projection and default `{}`.
- RED recipe primitive tests for `describe_primitives` presentation schemas.
- RED server capability tests for toolset and recipe descriptor pass-through.
- RED webapp renderer tests for field grid, table/checklist/timeline/artifact/raw fallback, invalid schema, missing paths and React escaping.

Verification target:

- Focused pytest for registry, recipe runner, server capability projection.
- Focused Vitest for renderer and diagnostics integration.
- `python -m compileall -q pc_agent scripts/navigation_catalog.py`, `python scripts/verify_workspace.py`, `python scripts/docs_inventory.py --check-links`, `git diff --check`, `git diff --cached --check`.
- Full `python -m pytest pc_agent/tests/ -v --tb=short`.

## Active Work: Tool Output Presentation Builder v1

Status: accepted / local verification passed.

Goal:

- Add managed server-side presentation schema overrides and a minimal admin UI builder so capability/tool output presentation can be edited, previewed and reset without changing module defaults or tool result wire formats.

Scope:

- Server storage/API: add `tool_presentation_overrides`, validation, effective schema resolution and `/api/web/tool-presentations` endpoints.
- Capability projection: keep module `presentation_schema` unchanged while exposing `effective_presentation_schema`, `presentation_schema_source` and `has_presentation_override`.
- Webapp: add a JSON editor builder in capability detail, output schema path picker, generated/sample result editor and live preview through the existing `ModuleResultRenderer`.
- Docs/navigation: document override semantics, API, security limits and builder entrypoints.

TDD checkpoints:

- RED server tests for default effective schema, override upsert, reset, validation failures and capability list effective projection.
- RED webapp tests for output schema path extraction, builder rendering, invalid JSON, live preview, save/reset calls and missing-schema fallback.

Verification target:

- Focused server pytest for presentation overrides and no-db diagnostic capabilities.
- Focused Vitest for builder/path picker and existing module result renderer.
- `pnpm --dir webapp build`, migration-focused server tests, docs checks, workspace verification and diff whitespace checks.

Implementation snapshot:

- Added migration `093_tool_presentation_overrides`, SQLAlchemy model `ToolPresentationOverride`, and `diagnostics.presentation_overrides` for validation, upsert/reset and effective schema projection.
- Added `/api/web/tool-presentations?tool_id=...` GET/PUT/DELETE and projected `effective_presentation_schema`, `presentation_schema_source` and `has_presentation_override` in capability APIs.
- Added `PresentationSchemaBuilder`, `schema-path-picker` helpers, generated sample result preview and Capability detail integration using the existing `ModuleResultRenderer`.
- Follow-up blocker fix: support timeline `tool_call_result` DTOs now expose bounded real `result_payload` plus effective presentation schema/source, and `/app/tickets` renders that payload through `ModuleResultRenderer` so completed `system.collect` results can show field grids, metrics and tables instead of only a compact JSON preview.

Verification:

- RED server/webapp tests failed on missing override service and builder modules before implementation.
- `python -m pytest server/tests/test_tool_presentation_overrides.py server/tests/test_diagnostic_capabilities_no_db.py server/tests/test_modules_manifest_no_db.py -v --tb=short` -> 41 passed.
- `python -m pytest pc_agent/tests/test_tool_presentation_schema_registry.py pc_agent/tests/test_tool_contract_runtime.py::test_builtin_specs_expose_contract_fields -v --tb=short` -> 4 passed.
- `pnpm --dir webapp test -- src/components/module-result/module-result-renderer.test.tsx src/components/module-result/schema-path-picker.test.ts src/components/module-result/presentation-builder.test.tsx src/features/diagnostics/diagnostic-center-panel.test.tsx` -> 4 files / 19 tests passed.
- `pnpm --dir webapp build`, `python -m compileall -q server pc_agent scripts`, `python scripts/docs_inventory.py --check-links`, `python scripts/verify_workspace.py` and `git diff --check` passed.

## Completed Work: Inventory Collect v1 + Device Card Slots

Status: accepted on branch `codex/inventory-collect-v1`, latest commit `d0a5dec`.

Goal:

- Add practical readable tool output value by collecting a privacy-safe endpoint inventory snapshot, persisting latest/history on the server, and rendering inventory/tool results through the shared presentation renderers in the device card and ticket timeline.

Scope:

- Agent: new built-in `inventory.collect` core module with detailed `output_schema`, `output_contract.kind=device.inventory.snapshot`, `device_card.slots` and default `presentation_schema`.
- Server: new `device_inventory_snapshots` persistence, command-result side effect for `inventory.collect`, latest/history projection and admin device inventory API with `effective_presentation_schema`.
- Webapp: `DeviceInventoryPanel` in `/app/admin/device`, collect button, compact inventory header/KPIs, `ModuleResultRenderer` preview, raw JSON fallback and shared `ToolResultEventCard` for ticket timeline results including composite recipes.
- Privacy: no screenshots, keystrokes, browser history, clipboard, document/message contents or file listings.

Verification so far:

- `python -m pytest pc_agent/tests/test_inventory_collect.py pc_agent/tests/test_tool_presentation_schema_registry.py pc_agent/tests/test_registry_and_module_loading.py pc_agent/tests/test_config_loader_core_modules.py -v --tb=short` -> 17 passed.
- `pnpm --dir webapp test -- src/components/module-result/module-result-renderer.test.tsx src/components/module-result/presentation-builder.test.tsx src/features/admin/device-inventory-panel.test.tsx src/components/module-result/tool-result-event-card.test.tsx` -> 4 files / 15 tests passed.
- `pnpm --dir webapp build` passed.
- `python -m pytest pc_agent/tests/ -v --tb=short` -> 329 passed, 7 subtests passed.
- `pnpm --dir webapp test` -> 232 passed.
- Real PostgreSQL migration reached `094 (head)` on the remote host.
- Browser smoke on updated remote agent collected a real `inventory.collect` snapshot and rendered it through `ModuleResultRenderer` in the device card.
- Server `test_client` API tests hang in the local Windows fixture even for pre-existing `test_tool_presentation_overrides` endpoint tests; direct service tests, compile checks, remote migration and browser checks covered the v1 blocker path.

## Active Work: Inventory Collect v2

Status: accepted / branch `codex/inventory-collect-v2`.

Goal:

- Harden endpoint inventory for operational use without turning it into full CMDB: richer printer details, static key-app detection profiles, optional hardware identifiers, lightweight binding fields, scheduled refresh policy and a server-readable builtin descriptor catalog.

Scope:

- Agent: v2 printer details, key-app profile detector, optional hardware identifiers, updated output/presentation schemas while preserving v1 result shape.
- Shared/server descriptor: move declarative `inventory.collect` schemas into a pure shared catalog so server fallback no longer imports agent collector implementation.
- Server: binding metadata, refresh policy storage/API, due-selection helper using existing `ToolExecutionService.run_tool`, latest inventory payload extension.
- Webapp: DeviceInventoryPanel v2 with binding editor, schedule status, printers/software tabs and unchanged `ModuleResultRenderer`/raw JSON fallback.
- Privacy: endpoint technical inventory only; no screenshots, keystrokes, clipboard, browser history, document contents, messages or personal file listings.

Implementation snapshot:

- Agent `inventory.collect` v2 now returns best-effort printer details, static key-app profile summaries and optional hardware identifiers while preserving the v1 top-level shape.
- Declarative inventory descriptors live in `shared.builtin_tool_descriptors`; server fallback uses this pure catalog instead of importing `pc_agent.modules.impl.inventory`.
- Server added `device_inventory_bindings` and `device_inventory_refresh_policies`, binding/refresh APIs, latest inventory payload extensions and an `InventoryRefreshRuntime` that dispatches `inventory.collect` through the existing `ToolExecutionService`.
- Webapp `DeviceInventoryPanel` shows inventory source/slots, binding editor, refresh schedule controls/status, v2 printer/software/hardware blocks and raw JSON fallback through `ModuleResultRenderer`.

Verification:

- `python -m pytest pc_agent/tests/test_inventory_collect.py pc_agent/tests/test_inventory_profiles.py pc_agent/tests/test_registry_and_module_loading.py -v --tb=short` -> 17 passed.
- `python -m pytest pc_agent/tests/ -v --tb=short` -> 333 passed, 7 subtests passed.
- `python -m pytest server/tests/test_inventory_presentation_unit.py server/tests/test_tool_service_auto_install_no_db.py -v --tb=short` -> 6 passed.
- `pnpm --dir webapp test -- src/components/module-result/tool-result-event-card.test.tsx src/features/admin/device-inventory-panel.test.tsx` -> 2 files / 6 tests passed.
- `pnpm --dir webapp test -- src/app/router.test.tsx` -> 7 passed after widening the lazy route assertion timeout for full-suite contention.
- `pnpm --dir webapp test` -> 47 files / 234 tests passed.
- `pnpm --dir webapp build`, `python -m compileall -q pc_agent server shared scripts/navigation_catalog.py`, `python scripts/docs_inventory.py --check-links`, `python scripts/verify_workspace.py`, `git diff --check` and `git diff --cached --check` passed.
- Remote quick release ran Alembic `094 -> 095` on PostgreSQL, started server/control and passed `/api/health` smoke.
- Browser smoke at `https://192.168.100.17:9443/admin` opened the real device card, saved/restored binding fields, saved disabled refresh schedule status, restarted the updated remote agent and ran `inventory.collect`; latest API returned a fresh `2026-05-19T05:08:08Z` snapshot with `printers.items`, 11 key-app profiles, hardware identifier fields, binding and refresh policy, and the UI rendered the v2 blocks with no browser console warnings/errors.

Known verification limitation:

- Local Windows DB-backed server `pytest` fixtures still hang on existing `test_client` DB tests, including pre-existing presentation override tests. The v2 DB migration and API/browser path were verified on the real PostgreSQL stand instead.

## Active Work: Inventory Processes Items / Agent 3.1.59

Status: accepted / released on branch `codex/helpdesk-process-model`, commit `8605a03`.

Goal:

- Extend `inventory.collect` so device inventory shows real running processes instead of using the legacy "Ключевое ПО" presentation block as the primary operational list.

Scope:

- Agent: add bounded `processes.items` to the core built-in `inventory.collect` payload, sorted by memory and limited to 50 rows.
- Shared descriptor: add `processes` to the output schema/device-card slots and repoint the default presentation table to `processes.items` with title "Процессы".
- Compatibility: keep `software.key_apps` in the payload for existing server summaries/reports.
- Release: bump agent to `3.1.59`, build and publish Windows/Linux release artifacts after local checks.

Verification plan:

- `python -m pytest pc_agent/tests/test_inventory_collect.py pc_agent/tests/test_linux_packaging.py -q --tb=short` -> 8 passed.
- `pnpm --dir webapp test -- src/features/admin/device-inventory-panel.test.tsx src/components/module-result/tool-result-event-card.test.tsx` -> 2 files / 7 tests passed.
- `python -m pytest pc_agent/tests/ -q --tb=short` -> 342 passed, 7 subtests passed.
- `pnpm --dir webapp build` passed.
- `python scripts/verify_workspace.py` passed.
- `python -m pytest server/tests/test_inventory_presentation_unit.py server/tests/test_tool_service_auto_install_no_db.py -q --tb=short` -> 6 passed.
- Packaged Windows/Linux verify passed for 3.1.59.
- Uploaded release artifacts to the server registry and assigned stable rollout for `windows_amd64` and `linux_alt_x86_64`.
- Released the updated web bundle to the stand with quick gate and `--leave-running`.
- Live `inventory.collect` on ADMIN-2 (`7a3429ec-1c0b-5495-9aad-b284f08ae965`) succeeded: snapshot `f00a5b35-d738-4a72-9762-9cb1094d99a8` contains `processes.items` with 50 rows from 292 processes, and browser verification shows the `Процессы` block with real rows such as `Codex.exe` and `pc_agent.exe`.

## Active Work: Inventory v3 / Lightweight CMDB

Status: accepted / verified on branch `codex/inventory-v3-lightweight-cmdb`, commit `3b9b50c`.

Goal:

- Add a lightweight operational inventory layer on top of v2 without building a procurement/accounting CMDB: binding history, CSV import/export, fleet dashboard, refresh run visibility and stale/missing reports.

Scope:

- Cleanup: keep `shared.builtin_tool_descriptors` as the only descriptor source of truth and move inventory admin endpoints out of the large `admin_handlers.py` while preserving URLs.
- Server: add binding status/tags, binding history, CSV dry-run/apply import, binding and inventory CSV export, fleet dashboard aggregation and refresh run records.
- Webapp: enhance `/app/admin/inventory` with fleet summary/import/export/report sections and enhance `DeviceInventoryPanel` with stale status, binding history and refresh run visibility.
- Privacy: aggregate endpoint inventory and admin-entered binding metadata only; no employee activity monitoring or user-content collection.

Verification plan:

- Phase 0 cleanup: `python -m pytest pc_agent/tests/test_inventory_collect.py pc_agent/tests/test_inventory_profiles.py -v --tb=short`, `python -m pytest server/tests/test_inventory_presentation_unit.py server/tests/test_tool_service_auto_install_no_db.py -v --tb=short`, `python -m compileall -q pc_agent server shared scripts/navigation_catalog.py`, `git diff --check`.
- Server focused: binding history, CSV import/export, dashboard aggregation, refresh run service/scheduler, no-db inventory presentation tests.
- Webapp focused: inventory dashboard totals/import/export, device panel binding history/refresh history/stale badge, plus full `pnpm --dir webapp test` and build.
- General: docs link check, workspace verify, diff whitespace checks, migration upgrade on the remote PostgreSQL stand if DB schema changes are committed.

Implementation notes:

- Cleanup: `inventory.collect` descriptors remain single-source in `shared.builtin_tool_descriptors`; inventory admin HTTP handlers moved to `server/web_api/admin_inventory_handlers.py` without changing existing URLs.
- DB: migration `096_inventory_v3_lightweight_cmdb` adds `status`/`tags` to `device_inventory_bindings`, plus `device_inventory_binding_history` and `device_inventory_refresh_runs`.
- Server/API: `/api/web/admin/devices/{device_id}/inventory` is extended backward-compatibly with `binding_history`, `refresh_runs` and `last_refresh_run`; new endpoints cover binding history, binding CSV import/export, fleet inventory CSV export, dashboard aggregation and refresh run listing.
- Webapp: `/app/admin/inventory?panel=fleet` renders fleet summary, CSV export buttons and dry-run/apply binding import; `DeviceInventoryPanel` shows stale status, tags/status binding fields, binding change history and refresh run history.
- Verification: remote PostgreSQL migration `095 -> 096` completed, browser smoke on `https://192.168.100.17:9443/admin` verified the fleet dashboard after fixing the dashboard `last_requested_at` null case, local focused/full agent and webapp tests passed, and the branch was pushed to GitHub.

## Active Work: Inventory v4 / Fleet Operations, Workplace Registration v1 and Presence v1

Status: accepted / verified on branch `codex/inventory-v4-registration-presence`; remote quick release, PostgreSQL migration and browser smoke passed on 2026-05-19. Full release gate remains an explicit final-release checkpoint.

Goal:

- Extend lightweight inventory into fleet operations without building a procurement/accounting CMDB: selected/stale/missing/department/building bulk refresh, operation tracking, reports, XLSX export, profile-based workplace binding suggestions and safe workplace presence snapshots.

Scope:

- Agent: add `presence.collect` as a core built-in read-only module with `output_schema`, `output_contract.kind=device.presence.snapshot` and `presentation_schema`; keep `inventory.collect` shape and descriptors stable.
- Server: add migration `097_inventory_v4_registration_presence` for bulk operations/items, binding suggestions and presence snapshots/daily summaries; extend inventory dashboard/report/export APIs; persist `presence.collect` command results; create non-destructive binding suggestions from agent profiles.
- Webapp: enhance `/app/admin/inventory?panel=fleet` with bulk refresh, attention groups and XLSX export; enhance `DeviceInventoryPanel` with agent profiles, binding suggestions and workplace presence.
- Privacy: presence is endpoint availability/session state only. It must not collect screenshots, keystrokes, mouse coordinates, window titles, browser history, full URLs, document contents, clipboard contents, messages or personal file listings. Agent profiles may suggest binding fields but must not overwrite confirmed binding automatically.

Verification target:

- Agent focused: `python -m pytest pc_agent/tests/test_presence_collect.py pc_agent/tests/test_inventory_collect.py pc_agent/tests/test_inventory_profiles.py pc_agent/tests/test_registry_and_module_loading.py -v --tb=short`.
- Server focused: `python -m pytest server/tests/test_inventory_v4_service.py server/tests/test_inventory_v3_service.py server/tests/test_inventory_presentation_unit.py server/tests/test_tool_service_auto_install_no_db.py -v --tb=short`; DB-backed v3/v4 tests are expected to run on Linux/CI and skip on Windows.
- Webapp: `pnpm --dir webapp test`, `pnpm --dir webapp build`, `pnpm --dir webapp exec tsc --noEmit`.
- General: `python -m compileall -q pc_agent server shared scripts/navigation_catalog.py`, docs link check, workspace verify, `git diff --check`, and remote PostgreSQL migration/browser smoke before release acceptance.

Verification:

- Passed: focused `presence.collect`/inventory/registry/config-loader agent tests, full `pc_agent/tests/`, focused server no-db/inventory presentation tests, webapp full Vitest suite, webapp typecheck/build, `compileall`, docs link check, workspace verification and diff whitespace checks.
- Passed remote/browser smoke: `/app/admin/inventory` fleet dashboard opens, bulk-refresh dry-run works, `/app/admin/device` shows the inventory card, and `DeviceInventoryPanel` now exposes Registration/Presence tabs even before the first inventory snapshot.
- Windows-local DB-backed inventory v3/v4 service tests skip by design. The remote runtime venv does not include pytest, so DB-backed Linux pytest must run in CI or a test venv, not on the production runtime venv.

## Active Work: Device Registration Claims and Authoritative User Binding

Status: in progress on branch `codex/helpdesk-process-model`.

Goal:

- Replace direct self-reported requester-profile ownership assignment with a controlled device registration workflow: claim creation, user/admin confirmation, conflict handling, active authoritative binding, audit history and ticket requester enrichment.

Classification:

- Cross-cutting DB/API/server-agent-web change. Contract surfaces: DB schema/models/repos, `/api/registry*` and `/api/web/admin/registry*`, handshake `handshake_ack.payload.registration`, ticket create requester context, React registry payload, agent GUI/API profile handling.

Scope:

- Server DB: add `registry_person_identities`, `device_registration_claims`, `device_user_bindings`, `device_registration_events`; extend `device_inventory_bindings` and `tickets`.
- Server domain: add `RegistrationRepo` and `RegistrationService`; make `RegistryIngestionService.ingest_requester_profile()` create/update claims and suggestions without directly assigning `registry_assets.assigned_person_id`.
- Server API: add agent/user registration profile/status/confirm endpoints and admin claim approve/reject/binding revoke/timeline endpoints.
- Server integrations: include registration status in handshake ack; enrich ticket creation from active primary binding without blocking unregistered devices.
- Webapp: extend `/app/admin/registry` with registration tab, badges, claim actions and new registry quality signals.
- Agent: add local user profile manager, registration API methods, handshake registration status handling and minimal GUI/status integration.

Non-goals:

- Do not convert `devices` into owner records.
- Do not trust self-reported profile data as authoritative.
- Do not change token/fingerprint/device-auth semantics.
- Do not run full CI/full deploy gate unless explicitly requested after a frozen candidate.

Execution plan:

- [ ] Step 1: Complete discovery of current migrations, models, registry/ticket/handshake/webapp/agent entrypoints.
- [ ] Step 2: Add failing server service/API/ticket/handshake tests around no direct assignment, approve/reject/conflict, status payload and ticket enrichment.
- [ ] Step 3: Add migration `098` and SQLAlchemy models/columns/indexes.
- [ ] Step 4: Implement `RegistrationRepo` and `RegistrationService` with identity normalization, claim dedupe, conflict detection, active binding sync, events and inventory binding sync.
- [ ] Step 5: Modify registry ingestion and snapshot payload/data-quality signals.
- [ ] Step 6: Add registration HTTP endpoints and route registration with auth boundary checks.
- [ ] Step 7: Add handshake registration payload and ticket requester binding enrichment.
- [ ] Step 8: Extend React admin registry API/types/page and run webapp type/build checks.
- [ ] Step 9: Add agent user profile manager/API/status handling and focused agent tests.
- [ ] Step 10: Run targeted verification: workspace verify, server registration/registry/inventory/ticket/auth tests, agent tests and webapp build/typecheck.

Verification matrix:

- Server focused: `python -m pytest server/tests/test_device_registration_service.py server/tests/test_registration_api.py -q`.
- Registry/inventory/ticket regressions: `python -m pytest server/tests/test_registry_service.py server/tests/test_inventory_v4_service.py server/tests/test_soft_delete_auth.py -q` plus ticket create tests found during implementation.
- Agent focused: `python -m pytest pc_agent/tests/test_user_profile_manager.py pc_agent/tests/test_registration_status.py pc_agent/tests/test_connection_request_flow.py -q`.
- Webapp: run the actual package script from `webapp/package.json` (`pnpm --dir webapp run build` or available typecheck).
- General: `python scripts/verify_workspace.py`, migration import/syntax check, and `git diff --check`.

2026-05-23 account-session extension:

- Added the requester/account session layer for the Qt agent GUI without changing machine-token auth: `GET /api/registry/agent/account-state`, `AccountSessionManager`, non-modal `AccountGateWidget`, ticket `requester_account` context and other-account ticket marking.
- Account gate is the first app page; settings remain available before login, while ticket list/create/detail paths require a valid local account session confirmed against account-state.
- Other-account login is local-only, does not call registration submit/confirm, and server ticket creation stores `custom_fields.requester_account_context.created_from_other_account=true` plus the active registered-device binding/person context without creating a registration claim.
- Focused verification added: `server/tests/test_registration_api.py`, `server/tests/test_ticket_registration_enrichment.py`, `pc_agent/tests/test_account_session_manager.py`, `pc_agent/tests/test_account_gate.py`, `pc_agent/tests/test_registration_status.py`.

2026-05-23 server-backed account-session hardening:

- Goal: replace local-only requester account selection with server-issued account sessions while preserving machine-token auth as device auth.
- Classification: cross-cutting DB/API/server-agent-web change. Contract surfaces: migration/models/repos, `/api/registry/agent/account-*`, admin registry review endpoints, `/api/tickets/create` requester account validation, Qt account gate/session storage, support/admin ticket context.
- Plan:
  - [x] Add regression tests for phone/reason preservation, other-account visibility rules, server session creation/validation, other-account request approval, and ticket create with server sessions.
  - [x] Add migration `099` and SQLAlchemy models for `device_account_sessions` and `device_account_login_requests`.
  - [x] Implement `AccountSessionRepo` and `AccountSessionService` for confirmed-binding sessions, other-account login requests, admin approve/reject and session validation.
  - [x] Extend registry endpoints/routes and account-state read model with server sessions, pending requests and allowed actions.
  - [x] Change ticket create to trust `requester_account.session_id` instead of client-supplied identity payload, leaving legacy self-declared other-account as explicitly unverified.
  - [x] Update Qt API client, `AccountSessionManager`, account gate and main window so confirmed login creates a server session and other-account login creates an approval request, not an instant local session.
  - [x] Ensure legacy local requester profiles cannot override selected account sessions in ticket creation.

## Active Work: Registry Management Center P0

Status: in progress on branch `codex/helpdesk-process-model`.

Goal:

- Turn `/app/admin/registry` from a mostly read-only registry overview into an action-first Registry Management Center for device-user bindings, people identities, registration claims and requester account sessions.

Classification:

- Cross-cutting Registry / typed web boundary / React UI change. Contract surfaces: `server/registry/*`, `server/app/repos/*`, `server/web_api/registry_handlers.py`, `server/routes.py`, `webapp/src/features/admin/api.ts`, `/app/admin/registry`, `server/docs/CODEMAP.md`, `docs/QUICK_LOOKUP.md`.

P0 scope:

- Server: add service-backed admin operations for bind person to device, transfer primary owner, add shared user, assign responsible person, revoke dependent account sessions on binding revoke/transfer, global account-session listing and basic person/identity admin mutations.
- Server snapshot: expand `GET /api/web/admin/registry` with device summaries, people counts, binding rows, account sessions, login requests and action metadata while preserving existing fields for current consumers.
- Webapp: refactor `registry-page.tsx` into a page orchestrator and feature components under `webapp/src/features/admin/registry/`; implement tabs `Обзор`, `Устройства`, `Пользователи`, `Привязки`, `Заявки`, `Аккаунт-сессии`, `Качество данных`; keep `Локации`, `Подразделения`, `Политики` as useful P1 placeholders.
- UX: global search, quick actions, reusable right detail panel, modal actions with reason fields for destructive/ownership operations, React Query invalidation for `admin-registry` and account-session queries.

Non-goals for this pass:

- Full locations/departments/policies CRUD.
- Person duplicate merge/split workflow beyond showing actionable placeholders.
- New DB schema unless existing tables cannot represent the P0 lifecycle.
- Full CI/full release gate unless explicitly requested after a frozen candidate.

Execution plan:

- [x] Step 1: Run intake, rebuild context index, bootstrap web toolchain and inspect existing registry/account-session contracts.
- [x] Step 2: Add failing backend tests for manual bind, primary conflict, replace/transfer, shared/responsible bindings and dependent account-session revoke.
- [x] Step 3: Implement `RegistrationService` admin binding helpers and `AccountSessionService` dependent-session revoke/list helpers.
- [x] Step 4: Add admin registry routes/handlers and update `server/routes.py`.
- [x] Step 5: Expand `RegistryIngestionService.build_snapshot()` payload with P0 summary/device/person/binding/session fields.
- [x] Step 6: Add frontend API types and mutation helpers.
- [x] Step 7: Replace `/app/admin/registry` with orchestrator + P0 tab components, dialogs and detail drawer.
- [x] Step 8: Update `server/docs/CODEMAP.md`, `docs/QUICK_LOOKUP.md` and this plan status.
- [ ] Step 9: Run focused backend tests, webapp build/test target if available, `compileall`, `verify_workspace.py` and `git diff --check`.

Verification target:

- Backend: `python -m pytest server/tests/test_registry_admin_actions.py -q`, `python -m pytest server/tests/test_device_registration_service.py server/tests/test_registration_api.py server/tests/test_account_session_service.py server/tests/test_ticket_account_access.py -q`.
- Webapp: `pnpm --dir webapp run build`; run registry-targeted Vitest if a useful test target is added.
- General: `python -m compileall server pc_agent`, `python scripts/verify_workspace.py`, `git diff --check`.
- Browser: MCP/browser check at `https://192.168.100.17:9443/admin` after deploy/smoke if this pass reaches remote verification.
  - [x] Add minimal admin registry UI/API client support for reviewing other-account login requests if feasible in this pass.
  - [x] Update CODEMAP/quick lookup docs for new account-session contract.
  - [ ] Run focused server/agent tests, compileall, webapp build, workspace verify and diff checks; commit and push.

2026-05-25 registration claim reconciliation follow-up:

- Goal: close the live-smoke gap where an agent can submit duplicate registration claims while pending, manual admin binding can create an active binding while the user claim remains open, and the Qt GUI can enter the main ticket workspace while registration is still pending.
- Classification: cross-cutting Registry / account-session / Qt GUI contract change. Contract surfaces: `RegistrationService.submit_agent_profile_claim()`, admin bind helpers, `/api/registry/agent/account-state`, registration form payload, `AccountGateWidget`, `MainWindow` ticket gating and registry docs/CODEMAP.
- Plan:
  - [x] Add RED tests for device-level open-claim dedupe, admin-bind claim reconciliation and pending GUI gate behavior.
  - [x] Reuse an existing open device claim instead of creating parallel pending claims for the same agent device/source.
  - [x] Make manual admin bind satisfy or supersede pending agent claims for the same device and invalidate pending-session login via terminal claim state.
  - [x] Keep `registration_pending` visible in account gate but block the normal app workspace until a confirmed binding or verified other-account session is selected.
  - [x] Add registration form policy hooks for strict existing department/location picker fields while preserving configurable fallback to pending free-text requests.
  - [x] Update docs/CODEMAP and run focused server/agent checks.

2026-05-26 GUI ticket E2E follow-up:

- Source scenario: local Windows GUI agent v3.1.60 created ticket `T-000602` (`1f83c6be-cf21-434a-89bb-fc3bebaed3ed`), support web UI moved it through `queued -> in_progress -> resolved`, requester confirmed closure in the GUI, final status `closed`.
- Bug: the GUI create-ticket preview displayed boolean fields `critical_service` and `public_service` as `Да`, while the submitted ticket workspace stored both as `Нет`. Future fix: add a regression around preview/value formatting for boolean custom fields and align the preview renderer with the final request payload serializer.
- Bug: support web UI showed inconsistent priority labels for the same ticket: action list used the legacy/computed priority (`P2`) while the ticket card/header used effective priority class (`P1`). Future fix: choose one canonical display field for support surfaces, preferably the effective `priority_class`, and add a UI/API contract test for `priority`, `priority_class`, and modifier-derived priority decisions.
- Data quality issue: some tool descriptions in the support workspace API response contained replacement question marks instead of readable Russian text. Future fix: trace those module metadata records to their source encoding and add UTF-8 validation for tool catalog ingestion/rendering.

## Live V3 / Tickets / Agent deep validation

Status: in progress.

Scope:

- Live server and local Windows PC Agent validation for Protocol V3, tickets, modules, run_tool, account-session boundary, local agent GUI and browser/admin UI.
- Bugs are evidence-recorded here and not fixed immediately unless they block downstream live testing with no reasonable workaround.
- For UI-visible flows, a scenario is not green until browser/admin UI confirmation and, where agent-facing, pywinauto/UIA confirmation are recorded.

Initial evidence journal:

- Started: 2026-05-27T00:12:42+05:00.
- Branch: `codex/helpdesk-process-model`.
- Commit: `b64eb2f0e4235dc930dfbc52a1805aef50ace646`.
- Server URL: `https://192.168.100.17:9443`.
- Browser/admin URL: `https://192.168.100.17:9443/admin`.
- Local workspace: `C:\Users\admin-2\CodexProjects\pc_client`.
- Remote workspace: `/var/chat_bot/pc_client` on `192.168.100.17`.
- Required docs read before execution: `AGENTS.md`, `docs/QUICK_LOOKUP.md`, `docs/ARCHITECTURE_BOUNDARIES.md`, `server/docs/PROTOCOL_V3.md`, `pc_agent/docs/PROTOCOL_V3.md`, `server/docs/TICKET_SYSTEM.md`, `server/docs/MODULES_API.md`, `pc_agent/docs/CODEMAP.md`, `server/docs/CODEMAP.md`.
- pywinauto requirement: pending verification with `python -c "import pywinauto; print(pywinauto.__version__)"`, must be `0.6.9` and UIA backend.
- Server status/log paths: pending collection through `scripts/manage_remote_stack.py status|logs`.
- Agent device_id/machine_id/version/log paths: pending collection from local UI bridge/process/SQLite.
- Server DB evidence path: pending selection of safe query method; raw tokens must not be logged.
- Browser evidence path: pending Playwright/browser session against canonical admin URL.

Diagnostic tooling plan:

- `scripts/live_ws_v3_probe.py`: created. Purpose: send safe Protocol V3 handshake/double-connection probes, validate close codes and ACK/NACK correlation, never print raw token, accept token via `PC_CLIENT_AGENT_TOKEN` or secure prompt, log token prefix/sha length only. Current scope covers P0.2/P0.3; malformed outbox support still pending for P0.10.
- `diag_live.sleep`: needed only if no existing cancellable long-running safe tool/module is available. Purpose: read-only sleep/progress/cancel validation for P0.8.
- `diag_live.artifact`: needed only if no existing safe artifact-producing tool exists for P2.2.
- `diag_live.consent`: needed only if no existing consent-required safe tool exists for P1.3.

P0 checklist:

- [x] P0.1 Agent handshake happy path: passed after server restart recovery; BUG-20260527-01 recorded for server stop.
- [x] P0.2 Invalid Protocol V3 handshake: failed close-code observation; BUG-20260527-02 recorded.
- [x] P0.3 Same device double connection: state handling partial pass, close-code failure covered by BUG-20260527-02.
- [x] P0.4 Agent account-session boundary for ticket create: direct HTTP paths verified; GUI/UIA and automation bridge defects recorded as BUG-20260527-03/04.
- [x] P0.5 WS `chat_raise` account-boundary check: failed; BUG-20260527-05 recorded.
- [x] P0.6 Full ticket lifecycle: passed for canonical path and blocked assigned-without-assignee check; permissive resolve policy noted.
- [x] P0.7 `run_tool` happy lifecycle: passed for `system.collect`.
- [x] P0.8 Long-running tool + `cancel_operation`: partial pass; BUG-20260527-06/07 recorded.
- [x] P0.9 Module/toolset snapshot after module lifecycle: partial pass; BUG-20260527-08 recorded.
- [x] P0.10 Protocol V3 malformed outbox probes: failed; BUG-20260527-09 recorded.

P1/P2 checklist:

- [ ] P1.1 Outbox ACK/NACK/dedup.
- [ ] P1.2 Command idempotency.
- [ ] P1.3 Consent flow.
- [ ] P1.4 Module auto-install before `run_tool`.
- [ ] P1.5 Restart/reconnect with pending state.
- [ ] P1.6 Browser/UI projection consistency.
- [ ] P2.1 Public/requester safety.
- [ ] P2.2 Attachments/artifacts.
- [ ] P2.3 Two-agent matrix, if a second agent is available.

Scenario evidence:

### BUG-20260527-01 — Live server stopped during P0.1 baseline

Severity: P0
Status: verified-fixed
Area: other

Scenario:
P0.1 baseline collection while starting `live-v3-deep` local Windows launcher/GUI agent against `wss://192.168.100.17:9443/ws`.

Expected:
Live server remains running during agent provisioning and browser/API checks.

Actual:
`scripts/manage_remote_stack.py status server` reported `server: stopped (active=inactive, sub=dead)`. Server log tail showed `pc-client-server.service: Main process exited, code=killed, status=9/KILL` at 2026-05-27 00:16:51+05.

Repro steps:
1. Start local GUI launcher instance `live-v3-deep` with `python scripts/manage_local_agent.py start live-v3-deep --gui --launcher --ws-url wss://192.168.100.17:9443/ws --api-url https://192.168.100.17:9443/api`.
2. Read `/ui/agent/status` from `http://127.0.0.1:8765/ui/agent/status`.
3. Attempt admin session/API baseline and server log/status collection.

Evidence:
- Server log: `pc-client-server.service: Main process exited, code=killed, status=9/KILL`; `Stopped pc-client-server.service`.
- Agent log: local agent was waiting for connection approval with `has_auth_token=false`, `connection_state=initializing`.
- Browser/UI: pending; browser confirmation not possible while server returned `502 Bad Gateway`.
- Server DB: pending; DB query not run before restart.
- Agent SQLite: pending.
- WS/API payload: `/api/health` over `https://192.168.100.17:9443` returned `502 Bad Gateway` after stop.

Impact:
Blocks all P0 live scenarios until the server is restarted. It also invalidates any handshake/browser evidence gathered after the stop timestamp.

Root cause hypothesis:
Unknown runtime/process incident or external stop; evidence currently shows SIGKILL rather than an application exception. Needs later correlation with host resource logs/systemd history if it repeats.

Fix policy:
- Blocking further tests: yes
- Fixed now: no product code fix; recover by restarting the live server with the project control script and continue testing.

Fix summary, if fixed:
N/A.

Verification after fix:
Server restarted with `python scripts/manage_remote_stack.py start server`; fresh P0.1 handshake completed after restart.

Regression check:
P0.1 adjacent check after restart: agent provisioning, token delivery, WS handshake, browser inventory and UIA checks all collected.

Remaining risk:
If SIGKILL repeats under live load, P0 cannot be completed reliably without host-level root cause analysis.

### P0.1 Agent handshake happy path

Status: passed after server restart; browser/admin and UIA evidence recorded.

Evidence:
- Transport:
  - Agent provisioning request created `request_id=f26ccfe4-1e51-48d8-967c-fd47ec4112b1`, approved by admin through `/api/web/admin/connection_requests/{device_id}/approve`.
  - Server created agent token with prefix `d7ad25a1`; raw token was not printed.
  - Agent log: connected to `wss://192.168.100.17:9443/ws`, sent authenticated handshake, received `handshake_ack` at 2026-05-27 00:17:43+05.
  - Server log: `Protocol: ws_ticket_v3`; capabilities included `protocol_v3`, `envelope_v3`, `outbox_ack_v3`, `trace_correlation`, `nack_support`, `outbox_batch_v1`, `consent_flow`, `rpc_request`, `rpc_response`, `outbox_item`, `job_events`, `device_events`.
  - No reconnect loop observed after token delivery; `/ui/agent/status` reported `connection_state=connected`, `connection_detail=WS подключён`.
- Server DB/state:
  - `devices`: `device_id=7a3429ec-1c0b-5495-9aad-b284f08ae965`, hostname `ADMIN-2`, OS `Windows`, `agent_version=3.1.61`, `protocol_version=ws_ticket_v3`, `last_seen_at=2026-05-27 00:18:07+05`, `last_handshake_at=2026-05-27 00:18:07+05`, `current_toolset_hash=464075d978b3230f`.
  - `connection_requests`: latest row `approved`, `request_id=f26ccfe4-1e51-48d8-967c-fd47ec4112b1`, `approved_token_delivered_at=2026-05-27 00:18:07+05`, machine/install ids match agent identity.
  - `agent_tokens`: active token prefix `d7ad25a1`, `last_used_at=2026-05-27 00:28:26+05`; prior active token prefix `8f8a95da` still exists.
  - `device_toolset_snapshots`: existing snapshot `snapshot_id=1`, `tool_count=6`; `device_outbox` latest `list_tools` was already `delivered` from an earlier snapshot flow.
- Agent local state:
  - Local launcher instance `live-v3-deep`, PID `32636`, mode `gui/launcher`, UI port `8765`; child `pc_agent.exe` PID `27208`.
  - `/ui/agent/status`: device_id `7a3429ec-1c0b-5495-9aad-b284f08ae965`, agent_version `3.1.61`, `has_auth_token=true`, `ui_bridge_running=true`, `connection_state=connected`, release channel `stable`, recommended version `3.1.61`.
  - `/ui/automation/status`: `window_visible=true`, `bridge_connected=true`, `connection_state=connected`, `has_active_profile=true`, active GUI view `tickets`, `ticket_count=1`.
  - SQLite `storage.db`: tables include `outbox`, `outbox_sent_history`, `seen_commands`, `pending_consents`, `auth_tokens`; `outbox=[]`, `outbox_sent_history=[]`, `seen_commands=[]`, `pending_consents=[]`, `auth_tokens` has one active redacted token row for the device.
  - Log paths: `C:\Users\admin-2\CodexProjects\pc_client\.local-agent\instances\live-v3-deep\data\logs\agent.log`, `action_trace.jsonl`, launcher log `C:\Users\admin-2\CodexProjects\pc_client\.local-agent\instances\live-v3-deep\launcher.log`.
- Browser/admin UI:
  - Browser URL: `https://192.168.100.17:9443/app/admin/inventory?device=7a3429ec-1c0b-5495-9aad-b284f08ae965`.
  - Visible admin inventory row: `ADMIN-2`, `7a3429ec...e965`, status `Онлайн`, OS `Windows`, version `3.1.61`, activity `27 мая 2026 г., 00:18`, state `Готово к действиям`.
  - Detail panel visible: `ADMIN-2`, `Онлайн`, version `3.1.61`, identifier `Windows MachineGuid`, tokens `2`, active `2`, no identity duplicates warning.
  - Screenshot: Playwright `live-v3-p0-1-admin-inventory.png`.
- Agent GUI/UIA:
  - `python -c "import pywinauto; print(pywinauto.__version__)"` returned `0.6.9`.
  - UIA backend used: `Application(backend="uia").connect(process=27208)`.
  - Initial control tree showed window `Maria Agent v3.1.61`, registration gate texts `Этот ПК зарегистрирован за:`, `admin-2`, `admin_confirmed`, button `Войти как admin-2`.
  - UIA `invoke()` on `Войти как admin-2` opened the main requester workspace.
  - Main UIA tree showed `Обращения`, sidebar account `admin-2 | Подтвержденный аккаунт`, agent status card `Агент v3.1.61`, `Релиз актуален`, and security footer `Ваше соединение защищено...`.
  - Screenshots: `artifacts/live-v3-p0-1-agent-uia-after-login.png`, `artifacts/live-v3-p0-1-agent-main-uia.png`.
- Root cause notes:
  - `BUG-20260527-01` was recovered by server restart; no product code fix applied.
  - Launcher log contains mojibake/replacement characters while `agent.log` is readable UTF-8. This is a log-quality risk to track if it affects later evidence collection.

### P0.2 Invalid Protocol V3 handshake

Status: failed; BUG-20260527-02 recorded.

Evidence:
- Diagnostic tool: `scripts/live_ws_v3_probe.py invalid-handshake --case <case>`, compiled with `python -m py_compile`.
- Transport:
  - Cases run: `wrong_protocol`, `missing_protocol_v3`, `missing_envelope_v3`, `missing_outbox_ack_v3`, `missing_token`, `invalid_token`.
  - Probe request/trace examples:
    - `wrong_protocol`: `request_id=0ad36cdb-f73f-48d4-8b4d-98c307d05530`, `trace_id=6cf40ae4-8a73-4c63-b591-3eaf7f18b0d8`.
    - `invalid_token`: `request_id=6d164bfd-fa0c-42d2-9c9b-6aa17f149404`, `trace_id=fd09777a-9df1-4339-bea2-0362b77f3f85`, token evidence only `prefix=invalid-`, `sha256_12=f89856230bb2`.
  - Actual client-observed close for all invalid cases: `close_code=1000`, `close_reason=""`, not expected `4003`.
  - Server log confirms rejection reasons, e.g. `Invalid protocol_version: ws_ticket_v2, expected ws_ticket_v3` and `Невалидный токен агента: invalid-...`.
- Server DB/state:
  - `devices.last_handshake_at` for the real device stayed at the previous valid handshake timestamp after invalid probes; no device row with hostname `ADMIN-2-PROBE`.
  - `device_events` recent count for this device remained `0`; the only recent `connection_requests` row was the earlier valid provisioning request, not the invalid probes.
- Agent local state:
  - Real local agent remained connected after invalid probes; no local SQLite outbox/pending consent changes observed for this negative protocol-only scenario.
- Browser/admin UI:
  - Browser confirmation not applicable for invalid handshake itself because the negative probe should have no UI representation. Admin inventory was checked around adjacent P0.1/P0.3 and did not show phantom `ADMIN-2-PROBE`.
- Root cause notes:
  - Server appears to execute rejection branch, but close code is not propagated to the client over the observed `wss://192.168.100.17:9443/ws` path.

### P0.3 Same device double connection

Status: partial pass with close-code failure covered by BUG-20260527-02.

Evidence:
- Transport:
  - `scripts/live_ws_v3_probe.py double-connect` used the live agent token from local SQLite via env only; output printed token prefix `d7ad25a1`, hash prefix `54898cb35fe5`, length `64`, never raw token.
  - First raw WS received `handshake_ack`: `request_id=2de05a0e-c45e-473d-99f4-0c4b70cb8244`, `trace_id=7f71296a-50fc-498f-8367-cf3b34389e9c`.
  - Second raw WS received `handshake_ack`: `request_id=7065aa39-1fa7-4ea3-a54a-6702c112da14`, `trace_id=37db5588-b927-4c33-866d-aaa9b8511eaf`.
  - Server log: `Superseding existing agent websocket` twice; superseded disconnects were logged as ignored.
  - Actual client-observed close for superseded first raw connection: `close_code=1000`, not expected `4002`.
- Server DB/state:
  - Server continued to resolve the device from token DB; `device_id=7a3429ec-1c0b-5495-9aad-b284f08ae965`.
  - Handshake rows updated the same device; no duplicate device row was created.
- Agent local state:
  - The live GUI agent was superseded by the first raw probe, then reconnected cleanly after the probes ended.
  - `/ui/agent/status` after recovery: `connection_state=connected`, `connection_detail=WS подключён`, `has_auth_token=true`, `ui_bridge_running=true`.
- Browser/admin UI:
  - Browser URL: `https://192.168.100.17:9443/app/admin/inventory?device=7a3429ec-1c0b-5495-9aad-b284f08ae965`.
  - Visible admin inventory after probe/reconnect: `ADMIN-2`, `Онлайн`, Windows, version `3.1.61`, activity `27 мая 2026 г., 00:33`, state `Готово к действиям`.
- Agent GUI/UIA:
  - Existing GUI session survived the forced reconnect; automation status remained `connection_state=connected`, main requester workspace visible.
- Root cause notes:
  - Supersede state handling on server looks correct from logs for superseded disconnects; close-code propagation to client is the failing part.

### BUG-20260527-02 — Protocol V3 close codes are not observed by raw WS clients

Severity: P1
Status: open
Area: protocol

Scenario:
P0.2 invalid Protocol V3 handshake and P0.3 same-device double connection through `wss://192.168.100.17:9443/ws`.

Expected:
Invalid handshakes close with code `4003`. Superseded same-device websocket closes with code `4002`.

Actual:
The raw aiohttp WS client observed `close_code=1000`, empty close reason, for invalid protocol/capability/token cases and for the superseded double-connection socket.

Repro steps:
1. Run `python scripts/live_ws_v3_probe.py invalid-handshake --case wrong_protocol`.
2. Run `python scripts/live_ws_v3_probe.py invalid-handshake --case invalid_token`.
3. Set `PC_CLIENT_AGENT_TOKEN` from the live agent token source without printing it and run `python scripts/live_ws_v3_probe.py double-connect`.

Evidence:
- Server log: invalid handshake branches log `Invalid protocol_version...` and `Невалидный токен агента...`.
- Agent log: live agent reconnects after supersede and receives `handshake_ack`.
- Browser/UI: admin inventory returns to `ADMIN-2` online after reconnect.
- Server DB: no phantom `ADMIN-2-PROBE` device row; valid device remains same.
- Agent SQLite: no outbox/pending consent side effects from negative probes.
- WS/API payload: probe outputs show invalid close `1000` where expected `4003`; double-connect superseded close `1000` where expected `4002`.

Impact:
Protocol clients cannot rely on documented close codes for auth/contract handling. This weakens live diagnostics and may hide reconnect/supersede contract regressions behind normal-close semantics.

Root cause hypothesis:
Server calls `ws.close(code=4003/4002, ...)`, but the observed HTTPS/WSS path or aiohttp close handling reports normal close `1000`. Needs isolation between server aiohttp behavior and TLS/reverse-proxy behavior.

Fix policy:
- Blocking further tests: no
- Fixed now: no

Fix summary, if fixed:
N/A.

Verification after fix:
Pending future targeted WS close-code regression using raw client and, if needed, direct backend port bypassing TLS proxy.

Regression check:
P0.2/P0.3 should be rerun after any protocol/proxy close-code fix.

Remaining risk:
P0.10 malformed outbox NACK cases may also lose transport-level close-code evidence if they rely on websocket close semantics.

### P0.4 Agent account-session boundary for ticket create

Status: partial pass; HTTP/API account boundary behaved correctly, GUI create path blocked by recorded UI/automation bugs.

Evidence:
- HTTP/API create path:
  - Live agent token was read from the local agent SQLite store for the request and was not printed.
  - Active local account session: `account_session_id=16a1e306-610b-436c-b5f9-65f6222386d1`, `account_mode=confirmed_binding`, `verification_status=verified`, `person_id=bb00a942-fe2c-461c-b982-9da17d3fd1ff`, `binding_id=0618eb74-9fa6-4dbe-9634-d9b56825f3ad`.
  - No-account request to `/api/tickets/create` returned HTTP `403`, `error=account_session_invalid`, `error_code=ACCOUNT_SESSION_REQUIRED`; no ticket_id returned.
  - Valid confirmed account-session request to `/api/tickets/create` returned HTTP `200`, `status=ok`, `ticket_id=44b04e94-4048-4593-b2bc-4054c7cfa7b1`, `requester_account_session_id=16a1e306-610b-436c-b5f9-65f6222386d1`, `requester_account_mode=confirmed_binding`.
  - Request trace marker in the created ticket description: `live-v3-p0-4-api-42315289`.
- GUI/UIA create path:
  - UIA backend confirmed with `pywinauto==0.6.9`; local agent window title readable as `Maria Agent v3.1.61`.
  - UIA create wizard was opened from the local agent GUI and moved through the first steps.
  - `set_edit_text()` through UIA corrupted Cyrillic values in Qt fields/preview into `?` characters while ASCII text stayed intact.
  - Required combo boxes on the confirmation step exposed no selectable values through UIA and could not be selected with `.select()` or keyboard `Alt+Down/Enter`; submit stayed blocked by visible validation messages `Заполните поле «Кого затронула проблема?».` and `Заполните поле «Можно ли продолжать работу?».`.
  - GUI preview panel also showed `Предпросмотр сервера временно недоступен. Можно продолжить...` during the failed GUI submit attempt.
  - Later focused UIA reads could still connect to the window title, but child-control searches hung on the create view; only the helper Python/PowerShell processes were killed, not the agent.
  - Screenshot/evidence paths from earlier UIA checks: `artifacts/live-v3-p0-1-agent-uia-after-login.png`, `artifacts/live-v3-p0-1-agent-main-uia.png`; P0.4 window screenshot attempt via `PIL.ImageGrab` failed with `OSError: screen grab failed`.
- Local GUI automation endpoint:
  - `python scripts/agent_test_driver.py create-ticket live-v3-deep ...` returned HTTP `500` from `/ui/automation/run`; embedded server error was HTTP `403`, `error=account_session_invalid`, `error_code=ACCOUNT_SESSION_REQUIRED`.
  - `action_trace.jsonl` request evidence shows `ticket_api ticket.create` payload did not include `requester_account` even though `account_session.json` contains the verified confirmed-binding session.
- Server DB/state:
  - Ticket `44b04e94-4048-4593-b2bc-4054c7cfa7b1`, code `T-000603`, stored as `status=queued`, `device_id=7a3429ec-1c0b-5495-9aad-b284f08ae965`, `requester_id=7a3429ec-1c0b-5495-9aad-b284f08ae965`, `requester_person_id=bb00a942-fe2c-461c-b982-9da17d3fd1ff`, `requester_binding_id=0618eb74-9fa6-4dbe-9634-d9b56825f3ad`, `requester_registration_status=admin_confirmed`, `requester_account_session_id=16a1e306-610b-436c-b5f9-65f6222386d1`, `requester_account_mode=confirmed_binding`, `next_action_owner=support`, `requester_status=accepted`.
  - Ticket events for `T-000603`: `routing_applied`, `queue_changed`, `sla_started`, `status_changed`, initial user `chat_message` with trace marker, and public access-code `chat_message`.
  - `operations` and operation-linked `device_outbox` rows for this ticket are `0`, as expected for plain create.
  - `device_account_sessions` row for session `16a1e306-610b-436c-b5f9-65f6222386d1` remains `verified`, `revoked_at=NULL`.
- Browser/admin UI:
  - Browser URL: `https://192.168.100.17:9443/app/tickets/44b04e94-4048-4593-b2bc-4054c7cfa7b1`.
  - Visible support workspace: `T-000603 Live V3 P0.4 API account-boundary check`, requester `admin-2`, status `В очереди`, queue `ServiceDesk L1`, assignee `Не назначен`, SLA about `1 ч 59 мин`.
  - Visible timeline included the initial user message `Live V3 P0.4 API create account-session boundary trace live-v3-p0-4-api-42315289`.
  - Browser screenshot: `live-v3-p0-4-ticket-detail.png`.
- Agent local state:
  - `/ui/automation/status` after the HTTP/API create showed `ticket_count=2` and included `ticket_ids=["44b04e94-4048-4593-b2bc-4054c7cfa7b1","1f83c6be-cf21-434a-89bb-fc3bebaed3ed"]`, `connection_state=connected`, `has_active_profile=true`.
  - Local SQLite remained clean for this HTTP create path: `outbox=0`, `outbox_sent_history=0`, `seen_commands=0`, `pending_consents=0`.
- Root cause notes:
  - Server account-session enforcement for agent-created tickets is working for the direct HTTP path.
  - GUI wizard and local automation endpoint are not currently sufficient to complete the required GUI create flow without a product fix or a lower-level UI hook.
  - The automation endpoint root cause is visible in code: `pc_agent/ui_gui/automation_controller.py` calls `ticket_client.create_ticket(...)` without passing `requester_account`, while `pc_agent/ui_gui/chat_panel.py` regular GUI submit passes `requester_account=account_session`.

### BUG-20260527-03 — UIA create wizard cannot complete required fields reliably

Severity: P1
Status: open
Area: UI

Scenario:
P0.4 local agent GUI create flow driven by `pywinauto==0.6.9` with `backend="uia"`.

Expected:
Stable UIA selectors allow the test to fill requester-visible Russian text and select all required request-template fields without coordinate-only interaction; submit creates a ticket or returns a server-side validation result.

Actual:
UIA text injection corrupted Cyrillic field values to `?`, required combo boxes exposed no selectable items through UIA and could not be set with `.select()` or keyboard fallback, submit stayed blocked by required-field validation, and later child-control discovery on the create view hung.

Repro steps:
1. Connect to PID `27208` with `Application(backend="uia")`.
2. Open `Создать обращение`, choose `Сломался ноутбук`, proceed to the form.
3. Fill Russian values with `set_edit_text()`.
4. Attempt to select required combo boxes `Кого затронула проблема?` and `Можно ли продолжать работу?`.
5. Click `Создать обращение`.

Evidence:
- Server log: no ticket was created by the GUI/UIA wizard attempt.
- Agent log: GUI remained connected; no reconnect loop.
- Browser/UI: direct API-created ticket exists, but GUI-created ticket does not.
- Server DB: no additional GUI-created ticket with the corrupted UIA Russian payload.
- Agent SQLite: outbox/history/seen_commands/pending_consents unchanged.
- WS/API payload: not applicable; submit was blocked client-side before a successful create request.

Impact:
Blocks the mandatory GUI-driven ticket create validation in P0.4 and reduces repeatability of live GUI tests for Russian request-template forms.

Root cause hypothesis:
Qt accessibility/value patterns for these widgets are not exposing stable selectable ComboBox items to Microsoft UI Automation, and pywinauto `set_edit_text()` is not preserving Unicode for the Qt edit controls in this runtime.

Fix policy:
- Blocking further tests: no, because direct HTTP/API and browser checks can continue; yes for the GUI-create subcase.
- Fixed now: no

Fix summary, if fixed:
N/A.

Verification after fix:
Pending future UIA regression that creates a Russian GUI ticket through the wizard and confirms it in browser/DB.

Regression check:
After a fix, repeat P0.1 UIA connected-state checks and P0.4 GUI create with required combo boxes.

Remaining risk:
Other GUI flows with Qt combo boxes or Russian text may be similarly hard to automate until control AutomationIds/value patterns are improved.

### BUG-20260527-04 — Local GUI automation ticket.create omits active account session

Severity: P1
Status: verified-fixed
Area: account-session

Scenario:
P0.4 `scripts/agent_test_driver.py create-ticket live-v3-deep ...` through `/ui/automation/run` while the local GUI has a verified confirmed-binding account session.

Expected:
The local automation ticket.create path should behave like the real GUI submit path and include the active `requester_account.session_id`/token, allowing a confirmed account session to create a ticket.

Actual:
The automation endpoint called `/api/tickets/create` without `requester_account` and the server correctly rejected it with `ACCOUNT_SESSION_REQUIRED`.

Repro steps:
1. Confirm `account_session.json` contains `account_session_id=16a1e306-610b-436c-b5f9-65f6222386d1`, `account_mode=confirmed_binding`, `verification_status=verified`.
2. Run `python scripts/agent_test_driver.py create-ticket live-v3-deep --title ... --description ...`.
3. Observe HTTP `500` from the local automation endpoint with embedded server HTTP `403`.

Evidence:
- Server log/API: `/api/tickets/create` rejection `ACCOUNT_SESSION_REQUIRED`.
- Agent log: action trace records automation `ticket.create` failure.
- Browser/UI: no ticket created by the automation endpoint.
- Server DB: no ticket row for the automation request.
- Agent SQLite: no outbox/history side effects.
- WS/API payload: `action_trace.jsonl` `ticket_api ticket.create` request payload lacks `requester_account`.
- Fix evidence, 2026-05-27 11:56-12:05 +05:
  - Changed files: `pc_agent/ui_gui/automation_controller.py`, `pc_agent/tests/test_gui_automation_controller.py`.
  - Targeted tests: `python -m py_compile pc_agent\ui_gui\automation_controller.py pc_agent\tests\test_gui_automation_controller.py` exit 0; `python -m pytest pc_agent\tests\test_gui_automation_controller.py pc_agent\tests\test_registration_status.py::test_create_ticket_sends_only_requester_account_session_when_passed -q` -> `3 passed in 0.76s`.
  - Live GUI precondition: source-mode local agent restarted with `python scripts\manage_local_agent.py start live-v3-deep --gui --ws-url wss://192.168.100.17:9443/ws --api-url https://192.168.100.17:9443/api`; `/ui/automation/status` showed `connection_state=connected`, then pywinauto `0.6.9` UIA invoked account-gate PrimaryButton `Войти как admin-2`, moving `sidebar_view` to `tickets`.
  - Live command: `python scripts\agent_test_driver.py create-ticket live-v3-deep --title "Live V3 Fix6 automation account session bd33bce2" --description "Live regression for BUG-20260527-04: automation create should include active confirmed account session."`.
  - Local automation response: HTTP success, `ticket_id=3df55d98-0f34-472f-b19b-72b990388025`, `ticket_code=T-000605`, `requester_account_session_id=6196fe8b-d836-44c5-9760-88a2f5d31f7a`, `requester_account_mode=confirmed_binding`, `requester_registration_status=admin_confirmed`.
  - Server DB: `tickets.T-000605` persisted with `requester_person_id=bb00a942-fe2c-461c-b982-9da17d3fd1ff`, `requester_binding_id=0618eb74-9fa6-4dbe-9634-d9b56825f3ad`, `requester_account_session_id=6196fe8b-d836-44c5-9760-88a2f5d31f7a`, `requester_account_mode=confirmed_binding`; initial `chat_message` event payload contains the same requester account/session fields.
  - Agent SQLite: no recent failed outbox rows after the automation create.
  - Browser/UI: real browser URL `https://192.168.100.17:9443/app/tickets/3df55d98-0f34-472f-b19b-72b990388025`; DOM shows `T-000605`, title, requester `Тестовый тест 12`, status `В очереди`, initial user message. Screenshot: `live-v3-fix6-ticket.png`.

Impact:
Blocks using the local automation bridge as a reliable substitute for manual GUI submission in account-boundary tests.

Root cause:
`pc_agent/ui_gui/automation_controller.py::_create_ticket()` passed requester profile/display name but omitted `chat_panel._current_account_session()` when calling `TicketApiClient.create_ticket()`. The real GUI path in `pc_agent/ui_gui/chat_panel.py::_async_create_ticket()` already passed `requester_account=account_session`.

Fix policy:
- Blocking further tests: no, because direct HTTP/API and browser verification can continue; yes for bridge-driven create.
- Fixed now: yes

Fix summary, if fixed:
Automation ticket creation now reads `chat_panel._current_account_session()` and passes it as `requester_account` to `TicketApiClient.create_ticket()`. No-account automation still does not synthesize credentials; it propagates the server denial.

Verification after fix:
Verified by unit tests and live `agent_test_driver.py create-ticket`: `T-000605` was created through `/ui/automation/run`, DB requester account fields match the active confirmed binding session, initial ticket event carries requester account context, browser ticket detail shows the new ticket, and local outbox has no new failed rows.

Regression check:
Unit regression covers no-account server denial and valid confirmed-session create success. Live regression covered confirmed-session create success through the local automation bridge and browser detail confirmation.

Remaining risk:
Other automation actions may also omit account-session headers/payloads where the real GUI path already includes them.

### P0.5 WS chat_raise account-boundary check

Status: failed; BUG-20260527-05 recorded.

Evidence:
- Transport:
  - Trigger path: `POST http://127.0.0.1:8765/ui/request_support` on local bridge, which calls `ws_agent.chat_raise()` and sends WS `type=command`, `payload.command=chat_raise` to the server.
  - Local bridge response: HTTP `200`, body `status=ok`, `result.ok=true`, `job_id=60a0933e-b170-4170-b8ac-bcb733336291`, `ticket_id=cc002181-f7d9-44da-8726-da46463c090f`.
  - Agent log: `[chat_raise] command sent request_id=9000ae24-eacf-48e2-ad29-6fd16fcf852c`; `[chat_raise] success job_id=60a0933e-b170-4170-b8ac-bcb733336291 ticket_id=cc002181-f7d9-44da-8726-da46463c090f`.
  - Server->agent follow-up commands were created/delivered for `start_job` and `ui_notify`; `device_outbox` rows `3fb11f58-f2ec-48d3-9e8b-0fc51418e073` and `32b02f8a-8338-428d-8da2-bed252ffb61d` both reached `delivered`.
  - Agent then sent outbox batch items for the returned ticket id; server returned per-item non-retryable `outbox_nack` with code `UNKNOWN_TICKET`.
- Server DB/state:
  - `select * from tickets where ticket_id='cc002181-f7d9-44da-8726-da46463c090f'` returned zero rows.
  - `ticket_events` for that ticket returned zero rows.
  - Recent `tickets` only contained the earlier P0.4 valid API ticket `T-000603`; no P0.5 chat_raise ticket was persisted.
  - `operations` for returned ticket id returned `0`.
  - `device_outbox` contained only the follow-up `start_job` and `ui_notify` command rows, both delivered and not ticket-bound.
- Agent local state:
  - Agent job manager logged `Created ticket from server: cc002181-f7d9-44da-8726-da46463c090f` and opened support chat for `job_id=60a0933e-b170-4170-b8ac-bcb733336291`.
  - Local SQLite `outbox` contains failed rows `outbox_id=1..7` for ticket `cc002181-f7d9-44da-8726-da46463c090f`; all have `status=failed`, `attempts=1`, `last_error=NACK: UNKNOWN_TICKET - Ticket cc002181-f7d9-44da-8726-da46463c090f not found`.
  - Failed item kinds include `job_started`, `tool_response`, `job_running`, `chat_session`, and `chat_message`.
- Browser/admin UI:
  - Browser URL: `https://192.168.100.17:9443/app/tickets/cc002181-f7d9-44da-8726-da46463c090f`.
  - Visible result: `Тикет не найден`; queue still only shows `T-000603 Live V3 P0.4 API account-boundary check`.
  - Browser console/network showed failed loads for `/api/web/support/tickets/cc002181-f7d9-44da-8726-da46463c090f/workspace` and `/timeline?filter=all`.
  - Screenshot: `live-v3-p0-5-chat-raise-not-found.png`.
- Agent GUI/UIA:
  - Agent GUI auto-opened chat for the returned job id according to agent log: `Chat автоматически открыт для job_id=60a0933e-b170-4170-b8ac-bcb733336291`.
  - Current deeper UIA child traversal is unstable on this GUI state (see BUG-20260527-03), so GUI evidence for P0.5 is from local bridge response and agent logs rather than a fresh UIA control-tree excerpt.
- Root cause notes:
  - Documentation says WS `chat_raise` and legacy `/api/chat_raise` use DB-first create flow, but the live WS path returned success for a ticket that is absent from DB.
  - This is not merely an account-boundary bypass; it is a stronger consistency bug: the agent receives a canonical-looking ticket id and starts local work against a nonexistent server ticket.

### BUG-20260527-05 — WS chat_raise returns success for a non-persisted ticket

Severity: P1
Status: verified-fixed
Area: protocol / tickets / DB

Scenario:
P0.5 agent-side chat_raise through local bridge `/ui/request_support` and Protocol V3 WS `command=chat_raise`.

Expected:
If account-session boundary is required, unauthenticated account state should not create a requester ticket and should return an explicit denial. If legacy chat_raise is allowed, the returned `ticket_id` must exist in `tickets`, have initial `ticket_events`, and be visible in the support UI.

Actual:
Local bridge and agent WS path returned success with `ticket_id=cc002181-f7d9-44da-8726-da46463c090f`, but the server DB has no ticket row or ticket_events for that id. The browser shows `Тикет не найден`. Agent outbox events for that id were NACKed as `UNKNOWN_TICKET` and marked failed locally.

Repro steps:
1. Run `POST http://127.0.0.1:8765/ui/request_support` with title `Live V3 P0.5 WS chat_raise boundary check`.
2. Observe local bridge HTTP `200` and returned job/ticket ids.
3. Query `tickets` and `ticket_events` for the returned ticket id.
4. Open `/app/tickets/{returned_ticket_id}` in browser.
5. Query local SQLite `outbox`.

Evidence:
- Server log: device_outbox delivered `start_job` and `ui_notify`; server emitted `outbox_nack` `UNKNOWN_TICKET` for subsequent agent events targeting the returned ticket id.
- Agent log: `[chat_raise] success ... ticket_id=cc002181-f7d9-44da-8726-da46463c090f`; support chat started; subsequent outbox rows NACKed `UNKNOWN_TICKET`.
- Browser/UI: `/app/tickets/cc002181-f7d9-44da-8726-da46463c090f` shows `Тикет не найден`; screenshot `live-v3-p0-5-chat-raise-not-found.png`.
- Server DB: zero rows in `tickets` and `ticket_events` for returned ticket id.
- Agent SQLite: failed outbox rows `1..7`, non-retryable `UNKNOWN_TICKET`.
- WS/API payload: local bridge response contains `job_id=60a0933e-b170-4170-b8ac-bcb733336291`, `ticket_id=cc002181-f7d9-44da-8726-da46463c090f`, `ok=true`.

Impact:
Data-loss/state-divergence risk. The agent and GUI believe a support chat/ticket exists, while the server and browser have no persisted ticket. Follow-up events are permanently failed, and operators cannot see or act on the returned ticket.

Root cause hypothesis:
`server/websocket/agent_services.py::AgentCommandService.handle()` catches exceptions around `create_ticket_with_side_effects()` and continues returning success using the pre-generated random `ticket_id`; it then enqueues `start_job`/`ui_notify` for a ticket that was never committed. The DB create likely fails in live policy/account-session/routing context, but the exception is swallowed.

Root cause confirmed:
The WS `chat_raise` path generated a `chat_job_id`/`ticket_id`, created the chat session before durable ticket creation, swallowed DB create failure, then unconditionally returned `command_result.status=success` and scheduled `start_job`/`ui_notify`. The legacy HTTP chat raise path had the same ordering risk by creating the chat session before the DB create returned a canonical ticket id.

Fix policy:
- Blocking further tests: no for HTTP/API ticket lifecycle; yes for WS chat_raise validation.
- Fixed now: yes

Fix summary, if fixed:
- Changed files:
  - `server/websocket/agent_services.py`
  - `server/chat/handlers.py`
  - `server/tests/test_agent_services_pipeline.py`
  - `pc_agent/ws_agent.py`
  - `pc_agent/tests/test_ws_agent_chat_raise.py`
- Server `chat_raise` is now DB-first: if ticket creation is unavailable, fails, or returns no persisted ticket id, the command returns `status=error` and does not create a chat session or enqueue `start_job`/`ui_notify`.
- Legacy `/api/chat_raise` now creates its chat session only after a durable ticket id is returned.
- Local agent bridge now propagates server-side `command_result.status=error` details as `ok=false` with a stable `error_code`, instead of flattening them into generic bridge failure.
- Commits:
  - Server fix: `862a266ce2d6f3411320bbb93c55b8b41500e22d`, pushed and deployed to the live Linux server with quick gate.
  - Local bridge fix: `3539290c`, pushed; verified by running `live-v3-deep` in source GUI mode.

Verification after fix:
- Targeted tests:
  - `python -m pytest server\tests\test_agent_services_pipeline.py -q` -> `24 passed`.
  - `python -m pytest pc_agent\tests\test_ws_agent_chat_raise.py -q` -> `2 passed`.
  - `python -m py_compile server\websocket\agent_services.py server\chat\handlers.py pc_agent\ws_agent.py scripts\live_ws_v3_probe.py` -> passed.
- Live regression:
  - Server deployed at `862a266ce2d6f3411320bbb93c55b8b41500e22d`; local agent `live-v3-deep` restarted in source GUI mode from commit `3539290c`.
  - Command: `python scripts\agent_test_driver.py request-support live-v3-deep --title 'Live V3 Fix2 chat_raise db-first retry 3539290c' --reason fix2_live_regression --severity warning`.
  - Local bridge result: `ok=false`, `error_code=TICKET_CREATE_UNAVAILABLE`, `error=Ticket creation is unavailable for chat_raise`.
  - Server DB: zero `tickets` and zero `ticket_events` for the Fix2 live regression titles/reason; no new phantom ticket id was returned.
  - Agent SQLite: no new `UNKNOWN_TICKET` outbox rows after the Fix2 regression; only the older P0.5 phantom-ticket evidence remains.
  - Browser: real ticket list/timeline did not show the Fix2 title; screenshot `artifacts/live-v3-fix2-no-ticket-browser.png`.

Regression check:
P0.5 regression now returns explicit denial instead of success with a phantom id. Adjacent P0.7 must still be rerun in the final verification gate after Fix 1-6 because Fix2 only changed `chat_raise`/bridge behavior, not normal `run_tool` command_result flow.

Remaining risk:
The live server currently returns `TICKET_CREATE_UNAVAILABLE` for WS `chat_raise`; if product policy expects chat_raise to create a technical support requester ticket, server runtime config/policy needs a separate decision. This no longer pollutes ticket/outbox state because the denial is explicit and no local chat session is started.

### P0.6 Full ticket lifecycle

Status: passed for the available live policy path; one policy-risk note recorded.

Evidence:
- Status path:
  - Test ticket: `44b04e94-4048-4593-b2bc-4054c7cfa7b1`, code `T-000603`.
  - Initial create flow had already moved `new -> queued` via routing, with `status_changed` event reason `routed_to_queue`.
  - Blocked check: `queued -> assigned` without assignee returned HTTP `400`, `error_code=WORKFLOW_POLICY_BLOCKED`, message `workflow_profile transition gate missing required_fields: assignee_id`.
  - Assigned assignee `op1` through `/api/web/support/tickets/{ticket_id}/assign`; DB/UI still `queued`, `assignee_id=op1`.
  - Status path through browser-authenticated support API:
    - `queued -> assigned`: HTTP `200`, status `assigned`.
    - `assigned -> in_progress`: HTTP `200`, status `in_progress`.
    - `in_progress -> waiting_on_user`: HTTP `200`, status `waiting_on_user`.
    - `waiting_on_user -> in_progress`: HTTP `200`, status `in_progress`.
    - `in_progress -> resolved`: HTTP `200`, status `resolved`.
    - repeated `resolved -> resolved` with resolution fields returned HTTP `400`, `error_code=INVALID_TRANSITION`, as expected because the ticket was already resolved.
    - `resolved -> closed`: HTTP `200`, status `closed`.
- Blocked transitions:
  - `assigned` without assignee was blocked by workflow gate.
  - Invalid repeat transition `resolved -> resolved` was blocked with `INVALID_TRANSITION`.
  - `resolved` without `resolution_code`/summary was allowed by the live policy; not marked as a product bug unless the intended published policy requires those fields.
- Server DB/state:
  - Final ticket row: `status=closed`, `assignee_id=op1`, `queue_id=1`, `requester_status=closed`, `next_action_owner=system`, `resolved_at=2026-05-27 00:53:44+05`, `closed_at=2026-05-27 00:53:44+05`, `resolution_code=NULL`, `resolution_summary=NULL`, `sla_paused_seconds=0`, `resolution_at=2026-05-27 00:53:44+05`.
  - Status events persisted in order:
    - `new -> queued`
    - `queued -> assigned`
    - `assigned -> in_progress`
    - `in_progress -> waiting_on_user`
    - `waiting_on_user -> in_progress`
    - `in_progress -> resolved`
    - `resolved -> closed`
  - `assignee_changed` event persisted for `op1`.
  - SLA/OLA timeline side effects persisted/rendered: `sla_started`, `SLA paused`, `SLA resumed`, `Срок решения остановлен`, `OLA acknowledgement stopped`, `OLA paused`, `OLA resumed`, `OLA processing stopped`.
  - `ticket_public_sessions` had zero rows for this ticket, so explicit public-session revocation was not applicable for this live ticket.
- Browser/admin UI:
  - Browser URL: `https://192.168.100.17:9443/app/tickets/44b04e94-4048-4593-b2bc-4054c7cfa7b1`.
  - Visible final state: `T-000603 Live V3 P0.4 API account-boundary check`, queue `ServiceDesk L1`, assignee `op1`, status `Закрыта`, requester-facing status `Обращение закрыто`.
  - Timeline visibly shows assignment, in-work, waiting-on-user, resume, resolved, confirmation prompt, and closed events.
  - Screenshot: `live-v3-p0-6-ticket-closed.png`.
- Agent/requester UI:
  - Browser support UI is the authoritative UI confirmation for this support lifecycle flow.
  - Local agent ticket list had already seen this ticket before close via `/ui/automation/status`; deeper UIA traversal remains unstable on the current GUI state (BUG-20260527-03), so no fresh UIA lifecycle detail was captured for closed status.
- Root cause notes:
  - The canonical DB constraint prevented non-canonical status storage; no `triaged` status appeared.
  - Current live workflow allows resolution without resolution fields; if the intended helpdesk policy requires evidence/summary/code, the published policy is too permissive rather than the transition engine failing.

### P0.7 run_tool happy lifecycle

Status: passed with adjacent pre-existing failed outbox rows from P0.5 noted separately.

Evidence:
- Browser/API trigger:
  - Ticket created through the confirmed account-session HTTP path for this scenario: `T-000604`, `ticket_id=68de6816-471b-48ba-88e3-fa691264bba3`, trace label `live-v3-p0-7-run-tool-a80d9c22`.
  - Browser support API `/api/web/support/tickets/68de6816-471b-48ba-88e3-fa691264bba3/tools` listed `system.collect` from module `system`, `risk_level=safe_readonly`, `requires_consent=false`, presets `minimal/basic/identity/network/full`.
  - Browser-authenticated support API `POST /api/web/support/tickets/68de6816-471b-48ba-88e3-fa691264bba3/tools/run` with `tool_name=system.collect`, `params={"preset":"basic"}` returned HTTP 202, `operation_id=040d1878-4416-4661-a1b8-3f11a7717013`, `trace_id=8dde0d69-3183-4530-90ce-ed1388ccd690`, `dispatch_status=accepted`.
- Operation/outbox:
  - `operations`: `kind=tool_call`, `tool_name=system.collect`, `actor_role=admin`, `status=succeeded`, `queued_at=2026-05-27 00:55:17.712060+05`, `sent_at=2026-05-27 00:55:17.732407+05`, `accepted_at=2026-05-27 00:55:17.742598+05`, `finished_at=2026-05-27 00:55:18.792099+05`, `result_event_id=46`.
  - `device_outbox`: row id `4`, `command_id=request_id=operation_id=040d1878-4416-4661-a1b8-3f11a7717013`, command `run_tool`, status `delivered`, same trace id `8dde0d69-3183-4530-90ce-ed1388ccd690`, params include `call_id=f76d99bc-7d5c-4f4b-b158-1aadaeaff3d3`.
- Agent execution:
  - Agent accepted and executed the command; result reached the server in under two seconds.
  - `seen_commands` local SQLite row for command `040d1878-4416-4661-a1b8-3f11a7717013` has `status=success` and result JSON with `preset=basic`, `hostname=ADMIN-2`, CPU/RAM/disk observations.
- Server DB/events:
  - Ticket events for `T-000604` include routing and initial message events, then `tool_call_started` event id `45` before terminal result, followed by `tool_call_result` event id `46` and agent-origin `tool_response` event id `47`.
  - `tool_call_started`: `operation_id=040d1878-4416-4661-a1b8-3f11a7717013`, `trace_id=8dde0d69-3183-4530-90ce-ed1388ccd690`, payload includes `tool_name=system.collect`, `params={"preset":"basic"}`, actor role `admin`.
  - `tool_call_result`: same operation and trace, output includes `hostname=ADMIN-2`, `cpu=13.9`, `ram=94.3`, `disk=25.1`.
  - `tool_response`: `agent_seq=1`, `trace_id=558638be-8e11-4295-a84b-e4894fc13eb8`, payload mirrors the `system.collect` observation. No duplicate terminal operation row was found.
- Agent SQLite:
  - `outbox_sent_history`: one P0.7 row, `outbox_id=8`, `ticket_id=68de6816-471b-48ba-88e3-fa691264bba3`, `kind=tool_response`, payload preview contains `system.collect` observations.
  - `pending_consents`: `0` rows after the safe read-only tool run.
  - `outbox`: still contains seven failed rows from the earlier P0.5 phantom-ticket scenario with `NACK: UNKNOWN_TICKET`; these are pre-existing evidence for `BUG-20260527-05`, not a P0.7 regression.
- Browser/admin UI:
  - Real browser URL: `https://192.168.100.17:9443/app/tickets/68de6816-471b-48ba-88e3-fa691264bba3`.
  - DOM/browser output shows `T-000604`, timeline entry `Специалист запустил диагностику.` with operation `system.collect`, status `Принята`, then `Выполнена диагностика`, operation `system.collect`, status `Успешно`, and visible result values for `ADMIN-2`, CPU/RAM/disk.
  - Screenshot: `live-v3-p0-7-run-tool-result.png`; browser snapshot file: `live-v3-p0-7-run-tool-result-snapshot.md`.
- Root cause notes:
  - The happy command lifecycle works end to end for a safe built-in tool when the ticket exists and the operation is support-initiated.
  - The UI timeline currently exposes Python-dict-style result text in places before/alongside JSON. This is a presentation-quality issue to revisit during P1.6 UI projection consistency, not a blocker for P0.7 transport/DB/agent correctness.

### P0.8 Long-running tool + cancel_operation

Status: partial pass; cancellation reaches the agent and terminal server state is correct, but BUG-20260527-06 and BUG-20260527-07 were recorded.

Evidence:
- Diagnostic or existing tool:
  - No new diagnostic module was created for this pass because the live toolset already exposes built-in `screen.record` with `duration_sec`, `side_effects=false`, `requires_consent=false`, `artifact_kinds=["screen_recording"]`, and a real long-running agent-side loop with cancel stop-event support.
  - Tool used: `screen.record`, params `{"duration_sec":30,"fps":5,"max_width":640,"quality_crf":35}`. Earlier exploratory run with `fps=2` failed immediately with `INVALID_PARAMS` because the contract requires `fps >= 5`; that was tester error, not a product bug.
- Operation/cancel transport:
  - Browser-authenticated support API started the valid long-running operation on `T-000604`: HTTP 202, `operation_id=b24a6bf5-cad2-4085-94a2-2049f3798cbd`, `trace_id=8dde0d69-3183-4530-90ce-ed1388ccd690`, `dispatch_status=accepted`.
  - Browser/web-session `POST /api/operations/b24a6bf5-cad2-4085-94a2-2049f3798cbd/cancel` returned HTTP 401 `AUTH_REQUIRED` despite the support UI session being valid enough to start the tool. See `BUG-20260527-06`.
  - Agent-token authenticated cancel request to the same endpoint returned HTTP 200 with `cancel_operation_id=6e11ef62-c10e-47ce-be80-94ee24a614d0`.
  - Agent log shows V3 `command_ack` for `run_tool` request `b24a6bf5-cad2-4085-94a2-2049f3798cbd`, later V3 `command_ack` and `command_result` for cancel request `6e11ef62-c10e-47ce-be80-94ee24a614d0`.
- Agent runtime:
  - Agent log: `execution lane acquired tool=screen.record operation_id=b24a6bf5-cad2-4085-94a2-2049f3798cbd`.
  - Agent log after cancel: received `cancel_operation`, then `[AGENT] run_tool canceled tool=screen.record operation_id=b24a6bf5-cad2-4085-94a2-2049f3798cbd`, then sent cancel `command_result` with status `success`.
  - Local SQLite `outbox_sent_history` contains outbox ids `10` and `11` for the canceled tool result and cancel tool_response; `pending_consents=0`.
- Server DB/state:
  - Target operation `b24a6bf5-cad2-4085-94a2-2049f3798cbd`: `kind=tool_call`, `tool_name=screen.record`, actor role `admin`, final status `canceled`, `cancel_reason=live-v3-p0-8-agent-token-cancel`, `cancel_requested_at=2026-05-27 01:01:39.492746+05`, `canceled_at=2026-05-27 01:01:39.613391+05`.
  - Cancel operation `6e11ef62-c10e-47ce-be80-94ee24a614d0`: `kind=cancel_operation`, actor role `agent`, final status `succeeded`, `cancel_target_operation_id=b24a6bf5-cad2-4085-94a2-2049f3798cbd`, sent/accepted/finished around `2026-05-27 01:01:39+05`.
  - Ticket events include `tool_call_started` id `52`, `op_cancel_requested` id `53`, `op_canceled` id `54`, agent-origin `tool_call_result` id `55` with status `canceled`, and cancel `tool_response` id `56`.
- Browser/admin UI:
  - Real browser URL: `https://192.168.100.17:9443/app/tickets/68de6816-471b-48ba-88e3-fa691264bba3`.
  - DOM/browser output shows a top diagnostic entry with status `Отменена` and cancel text, plus the earlier invalid-params exploratory `screen.record` entry as `error`.
  - Screenshot: `live-v3-p0-8-cancel-result.png`.
- Cleanup/no-stuck-state:
  - Server target operation is terminal `canceled`; cancel operation is terminal `succeeded`; local agent outbox rows for this cancel flow are ACKed into `outbox_sent_history`.
  - Stuck-state failure: server `device_outbox` target `run_tool` command id `b24a6bf5-cad2-4085-94a2-2049f3798cbd` remains `status=sent`, `delivered_at=NULL`, even though the agent received it and the target operation is terminal canceled.
  - Stuck-state failure: local `seen_commands` row for target command `b24a6bf5-cad2-4085-94a2-2049f3798cbd` remains `status=in_progress` with no `result_json`; cancel command `6e11ef62-c10e-47ce-be80-94ee24a614d0` is `status=success`.
- Root cause notes:
  - Cancel command priority/dispatch and agent stop-event handling are functioning.
  - Browser-visible cancel controls are not safely usable through the documented web-session path because the legacy operations route does not receive/accept the web auth context.
  - Agent/server cleanup after canceled long-running run_tool is incomplete: the target command is not marked delivered/terminal in both server outbox and local command idempotency cache.

### BUG-20260527-06 — Web-session operation cancel endpoint returns AUTH_REQUIRED

Severity: P1
Status: open
Area: UI / protocol / account-session

Scenario:
P0.8 long-running `screen.record` cancellation from the support/browser UI session.

Expected:
The support web session that can start `/api/web/support/tickets/{ticket_id}/tools/run` should also be able to call the cancel URL exposed by the support operation card, or the support API should expose a web-session cancel alias.

Actual:
`POST /api/operations/b24a6bf5-cad2-4085-94a2-2049f3798cbd/cancel` from the real browser returned HTTP 401 with `AUTH_REQUIRED`.

Repro steps:
1. Open `https://192.168.100.17:9443/app/tickets/68de6816-471b-48ba-88e3-fa691264bba3` with a valid support/admin web session.
2. Start `screen.record` through `POST /api/web/support/tickets/{ticket_id}/tools/run`.
3. Call the returned/exposed cancel URL `/api/operations/{operation_id}/cancel` with browser credentials.

Evidence:
- Server log:
- Agent log:
- Browser/UI: browser fetch returned HTTP `401`, body `{"status":"error","error":"Требуется аутентификация","error_code":"AUTH_REQUIRED"}` while the same session successfully started the tool.
- Server DB: no cancel-op row was created by the browser 401 attempt; cancel-op row appeared only after agent-token request.
- Agent SQLite:
- WS/API payload: successful fallback cancel used agent-token auth and returned `cancel_operation_id=6e11ef62-c10e-47ce-be80-94ee24a614d0`.

Impact:
Support UI cancel controls can appear actionable but fail for web-session users, blocking realistic browser-driven cancellation testing and likely user cancellation workflows.

Root cause hypothesis:
Confirmed root cause:
The legacy `/api/operations/{operation_id}/cancel` route remains token-auth scoped, while web-session cookies are extracted only for `/api/web/*` routes. Support operation snapshots and the React cancel mutation both pointed browser users at the token-only URL, so a valid support web session received `AUTH_REQUIRED`.

Fix policy:
- Blocking further tests: yes for realistic browser-driven P0.8/P1 cancel validation.
- Fixed now: yes

Fix summary, if fixed:
- Changed files:
  - `server/api/operations.py`
  - `server/routes.py`
  - `server/web_api/support_handlers.py`
  - `server/tests/test_web_support_api.py`
  - `webapp/src/features/queues/api.ts`
  - `webapp/src/features/queues/support-workspace-mappers.test.ts`
  - `webapp/src/pages/tickets/list-page.test.tsx`
  - `docs/QUICK_LOOKUP.md`
  - `server/docs/CODEMAP.md`
- Added typed route `POST /api/web/support/operations/{operation_id}/cancel` for support/admin web-session auth.
- Support operation snapshots now advertise `/api/web/support/operations/{operation_id}/cancel`.
- React support workspace cancel mutation now calls the web-session route.
- Legacy `/api/operations/{operation_id}/cancel` remains available for token clients.
- Commit/deploy: `91f7529aa2e864298ae025ac4e20123688d1e368` (`fix: add web support operation cancel route`) pushed to `origin`, deployed to Linux, webapp bundle rebuilt and uploaded, server restarted to PID `3884978`, remote smoke passed on attempt 2.

Verification after fix:
- Targeted pytest:
  - `python -m py_compile server\api\operations.py server\routes.py server\web_api\support_handlers.py` -> passed.
  - `python -m pytest server\tests\test_web_support_api.py::test_web_support_operation_cancel_uses_web_session_boundary -q` -> `1 passed in 343.15s`.
  - `python -m pytest server\tests\test_web_support_api.py::test_web_support_operation_cancel_denies_auditor -q` -> `1 passed in 340.86s`.
  - `pnpm --dir webapp test src\features\queues\support-workspace-mappers.test.ts src\pages\tickets\list-page.test.tsx` -> `2 passed`, `56 passed`.
- Release verification:
  - `python scripts\release_server_to_remote.py --gate quick --allow-local-dirty --leave-running` ran `verify_workspace.py`, built the webapp, deployed committed state, ran migrations, uploaded webapp bundle, restarted control/server, and passed remote smoke.
- Live browser regression:
  - Real browser URL: `https://192.168.100.17:9443/app/tickets/68de6816-471b-48ba-88e3-fa691264bba3`.
  - Browser web-session started `screen.record` through `POST /api/web/support/tickets/{ticket_id}/tools/run`, HTTP `202`, target operation `5a84f059-7f0c-448d-9adb-854175d03a2c`.
  - Same browser session canceled through `POST /api/web/support/operations/5a84f059-7f0c-448d-9adb-854175d03a2c/cancel`, HTTP `200`, cancel operation `a69adba7-3bfd-417b-b9a0-45a3535fee17`.
  - Browser support detail API returned target `status=canceled`, cancel `status=succeeded`; operation card had `can_cancel=false` after terminal state.
  - Browser timeline shows `screen.record` at `27 мая, 11:18` with status `Отменена` and summary `Tool screen.record canceled`.
  - Screenshot: browser MCP `live-v3-fix4-web-session-cancel-browser.png`.
- Server DB:
  - Target operation `5a84f059-7f0c-448d-9adb-854175d03a2c`: `kind=tool_call`, `status=canceled`, `cancel_reason=live-v3-fix4-web-session-cancel`.
  - Cancel operation `a69adba7-3bfd-417b-b9a0-45a3535fee17`: `kind=cancel_operation`, `status=succeeded`, `cancel_target_operation_id=5a84f059-7f0c-448d-9adb-854175d03a2c`.
  - `device_outbox`: both target `run_tool` and cancel command are `status=delivered`, with `sent_at` and `delivered_at`.
  - `ticket_events`: `tool_call_started`, `op_cancel_requested`, `tool_call_result status=canceled`, `op_canceled cancel_status=canceled`.

Regression check:
- Support/admin web route creates cancel-op; auditor route test returns `403`.
- Existing token-only legacy cancel route remains unchanged for non-web clients.
- Retry/approve/deny still use legacy operation routes and remain a separate auth-surface review item if web-session action buttons are later exposed for those controls.

Remaining risk:
The web-session route is intentionally limited to support/admin. Future UI work should avoid exposing legacy `/api/operations/*` mutations to browser sessions unless a typed `/api/web/*` alias exists.

### BUG-20260527-07 — Canceled run_tool leaves stale sent/in_progress command state

Severity: P1
Status: verified-fixed
Area: DB / reconnect / protocol

Scenario:
P0.8 cancellation of long-running `screen.record` after the agent accepted and started the run_tool.

Expected:
After cancellation, the target operation is terminal canceled and no target command state remains stuck: server `device_outbox` should be terminal/delivered or otherwise reconciled, and local `seen_commands` for the target run_tool should not remain `in_progress`.

Actual:
The target operation is correctly `canceled`, but server `device_outbox` row id `6` for command `b24a6bf5-cad2-4085-94a2-2049f3798cbd` remains `status=sent`, `delivered_at=NULL`; local `seen_commands` for the same command remains `status=in_progress` with no result JSON.

Repro steps:
1. Start `screen.record` for 30 seconds on an existing ticket.
2. Wait until agent log shows execution lane acquired.
3. Send `cancel_operation`.
4. Query `operations`, `device_outbox`, and local SQLite `seen_commands`.

Evidence:
- Server log:
- Agent log: `[AGENT] run_tool canceled tool=screen.record operation_id=b24a6bf5-cad2-4085-94a2-2049f3798cbd`; cancel `command_result` sent for `6e11ef62-c10e-47ce-be80-94ee24a614d0`.
- Browser/UI: ticket timeline shows a canceled diagnostic entry.
- Server DB: target operation `canceled`, cancel operation `succeeded`; `device_outbox` target run_tool still `sent`.
- Agent SQLite: `outbox_sent_history` ids `10` and `11` ACKed; `seen_commands.command_id=b24a6bf5-cad2-4085-94a2-2049f3798cbd` remains `in_progress`.
- WS/API payload: ticket events include `op_cancel_requested`, `op_canceled`, agent-origin canceled `tool_call_result`, and cancel `tool_response`.

Impact:
Reconnect/idempotency behavior may treat an already canceled command as still in progress, and server device outbox contains stale non-terminal command state after a successful cancel.

Root cause hypothesis:
Confirmed root cause:
1. The agent background `run_tool` path did not catch `asyncio.CancelledError`, so target-command cancellation could skip terminal `seen_commands` state and skip the target `command_result`.
2. Server cancel-result handling marked the cancel operation succeeded and the target operation canceled, but did not reconcile the target `device_outbox` row.
3. A live regression exposed an adjacent race: cancel can arrive after local `seen_commands=in_progress` is written but before the target command is registered in `orchestrator.running_tasks`; that path returned `already_finished` and left local idempotency `in_progress`.

Fix policy:
- Blocking further tests: yes for P1 ACK/dedup/idempotency reliability.
- Fixed now: yes

Fix summary, if fixed:
- Changed files:
  - `pc_agent/ws_agent.py`
  - `pc_agent/core/orchestrator.py`
  - `pc_agent/core/database.py`
  - `pc_agent/tests/test_ws_agent_canceled_command_idempotency.py`
  - `pc_agent/tests/test_cancel_operation_runtime.py`
  - `server/websocket/agent_services.py`
  - `server/tests/test_command_result_lifecycle_db.py`
- Agent `run_tool` cancellation now sends a terminal canceled target `command_result`, stores local `seen_commands.status='canceled'`, and returns cached canceled results for duplicate command ids instead of `COMMAND_IN_PROGRESS`.
- Agent cancel handling now finalizes a pre-running target command if local idempotency is already `in_progress` but the execution task is not yet registered.
- Server cancel-result handling now marks the target operation's `device_outbox` command as delivered/reconciled when cancel succeeds.

Verification after fix:
- Targeted pytest:
  - `python -m pytest pc_agent\tests\test_ws_agent_canceled_command_idempotency.py pc_agent\tests\test_cancel_operation_runtime.py -q` -> `5 passed`.
  - `python -m pytest server\tests\test_command_result_lifecycle_db.py -q` -> `4 passed in 359.05s`.
  - `python -m py_compile pc_agent\ws_agent.py pc_agent\core\orchestrator.py pc_agent\core\database.py server\websocket\agent_services.py` -> passed.
- Live regression 1 after the first fix commit (`1fb8c9fa`):
  - Started `screen.record`, canceled operation `7ca3d807-44d7-4578-95d6-316e2948f0a0` via token-auth fallback because BUG-20260527-06 still blocks web-session cancel.
  - Server target operation became `canceled` and target outbox was reconciled, but local `seen_commands` remained `in_progress`; this exposed the pre-running race above and was fixed in follow-up commit `f7e350e0`.
  - Evidence: `artifacts/live-v3-fix3-cancel-regression.json`.
- Live regression 2 after follow-up commit `f7e350e0`:
  - Ticket: `T-000604` / `68de6816-471b-48ba-88e3-fa691264bba3`.
  - Target operation: `1cb15ce7-9bb8-4393-8029-b477fe67b7ab`.
  - Cancel operation: `8ebb9e62-ee4a-4e48-99a9-496d9b5b4c03`.
  - Final server operations: target `canceled`, cancel operation `succeeded`.
  - Server `device_outbox`: target `run_tool` and cancel command both `status=delivered`.
  - Agent SQLite: target `seen_commands.status='canceled'`, `result_status='canceled'`, `result_error_code='OPERATION_CANCELED'`; cancel command `seen_commands.status='success'`; target/cancel outbox history rows ACKed.
  - Ticket events include `op_cancel_requested`, `op_canceled`, and agent-origin `tool_call_result status=canceled cancel_status=canceled`.
  - Browser/UI: real support UI at `https://192.168.100.17:9443/app/tickets/68de6816-471b-48ba-88e3-fa691264bba3` shows the latest `screen.record` diagnostic at `27 мая, 10:37` with status `Отменена`.
  - Evidence: `artifacts/live-v3-fix3-cancel-regression-2.json`; browser MCP screenshot `live-v3-fix3-cancel-browser.png`.

Regression check:
- Happy `run_tool` path remains covered by existing scheduler/idempotency tests and must be re-run in the final post-fix live gate as P0.7.
- Duplicate canceled command behavior is covered by `test_duplicate_canceled_command_returns_cached_result_without_rerun`.

Remaining risk:
Browser cancellation no longer requires token-auth fallback after BUG-20260527-06; the final post-fix gate should still re-run P0.8 through the visible UI controls, not only browser `fetch`.

### P0.9 Module/toolset snapshot after module lifecycle

Status: partial pass; auto-install, list_tools refresh, snapshot, and newly available tool execution worked, but module lifecycle device events are missing and legacy deactivate is not browser-authenticated.

Evidence:
- Module/runtime state:
  - Started from no `device_modules` rows for `device_id=7a3429ec-1c0b-5495-9aad-b284f08ae965`.
  - Browser support API ran server-listed `network_ping.ping` with params `{"host":"127.0.0.1","count":2,"timeout_ms":1000}` on `T-000604`.
  - Agent log shows automatic `install_module_package` for `network_ping` version `1.0.0`, HTTP download, smoke/load via `module:register`, activation from local `modules_store`, registry rebuild, `list_installed_modules`, `list_tools`, then the actual `run_tool`.
- Device events/toolset snapshots:
  - `device_toolset_snapshots` gained snapshot id `2`, `toolset_hash=bc275e4f2f72a46a`, `agent_version=3.1.61`, `tool_count=7`.
  - `devices.current_toolset_hash` now matches the new snapshot hash `bc275e4f2f72a46a`; `last_tools_changed_at=2026-05-27 01:05:00.409370+05`.
  - `device_events` has no `module_state_changed` or `tools_changed` rows for this device, even though module install/activation and toolset hash changed. See `BUG-20260527-08`.
  - Baseline drift before this install: `devices.current_toolset_hash=464075d978b3230f` had no matching `device_toolset_snapshots` row; only stale snapshot id `1` existed with hash `b79fbe209afb45c2`, agent version `3.1.60`, `tool_count=6`. The explicit install/list_tools flow repaired the snapshot to hash `bc275e4f2f72a46a`.
- Server DB/state:
  - `device_modules`: `network_ping` version `1.0.0`, `installed=true`, `active=true`, `state=active`, `source=command_result`, `installed_at/activated_at/last_seen_at=2026-05-27 01:05:00+05`.
  - Operations/device_outbox chain delivered: `install_module_package` operation `e0d937e8-0d4e-4438-9bff-ae1aa12b0fca`, `list_installed_modules` `437cd2f2-72da-4c7a-8d2b-0bcaf284641f`, `list_tools` `981b12a6-14aa-48d3-9603-c93ba9656aff`, and `network_ping.ping` run `caba269d-7410-4c53-9ac1-bf42318d0646`.
- Browser/admin UI:
  - Real admin modules URL: `https://192.168.100.17:9443/app/admin/modules`; DOM shows `network_ping`, latest/preferred `1.0.0`, tool `network_ping.ping`, and ADMIN-2 as an online compatible Windows lab agent.
  - Real support ticket URL: `https://192.168.100.17:9443/app/tickets/68de6816-471b-48ba-88e3-fa691264bba3`; DOM shows `network_ping.ping` started and then `Успешно` with ping result for `127.0.0.1`.
  - Screenshot: `live-v3-p0-9-network-ping-result.png`.
- Tool behavior:
  - Operation `caba269d-7410-4c53-9ac1-bf42318d0646` succeeded. Result summary: reachable localhost ping, command `ping -n 2 -w 1000 127.0.0.1`, exit code `0`, packet loss `0%`.
  - Running a deactivated tool was not completed: browser/web-session call to `POST /api/devices/{device_id}/modules/deactivate` returned 401 `AUTH_REQUIRED`, same auth-boundary class as `BUG-20260527-06`.
- Root cause notes:
  - The auto-install-before-run path works and explicitly queues follow-up `list_installed_modules` and `list_tools`; this covers the suspected handshake-only hash-compare risk after the operation.
  - Lifecycle event coverage is incomplete: server state converged from command results, but the required agent-origin `module_state_changed` and `tools_changed` device events are absent.
  - Deactivate/remove negative behavior still needs a valid web-session alias or admin-token path before it can be tested from the real admin UI.

### BUG-20260527-08 — Module lifecycle changes do not persist module_state_changed/tools_changed device events

Severity: P1
Status: open
Area: module-runtime / protocol / DB

Scenario:
P0.9 auto-install and activation of `network_ping` before running `network_ping.ping`.

Expected:
Agent module install/activation and toolset hash change should emit `module_state_changed` and `tools_changed` device events, the server should ACK/persist those events, and list_tools snapshot refresh should be traceable to those convergence signals.

Actual:
The module was installed and activated, `device_modules` and `device_toolset_snapshots` converged, and `network_ping.ping` succeeded, but `device_events` contains no rows for the device, including no `module_state_changed` or `tools_changed`.

Repro steps:
1. Run `network_ping.ping` on a device with no prior `network_ping` row in `device_modules`.
2. Observe agent log installing and activating the module, then running `list_installed_modules`, `list_tools`, and the tool.
3. Query `device_events` for the device.

Evidence:
- Server log:
- Agent log: install/load/activate sequence for `network_ping` version `1.0.0`, then `list_installed_modules`, `list_tools`, and successful `network_ping.ping`.
- Browser/UI: admin modules page shows `network_ping`; support ticket timeline shows successful `network_ping.ping`.
- Server DB: `device_modules.network_ping` active; snapshot id `2` hash `bc275e4f2f72a46a`, `tool_count=7`; `device_events` returned `0` rows for the device.
- Agent SQLite:
- WS/API payload: command-result path delivered, but no persisted device-event envelope exists for module/toolset change.
- Fix evidence, 2026-05-27 11:41-11:45 +05:
  - Changed files: `pc_agent/core/orchestrator.py`, `pc_agent/ws_agent.py`, `pc_agent/core/sender.py`, `pc_agent/tests/test_sender_batching.py`, `pc_agent/tests/test_orchestrator_module_lifecycle_events.py`.
  - Targeted tests: `python -m py_compile pc_agent\core\sender.py pc_agent\core\orchestrator.py pc_agent\ws_agent.py pc_agent\tests\test_sender_batching.py pc_agent\tests\test_orchestrator_module_lifecycle_events.py` exit 0; `python -m pytest pc_agent\tests\test_sender_batching.py pc_agent\tests\test_orchestrator_module_lifecycle_events.py pc_agent\tests\test_startup_module_inventory_sync.py -q` -> `8 passed in 0.94s`.
  - Live agent restarted in source GUI mode: `python scripts\manage_local_agent.py start live-v3-deep --gui --ws-url wss://192.168.100.17:9443/ws --api-url https://192.168.100.17:9443/api`; status `mode=gui/source`, `connection_state=connected`, `device_id=7a3429ec-1c0b-5495-9aad-b284f08ae965`.
  - Live module lifecycle regression: remove operation `55f4f644-9a5b-46f2-b8d1-a139b0a1e5ec` succeeded; install operation `a7416018-9094-46ff-821b-f260b05ab9bd` succeeded.
  - Agent SQLite `outbox_sent_history`: `tools_changed` outbox ids `23` and `26`; `module_state_changed` outbox ids `22`, `24`, `25`, `27`, `28`, `29`; no pending/failed rows for these kinds.
  - Server DB `device_events`: persisted `device_seq=2 tools_changed tools_count=6 hash=464075d978b3230f`, `device_seq=3 module_state_changed deactivate:network_ping`, `device_seq=4 module_state_changed remove:network_ping`, `device_seq=5 tools_changed tools_count=7 hash=849e77ee78906464`, `device_seq=6..8 module_state_changed install:network_ping@1.0.0`.
  - Server DB `device_modules`: `network_ping` version `1.0.0`, `installed=true`, `active=true`, `state=active`, `source=event`, `last_seen_at=2026-05-27 06:42:45+00`.
  - Server DB `device_outbox`: remove/install commands are `delivered`, with `delivered_at` set and `error_code=null`.
  - Browser/UI: real browser URL `https://192.168.100.17:9443/app/admin/device-operations/7a3429ec-1c0b-5495-9aad-b284f08ae965?tab=modules`; DOM shows `МОДУЛИ ok`, `Missing 0, outdated 0, failed 0`, `network_ping`, `Установлено: 1.0.0`, `Desired: 1.0.0`, `active`. Screenshots: `live-v3-fix5-device-modules-tab.png`, `live-v3-fix5-modules.png`.

Impact:
Observer/reconcile flows that rely on device events cannot explain or react to module lifecycle changes, and future no-op installs may depend on command-result follow-ups rather than the documented event contract.

Root cause:
Two independent agent-side issues masked the documented module lifecycle event path:
1. `WSAgent` constructed `AgentOrchestrator` without `agent_uuid`, leaving `orchestrator.device_id=None`; `_emit_module_state_changed` and `_rebuild_registry_from_active_modules` therefore returned without enqueueing durable device events in the real runtime.
2. `DatabaseManager.enqueue_event` stores `ticket_id=device_id` for local SQLite compatibility, and `WSOutboxFlusher` leaked that compatibility ticket context into Protocol V3 device-event envelopes. After strict server validation, device events with `device_seq` plus ticket context are invalid; device events must be classified solely by `device_seq` and must omit top-level/event `ticket_id`.

Fix policy:
- Blocking further tests: no, because command-result follow-ups updated DB and toolset snapshot enough to continue.
- Fixed now: yes

Fix summary, if fixed:
`WSAgent` now passes the canonical device id into `AgentOrchestrator`, `AgentOrchestrator` also falls back to `identity_manager.device_id`, and `WSOutboxFlusher` strips compatibility `ticket_id` from device-event wire envelopes while preserving ticket events.

Verification after fix:
P0.9 live regression repeated against the real server and source-mode GUI agent. Server persisted ordered `module_state_changed` and `tools_changed` rows; local agent archived the events in `outbox_sent_history`; no pending/failed lifecycle outbox rows remained; browser device modules tab showed `network_ping` active with clean reconcile counts.

Regression check:
Targeted pytest covers install emits module/tools events, no-op reinstall does not duplicate `tools_changed`, deactivate emits module state and hash-change `tools_changed`, startup inventory sync still emits module state, and sender device-event envelopes omit ticket context. Live regression covered remove/install via real server commands.

Remaining risk:
The live remove/install path emitted duplicate `module_state_changed install:network_ping@1.0.0` rows (`device_seq=6..8`). They are persisted correctly and no longer lost, but dedup/noise should be reviewed during the next module lifecycle pass rather than blocking P1 ACK/dedup fixes.

### P0.10 Protocol V3 malformed outbox probes

Status: failed; BUG-20260527-09 recorded. Probe required briefly stopping the real local agent to avoid same-device websocket supersede races, then `live-v3-deep` was restarted and is running again.

Evidence:
- Diagnostic tool:
  - Extended `scripts/live_ws_v3_probe.py` with `malformed-outbox --case all`.
  - Token source: `PC_CLIENT_AGENT_TOKEN` from local SQLite, printed only prefix `d7ad25a1`, sha prefix `54898cb35fe5`, length `64`.
  - Probe ticket: `T-000604`, `ticket_id=68de6816-471b-48ba-88e3-fa691264bba3`.
  - The first attempt while the GUI agent was running was superseded by the real agent reconnecting. For the actual probe, `python scripts/manage_local_agent.py stop live-v3-deep` was run, then the raw probe, then `python scripts/manage_local_agent.py start live-v3-deep --gui --launcher --ws-url wss://192.168.100.17:9443/ws --api-url https://192.168.100.17:9443/api`. Final status: `live-v3-deep: running`.
- ACK/NACK cases:
  - `both_seq`: sent `agent_seq` and `device_seq` together for a ticket event. Expected non-retryable NACK; actual `outbox_ack`, and a `ticket_events.chat_message` row was persisted.
  - `neither_seq`: sent no `agent_seq`/`device_seq` and no ticket id in the event. Expected non-retryable NACK; actual `outbox_ack` with no corresponding DB event found.
  - `unknown_ticket`: sent a random unknown `ticket_id`. Expected `UNKNOWN_TICKET` NACK; actual `outbox_ack` with no ticket event found.
  - `missing_trace_id`: expected validation NACK; actual `outbox_nack`, `retryable=false`, `code=VALIDATION_ERROR`, with fallback server trace id. This case passed.
  - `wrong_actor_role`: sent `meta.actor_role=user`. Expected `UNAUTHORIZED`; actual `outbox_nack`, `retryable=false`, `code=UNAUTHORIZED`. This case passed.
  - `top_ticket_only`: top-level `ticket_id` set but `event.ticket_id` missing and `device_seq` set. Expected NACK/no phantom event; actual `outbox_ack`, persisted as a device event `chat_message` with `device_seq=9406`.
  - `unknown_item_type`: sent `item_type=unknown_live_probe_type` and `event=unknown_live_probe_event`. Expected validation NACK; actual `outbox_ack` with no DB event found.
- Server DB/state:
  - `ticket_events`: inserted id `60`, `event_type=chat_message`, `agent_seq=9001`, `probe_case=both_seq`, visible text `live malformed probe both_seq`; a `message_read` event id `61` followed.
  - `device_events`: inserted id `1`, `event_type=chat_message`, `device_seq=9406`, `probe_case=top_ticket_only`.
  - ACK-without-persistence cases observed for `neither_seq`, `unknown_ticket`, and `unknown_item_type`.
  - Probe side effect: while the raw probe was connected, server dispatched pending `install_module_package` commands `5981ac79-e117-497f-bbf4-104b59e100f3` and `0e539dee-e910-4851-9295-d80ff25649a8` to the probe connection; because the probe is not a full agent, those `device_outbox` rows remain `sent`. This is test contamination and also evidence for reconnect/outbox cleanup follow-up.
- Agent local state:
  - The local agent was stopped during the raw probe, then restarted. It reloaded active module `network_ping` from `modules_store` and received `handshake_ack`.
  - Local agent SQLite was not expected to contain the raw probe outbox rows because the malformed items were sent directly by the diagnostic script, not through the agent outbox.
- Browser/admin UI:
  - Real browser URL: `https://192.168.100.17:9443/app/tickets/68de6816-471b-48ba-88e3-fa691264bba3`.
  - DOM/browser output confirms phantom user-visible message `live malformed probe both_seq` under `admin-2`.
  - Screenshot: `live-v3-p0-10-phantom-probe-event.png`.
- Root cause notes:
  - The server validates missing trace and unauthorized actor correctly.
  - Several contract-invalid or semantically invalid envelopes are ACKed, and at least two create persisted phantom events. This is a data-integrity risk and violates the Protocol V3 invariant that event type is determined only by exactly one of `agent_seq` or `device_seq`.
  - The raw probe also exposed that command dispatch can race with handshake/probe connections and leave sent commands when a non-agent client uses a valid device token.

### BUG-20260527-09 — Malformed outbox items are ACKed and can persist phantom events

Severity: P1
Status: verified-fixed
Area: protocol / DB / UI

Scenario:
P0.10 raw Protocol V3 malformed outbox probes against a valid post-handshake device session.

Expected:
Contract-invalid outbox items should receive non-retryable `outbox_nack`; wrong/unknown ticket should receive `DEVICE_MISMATCH` or `UNKNOWN_TICKET`; unauthorized actor should receive `UNAUTHORIZED`; invalid events should not persist or appear in UI.

Actual:
`both_seq`, `neither_seq`, `unknown_ticket`, `top_ticket_only`, and `unknown_item_type` received `outbox_ack`. `both_seq` persisted a ticket `chat_message`; `top_ticket_only` persisted a device `chat_message`; other ACKed invalid cases had no DB event, creating ACK-without-persistence data-loss risk.

Repro steps:
1. Stop the live GUI agent to avoid same-device websocket supersede.
2. Run `scripts/live_ws_v3_probe.py --timeout 2.0 malformed-outbox --case all` with the live agent token in `PC_CLIENT_AGENT_TOKEN`.
3. Query `ticket_events` and `device_events` for `payload.probe_case`.
4. Open the ticket in the browser and search for `live malformed probe`.

Evidence:
- Server log:
- Agent log: local agent was stopped for raw probe and restarted after; raw probe itself is not the agent.
- Browser/UI: ticket `T-000604` shows phantom message `live malformed probe both_seq`.
- Server DB: `ticket_events.id=60` for `probe_case=both_seq`; `device_events.id=1` for `probe_case=top_ticket_only`; ACK-without-persistence for several invalid cases.
- Agent SQLite: not applicable for direct raw WS probe.
- WS/API payload: probe output captured per-case ACK/NACK; `missing_trace_id` and `wrong_actor_role` NACKed correctly, others ACKed incorrectly.

Impact:
Malformed or malicious agent messages can create user-visible phantom timeline entries or receive ACK despite no durable persistence, breaking outbox reliability and audit guarantees.

Root cause hypothesis:
Outbox envelope validation checks only basic `payload.outbox_id`, `item_type`, and `trace_id`; persistence then classifies by `event.ticket_id` instead of first enforcing the strict XOR invariant for `agent_seq`/`device_seq` and validating `item_type` against allowed event families. Top-level `ticket_id` is ignored for classification, enabling ticket-context mismatch.

Fix policy:
- Blocking further tests: yes for P1.1/P1.2 credibility, because ACK-without-persistence and phantom events make ACK/dedup/idempotency conclusions unreliable.
- Fixed now: yes

Fix summary, if fixed:
- Root cause: `OutboxEnvelopeValidator` only checked basic `outbox_id`/`trace_id`; `OutboxPersistenceService` ACKed unsupported `item_type` as no-op and classified ticket vs device events from `payload.event.ticket_id` instead of the Protocol V3 seq XOR invariant.
- Changed files: `server/websocket/outbox_ingest_components.py`, `server/tests/test_agent_services_pipeline.py`, `scripts/live_ws_v3_probe.py`.
- Fix: server now rejects unsupported `item_type`, non-object `payload.event`, both/missing seq, ticket/device context conflicts, missing top-level ticket_id for ticket events, and event/top-level ticket_id mismatch before persistence. Persistence now uses `agent_seq` vs `device_seq` as the source of truth and top-level `ticket_id` for ticket events.
- Commit/deploy: local commit `e7518d88117d6adcbb7066eaadc3d8561f8f334f` (`fix: harden protocol v3 outbox ingest`) pushed to `origin` and deployed to Linux with `python scripts/deploy_workspace_to_remote.py --gate quick --allow-local-dirty`; server restarted to PID `3795474`.

Verification after fix:
- Targeted pytest: `python -m pytest server\tests\test_agent_services_pipeline.py -q` -> `23 passed in 0.16s`.
- Diagnostic compile: `python -m py_compile scripts\live_ws_v3_probe.py` -> passed.
- Live regression command: stopped `live-v3-deep`, ran `python scripts\live_ws_v3_probe.py --timeout 2 malformed-outbox --case all --run-id fix1e7518d --seq-base 777000`, then restarted `live-v3-deep`.
- Transport evidence: all malformed cases returned non-retryable NACK. `both_seq` and `neither_seq` -> `VALIDATION_ERROR` (`exactly one of agent_seq or device_seq`); `unknown_ticket` -> `UNKNOWN_TICKET`; `missing_trace_id` -> `VALIDATION_ERROR`; `wrong_actor_role` -> `UNAUTHORIZED`; `top_ticket_only` -> `VALIDATION_ERROR` (`Device event must not include ticket_id context`); `unknown_item_type` -> `VALIDATION_ERROR`.
- Server DB evidence: for `payload->>'probe_run_id' = 'fix1e7518d'`, `ticket_events=0`, `device_events=0`.
- Agent state: `live-v3-deep` restarted and running after probe (`pid=10324`, `wss://192.168.100.17:9443/ws`).
- Browser/UI evidence: real browser URL `https://192.168.100.17:9443/app/tickets/68de6816-471b-48ba-88e3-fa691264bba3`; timeline still shows the old P0.10 evidence message `live malformed probe both_seq`, but no `fix1e7518d` marker or new malformed probe entry appears. Screenshot: `artifacts/live-v3-fix1-ticket-browser.png`.

Regression check:
- Unit regressions covered valid ticket event ACK/persist, valid device event ACK/persist, missing trace NACK, wrong actor `UNAUTHORIZED`, unknown ticket `UNKNOWN_TICKET`, malformed contract NACK before persistence, and retryable NACK duplicate behavior.
- Full live regression for P0.7 happy `system.collect` and valid `tools_changed` device event remains in the final verification gate after Fix 1-6, per current task ordering.

Remaining risk:
- Existing pre-fix phantom evidence remains in live data by design: ticket `T-000604` still contains old `live malformed probe both_seq`, and the old `device_events.chat_message` row remains. Treat only new `probe_run_id` markers as post-fix evidence.
- During the raw probe the server again attempted to dispatch stale pending `install_module_package` command state to the probe connection before handshake ack was observed; this is test contamination from earlier P0 rows and should be revisited with BUG-20260527-07/reconnect cleanup, not as a new BUG-09 failure.

### BUG-20260527-10 — Local GUI automation tool actions omit account-session context

Severity: P1
Status: open
Area: account-session / UI

Scenario:
Post-fix P0.7/P0.8 regression attempted to run `ticket.tool.run` and `ticket.capture_video` through `scripts/agent_test_driver.py` while the local GUI had an active confirmed account session and ticket `T-000606` existed.

Expected:
Local automation tool actions should either mirror the real supported GUI/web support tool flow with the active server account session, or return a clear unsupported-action error before calling the server.

Actual:
Both local automation calls returned HTTP `500` from `/ui/automation/run` with embedded server HTTP `403`, `error=account_session_invalid`, `error_code=ACCOUNT_SESSION_REQUIRED`.

Repro steps:
1. Ensure `live-v3-deep` is connected and an account is selected.
2. Run `python scripts\agent_test_driver.py run-tool live-v3-deep --ticket-id 92923cf9-3a68-4e1f-a130-e7397a306b2e --tool-name system.collect --params-json "{}"`.
3. Run `python scripts\agent_test_driver.py capture-video live-v3-deep --ticket-id 92923cf9-3a68-4e1f-a130-e7397a306b2e --duration-sec 30`.

Evidence:
- Server log/API: server returned `ACCOUNT_SESSION_REQUIRED` to the automation-initiated requester API path.
- Agent log: local automation returned HTTP `500` with embedded HTTP `403`.
- Browser/UI: not created through local automation; browser support route was used as a workaround and succeeded.
- Server DB: no operation rows were created by the failed local automation attempts.
- Agent SQLite: no new operation idempotency rows from these failed local automation tool attempts.
- WS/API payload: local error body `{"status":"error","error":"HTTP 403: ... ACCOUNT_SESSION_REQUIRED"}`.

Impact:
The automation bridge is now reliable for `ticket.create` after BUG-20260527-04, but it is still not a complete substitute for real GUI/support-browser tool action testing. P0.7/P0.8 had to use the browser web-session route instead.

Root cause hypothesis:
`pc_agent/ui_gui/automation_controller.py` / `pc_agent/ui_gui/server_api.py` tool-action paths do not pass the active requester account session where the server expects account-scoped requester authorization, unlike the fixed create-ticket path.

Fix policy:
- Blocking further tests: no, because browser support routes exercise the canonical support tool flow and were used for P0.7/P0.8.
- Fixed now: no

Fix summary, if fixed:
N/A.

Verification after fix:
Pending.

Regression check:
After fixing, repeat `agent_test_driver.py run-tool` and `capture-video` with an active confirmed account session and confirm operation rows/timeline entries in browser.

Remaining risk:
Other `/ui/automation/run` actions may still diverge from real GUI account-session behavior.

### P0 milestone summary

Recorded at: 2026-05-27 01:15 Asia/Yekaterinburg.

P0 execution status:
- Run: P0.1 through P0.10.
- Passed: P0.1 after server restart recovery, P0.6 canonical lifecycle, P0.7 `system.collect` happy lifecycle.
- Partial pass: P0.3, P0.4, P0.8, P0.9.
- Failed with bugs recorded: P0.2, P0.5, P0.10.

Bugs recorded and not fixed at original P0 closeout:
- `BUG-20260527-01`: live server stopped during baseline.
- `BUG-20260527-02`: Protocol V3 close codes are not observed by raw WS clients.
- `BUG-20260527-03`: UIA create wizard cannot complete required fields reliably.
- `BUG-20260527-04`: local GUI automation ticket.create omits active account session.
- `BUG-20260527-05`: WS chat_raise returns success for a non-persisted ticket.
- `BUG-20260527-06`: web-session operation cancel endpoint returns AUTH_REQUIRED.
- `BUG-20260527-07`: canceled run_tool leaves stale sent/in_progress command state.
- `BUG-20260527-08`: module lifecycle changes do not persist module_state_changed/tools_changed device events.
- `BUG-20260527-09`: malformed outbox items are ACKed and can persist phantom events.

Blocking fixes applied:
- None. Server restart and local agent restart were operational recovery steps only; no product code fixes were made.

Post-P0 fix status:
- 2026-05-27 09:51 +05: `BUG-20260527-09` verified-fixed by commit `e7518d88117d6adcbb7066eaadc3d8561f8f334f`, targeted pytest, live malformed-outbox regression, DB zero-row check, and browser ticket timeline confirmation.
- 2026-05-27 10:13 +05: `BUG-20260527-05` verified-fixed by DB-first/error-only `chat_raise` handling, server and agent targeted pytest, live `/ui/request_support` regression with explicit `TICKET_CREATE_UNAVAILABLE`, zero phantom DB rows, zero new `UNKNOWN_TICKET`, and browser timeline confirmation.
- 2026-05-27 10:43 +05: `BUG-20260527-07` verified-fixed by commits `1fb8c9fa7874629d8e9ec898562b4362f43bb6d2` and `f7e350e08e4a3faef4728133e1464d7509759b8f`, targeted server/agent pytest, live `screen.record` cancel regression, server `device_outbox` delivered check, agent `seen_commands.status='canceled'`, and browser ticket timeline confirmation.
- 2026-05-27 11:23 +05: `BUG-20260527-06` verified-fixed by commit `91f7529aa2e864298ae025ac4e20123688d1e368`, targeted server/webapp tests, quick release with rebuilt web bundle, live browser web-session `screen.record` cancel through `/api/web/support/operations/{operation_id}/cancel`, DB/device_outbox verification, and browser timeline confirmation.
- 2026-05-27 11:45 +05: `BUG-20260527-08` verified-fixed in local/source agent by passing canonical device id into `AgentOrchestrator` and stripping compatibility `ticket_id` from device-event wire envelopes; targeted agent pytest passed, live remove/install `network_ping` regression persisted `module_state_changed`/`tools_changed`, local outbox had no pending lifecycle rows, and browser device modules tab confirmed `network_ping` active.
- 2026-05-27 12:05 +05: `BUG-20260527-04` verified-fixed in local/source agent by passing the active account session through GUI automation create; targeted agent tests passed, pywinauto/UIA selected the confirmed account, `agent_test_driver.py create-ticket` created `T-000605`, DB requester account fields were correct, local outbox had no recent failed rows, and browser ticket detail showed the new ticket.
- 2026-05-27 12:20 +05: all requested Fix 1-6 code changes are committed and pushed through `bb6f77267509133bd8cb0a70901ec6a019161dca`; post-fix gates reran `verify_workspace.py`, targeted pytest, P0.4 automation create, P0.5 chat_raise, P0.7 `system.collect`, P0.8 browser cancel, P0.9 module projection, and P0.10 malformed outbox.

Post-fix verification gate, 2026-05-27 12:05-12:20 +05:
- Code/test gates:
  - Fix 6 commit: `bb6f77267509133bd8cb0a70901ec6a019161dca` (`fix: pass account session through GUI automation`) pushed to `origin/codex/helpdesk-process-model`.
  - Targeted pytest: `python -m pytest pc_agent\tests\test_gui_automation_controller.py pc_agent\tests\test_registration_status.py::test_create_ticket_sends_only_requester_account_session_when_passed -q` -> `3 passed in 0.69s`.
  - Workspace gate: `python scripts\verify_workspace.py` -> passed.
- P0.4 automation create:
  - Command: `python scripts\agent_test_driver.py create-ticket live-v3-deep --title "Live V3 post-fix automation create bb6f7726" --description "Post-fix gate for P0.4 automation create with active confirmed account session."`.
  - Result: `ticket_id=92923cf9-3a68-4e1f-a130-e7397a306b2e`, `ticket_code=T-000606`, status `queued`, requester account session `6196fe8b-d836-44c5-9760-88a2f5d31f7a`, mode `confirmed_binding`.
  - Server DB: `tickets.T-000606` persisted with requester person `bb00a942-fe2c-461c-b982-9da17d3fd1ff`, binding `0618eb74-9fa6-4dbe-9634-d9b56825f3ad`, account session `6196fe8b-d836-44c5-9760-88a2f5d31f7a`.
  - Browser/UI: `https://192.168.100.17:9443/app/tickets/92923cf9-3a68-4e1f-a130-e7397a306b2e` showed `T-000606`, requester `Тестовый тест 12`, status `В очереди`, and the initial user message.
- P0.5 chat_raise:
  - Command: `python scripts\agent_test_driver.py request-support live-v3-deep --title "Live V3 post-fix chat_raise bb6f7726" --reason "post_fix_gate" --severity "warning"`.
  - Result: local bridge returned `status=ok`, `result.ok=false`, `error_code=TICKET_CREATE_UNAVAILABLE`, `error="Ticket creation is unavailable for chat_raise"`.
  - No new phantom persisted ticket id was returned; no new local `UNKNOWN_TICKET` rows were created by this post-fix chat_raise attempt.
- P0.7 system.collect:
  - Browser web-session route: `POST /api/web/support/tickets/92923cf9-3a68-4e1f-a130-e7397a306b2e/tools/run` with `tool_name=system.collect`.
  - Result: HTTP `202`, operation `8f223efd-4086-472c-8925-0453b7317280`, trace `8b9e2aff-db27-48da-8bd2-44dc407a106b`; DB `operations.status=succeeded`, `device_outbox.status=delivered`.
  - Browser ticket timeline showed `system.collect` accepted and then successful diagnostic output with hostname `ADMIN-2`, CPU/RAM/Disk values.
  - Agent SQLite `seen_commands`: target command `8f223efd-4086-472c-8925-0453b7317280` status `success`.
- P0.8 browser cancel:
  - Browser web-session run: `screen.record`, operation `a0512684-cc48-47ee-a20d-f206dc003a9a`; cancel route `POST /api/web/support/operations/a0512684-cc48-47ee-a20d-f206dc003a9a/cancel`.
  - Result: HTTP `200`, cancel operation `c3ca2ceb-2059-40cb-96cb-3b09dc8b0538`.
  - Server DB: target operation `canceled`, cancel operation `succeeded`; target and cancel `device_outbox` rows are `delivered`.
  - Agent SQLite `seen_commands`: target status `canceled`, cancel status `success`.
  - Browser ticket timeline showed `screen.record` accepted and then `Статус: Отменена`, result `Tool screen.record canceled`. Screenshot: `live-v3-postfix-ticket-tool-cancel.png`.
- P0.9 module lifecycle/projection:
  - Reused the verified Fix 5 live remove/install regression for durable lifecycle events, then rechecked browser projection after all fixes.
  - Server DB recent `device_events` includes `module_state_changed` and `tools_changed` for device `7a3429ec-1c0b-5495-9aad-b284f08ae965`; latest post-restart `module_state_changed` had `device_seq=10`.
  - Browser admin modules tab `https://192.168.100.17:9443/app/admin/device-operations/7a3429ec-1c0b-5495-9aad-b284f08ae965?tab=modules` showed `Модули ok`, `Missing: 0`, `Outdated: 0`, `network_ping`, `Установлено: 1.0.0`, `Desired: 1.0.0`, `active`. Screenshot: `live-v3-postfix-device-modules.png`.
  - Note: the device operations overview still shows historical failed operation counts and an `install_module_package` timeout from raw-probe/test contamination; module reconcile state itself is ok.
- P0.10 malformed outbox:
  - First post-fix probe while the GUI agent was running was superseded by the real same-device agent reconnecting, so the clean run briefly stopped `live-v3-deep`, ran the raw probe, and restarted the source GUI agent.
  - Command: `python scripts\live_ws_v3_probe.py malformed-outbox --case all --ticket-id 92923cf9-3a68-4e1f-a130-e7397a306b2e --run-id postfixbb6 --seq-base 930000`.
  - Probe output: all malformed cases returned non-retryable NACK: `both_seq`/`neither_seq` `VALIDATION_ERROR`, `unknown_ticket` `UNKNOWN_TICKET`, `missing_trace_id` `VALIDATION_ERROR`, `wrong_actor_role` `UNAUTHORIZED`, `top_ticket_only` `VALIDATION_ERROR`, `unknown_item_type` `VALIDATION_ERROR`.
  - Server DB: `malformed_count=0` for `payload::text like '%postfixbb6%'` on ticket `T-000606`; browser ticket timeline did not show `postfixbb6` or `live malformed probe`.
  - Agent restarted after the probe and is running source GUI mode on `wss://192.168.100.17:9443/ws`.
- New non-blocking defect recorded during this gate: `BUG-20260527-10` for local automation `ticket.tool.run`/`capture-video` account-session omission. Browser web-session routes were used for P0.7/P0.8, so P1 ACK/dedup/idempotency is not blocked by this bridge-only gap.

Current live state:
- Local agent `live-v3-deep` is running again after P0.10, currently `pid=4528`, `mode=gui/source`, connected to `wss://192.168.100.17:9443/ws`.
- Server remains running on `https://192.168.100.17:9443`.
- Test ticket `T-000604` contains intentional P0.10 probe evidence (`live malformed probe both_seq`) and should not be treated as normal requester input.
- Known residual stale rows from pre-fix testing: target cancel run_tool `device_outbox` row id `6` remains `sent`; raw probe `install_module_package` rows ids `12` and `13` remain `sent`; local SQLite still contains old failed `UNKNOWN_TICKET` rows from pre-fix chat_raise `cc002181-f7d9-44da-8726-da46463c090f`. Post-fix cancel regression uses operation `a0512684-cc48-47ee-a20d-f206dc003a9a`, whose target outbox is delivered and local idempotency is terminal canceled.

Recommended next test pass:
- First fix or explicitly tolerate the P0 protocol/data-integrity defects before running P1.1/P1.2, because malformed ACKs and stale command idempotency can contaminate ACK/dedup and duplicate-command conclusions.
- Then run P1 in this order: P1.1 ACK/NACK/dedup, P1.2 command idempotency, P1.3 consent, P1.5 restart/reconnect, P1.6 UI projection, P1.4 auto-install negatives.
- P2 should wait until P0.10 and P0.8 cleanup semantics are fixed or isolated to a disposable test device/ticket.
