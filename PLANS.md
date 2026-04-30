# PLANS.md

## 2026-04-30 Help Desk Policy Runtime Completion Plan

Status: executing the remaining target-model gaps. Current factual completion is about 88% after custom smart-view runtime, standalone SLA JSON target calculation and lifecycle effective policy resolution for workflow guards, notifications and runtime visibility.

### Goal

Finish the remaining gap between the standalone helpdesk policy registry and real runtime behavior. Every published policy must either be executable or clearly marked as stored metadata with a tracked implementation slice.

### Scope and Order

1. Custom smart views in support queue runtime.
   - Files: `server/tickets/smart_views.py`, `server/web_api/support_handlers.py`, `server/tests/test_web_support_api.py`, docs/CODEMAP/navigation.
   - Behavior: active published `smart_views` appear in `GET /api/web/support/queue` filter options; `smart_view=<custom_code>` applies the saved JSON filter to queue rows.
   - Minimum filters: `status_in`, `status_not_in`, `open_only`, `queue_code`, `assignee_id`, `assignee_empty`, `assigned_to_me`, `next_action_owner`, `due_before_hours` + `due_fields`, `breached_fields`, `field_equals`, `field_in`, `tags_any`.
   - Verification: focused pytest for published custom smart view, existing built-in smart-view test, then support queue browser/API smoke.

2. Standalone SLA policy timer engine.
   - Files: `server/tickets/sla_service.py`, `server/tickets/calendar_engine.py`, `server/tickets/helpdesk_policy_runtime.py`, `server/tests/test_ticket_sla_policy.py` or a focused new test file.
   - Behavior: standalone `sla_policies.config.targets.first_response/resolution` can calculate due dates directly when no canonical `ticket_sla_policies` id is referenced.
   - Calendar: keep existing business-calendar calculation; numeric JSON durations with `m`, `h` or `d` units such as `15m`, `90m`, `1h`, `8h`, `3d` must map to working-time aware deadlines. Raw numeric values remain minutes for backward compatibility.
   - Compatibility: if `sla_policy_id` points to canonical `ticket_sla_policies`, keep existing engine path.
   - Verification: tests for P0/P1/P2/P3 targets, calendar pauses, stop/pause conditions where currently supported.

3. Effective policy resolution across lifecycle.
   - Files: `server/tickets/workflow_service.py`, `server/tickets/notification_service.py`, `server/tickets/visibility_policy.py`, `server/web_api/support_handlers.py`, `server/tickets/helpdesk_policy_runtime.py`.
   - Behavior: status changes, notification dispatch, requester/support serialization and reporting helpers resolve effective registry policy by ticket template/classification when ticket snapshot is missing or stale.
   - Rule: ticket creation still snapshots effective sources into `custom_fields.request_template`; lifecycle runtime may refresh from registry but must not mutate historical ticket data silently.
   - Verification: tests for notification/visibility/workflow using registry-only policy.

4. Workflow guards/actions editor.
   - Files: `webapp/src/features/forms-builder/forms-builder-panel.tsx`, `webapp/src/features/settings/*`, `server/web_api/settings_handlers.py`, `server/tickets/workflow_service.py`.
   - Behavior: admin can edit transition guards/actions beyond roles/required fields: public/internal comment requirement, approval/evidence guard, notification action, SLA pause/resume marker.
   - Verification: frontend test for editor payload, backend transition tests for guard/action execution.

5. Policy rollback, diff and deactivate UI.
   - Files: `server/app/repos/helpdesk_policy_repo.py`, `server/web_api/admin_handlers.py`, `webapp/src/features/forms-builder/*`.
   - Behavior: list versions, compare JSON configs, deactivate active version, publish rollback as a new version, audit every action.
   - Safety: never hard-delete policy versions.
   - Verification: repo/API tests for deactivate/rollback/audit, React test for action calls.

6. External notification channels.
   - Files: `server/tickets/notification_service.py`, notification provider modules, admin settings UI.
   - Behavior: policy channel blocks can route selected events to email and later Telegram/VK Teams through provider abstraction.
   - Safety: in-app notification remains baseline; external delivery failures must be logged and non-blocking.
   - Verification: provider fake tests and delivery audit tests.

