# CODEMAP (server)

Карта кода `pc_client/server`. Используется для быстрой навигации и поиска (в т.ч. скрипт `scripts/agent_find.py` и контекст агента). Пути указаны относительно корня репозитория (например `server/routes.py`).

---

## 0. Операционный старт

- Если задача начинается с diff, сначала выполните `python scripts/diff_context.py`.
- Если тема затрагивает сервер и агент или формулировка пока широкая, откройте `docs/QUICK_LOOKUP.md`.
- Для точечного поиска по серверу используйте `python scripts/agent_find.py "<ключевое слово>" --dir server`.

### Truth baseline

- Корневой pytest-контур: `pytest.ini` (markers `unit`, `integration`, `manual`, `no_db`).
- Server harness: `server/tests/conftest.py`, `server/tests/README.md`.
- CI runner: `scripts/run_ci_suite.py`; isolated temp checkout runner: `scripts/run_ci_in_temp_workspace.py`.
- Канонические test/CI env vars: `TEST_DATABASE_ADMIN_URL`, `TEST_DATABASE_URL`, `PC_CLIENT_ALLOW_SHARED_TEST_DB`.
- Windows default: if `TEST_DATABASE_URL` and `TEST_DATABASE_ADMIN_URL` are not set, DB-backed server pytest uses shared `pc_support_test` through a local SSH tunnel; the shared fallback now terminates stale test backends before cleanup and applies a short `lock_timeout`, while explicit admin DSN is still required for isolated ephemeral DBs from Windows.
- For websocket-heavy pytest on Windows, `server/tests/conftest.py` also switches the harness to `WindowsSelectorEventLoopPolicy`, which removes the old Proactor-only `unexpected connection_lost() call` noise during teardown.

| Сценарий | Открыть сначала | Затем |
|------|------------------|-------|
| Handshake / Protocol V3 | `server/websocket/agent_handshake.py` | `server/docs/PROTOCOL_V3.md`, `pc_agent/docs/PROTOCOL_V3.md` |
| `run_tool` / consent | `server/tools/service.py` | `server/app/services/operation_service.py`, `server/docs/TOOL_CALL_STARTED_INVARIANT.md` |
| Тикеты / очередь / чат | `server/tickets/handlers.py` | `server/tickets/create_flow.py`, `server/tickets/workflow_service.py`, `server/docs/TICKET_SYSTEM.md` |
| Модули / reconcile | `server/modules/service.py`, `server/modules/handlers.py`, `server/modules/workbench_service.py` | `server/websocket/modules_sync.py`, `server/docs/MODULE_CREATION_GUIDE.md`, `server/docs/MODULES_API.md` |
| Admin / support / ticket UI | `server/admin.js`, `server/admin_modules_workbench.js`, `server/support.js`, `server/ticket.js`, `server/web_shared.js`, `server/control_plane.py`, `server/runtime_control.py` | `server/static_pages/`, `server/docs/SECURITY_AND_AUTH.md`, browser check на `http://192.168.100.17:8666/admin`; legacy admin queue fallback now keeps list refresh on polling and no longer subscribes `/ws_ui` to every visible ticket row |

---

## 1. Точки входа

| Файл | Назначение |
|------|------------|
| `server/server.py` | Запуск aiohttp, startup/shutdown, watchdog/scheduler; поднимает background `ObserverRefreshRuntime` для incremental trace projection и historical backfill ticket-root traces; перед настройкой loguru принудительно включает UTF-8 для stdout/stderr на Windows, чтобы консоль и логи не превращались в mojibake; bootstrap-ит repo root в `sys.path`, чтобы sibling-пакет `shared/*` был доступен в canonical runtime wrappers; legacy `server_old.py` удалён из активного runtime tree |
| `server/control_plane.py` | Отдельный aiohttp control-plane на порту `8667`: status/logs/download/actions для server runtime, auth/CORS/audit и переживание `stop/restart` основного сервера; так же bootstrap-ит repo root в `sys.path` для shared runtime helpers |
| `server/routes.py` | Регистрация всех HTTP и WS маршрутов, включая shell-страницы `/login`, `/admin`, `/support`, `/ticket`, новые React SPA routes `/app` + `/app/{tail}`, built asset endpoints `/assets/*` и `/favicon.svg`, legacy session endpoint `GET /api/ui_session`, typed web boundary `/api/web/session|support|admin|reports|settings|realtime/*`, device update recommendation `GET /api/devices/{device_id}/agent/update_recommendation`, module rollout settings `GET/PATCH /api/modules/rollout_settings`, typed reports/settings routes `GET /api/web/reports/summary` + `GET /api/web/settings`, новый typed preview endpoint `POST /api/web/admin/forms/route-preview`, а также `/api/web/settings/*` alias-маршруты поверх legacy admin-config handlers для очередей, членов очередей, OLA, routing, SLA, calendars, resolution codes и audit |
| `server/config.py` | Конфигурация, feature flags, таймауты SLA/operations/playbook |
| `server/runtime_control.py` | Канонический runtime-control слой для `systemctl`/`journalctl`, control-plane state, smoke/status/log filtering и unit-level lifecycle |

### Observer docs

- `server/docs/OBSERVER_LAYER.md` — полная модель observer-слоя, runtime, APIs, UI и быстрый путь диагностики.
- `server/docs/OBSERVER_AUTHORING_RULES.md` — правила, как добавлять новый dangerous flow или instrumentation без деградации observer.

---

## 2. Структура каталогов (ключевые файлы)

