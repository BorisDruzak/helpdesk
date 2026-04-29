# PLANS.md

## 2026-04-29 Help Desk Process Model Completion Slice

Status: second slice in progress: server-driven priority questions, agent SLA display and ticket passport completeness added locally; live verification pending.

### Goal

Close the gap called out after the first process-model slice:

- expose the full future service-desk model in server UI settings;
- run and lock an acceptance route for `request_template -> ticket_type/workflow_profile -> priority -> routing -> SLA/OLA -> ticket observer summary -> observer trace/detail`;
- update the local agent ticket creation path so it sends structured priority facts, not only the old `urgency`/`importance` booleans.

### Implemented Changes

- `GET /api/web/settings.ticket_settings` now exposes:
  - `process_schema` for the complete service-desk chain;
  - read-only planned support lines `L1`, `L2`, `L3`;
  - `priority_model` showing impact/urgency/importance/modifiers and that users do not directly pick P0/P1/P2/P3.
- `/app/settings` → `Тикеты` renders:
  - `Схема service desk`;
  - workflow profiles;
  - priority model;
  - support lines.
- Settings priority/SLA controls now use process priorities `P0`, `P1`, `P2`, `P3`.
- OLA settings now accept process priority `P0` while retaining legacy `P4` compatibility.
- `server/tickets/form_catalog.py` now preserves priority-policy fact keys from submitted payload even if they are helper facts not rendered as visible fields.
- `server/tickets/routing_service.py` now applies `request_template.default_queue_id` after explicit routing rules and before `servicedesk_l1` fallback.
- `pc_agent/ui_gui/chat_panel.py` now:
  - keeps `ticket_type` from form templates;
  - gives default local forms `ticket_type` and `priority_policy`;
  - collects `impact_scope`, `work_continuity`, `business_importance`;
  - renders server-driven priority fields from the selected request template when the form builder defines them;
  - keeps the old fixed priority questions only as a legacy fallback for old packs;
  - merges those facts into `form_payload`;
  - shows server-calculated SLA first-response and resolution/workaround deadlines in ticket metadata and create-success text;
  - keeps legacy `urgency`/`importance` booleans for server compatibility.
- `server/tickets/form_catalog.py` now attaches editable priority question fields and `field_roles` to the built-in request templates.
- `/app/admin/forms` now lets admins add the standard priority question set to a request template and edit field roles (`routing_field`, `priority_field`, `sla_field`, `approval_field`, `diagnostic_input`, `closure_evidence`, `display_only`) in the field constructor.
- `/app/tickets/:ticketId` operational card now derives the seven-question passport from richer request-form keys, SLA/deadline fields and timeline/operation evidence, and shows `Passport X/7` completeness.
- Added acceptance test `server/tests/test_helpdesk_process_observer_route.py`.

### Verification So Far

- `python -m pytest server\tests\test_web_settings_api.py server\tests\test_helpdesk_process_observer_route.py server\tests\test_ticket_form_packs.py server\tests\test_ticket_priority_policy.py -q` -> 22 passed.
- `python -m pytest pc_agent\tests\test_chat_panel_helpers.py -q` -> 25 passed.
- `pnpm --dir webapp run test -- src/pages/settings/index.test.tsx --run` -> 3 passed.
- 2026-04-29 second slice:
  - `python -m pytest pc_agent/tests/test_chat_panel_helpers.py -q` -> 28 passed.
  - `python -m pytest server/tests/test_ticket_form_packs.py server/tests/test_helpdesk_process_observer_route.py -q` -> 13 passed.
  - `pnpm --dir webapp test -- forms-builder-panel detail-page` -> 20 passed.
  - `pnpm --dir webapp exec tsc --noEmit` -> passed.
- Live `/app/settings` check confirms the service desk schema, workflow profiles, priority model, support lines, statuses and `next_action_owner` are visible.
- Live route check created ticket `T-000315`: request template `site_system` -> `ticket_type=incident` -> `effective_priority=P0` -> queue routing -> SLA -> observer summary -> trace detail.
- Live OLA route found and fixed a backend validation gap: OLA target PUT still rejected `P0`.

### Remaining Verification

- re-run focused and full verification after the OLA validation fix;
- commit/deploy the OLA validation fix;
- live route check with non-null OLA;
- stop remote server after checks.

## 2026-04-29 Help Desk Process Model, Request Templates, Priority And SLA

Status: in progress. Core backend/UI slice implemented and under verification.

### Goal

Turn the current ticket/form/routing system into a process-driven service desk model where a user-facing request template produces process context, `ticket_type` selects a workflow profile, priority is calculated from facts, SLA/OLA are based on the effective priority, and the operator ticket card answers the seven operational questions:

1. What happened?
2. Who is affected?
3. Where did it happen?
4. What object/service is affected?
5. Who must act now?
6. What is the deadline?
7. What has already been checked or done?

### Scope

In scope:

- Request template model on top of the existing `request_forms` form pack.
- Separation of four layers:
  - process type: `ticket_type`;
  - category / service / subcategory;
  - form fields and conditional fields;
  - routing / SLA / OLA / workflow / approval / diagnostics / closure policies.
- Minimal workflow profiles:
  - `incident`;
  - `service_request`;
  - `access_request`;
  - `change_request`;
  - `consultation`.
- Configurable workflow foundation, initially backed by code-defined profiles plus typed server/API/UI contracts that can later move to DB-backed editing.
- Form builder upgrade into a request template builder with tabs:
  - Basic;
  - Classification;
  - Form fields;
  - Conditions;
  - Priority;
  - Routing;
  - SLA / OLA;
  - Approvals;
  - Diagnostics / modules;
  - Closure.
- Priority model based on user facts:
  - impact;
  - urgency;
  - importance / business criticality;
  - modifiers;
  - computed priority;
  - manual override;
  - effective priority.
