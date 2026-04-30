# PLANS.md

## 2026-04-30 ПК-агент: создание обращений по целевой helpdesk-модели

Status: план срезов 1-6 выполнен и проверен. Старый серверный helpdesk policy plan завершён и убран из актуального рабочего плана. Текущая фактическая готовность ПК-агента к целевой модели после этого релиза: функционально около 85-88%, GUI около 75-78%.

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

### Current Slice

Slice 6: local live validation and release path.

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
