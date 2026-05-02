# PLANS.md

## 2026-05-01 Service desk модель: доведение соответствия с 72% до 100%

Status: Slice 10a is locally verified: diagnostic policy runtime now classifies terminal operation/result payloads into `diagnostic_result` facts and executes `reroute_by_result` queue handoff without changing ticket workflow status. Baseline audit was backend/runtime about 76%, server UI about 70%, agent GUI about 73%, overall configurable service desk maturity about 72%. After completed Slices 1-6 the working estimate was backend/runtime about 88%, server UI about 74%, agent GUI about 73%, overall about 84%. After Slice 7a release verification the working estimate was backend/runtime about 89%, server UI about 76%, agent GUI about 73%, overall about 85%. After Slice 7b release/browser signoff the working estimate was backend/runtime about 90%, server UI about 77%, agent GUI about 73%, overall about 86%. After Slice 8a release/browser signoff the working estimate was backend/runtime about 91%, server UI about 77%, agent GUI about 73%, overall about 87%. After Slice 8b release/browser signoff the working estimate is backend/runtime about 92%, server UI about 77%, agent GUI about 73%, overall about 88%. After Slice 8c release/browser signoff the working estimate is backend/runtime about 93%, server UI about 77%, agent GUI about 73%, overall about 89%. After Slice 9a release/browser signoff the working estimate is backend/runtime about 94%, server UI about 77%, agent GUI about 73%, overall about 90%. After Slice 9b release/browser signoff the working estimate is backend/runtime about 95%, server UI about 79%, agent GUI about 73%, overall about 91%. After Slice 10a local verification the working estimate is backend/runtime about 96%, server UI about 79%, agent GUI about 73%, overall about 92%. The remaining plan targets the full chain `request_template -> form -> workflow -> priority -> SLA/OLA -> routing -> approvals -> diagnostics -> closure -> reporting/passport`.

### Goal

Довести проект до полноценной service desk модели, где пользователь выбирает понятный шаблон обращения, сервер хранит версионируемые политики как отдельные сущности, runtime исполняет эти политики без ручных обходов, а администратор может настраивать процесс без редактирования больших JSON-блоков.

### Scope

- Backend domain/model: `server/app/db/models.py`, migrations in `server/app/db/migrations/versions/`, `server/app/repos/helpdesk_policy_repo.py`, `server/tickets/helpdesk_policy_runtime.py`.
- Ticket runtime: `server/tickets/create_flow.py`, `server/tickets/form_catalog.py`, `server/tickets/workflow_profiles.py`, `server/tickets/workflow_service.py`, `server/tickets/priority_policy.py`, `server/tickets/sla_service.py`, `server/tickets/ola_service.py`, `server/tickets/routing_service.py`, `server/tickets/approval_policy.py`, `server/tickets/closure_policy.py`, `server/tickets/diagnostic_policy.py`, `server/tickets/notification_service.py`, `server/tickets/visibility_policy.py`, `server/tickets/passport_service.py`, `server/tickets/smart_views.py`.
- Typed web API/UI: `server/web_api/admin_handlers.py`, `server/web_api/settings_handlers.py`, `server/web_api/dto/admin.py`, `webapp/src/features/forms-builder/*`, `webapp/src/features/settings/*`, `webapp/src/pages/settings/index.tsx`, `webapp/src/pages/tickets/detail-page.tsx`.
- Agent GUI consumer: `pc_agent/ui_gui/chat_panel.py`, `pc_agent/ui_gui/server_api.py`.
- Docs/navigation: `server/docs/TICKET_SYSTEM.md`, `server/docs/REQUEST_FORM_BUILDER.md`, `server/docs/CODEMAP.md`, `pc_agent/docs/CODEMAP.md`, `docs/QUICK_LOOKUP.md`, `scripts/navigation_catalog.py`.

### Constraints

- Все изменения делать только в локальной копии `C:\Users\admin-2\CodexProjects\pc_client`.
- Для нового `webapp/` перед frontend-командами запускать `python scripts/bootstrap_web_toolchain.py`.
- Не ломать текущий `request_forms` compatibility path: старые packs и `form_key` должны продолжать работать.
- Версионирование политик обязательно: старый тикет должен сохранять snapshot шаблона, но runtime для lifecycle-действий может применять active effective policies там, где это уже предусмотрено.
- Пользовательские строки в агенте и web UI должны быть на русском и без raw SLA/OLA-жаргона для requester.
- Для каждого среза: сначала focused regression tests, затем реализация, затем `python scripts/verify_workspace.py`; для UI-срезов добавлять Vitest/browser signoff.

### Current State

- Completed Slice 1-6 summary: versioned `ticket_types`, `form_schemas`/fields/conditions, explicit request-template policy refs/snapshots, configurable priority matrix/modifiers/manual override, policy-aware SLA lifecycle, and policy-aware OLA lifecycle/breach detection are implemented, tested, committed and deployed through `0b9857d server: add policy-aware OLA runtime`.
- Active gap list starts at Slice 7a below; detailed historical verification for Slice 1-6 is intentionally removed from this active plan block to keep the plan readable.
- Уже есть inheritance `system -> ticket_type -> category -> request_template`.
- Уже исполняются routing, priority facts, workflow gates, SLA/OLA timers, approval gate, closure gate, visibility, notifications, diagnostic evidence и passport/reporting policy.
- Серверный UI `/app/admin/forms` умеет visual chain и registry publication, но часть политик ещё редактируется JSON-блоками.
- Agent GUI уже потребляет request-template-aware forms, priority fields, picker/file fields, diagnostic consent и server-backed create preview.

### Decisions Added 2026-05-02

- External escalation/recipient actions for SLA/OLA breach actions will be implemented as a shared `policy_action_dispatcher`, not inside SLA/OLA services. SLA/OLA services emit canonical policy-aware events with `breach_actions`; dispatcher resolves recipients (`assignee`, `queue_lead`, queue members, admins, explicit actors/groups), applies notification preferences/channel availability, creates delivery audit rows and keeps retry/idempotency by `(ticket_id, event_id, action_key, recipient)`.
- Structured OLA editor will be part of the admin policy editor, not the legacy queue target grid. MVP fields: ack/processing P0-P3 targets, start conditions, ack stop conditions, processing stop conditions, pause/resume conditions, breach actions, fallback queue target visibility and JSON advanced preview.
- OLA risk UI will surface as an operational smart-view slice with counts, not only as a hidden query parameter. The support queue response should expose `summary.smart_view_counts`, and React support/tickets pages should render the OLA risk count next to built-in smart views.
- The existing `web_settings` warning for calendar JSON shape is a compatibility cleanup: typed settings must accept both dict-shaped and list-shaped `weekly_hours_json` / `holidays_json` stored by historical calendar editors without falling back to an empty settings payload.

### Target Completion Criteria

- Есть отдельная управляемая сущность `ticket_type`, а не только строка/профиль workflow.
- Есть отдельный versioned реестр `form_schemas` / `form_fields` / `form_conditions`, связанный с `request_template`, с совместимостью для текущего `request_forms`.
- `request_template` ссылается на отдельные политики, а не зависит от inline JSON как основного пути.
- Priority policy поддерживает настраиваемую matrix/modifiers/manual override, а не только фиксированный вычислитель.
- SLA/OLA policies полностью покрывают calendar/start/pause/resume/stop/targets/warnings/breach actions/applies-to.
- Workflow profile настраивает statuses/transitions/allowed roles/required fields/comments/actions/logging и исполняет это в runtime.
- Approval policy умеет не только блокировать переход, но и создавать approval requests по источникам согласующих, режиму, timeout/reminder/escalation.
- Closure policy покрывает resolution code, public/internal summary, evidence, operation log, approval evidence, requester confirmation, negative feedback reopen/keep-resolved behavior, auto-close and support-facing missing requirement checklist.
- Diagnostic policy умеет suggested playbooks, consent, safe auto-run constraints, attach-to-passport/evidence и reroute-by-result.
- Notification/visibility/reporting/smart views имеют отдельные UI editors и runtime-tests.
- Админка даёт мастер настройки шаблона без обязательного ручного JSON.
- GUI агента показывает только requester-facing часть модели и всегда получает effective preview с сервера.

### Completed Slices 1-6: Registry, Runtime Policies And OLA Engine