### 2.1 WebSocket
| Файл | Назначение |
|------|------------|
| `server/websocket/agent_handler.py` | WS агентов `/ws`: transport-loop + wiring `AgentMessageRouter`; compare-safe disconnect cleanup и `outbox_items_batch` routing |
| `server/websocket/agent_services.py` | `AgentMessageRouter` + сервисы handshake/ack/result/outbox/agent-command; batched outbox ingest reuses the per-item pipeline and flushes ACK/NACK once per WS batch |
| `server/websocket/agent_handshake.py` | Полная логика `handle_handshake` (Protocol V3 auth/register/capabilities), canonical `machine_id`/`install_id` metadata, controlled reprovision токена на уже известный `device_id`, runtime `connection_id` per successful handshake и supersede-close старого websocket того же `device_id` |
| `server/websocket/agent_command_result.py` | Thin compatibility wrapper (deprecated-internal) |
| `server/websocket/command_result_components.py` | Компоненты command_result pipeline: normalizer/future/artifact/event publisher + side effects для `list_installed_modules` и `list_tools` (inventory/toolset snapshots); future resolver сначала смотрит state-level waiter registry, а не только metadata текущего websocket |
| `server/websocket/agent_outbox_ingest.py` | Thin compatibility wrapper (deprecated-internal) |
| `server/websocket/outbox_ingest_components.py` | Компоненты outbox pipeline: envelope validator, persistence c requester-name enrichment для `chat_message`, ACK/NACK decision, post-commit publish; `module_state_changed` здесь синхронизирует `device_modules` из snapshot и затем запускает reconcile |
| `server/websocket/job_event_persistence.py` | Best-effort `persist_job_event` в `job_events` |
| `server/websocket/contexts.py` | Контексты `AgentConnectionContext`, `EnvelopeContext` |
| `server/websocket/ui_handler.py` | WS UI `/ws_ui`: `ui_hello`, `run_tool`, ticket/device/chat subscriptions; новый web-layer теперь допускает auth не только по raw `token` в `ui_hello`, но и по httpOnly cookie `pc_client_web_session`, а live-only подписки умеют `skip_catchup` для React realtime bridge |
| `server/websocket/protocol.py` | Отправка ACK/NACK/command, trace_id; ticket-bound `send_ws_command` теперь пытается закрепить canonical `observer_root_trace_id` тикета до создания operation/outbox entry, а sync `wait_for_result=True` регистрирует waiter в `StateManager.pending_command_futures` для reconnect-safe ожидания `command_result` |
| `server/websocket/device_outbox_sender.py` | Dispatch runtime: `poll` и `sharded` (`DeviceReadyQueue`, shard workers, DB lease claim, reconcile); send failures теперь синхронизируют `operations.retry_count`, пишут runtime audit (`command_retry_scheduled` / `command_delivery_failed`) и завершают operation явным `DELIVERY_RETRY_EXHAUSTED`, когда outbox исчерпал retries |
| `server/app/repos/device_outbox_repo.py` | Репозиторий server-side command outbox; pending drain order теперь lane-aware (`cancel_operation` -> update -> control/health -> FIFO по `created_at`) |
| `server/websocket/validator.py` | Валидация событий, device binding |
| `server/websocket/modules_sync.py` | Синхронизация модулей с UI/агентом |
| `server/websocket/ui_publisher.py` | Публикация событий в UI |
| `server/websocket/command_result_parser.py` | Разбор command_result |

### 2.2 API (HTTP)
| Файл | Назначение |
|------|------------|
| `server/api/events.py` | Replay: ticket_events, device_events, ticket_messages |
| `server/api/commands.py` | send_command, check_functions, smoke_run |
| `server/api/operations.py` | Lifecycle операций, consent/cancel |
| `server/api/admin.py` | admin_run_tool и др. |
| `server/api/protocol.py` | Endpoint протокола |
| `server/web_api/` | Typed web-facing boundary для нового `webapp/`: `session_handlers.py`, `support_handlers.py`, `admin_handlers.py`, `reports_handlers.py`, `settings_handlers.py`, `realtime_handlers.py` и DTO-модели в `dto/*`; `session_handlers.py` обслуживает `POST /api/web/session/login`, `POST /api/web/session/logout`, `GET /api/web/session/me` через httpOnly cookie flow, `realtime_handlers.py` отдаёт typed transport bootstrap `GET /api/web/realtime/bootstrap` для `ws_ui` bridge (session-cookie auth, `ui_hello`, channel contracts `support.queue` / `ticket.stream` / `admin.devices` / `tech.feed`), `support_handlers.py` уже даёт queue/detail/action routes `GET /api/web/support/bootstrap`, `GET /api/web/support/queue`, `GET /api/web/support/tickets/{ticket_id}`, `GET /api/web/support/tickets/{ticket_id}/tools`, `POST /api/web/support/tickets/{ticket_id}/messages`, `POST /api/web/support/tickets/{ticket_id}/status`, `POST /api/web/support/tickets/{ticket_id}/tools/run` и typed queue counters для SaaS-style ticket list, а detail payload теперь нормализует `request_form_summary` в отдельный блок `request_form` для `/app/support`; `admin_handlers.py` теперь кроме bootstrap обслуживает `GET /api/web/admin/devices` с typed inventory устройств, status/query filters и rollout summary, `GET /api/web/admin/modules` с family-level registry overview, preferred-version rollout settings, validation/preflight labels и file-availability summary, `GET /api/web/admin/forms/current` + `POST /api/web/admin/forms/save` для typed request-form catalog builder и `POST /api/web/admin/forms/route-preview` для preview form-aware routing по draft-форме и примерным значениям, а также admin modules action endpoints `PATCH /api/web/admin/modules/rollout_settings` и `PATCH /api/web/admin/modules/{module_name}/preferred`, чтобы React-панели `Реестр модулей` и `Конструктор форм заявок` могли работать без legacy shell; device-scoped update boundary остаётся `GET /api/web/admin/devices/{device_id}/updates` и `POST /api/web/admin/devices/{device_id}/updates/run`, а typed observer surfaces `GET /api/web/admin/observer/quick`, `GET /api/web/admin/observer/traces` и `GET /api/web/admin/observer/traces/{trace_id}` продолжают кормить device-scoped quick summary, список трасс и drilldown span/error detail в `/app/admin` без прямой зависимости React от legacy `/api/admin/tech/traces*`; `reports_handlers.py` агрегирует реальные helpdesk-метрики для `GET /api/web/reports/summary` (backlog, SLA, reopen rate, daily trend, request kinds, top queues/requesters, recent tickets) и теперь подписывает `request_kind` по текущему preferred form pack, а `settings_handlers.py` собирает typed settings snapshot для `GET /api/web/settings`, включая `routing_builder` catalog из текущих форм, после чего web shell пишет обратно через `/api/web/settings/*` alias-маршруты в существующий admin-config backend (`admin_config_handlers.py`) без фронтенд-моков; typed detail payload для support включает chat + `tool_call_started` / `tool_call_result` timeline entries, observer root trace metadata и device-bound tool inventory/run surface для `/app/support`, а bootstrap-ответы рекламируют observer capability links и forms-builder feature для `/app/admin` |
| `server/tech/handlers.py` | Техпанель `/api/admin/tech/*`: overview/alerts/logs, русифицированный аудит агентов/пользователей, drilldown по агенту (`/agents/{device_id}/timeline`), observer quick diagnosis (`/observer/quick`), trace/signature/degradation search (`/traces`, `/signatures`, `/degradations`, `/traces/rebuild`, `/traces/runtime`), observer settings API (`GET/PATCH /api/admin/settings/observer`), lazy sync agent action trace в first-class observer spans, быстрые диагностические actions, lifecycle тикета (`milestone_rail`, `sla_lane`, ссылки ticket/device/operation), dismiss endpoint `/api/admin/tech/dismiss`, suppression шумных UI WebSocket alert и удаление log/alert из панели |
| `server/control_plane.py` | Внешний runtime API `/api/control/server/*`: status, full journal logs, download logs, lifecycle actions `start/stop/restart/smoke` |

