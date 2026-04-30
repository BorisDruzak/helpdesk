# PLANS.md

## 2026-04-30 ПК-агент: создание обращений по целевой helpdesk-модели

Status: новый план активен. Старый серверный helpdesk policy plan завершён и убран из актуального рабочего плана. Текущая фактическая готовность ПК-агента к целевой модели: функционально около 75-80%, GUI около 65-70%.

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

### Current Slice

Slice 1: request-template-aware payload contract.

Steps:

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

### Handoff

Current branch: `codex/helpdesk-process-model`. There are unrelated dirty files in the workspace from prior context/index work; do not stage or revert them while working on the agent slice.