- [x] Slice 1: versioned `ticket_types` registry, inheritance defaults, settings selectors and legacy fallback.
- [x] Slice 2: first-class `form_schemas` / `form_fields` / `form_conditions` with request-form compatibility.
- [x] Slice 3: request-template policy refs, effective resolver and ticket snapshots with policy sources.
- [x] Slice 4: configurable priority matrix/modifiers/manual override, stored priority fields and create-preview explanation.
- [x] Slice 5: policy-aware SLA start/pause/resume/stop, calendar-aware targets, warning-before and breach-action payload metadata.
- [x] Slice 6: policy-aware OLA ack/processing lifecycle, queue handoff behavior, runtime source tracking and watchdog breach events.

Verification anchor: Slice 6 was committed and deployed as `0b9857d server: add policy-aware OLA runtime`; local server tests, navigation checks, `verify_workspace.py`, remote smoke, live OLA rollback and browser signoff passed. Remaining external recipient/escalation delivery is intentionally moved to a shared dispatcher slice below, because SLA/OLA services should emit policy events rather than own channel delivery.

### Slice 7a: OLA Risk UI And Calendar Settings Cleanup

- [x] Fix `web_settings` calendar JSON compatibility so list-shaped `weekly_hours_json` / `holidays_json` does not trigger fallback payload or warning logs.
- [x] Expose support queue `summary.smart_view_counts` for built-in and published smart views, including `ola_risk`.
- [x] Add minimal React queue UI support for smart-view filters/counts so OLA risk is visible as an operational slice.
- [x] Update docs/navigation for the settings compatibility and OLA risk surfacing.
- [x] Tests: settings payload accepts list-shaped calendars; support queue returns OLA risk count and filter; web build/typecheck; browser check `/app/tickets` or `/app/admin/forms`.

Slice 7a local verification:

- RED confirmed: focused tests failed on list-shaped calendar JSON fallback and missing `summary.smart_view_counts`.
- GREEN focused: `python -m pytest server\tests\test_web_settings_api.py::test_web_settings_accepts_list_shaped_calendar_json server\tests\test_web_support_api.py::test_web_support_queue_surfaces_ola_risk_smart_view_count -q --tb=short` -> 2 passed.
- Broader local: `python -m pytest server\tests\test_web_settings_api.py server\tests\test_web_support_api.py -q --tb=short` -> 35 passed.
- Web: `pnpm --dir webapp run build` -> passed.
- Navigation/workspace: `python -m pytest scripts\test_navigation_catalog.py -q --tb=short` -> 10 passed; `python scripts\verify_workspace.py` -> passed.

### Slice 7: Workflow Profile Builder And Runtime Actions

- [x] Slice 7b: add trigger/auto transition metadata to workflow profiles, execute requester reply through configured transition before legacy fallback, and expose trigger/auto fields in the settings workflow builder.
- [ ] Extend workflow profile schema to include transition actions: notify, start/pause/stop SLA, create approval, require evidence, require public/internal comment, log fields, auto transitions.
- [ ] Add typed admin API for workflow profiles with validation and diff/audit, not only raw config save.
- [ ] Update `TicketWorkflowService` to execute configured transition actions where safe.
- [ ] Add system-triggered transitions for requester replied, approval received/rejected, auto-close due.
- [ ] Tests: allowed roles, required fields, required comments, transition actions, auto transition trigger, audit payload.
- [ ] UI: visual workflow editor for statuses/transitions/gates with safe presets for incident/service_request/access_request/change_request/consultation/problem.

Slice 7b local verification:

- RED confirmed: workflow profile tests failed on missing `WorkflowTransitionGate.trigger` / `auto`; runtime test failed on missing `TicketWorkflowService.apply_triggered_transition`; settings Vitest failed on missing `Trigger события` editor.
- GREEN focused: `python -m pytest server\tests\test_ticket_workflow_profiles.py::test_workflow_profile_accepts_auto_triggered_transition server\tests\test_ticket_workflow_profiles.py::test_workflow_triggered_transition_uses_configured_target_for_requester_reply -q --tb=short` -> 2 passed; `pnpm --dir webapp exec vitest run src/pages/settings/index.test.tsx --testNamePattern "builds workflow transition guards"` -> 1 passed.
- Handler/API regression: `python -m pytest server\tests\test_ticket_create_contracts.py::test_requester_reply_requeues_waiting_ticket server\tests\test_ticket_create_contracts.py::test_requester_reply_uses_workflow_trigger_when_profile_configured -q --tb=short` -> 2 passed.
- Broader local: `python -m pytest server\tests\test_ticket_workflow_profiles.py server\tests\test_ticket_create_contracts.py server\tests\test_web_settings_api.py -q --tb=short` -> 36 passed.
- Web/navigation/workspace: `pnpm --dir webapp exec vitest run src/pages/settings/index.test.tsx` -> 4 passed; `pnpm --dir webapp run build` -> passed; `python -m pytest scripts\test_navigation_catalog.py -q --tb=short` -> 10 passed; `python scripts\verify_workspace.py` -> passed.
- Release/live: committed as `ce680d3 server: add workflow trigger transitions`; `python scripts\release_server_to_remote.py --allow-local-dirty --skip-ci-check --leave-running --smoke-attempts 5 --smoke-delay 3` -> remote fast-forward and smoke OK; browser signoff on `http://192.168.100.17:8666/app/settings` confirmed workflow builder `Trigger события` / `Автоматический переход`; `http://192.168.100.17:8666/app/admin/observer` loaded runtime quick traces; browser console errors -> 0.

### Slice 8: Approval Requests

- [x] Slice 8a: create active `ticket_approvals` from `approval_policy` when entering waiting approval, with explicit user, form field, service owner/requester manager fallback, queue lead, security role and group identifiers.
- [x] Slice 8b: implement `approval_mode=all` execution semantics and `approval_mode=sequential` request creation semantics (`requested` first step, `pending` later steps).
- [x] Slice 8c: implement due/reminder/escalate timeout behavior and require comment on reject.
- [ ] Add requester/support UI to show pending approvals and actions.
- [ ] Tests: approval request creation, source resolution fallback, sequential mode, rejection transition, timeout reminder/escalation, passport logging.

Slice 8a local verification:

- RED confirmed: approval policy tests failed because entering `waiting_on_approval` changed status but created no `ticket_approvals`.
- GREEN focused: `python -m pytest server\tests\test_ticket_approval_policy.py::test_approval_policy_creates_request_when_entering_waiting_status server\tests\test_ticket_approval_policy.py::test_approval_policy_creates_request_from_form_field_source -q --tb=short` -> 2 passed.
- Fallback/idempotency: `python -m pytest server\tests\test_ticket_approval_policy.py::test_approval_policy_uses_fallback_source_without_duplicate_requests -q --tb=short` -> 1 passed.
- Broader approval suite: `python -m pytest server\tests\test_ticket_approval_policy.py -q --tb=short` -> 8 passed.
- Broader local: `python -m pytest server\tests\test_ticket_approval_policy.py server\tests\test_ticket_workflow_profiles.py server\tests\test_ticket_passport_service.py -q --tb=short` -> 30 passed; `python -m pytest scripts\test_navigation_catalog.py -q --tb=short` -> 10 passed; `python scripts\verify_workspace.py` -> passed.
- Release/live: committed as `85c016b server: create approval requests from policy`; `python scripts\release_server_to_remote.py --allow-local-dirty --skip-ci-check --leave-running --smoke-attempts 5 --smoke-delay 3` -> remote fast-forward and smoke OK; browser signoff on `http://192.168.100.17:8666/admin` loaded admin workspace and `http://192.168.100.17:8666/app/admin/observer` loaded runtime quick traces; browser console errors -> 0.

Slice 8b local verification:

- RED confirmed: sequential mode created both approvers as parallel `requested`; all-mode execution test showed the need to isolate inline policy from active registry overrides in the regression setup.
- GREEN focused: `python -m pytest server\tests\test_ticket_approval_policy.py::test_approval_policy_sequential_mode_creates_one_requested_step server\tests\test_ticket_approval_policy.py::test_approval_policy_all_mode_requires_every_approval -q --tb=short` -> 2 passed.
- Broader approval suite: `python -m pytest server\tests\test_ticket_approval_policy.py -q --tb=short` -> 10 passed.
- Broader local: `python -m pytest server\tests\test_ticket_approval_policy.py server\tests\test_ticket_workflow_profiles.py server\tests\test_ticket_passport_service.py -q --tb=short` -> 32 passed; `python -m pytest scripts\test_navigation_catalog.py -q --tb=short` -> 10 passed; `python scripts\verify_workspace.py` -> passed.
- Release/live: committed as `cdc0d3b server: add approval mode semantics`; `python scripts\release_server_to_remote.py --allow-local-dirty --skip-ci-check --leave-running --smoke-attempts 5 --smoke-delay 3` -> remote fast-forward and smoke OK; browser signoff on `http://192.168.100.17:8666/admin` loaded admin inventory and `http://192.168.100.17:8666/app/admin/observer` showed `Runtime: ok`, hot traces and dangerous flows; browser console errors -> 0.

Slice 8c local verification:

- RED confirmed: focused tests failed because approval timeout processing returned `0` instead of reminder/escalation/timeout events, and `require_comment_on_reject=true` did not block a rejected transition without a reason.
- GREEN focused: `python -m pytest server\tests\test_ticket_approval_policy.py::test_approval_policy_timeout_runtime_emits_reminder_escalation_and_timeout server\tests\test_ticket_approval_policy.py::test_approval_policy_requires_comment_on_reject_transition -q --tb=short` -> 2 passed.
- Broader approval suite: `python -m pytest server\tests\test_ticket_approval_policy.py -q --tb=short` -> 12 passed.
- Broader local: `python -m pytest server\tests\test_ticket_approval_policy.py server\tests\test_ticket_workflow_profiles.py server\tests\test_ticket_passport_service.py server\tests\test_ticket_sla_calendar.py -q --tb=short` -> 42 passed; `python -m pytest scripts\test_navigation_catalog.py -q --tb=short` -> 10 passed; `python scripts\verify_workspace.py` -> passed.
- Release/live: committed as `4a30a49 server: add approval timeout runtime`; `python scripts\release_server_to_remote.py --allow-local-dirty --skip-ci-check --leave-running --smoke-attempts 5 --smoke-delay 3` -> remote fast-forward and smoke OK; browser signoff on `http://192.168.100.17:8666/admin` loaded admin inventory and `http://192.168.100.17:8666/app/admin/observer` showed `Runtime: ok`, hot traces and dangerous flows; browser console errors -> 0.

### Slice 9: Closure Policy Completion

- [x] Slice 9a: expand closure policy runtime to support nested `before_resolved`, `evidence`, `requester_confirmation`, `allowed_resolution_codes`.
- [x] Slice 9a: enforce operation log evidence when diagnostic/remediation modules were used.
- [x] Slice 9a: enforce approval evidence when approval policy was used.
- [x] Slice 9a: implement requester confirmation policy and auto-close-after-days as policy-driven, not just global defaults.
- [x] Slice 9a tests: resolution code whitelist, public/internal summary requirements, P0/P1 evidence, module evidence, approval evidence and auto-close timer.
- [x] Slice 9b: requester reject/reopen behavior reads `requester_confirmation.reopen_on_negative_feedback` instead of always using legacy `assigned`.
- [x] Slice 9b: support ticket detail exposes `actions.closure_requirements`, and the close/resolve panel shows exactly which closure requirements are missing.

Slice 9a local verification:

- RED confirmed: new focused tests failed on missing nested `allowed_resolution_codes`, operation-log evidence, approval evidence, requester-confirmation metadata and policy auto-close execution.
- GREEN focused: `python -m pytest server\tests\test_ticket_closure_policy.py -q --tb=short` -> 10 passed.
- Broader local: `python -m pytest server\tests\test_ticket_closure_policy.py server\tests\test_ticket_workflow_profiles.py server\tests\test_ticket_passport_service.py server\tests\test_ticket_create_contracts.py -q --tb=short` -> 43 passed.
- Navigation/workspace: `python -m pytest scripts\test_navigation_catalog.py -q --tb=short` -> 10 passed; `python scripts\verify_workspace.py` -> passed.
- Release/live: committed as `73eefbf server: complete closure policy runtime`; `python scripts\release_server_to_remote.py --allow-local-dirty --skip-ci-check --leave-running --smoke-attempts 5 --smoke-delay 3` -> remote fast-forward and smoke OK; browser signoff on `http://192.168.100.17:8666/admin` loaded admin inventory and `http://192.168.100.17:8666/app/admin/observer` showed `Runtime: ok`; browser console errors -> 0; remote server stopped after verification.

Slice 9b local verification so far:

- RED confirmed: focused backend tests failed because requester reject ignored `reopen_on_negative_feedback`, support detail lacked `actions.closure_requirements`, and typed support status always created requester confirmation even when closure policy set `required=false`; Vitest failed because the resolve panel had no missing-requirements checklist.
- GREEN focused: `python -m pytest server\tests\test_ticket_create_contracts.py::test_resolution_confirmation_reject_requeues_ticket server\tests\test_ticket_create_contracts.py::test_resolution_confirmation_reject_respects_reopen_policy server\tests\test_ticket_create_contracts.py::test_resolution_confirmation_reject_can_keep_resolved_by_policy server\tests\test_web_support_api.py::test_web_support_status_action_returns_typed_result_and_updates_ticket server\tests\test_web_support_api.py::test_web_support_resolved_status_respects_confirmation_required_false server\tests\test_web_support_api.py::test_web_support_detail_exposes_closure_policy_requirements -q --tb=short` -> 6 passed.
- GREEN UI focused: `pnpm --dir webapp exec vitest run src/pages/tickets/detail-page.test.tsx --testNamePattern "missing closure requirements|status transition"` -> 2 passed.
- Broader sequential backend: `python -m pytest server\tests\test_ticket_closure_policy.py -q --tb=short` -> 10 passed; `python -m pytest server\tests\test_web_support_api.py -q --tb=short` -> 27 passed; `python -m pytest server\tests\test_ticket_create_contracts.py -q --tb=short` -> 13 passed.
- Web/navigation/workspace: `pnpm --dir webapp exec vitest run src/pages/tickets/detail-page.test.tsx` -> 12 passed; `pnpm --dir webapp run build` -> passed; `python -m pytest scripts\test_navigation_catalog.py -q --tb=short` -> 10 passed; `python scripts\verify_workspace.py` -> passed.
- Note: one parallel combined backend attempt failed with asyncpg connection-closed/TRUNCATE interference because several pytest processes shared the same test DB; sequential reruns above passed.
- Release/live: committed as `81797cb server: surface closure requirements`; `python scripts\release_server_to_remote.py --allow-local-dirty --skip-ci-check --leave-running --smoke-attempts 5 --smoke-delay 3` -> remote fast-forward, webapp rebuild and smoke OK; browser signoff on `http://192.168.100.17:8666/admin`, `/app/admin/observer` and `/app/tickets` loaded successfully; browser console errors -> 0; remote server stopped after verification.

### Slice 10: Diagnostic Policy Completion

- [x] Slice 10a: classify terminal diagnostic/tool results into `diagnostic_result` facts and execute `diagnostic_policy.reroute_by_result` without changing `ticket.status`.
- [ ] Add `diagnostic_policy` runtime for suggested playbooks, safe auto-run checks, consent requirements and attach results.
- [x] Keep invariant: `ticket.status` remains workflow status; operation status carries diagnostic running/succeeded/failed.
- [x] Add result classification contract (`DNS_FAIL`, `HTTP_500`, `TLS_CERT_INVALID`, etc.) from terminal operation/result payloads to routing facts.
- [ ] Tests: consent required/denied/granted, auto-run only for allowed priority/online agent, evidence attachment, reroute by diagnostic result, no ticket status misuse.
- [ ] UI: admin diagnostic editor and support ticket automation panel show suggested playbooks and consent/evidence behavior.

Slice 10a local verification so far:

- RED confirmed: `server/tests/test_ticket_diagnostic_policy.py` initially failed because `apply_diagnostic_result_policy` did not exist.
- GREEN focused: `python -m pytest server\tests\test_ticket_diagnostic_policy.py -q --tb=short` -> 2 passed.
- Broader local: `python -m pytest server\tests\test_ticket_diagnostic_policy.py server\tests\test_ticket_passport_service.py server\tests\test_p0_workbench_update_contracts.py::test_tool_call_command_result_creates_ticket_event_and_links_artifacts -q --tb=short` -> 10 passed.
- Navigation/workspace: `python -m pytest scripts\test_navigation_catalog.py -q --tb=short` -> 10 passed; `python scripts\verify_workspace.py` -> passed.