### 2.2.1 Tools / единый путь run_tool
| Файл | Назначение |
|------|------------|
| `server/tools/service.py` | Канонический вход `ToolExecutionService.run_tool` (совместим с `ToolService`): pre-start event `tool_call_started`, version-aware auto-install/auto-update module pack по preferred version, фиксация desired state перед `run_tool` |
| `server/tools/handlers.py` | HTTP handlers, которые делегируют run_tool в `ToolExecutionService`; `/api/tools/run` по умолчанию возвращает async `202 Accepted` + `operation_id` + `poll_url`, sync path допускается только через явный `wait=1` |
| `server/app/services/operation_service.py` | Ветка consent: `approve_consent()` переводит operation `waiting_consent -> queued` и enqueue `run_tool` в `device_outbox` (исполнение после явного approve) |
| `server/websocket/protocol.py` | Транспорт: `send_ws_command(..., wait_for_result=...)` enqueue в `device_outbox` + опционально ожидание `command_result` |

### 2.3 БД и репозитории
| Файл | Назначение |
|------|------------|
| `server/app/db/models.py` | SQLAlchemy модели (в т.ч. modules.manifest_json, validation_json) |
| `server/app/db/engine.py` | Async engine/session; DB pool tunables via `PC_CLIENT_DB_POOL_SIZE`, `PC_CLIENT_DB_MAX_OVERFLOW`, `PC_CLIENT_DB_POOL_TIMEOUT_SEC`, `PC_CLIENT_DB_POOL_RECYCLE_SEC` |
| `server/app/db/migrations/versions/*.py` | Alembic миграции |
| `server/app/repos/device_outbox_repo.py` | device_outbox (pending/sent/delivered) |
| `server/app/repos/device_events_repo.py` | События устройства |
| `server/app/repos/ticket_events_repo.py` | События тикета; canonical observer trace resolution для ticket-bound lifecycle events, lazy bootstrap `tickets.observer_root_trace_id` и связь server-originated событий с operation trace/root trace |
| `server/app/repos/operations_repo.py` | Операции |
| `server/app/repos/modules_repo.py` | Модули в БД |
| `server/app/repos/device_modules_repo.py` | Установленные модули на устройстве |
| `server/app/repos/device_desired_modules_repo.py` | Желаемое состояние модулей |
| `server/app/repos/auth_tokens_repo.py` | Токены устройств/UI и public-session токены requester-доступа; проверка, ротация, controlled rebind токена агента по canonical `machine_id` |
| `server/app/repos/devices_repo.py` | Реестр устройств: handshake upsert, last_seen/toolset update, soft-delete/архивирование устройства с сохранением истории, отзывом token и остановкой pending runtime/provisioning |
| `server/app/repos/connection_requests_repo.py` | Запросы на подключение устройств, политика (reject_all/accept_all/manual) |
| Остальные repos | artifacts, notifications, playbook, tickets, agents, jobs, ui_users и др. — см. `server/app/repos/`. |

