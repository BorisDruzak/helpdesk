# Тикетная система — полная документация

Единый документ по тикетной системе сервера: маршрутизация, SLA, workflow, RBAC, уведомления, проблемы/изменения, админ-конфиг, пользователи, очереди, UI, календари, OLA, retention и вложения.

**Связанные документы:** [DATABASE.md](DATABASE.md), [SECURITY_AND_AUTH.md](SECURITY_AND_AUTH.md), [CHAT_MESSAGE_CONTRACT.md](CHAT_MESSAGE_CONTRACT.md), [ARTIFACTS_API.md](ARTIFACTS_API.md). Исторический анализ пробелов и багов: [TICKET_CRM_GAP_ANALYSIS.md](../../docs/archive/TICKET_CRM_GAP_ANALYSIS.md).

---

## Источники создания тикета и инварианты

**Канонические источники создания тикета (DB-first):**
1. **POST /api/tickets/create** — основной путь из UI; создаёт тикет в PostgreSQL, запускает routing/SLA/OLA, сохраняет начальное сообщение в ticket_events. Для RBAC при создании обязательно задаётся `requester_id` (из AuthContext или device_id при отсутствии контекста).
2. **Команда chat_raise (WebSocket)** — агент инициирует «поддержку»; сервер создаёт тикет в БД с `status="new"` и `requester_id=agent_id`, чтобы тикет участвовал в фильтрации по requester.

**Инварианты:**
- В БД хранятся только канонические статусы (snake_case): `new`, `queued`, `assigned`, `in_progress`, `waiting_on_user`, `waiting_on_internal_team`, `waiting_on_vendor`, `waiting_on_approval`, `scheduled`, `resolved`, `closed`, `canceled`. Legacy `triaged` принимается soft-normalization и миграцией переводится в `queued` / `assigned`.
- Для понятного владения работой каждый тикет хранит `next_action_owner`, `next_action_due_at`, `status_reason`, `requester_status`, summary решения, evidence-поля и `closure_feedback`; активные ожидания пишутся в `ticket_waits`.
- Для корректного RBAC (список «мои заявки» для requester) при создании тикета должен быть задан `requester_id`.
- Сообщения chat_message в payload должны содержать каноническое поле `sender_role` (см. CHAT_MESSAGE_CONTRACT.md).
- `/api/tickets/create`, WS `chat_raise` и legacy `POST /api/chat_raise` используют общий DB-first create flow в `server/tickets/create_flow.py`: routing, SLA, OLA, auto-assign и initial chat event должны совпадать.
- Support ticket list включает queue-less active tickets как triage backlog; detail/snapshot для таких тикетов не должен давать `403`.
- `GET /api/tickets/{ticket_id}` поддерживает `since_event_id` для incremental refresh и reverse pagination через `before_event_id` + `limit`; агентский GUI открывает тикет с tail-page и догружает старую историю вверх без полного reload всей ленты.
- При переходе в `resolved` support/admin отправляет requester structured `confirmation_request`; `closed` для таких тикетов разрешён только после подтверждения requester.
- Request-template `approval_policy` исполняется в `server/tickets/approval_policy.py`: вход в `waiting_on_approval` разрешён без решения, но переходы в исполнение (`assigned`, `in_progress`, `scheduled`, `resolved` или явно заданный `approved_transition`) требуют approved-запись в `ticket_approvals`; rejected/denied/declined согласование блокирует переход.
- Workflow profile transition gates исполняются в `server/tickets/workflow_service.py`: structured transition entries из `server/tickets/workflow_profiles.py` могут требовать `allowed_roles` и `required_fields`; typed support status API возвращает `WORKFLOW_POLICY_BLOCKED` для таких блокировок.
- Для проверяемого закрытия в госсекторном контуре тикет может иметь `evidence_required=true`; переход в `resolved` тогда запрещён без `evidence_ref` или записи в `ticket_evidence_items`, а официальный `Паспорт решения` собирается из фактов тикета, событий, операций, worklog, согласований и доказательств.
- Request-template `closure_policy` исполняется в `server/tickets/closure_policy.py` при переходе в `resolved`: политика может требовать `resolution_code`, публичный `resolution_summary` / `requester_resolution_summary` и evidence для указанных P0..P3 приоритетов.
- Versioned `ticket_types` live in the standalone helpdesk model registry (`ticket_types`, migration `066`). A ticket type is the top-level process profile (`incident`, `service_request`, `access_request`, etc.) with default workflow/profile/policy references and feature flags; `request_templates` inherit those defaults when published while legacy unknown `ticket_type` values remain accepted for old form packs.
- Versioned `form_schemas`, `form_fields` and `form_conditions` live in migration `067`. `request_templates.form_schema_id` is now backed by a first-class schema publication when the visual forms builder publishes a template; the legacy `ticket_form_packs` path stays compatible for `/help`, agent create and old packs. Field `process_mapping.roles` is normalized as an alias of existing `field_roles`, and `validation.required_message` is preserved by server-side submission validation.
- Request-template policy references live on the template row, including `priority_policy_code`, `routing_policy_code`, `sla_policy_code`/legacy `sla_policy_id`, `ola_policy_code`, `approval_policy_code`, `diagnostic_policy_code`, `closure_policy_code`, `visibility_policy_code`, `notification_policy_code` and `reporting_policy_code` (migration `068`). `HelpdeskPolicyRepo.resolve_effective_request_template()` prefers those refs over inline legacy form JSON, returns resolved config plus source rows, and ticket creation stores `policy_refs`, `effective_policy_sources` and `effective_policy_snapshots` in `custom_fields.request_template` so historical tickets remain explainable.
- `priority_policy` now supports configured `input_fields`, named/raw `matrix` rows and columns, list `modifiers` with `condition`/`action` rules, and `manual_override` role/reason checks. Ticket creation and create-preview expose canonical priority fields (`impact`, `urgency`, `importance`, `computed_priority`, `manual_priority`, `effective_priority`, `priority_source`, `priority_reason`), requester-safe `priority_explanation`, matched modifier labels, and a `priority_overridden` audit event when manual override logging is enabled.
- Request-template `sla_policy` now participates in lifecycle execution: standalone targets and inline calendars are used for due dates; `start_conditions`, `pause_conditions`, `resume_conditions` and `stop_conditions` gate timer state changes; warning-before settings emit `sla_warning`; SLA events include policy code/version/source and configured breach action metadata for observer/reporting.
- Request-template `ola_policy` now participates in lifecycle execution: standalone ack/processing targets can gate start, ack stop, processing stop, pause/resume and breach behavior while legacy `ticket_queue_ola_targets` remains the fallback. Runtime source tracking is stored in `custom_fields.ola_runtime`, and OLA events include policy code/version/source plus configured breach action metadata.