### Slice 11: Notification And Visibility Policy Completion

- [ ] Expand notification policy events: created, assigned, waiting_user, requester_replied, SLA warning/breach, resolved, closed, approval events, diagnostic completion.
- [ ] Add channel configuration validation for web/email/telegram/vk_teams/provider channels.
- [ ] Ensure preferences remain final per-recipient filter after policy selection.
- [ ] Expand visibility policy to support field-level requester/support views, public status mapping, raw diagnostics redaction, OLA hiding, passport export visibility.
- [ ] Tests: each notification group, channel audit, requester redaction, support-visible metadata, public status mapping.
- [ ] UI: structured notification/visibility editors with preview for requester vs support.

### Slice 12: Reporting And Passport Policy Completion

- [ ] Expand reporting policy editor/runtime for required sections, evidence package, action package, related objects, export visibility, report tags and knowledge draft hints.
- [ ] Add passport validation before closure when policy requires official dossier.
- [ ] Add deterministic section coverage report: which required facts are missing before publish/print.
- [ ] Tests: required sections, hidden internal sections, diagnostic evidence inclusion, approval/action/related object package, knowledge draft source.
- [ ] UI: support passport tab shows policy requirements, missing facts and export preview.

### Slice 13: Smart Views As Configurable Operational Queues

- [ ] Make custom smart views fully executable for filters used in target model: SLA risk, OLA risk, unassigned, waiting approval, stale waits, diagnostics failed, requester replied, mass incident candidates.
- [ ] Add validation for smart view filters/sorts/columns at publication time.
- [ ] Add UI builder for smart view filters instead of raw JSON only.
- [ ] Tests: each builtin smart view, published custom filter, invalid filter rejection, support queue counters.

### Slice 14: Server Admin UX To Remove JSON Dependency

- [ ] Convert policy editors in `/app/admin/forms` from raw JSON-first to structured controls for priority, SLA, OLA, routing, approvals, diagnostics, closure, visibility, notifications, reporting.
- [ ] Keep advanced JSON preview/edit behind explicit advanced mode with validation/diff.
- [ ] Add template wizard screens: Основное, Классификация, Форма, Процесс, Приоритет, Роутинг, SLA/OLA, Согласования, Диагностика, Закрытие, Видимость/Уведомления, Паспорт/Отчётность.
- [ ] Add "publish impact preview": what templates/ticket types/categories will be affected by policy publication.
- [ ] Tests: Vitest coverage for each structured editor, publish-from-form, policy publish/diff/deactivate/rollback, smart view publish.
- [ ] Browser signoff: `pnpm --dir webapp run check:remote:webapp -- --base-url http://192.168.100.17:8666` after deploy.

### Slice 15: Agent GUI Final Consumer Alignment

- [ ] Ensure agent never exposes internal process choices to requester: no direct ticket_type/priority/SLA policy selection unless template says fields are visible.
- [ ] Agent create preview must always call server preview when available and show effective queue/approval/diagnostics/deadlines.
- [ ] Agent must handle schema/policy versions in cached form pack and refresh when server version changes.
- [ ] Add requester-safe rendering of public status, expected due dates and passport/result summary after create.
- [ ] Tests: cached pack refresh, server-preview fallback, hidden internal fields, dynamic required fields, diagnostic consent, file/picker fields.
- [ ] Live GUI smoke with remote server and current published templates.

### Slice 16: Migration, Backfill And Compatibility

- [ ] Add migration/backfill from current default `request_forms` pack into `request_templates`, `form_schemas` and initial policy rows.
- [ ] Add idempotent admin command/API to republish legacy forms into registry.
- [ ] Add compatibility tests for old clients sending only `form_key`, old packs without priority fields, and tickets created before registry.
- [ ] Add data-quality report: templates missing workflow/priority/routing/SLA/closure policies.
- [ ] Docs: operator migration steps and rollback path.

### Slice 17: Verification And Release Gates

- [ ] Local baseline: `python scripts/verify_workspace.py`.
- [ ] Server focused: `python -m pytest server/tests/test_helpdesk_policy_registry.py server/tests/test_ticket_form_packs.py server/tests/test_ticket_priority_policy.py server/tests/test_ticket_routing_policy.py server/tests/test_ticket_sla_calendar.py server/tests/test_ticket_approval_policy.py server/tests/test_ticket_closure_policy.py server/tests/test_ticket_passport_service.py server/tests/test_web_support_api.py server/tests/test_web_settings_api.py -q --tb=short`.
- [ ] Agent focused: `python -m pytest pc_agent/tests/test_chat_panel_helpers.py pc_agent/tests/test_ticket_api_client_attachments.py -q --tb=short`.
- [ ] Web focused: `pnpm --dir webapp exec vitest run src/features/forms-builder/forms-builder-panel.test.tsx src/pages/settings/index.test.tsx src/pages/tickets/detail-page.test.tsx`.
- [ ] Remote deploy smoke through `python scripts/release_server_to_remote.py` and `python scripts/manage_remote_stack.py smoke server`.
- [ ] Browser signoff at `http://192.168.100.17:8666/admin`; for admin UI changes inspect `/app/admin/forms`, `/app/settings`, `/app/tickets/:ticketId`.
- [ ] Stop remote server after checks unless explicitly asked to keep it running: `python scripts/manage_remote_stack.py stop server`.

### Handoff

Recommended execution order: Slices 1-3 establish the missing canonical model; Slices 4-13 complete runtime policy behavior; Slices 14-15 make the model usable in server UI and agent GUI; Slices 16-17 harden migration and release. Do not start with UI-only polish before ticket type/form schema/policy references are stable, otherwise the admin surface will encode temporary shapes.

## 2026-04-30 ПК-агент: создание обращений по целевой helpdesk-модели

Status: план срезов 1-8 выполнен, локально проверен, закоммичен и проверен на Linux стенде. Старый серверный helpdesk policy plan завершён и убран из актуального рабочего плана. Текущая фактическая готовность ПК-агента к целевой модели после registry/file fields: функционально около 91-93%, GUI около 80-82%.

## 2026-05-01 ПК-агент: UX формы, post-create процесс и release

Status: срезы 9-11 выполнены: UX формы и post-create процесс реализованы, агентская версия поднята до `3.1.25`, Windows release собран, загружен на сервер, canary на launcher-managed Windows устройстве подтверждён handshake, stable rollout policy `windows_amd64` назначен на `3.1.25`. Текущая готовность: функционально 96%, GUI 90%.

### Goal

Довести пользовательский мастер создания обращения в ПК-агенте до рабочего UX-уровня: нормальные date/datetime controls, управляемое file-поле, понятный post-create summary по процессу и более цельный предпросмотр выбранного шаблона до отправки. После проверки собрать и выкатить agent release через штатный update flow.

### Current Slice 9: form field UX and process summaries

- [x] RED: `date` и `datetime` поля в `TicketDynamicFieldsWidget` должны рендериться нативными Qt controls и возвращать нормализованные значения.
- [x] RED: `file` поле должно уметь заменить и очистить файл; обязательность должна снова срабатывать после очистки.
- [x] RED: helper post-create summary должен показывать очередь/исполнителя, следующий шаг, согласование, диагностику, сроки ответа/решения и паспорт без raw SLA.
- [x] GREEN: реализовать field controls, file clear/replace and post-create summary.
- [x] GREEN: встроить process summary в wizard success/status and modal success dialog.
- [x] Обновить `pc_agent/docs/CODEMAP.md`, `docs/QUICK_LOOKUP.md`, `PLANS.md`.
- [x] Прогнать focused tests, runtime tests, `python scripts/verify_workspace.py`.

### Planned Slice 10: visual wizard polish

- [x] Сделать step 2/4 более цельным: описание шаблона, компактные блоки "куда попадёт", "что потребуется", "когда ответят/решат", "диагностика/паспорт".
- [x] Убрать перегруз в preview label: разделить summary на структурированные строки/блоки, сохранить русские пользовательские формулировки.
- [x] Проверить GUI live через isolated local agent.

### Planned Slice 11: agent release and canary