### 2.4 Сервисы (app/services)
| Файл | Назначение |
|------|------------|
| `server/app/services/operation_watchdog.py` | SLA операций |
| `server/app/services/operation_service.py` | Жизненный цикл операций |
| `server/app/services/ticket_sla_watchdog.py` | SLA тикетов |
| `server/app/services/ticket_auto_close_watchdog.py` | Контроль policy для resolved; закрытие только после подтверждения пользователя |
| `server/app/services/playbook_engine.py` | Движок playbook |
| `server/app/services/playbook_scheduler.py` | Планировщик playbook |
| `server/app/services/module_reconcile_scheduler.py` | Реконсиляция модулей |
| `server/app/services/artifact_service.py` | Артефакты |
| `server/observer/service.py` | Trace overlay projection/search: `observer_traces`, `observer_spans`, `observer_span_links`, `observer_error_occurrences`, `observer_error_signatures`; observer v3 умеет canonical ticket-root trace, synthetic `ticket.lifecycle` span, materialized `agent_action` spans/links, redacted attrs/details export и degradation queries (`min_duration_ms`, `min_retry_count`, timeout/retry/slow rates); request-side `_ensure_projected`/`rebuild_traces` теперь завершают source read-транзакцию и materialize traces в отдельных short-lived projection sessions, чтобы tech/support polling не держал idle-in-transaction соединения во время trace-lock wait |
| `server/observer/runtime.py` | Background refresh для observer traces: сканирует committed source rows, enqueue-ит hot ticket-root traces, делает исторический backfill missing projections без ручного rebuild/search и obey-ит DB-backed retention/sampling settings |

### 2.5 Доменные модули (handlers + service)
| Каталог/файл | Назначение |
|--------------|------------|
| `server/tickets/` | handlers, `create_flow.py`, service, assignment_service, sla_service, workflow_service, public_queue_handlers, public_ticket_handlers, admin_config_handlers и др.; `create_flow.py` держит единый DB-first путь создания для `/api/tickets/create`, WS `chat_raise` и legacy `/api/chat_raise`, а `assignment_service.py` и `ticket_events_repo.py` считают состав очереди обязательным для назначения и автоназначения; `handle_ticket_get` поддерживает forward catch-up (`since_event_id`) и reverse pagination (`before_event_id`, `limit`, `has_older`, `next_before_event_id`) для агентского ticket chat; `handle_ticket_get_observer_summary` отдаёт support-facing trace summary по `GET /api/tickets/{ticket_id}/observer`, где summary counts считаются по полному trace-set тикета, а signatures несут и глобальный `occurrences_count`, и ticket-local `ticket_occurrences_count`; `admin_config_handlers.py` ведёт helpdesk-admin settings API: очереди, состав очередей, routing rules, SLA policies, targets/matrix (GET/PUT), calendars, OLA targets, audit |
| `server/agents/` | handlers, agent_builds_handlers, service; `handlers.py` также даёт admin-only архивирование устройства с очисткой live runtime-сессии |
| `server/modules/` | handlers, service, reconcile, verification, `workbench_service.py` для реконструкции editable draft и module-family workbench payload; preferred-version auto-rollout теперь через policy может переводить существующие установки в новый desired state |
| `server/tools/` | handlers, service (каталог инструментов, manifest) |
| `server/chat/` | handlers, service |
| `server/jobs/` | handlers |
| `server/uploads/` | handlers |
| `server/auth/` | handlers, admin_users_handlers, connection_request_handlers (запросы на подключение устройств, включая `DEVICE_ARCHIVED` status/error_code для агента), middleware, service, `agent_token_service.py`, `connection_request_service.py`, password_service; legacy `handlers.py` содержит UI login/session endpoints, `middleware.py` дополнительно читает web session cookie `pc_client_web_session` для `/api/web/*`, а `service.py` теперь поддерживает config/in-memory fallback для локального UI session flow без PostgreSQL |
| `server/playbook_handlers.py` | Старт playbook run |
| `server/static_pages/` | `cutover.py` с operational policy для default-route switch, `handlers.py` для legacy login/admin/support/ticket/public_queue/help shell-файлов и общего `web_shared.js`, плюс `webapp_assets.py` для отдачи built React bundle: `/app/*`, `/assets/*`, `/favicon.svg`; direct route `/favicon.svg` теперь обслуживается тем же public-asset handler без обязательного `match_info`, чтобы browser shell не ловил `500` на favicon при cutover |
| `webapp/` | Внутренний React/Vite webapp теперь живёт как SaaS-style shell с Tailwind v4: `src/main.tsx`, `src/app/router.tsx`, `src/app/navigation.tsx`, `src/app/providers/query-provider.tsx`, `src/app/layouts/app-shell.tsx`, `src/components/shell/*`, `src/components/ui/*`, `src/features/auth/*`, `src/features/queues/api.ts`, `src/features/reports/api.ts`, `src/features/settings/api.ts`, `src/pages/tickets/*`, `src/pages/reports/index.tsx`, `src/pages/knowledge/index.tsx`, `src/pages/settings/index.tsx`, `src/pages/admin/*`; актуальный route model: `/app/tickets`, `/app/tickets/:ticketId`, `/app/reports`, `/app/knowledge`, `/app/settings`, `/app/admin/inventory`, `/app/admin/device`, `/app/admin/modules`, `/app/admin/forms`, `/app/admin/observer`, при этом `/app/support` и `/app/admin` остаются compatibility aliases для старых deep links; левый rail стал компактным menu-shell, а workspace switch/logout переехали в topbar. Typed `/api/web/*` boundary и realtime bridge (`src/shared/realtime/adapters/ws-ui-bridge.ts`, `src/shared/realtime/client.ts`) по-прежнему остаются каноническим transport слоем, но tickets, admin, reports и settings теперь питаются реальными серверными payload-ами вместо mock data; `/app/knowledge` сознательно остаётся placeholder-страницей "в разработке" до появления отдельного knowledge backend. `playwright.config.ts`, `tests/fixtures/support_fixture_server.py`, `tests/support-workspace.spec.ts` и `tests/admin-workspace.spec.ts` остаются локальным browser smoke для нового shell |

