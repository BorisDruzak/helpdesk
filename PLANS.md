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

Status: implemented / production-oriented cut pending release signoff.

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

Verification target:

- `server/tests/test_approval_consent_center.py`, command-center and device-operations regressions, `python -m compileall -q server`.
- `pnpm --dir webapp test -- approval-consent`, `pnpm --dir webapp test -- command-center`, `pnpm --dir webapp build`.
- `python scripts/verify_workspace.py`, `git diff --check`, browser smoke for `/app/support/approvals` before release acceptance.

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
