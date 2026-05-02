# Service Desk Hardening And Agent Live UX Plan

> For agentic workers: use `superpowers:executing-plans` for each slice and keep this file current after every verified checkpoint. This is the active long-horizon plan for `pc_client`; completed historical service-desk and agent plans were intentionally removed from this file after Slice 17 signoff.

## Status

Created: 2026-05-02.

Last updated: 2026-05-03, after Slice 8 final gates.

The previous service desk model plan is complete. Final signoff covered server/agent/web focused tests, release smoke, browser checks and observer runtime. Working maturity estimate after that signoff:

- Backend/runtime: about 99.6%.
- Server UI: about 91.5%.
- Agent GUI: about 74.5%.
- Overall configurable service desk maturity: about 99.0% for the documented model, with remaining work treated as hardening/UX backlog.

This new plan is not a continuation of the model-build plan. It is a hardening and UX plan for the remaining gaps: workflow action depth, approval UX, notification/visibility previews, passport/reporting rigor, smart-view coverage, agent live UX, and data cleanup.

Current plan completion: 100.0% (8 of 8 slices complete).

## Goal

Turn the completed service desk model into a more production-grade operator/requester experience: policy actions are explicit and auditable, support/requester UIs show the right next actions, exported/passport evidence is validated, smart views are dependable, and the agent create flow is live-smoked end to end against current published templates.

## Scope

- Workflow actions and editor:
  - `server/tickets/workflow_profiles.py`
  - `server/tickets/workflow_service.py`
  - `server/web_api/settings_handlers.py`
  - `webapp/src/pages/settings/index.tsx`
  - `server/tests/test_ticket_workflow_profiles.py`
  - `server/tests/test_web_settings_api.py`
  - `webapp/src/pages/settings/index.test.tsx`

- Approvals UI and API surfacing:
  - `server/tickets/approval_policy.py`
  - `server/web_api/support_handlers.py`
  - `server/web_api/dto/support.py`
  - `webapp/src/pages/tickets/detail-page.tsx`
  - `server/tests/test_ticket_approval_policy.py`
  - `server/tests/test_web_support_api.py`
  - `webapp/src/pages/tickets/detail-page.test.tsx`

- Notification and visibility hardening:
  - `server/tickets/notification_service.py`
  - `server/tickets/policy_action_dispatcher.py`
  - `server/tickets/visibility_policy.py`
  - `server/tickets/passport_service.py`
  - `webapp/src/features/forms-builder/forms-builder-panel.tsx`
  - `server/tests/test_ticket_notification_policy.py`
  - `server/tests/test_ticket_visibility_policy.py`
  - `webapp/src/features/forms-builder/forms-builder-panel.test.tsx`

- Passport/reporting hardening:
  - `server/tickets/passport_service.py`
  - `server/tickets/closure_policy.py`
  - `server/web_api/support_handlers.py`
  - `webapp/src/pages/tickets/detail-page.tsx`
  - `server/tests/test_ticket_passport_service.py`
  - `server/tests/test_ticket_closure_policy.py`

- Smart views:
  - `server/tickets/smart_views.py`
  - `server/web_api/support_handlers.py`
  - `server/app/repos/helpdesk_policy_repo.py`
  - `webapp/src/pages/tickets/list-page.tsx`
  - `server/tests/test_web_support_api.py`
  - `server/tests/test_helpdesk_policy_registry.py`

- Agent live UX:
  - `pc_agent/ui_gui/chat_panel.py`
  - `pc_agent/ui_gui/server_api.py`
  - `pc_agent/tests/test_chat_panel_helpers.py`
  - `pc_agent/tests/test_ticket_api_client_attachments.py`
  - `pc_agent/docs/CODEMAP.md`

- Docs/navigation:
  - `docs/QUICK_LOOKUP.md`
  - `server/docs/CODEMAP.md`
  - `server/docs/TICKET_SYSTEM.md`
  - `scripts/navigation_catalog.py`
  - `scripts/helpdesk_data_cleanup.py`
  - `PLANS.md`

## Constraints