### 2.6 Утилиты (модули/manifest)
| Файл | Назначение |
|------|------------|
| `server/utils/module_manifest.py` | Manifest contract и strict validation для typed tools: canonical semantic ids, aliases, contract/dependencies/redaction/resources blocks, reserved namespace governance |
| `server/utils/module_preflight.py` | Preflight ZIP, manifest_json, validation_json; теперь жестко применяет observer contract guard к module ZIP, чтобы новые tool methods без mandatory breadcrumbs не публиковались |
| `server/utils/module_observer_contract.py` | AST-валидатор observer contract для `BaseCollector`-модулей: требует `self.trace_span("tool.entry", ...)` в каждом `@exposed_tool`, используется и в upload preflight, и в `scripts/verify_workspace.py` |
| `server/utils/module_builder.py` | Сборка пакета для POST /api/modules/create: legacy single-tool и multi-tool module packs с canonical semantic tool ids |
| `server/utils/module_storage.py` | Хранение модулей |
| `server/utils/tool_metadata_validation.py` | Валидация метаданных инструментов |
| `server/core/policy_engine.py` | Политики доступа |
| `shared/tool_contracts.py` | Shared contract layer для server+agent: ToolMetadata, ToolExecutionEnvelope, ToolError, artifacts/dependencies/redaction/resources vocabulary |

### 2.7 UI (статика)
| Файл | Назначение |
|------|------------|
| `server/admin.html`, `server/admin.js`, `server/admin_modules_workbench.html`, `server/admin_modules_workbench.js`, `server/admin.css`, `server/web_shared.js` | Админка и shared web-shell helpers (`authHeaders`, `responseToJson`, `escapeHtml`, `parseServerDate`, `formatDate`) для admin/support/ticket; вкладка `Модули` теперь разделена на подтемы `Разработка модулей` / `Список модулей` / `Редактор модулей` / `Модули на устройствах`, observer-блок техпанели ищет traces/signatures/degradations и умеет thresholds по duration/retry, а legacy queue fallback больше не подписывает `/ws_ui` на весь видимый список тикетов, чтобы `?legacy=1` не создавал burst из сотен `subscribe_ticket` |
| `server/control_plane.py`, `server/runtime_control.py` | Control-plane и runtime orchestration для техпанели: статус сервера (включая `started_at`/`uptime` из systemd и его timezone-offset timestamps вида `+05`), корректный `stop -> stopped/inactive` без ложного `failed`, health summary main API, полные логи (по умолчанию `Info+`), подтверждённые lifecycle actions с аудитом |
| `server/login.html`, `server/login.js`, `server/login.css` | Единая legacy-страница логина: выбор целевой роли (`admin` или `support`), POST `/api/ui_login` c `expected_role`, redirect в нужный shell |
| `server/support.html`, `server/support.js`, `server/support.css` | Отдельный support workspace: двухрежимный экран `Очередь` + `Тикеты`; runtime теперь опирается на `web_shared.js` для общих auth/date/html helpers, чтобы не дублировать базовый shell-код. Переключатель режимов собран в верхние twin-cards внутри workspace: слева компактная доска очереди с summary-плитками, встроенным scope-toggle и hover-подсказкой по новым ответам пользователя, справа компактный вход в рабочий тикет без дублирования длинной мета-строки. В `Очереди` основное место отдано доске тикетов, поиск/сортировка живут отдельной полосой ниже, а поиск сохраняет фокус при каждом вводе. В `Рабочем тикете` используются режимы preview/work/observe и встроенный ticket workbench (`Трасса`, `Контекст`, `Инструменты`, `Пайплайн`); observer summary тянется через `GET /api/tickets/{ticket_id}/observer`, а support drawer должен показывать ticket-local signature counts (`ticket_occurrences_count`) отдельно от глобального `occurrences_count`. Быстрые статусы `Ждём пользователя` / `Решено` делегируются в embedded composer тикета через postMessage bridge. Dev-only тестовая учётка support для локальных/browser проверок: `op1` / `1.Abcdef` (убрать перед production) |
| `server/ticket.html`, `server/ticket.js`, `server/ticket.css` | Основная рабочая область тикета: чат, reply-to баннер/ссылки на исходное сообщение, mark-read, подтверждение решения, редактирование профиля инициатора, очередь/исполнитель по составу очереди, SLA/OLA и ручной reroute по правилам; поддерживает `embed=1` для встраивания в support workspace и использует `web_shared.js` для базовых shell helpers |
| `server/public_queue.html`, `server/public_queue.js` | Публичная очередь со ссылками на requester-вход в тикет |
| `server/help.html`, `server/help.js`, `server/help.css` | Публичная страница requester: создание тикета, вход по коду, чат |
| `server/static_pages/` | Обработчики legacy shell-страниц и built React-ассетов для `/app/*` |

---

## 3. Быстрый поиск (ключевое слово → файлы)

Используйте поиск по документу, `docs/QUICK_LOOKUP.md` или `scripts/agent_find.py <ключевое_слово> --dir server`. Ниже — куда смотреть в первую очередь.