- [x] Обновить версию агента, если меняется распространяемый build.
- [x] Собрать Windows release штатным `pc_agent/build_windows_release_v2.py`.
- [x] Загрузить build на сервер, назначить canary, проверить handshake/update diagnostics/UI.
- [x] Зафиксировать результаты и остаточные риски.

Verification:

- `python -m pytest pc_agent/tests/test_chat_panel_helpers.py pc_agent/tests/test_ticket_api_client_attachments.py pc_agent/tests/test_ui_api_server_shutdown.py pc_agent/tests/test_runtime_logging.py -q --tb=short` -> passed, 60 tests.
- `python -m pytest scripts/test_navigation_catalog.py -q --tb=short` -> passed, 10 tests.
- `python -m pytest pc_agent/tests/ -q --tb=short` -> passed, 172 tests.
- `python scripts/verify_workspace.py` -> passed after `scripts/navigation_catalog.py` sync and after version bump.
- Source GUI live: `python scripts/manage_local_agent.py start codex-agent-ux-3125 --gui --ui-port 8881` -> `/ui/agent/status` returned `agent_version=3.1.25`, `ui_bridge_running=true`, `has_auth_token=true`; server connection was unavailable because remote server was stopped.
- Built launcher live: `python scripts/manage_local_agent.py start codex-agent-build-3125 --launcher --build-root pc_agent\dist --ui-port 8882` -> `/ui/agent/status` returned `agent_version=3.1.25`, `ui_bridge_running=true`, `has_auth_token=true`; instance stopped after smoke.
- `python pc_agent/build_windows_release_v2.py` -> produced `pc_agent/dist/release/windows_amd64/stable/3.1.25/pc_agent-windows_amd64-3.1.25.zip`, size `98258789`, SHA256 `C7BB83C01B2672AB31A18E9D852310A5569610453E663BF9CC7582F817DFCC50`.
- `python scripts/release_server_to_remote.py --allow-local-dirty --skip-ci-check --leave-running` -> deployed commit `194b705`, ran migrations, started remote server and passed `/api/health` smoke.
- `POST /api/agent_builds/upload` -> uploaded `windows_amd64/stable/3.1.25`, server SHA256 `c7bb83c01b2672ab31a18e9d852310a5569610453e663bf9cc7582f817dfcc50`, size `98258789`.
- Canary on `AD-MAIN` (`15c8f029-bd7d-533b-a11e-dcd6c2ff48ab`) -> operation `5d93b4fa-e50d-4a49-a397-f680f8d21d8e`, confirmed by next handshake: `agent_version=3.1.25`, `last_update_operation_status=succeeded`, `last_update_result_summary=confirmed_by_handshake:3.1.25`.
- `PATCH /api/agent_updates/rollout_policy` -> assigned `windows_amd64/stable/3.1.25`; `GET /api/agent_builds` shows `3.1.25` as `is_rollout_assigned=true`.
- Residual note: the first local `ADMIN-2` canary command was accepted by a source-run agent without launcher install layout, so it downloaded the artifact and exited with code `42` but could not apply the ZIP by itself. The local source agent was restarted from the repo at `3.1.25` and is online; use launcher-managed devices for release canary evidence.

## 2026-05-01 ПК-агент: финальный GUI-polish мастера обращений

Status: срезы 12-14 выполнены и проверены локально. Цель: довести GUI мастера до цельного пользовательского потока без изменения серверного контракта. Итоговая готовность после среза: функционально 96-97%, GUI 93-95%.

### Goal

Сделать мастер создания обращения в ПК-агенте визуально понятным для обычного пользователя: быстрый выбор шаблона, карточка выбранного сценария, компактный предпросмотр маршрута/сроков/диагностики, понятные ошибки рядом с формой и полноценный экран результата после создания.

### Scope

- `pc_agent/ui_gui/chat_panel.py`: только GUI/UX мастера, без изменения API payload contract.
- `pc_agent/tests/test_chat_panel_helpers.py`: TDD-покрытие helper-ов и структуры виджетов.
- `pc_agent/docs/CODEMAP.md`, `docs/QUICK_LOOKUP.md`, `scripts/navigation_catalog.py`, `PLANS.md`: синхронизация навигации после GUI-правок.

### Current Slice 12: template chooser and compact process cards

- [x] RED: helper для summary шаблона должен выдавать категорию, описание и человекочитаемые бейджи "нужно согласование", "может быть диагностика", "понадобятся файлы", "есть сроки ответа".
- [x] RED: wizard step 2 должен иметь поиск по шаблонам, список шаблонов и карточку выбранного шаблона, а не только одиночный dropdown.
- [x] GREEN: реализовать searchable template chooser с сохранением совместимости `form_selector.currentData()`.
- [x] GREEN: добавить карточку выбранного шаблона с описанием, категорией, бейджами и кратким preview "что будет дальше".
- [x] Проверить focused tests и docs drift.

### Planned Slice 13: field validation and attachments polish

- [x] Показывать ошибки рядом с конкретными полями, а не только общим статусом.
- [x] Сделать визуальный список вложений с размером, remove/replace и понятным состоянием пустого списка.
- [x] Добавить подсказки/help text под полями, если они приходят из схемы.

### Planned Slice 14: result screen and live GUI pass

- [x] После создания показывать отдельный результат: код, статус, очередь/исполнитель, сроки, действия "открыть обращение" / "создать ещё".
- [x] Пройти source GUI live smoke через `manage_local_agent.py`.
- [x] Прогнать runtime tests и `python scripts/verify_workspace.py`.

Verification:

- RED: `python -m pytest pc_agent/tests/test_chat_panel_helpers.py::test_ticket_create_wizard_has_searchable_template_chooser pc_agent/tests/test_chat_panel_helpers.py::test_build_request_template_card_summary_surfaces_badges_and_next_steps -q --tb=short` -> failed on missing `build_request_template_card_summary`.
- GREEN: same focused tests -> passed, 2 tests.
- RED: `python -m pytest pc_agent/tests/test_chat_panel_helpers.py::test_dynamic_fields_widget_shows_inline_required_message -q --tb=short` -> failed on missing `_error_labels`.
- GREEN: inline required-message test -> passed.
- RED: `python -m pytest pc_agent/tests/test_chat_panel_helpers.py::test_format_attachment_item_label_includes_file_size -q --tb=short` -> failed on missing `format_attachment_item_label`.
- GREEN: attachment label test -> passed.
- RED: `python -m pytest pc_agent/tests/test_chat_panel_helpers.py::test_ticket_create_wizard_has_post_create_result_panel -q --tb=short` -> failed on missing result panel.
- GREEN: result panel test -> passed.
- Focused: `python -m pytest pc_agent/tests/test_chat_panel_helpers.py pc_agent/tests/test_ticket_api_client_attachments.py -q --tb=short` -> passed, 57 tests.
- Runtime/docs: `python -m pytest pc_agent/tests/test_chat_panel_helpers.py pc_agent/tests/test_ticket_api_client_attachments.py pc_agent/tests/test_ui_api_server_shutdown.py pc_agent/tests/test_runtime_logging.py scripts/test_navigation_catalog.py -q --tb=short` -> passed, 75 tests.
- Workspace: `python scripts/verify_workspace.py` -> passed.
- Live source GUI: `python scripts/manage_local_agent.py start codex-agent-gui-polish --gui --ui-port 8883` -> `/ui/agent/status` returned `agent_version=3.1.25`, `ui_bridge_running=true`, `has_auth_token=true`; stopped through `POST /ui/agent/shutdown`, then `manage_local_agent.py status` returned stopped.

## 2026-05-01 ПК-агент: error states/result screen и release 3.1.26

Status: выполнено. Шаги 3 и 5 реализованы, `3.1.26` собрана, загружена на сервер, прошла canary на `AD-MAIN` и назначена приоритетной stable-версией для `windows_amd64`.

### Scope

- `pc_agent/ui_gui/chat_panel.py`: понятные ошибки создания/preview/вложений и более явный result panel.
- `pc_agent/version.py`: bump до `3.1.26`.
- `pc_agent/tests/test_chat_panel_helpers.py`: TDD для error/result helpers.
- Docs/navigation/plan sync, local GUI smoke, Windows release build/upload/canary/rollout.

### Slice 15: error states

- [x] RED: helper должен переводить сетевые/preview/form/file ошибки в понятные русские тексты.
- [x] RED: вложения перед submit должны проверяться на отсутствие файла и превышение лимита.
- [x] GREEN: показать warning при недоступном preview без блокировки отправки.
- [x] GREEN: показывать понятную ошибку, если файл исчез/слишком большой до отправки.

