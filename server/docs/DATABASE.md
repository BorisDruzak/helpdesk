# База данных PostgreSQL

Документ описывает схему и использование PostgreSQL в Helpdesk.

**Требования:** PostgreSQL 12+. Подключение: `DATABASE_URL` (формат `postgresql+asyncpg://user:password@host/dbname`).  
**Миграции:** Alembic, каталог `server/app/db/migrations/versions/`.  
**Модели:** `server/app/db/models.py`.

---

## Роль PostgreSQL (Source of Truth)

PostgreSQL является **единственным источником истины** для:

- тикетов и истории событий тикетов;
- исторических снимков устройств и привязок;
- тикетных операций, решений consent и доказательств;
- артефактов и UI-аутентификации.

Runtime-данные браузерского интерфейса и кэши хранятся в **StateManager** в памяти, не в БД. Управление агентами, transport и delivery принадлежат Endpoint Platform.

---

## Таблицы

### Тикеты и события

| Таблица | Назначение | Где используется |
|--------|------------|-------------------|
| **tickets** | Тикет поддержки, привязан к устройству. | `TicketEventsRepo`: создание/получение/обновление тикета, список тикетов. API: создание тикета, получение тикета, закрытие. |
| **ticket_events** | События тикета: сообщения, процессный lifecycle и исторические доказательства. | `TicketEventsRepo`: добавление, replay и доступ к артефактам. Источником управления агентскими операциями служит Endpoint Platform. |

**tickets:** `ticket_id` (PK), `ticket_code` (UNIQUE, формат T-000001, миграция 031), `device_id`, `title`, `description`, `status`, `created_at`, `updated_at`; расширенные поля (миграция 018); `ticket_type` (`varchar(64)`, миграция 061, используется как `request_kind` для маршрутизации форм), `priority`, `impact`, `urgency`, `importance`, `urgency_reason`, `importance_reason`, `requester_id`, `assignee_id`, `queue_id`, `category_id`, `service_id`, `subcategory_id`, `resolved_at`, `closed_at`, `sla_policy_id`, таймеры FRT/Resolution, `tags` (JSONB), `custom_fields` (JSONB), `external_ref`, `resolution_code`, `root_cause`, `reopen_count`, `parent_ticket_id`. Stage 10.2 (миграция 032): `manual_rank` (BIGINT NULL), `manual_rank_updated_at`, `manual_rank_updated_by` — ручной порядок в очереди. P0 contract hardening (migration 081): `status` is constrained by `ck_tickets_status_canonical` to `new`, `queued`, `assigned`, `in_progress`, `waiting_on_user`, `waiting_on_internal_team`, `waiting_on_vendor`, `waiting_on_approval`, `scheduled`, `resolved`, `closed`, `canceled`; legacy `triaged` is only an input/backfill alias and is never stored. `requester_id` is `NOT NULL` and guarded by `ck_tickets_requester_id_non_empty`; legacy null/blank rows are backfilled as `device:<device_id>` or `legacy:<ticket_id>`, and the SQLAlchemy `Ticket` model applies the same fallback before direct ORM inserts/updates.
P1 Service Catalog (migration 082) adds explicit ticket reporting/process fields: `catalog_service_id`, `catalog_offering_id`, `service_code`, `offering_code`, `request_type`, `business_criticality`, `reporting_category`, `service_owner_actor_id`, `support_group_code`. These fields are separate from legacy `tickets.service_id`; `custom_fields.service_catalog` stores the selected catalog/policy snapshot.
**ticket_events:** `id` (PK), `ticket_id`, `device_id`, `agent_seq` (nullable historical correlation), `event_type`, `payload` (JSONB), `trace_id`, `event_id`, `operation_id`, `created_at`. Canonical timeline/replay ordering is deterministic: `ORDER BY created_at ASC, id ASC`.

**Service Catalog (migration 082, Request Studio hardening migration 106):** `helpdesk_services`, `helpdesk_service_offerings`, `helpdesk_service_catalog_audit`, `request_studio_publish_tokens`. Catalog services are requester-facing process objects and may link to CMDB `registry_services`; offerings link services to `request_templates` / form schemas and policy overrides. Request Studio publish tokens store only `token_hash` and `nonce_hash` for one-time HMAC/nonce confirmation, plus draft hash, actor binding, TTL and used-at metadata; raw confirmation tokens are never persisted. Indexes cover lifecycle/visibility, offering full code, offering template key, token lookup/expiry/actor binding and ticket service/offering/reporting dimensions. P1.1 adds no schema migration; baseline catalog data is managed by the idempotent `scripts/seed_service_catalog.py` setup command and should be retired, not deleted, if tickets reference it. See [SERVICE_CATALOG.md](SERVICE_CATALOG.md).