- **handshake** — `websocket/agent_handshake.py`, `websocket/agent_services.py`, `websocket/validator.py`, `docs/PROTOCOL_V3.md` (включая migration rebind legacy install-based token -> canonical `machine_id`)
- **outbox_ack, outbox_nack** — `websocket/agent_services.py`, `websocket/outbox_ingest_components.py`, `websocket/protocol.py`
- **run_tool** — `websocket/ui_handler.py`, `api/admin.py`, `tools/handlers.py`
- **device_outbox, DeviceOutboxSender** — `websocket/device_outbox_sender.py`, `app/repos/device_outbox_repo.py`, `config.py` (`DEVICE_DISPATCH_*`); retry exhaustion теперь коррелируется обратно в `operations` и `agent_runtime_audit`
- **command_result** — `websocket/agent_services.py`, `websocket/command_result_components.py`, `websocket/command_result_parser.py`, `app/repos/operations_repo.py`
- **tool_call_started** — сервер создаёт до run_tool; идемпотентность: `docs/TOOL_CALL_STARTED_INVARIANT.md`
- **device_seq, agent_seq** — тип события только по ним; `websocket/validator.py`, `app/repos/device_events_repo.py`, `app/repos/ticket_events_repo.py`
- **ticket_events, device_events** — `api/events.py`, соответствующие repos
- **модули (install, desired, reconcile, preferred version, rollout policy, UI workbench)** — `modules/handlers.py`, `modules/service.py`, `modules/reconcile.py`, `modules/workbench_service.py`, `websocket/modules_sync.py`, `websocket/outbox_ingest_components.py`, `app/repos/device_desired_modules_repo.py`, `app/repos/module_rollout_repo.py`, `app/services/module_reconcile_scheduler.py`, `utils/module_manifest.py`, `utils/module_preflight.py`, `utils/module_observer_contract.py`, `utils/module_builder.py`
- **playbook** — `playbook_handlers.py`, `app/services/playbook_engine.py`, `app/services/playbook_scheduler.py`, `app/repos/playbook_repo.py`
- **операции (consent, cancel, lifecycle)** — `api/operations.py`, `app/services/operation_service.py`, `app/services/operation_watchdog.py`, `app/repos/operations_repo.py`
- **observer traces / signatures / degradations** — `observer/service.py`, `observer/runtime.py`, `tech/handlers.py`, `app/db/models.py`, `websocket/agent_services.py`, `pc_agent/core/action_trace.py`, `server/docs/OBSERVER_LAYER.md`, `server/docs/OBSERVER_AUTHORING_RULES.md`
- **тикеты (SLA, назначение, очереди, structured confirmation, public access, описание заявки)** — `tickets/handlers.py`, `tickets/assignment_service.py`, `tickets/sla_service.py`, `tickets/workflow_service.py`, `tickets/public_queue_handlers.py`, `tickets/public_ticket_handlers.py`, `tickets/public_access.py`, `auth/admin_users_handlers.py`
- **ticket snapshot / workbench payload** — `tickets/handlers.py` (`GET /api/tickets/{ticket_id}/snapshot`: relations, worklogs, watchers/links/kb, device/provisioning/update summary, latest operations, notification counters, device_metadata, OLA-блок, а также queue_members / assignable_users / available_queues / queue_auto_assign_enabled для основной рабочей области; `GET /api/tickets/{ticket_id}/observer`: root trace, related traces, signatures, occurrences для support workspace). Новый typed support boundary в `server/web_api/support_handlers.py` агрегирует из этого ticket detail/timeline/snapshot/action payload для `/app/support`, теперь уже включая tool events в timeline, нормализованный блок `request_form` из `request_form_summary`, и отдельный typed inventory/run contract для `GET /api/web/support/tickets/{ticket_id}/tools` + `POST /api/web/support/tickets/{ticket_id}/tools/run`, чтобы React-слой не зависел от raw legacy snapshot shape и `/api/tools/*`.
- **аутентификация, RBAC, login routing** — `auth/`, `auth/agent_token_service.py`, `routes.py`, `static_pages/handlers.py`, `docs/SECURITY_AND_AUTH.md`
- **миграции БД** — `app/db/migrations/versions/`, `docs/DATABASE.md`
- **обновление агента (builds, upload, delete, update, mass, diagnostics, recommendation, global rollout policy)** — `agents/agent_builds_handlers.py`, `agents/handlers.py`, `app/repos/agent_rollout_repo.py`, `websocket/agent_handshake.py`, `docs/AGENT_UPDATES_API.md`, `../../docs/AGENT_UPDATE_CONTRACT.md`, `../../pc_agent/docs/AGENT_UPDATE_WORKFLOW.md`, маршруты `POST/GET/DELETE /api/agent_builds*`, `GET/PATCH /api/agent_updates/rollout_policy`, `POST /api/devices/{id}/agent/update`, `GET /api/devices/{id}/agent/update_recommendation`, `POST /api/agents/update_bulk`, `GET /api/devices/{id}/agent/update_diagnostics`, а новый typed admin boundary использует тот же flow через `GET /api/web/admin/devices/{device_id}/updates` + `POST /api/web/admin/devices/{device_id}/updates/run`
  - Инвариант recommendation: `assigned_rollout` — source of truth; любой version mismatch с rollout actionable, включая controlled rollback на более старую release-версию.
  - Инвариант cleanup: rollout-assigned build нельзя удалять, пока он назначен source of truth для target.
- **tech observability / tech panel** — `tech/handlers.py`, `observer/service.py`, `observer/runtime.py`, `tech/runtime_audit.py`, `tech/log_buffer.py`, `control_plane.py`, `runtime_control.py`, таблицы `agent_runtime_audit` + `observer_*`, маршруты `/api/admin/tech/*` и `/api/control/server/*` (overview, alerts, runtime health, full journal logs, lifecycle actions, traces/signatures/runtime/degradations, audits)
  - Observer queries now accept first-class filters `root_kind`, `min_duration_ms`, `min_retry_count`, `min_timeout_rate`, `min_retry_rate`, `min_slow_rate`, plus canonical ids (`trace_id`, `ticket_id`, `operation_id`, `device_id`).
  - `root_kind=agent_update` is the canonical way to isolate risky client-update traces and degradation groups from normal tool traffic.
- **device provisioning/update summary API** — `agents/handlers.py` (`GET /api/devices`, `GET /api/devices/{device_id}` возвращают `provisioning_summary`, `update_summary` и `identity_summary`)

---

## 4. Потоки выполнения