### Slice 16: result screen

- [x] RED: result panel должен иметь отдельные строки кода доступа, следующего действия, сроков и кнопки `Открыть обращение`, `Добавить сообщение`, `Создать ещё одно`.
- [x] GREEN: усилить `_show_create_result()` и скрывать старый результат при новом создании.

### Slice 17: release

- [x] Bump `pc_agent/version.py` до `3.1.26`.
- [x] Focused/runtime/full agent tests + `verify_workspace.py`.
- [x] Local GUI smoke.
- [x] Commit, deploy committed state to remote, build Windows release, upload build.
- [x] Canary на launcher-managed Windows устройстве, затем `PATCH /api/agent_updates/rollout_policy` на `windows_amd64/stable/3.1.26`.

Verification so far:

- RED: `python -m pytest pc_agent/tests/test_chat_panel_helpers.py -q --tb=short` first failed on missing `build_ticket_create_error_message`.
- Focused/runtime/navigation: `python -m pytest pc_agent/tests/test_chat_panel_helpers.py pc_agent/tests/test_ticket_api_client_attachments.py pc_agent/tests/test_ui_api_server_shutdown.py pc_agent/tests/test_runtime_logging.py scripts/test_navigation_catalog.py -q --tb=short` -> 77 passed.
- Workspace: `python scripts/verify_workspace.py` -> passed.
- Full agent tests: `python -m pytest pc_agent/tests/ -q --tb=short` -> 179 passed.
- Live source GUI: `python scripts/manage_local_agent.py start codex-agent-gui-3126 --gui --ui-port 8884` -> `/ui/agent/status` returned `agent_version=3.1.26`, `ui_bridge_running=true`; stopped through `POST /ui/agent/shutdown`, then `manage_local_agent.py status` returned stopped.
- Deploy: `python scripts/release_server_to_remote.py --allow-local-dirty --skip-ci-check --leave-running` -> committed revision `e96be4845238e91f8ee1a2119f22a7f3e8f85ccd` deployed, migrations checked, remote server smoke `/api/health` passed.
- Build: `python pc_agent/build_windows_release_v2.py` -> `pc_agent-windows_amd64-3.1.26.zip`, size `98269850`, SHA256 `3abfa25a59e1cc4d11997af0f0f83adb65546eee60da99edead78d028c440225`.
- Upload: `POST /api/agent_builds/upload` -> `status=success`, target `windows_amd64`, channel `stable`, version `3.1.26`.
- Canary: device `AD-MAIN` / `15c8f029-bd7d-533b-a11e-dcd6c2ff48ab`, operation `64a8135a-4959-46e4-bb9f-7f3ddd7beb48` -> `succeeded`, `confirmed_by_handshake:3.1.26`.
- Rollout: `PATCH /api/agent_updates/rollout_policy` -> `windows_amd64/stable/3.1.26`; build registry returned `is_rollout_assigned=true`.

### Goal

Довести пользовательский ПК-агент до модели, где человек создаёт не "тикет" и не абстрактную форму, а понятное обращение по опубликованному `request_template`; агент показывает только нужные поля, объясняет последствия выбора человеческим языком, корректно передаёт template/process context на сервер и поддерживает диагностику/согласие/материалы.

### Constraints

- Редактировать только локальную рабочую копию `C:\Users\admin-2\CodexProjects\pc_client`.
- Сохранять совместимость со старым `request_forms` pack и `/ticket_forms/current`.
- Пользовательский текст в агенте должен быть русским, без mojibake и без внутреннего жаргона вроде raw `SLA`.
- Для каждой функциональной правки сначала тест RED, затем минимальная реализация GREEN.
- После GUI/runtime правок проверять минимум релевантные pytest и `python scripts/verify_workspace.py`; для live-срезов запускать локальный агент/GUI или browser/API smoke по каноническим скриптам.

### Target Model For Agent

Пользовательский поток:

1. Профиль инициатора.
2. Шаблон обращения (`request_template`) с понятным названием.
3. Форма сбора данных, включая условные и расширенные поля.
4. Краткое описание и материалы.
5. Влияние/срочность только если это нужно шаблону.
6. Предпросмотр: куда пойдёт обращение, нужен ли ответ/согласование/диагностика, когда ожидается ответ.
7. Создание обращения и показ кода/сроков человеческим языком.

### Scope And Order

1. **Request-template-aware payload contract.**
   - Files: `pc_agent/ui_gui/chat_panel.py`, `pc_agent/ui_gui/server_api.py`, `pc_agent/tests/test_chat_panel_helpers.py`, `server/tickets/form_catalog.py`, `server/tickets/handlers.py`, `server/tests/test_ticket_forms.py` or focused existing tests.
   - Behavior: normalized agent form definitions carry `request_template_key`/`request_template_title`; GUI payload and `TicketApiClient.create_ticket()` send `request_template_key`; server accepts it as first-class alias while preserving `form_key`; created ticket stores `custom_fields.request_template.key` and request form metadata consistently.
   - Verification: helper tests for normalization/payload, API test for `request_template_key` ticket creation.

2. **Agent creation microcopy cleanup.**
   - Files: `pc_agent/ui_gui/chat_panel.py`, `pc_agent/ui_gui/main_window.py`, `pc_agent/docs/CODEMAP.md`, `docs/QUICK_LOOKUP.md`.
   - Behavior: user-facing creation flow says "обращение", "шаблон обращения", "создать обращение", "служба поддержки"; internal logs may keep `ticket`.
   - Verification: helper/UI text tests where feasible and targeted grep for user-visible legacy strings.

3. **Extended field types in the agent.**
   - Files: `pc_agent/ui_gui/chat_panel.py`, `server/tickets/form_catalog.py`, related tests.
   - Behavior: agent renders and submits `date`, `datetime`, `multi_select`, `file`, `url`, `phone`, `email`, `department_picker`, `location_picker`, `device_picker`, `service_picker`, with graceful fallback for unknown picker catalogs.
   - Verification: unit tests for widget values, validation and submission normalization.

4. **Creation preview before submit.**
   - Files: `pc_agent/ui_gui/chat_panel.py`, `pc_agent/ui_gui/server_api.py`, server route-preview reuse or new safe endpoint if needed.
   - Behavior: before submit, agent shows likely queue/routing, user-facing response deadline, whether approval/consent is expected and whether diagnostics can be attached.
   - Verification: fake route-preview API tests and GUI helper tests.

5. **Diagnostic consent UX at creation time.**
   - Files: `pc_agent/ui_gui/chat_panel.py`, `pc_agent/ui_gui/consent_dialog.py` if reused, server diagnostic policy metadata.
   - Behavior: if template diagnostic policy says consent is required, agent asks clear consent and sends decision/metadata; diagnostics remain operation-level, not ticket status.
   - Verification: tests for consent payload and non-consent fallback.

6. **Local live validation and release path.**
   - Files: docs/plan only unless issues found.
   - Behavior: start local GUI agent through `scripts/manage_local_agent.py`, create an обращение through a published template, verify server ticket context, route/priority/deadlines and agent UI result.
   - Verification: local GUI smoke, focused tests, `verify_workspace.py`, commit/release if server/agent contract changed.

### Completed Slice 1: request-template-aware payload contract

- [x] Write failing tests for agent form normalization and payload: selected form should expose `request_template_key`, payload should send it, title should be "Обращение: <template title>".
- [x] Write failing server/API test: `/tickets/create` accepts `request_template_key` and stores matching `custom_fields.request_template.key`.
- [x] Implement agent normalization and `TicketApiClient.create_ticket(..., request_template_key=...)`.
- [x] Implement server alias handling for `request_template_key` without breaking `form_key`.
- [x] Run focused agent/server tests.
- [x] Update `pc_agent/docs/CODEMAP.md`, `docs/QUICK_LOOKUP.md` and this plan.
- [x] Run `python scripts/verify_workspace.py`.
- [x] Commit slice 1.

### Verification Log

