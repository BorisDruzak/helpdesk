# База данных PostgreSQL

Документ описывает схему и использование PostgreSQL на сервере PC Agent.

**Требования:** PostgreSQL 12+. Подключение: `DATABASE_URL` (формат `postgresql+asyncpg://user:password@host/dbname`).  
**Миграции:** Alembic, каталог `server/app/db/migrations/versions/`.  
**Модели:** `server/app/db/models.py`.

---

## Роль PostgreSQL (Source of Truth)

После миграции на Protocol V3 PostgreSQL является **единственным источником истины** для:

- тикетов и истории событий тикетов;
- событий устройств (без привязки к тикету);
- очереди команд к агентам (device outbox);
- реестра устройств, конфигураций и снапшотов toolset;
- операций (run_tool, cancel и т.д.) и решений consent;
- артефактов (скриншоты, запись экрана);
- модулей (реестр ZIP) и состояния модулей на устройствах;
- аутентификации (токены агентов и UI, сессии, аудит скачиваний).

Runtime-данные (подключённые агенты, UI-сессии, кэши) хранятся в **StateManager** в памяти, не в БД.

---

## Таблицы

### Тикеты и события

| Таблица | Назначение | Где используется |
|--------|------------|-------------------|
| **tickets** | Тикет поддержки, привязан к устройству. | `TicketEventsRepo`: создание/получение/обновление тикета, список тикетов. API: создание тикета, получение тикета, закрытие. |
| **ticket_events** | События тикета: сообщения чата, command lifecycle (tool_call_started, tool_call_result и т.д.). Упорядочивание по `agent_seq` в рамках тикета. | `TicketEventsRepo`: добавление событий, replay по тикету, дедупликация по `(device_id, ticket_id, agent_seq)`. Проверка доступа к артефактам: `ticket_contains_artifact()`. Пайплайн WS агента (`agent_outbox_ingest`, `agent_command_result`) при сохранении событий от агента и сервера. |

**tickets:** `ticket_id` (PK), `ticket_code` (UNIQUE, формат T-000001, миграция 031), `device_id`, `title`, `description`, `status`, `created_at`, `updated_at`; расширенные поля (миграция 018); `ticket_type` (`varchar(64)`, миграция 061, используется как `request_kind` для маршрутизации форм), `priority`, `impact`, `urgency`, `importance`, `urgency_reason`, `importance_reason`, `requester_id`, `assignee_id`, `queue_id`, `category_id`, `service_id`, `subcategory_id`, `resolved_at`, `closed_at`, `sla_policy_id`, таймеры FRT/Resolution, `tags` (JSONB), `custom_fields` (JSONB), `external_ref`, `resolution_code`, `root_cause`, `reopen_count`, `parent_ticket_id`. Stage 10.2 (миграция 032): `manual_rank` (BIGINT NULL), `manual_rank_updated_at`, `manual_rank_updated_by` — ручной порядок в очереди. P0 contract hardening (migration 081): `status` is constrained by `ck_tickets_status_canonical` to `new`, `queued`, `assigned`, `in_progress`, `waiting_on_user`, `waiting_on_internal_team`, `waiting_on_vendor`, `waiting_on_approval`, `scheduled`, `resolved`, `closed`, `canceled`; legacy `triaged` is only an input/backfill alias and is never stored. `requester_id` is `NOT NULL` and guarded by `ck_tickets_requester_id_non_empty`; legacy null/blank rows are backfilled as `device:<device_id>` or `legacy:<ticket_id>`, and the SQLAlchemy `Ticket` model applies the same fallback before direct ORM inserts/updates.
P1 Service Catalog (migration 082) adds explicit ticket reporting/process fields: `catalog_service_id`, `catalog_offering_id`, `service_code`, `offering_code`, `request_type`, `business_criticality`, `reporting_category`, `service_owner_actor_id`, `support_group_code`. These fields are separate from legacy `tickets.service_id`; `custom_fields.service_catalog` stores the selected catalog/policy snapshot.
**ticket_events:** `id` (PK), `ticket_id`, `device_id`, `agent_seq` (nullable для server-originated), `event_type`, `payload` (JSONB), `trace_id`, `event_id`, `operation_id`, `created_at`. UNIQUE `(device_id, ticket_id, agent_seq)` WHERE `agent_seq IS NOT NULL`. Canonical timeline/replay ordering is deterministic: `ORDER BY created_at ASC, id ASC`. Migration 081 adds `ix_ticket_events_ticket_created_id` and `ix_ticket_events_ticket_type_created_id` while preserving the partial unique idempotency constraint for agent-originated events.

