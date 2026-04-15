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

| Сценарий | Открыть сначала | Затем |
|------|------------------|-------|
| Handshake / Protocol V3 | `server/websocket/agent_handshake.py` | `server/docs/PROTOCOL_V3.md`, `pc_agent/docs/PROTOCOL_V3.md` |
| `run_tool` / consent | `server/tools/service.py` | `server/app/services/operation_service.py`, `server/docs/TOOL_CALL_STARTED_INVARIANT.md` |
| Тикеты / очередь / чат | `server/tickets/handlers.py` | `server/tickets/create_flow.py`, `server/tickets/workflow_service.py`, `server/docs/TICKET_SYSTEM.md` |
| Модули / reconcile | `server/modules/service.py` | `server/websocket/modules_sync.py`, `server/docs/MODULES_API.md` |
| Admin / support / ticket UI | `server/admin.js`, `server/support.js`, `server/ticket.js`, `server/web_shared.js`, `server/control_plane.py`, `server/runtime_control.py` | `server/static_pages/`, `server/docs/SECURITY_AND_AUTH.md`, browser check на `http://192.168.100.17:8666/admin` |

---

## 1. Точки входа

| Файл | Назначение |
|------|------------|
| `server/server.py` | Запуск aiohttp, startup/shutdown, watchdog/scheduler; перед настройкой loguru принудительно включает UTF-8 для stdout/stderr на Windows, чтобы консоль и логи не превращались в mojibake; legacy `server_old.py` удалён из активного runtime tree |
| `server/control_plane.py` | Отдельный aiohttp control-plane на порту `8667`: status/logs/download/actions для server runtime, auth/CORS/audit и переживание `stop/restart` основного сервера |
| `server/routes.py` | Регистрация всех HTTP и WS маршрутов, включая shell-страницы `/login`, `/admin`, `/support`, `/ticket`, session endpoint `GET /api/ui_session`, device update recommendation `GET /api/devices/{device_id}/agent/update_recommendation` и device-scoped module lifecycle endpoints |
| `server/config.py` | Конфигурация, feature flags, таймауты SLA/operations/playbook |
| `server/runtime_control.py` | Канонический runtime-control слой для `systemctl`/`journalctl`, control-plane state, smoke/status/log filtering и unit-level lifecycle |

---

## 2. Структура каталогов (ключевые файлы)

### 2.1 WebSocket
| Файл | Назначение |
|------|------------|
| `server/websocket/agent_handler.py` | WS агентов `/ws`: transport-loop + wiring `AgentMessageRouter` |
| `server/websocket/agent_services.py` | `AgentMessageRouter` + сервисы handshake/ack/result/outbox/agent-command |
| `server/websocket/agent_handshake.py` | Полная логика `handle_handshake` (Protocol V3 auth/register/capabilities), canonical `machine_id`/`install_id` metadata, controlled reprovision токена на уже известный `device_id` и migration rebind legacy install-based token binding -> canonical `machine_id` |
| `server/websocket/agent_command_result.py` | Thin compatibility wrapper (deprecated-internal) |
| `server/websocket/command_result_components.py` | Компоненты command_result pipeline: normalizer/future/artifact/event publisher |
| `server/websocket/agent_outbox_ingest.py` | Thin compatibility wrapper (deprecated-internal) |
| `server/websocket/outbox_ingest_components.py` | Компоненты outbox pipeline: envelope validator, persistence c requester-name enrichment для `chat_message`, ACK/NACK decision, post-commit publish |
| `server/websocket/job_event_persistence.py` | Best-effort `persist_job_event` в `job_events` |
| `server/websocket/contexts.py` | Контексты `AgentConnectionContext`, `EnvelopeContext` |
| `server/websocket/ui_handler.py` | WS UI `/ws_ui`: ui_hello, run_tool, подписки |
| `server/websocket/protocol.py` | Отправка ACK/NACK/command, trace_id |
| `server/websocket/device_outbox_sender.py` | Dispatch runtime: `poll` и `sharded` (`DeviceReadyQueue`, shard workers, DB lease claim, reconcile) |
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
| `server/tech/handlers.py` | Техпанель `/api/admin/tech/*`: overview/alerts/logs, русифицированный аудит агентов/пользователей, drilldown по агенту (`/agents/{device_id}/timeline`), быстрые диагностические actions, lifecycle тикета (`milestone_rail`, `sla_lane`, ссылки ticket/device/operation), dismiss endpoint `/api/admin/tech/dismiss`, suppression шумных UI WebSocket alert и удаление log/alert из панели |
| `server/control_plane.py` | Внешний runtime API `/api/control/server/*`: status, full journal logs, download logs, lifecycle actions `start/stop/restart/smoke` |