- RED confirmed:
  - `python -m pytest pc_agent/tests/test_chat_panel_helpers.py::test_agent_default_forms_carry_process_type_and_priority_policy pc_agent/tests/test_chat_panel_helpers.py::test_agent_normalizes_request_template_identity_from_server_pack pc_agent/tests/test_ticket_api_client_attachments.py::test_create_ticket_sends_request_template_key -q` -> failed on missing `request_template_key` support and missing API argument.
  - `python -m pytest server/tests/test_ticket_form_packs.py::test_create_ticket_accepts_request_template_key_as_form_alias -q --tb=short` -> failed because server ignored `request_template_key` and kept request body `ticket_type=service_request`.
- GREEN focused:
  - `python -m pytest pc_agent/tests/test_chat_panel_helpers.py::test_agent_default_forms_carry_process_type_and_priority_policy pc_agent/tests/test_chat_panel_helpers.py::test_agent_normalizes_request_template_identity_from_server_pack pc_agent/tests/test_ticket_api_client_attachments.py::test_create_ticket_sends_request_template_key -q` -> passed, 3 tests.
  - `python -m pytest server/tests/test_ticket_form_packs.py::test_create_ticket_accepts_request_template_key_as_form_alias -q --tb=short` -> passed, 1 test.
- Broader focused:
  - `python -m pytest pc_agent/tests/test_chat_panel_helpers.py pc_agent/tests/test_ticket_api_client_attachments.py -q --tb=short` -> passed, 37 tests.
  - `python -m pytest server/tests/test_ticket_form_packs.py -q --tb=short` -> passed, 14 tests.
- Workspace:
  - `python scripts/verify_workspace.py` -> passed.

### Completed Slice 2: agent creation microcopy cleanup

- [x] Write failing helper test proving visible creation UI still says "Создать тикет", "Тип заявки" and "Тикет создан".
- [x] Replace visible creation-flow labels/statuses/dialog titles with "обращение" and "шаблон обращения".
- [x] Replace remaining user-facing PC-agent dashboard/sidebar/chat labels such as "Создать тикет", "Тикеты", "Тикет не найден" with requester-friendly "обращение" wording.
- [x] Keep internal API/log vocabulary stable where it is not shown to the user.

Verification:

- RED: `python -m pytest pc_agent/tests/test_chat_panel_helpers.py::test_ticket_creation_user_microcopy_uses_request_wording -q` -> failed on `Создать тикет`.
- GREEN: `python -m pytest pc_agent/tests/test_chat_panel_helpers.py::test_ticket_creation_user_microcopy_uses_request_wording -q` -> passed, 1 test.

### Completed Slice 3: extended field types

- [x] Write failing agent widget test for `multi_select`, `datetime`, `url`, `user_picker` and `phone`.
- [x] Write failing server form submission test for `url`, `datetime`, `multi_select`, `user_picker`, `email` and `file`.
- [x] Implement `multi_select` as a multi-selection list in the agent and keep text/picker/date-like types as line-edit fallback.
- [x] Extend server form schema/submission normalization for the new field types.

Verification:

- RED:
  - `python -m pytest pc_agent/tests/test_chat_panel_helpers.py::test_dynamic_fields_widget_supports_extended_field_types -q --tb=short` -> failed because `multi_select` rendered as `QLineEdit`.
  - `python -m pytest server/tests/test_ticket_form_packs.py::test_validate_form_submission_accepts_extended_field_types -q --tb=short` -> failed because `url` was unsupported.
- GREEN:
  - `python -m pytest pc_agent/tests/test_chat_panel_helpers.py::test_dynamic_fields_widget_supports_extended_field_types -q --tb=short` -> passed, 1 test.
  - `python -m pytest server/tests/test_ticket_form_packs.py::test_validate_form_submission_accepts_extended_field_types -q --tb=short` -> passed, 1 test.

### Completed Slice 4: creation preview before submit

- [x] Write failing helper test for a template preview that includes template title, likely queue, approval, diagnostic consent and user-facing response/resolution targets.
- [x] Implement `build_request_creation_preview(...)` with local template policy metadata.
- [x] Preserve `routing_policy`, `approval_policy`, `diagnostic_policy`, `sla_policy` and `default_queue_id` during agent form-pack normalization for preview use.
- [x] Render the preview on step 4 of the embedded creation wizard and refresh it when template/priority facts change.

Verification:

- RED: `python -m pytest pc_agent/tests/test_chat_panel_helpers.py::test_build_request_creation_preview_uses_template_policies -q` -> failed because helper was missing.
- GREEN: `python -m pytest pc_agent/tests/test_chat_panel_helpers.py::test_build_request_creation_preview_uses_template_policies -q --tb=short` -> passed, 1 test.
- Broader: `python -m pytest pc_agent/tests/test_chat_panel_helpers.py pc_agent/tests/test_ticket_api_client_attachments.py -q --tb=short` -> passed, 40 tests.

### Completed Slice 5: diagnostic consent UX at creation time

- [x] Write failing agent helper/API tests for a diagnostic consent payload when a template requires requester-device consent.
- [x] Write failing server tests for authenticated and public create-flow persistence of normalized `diagnostic_consent`.
- [x] Implement agent checkbox/payload support in dialog and embedded wizard.
- [x] Send `diagnostic_consent` through `TicketApiClient.create_ticket(...)`.
- [x] Normalize and persist diagnostic consent for both `/api/tickets/create` and `/public_api/tickets/create`.
- [x] Update navigation docs for the new create-flow contract.

Verification:

- RED: `python -m pytest server/tests/test_ticket_form_packs.py::test_create_ticket_stores_diagnostic_consent server/tests/test_ticket_form_packs.py::test_public_create_ticket_stores_diagnostic_consent -q --tb=short` -> failed on public create missing `custom_fields.diagnostic_consent`.
- GREEN:
  - `python -m pytest pc_agent/tests/test_chat_panel_helpers.py::test_diagnostic_consent_payload_marks_requester_device_decision pc_agent/tests/test_ticket_api_client_attachments.py::test_create_ticket_sends_diagnostic_consent -q --tb=short` -> passed, 2 tests.
  - `python -m pytest server/tests/test_ticket_form_packs.py::test_create_ticket_stores_diagnostic_consent server/tests/test_ticket_form_packs.py::test_public_create_ticket_stores_diagnostic_consent -q --tb=short` -> passed, 2 tests.
- Broader focused:
  - `python -m pytest pc_agent/tests/test_chat_panel_helpers.py pc_agent/tests/test_ticket_api_client_attachments.py -q --tb=short` -> passed, 42 tests.
  - `python -m pytest server/tests/test_ticket_form_packs.py -q --tb=short` -> passed, 17 tests.

### Current Slice 8: registry picker fields and file fields.

Goal: закрыть функциональный разрыв в "форме сбора данных": picker-поля должны выбирать реальные объекты из серверного registry, а `file`-поля должны быть связаны с конкретным полем формы и общим механизмом вложений.

Scope:

- `server/web_api/registry_handlers.py`, `server/routes.py`: добавить authenticated registry-options endpoint для `agent/user/support/admin` без admin-only доступа.
- `pc_agent/ui_gui/server_api.py`: добавить `get_registry_options()`.
- `pc_agent/ui_gui/chat_panel.py`: хранить registry options в `ChatPanel`, обновлять их рядом с form pack, передавать в `TicketDynamicFieldsWidget`, рендерить `*_picker` как `QComboBox` с id/key объекта, а `file` как выбираемое поле формы с metadata.
- `pc_agent/tests/test_chat_panel_helpers.py`, `pc_agent/tests/test_ticket_api_client_attachments.py`, server registry tests: TDD-контракты на API, widget values and create payload attachment propagation.
- Docs: обновить `docs/QUICK_LOOKUP.md`, `pc_agent/docs/CODEMAP.md`, `server/docs/CODEMAP.md`, `scripts/navigation_catalog.py` если меняется route/API surface.

Steps:

- [x] RED: тест server endpoint `/api/registry/options` for non-admin agent/user role.
- [x] RED: тест `TicketApiClient.get_registry_options()`.
- [x] RED: widget test: `department_picker`, `location_picker`, `device_picker`, `service_picker`, `user_picker` render as combo options and return selected object id.
- [x] RED: widget/file payload test: `file` field returns `{path, filename}` metadata in `form_payload` and adds the selected path to `attachment_paths`.
- [x] GREEN: implement endpoint/client/cache/widget/file propagation.
- [x] Run focused agent/server tests.
- [x] Run `python scripts/verify_workspace.py`.
- [x] Commit scoped files; if server route changed, deploy and live smoke `/api/registry/options` plus create-preview/create payload.