- **Agent → Server (Protocol V3):** агент подключается к `/ws`, handshake → outbox_item (ticket_event/device_event) → outbox_ack/outbox_nack.
- **Server → Agent:** команда в device_outbox → DeviceOutboxSender → WS → при command_result outbox помечается delivered/failed.
- **UI → Server:** `/ws_ui`, ui_hello → run_tool/API → операции и события в UI.
- **Helpdesk ticket flow:** создание тикета → routing/SLA/OLA → попытка auto-assign только внутри состава целевой очереди и только если у очереди включено автоназначение → статус `new` или `triaged` ("В очереди у оператора"); form-aware routing теперь строит условия не только по базовым полям тикета, но и по `ticket_type`, `request_kind`, `custom_fields`, `request_form_data.<field>` и `request_form_*` metadata из typed intake-форм; ручная смена очереди ставит routing lock, а ручной reroute и сохранение профиля инициатора с флагом reroute пересчитывают очередь по правилам и дополнительно приводят назначение к составу новой очереди (старый исполнитель снимается, затем возможен auto-assign по новой очереди); лимит оператора считается только по `in_progress`; `resolved` закрывается только после подтверждения requester, а его ответ из `waiting_on_user` возвращает тикет в очередь оператора.

### 4.1 Internal WS pipelines

- **`command_result` pipeline (`AgentMessageRouter` → `CommandResultService`)**
  - normalize (`CommandResultNormalizer`)
  - lifecycle update (`OperationLifecycleService`)
  - sync wait future resolve (`CommandResultFutureResolver`)
  - artifact/result post-processing (`CommandResultArtifactHandler`)
  - side effects publish (`CommandResultEventPublisher`)
- **`outbox_item` pipeline (`AgentMessageRouter` → `OutboxIngestService`)**
  - envelope validate (`OutboxEnvelopeValidator`)
  - post-handshake guard (`OutboxGuardService`)
  - dedupe check (`OutboxDedupService`)
  - persistence (`OutboxPersistenceService`, включая enrichment `sender_display_name`/`requester_display_name` для requester-originated `chat_message`)
  - ack/nack decision (`OutboxAckDecisionService`)
  - publish after persistence (`OutboxEventPublishService`)

---

## 5. БД и миграции

- PostgreSQL. Миграции: `server/app/db/migrations/versions/`. Команда: из каталога `server` — `alembic upgrade head`. См. `docs/DATABASE.md`, `docs/COMMAND_RESULT_LIFECYCLE.md`.

---

## 6. Тесты и скрипты

- `pytest.ini` — корневой test harness и markers для всего монорепо.
- `server/tests/` — интеграционные/регрессионные тесты.
- `server/tests/conftest.py` — isolated DB-per-run, session-scoped engine, in-process agent harness.
- `server/tests/README.md` — канон по локальному server baseline и env vars.
- `scripts/bootstrap_web_toolchain.py` — каноничный bootstrap `Node.js 24 LTS + corepack + pnpm` для нового `webapp/` и frontend build/release pipeline.
- `scripts/check_webapp_cutover.py` — preflight по operational readiness нового cutover: built bundle, requested/active флаги и готовность полного default-route switch; путь workspace теперь определяется от самого repo и одинаково работает локально и на Linux.
- `scripts/run_ci_suite.py` — канонический локальный/self-hosted CI run с artifact layout `artifacts/ci/<sha>/`.
- `scripts/run_ci_in_temp_workspace.py` — hook-friendly runner для self-hosted CI в отдельном checkout/venv.
- `requirements-ci.txt` — минимальный CI dependency set.
- Корень проекта: `scripts/run_server.py`, `scripts/stop_server.py`, `scripts/restart_server.py`, `scripts/run_control_plane.py`, `scripts/runtime_stack.py`, `scripts/manage_remote_stack.py`, `scripts/release_server_to_remote.py`, `scripts/smoke_test.py`, `scripts/admin_run_tool.py`.
- `server/scripts/` — `run_subagents.py`, `subagent_worker_server.py`, `subagent_worker_agent.py`.

---

## 7. Инварианты

- Тип события только по `device_seq` vs `agent_seq`. `tool_call_started` создаётся на сервере до run_tool, идемпотентен. Не логировать сырой токен. Детали: `AGENTS.md`, `docs/PROTOCOL_V3.md`.

---

## 8. Когда обновлять этот CODEMAP

Каноническая карта сервера — этот файл: `server/docs/CODEMAP.md` (других CODEMAP для дерева `server/` нет).

При изменениях, затрагивающих структуру кода сервера, его **нужно** обновить:

- добавление/удаление/перенос маршрутов (routes) или ключевых обработчиков;
- новые или переименованные ключевые каталоги/файлы в `server/`;
- новые точки входа или смена назначения существующих модулей.
- если change затрагивает observer-слой, dangerous flow, trace-visible API/UI или instrumentation rules — синхронно обновлять и `server/docs/OBSERVER_LAYER.md` + `server/docs/OBSERVER_AUTHORING_RULES.md`.

Проверка: ключевые термины и файлы из раздела «Быстрый поиск» и «Структура каталогов» должны соответствовать коду.
---

## 2026-04-15 Module workbench note

- `server/modules/handlers.py` now exposes `POST /api/modules/workbench/validate` in addition to list/detail/save/preferred endpoints, plus `GET/PATCH /api/modules/rollout_settings` for preferred-version auto-rollout policy.
- `server/modules/workbench_service.py` can reconstruct editable tool fragments from module archives via builder markers or AST analysis of `@exposed_tool` functions.
- `server/admin_modules_workbench.js` is the main entrypoint for template-driven module authoring, inline validation, API preview, archive/source exploration, and rollout-policy controls in the admin UI.

## 2026-04-16 Module page refactor