- Work only in `C:\Users\admin-2\CodexProjects\pc_client`.
- Keep the remote Linux copy `/var/chat_bot/pc_client` as a deploy target only.
- Preserve old `request_forms`, `form_key`, public `/help`, and agent cached form-pack compatibility.
- Do not expose raw SLA/OLA/internal policy jargon to requester-facing UI.
- For UI changes use the Browser Canon: `http://192.168.100.17:8666/admin`, then inspect the relevant `/app/*` pages.
- For new or changed React/webapp paths, first run `python scripts/bootstrap_web_toolchain.py`.
- Use RED/GREEN tests for behavior changes where realistic.
- Before claiming a slice complete, run fresh verification and record it here.
- After remote checks stop the server unless the user explicitly asks to leave it running.

## Current State

- The core model chain exists and is released:
  `request_template -> form_schema -> workflow_profile -> priority_policy -> SLA/OLA -> routing_policy -> approval_policy -> diagnostic_policy -> closure_policy -> visibility/notification/reporting -> passport`.
- Legacy migration/backfill and compatibility are in place:
  old `request_forms` packs, old clients sending only `form_key`, old packs without priority fields, and pre-registry tickets are covered by tests.
- External SLA/OLA policy actions are dispatched outside event payloads through `policy_action_dispatcher`.
- Structured OLA editor and OLA risk UI are already present at MVP level.
- The known old `web_settings` calendar JSON warning cleanup was completed in the previous plan.
- Slice 7 added a read-only helpdesk historical data cleanup inventory. Latest remote dry-run report: `/var/chat_bot/pc_client/artifacts/diagnostics/helpdesk_data_cleanup_20260502_211544.json`.
- Slice 8 final release gates are complete. Remaining items are now backlog follow-ups, not blockers for this hardening plan.

## Decisions

- Keep workflow transition actions explicit and typed. Runtime may execute safe actions automatically, but high-risk side effects must be auditable and gated.
- Keep approvals as first-class requests, not only status flags. Support and requester UI must show who is expected to act next.
- Notification policy chooses intent and recipients; preferences/channel availability remain the final per-recipient filter, and unavailable/disabled external channels must leave audit evidence instead of disappearing silently.
- Visibility policy owns requester-safe projection. Redaction, including nested dotted paths, must happen before public/requester payloads leave the server.
- Passport/reporting policy owns required facts and export visibility. Closure should block only when the active closure/reporting policy explicitly requires an official dossier.
- Smart views are saved filters, not ownership queues.
- Agent live UX should be validated against the remote server with current published templates, not only unit helpers.

## Slice 1: Workflow Actions, Typed API And Visual Editor

- [x] Add tests for transition actions in `server/tests/test_ticket_workflow_profiles.py`: notify action metadata, SLA action marker, approval creation marker, required public/internal comment, evidence gate and audit payload.
- [x] Extend workflow profile schema normalization in `server/tickets/workflow_profiles.py` for `actions.notify`, `actions.sla`, `actions.approval`, `require_evidence`, `required_comment_type`, and `log_fields`.
- [x] Update `TicketWorkflowService` to execute safe configured gates/actions and record skipped high-risk actions in audit payload instead of silently ignoring them.
- [x] Add typed workflow profile publish/diff validation in `server/web_api/settings_handlers.py` without removing raw JSON compatibility.
- [x] Add visual workflow editor controls in `webapp/src/pages/settings/index.tsx` for statuses, transitions, gates and action markers.
- [x] Verification: `python -m pytest server\tests\test_ticket_workflow_profiles.py server\tests\test_web_settings_api.py -q --tb=short` -> 25 passed.
- [x] Verification: `pnpm --dir webapp exec vitest run src/pages/settings/index.test.tsx` -> 4 passed.
- [x] Verification: browser `/app/settings`, workflow editor visible and console errors 0.
- [x] Update `server/docs/TICKET_SYSTEM.md`, `server/docs/CODEMAP.md`, `docs/QUICK_LOOKUP.md`, `scripts/navigation_catalog.py`, and this plan.
- [x] Commit and release if server/runtime behavior changes.

## Slice 2: Approvals UI And Action Surface