**Retired local Knowledge/AI schema (revision 134):** migrations `083`–`087`, `110`–`113`, `117`–`119`, `121` and `123` remain immutable historical Alembic sources, but revision `134` drops their approved 45-table Knowledge/AI graph, including `ticket_knowledge_links` and `problem_known_error_links`, in static historical reverse-FK order. It preserves `ticket_kb_links`, tickets, problems, resolution passports, UI users/sessions/RBAC, consent and all Registry tables. `TicketKbLink`, its repository and the ticket snapshot may expose `ticket_kb_links` only as a read-only historical projection: they do not mutate links, resolve local Knowledge or activate local content behavior. Sanitized `knowledge_attempts` is likewise read-only history. Revision 134 is forward-only: application rollback plus a verified PostgreSQL backup restore is the only rollback path; never use Alembic downgrade to recreate local Knowledge data.

**Quality Loop (migrations 088-089):** `ticket_feedback`, `ticket_reopen_events`, `ticket_quality_reviews`, `ticket_quality_review_comments`, `continuous_improvement_actions`, `service_quality_snapshots`, and `quality_policies`. These tables implement structured CSAT, mandatory reopen reason taxonomy, internal QA review queues, continuous improvement actions and aggregate service/offering quality analytics. Migration `089` adds the partial unique index `uq_ticket_feedback_latest_per_ticket` so only one `is_latest=true` feedback row can exist per ticket. Analytics snapshots intentionally avoid requester PII and are recomputed by the quality snapshot scheduler plus the manual recompute API. See [QUALITY_LOOP.md](QUALITY_LOOP.md).

**Problem Management (migrations 090-091):** `problems`, `problem_ticket_links`, `problem_rca_records`, `problem_affected_objects`, `problem_detection_rules`, `problem_candidates`, `problem_activity_events`, `problem_scanner_runs`, and `problem_slo_policies`. The former `problem_known_error_links` physical table is retired by revision `134`; Problem Management continues with local lifecycle summaries and no local Knowledge-link persistence. Migration `090` implements P4 candidates, problem lifecycle, many-to-many ticket links, versioned RCA, affected service/offering/registry object links, opaque external-reference links and append-only activity audit. Migration `091` adds scheduled scanner observability, candidate fingerprint/dedup/cooldown/merge metadata, failed-QA/service-gap thresholds, and problem SLO due milestones. Migration `090` also adds nullable `problem_id` and `problem_candidate_id` to `continuous_improvement_actions` and extends action/source enums for RCA, permanent-fix, workaround validation and known-error update actions. Problem analytics are aggregate-only and avoid requester PII. See [PROBLEM_MANAGEMENT.md](PROBLEM_MANAGEMENT.md).

**Change Enablement (migration 092):** `changes`, `change_risk_assessments`, `change_plans`, `change_approvals`, `change_windows`, `change_affected_objects`, `change_tasks`, `change_pir_records`, `change_activity_events`, and `change_policies`. P5 models change requests as first-class entities separate from tickets/problems, with type `standard|normal|emergency`, risk/impact assessment, auditable CAB-lite approvals, standard preapproval catalog metadata on policies, one-off/recurring maintenance and blackout windows, implementation and rollback plans, implementation tasks, PIR and aggregate no-PII metrics. Calendar recurrence uses existing `change_windows.recurrence_rule`; emergency retrospective uses existing `change_policies.max_emergency_retro_hours`. Migration `092` also adds nullable `continuous_improvement_actions.change_id` and extends improvement action source compatibility for failed/rolled-back changes. See [CHANGE_ENABLEMENT.md](CHANGE_ENABLEMENT.md).