- `server/admin.html` and `server/admin.js` now treat the admin `Модули` page as an inner-tab workspace with four subviews: step-by-step authoring, module registry list, advanced editor, and device installs.
- `server/admin_modules_workbench.html` / `server/admin_modules_workbench.js` split authoring into a guided 4-step flow (`Каркас` -> `Инструменты` -> `Политики` -> `Проверка`) while keeping the advanced manifest/tool editor available as a separate view for power users.
- The workbench list can now import a ready ZIP archive, delete a published module version, and open the uploaded package directly in the editor; the authoring/editor views replace most routine JSON entry with guided controls: platform pills, line-based requirements, and validated schema blueprints for params/output before publish.

## 2026-04-16 Request form builder UX

- `server/admin_ticket_forms_builder.html` / `server/admin_ticket_forms_builder.js` are the dedicated admin UI entrypoints for the request-form catalog.
- `webapp/src/features/forms-builder/forms-builder-panel.tsx` and `webapp/src/features/forms-builder/api.ts` now mirror the same authoring flow inside `/app/admin` via typed `GET /api/web/admin/forms/current` and `POST /api/web/admin/forms/save`.
- The UI is now organized around one working catalog: a left navigator, a central form editor, and a right field-parameters panel with shared height and independent scrolling.
- Clicking a form opens its fields directly; clicking a field opens its parameters. The builder keeps `title` / `description` of the catalog in a hidden service section so the main flow stays focused on forms.

## 2026-04-17 Trace overlay

- `server/observer/service.py` projects a technical trace overlay over existing domain data instead of replacing ticket/problem entities.
- `server/observer/runtime.py` keeps hot traces fresh in the background by scanning newly committed source rows and re-projecting only changed trace ids.
- New observer storage lives in `observer_traces`, `observer_spans`, `observer_span_links`, `observer_error_occurrences`, and `observer_error_signatures` (migration `052_observer_trace_overlay`).
- Canonical observer docs: `server/docs/OBSERVER_LAYER.md` and `server/docs/OBSERVER_AUTHORING_RULES.md`.
- Tech API now exposes `GET /api/admin/tech/traces`, `GET /api/admin/tech/traces/runtime`, `GET /api/admin/tech/traces/{trace_id}`, `POST /api/admin/tech/traces/rebuild`, `GET /api/admin/tech/signatures`, and `GET /api/admin/tech/signatures/{error_signature}`.
- The projection bridges `operations`, `ticket_events`, `device_events`, `agent_runtime_audit`, and optional agent-side `action_trace` search for drilldown near failures.

## 2026-04-19 Observer v2

- `tickets.observer_root_trace_id` (migration `053_ticket_observer_root_trace`) is the technical anchor for a full ticket lifecycle trace; server-originated ticket events resolve to this root instead of ad-hoc random trace ids.
- `server/observer/service.py` can project a ticket-root trace by `ticket_id`, even if historical source rows were written with multiple old trace ids; the resulting detail includes a synthetic `ticket.lifecycle` root span and nested operation/event spans.
- `server/observer/runtime.py` now discovers hot ticket-root traces plus missing historical projections, so archive tickets no longer rely on manual rebuild as the normal path.
- Tech API and `/admin` now expose degradation search (`GET /api/admin/tech/degradations`) alongside trace/signature drilldown, with first-class filters for `min_duration_ms`, `min_retry_count`, and `lookback_hours`.
- Tech API now also exposes quick diagnosis via `GET /api/admin/tech/observer/quick`, and support workspace gets ticket-scoped observer summary via `GET /api/tickets/{ticket_id}/observer`.
- `/admin` now shows a quick observer dashboard for operators, while `/support` gets a dedicated `Трасса` drawer tab with root trace, related traces, signatures and recent occurrences.
- Everyday authoring should happen through the direct form -> field -> parameter flow; raw JSON preview, visibility rules, placeholders, and other power-user controls live in advanced sections instead of the main path.
- The UI no longer exposes manual version management for request-form packs: saving the catalog automatically creates the next internal version and immediately makes it active.
- The canonical operator guide for this UI is `server/docs/REQUEST_FORM_BUILDER.md`.

## 2026-04-21 Web cutover and pytest harness cleanup

- `server/web_api/session_handlers.py` now returns `default_workspace` and `available_workspaces` in `GET /api/web/session/me`, and that payload is the source of truth for role-aware redirect logic in the new `/app/*` shell.
- `webapp/src/features/auth/workspace-access.ts` plus `webapp/src/app/router.tsx` own the new role-aware `/app` entrypoint, access gate for `/app/admin`, and safe fallback redirect for sessions that only have `/app/support`.
- `server/static_pages/cutover.py`, `server/static_pages/handlers.py`, and `server/config.py` now prepare and enable legacy-shell cutover through `WEBAPP_CUTOVER_LOGIN_ENABLED`, `WEBAPP_CUTOVER_SUPPORT_ENABLED`, and `WEBAPP_CUTOVER_ADMIN_ENABLED`; redirect в новый shell активируется по умолчанию при наличии built bundle, а для `/support` и `/admin` дополнительно требуется включённый login cutover; explicit legacy escape remains `?legacy=1`, while `WEBAPP_CUTOVER_*=false` in `server/.env` is the rollback path.
- `server/tests/conftest.py`, `server/websocket/device_outbox_sender.py`, `server/server.py`, and `pc_agent/ws_agent.py` now close websocket-heavy test/runtime paths more gracefully; on Windows pytest also switches to `WindowsSelectorEventLoopPolicy`, which removes the non-fatal `unexpected connection_lost() call` tail noise from websocket suites.
- `webapp/scripts/remote-browser-signoff.mjs` plus `pnpm --dir webapp run check:remote:webapp -- --base-url http://192.168.100.17:8666` are now the canonical live browser signoff for the new `/app/*` shell after release: the script logs in, verifies `/app` default routing, checks `/app/admin` and `/app/support`, confirms Russian UI strings, validates raw redirects `/login|/admin|/support` and `?legacy=1` escape, and fails fast on browser console/page errors.