---

## Содержание

1. [Этап 2: Routing + SLA Core](#этап-2-routing--sla-core)
2. [Этап 3: Workflow + RBAC](#этап-3-workflow--rbac-enforcement)
3. [Этап 4: Communication Visibility + Worklog](#этап-4-communication-visibility--worklog)
4. [Этап 5: Relations + Resolution + Metrics](#этап-5-relations--resolution-governance--metrics)
5. [Этап 6: Hardening + Notifications](#этап-6-hardening--notifications)
6. [Этап 7: Problem/Change Core](#этап-7-problemchange-core--notification-hardening)
7. [Этап 8: Notification Preferences](#этап-8-notification-preferences--hardening)
8. [Этап 9: Admin Config API + Auditor RBAC](#этап-9-admin-config-api--auditor-rbac)
9. [Этап 10: Users/Roles из БД](#этап-10-usersroles-из-бд)
10. [Этап 10.1: Admin Queue Page](#этап-101-admin-queue-page)
11. [Этап 10.2: Public Queue + Position Engine](#этап-102-public-user-queue-panel--position-engine)
12. [Этап 10.3: Admin Queue UX Refactor](#этап-103-admin-queue-uxlogic-refactor)
13. [Этап 10.3.1: Русификация UI очереди](#этап-1031-русификация-ui-очереди)
14. [Этап 10.4: Chat-first (deprecated)](#этап-104-chat-first-deprecated)
15. [Этап 10.5: Action Dock + Inline Panels](#этап-105-action-dock--inline-panels)
16. [Этап 11: SLA Calendar + OLA](#этап-11-sla-calendar--ola)
17. [Этап 12: Retention/Archive + Runbooks](#этап-12-operational-hardening)
18. [Чеклист этапов 10–12](#чеклист-этапов-1012)
19. [Вложения в сообщениях](#вложения-в-сообщениях)

---

## Этап 2: Routing + SLA Core

Поверх схемы 018 (миграция `20260216_1000_018_ticket_system_extended`).

### Компоненты

**TicketRoutingService (`tickets/routing_service.py`)**
- First-match выполняется в порядке: `request_template.routing_policy.rules` -> глобальные `ticket_routing_rules` -> `request_template.default_queue_id` -> `servicedesk_l1`.
- Условия используют общий evaluator (`when` / `condition` / `condition_json`) по полям тикета, template context, `custom_fields`, `request_form_data.<field>` и `devices.metadata`.
- Template actions могут выставлять `queue_id` / `queue_code`, `assignee_id`, `priority_boost` / `minimum_priority`, `sla_policy_id`, `approval_policy`, `suggested_playbook_id`, `tags`; OLA/watchers/visibility сохраняются в `custom_fields.routing_decision`.
- Loop guards: `routing_lock`, `do_not_reroute_if_assignee_locked`, `max_auto_reroutes`.
- События: `routing_applied` с `routing_source`, matched rule и actions; `queue_changed` только при фактической смене очереди.

**Manual queue lock**
- При ручной смене очереди (POST `/api/tickets/{id}/queue`) в `custom_fields` сохраняются: `routing_lock` = true, `routing_lock_reason`, `routing_lock_at`.
- Авто-роутинг не перезаписывает очередь при установленном lock.
- POST `/api/tickets/{id}/reroute` снимает lock и пересчитывает очередь по правилам.

**TicketSlaService (`tickets/sla_service.py`)**
- При создании тикета: старт FRT и Resolution по policy + priority; standalone `request_template.sla_policy.targets` и inline/legacy calendars поддерживаются без обязательного legacy `ticket_sla_policies.id`.
- `start_conditions`, `pause_conditions`, `resume_conditions` и `stop_conditions` могут управлять стартом, паузой, возобновлением, остановкой FRT и остановкой resolution timer; без явных условий сохраняется legacy-поведение.
- FRT закрывается первым public comment от support/agent (`first_response_at`) или другим trigger, если это явно задано в policy.
- В статусах ожидания (`waiting_on_user`, `waiting_on_internal_team`, `waiting_on_vendor`, `waiting_on_approval`) workflow пишет `ticket_waits`, обновляет `next_action_owner` и выполняет policy-aware паузу/возобновление SLA с накоплением `sla_paused_seconds`.
- При reopen: сброс resolution timer, `reopen_count++`.

**TicketSlaWatchdog (`app/services/ticket_sla_watchdog.py`)**
- До breach проверяет `warnings.warning_before` / `breach_actions.warning_before` и пишет однократный `sla_warning` по каждому таймеру.
- Периодический скан тикетов с истёкшими `first_response_due_at` / `resolution_due_at` (с учётом `sla_paused_seconds`).
- При первом breach: проставление `*_breached_at`, событие `sla_breached`, policy metadata и configured `breach_actions` в payload, push в UI.
- Напоминания каждые 60 минут: событие `sla_reminder_sent`, push в UI.
- Остановка напоминаний при переходе в Resolved/Closed.

### API (Этап 2)

- **POST** `/api/tickets/{ticket_id}/reroute` — явный пересчёт очереди, снятие manual lock.
- **POST** `/api/tickets/{ticket_id}/classify` — body: `category_id`, `service_id`, `subcategory_id`; триггер reroute только для статусов New/Triaged.
- **POST** `/api/tickets/{ticket_id}/queue` — ручная смена очереди + reason, устанавливает routing lock, снимает исполнителя вне новой очереди и при необходимости запускает автоназначение уже по составу целевой очереди.
- **GET** `/api/tickets/{ticket_id}/sla` — текущие SLA-таймеры, breach state, paused seconds.

**Расширенный ответ тикета (ticket_to_dict):** `queue_id`, `queue_code`, `assignee_id`, `priority`, `impact`, `urgency`, `requester_id`, `status_label`, `requester_status`, `requester_status_label`, `next_action_owner`, `next_action_due_at`, `status_reason`, `first_response_due_at`, `resolution_due_at`, `first_response_at`, `first_response_breached_at`, `resolution_breached_at`, `sla_paused_at`, `sla_paused_seconds`, `reopen_count`, `resolution_code`, `resolution_summary`, `requester_resolution_summary`, `evidence_required`, `evidence_ref`, `closure_feedback`, `routing_lock`, `routing_lock_reason`.

**Фильтры GET `/api/tickets`:** `device_id`, `queue_id`, `priority`, `assignee_id`, `requester_id`, `status`, `first_response_breached`, `resolution_breached`.

**События ticket_events:** `routing_applied`, `queue_changed`, `sla_started`, `sla_paused`, `sla_resumed`, `sla_first_response_stopped`, `sla_resolution_stopped`, `sla_warning`, `sla_breached`, `sla_reminder_sent`, `sla_cleared`.

**Терминальные статусы:** Resolved, Closed. SLA due dates считаются через `calendar_engine.add_business_minutes`, если политика SLA связана с бизнес-календарём; расчёт ведётся в секундах, чтобы реальный `now()` у границы рабочего окна не застревал на неполной минуте. Без календаря остаётся 24x7. Recipients эскалации: участники очереди (`ticket_queue_members`) + admins; доставка через `ticket_event_committed`.

---

## Этап 3: Workflow + RBAC Enforcement

Поверх этапа 2. Soft FSM для переходов статусов, единый API смены статуса, полный RBAC и авто-закрытие.

### Цель

- Единый workflow engine для переходов статусов (soft normalize + FSM).
- RBAC enforcement в ticket API через `request['auth_context']`.
- Ownership: requester видит только свои тикеты (requester_id = actor_id).
- Resolved → Closed теперь выполняется только после подтверждения пользователя; watchdog авто-закрытия не переводит тикеты в `closed`.

### Компоненты

**statuses.py (tickets/):** канонические статусы: New, Queued, Assigned, In Progress, Waiting on User, Waiting on Internal Team, Waiting on Vendor, Waiting on Approval, Scheduled, Resolved, Closed, Canceled. `normalize_status(raw)` — soft-нормализация; неизвестный → 400 validation_error. Пользовательский mapping: accepted / in_work / needs_requester / review_solution / closed / canceled.

**workflow_service.py (tickets/):** матрица переходов (support/admin — полная FSM; requester — подтверждение/возврат решения). `TicketWorkflowService.apply_status_transition(...)` — обновление тикета + side effects (`resolved_at`, `closed_at`, `canceled_at`, reopen, SLA pause/resume, wait ledger, `next_action_owner`, `requester_status`) и проверка workflow transition gates, `approval_policy` / `closure_policy` перед guarded-переходами. Событие `status_changed` несёт owner/status для UI.

**RBAC:** support/admin — reroute, classify, queue, любые переходы; requester — только свои тикеты, только Resolved → New (reopen). POST /message, /close: роль только из AuthContext; from_role/closed_by_role в body — legacy, deprecation_warning.

**Resolved confirmation:** при переходе в `resolved` пользователю отправляется системное сообщение с просьбой подтвердить решение; `closed` выставляется только после подтверждения пользователя.

### API

- **POST** `/api/tickets/{ticket_id}/status` — body: `to_status`, `reason`, `resolution_code`, `resolution_summary`, `requester_resolution_summary`, `root_cause`. 409 invalid_transition при невалидном переходе; workflow gates и `closure_policy` возвращают validation/API error, если не хватает обязательных ролей или фактов закрытия.
- **POST** `/api/tickets/{ticket_id}/close` — compatibility wrapper (переход в Closed).
- **GET** /api/tickets, GET /api/tickets/{id}, GET /api/tickets/{id}/sla — для requester только свои тикеты.

**Конфигурация:** `TICKET_FSM_MODE=soft`, `TICKET_LEGACY_ROLE_FIELDS=true`, `TICKET_AUTO_CLOSE_HOURS=72`. Миграция 019: индекс `ix_tickets_status_resolved_at`.

---

## Этап 4: Communication Visibility + Worklog

Видимость комментариев public/internal, worklog (append-only).

### Visibility комментариев

- **visibility** в payload chat_message: `"public"` | `"internal"`. Requester только public; support/admin могут писать internal. При чтении requester видит только public.
- **POST** `/api/tickets/{ticket_id}/read`: requester фиксирует реальное прочтение новых public-сообщений, сервер пишет `ticket_event` с `event_type="message_read"` и отправляет его в UI через обычный `ticket_event_committed`.
- **POST** `/api/tickets/{ticket_id}/message`: опциональное поле `visibility`.

### Worklog

- **POST** `/api/tickets/{ticket_id}/worklogs` — body: `spent_minutes`, `note`. RBAC: support/admin.
- **GET** `/api/tickets/{ticket_id}/worklogs` — список (support/admin).
- **GET** `/api/tickets/{ticket_id}/worklog_total` — сумма минут (все роли с ownership).
- В GET ticket/snapshot добавлено `worklog_total_minutes`. Worklog append-only; событие `worklog_added`.

**FRT:** закрывается любым комментарием support/admin (public или internal). Миграция 020: индекс `ix_ticket_worklogs_ticket_created_at`.

---

## Этап 5: Relations + Resolution Governance + Metrics

Связи тикетов (duplicate/related, parent-child), watchers, KB-ссылки, валидация резолюции, операционные метрики.

### Relations

- **ticket_links:** link_type `duplicate` | `related`; unique (src_ticket_id, dst_ticket_id, link_type). API: POST/GET/DELETE `/api/tickets/{id}/links`. События: `ticket_link_added`, `ticket_link_removed`.
- **parent_ticket_id:** POST/DELETE `/api/tickets/{id}/parent`. Событие `parent_ticket_changed`.

### Watchers, KB

- **POST/GET/DELETE** `/api/tickets/{id}/watchers` — requester только self в своём тикете. События: `watcher_added`, `watcher_removed`.
- **POST/GET/DELETE** `/api/tickets/{id}/kb_links` — body: `article_ref`, `title`, `source`. События: `kb_linked`, `kb_unlinked`.

### Resolution governance

- **GET** `/api/tickets/resolution_codes` — справочник кодов. **POST** `/api/tickets/{id}/status` при переходе в Resolved/Closed: `TicketResolutionPolicyService.validate` в режиме warn | enforce. Событие `resolution_policy_warning` (warn).
- **Паспорт решения:** миграция `059` добавляет `ticket_resolution_passports`, `ticket_evidence_items`, `ticket_action_log`, `ticket_approvals`, `ticket_related_objects`. `TicketPassportService` собирает версионированный паспорт из полей заявки, requester/device контекста, `ticket_events`, worklog, операций, evidence и approvals без выдумывания фактов; повторный refresh создаёт новую версию.
- **Typed web API:** support/admin используют `GET /api/web/support/tickets/{ticket_id}/passport`, `POST /api/web/support/tickets/{ticket_id}/passport/generate`, `PATCH /api/web/support/tickets/{ticket_id}/passport`, `POST /api/web/support/tickets/{ticket_id}/passport/evidence`, `POST /api/web/support/tickets/{ticket_id}/passport/knowledge-draft`.
- **React UI:** `/app/tickets/:ticketId` содержит вкладку `Паспорт` с действиями `Собрать паспорт`, `Обновить по последним действиям`, `Печать / PDF`, `Сохранить как черновик знания`; печатная форма живёт на `/app/tickets/:ticketId/passport/print`.

### Метрики (GET; RBAC support/admin)

- `/api/tickets/metrics/backlog`, `/api/tickets/metrics/aging`, `/api/tickets/metrics/sla`, `/api/tickets/metrics/reopen_rate`, `/api/tickets/metrics/top`, `/api/tickets/metrics/status_age`. Query: `queue_id`, `days`, `period_start`, `period_end`, `top_n`.

**Конфигурация:** `TICKET_RESOLUTION_VALIDATION_MODE` (warn|enforce), `TICKET_REQUIRE_ROOT_CAUSE_PRIORITIES`, `TICKET_METRICS_DEFAULT_DAYS`, `TICKET_METRICS_MAX_DAYS`. Миграции 021–022.

---

## Этап 6: Hardening + Notifications

Стабилизация Stage 5, уведомления по событиям тикетов (in-app), API уведомлений.

### Модель (миграция 023)

- **ticket_notifications:** id, actor_id, ticket_id, event_type, payload, is_read, created_at, read_at. Индексы: (actor_id, is_read, created_at), (ticket_id, created_at).

### Получатели

- support/admin: участники очереди + assignee.
- requester: только public-события (например `status_changed`); как watcher — тоже только public.
- watchers: все наблюдатели (с учётом visibility для requester).

**События уведомлений:** status_changed, sla_breached, sla_reminder_sent, ticket_link_added/removed, parent_ticket_changed, kb_linked/kb_unlinked.

### API уведомлений

- **GET** `/api/notifications` — query: limit, offset, unread_only.
- **GET** `/api/notifications/unread_count`
- **POST** `/api/notifications/read_all` — ответ: marked_count.
- **POST** `/api/notifications/{id}/read`

---

## Этап 7: Problem/Change Core + Notification Hardening

ITSM Problem и Change linkage.

### Problem (миграция 024)

- **problems**, **problem_ticket_links**. FSM: New → Investigating → Mitigated → Resolved → Closed; reopen Resolved → Investigating.
- **API:** POST/GET /api/problems, GET /api/problems/{id}, POST /api/problems/{id}/status, POST/DELETE /api/problems/{id}/tickets, GET /api/tickets/{id}/problems.
- События: `problem_status_changed`, `problem_ticket_linked`, `problem_ticket_unlinked`.

### Change linkage (миграция 025)

- **ticket_change_links:** ticket_id, change_ref, change_system. API: POST/GET/DELETE `/api/tickets/{id}/change_links`. События: `change_linked`, `change_unlinked`.

**RBAC:** requester — GET problems/change_links только для своих тикетов.

---

## Этап 8: Notification Preferences + Problem/Change Hardening

### Notification preferences (миграция 026)

- **ticket_notification_prefs:** actor_id (PK), mute_internal, muted_event_types (JSONB), suppress_self, updated_at.
- **notify_ticket_event** с опцией initiator_id и prefs_repo: фильтрация по mute_internal, muted_event_types, suppress_self.

### API

- **GET/POST** `/api/notifications/preferences` — body: mute_internal, muted_event_types, suppress_self. RBAC: только свой actor_id.

**Problem/Change:** при создании problem с `ticket_ids` — links + problem_created в ticket_events; problem_ticket_unlinked атомарно с удалением связи; 409 при дубликате link.

---

## Этап 9: Admin Config API + Auditor RBAC

Управляемая админ-конфигурация тикетной системы, роль auditor (read-only cross-queue), аудит изменений.

### Admin Config API

- **Queues:** GET/POST /api/admin/tickets/queues, GET/PATCH /api/admin/tickets/queues/{id}, GET/PUT/DELETE members.
- **Routing rules:** GET/POST /api/admin/tickets/routing_rules, PATCH /api/admin/tickets/routing_rules/{id}.
- **SLA policies:** GET/POST/PATCH /api/admin/tickets/sla_policies, POST set_default, PUT targets, PUT priority_matrix.
- **Audit:** GET /api/admin/tickets/audit (entity_type, entity_id, actor_id, limit, offset).
- **React settings:** `GET /api/web/settings` includes `ticket_settings` for `/app/settings` -> `Тикеты`: internal/requester status mapping, `next_action_owner`, resolution/evidence/passport governance and operational ticket flags. Editable parts remain in Queues, Routing, SLA, Calendars and Resolution tabs.

### RBAC

- **admin:** полный доступ к admin-config (при включённом write-flag).
- **support:** read-only к admin-config; write к тикетам как раньше.
- **auditor:** read-only к ticket-domain GET (кросс-очередной), в т.ч. admin-config GET при `TICKET_AUDITOR_ROLE_ENABLED=true`.

### Feature flags

- `TICKET_ADMIN_CONFIG_API_ENABLED`, `TICKET_ADMIN_CONFIG_WRITE_ENABLED`, `TICKET_AUDITOR_ROLE_ENABLED`. `UI_USER_ROLES_JSON` — маппинг login→role.

**Миграция 027:** ticket_sla_policies.is_active, ticket_admin_audit. Soft deactivate: нельзя деактивировать queue с open tickets или enabled routing rule; нельзя деактивировать default SLA policy.

---

## Этап 10: Users/Roles из БД

UI-пользователи и роли в PostgreSQL (dual-mode: БД + fallback на config).

### База данных (миграция 028)

- **ui_users:** user_login (PK), password_hash (pbkdf2_sha256$...), actor_role, is_active, failed_attempts, locked_until, last_login_at, created_at, updated_at.
- **ui_user_audit:** id, user_login, action, actor_id, details_json, created_at.

### Feature flags

- `AUTH_UI_DB_USERS_ENABLED`, `AUTH_UI_CONFIG_FALLBACK_ENABLED`, `AUTH_UI_MAX_FAILED_ATTEMPTS`, `AUTH_UI_LOCK_MINUTES`.

### API

- **Admin Users (RBAC admin):** GET/POST /api/admin/users, GET/PATCH /api/admin/users/{login}, POST .../password, POST .../deactivate.
- **Self-service:** POST /api/users/me/password (current_password, new_password).

**Логика POST /api/ui_login:** при AUTH_UI_DB_USERS_ENABLED — поиск в ui_users, проверка пароля, lockout при неудачах; при отсутствии в БД и fallback — state.users / USERS.

---

## Этап 10.1: Admin Queue Page

Страница очереди тикетов для L1/L2: Table First, inline-действия.

### Реализовано

- **Миграция 031:** поле `ticket_code` (T-000001), последовательность `ticket_code_seq`.
- **API:** ticket_code в list/get; фильтры ticket_code, unassigned; POST assign, queue, reroute; GET /api/admin/tickets/queues.
- **Admin Queue UI (/admin):** вкладка Ticket Queue, KPI-лента, фильтры и пресеты, таблица с колонками Pin, Ticket, Title, Queue, Status, Priority, Assignee, Requester, Created, Age, SLA, OLA, Actions. Inline: Status, Assign, Очередь, Reroute, Open; локальный порядок (pin, manual_rank) в localStorage; режим Compact.
- **Realtime:** WebSocket /ws_ui, subscribe_ticket/unsubscribe_ticket, ticket_event_committed с debounce/reload, Live/Degraded, polling 25/60 с.
- **RBAC:** auditor — read-only (только «Открыть»); admin/support — полные действия.

---

## Этап 10.2: Public User Queue Panel + Position Engine

Публичная страница `/queue` без авторизации; ручной порядок в БД (manual_rank).

### БД (миграция 032)

- **tickets:** manual_rank, manual_rank_updated_at, manual_rank_updated_by. Индексы: ix_tickets_queue_manual_rank, ix_tickets_queue_open_sort. При смене очереди/reroute — сброс manual_rank.

### Position Engine

- **tickets/queue_position_service.py:** list_queue_positions, has_manual_mode, reorder_ticket (up/down/top/bottom), reset_manual_order. Сортировка: при manual_rank — по manual_rank; иначе priority → breached → effective_due_at → created_at → ticket_code.

### API

**Публичные (без auth):**
- GET /public_api/queues — список очередей с open_count; по умолчанию только с open_count &gt; 0; `include_empty=true` — все активные.
- GET /public_api/queue/tickets — queue_id, limit, offset, ticket_code; позиция, код, статус, приоритет, ФИО (`requester_display_name`), `urgency`, `importance`, ожидание; ETag/304.
- GET /public_api/queue/stats — days, queue_id; KPI; ETag/304.

**Внутренние (admin/support):**
- POST /api/tickets/{id}/order — body direction (up|down|top|bottom), reason. Событие `queue_reordered`.
- POST /api/tickets/queues/{queue_id}/order/reset. Событие `queue_order_reset`.

**UI:** link-based public queue (`/queue/common`, `/queue/test`; fallback `/queue?queue=<alias|queue_code>`) — public_queue.html/js/css; KPI, поиск по коду талона, таблица без селектора очереди; в админке при одной очереди — бейдж AUTO/MANUAL, кнопки порядка и «Сбросить авто».

---

## Этап 10.3: Admin Queue UX/Logic Refactor + Public Queue Cleanup

Единое модальное окно «Управление тикетом», валидация queue_id, POST priority с пересчётом SLA.

### Hotfix

- admin.js: queueReloadLock при ticket_event_committed.
- POST /api/tickets/{id}/queue: валидация queue_id (существует, is_active). GET /public_api/queues: по умолчанию только с open_count &gt; 0; include_empty; сортировка open_count desc, queue_code asc.

### API

- **POST** /api/tickets/{id}/priority — body: priority (P1..P5), reason. Пересчёт SLA, событие `priority_changed`.

### Admin UI

- В строке тикета: кнопки «Взять себе» (для `new` и без assignee), «Очередь» (модалка) и «Открыть». Модалка: Статус, Назначить, Очередь (смена очереди, приоритет, Reroute). Русские подписи статусов в UI; в API — канонические имена (New, Triaged, In Progress, Waiting on User, Waiting on Vendor, Resolved, Closed).

---

## Этап 10.3.1: Русификация UI очереди + защита API

- На публичной очереди: русские подписи статусов и приоритетов (канонические значения в БД/API не меняются). Приоритеты: P1→Критический, P2→Высокий и т.д.
- GET /public_api/queue/tickets: обязательный queue_id; limit 1..200, offset 0..10000; при невалидных — 400 validation_error.
- GET /public_api/queue/stats: days 1..90; при невалидных — 400.

---

## Этап 10.4: Chat-first интерфейс тикета (deprecated)

Единое окно чата с таймлайном, WebSocket, переключатель public/internal. **С Stage 10.5 управление тикетом переведено на Action Dock и inline-панели; slash-команды из UI убраны.**

- ticket.html/css/js: верхняя панель, таймлайн (сообщения + system events + tool_call), composer с переключателем «Внутренняя заметка». Realtime через /ws_ui (subscribe_ticket, ticket_event_committed), fallback polling 25 с.
- Slash-команды (исторически): /status, /assign, /queue, /priority, /reroute, /close, /worklog, /tool — в Stage 10.5 заменены на Action Dock.

---

## Этап 10.5: Action Dock + Inline Panels

Управление тикетом: таймлайн сверху, Action Dock над composer, inline-панели вместо модалок и slash-команд.

### Компоновка

- Верхняя панель: код, статус, очередь, исполнитель, приоритет, SLA, Live/Обновление по опросу.
- Action Dock: Статус, Назначить, Очередь, Приоритет, Инструменты ПК, Трудозатраты, Закрыть, Перемаршрутизация.
- Inline-панель открывается под Dock; формы для статуса, назначения, очереди, приоритета, закрытия, трудозатрат; инструменты ПК — по сценариям (Диагностика, Сеть, Логи и т.д.), подтверждение для рискованных операций.

### RBAC

- **auditor:** Action Dock отключён (кнопки disabled).
- **admin/support:** полный доступ. Роль из snapshot (`actor_role`).

API: POST status, assign, queue, priority, reroute, close, worklogs, read; GET tools, snapshot (с actor_role), admin/users, admin/tickets/queues; WebSocket /ws_ui.

---

## Этап 10.6: Единая рабочая очередь + профиль инициатора

Целевая бизнес-модель без изменения Protocol V3 wire-контракта:

- Канонические статусы тикетов хранятся в snake_case: `new`, `queued`, `assigned`, `in_progress`, `waiting_on_user`, `waiting_on_internal_team`, `waiting_on_vendor`, `waiting_on_approval`, `scheduled`, `resolved`, `closed`, `canceled`.
- `queued` означает маршрутизированную заявку без исполнителя, `assigned` — исполнитель есть, но активная работа ещё не начата.
- UI продолжает русифицировать статусы; soft-normalization на сервере принимает legacy-значения старых клиентов.
- Классификация приоритета строится по `urgency` + `importance` + текстовым обоснованиям. Квадрант даёт `priority_class` (`P0..P3`), а legacy `priority` остаётся внутренним SLA-слоем совместимости.
- `requester_profile` хранится в `tickets.custom_fields.requester_profile`, `requester_display_name` вычисляется по правилу `full_name -> user_display_name -> requester_id`.
- В snapshot/list добавлены `priority_class`, `effective_priority`, `requester_profile`, `requester_display_name`, `requires_operator_action`; в snapshot рабочей области также доступны `queue_members`, `assignable_users`, `available_queues`, `queue_auto_assign_enabled`, `device_metadata`, `ola`.
- POST `/api/tickets/{id}/requester_profile` обновляет профиль инициатора, не изменяя `requester_id` (RBAC-идентификатор).
- Назначение исполнителя: `admin` может ручное/auto (`auto_assign=true`), `support` может назначать только на себя. Для auto сервер выбирает оператора с минимальным `active_count`, затем по самому давно не назначавшемуся. Новый тикет при автоназначении переводится в `assigned`.
- Лимит `3` считается только по статусу `in_progress`; `assigned`, `queued` и waiting-статусы не занимают активный слот, но `assigned` и waiting-статусы сохраняют назначение за оператором.
- При `take_self` (новый тикет без assignee) сервер может автоматически перенести тикет в целевую очередь по настройке `TICKET_TAKE_QUEUE_MODE` (`keep|common|test|<queue_code>`). Коды очередей берутся из `TICKET_TAKE_QUEUE_COMMON_CODE` / `TICKET_TAKE_QUEUE_TEST_CODE`.
- Аудит бизнес-изменений (`status_changed`, `priority_changed`, `assignee_changed`, `queue_changed`, `requester_profile_changed`) хранится в `ticket_events` с actor/old_value/new_value/reason/comment и отображается в карточке тикета.

---

## Этап 11: SLA Calendar + OLA

Бизнес-календари для SLA (рабочие часы, праздники), queue-level OLA (ack/processing).

### База данных (миграция 029)

- **ticket_business_calendars:** id, code, name, timezone, weekly_hours_json, holidays_json, is_active.
- **ticket_sla_policies:** calendar_id (FK, nullable).
- **ticket_queue_ola_targets:** queue_id, priority, ack_min, processing_min.
- **tickets:** ola_queue_id, ola_started_at, ola_ack_due_at, ola_ack_at, ola_ack_breached_at, ola_processing_due_at, ola_processing_at, ola_processing_breached_at, ola_paused_at, ola_paused_seconds.

### Feature flags

- SLA due_at рассчитывается по календарю, если `ticket_sla_policies.calendar_id` задан; иначе используется 24x7 fallback.
- `TICKET_OLA_ENABLED` — учёт OLA. Legacy fallback starts OLA при create/queue change, closes ack при assign, closes processing при handoff/Resolved/Closed. If `request_template.ola_policy` is present, its `start_conditions`, `stop_conditions.ack`, `stop_conditions.processing`, `pause_conditions`, `resume_conditions`, targets and `breach_actions` control runtime behavior.
- OLA source tracking: `custom_fields.ola_runtime.policy`, `queue_id`, `start_reason`, `ack_stop_reason`, `processing_stop_reason`, `pause_reason`, `resume_reason`, `breach_types`.
- OLA events: `ola_started`, `ola_ack_stopped`, `ola_processing_stopped`, `ola_paused`, `ola_resumed`, `ola_breached`.

### Calendar engine

- add_business_minutes(start_utc, minutes, calendar), business_seconds_between(start_utc, end_utc, calendar). Формат weekly_hours_json, holidays_json.

### API

- Admin: GET/POST/PATCH /api/admin/tickets/calendars; GET/PUT /api/admin/tickets/queues/{id}/ola_targets. В POST/PATCH sla_policies — calendar_id. GET /api/tickets/{id}/sla — при TICKET_OLA_ENABLED блок **ola** в ответе.

---

## Этап 12: Operational Hardening

Retention/archive, backup/restore baseline, runbooks.

### Retention/Archive (миграция 030)

- **ticket_events_archive**, **ticket_admin_audit_archive** — перенос по политикам (180 и 365 дней).
- **ticket_retention_runs:** id, started_at, finished_at, status, moved_events, moved_audit, error.

**Конфигурация:** TICKET_RETENTION_ENABLED, TICKET_EVENTS_HOT_RETENTION_DAYS (180), TICKET_ADMIN_AUDIT_HOT_RETENTION_DAYS (365), TICKET_RETENTION_BATCH_SIZE, TICKET_RETENTION_MAX_BATCHES_PER_RUN, TICKET_RETENTION_DRY_RUN.

**Backup baseline:** daily full (pg_basebackup), WAL archiving, retention 14 daily + 8 weekly. Runbooks: RUNBOOK_BACKUP_RESTORE.md, RUNBOOK_RETENTION_ARCHIVE.md, RUNBOOK_INCIDENT_DB_RECOVERY.md.

---

## Чеклист этапов 10–12

### Миграции

Применить вручную на каждом окружении:

```bash
cd server
export DATABASE_URL="postgresql+asyncpg://user:pass@host:5432/dbname"
alembic upgrade head
alembic current   # ожидаемая ревизия 030 (или выше с учётом 031, 032)
```

### Stage 10: bootstrap ui_users

1. Включить dual-mode: AUTH_UI_DB_USERS_ENABLED=true, AUTH_UI_CONFIG_FALLBACK_ENABLED=true.
2. Заполнить ui_users из USERS (скрипт bootstrap_ui_users.py).
3. После проверки: AUTH_UI_CONFIG_FALLBACK_ENABLED=false.

### Retention

- run_retention_and_record(get_session) вызывать по расписанию (cron или фоновая задача). На staging TICKET_RETENTION_DRY_RUN=true; на production после проверки TICKET_RETENTION_DRY_RUN=false, TICKET_RETENTION_ENABLED=true.

### Stage 11

- OLA: вызовы при create, queue change, assign (когда есть API назначения), Resolved/Closed. `TicketSlaService` считает due_at через `calendar_engine` для policy calendar/business hours и использует 24x7 fallback без календаря.

---

## Вложения в сообщениях

(Обновление 2026-02-13.)

**POST /api/tickets/{ticket_id}/message:**
- Поддержка `attachment_refs: string[]`; допускается пустой `text` при наличии refs.
- Валидация refs по БД: артефакт существует, тот же ticket_id и device_id.
- В ticket_events.payload сохраняются нормализованные `attachments` и исходные `attachment_refs`; в ответе — `attachments_count`.

**GET /api/tickets/{id}, GET /api/tickets/{id}/messages:**
- В messages возвращаются `attachments` (по умолчанию пустой массив), нормализация sender: from → from_role → sender_role; в /messages — `attachment_refs`.

**Сценарий:** загрузка файла POST /api/upload (ticket_id, kind=file) → artifact_id → отправка сообщения с attachment_refs. В ticket.html отображаются превью изображений/видео и карточка скачивания; URL скачивания — attachment.url или /api/artifacts/{id}/download.

См. также [ARTIFACTS_API.md](ARTIFACTS_API.md).

---

## Модель приоритетов P0..P3 (актуальная)

*(Обновление 2026-03-12. Миграция 041.)*

### Контракт API (POST `/api/tickets/{id}/priority`)

Единственный вход — `urgency` (bool), `importance` (bool) и обязательные обоснования:

| Поле | Тип | Ограничение |
|---|---|---|
| `urgency` | boolean | обязательно (если не передан shortcut `priority`) |
| `importance` | boolean | обязательно (если не передан shortcut `priority`) |
| `urgency_reason` | string | обязательно, 1–500 символов |
| `importance_reason` | string | обязательно, 1–500 символов |
| `priority` | string (shortcut) | опционально: `P0`, `P1`, `P2`, `P3` — разворачивается в urgency+importance |

**Shortcut `priority` принимает только `P0..P3` (новая каноника). Legacy-значения `P1..P5` из старого API (P1→urgency+importance, P2→urgency, …) больше не принимаются.**

### Маппинг P0..P3 → urgency/importance

| priority_class | urgency | importance | legacy priority (SLA) |
|---|---|---|---|
| P0 | true | true | P1 |
| P1 | true | false | P2 |
| P2 | false | true | P3 |
| P3 | false | false | P4 |

Маппинг определён в `tickets/statuses.py` (`PRIORITY_CLASS_TO_FLAGS`, `PRIORITY_CLASS_TO_LEGACY_PRIORITY`).

### priority в БД и ответах

Поле `tickets.priority` хранит legacy-значение (`P1..P4`) для расчёта SLA. В ответах API это внутреннее поле. **Основной контракт для UI и очереди** — `priority_class` из `custom_fields` (строка `P0..P3`).

Запросы с сортировкой по priority_class используют индекс:
```sql
ix_tickets_custom_fields_priority_class ON tickets ((custom_fields->>'priority_class'))
WHERE custom_fields ? 'priority_class'
```

### Ограничение обоснований

Поля `urgency_reason` и `importance_reason` ограничены 500 символами:
- Валидация в `normalize_ticket_priority_inputs` (ValueError при превышении).
- Колонки БД: `VARCHAR(500)` с CHECK-ограничениями `ck_tickets_urgency_reason_len` / `ck_tickets_importance_reason_len`.

---

## Auto-assign: транзакционная блокировка

*(Обновление 2026-03-12.)*

При `auto_assign=true` в POST `/api/tickets/{id}/assign` выбор оператора выполняется через метод `select_assignee_for_update` репозитория, который:

1. Запрашивает список кандидатов (admin/support, is_active=true) по нагрузке (active_count ASC, last_ticket_assigned_at ASC).
2. Для первого кандидата с `active_count < MAX_ACTIVE_TICKETS_PER_OPERATOR` выполняет `SELECT ... FOR UPDATE SKIP LOCKED` на строке `ui_users`.
3. Перепроверяет счётчик после блокировки.
4. При успехе возвращает `user_login`; если строка уже заблокирована конкурирующей транзакцией — переходит к следующему кандидату.

Это исключает гонку при параллельных запросах auto-assign.

`MAX_ACTIVE_TICKETS_PER_OPERATOR = 3` определён в `tickets/assignment_service.py`; в лимит входят только тикеты со статусом `in_progress`.

### Единый поток назначения (assign_ticket)

`TicketAssignmentService.assign_ticket(...)` инкапсулирует: `update_ticket` → `add_event(assignee_changed)` → `mark_assigned` → `close_ola_ack`. Handler `handle_ticket_assign` вызывает этот метод вместо прямых вызовов репозитория, логика смены очереди (`queue_changed`) остаётся в handler.

---

## Public Queue API — валидация параметров

*(GET `/public_api/queue/tickets`, GET `/public_api/queue/stats`)*

| Параметр | Тип | Диапазон | По умолчанию |
|---|---|---|---|
| `limit` | integer | 1–200 | 100 |
| `offset` | integer | 0–10000 | 0 |
| `days` | integer | 1–90 | 7 |

При невалидном значении (нечисловое, вне диапазона) — **400 validation_error** с `details` (имя параметра и допустимый диапазон).

---

## Проверка is_active очереди при take_self

При "взятии" тикета оператором (take_self) с переносом в целевую очередь: если `target_queue.is_active == False`, перенос не выполняется (тикет остаётся в текущей очереди). Это защитная проверка на случай изменения состояния очереди в репозитории.