- Priority settings and SLA settings in the React server UI.
- Ticket creation flow that derives process context from request templates.
- Support ticket card/detail improvements for the seven operational questions.
- Audit trail for priority calculation, priority overrides, workflow profile decisions, routing, SLA recalculation, OLA changes and closure evidence.
- Documentation and tests for the new contract.

Out of scope for this plan:

- Separate `support_line` / L1 / L2 / L3 entity and support-level escalation model. Support level stays modeled through queues, members, diagnostics and evidence for now.
- Full AI automation. AI can be planned as suggestion-only metadata after the deterministic process model is in place.
- Replacing legacy `/admin` and `/support` shells. New work targets typed `/app/*` surfaces first; legacy remains compatibility/rollback.
- External integrations with Zendesk, Jira Service Management, Freshservice or other SaaS products.

### Current State

Relevant current implementation:

- `tickets.ticket_type` exists and is stored on tickets, but it currently behaves mostly as classification/routing context, not as a workflow selector.
- `server/tickets/routing_service.py` already builds routing context from `ticket_type`, `request_kind`, `category_id`, `service_id`, `subcategory_id`, requester profile, device metadata and `request_form_data`.
- `server/tickets/workflow_service.py` has one global FSM for all ticket types.
- `server/tickets/form_catalog.py` stores forms with `key`, `request_kind`, fields and playbook triggers in the `request_forms` pack.
- `/app/admin/forms` edits the form pack through `webapp/src/features/forms-builder/forms-builder-panel.tsx`.
- `/app/settings` already exposes queues, routing, SLA policies, priority matrix and OLA targets through `server/web_api/settings_handlers.py` and `webapp/src/pages/settings/index.tsx`.
- Priority currently uses `urgency + importance -> P0..P3`, with legacy `tickets.priority` used for SLA target lookup.
- `impact`, `urgency` and `importance` columns already exist on `tickets`, but their current semantics are not the full impact/urgency/criticality model described here.
- OLA exists as queue-level `ack_min` and `processing_min` targets.
- Ticket detail already shows status, next action owner, request form data, device context, tools, playbooks, passport and knowledge draft actions.

### Core Decisions

1. The existing form pack becomes the first implementation of `request_template`.
   - Do not introduce a separate table in the first slice unless JSON pack versioning blocks required behavior.
   - Rename the UI concept from "form" to "request template" where the admin is configuring process behavior.
   - Keep API compatibility by accepting existing form pack shape and defaulting new fields.

2. `ticket_type` becomes the process selector.
   - `request_kind` remains catalog/request analytics identity.
   - `form.key` remains the public template key.
   - `ticket_type` is no longer derived blindly from `request_kind`.
   - Template examples:
     - "Не открывается сайт": `ticket_type=incident`, `category=network`, `subcategory=website_unavailable`.
     - "Нужен доступ": `ticket_type=access_request`, `category=access`, `subcategory=grant_access`.

3. Workflow profiles start as server-owned definitions.
   - Use a code registry first: deterministic, testable, minimal migration risk.
   - Expose profiles through typed settings/forms APIs so UI can bind to them.
   - Store selected profile on the ticket through `ticket_type`.
   - Add DB-backed configurability later by preserving a serializable profile shape.

4. Priority is calculated from facts, not chosen directly by users.
   - Users answer business questions.
   - System computes `computed_priority`.
   - Staff can override to `manual_priority` with mandatory reason.
   - SLA uses `effective_priority`.
   - Existing `tickets.priority` remains the legacy SLA lookup field until all SLA code is migrated to P0..P3 directly.

5. SLA is selected by effective priority and policy.
   - SLA target lookup should use the ticket's effective priority mapping.
   - P0/P1 targets can mean "restore service or provide official workaround", not always permanent root-cause fix.

6. OLA stays queue-level for now.
   - OLA starts when queue ownership begins.
   - OLA ack closes on accepted assignment or equivalent acknowledgement.
   - OLA processing closes on queue handoff, resolution or closure.
   - No separate support-line model in this plan.

7. The operator card is an operational summary, not just a status panel.
   - It must summarize classification, affected object, location, action owner, deadline, evidence and performed diagnostics.
   - Data should come from normalized server DTOs, not duplicated frontend inference where possible.

8. AI remains advisory.
   - AI can suggest classification, similar tickets and resolution summary.
   - AI must not silently set priority, routing, workflow or closure facts without audit and human/system rule ownership.

### Target Domain Model

#### Request Template

First implementation: extend the existing form object inside `request_forms`.

Target shape:

```yaml
request_template:
  key: website_unavailable
  public_title: Не открывается сайт
  internal_name: Website unavailable incident
  description: Сайт не открывается или возвращает ошибку
  active: true
  audience: all_users
  ticket_type: incident
  request_kind: website_unavailable
  category_id: network
  service_id: optional
  subcategory_id: website_unavailable
  form_schema:
    fields: [...]
  form_conditions: [...]
  field_roles:
    affected_scope: [priority_field, routing_field]
    workaround_available: [priority_field, sla_field]
    url: [routing_field, diagnostic_input]
    screenshot: [closure_evidence]
  priority_policy:
    policy_id: default_incident_priority
    impact_field: affected_scope
    urgency_field: work_blocked
    importance_sources: [service_criticality, deadline]
    modifiers: [...]
  routing_policy:
    default_queue_id: servicedesk_l1
    rules: [...]
    diagnostic_reroute_rules: [...]
  sla_policy_id: incident_default
  ola_policy:
    use_queue_targets: true
  approval_policy:
    required: false
  suggested_playbook_id: diagnose.website
  closure_policy:
    require_resolution_code: true
    require_public_summary: true
    require_diagnostic_evidence_for_priorities: [P0, P1]
  visibility_policy:
    requester_fields: [...]
    operator_fields: [...]
```

