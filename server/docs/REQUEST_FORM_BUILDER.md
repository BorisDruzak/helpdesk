# Конструктор форм заявок

Документ описывает рабочий сценарий администратора для каталога входящих заявок `request_forms`.

P1/P1.1 Service Catalog sits above this builder: a catalog offering points to a `request_template_key` / form schema, and create/preview accepts `service_code`, `offering_code` or `offering_full_code` before resolving the linked form. Legacy `/help`, public form-pack and agent form-only flows remain compatible; if a template maps to exactly one published offering, the runtime attaches a catalog snapshot, otherwise it preserves legacy behavior. The requester portal and agent GUI use the safe `other.unknown` fallback and call runtime-backed safe preview before catalog submit. See [SERVICE_CATALOG.md](SERVICE_CATALOG.md).

The local Knowledge suggestion integration is removed. A future external Knowledge Platform may consume opaque `request_template_key`, service and offering references through [KNOWLEDGE_PLATFORM_API_V1.md](KNOWLEDGE_PLATFORM_API_V1.md); Helpdesk form create stays independent while the port is unavailable.

## Канонические поверхности

- Typed workspace: панель `Конструктор форм заявок` в `/app/admin`, файлы `webapp/src/features/forms-builder/forms-builder-panel.tsx` и `webapp/src/features/forms-builder/api.ts`.
- Новый typed boundary для React-панели: `GET /api/web/admin/forms/current`, `POST /api/web/admin/forms/save`, `POST /api/web/admin/forms/route-preview` и `POST /api/web/admin/forms/process-preview`.
- Доменный pack-registry остаётся общим: `GET /api/ticket_forms/current`, `GET /public_api/ticket_forms/current`, `POST /api/ticket_forms/packs/save`, `PATCH /api/ticket_forms/packs/{pack_key}/{version}/preferred`.

## Зачем нужен конструктор

Конструктор управляет типовыми формами, которые используют:

- пользователь на странице `/help`;
- локальный агент при создании заявки;
- сервер при валидации `form_key`, `form_payload` и `ticket_type`;
- настройки маршрутизации в `/app/settings`, которые получают typed catalog текущих форм и могут строить правила по `request_form_data.<field>`;
- support workspace `/app/support`, который показывает нормализованную сводку ответов в блоке `Данные формы`;
- diagnostic playbooks, которые могут стартовать при создании тикета и получать пакет фактов из ответов формы;
- отчёты, которые подписывают `request_kind` по текущему preferred form pack.

Цель конструктора: собирать понятные формы без ручного редактирования JSON и без лишних технических решений в обычном операторском сценарии.

## Основные сущности

- Каталог форм: пакет с `pack_key`, внутренней `version`, `title`, `description`, `forms`.
- Форма: тип заявки с `key`, `request_kind`, `title`, `description`, `fields`, опциональными `playbook_triggers`.
- Поле: элемент формы с `key`, `label`, `type`, `required`, `placeholder`, `help_text`, `options`, `visible_when`.
- `playbook_triggers`: список автозапусков сценариев; сейчас поддержан `event=ticket_created` и безопасный `module_kind=diagnostic`.

Важно: сейчас в продукте используется один рабочий каталог `request_forms`. Поэтому в обычном UI администратор работает в первую очередь с формами и полями, а не со служебными параметрами каталога. Версионность каталога остаётся внутренней серверной механикой.

## Обычный сценарий администратора

### 1. Открыть список форм

Слева показывается единый список форм. Достаточно нажать на форму один раз, чтобы открыть её поля и параметры.

Если нужна новая форма, используйте кнопку `Новая форма`.

### 2. Заполнить основу формы

На базовом пути администратор заполняет только:

- название формы;
- системный ключ формы;
- список полей.

Дополнительные параметры должны быть скрыты в `Расширенных настройках`.

### 3. Добавить поля

Для каждого поля в базовом сценарии нужны:

- название поля;
- ключ поля;
- тип поля;
- обязательность.

Если тип поля `select` или `radio`, редактор должен запросить варианты ответа.

Добавление поля должно идти через раскрывающееся меню `Добавить поле`, а не через набор разрозненных кнопок по экрану.

### 4. Проверить форму

Перед сохранением администратор должен видеть:

- краткую сводку по форме;
- список ошибок или предупреждений, если что-то не заполнено;
- понятное подтверждение, что после сохранения каталога изменения сразу станут активными.

### 5. Сохранить каталог

Публикация каталога делается одной кнопкой `Сохранить изменения`.

При сохранении сервер:

- автоматически создаёт новую внутреннюю версию пакета;
- сразу делает её активной;
- отдаёт обновлённый каталог в `/help` и агент.

От администратора не требуется:

- вручную указывать номер версии;
- выбирать активную версию;
- переключаться между историческими версиями в обычном интерфейсе.
- постоянно видеть название или описание каталога в базовом сценарии.

### 6. Привязать диагностический плейбук

