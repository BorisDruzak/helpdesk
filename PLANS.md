# PLANS.md

## 2026-04-30 Help Desk Settings: Functional Policy Model

Status: slice 4 implemented, verified locally, deployed and live-checked on the Linux stand. Scope is functional backend/domain behavior first; visual redesign is intentionally out of scope for this plan.

### Goal

Bring the existing help desk settings model closer to the target chain:

```text
request_template
  -> form_schema
  -> workflow_profile
  -> priority_policy
  -> sla_policy / ola_policy
  -> routing_policy
  -> approval_policy
  -> diagnostic_policy
  -> closure_policy
  -> reporting / solution passport
```

The first implementation path must reuse what already exists, enforce stored policies where they are currently passive metadata, and keep every slice testable.

### Current Functional State

Already present:

- Request-template-like catalog exists as the `request_forms` form pack in `ticket_form_packs`.
- Form validation supports fields, required flags, options and conditional visibility.
- Template context is preserved in `custom_fields.request_template`, including `ticket_type`, category/service/subcategory, queue, SLA, priority/routing/approval/OLA/closure/visibility policies, field roles and suggested playbook.
- Workflow profiles exist and status transitions use the configured profile for `ticket_type`.
- Priority policy exists for intake facts and stores computed/effective priority context.
- SLA and OLA services exist, but SLA due dates still need calendar-aware calculation.
- Routing exists through global rules, executable template-level `routing_policy`, template fallback queue and global fallback queue.
- Diagnostics/playbooks are separate operations, not ticket statuses.
- Resolution passport tables and services exist.

Missing or weak:

- No standalone persisted entities yet for `request_templates`, `form_schemas`, `priority_policies`, `routing_policies`, `approval_policies`, `closure_policies`, `diagnostic_policies`, `notification_policies`, `visibility_policies` and `smart_views`.
- `closure_policy`, `approval_policy` and `routing_policy` are executable; `visibility_policy` is still mostly saved as template metadata.
- Workflow transitions do not yet enforce per-transition roles, required fields, guards and actions beyond the profile transition map.
- SLA does not yet use the business calendar engine for due date calculation.
- Notification rules are not policy-driven.
- Smart views are not first-class saved settings.

### Decisions

- Keep the first storage layer on top of the existing `request_forms` / request-template metadata. Do not add migrations until behavior proves the split.
- Make stored policies executable one by one, starting with the lowest-risk policy that is already in template metadata.
- Use focused backend tests before implementation for each slice.
- Do not start the request-template visual builder until backend contracts and enforcement are stable.
- Live verification is required after local tests for slices that affect server behavior.

### Execution Plan

1. Executable `closure_policy`.
   - Enforce `require_resolution_code`.
   - Enforce `require_public_summary`.
   - Enforce evidence requirements for configured priorities.
   - Apply through ticket workflow/API status changes.
   - Verify with focused workflow tests and live status-change smoke.

2. Executable `approval_policy`.
   - Enforce required approval for access/change templates.
   - Support approver source metadata already present in template context.
   - Block workflow transitions when approval evidence is missing.

3. Calendar-aware SLA.
   - Route SLA target calculation through the existing calendar engine.
   - Preserve current SLA target configuration and event semantics.
   - Add tests for working hours, pauses, resume and stop conditions.

4. Workflow transition gates.
   - Add required fields per transition.
   - Add role checks beyond support/requester split where profile data provides them.
   - Return blocked transition reasons for API/UI consumers.

5. Routing policy actions.
   - Execute template-level routing rules in addition to global routing rules.
   - Support queue, assignee, priority boost, SLA/OLA override, tags/watchers and playbook suggestion where existing models allow it.
   - Add loop/lock protections.

6. Diagnostic policy and evidence/passport binding.
   - Make diagnostic policy decide suggested playbooks, consent, attach-to-passport and evidence behavior.
   - Keep `ticket.status` independent from operation status.

7. Visibility, notifications and smart views.
   - Execute public status mapping and requester/support field visibility.
   - Move notification rules toward configurable policy.
   - Add saved operational views such as SLA risk, OLA risk, waiting approval and diagnostics failed.

8. Request-template builder and admin settings UI.
   - Only after backend behavior is stable.
   - Use existing form builder as the base.
   - Add tabs for basic, classification, form, workflow, priority, routing, SLA/OLA, approvals, diagnostics and closure.

9. Release and live verification.
   - Run local verification first.
   - Commit verified state.
   - Deploy through project scripts only.
   - Run remote smoke/live checks.
   - Stop remote server after checks unless the user explicitly asks to leave it running.

### Current Step

Slice 4 implemented locally: executable request-template `routing_policy`.

Implemented behavior:

- `TicketRoutingService` evaluates `custom_fields.request_template.routing_policy.rules` before global `ticket_routing_rules`.
- Rules are first-match by `priority_order` and support `when` / `condition` / `condition_json` using the existing condition evaluator over ticket, template and form facts.
- Actions support `queue_id` / `queue_code`, `assignee_id`, `priority_boost` / `increase_priority_by`, `minimum_priority`, `sla_policy_id`, `approval_policy`, `suggested_playbook_id`, `tags`, plus persisted decision metadata for OLA/watchers/visibility.
- `routing_policy.fallback.queue_id` and `routing_policy.default_queue_id` are evaluated before the old `request_template.default_queue_id` and global `servicedesk_l1` fallback.
- Loop/lock protections include existing manual `routing_lock`, `do_not_reroute_if_assignee_locked` and `max_auto_reroutes`.
- `routing_applied` events now include `routing_source`, matched rule metadata and actions; `queue_changed` remains emitted only when queue changes.

Changed files for slice 4:

- `server/tickets/routing_service.py`
- `server/app/repos/ticket_events_repo.py`
- `server/tests/test_ticket_routing_policy.py`

Previous current step:

Slice 3 implemented locally: calendar-aware SLA due dates.

Implemented behavior:

- `TicketSlaService.start_sla`, `on_reopen` and priority recalculation use `calendar_engine.add_business_minutes` when the SLA policy has `calendar_id` or business-hours config.
- SLA without calendar keeps 24x7 fallback behavior.
- `calendar_engine.add_business_minutes` now moves from a non-working time to the next work interval start before consuming remaining minutes.
- Calendar due-date calculation consumes seconds internally, so live `now()` values near the end of a work interval cannot stall on a zero-minute segment.

Slice 2 implemented and live-verified: executable `approval_policy`.

Implemented behavior:

- A ticket with `request_template.approval_policy.required=true` can move into `waiting_on_approval` without prior approval evidence.
- The same ticket cannot move from approval wait into execution statuses without an approved `ticket_approvals` row.
- A rejected approval blocks execution transitions.
- An approved approval allows the configured workflow transition.
- Typed support status actions return `APPROVAL_POLICY_BLOCKED` for approval-policy blocks while keeping `CLOSURE_POLICY_BLOCKED` for closure-policy blocks.

Slice 1 already implemented and live-verified: executable `closure_policy`.

Implemented behavior:

- A ticket with `request_template.closure_policy.require_resolution_code=true` cannot move to `resolved` without a resolution code.
- A ticket with `request_template.closure_policy.require_public_summary=true` cannot move to `resolved` without a public summary.
- A high-priority ticket with evidence required by closure policy cannot move to `resolved` without evidence.
- The same ticket can move to `resolved` after required code, summary and evidence are provided.
- `resolution_summary` and `requester_resolution_summary` are accepted by workflow status transitions and typed support/API status routes.
- Policy blocks return a controlled validation/API error instead of silently resolving.

Changed files:

- `server/tickets/closure_policy.py`
- `server/tickets/workflow_service.py`
- `server/tickets/handlers.py`
- `server/web_api/support_handlers.py`
- `server/tests/test_ticket_closure_policy.py`
- `server/tests/test_ticket_approval_policy.py`
- `server/tickets/approval_policy.py`
- `server/docs/CODEMAP.md`
- `docs/QUICK_LOOKUP.md`
- `server/docs/TICKET_SYSTEM.md`
- `scripts/navigation_catalog.py`
- `server/tickets/sla_service.py`
- `server/tickets/calendar_engine.py`
- `server/tests/test_ticket_sla_calendar.py`
- `server/tickets/routing_service.py`
- `server/app/repos/ticket_events_repo.py`
- `server/tests/test_ticket_routing_policy.py`

### Verification Plan

Local:

- `python -m pytest server/tests/test_ticket_closure_policy.py -q` -> passed, 4 tests.
- `python -m pytest server/tests/test_ticket_closure_policy.py server/tests/test_ticket_workflow_profiles.py server/tests/test_ticket_form_packs.py server/tests/test_web_support_api.py::test_web_support_status_action_returns_typed_result_and_updates_ticket -q` -> passed, 24 tests.
- `python -m pytest server/tests/test_ticket_approval_policy.py -q` -> passed, 4 tests.
- `python -m pytest server/tests/test_ticket_approval_policy.py server/tests/test_ticket_closure_policy.py server/tests/test_ticket_workflow_profiles.py server/tests/test_ticket_form_packs.py server/tests/test_web_support_api.py::test_web_support_status_action_returns_typed_result_and_updates_ticket -q` -> passed, 28 tests.
- `python -m pytest server/tests/test_ticket_sla_calendar.py -q` -> passed, 1 test.
- `python -m pytest server/tests/test_ticket_sla_calendar.py server/tests/test_ticket_priority_policy.py server/tests/test_ticket_queue_routing_contracts.py::test_create_ticket_applies_sla_and_ola_configuration server/tests/test_ticket_approval_policy.py server/tests/test_ticket_closure_policy.py -q` -> passed, 12 tests.
- After the sub-minute calendar edge-case regression test was added: `python -m pytest server/tests/test_ticket_sla_calendar.py server/tests/test_ticket_priority_policy.py server/tests/test_ticket_queue_routing_contracts.py::test_create_ticket_applies_sla_and_ola_configuration server/tests/test_ticket_approval_policy.py server/tests/test_ticket_closure_policy.py -q` -> passed, 13 tests.
- `python -m pytest server/tests/test_ticket_routing_policy.py -q` -> passed, 5 tests.
- `python -m pytest server/tests/test_ticket_routing_policy.py server/tests/test_ticket_queue_routing_contracts.py server/tests/test_ticket_priority_policy.py server/tests/test_ticket_sla_calendar.py server/tests/test_ticket_approval_policy.py server/tests/test_ticket_closure_policy.py -q` -> passed, 28 tests.
- `python -m pytest server/tests/test_web_admin_api.py::test_web_admin_forms_save_accepts_request_template_process_context server/tests/test_web_admin_api.py::test_web_admin_forms_route_preview_returns_typed_payload server/tests/test_web_settings_api.py::test_web_settings_returns_aggregated_real_payload server/tests/test_ticket_form_packs.py::test_validate_form_pack_schema_preserves_request_template_process_context -q` -> passed, 4 tests.
- `python scripts/verify_workspace.py` -> passed.

Live:

- Released commit `f7bdac3` with `python scripts/release_server_to_remote.py --allow-local-dirty --skip-ci-check --leave-running`.
- Remote smoke passed: `GET /api/health` -> 200.
- Live routing-policy check created ticket `8fa40e76-20d3-4910-97c1-9e1c0a587205` through `create_ticket_with_side_effects` using a temporary request template.
- Template `routing_policy.rules[0]` matched `request_form_data.affected_scope = whole_building` and routed the ticket to queue `25` (`live_route_c9df660c27`).
- Ticket stored `custom_fields.routing_decision.source = request_template.routing_policy`, matched rule `priority_order = 10`, `suggested_playbook_id = diagnose.network.basic`, tag `live-routing-policy` and priority boost result `priority = P3`.
- `ticket_events` included `routing_applied` and `queue_changed` for the live ticket.
- Final remote status/smoke passed, then server was stopped: `active=inactive`.

Previous SLA-calendar live check:

- Released commit `1ed5847` with `python scripts/release_server_to_remote.py --allow-local-dirty --skip-ci-check --leave-running`.
- Remote smoke passed: `GET /api/health` -> 200.
- Live runtime SLA check created ticket `2c83384f-7eee-4b72-a4bd-21f5f6f830dd` with temporary calendar `live_sla_623631d545`.
- Test calendar window was `2026-04-30 07:07-07:11 UTC`; `now_utc` was `2026-04-30T07:08:06.790452+00:00`.
- `first_response_due_at` was `2026-04-30T07:09:06.859330+00:00`.
- `resolution_due_at` was `2026-05-01T09:07:07+00:00`, later than naive 24x7 `2026-04-30T07:18:06.790452+00:00`, proving the SLA used the business calendar.
- Final remote status/smoke passed, then server was stopped: `active=inactive`.

Previous approval-policy live check:

- Released commit `e587d7c` with `python scripts/release_server_to_remote.py --allow-local-dirty --skip-ci-check --leave-running`.
- Remote smoke passed: `GET /api/health` -> 200.
- Live API login as support `op1` succeeded.
- Created live verification ticket `051c5ea7-b55f-4e0c-90bc-97628e237e56` with `request_template.approval_policy`.
- Transition to `in_progress` without approval returned HTTP 400 with `APPROVAL_POLICY_BLOCKED` and `approval_policy requires approved approval`.
- After adding approved `ticket_approvals` row, transition to `in_progress` returned HTTP 200 and ticket status became `in_progress`.
- Final remote status/smoke passed, then server was stopped: `active=inactive`.

Previous closure-policy live check:

- Released commit `248e276` with `python scripts/release_server_to_remote.py --allow-local-dirty --skip-ci-check --leave-running`.
- Remote smoke passed: `GET /api/health` -> 200.
- Live API login as support `op1` succeeded.
- Created live verification ticket `9bcc445d-3855-4167-a5f2-1e353df2b48a` with `request_template.closure_policy`.
- Resolve without public summary returned HTTP 400 with `CLOSURE_POLICY_BLOCKED` and `closure_policy requires resolution_summary`.
- After adding evidence and `resolution_summary`, resolve returned HTTP 200 and ticket status became `resolved`.
- Final remote status/smoke passed, then server was stopped: `active=inactive`.

### Handoff

Next immediate action:

1. Continue with workflow transition gates: required fields and role checks beyond the current transition map.
2. Start with failing tests around `workflow_profile.transitions[*].required_fields` and `allowed_roles`.
3. Keep routing/priority/SLA/approval/closure regression tests in the verification set.