#### Workflow Profile

Initial code-defined profile shape:

```yaml
workflow_profile:
  ticket_type: incident
  label: Инцидент
  purpose: Restore service as quickly as possible
  statuses:
    - new
    - queued
    - assigned
    - in_progress
    - waiting_on_user
    - waiting_on_internal_team
    - waiting_on_vendor
    - resolved
    - closed
    - canceled
  required_fields:
    create: []
    resolve: [resolution_code, public_summary]
  gates:
    evidence_required_for_priorities: [P0, P1]
  suggested_status_path:
    - new
    - queued
    - in_progress
    - resolved
    - closed
```

Minimal profiles:

| ticket_type | Purpose | Default path | Required process facts |
|---|---|---|---|
| `incident` | Restore work/service quickly | `new -> queued -> in_progress -> resolved -> closed` | affected object, impact, urgency, workaround, diagnostics for P0/P1 |
| `service_request` | Fulfil a standard service | `new -> queued -> assigned -> in_progress -> resolved -> closed` | requested service, requester, target device/user, fulfilment notes |
| `access_request` | Collect data, approve, grant access | `new -> waiting_on_approval -> queued/assigned -> in_progress -> resolved -> closed` | system, role, target user, justification, approver, approval evidence, action log |
| `change_request` | Plan, approve, schedule, execute, verify | `new -> waiting_on_approval -> scheduled -> in_progress -> resolved -> closed` initially; later add explicit `verification` status | change plan, work window, risk, rollback plan, approver |
| `consultation` | Answer/instruct and close | `new -> queued -> in_progress -> resolved -> closed` | question, answer/public summary |

Note: current canonical statuses do not include `verification`. First implementation should not add it unless tests show it is low risk. For `change_request`, use `resolved` as "verification requested" plus closure evidence initially, or plan a later migration for `verification`.

#### Priority Model

User-facing inputs:

- Impact question: "Кого затронула проблема?"
  - only_me;
  - several_people;
  - department;
  - building_or_org;
  - critical_system.
- Urgency question: "Можно ли продолжать работу?"
  - work_stopped_no_workaround;
  - partial_work;
  - workaround_available;
  - inconvenience_only.
- Importance / criticality:
  - service criticality from registry/service catalog;
  - deadline today/tomorrow;
  - public service / citizen reception affected;
  - security category;
  - reporting period.

Base matrix:

| Impact \ Urgency | Work stopped | Strongly degraded | Workaround exists | Inconvenience |
|---|---|---|---|---|
| High: organization/building/critical system | P0 | P1 | P2 | P2 |
| Medium: department/group | P1 | P1 | P2 | P3 |
| Low: one user | P2 | P2 | P3 | P3 |
| Minimal: question/no work disruption | P3 | P3 | P3 | P3 |

Modifiers:

| Condition | Effect |
|---|---|
| critical service affected | raise one level |
| reporting deadline today/tomorrow | raise one level |
| several similar tickets in short period | raise to P1/P0 depending on count and object |
| security category | minimum P1 or security-specific policy |
| confirmed outage from diagnostics | raise one level or to configured floor |
| public service/citizen reception affected | raise one level |
| workaround exists | lower urgency before matrix calculation |
| cosmetic/planned/non-blocking request | cap at P3 unless staff override |

Required priority audit fields:

```yaml
priority:
  impact
  urgency
  importance
  computed_priority
  manual_priority
  effective_priority
  priority_source: system | user_input | support_override | admin_override | ai_suggestion
  priority_reason
  priority_changed_by
  priority_changed_at
  priority_context_json
```

Implementation detail:

- Keep current `tickets.priority` as the legacy SLA priority field during transition.
- Add explicit P0..P3 fields for `computed_priority`, `manual_priority`, `effective_priority`.
- Provide mapping:
  - P0 -> legacy P1;
  - P1 -> legacy P2;
  - P2 -> legacy P3;
  - P3 -> legacy P4.

### Target UI Model

#### Request Template Builder Tabs

1. Basic
   - public title;
   - internal name;
   - description;
   - active flag;
   - audience.

2. Classification
   - `ticket_type`;
   - category;
   - service;
   - subcategory;
   - request kind.

3. Form Fields
   - field key;
   - label;
   - type;
   - required flag;
   - placeholder/help text;
   - default value;
   - validation;
   - options.

4. Conditions
   - if field X equals/in Y, show field Z;
   - if answer requires more detail, make field required;
   - if selected system is critical, show urgency/deadline block.

5. Priority
   - select fields that map to impact;
   - select fields that map to urgency;
   - select importance sources;
   - configure modifiers;
   - preview computed priority from sample answers;
   - never expose P0/P1/P2/P3 to requester.

6. Routing
   - default queue;
   - fallback queue;
   - routing rules;
   - route preview;
   - diagnostic reroute rules.

7. SLA / OLA
   - SLA policy;
   - SLA targets by effective priority;
   - business calendar;
   - OLA queue targets;
   - pause rules;
   - escalation warnings.

8. Approvals
   - approval required;
   - approver source;
   - conditions;
   - denial path;
   - approval evidence requirement.

9. Diagnostics / Modules
   - suggested playbook;
   - auto-start or manual start;
   - consent requirement;
   - tool results to attach to ticket.

10. Closure
   - resolution code required;
   - public summary required;
   - internal summary required;
   - evidence required;
   - approval evidence required;
   - auto-close after N days.

#### Operator Ticket Card

The support ticket card/detail must expose a normalized `operational_summary`:

```yaml
operational_summary:
  what_happened:
    title
    description
    request_template
    structured_facts
  affected_person:
    requester_id
    display_name
    department
    phone
  location:
    building
    room
    device_location
  affected_object:
    category
    service
    subcategory
    asset
    url_or_system
  action_owner:
    next_action_owner
    queue
    assignee
    required_action_label
  deadline:
    next_action_due_at
    sla_first_response_due_at
    sla_resolution_due_at
    ola_ack_due_at
    ola_processing_due_at
    breach_state
  work_done:
    diagnostics
    playbook_runs
    tool_results
    status_changes
    messages
    evidence
```

### Implementation Phases

#### Phase 0. Baseline And Safety

Purpose: establish a clean baseline before changing process contracts.

Files to inspect first:

- `docs/QUICK_LOOKUP.md`
- `server/docs/CODEMAP.md`
- `server/docs/TICKET_SYSTEM.md`
- `server/docs/REQUEST_FORM_BUILDER.md`
- `server/tickets/form_catalog.py`
- `server/tickets/create_flow.py`
- `server/tickets/routing_service.py`
- `server/tickets/workflow_service.py`
- `server/tickets/statuses.py`
- `server/tickets/sla_service.py`
- `server/tickets/ola_service.py`
- `server/web_api/admin_handlers.py`
- `server/web_api/settings_handlers.py`
- `server/web_api/support_handlers.py`
- `server/web_api/dto/settings.py`
- `server/web_api/dto/support.py`
- `webapp/src/features/forms-builder/forms-builder-panel.tsx`
- `webapp/src/features/forms-builder/api.ts`
- `webapp/src/pages/settings/index.tsx`
- `webapp/src/pages/tickets/detail-page.tsx`
- `webapp/src/features/queues/api.ts`
- `webapp/src/features/queues/support-workspace.tsx`
- `webapp/src/pages/help/index.tsx`
- `webapp/src/features/requester/types.ts`

Commands:

- `.\scripts\bootstrap_shell_utf8.ps1`
- `python scripts/task_intake.py --task "help desk request templates workflow profiles priority policy SLA OLA settings UI forms builder ticket card"`
- `python scripts/bootstrap_web_toolchain.py`
- `python -m pytest server/tests/test_ticket_queue_routing_contracts.py server/tests/test_ticket_work_visibility_schema.py server/tests/test_web_settings_api.py -q`
- `pnpm --dir webapp run test -- --run webapp/src/features/forms-builder/forms-builder-panel.test.tsx webapp/src/pages/settings/index.test.tsx webapp/src/pages/tickets/detail-page.test.tsx`

Exit criteria:

- Current behavior is documented.
- Existing focused tests pass or failures are recorded with exact cause.
- No schema or UI changes happen before this baseline.

#### Phase 1. Process Profile Registry

Purpose: make `ticket_type` a first-class process selector without making workflow DB-configurable yet.

Server files:

- Create `server/tickets/workflow_profiles.py`.
- Modify `server/tickets/workflow_service.py`.
- Modify `server/web_api/settings_handlers.py`.
- Modify `server/web_api/dto/settings.py`.
- Modify `server/web_api/admin_handlers.py` for form/template catalog payloads.
- Update `server/docs/TICKET_SYSTEM.md`.
- Update `server/docs/REQUEST_FORM_BUILDER.md`.
- Update `server/docs/CODEMAP.md`.

Tests:

- Create `server/tests/test_ticket_workflow_profiles.py`.
- Extend `server/tests/test_web_settings_api.py`.
- Extend `server/tests/test_web_admin_api.py`.

Tasks:

- Define `WorkflowProfile` dataclass / Pydantic-like plain structure with:
  - `ticket_type`;
  - label;
  - purpose;
  - suggested path;
  - allowed statuses;
  - required create fields;
  - required resolve fields;
  - gates.
- Add registry entries for `incident`, `service_request`, `access_request`, `change_request`, `consultation`.
- Add resolver:
  - unknown or blank `ticket_type` maps to `service_request` or existing `request` compatibility profile;
  - legacy request kinds remain accepted but normalize through template configuration.
- Change `TicketWorkflowService.apply_status_transition` to load profile by ticket's `ticket_type`.
- Do not remove the global transition table yet.
- Add profile-level validation:
  - `access_request` cannot resolve without approval evidence/action log once approval policy is attached;
  - `change_request` cannot move to work without approval and schedule once the policy is attached;
  - `incident` can resolve with diagnostic/evidence gates depending on priority.
- Expose workflow profiles in `/api/web/settings` and `/api/web/admin/forms/current`.
- Add frontend type definitions only after server DTO tests exist.

Acceptance tests:

- `incident` profile exposes expected suggested path.
- `access_request` profile exposes approval requirement metadata.
- settings API returns all workflow profiles.
- forms admin API returns workflow profile catalog.
- existing tickets without recognized `ticket_type` still transition through compatibility profile.

#### Phase 2. Request Template Contract

Purpose: upgrade the form catalog from "fields only" to "request template produces process context".

Server files:

- Modify `server/tickets/form_catalog.py`.
- Modify `server/tickets/create_flow.py`.
- Modify `server/tickets/public_ticket_handlers.py`.
- Modify `server/tickets/handlers.py`.
- Modify `server/web_api/admin_handlers.py`.
- Modify `server/web_api/settings_handlers.py`.
- Modify `server/tickets/routing_service.py`.
- Update `server/docs/REQUEST_FORM_BUILDER.md`.

Frontend files:

- Modify `webapp/src/features/forms-builder/api.ts`.
- Modify `webapp/src/features/forms-builder/forms-builder-panel.tsx`.
- Modify `webapp/src/features/forms-builder/forms-builder-panel.test.tsx`.
- Modify `webapp/src/pages/help/index.tsx`.
- Modify `webapp/src/pages/help/index.test.tsx`.
- Modify `webapp/src/features/requester/types.ts`.
- Modify `pc_agent/ui_gui/chat_panel.py` only if agent-side form creation needs the new fields.