7. Reporting/passport policy editor as standalone entity.
   - Files: `server/app/db/models.py`, migration, `server/app/repos/helpdesk_policy_repo.py`, `server/tickets/passport_service.py`, forms builder policy editor.
   - Behavior: reporting/passport policy defines required passport sections, evidence package, export visibility and report tags separately from closure policy.
   - Verification: passport generation tests and admin publish tests.

### Current Slice

Slice 16: effective registry policy resolution across lifecycle runtime.

Progress:

- [x] Write failing pytest proving `smart_view=<published_code>` currently falls back to `all`.
- [x] Implement custom smart-view normalization, filter options and matcher.
- [x] Run focused built-in + custom smart-view tests.
- [x] Update CODEMAP/QUICK_LOOKUP/navigation docs.
- [x] Run workspace verification and commit this slice.
- [x] Release/live-check support queue if web/API behavior changed.
- [x] Write failing pytest proving `request_template.sla_policy.targets` is ignored without legacy `ticket_sla_policies`.
- [x] Implement standalone SLA duration parsing and target selection for `first_response` / `resolution`.
- [x] Support embedded standalone business calendar config through the existing calendar engine.
- [x] Add ticket-create API regression proving published standalone `sla` policy sets due dates without `ticket.sla_policy_id`.
- [x] Run focused SLA/priority/registry tests and workspace verification.
- [x] Release/live-check standalone SLA runtime on the Linux stand.
- [x] Write failing tests proving registry-only `closure`, `approval`, `notification` and `visibility` policies are ignored after ticket creation.
- [x] Add `resolve_effective_ticket_policy(...)` for existing-ticket lifecycle runtime.
- [x] Apply effective registry resolution to approval guards, closure guards, notification recipients and async ticket visibility payloads.
- [x] Run focused lifecycle/registry tests and workspace verification.
- [x] Commit, release/live-check lifecycle runtime and stop the remote server.

Local verification for slice 16:

- `python -m pytest server/tests/test_ticket_closure_policy.py::test_closure_policy_resolves_from_registry_during_transition server/tests/test_ticket_approval_policy.py::test_approval_policy_resolves_from_registry_during_transition server/tests/test_stage8.py::test_notification_policy_resolves_from_registry_when_snapshot_missing -v --tb=short` -> passed, 3 tests.
- `python -m pytest server/tests/test_ticket_workflow_visibility.py::test_runtime_visibility_policy_resolves_from_registry -v --tb=short` -> passed, 1 test.
- `python -m pytest server/tests/test_ticket_closure_policy.py server/tests/test_ticket_approval_policy.py server/tests/test_stage8.py server/tests/test_ticket_workflow_visibility.py server/tests/test_helpdesk_policy_registry.py -q --tb=short` -> passed, 29 tests.
- `python -m pytest server/tests/test_web_support_api.py::test_web_support_queue_returns_typed_scope_and_filter_payload server/tests/test_web_support_api.py::test_web_support_status_action_returns_typed_result_and_updates_ticket -q --tb=short` -> passed, 2 tests.
- `python scripts/verify_workspace.py` -> passed.

Live verification for slice 16:

- Released commit `3427ed4` with `python scripts/release_server_to_remote.py --allow-local-dirty --skip-ci-check --leave-running`.
- Release flow ran `verify_workspace.py`, built the webapp bundle, deployed the committed Git state to `/var/chat_bot/pc_client`, applied migrations and started control/server.
- Remote smoke passed: `GET /api/health` -> 200 after retry.
- Live transaction published temporary registry-only closure/approval/notification/visibility policies for template `live_lifecycle_81be236adb` and created ticket `2e91a094-ec7f-4612-b4be-7e102d752afe` without policy snapshot blocks.
- Runtime checks confirmed `closure_policy` blocked resolve without `resolution_code`, `approval_policy` blocked execution without approval, `notification_policy` produced no recipients for `status_changed`, and `visibility_policy` returned `public_status_label="Live registry public status"` while redacting `root_cause`; the transaction was rolled back after verification.

### Completion Metric

- 78%: previous committed state, editors and ticket-create effective overlay done.
- 80%: custom smart views executable in support queue.
- 84%: standalone SLA JSON targets executable by timer engine.
- 88%: lifecycle runtime uses effective registry resolution for workflow/visibility/notifications.
- 92%: workflow guards/actions editor and execution.
- 95%: rollback/diff/deactivate lifecycle.
- 98%: external notification channels.
- 100%: reporting/passport standalone policy editor and runtime.

