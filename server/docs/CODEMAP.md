# CODEMAP (server)

Карта кода `pc_client/server`. Используется для быстрой навигации и поиска (в т.ч. скрипт `scripts/agent_find.py` и контекст агента). Пути указаны относительно корня репозитория (например `server/routes.py`).

---

## 1. Точки входа

| Файл | Назначение |
|------|------------|
| `server/server.py` | Запуск aiohttp, startup/shutdown, watchdog/scheduler |
| `server/routes.py` | Регистрация всех HTTP и WS маршрутов |
| `server/config.py` | Конфигурация, feature flags, таймауты SLA/operations/playbook |

---

## 2. Структура каталогов (ключевые файлы)

### 2.1 WebSocket
| Файл | Назначение |
|------|------------|
| `server/websocket/agent_handler.py` | WS агентов `/ws`: transport-only loop (decode/route/flush/close) |
| `server/websocket/agent_services.py` | `AgentMessageRouter` + сервисы handshake/ack/result/outbox/agent-command |
| `server/websocket/contexts.py` | Контексты `AgentConnectionContext`, `EnvelopeContext` |
| `server/websocket/ui_handler.py` | WS UI `/ws_ui`: ui_hello, run_tool, подписки |
| `server/websocket/protocol.py` | Отправка ACK/NACK/command, trace_id |
| `server/websocket/device_outbox_sender.py` | Dispatch runtime: `poll` и `sharded` (`DeviceReadyQueue`, shard workers, reconcile) |
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

### 2.2.1 Tools / единый путь run_tool
| Файл | Назначение |
|------|------------|
| `server/tools/service.py` | Канонический вход `ToolExecutionService.run_tool` (совместим с `ToolService`): pre-start event `tool_call_started`, отправка команды агенту |
| `server/tools/handlers.py` | HTTP handlers, которые делегируют run_tool в `ToolExecutionService` |
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
| `server/app/repos/auth_tokens_repo.py` | Токены устройств/UI и public-session токены requester-доступа |
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
| `server/tickets/` | handlers, service, assignment_service, sla_service, workflow_service, public_queue_handlers, public_ticket_handlers, admin_config_handlers и др. |
| `server/agents/` | handlers, agent_builds_handlers, service |
| `server/modules/` | handlers, service, reconcile, verification |
| `server/tools/` | handlers, service (каталог инструментов, manifest) |
| `server/chat/` | handlers, service |
| `server/jobs/` | handlers |
| `server/uploads/` | handlers |
| `server/auth/` | handlers, admin_users_handlers, connection_request_handlers (запросы на подключение устройств), middleware, service, password_service |
| `server/playbook_handlers.py` | Старт playbook run |
| `server/static_pages/` | handlers для admin, ticket, public_queue, CSS/JS |

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
| `server/admin.html`, `server/admin.js`, `server/admin.css` | Админка (модули, устройства, run_tool, bind тикета к агенту) |
| `server/ticket.html`, `server/ticket.js`, `server/ticket.css` | Страница тикета: чат, описание заявки, привязка к агенту, подтверждение решения |
| `server/public_queue.html`, `server/public_queue.js` | Публичная очередь со ссылками на requester-вход в тикет |
| `server/help.html`, `server/help.js`, `server/help.css` | Публичная страница requester: создание тикета, вход по коду, чат |
| `server/static_pages/` | Обработчики страниц и статики |

---

## 3. Быстрый поиск (ключевое слово → файлы)

Используйте поиск по документу или `scripts/agent_find.py <ключевое_слово> --dir server`. Ниже — куда смотреть в первую очередь.