**Diagnostic Layer (migration 074):** `diagnostic_sessions`, `diagnostic_steps`, `diagnostic_evidence`, `diagnostic_findings`, `diagnostic_bundles`. These tables are ticket-scoped diagnostic state, not ticket workflow state. They normalize Endpoint operations, playbook runs, observer root traces, historical remote-assist snapshots, artifacts and manual checks into support-facing evidence/findings/bundles while leaving ticket state unchanged. Main repo/service entrypoints: `server/app/repos/diagnostics_repo.py` and `server/diagnostics/*`.

**Legacy cutover marker (migration 143):** `server_config.endpoint_agent_control_plane_authority=endpoint_platform` records the one-way control-plane transfer. Historical agent/build/update tables remain intact in this release and are not used by Helpdesk runtime.

**Diagnostic Provider Config (migration 075):** `diagnostic_providers`, `diagnostic_capabilities`, `diagnostic_capability_versions`, `diagnostic_provider_configs`, `diagnostic_provider_credential_refs`, `diagnostic_provider_audit`. Capability descriptors still remain computed from manifests/providers for runtime compatibility, while these tables persist provider configuration lifecycle, credential references, redacted integration config and audit rows for server connectors such as Zabbix. Main entrypoints: `server/app/repos/diagnostic_provider_config_repo.py`, `server/diagnostics/provider_config.py`, and `/api/diagnostics/providers/configs*`.

**Agent Recipe Runtime Dependencies (migration 078):** `operation_dependencies` plus nullable `operations.phase`. These fields model ticket-bound runtime prerequisites such as installing/upgrading the protected `agent_recipe_runner` before a recipe operation can continue. Parent recipe operations keep the existing `operations.status` lifecycle and use phase values like `waiting_dependency`, `installing_dependency`, `sending_run_recipe` and `running_recipe`; dependency rows link to the module install operation created by reconcile.

**Agent Recipe Runner Fleet Rollout (migrations 079-080):** `runner_rollout_plans`, `runner_rollout_waves`, `runner_rollout_targets`, `runner_rollout_events`. These tables model admin-controlled canary/wave rollout and rollback for the protected `agent_recipe_runner` module. They store plan state separately from ticket-bound runtime dependencies, while actual delivery still goes through `device_desired_modules` and `modules.reconcile.reconcile_device`.

**Тикетная система (миграция 018):**  
**ticket_queues** — очереди (ServiceDesk L1, SysAdmins, Network, 1C, Security).  
**ticket_queue_members** — участники очередей.  
**support_queue_saved_views** — DB-backed Queue Mode saved views and column presets for personal, queue-shared and global support workspace scopes (migration 072).
**ticket_categories** — иерархия category/service/subcategory.  
**ticket_sla_policies**, **ticket_sla_targets**, **ticket_priority_matrix** — SLA и матрица impact×urgency→priority.  
**ticket_routing_rules** — правила маршрутизации.  
**ticket_watchers**, **ticket_links**, **ticket_worklogs** — наблюдатели, связи тикетов, трудозатраты.

