# CODEMAP (pc_agent)

Карта кода `pc_client/pc_agent`. Используется для быстрой навигации и поиска (в т.ч. скрипт `scripts/agent_find.py` и контекст агента). Пути указаны относительно корня репозитория (например `pc_agent/ws_agent.py`).

---

## 1. Точки входа

| Файл | Назначение |
|------|------------|
| `pc_agent/ws_agent.py` | Основной runtime: WS-соединение, handshake, команды, UI bridge; auth/connection orchestration (через state machine), Scheduler RPC + runtime loop |
| `pc_agent/launcher/launcher_main.py` | Launcher / запускные сценарии |
| `pc_agent/launcher_portable_main.py` | Портативный launcher |
| `pc_agent/ui_gui/main.py` | Запуск Qt GUI |

---

## 2. Структура каталогов (ключевые файлы)

### 2.1 Ядро (core/)
| Файл | Назначение |
|------|------------|
| `pc_agent/core/orchestrator.py` | Обработка команд: run_tool, collect/list/update, lifecycle операций, orchestration над `ConsentService`, кэш модулей |
| `pc_agent/core/consent_service.py` | Отдельный lifecycle consent (`WAITING_USER/APPROVED/REJECTED/EXPIRED`) поверх `pending_consents` |
| `pc_agent/core/database.py` | SQLite (data/storage.db), outbox, seq, idempotency, consent, scheduled_tasks, DB_SCHEMA_VERSION |
| `pc_agent/core/sender.py` | WSOutboxFlusher: доставка outbox, ACK/NACK, retries |
| `pc_agent/core/identity.py` | device_id, AUTH_TOKEN, auth_tokens, legacy |
| `pc_agent/core/module_manager.py` | Установка/удаление/rollback модулей, semver, инвентарь |
| `pc_agent/core/loader.py` | load_module_from_path (modules_store), сброс кэша импорта |
| `pc_agent/core/registry.py` | Дескрипторы инструментов, alias→method, call_tool() |
| `pc_agent/core/tools.py` | Инструментальная подсистема (каталог для сервера) |
| `pc_agent/core/policy_engine.py` | Политики выполнения |
| `pc_agent/core/artifacts.py` | Артефакты (screenshot/record) |
| `pc_agent/core/recording_controller.py` | Управление записью |
| `pc_agent/core/job_manager.py` | Джобы |
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
| `pc_agent/ui_bridge/api_server.py` | Локальный API для GUI (SSE/HTTP) |
| `pc_agent/ui_bridge/event_bus.py` | События между core и GUI |
| `pc_agent/ui_bridge/models.py` | Модели данных для UI |
| `pc_agent/ui_bridge/settings_service.py` | Настройки для GUI |

### 2.5 GUI (Qt)
| Файл | Назначение |
|------|------------|
| `pc_agent/ui_gui/main_window.py` | Главное окно, настройки и вход в управление профилями инициатора |
| `pc_agent/ui_gui/chat_panel.py` | Чат, создание тикета, локальные профили инициатора, прочтение тикетов, in-chat подтверждения |
| `pc_agent/ui_gui/server_api.py` | Обращение к серверу из GUI, отправка message metadata |
| `pc_agent/ui_gui/sse_client.py` | SSE-клиент к ui_bridge |
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

Используйте поиск по документу или `scripts/agent_find.py <ключевое_слово> --dir pc_agent`. Ниже — куда смотреть в первую очередь.

- **handshake, protocol_version, ws_ticket_v3** — `ws_agent.py`, `docs/PROTOCOL_V3.md`
- **outbox, outbox_ack, ACK/NACK** — `core/sender.py`, `core/database.py`, `docs/SENDER.md`
- **run_tool, command** — `core/orchestrator.py`, обработка command/envelope V3 в `ws_agent.py`
- **schedule_task, cancel_task, list_tasks, task_run_now** — `ws_agent.py` (Scheduler RPC), `core/database.py` (scheduled_tasks storage)
- **device_seq, agent_seq** — тип события только по ним; outbox в `core/database.py`
- **модули (загрузка, registry, rollback)** — `core/module_manager.py`, `core/loader.py`, `core/registry.py`, `core/orchestrator.py` (cached context, rebuild), `modules/__init__.py`
- **инструменты (list_tools, call_tool)** — `core/registry.py`, `core/tools.py`, `core/orchestrator.py`
- **consent, pending_consents** — `core/consent_service.py`, `core/database.py`, `core/orchestrator.py`, `ui_gui/consent_dialog.py`
- **аутентификация, токен** — `core/identity.py`, `docs/AUTHENTICATION.md` (не логировать сырой токен)
- **артефакты, upload** — `core/artifacts.py`, `core/recording_controller.py`, `network/uploader.py`
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

При изменениях, затрагивающих структуру кода агента, этот файл **нужно** обновить (см. правило в `.cursor/rules/codemap.mdc`):

- добавление/удаление/перенос ключевых модулей или точек входа в `pc_agent/`;
- новые или переименованные ключевые файлы в core/, modules/, ui_gui/, ui_bridge/;
- смена назначения существующих модулей или потоков.

Проверка: ключевые термины и файлы из раздела «Быстрый поиск» и «Структура каталогов» должны соответствовать коду.