Historical slices remain below for audit context.

## 2026-04-30 Help Desk Settings: Functional Policy Model

Status: superseded by the runtime completion plan above. Historical context only.

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
- Template context is preserved in `custom_fields.request_template`, including `ticket_type`, category/service/subcategory, queue, SLA, priority/routing/approval/OLA/closure/visibility/notification policies, field roles and suggested playbook.
- Workflow profiles exist and status transitions use the configured profile for `ticket_type`.
- Priority policy exists for intake facts and stores computed/effective priority context.
- SLA and OLA services exist, and SLA due dates use calendar-aware calculation when a policy points to a business calendar.
- Routing exists through global rules, executable template-level `routing_policy`, template fallback queue and global fallback queue.
- Diagnostics/playbooks are separate operations, not ticket statuses.
- Resolution passport tables and services exist.

Missing or weak:

- Standalone persisted entities exist for `request_templates`, `priority_policies`, `sla_policies`, `ola_policies`, `routing_policies`, `approval_policies`, `closure_policies`, `diagnostic_policies`, `notification_policies`, `visibility_policies` and `smart_views`. Existing `ticket_sla_policies` / calendars remain the canonical timer engine; standalone `sla_policies` can reference a valid legacy SLA policy id and carry versioned SLA config for the template model.
- `closure_policy`, `approval_policy`, `routing_policy`, diagnostic attach-to-evidence behavior, `visibility_policy` public-status/redaction behavior and `notification_policy` recipient selection are executable.
- Workflow transitions now enforce configured per-transition roles and required fields; transition actions/guards beyond that remain future work.
- Notification delivery is policy-driven for in-app recipients; external channels remain future work.
- Smart views exist as backend support queue filters and as standalone versioned saved-view records with a visual publisher. Applying custom smart-view filters to the live support queue remains future work.

### Decisions

- Keep backward compatibility with the existing `request_forms` / request-template metadata. New registry publishing must not break `/help`, local agent ticket creation or existing packs.
- Add migrations only for the standalone registry layer, not for speculative UI-only data.
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

4. Routing policy actions.
   - Execute template-level routing rules in addition to global routing rules.
   - Support queue, assignee, priority boost, SLA/OLA override, tags/watchers and playbook suggestion where existing models allow it.
   - Add loop/lock protections.

5. Workflow transition gates.
   - Add required fields per transition.
   - Add role checks beyond support/requester split where profile data provides them.
   - Return blocked transition reasons for API/UI consumers.

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

Slice 13 in progress: priority/SLA/OLA/smart-view editors plus first runtime use of standalone effective policies.

Planned behavior:

- Add separate versioned tables for `request_templates`, `priority_policies`, `sla_policies`, `ola_policies`, `routing_policies`, `approval_policies`, `closure_policies`, `diagnostic_policies`, `notification_policies`, `visibility_policies` and `smart_views`.
- Add generic audit rows for policy/template publication.
- Add a repository that can publish new versions and resolve effective policy config through inheritance: `system` defaults, then `ticket_type`, then `category`, then `request_template` overrides.
- Add typed admin API:
  - `GET /api/web/admin/helpdesk-model/policies` for registry overview.
  - `POST /api/web/admin/helpdesk-model/request-templates/publish-from-form` for publishing the currently edited visual constructor form into the standalone registry.
- Extend `/app/admin/forms` so the visual constructor can publish the selected template and its policies into the standalone registry, while the existing catalog-save flow remains unchanged.
- Add typed admin API `POST /api/web/admin/helpdesk-model/policies/publish` for publishing one standalone policy version from a dedicated editor.
- Add dedicated editors for priority, SLA, OLA, routing, approval, closure, diagnostic, notification, visibility policies and smart views over the standalone registry.
- Add focused backend and frontend tests, then run local verification, release to Linux, browser-check the new registry controls and stop the remote server.

Implemented locally:

- Migration `063` adds standalone versioned tables: `request_templates`, `priority_policies`, `routing_policies`, `approval_policies`, `closure_policies`, `diagnostic_policies`, `notification_policies`, `visibility_policies`, `smart_views` and `helpdesk_policy_audit`. Migration `064` adds standalone `sla_policies` and `ola_policies`.
- `server/app/repos/helpdesk_policy_repo.py` publishes policy/template versions, deactivates previous active versions for the same code, writes audit rows and resolves effective policy config through `system -> ticket_type -> category -> request_template`.
- Typed admin API now exposes:
  - `GET /api/web/admin/helpdesk-model/policies`
  - `POST /api/web/admin/helpdesk-model/request-templates/publish-from-form`
  - `POST /api/web/admin/helpdesk-model/policies/publish`
  - `POST /api/web/admin/helpdesk-model/smart-views/publish`
- `/app/admin/forms` now shows a `Реестр целевой модели` block and can publish the selected visual constructor form into the standalone registry without replacing the existing form-pack publish flow.
- Tests cover inheritance resolution, API publish-from-form, policy publish/version/audit, SLA/OLA policy publication, smart-view publication, runtime priority overlay from the standalone registry and the React policy publish action.

Local verification for slice 11 so far:

- `python -m pytest server/tests/test_helpdesk_policy_registry.py -q --tb=short` -> passed, 2 tests.
- `pnpm --dir webapp exec tsc --noEmit` -> passed.
- `pnpm --dir webapp exec vitest run src/features/forms-builder/forms-builder-panel.test.tsx` -> passed, 11 tests.

Remaining gaps after this slice:

- External email/Telegram/VK Teams delivery.
- Workflow actions beyond the existing transition roles/required fields.
- Full runtime migration for every executable policy path to standalone effective resolution. Ticket creation now overlays effective registry policies into `custom_fields.request_template`; follow-up work should move workflow/status updates, notification dispatch, visibility serialization and support queue smart-view filtering to direct registry reads where appropriate.
- Custom standalone smart-view filters are published and stored, but support queue filtering still primarily uses the built-in backend smart-view matcher.

Slice 12 delta implemented locally:

- Typed admin API now also exposes `POST /api/web/admin/helpdesk-model/policies/publish` for direct standalone policy publication.
- `/app/admin/forms` has dedicated editors for routing, approval, closure, diagnostic, notification and visibility policies. They provide structured controls, JSON preview and active-version publication into the same registry/audit path.
- Focused tests now cover direct policy publish/version/audit behavior and the React routing-policy editor action.

Slice 13 delta implemented locally:

- Added standalone versioned `sla_policies` and `ola_policies` registry tables and models.
- Added direct smart-view publication endpoint `POST /api/web/admin/helpdesk-model/smart-views/publish`.
- `/app/admin/forms` policy editors now include priority, SLA, OLA and smart views in addition to routing/approval/closure/diagnostic/notification/visibility.
- Ticket creation overlays effective standalone registry policies through inheritance before computing priority, routing, SLA/OLA context and request-template custom fields.
- SLA registry config only writes `ticket.sla_policy_id` when the referenced canonical `ticket_sla_policies` row exists, preventing FK failures from draft registry configs.

Previous current step:

Slice 10 completed: visual request-template constructor.

Implemented locally:

- `/app/admin/forms` now has an interactive request-template chain: template -> form -> workflow -> priority -> deadlines -> routing -> approvals -> diagnostics -> closure -> visibility -> notifications.
- The constructor keeps the existing form editor and route preview, but adds step-based policy editing and quick presets for OLA, routing, approvals, diagnostics, closure, visibility and notifications.
- Web draft/save payload now preserves `diagnostic_policy` and `notification_policy` from the visual constructor.
- Focused test verifies the visual constructor writes OLA, diagnostic and notification policies into the catalog save payload.

Local verification for slice 10 so far:

- `pnpm --dir webapp exec tsc --noEmit` -> passed.
- `pnpm --dir webapp exec vitest run src/features/forms-builder/forms-builder-panel.test.tsx` -> passed, 10 tests.

Next verification:

- Run `pnpm --dir webapp run build`.
- Run `python scripts/verify_workspace.py`.
- Deploy through project release scripts, browser-check `/app/admin/forms`, API-check saved contract if needed, then stop the remote server.

Previous current step:

Slice 9 completed: request-template catalog contract and Russian user-facing localization.

Planned behavior:

- `GET /api/web/settings` exposes a typed `ticket_settings.request_templates` catalog assembled from the current preferred request-form pack.
- Each request template shows its public title, internal/process classification, form stats, workflow profile and policy bindings without requiring a separate DB migration yet.
- User-facing web and agent strings avoid raw `SLA` where the user needs an understandable promise: "вам должны ответить до", "решение ожидается до", "сроки ответа и решения".
- Admin/internal surfaces may keep technical keys in small code/source fields, but labels and descriptions should be Russian.

Implemented behavior:

- `GET /api/web/settings` now exposes `ticket_settings.request_templates`, assembled from the preferred request-form pack without adding a new storage migration.
- Request-template rows include public title, internal name, classification, form stats, workflow binding, priority/routing/SLA/OLA/approval/diagnostic/closure/visibility/notification policy bindings, field roles and missing-policy markers.
- Form-pack validation/admin DTOs preserve `diagnostic_policy` alongside the existing request-template policy JSON blocks.
- Web UI labels in settings/forms/reports/ticket detail and local agent ticket metadata now use Russian wording such as "сроки ответа и решения", "вам должны ответить до" and "решение ожидается до" instead of exposing raw SLA/OLA wording to users.
- Backend smart-view labels now describe deadline risks as "Риск по сроку ответа" and "Риск внутренней очереди".

Initial failing tests:

- `server/tests/test_web_settings_api.py::test_web_settings_returns_aggregated_real_payload` fails on old `SLA` process-schema wording and missing `request_templates`.
- `pc_agent/tests/test_chat_panel_helpers.py::test_build_ticket_meta_html_includes_request_form_summary` fails on old `SLA: first response`.
- `pc_agent/tests/test_chat_panel_helpers.py::test_build_ticket_sla_user_summary_uses_dynamic_due_dates` fails on old `first response due` / `resolution/workaround due`.

Local verification for slice 9:

- `python -m pytest server/tests/test_web_settings_api.py server/tests/test_web_support_api.py::test_web_support_queue_applies_smart_view_sla_risk server/tests/test_ticket_form_packs.py::test_validate_form_pack_schema_preserves_request_template_process_context server/tests/test_web_admin_api.py::test_web_admin_forms_save_accepts_request_template_process_context -q --tb=short` -> passed, 12 tests.
- `python -m pytest pc_agent/tests/test_chat_panel_helpers.py -q --tb=short` -> passed, 28 tests.
- `pnpm --dir webapp exec vitest run src/pages/settings/index.test.tsx src/features/forms-builder/forms-builder-panel.test.tsx src/pages/tickets/detail-page.test.tsx` -> passed, 23 tests.
- `python -m pytest scripts/test_navigation_catalog.py -q --tb=short` -> passed, 10 tests.
- `python -m pytest server/tests/test_web_settings_api.py server/tests/test_web_support_api.py server/tests/test_ticket_form_packs.py server/tests/test_web_admin_api.py::test_web_admin_forms_save_accepts_request_template_process_context server/tests/test_web_admin_api.py::test_web_admin_forms_current_returns_typed_payload -q --tb=short` -> passed, 47 tests.
- `pnpm --dir webapp run build` -> passed.
- `python scripts/verify_workspace.py` -> passed.
- After final localization cleanup:
  - `python -m pytest pc_agent/tests/test_chat_panel_helpers.py -q --tb=short` -> passed, 28 tests.
  - `pnpm --dir webapp exec vitest run src/pages/tickets/detail-page.test.tsx src/pages/settings/index.test.tsx src/features/forms-builder/forms-builder-panel.test.tsx` -> passed, 23 tests.
  - `python -m pytest server/tests/test_web_settings_api.py server/tests/test_web_support_api.py::test_web_support_queue_applies_smart_view_sla_risk -q --tb=short` -> passed, 10 tests.
  - `pnpm --dir webapp run build` -> passed.

Live verification for slice 9:

