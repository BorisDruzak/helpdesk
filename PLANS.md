# pc_client Product / Infra Plan

This file is intentionally compact. Detailed phase logs live in git history and the referenced CI/release artifacts; this document keeps the current product state, accepted checkpoints, active work, verification evidence and rollback notes.

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

## Current Invariants

- Work only in `C:\Users\admin-2\CodexProjects\pc_client`; the SMB share and Linux checkout are mirrors.
- Do not weaken P0-P4 contracts, canonical ticket statuses, Service Catalog fields, Knowledge visibility, Quality privacy or Problem lifecycle.
- Protocol V3 is unchanged unless explicitly required; current P5 scope does not require it.
- Requester/public surfaces must not expose internal QA, RCA, change risk notes, infrastructure details, rollback steps, queue ids, raw policy JSON or requester PII in analytics.
- Full DB/API gates use isolated test databases through the P2.3 harness; shared `pc_support_test` is debug-only and not a full gate.
- Product UI changes require webapp build plus remote/browser signoff at `https://192.168.100.17:9443/admin` before release acceptance.

## Active Work: P5 Change Enablement

Status: local release-candidate; remote/browser signoff pending.

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
- Full canonical CI passed: `python scripts/run_ci_suite.py --server-pytest-timeout 7200 --pc-agent-pytest-timeout 3600 --idle-timeout 0`.
- Full CI artifact: `artifacts/ci/d7f383693633ccb22cc79114a737ee9697af9004/summary.json`.
- Full CI layer counts: `server_pytest_no_db` 323 passed; `server_pytest_db_knowledge` 90 passed; `server_pytest_db_tickets` 275 passed; `server_pytest_db_observer_diagnostics` 74 passed; `server_pytest_db_agent_runtime` 84 passed; `server_pytest_db_web_api` 195 passed; `server_pytest_agent_ws` 30 passed; `pc_agent_pytest` 315 passed.
- Remote/browser signoff remains pending for `/app/admin/changes`, create normal change, risk/plan/rollback, approval, scheduling, tasks, PIR, close, create from problem and linked problem detail.

### Rollback Notes

- Disable/hide change creation UI and keep `changes` read-only if P5 must be paused.
- Alembic downgrade `092` removes P5 change tables/links only; P0-P4 tables and workflows remain intact.
- No ticket workflow rollback is required because P5 does not change canonical ticket statuses or automatic ticket transitions.

### Remaining Risks

- Final acceptance still requires commit/push plus remote release/browser signoff.
- P5 does not implement external calendar integrations, automatic execution, or full P5+ release orchestration; those are intentionally outside Change Enablement.