В блоке `Плейбук при создании тикета` можно указать ключ опубликованного плейбука, например `site_not_opening`, и включить автозапуск.

При создании тикета сервер переносит trigger в `custom_fields.request_form_playbook_triggers`, собирает `facts_package` из `request_form_data` и `request_form_summary`, запускает последнюю опубликованную версию сценария и пишет событие `playbook_started` в тикет.

Плейбуки описаны в `server/docs/DIAGNOSTIC_PLAYBOOKS.md`. В этом UI допустим только класс `diagnostic`: он собирает факты и не меняет устройство.

## Что считается расширенными настройками

Эти параметры не должны мешать базовому сценарию и должны быть скрыты под `details/summary` или отдельным advanced-блоком:

- `title` и `description` каталога;
- `description` формы;
- `request_kind`, если он отличается от `key`;
- `placeholder`;
- `help_text`;
- `visible_when`;
- raw JSON preview.

## Маршрутизация и preview

- Конструктор форм теперь напрямую связан с routing builder: `GET /api/web/settings` возвращает `routing_builder` catalog, собранный из текущего preferred pack, поэтому правила маршрутизации можно настраивать по базовым полям тикета и по `request_form_data.<field>` без ручного угадывания ключей.
- Preview маршрута вызывается через `POST /api/web/admin/forms/route-preview`: React-панель отправляет текущий draft формы и примерные значения, а сервер отвечает, какая очередь и какое правило совпадут, либо что сработал fallback.
- Process preview вызывается через `POST /api/web/admin/forms/process-preview`: React-панель отправляет текущий draft формы и примерные значения, а сервер без side effects возвращает `ticket_type`, `request_kind`, computed priority, matched routing rule/queue, SLA/OLA targets, approval summary, suggested diagnostics, closure checklist, visibility/notification summaries and business validation report.
- Policy Health dashboard is the production guard for published request templates after publication: `GET /api/web/admin/helpdesk/policy-health` returns routing/SLA/OLA/approval/closure/visibility/notification/diagnostic/reporting checks, invalid references, conflict counts, health score/status and issue drill-down for each active/published request template. `POST /api/web/admin/helpdesk/policy-health/simulate` accepts sample form/requester/device data and returns a dry-run process preview without creating a ticket. Simulation is runtime-equivalent: it overlays effective registry policies into an unsaved ticket context and calls the real routing, priority, SLA, OLA, approval, closure, visibility and diagnostic resolvers. The React route is `/app/admin/policy-health`.
- Runtime routing использует тот же form-aware context, что и preview: `ticket_type`, `request_kind`, `custom_fields`, `request_form_data`, `request_form_key`, `request_form_title`, `request_form_summary`.
- Runtime create/create-preview сохраняет explainable snapshot: `custom_fields.request_form` показывает источник (`legacy_pack` или `standalone_registry`), pack/form keys and versions, а `custom_fields.request_template` хранит template/schema versions, policy refs/snapshots and `computed` decisions. `computed` содержит priority, routing source, queue id/code/name and matched routing rule. Requester/public ticket payloads hide `custom_fields.request_template` by default so internal policy JSON does not leak.

## Integrity rules для зависимых полей

- `visible_when.field` должен ссылаться на реально существующее поле внутри той же формы; серверная валидация отклоняет пакеты с битой ссылкой ещё до публикации.
- При rename/delete поля React builder должен автоматически обновлять или очищать связанные `visible_when.field`, чтобы администратор не оставил невидимое навсегда поле.
- Visibility rules поддерживают как `equals`, так и `in`; это покрыто серверными тестами и должно оставаться совместимым для `/help`, локального агента и preview маршрута.

## Правила ключей

- Используйте латиницу, цифры и `_`.
- Для форм придерживайтесь коротких semantic key: `printer`, `access`, `site_system`.
- Для полей придерживайтесь snake_case: `printer_model`, `system_name`, `affected_scope`.
- Если `request_kind` не переопределён, он должен совпадать с `key`.
- Ключ формы должен быть уникальным в каталоге.
- Ключ поля должен быть уникальным внутри своей формы.

## Подсказки, которые должны быть в UI

Интерфейс должен объяснять:

- что в системе один рабочий каталог и в обычной работе нужно думать именно о формах;
- что клик по форме открывает поля, а клик по полю открывает его параметры;
- что ключи нужны для API, аналитики и маршрутизации;
- что сложные правила показа доступны в расширенных настройках;
- что после кнопки сохранения сервер сам выпускает новую активную редакцию каталога.

## Где используется этот контракт

- UI администратора: `webapp/src/features/forms-builder/forms-builder-panel.tsx`
- Серверная валидация и default pack: `server/tickets/form_catalog.py`
- HTTP API pack registry: `server/tickets/form_pack_handlers.py`, typed web boundary `server/web_api/admin_handlers.py`
- Публичная форма: `webapp/src/pages/help/index.tsx`
## 2026-05-11 lifecycle and business preflight