Tests:

- Extend `server/tests/test_ticket_form_packs.py`.
- Extend `server/tests/test_ticket_queue_routing_contracts.py`.
- Extend `server/tests/test_web_admin_api.py`.
- Extend `webapp/src/features/forms-builder/forms-builder-panel.test.tsx`.
- Extend `webapp/src/pages/help/index.test.tsx`.

Tasks:

- Add optional template fields to form schema:
  - `ticket_type`;
  - `category_id`;
  - `service_id`;
  - `subcategory_id`;
  - `default_queue_id`;
  - `sla_policy_id`;
  - `priority_policy`;
  - `approval_policy`;
  - `suggested_playbook_id`;
  - `closure_policy`;
  - `visibility_policy`;
  - `field_roles`;
  - `routing_policy`.
- Preserve compatibility:
  - old form without `ticket_type` defaults to `service_request` or maps from `request_kind` through a compatibility map;
  - old `playbook_triggers` continue to work.
- Change ticket creation:
  - if `form_key` is provided, validated form template is authoritative for `ticket_type`;
  - request body `ticket_type` cannot override template `ticket_type` for public/requester flows;
  - staff/internal APIs may override only with audit event.
- Write `template_context` into `tickets.custom_fields`:
  - `request_template_key`;
  - `request_template_title`;
  - `request_kind`;
  - selected process policies;
  - field role extraction result.
- Ensure routing preview uses the same template context as real creation.
- Rename UI labels from "Форма" to "Шаблон обращения" where the admin is configuring process behavior, while still using existing API names internally.

Acceptance tests:

- Template "Не открывается сайт" produces `ticket_type=incident`, network category and website playbook trigger.
- Template "Нужен доступ" produces `ticket_type=access_request`, access category and approval policy metadata.
- Public user cannot force `ticket_type=incident` by changing request payload when selected template says `consultation`.
- Route preview and real creation use the same context.
- Old form packs load without migration errors.

#### Phase 3. Priority Policy Engine

Purpose: calculate priority from facts, keep audit evidence, and make SLA use the effective priority.

Server files:

- Create `server/tickets/priority_policy.py`.
- Modify `server/tickets/statuses.py`.
- Modify `server/tickets/create_flow.py`.
- Modify `server/tickets/public_ticket_handlers.py`.
- Modify `server/tickets/handlers.py`.
- Modify `server/tickets/sla_service.py`.
- Modify `server/tickets/routing_service.py`.
- Modify `server/app/api/serializers.py`.
- Modify `server/web_api/support_handlers.py`.
- Modify `server/web_api/dto/support.py`.
- Modify `server/web_api/settings_handlers.py`.
- Modify `server/web_api/dto/settings.py`.
- Add migration under `server/app/db/migrations/versions/`.
- Update `server/docs/TICKET_SYSTEM.md`.

Database changes:

- Add nullable columns to `tickets`:
  - `computed_priority` `String(5)`;
  - `manual_priority` `String(5)`;
  - `effective_priority` `String(5)`;
  - `priority_source` `String(30)`;
  - `priority_reason` `Text`;
  - `priority_changed_by` `Text`;
  - `priority_changed_at` `TIMESTAMP(timezone=True)`;
  - `priority_context_json` `JSONB`.
- Keep `priority` as legacy SLA priority for now.
- Backfill:
  - `effective_priority` from `custom_fields.priority_class` or legacy `priority`;
  - `computed_priority` equals `effective_priority`;
  - `priority_source=system`;
  - `priority_context_json` records `migration_backfill=true`.

Frontend files:

- Modify `webapp/src/pages/help/index.tsx`.
- Modify `webapp/src/features/requester/types.ts`.
- Modify `webapp/src/features/forms-builder/forms-builder-panel.tsx`.
- Modify `webapp/src/pages/settings/index.tsx`.
- Modify `webapp/src/pages/tickets/detail-page.tsx`.
- Modify `webapp/src/features/queues/api.ts`.

Tests:

- Create `server/tests/test_ticket_priority_policy.py`.
- Extend `server/tests/test_ticket_queue_routing_contracts.py`.
- Extend `server/tests/test_web_support_api.py`.
- Extend `server/tests/test_web_settings_api.py`.
- Extend `webapp/src/pages/help/index.test.tsx`.
- Extend `webapp/src/pages/settings/index.test.tsx`.
- Extend `webapp/src/pages/tickets/detail-page.test.tsx`.

Tasks:

- Define normalized impact levels:
  - `minimal`;
  - `low`;
  - `medium`;
  - `high`.
- Define normalized urgency levels:
  - `inconvenience`;
  - `workaround_available`;
  - `partial_work`;
  - `work_stopped`.
- Define importance sources:
  - service criticality;
  - deadline;
  - security category;
  - public service/citizen reception;
  - reporting period.
- Implement base matrix P0..P3.
- Implement modifier application with explicit reason list.
- Implement `computed_priority`, `manual_priority`, `effective_priority`.
- Implement override API:
  - staff only;
  - reason required;
  - event `priority_changed`;
  - event payload includes previous context and new context;
  - SLA recalculates after effective priority changes.
- Replace user-facing urgency/importance checkboxes with fact questions in `/app/help`.
- Keep raw P0/P1/P2/P3 hidden from requester.
- Show priority rationale in support card:
  - affected scope;
  - work continuity;
  - criticality/deadline;
  - modifiers;
  - override reason if present.

Acceptance tests:

- One user, workaround exists, normal service -> P3.
- One user, work stopped, normal service -> P2.
- Department affected, work stopped -> P1.
- Critical system affected and work stopped -> P0.
- Security category enforces minimum P1.
- Staff override requires reason.
- SLA due dates recalculate after effective priority changes.
- Requester UI does not render P0/P1/P2/P3 selection controls.