- Released commit `d0fdfba` with `python scripts/release_server_to_remote.py --allow-local-dirty --skip-ci-check --leave-running`.
- Release flow ran `verify_workspace.py`, bootstrapped the web toolchain, built the webapp bundle, deployed the committed Git state to `/var/chat_bot/pc_client`, applied migrations and started control/server.
- Remote smoke passed: `GET /api/health` -> 200.
- Browser signoff passed with `pnpm --dir webapp run check:remote:webapp -- --base-url http://192.168.100.17:8666`; login, admin/support routing and webapp fallback routes loaded without page/console errors.
- Live API settings check confirmed `ticket_settings.request_templates` count is `9`, first template has `form_schema_id=breakage_form`, `workflow_profile_id=incident`, and the process schema uses Russian deadline wording `Сроки ответа и решения`.
- Live smart-view check confirmed queue filters expose `Риск по сроку ответа` and `Риск внутренней очереди`.
- Artifact written to `artifacts/live_checks/request_template_settings_live_20260430.json`.

Previous current step:

Slice 8 implemented and live-verified: executable notification policy and backend smart views.

Implemented behavior:

- `request_template.notification_policy` controls in-app notification recipients per event while keeping existing user notification preferences (`mute_internal`, `muted_event_types`, `suppress_self`) as the final per-recipient filter.
- Policy events use `on_<event_type>` blocks such as `on_status_changed`, `on_sla_breach`, `on_requester_replied`, with recipient toggles for requester, assignee, queue and watchers.
- Typed support queue exposes backend smart views as saved operational filters (`sla_risk`, `ola_risk`, `unassigned`, `waiting_approval`, requester replies and stale waits) through the existing `/api/web/support/queue` payload.
- Smart views filter ticket payloads server-side and are queryable without adding a visual builder in this slice.

Changed files for slice 8:

- `server/tickets/notification_service.py`
- `server/tickets/smart_views.py`
- `server/tickets/form_catalog.py`
- `server/web_api/dto/admin.py`
- `server/web_api/admin_handlers.py`
- `server/web_api/dto/support.py`
- `server/web_api/support_handlers.py`
- `server/tests/test_stage8.py`
- `server/tests/test_ticket_form_packs.py`
- `server/tests/test_web_admin_api.py`
- `server/tests/test_web_support_api.py`
- `server/docs/CODEMAP.md`
- `docs/QUICK_LOOKUP.md`
- `scripts/navigation_catalog.py`
- `PLANS.md`

Previous current step:

Slice 7 implemented and live-verified: executable visibility policy for ticket payloads.

Implemented behavior:

- `server/tickets/visibility_policy.py` reads `custom_fields.request_template.visibility_policy`.
- `public_status_mapping` maps internal workflow statuses to requester-facing labels without changing internal `ticket.status`.
- `ticket_to_dict(..., visibility="requester")` and `_ticket_payload(..., visibility="requester")` redact configured/default requester-hidden fields such as `root_cause`, `ola`, `latest_operations`, raw diagnostics and assignment internals.
- Support/internal payloads keep internal fields while exposing `public_status`, `public_status_label`, visibility source and requester/support-visible field metadata.
- Typed support queue/detail payloads now include public status fields; detail includes visibility metadata for UI consumers.

Changed files for slice 7:

- `server/tickets/visibility_policy.py`
- `server/app/api/serializers.py`
- `server/tickets/handlers.py`
- `server/tickets/public_ticket_handlers.py`
- `server/web_api/dto/support.py`
- `server/web_api/support_handlers.py`
- `server/tests/test_ticket_workflow_visibility.py`
- `server/tests/test_web_support_api.py`
- `server/docs/CODEMAP.md`
- `docs/QUICK_LOOKUP.md`
- `scripts/navigation_catalog.py`
- `PLANS.md`

Previous current step:

Slice 6 implemented and live-verified: diagnostic policy and evidence/passport binding.

Implemented behavior:

- `server/tickets/diagnostic_policy.py` reads `custom_fields.request_template.diagnostic_policy` / legacy `diagnostics`.
- When `attach_results.as_evidence=true` and `attach_results.to_passport` is not disabled, passport generation materializes terminal ticket operations as `ticket_evidence_items`.
- Generated evidence uses `evidence_type=diagnostic_result`, `source_ref=operation:<operation_id>`, operation title/summary and the passport actor as `created_by`.
- Evidence creation is idempotent per ticket/evidence type/source operation, so passport refresh does not create duplicates.
- Device-level operation fallback never materializes evidence from another ticket; only operations owned by the current ticket can become diagnostic evidence.
- Ticket status remains independent from operation status: operations still feed automated checks and now can become closure/passport evidence only through policy.