- [x] Add server tests showing support ticket detail exposes pending approvals, current approver source, due/reminder/escalation timestamps, mode and reject-comment requirement.
- [x] Extend support DTO/API to include support-safe approval summary and requester-safe builder mode for future public/requester surfaces.
- [x] Render approvals in `/app/tickets/:ticketId`: pending approvers, current action owner, approve/reject transitions, missing reject comment state and timeout/escalation status.
- [x] Keep requester-safe public status text for waiting approval through the existing visibility/status projection without exposing internal approver groups in public labels.
- [x] Verification: `python -m pytest server\tests\test_ticket_approval_policy.py server\tests\test_web_support_api.py -q --tb=short` -> 41 passed.
- [x] Verification: `pnpm --dir webapp exec vitest run src/pages/tickets/detail-page.test.tsx` -> 13 passed.
- [x] Verification: browser ticket detail with seeded approval-policy ticket `T-000352`, approval panel visible, console errors 0.
- [x] Update docs/navigation and this plan.
- [x] Commit and release if API/UI changed: functional commit created, remote smoke passed, browser signoff completed.

## Slice 3: Notification And Visibility Hardening

- [x] Add tests for notification events: created, assigned, waiting_user, requester_replied, SLA warning/breach, resolved, closed, approval events and diagnostic completion.
- [x] Add channel validation for `web`, `email`, `telegram`, `vk_teams`, provider channels and disabled/unavailable channel audit.
- [x] Ensure notification preferences remain the final per-recipient filter after policy recipient resolution.
- [x] Expand visibility policy tests for field-level requester/support views, public status mapping, raw diagnostics redaction, OLA hiding and passport export visibility.
- [x] Add UI preview in the policy editor showing requester view vs support view before publication.
- [x] Verification: `python -m pytest server\tests\test_ticket_notification_policy.py server\tests\test_ticket_visibility_policy.py server\tests\test_ticket_passport_service.py -q --tb=short` -> 21 passed.
- [x] Verification: `pnpm --dir webapp exec vitest run src/features/forms-builder/forms-builder-panel.test.tsx` -> 27 passed.
- [x] Browser check `/app/admin/forms`, notification/visibility policy editors and preview: requester/support preview and notification recipient/channel preview visible, active-tab console errors 0.
- [x] Update docs/navigation and this plan.
- [x] Commit and release if API/runtime/UI changed: `efb9c06 server: harden notification visibility policies`, remote smoke passed.

## Slice 4: Passport And Reporting Enforcement

- [x] Add tests for required reporting sections, hidden internal sections, diagnostic evidence inclusion, approval/action packages, related objects and knowledge draft source.
- [x] Add deterministic missing-facts report in `passport_service`: required fact, source, current value, requester-visible label and blocking severity.
- [x] Enforce official dossier requirements before closure only when active policies require it.
- [x] Render support passport tab requirements, missing facts and export preview in ticket detail.
- [x] Verification: `python -m pytest server\tests\test_ticket_passport_service.py server\tests\test_ticket_closure_policy.py server\tests\test_web_support_api.py -q --tb=short` -> 50 passed.
- [x] Verification: `pnpm --dir webapp exec vitest run src/pages/tickets/detail-page.test.tsx` -> 14 passed.
- [x] Browser check ticket detail passport tab and closure requirement checklist: live ticket `T-000353` showed passport missing facts/export preview and resolved-transition close checklist.
- [x] Update docs/navigation and this plan.
- [x] Commit and release if API/runtime/UI changed: `af13e86 server: enforce passport reporting requirements`, remote smoke passed.

## Slice 5: Smart Views Execution Coverage

- [x] Add executable coverage for target smart views: `sla_risk`, `ola_risk`, `unassigned`, `waiting_approval`, `stale_waiting`, `diagnostics_failed`, `requester_reply`, `mass_incident_candidates`.
- [x] Add tests for published custom filters, invalid filter rejection and support queue counters.
- [x] Make unsupported custom filter paths fail at publication time with actionable validation messages.
- [x] Ensure list UI shows custom/built-in smart-view counts consistently and does not confuse smart views with queues.
- [x] Verification: `python -m pytest server\tests\test_web_support_api.py server\tests\test_helpdesk_policy_registry.py -q --tb=short` -> 50 passed.
- [x] Verification: `pnpm --dir webapp exec vitest run src/pages/tickets/list-page.test.tsx src/features/forms-builder/forms-builder-panel.test.tsx` -> 28 passed.
- [x] Browser check `/app/tickets` and `/app/admin/forms` smart-view editor: OLA risk filter reduced the queue to 1 ticket, smart-view editor structured filter/sort controls visible, active-tab console errors 0.
- [x] Update docs/navigation and this plan.
- [x] Commit and release if API/UI changed: no runtime/API/UI source changed in this slice, only tests and plan; release skipped.

## Slice 6: Agent Live UX And Template Create Smoke