### 2.2.1 Tools / единый путь run_tool
| Файл | Назначение |
|------|------------|
| `server/tools/service.py` | Канонический вход `ToolExecutionService.run_tool` (совместим с `ToolService`): pre-start event `tool_call_started`, отправка команды агенту |
| `server/tools/handlers.py` | HTTP handlers, которые делегируют run_tool в `ToolExecutionService`; `/api/tools/run` по умолчанию возвращает async `202 Accepted` + `operation_id` + `poll_url`, sync path допускается только через явный `wait=1` |
| `server/app/services/operation_service.py` | Ветка consent: `approve_consent()` переводит operation `waiting_consent -> queued` и enqueue `run_tool` в `device_outbox` (исполнение после явного approve) |
| `server/websocket/protocol.py` | Транспорт: `send_ws_command(..., wait_for_result=...)` enqueue в `device_outbox` + опционально ожидание `command_result` |

### 2.3 БД и репозитории
| Файл | Назначение |
|------|------------|
| `server/app/db/models.py` | SQLAlchemy модели (в т.ч. modules.manifest_json, validation_json) |
| `server/app/db/engine.py` | Async engine/session |
| `server/app/db/migrations/versions/*.py` | Alembic миграции |
| `server/app/repos/device_outbox_repo.py` | device_outbox (pending/sent/delivered) |
| `server/app/repos/device_events_repo.py` | События устройства |
| `server/app/repos/ticket_events_repo.py` | События тикета |
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

### 2.5 Доменные модули (handlers + service)
| Каталог/файл | Назначение |
|--------------|------------|
| `server/tickets/` | handlers, `create_flow.py`, service, assignment_service, sla_service, workflow_service, public_queue_handlers, public_ticket_handlers, admin_config_handlers и др.; `create_flow.py` держит единый DB-first путь создания для `/api/tickets/create`, WS `chat_raise` и legacy `/api/chat_raise`, а `assignment_service.py` и `ticket_events_repo.py` считают состав очереди обязательным для назначения и автоназначения; `handle_ticket_get` поддерживает forward catch-up (`since_event_id`) и reverse pagination (`before_event_id`, `limit`, `has_older`, `next_before_event_id`) для агентского ticket chat; `admin_config_handlers.py` ведёт helpdesk-admin settings API: очереди, состав очередей, routing rules, SLA policies, targets/matrix (GET/PUT), calendars, OLA targets, audit |
| `server/agents/` | handlers, agent_builds_handlers, service; `handlers.py` также даёт admin-only архивирование устройства с очисткой live runtime-сессии |
| `server/modules/` | handlers, service, reconcile, verification |
| `server/tools/` | handlers, service (каталог инструментов, manifest) |
| `server/chat/` | handlers, service |
| `server/jobs/` | handlers |
| `server/uploads/` | handlers |
| `server/auth/` | handlers, admin_users_handlers, connection_request_handlers (запросы на подключение устройств, включая `DEVICE_ARCHIVED` status/error_code для агента), middleware, service, `agent_token_service.py`, `connection_request_service.py`, password_service; `handlers.py` также содержит UI login/session endpoints |
| `server/playbook_handlers.py` | Старт playbook run |
| `server/static_pages/` | handlers для login/admin/support/ticket/public_queue/help и их CSS/JS shell-файлов, включая общий `web_shared.js` |

### 2.6 Утилиты (модули/manifest)
| Файл | Назначение |
|------|------------|
| `server/utils/module_manifest.py` | Manifest v2, нормализация, summary/detail |
| `server/utils/module_preflight.py` | Preflight ZIP, manifest_json, validation_json |
| `server/utils/module_builder.py` | Сборка пакета для POST /api/modules/create |
| `server/utils/module_storage.py` | Хранение модулей |
| `server/utils/tool_metadata_validation.py` | Валидация метаданных инструментов |
| `server/core/policy_engine.py` | Политики доступа |