Changed files for slice 6:

- `server/tickets/diagnostic_policy.py`
- `server/tickets/passport_service.py`
- `server/tests/test_ticket_passport_service.py`
- `server/docs/CODEMAP.md`
- `server/docs/DIAGNOSTIC_PLAYBOOKS.md`
- `docs/QUICK_LOOKUP.md`
- `scripts/navigation_catalog.py`
- `PLANS.md`

Previous current step:

Slice 5 implemented and live-verified: workflow transition gates.

Implemented behavior:

- Workflow profile `transitions` remain backward-compatible with the existing `{from_status: [to_status]}` shape.
- Saved profiles can also define structured transition entries such as `{to, allowed_roles, required_fields}`.
- The normalized profile keeps the transition map for existing UI/API consumers and stores gate metadata under `transition_gates`.
- `TicketWorkflowService.apply_status_transition(...)` enforces gate `required_fields` against the prospective ticket update plus existing ticket fields/custom fields.
- `allowed_roles` supports direct actor roles and semantic `assignee`, `requester`, `queue_lead`, `system`.
- Blocked typed support status actions return `WORKFLOW_POLICY_BLOCKED`; successful transitions record `workflow_transition_gate` in the `status_changed` event payload.

Changed files for slice 5:

- `server/tickets/workflow_profiles.py`
- `server/tickets/workflow_service.py`
- `server/web_api/dto/settings.py`
- `server/web_api/support_handlers.py`
- `server/tests/test_ticket_workflow_profiles.py`
- `server/tests/test_web_support_api.py`

Previous current step:

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
- `python -m pytest server/tests/test_ticket_workflow_profiles.py server/tests/test_web_support_api.py::test_web_support_status_action_reports_workflow_gate_block server/tests/test_web_settings_api.py::test_web_settings_can_save_workflow_profiles -q` -> passed, 12 tests.
- `python -m pytest server/tests/test_ticket_workflow_profiles.py server/tests/test_web_support_api.py::test_web_support_status_action_reports_workflow_gate_block server/tests/test_web_settings_api.py::test_web_settings_can_save_workflow_profiles server/tests/test_ticket_routing_policy.py server/tests/test_ticket_queue_routing_contracts.py server/tests/test_ticket_priority_policy.py server/tests/test_ticket_sla_calendar.py server/tests/test_ticket_approval_policy.py server/tests/test_ticket_closure_policy.py -q` -> passed, 40 tests.
- `python -m pytest server/tests/test_ticket_passport_service.py -v --tb=short` -> passed, 6 tests.
- `python -m pytest server/tests/test_ticket_passport_service.py server/tests/test_ticket_passport_web_api.py server/tests/test_ticket_closure_policy.py -q --tb=short` -> passed, 14 tests.
- `python -m pytest server/tests/test_ticket_workflow_visibility.py server/tests/test_web_support_api.py -q --tb=short` -> passed, 28 tests.
- `python -m pytest server/tests/test_ticket_workflow_visibility.py server/tests/test_web_support_api.py server/tests/test_ticket_create_contracts.py -q --tb=short` -> passed, 38 tests.
- `python -m pytest server/tests/test_stage8.py server/tests/test_ticket_form_packs.py::test_validate_form_pack_schema_preserves_request_template_process_context server/tests/test_web_admin_api.py::test_web_admin_forms_save_accepts_request_template_process_context server/tests/test_web_support_api.py::test_web_support_queue_returns_typed_scope_and_filter_payload server/tests/test_web_support_api.py::test_web_support_queue_applies_smart_view_sla_risk -q --tb=short` -> passed, 11 tests.
- `python -m pytest server/tests/test_ticket_workflow_visibility.py server/tests/test_web_support_api.py server/tests/test_ticket_create_contracts.py server/tests/test_stage8.py server/tests/test_web_admin_api.py::test_web_admin_forms_save_accepts_request_template_process_context server/tests/test_ticket_form_packs.py::test_validate_form_pack_schema_preserves_request_template_process_context -q --tb=short` -> passed, 48 tests.
- `python scripts/verify_workspace.py` -> passed.

Live:

- Released commit `3e1a67d` with `python scripts/release_server_to_remote.py --allow-local-dirty --skip-ci-check --leave-running`.
- Release flow ran `verify_workspace.py`, bootstrapped the web toolchain, built the webapp bundle, deployed the committed Git state to `/var/chat_bot/pc_client`, applied migrations and started control/server.
- Remote smoke passed: `GET /api/health` -> 200.
- Live notification/smart-view check created transactional queue `live_smart_0a5891ee2b` and uncommitted ticket `dc5d603f-b394-494f-b3ad-423886047d4f` with `request_template.notification_policy.on_status_changed`.
- Runtime `notify_ticket_event` created notifications only for `["assignee-live", "requester-live"]`, excluding queue members and watcher by policy while keeping preferences in the path.
- Runtime `smart_view=sla_risk` matched only `["Live SLA risk"]` among the transactional live tickets; safe and closed tickets were excluded; the transaction was rolled back after verification.
- Final remote status/smoke passed, then server was stopped: `active=inactive`.

- Released commit `57d31dc` with `python scripts/release_server_to_remote.py --allow-local-dirty --skip-ci-check --leave-running`.
- Release flow ran `verify_workspace.py`, bootstrapped the web toolchain, built the webapp bundle, deployed the committed Git state to `/var/chat_bot/pc_client`, applied migrations and started control/server.
- Remote smoke passed: `GET /api/health` -> 200.
- Live visibility-policy check created uncommitted transactional ticket `6d517cf4-8773-4ca9-ab9f-025fff5b7fa2` with `request_template.visibility_policy.public_status_mapping.waiting_on_internal_team = "Заявка в работе"`.
- Runtime payloads resolved `public_status = in_work` and `public_status_label = "Заявка в работе"` for both support and requester views without changing internal `ticket.status`.
- Support view kept internal `root_cause` and `ola`; requester view redacted both and preserved requester-visible field metadata `["public_status", "public_status_label", "expected_due_at"]`; the transaction was rolled back after verification.
- Final remote status/smoke passed, then server was stopped: `active=inactive`.

- Released commit `cd24d39` with `python scripts/release_server_to_remote.py --allow-local-dirty --skip-ci-check --leave-running`.
- Release flow ran `verify_workspace.py`, built the webapp bundle, deployed the committed Git state to `/var/chat_bot/pc_client`, applied migrations and started control/server.
- Remote smoke passed: `GET /api/health` -> 200.
- Live diagnostic-policy check created an uncommitted transactional ticket `17d28afe-92ba-4164-9d6e-649a46a6e7a5` with `request_template.diagnostic_policy.attach_results.as_evidence=true`, a terminal operation `7f364cda-a246-4317-a2bc-e7c44a52ca4d`, generated a passport, and observed `evidence_count=1` with `source_ref=operation:7f364cda-a246-4317-a2bc-e7c44a52ca4d`; the transaction was rolled back after verification.
- Final remote status/smoke passed, then server was stopped: `active=inactive`.

- Released commit `f295abe` with `python scripts/release_server_to_remote.py --allow-local-dirty --skip-ci-check --leave-running`.
- Remote smoke passed: `GET /api/health` -> 200.
- Live workflow-gate check created ticket `2cbee566-ed84-432e-b49a-87c86f96f0e4` with temporary ticket type `live_workflow_3b5b312584`.
- Transition `in_progress -> resolved` as support with `resolution_code=fixed_remote` was blocked with `workflow_profile transition gate blocked by allowed_roles`.
- Transition `in_progress -> resolved` as admin without `resolution_code` was blocked with `workflow_profile transition gate missing required_fields: resolution_code`.
- Transition `in_progress -> resolved` as admin with `resolution_code=fixed_remote` succeeded; final status is `resolved`, and the event payload contains `workflow_transition_gate` with `allowed_roles=["admin"]` and `required_fields=["resolution_code"]`.
- Browser check opened `http://192.168.100.17:8666/admin`, logged in with `op1`, and loaded the real support ticket queue. The only browser console error was the expected 401 from a first wrong login attempt.
- Final remote status confirmed the server was stopped: `active=inactive`.

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

1. Finish slice 9 implementation from the failing tests.
2. Run focused backend, web and agent tests, then `python scripts/verify_workspace.py`.
3. Build/release web assets, deploy through project scripts, perform live API/browser verification, then stop the remote server.