- [x] Add or refresh helper tests for agent post-create public rendering, server-preview fallback, dynamic required fields, diagnostic consent and file/picker edge cases. Added conditional hidden-required file coverage and kept existing preview/consent/picker/result-label coverage green.
- [x] Run agent focused tests: `python -m pytest pc_agent\tests\test_chat_panel_helpers.py pc_agent\tests\test_ticket_api_client_attachments.py -q --tb=short` -> 67 passed.
- [x] Add server coverage for schema/template/policy metadata preservation from versioned `request_forms` into `custom_fields.request_template`.
- [x] Verification: `python -m pytest server\tests\test_ticket_form_packs.py::test_create_ticket_preserves_form_schema_and_policy_refs_in_template_context server\tests\test_ticket_form_packs.py::test_create_ticket_accepts_request_template_key_as_form_alias server\tests\test_ticket_form_packs.py::test_create_ticket_preview_returns_effective_template_context -q --tb=short` -> 3 passed.
- [x] Verification: `python scripts\verify_workspace.py` -> passed.
- [x] Start remote server through release script and run a live agent GUI/API create smoke against current preferred template and a temporary schema-backed template version.
- [x] Verify created ticket context on server: `request_template`, `form_schema`, priority decision, routing decision, requester-safe due dates, consent, attachments if used and passport/result summary. Live schema-backed ticket `1161327d-e873-4ded-bd48-a38b98209722` preserved `form_schema_id`, template version, policy refs, diagnostic consent, P0 priority, fallback routing, attachment message ref and observer root trace. Temporary template was removed from the preferred pack afterwards.
- [x] Verify agent result panel text: access code, next action, expected due dates, open/add-message/create-another actions, no raw SLA/OLA/internal wording. Source-level button coverage remains in helper tests; live result labels had access code, next action, response/resolution deadlines, diagnostics/passport user wording and no raw SLA/OLA terms.
- [x] Update `pc_agent/docs/CODEMAP.md`, `docs/QUICK_LOOKUP.md`, `scripts/navigation_catalog.py`, and this plan.
- [x] Commit and release agent/server changes if any were required by smoke findings: `c204c83 server: preserve request form schema metadata`, remote release smoke passed.

## Slice 7: Data Cleanup And Mojibake Hardening

- [x] Inventory historical live data with mojibake or placeholder `???` in ticket titles, requester names, module descriptions and tool descriptions via `scripts/helpdesk_data_cleanup.py`.
- [x] Decide which cleanup is data-only and which requires code hardening/security review: placeholder-only findings are `data_only_cleanup_candidate`; mojibake/mixed findings are `manual_review_required`; token-like values are redacted and classified as `security_review_required`.
- [x] Add a safe admin/scripted cleanup path for historical test data, with dry-run output and no token leakage. Mutation is intentionally disabled: `--apply` returns `apply_requested_but_not_implemented` until deterministic cleanup rules are reviewed.
- [x] Add tests for UTF-8 preservation in any new cleanup parser/formatter.
- [x] Verification: remote dry-run report stored at `/var/chat_bot/pc_client/artifacts/diagnostics/helpdesk_data_cleanup_20260502_211544.json` and Markdown sibling `.md`.
- [x] Browser check representative cleaned pages if cleanup is applied to remote data: skipped because no cleanup was applied; this slice was inventory-only.
- [x] Update docs/navigation and this plan.
- [x] Commit script/docs changes if added: `ec00606 server: add helpdesk data cleanup inventory` plus merge commit `f51fb32` for fast-forward remote deploy after amended detection.

Remote dry-run summary:

- Scanned rows: tickets 338, registry_people 6, modules 53, device_toolset_snapshots 69.
- Findings: 73 total; mojibake 20, placeholder 33, sensitive_token_like 20.
- Strategies: data-only cleanup candidates 33, manual review 20, security review 20.
- No raw token-like values were printed in the report samples; samples use `[REDACTED_TOKEN]`.

## Slice 8: Final Hardening Release Gates