- The typed React boundary now separates draft, validation, publication and preferred rollout:
  - `POST /api/web/admin/forms/save-draft`
  - `POST /api/web/admin/forms/validate`
  - `POST /api/web/admin/forms/publish`
  - `PATCH /api/web/admin/forms/preferred`
- `POST /api/web/admin/forms/save` remains compatible with older callers and still routes through the same lifecycle service.
- `server/tickets/form_lifecycle_service.py` owns draft storage, validation orchestration, publish versioning and preferred switching.
- `server/tickets/form_business_validation.py` owns the business preflight report. It returns `summary`, `errors[]` and `warnings[]`; publish/save is blocked when `errors[]` is not empty.
- Current blocking checks cover missing conditional fields, required fields hidden without a checkable condition, missing routing queues, missing SLA policy ids, queues with OLA targets but no OLA policy, missing diagnostic playbooks, playbooks that are not diagnostic-domain safe, approval policies without approver source, closure policies without `closure_evidence`, and unknown/inactive policy refs.
- Current warning checks cover missing SLA policy, weak/missing public title, missing priority facts in raw packs, required fields without help text, missing saved route/process preview samples for process-aware forms, and field-key changes against `base_version` without alias or migration note.
- Preflight metadata preserved in form packs: `route_preview_examples`, `process_preview_examples`, `field_aliases`, and `field_migration_note`.
- Canonical policy references are accepted on forms as `priority_policy_ref`, `routing_policy_ref`, `sla_policy_ref`, `ola_policy_ref`, `approval_policy_ref`, `diagnostic_policy_ref`, `closure_policy_ref`, `visibility_policy_ref`, `notification_policy_ref`, and `reporting_policy_ref`. Normalization mirrors them into `policy_refs` and the existing `*_policy_code` fields so old runtime and standalone registry paths keep working.
- When an explicit `*_policy_ref` and inline legacy policy JSON are both present, the ref is authoritative for publication. `publish-from-form` attaches that ref to the request template and skips publishing a generated policy for that kind.
- In `/app/admin/forms`, policy refs are the primary template controls. Inline policy JSON is still editable, but it is labeled as `Advanced inline policy JSON`; the ref panel also shows active request templates already using an entered policy code.
- `on_behalf_policy` is an opt-in form-level policy for requester on-behalf creation. The default for absent legacy forms is disabled. When enabled, the normalized contract records `reason_required`, `affected_person_required`, `allowed_scope`, `diagnostic_target=affected_person_primary_agent`, creator-only knowledge visibility, creator+affected support visibility, no-primary-agent behavior and support/admin override allowance. Supported scopes are `self_only`, `same_department`, `direct_reports`, `same_department_or_privileged`, `privileged_only`, `exact_search_only` and `any_employee`. `/app/admin/forms` exposes it in the template `Процесс` step with the Russian toggle `Разрешить создание обращения за другого сотрудника`; `/app/requester` consumes it through scoped affected-person search and server-side preview/create authorization. Those reads and decisions go through the purpose-bound RegistryPort on-behalf operations with verified creator correlation and this server-resolved policy snapshot; browser-supplied role, creator or policy values are never authoritative.
- `/app/admin/forms` now has a `Проверить процесс` action backed by `server/tickets/form_process_preview.py`. It keeps the old route-preview action available, but the primary admin check now shows what ticket would be created from the sample answers: type, priority, route, SLA/OLA, approval, diagnostics, closure and notification plan.

## 2026-04-29 priority question contract

- Priority facts are normal request-template fields, not hardcoded priority selectors.
- The standard field keys are `impact_scope`, `work_continuity`, `business_importance`, `critical_service` and `public_service`.
- `priority_policy.impact_field`, `priority_policy.urgency_field`, `priority_policy.importance_field` map those fields into the deterministic priority engine.
- `priority_policy.modifier_fields` maps boolean modifiers such as `critical_service` and `public_service`.
- `field_roles` marks how fields participate in process execution. The canonical roles are `routing_field`, `priority_impact`, `priority_urgency`, `priority_importance`, `diagnostic_input`, `approval_subject`, `closure_evidence`, `reporting_dimension`, `passport_fact`, `visibility_public` and `display_only`; legacy packs may still load old `priority_field`, `sla_field` and `approval_field` roles for compatibility. Business preflight now enforces singleton priority roles, requires `diagnostic_input` parameter mappings for diagnostic autorun, checks `approval_subject` fields for user/service/role/group compatibility and checks `closure_evidence` fields against closure evidence requirements. `/app/admin/forms` shows the same role issues inline on affected fields.
- `/app/admin/forms` can add the standard priority question set to any request template, after which every label, option, required flag and role remains editable in the server UI.
- The local agent reads the same server form pack. If a template defines priority fields, the agent renders those fields in the priority step and sends their values in `form_payload`. Fixed local priority controls are only a fallback for old packs without priority fields.
- SLA shown to the requester/agent is not local text. It is read from the created/refreshed ticket payload (`first_response_due_at`, `resolution_due_at`) after the server computes effective priority and SLA targets.