#### Phase 4. SLA / OLA Settings Based On Priority

Purpose: make priority settings and SLA/OLA settings explicit and understandable in server UI.

Server files:

- Modify `server/tickets/admin_config_handlers.py`.
- Modify `server/tickets/admin_config_service.py`.
- Modify `server/app/repos/ticket_admin_config_repo.py`.
- Modify `server/web_api/settings_handlers.py`.
- Modify `server/web_api/dto/settings.py`.
- Modify `server/tickets/sla_service.py`.
- Modify `server/tickets/ola_service.py` if response shape needs clearer labels.
- Update `server/docs/TICKET_SYSTEM.md`.

Frontend files:

- Modify `webapp/src/features/settings/api.ts`.
- Modify `webapp/src/pages/settings/index.tsx`.
- Modify `webapp/src/pages/settings/index.test.tsx`.

Tests:

- Extend `server/tests/test_web_settings_api.py`.
- Extend `server/tests/test_ticket_queue_routing_contracts.py`.
- Extend `webapp/src/pages/settings/index.test.tsx`.

Tasks:

- Add settings payload sections:
  - `priority_settings`;
  - `priority_matrix`;
  - `priority_modifiers`;
  - `sla_targets_by_effective_priority`;
  - `ola_targets_by_queue_and_priority`.
- UI tab "Приоритет":
  - impact labels;
  - urgency labels;
  - matrix editor;
  - modifier list;
  - preview from sample answers.
- UI tab "SLA / OLA":
  - first response target;
  - restore/workaround target;
  - resolution target label if distinct from restore target;
  - business calendar;
  - OLA ack and processing targets by queue/effective priority.
- Keep P0/P1/P2/P3 visible only in admin/support settings, not requester.
- Ensure SLA service uses effective priority mapping.
- Add visible explanation in admin settings that P0/P1 restoration target can mean temporary workaround.

Acceptance tests:

- Settings API returns matrix and SLA targets with P0..P3 labels.
- Updating matrix changes priority preview.
- Updating SLA target changes due dates on new ticket.
- OLA target remains queue-scoped.
- Settings UI renders priority and SLA/OLA without raw JSON as normal path.

#### Phase 5. Workflow-Gated Ticket Actions

Purpose: enforce process differences for incident, access request, change request and consultation.

Server files:

- Modify `server/tickets/workflow_service.py`.
- Modify `server/tickets/handlers.py`.
- Modify `server/web_api/support_handlers.py`.
- Modify `server/web_api/dto/support.py`.
- Possibly add `server/tickets/workflow_gates.py`.
- Update `server/docs/TICKET_SYSTEM.md`.

Frontend files:

- Modify `webapp/src/pages/tickets/detail-page.tsx`.
- Modify `webapp/src/features/queues/support-workspace.tsx`.
- Modify `webapp/src/features/queues/api.ts`.
- Modify shared status presentation helper if needed.

Tests:

- Extend `server/tests/test_ticket_work_visibility_schema.py`.
- Create/extend `server/tests/test_ticket_workflow_profiles.py`.
- Extend `server/tests/test_web_support_api.py`.
- Extend `webapp/src/pages/tickets/detail-page.test.tsx`.

Tasks:

- Add `workflow_guidance` to ticket detail DTO:
  - profile label;
  - current stage;
  - suggested next statuses;
  - blocked transitions with reasons;
  - required facts/evidence.
- Incident:
  - allow standard restore path;
  - require diagnostics/evidence for P0/P1 before resolved if closure policy says so.
- Access request:
  - require approval policy fields before `in_progress` or `resolved`;
  - require action log before closure/resolution.
- Change request:
  - require work plan, window, risk and rollback plan before scheduled/in_progress;
  - require approval evidence before scheduled/in_progress.
- Consultation:
  - require public answer/summary before resolved.
- Frontend:
  - show why a status transition is blocked;
  - show required missing facts;
  - keep mutation through explicit apply button only.

Acceptance tests:

- Access request cannot skip approval gate when approval required.
- Change request cannot move to scheduled without work window and rollback plan.
- Consultation cannot resolve without public answer.
- Incident P0 cannot resolve without required diagnostic evidence when policy requires it.
- Existing generic tickets keep compatibility behavior.

#### Phase 6. Request Template Builder UI

Purpose: implement the 10-tab admin request template builder.

Prerequisite:

- Run `python scripts/bootstrap_web_toolchain.py`.

Frontend files:

- Modify `webapp/src/features/forms-builder/forms-builder-panel.tsx`.
- Modify `webapp/src/features/forms-builder/api.ts`.
- Consider extracting focused files:
  - `webapp/src/features/forms-builder/template-basic-tab.tsx`;
  - `webapp/src/features/forms-builder/template-classification-tab.tsx`;
  - `webapp/src/features/forms-builder/template-fields-tab.tsx`;
  - `webapp/src/features/forms-builder/template-conditions-tab.tsx`;
  - `webapp/src/features/forms-builder/template-priority-tab.tsx`;
  - `webapp/src/features/forms-builder/template-routing-tab.tsx`;
  - `webapp/src/features/forms-builder/template-sla-ola-tab.tsx`;
  - `webapp/src/features/forms-builder/template-approvals-tab.tsx`;
  - `webapp/src/features/forms-builder/template-diagnostics-tab.tsx`;
  - `webapp/src/features/forms-builder/template-closure-tab.tsx`;
  - `webapp/src/features/forms-builder/template-preview.tsx`.
- Modify tests in `webapp/src/features/forms-builder/forms-builder-panel.test.tsx`.

Server files:

- Modify `server/web_api/admin_handlers.py` only for missing catalog data.
- Modify `server/web_api/dto/admin.py` only if typed DTOs need new response/request fields.

Tasks:

- Preserve existing single working catalog behavior.
- Add left list of request templates.
- Add tabbed editor for selected template.
- Keep field editing stable:
  - key;
  - label;
  - type;
  - required;
  - options;
  - conditional visibility.
- Add field roles editor:
  - routing field;
  - priority field;
  - SLA field;
  - approval field;
  - diagnostic input;
  - closure evidence;
  - display only.
- Add priority tab:
  - map form answers to impact/urgency/importance;
  - preview priority;
  - show rationale.
- Add routing tab:
  - default queue;
  - fallback queue;
  - preview.
- Add SLA/OLA tab:
  - SLA policy select;
  - OLA information based on selected queue.
- Add approvals tab:
  - required flag;
  - approver source;
  - denial path.
- Add diagnostics tab:
  - playbook select or current text input if catalog is not ready;
  - auto-start/manual;
  - consent flag;
  - attach result flags.
- Add closure tab:
  - require resolution code;
  - require public summary;
  - require evidence;
  - auto-close days.

React performance constraints:

- Keep large derived lists in `useMemo` with primitive dependencies.
- Do not define nested components inside the main panel render path.
- Use controlled components with focused local state per tab.
- Avoid re-rendering the full builder on every field option edit if extraction is feasible.

Acceptance tests:

- Admin can create a template with `ticket_type=incident`.
- Admin can map priority fields without raw JSON.
- Admin can configure an access approval requirement.
- Existing visibility rule tests still pass.
- Route preview still works from draft template.
- Save payload remains compatible with server validation.

#### Phase 7. Requester Intake UI

Purpose: user chooses human catalog items and answers fact questions; system computes process context.

Frontend files:

- Modify `webapp/src/pages/help/index.tsx`.
- Modify `webapp/src/features/requester/api.ts`.
- Modify `webapp/src/features/requester/types.ts`.
- Modify `webapp/src/pages/help/index.test.tsx`.

Server files:

- Modify `server/tickets/public_ticket_handlers.py`.
- Modify `server/tickets/create_flow.py`.
- Modify `server/tickets/form_catalog.py` if validation changes are needed.

Tasks:

- Show public catalog titles, not internal process/category values.
- Render template-specific fields and conditional fields.
- Replace urgency/importance checkboxes with:
  - affected scope;
  - ability to continue work;
  - critical deadline/reporting;
  - workaround availability;
  - affected system/service.
- Do not show P0/P1/P2/P3 to requester.
- Submit facts to server as structured form payload.
- Server computes process context and priority.
- Response page shows ticket code and access code, not internal priority unless explicitly required later.

Acceptance tests:

- User sees "Не открывается сайт", "Нужен доступ", etc.
- User does not see `incident`, `access_request`, `P0`, `P1`, `P2`, `P3` as choices.
- Selecting website incident submits URL/location/workaround facts.
- Selecting access request submits system/role/justification/approver facts.

#### Phase 8. Operator Ticket Card And Seven Questions

Purpose: make ticket detail operationally complete for L1/support without support-line changes.

Server files:

- Modify `server/web_api/support_handlers.py`.
- Modify `server/web_api/dto/support.py`.
- Modify `server/app/api/serializers.py`.
- Possibly add `server/tickets/operational_summary.py`.

Frontend files:

- Modify `webapp/src/features/queues/api.ts`.
- Modify `webapp/src/pages/tickets/detail-page.tsx`.
- Modify `webapp/src/features/queues/support-workspace.tsx`.
- Modify `webapp/src/pages/tickets/detail-page.test.tsx`.
- Modify `webapp/src/features/queues/support-workspace.test.tsx`.

Tasks:

- Add server-side `operational_summary` DTO.
- What happened:
  - title;
  - description;
  - request template title;
  - normalized form facts.
- Who:
  - requester display name;
  - department;
  - contact;
  - target user for access requests.
- Where:
  - building;
  - room;
  - device location;
  - requester profile location.
- What affected:
  - category;
  - service;
  - subcategory;
  - asset/device/system/url.
- Who acts now:
  - `next_action_owner`;
  - queue;
  - assignee;
  - required action label.
- Deadline:
  - next action due;
  - SLA first response;
  - SLA restore/resolution;
  - OLA ack/processing;
  - breach badges.
- What checked/done:
  - playbook started/completed;
  - tool runs;
  - diagnostic evidence;
  - status transitions;
  - worklog/action log;
  - passport/evidence.
- Add priority rationale block:
  - computed priority;
  - effective priority;
  - override reason;
  - SLA selected from effective priority.

Acceptance tests:

- Detail page renders all seven sections for incident.
- Access request shows system/role/approver/action log fields.
- Change request shows plan/window/risk/rollback fields when present.
- Priority rationale renders computed/effective/override states.
- OLA/SLA deadline section distinguishes user-facing SLA from internal OLA.

#### Phase 9. Diagnostics, Evidence, Knowledge And AI Suggestions

Purpose: connect existing playbooks/passport/knowledge draft to the new process context.

Server files:

- Modify `server/tickets/passport_service.py`.
- Modify `server/web_api/support_handlers.py`.
- Modify `server/app/services/playbook_engine.py` only if facts package needs new template context.
- Possibly create `server/tickets/ai_suggestions.py` later.

Frontend files:

- Modify `webapp/src/pages/tickets/detail-page.tsx`.
- Modify `webapp/src/features/queues/api.ts`.

Tasks:

- Ensure form-derived facts are passed into diagnostic playbooks.
- Ensure playbook results can count as closure evidence when closure policy allows it.
- Ensure passport generation includes:
  - ticket_type;
  - category;
  - priority rationale;
  - approval facts for access/change;
  - diagnostics/actions/evidence.
- Keep knowledge draft generation based on confirmed solution/passport.
- AI suggestion model:
  - classify suggestion;
  - similar tickets;
  - summary draft;
  - suggested resolution article.
