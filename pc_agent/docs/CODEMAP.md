# CODEMAP (pc_agent)

Карта кода `pc_client/pc_agent`. Используется для быстрой навигации и поиска (в т.ч. скрипт `scripts/agent_find.py` и контекст агента). Пути указаны относительно корня репозитория (например `pc_agent/ws_agent.py`).

---

## 0. Операционный старт

- Если задача начинается с diff, сначала выполните `python scripts/diff_context.py`.
- Если тема пересекает сервер и агент или неясно, где вход, откройте `docs/QUICK_LOOKUP.md`.
- Для точечного поиска по агенту используйте `python scripts/agent_find.py "<ключевое слово>" --dir pc_agent`.

| Сценарий | Открыть сначала | Затем |
|------|------------------|-------|
| Handshake / outbox / ACK | `pc_agent/ws_agent.py` | `pc_agent/core/sender.py`, `pc_agent/docs/PROTOCOL_V3.md` |
| `run_tool` / команды | `pc_agent/core/orchestrator.py` | `pc_agent/core/registry.py`, `server/tools/service.py` |
| Auth / bootstrap | `pc_agent/core/identity.py`, `pc_agent/core/machine_identity.py` | `pc_agent/auth/token_source.py`, `pc_agent/auth/connection_request.py`, `pc_agent/docs/AUTHENTICATION.md` |
| Self-update / launcher / rollout | `pc_agent/docs/AGENT_UPDATE_WORKFLOW.md` | `pc_agent/docs/SELF_UPDATE.md`, `pc_agent/launcher/installer.py`, `server/docs/AGENT_UPDATES_API.md` |
| Always-on / tray / runtime logs | `pc_agent/docs/AGENT_RUNTIME_ALWAYS_ON.md` | `pc_agent/ws_agent.py`, `pc_agent/core/runtime_logging.py`, `pc_agent/ui_gui/main.py`, `pc_agent/ui_gui/tray_manager.py` |
| GUI / `ui_bridge` | `pc_agent/ui_gui/main_window.py` | `pc_agent/ui_gui/chat_panel.py`, `pc_agent/ui_bridge/api_server.py`, `pc_agent/docs/AGENT_RUNTIME_ALWAYS_ON.md` |
| Модули / registry | `pc_agent/core/module_manager.py` | `pc_agent/core/loader.py`, `pc_agent/docs/MODULES.md` |

---

## 1. Точки входа

| Файл | Назначение |
|------|------------|
| `pc_agent/ws_agent.py` | Основной runtime: WS-соединение, handshake, команды, UI bridge; auth/connection orchestration (через state machine), Scheduler RPC + runtime loop; now runs as always-on process with sticky `connection_state`, runtime diagnostics/status/log tail callbacks для `ui_bridge`, а GUI закрытие больше не считается автоматическим shutdown |
| `pc_agent/launcher/launcher_main.py` | Launcher / запускные сценарии |
| `pc_agent/launcher_portable_main.py` | Портативный launcher |
| `pc_agent/ui_gui/main.py` | Запуск Qt GUI, lifecycle окна, minimize-to-tray, start-hidden, явный exit path и cleanup локальных SSE/API ресурсов |
| `pc_agent/build_windows_release_v2.py` | Каноническая Windows release-сборка: launcher.exe + versioned agent layout + update ZIP |

---

## 2. Структура каталогов (ключевые файлы)

### 2.1 Ядро (core/)
| Файл | Назначение |
|------|------------|
| `pc_agent/core/orchestrator.py` | Обработка команд: run_tool, collect/list/update, lifecycle операций, orchestration над `ConsentService`, кэш модулей |
| `pc_agent/core/consent_service.py` | Отдельный lifecycle consent (`WAITING_USER/APPROVED/REJECTED/EXPIRED`) поверх `pending_consents` |
| `pc_agent/core/database.py` | SQLite (data/storage.db), outbox, seq, idempotency, consent, scheduled_tasks, DB_SCHEMA_VERSION |
| `pc_agent/core/sender.py` | WSOutboxFlusher: доставка outbox, ACK/NACK, retries |
| `pc_agent/core/identity.py` | Каноническая identity агента: `machine_id` -> `device_id`, вторичный `install_id`, миграция legacy `identity.json`, handshake metadata |
| `pc_agent/core/machine_identity.py` | Разрешение стабильного `machine_id` из OS/runtime (Windows MachineGuid, Linux machine-id, env override, fallback file) |
| `pc_agent/core/module_manager.py` | Установка/удаление/rollback модулей, semver, инвентарь |
| `pc_agent/core/loader.py` | load_module_from_path (modules_store), сброс кэша импорта |
| `pc_agent/core/registry.py` | Дескрипторы инструментов, alias→method, call_tool() |
| `pc_agent/core/tools.py` | Инструментальная подсистема (каталог для сервера) |
| `pc_agent/core/policy_engine.py` | Политики выполнения |
| `pc_agent/core/artifacts.py` | Артефакты (screenshot/record) |
| `pc_agent/core/recording_controller.py` | Управление записью |
| `pc_agent/core/job_manager.py` | Джобы |
| `pc_agent/core/runtime_logging.py` | Единая настройка runtime-логирования: loguru sink, rotation/retention/compression, чтение tail для diagnostics |
| `pc_agent/core/runtime_paths.py` | Пути данных/модулей |
| `pc_agent/core/single_instance.py` | Один экземпляр приложения |