**Stage 10.3:** POST `/api/tickets/{id}/queue` — валидация `queue_id` (очередь существует, is_active); при смене приоритета (POST `/api/tickets/{id}/priority`) пересчёт SLA и событие `priority_changed`. См. [TICKET_SYSTEM.md](TICKET_SYSTEM.md#этап-103-admin-queue-uxlogic-refactor).

**Stage 10.5:** UI тикета — Action Dock и inline-панели; изменений схемы БД нет, в snapshot добавлено поле `actor_role` для RBAC в UI. См. [TICKET_SYSTEM.md](TICKET_SYSTEM.md#этап-105-action-dock--inline-panels).

**Этап 2 (Routing + SLA):** маршрутизация по правилам (`TicketRoutingService`), fallback `servicedesk_l1`; manual queue lock в `tickets.custom_fields`; SLA таймеры и breach/reminders (`TicketSlaService`, `TicketSlaWatchdog`). Подробнее: [TICKET_SYSTEM.md](TICKET_SYSTEM.md#этап-2-routing--sla-core).

**Этап 3 (Workflow + RBAC):** единый FSM переходов статусов (`tickets/statuses.py`, `tickets/workflow_service.py`), RBAC и ownership в API (requester только свои тикеты), подтверждение requester перед переходом Resolved→Closed и watchdog без авто-закрытия (`TicketAutoCloseWatchdog`), индекс `ix_tickets_status_resolved_at` (миграция 019). Подробнее: [TICKET_SYSTEM.md](TICKET_SYSTEM.md#этап-3-workflow--rbac-enforcement).

**Этап 4 (Visibility + Worklog):** в payload событий `chat_message` хранится поле **visibility** (`public` | `internal`); requester при чтении получает только public. Таблица **ticket_worklogs** используется для трудозатрат (append-only); при добавлении записывается событие **worklog_added** в ticket_events (payload: worklog_id, spent_minutes, actor_id). Агрегат **worklog_total_minutes** доступен в GET ticket/snapshot и через GET `/api/tickets/{id}/worklog_total`. Индекс `ix_ticket_worklogs_ticket_created_at` (миграция 020). Подробнее: [TICKET_SYSTEM.md](TICKET_SYSTEM.md#этап-4-communication-visibility--worklog).

**Stage 5 (Relations + Resolution + Metrics):** `ticket_resolution_codes` and `ticket_links` remain the Stage 5 relation/resolution schema. `TicketKbLink` / `ticket_kb_links` and related legacy link-event variants are a read-only historical projection of the deleted local feature; they are not created or mutated. Migration indexes `021`–`022` remain history. See [TICKET_SYSTEM.md](TICKET_SYSTEM.md#этап-5-relations--resolution-governance--metrics).

**Этап 6 (Hardening + Notifications):** таблица **ticket_notifications** (id, actor_id, ticket_id, event_type, payload, is_read, created_at, read_at) для in-app уведомлений; индексы (actor_id, is_read, created_at), (ticket_id, created_at). Миграция 023. Подробнее: [TICKET_SYSTEM.md](TICKET_SYSTEM.md#этап-6-hardening--notifications).

---

### События устройств

| Таблица | Назначение | Где используется |
|--------|------------|-------------------|
| **device_events** | Исторические события устройства без привязки к тикету. | Read-only evidence for Helpdesk diagnostics; current device telemetry belongs to Endpoint Platform. |

**device_events:** `id` (PK), `device_id`, `device_seq`, `event_type`, `payload` (JSONB), `trace_id`, `event_id`, `operation_id`, `created_at`. UNIQUE `(device_id, device_seq)`.

---

### Команды и операции

| Таблица | Назначение | Где используется |
|--------|------------|-------------------|
| **device_outbox** | Историческая таблица снятого Helpdesk delivery. | Сохраняется как schema residue; Helpdesk runtime не импортирует модель, не читает и не пишет её. |
| **operations** | Процессное состояние операций и Endpoint evidence. | Helpdesk отображает ticket lifecycle; command delivery и отмена принадлежат Endpoint Platform. |

**device_outbox:** `id` (PK), `device_id`, `command_id`, `command`, `params` (JSONB), `status`, `request_id`, `trace_id`, `operation_id`, `actor_role`, `retry_count`, `max_retries`, `created_at`, `sent_at`, `delivered_at`, `failed_at`, `error_code`, `error_message`.  
**operations:** `operation_id` (PK), `device_id`, `ticket_id`, `job_id`, `kind`, `tool_name`, `actor_role`, `trace_id`, `status`, `phase`, `deadline_at`, `queued_at`, `sent_at`, `accepted_at`, `started_at`, `finished_at`, `retry_count`, `max_retries`, `retry_of_operation_id`, `error_code`, `error_message`, `result_summary`, `result_event_id`, поля отмены (`cancel_target_operation_id`, `canceled_at` и др.).

**operation_dependencies:** `id` (PK), `operation_id` (FK operations), `dependency_operation_id` (nullable FK operations), `dependency_type`, `dependency_key`, `provider_id`, `module_name`, `current_version`, `target_version`, `version_constraint`, `status`, `reason`, `reason_code`, `created_at`, `resolved_at`, `timeout_at`, `resume_attempts`, `metadata_json`.

**runner_rollout_plans:** `id`, `module_name`, `target_version`, `rollback_version`, `status`, `strategy`, `canary_size`, `wave_size`, `max_concurrency`, timestamps and `metadata_json`.
**runner_rollout_waves:** `id`, `plan_id`, `wave_index`, `status`, timestamps and metadata.
**runner_rollout_targets:** `id`, `plan_id`, `wave_id`, `device_id`, target/rollback versions, target status, current version, optional install operation id and timestamps.
**runner_rollout_events:** append-only admin/audit events for plan, wave and target actions.

---

### Реестр устройств

| Таблица | Назначение | Где используется |
|--------|------------|-------------------|
| **devices** | Реестр устройств: метаданные после handshake (protocol_version, agent_version, hostname, os, capabilities, toolset_hash и т.д.). | `DevicesRepo`: создание/обновление при handshake, список устройств, получение по device_id. Handshake WebSocket, Devices API. |
| **device_config** | Желаемая и применённая конфигурация устройства (revision-based). | `DeviceConfigRepo`: чтение/запись desired_config, applied_revision. API конфигурации устройств. |
| **device_toolset_snapshots** | Снапшоты списка инструментов устройства (по toolset_hash). UNIQUE (device_id, toolset_hash). | `ToolsetSnapshotsRepo`: сохранение снапшота при list_tools, получение по device_id/snapshot_id. Handshake, Tools API, MODULES_DRIFT. |

**devices:** `device_id` (PK), `first_seen_at`, `last_seen_at`, `last_handshake_at`, `last_toolset_refresh_at`, `last_tools_changed_at`, `protocol_version`, `agent_version`, `hostname`, `os`, `capabilities` (JSONB), `tools_version`, `current_toolset_hash`, `current_toolset_snapshot_id`, `metadata` (JSONB).  
**device_config:** `device_id` (PK), `desired_revision`, `desired_config` (JSONB), `applied_revision`, `applied_at`, `last_apply_status`, `last_apply_error` (JSONB), `updated_at`.  
**device_toolset_snapshots:** `snapshot_id` (PK), `device_id`, `captured_at`, `agent_version`, `toolset_hash`, `toolset_json` (JSONB), `tool_count`. UNIQUE `(device_id, toolset_hash)`.

---

### Модули

| Таблица | Назначение | Где используется |
|--------|------------|-------------------|
| **modules** | Реестр загруженных модулей (ZIP): имя, версия, sha256, путь на диске. | `ModulesRepo`: загрузка модуля (сохранение в БД и на диск), список модулей, получение по имени/версии. Modules API upload/download. |
| **device_modules** | Установленные/активные модули на каждом устройстве. | `DeviceModulesRepo`: установка, активация, синхронизация состояния. Modules API, drift/snapshots. |

**modules:** `module_name`, `version` (PK composite), `sha256`, `size`, `storage_path`, `created_at`, `uploaded_by`, `manifest_summary` (JSONB).  
**device_modules:** `id` (PK), `device_id`, `module_name`, `version`, UNIQUE(device_id, module_name, version), `installed`, `active`, `state`, `installed_at`, `activated_at`, `last_updated_at`, `last_error_code`, `last_error_message`.

---

### Аутентификация и сессии

| Таблица | Назначение | Где используется |
|--------|------------|-------------------|
| **agent_tokens** | Токены агентов: SHA256 hash, привязка к device_id. Ротация и отзыв. | `AuthTokensRepo` (агент): проверка токена при handshake и HTTP, выдача токенов. См. [SECURITY_AND_AUTH.md](SECURITY_AND_AUTH.md). |
| **ui_tokens** | Токены UI: SHA256 hash, user_login, actor_role. | `AuthTokensRepo` (UI): проверка при API и WebSocket ui_hello, выдача при логине. |
| **auth_sessions** | Сессии аутентификации (Phase 2, для будущего session-based UI). | Зарезервировано. |
| **download_audit** | Аудит скачивания модулей: кто (token_hash), что, когда. | Запись при GET download модуля. |

**agent_tokens:** `token_hash` (PK), `token_prefix`, `device_id`, `created_at`, `expires_at`, `revoked_at`, `replaced_by_token_hash`, `rotated_at`, `last_used_at`.  
**ui_tokens:** `token_hash` (PK), `token_prefix`, `user_login`, `actor_role`, `created_at`, `expires_at`, `revoked_at`, `replaced_by_token_hash`, `rotated_at`, `last_used_at`.  
**ui_users:** `user_login`, `actor_role`, `is_active`, `failed_attempts`, `locked_until`, `last_login_at`, `last_ticket_assigned_at`, `created_at`, `updated_at` — `last_ticket_assigned_at` используется для tie-break при автоназначении.  
**access_groups / access_group_members / access_group_permissions / access_group_queue_members / access_audit:** RBAC-группы для нового `/app/admin/access`: group code/name, активность, участники по `actor_id`, grants из server-owned permission catalog, grants на очереди и append-only audit изменений.  
**registry_audience_groups / registry_audience_group_members:** content/service/notification targeting groups for Registry Visibility Foundation. They are separate from `access_groups`: membership can target service audiences but never grants RBAC permissions. Members can reference person, department, department_tree, location, access_group, role or service; `department` with `include_children=true` intentionally follows the same subtree/path expansion as `department_tree`, while `department` with `include_children=false` remains direct-current-department targeting. Archive uses `status`, not hard delete. Admin CRUD and preview expansion are under `/api/web/admin/registry/audience-groups*`.
**registry_person_department_memberships:** compatibility-safe multi-department membership table introduced by migration `120`; `registry_people.department_id` remains the primary/default department and is backfilled as `is_primary=true`.
**auth_sessions:** `session_id` (PK), `user_login`, `actor_role`, `created_at`, `expires_at`, `last_used_at`, `ip_address`, `user_agent`.  
**download_audit:** `id` (PK), `token_hash`, `token_prefix`, `module_name`, `version`, `downloaded_at`, `ip_address`, `user_agent`.

---

### Consent и артефакты

| Таблица | Назначение | Где используется |
|--------|------------|-------------------|
| **consent_decisions** | Решения по операциям, требующим согласия (approve/deny). | `OperationsRepo` / обработка waiting_consent: запись решения, обновление операции. Consent API. |
| **artifacts** | Метаданные загруженных файлов (скриншоты, запись экрана). Файлы на диске в UPLOAD_DIR. | `ArtifactsRepo`: создание при upload, get_by_id, get_by_sha256_and_operation_id (идемпотентность), delete_expired. `ArtifactService`: проверка прав при download. См. [ARTIFACTS_API.md](ARTIFACTS_API.md). |

**consent_decisions:** `operation_id` (PK, FK operations), `decision` (approved/denied), `decided_by`, `decided_at`, `reason`.  
**artifacts:** `artifact_id` (PK), `storage_path`, `original_name`, `mime_type`, `size_bytes`, `sha256`, `kind`, `device_id`, `ticket_id`, `operation_id`, `expires_at`, `created_at`. Индексы: device_id, ticket_id, operation_id, expires_at, sha256.

---

### События job (чат/задачи)

| Таблица | Назначение | Где используется |
|--------|------------|-------------------|
| **job_events** | События job (чат, tool_requested, tool_result и т.д.) с дедупликацией по message_id. | `JobEventsRepo`: добавление событий, replay по job_id. Chat/Job API, SSE. |

**job_events:** `id` (PK), `job_id`, `seq`, `ts`, `event_type`, `message_id`, `payload` (JSONB). UNIQUE `(job_id, message_id)` WHERE `message_id IS NOT NULL`.

---

### Historical agent-control-plane schema

Legacy agent build, module, token, outbox and recipe tables can remain in an
existing database as rollback history. They are deliberately not mapped by the
active Helpdesk ORM and no Helpdesk runtime writes to them. Endpoint Platform
owns active agent lifecycle and package delivery.

---

## Репозитории (app/repos)

| Репозиторий | Таблицы |
|------------|---------|
| `ticket_events_repo.py` | tickets, ticket_events |
| `device_events_repo.py` | device_events |
| `operations_repo.py` | operations, consent_decisions |
| `devices_repo.py` | devices |
| `device_config_repo.py` | device_config |
| `artifacts_repo.py` | artifacts |
| `job_events_repo.py` | job_events |

Тикеты создаются/читаются через `TicketEventsRepo` (модель `Ticket` в том же модуле).

---

## Миграции (Alembic)

Файлы в `app/db/migrations/versions/` (порядок по revision):

- `001_add_job_events.py` — job_events
- `002_add_v3_tables.py` — tickets, ticket_events, device_events
- `003_add_device_outbox.py` — device_outbox
- `004_add_device_registry.py` — devices, device_config, device_toolset_snapshots
- `005_make_agent_seq_nullable.py` — agent_seq nullable в ticket_events
- `006_add_operations.py` — operations
- `007_add_operation_id.py` — operation_id в outbox/events
- `008_add_cancel_fields.py` — поля отмены в operations
- `009_add_tool_started_unique_index.py` — уникальный индекс tool_call_started
- `010_add_modules_registry.py` — modules, device_modules
- `011_add_last_tools_changed_at.py` — last_tools_changed_at в devices
- `012_add_auth_tokens.py` — agent_tokens, ui_tokens
- `013_add_consent.py` — consent_decisions
- `014_add_download_audit.py` — download_audit
- `015_add_artifacts.py` — artifacts
- `016_add_agent_builds.py` — agent_builds, agent_build_download_audit
- `017_agent_builds_artifact_metadata.py` — artifact_filename, archive_type, mime_type в agent_builds
- `018_ticket_system_extended.py` — расширение tickets, очереди, категории, SLA, worklogs, links, watchers; seed и backfill
- `019_ticket_auto_close_index.py` — ix_tickets_status_resolved_at
- `020_ticket_worklogs_index.py` — ix_ticket_worklogs_ticket_created_at
- `021_ticket_stage5_tables.py` — ticket_stage5 (resolution codes and retained historical link projection)
- `022_ticket_stage5_indexes.py` — индексы Stage 5
- `023_ticket_notifications.py` — ticket_notifications (Stage 6)
- `024_problems.py` — problems, problem_ticket_links (Stage 7)
- `025_ticket_change_links.py` — ticket_change_links (Stage 7)
- `026_notification_prefs.py` — ticket_notification_prefs (Stage 8)
- `027_ticket_admin_config_audit.py` — ticket_sla_policies.is_active, ticket_admin_audit (Stage 9)
- `028_ui_users.py` — ui_users, ui_user_audit (Stage 10)
- `029_sla_calendar_ola.py` — ticket_business_calendars, ticket_sla_policies.calendar_id, ticket_queue_ola_targets, tickets OLA fields (Stage 11)
- `030_ticket_archive_retention.py` — ticket_events_archive, ticket_admin_audit_archive, ticket_retention_runs (Stage 12)
- `031_ticket_code.py` — tickets.ticket_code, sequence ticket_code_seq
- `032_ticket_manual_rank.py` — tickets.manual_rank, manual_rank_updated_at, manual_rank_updated_by; индексы ix_tickets_queue_manual_rank, ix_tickets_queue_open_sort (Stage 10.2)
- `038_ticket_queue_rework.py` — snake_case статусы, importance/reasons, ui_users.last_ticket_assigned_at (Stage 10.6)
- `081_ticket_contract_hardening.py` — canonical ticket status check, legacy `triaged` backfill, `requester_id` NOT NULL/non-empty check, SLA priority check, deterministic ticket event ordering indexes.
- `082_service_catalog_process_layer.py` — `helpdesk_services`, `helpdesk_service_offerings`, `helpdesk_service_catalog_audit`, explicit ticket catalog/reporting fields and service/offering reporting indexes.
- `106_request_studio_publish_tokens.py` — `request_studio_publish_tokens` one-time hashed confirmation-token state for Request Studio safe publish.
- `083_knowledge_platform.py` through `123_knowledge_correction_reviewing_status.py` — immutable historical sources for the removed local Knowledge/AI schema; no local runtime is active from them.
- `134_retire_local_knowledge_ai_schema.py` — forward-only removal of exactly the approved 45-table historical Knowledge/AI graph, including `ticket_knowledge_links` and `problem_known_error_links`; preserves Helpdesk, auth/RBAC, consent and Registry tables. Roll back with a verified PostgreSQL backup restore, never Alembic downgrade.
- `088_quality_loop.py` — structured ticket feedback, reopen events, QA reviews, improvement actions, service quality snapshots and quality policies.
- `089_quality_loop_production_hardening.py` — latest feedback partial unique index and quality snapshot scheduler metadata.
- `090_problem_management_rca.py` — problem candidates, problem records, ticket links, versioned RCA, known-error/workaround links, affected objects, detection rules and problem activity events.
- `091_problem_management_production_hardening.py` — scanner run records, candidate fingerprint/dedup/cooldown/merge metadata, detection thresholds for failed QA/content gaps and problem SLO policies/due milestones.
- `039_add_servicedesk_test_queue.py` — upsert очереди `servicedesk_test` (active) для публичной ссылки `/queue/test`
- `062_access_control_groups.py` — access groups, group permissions, group queue grants and access_audit для `/app/admin/access`
- `072_support_queue_saved_views.py` — `support_queue_saved_views` for DB-backed support Queue Mode saved views and column presets.

Команды: из каталога `server` — `alembic upgrade head`, `alembic revision --autogenerate`.

**Подгрузка .env:** Alembic сам не читает `server/.env`. Для запуска миграций с теми же настройками, что и сервер, используйте скрипт `server/scripts/run_migrations.py` (подгружает `server/.env` и вызывает alembic). Пример: из каталога `server` — `python scripts/run_migrations.py upgrade head` или `python scripts/run_migrations.py current`.

### Миграции на production Helpdesk host

- Helpdesk работает отдельно от Endpoint Platform на `osn_admin@192.168.100.19`. Его база, роль PostgreSQL, пользователь ОС и runtime-каталоги не разделяются с Endpoint.
- Production-конфигурация хранится только в `/etc/helpdesk/helpdesk.env` с правами `root:root` и `0600`; её значения не коммитятся и не выводятся.
- Новые релизы выполняются из Windows только через `python scripts/deploy_helpdesk_release.py --commit <commit>`: скрипт создаёт immutable release в `/opt/helpdesk/releases`, переключает `/opt/helpdesk/current` и запускает миграцию до перезапуска сервисов.
- Для проверки схемы после deploy:
  ```text
  python scripts/run_remote_migrations.py current
  ```
  Скрипт запускает `server/scripts/run_migrations.py` внутри текущего Helpdesk release. Обычный production deploy выполняет `upgrade head` сам; не применяйте ручные миграции к Endpoint database.

---

## Registry retirement: PR-11 preflight only

This repository does not yet contain the destructive PR-11 migration. The
reviewed scope is declared in `scripts/registry_retirement_manifest.py`; its
read-only gate is run with:

```text
python scripts/rehearse_registry_retirement.py --workspace . --dry-run
```

The command neither connects to PostgreSQL nor executes Alembic or DDL. A
non-ready result is expected until every local Registry route, writer and
consumer has been cut over. Only a release operator may use `--require-ready`
as a prerequisite for creating/applying the later forward-only migration. That
mode requires `--expected-environment <immutable-release-environment>` and
derives the exact Git `HEAD` revision from the workspace; signed evidence must
match both. Evidence expires 24 hours after attestation, permits at most five
minutes of future clock skew, and must be strictly ordered backup → restore →
clone catalog → maintenance/writers stop → attestation. A stale, future,
misordered, cross-environment or cross-revision bundle is not release-ready.

The later migration must first detach the approved legacy Registry columns
from `tickets`, `user_consent_requests` and `helpdesk_services`; it may then
drop the declared Registry/registration/session/pairing and retired local
content/AI targets in the manifest's deterministic reverse-FK order, validated
against `server/app/db/models.py` without a database connection. It must retain
actual Helpdesk session/identity tables `ui_users`, `auth_sessions`, `ui_tokens`,
`ui_user_audit`, `ui_password_reset_requests` and `ticket_public_sessions`; RBAC
tables `access_groups`, `access_group_members`, `access_group_permissions`,
`access_group_queue_members`, `access_audit`, `ticket_queues`,
`ticket_queue_members`, `ticket_queue_ola_targets`; plus `tickets`,
`user_consent_requests` and the `TicketKbLink` / `ticket_kb_links` read-only historical projection.
Do not use `alembic downgrade` for this programme:
rollback is application rollback plus a tested database restore.

## Связанные документы

- [RUNBOOK_BACKUP_RESTORE.md](RUNBOOK_BACKUP_RESTORE.md) — конфигурация и восстановление PostgreSQL.
- [RUNBOOK_POSTGRES_EXTERNAL_READONLY.md](RUNBOOK_POSTGRES_EXTERNAL_READONLY.md) — доступ к PostgreSQL извне (listen_addresses, pg_hba, firewall, read-only пользователь для другого агента).
- [SECURITY_AND_AUTH.md](SECURITY_AND_AUTH.md) — UI-аутентификация и защищённые browser-сеансы.
- [ARTIFACTS_API.md](ARTIFACTS_API.md) — upload/download артефактов, таблица artifacts.
- [MODULES_API.md](MODULES_API.md) — модули, tables modules, device_modules.
- [ENDPOINT_OPERATION_CONTRACT.md](ENDPOINT_OPERATION_CONTRACT.md) — Endpoint operation links and reconciliation.