- **handshake** — `websocket/agent_services.py`, `websocket/agent_handler.py`, `websocket/validator.py`, `docs/PROTOCOL_V3.md`
- **outbox_ack, outbox_nack** — `websocket/agent_handler.py`, `websocket/protocol.py`
- **run_tool** — `websocket/ui_handler.py`, `api/admin.py`, `tools/handlers.py`
- **device_outbox, DeviceOutboxSender** — `websocket/device_outbox_sender.py`, `app/repos/device_outbox_repo.py`, `config.py` (`DEVICE_DISPATCH_*`)
- **command_result** — `websocket/agent_services.py`, `websocket/command_result_parser.py`, `app/repos/operations_repo.py`
- **tool_call_started** — сервер создаёт до run_tool; идемпотентность: `docs/TOOL_CALL_STARTED_INVARIANT.md`
- **device_seq, agent_seq** — тип события только по ним; `websocket/validator.py`, `app/repos/device_events_repo.py`, `app/repos/ticket_events_repo.py`
- **ticket_events, device_events** — `api/events.py`, соответствующие repos
- **модули (install, desired, reconcile)** — `modules/handlers.py`, `modules/service.py`, `modules/reconcile.py`, `websocket/modules_sync.py`, `app/repos/device_desired_modules_repo.py`, `app/services/module_reconcile_scheduler.py`, `utils/module_manifest.py`, `utils/module_preflight.py`, `utils/module_builder.py`
- **playbook** — `playbook_handlers.py`, `app/services/playbook_engine.py`, `app/services/playbook_scheduler.py`, `app/repos/playbook_repo.py`
- **операции (consent, cancel, lifecycle)** — `api/operations.py`, `app/services/operation_service.py`, `app/services/operation_watchdog.py`, `app/repos/operations_repo.py`
- **тикеты (SLA, назначение, очереди, structured confirmation, public access, описание заявки)** — `tickets/handlers.py`, `tickets/assignment_service.py`, `tickets/sla_service.py`, `tickets/workflow_service.py`, `tickets/public_queue_handlers.py`, `tickets/public_ticket_handlers.py`, `tickets/public_access.py`, `auth/admin_users_handlers.py`
- **аутентификация, RBAC** — `auth/`, `docs/SECURITY_AND_AUTH.md`
- **миграции БД** — `app/db/migrations/versions/`, `docs/DATABASE.md`
- **обновление агента (builds, upload, update, mass)** — `agents/agent_builds_handlers.py`, `docs/AGENT_UPDATES_API.md`, маршруты `POST /api/agent_builds/upload`, `POST /api/devices/{id}/agent/update`, `POST /api/agents/update_bulk`

---

## 4. Потоки выполнения

- **Agent → Server (Protocol V3):** агент подключается к `/ws`, handshake → outbox_item (ticket_event/device_event) → outbox_ack/outbox_nack.
- **Server → Agent:** команда в device_outbox → DeviceOutboxSender → WS → при command_result outbox помечается delivered/failed.
- **UI → Server:** `/ws_ui`, ui_hello → run_tool/API → операции и события в UI.
- **Helpdesk ticket flow:** создание тикета → routing/SLA → попытка auto-assign → статус `new` или `triaged` ("В очереди у оператора"); лимит оператора считается только по `in_progress`; `resolved` закрывается только после подтверждения requester, а его ответ из `waiting_on_user` возвращает тикет в очередь оператора.

---

## 5. БД и миграции

- PostgreSQL. Миграции: `server/app/db/migrations/versions/`. Команда: из каталога `server` — `alembic upgrade head`. См. `docs/DATABASE.md`, `docs/COMMAND_RESULT_LIFECYCLE.md`.

---

## 6. Тесты и скрипты

- `server/tests/` — интеграционные/регрессионные тесты.
- Корень проекта: `scripts/run_server.py`, `scripts/stop_server.py`, `scripts/restart_server.py`, `scripts/smoke_test.py`, `scripts/admin_run_tool.py`.
- `server/scripts/` — `run_subagents.py`, `subagent_worker_server.py`, `subagent_worker_agent.py`.

---

## 7. Инварианты

- Тип события только по `device_seq` vs `agent_seq`. `tool_call_started` создаётся на сервере до run_tool, идемпотентен. Не логировать сырой токен. Детали: `AGENTS.md`, `docs/PROTOCOL_V3.md`.

---

## 8. Когда обновлять этот CODEMAP

При изменениях, затрагивающих структуру кода сервера, этот файл **нужно** обновить (см. правило в `.cursor/rules/codemap.mdc`):

- добавление/удаление/перенос маршрутов (routes) или ключевых обработчиков;
- новые или переименованные ключевые каталоги/файлы в `server/`;
- новые точки входа или смена назначения существующих модулей.

Проверка: ключевые термины и файлы из раздела «Быстрый поиск» и «Структура каталогов» должны соответствовать коду.