### 2.2 Модули (modules/)
| Файл/каталог | Назначение |
|--------------|------------|
| `pc_agent/modules/base_module.py` | Базовый контракт модуля |
| `pc_agent/modules/impl/` | Встроенные реализации модулей |
| `pc_agent/modules/dynamic/` | Legacy (загрузчик использует только пакеты из modules_store) |
| `pc_agent/modules/__init__.py` | extra_paths, поддержка test_<name> для тестов |

### 2.3 Сеть и загрузки
| Файл | Назначение |
|------|------------|
| `pc_agent/network/uploader.py` | Загрузка файлов/артефактов на сервер |

### 2.3.1 Аутентификация и bootstrap подключения
| Файл | Назначение |
|------|------------|
| `pc_agent/auth/token_source.py` | Источник токена: `AUTH_TOKEN` → `auth_tokens` → optional GUI callback |
| `pc_agent/auth/connection_request.py` | Connection-request flow: POST/GET polling, approve/reject и события в event_bus |
| `pc_agent/auth/gui_auth_state_machine.py` | Явные состояния GUI-авторизации (`NoToken -> RequestSent -> Polling -> TokenReady/WsConnecting`) |
| `pc_agent/auth/rejected_flag.py` | Путь к локальному флагу `connection_rejected.flag` |

### 2.4 UI bridge (core ↔ GUI)
| Файл | Назначение |
|------|------------|
| `pc_agent/ui_bridge/api_server.py` | Локальный API для GUI (SSE/HTTP), settings + local agent control/diagnostics (`/ui/agent/status`, `/ui/agent/logs`, `/ui/agent/shutdown`) |
| `pc_agent/ui_bridge/event_bus.py` | События между core и GUI; хранит sticky `connection_state` для поздних SSE-подписчиков |
| `pc_agent/ui_bridge/models.py` | Модели данных для UI |
| `pc_agent/ui_bridge/settings_service.py` | Настройки для GUI |

### 2.5 GUI (Qt)
| Файл | Назначение |
|------|------------|
| `pc_agent/ui_gui/main_window.py` | Главное окно (splitter: панель профиля + тикеты), настройки и статусы, секция always-on/tray/logging diagnostics |
| `pc_agent/ui_gui/chat_panel.py` | Чат, создание тикета, reply-to, mark-read, локальные профили инициатора; detail refresh разделён на initial tail load, forward catch-up через `since_event_id` и reverse pagination вверх через `before_event_id`, с prepend history и сохранением viewport; список тикетов на `QListView` + модель |
| `pc_agent/ui_gui/tickets_list_model.py` | `TicketsListModel` и `TicketCardDelegate` — обновление строк без полного `clear()`, отрисовка карточек |
| `pc_agent/ui_gui/ticket_format.py` | Подписи/цвета статусов, формат дат, отпечаток строки тикета для диффа модели |
| `pc_agent/ui_gui/theme.py` | Общая тёплая палитра и QSS-фрагменты для `ChatPanel` и боковой панели профиля |
| `pc_agent/ui_gui/server_api.py` | Обращение к серверу из GUI, отправка `reply_to`/message metadata, вызов `mark_ticket_read()` и ticket history API с `get_ticket(..., since_event_id=..., before_event_id=..., limit=...)` |
| `pc_agent/ui_gui/sse_client.py` | SSE-клиент к ui_bridge |
| `pc_agent/ui_gui/tray_manager.py` | Тонкая cross-platform обёртка над `QSystemTrayIcon`: открыть окно, открыть логи, restart agent, exit agent |
| `pc_agent/ui_gui/consent_dialog.py` | Диалог согласия на операцию |
| `pc_agent/ui_gui/token_dialog.py` | Диалог токена |

### 2.6 Конфигурация
| Файл | Назначение |
|------|------------|
| `pc_agent/config/config_loader.py` | Загрузка настроек |
| `pc_agent/config/settings.yaml`, `settings.default.yaml` | Конфиг |