**Service Catalog (migration 082):** `helpdesk_services`, `helpdesk_service_offerings`, `helpdesk_service_catalog_audit`. Catalog services are requester-facing process objects and may link to CMDB `registry_services`; offerings link services to `request_templates` / form schemas and policy overrides. Indexes cover lifecycle/visibility, offering full code, offering template key and ticket service/offering/reporting dimensions. P1.1 adds no schema migration; baseline catalog data is managed by the idempotent `scripts/seed_service_catalog.py` setup command and should be retired, not deleted, if tickets reference it. See [SERVICE_CATALOG.md](SERVICE_CATALOG.md).

**Knowledge Platform (migrations 083-087):** `knowledge_spaces`, `knowledge_items`, `knowledge_item_versions`, `knowledge_chunks`, `knowledge_bindings`, `knowledge_nodes`, `knowledge_edges`, `knowledge_entity_mentions`, `knowledge_feedback_events`, `knowledge_ingestion_jobs`, `ticket_knowledge_links`, `knowledge_content_packs`, `knowledge_content_pack_items`, `knowledge_rollout_policies`, `knowledge_review_tasks`, `knowledge_review_comments`, `knowledge_quality_snapshots`, `knowledge_gap_findings`, and `knowledge_search_events`. These tables implement universal knowledge spaces/items, lifecycle/versioning, chunked search/retrieval foundation, service/offering/request-template bindings, PostgreSQL graph relations, ingestion job tracking, usage/deflection metrics, normalized ticket knowledge links, idempotent content-pack audit, controlled self-service deflection rollout, operational review tasks, explainable quality snapshots, persisted gap findings and privacy-preserving search analytics. Revision `084` adds DB CHECK constraints for graph node/relation/status enums, feedback event/source-surface roles, ingestion source/status values and ticket-knowledge link enums. Revision `085` adds content pack install state and rollout policy tables. Revision `086` adds knowledge operations review/quality/gap/search tables. Revision `087` expands `knowledge_rollout_policies` with `scope_type`, before/after form flags, submit gating, skip/bypass, min/max suggestions, known-error/quality/freshness label flags, no-suggestions and API-unavailable behavior, bypass roles and effective dates; it also allows `bindings_repaired` audit rows in `knowledge_content_pack_items`. Existing `ticket_kb_links` remains compatible. See [KNOWLEDGE_PLATFORM.md](KNOWLEDGE_PLATFORM.md) and [KNOWLEDGE_OPERATIONS.md](KNOWLEDGE_OPERATIONS.md).

**Quality Loop (migrations 088-089):** `ticket_feedback`, `ticket_reopen_events`, `ticket_quality_reviews`, `ticket_quality_review_comments`, `continuous_improvement_actions`, `service_quality_snapshots`, and `quality_policies`. These tables implement structured CSAT, mandatory reopen reason taxonomy, internal QA review queues, continuous improvement actions and aggregate service/offering quality analytics. Migration `089` adds the partial unique index `uq_ticket_feedback_latest_per_ticket` so only one `is_latest=true` feedback row can exist per ticket. Analytics snapshots intentionally avoid requester PII and are recomputed by the quality snapshot scheduler plus the manual recompute API. See [QUALITY_LOOP.md](QUALITY_LOOP.md).

**Diagnostic Layer (migration 074):** `diagnostic_sessions`, `diagnostic_steps`, `diagnostic_evidence`, `diagnostic_findings`, `diagnostic_bundles`. These tables are ticket-scoped diagnostic state, not ticket workflow state. They normalize existing operations, playbook runs, observer root traces, remote assist sessions, artifacts and manual checks into support-facing evidence/findings/bundles while leaving `tickets.status`, playbook execution and `ToolExecutionService.run_tool` semantics unchanged. Main repo/service entrypoints: `server/app/repos/diagnostics_repo.py` and `server/diagnostics/*`.

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