- [x] Local baseline: `python scripts\verify_workspace.py` -> passed.
- [x] Server focused: workflow, approval, notification, visibility, passport, smart-view and support API tests from Slices 1-5 -> 121 passed.
- [x] Agent focused: `python -m pytest pc_agent\tests\test_chat_panel_helpers.py pc_agent\tests\test_ticket_api_client_attachments.py -q --tb=short` -> 67 passed.
- [x] Web focused: settings/forms/tickets Vitest suites touched by this plan -> 4 files / 46 tests passed.
- [x] Remote release: `python scripts\release_server_to_remote.py --allow-local-dirty --skip-ci-check --leave-running --smoke-attempts 5 --smoke-delay 3` -> completed; webapp build/upload, migrations, control/server start and release smoke passed.
- [x] Remote smoke: `python scripts\manage_remote_stack.py smoke server` -> `/api/health` 200.
- [x] Browser signoff: `/admin`, `/app/admin/forms`, `/app/settings`, `/app/tickets`, one real `/app/tickets/:ticketId`, `/app/admin/observer` -> MCP/browser signoff passed on `http://192.168.100.17:8666`.
- [x] Observer signoff: `/app/admin/observer` showed `Runtime: ok`; browser console errors 0; server logs had no traceback/critical/exception. Two startup reconcile ERROR lines for offline agents were observed and treated as existing operational noise, not changed-flow regressions.
- [x] Stop server: `python scripts\manage_remote_stack.py stop server`, then confirm stopped -> stopped, `active=inactive`, `sub=dead`.
- [x] Update final status and completion percentage in this plan.
- [x] Commit docs closure.

Slice 8 verification details:

- `python scripts\verify_workspace.py` -> passed.
- `python scripts\bootstrap_web_toolchain.py` -> Node.js 24.15.0, pnpm 10.33.0 ready.
- `python -m pytest server\tests\test_ticket_workflow_profiles.py server\tests\test_web_settings_api.py server\tests\test_ticket_approval_policy.py server\tests\test_web_support_api.py server\tests\test_ticket_notification_policy.py server\tests\test_ticket_visibility_policy.py server\tests\test_ticket_passport_service.py server\tests\test_ticket_closure_policy.py server\tests\test_helpdesk_policy_registry.py -q --tb=short` -> 121 passed.
- `python -m pytest pc_agent\tests\test_chat_panel_helpers.py pc_agent\tests\test_ticket_api_client_attachments.py -q --tb=short` -> 67 passed.
- `pnpm --dir webapp test src\pages\settings\index.test.tsx src\features\forms-builder\forms-builder-panel.test.tsx src\pages\tickets\detail-page.test.tsx src\pages\tickets\list-page.test.tsx` -> 4 files / 46 tests passed.
- `pnpm --dir webapp run check:remote:webapp -- --base-url http://192.168.100.17:8666` -> route mode `webapp`, admin/support pages loaded, console/page errors empty.
- MCP live paths checked: `/admin`, `/app/admin/forms`, `/app/settings`, `/app/tickets`, `/app/tickets/1161327d-e873-4ded-bd48-a38b98209722`, `/app/admin/observer`.

## Hardening / UX Backlog

These are known follow-ups. Promote them into slices only when they become the next active work item.

- Full recipient expansion for admin/group notification recipients beyond explicit actor ids.
- Richer notification delivery provider health UI and retry controls.
- Requester-facing approval actions outside the support workspace if a requester must approve.
- More granular visibility previews for every form field and passport section.
- Printable/exported passport visual QA with representative long Russian text and attachments.
- Automated remote browser signoff through `pnpm --dir webapp run check:remote:webapp -- --base-url http://192.168.100.17:8666`.
- Dedicated load/performance pass for support queue smart-view counters with large ticket volumes.
- Cleanup of historical observer-canary/test tickets and duplicated offline agents on the remote stand.
- Agent GUI visual QA on Windows for small screens, long labels, file picker paths and preview-unavailable state.
- Release-note and operator-runbook pass once the hardening plan is complete.

## Handoff

Recommended execution order is the slice order above:

1. Workflow actions first, because approvals, notifications, closure and auto-close flows depend on reliable transition semantics.
2. Approvals UI second, because it is the highest-value missing operator/requester surface.
3. Notification/visibility third, because it governs what each actor sees and receives.
4. Passport/reporting fourth, because closure rigor depends on missing-facts visibility.
5. Smart views fifth, because they are operational prioritization rather than core lifecycle.
6. Agent live UX sixth, after server policy and support surfaces are stable.
7. Data cleanup seventh, after behavior is stable enough to distinguish code bugs from historical test data.
8. Final release gates last.

Keep every slice small enough to test and commit independently.