Verification so far:

- RED confirmed:
  - `python -m pytest server/tests/test_registry_web_api.py::test_registry_options_available_to_agent_request_forms pc_agent/tests/test_ticket_api_client_attachments.py::test_get_registry_options_reads_picker_catalog pc_agent/tests/test_chat_panel_helpers.py::test_dynamic_fields_widget_uses_registry_options_for_picker_fields pc_agent/tests/test_chat_panel_helpers.py::test_dynamic_fields_widget_returns_file_metadata_for_file_field -q --tb=short` -> failed on missing endpoint/client/widget methods.
- GREEN:
  - Same command -> passed, 4 tests.
  - `python -m pytest pc_agent/tests/test_chat_panel_helpers.py pc_agent/tests/test_ticket_api_client_attachments.py server/tests/test_registry_web_api.py server/tests/test_registry_service.py server/tests/test_ticket_form_packs.py -q --tb=short` -> passed, 71 tests.
  - `python -m pytest scripts/test_navigation_catalog.py -q --tb=short` -> passed, 10 tests.
  - `python scripts/verify_workspace.py` -> passed.
- Commit:
  - `55be13c pc_agent: add registry-backed form fields`.
- Remote/live:
  - `python scripts/release_server_to_remote.py --allow-local-dirty --skip-ci-check --leave-running` -> deployed commit `55be13c`, migrations up to head, remote server smoke passed.
  - `GET http://192.168.100.17:8666/api/registry/options` with a real local agent token -> 200, `status=success`, returned compact counts: devices 24, users 4, locations 1.
  - `POST http://192.168.100.17:8666/api/tickets/create/preview` for `request_template_key=breakage` -> 200, `priority_class=P3`, routed to `ServiceDesk L1`, first-response/resolution due fields present.

### Completed Slice 7: server-backed creation preview.

- [x] RED: добавить тест клиента `TicketApiClient.preview_ticket_create(...)`, который отправляет `request_template_key`, `form_key`, `form_pack_key`, `form_payload` и `ticket_type`.
- [x] RED: добавить серверный тест `/api/tickets/create/preview`, который требует effective request-template context, priority, routing fallback and first-response/resolution due dates without creating a ticket.
- [x] Реализовать authenticated preview endpoint без сайд-эффектов: form validation, effective registry overlays, priority policy, routing decision and SLA target calculation.
- [x] Подключить агентский API method for preview.
- [x] GREEN: подключить master preview в `TicketCreateWizardWidget` с локальным fallback, если сервер временно недоступен.
- [x] Обновить docs/CODEMAP and run focused/broader verification.
- [x] Выполнить remote/live API preview check после локальной проверки.

Verification:

- RED:
  - `python -m pytest pc_agent/tests/test_ticket_api_client_attachments.py::test_preview_ticket_create_posts_request_template_payload -q --tb=short` -> failed because `TicketApiClient.preview_ticket_create` did not exist.
  - `python -m pytest server/tests/test_ticket_form_packs.py::test_create_ticket_preview_returns_effective_template_context -q --tb=short` -> failed with 404 for `/api/tickets/create/preview`.
  - `python -m pytest pc_agent/tests/test_chat_panel_helpers.py::test_build_request_creation_preview_prefers_server_effective_preview -q --tb=short` -> failed because `server_preview` was unsupported.
  - `python -m pytest pc_agent/tests/test_chat_panel_helpers.py::test_ticket_create_wizard_uses_server_backed_preview -q --tb=short` -> failed because the wizard did not call `preview_ticket_create`.
- GREEN focused so far:
  - `python -m pytest pc_agent/tests/test_ticket_api_client_attachments.py::test_preview_ticket_create_posts_request_template_payload server/tests/test_ticket_form_packs.py::test_create_ticket_preview_returns_effective_template_context -q --tb=short` -> passed, 2 tests.
  - `python -m pytest pc_agent/tests/test_chat_panel_helpers.py::test_ticket_create_wizard_uses_server_backed_preview pc_agent/tests/test_chat_panel_helpers.py::test_build_request_creation_preview_prefers_server_effective_preview -q --tb=short` -> passed, 2 tests.
- Broader local:
  - `python -m pytest pc_agent/tests/test_chat_panel_helpers.py pc_agent/tests/test_ticket_api_client_attachments.py -q --tb=short` -> passed, 45 tests.
  - `python -m pytest server/tests/test_ticket_form_packs.py -q --tb=short` -> passed, 18 tests.
  - `python -m pytest scripts/test_navigation_catalog.py -q --tb=short` -> passed, 10 tests.
  - `python -m pytest pc_agent/tests/test_ui_api_server_shutdown.py pc_agent/tests/test_runtime_logging.py -q --tb=short` -> passed, 8 tests.
  - `python scripts/verify_workspace.py` -> passed.
- Remote/live:
  - `python scripts/release_server_to_remote.py --allow-local-dirty --skip-ci-check --leave-running` -> deployed commit `c1f214a`, built webapp, ran migrations, started remote server and passed remote smoke.
  - Live `POST /api/tickets/create/preview` with an issued agent token and `request_template_key=printer` returned `status=ok`, `ticket_type=incident`, `priority_class=P0`, fallback `target_queue_id=1`, and first-response/resolution due dates.
  - Side-effect-free check after preview on a fresh agent token: `GET /api/tickets` returned `count=0`.
  - `python scripts/manage_remote_stack.py stop server` -> server stopped.

### Completed Slice 6: local live validation and release path.

- [x] Run `python scripts/verify_workspace.py`.
- [x] Run agent runtime baseline tests required for `pc_agent/ui_gui/*` changes.
- [x] Run a local GUI agent smoke through `scripts/manage_local_agent.py`.
- [x] Document local create-flow live blocker: local `run_server.py` uses PostgreSQL at `127.0.0.1:5432`; without that DB it can answer `/api/health` but create-flow returns 500/service_unavailable, so DB-backed live create must be done after release/deploy on the remote stack.
- [x] Review scoped diff and commit only files from this plan.
- [x] Deploy/release committed state to DB-backed remote stack, run smoke and live create-flow check, then stop server unless explicitly kept running.

Verification:

- `python -m pytest pc_agent/tests/test_chat_panel_helpers.py pc_agent/tests/test_ticket_api_client_attachments.py pc_agent/tests/test_ui_api_server_shutdown.py pc_agent/tests/test_runtime_logging.py -q --tb=short` -> passed, 50 tests.
- `python -m pytest server/tests/test_ticket_form_packs.py scripts/test_navigation_catalog.py -q --tb=short` -> passed, 27 tests.
- `python scripts/verify_workspace.py` -> passed.
- Local live:
  - `python scripts/manage_local_agent.py start codex-helpdesk-agent --gui --ui-port 8875` -> started isolated GUI/source agent; `GET http://127.0.0.1:8875/ui/agent/status` returned `status=ok`, `ui_bridge_running=true`, `has_auth_token=true`.
  - Local create-flow against `run_server.py` was not accepted as a valid live create check because server logs showed PostgreSQL connection refused and in-memory-only startup; authenticated/public create returned 500/service_unavailable in that environment.
- Remote release/live:
  - `python scripts/release_server_to_remote.py --allow-local-dirty --skip-ci-check --leave-running` -> deployed committed state, ran migrations, started remote server and passed remote smoke on `http://192.168.100.17:8666/api/health`.
  - Public live create on `POST /public_api/tickets/create` with `request_template_key=printer` and `diagnostic_consent.granted=false` returned 200; response contained `custom_fields.request_template.key=printer`, `custom_fields.diagnostic_consent.source=public_request_create`, routing fallback and response/resolution due dates.
  - Authenticated live create with `Bearer test-ui-user:codex-live` was rejected on remote with `AUTH_REQUIRED`, as expected for the real remote auth boundary.
  - `python scripts/manage_local_agent.py start codex-helpdesk-agent --gui --ui-port 8875 --ws-url ws://192.168.100.17:8666/ws --api-url http://192.168.100.17:8666/api` -> isolated agent connected to remote server; local status reported `connection_state=connected`, `ui_bridge_running=true`, `has_auth_token=true`, `update_status_error=null`.

### Handoff

Current branch: `codex/helpdesk-process-model`. There are unrelated dirty files in the workspace from prior context/index work; do not stage or revert them while working on the agent slice.