### 2.7 Скрипты и тесты
| Путь | Назначение |
|------|------------|
| `pc_agent/scripts/smoke_check_module.py` | Проверка модуля (tool names, resolved methods) |
| `pc_agent/tests/` | Unit/integration тесты |

---

## 3. Быстрый поиск (ключевое слово → файлы)

Используйте поиск по документу, `docs/QUICK_LOOKUP.md` или `scripts/agent_find.py <ключевое_слово> --dir pc_agent`. Ниже — куда смотреть в первую очередь.

- **handshake, protocol_version, ws_ticket_v3** — `ws_agent.py`, `docs/PROTOCOL_V3.md`
- **outbox, outbox_ack, ACK/NACK** — `core/sender.py`, `core/database.py`, `docs/SENDER.md`
- **run_tool, command** — `core/orchestrator.py`, обработка command/envelope V3 в `ws_agent.py`
- **schedule_task, cancel_task, list_tasks, task_run_now** — `ws_agent.py` (Scheduler RPC), `core/database.py` (scheduled_tasks storage)
- **device_seq, agent_seq** — тип события только по ним; outbox в `core/database.py`
- **модули (загрузка, registry, rollback)** — `core/module_manager.py`, `core/loader.py`, `core/registry.py`, `core/orchestrator.py` (cached context, rebuild), `modules/__init__.py`
- **инструменты (list_tools, call_tool)** — `core/registry.py`, `core/tools.py`, `core/orchestrator.py`
- **consent, pending_consents** — `core/consent_service.py`, `core/database.py`, `core/orchestrator.py`, `ui_gui/consent_dialog.py`
- **аутентификация, machine_id, install_id, токен** — `core/identity.py`, `core/machine_identity.py`, `auth/token_source.py`, `docs/AUTHENTICATION.md` (не логировать сырой токен)
- **always-on, tray, runtime logs, локальный shutdown/status/logs** — `docs/AGENT_RUNTIME_ALWAYS_ON.md`, `ws_agent.py`, `core/runtime_logging.py`, `ui_gui/main.py`, `ui_gui/tray_manager.py`, `ui_bridge/api_server.py`
- **reprovision_required / invalid token** — `ws_agent.py` (`_request_token_from_console` теперь запускает auto reprovision через `connection_request` flow без ручного ввода)
- **артефакты, upload** — `core/artifacts.py`, `core/recording_controller.py`, `network/uploader.py`
- **self-update, pending_update, update_history, launcher rollback** — `docs/AGENT_UPDATE_WORKFLOW.md`, `docs/SELF_UPDATE.md`, `launcher/installer.py`, `build_windows_release_v2.py`
- **GUI, SSE, UI bridge, профили инициатора** — `ui_gui/*`, `ui_bridge/*`
- **SQLite, миграции схемы** — `core/database.py` (DB_SCHEMA_VERSION), `docs/DATABASE.md`

---

## 4. Потоки выполнения

- **Boot:** ws_agent.py → IdentityManager, DatabaseManager, AgentOrchestrator, загрузка модулей → WSOutboxFlusher, UI bridge.
- **Agent → Server:** события в outbox → WSOutboxFlusher → WS → outbox_ack (удаление записи) / outbox_nack (retry).
- **Server → Agent:** command по WS → оркестратор (run_tool/module/job) → результат и события в outbox.

---

## 5. Хранилище и миграции

- SQLite: `pc_agent/data/storage.db`. Версия схемы: `core/database.py` (DB_SCHEMA_VERSION). Таблицы: outbox, seq_ticket, seq_device, seen_commands, pending_consents, auth_tokens, scheduled_tasks. См. `docs/DATABASE.md`, `docs/SENDER.md`.

---

## 6. Инварианты

- Protocol version на handshake: `ws_ticket_v3`. Тип события только по device_seq/agent_seq. ACK для outbox = удаление записи. Не логировать сырой токен. Детали: корневой `AGENTS.md`, `docs/PROTOCOL_V3.md`.

---

## 7. Когда обновлять этот CODEMAP

Каноническая карта агента — этот файл: `pc_agent/docs/CODEMAP.md` (других CODEMAP для дерева `pc_agent/` нет).

При изменениях, затрагивающих структуру кода агента, его **нужно** обновить (сводка критериев — `.cursor/rules/codemap.mdc`):

- добавление/удаление/перенос ключевых модулей или точек входа в `pc_agent/`;
- новые или переименованные ключевые файлы в core/, modules/, ui_gui/, ui_bridge/;
- смена назначения существующих модулей или потоков.

Проверка: ключевые термины и файлы из раздела «Быстрый поиск» и «Структура каталогов» должны соответствовать коду.