- AI suggestions must be stored as suggestions with source and confidence, not direct authoritative fields.

Acceptance tests:

- Diagnostic result appears in operational summary.
- Passport includes process context.
- Knowledge draft uses confirmed/passport data, not unverified AI-only facts.

#### Phase 10. Documentation, Release And Live Verification

Docs to update:

- `server/docs/TICKET_SYSTEM.md`
- `server/docs/REQUEST_FORM_BUILDER.md`
- `server/docs/DIAGNOSTIC_PLAYBOOKS.md` if facts/playbook context changes
- `server/docs/CODEMAP.md`
- `docs/QUICK_LOOKUP.md`
- `scripts/navigation_catalog.py` if new files/routes are added
- `docs/README.md` if new canonical docs or concepts are added
- `PLANS.md` after each implementation checkpoint

Local verification:

- `python scripts/verify_workspace.py`
- `python -m pytest server/tests/test_ticket_workflow_profiles.py -q`
- `python -m pytest server/tests/test_ticket_priority_policy.py -q`
- `python -m pytest server/tests/test_ticket_form_packs.py server/tests/test_ticket_queue_routing_contracts.py server/tests/test_ticket_work_visibility_schema.py server/tests/test_web_admin_api.py server/tests/test_web_support_api.py server/tests/test_web_settings_api.py -q`
- `python scripts/bootstrap_web_toolchain.py`
- `pnpm --dir webapp run test`
- `pnpm --dir webapp run build`

Remote/browser verification:

- Deploy only after local verification.
- Use official scripts:
  - `python scripts/deploy_workspace_to_remote.py`
  - `python scripts/release_server_to_remote.py`
  - `python scripts/manage_remote_stack.py start server`
  - `python scripts/manage_remote_stack.py smoke server`
- Browser check only at `http://192.168.100.17:8666/admin`.
- Verify:
  - `/app/help` requester catalog and no priority choice;
  - `/app/admin/forms` request template builder tabs;
  - `/app/settings` priority and SLA/OLA settings;
  - `/app/tickets` and ticket detail seven-question card;
  - access request approval gate;
  - incident priority rationale and SLA;
  - playbook/evidence/knowledge draft path.
- Stop server after checks unless explicitly asked otherwise:
  - `python scripts/manage_remote_stack.py stop server`

### Suggested Commit Slices

1. `feat(tickets): add workflow profile registry`
2. `feat(forms): extend request templates with process context`
3. `feat(tickets): calculate effective priority from intake facts`
4. `feat(settings): expose priority and SLA configuration`
5. `feat(tickets): enforce workflow profile gates`
6. `feat(webapp): upgrade request template builder`
7. `feat(webapp): improve requester intake priority facts`
8. `feat(support): add operational ticket summary`
9. `feat(tickets): connect diagnostics evidence and knowledge draft context`
10. `docs: document service desk process model`

Each slice must include focused tests and update `PLANS.md` Current State / Verification / Handoff before moving to the next slice.

### Risks And Mitigations

Risk: conflating form key, request kind and ticket type again.

Mitigation:

- Add explicit tests proving:
  - form key is public template identity;
  - request kind is analytics/catalog identity;
  - ticket type selects workflow profile.

Risk: changing priority breaks SLA due dates.

Mitigation:

- Keep legacy `tickets.priority` mapped from effective priority.
- Add tests for SLA recalculation on priority changes.

Risk: request template schema becomes too large and hard to maintain.

Mitigation:

- Keep defaults explicit.
- Split frontend builder tabs into focused components.
- Keep server validation centralized in `form_catalog.py`.

Risk: workflow configurability is overbuilt too early.

Mitigation:

- Start with code-defined profiles.
- Expose serializable DTO.
- Do not add workflow editor until profile behavior is proven.

Risk: support UI becomes too verbose.

Mitigation:

- The seven-question card is a summary.
- Full raw facts stay in detail sections/tabs.
- Use progressive disclosure for evidence, diagnostics and audit.

Risk: support level escalation is requested implicitly.

Mitigation:

- Do not introduce support-line entity in this plan.
- Use queue reroute, OLA restart and evidence handoff as the current escalation mechanism.

### Current State

- Planning complete in this file.
- No code, migrations, tests or docs have been changed yet for the new model.
- Last focused baseline previously observed: `server/tests/test_ticket_queue_routing_contracts.py`, `server/tests/test_ticket_work_visibility_schema.py`, `server/tests/test_web_settings_api.py` passed with 17 tests.
- Fresh baseline must be rerun before implementation starts.

### Next Steps

1. Run Phase 0 baseline commands.
2. Implement Phase 1 workflow profile registry with tests.
3. Update `PLANS.md` after Phase 1 with:
   - changed files;
   - tests run;
   - open risks;
   - next slice.
4. Proceed phase by phase; do not start UI builder tabs before backend request template/process DTOs are stable.

### Verification

For this planning update:

- Verify `PLANS.md` is UTF-8 readable and contains the new plan.
- Verify no source files were modified as part of planning.

For implementation:

- Follow Phase 10 verification.
- Before any completion claim, rerun the relevant focused tests and read their output.

### Handoff

Primary implementation entrypoint:

1. Start with `server/tickets/workflow_profiles.py`.
2. Add tests in `server/tests/test_ticket_workflow_profiles.py`.
3. Expose workflow profile catalog in settings/admin forms APIs.
4. Only then extend request templates and priority calculation.

Key rule:

- `ticket_type` is the process selector.
- Form/template collects facts and produces process context.
- Priority is calculated from facts.
- Routing chooses queue.
- Queue owns responsible group.
- SLA is user-facing deadline.
- OLA is internal queue deadline.
- Status shows process stage.
- `next_action_owner` shows whose move it is.