**Этап 5 (Relations + Resolution + Metrics):** таблицы **ticket_resolution_codes** (справочник кодов резолюции), **ticket_kb_links** (ссылки на статьи БЗ); в **ticket_links** — unique по (src_ticket_id, dst_ticket_id, link_type) и check link_type IN ('duplicate','related'). События в ticket_events: ticket_link_added, ticket_link_removed, parent_ticket_changed, watcher_added, watcher_removed, kb_linked, kb_unlinked, resolution_policy_warning. Индексы миграций 021–022. Подробнее: [TICKET_SYSTEM.md](TICKET_SYSTEM.md#этап-5-relations--resolution-governance--metrics).

**Этап 6 (Hardening + Notifications):** таблица **ticket_notifications** (id, actor_id, ticket_id, event_type, payload, is_read, created_at, read_at) для in-app уведомлений; индексы (actor_id, is_read, created_at), (ticket_id, created_at). Миграция 023. Подробнее: [TICKET_SYSTEM.md](TICKET_SYSTEM.md#этап-6-hardening--notifications).

---

### События устройств

| Таблица | Назначение | Где используется |
|--------|------------|-------------------|
| **device_events** | События устройства без привязки к тикету (tools_changed, метрики и т.д.). Упорядочивание по `device_seq` в рамках устройства. | `DeviceEventsRepo`: добавление событий, replay по device_id. Пайплайн WS агента при сохранении device events от агента. |

**device_events:** `id` (PK), `device_id`, `device_seq`, `event_type`, `payload` (JSONB), `trace_id`, `event_id`, `operation_id`, `created_at`. UNIQUE `(device_id, device_seq)`.

---

### Команды и операции

| Таблица | Назначение | Где используется |
|--------|------------|-------------------|
| **device_outbox** | Серверная outbox: команды к агентам до доставки по WebSocket. Жизненный цикл: pending → sent → delivered/failed. | `DeviceOutboxRepo`: вставка команды, выборка pending по device_id, обновление status/sent_at/delivered_at. Отправка команд агенту через outbox sender (`device_outbox_sender`) и доставка по WS. |
| **operations** | Материализованное состояние операций (run_tool, cancel, agent_recipe и т.д.) для быстрого запроса и отображения. | `OperationsRepo`: создание/обновление операции по этапам (queued, sent, accepted, running, waiting_consent, succeeded/failed и т.д.) плюс nullable `phase` для runtime dependency substate. Связь с consent_decisions и operation_dependencies. Tools API, WebSocket, отмена операций. |
| **operation_dependencies** | Явная связь parent operation с runtime dependency operation/resource. | `OperationDependenciesRepo` / `diagnostics.runtime_dependencies`: runner/module dependency status, target version, timeout, resume attempts and dependency operation linkage. |
| **runner_rollout_plans / waves / targets / events** | Admin-managed canary/wave rollout and rollback state for `agent_recipe_runner`. | `diagnostics.runner_rollout.RunnerRolloutService`: create plan, start canary, promote waves, pause/resume, refresh status, rollback via desired modules + reconcile. |

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

### Сборки агента (self-update)

| Таблица | Назначение | Где используется |
|--------|------------|-------------------|
| **agent_builds** | Реестр загруженных сборок pc_agent (ZIP/tar.gz) по target/channel/version. | `AgentBuildsRepo`: загрузка, список, получение по target/channel/version, скачивание. |
| **agent_build_download_audit** | Аудит скачивания сборок агента. | Запись при GET download сборки. |

**agent_builds:** `target`, `channel`, `version` (PK composite), `sha256`, `size`, `storage_path`, `created_at`, `uploaded_by`, `notes`, `artifact_filename`, `archive_type`, `mime_type`.  
**agent_build_download_audit:** `id` (PK), `token_hash`, `token_prefix`, `target`, `channel`, `version`, `downloaded_at`, `ip_address`, `user_agent`.

---

## Репозитории (app/repos)

| Репозиторий | Таблицы |
|------------|---------|
| `ticket_events_repo.py` | tickets, ticket_events |
| `device_events_repo.py` | device_events |
| `device_outbox_repo.py` | device_outbox |
| `operations_repo.py` | operations, consent_decisions |
| `devices_repo.py` | devices |
| `device_config_repo.py` | device_config |
| `toolset_snapshots_repo.py` | device_toolset_snapshots |
| `modules_repo.py` | modules |
| `device_modules_repo.py` | device_modules |
| `auth_tokens_repo.py` | agent_tokens, ui_tokens |
| `artifacts_repo.py` | artifacts |
| `job_events_repo.py` | job_events |
| `agent_builds_repo.py` | agent_builds |
| `knowledge_repo.py` | knowledge_spaces, knowledge_items, knowledge_item_versions, knowledge_chunks, knowledge_bindings |
| `knowledge.content_pack_service` | knowledge_content_packs, knowledge_content_pack_items |
| `knowledge.review_task_service` | knowledge_review_tasks, knowledge_review_comments |
| `knowledge.quality_service` | knowledge_quality_snapshots |
| `knowledge.gap_service` | knowledge_gap_findings |
| `knowledge.search_analytics_service` | knowledge_search_events |
| `knowledge.operations_service` | knowledge_rollout_policies |

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
- `021_ticket_stage5_tables.py` — ticket_stage5 (resolution_codes, kb_links)
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
- `083_knowledge_platform.py` — universal knowledge platform tables: spaces, items, item versions, chunks, bindings, graph nodes/edges/entity mentions, feedback events, ingestion jobs and `ticket_knowledge_links`; keeps existing `ticket_kb_links` compatibility.
- `084_knowledge_acceptance_constraints.py` — P2.1 acceptance constraints for knowledge graph, feedback, ingestion and ticket-knowledge enum-like fields.
- `085_knowledge_operations.py` — P2.2 knowledge operations: idempotent content pack audit tables and self-service deflection rollout policies.
- `039_add_servicedesk_test_queue.py` — upsert очереди `servicedesk_test` (active) для публичной ссылки `/queue/test`
- `062_access_control_groups.py` — access groups, group permissions, group queue grants and access_audit для `/app/admin/access`
- `072_support_queue_saved_views.py` — `support_queue_saved_views` for DB-backed support Queue Mode saved views and column presets.

Команды: из каталога `server` — `alembic upgrade head`, `alembic revision --autogenerate`.

**Подгрузка .env:** Alembic сам не читает `server/.env`. Для запуска миграций с теми же настройками, что и сервер, используйте скрипт `server/scripts/run_migrations.py` (подгружает `server/.env` и вызывает alembic). Пример: из каталога `server` — `python scripts/run_migrations.py upgrade head` или `python scripts/run_migrations.py current`.

### Миграции на удалённом хосте (PostgreSQL на удалённой шаре)

- Миграции выполняются **на Linux-хосте**, где развёрнут код (например `/var/chat_bot/pc_client`), так как именно там настроен доступ к БД.
- **Один раз** на удалённом хосте нужно создать `server/.env` с `DATABASE_URL=postgresql+asyncpg://user:password@host:port/dbname`. Файл в репозиторий не коммитится (см. `.gitignore`). Можно скопировать с рабочей машины или создать вручную; шаблон — `server/.env.example`.
- **С Windows** миграции на удалённом хосте запускаются так (после deploy):
  ```text
  python scripts/run_remote_migrations.py              # upgrade head
  python scripts/run_remote_migrations.py current
  python scripts/run_remote_migrations.py upgrade head
  ```
  Скрипт по SSH выполняет на хосте `server/venv/bin/python server/scripts/run_migrations.py ...`; `run_migrations.py` подгружает `server/.env` и запускает alembic.

---

## Связанные документы

- [README.md](README.md) — раздел «База данных», конфигурация DATABASE_URL.
- [RUNBOOK_POSTGRES_EXTERNAL_READONLY.md](RUNBOOK_POSTGRES_EXTERNAL_READONLY.md) — доступ к PostgreSQL извне (listen_addresses, pg_hba, firewall, read-only пользователь для другого агента).
- [SECURITY_AND_AUTH.md](SECURITY_AND_AUTH.md) — хранение и проверка agent_tokens, ui_tokens.
- [ARTIFACTS_API.md](ARTIFACTS_API.md) — upload/download артефактов, таблица artifacts.
- [MODULES_API.md](MODULES_API.md) — модули, tables modules, device_modules.
- [MODULES_DRIFT_AND_SNAPSHOTS.md](MODULES_DRIFT_AND_SNAPSHOTS.md) — device_toolset_snapshots, device_modules.
- [COMMAND_RESULT_LIFECYCLE.md](COMMAND_RESULT_LIFECYCLE.md) — device_outbox, operations, ticket_events.
- [TOOL_CALL_STARTED_INVARIANT.md](TOOL_CALL_STARTED_INVARIANT.md) — tool_call_started, operations.