### 2.7 UI (статика)
| Файл | Назначение |
|------|------------|
| `server/admin.html`, `server/admin.js`, `server/admin.css`, `server/web_shared.js` | Админка и shared web-shell helpers (`authHeaders`, `responseToJson`, `escapeHtml`, `parseServerDate`, `formatDate`) для admin/support/ticket |
| `server/control_plane.py`, `server/runtime_control.py` | Control-plane и runtime orchestration для техпанели: статус сервера (включая `started_at`/`uptime` из systemd и его timezone-offset timestamps вида `+05`), корректный `stop -> stopped/inactive` без ложного `failed`, health summary main API, полные логи (по умолчанию `Info+`), подтверждённые lifecycle actions с аудитом |
| `server/login.html`, `server/login.js`, `server/login.css` | Единая страница логина: выбор целевой роли (`admin` или `support`), POST `/api/ui_login` c `expected_role`, redirect в нужный shell |
| `server/support.html`, `server/support.js`, `server/support.css` | Отдельный support workspace: двухрежимный экран `Очередь тикетов` + `Рабочий тикет`; runtime теперь опирается на `web_shared.js` для общих auth/date/html helpers, чтобы не дублировать базовый shell-код. Переключатель режимов вынесен в верхний action-bar рядом с `Обновить / Выйти / Войти как admin`, чтобы оба режима воспринимались как единый workspace. В `Очереди тикетов` левый inbox скрывается, управление очередью собрано в компактную верхнюю панель (summary, фильтры, сортировка), а основной экран отдан широкой доске тикетов; левая колонка используется под действия по очереди и выбранному тикету. Карточки тикетов раскрывают `SLA / OLA / маршрут` и `Контекст и присутствие`. В `Рабочем тикете` левый inbox снова показывается, при этом фильтр `Мои` показывает только назначенные на текущего support-оператора тикеты, а фильтры `Нужны действия` и `Ждут пользователя` считаются только по своим тикетам. Для работы по тикету используются режимы preview/work/observe и встроенный ticket workbench (`Контекст`, `Инструменты`, `Пайплайн`). Для закрытия тикета использует встроенную форму кодов решения вместо prompt. Dev-only тестовая учётка support для локальных/browser проверок: `op1` / `1.Abcdef` (убрать перед production) |
| `server/ticket.html`, `server/ticket.js`, `server/ticket.css` | Основная рабочая область тикета: чат, reply-to баннер/ссылки на исходное сообщение, mark-read, подтверждение решения, редактирование профиля инициатора, очередь/исполнитель по составу очереди, SLA/OLA и ручной reroute по правилам; поддерживает `embed=1` для встраивания в support workspace и использует `web_shared.js` для базовых shell helpers |
| `server/public_queue.html`, `server/public_queue.js` | Публичная очередь со ссылками на requester-вход в тикет |
| `server/help.html`, `server/help.js`, `server/help.css` | Публичная страница requester: создание тикета, вход по коду, чат |
| `server/static_pages/` | Обработчики страниц и статики |

---

## 3. Быстрый поиск (ключевое слово → файлы)

Используйте поиск по документу, `docs/QUICK_LOOKUP.md` или `scripts/agent_find.py <ключевое_слово> --dir server`. Ниже — куда смотреть в первую очередь.

- **handshake** — `websocket/agent_handshake.py`, `websocket/agent_services.py`, `websocket/validator.py`, `docs/PROTOCOL_V3.md` (включая migration rebind legacy install-based token -> canonical `machine_id`)
- **outbox_ack, outbox_nack** — `websocket/agent_services.py`, `websocket/outbox_ingest_components.py`, `websocket/protocol.py`
- **run_tool** — `websocket/ui_handler.py`, `api/admin.py`, `tools/handlers.py`
- **device_outbox, DeviceOutboxSender** — `websocket/device_outbox_sender.py`, `app/repos/device_outbox_repo.py`, `config.py` (`DEVICE_DISPATCH_*`)
- **command_result** — `websocket/agent_services.py`, `websocket/command_result_components.py`, `websocket/command_result_parser.py`, `app/repos/operations_repo.py`
- **tool_call_started** — сервер создаёт до run_tool; идемпотентность: `docs/TOOL_CALL_STARTED_INVARIANT.md`
- **device_seq, agent_seq** — тип события только по ним; `websocket/validator.py`, `app/repos/device_events_repo.py`, `app/repos/ticket_events_repo.py`
- **ticket_events, device_events** — `api/events.py`, соответствующие repos
- **модули (install, desired, reconcile)** — `modules/handlers.py`, `modules/service.py`, `modules/reconcile.py`, `websocket/modules_sync.py`, `websocket/outbox_ingest_components.py`, `app/repos/device_desired_modules_repo.py`, `app/services/module_reconcile_scheduler.py`, `utils/module_manifest.py`, `utils/module_preflight.py`, `utils/module_builder.py`
- **playbook** — `playbook_handlers.py`, `app/services/playbook_engine.py`, `app/services/playbook_scheduler.py`, `app/repos/playbook_repo.py`
- **операции (consent, cancel, lifecycle)** — `api/operations.py`, `app/services/operation_service.py`, `app/services/operation_watchdog.py`, `app/repos/operations_repo.py`
- **тикеты (SLA, назначение, очереди, structured confirmation, public access, описание заявки)** — `tickets/handlers.py`, `tickets/assignment_service.py`, `tickets/sla_service.py`, `tickets/workflow_service.py`, `tickets/public_queue_handlers.py`, `tickets/public_ticket_handlers.py`, `tickets/public_access.py`, `auth/admin_users_handlers.py`
- **ticket snapshot / workbench payload** — `tickets/handlers.py` (`GET /api/tickets/{ticket_id}/snapshot`: relations, worklogs, watchers/links/kb, device/provisioning/update summary, latest operations, notification counters, device_metadata, OLA-блок, а также queue_members / assignable_users / available_queues / queue_auto_assign_enabled для основной рабочей области)
- **аутентификация, RBAC, login routing** — `auth/`, `auth/agent_token_service.py`, `routes.py`, `static_pages/handlers.py`, `docs/SECURITY_AND_AUTH.md`
- **миграции БД** — `app/db/migrations/versions/`, `docs/DATABASE.md`
- **обновление агента (builds, upload, update, mass, diagnostics, recommendation)** — `agents/agent_builds_handlers.py`, `agents/handlers.py`, `websocket/agent_handshake.py`, `docs/AGENT_UPDATES_API.md`, `../../pc_agent/docs/AGENT_UPDATE_WORKFLOW.md`, маршруты `POST /api/agent_builds/upload`, `POST /api/devices/{id}/agent/update`, `GET /api/devices/{id}/agent/update_recommendation`, `POST /api/agents/update_bulk`, `GET /api/devices/{id}/agent/update_diagnostics`
- **tech observability / tech panel** — `tech/handlers.py`, `tech/runtime_audit.py`, `tech/log_buffer.py`, `control_plane.py`, `runtime_control.py`, таблица `agent_runtime_audit`, маршруты `/api/admin/tech/*` и `/api/control/server/*` (overview, alerts, runtime health, full journal logs, lifecycle actions, audits)
- **device provisioning/update summary API** — `agents/handlers.py` (`GET /api/devices`, `GET /api/devices/{device_id}` возвращают `provisioning_summary`, `update_summary` и `identity_summary`)

---

## 4. Потоки выполнения

- **Agent → Server (Protocol V3):** агент подключается к `/ws`, handshake → outbox_item (ticket_event/device_event) → outbox_ack/outbox_nack.
- **Server → Agent:** команда в device_outbox → DeviceOutboxSender → WS → при command_result outbox помечается delivered/failed.
- **UI → Server:** `/ws_ui`, ui_hello → run_tool/API → операции и события в UI.
- **Helpdesk ticket flow:** создание тикета → routing/SLA/OLA → попытка auto-assign только внутри состава целевой очереди и только если у очереди включено автоназначение → статус `new` или `triaged` ("В очереди у оператора"); ручная смена очереди ставит routing lock, а ручной reroute и сохранение профиля инициатора с флагом reroute пересчитывают очередь по правилам и дополнительно приводят назначение к составу новой очереди (старый исполнитель снимается, затем возможен auto-assign по новой очереди); лимит оператора считается только по `in_progress`; `resolved` закрывается только после подтверждения requester, а его ответ из `waiting_on_user` возвращает тикет в очередь оператора.

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

При изменениях, затрагивающих структуру кода сервера, его **нужно** обновить (сводка критериев — `.cursor/rules/codemap.mdc`):

- добавление/удаление/перенос маршрутов (routes) или ключевых обработчиков;
- новые или переименованные ключевые каталоги/файлы в `server/`;
- новые точки входа или смена назначения существующих модулей.

Проверка: ключевые термины и файлы из раздела «Быстрый поиск» и «Структура каталогов» должны соответствовать коду.
